"""Tests unitarios (sin red) del validador de solo lectura, límite de filas
e identificadores. Ejecutar con: pytest tests/test_db_query_runner.py -v"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.db.exceptions import (
    InvalidIdentifierError,
    QueryRowLimitExceededError,
    ReadOnlyViolationError,
)
from src.db.query_runner import run_query, validate_identifier, validate_read_only_sql


# --------------------------------------------------------------------------
# SQL permitido
# --------------------------------------------------------------------------

ALLOWED_SQL = [
    "SELECT 1",
    "SELECT * FROM Foo",
    "SELECT * FROM Foo WHERE x = 1",
    "  SELECT 1  ",
    "SELECT 1;",
    ";WITH cte AS (SELECT 1 AS x) SELECT * FROM cte",
    "WITH a AS (SELECT 1), b AS (SELECT 2) SELECT * FROM a, b",
    "SELECT * FROM Foo -- comentario con DROP TABLE dentro\nWHERE x=1",
    "SELECT * FROM Foo /* comentario con INSERT INTO dentro */ WHERE x=1",
    "SELECT motivo FROM Foo WHERE motivo = 'DROP TABLE intentado'",
    "SELECT into_date, delete_flag FROM Foo",
    "SELECT * FROM Foo JOIN Bar ON Foo.Id = Bar.FooId",
]


@pytest.mark.parametrize("sql", ALLOWED_SQL)
def test_sql_permitido_no_lanza(sql):
    validate_read_only_sql(sql)  # no debe lanzar


# --------------------------------------------------------------------------
# SQL bloqueado
# --------------------------------------------------------------------------

BLOCKED_SQL = [
    "INSERT INTO Foo VALUES (1)",
    "UPDATE Foo SET x = 1",
    "DELETE FROM Foo",
    "MERGE INTO Foo USING Bar ON Foo.Id = Bar.Id WHEN MATCHED THEN DELETE",
    "CREATE TABLE Foo (x INT)",
    "ALTER TABLE Foo ADD y INT",
    "DROP TABLE Foo",
    "TRUNCATE TABLE Foo",
    "GRANT SELECT ON Foo TO Bar",
    "REVOKE SELECT ON Foo FROM Bar",
    "DENY SELECT ON Foo TO Bar",
    "BACKUP DATABASE Foo TO DISK = 'x.bak'",
    "RESTORE DATABASE Foo FROM DISK = 'x.bak'",
    "DBCC CHECKDB('Foo')",
    "EXEC sp_who",
    "EXECUTE sp_who",
    "BULK INSERT Foo FROM 'archivo.csv'",
    "SELECT * INTO NuevaTabla FROM Foo",
    "SELECT * FROM (SELECT * INTO Tmp FROM Foo) AS sub",
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE Foo",
    "",
    "   ",
    ";",
    ";;",
    "WITH cte AS (SELECT 1) INSERT INTO Foo SELECT * FROM cte",
    "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=X;Trusted_Connection=yes;', 'SELECT 1')",
    "SELECT * FROM OPENDATASOURCE('SQLNCLI', 'Server=X') .Db.dbo.Foo",
]


@pytest.mark.parametrize("sql", BLOCKED_SQL)
def test_sql_bloqueado_lanza(sql):
    with pytest.raises(ReadOnlyViolationError):
        validate_read_only_sql(sql)


def test_multiples_sentencias_mensaje_especifico():
    with pytest.raises(ReadOnlyViolationError, match="sentencia"):
        validate_read_only_sql("SELECT 1; SELECT 2")


def test_select_into_mensaje_especifico():
    with pytest.raises(ReadOnlyViolationError, match="INTO"):
        validate_read_only_sql("SELECT * INTO NuevaTabla FROM Foo")


# --------------------------------------------------------------------------
# Validación de identificadores
# --------------------------------------------------------------------------

VALID_IDENTIFIERS = ["Foo", "foo_bar", "_x", "Tabla1", "ITP_ANALISIS"]
INVALID_IDENTIFIERS = [
    "Foo; DROP TABLE Bar--",
    "foo bar",
    "123foo",
    "foo.bar",
    "[Foo]",
    "",
    "a" * 200,
    None,
]


@pytest.mark.parametrize("name", VALID_IDENTIFIERS)
def test_identificador_valido(name):
    assert validate_identifier(name) == name


@pytest.mark.parametrize("name", INVALID_IDENTIFIERS)
def test_identificador_invalido(name):
    with pytest.raises(InvalidIdentifierError):
        validate_identifier(name)


# --------------------------------------------------------------------------
# Límite de filas -- lectura por lotes con SQLite en memoria (sin red)
# --------------------------------------------------------------------------

@pytest.fixture
def sqlite_engine_100_rows():
    # StaticPool + check_same_thread=False: una base SQLite en memoria solo
    # vive mientras dura una única conexión física; sin esto, cada
    # engine.connect() abriría una base en memoria nueva y vacía.
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE numeros (n INTEGER)"))
        conn.execute(
            text("INSERT INTO numeros (n) VALUES (:n)"),
            [{"n": i} for i in range(100)],
        )
    return engine


def test_run_query_dentro_del_limite(monkeypatch, sqlite_engine_100_rows):
    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: sqlite_engine_100_rows)
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 1000},
    )
    df = run_query("SELECT n FROM numeros ORDER BY n")
    assert len(df) == 100
    assert list(df["n"]) == list(range(100))


def test_run_query_supera_limite_lanza_y_no_devuelve_parcial(monkeypatch, sqlite_engine_100_rows):
    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: sqlite_engine_100_rows)
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 10},
    )
    with pytest.raises(QueryRowLimitExceededError):
        run_query("SELECT n FROM numeros ORDER BY n")


def test_effective_chunk_size_no_supera_max_rows(monkeypatch, sqlite_engine_100_rows):
    """DEFAULT_CHUNK_SIZE (10_000) debe recortarse a max_rows cuando este es
    menor, para no pedir lotes más grandes que el propio límite."""
    seen_sizes = []
    engine = sqlite_engine_100_rows

    class _TrackingResult:
        def __init__(self, real_result):
            self._real = real_result

        def keys(self):
            return self._real.keys()

        def fetchmany(self, size):
            seen_sizes.append(size)
            return self._real.fetchmany(size)

    class _TrackingConn:
        def __init__(self, real_conn):
            self._real = real_conn

        def execute(self, *args, **kwargs):
            return _TrackingResult(self._real.execute(*args, **kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._real.close()

    class _TrackingEngine:
        def connect(self):
            return _TrackingConn(engine.connect())

    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: _TrackingEngine())
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 5},
    )
    with pytest.raises(QueryRowLimitExceededError):
        run_query("SELECT n FROM numeros ORDER BY n")
    assert seen_sizes[0] == 5


def test_run_query_sin_filas_conserva_columnas(monkeypatch, sqlite_engine_100_rows):
    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: sqlite_engine_100_rows)
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 1000},
    )
    df = run_query("SELECT n FROM numeros WHERE n > 999999")
    assert list(df.columns) == ["n"]
    assert len(df) == 0
