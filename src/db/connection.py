"""
Conexión SQL de solo lectura.

Nunca usar este módulo para ejecutar INSERT/UPDATE/DELETE/DROP/ALTER, ni
contra el SQL origen ni contra ningún otro sistema. Las salvaguardas de
config/databases.yaml (safety.forbid_statements) se aplican en
query_runner.py antes de ejecutar cualquier sentencia.

Este es el ÚNICO módulo del proyecto que lee `.env` / `os.environ` para
resolver credenciales. Toda configuración no sensible (driver, host de
variable de entorno a usar, application intent...) se obtiene de
`src.config`, no se vuelve a parsear `config/databases.yaml` aquí.

La garantía real de "solo lectura" es el permiso del login SQL a nivel de
servidor (aquí: `ClaudeReadOnly` con únicamente `db_datareader` en las
bases GCT y Prevencion, y `public` como único rol de servidor -- sin GRANT
SELECT explícito documentado ni asumido). `ApplicationIntent=ReadOnly` en
la cadena de conexión es una señal de enrutamiento adicional para Always On
Availability Groups, NO un control de seguridad por sí mismo.

Sprint 8.6.1 (SQL Execution Guard): que el entorno TENGA conectividad real
(credenciales válidas, red accesible) nunca implica autorización de uso --
`get_engine()` exige una autorización explícita y vigente para la
ejecución actual (`src.db.sql_execution_guard`) antes de construir el
`Engine`, independientemente de si la operación es `sample` o `full`. Ver
`docs/01-architecture/sql-execution-guard.md`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_database_config
from src.db.exceptions import DatabaseConfigurationError
from src.db.sql_execution_guard import require as require_real_sql_authorization

_env_loaded = False


def _ensure_env_loaded() -> None:
    """Carga `.env` una sola vez por proceso. No hace nada si ya se cargó."""
    global _env_loaded
    if not _env_loaded:
        load_dotenv()
        _env_loaded = True


@dataclass
class ConnectionSpec:
    """Especificación resuelta de una conexión: metadatos de
    config/databases.yaml + credenciales de `.env`.

    `password` se excluye deliberadamente de `repr()`/`str()`
    (`field(repr=False)`) -- nunca debe aparecer en logs, tracebacks, ni en
    la representación por defecto de este objeto.
    """

    name: str
    description: str
    driver: str
    server: str
    database: str
    user: str
    password: str = field(repr=False)
    application_intent: str = "ReadOnly"
    trust_server_certificate: bool = True

    def to_sqlalchemy_url(self) -> URL:
        """Construye la URL de conexión con `sqlalchemy.engine.URL.create`,
        que percent-encodea usuario/contraseña/host correctamente (barras
        invertidas de instancia con nombre, símbolos en la contraseña,
        etc.) -- no se construye ninguna cadena ODBC a mano.
        """
        query: dict[str, str] = {
            "driver": self.driver,
            "ApplicationIntent": self.application_intent,
        }
        if self.trust_server_certificate:
            query["TrustServerCertificate"] = "yes"

        return URL.create(
            "mssql+pyodbc",
            username=self.user,
            password=self.password,
            host=self.server,
            database=self.database,
            query=query,
        )


def _resolve_trust_server_certificate() -> bool:
    """Determina si se añade `TrustServerCertificate=yes`.

    Se obtiene de la variable de entorno `SQL_TRUST_SERVER_CERTIFICATE`
    ("yes"/"no", no sensible a mayúsculas). Por defecto `True` -- pensado
    para una instancia local (SQL Server Express) sin certificado válido --
    pero nunca queda fijado incondicionalmente: cualquier entorno puede
    desactivarlo con `SQL_TRUST_SERVER_CERTIFICATE=no`.
    """
    raw = os.environ.get("SQL_TRUST_SERVER_CERTIFICATE", "yes")
    return raw.strip().lower() not in ("no", "false", "0")


def _read_env(var_name: str, connection_name: str) -> str:
    value = os.environ.get(var_name)
    if not value:
        raise DatabaseConfigurationError(
            f"Falta la variable de entorno '{var_name}' para la conexión "
            f"'{connection_name}'. Copia .env.example a .env y rellénala."
        )
    return value


def get_connection_spec(name: str | None = None) -> ConnectionSpec:
    """Construye la especificación de conexión a partir de
    `src.config.get_database_config()` (metadatos no sensibles) + `.env`
    (credenciales).

    `name=None` usa la conexión `default` declarada en
    config/databases.yaml -- se documenta aquí como conexión "default" en
    los mensajes de error, ya que este módulo no vuelve a leer esa clave
    por su cuenta.
    """
    _ensure_env_loaded()
    label = name or "default"

    try:
        conn_cfg = get_database_config(name)
    except KeyError as exc:
        raise DatabaseConfigurationError(
            f"No se pudo resolver la conexión '{label}': {exc}"
        ) from exc

    return ConnectionSpec(
        name=label,
        description=conn_cfg.get("description", ""),
        driver=conn_cfg["driver"],
        server=_read_env(conn_cfg["server_env"], label),
        database=_read_env(conn_cfg["database_env"], label),
        user=_read_env(conn_cfg["user_env"], label),
        password=_read_env(conn_cfg["password_env"], label),
        application_intent=conn_cfg.get("application_intent", "ReadOnly"),
        trust_server_certificate=_resolve_trust_server_certificate(),
    )


@lru_cache(maxsize=None)
def get_engine(name: str | None = None) -> Engine:
    """Devuelve un `Engine` de SQLAlchemy cacheado para la conexión pedida.

    Cacheado por nombre de conexión para no reabrir conexiones en cada
    llamada dentro del mismo proceso. `create_engine` no conecta de forma
    inmediata (es perezoso) -- el primer intento de red ocurre en el
    primer `.connect()`/ejecución real.

    Sprint 8.6.1: exige `src.db.sql_execution_guard.require()` ANTES de
    `create_engine()` -- es el único chokepoint universal (todo lo demás
    que puede abrir SQL real pasa por aquí, directa o transitivamente:
    `run_query`, `src.db.metadata.*`, `src.analysis.sql_inventory`), así
    que basta gatear aquí para cubrir cualquier camino presente o futuro.
    Una excepción no se cachea (`lru_cache` no memoriza excepciones) -- un
    segundo intento, ya autorizado, vuelve a evaluarse desde cero.

    Sprint 9.1 (diagnóstico del primer fallo real de Drills): `hide_parameters=True`
    -- sin esto, el `str()` por defecto de un `SQLAlchemyError` real (p. ej.
    `OperationalError`) incluye el texto íntegro de la SQL ejecutada y los
    valores de sus parámetros (`[SQL: ...] [parameters: ...]`), lo que viola
    la regla de `src/db/exceptions.py` de no exponer nunca el texto de la
    consulta en un mensaje de excepción. No afecta a la ejecución -- solo a
    cómo SQLAlchemy formatea sus propios mensajes de error.
    """
    spec = get_connection_spec(name)
    require_real_sql_authorization(spec.name)
    try:
        return create_engine(spec.to_sqlalchemy_url(), pool_pre_ping=True, hide_parameters=True)
    except SQLAlchemyError as exc:
        raise DatabaseConfigurationError(
            f"No se pudo construir el motor de conexión para '{spec.name}'."
        ) from exc
