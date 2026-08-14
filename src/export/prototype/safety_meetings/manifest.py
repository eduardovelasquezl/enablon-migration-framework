"""Manifest/validation report para safety_meetings.Group_Meetings (Sprint 9.7).

`write_yaml_atomic`/`write_text_atomic`/hashing/`git_commit`/`PROTOTYPE_VERSION`/
`build_*_section`/`determine_status` vienen de `src.export.engine.manifest`
(Sprint 9.6) -- REUSED_ENGINE directo, sin ningún import de `drills`/`bypass`.

`RunStats` extiende `BaseRunStats` (Engine) con los contadores propios de
Safety Meetings: `lookups_resolved`/`lookups_unresolved`/`lookups_empty`
(3 categorías, no 2 como Bypass -- ver más abajo por qué).

DECISIÓN DE DISEÑO (Fase 10 del encargo de Sprint 9.7, no copiada de
Drills ni de Bypass): Safety Meetings SÍ usa `determine_status` de 3
estados (`SUCCESS`/`SUCCESS_WITH_WARNINGS`/`FAILED_VALIDATION`), la misma
función que ya usa Drills. Motivo propio de este módulo, no heredado:
ninguno de sus 3 lookups (`CS_WorkflowStatus`/`CS_Level`/`CS_Letter`) tiene
un `nullcontrol`/default documentado -- cualquier valor vacío o sin
coincidencia queda `unresolved`/`empty` de verdad (nunca se enmascara con
un literal por defecto, a diferencia de Bypass, cuyos 4 lookups SÍ tienen
default documentado y por eso "sin default" era la excepción, no la
norma). Con datos reales ya se observaron ~19 filas con `CS_Level`/
`CS_Letter` vacíos -- un `SUCCESS` que no distinga eso de un run
perfectamente limpio sería activamente engañoso para este módulo. Esto es
evidencia -- no una copia -- de que 3 estados es el comportamiento
correcto aquí; ver el informe de cierre de Sprint 9.7 para la
reevaluación de `determine_status` de Bypass con este tercer punto de
datos."""
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
    determine_status,
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
    Safety Meetings -- 3 categorías de resultado de lookup, no 2 como
    Bypass, porque aquí "vacío"/"sin coincidencia" son casos reales y
    distintos, ninguno enmascarado por un default."""

    lookups_resolved: int = 0
    lookups_unresolved: int = 0
    lookups_empty: int = 0


def write_validation_report(stats: RunStats, path: Path) -> dict:
    result, blocking_errors, warnings = determine_status(stats.errors, stats.warnings)
    report = {
        "run": build_run_section(stats, migration_object="Group_Meetings"),
        "counts": build_counts_section(stats),
        "lookups": {
            "resolved": stats.lookups_resolved,
            "unresolved": stats.lookups_unresolved,
            "empty": stats.lookups_empty,
        },
        "reference": {
            "missing_historical_origin_id": stats.missing_historical_origin_id,
        },
        "output": build_output_section(stats),
        "status": {
            "result": result,
            "blocking_errors": blocking_errors,
            "warnings": warnings,
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
        "migration_object": "Group_Meetings", "module": "safety_meetings",
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
