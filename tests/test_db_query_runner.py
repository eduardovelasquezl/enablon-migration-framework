"""Tests unitarios (sin red) del validador de solo lectura, límite de filas
e identificadores. Ejecutar con: pytest tests/test_db_query_runner.py -v"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from src.db.exceptions import (
    InvalidIdentifierError,
    QueryExecutionError,
    QueryRowLimitExceededError,
    ReadOnlyViolationError,
)
from src.db.query_runner import (
    _sanitize_error_detail,
    run_query,
    validate_identifier,
    validate_read_only_sql,
)


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


# --------------------------------------------------------------------------
# Observabilidad de errores de base de datos (Sprint 9.1) -- diagnóstico del
# primer fallo real de Drills (execution_id 458dfb9f27f3): el `str()` por
# defecto de un `SQLAlchemyError` real solo se conservaba en `__cause__`,
# nunca se registraba, así que se perdía en cuanto terminaba el proceso.
# Ninguno de estos tests abre SQL real -- un engine/conexión falso basta
# para forzar el mismo camino de excepción que tomaría un fallo real.
# --------------------------------------------------------------------------

class _FailingConn:
    """Conexión falsa cuyo `execute()` siempre lanza la excepción dada --
    simula un fallo de SQL Server/driver sin abrir ninguna red."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def execute(self, *args, **kwargs):
        raise self._exc

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FailingEngine:
    def __init__(self, exc: Exception):
        self._exc = exc

    def connect(self):
        return _FailingConn(self._exc)


def _make_fake_operational_error(detail_message: str) -> OperationalError:
    """Construye un `OperationalError` real de SQLAlchemy (no un mock) con
    un `.orig` cuyo `str()` es `detail_message` -- así el texto que viaja
    hasta `run_query` es el mismo tipo de objeto que produciría pyodbc."""
    orig = Exception(detail_message)
    return OperationalError("SELECT 1", {}, orig)


def _run_failing_query(monkeypatch, fake_exc: Exception):
    monkeypatch.setattr("src.db.query_runner.get_engine", lambda name=None: _FailingEngine(fake_exc))
    monkeypatch.setattr(
        "src.db.query_runner.get_safety_settings",
        lambda: {"max_rows_per_query": 1000},
    )
    return lambda: run_query("SELECT 1")


def test_query_execution_error_conserva_cause(monkeypatch):
    """1. DatabaseError conserva __cause__."""
    fake_exc = _make_fake_operational_error(
        "[08001] Login failed for user 'ClaudeReadOnly'. (18456)"
    )
    call = _run_failing_query(monkeypatch, fake_exc)

    with pytest.raises(QueryExecutionError) as excinfo:
        call()

    assert excinfo.value.__cause__ is fake_exc


def test_verbose_registra_causa_tecnica_sanitizada(monkeypatch, caplog):
    """2. logging captura la causa original. 4. --verbose (nivel DEBUG)
    muestra el diagnóstico técnico."""
    fake_exc = _make_fake_operational_error("Login failed for user 'ClaudeReadOnly'. (18456)")
    call = _run_failing_query(monkeypatch, fake_exc)

    with caplog.at_level(logging.DEBUG, logger="src.db.query_runner"):
        with pytest.raises(QueryExecutionError):
            call()

    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert debug_records, "se esperaba un registro DEBUG con la causa técnica"
    joined = "\n".join(r.getMessage() for r in debug_records)
    assert "OperationalError" in joined
    assert "Login failed for user 'ClaudeReadOnly'" in joined
    # Deliberadamente sin exc_info: ver comentario en query_runner.py -- el
    # traceback real expondría el mensaje sin sanear.
    assert all(r.exc_info is None for r in debug_records)


def test_modo_normal_no_expone_causa_tecnica(monkeypatch, caplog):
    """3. El modo normal (sin --verbose, nivel INFO) no expone detalles
    técnicos -- ni en logs ni en el mensaje de la excepción."""
    fake_exc = _make_fake_operational_error("Login failed for user 'ClaudeReadOnly'. (18456)")
    call = _run_failing_query(monkeypatch, fake_exc)

    with caplog.at_level(logging.INFO, logger="src.db.query_runner"):
        with pytest.raises(QueryExecutionError) as excinfo:
            call()

    assert not any(r.levelno == logging.DEBUG for r in caplog.records)
    assert "Login failed" not in caplog.text
    assert "Login failed" not in str(excinfo.value)


def test_sanitize_error_detail_redacta_credenciales():
    """5. secrets/connection strings se sanitizan."""
    detail = "Connection failed: Password=SuperSecret123;PWD=OtroSecreto;Server=X;Token=abc.def.ghi"
    sanitized = _sanitize_error_detail(detail)

    assert "SuperSecret123" not in sanitized
    assert "OtroSecreto" not in sanitized
    assert "abc.def.ghi" not in sanitized
    assert sanitized.count("REDACTED") == 3
    # El texto no sensible alrededor se conserva -- no es un borrado ciego.
    assert "Server=X" in sanitized


def test_sanitize_error_detail_trunca_mensajes_largos():
    detail = "x" * 1000
    sanitized = _sanitize_error_detail(detail)

    assert len(sanitized) <= 520
    assert sanitized.endswith("(truncado)")


def test_causa_tecnica_sanitizada_incluso_en_log_verbose(monkeypatch, caplog):
    """5 (extremo a extremo): si el driver incrusta algo con pinta de
    credencial en su propio mensaje, ni siquiera el log en modo --verbose
    lo expone -- no depende solo de hide_parameters (src/db/connection.py),
    que no cubre el texto libre de un DBAPIError.orig."""
    fake_exc = _make_fake_operational_error(
        "Login failed. Retry with Password=SuperSecret123 against the server."
    )
    call = _run_failing_query(monkeypatch, fake_exc)

    with caplog.at_level(logging.DEBUG, logger="src.db.query_runner"):
        with pytest.raises(QueryExecutionError):
            call()

    assert "SuperSecret123" not in caplog.text
    assert "REDACTED" in caplog.text


def test_no_se_necesita_sql_real(monkeypatch):
    """6. Ningún test de este bloque abre una conexión real -- se ejerce con
    un engine/conexión falso; lo confirma el hecho de que corren sin
    EMF_ALLOW_REAL_SQL ni credenciales reales configuradas."""
    fake_exc = _make_fake_operational_error("cualquier fallo")
    call = _run_failing_query(monkeypatch, fake_exc)
    with pytest.raises(QueryExecutionError):
        call()
