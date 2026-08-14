"""Construcción de `validation_report.yaml` y `export_manifest.yaml`.

Ninguna de las dos funciones de escritura decide reglas de negocio -- solo
serializan las estadísticas ya acumuladas por `pipeline.py` en las
estructuras exactas pedidas por el incremento de implementación.

Desde Sprint 9.6 (Export Engine mínimo), las piezas ya demostradas idénticas
entre Drills y Bypass viven en `src.export.engine.manifest` -- ver ese
fichero para el detalle de qué se movió y por qué. Este fichero conserva
`RunStats` (con los campos de extensión propios de Drills: `reference_*`/
`entities_*`/`dates_*`), `build_validation_report`/`build_export_manifest`
(con las secciones `reference`/`entities`/`dates` y la trazabilidad extendida
que Bypass todavía no tiene), y los re-exports necesarios para que
`pipeline.py` no cambie ni un import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Sequence

import yaml

from src.export.engine.manifest import (
    PROTOTYPE_VERSION,
    BaseRunStats,
    build_connection_section,
    build_counts_section,
    build_output_section,
    build_query_filters_section,
    build_run_section,
    determine_status as _engine_determine_status,
    git_commit as _git_commit,
    sha256_file as _sha256_file,
    sha256_text as _sha256_text,
    write_text_atomic,
    write_yaml_atomic,
)

__all__ = [
    "RunStats", "build_validation_report", "write_validation_report",
    "build_query_filters_section", "build_export_manifest", "write_export_manifest",
    "write_yaml_atomic", "write_text_atomic", "determine_status",
]


def _unfreeze(value: Any) -> Any:
    """Inverso de `src.config.loader._freeze`: `MappingProxyType` -> `dict`,
    `tuple` -> `list`, recursivamente. `config.raw` llega congelado (ver
    `src/config/loader.py`) y PyYAML no sabe serializar ese tipo -- sin este
    paso, `yaml.safe_dump` fallaría con `RepresenterError`."""
    if isinstance(value, MappingProxyType):
        return {k: _unfreeze(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {k: _unfreeze(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_unfreeze(v) for v in value]
    if isinstance(value, list):
        return [_unfreeze(v) for v in value]
    return value


@dataclass
class RunStats(BaseRunStats):
    """Extiende `BaseRunStats` (Engine) con los contadores propios de
    Drills -- ninguno de estos campos aplica a Bypass (ver
    `bypass/manifest.py::RunStats`, que extiende la misma base con SUS
    propios campos)."""

    reference_valid: int = 0
    reference_invalid: int = 0
    missing_typology: int = 0
    missing_starting_date: int = 0
    duplicate_references: int = 0

    entities_resolved: int = 0
    entities_do_not_migrate: int = 0
    entities_unresolved: int = 0
    entities_conflicting: int = 0
    entities_empty: int = 0

    dates_valid: int = 0
    dates_invalid: int = 0
    dates_empty: int = 0
    dates_hora_missing_or_invalid: int = 0


def determine_status(stats: RunStats) -> tuple[str, list[str], list[str]]:
    """Determina `status.result` a partir de las estadísticas acumuladas --
    delega en `engine.manifest.determine_status` (3 estados: éxito limpio,
    éxito con warnings, fallo de validación). `FAILED_EXECUTION` lo decide
    `pipeline.py` directamente (una excepción no controlada)."""
    return _engine_determine_status(stats.errors, stats.warnings)


def build_validation_report(stats: RunStats) -> dict:
    result, blocking_errors, warnings = determine_status(stats)
    report: dict[str, Any] = {"run": build_run_section(stats, migration_object="Drills")}
    report["counts"] = build_counts_section(stats)
    report["reference"] = {
        "valid": stats.reference_valid,
        "invalid": stats.reference_invalid,
        "missing_typology": stats.missing_typology,
        "missing_historical_origin_id": stats.missing_historical_origin_id,
        "missing_starting_date": stats.missing_starting_date,
        "duplicate_references": stats.duplicate_references,
    }
    report["entities"] = {
        "resolved": stats.entities_resolved,
        "do_not_migrate": stats.entities_do_not_migrate,
        "unresolved": stats.entities_unresolved,
        "conflicting": stats.entities_conflicting,
        "empty": stats.entities_empty,
    }
    report["dates"] = {
        "valid": stats.dates_valid,
        "invalid": stats.dates_invalid,
        "empty": stats.dates_empty,
        "hora_missing_or_invalid": stats.dates_hora_missing_or_invalid,
    }
    report["output"] = build_output_section(stats)
    report["status"] = {
        "result": result,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
    }
    return report


def write_validation_report(stats: RunStats, path: Path) -> dict:
    report = build_validation_report(stats)
    write_yaml_atomic(report, path)
    return report


def build_export_manifest(
    *,
    run_id: str,
    timestamp: str,
    config_raw: dict,
    sql_text: str,
    csv_path: Path,
    row_count: int,
    columns: list[str],
    connection_name: str,
    mode: str,
    evidence_ids: list[str],
    limitations: list[str],
    open_questions: list[str],
    sql_source_evidence_id: str,
    query_filters: dict | None = None,
) -> dict:
    config_raw = _unfreeze(config_raw)
    config_text = yaml.safe_dump(config_raw, allow_unicode=True, sort_keys=True)
    mappings_text = yaml.safe_dump(config_raw.get("reference_data", {}), allow_unicode=True, sort_keys=True)
    sql_sha256 = _sha256_text(sql_text)

    runtime_sql_composed = bool(query_filters and query_filters.get("applied"))
    if query_filters is None:
        query_filters = build_query_filters_section(
            compiled_filters=(),
            source_sql_sha256=sql_sha256,
            generated_sql_file=None,
            generated_sql_sha256=None,
        )

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "git_commit": _git_commit(),
        "migration_object": "Drills",
        "module": "simulacros",
        "prototype_version": PROTOTYPE_VERSION,
        "prototype_status": "review_only",
        "mode": mode,
        "connection": build_connection_section(connection_name),
        "source": {
            "sql_file": "sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql",
            "sql_sha256": sql_sha256,
            "sql_modified_from_original": False,
            # Campos explícitos (Query Engine v0.1): el fichero original en
            # sql/source_queries/ nunca se modifica en disco --
            # `runtime_sql_composed` distingue si, para ESTA ejecución, se
            # compuso una variante en memoria con filtros (ver
            # src/query/sql_builder.py) sin que eso implique tocar el
            # fichero fuente.
            "source_sql_modified": False,
            "runtime_sql_composed": runtime_sql_composed,
            "evidence_id": sql_source_evidence_id,
        },
        "hashes": {
            "sql_sha256": sql_sha256,
            "mappings_sha256": _sha256_text(mappings_text),
            "config_sha256": _sha256_text(config_text),
            "csv_sha256": _sha256_file(csv_path),
        },
        "output": {
            "row_count": row_count,
            "columns": columns,
            "encoding": config_raw["output"]["encoding"],
            "delimiter": config_raw["output"]["delimiter"],
            "bom": config_raw["output"]["bom"],
            "line_terminator": config_raw["output"]["line_terminator"],
        },
        "query_filters": query_filters,
        "rules_applied": [
            "build_reference (AFD-DRILLS-REFERENCE-001)",
            "typology_lookup (IDTipo -> CS_Typology, 2-step XLOOKUP confirmado)",
            "letter_lookup (IDLetra -> CS_Letter)",
            "workflow_status_lookup (Estado -> CS_WorkflowStatus)",
            "entity_resolution (IDUnidadOrg -> CS_ImpactedEntities vía Entidades_Enablon_ITP)",
            "constant (CS_HistoricalDataOrigin)",
        ],
        "evidence_ids": evidence_ids,
        "limitations": limitations,
        "open_questions": open_questions,
        "approved_for_enablon_import": False,
    }


def write_export_manifest(manifest: dict, path: Path) -> None:
    write_yaml_atomic(manifest, path)
