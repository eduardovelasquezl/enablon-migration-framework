"""Manifest/validation report mínimos para bypass.By_Passes (Sprint 9.4).

Desde Sprint 9.6 (Export Engine mínimo), las piezas ya demostradas
idénticas entre Drills y Bypass viven en `src.export.engine.manifest` --
`write_yaml_atomic`/`write_text_atomic`/hashing/`git_commit` se importaban
antes DIRECTAMENTE de `drills/manifest.py` (acoplamiento bypass -> drills);
ahora ambos módulos importan del Engine, ninguno del otro.

`RunStats` SÍ sigue siendo propio de Bypass (extiende `BaseRunStats` del
Engine con `lookups_*`, que no aplica a Drills).

`determine_status` de Bypass NO se migra a la versión de 3 estados del
Engine en este sprint -- sigue calculando inline `FAILED_VALIDATION` si hay
errores, `SUCCESS` si no, IGUAL que antes de Sprint 9.6. Migrarlo cambiaría
el comportamiento observable de Bypass (empezaría a devolver
`SUCCESS_WITH_WARNINGS` cuando antes devolvía `SUCCESS` con warnings
presentes) -- no autorizado en un refactor behavior-preserving. Ver
`reports/executions/2026-08-14/Informe-Minimal-Export-Engine-Extraction-EMF.md`
§ Fase 6 para la clasificación completa de este hallazgo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.export.engine.manifest import (
    PROTOTYPE_VERSION,
    BaseRunStats,
    build_connection_section,
    build_counts_section,
    build_output_section,
    build_query_filters_section,
    build_run_section,
    git_commit as _git_commit,
    sha256_file as _sha256_file,
    sha256_text as _sha256_text,
    write_text_atomic,
    write_yaml_atomic,
)

__all__ = [
    "RunStats", "build_export_manifest", "write_validation_report",
    "write_yaml_atomic", "write_text_atomic", "build_query_filters_section",
]


@dataclass
class RunStats(BaseRunStats):
    """Extiende `BaseRunStats` (Engine) con los contadores propios de
    Bypass -- ninguno de estos campos aplica a Drills."""

    lookups_resolved: int = 0
    lookups_unresolved: int = 0
    lookups_null_default: int = 0


def write_validation_report(stats: RunStats, path: Path) -> dict:
    # Status de 2 estados, deliberadamente NO migrado a
    # `engine.manifest.determine_status` (3 estados) -- ver docstring del
    # módulo para el porqué.
    report = {
        "run": build_run_section(stats, migration_object="By_Passes"),
        "counts": build_counts_section(stats),
        "lookups": {
            "resolved": stats.lookups_resolved, "unresolved": stats.lookups_unresolved,
            "null_default": stats.lookups_null_default,
        },
        "reference": {
            "missing_historical_origin_id": stats.missing_historical_origin_id,
        },
        "output": build_output_section(stats),
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
        "prototype_version": PROTOTYPE_VERSION, "prototype_status": "review_only",
        "mode": mode,
        "connection": build_connection_section(connection_name),
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
