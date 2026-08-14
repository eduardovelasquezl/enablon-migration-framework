"""Piezas genéricas de manifest/validation report (Sprint 9.6).

Extraído de `drills/manifest.py` y `bypass/manifest.py` tras confirmar, línea
a línea, qué es realmente idéntico entre ambos (Sprint 9.5.1 § Fase 1/2):

- `write_yaml_atomic`/`write_text_atomic`: ya eran compartidas -- Bypass las
  importaba directamente de `drills/manifest.py` (acoplamiento bypass ->
  drills que este refactor elimina, moviendo el original aquí y hacienda que
  AMBOS módulos importen del Engine, nunca uno del otro).
- `_sha256_file`/`_sha256_text`/`_git_commit`: estaban copiadas LITERAL en
  `bypass/manifest.py` en vez de importadas -- hallazgo propio de Sprint
  9.5.1/9.6 (ni siquiera seguían el patrón de import ya usado en el mismo
  fichero para `write_yaml_atomic`).
- `BaseRunStats`: el subconjunto de campos idéntico carácter a carácter
  entre `drills.manifest.RunStats` y `bypass.manifest.RunStats` (13 de 17 /
  13 de 15 respectivamente) -- cada módulo sigue teniendo su propia
  subclase con SUS campos de extensión (`entities_*`/`dates_*` en Drills,
  `lookups_*` en Bypass), nunca forzados a una clase común.
- `determine_status`: lógica de 3 estados YA existente en Drills, sin
  cambios de comportamiento para Drills. Bypass NO se migra a esta función
  en este sprint -- ver nota en `PROTOTYPE_VERSION`/`determine_status` más
  abajo y el informe de Sprint 9.6 § Fase 6 para el porqué (cambiar el
  cálculo de estado de Bypass alteraría su comportamiento observable, no
  autorizado en un refactor behavior-preserving).
- `build_connection_section`/`build_counts_section`/`build_output_section`/
  `build_run_section`: sub-diccionarios de forma y valores YA idénticos en
  ambos manifests/reports (verificado comparando los literales de ambos
  ficheros antes de extraer una sola clave).

NO se extrae aquí (y sigue module-specific, deliberadamente): el resto de
`build_validation_report`/`build_export_manifest` de cada módulo -- sus
secciones adicionales (`reference`/`entities`/`dates` en Drills, `lookups`
en Bypass; `rules_applied`/`open_questions`/hashes extendidos en Drills)
tienen forma genuinamente distinta, no solo nombres distintos.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import yaml

PROTOTYPE_VERSION = "0.1.0-prototype"

SUCCESS = "SUCCESS"
SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
FAILED_VALIDATION = "FAILED_VALIDATION"
FAILED_EXECUTION = "FAILED_EXECUTION"


# ---------------------------------------------------------------------------
# Hashing / git / escritura atómica -- puras, sin estado, ya demostradas
# idénticas en las dos implementaciones existentes.
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_commit() -> str | None:
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
    """Escritura atómica genérica (temporal + `os.replace`) -- usada por
    `validation_report.yaml`, `export_manifest.yaml` y `comparison_report.yaml`
    de cualquier módulo."""
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


# ---------------------------------------------------------------------------
# RunStats -- núcleo compartido
# ---------------------------------------------------------------------------

@dataclass
class BaseRunStats:
    """Núcleo de `RunStats` idéntico en Drills y Bypass -- cada módulo
    declara su propia subclase (`drills.manifest.RunStats`,
    `bypass.manifest.RunStats`) añadiendo SOLO sus campos de extensión
    propios (ver docstring del módulo). No instanciar directamente desde un
    pipeline concreto -- es la base, no el contrato final de ningún módulo."""

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

    output_path: str = ""
    output_encoding: str = ""
    output_bom: bool = False
    output_delimiter: str = ""
    output_line_terminator: str = ""
    output_column_count: int = 0
    output_columns: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cálculo de estado -- 3 estados, lógica ya vigente en Drills sin cambios.
#
# Bypass NO usa esta función todavía (sigue con su propio cálculo de 2
# estados en `bypass/manifest.py`) -- migrarlo aquí haría que Bypass
# empezara a devolver SUCCESS_WITH_WARNINGS cuando antes devolvía SUCCESS,
# un cambio de comportamiento observable que este sprint (refactor
# behavior-preserving) NO autoriza. Clasificación (Sprint 9.6 § Fase 6): A
# (diferencia accidental -- no hay ninguna decisión de diseño documentada
# que justifique 2 estados en vez de 3) y C a la vez (capability genérica
# que faltaba declarar) -- no B. Queda registrado para que un sprint
# posterior decida migrar Bypass explícitamente, con esa decisión visible
# en su propio commit, no oculta dentro de un refactor de infraestructura.
# ---------------------------------------------------------------------------

def determine_status(errors: Sequence[str], warnings: Sequence[str]) -> tuple[str, list[str], list[str]]:
    blocking = list(errors)
    warning_list = list(warnings)
    if blocking:
        return FAILED_VALIDATION, blocking, warning_list
    if warning_list:
        return SUCCESS_WITH_WARNINGS, blocking, warning_list
    return SUCCESS, blocking, warning_list


# ---------------------------------------------------------------------------
# Sub-secciones de forma ya idéntica en ambos manifests/reports.
# ---------------------------------------------------------------------------

def build_connection_section(connection_name: str) -> dict:
    return {
        "name": connection_name,
        "note": "Sin credenciales -- ver config/databases.yaml y .env (no incluidos aquí).",
    }


def build_counts_section(stats: BaseRunStats) -> dict:
    return {
        "rows_read": stats.rows_read,
        "rows_transformed": stats.rows_transformed,
        "rows_exported": stats.rows_exported,
        "rows_excluded": stats.rows_excluded,
        "warnings": len(stats.warnings),
        "errors": len(stats.errors),
    }


def build_output_section(stats: BaseRunStats) -> dict:
    return {
        "path": stats.output_path,
        "encoding": stats.output_encoding,
        "bom": stats.output_bom,
        "delimiter": stats.output_delimiter,
        "line_terminator": stats.output_line_terminator,
        "column_count": stats.output_column_count,
        "columns": stats.output_columns,
    }


def build_run_section(
    stats: BaseRunStats, *, migration_object: str, prototype_status: str = "review_only",
) -> dict:
    return {
        "run_id": stats.run_id,
        "timestamp": stats.timestamp,
        "mode": stats.mode,
        "connection_name": stats.connection_name,
        "migration_object": migration_object,
        "prototype_status": prototype_status,
    }


def build_query_filters_section(
    *,
    compiled_filters: Sequence[Any],
    source_sql_sha256: str,
    generated_sql_file: str | None,
    generated_sql_sha256: str | None,
) -> dict:
    """Sección `query_filters` de `export_manifest.yaml` (Query Engine v0.1).

    Ya era 100% genérica antes de Sprint 9.6 (`compiled_filters` son objetos
    `CompiledFilter`, o cualquier objeto con una propiedad `manifest_entry`
    -- se evita importar `src.query` aquí para no crear un acoplamiento
    circular entre `src.export` y `src.query`); vivía en `drills/manifest.py`
    y Bypass la importaba directamente de Drills -- movida aquí para que
    ambos módulos dependan del Engine, nunca uno del otro. Nunca incluye el
    fragmento SQL, los nombres de parámetro ni ningún valor de conexión --
    solo `field`/`operator`/`value` por filtro.
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
