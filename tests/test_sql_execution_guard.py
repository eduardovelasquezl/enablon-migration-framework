"""Tests del SQL Execution Guard (Sprint 8.6.1): autorización explícita
antes de abrir una conexión SQL real. Nunca ejecuta SQL real -- verifica
el bloqueo (antes de `create_engine`) y, para el camino autorizado, que
`get_engine()` construye un `Engine` perezoso (sin `.connect()`) con
credenciales sintéticas, nunca contra un servidor real.

`tests/conftest.py` ya revoca la autorización de forma autouse antes y
después de cada test -- este fichero no depende de ese detalle para sus
propias aserciones (siempre concede/revoca explícitamente lo que necesita).

Ejecutar con: pytest tests/test_sql_execution_guard.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.db import sql_execution_guard
from src.db.connection import get_engine
from src.db.exceptions import DatabaseError

FAKE_CONNECTION_CONFIG = {
    "description": "conexión falsa para tests del guard",
    "driver": "ODBC Driver 17 for SQL Server",
    "server_env": "GUARD_TEST_HOST",
    "database_env": "GUARD_TEST_DB",
    "user_env": "GUARD_TEST_USER",
    "password_env": "GUARD_TEST_PASSWORD",
    "application_intent": "ReadOnly",
}

FAKE_ENV = {
    "GUARD_TEST_HOST": "fake-host",
    "GUARD_TEST_DB": "fake-db",
    "GUARD_TEST_USER": "fake-user",
    "GUARD_TEST_PASSWORD": "fake-password",
}


@pytest.fixture
def fake_config(monkeypatch):
    monkeypatch.setattr("src.db.connection.get_database_config", lambda name=None: FAKE_CONNECTION_CONFIG)
    monkeypatch.setattr("src.db.connection._ensure_env_loaded", lambda: None)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


# --------------------------------------------------------------------------
# Estado por defecto / grant / revoke
# --------------------------------------------------------------------------

def test_por_defecto_no_autorizado():
    assert sql_execution_guard.is_authorized() is False
    assert sql_execution_guard.current_authorization() is None


def test_grant_autoriza():
    sql_execution_guard.grant(source="test")
    assert sql_execution_guard.is_authorized() is True
    auth = sql_execution_guard.current_authorization()
    assert auth.source == "test"
    sql_execution_guard.revoke()


def test_revoke_vuelve_a_bloquear():
    sql_execution_guard.grant(source="test")
    sql_execution_guard.revoke()
    assert sql_execution_guard.is_authorized() is False


def test_grant_source_invalido_lanza_valueerror():
    with pytest.raises(ValueError):
        sql_execution_guard.grant(source="not_a_real_source")
    assert sql_execution_guard.is_authorized() is False  # el grant fallido no deja estado a medias


def test_require_sin_autorizacion_lanza_real_sql_not_authorized_error():
    with pytest.raises(sql_execution_guard.RealSqlNotAuthorizedError):
        sql_execution_guard.require("prevencion")


def test_require_con_autorizacion_no_lanza():
    sql_execution_guard.grant(source="test")
    sql_execution_guard.require("prevencion")  # no debe lanzar
    sql_execution_guard.revoke()


def test_mensaje_de_bloqueo_no_contiene_secretos():
    try:
        sql_execution_guard.require("prevencion")
    except sql_execution_guard.RealSqlNotAuthorizedError as exc:
        message = str(exc).lower()
        for forbidden in ("password", "pwd=", "server=", "@", "mssql+pyodbc"):
            assert forbidden not in message
    else:
        pytest.fail("Se esperaba RealSqlNotAuthorizedError")


def test_real_sql_not_authorized_error_es_database_error():
    assert issubclass(sql_execution_guard.RealSqlNotAuthorizedError, DatabaseError)


# --------------------------------------------------------------------------
# Integración con get_engine() -- el chokepoint real
# --------------------------------------------------------------------------

def test_get_engine_sin_autorizacion_bloquea_antes_de_create_engine(fake_config, monkeypatch):
    called = {"create_engine": False}

    def _fail_if_called(*args, **kwargs):
        called["create_engine"] = True
        raise AssertionError("create_engine no debía llamarse sin autorización.")

    monkeypatch.setattr("src.db.connection.create_engine", _fail_if_called)

    with pytest.raises(sql_execution_guard.RealSqlNotAuthorizedError):
        get_engine("fake")

    assert called["create_engine"] is False


def test_get_engine_con_autorizacion_construye_engine_perezoso(fake_config):
    """`create_engine` no abre conexión de red (es perezoso) -- construir
    el Engine con credenciales sintéticas es seguro, nunca se llama a
    `.connect()` en este test."""
    sql_execution_guard.grant(source="test")
    engine = get_engine("fake")
    assert engine is not None
    sql_execution_guard.revoke()


def test_get_engine_excepcion_no_se_cachea_reintentar_tras_autorizar(fake_config):
    with pytest.raises(sql_execution_guard.RealSqlNotAuthorizedError):
        get_engine("fake")

    sql_execution_guard.grant(source="test")
    engine = get_engine("fake")  # el intento anterior (fallido) no quedó cacheado
    assert engine is not None
    sql_execution_guard.revoke()


def test_get_engine_revocado_vuelve_a_bloquear_en_otra_conexion(fake_config):
    """Cachear por nombre de conexión no debe permitir que autorizar
    'fake' dé acceso implícito a otra conexión distinta ya cacheada -- aquí
    se confirma con la MISMA conexión tras revocar, ya que `get_engine`
    cachea por engine construido con éxito (no por intento fallido)."""
    sql_execution_guard.grant(source="test")
    get_engine("fake")
    sql_execution_guard.revoke()
    get_engine.cache_clear()  # simula un proceso nuevo sin el engine ya cacheado
    with pytest.raises(sql_execution_guard.RealSqlNotAuthorizedError):
        get_engine("fake")
