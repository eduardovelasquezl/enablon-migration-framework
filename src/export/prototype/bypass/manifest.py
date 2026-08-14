"""Manifest/validation report mínimos para bypass.By_Passes (Sprint 9.4).

`write_yaml_atomic`/`write_text_atomic` se REUTILIZAN tal cual de
`src.export.prototype.drills.manifest` -- utilidades de I/O genéricas
(escritura atómica temporal+rename), sin ningún campo de Drills.

`RunStats`/`build_export_manifest`/`write_validation_report` SÍ son
nuevos (DUPLICATED_FROM_DRILLS, patrón, no código): el `RunStats` de
Drills tiene campos específicos de sus 8 columnas (`entities_resolved`,
`dates_hora_missing_or_invalid`...) que no aplican a las 7 de Bypass --
forzar la misma clase habría sido peor que un contenedor propio,
pequeño y honesto sobre lo que Bypass realmente mide."""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.export.prototype.drills.manifest import write_text_atomic, write_yaml_atomic

__all__ = ["RunStats", "build_export_manifest", "write_validation_report", "write_yaml_atomic", "write_text_atomic"]


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

    missing_historical_origin_id: int = 0
    lookups_resolved: int = 0
    lookups_unresolved: int = 0
    lookups_null_default: int = 0

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


def write_validation_report(stats: RunStats, path: Path) -> dict:
    report = {
        "run": {
            "run_id": stats.run_id, "timestamp": stats.timestamp, "mode": stats.mode,
            "connection_name": stats.connection_name, "migration_object": "By_Passes",
            "prototype_status": "review_only",
        },
        "counts": {
            "rows_read": stats.rows_read, "rows_transformed": stats.rows_transformed,
            "rows_exported": stats.rows_exported, "rows_excluded": stats.rows_excluded,
            "warnings": len(stats.warnings), "errors": len(stats.errors),
        },
        "lookups": {
            "resolved": stats.lookups_resolved, "unresolved": stats.lookups_unresolved,
            "null_default": stats.lookups_null_default,
        },
        "reference": {
            "missing_historical_origin_id": stats.missing_historical_origin_id,
        },
        "output": {
            "path": stats.output_path, "encoding": stats.output_encoding, "bom": stats.output_bom,
            "delimiter": stats.output_delimiter, "line_terminator": stats.output_line_terminator,
            "column_count": stats.output_column_count, "columns": stats.output_columns,
        },
        "status": {
            "result": "FAILED_VALIDATION" if stats.errors else "SUCCESS",
            "blocking_errors": list(stats.errors), "warnings": list(stats.warnings),
        },
    }
    write_yaml_atomic(report, path)
    return report


def build_export_manifest(
    *, run_id: str, timestamp: str, config_raw: dict, sql_text: str, csv_path: Path,
    row_count: int, columns: list[str], connection_name: str, mode: str,
    evidence_ids: list[str], limitations: list[str], query_filters: dict[str, Any] | None,
) -> dict:
    return {
        "run_id": run_id, "timestamp": timestamp, "git_commit": _git_commit(),
        "migration_object": "By_Passes", "module": "bypass",
        "prototype_version": "0.1.0-prototype", "prototype_status": "review_only",
        "mode": mode,
        "connection": {
            "name": connection_name,
            "note": "Sin credenciales -- ver config/databases.yaml y .env (no incluidos aquí).",
        },
        "source": {
            "sql_file": config_raw["source"]["sql_file"],
            "sql_sha256": _sha256_text(sql_text),
        },
        "hashes": {
            "sql_sha256": _sha256_text(sql_text),
            "csv_sha256": _sha256_file(csv_path) if csv_path.is_file() else None,
        },
        "output": {"row_count": row_count, "columns": columns},
        "query_filters": query_filters or {"applied": False, "count": 0},
        "evidence_ids": sorted(set(evidence_ids)),
        "limitations": limitations,
        "approved_for_enablon_import": False,
    }
