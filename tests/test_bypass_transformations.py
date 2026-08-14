"""Tests unitarios de las transformaciones puras de bypass.By_Passes
(Sprint 9.4). Datos 100% sintéticos -- ningún valor real de cliente.

Ejecutar con: pytest tests/test_bypass_transformations.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.export.prototype.bypass import transformations as tr


# --------------------------------------------------------------------------
# to_historical_id -- REUSED_AS_IS de drills.transformations (se prueba
# aquí solo para confirmar el import/re-export, no para reprobar su lógica
# ya cubierta en tests/test_drills_export_prototype.py).
# --------------------------------------------------------------------------

def test_to_historical_id_reexportado_funciona():
    assert tr.to_historical_id(2878) == "2878"
    assert tr.to_historical_id(2878.0) == "2878"
    assert tr.to_historical_id(None) is None


# --------------------------------------------------------------------------
# resolve_lookup (= drills.resolve_letter reutilizado): null_default SOLO
# para vacío; presente-sin-coincidencia = unresolved, sin default.
# --------------------------------------------------------------------------

_BYPASS_TYPE_LOOKUP = {"1": "Operational", "2": "Preventive Maintenance", "3": "Non-Routine"}
_NULL_DEFAULT = "Null-not_relevant"


def test_resolve_lookup_resuelto():
    result = tr.resolve_lookup(1, _BYPASS_TYPE_LOOKUP, _NULL_DEFAULT)
    assert result.value == "Operational"
    assert result.status == "resolved"


def test_resolve_lookup_vacio_usa_null_default():
    result = tr.resolve_lookup(None, _BYPASS_TYPE_LOOKUP, _NULL_DEFAULT)
    assert result.value == _NULL_DEFAULT
    assert result.status == "null_default"


def test_resolve_lookup_sin_coincidencia_queda_unresolved_sin_default():
    """Confirma la semántica correcta para Bypass: un valor PRESENTE pero
    sin entrada en la tabla NUNCA recibe el null_default -- solo el caso
    vacío lo recibe (evidencia: las hojas Mapeo_* del ETL solo declaran
    un nullcontrol para DatoOrigen=NULL, nunca para "sin coincidencia")."""
    result = tr.resolve_lookup(99, _BYPASS_TYPE_LOOKUP, _NULL_DEFAULT)
    assert result.value is None
    assert result.status == "unresolved"


def test_resolve_lookup_realization_methods_numerico():
    """RealizationMethods: el DatoDestino real es un número, no la letra
    de la columna 'InfoIgnore-clave' del ETL (ver bypass.yaml)."""
    lookup = {"2": 1, "3": 2, "1": 3, "5": 4, "4": 5}
    result = tr.resolve_lookup(2, lookup, "Null value")
    assert result.value == 1
    assert result.status == "resolved"


# --------------------------------------------------------------------------
# nullcontrol_passthrough (Motivo -> Reason)
# --------------------------------------------------------------------------

def test_nullcontrol_passthrough_valor_presente():
    result = tr.nullcontrol_passthrough("Fuga de línea", "Not specified in Migration Data Origin")
    assert result.value == "Fuga de línea"
    assert result.status == "resolved"


@pytest.mark.parametrize("valor_vacio", [None, "", "   "])
def test_nullcontrol_passthrough_vacio_usa_default(valor_vacio):
    result = tr.nullcontrol_passthrough(valor_vacio, "Not specified in Migration Data Origin")
    assert result.value == "Not specified in Migration Data Origin"
    assert result.status == "null_default"


def test_nullcontrol_passthrough_recorta_espacios():
    result = tr.nullcontrol_passthrough("  Fuga  ", "default")
    assert result.value == "Fuga"
