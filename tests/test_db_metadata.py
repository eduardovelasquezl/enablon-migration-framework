"""Tests de src/db/metadata.py -- sin red, usando SQLite en memoria
inyectado en lugar de get_engine, más los casos de validación de
identificadores que no llegan a necesitar ningún engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.db import metadata
from src.db.exceptions import InvalidIdentifierError


@pytest.fixture
def sqlite_engine_con_tabla():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE Personas (Id INTEGER, Nombre VARCHAR(50))"))
        conn.execute(text("INSERT INTO Personas (Id, Nombre) VALUES (1, 'Ana'), (2, 'Luis')"))
    return engine


# --------------------------------------------------------------------------
# Validación de identificadores -- se dispara ANTES de tocar el engine
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_table", ["Foo; DROP TABLE Bar--", "foo bar", "[Foo]", ""])
def test_describe_table_rechaza_tabla_invalida(bad_table):
    with pytest.raises(InvalidIdentifierError):
        metadata.describe_table(bad_table)


@pytest.mark.parametrize("bad_schema", ["dbo; DROP TABLE Bar--", "dbo.x", ""])
def test_describe_table_rechaza_schema_invalido(bad_schema):
    with pytest.raises(InvalidIdentifierError):
        metadata.describe_table("Foo", schema=bad_schema)


@pytest.mark.parametrize("bad_table", ["Foo; DROP TABLE Bar--", "foo bar"])
def test_row_count_rechaza_tabla_invalida(bad_table):
    with pytest.raises(InvalidIdentifierError):
        metadata.row_count(bad_table)


def test_list_tables_rechaza_schema_invalido():
    with pytest.raises(InvalidIdentifierError):
        metadata.list_tables(schema="dbo; DROP TABLE Bar--")


# --------------------------------------------------------------------------
# Comportamiento real contra SQLite (identificadores válidos)
# --------------------------------------------------------------------------

def test_row_count_devuelve_conteo_correcto(monkeypatch, sqlite_engine_con_tabla):
    monkeypatch.setattr("src.db.metadata.get_engine", lambda name=None: sqlite_engine_con_tabla)
    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: sqlite_engine_con_tabla)
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 1000},
    )
    # SQLite no tiene esquema "dbo"; row_count construye "[schema].[table]",
    # así que se prueba con schema="main" (el de SQLite) para validar la
    # ruta real de ejecución, no solo la validación de identificadores.
    total = metadata.row_count("Personas", schema="main")
    assert total == 2
