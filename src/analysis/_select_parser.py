"""
Parser interno de la lista de columnas de un SELECT.

PRIVADO -- nadie fuera de `src/analysis/query_analyzer.py` debe importar
este módulo directamente (por eso el prefijo `_`). `query_analyzer.py` sigue
siendo el único punto público de análisis de queries.

No ejecuta SQL, no abre conexión alguna. Reutiliza `sqlparse` con el mismo
criterio ya asumido en `src/db/query_runner.py`: un parser tolerante, no un
validador de gramática T-SQL. Cuando encuentra una construcción que no puede
resolver con confianza (subquery, CTE, columna sin cualificar con múltiples
tablas), lo señala con un warning y sigue con lo que sí puede extraer -- no
falla, no inventa significado funcional, no convierte una expresión
calculada en una columna simple.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_FUNCTION_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
# Columna cualificada tabla.columna -- la columna puede venir entre
# corchetes (`Tabla.[Columna]`, patrón real de este proyecto) o sin ellos
# (`Tabla.Columna`). Se maneja como alternancia explícita en vez de un `\b`
# final tras un corchete opcional -- `\b` no marca límite de palabra justo
# después de `]` (no es un carácter de palabra), así que un `\]?\b` genérico
# recorta la coincidencia un carácter antes de lo debido.
_QUALIFIED_COLUMN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.(?:\[([^\]]+)\]|([A-Za-z_][A-Za-z0-9_]*)\b)"
)
_BARE_IDENTIFIER = re.compile(r"^\[?([A-Za-z_][A-Za-z0-9_]*)\]?$")


def _iter_qualified_columns(text: str):
    """Itera (tabla, columna, span) para cada referencia `tabla.columna` (con
    o sin corchetes en la columna) encontrada en `text`."""
    for m in _QUALIFIED_COLUMN.finditer(text):
        column = m.group(2) or m.group(3)
        yield m.group(1), column, m.span()
_AS_ALIAS = re.compile(r"^(.*?)\s+AS\s+(\[?[A-Za-z_][A-Za-z0-9_]*\]?)\s*$", re.IGNORECASE | re.DOTALL)
_REVERSED_ALIAS = re.compile(r"^(\[?[A-Za-z_][A-Za-z0-9_]*\]?)\s*=\s*(.+)$", re.DOTALL)
_TRAILING_BARE_ALIAS = re.compile(r"^(.*\S)\s+(\[?[A-Za-z_][A-Za-z0-9_]*\]?)\s*$", re.DOTALL)
_SQL_KEYWORDS_NOT_ALIAS = {
    "select", "from", "where", "and", "or", "not", "as", "on", "join", "left", "right",
    "inner", "outer", "full", "case", "when", "then", "else", "end", "null", "is",
}

FROM_KEYWORD = re.compile(r"\bFROM\b", re.IGNORECASE)
SELECT_KEYWORD = re.compile(r"\bSELECT\b", re.IGNORECASE)
WITH_KEYWORD = re.compile(r"^\s*WITH\b", re.IGNORECASE)
_IDENT_PART = r"\[[^\]]+\]|\w+"
JOIN_TABLE_PATTERN = re.compile(
    rf"\b(?:FROM|JOIN)\s+((?:{_IDENT_PART})(?:\s*\.\s*(?:{_IDENT_PART}))*)"
    rf"(?:\s+(?:AS\s+)?(\[?[A-Za-z_][A-Za-z0-9_]*\]?))?",
    re.IGNORECASE,
)


@dataclass
class SelectExpressionInfo:
    position: int
    raw_expression: str
    output_alias: str | None = None
    source_table_alias: str | None = None
    source_table: str | None = None  # resuelto aparte por resolve_source_table(), solo si no hay ambigüedad
    source_column: str | None = None
    is_calculated: bool = False
    functions_used: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)
    is_wildcard: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class SelectParseResult:
    expressions: list[SelectExpressionInfo] = field(default_factory=list)
    table_aliases: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _strip_sql_comments(sql: str) -> str:
    """Quita comentarios `--` y `/* */` para no confundir paréntesis o
    palabras clave comentadas con código activo. No modifica el fichero
    original -- opera solo sobre el texto en memoria."""
    no_line_comments = re.sub(r"--[^\n]*", "", sql)
    no_block_comments = re.sub(r"/\*.*?\*/", "", no_line_comments, flags=re.DOTALL)
    return no_block_comments


def _find_top_level(pattern: re.Pattern, text: str) -> list[int]:
    """Posiciones de `pattern` que caen a profundidad de paréntesis 0,
    ignorando el contenido de literales de cadena ('...') para no contar mal
    la profundidad por un paréntesis dentro de un string."""
    positions = []
    depth = 0
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "'":
                in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            m = pattern.match(text, i)
            if m:
                positions.append(i)
        i += 1
    return positions


def _split_top_level_commas(text: str) -> list[str]:
    """Divide `text` por comas de nivel superior (profundidad de paréntesis
    0), respetando literales de cadena. No usa el agrupado de sqlparse
    porque no agrupa de forma fiable expresiones CASE/función seguidas de
    alias en todos los casos vistos."""
    segments = []
    depth = 0
    in_string = False
    current = []
    for ch in text:
        if in_string:
            current.append(ch)
            if ch == "'":
                in_string = False
            continue
        if ch == "'":
            in_string = True
            current.append(ch)
            continue
        if ch == "(":
            depth += 1
            current.append(ch)
            continue
        if ch == ")":
            depth -= 1
            current.append(ch)
            continue
        if ch == "," and depth == 0:
            segments.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        segments.append("".join(current))
    return [s.strip() for s in segments if s.strip()]


def _extract_alias(segment: str) -> tuple[str, str | None]:
    """Devuelve (expresión_sin_alias, alias). Soporta `expr AS alias`,
    `alias = expr` (forma T-SQL invertida) y, como último recurso, `expr
    alias` sin AS (heurística, puede fallar en expresiones ambiguas)."""
    m = _AS_ALIAS.match(segment)
    if m:
        return m.group(1).strip(), m.group(2).strip("[]")

    m = _REVERSED_ALIAS.match(segment)
    if m:
        candidate_alias = m.group(1).strip("[]")
        if candidate_alias.lower() not in _SQL_KEYWORDS_NOT_ALIAS:
            return m.group(2).strip(), candidate_alias

    # Heurística de último recurso: "expr alias" sin AS. Solo se acepta si
    # el expr resultante no queda vacío y el alias no es una palabra clave.
    m = _TRAILING_BARE_ALIAS.match(segment)
    if m and " " in segment.strip():
        expr_part, alias_part = m.group(1).strip(), m.group(2).strip("[]")
        if (
            alias_part.lower() not in _SQL_KEYWORDS_NOT_ALIAS
            and not expr_part.endswith((",", "(", "."))
            and _BARE_IDENTIFIER.match(alias_part)
            and expr_part != alias_part
        ):
            return expr_part, alias_part

    return segment, None


def _looks_like_simple_column(expr: str) -> tuple[bool, str | None, str | None]:
    """Si `expr` es (solo) una referencia de columna simple, opcionalmente
    cualificada por alias de tabla, devuelve (True, alias_tabla, columna).
    Si no, (False, None, None) -- nunca se promueve una expresión calculada
    a columna simple."""
    stripped = expr.strip()
    m = _QUALIFIED_COLUMN.match(stripped)
    if m and m.span() == (0, len(stripped)):
        column = m.group(2) or m.group(3)
        return True, m.group(1).strip("[]"), column
    m2 = _BARE_IDENTIFIER.match(stripped)
    if m2:
        return True, None, m2.group(1)
    return False, None, None


def parse_select_list(sql_text: str) -> SelectParseResult:
    """Extrae la lista de expresiones del `SELECT` de nivel superior de
    `sql_text`. No ejecuta la query. No resuelve CTE ni subqueries en
    profundidad -- las detecta y avisa, procesando lo que puede del SELECT
    externo."""
    result = SelectParseResult()
    cleaned = _strip_sql_comments(sql_text)

    if WITH_KEYWORD.match(cleaned):
        result.warnings.append(
            "cte_detected: la query empieza con WITH -- se procesa el último "
            "SELECT de nivel superior encontrado, la extracción puede ser incompleta."
        )

    select_positions = _find_top_level(SELECT_KEYWORD, cleaned)
    if not select_positions:
        result.warnings.append("No se encontró ningún SELECT de nivel superior -- no se extrae nada.")
        return result
    if len(select_positions) > 1:
        result.warnings.append(
            f"Se detectaron {len(select_positions)} SELECT de nivel superior "
            "(posible UNION o múltiples CTE) -- se usa el último."
        )

    select_start = select_positions[-1] + len("SELECT")
    from_positions = [p for p in _find_top_level(FROM_KEYWORD, cleaned) if p > select_start]
    if not from_positions:
        result.warnings.append("No se encontró FROM de nivel superior tras el SELECT -- no se extrae nada.")
        return result

    select_clause = cleaned[select_start:from_positions[0]]

    # Subquery en profundidad: cualquier SELECT que NO esté a nivel superior.
    all_select_count = len(re.findall(SELECT_KEYWORD, cleaned))
    if all_select_count > len(select_positions):
        result.warnings.append(
            "subquery_detected: hay al menos un SELECT anidado dentro de "
            "paréntesis -- la extracción del SELECT externo puede ser incompleta "
            "respecto a columnas que dependan de esa subquery."
        )

    result.table_aliases = extract_table_aliases(cleaned)

    for i, segment in enumerate(_split_top_level_commas(select_clause), start=1):
        result.expressions.append(_parse_segment(segment, i))

    return result


def _parse_segment(segment: str, position: int) -> SelectExpressionInfo:
    raw = segment.strip()
    info = SelectExpressionInfo(position=position, raw_expression=raw)

    stripped = raw.strip()
    if stripped == "*" or re.match(r"^\[?[A-Za-z_][A-Za-z0-9_]*\]?\.\*$", stripped):
        info.is_wildcard = True
        m = re.match(r"^\[?([A-Za-z_][A-Za-z0-9_]*)\]?\.\*$", stripped)
        if m:
            info.source_table_alias = m.group(1)
        return info

    expr_without_alias, alias = _extract_alias(raw)
    info.output_alias = alias

    is_simple, table_alias, column = _looks_like_simple_column(expr_without_alias)
    if is_simple:
        info.source_table_alias = table_alias
        info.source_column = column
        info.referenced_columns = [f"{table_alias}.{column}" if table_alias else column]
        info.is_calculated = False
        return info

    info.is_calculated = True
    if re.match(r"^\s*CASE\b", expr_without_alias, re.IGNORECASE):
        info.functions_used.append("CASE")
    info.functions_used.extend(
        fn for fn in _FUNCTION_CALL.findall(expr_without_alias) if fn.upper() != "CASE"
    )
    info.referenced_columns = [
        f"{tbl}.{col}" for tbl, col, _ in _iter_qualified_columns(expr_without_alias)
    ]
    return info


def extract_table_aliases(sql_text: str) -> dict[str, str]:
    """Construye `{alias: tabla}` a partir de FROM/JOIN. Una tabla sin alias
    explícito se indexa con su propio nombre como alias (permite resolver
    `IDSIM` en una query de una sola tabla sin alias)."""
    cleaned = _strip_sql_comments(sql_text)
    aliases: dict[str, str] = {}
    for m in JOIN_TABLE_PATTERN.finditer(cleaned):
        full_name = m.group(1)
        table = full_name.split(".")[-1].strip("[]")
        alias = (m.group(2) or table).strip("[]")
        if alias.upper() in {"WHERE", "ON", "GROUP", "ORDER", "INNER", "LEFT", "RIGHT", "FULL", "JOIN"}:
            alias = table
        aliases[alias] = table
    return aliases


def resolve_source_table(expr: SelectExpressionInfo, table_aliases: dict[str, str]) -> tuple[str | None, list[str]]:
    """Resuelve la tabla origen de una expresión de columna simple, solo si
    no hay ambigüedad: una única tabla en toda la query, o el alias de la
    expresión coincide exactamente con una entrada de `table_aliases`.
    Nunca asume una tabla cuando hay varias posibles y la columna no está
    cualificada -- devuelve (None, [warning])."""
    if expr.is_calculated or expr.is_wildcard or expr.source_column is None:
        return None, []

    if expr.source_table_alias:
        table = table_aliases.get(expr.source_table_alias)
        if table is None:
            return None, [f"Alias de tabla '{expr.source_table_alias}' no encontrado en FROM/JOIN."]
        return table, []

    if len(table_aliases) == 1:
        return next(iter(table_aliases.values())), []

    if len(table_aliases) > 1:
        return None, [
            f"Columna '{expr.source_column}' sin cualificar en una query con "
            f"{len(table_aliases)} tablas -- no resoluble sin ambigüedad."
        ]

    return None, ["No se encontró ninguna tabla en FROM/JOIN para resolver la columna."]
