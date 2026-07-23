"""
Excepciones propias del componente de conexión SQL (src/db/).

Todas heredan de `DatabaseError`, para permitir un `except DatabaseError`
genérico desde el resto del proyecto sin tener que enumerar cada subtipo.

Regla de todo este módulo: ningún mensaje de excepción puede contener una
contraseña, una cadena de conexión/URL completa, ni el texto íntegro de una
consulta. Para trazabilidad se usa nombre de conexión, nombre de archivo
.sql (si existe) y/o un hash corto de la consulta — nunca el contenido.
"""
from __future__ import annotations


class DatabaseError(Exception):
    """Base común de todas las excepciones de src/db/."""


class DatabaseConfigurationError(DatabaseError):
    """Falta una variable de entorno, una conexión no existe en
    config/databases.yaml, o la especificación de conexión es inválida de
    alguna otra forma detectable sin tocar la red.

    Se lanza siempre ANTES de intentar cualquier operación de red.
    """


class ReadOnlyViolationError(DatabaseError):
    """El texto de una consulta no supera la validación de solo lectura
    (ver query_runner.validate_read_only_sql). Se lanza antes de ejecutar
    nada contra el servidor.

    IMPORTANTE: esta validación es una defensa adicional, basada en un
    parser (`sqlparse`) no validante y no específico de T-SQL — no
    sustituye a los permisos reales del login SQL a nivel de servidor.
    """


class InvalidIdentifierError(DatabaseError):
    """Un nombre de esquema, tabla o columna no cumple el formato estricto
    esperado (ver query_runner.validate_identifier). Se lanza antes de
    construir cualquier SQL con ese identificador."""


class QueryExecutionError(DatabaseError):
    """Fallo al ejecutar una consulta contra el servidor: conexión caída,
    timeout, permiso denegado por el propio SQL Server, error de sintaxis,
    etc.

    El mensaje solo puede referenciar nombre de conexión, nombre de archivo
    .sql (si aplica) y un hash corto de la consulta — nunca contraseña, URL
    completa, cadena ODBC, ni el texto de la consulta. La excepción
    original de SQLAlchemy/pyodbc se conserva siempre como causa
    (`raise ... from exc`).
    """


class QueryRowLimitExceededError(QueryExecutionError):
    """La consulta superó `max_rows_per_query` durante la lectura.

    La lectura se detiene en cuanto se detecta -- nunca se construye ni se
    devuelve un DataFrame parcial en ese caso.
    """
