"""Tests unitarios del compositor SQL en memoria del Query Engine v0.1
(sin red -- no abre ninguna conexión a SQL Server, solo compone y
revalida texto).

Ejecutar con: pytest tests/test_query_sql_builder.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.query.catalog import DRILLS_FILTER_CATALOG
from src.query.models import UnsupportedQueryStructureError
from src.query.sql_builder import ComposedQuery, compose_filtered_sql, render_generated_sql_file
from src.query.validator import compile_filter_tokens

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRILLS_SQL_PATH = PROJECT_ROOT / "sql" / "source_queries" / "Simulacros" / "SQLQuery - DATASET SIMULACRO.sql"


def _drills_sql_text() -> str:
    return DRILLS_SQL_PATH.read_text(encoding="utf-8-sig")


# --------------------------------------------------------------------------
# Sin filtros -- passthrough exacto (regresión: comportamiento sin --filter)
# --------------------------------------------------------------------------

def test_sin_filtros_devuelve_sql_original_sin_cambios():
    original = "SELECT * FROM Foo ORDER BY y"
    composed = compose_filtered_sql(original, [])
    assert composed.sql_text == original
    assert composed.parameters == {}


# --------------------------------------------------------------------------
# Inserción antes de ORDER BY / conservación del ORDER BY original
# --------------------------------------------------------------------------

def test_inserta_where_antes_del_order_by_de_nivel_superior():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    original = _drills_sql_text()
    composed = compose_filtered_sql(original, compiled)

    where_pos = composed.sql_text.index("WHERE")
    order_by_pos = composed.sql_text.index("order by")
    assert where_pos < order_by_pos


def test_conserva_el_order_by_original_tal_cual():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    original = _drills_sql_text()
    composed = compose_filtered_sql(original, compiled)
    assert "order by FechaCreacion asc" in composed.sql_text


def test_conserva_el_select_original_intacto_antes_del_where():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    original = _drills_sql_text()
    composed = compose_filtered_sql(original, compiled)
    select_clause = original.split("FROM [Prevencion]")[0]
    assert select_clause in composed.sql_text


def test_sin_order_by_inserta_where_al_final():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    composed = compose_filtered_sql("SELECT * FROM Foo", compiled)
    assert "WHERE [ITP_SIMULACRO].[IDCentro] = :filter_1" in composed.sql_text


def test_sin_order_by_con_punto_y_coma_inserta_antes_del_punto_y_coma():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    composed = compose_filtered_sql("SELECT * FROM Foo;", compiled)
    assert composed.sql_text.rstrip().endswith(";")
    assert composed.sql_text.index("WHERE") < composed.sql_text.rindex(";")


# --------------------------------------------------------------------------
# Combinación de varios filtros con AND
# --------------------------------------------------------------------------

def test_combina_varios_filtros_con_and():
    compiled = compile_filter_tokens(
        ["center_id:eq:25", "typology_id:in:1,2"], DRILLS_FILTER_CATALOG
    )
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    assert (
        "[ITP_SIMULACRO].[IDCentro] = :filter_1 AND "
        "[ITP_SIMULACRO].[IDTipo] IN (:filter_2_0, :filter_2_1)"
    ) in composed.sql_text
    # No implementa OR en v0.1.
    assert " OR " not in composed.sql_text.upper()


def test_parametros_fusionados_de_todos_los_filtros():
    compiled = compile_filter_tokens(
        ["center_id:eq:25", "typology_id:in:1,2"], DRILLS_FILTER_CATALOG
    )
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    assert composed.parameters == {"filter_1": 25, "filter_2_0": 1, "filter_2_1": 2}


# --------------------------------------------------------------------------
# WHERE de nivel superior ya existente -- rechazo explícito
# --------------------------------------------------------------------------

def test_falla_si_existe_where_de_nivel_superior():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    with pytest.raises(UnsupportedQueryStructureError, match="WHERE"):
        compose_filtered_sql("SELECT * FROM Foo WHERE y = 1 ORDER BY y", compiled)


def test_falla_si_existe_where_sin_order_by():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    with pytest.raises(UnsupportedQueryStructureError):
        compose_filtered_sql("SELECT * FROM Foo WHERE y = 1", compiled)


def test_falla_si_hay_mas_de_una_sentencia():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    with pytest.raises(UnsupportedQueryStructureError):
        compose_filtered_sql("SELECT 1; SELECT 2", compiled)


# --------------------------------------------------------------------------
# El SQL final vuelve a pasar por validate_read_only_sql()
# --------------------------------------------------------------------------

def test_sql_compuesto_pasa_validate_read_only_sql():
    from src.db.query_runner import validate_read_only_sql

    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    validate_read_only_sql(composed.sql_text)  # no debe lanzar


def test_sql_compuesto_con_intento_de_inyeccion_en_workflow_status_sigue_siendo_select_valido():
    """El valor va parametrizado (:filter_1) -- un intento de inyección
    como valor de filtro no puede alterar la forma de la sentencia."""
    compiled = compile_filter_tokens(
        ["workflow_status_source:eq:Terminado'; DROP TABLE ITP_SIMULACRO; --"],
        DRILLS_FILTER_CATALOG,
    )
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    from src.db.query_runner import validate_read_only_sql

    validate_read_only_sql(composed.sql_text)  # sigue siendo un único SELECT válido
    assert "DROP TABLE" not in composed.sql_text  # el valor nunca se concatena en el texto SQL
    assert composed.parameters["filter_1"] == "Terminado'; DROP TABLE ITP_SIMULACRO; --"


# --------------------------------------------------------------------------
# Ningún valor aparece concatenado en el SQL -- solo placeholders
# --------------------------------------------------------------------------

def test_ningun_valor_aparece_literal_en_el_sql_solo_placeholders():
    compiled = compile_filter_tokens(
        ["center_id:eq:987654", "typology_id:in:111,222"], DRILLS_FILTER_CATALOG
    )
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    assert "987654" not in composed.sql_text
    assert "111" not in composed.sql_text
    assert "222" not in composed.sql_text
    assert ":filter_1" in composed.sql_text
    assert ":filter_2_0" in composed.sql_text
    assert ":filter_2_1" in composed.sql_text
    # los valores reales solo viven en el diccionario de parámetros.
    assert composed.parameters["filter_1"] == 987654


# --------------------------------------------------------------------------
# La SQL fuente original en disco no cambia
# --------------------------------------------------------------------------

def test_la_sql_fuente_original_no_cambia_en_disco():
    before = DRILLS_SQL_PATH.read_bytes()
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    compose_filtered_sql(_drills_sql_text(), compiled)
    after = DRILLS_SQL_PATH.read_bytes()
    assert before == after


def test_compose_filtered_sql_no_muta_el_texto_de_entrada():
    original = _drills_sql_text()
    original_copy = str(original)
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    compose_filtered_sql(original, compiled)
    assert original == original_copy


# --------------------------------------------------------------------------
# generated_query.sql -- contenido (función pura, sin I/O)
# --------------------------------------------------------------------------

def test_render_generated_sql_file_contiene_placeholders_no_valores():
    compiled = compile_filter_tokens(["center_id:eq:987654"], DRILLS_FILTER_CATALOG)
    composed = compose_filtered_sql(_drills_sql_text(), compiled)
    rendered = render_generated_sql_file(
        sql_text=composed.sql_text,
        source_sql_relpath="sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql",
        source_sql_sha256="deadbeef",
        run_id="abc123",
        timestamp="20260101T000000Z",
    )
    assert ":filter_1" in rendered
    assert "987654" not in rendered
    assert "Query Engine v0.1" in rendered
    assert "deadbeef" in rendered
    assert "abc123" in rendered


def test_render_generated_sql_file_incluye_cabecera_de_advertencia():
    composed = ComposedQuery(sql_text="SELECT 1 WHERE x = :filter_1", parameters={"filter_1": 1})
    rendered = render_generated_sql_file(
        sql_text=composed.sql_text,
        source_sql_relpath="sql/source_queries/x.sql",
        source_sql_sha256="hash",
        run_id="rid",
        timestamp="ts",
    )
    assert rendered.startswith("--")
    assert "sql/source_queries/x.sql" in rendered
