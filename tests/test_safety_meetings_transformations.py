"""Tests unitarios de las transformaciones puras de
safety_meetings.Group_Meetings (Sprint 9.7). Datos 100% sintéticos --
ningún valor real de cliente.

Ejecutar con: pytest tests/test_safety_meetings_transformations.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.export.prototype.safety_meetings import transformations as tr


# --------------------------------------------------------------------------
# to_historical_id -- REUSED de drills.transformations (se prueba aquí solo
# para confirmar el import/re-export, mismo patrón que Bypass).
# --------------------------------------------------------------------------

def test_to_historical_id_reexportado_funciona():
    assert tr.to_historical_id(5303) == "5303"
    assert tr.to_historical_id(5303.0) == "5303"
    assert tr.to_historical_id(None) is None


# --------------------------------------------------------------------------
# resolve_lookup (= drills.resolve_workflow_status reutilizado): SIN
# default en ningún caso -- ni vacío ni sin coincidencia. Semántica
# distinta de Bypass (que sí tiene null_default documentado) porque ningún
# Mapeo_* de Safety Meetings documenta un nullcontrol.
# --------------------------------------------------------------------------

_WORKFLOW_LOOKUP = {"1": "Scheduled", "2": "Initiated", "3": "Validation", "4": "Completed"}


def test_resolve_lookup_resuelto():
    result = tr.resolve_lookup(4, _WORKFLOW_LOOKUP)
    assert result.value == "Completed"
    assert result.status == "resolved"


def test_resolve_lookup_vacio_queda_unresolved_sin_default():
    """A diferencia de Bypass: aquí NO hay null_default documentado -- un
    valor vacío también queda 'unresolved', nunca se inventa un literal."""
    result = tr.resolve_lookup(None, _WORKFLOW_LOOKUP)
    assert result.value is None
    assert result.status == "unresolved"


def test_resolve_lookup_sin_coincidencia_queda_unresolved():
    result = tr.resolve_lookup(99, _WORKFLOW_LOOKUP)
    assert result.value is None
    assert result.status == "unresolved"


def test_resolve_lookup_level_numerico():
    """CS_Level: el DatoDestino real es un número (IDNivel -> 1..8)."""
    level_lookup = {"256": 1, "257": 2, "371": 3, "372": 4, "640": 5, "856": 6, "857": 8}
    result = tr.resolve_lookup(857, level_lookup)
    assert result.value == 8
    assert result.status == "resolved"


# --------------------------------------------------------------------------
# passthrough_or_empty (Fecha -> StartDate, Lugar -> CS_MeetingPlace,
# Asistentes -> CS_HistoricalAtendee)
# --------------------------------------------------------------------------

def test_passthrough_or_empty_valor_presente():
    result = tr.passthrough_or_empty("Sala San Roque")
    assert result.value == "Sala San Roque"
    assert result.status == "resolved"


def test_passthrough_or_empty_recorta_espacios():
    result = tr.passthrough_or_empty("  Sala  ")
    assert result.value == "Sala"


def test_passthrough_or_empty_vacio_nunca_inventa_default():
    """Sin nullcontrol documentado -- un valor ausente queda explícitamente
    vacío (status='empty'), nunca se sustituye por un literal inventado."""
    result = tr.passthrough_or_empty(None)
    assert result.value == ""
    assert result.status == "empty"


def test_passthrough_or_empty_cadena_vacia_tambien_es_empty():
    result = tr.passthrough_or_empty("   ")
    assert result.value == ""
    assert result.status == "empty"
