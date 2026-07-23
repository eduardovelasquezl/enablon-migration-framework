"""Tests del parser interno de columnas SELECT (src/analysis/_select_parser.py)
y de su exposición pública en query_analyzer.py. Ejecutar con: pytest tests/

Ninguna query se ejecuta contra SQL Server -- todo es análisis de texto."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import _select_parser
from src.analysis.query_analyzer import analyze_select_columns
from src.analysis._select_parser import extract_table_aliases, parse_select_list, resolve_source_table


def test_no_depende_de_src_db():
    # El parser de SELECT es análisis de texto puro -- no debe importar
    # nada de la capa de conexión/ejecución SQL.
    assert not hasattr(_select_parser, "src.db")
    import inspect
    source = inspect.getsource(_select_parser)
    assert "src.db" not in source
    assert "sqlalchemy" not in source.lower()


# ---------------------------------------------------------------------------
# Columna simple
# ---------------------------------------------------------------------------

def test_columna_simple():
    result = parse_select_list("SELECT [IDSIM] FROM ITP_SIMULACRO")
    assert len(result.expressions) == 1
    e = result.expressions[0]
    assert e.source_column == "IDSIM"
    assert e.is_calculated is False
    assert e.output_alias is None


# ---------------------------------------------------------------------------
# Alias (AS y forma invertida alias = expr)
# ---------------------------------------------------------------------------

def test_columna_con_alias_as():
    result = parse_select_list("SELECT [IDSIM] AS HistoricalOriginID FROM ITP_SIMULACRO")
    e = result.expressions[0]
    assert e.source_column == "IDSIM"
    assert e.output_alias == "HistoricalOriginID"
    assert e.is_calculated is False


def test_alias_forma_invertida_tsql():
    result = parse_select_list("SELECT HistoricalOriginID = S.IDSIM FROM ITP_SIMULACRO S")
    e = result.expressions[0]
    assert e.output_alias == "HistoricalOriginID"
    assert e.source_column == "IDSIM"
    assert e.source_table_alias == "S"


# ---------------------------------------------------------------------------
# Expresión calculada -- CASE (ejemplo exacto del enunciado)
# ---------------------------------------------------------------------------

def test_expresion_case_calculada_no_se_promueve_a_columna_simple():
    sql = (
        "SELECT S.IDSIM AS HistoricalOriginID, "
        "CASE WHEN S.ACTIVO = 1 THEN 'Yes' ELSE 'No' END AS ActiveStatus "
        "FROM ITP_SIMULACRO S"
    )
    result = parse_select_list(sql)
    assert len(result.expressions) == 2

    e1 = result.expressions[0]
    assert e1.source_column == "IDSIM"
    assert e1.output_alias == "HistoricalOriginID"
    assert e1.is_calculated is False

    e2 = result.expressions[1]
    assert e2.output_alias == "ActiveStatus"
    assert e2.is_calculated is True
    assert e2.source_column is None  # nunca se inventa una columna simple
    assert "CASE" in e2.functions_used
    assert "S.ACTIVO" in e2.referenced_columns


# ---------------------------------------------------------------------------
# Función
# ---------------------------------------------------------------------------

def test_funcion_format_es_calculada():
    result = parse_select_list("SELECT format([Fecha], 'dd/MM/yyyy') AS Fecha FROM ITP_SIMULACRO")
    e = result.expressions[0]
    assert e.is_calculated is True
    assert "format" in e.functions_used
    assert e.output_alias == "Fecha"


# ---------------------------------------------------------------------------
# Wildcard
# ---------------------------------------------------------------------------

def test_wildcard_simple():
    result = parse_select_list("SELECT * FROM ITP_SIMULACRO")
    assert result.expressions[0].is_wildcard is True
    assert result.expressions[0].source_column is None


def test_wildcard_cualificado_por_tabla():
    result = parse_select_list("SELECT S.* FROM ITP_SIMULACRO S")
    e = result.expressions[0]
    assert e.is_wildcard is True
    assert e.source_table_alias == "S"


# ---------------------------------------------------------------------------
# Joins y alias -- resolución de tabla origen
# ---------------------------------------------------------------------------

def test_joins_y_alias_resuelven_tabla_origen():
    sql = "SELECT S.IDSIM FROM ITP_SIMULACRO S JOIN ITP_USUARIOS U ON S.IDUSUARIO = U.ID"
    aliases = extract_table_aliases(sql)
    assert aliases.get("S") == "ITP_SIMULACRO"
    assert aliases.get("U") == "ITP_USUARIOS"

    result = parse_select_list(sql)
    e = result.expressions[0]
    table, warnings = resolve_source_table(e, result.table_aliases)
    assert table == "ITP_SIMULACRO"
    assert warnings == []


def test_columna_ambigua_sin_cualificar_con_multiples_tablas():
    sql = "SELECT [Nombre] FROM ITP_SIMULACRO S JOIN ITP_USUARIOS U ON S.IDUSUARIO = U.ID"
    result = parse_select_list(sql)
    e = result.expressions[0]
    table, warnings = resolve_source_table(e, result.table_aliases)
    assert table is None
    assert warnings and "ambig" in warnings[0].lower()


def test_columna_cualificada_por_nombre_de_tabla_con_corchetes_no_es_calculada():
    # Patrón real y muy frecuente en las queries del proyecto:
    # "ITP_ANALISIS.[IDCentro]" (tabla SIN alias, columna entre corchetes).
    result = parse_select_list("SELECT ITP_ANALISIS.[IDCentro] FROM ITP_ANALISIS")
    e = result.expressions[0]
    assert e.is_calculated is False
    assert e.source_table_alias == "ITP_ANALISIS"
    assert e.source_column == "IDCentro"


def test_extract_table_aliases_con_nombre_completamente_cualificado_con_corchetes():
    # Patrón real del proyecto: FROM [Prevencion].[dbo].[ITP_USUARIOS]
    sql = "SELECT [IDUsuario] FROM [Prevencion].[dbo].[ITP_USUARIOS]"
    aliases = extract_table_aliases(sql)
    assert aliases == {"ITP_USUARIOS": "ITP_USUARIOS"}


def test_columna_sin_cualificar_con_una_sola_tabla_se_resuelve():
    sql = "SELECT [IDSIM] FROM ITP_SIMULACRO"
    result = parse_select_list(sql)
    e = result.expressions[0]
    table, warnings = resolve_source_table(e, result.table_aliases)
    assert table == "ITP_SIMULACRO"
    assert warnings == []


# ---------------------------------------------------------------------------
# Subquery y CTE -- degradan con warning, no fallan
# ---------------------------------------------------------------------------

def test_subquery_genera_warning_no_falla():
    sql = "SELECT IDSIM, (SELECT COUNT(*) FROM ITP_USUARIOS) AS Total FROM ITP_SIMULACRO"
    result = parse_select_list(sql)
    assert any("subquery" in w.lower() for w in result.warnings)
    assert len(result.expressions) == 2  # sigue extrayendo lo que puede


def test_cte_genera_warning_no_falla():
    sql = "WITH Base AS (SELECT IDSIM FROM ITP_SIMULACRO) SELECT IDSIM FROM Base"
    result = parse_select_list(sql)
    assert any("cte" in w.lower() for w in result.warnings)
    assert len(result.expressions) >= 1


# ---------------------------------------------------------------------------
# Preservación de la expresión original
# ---------------------------------------------------------------------------

def test_preserva_expresion_sql_original():
    sql = "SELECT CASE WHEN S.ACTIVO = 1 THEN 'Yes' ELSE 'No' END AS ActiveStatus FROM ITP_SIMULACRO S"
    result = parse_select_list(sql)
    assert "CASE WHEN" in result.expressions[0].raw_expression


# ---------------------------------------------------------------------------
# Superficie pública: query_analyzer.analyze_select_columns
# ---------------------------------------------------------------------------

def test_analyze_select_columns_expone_resolucion_de_tabla(tmp_path):
    sql_path = tmp_path / "query.sql"
    sql_path.write_text(
        "SELECT S.IDSIM AS HistoricalOriginID FROM ITP_SIMULACRO S",
        encoding="utf-8",
    )
    result = analyze_select_columns(sql_path)
    assert result.expressions[0].source_table == "ITP_SIMULACRO"
