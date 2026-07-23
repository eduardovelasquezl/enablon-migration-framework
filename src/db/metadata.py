"""
Introspección de esquema para las tablas de origen.

Útil para Función 2 del framework original (Revisión SQL): antes de dar por
buena una query nueva, comprobar qué columnas existen realmente, sus tipos,
y si hay columnas obligatorias en el destino que no tengan equivalente aquí.

Estas funciones usan el inspector de SQLAlchemy (`sqlalchemy.inspect`), que
no pasa por `query_runner.validate_read_only_sql` (no construye el SQL como
texto libre) -- por eso aquí la validación estricta de identificadores
(`validate_identifier`) es la única defensa antes de pasar `table`/`schema`
al inspector o a un SQL construido a mano (`row_count`).
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from src.db.connection import get_engine
from src.db.exceptions import QueryExecutionError
from src.db.query_runner import run_query, validate_identifier


def list_tables(connection: str | None = None, schema: str = "dbo") -> list[str]:
    schema = validate_identifier(schema, kind="nombre de esquema")
    engine = get_engine(connection)
    try:
        return inspect(engine).get_table_names(schema=schema)
    except SQLAlchemyError as exc:
        raise QueryExecutionError(
            f"Fallo al listar tablas (conexión='{connection}', esquema='{schema}')."
        ) from exc


def describe_table(table: str, connection: str | None = None, schema: str = "dbo") -> pd.DataFrame:
    """Devuelve columnas, tipo y nulabilidad de una tabla — el equivalente
    de mirar el catálogo antes de escribir/validar una query."""
    table = validate_identifier(table, kind="nombre de tabla")
    schema = validate_identifier(schema, kind="nombre de esquema")
    engine = get_engine(connection)
    try:
        columns = inspect(engine).get_columns(table, schema=schema)
    except SQLAlchemyError as exc:
        raise QueryExecutionError(
            f"Fallo al describir la tabla '{schema}.{table}' (conexión='{connection}')."
        ) from exc
    return pd.DataFrame(
        [
            {"columna": c["name"], "tipo": str(c["type"]), "nullable": c["nullable"]}
            for c in columns
        ]
    )


def row_count(table: str, connection: str | None = None, schema: str = "dbo") -> int:
    table = validate_identifier(table, kind="nombre de tabla")
    schema = validate_identifier(schema, kind="nombre de esquema")
    df = run_query(f"SELECT COUNT(*) AS n FROM [{schema}].[{table}]", connection=connection)
    return int(df["n"].iloc[0])
