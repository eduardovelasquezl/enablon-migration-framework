"""Tests unitarios de las transformaciones puras de
safety_meetings.Group_Meetings (Sprint 9.7). Datos 100% sintéticos --
ningún valor real de cliente.

Ejecutar con: pytest tests/test_safety_meetings_transformations.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

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
# passthrough_or_empty (Lugar -> CS_MeetingPlace, Asistentes -> CS_HistoricalAtendee)
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


# --------------------------------------------------------------------------
# resolve_start_date (Micro-sprint 9.10.3) -- Fecha + Hora -> StartDate.
# Regla VERIFIED contra ITP-SM-DBC (10.782 filas reales, 10778/10778 exacto
# donde FechaHora existe -- ver Informe-Micro-Sprint-9.10.2-StartDate-
# RootCause-EMF.md). Reutiliza parse_hora/parse_starting_date de
# drills.transformations SIN reimplementar -- se confirma aquí solo el
# import/re-export (mismo patrón que to_historical_id) y el formateo final
# (que sí es propio de Safety Meetings, porque format_starting_date no
# soporta segundos). Datos 100% sintéticos, ningún valor real de cliente.
# --------------------------------------------------------------------------

def test_resolve_start_date_reexporta_las_mismas_funciones_de_drills():
    """Identidad de objeto, no una copia -- mismo patrón que Sprint 9.8
    confirmó para to_historical_id/resolve_workflow_status."""
    from src.export.prototype.drills.transformations import parse_hora, parse_starting_date
    assert tr.parse_hora is parse_hora
    assert tr.parse_starting_date is parse_starting_date


def test_resolve_start_date_fecha_y_hora_normal_hmm():
    result = tr.resolve_start_date("18/06/2018 00:00:00", "9:59")
    assert result.value == "18/06/2018 09:59:00"
    assert result.status == "resolved"


def test_resolve_start_date_fecha_y_hora_normal_hhmm():
    result = tr.resolve_start_date("18/06/2018 00:00:00", "09:59")
    assert result.value == "18/06/2018 09:59:00"
    assert result.status == "resolved"


def test_resolve_start_date_hora_vacia_conserva_solo_la_fecha():
    """Hora ausente: se conserva la fecha con hora 00:00:00 -- nunca se
    inventa una hora (comportamiento de parse_starting_date, no nuevo)."""
    for hora_vacia in (None, "", "   "):
        result = tr.resolve_start_date("18/06/2018 00:00:00", hora_vacia)
        assert result.value == "18/06/2018 00:00:00"
        assert result.status == "resolved"


@pytest.mark.parametrize("hora_corrupta", ["10:", "12:", "7:000", "14:"])
def test_resolve_start_date_hora_corrupta_conserva_solo_la_fecha(hora_corrupta):
    """Las 4 formas de Hora corrupta encontradas en ITP-SM-DBC -- el propio
    ETL las dejaba con FechaHora vacío; parse_starting_date las rechaza con
    el mismo criterio y conserva solo la fecha, nunca inventa una hora."""
    result = tr.resolve_start_date("18/06/2018 00:00:00", hora_corrupta)
    assert result.value == "18/06/2018 00:00:00"
    assert result.status == "resolved"


def test_resolve_start_date_fecha_invalida_nunca_inventa_fecha():
    result = tr.resolve_start_date("no-es-una-fecha", "9:59")
    assert result.value == ""
    assert result.status == "empty"


def test_resolve_start_date_fecha_ausente_nunca_inventa_fecha():
    result = tr.resolve_start_date(None, "9:59")
    assert result.value == ""
    assert result.status == "empty"


def test_resolve_start_date_formato_salida_dd_mm_yyyy_hh_mm_ss():
    result = tr.resolve_start_date("01/01/2024 00:00:00", "5:07")
    assert result.value == "01/01/2024 05:07:00"
