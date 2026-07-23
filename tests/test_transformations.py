"""Tests unitarios de las reglas de transformación. Ejecutar con: pytest tests/"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.transformations import (
    nullcontrol, concat, barconcat, titlefix, cloneorigin,
    cloneorigin_fanout, lookup_simple, resolve_rule,
)


def test_nullcontrol_sustituye_nulo():
    assert nullcontrol(None, default="N/D") == "N/D"
    assert nullcontrol("", default="N/D") == "N/D"
    assert nullcontrol("valor", default="N/D") == "valor"


def test_concat_ignora_vacios():
    row = {"a": "Hola", "b": None, "c": "Mundo"}
    assert concat(row, ["a", "b", "c"]) == "Hola Mundo"


def test_barconcat_usa_separador_barra():
    row = {"a": "x", "b": "y"}
    assert barconcat(row, ["a", "b"]) == "x | y"


def test_titlefix_quita_comillas():
    # Comportamiento CONFIRMADO con datos reales de MOC.
    assert titlefix('Línea 8"-CB-002') == "Línea 8-CB-002"


def test_titlefix_puede_preservar_pulgadas():
    assert titlefix('Línea 8"', preserve_inches=True) == "Línea 8 in"


def test_cloneorigin_es_passthrough():
    assert cloneorigin("valor") == "valor"


def test_cloneorigin_fanout_replica_n_veces():
    assert cloneorigin_fanout("Hola", 5) == ["Hola"] * 5


def test_lookup_simple_usa_default_si_no_existe():
    tabla = {"A": "Abierto", "B": "Cerrado"}
    assert lookup_simple("A", tabla) == "Abierto"
    assert lookup_simple("Z", tabla, default="Desconocido") == "Desconocido"


def test_resolve_rule_normaliza_nombre():
    # Las reglas aparecen escritas de formas distintas en cada módulo.
    assert resolve_rule("Titlefix") is resolve_rule("titlefix") is resolve_rule("TitleFix")


def test_resolve_rule_lanza_si_no_existe():
    import pytest
    with pytest.raises(KeyError):
        resolve_rule("reglaqueseinventaronayer")
