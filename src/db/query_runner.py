"""
Ejecución de consultas de solo lectura, con salvaguardas explícitas.

Uso típico:

    from src.db.query_runner import run_query, run_query_file

    df = run_query("SELECT IDCentro, COUNT(*) AS Total FROM ITP_ANALISIS GROUP BY IDCentro",
                    connection="prevencion")

    df = run_query_file("sql/source_queries/eventos/eventos_antiguos.sql",
                         connection="prevencion")

Dos capas de defensa independientes antes de tocar el servidor, ninguna de
las cuales sustituye a la garantía real (permisos del login SQL a nivel de
servidor -- ver src/db/connection.py):

1. `validate_read_only_sql`: un criterio ESTRUCTURAL (whitelist) -- la
   consulta debe reducirse a una única sentencia SELECT, o WITH que
   desemboque en SELECT, sin SELECT INTO en ningún nivel de anidamiento.
2. Un barrido léxico adicional (lista negra) sobre todos los tokens de la
   consulta, en cualquier profundidad, para palabras/funciones que igual
   podrían colarse como expresión dentro de un SELECT sintácticamente
   válido (OPENROWSET, OPENDATASOURCE) y como redundancia defensiva sobre
   el resto de palabras prohibidas.

IMPORTANTE: `sqlparse` es un parser tolerante y no específico de T-SQL, no
un validador de gramática SQL Server. Esta capa reduce el riesgo de
ejecutar algo que no sea una lectura, pero no es una garantía absoluta --
la garantía real sigue siendo el permiso del login SQL en el servidor.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import pandas as pd
import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.elements import TextClause
from sqlparse import tokens as T
from sqlparse.sql import Comment, Statement, TokenList

from src.config import get_safety_settings
from src.db.connection import get_engine
from src.db.exceptions import (
    InvalidIdentifierError,
    QueryExecutionError,
    QueryRowLimitExceededError,
    ReadOnlyViolationError,
)

logger = logging.getLogger(__name__)

# Tamaño de lote de lectura -- detalle técnico interno, no configuración de
# negocio, por eso no vive en config/*.yaml. Se limita respecto al límite
# real (max_rows_per_query, que sí viene de src.config) para no pedir
# lotes más grandes que el propio límite.
DEFAULT_CHUNK_SIZE = 10_000

# Identificador SQL Server "seguro": letras/dígitos/guion bajo, empezando
# por letra o guion bajo. Deliberadamente conservador -- no acepta
# corchetes, espacios ni caracteres especiales; el código que la use añade
# los corchetes tras validar, nunca antes.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

# Lista negra: defensa ADICIONAL, no el criterio principal de autorización
# (ver validate_read_only_sql). Cubre tanto keywords de escritura/DDL/DCL
# como funciones que sí son válidas como expresión dentro de un SELECT
# (OPENROWSET/OPENDATASOURCE) y por tanto no las bloquea el criterio
# estructural de "una única sentencia SELECT".
_BLOCKED_TERMS = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "ALTER", "DROP",
    "TRUNCATE", "GRANT", "REVOKE", "DENY", "BACKUP", "RESTORE", "DBCC",
    "EXEC", "EXECUTE", "BULK", "INTO", "OPENROWSET", "OPENDATASOURCE",
}

_WITH_TARGET_KEYWORDS = ("SELECT", "INSERT", "UPDATE", "DELETE", "MERGE")


# --------------------------------------------------------------------------
# Validación de identificadores
# --------------------------------------------------------------------------

def validate_identifier(name: str, kind: str = "identificador") -> str:
    """Valida estrictamente un nombre de esquema/tabla/columna antes de que
    se concatene en un SQL construido como texto (grouped_count, metadata).

    No acepta corchetes, puntos, espacios ni ningún carácter fuera de
    [A-Za-z0-9_] -- quien llame debe envolver el resultado entre corchetes
    (`[nombre]`) al construir el SQL, nunca interpolar `name` directamente.
    """
    if not isinstance(name, str) or not _IDENTIFIER_PATTERN.match(name):
        raise InvalidIdentifierError(
            f"'{name}' no es un {kind} válido. Se esperaba una única "
            "palabra con letras, dígitos o guion bajo, empezando por letra "
            "o guion bajo (sin corchetes, puntos ni espacios)."
        )
    return name


# --------------------------------------------------------------------------
# Validador de solo lectura -- función pura, sin I/O
# --------------------------------------------------------------------------

def _is_trivial_token(tok) -> bool:
    return tok.is_whitespace or tok.ttype in T.Comment or isinstance(tok, Comment)


def _first_meaningful_token(tokens):
    for tok in tokens:
        if _is_trivial_token(tok):
            continue
        return tok
    return None


def _statement_has_content(stmt: Statement) -> bool:
    """Una sentencia es 'vacía' a efectos de conteo si solo contiene
    espacios, comentarios y/o punto y coma sueltos (el caso típico de un
    ';' inicial antes de un WITH, o un ';' final tras la sentencia real)."""
    for tok in stmt.tokens:
        if _is_trivial_token(tok):
            continue
        if tok.ttype is T.Punctuation and tok.value == ";":
            continue
        return True
    return False


def _classify_with_statement(stmt: Statement) -> str:
    """Para una sentencia que empieza por WITH, devuelve el keyword de la
    sentencia real a la que desemboca (SELECT/INSERT/UPDATE/DELETE/MERGE)
    tras saltar la lista de CTE (uno o varios, separados por comas)."""
    tokens = list(stmt.tokens)
    with_index = None
    for i, tok in enumerate(tokens):
        if _is_trivial_token(tok):
            continue
        if tok.ttype in T.Keyword and (tok.normalized or tok.value).upper() == "WITH":
            with_index = i
            break
    if with_index is None:
        return "DESCONOCIDO"

    for tok in tokens[with_index + 1:]:
        if _is_trivial_token(tok):
            continue
        if tok.ttype in T.Keyword:
            value = (tok.normalized or tok.value).upper()
            if value in _WITH_TARGET_KEYWORDS:
                return value
            # otros keywords (p. ej. "AS" si quedara suelto) no determinan
            # el tipo de sentencia -- se ignoran y se sigue buscando.
            continue
        # Identifier / IdentifierList / Parenthesis / coma: son parte de
        # las definiciones de CTE, se saltan.
        continue
    return "DESCONOCIDO"


def _classify_statement(stmt: Statement) -> str:
    """Clasifica el tipo efectivo de una sentencia ya confirmada como
    única y no vacía. Devuelve 'SELECT' solo si la sentencia es un SELECT
    directo o un WITH que desemboca en SELECT; en cualquier otro caso
    devuelve el keyword real encontrado (para un mensaje de error claro)."""
    first = _first_meaningful_token(stmt.tokens)
    if first is None:
        return "VACIO"
    if first.ttype not in T.Keyword:
        return (first.normalized or first.value or "DESCONOCIDO").upper()

    value = (first.normalized or first.value).upper()
    if value == "WITH":
        return _classify_with_statement(stmt)
    return value


def _contains_select_into(token_list: TokenList) -> bool:
    """Busca un SELECT ... INTO en CUALQUIER nivel de anidamiento (no solo
    en la sentencia principal) -- cada nivel de anidamiento se evalúa de
    forma independiente, y se recorre siempre hacia dentro de cualquier
    grupo de tokens, esté o no relacionado con el estado de SELECT/INTO del
    nivel exterior."""
    seen_select_awaiting_into = False
    for tok in token_list.tokens:
        if _is_trivial_token(tok):
            pass
        elif tok.ttype in T.Keyword:
            value = (tok.normalized or tok.value).upper()
            if value == "SELECT":
                seen_select_awaiting_into = True
            elif value == "INTO" and seen_select_awaiting_into:
                return True
            elif value == "FROM":
                seen_select_awaiting_into = False

        if isinstance(tok, TokenList) and _contains_select_into(tok):
            return True
    return False


def _scan_blacklist(stmt: Statement) -> str | None:
    """Barrido léxico completo (todos los niveles) en busca de un término
    de _BLOCKED_TERMS. Ignora comentarios, espacios y literales de cadena
    -- por diseño, para no producir falsos positivos por texto dentro de
    un literal o un comentario (ver docstring del módulo)."""
    for tok in stmt.flatten():
        if tok.is_whitespace:
            continue
        if tok.ttype in T.Comment:
            continue
        if tok.ttype in T.Literal.String:
            continue
        value = (tok.normalized or tok.value or "").upper()
        if value in _BLOCKED_TERMS:
            return value
    return None


def validate_read_only_sql(sql: str) -> None:
    """Valida que `sql` sea una única sentencia de lectura.

    Lanza `ReadOnlyViolationError` si no lo es. Es una función pura (sin
    I/O ni efectos secundarios) para poder testearla de forma aislada.

    Criterio principal (whitelist): la consulta debe reducirse a una única
    sentencia SELECT, o WITH que desemboque en SELECT, sin SELECT INTO en
    ningún nivel. La lista negra de palabras/funciones prohibidas es una
    defensa ADICIONAL sobre ese criterio, no el único filtro.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ReadOnlyViolationError("La consulta está vacía.")

    parsed = sqlparse.parse(sql)
    statements = [s for s in parsed if _statement_has_content(s)]

    if not statements:
        raise ReadOnlyViolationError(
            "La consulta no contiene ninguna sentencia con contenido "
            "(solo espacios, comentarios y/o punto y coma)."
        )
    if len(statements) > 1:
        raise ReadOnlyViolationError(
            f"Se detectaron {len(statements)} sentencias; solo se permite "
            "una única sentencia de lectura por llamada."
        )

    stmt = statements[0]

    shape = _classify_statement(stmt)
    if shape != "SELECT":
        raise ReadOnlyViolationError(
            "Solo se permite SELECT, o WITH que desemboque en SELECT; la "
            f"sentencia efectiva detectada es '{shape}'."
        )

    if _contains_select_into(stmt):
        raise ReadOnlyViolationError(
            "SELECT INTO no está permitido (crea/modifica un objeto en el "
            "servidor), en ningún nivel de anidamiento."
        )

    blocked = _scan_blacklist(stmt)
    if blocked:
        raise ReadOnlyViolationError(
            f"Palabra clave o función no permitida detectada: '{blocked}'."
        )


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------

def _query_hash(sql: str) -> str:
    """Hash corto (no reversible) de la consulta, para trazabilidad en
    logs/excepciones sin exponer su contenido."""
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:12]


# Sprint 9.1 (diagnóstico del primer fallo real de Drills, execution_id
# 458dfb9f27f3): defensa en profundidad adicional a `hide_parameters=True`
# (src/db/connection.py) -- por si un driver/mensaje de error incrusta un
# fragmento con pinta de credencial que `hide_parameters` no cubre (que solo
# oculta SQL/params de SQLAlchemy, no el texto libre de un DBAPIError.orig).
_SECRET_LIKE_PATTERN = re.compile(
    r"(?i)\b(pwd|password|pass|token|secret|apikey|api_key)\s*=\s*[^;,\s]+"
)
_MAX_ERROR_DETAIL_LENGTH = 500


def _sanitize_error_detail(detail: str) -> str:
    """Redacta fragmentos tipo `password=...`/`pwd=...`/`token=...` de un
    texto de error técnico y lo trunca.

    Nunca decide si el texto resultante es apto para el modo CLI por
    defecto -- sigue reservado a `--verbose` (ver el `logger.debug` en
    `run_query`), esto es solo saneamiento adicional de lo que se registra."""
    redacted = _SECRET_LIKE_PATTERN.sub(r"\1=***REDACTED***", detail)
    if len(redacted) > _MAX_ERROR_DETAIL_LENGTH:
        redacted = redacted[:_MAX_ERROR_DETAIL_LENGTH] + "... (truncado)"
    return redacted


def run_query(
    sql: str,
    connection: str | None = None,
    params: dict | None = None,
    *,
    source_file: str | None = None,
) -> pd.DataFrame:
    """Ejecuta una consulta de solo lectura y devuelve un DataFrame.

    Aplica el límite de filas de config/databases.yaml -> safety de forma
    ESTRICTA durante la lectura (fetchmany por lotes), no después de haber
    cargado todo el resultado en memoria: en cuanto el acumulado supera
    `max_rows_per_query` se detiene la lectura y se lanza
    `QueryRowLimitExceededError`, sin devolver nunca un resultado parcial.

    `params`, si se pasa, usa la convención de parámetros con nombre de
    SQLAlchemy `text()` (`:nombre`), no marcadores posicionales `?`.
    """
    validate_read_only_sql(sql)

    settings = get_safety_settings()
    max_rows = settings.get("max_rows_per_query", 2_000_000)
    effective_chunk_size = min(DEFAULT_CHUNK_SIZE, max_rows) if max_rows else DEFAULT_CHUNK_SIZE

    query_hash = _query_hash(sql)
    logger.info(
        "Ejecutando query (conexión=%s, archivo=%s, hash=%s)",
        connection, source_file or "-", query_hash,
    )

    engine = get_engine(connection)
    statement: TextClause = text(sql)

    try:
        with engine.connect() as conn:
            result = conn.execute(statement, params or {})
            columns = list(result.keys())
            rows: list = []
            total = 0
            while True:
                batch = result.fetchmany(effective_chunk_size)
                if not batch:
                    break
                total += len(batch)
                if total > max_rows:
                    raise QueryRowLimitExceededError(
                        f"La consulta (conexión='{connection}', "
                        f"archivo={source_file or '-'}, hash={query_hash}) "
                        f"superó el límite de {max_rows} filas durante la "
                        "lectura; la lectura se ha detenido."
                    )
                rows.extend(batch)
    except QueryRowLimitExceededError:
        raise
    except SQLAlchemyError as exc:
        # Sprint 9.1: la causa técnica original (tipo de excepción + mensaje
        # del driver, saneado) se registra a nivel DEBUG -- invisible en modo
        # CLI por defecto, visible con `--verbose` (reutiliza el nivel de
        # logging que ya configura `_configure_logging` en src/cli.py, sin
        # flag nuevo). El mensaje amigable de QueryExecutionError no cambia;
        # `from exc` ya conservaba `__cause__` desde antes de este cambio --
        # lo nuevo es que ahora también queda REGISTRADO, no solo retenido en
        # el objeto excepción hasta que el proceso termina.
        #
        # Deliberadamente SIN `exc_info=True`: el formateador de logging
        # renderiza el traceback llamando a `str()` sobre la excepción REAL,
        # no sobre nuestro texto ya saneado -- adjuntarlo reintroduciría
        # exactamente el fragmento sin sanear que `_sanitize_error_detail`
        # acaba de quitar (confirmado con un test que lo reproduce). Se
        # registra tipo + mensaje saneado; se renuncia al traceback completo
        # a cambio de la garantía de no fuga.
        logger.debug(
            "Causa técnica original (query_hash=%s, conexión=%s): %s: %s",
            query_hash, connection, type(exc).__name__, _sanitize_error_detail(str(exc)),
        )
        raise QueryExecutionError(
            f"Fallo al ejecutar la consulta (conexión='{connection}', "
            f"archivo={source_file or '-'}, hash={query_hash})."
        ) from exc

    df = pd.DataFrame(rows, columns=columns)
    logger.info("Query devolvió %s filas x %s columnas.", *df.shape)
    return df


def run_query_file(
    path: str | Path,
    connection: str | None = None,
    params: dict | None = None,
) -> pd.DataFrame:
    """Lee un fichero .sql (tal cual los que aporta el cliente en
    sql/source_queries/) y lo ejecuta como solo lectura."""
    path = Path(path)
    sql = path.read_text(encoding="utf-8-sig")
    return run_query(sql, connection=connection, params=params, source_file=str(path))


def grouped_count(table: str, group_by_col: str, connection: str | None = None) -> pd.DataFrame:
    """Atajo para el patrón de diagnóstico más usado en este proyecto:
    volumetría por site. Genera y ejecuta un SELECT ... GROUP BY simple.

    `table` y `group_by_col` se validan estrictamente (validate_identifier)
    antes de concatenarse -- nunca se interpola un identificador sin
    validar en el SQL generado.

    Ejemplo: grouped_count("ITP_ANALISIS", "IDCentro", connection="prevencion")
    """
    table = validate_identifier(table, kind="nombre de tabla")
    group_by_col = validate_identifier(group_by_col, kind="nombre de columna")
    sql = (
        f"SELECT [{group_by_col}], COUNT(*) AS Total FROM [{table}] "
        f"GROUP BY [{group_by_col}] ORDER BY Total DESC"
    )
    return run_query(sql, connection=connection)
