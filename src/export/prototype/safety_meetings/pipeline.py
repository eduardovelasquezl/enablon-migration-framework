"""Orquestación end-to-end del prototipo de exportación de Safety Meetings:

    SQL -> extracción -> transformación -> mapping -> validación -> CSV

MODULE_SPECIFIC (deliberado, Sprint 9.7): misma forma de alto nivel que
`drills.pipeline.run`/`bypass.pipeline.run`, sin comparison ni evidence --
no son necesarias para `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY`. Esta es la
pieza que Sprint 9.5.1/9.6 clasificaron `WAIT_FOR_THIRD_MODULE` -- este
fichero ES la tercera confirmación de forma, no una generalización
prematura: ver el informe de cierre de Sprint 9.7 § Fase 9/16 para la
medición real de cuánto de este fichero sigue siendo necesario escribir a
mano incluso con el Export Engine ya reducido.
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
from src.export.prototype.drills.exporter import write_csv
from src.query.models import CompiledFilter
from src.query.sql_builder import render_generated_sql_file

from . import transformations as tr
from .config import SafetyMeetingsExportConfig, load_safety_meetings_config
from .extractor import MODE_FULL, MODE_SAMPLE, ExtractionResult, extract_safety_meetings
from .manifest import (
    RunStats,
    build_export_manifest,
    build_query_filters_section,
    write_text_atomic,
    write_validation_report,
    write_yaml_atomic,
)
from .validator import validate_output_csv

GENERATED_SQL_FILENAME = "generated_query.sql"

# Orden de columnas del CSV generado -- decisión propia de este prototipo,
# igual que en Drills/Bypass.
OUTPUT_COLUMNS = [
    "CS_HistoricalOriginID",
    "CS_WorkflowStatus",
    "CS_Level",
    "CS_Letter",
    "StartDate",
    "CS_MeetingPlace",
    "CS_HistoricalAtendee",
]


@dataclass
class PipelineResult:
    run_id: str
    output_dir: Path
    csv_path: Path
    validation_report_path: Path
    manifest_path: Path
    stats: RunStats


def _transform_rows(
    df: pd.DataFrame, config: SafetyMeetingsExportConfig, stats: RunStats,
) -> tuple[list[dict], list[dict]]:
    reference_data = config.reference_data
    workflow_status_lookup = {str(k): v for k, v in reference_data["workflow_status_lookup"].items()}
    level_lookup = {str(k): v for k, v in reference_data["level_lookup"].items()}
    letter_lookup = {str(k): v for k, v in reference_data["letter_lookup"].items()}

    included: list[dict] = []
    excluded: list[dict] = []

    for _, row in df.iterrows():
        stats.rows_read += 1
        stats.rows_transformed += 1

        historical_id = tr.to_historical_id(row.get("IDReunionGrupo"))
        if not historical_id:
            stats.missing_historical_origin_id += 1
            excluded.append({"row": dict(row), "reason": "CS_HistoricalOriginID ausente o no numérico"})
            continue

        workflow_status = tr.resolve_lookup(row.get("FaseActual"), workflow_status_lookup)
        level = tr.resolve_lookup(row.get("IDNivel"), level_lookup)
        letter = tr.resolve_lookup(row.get("IDLetra"), letter_lookup)
        start_date = tr.passthrough_or_empty(row.get("Fecha"))
        meeting_place = tr.passthrough_or_empty(row.get("Lugar"))
        atendee = tr.passthrough_or_empty(row.get("Asistentes"))

        for lookup_result in (workflow_status, level, letter):
            if lookup_result.status == "resolved":
                stats.lookups_resolved += 1
            elif lookup_result.status == "empty":
                stats.lookups_empty += 1
            else:
                stats.lookups_unresolved += 1
                stats.warnings.append(
                    f"row={historical_id}: valor sin resolver ({lookup_result.raw_source_value!r})"
                )

        included.append({
            "CS_HistoricalOriginID": historical_id,
            "CS_WorkflowStatus": workflow_status.value or "",
            "CS_Level": "" if level.value is None else str(level.value),
            "CS_Letter": "" if letter.value is None else str(letter.value),
            "StartDate": start_date.value or "",
            "CS_MeetingPlace": meeting_place.value or "",
            "CS_HistoricalAtendee": atendee.value or "",
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
    """Orquesta la exportación completa de Safety Meetings. Mismo contrato
    aditivo que `drills.pipeline.run`/`bypass.pipeline.run` para
    `extraction`/`run_id`/`timestamp`."""
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo no soportado: {mode!r}")

    run_id = run_id or uuid.uuid4().hex[:12]
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    config = load_safety_meetings_config()

    output_root = Path(output_root) if output_root else (PROJECT_ROOT / "outputs" / "prototype" / "safety_meetings")
    output_dir = output_root / timestamp
    if output_dir.exists():
        raise FileExistsError(f"El directorio de salida ya existe, no se reutiliza: {output_dir}")

    if extraction is None:
        extraction = extract_safety_meetings(config, mode=mode, limit=limit, compiled_filters=compiled_filters)

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
        "Prototipo limitado a 7 columnas del objeto Group_Meetings (26 en el CSV Template real) -- ver excluded_columns en config/exports/safety_meetings.yaml.",
        "CS_Entity NO se genera en este incremento: sin artefacto local IDUnidadOrg->Code/Ruta1 para el catálogo First_Axis vigente (mismo gap que Bypass, confirmado una tercera vez -- ver excluded_columns).",
        "Update_External_Meeting_Participations (segundo objeto Enablon real de Safety Meetings) NO forma parte de este incremento -- MULTI_OBJECT_GAP, ver docs/07-developer-guide/safety-meetings-module.md.",
        "CS_Level/CS_Letter/CS_WorkflowStatus: sin nullcontrol/default documentado en el ETL real -- un valor vacío o sin coincidencia queda `unresolved`/`empty`, nunca se inventa un literal por defecto.",
        "CS_HistoricalAtendee (Asistentes): limitación conocida ya reportada por el cliente (ticket #7359) -- asistentes incompletos, solo se usa 1 de 2 campos origen posibles. No corregida en este incremento.",
        f"Modo '{mode}': " + (
            f"la consulta original se ejecuta completa y se trunca localmente a {limit} filas "
            "(las más antiguas por FechaCreacion, ordenadas en pandas -- la SQL de origen no "
            "tiene ORDER BY propio, mismo patrón que Bypass)."
            if mode == MODE_SAMPLE else
            "se exportan todas las filas devueltas por la consulta, sujeto a max_rows_per_query."
        ),
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
