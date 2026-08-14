"""Orquestación end-to-end del prototipo de exportación de Bypass:

    SQL -> extracción -> transformación -> mapping -> validación -> CSV

DUPLICATED_FROM_DRILLS (estructura general, deliberadamente, Sprint
9.4): mismo patrón de alto nivel que `drills.pipeline.run`, sin
comparison ni evidence -- no son necesarias para
`BYPASS_OFFLINE_SAMPLE_READY` (ver
docs/07-developer-guide/bypass-module.md § 3, Fase 3 de este sprint:
GO sin necesitar esas dos etapas). No existe todavía un Export Engine
genérico que evite esta duplicación -- documentado como deuda conocida,
no resuelto en este incremento (ver informe de cierre de Sprint 9.3).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from src.config import PROJECT_ROOT
from src.export.engine.manifest import build_query_filters_section
from src.export.engine.writer import write_csv
from src.query.models import CompiledFilter
from src.query.sql_builder import render_generated_sql_file

from . import transformations as tr
from .config import BypassExportConfig, load_bypass_config
from .extractor import MODE_FULL, MODE_SAMPLE, ExtractionResult, extract_bypass
from .manifest import RunStats, build_export_manifest, write_text_atomic, write_validation_report, write_yaml_atomic
from .validator import validate_output_csv

GENERATED_SQL_FILENAME = "generated_query.sql"

# Orden de columnas del CSV generado -- decisión propia de este
# prototipo, igual que en Drills.
OUTPUT_COLUMNS = [
    "CS_HistoricalOriginID",
    "ByPassType",
    "Cause",
    "ElementType",
    "RealizationMethods",
    "Reason",
    "CS_HistoricalDataOrigin",
]


@dataclass
class PipelineResult:
    run_id: str
    output_dir: Path
    csv_path: Path
    validation_report_path: Path
    manifest_path: Path
    stats: RunStats


def _empty(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
    return isinstance(value, str) and value.strip() == ""


def _transform_rows(
    df: pd.DataFrame, config: BypassExportConfig, stats: RunStats,
) -> tuple[list[dict], list[dict]]:
    reference_data = config.reference_data
    bypass_type_lookup = {str(k): v for k, v in reference_data["bypass_type_lookup"].items()}
    cause_lookup = {str(k): v for k, v in reference_data["cause_lookup"].items()}
    element_type_lookup = {str(k): v for k, v in reference_data["element_type_lookup"].items()}
    realization_method_lookup = {str(k): v for k, v in reference_data["realization_method_lookup"].items()}
    historical_data_origin = reference_data["historical_data_origin_literal"]

    included: list[dict] = []
    excluded: list[dict] = []

    for _, row in df.iterrows():
        stats.rows_read += 1
        stats.rows_transformed += 1

        historical_id = tr.to_historical_id(row.get("IDBES"))
        if _empty(historical_id):
            stats.missing_historical_origin_id += 1
            excluded.append({"row": dict(row), "reason": "CS_HistoricalOriginID ausente o no numérico"})
            continue

        bypass_type = tr.resolve_lookup(
            row.get("IDTipoBypass"), bypass_type_lookup,
            reference_data["bypass_type_null_default"],
        )
        cause = tr.resolve_lookup(
            row.get("IDCausa"), cause_lookup, reference_data["cause_null_default"],
        )
        element_type = tr.resolve_lookup(
            row.get("IDTipoSCE"), element_type_lookup, reference_data["element_type_null_default"],
        )
        realization_method = tr.resolve_lookup(
            row.get("IDMetodoBypass"), realization_method_lookup,
            reference_data["realization_method_null_default"],
        )
        reason = tr.nullcontrol_passthrough(row.get("Motivo"), reference_data["reason_null_default"])

        for lookup_result in (bypass_type, cause, element_type, realization_method, reason):
            if lookup_result.status == "resolved":
                stats.lookups_resolved += 1
            elif lookup_result.status == "null_default":
                stats.lookups_null_default += 1
            else:
                stats.lookups_unresolved += 1
                stats.warnings.append(
                    f"row={historical_id}: valor sin resolver ({lookup_result.raw_source_value!r})"
                )

        included.append({
            "CS_HistoricalOriginID": historical_id,
            "ByPassType": bypass_type.value or "",
            "Cause": cause.value or "",
            "ElementType": element_type.value or "",
            "RealizationMethods": "" if realization_method.value is None else str(realization_method.value),
            "Reason": reason.value or "",
            "CS_HistoricalDataOrigin": historical_data_origin,
        })

    return included, excluded


def run(
    mode: str = MODE_SAMPLE,
    limit: int = 100,
    output_root: str | Path | None = None,
    compiled_filters: Sequence[CompiledFilter] | None = None,
    extraction: ExtractionResult | None = None,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> PipelineResult:
    """Orquesta la exportación completa de Bypass. Mismo contrato
    aditivo que `drills.pipeline.run` para `extraction`/`run_id`/
    `timestamp` (permite que un orquestador externo -- Framework Core v1
    -- reutilice una extracción ya hecha por una etapa `query` separada)."""
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo no soportado: {mode!r}")

    run_id = run_id or uuid.uuid4().hex[:12]
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    config = load_bypass_config()

    output_root = Path(output_root) if output_root else (PROJECT_ROOT / "outputs" / "prototype" / "bypass")
    output_dir = output_root / timestamp
    if output_dir.exists():
        raise FileExistsError(f"El directorio de salida ya existe, no se reutiliza: {output_dir}")

    if extraction is None:
        extraction = extract_bypass(config, mode=mode, limit=limit, compiled_filters=compiled_filters)

    stats = RunStats(run_id=run_id, timestamp=timestamp, mode=mode, connection_name=config.source.connection)

    output_dir.mkdir(parents=True, exist_ok=True)

    query_filters_section: dict | None = None
    if extraction.compiled_filters:
        generated_sql_path = output_dir / GENERATED_SQL_FILENAME
        generated_text = render_generated_sql_file(
            sql_text=extraction.composed_sql_text or extraction.sql_text,
            source_sql_relpath=extraction.source_file,
            source_sql_sha256=extraction.sql_sha256,
            run_id=run_id, timestamp=timestamp,
        )
        write_text_atomic(generated_text, generated_sql_path)
        query_filters_section = build_query_filters_section(
            compiled_filters=extraction.compiled_filters,
            source_sql_sha256=extraction.sql_sha256,
            generated_sql_file=GENERATED_SQL_FILENAME,
            generated_sql_sha256=hashlib.sha256(generated_text.encode("utf-8")).hexdigest(),
        )

    included, excluded = _transform_rows(extraction.dataframe, config, stats)

    csv_path = output_dir / config.output.filename
    write_csv(included, OUTPUT_COLUMNS, csv_path, config.output)

    post_check = validate_output_csv(csv_path, OUTPUT_COLUMNS, config.output)
    if not post_check.is_valid:
        stats.errors.extend(post_check.issues)
    stats.rows_exported = len(included)
    stats.rows_excluded = len(excluded)
    stats.output_path = str(csv_path)
    stats.output_encoding = config.output.encoding
    stats.output_bom = config.output.bom
    stats.output_delimiter = config.output.delimiter
    stats.output_line_terminator = repr(config.output.line_terminator)[1:-1]
    stats.output_column_count = post_check.column_count or len(OUTPUT_COLUMNS)
    stats.output_columns = post_check.columns or OUTPUT_COLUMNS

    validation_report_path = output_dir / "validation_report.yaml"
    write_validation_report(stats, validation_report_path)

    evidence_ids = sorted({f.evidence_id for f in config.fields})
    limitations = [
        "Prototipo limitado a 7 columnas del objeto By_Passes (43 en el CSV Operational real) -- ver excluded_columns en config/exports/bypass.yaml.",
        "Entity NO se genera en este incremento: sin artefacto local IDUnidadOrg->Code para el catálogo First_Axis vigente (ver excluded_columns).",
        f"Modo '{mode}': " + (
            f"la consulta original se ejecuta completa y se trunca localmente a {limit} filas "
            "(las más antiguas por FechaCreacion, ordenadas en pandas -- la SQL de origen no "
            "tiene ORDER BY propio, a diferencia de la de Drills)."
            if mode == MODE_SAMPLE else
            "se exportan todas las filas devueltas por la consulta, sujeto a max_rows_per_query."
        ),
        "HALLAZGO (Sprint 9.4, confirmado contra el CSV Operational real): la columna "
        "CS_HistoricalOriginID de ese fichero contiene valores con apariencia de fecha "
        "(p. ej. '17/11/1907 0:00') en vez de un IDBES entero -- consistente con un ID pequeño "
        "reinterpretado como número de serie de fecha de Excel en el proceso de export. No se ha "
        "intentado revertir esta corrupción en este pipeline -- afecta a la comparación futura "
        "contra ese fichero, no a esta generación.",
    ]

    manifest = build_export_manifest(
        run_id=run_id, timestamp=timestamp, config_raw=config.raw, sql_text=extraction.sql_text,
        csv_path=csv_path, row_count=len(included), columns=OUTPUT_COLUMNS,
        connection_name=config.source.connection, mode=mode, evidence_ids=evidence_ids,
        limitations=limitations, query_filters=query_filters_section,
    )
    manifest_path = output_dir / "export_manifest.yaml"
    write_yaml_atomic(manifest, manifest_path)

    return PipelineResult(
        run_id=run_id, output_dir=output_dir, csv_path=csv_path,
        validation_report_path=validation_report_path, manifest_path=manifest_path, stats=stats,
    )
