"""Orquestación end-to-end del prototipo de exportación de Drills:

    SQL -> extracción -> transformación -> mapping -> validación -> CSV

No es un Export Engine genérico: conoce explícitamente los 8 campos de
`config/exports/drills.yaml` -- una versión reutilizable para otros objetos
es trabajo futuro, fuera del alcance de este incremento (ver
`docs/specifications/v1.0/export/closing_recommendation.md`).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from src.config import PROJECT_ROOT
from src.query.models import CompiledFilter
from src.query.sql_builder import render_generated_sql_file

from . import comparison as comparison_mod
from . import mappings as mappings_mod
from . import transformations as tr
from .config import DrillsExportConfig, load_drills_config
from .exporter import write_csv
from .extractor import MODE_FULL, MODE_SAMPLE, extract_drills
from .manifest import (
    RunStats,
    build_export_manifest,
    build_query_filters_section,
    write_export_manifest,
    write_text_atomic,
    write_validation_report,
    write_yaml_atomic,
)
from .validator import (
    check_duplicate_references,
    validate_output_csv,
    validate_pre_write,
)

GENERATED_SQL_FILENAME = "generated_query.sql"

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
    issues_path: Path
    issues: list[dict] = field(default_factory=list)


def _write_issues_jsonl(issues: list[dict], path: Path) -> None:
    """Escritura atómica de `issues.jsonl` -- un objeto JSON por línea, con
    únicamente los campos del esquema acordado (Fase 8 del incremento de
    Evidence Engine). Se escribe SIEMPRE, incluso con `issues` vacío (un
    fichero vacío es una señal válida de "sin incidencias", no un error)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for issue in issues:
                f.write(json.dumps(issue, ensure_ascii=False))
                f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


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


def _issue(
    issues: list[dict],
    *,
    run_id: str,
    row_key: str,
    historical_origin_id: str | None,
    historical_data_origin: str,
    category: str,
    severity: str,
    source_value,
    mapped_value,
    message: str,
    evidence_id: str,
    included_in_csv: bool,
) -> None:
    """Añade un registro al detalle de incidencias por fila (`issues.jsonl`,
    ver Fase 8 del incremento de Evidence Engine). Nunca guarda la fila
    completa -- solo los campos declarados en el esquema acordado."""
    issues.append({
        "run_id": run_id,
        "row_key": row_key,
        "historical_origin_id": historical_origin_id,
        "historical_data_origin": historical_data_origin,
        "category": category,
        "severity": severity,
        "source_value": None if source_value is None else str(source_value),
        "mapped_value": None if mapped_value is None else str(mapped_value),
        "message": message,
        "evidence_id": evidence_id,
        "included_in_csv": included_in_csv,
    })


def _transform_rows(
    df: pd.DataFrame,
    config: DrillsExportConfig,
    stats: RunStats,
    run_id: str,
    issues: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Devuelve (filas_incluidas_en_csv, filas_excluidas_con_motivo).

    Cada fila fuente se procesa exactamente una vez -- nunca se descarta en
    silencio: toda fila que no llega al CSV queda en `excluded`. Además de
    los contadores de `stats` (ya existentes, sin cambios de comportamiento),
    esta función añade a `issues` un registro por cada incidencia real
    detectada -- nunca por filas sin problema (`RESOLVED` no genera
    incidencia, por ejemplo). Es la única adición de este incremento sobre
    el pipeline de exportación ya existente.
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
        row_key = None  # se fija en cuanto se conoce historical_id, más abajo.

        typology_result = tr.resolve_typology(row.get("IDTipo"), typology_lookup, typology_default)
        historical_id = tr.to_historical_id(row.get("IDSimulacro"))
        row_key = historical_id or f"row_{stats.rows_read}"

        raw_fecha = row.get("Fecha")
        starting_date = tr.parse_starting_date(raw_fecha)
        if _empty(raw_fecha):
            stats.dates_empty += 1
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="INVALID_DATE",
                severity="review_required", source_value=raw_fecha, mapped_value=None,
                message="Fecha ausente en el origen.",
                evidence_id="evidence:sql_source.simulacros_dataset", included_in_csv=False,
            )
        elif starting_date is None:
            stats.dates_invalid += 1
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="INVALID_DATE",
                severity="review_required", source_value=raw_fecha, mapped_value=None,
                message="Fecha presente pero no interpretable con los formatos soportados.",
                evidence_id="evidence:sql_source.simulacros_dataset", included_in_csv=False,
            )
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
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="ENTITY_DO_NOT_MIGRATE",
                severity="not_migrated_by_design", source_value=entity_result.raw_source_value,
                mapped_value=entity_result.value,
                message="IDUnidadOrg resuelve a una entidad marcada explícitamente 'No migra'.",
                evidence_id="object_assessments/drills_entity_resolution_assessment.md",
                included_in_csv=reference_result.is_valid,
            )
        elif entity_result.status == mappings_mod.UNRESOLVED:
            stats.entities_unresolved += 1
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: IDUnidadOrg "
                f"{entity_result.raw_source_value!r} no está en el catálogo de entidad."
            )
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="ENTITY_UNRESOLVED",
                severity="review_required", source_value=entity_result.raw_source_value,
                mapped_value=None,
                message="IDUnidadOrg no está en el catálogo de entidad normalizado.",
                evidence_id="object_assessments/drills_entity_resolution_assessment.md",
                included_in_csv=reference_result.is_valid,
            )
        elif entity_result.status == mappings_mod.CONFLICTING:
            stats.entities_conflicting += 1
            stats.warnings.append(
                f"IDSimulacro={historical_id or '?'}: IDUnidadOrg "
                f"{entity_result.raw_source_value!r} tiene más de un Code distinto en el catálogo."
            )
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="ENTITY_CONFLICTING",
                severity="blocking_for_approval", source_value=entity_result.raw_source_value,
                mapped_value=None,
                message="IDUnidadOrg tiene más de un Code distinto en el catálogo de entidad.",
                evidence_id="object_assessments/drills_entity_resolution_assessment.md",
                included_in_csv=reference_result.is_valid,
            )
        else:
            stats.entities_empty += 1
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="ENTITY_EMPTY",
                severity="review_required", source_value=entity_result.raw_source_value,
                mapped_value=None,
                message="IDUnidadOrg ausente en el origen -- sin información de entidad para resolver.",
                evidence_id="object_assessments/drills_entity_resolution_assessment.md",
                included_in_csv=reference_result.is_valid,
            )

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
            exclusion_reason = ",".join(reference_result.missing_components)
            excluded.append({
                **{k: _serialize(v) for k, v in row_dict.items()},
                "exclusion_reason": exclusion_reason,
            })
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="EXCLUDED_ROWS",
                severity="review_required", source_value=None, mapped_value=None,
                message=f"Fila excluida del CSV -- componente(s) ausente(s): {exclusion_reason}.",
                evidence_id="AFD-DRILLS-REFERENCE-001", included_in_csv=False,
            )
            _issue(
                issues, run_id=run_id, row_key=row_key, historical_origin_id=historical_id,
                historical_data_origin=historical_data_origin, category="INVALID_REFERENCE",
                severity="review_required", source_value=exclusion_reason, mapped_value=None,
                message="No fue posible construir 'Reference': falta al menos un componente obligatorio.",
                evidence_id="AFD-DRILLS-REFERENCE-001", included_in_csv=False,
            )

    stats.duplicate_references = check_duplicate_references(reference_values_for_dup_check)
    if stats.duplicate_references:
        stats.warnings.append(
            f"{stats.duplicate_references} fila(s) comparten un valor de Reference con otra fila."
        )
        seen_counts: dict[str, int] = {}
        for value in reference_values_for_dup_check:
            seen_counts[value] = seen_counts.get(value, 0) + 1
        duplicated_values = {value for value, count in seen_counts.items() if count > 1}
        for row_included in included:
            if row_included["Reference"] in duplicated_values:
                _issue(
                    issues, run_id=run_id,
                    row_key=row_included["CS_HistoricalOriginID"] or "?",
                    historical_origin_id=row_included["CS_HistoricalOriginID"] or None,
                    historical_data_origin=historical_data_origin, category="DUPLICATE_REFERENCE",
                    severity="review_required", source_value=None,
                    mapped_value=row_included["Reference"],
                    message="Este valor de 'Reference' se repite en más de una fila incluida en el CSV.",
                    evidence_id="AFD-DRILLS-REFERENCE-001", included_in_csv=True,
                )

    return included, excluded


def run(
    mode: str = MODE_SAMPLE,
    limit: int = 100,
    output_root: str | Path | None = None,
    compiled_filters: Sequence[CompiledFilter] | None = None,
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
        "Iniciando export drills (run_id=%s, modo=%s, conexion=%s, salida=%s, filtros=%s)",
        run_id, mode, config.source.connection, output_dir, len(compiled_filters or ()),
    )

    extraction = extract_drills(config, mode=mode, limit=limit, compiled_filters=compiled_filters)

    # Query Engine v0.1: si hubo filtros, escribir generated_query.sql
    # (placeholders únicamente, nunca valores) -- documentado ANTES de
    # cualquier posible fallo de validación posterior, porque describe
    # exactamente lo que se ejecutó contra SQL Server en esta extracción.
    generated_sql_file: str | None = None
    generated_sql_sha256: str | None = None
    if extraction.compiled_filters:
        generated_sql_text = render_generated_sql_file(
            sql_text=extraction.composed_sql_text,
            source_sql_relpath=str(config.source.sql_file),
            source_sql_sha256=extraction.sql_sha256,
            run_id=run_id,
            timestamp=timestamp,
        )
        generated_sql_path = output_dir / GENERATED_SQL_FILENAME
        write_text_atomic(generated_sql_text, generated_sql_path)
        generated_sql_file = GENERATED_SQL_FILENAME
        generated_sql_sha256 = hashlib.sha256(generated_sql_text.encode("utf-8")).hexdigest()

    query_filters_section = build_query_filters_section(
        compiled_filters=extraction.compiled_filters,
        source_sql_sha256=extraction.sql_sha256,
        generated_sql_file=generated_sql_file,
        generated_sql_sha256=generated_sql_sha256,
    )

    pre_check = validate_pre_write(extraction.dataframe, config)
    if not pre_check.is_valid:
        stats.errors.extend(pre_check.issues)
        stats.rows_transformed = 0
        report = write_validation_report(stats, output_dir / "validation_report.yaml")
        raise RuntimeError(
            f"Validación previa a la escritura falló, no se generó CSV: {pre_check.issues}"
        )
    stats.warnings.extend(pre_check.warnings)

    issues: list[dict] = []
    included_rows, excluded_rows = _transform_rows(extraction.dataframe, config, stats, run_id, issues)
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
        query_filters=query_filters_section,
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

    issues_path = output_dir / "issues.jsonl"
    _write_issues_jsonl(issues, issues_path)

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
        issues_path=issues_path,
        issues=issues,
    )
