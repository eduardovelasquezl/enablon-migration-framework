"""Tests unitarios de validación contra catálogo + conversión de tipos +
orquestación extremo a extremo del Query Engine v0.1 (sin red).

Ejecutar con: pytest tests/test_query_validator.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.query.catalog import (
    DATA_TYPE_INTEGER,
    DATA_TYPE_STRING,
    DRILLS_FILTER_CATALOG,
    FilterDefinition,
    ObjectFilterCatalog,
)
from src.query.models import (
    FilterExpression,
    InvalidFilterValueError,
    OperatorNotAllowedError,
    UnknownFilterFieldError,
)
from src.query.operators import MAX_IN_VALUES
from src.query.validator import compile_filter_tokens, validate_and_coerce

# Catálogo sintético con un campo que SOLO admite 'eq' -- necesario para
# probar "operador no permitido para el campo" de forma aislada, ya que
# los seis campos aprobados de Drills admiten eq/in por igual.
_ONLY_EQ_CATALOG = ObjectFilterCatalog(
    object_id="test_object",
    fields={
        "only_eq_field": FilterDefinition(
            field_name="only_eq_field",
            sql_source_expression="[T].[X]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq",),
        ),
        "string_field": FilterDefinition(
            field_name="string_field",
            sql_source_expression="[T].[Y]",
            data_type=DATA_TYPE_STRING,
            allowed_operators=("eq", "in"),
        ),
    },
)


# --------------------------------------------------------------------------
# Campo / operador
# --------------------------------------------------------------------------

def test_campo_desconocido_lanza_unknown_filter_field_error():
    expr = FilterExpression(field="no_existe", operator="eq", raw_value="1")
    with pytest.raises(UnknownFilterFieldError):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


def test_operador_desconocido_lanza_operator_not_allowed_error():
    expr = FilterExpression(field="center_id", operator="gte", raw_value="25")
    with pytest.raises(OperatorNotAllowedError, match="no reconocido"):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


def test_operador_no_permitido_para_el_campo_concreto():
    """'eq' SÍ es un operador globalmente reconocido, pero aquí se prueba
    contra un campo cuyo catálogo solo declara 'eq' -- 'in' debe rechazarse
    con un mensaje distinto al de "operador desconocido"."""
    expr = FilterExpression(field="only_eq_field", operator="in", raw_value=("1", "2"))
    with pytest.raises(OperatorNotAllowedError, match="no admite"):
        validate_and_coerce(expr, _ONLY_EQ_CATALOG)


# --------------------------------------------------------------------------
# Conversión de tipos
# --------------------------------------------------------------------------

def test_integer_valido_se_convierte():
    expr = FilterExpression(field="center_id", operator="eq", raw_value="25")
    field_def, value = validate_and_coerce(expr, DRILLS_FILTER_CATALOG)
    assert value == 25
    assert isinstance(value, int)


def test_integer_invalido_decimal_rechazado():
    expr = FilterExpression(field="center_id", operator="eq", raw_value="25.5")
    with pytest.raises(InvalidFilterValueError):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


def test_integer_invalido_texto_no_numerico_rechazado():
    expr = FilterExpression(field="center_id", operator="eq", raw_value="abc")
    with pytest.raises(InvalidFilterValueError):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


def test_integer_invalido_no_se_convierte_en_silencio():
    """Ningún valor inválido puede colarse convertido a 0 o similar -- debe
    lanzar, nunca devolver un valor por defecto inventado."""
    expr = FilterExpression(field="center_id", operator="in", raw_value=("25", "no-numero"))
    with pytest.raises(InvalidFilterValueError):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


def test_string_conserva_valor_y_elimina_espacios_externos():
    expr = FilterExpression(field="workflow_status_source", operator="eq", raw_value="Aprobado")
    field_def, value = validate_and_coerce(expr, DRILLS_FILTER_CATALOG)
    assert value == "Aprobado"


def test_in_integer_produce_tupla_de_enteros():
    expr = FilterExpression(field="center_id", operator="in", raw_value=("25", "30", "45"))
    field_def, value = validate_and_coerce(expr, DRILLS_FILTER_CATALOG)
    assert value == (25, 30, 45)


def test_in_string_produce_tupla_de_strings():
    expr = FilterExpression(field="workflow_status_source", operator="in", raw_value=("Terminado", "Aprobado"))
    field_def, value = validate_and_coerce(expr, DRILLS_FILTER_CATALOG)
    assert value == ("Terminado", "Aprobado")


# --------------------------------------------------------------------------
# Límite de 'in'
# --------------------------------------------------------------------------

def test_in_admite_hasta_200_valores():
    values = tuple(str(i) for i in range(MAX_IN_VALUES))
    expr = FilterExpression(field="center_id", operator="in", raw_value=values)
    field_def, value = validate_and_coerce(expr, DRILLS_FILTER_CATALOG)
    assert len(value) == MAX_IN_VALUES


def test_in_rechaza_mas_de_200_valores():
    values = tuple(str(i) for i in range(MAX_IN_VALUES + 1))
    expr = FilterExpression(field="center_id", operator="in", raw_value=values)
    with pytest.raises(InvalidFilterValueError, match="200"):
        validate_and_coerce(expr, DRILLS_FILTER_CATALOG)


# --------------------------------------------------------------------------
# compile_filter_tokens -- orquestación de extremo a extremo
# --------------------------------------------------------------------------

def test_compile_filter_tokens_campo_desconocido_propaga_error_de_catalogo():
    with pytest.raises(UnknownFilterFieldError):
        compile_filter_tokens(["campo_inexistente:eq:1"], DRILLS_FILTER_CATALOG)


def test_compile_filter_tokens_catalogo_cerrado_sin_filtros_no_falla():
    assert compile_filter_tokens([], DRILLS_FILTER_CATALOG) == []


def test_compile_filter_tokens_nombres_de_parametro_unicos_entre_filtros():
    compiled = compile_filter_tokens(
        ["center_id:eq:25", "typology_id:in:1,2"], DRILLS_FILTER_CATALOG
    )
    assert compiled[0].parameters == {"filter_1": 25}
    assert compiled[1].parameters == {"filter_2_0": 1, "filter_2_1": 2}
    # ningún nombre de parámetro se repite entre filtros distintos.
    all_names = list(compiled[0].parameters) + list(compiled[1].parameters)
    assert len(all_names) == len(set(all_names))


def test_compile_filter_tokens_orden_estable_de_filter_base():
    compiled = compile_filter_tokens(
        ["historical_origin_id:eq:1", "center_id:eq:2", "letter_id:eq:3"],
        DRILLS_FILTER_CATALOG,
    )
    assert [cf.parameters for cf in compiled] == [
        {"filter_1": 1}, {"filter_2": 2}, {"filter_3": 3},
    ]


def test_compile_filter_tokens_manifest_entry_no_incluye_sql():
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    entry = compiled[0].manifest_entry
    assert entry == {"field": "center_id", "operator": "eq", "value": 25}
    assert "sql_fragment" not in entry
    assert "parameters" not in entry
