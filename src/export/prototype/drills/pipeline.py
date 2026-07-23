"""Orquestación end-to-end del prototipo de exportación de Drills:

    SQL -> extracción -> transformación -> mapping -> validación -> CSV

No es un Export Engine genérico: conoce explícitamente los 8 campos de
`config/exports/drills.yaml` -- una versión reutilizable para otros objetos
es trabajo futuro, fuera del alcance de este incremento (ver
`docs/specifications/v1.0/export/closing_recommendation.md`).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import PROJECT_ROOT

from . import comparison as comparison_mod
from . import mappings as mappings_mod
from . import transformations as tr
from .config import DrillsExportConfig, load_drills_config
from .exporter import write_csv
from .extractor import MODE_FULL, MODE_SAMPLE, extract_drills
from .manifest import (
    RunStats,
    build_export_manifest,
    write_export_manifest,
    write_validation_report,
    write_yaml_atomic,
)
from .validator import (
    check_duplicate_references,
    validate_output_csv,
    validate_pre_write,
)

logger = logging.getLogger(__name__)

# Orden de columnas del CSV generado -- decisión propia de este prototipo,
# no una copia del orden del CSV histórico (que incluye columnas fuera de
# alcance, ver `excluded_columns` en config/exports/drills.yaml).
OUTPUT_COLUMNS = [
    "CS_Typology",
    "Reference",
    "StartingDate",
    "CS_HistoricalOriginID",
    "CS_Letter",
    "CS_ImpactedEntities",
    "CS_WorkflowStatus",
    "CS_HistoricalDataOrigin",
]

HISTORICAL_CSV_PATH = (
    "inputs/_incoming_claude_web/Bloque4_CSV_Enablon/Drills-22072026-41.csv"
)


@dataclass
class PipelineResult:
    run_id: str
    output_dir: Path
    csv_path: Path
    validation_report_path: Path
    manifest_path: Path
    comparison_report_path: Path | None
    stats: RunStats
    validation_report: dict
    manifest: dict
    excluded_rows: list[dict]


def _empty(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _serialize(value) -> str:
    return "" if value is None else str(value)


def _transform_rows(
    df: pd.DataFrame,
    config: DrillsExportConfig,
    stats: RunStats,
) -> tuple[list[dict], list[dict]]:
    """Devuelve (filas_incluidas_en_csv, filas_excluidas_con_motivo).

    Cada fila fuente se procesa exactamente una vez -- nunca se descarta en
    silencio: toda fila que no llega al CSV queda en `excluded`.
    """
    reference_data = config.reference_data
    entity_catalog = mappings_mod.get_entity_catalog(
        reference_data["entity_catalog_csv"],
        key_column=reference_data.get("entity_catalog_key_column", "IDUnidadOrg"),
        value_column=reference_data.get("entity_catalog_value_column", "Code"),
        do_not_migrate_literal=reference_data.get("entity_catalog_do_not_migrate_literal", "No migra"),
    )
    typology_lookup = dict(reference_data["typology_lookup"])
    typology_default = reference_data["typology_default_no_match"]
    letter_lookup = dict(reference_data["letter_lookup"])
    letter_null_default = reference_data["letter_null_default"]
    workflow_lookup = dict(reference_data["workflow_status_lookup"])
    historical_data_origin = reference_data["historical_data_origin_literal"]

    included: list[dict] = []
    excluded: list[dict] = []
    reference_values_for_dup_check: list[str] = []

    for _, row in df.iterrows():
        stats.rows_read += 1
        stats.rows_transformed += 1

        typology_result = tr.resolve_typology(row.get("IDTipo"), typology_lookup, typology_default)
        historical_id = tr.to_historical_id(row.get("IDSimulacro"))

        raw_fecha = row.get("Fecha")
        starting_date = tr.parse_starting_date(raw_fecha)
        if _empty(raw_fecha):
            stats.dates_empty += 1
        elif starting_date is None:
            stats.dates_invalid += 1
        else:
            stats.dates_valid += 1

        reference_result = tr.build_reference(typology_result.value, historical_id, starting_date)

        letter_result = tr.resolve_letter(row.get("IDLetra"), letter_lookup, letter_null_default)
        if letter_result.status == "unresolved":
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: IDLetra "
                f"{letter_result.raw_source_value!r} sin coincidencia en letter_lookup."
            )

        workflow_result = tr.resolve_workflow_status(row.get("Estado"), workflow_lookup)
        if workflow_result.status == "unresolved":
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: Estado "
                f"{workflow_result.raw_source_value!r} sin coincidencia en workflow_status_lookup."
            )

        entity_result = mappings_mod.resolve_entity(row.get("IDUnidadOrg"), entity_catalog)
        if entity_result.status == mappings_mod.RESOLVED:
            stats.entities_resolved += 1
        elif entity_result.status == mappings_mod.DO_NOT_MIGRATE:
            stats.entities_do_not_migrate += 1
        elif entity_result.status == mappings_mod.UNRESOLVED:
            stats.entities_unresolved += 1
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: IDUnidadOrg "
                f"{entity_result.raw_source_value!r} no está en el catálogo de entidad."
            )
        elif entity_result.status == mappings_mod.CONFLICTING:
            stats.entities_conflicting += 1
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: IDUnidadOrg "
                f"{entity_result.raw_source_value!r} tiene más de un Code distinto en el catálogo."
            )
        else:
            stats.entities_empty += 1

        row_dict = {
            "CS_Typology": typology_result.value,
            "Reference": reference_result.value,
            "StartingDate": tr.format_starting_date(starting_date) if starting_date else None,
            "CS_HistoricalOriginID": historical_id,
            "CS_Letter": letter_result.value,
            "CS_ImpactedEntities": entity_result.value,
            "CS_WorkflowStatus": workflow_result.value,
            "CS_HistoricalDataOrigin": historical_data_origin,
        }

        if reference_result.is_valid:
            stats.reference_valid += 1
            reference_values_for_dup_check.append(reference_result.value)
            included.append({k: _serialize(v) for k, v in row_dict.items()})
        else:
            stats.reference_invalid += 1
            stats.rows_excluded += 1
            if "missing_typology" in reference_result.missing_components:
                stats.missing_typology += 1
            if "missing_historical_origin_id" in reference_result.missing_components:
                stats.missing_historical_origin_id += 1
            if "missing_starting_date" in reference_result.missing_components:
                stats.missing_starting_date += 1
            excluded.append({
                **{k: _serialize(v) for k, v in row_dict.items()},
                "exclusion_reason": ",".join(reference_result.missing_components),
            })

    stats.duplicate_references = check_duplicate_references(reference_values_for_dup_check)
    if stats.duplicate_references:
        stats.warnings.append(
            f"{stats.duplicate_references} fila(s) comparten un valor de Reference con otra fila."
        )

    return included, excluded


def run(
    mode: str = MODE_SAMPLE,
    limit: int = 100,
    output_root: str | Path | None = None,
) -> PipelineResult:
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo no soportado: {mode!r}")

    run_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    config = load_drills_config()

    output_root = Path(output_root) if output_root else (PROJECT_ROOT / "outputs" / "prototype" / "drills")
    output_dir = output_root / timestamp
    if output_dir.exists():
        raise FileExistsError(f"El directorio de salida ya existe, no se reutiliza: {output_dir}")

    stats = RunStats(run_id=run_id, timestamp=timestamp, mode=mode, connection_name=config.source.connection)

    logger.info(
        "Iniciando export drills (run_id=%s, modo=%s, conexion=%s, salida=%s)",
        run_id, mode, config.source.connection, output_dir,
    )

    extraction = extract_drills(config, mode=mode, limit=limit)

    pre_check = validate_pre_write(extraction.dataframe, config)
    if not pre_check.is_valid:
        stats.errors.extend(pre_check.issues)
        stats.rows_transformed = 0
        report = write_validation_report(stats, output_dir / "validation_report.yaml")
        raise RuntimeError(
            f"Validación previa a la escritura falló, no se generó CSV: {pre_check.issues}"
        )
    stats.warnings.extend(pre_check.warnings)

    included_rows, excluded_rows = _transform_rows(extraction.dataframe, config, stats)
    stats.rows_exported = len(included_rows)

    csv_path = output_dir / config.output.filename
    write_csv(included_rows, OUTPUT_COLUMNS, csv_path, config.output)

    post_check = validate_output_csv(
        csv_path, config, expected_columns=OUTPUT_COLUMNS, expected_row_count=len(included_rows)
    )
    stats.errors.extend(post_check.issues)
    stats.warnings.extend(post_check.warnings)

    try:
        stats.output_path = str(csv_path.relative_to(PROJECT_ROOT))
    except ValueError:
        # `output_root` puede apuntar fuera del repositorio (p. ej. un
        # directorio temporal de test de integración) -- se registra la
        # ruta absoluta en ese caso, en vez de fallar.
        stats.output_path = str(csv_path)
    stats.output_encoding = config.output.encoding
    stats.output_bom = config.output.bom
    stats.output_delimiter = config.output.delimiter
    stats.output_line_terminator = repr(config.output.line_terminator)[1:-1]
    stats.output_column_count = post_check.column_count or len(OUTPUT_COLUMNS)
    stats.output_columns = post_check.columns or OUTPUT_COLUMNS

    validation_report_path = output_dir / "validation_report.yaml"
    validation_report = write_validation_report(stats, validation_report_path)

    evidence_ids = sorted({f.evidence_id for f in config.fields})
    limitations = [
        "Prototipo limitado a 8 columnas del objeto Drills (36 en el CSV real de Enablon) -- ver excluded_columns en config/exports/drills.yaml.",
        "CS_Letter y CS_WorkflowStatus sin default confirmado para valores no listados quedan `unresolved` (columna vacía), no se inventa un valor.",
        f"Modo '{mode}': " + (
            f"la consulta original se ejecuta completa y se trunca localmente a {limit} filas (las más antiguas por FechaCreacion)."
            if mode == MODE_SAMPLE else
            "se exportan todas las filas devueltas por la consulta, sujeto a max_rows_per_query de config/databases.yaml."
        ),
        "HALLAZGO (confirmado contra SQL Server real y el CSV histórico en este incremento): "
        "'StartingDate' se deriva solo de 'Fecha', que en la base de datos real suele tener la "
        "hora truncada a 00:00 -- la hora real del simulacro vive en la columna separada 'Hora' "
        "(varchar(5)), ya seleccionada por la SQL de origen pero sin usar. La propia consulta "
        "reserva una columna vacía 'FechaHoraCombinado' para esta combinación, nunca implementada. "
        "No se ha adivinado la regla exacta de combinación -- StartingDate queda con la hora "
        "truncada hasta que se confirme. No afecta a 'Reference' (usa solo la fecha, sin hora).",
        "HALLAZGO (confirmado por comparación cuantitativa contra el CSV histórico en este "
        "incremento): 'CS_ImpactedEntities' coincide en 9 de 19 filas comparables de la muestra "
        "-- el resto resuelve a un código hermano bajo la misma rama (p. ej. 'EPLR.FAB.P04-MMH' "
        "generado vs 'EPLR.FAB.P04' histórico). Consistente con OQ-ENT-04 (catálogo deprecado, "
        "sin confirmación de que siga siendo fiel entidad por entidad). Ver comparison_report.yaml "
        "de esta ejecución para el detalle exacto.",
    ]
    open_questions = ["OQ-ETL-05", "OQ-ETL-06", "OQ-ENT-04", "OQ-ETL-02", "OQ-OBJ-07", "OQ-ETL-07-NEW-FECHA-HORA"]

    manifest = build_export_manifest(
        run_id=run_id,
        timestamp=timestamp,
        config_raw=config.raw,
        sql_text=extraction.sql_text,
        csv_path=csv_path,
        row_count=len(included_rows),
        columns=OUTPUT_COLUMNS,
        connection_name=config.source.connection,
        mode=mode,
        evidence_ids=evidence_ids,
        limitations=limitations,
        open_questions=open_questions,
        sql_source_evidence_id="evidence:sql_source.simulacros_dataset",
    )
    manifest_path = output_dir / "export_manifest.yaml"
    write_export_manifest(manifest, manifest_path)

    comparison_report_path = None
    historical_path = PROJECT_ROOT / HISTORICAL_CSV_PATH
    if historical_path.is_file():
        comparison_report = comparison_mod.build_comparison_report(
            historical_path=historical_path,
            generated_rows=included_rows,
            generated_columns=OUTPUT_COLUMNS,
        )
        comparison_report_path = output_dir / "comparison_report.yaml"
        write_yaml_atomic(comparison_report, comparison_report_path)

    logger.info(
        "Export drills completado (run_id=%s, filas_exportadas=%s, filas_excluidas=%s, resultado=%s)",
        run_id, stats.rows_exported, stats.rows_excluded, validation_report["status"]["result"],
    )

    return PipelineResult(
        run_id=run_id,
        output_dir=output_dir,
        csv_path=csv_path,
        validation_report_path=validation_report_path,
        manifest_path=manifest_path,
        comparison_report_path=comparison_report_path,
        stats=stats,
        validation_report=validation_report,
        manifest=manifest,
        excluded_rows=excluded_rows,
    )
