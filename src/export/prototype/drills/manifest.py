"""Construcción de `validation_report.yaml` y `export_manifest.yaml`.

Ninguna de las dos funciones de escritura decide reglas de negocio -- solo
serializan las estadísticas ya acumuladas por `pipeline.py` en las
estructuras exactas pedidas por el incremento de implementación.
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Sequence

import yaml


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

PROTOTYPE_VERSION = "0.1.0-prototype"

SUCCESS = "SUCCESS"
SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
FAILED_VALIDATION = "FAILED_VALIDATION"
FAILED_EXECUTION = "FAILED_EXECUTION"


@dataclass
class RunStats:
    run_id: str
    timestamp: str
    mode: str
    connection_name: str

    rows_read: int = 0
    rows_transformed: int = 0
    rows_exported: int = 0
    rows_excluded: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    reference_valid: int = 0
    reference_invalid: int = 0
    missing_typology: int = 0
    missing_historical_origin_id: int = 0
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

    output_path: str = ""
    output_encoding: str = ""
    output_bom: bool = False
    output_delimiter: str = ""
    output_line_terminator: str = ""
    output_column_count: int = 0
    output_columns: list[str] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def write_yaml_atomic(data: dict, path: Path) -> None:
    """Escritura atómica genérica (temporal + `os.replace`) reutilizada por
    `validation_report.yaml`, `export_manifest.yaml` y `comparison_report.yaml`."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def write_text_atomic(text: str, path: Path) -> None:
    """Escritura atómica de texto plano (temporal + `os.replace`), mismo
    patrón que `write_yaml_atomic` -- usada por `generated_query.sql`
    (Query Engine v0.1). Nunca escribe sobre `sql/source_queries/`: `path`
    siempre vive bajo el directorio de la ejecución (`outputs/...`)."""
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def determine_status(stats: RunStats) -> tuple[str, list[str], list[str]]:
    """Determina `status.result` a partir de las estadísticas acumuladas.

    `FAILED_EXECUTION` lo decide `pipeline.py` directamente (una excepción
    no controlada) -- esta función solo distingue entre éxito limpio, éxito
    con warnings, y fallo de validación (post-escritura)."""
    blocking = list(stats.errors)
    warnings = list(stats.warnings)
    if blocking:
        return FAILED_VALIDATION, blocking, warnings
    if warnings:
        return SUCCESS_WITH_WARNINGS, blocking, warnings
    return SUCCESS, blocking, warnings


def build_validation_report(stats: RunStats) -> dict:
    result, blocking_errors, warnings = determine_status(stats)
    return {
        "run": {
            "run_id": stats.run_id,
            "timestamp": stats.timestamp,
            "mode": stats.mode,
            "connection_name": stats.connection_name,
            "migration_object": "Drills",
            "prototype_status": "review_only",
        },
        "counts": {
            "rows_read": stats.rows_read,
            "rows_transformed": stats.rows_transformed,
            "rows_exported": stats.rows_exported,
            "rows_excluded": stats.rows_excluded,
            "warnings": len(stats.warnings),
            "errors": len(stats.errors),
        },
        "reference": {
            "valid": stats.reference_valid,
            "invalid": stats.reference_invalid,
            "missing_typology": stats.missing_typology,
            "missing_historical_origin_id": stats.missing_historical_origin_id,
            "missing_starting_date": stats.missing_starting_date,
            "duplicate_references": stats.duplicate_references,
        },
        "entities": {
            "resolved": stats.entities_resolved,
            "do_not_migrate": stats.entities_do_not_migrate,
            "unresolved": stats.entities_unresolved,
            "conflicting": stats.entities_conflicting,
            "empty": stats.entities_empty,
        },
        "dates": {
            "valid": stats.dates_valid,
            "invalid": stats.dates_invalid,
            "empty": stats.dates_empty,
        },
        "output": {
            "path": stats.output_path,
            "encoding": stats.output_encoding,
            "bom": stats.output_bom,
            "delimiter": stats.output_delimiter,
            "line_terminator": stats.output_line_terminator,
            "column_count": stats.output_column_count,
            "columns": stats.output_columns,
        },
        "status": {
            "result": result,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
        },
    }


def write_validation_report(stats: RunStats, path: Path) -> dict:
    report = build_validation_report(stats)
    write_yaml_atomic(report, path)
    return report


def build_query_filters_section(
    *,
    compiled_filters: Sequence[Any],
    source_sql_sha256: str,
    generated_sql_file: str | None,
    generated_sql_sha256: str | None,
) -> dict:
    """Sección `query_filters` de `export_manifest.yaml` (Query Engine v0.1).

    `compiled_filters` son objetos `CompiledFilter` (o cualquier objeto con
    una propiedad `manifest_entry` -- se evita importar `src.query` aquí
    para no crear un acoplamiento circular entre `src.export` y
    `src.query`; el llamador ya conoce el tipo real). Nunca incluye el
    fragmento SQL, los nombres de parámetro ni ningún valor de conexión --
    solo `field`/`operator`/`value` por filtro, tal como se pide en el
    incremento.
    """
    expressions = [cf.manifest_entry for cf in compiled_filters]
    return {
        "applied": bool(compiled_filters),
        "count": len(expressions),
        "expressions": expressions,
        "generated_sql_file": generated_sql_file,
        "generated_sql_sha256": generated_sql_sha256,
        "source_sql_sha256": source_sql_sha256,
    }


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
        "connection": {
            "name": connection_name,
            "note": "Sin credenciales -- ver config/databases.yaml y .env (no incluidos aquí).",
        },
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
