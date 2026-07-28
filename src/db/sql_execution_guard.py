"""SQL Execution Guard -- autorización explícita para abrir una conexión
SQL real (Sprint 8.6.1, incidente contenido durante Sprint 8.6: ver
`reports/executions/2026-07-28/Informe-SQL-Execution-Guard-EMF.md` § 9).

Principio de seguridad (encargo de este sprint): "una ejecución que pueda
abrir una conexión SQL real debe estar bloqueada por defecto". La
disponibilidad de credenciales (`.env` poblado, conectividad de red real)
NUNCA implica autorización de uso -- ese es exactamente el error que
causó el incidente: el entorno SÍ tenía conectividad real, y nada la
bloqueaba.

Diseño -- por qué un estado de módulo controlado, y no un parámetro
enhebrado por toda la pila de llamadas:

- El único chokepoint universal para abrir una conexión real es
  `src.db.connection.get_engine()` (todo lo demás -- `run_query`,
  `run_query_file`, `grouped_count`, `src.db.metadata.list_tables`/
  `describe_table`/`row_count`, `src.analysis.sql_inventory` -- lo llama
  directa o transitivamente). Enhebrar un parámetro de autorización desde
  la CLI hasta ahí cruzaría `ExecutionRequest`, `PipelineFactory`,
  `DrillsQueryStage`, `extract_drills` y `run_query` -- alto riesgo para
  un cambio de seguridad que debe ser mínimo y auditable.
- Este módulo expone `grant()`/`revoke()`/`require()` como la única API
  para tocar el estado -- nunca se muta directamente. `revoke()` es
  obligatorio en tests (fixture autouse en `tests/conftest.py`) para que
  ninguna autorización concedida por un test se filtre a otro -- mismo
  cuidado de aislamiento que `ADR-010: No Hidden State` exige para
  cualquier estado compartido, aplicado aquí de forma explícita y
  reseteable, no implícita.
- La autorización NUNCA ES por defecto: `_current` empieza en `None` en
  cada proceso nuevo (fail closed).

Este módulo NO valida el contenido de una consulta (eso sigue siendo
`query_runner.validate_read_only_sql`, sin cambios) -- solo si está
permitido, para esta ejecución, siquiera intentar abrir una conexión.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.db.exceptions import DatabaseError

ENV_VAR = "EMF_ALLOW_REAL_SQL"

_VALID_SOURCES = frozenset({"cli_flag", "env_var", "test"})


class RealSqlNotAuthorizedError(DatabaseError):
    """Se intentó resolver una conexión SQL real
    (`src.db.connection.get_engine()`) sin autorización explícita vigente
    para esta ejecución. Se lanza ANTES de `create_engine()` -- ninguna
    conexión de red se intenta.

    El mensaje nunca incluye contraseñas, cadenas de conexión ni
    contenido de `.env` -- solo el nombre lógico de la conexión pedida y
    cómo autorizarla."""


@dataclass(frozen=True)
class SqlExecutionAuthorization:
    """Registro inmutable de una autorización concedida explícitamente
    para la ejecución actual del proceso. Nunca se construye de forma
    implícita -- solo `grant()` la crea."""

    source: str
    granted_at: datetime

    def __post_init__(self) -> None:
        if self.source not in _VALID_SOURCES:
            raise ValueError(
                f"SqlExecutionAuthorization.source={self.source!r} no es válido "
                f"(válidos: {sorted(_VALID_SOURCES)})."
            )


_current: SqlExecutionAuthorization | None = None


def grant(*, source: str) -> SqlExecutionAuthorization:
    """Concede autorización de SQL real para el resto de esta ejecución
    (proceso). `source` documenta CÓMO se concedió (`"cli_flag"` ->
    `--allow-real-sql`; `"env_var"` -> `EMF_ALLOW_REAL_SQL=1`; `"test"` ->
    fixture de test que necesita ejercitar el camino autorizado sin SQL
    real, ver `tests/conftest.py`) -- nunca silenciosa, siempre trazable."""
    global _current
    _current = SqlExecutionAuthorization(source=source, granted_at=datetime.now(timezone.utc))
    return _current


def revoke() -> None:
    """Vuelve al estado por defecto: SQL real bloqueado. Llamado por la
    fixture autouse de tests (`tests/conftest.py`) antes y después de
    cada test -- ninguna autorización debe sobrevivir entre tests."""
    global _current
    _current = None


def is_authorized() -> bool:
    return _current is not None


def current_authorization() -> SqlExecutionAuthorization | None:
    return _current


def require(connection_name: str) -> None:
    """Lanza `RealSqlNotAuthorizedError` si no hay autorización vigente.
    Llamada por `src.db.connection.get_engine()` justo antes de
    `create_engine()` -- el único punto de bloqueo real."""
    if not is_authorized():
        raise RealSqlNotAuthorizedError(
            f"Apertura de conexión SQL real bloqueada para la conexión "
            f"{connection_name!r} -- esta operación puede usar SQL Server real "
            "y está bloqueada por defecto. Añade --allow-real-sql tras recibir "
            f"autorización técnica explícita (o exporta {ENV_VAR}=1). "
            "No se abrió ninguna conexión."
        )
