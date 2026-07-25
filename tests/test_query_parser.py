"""Tests unitarios del parser sintáctico `campo:operador:valor` del Query
Engine v0.1 (sin red, sin catálogo -- ver test_query_validator.py para la
validación contra catálogo y la conversión de tipos).

Ejecutar con: pytest tests/test_query_parser.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.query.models import FilterExpression, FilterSyntaxError
from src.query.parser import parse_filter_token


# --------------------------------------------------------------------------
# eq -- integer / string (sintaxis; la conversión de tipo no ocurre aquí)
# --------------------------------------------------------------------------

def test_parse_eq_integer():
    expr = parse_filter_token("historical_origin_id:eq:440")
    assert expr == FilterExpression(field="historical_origin_id", operator="eq", raw_value="440")


def test_parse_eq_string():
    expr = parse_filter_token("workflow_status_source:eq:Aprobado")
    assert expr == FilterExpression(field="workflow_status_source", operator="eq", raw_value="Aprobado")


# --------------------------------------------------------------------------
# in -- integer / string -> siempre produce una tupla de texto
# --------------------------------------------------------------------------

def test_parse_in_integer():
    expr = parse_filter_token("center_id:in:25,30,45")
    assert expr.field == "center_id"
    assert expr.operator == "in"
    assert expr.raw_value == ("25", "30", "45")
    assert isinstance(expr.raw_value, tuple)


def test_parse_in_string():
    expr = parse_filter_token("workflow_status_source:in:Terminado,Aprobado")
    assert expr.raw_value == ("Terminado", "Aprobado")


def test_parse_in_un_solo_valor_produce_tupla_de_uno():
    expr = parse_filter_token("center_id:in:25")
    assert expr.raw_value == ("25",)


# --------------------------------------------------------------------------
# Espacios externos -- se eliminan en campo/operador/valor y en cada
# elemento de una lista `in`; el contenido interno de un valor se conserva.
# --------------------------------------------------------------------------

def test_multiples_espacios_alrededor_de_campo_operador_valor():
    expr = parse_filter_token("  center_id  :  eq  :  25  ")
    assert expr == FilterExpression(field="center_id", operator="eq", raw_value="25")


def test_multiples_espacios_en_elementos_de_in():
    expr = parse_filter_token("center_id: in : 25 ,  30 ,45 ")
    assert expr.raw_value == ("25", "30", "45")


def test_operador_se_normaliza_a_minusculas():
    expr = parse_filter_token("center_id:EQ:25")
    assert expr.operator == "eq"


def test_preserva_contenido_interno_del_valor_incluyendo_dos_puntos():
    # Solo se separan los dos primeros ":" -- el resto queda dentro del valor.
    expr = parse_filter_token("workflow_status_source:eq:10:30 Aprobado")
    assert expr.raw_value == "10:30 Aprobado"


# --------------------------------------------------------------------------
# Errores de forma
# --------------------------------------------------------------------------

def test_campo_vacio_rechazado():
    with pytest.raises(FilterSyntaxError, match="campo"):
        parse_filter_token(":eq:25")


def test_operador_vacio_rechazado():
    with pytest.raises(FilterSyntaxError, match="operador"):
        parse_filter_token("center_id::25")


def test_valor_vacio_rechazado():
    with pytest.raises(FilterSyntaxError, match="valor"):
        parse_filter_token("center_id:eq:")


def test_valor_solo_espacios_se_trata_como_vacio():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token("center_id:eq:   ")


def test_elemento_vacio_en_in_rechazado():
    with pytest.raises(FilterSyntaxError, match="in"):
        parse_filter_token("center_id:in:25,,45")


def test_elemento_vacio_al_final_de_in_rechazado():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token("center_id:in:25,30,")


def test_formato_sin_suficientes_separadores_rechazado():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token("center_id:eq")


def test_formato_sin_ningun_separador_rechazado():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token("center_id")


def test_cadena_vacia_rechazada():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token("")


def test_valor_no_string_rechazado():
    with pytest.raises(FilterSyntaxError):
        parse_filter_token(None)  # type: ignore[arg-type]
