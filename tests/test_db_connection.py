"""Tests de src/db/connection.py.

Las pruebas unitarias (la mayoría) son deterministas y no dependen del
`.env` real de la máquina: se sustituye `get_database_config` por una
especificación sintética mediante monkeypatch, para no acoplarse al
contenido real de config/databases.yaml ni requerir que `.env` esté
poblado en el entorno donde corran los tests.

Las pruebas de integración (al final del archivo) sí usan la conexión real
y solo se ejecutan si RUN_SQL_INTEGRATION_TESTS=1 está en el entorno -- ver
docstring de esa sección.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy.engine import URL

from src.db.connection import ConnectionSpec, get_connection_spec, get_engine
from src.db.exceptions import DatabaseConfigurationError
from src.db.query_runner import run_query

FAKE_CONNECTION_CONFIG = {
    "description": "conexión falsa para tests",
    "driver": "ODBC Driver 17 for SQL Server",
    "server_env": "FAKE_TEST_HOST",
    "database_env": "FAKE_TEST_DB",
    "user_env": "FAKE_TEST_USER",
    "password_env": "FAKE_TEST_PASSWORD",
    "application_intent": "ReadOnly",
}

FAKE_ENV = {
    "FAKE_TEST_HOST": r"ALL4-CJJKW74\SQLEXPRESS",
    "FAKE_TEST_DB": "Prevencion",
    "FAKE_TEST_USER": "ClaudeReadOnly",
    "FAKE_TEST_PASSWORD": "una-contraseña-con-símbolos-;{}=&?",
}


@pytest.fixture
def fake_config(monkeypatch):
    """Sustituye get_database_config por una conexión sintética y evita que
    _ensure_env_loaded intente cargar un .env real."""
    monkeypatch.setattr("src.db.connection.get_database_config", lambda name=None: FAKE_CONNECTION_CONFIG)
    monkeypatch.setattr("src.db.connection._ensure_env_loaded", lambda: None)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    get_engine.cache_clear()
    yield
    get_engine.cache_clear()


# --------------------------------------------------------------------------
# Configuración incompleta / conexión desconocida
# --------------------------------------------------------------------------

def test_falta_variable_de_entorno_lanza_configuration_error(monkeypatch):
    monkeypatch.setattr("src.db.connection.get_database_config", lambda name=None: FAKE_CONNECTION_CONFIG)
    monkeypatch.setattr("src.db.connection._ensure_env_loaded", lambda: None)
    monkeypatch.delenv("FAKE_TEST_HOST", raising=False)
    monkeypatch.setenv("FAKE_TEST_DB", "x")
    monkeypatch.setenv("FAKE_TEST_USER", "x")
    monkeypatch.setenv("FAKE_TEST_PASSWORD", "x")

    with pytest.raises(DatabaseConfigurationError, match="FAKE_TEST_HOST"):
        get_connection_spec("fake")


def test_conexion_desconocida_lanza_configuration_error(monkeypatch):
    def _raise_unknown(name=None):
        raise KeyError(f"No existe la conexión '{name}'")

    monkeypatch.setattr("src.db.connection.get_database_config", _raise_unknown)
    monkeypatch.setattr("src.db.connection._ensure_env_loaded", lambda: None)

    with pytest.raises(DatabaseConfigurationError) as exc_info:
        get_connection_spec("no_existe")
    assert exc_info.value.__cause__ is not None  # se conserva la causa original (raise ... from exc)


# --------------------------------------------------------------------------
# ConnectionSpec no expone la contraseña
# --------------------------------------------------------------------------

def test_connection_spec_no_expone_password_en_repr(fake_config):
    spec = get_connection_spec("fake")
    representacion = repr(spec)
    texto = str(spec)
    assert FAKE_ENV["FAKE_TEST_PASSWORD"] not in representacion
    assert FAKE_ENV["FAKE_TEST_PASSWORD"] not in texto
    assert "password" not in representacion.lower()


def test_connection_spec_url_no_expone_password_en_str(fake_config):
    spec = get_connection_spec("fake")
    url = spec.to_sqlalchemy_url()
    assert isinstance(url, URL)
    # str()/repr() de una URL de SQLAlchemy oculta la contraseña por
    # defecto (la sustituye por '***'); nunca se debe llamar aquí a
    # render_as_string(hide_password=False).
    assert FAKE_ENV["FAKE_TEST_PASSWORD"] not in str(url)
    assert FAKE_ENV["FAKE_TEST_PASSWORD"] not in repr(url)


def test_connection_spec_maneja_backslash_y_simbolos_en_url(fake_config):
    spec = get_connection_spec("fake")
    url = spec.to_sqlalchemy_url()
    assert url.host == r"ALL4-CJJKW74\SQLEXPRESS"
    assert url.password == FAKE_ENV["FAKE_TEST_PASSWORD"]
    # get_backend_name / drivername deben reflejar mssql+pyodbc
    assert url.drivername == "mssql+pyodbc"


# --------------------------------------------------------------------------
# Caché de engine
# --------------------------------------------------------------------------

def test_get_engine_cachea_por_nombre(fake_config):
    e1 = get_engine("fake")
    e2 = get_engine("fake")
    assert e1 is e2


def test_get_engine_no_conecta_de_inmediato(fake_config):
    # create_engine es perezoso: no debe intentar abrir una conexión real
    # solo por construir el Engine (esto debe funcionar sin red ni driver
    # ODBC instalado).
    engine = get_engine("fake")
    assert engine is not None


# --------------------------------------------------------------------------
# Pruebas de integración reales -- SOLO si RUN_SQL_INTEGRATION_TESTS=1
#
# Si la bandera no está activa: se omiten (pytest.skip), sin más.
# Si está activa y la conexión falla: la prueba FALLA (no se atrapa la
# excepción ni se convierte en skip) -- así lo pidió el usuario.
#
# Verifican identidad (servidor/base/usuario) y AUSENCIA de permisos de
# escritura consultando funciones de metadatos de SQL Server
# (HAS_PERMS_BY_NAME) mediante SELECT -- nunca se intenta una operación de
# escritura real para comprobar que se deniega.
# --------------------------------------------------------------------------

RUN_INTEGRATION = os.environ.get("RUN_SQL_INTEGRATION_TESTS") == "1"

pytestmark_integration = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="RUN_SQL_INTEGRATION_TESTS no está activo (usar =1 para probar contra SQL Server real).",
)


@pytestmark_integration
@pytest.mark.parametrize("connection_name", ["prevencion", "gct"])
def test_integracion_identidad_y_permisos_solo_lectura(connection_name):
    identidad = run_query(
        "SELECT SUSER_SNAME() AS usuario, DB_NAME() AS base, @@SERVERNAME AS servidor",
        connection=connection_name,
    )
    assert len(identidad) == 1
    fila = identidad.iloc[0]
    assert fila["usuario"] == "ClaudeReadOnly"
    assert fila["base"]
    assert fila["servidor"]

    permisos = run_query(
        "SELECT "
        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT') AS puede_insertar, "
        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE') AS puede_actualizar, "
        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE') AS puede_borrar, "
        "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE') AS puede_crear_tabla",
        connection=connection_name,
    )
    fila_permisos = permisos.iloc[0]
    assert fila_permisos["puede_insertar"] == 0
    assert fila_permisos["puede_actualizar"] == 0
    assert fila_permisos["puede_borrar"] == 0
    assert fila_permisos["puede_crear_tabla"] == 0
