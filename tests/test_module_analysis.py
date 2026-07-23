"""Tests de src/analysis/module_analysis.py. Ejecutar con: pytest tests/"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import module_analysis
from src.analysis.module_analysis import (
    ActionPlanCandidate,
    FieldValidationResult,
    detect_action_plan_candidates,
    mark_excluded,
    resolve_parent_reference,
    validate_action_plan_fields,
)
from src.knowledge_base.model import (
    ActionPlanProcessingStatus,
    ActionPlanRelationshipType,
    ResolutionStatus,
)


def _linked_candidate(**overrides) -> ActionPlanCandidate:
    base = dict(
        source_system="prevencion",
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        source_historical_id="EVT-500",
        action_plan_historical_id="AP-100",
        relationship_type=ActionPlanRelationshipType.LINKED,
        target_historical_reference="EVT-500",
    )
    base.update(overrides)
    return ActionPlanCandidate(**base)


def _standalone_candidate(**overrides) -> ActionPlanCandidate:
    base = dict(
        source_system="prevencion",
        source_module="module:ops",
        source_migration_object="migration_object:ops.jso",
        source_historical_id="OPS-900",
        action_plan_historical_id="AP-200",
        relationship_type=ActionPlanRelationshipType.STANDALONE,
        target_historical_reference=None,
    )
    base.update(overrides)
    return ActionPlanCandidate(**base)


# ---------------------------------------------------------------------------
# Contrato duro: nunca ready_for_final_load, nunca CSV
# ---------------------------------------------------------------------------

def test_module_analysis_nunca_produce_ready_for_final_load_en_el_codigo():
    # El texto "ready_for_final_load" SÍ aparece en los docstrings (explica
    # la garantía) -- lo que no debe existir es una referencia ejecutable
    # al valor del enum, que es la única forma en que el código podría
    # llegar a asignarlo.
    source = inspect.getsource(module_analysis)
    assert "ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD" not in source


def test_module_analysis_nunca_produce_ready_for_final_load_en_ejecucion():
    # Recorre el flujo completo posible (discovered -> validated/waiting ->
    # parent_resolved) y comprueba que ready_for_final_load nunca aparece.
    buf = detect_action_plan_candidates([_linked_candidate()])[0]
    buf = validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    buf = resolve_parent_reference(
        buf, target_enablon_reference="MOEVE > ... > EPSR", resolution_status=ResolutionStatus.CONFIRMED, evidence_ids=["evidence:x#1"]
    )
    assert buf.processing_status != ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD
    assert buf.processing_status == ActionPlanProcessingStatus.PARENT_RESOLVED


def test_module_analysis_no_escribe_ningun_csv():
    source = inspect.getsource(module_analysis)
    assert ".csv" not in source.lower()
    assert "import csv" not in source
    assert "open(" not in source


# ---------------------------------------------------------------------------
# linked sin padre -> waiting_for_parent
# ---------------------------------------------------------------------------

def test_linked_con_campos_validos_y_sin_padre_resuelto_queda_waiting_for_parent():
    buf = detect_action_plan_candidates([_linked_candidate()])[0]
    assert buf.processing_status == ActionPlanProcessingStatus.DISCOVERED

    buf = validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    assert buf.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT
    assert buf.relationship_status == ResolutionStatus.PENDING
    # "validated" no implica que el padre esté resuelto ni que esté lista
    # para carga -- confirmado: sigue linked, sigue sin target_enablon_reference.
    assert buf.target_enablon_reference is None


def test_linked_con_campos_invalidos_queda_blocked():
    buf = detect_action_plan_candidates([_linked_candidate()])[0]
    buf = validate_action_plan_fields(
        buf, FieldValidationResult(is_valid=False, blocking_reasons=["campo X sin transformar"])
    )
    assert buf.processing_status == ActionPlanProcessingStatus.BLOCKED
    assert "campo X sin transformar" in buf.blocking_reasons


# ---------------------------------------------------------------------------
# standalone -> relationship_status=not_applicable, siempre
# ---------------------------------------------------------------------------

def test_standalone_usa_relationship_status_not_applicable_desde_el_principio():
    buf = detect_action_plan_candidates([_standalone_candidate()])[0]
    assert buf.relationship_status == ResolutionStatus.NOT_APPLICABLE


def test_standalone_mantiene_not_applicable_tras_validar_campos():
    buf = detect_action_plan_candidates([_standalone_candidate()])[0]
    buf = validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    assert buf.processing_status == ActionPlanProcessingStatus.VALIDATED
    assert buf.relationship_status == ResolutionStatus.NOT_APPLICABLE  # no se toca


# ---------------------------------------------------------------------------
# Padre ausente NUNCA convierte linked en standalone
# ---------------------------------------------------------------------------

def test_padre_ausente_no_convierte_linked_en_standalone():
    buf = detect_action_plan_candidates([_linked_candidate()])[0]
    buf = validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    buf = resolve_parent_reference(buf, target_enablon_reference=None, resolution_status=ResolutionStatus.PENDING, evidence_ids=[])

    assert buf.relationship_type == ActionPlanRelationshipType.LINKED  # nunca cambia
    assert buf.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT
    assert buf.relationship_status == ResolutionStatus.PENDING


def test_resolve_parent_reference_solo_aplica_a_linked():
    buf = detect_action_plan_candidates([_standalone_candidate()])[0]
    with pytest.raises(ValueError):
        resolve_parent_reference(buf, target_enablon_reference="X", resolution_status=ResolutionStatus.CONFIRMED, evidence_ids=[])


# ---------------------------------------------------------------------------
# IDs no colisionan entre fuentes distintas
# ---------------------------------------------------------------------------

def test_acciones_de_fuentes_distintas_no_colisionan_en_id():
    prevencion = _linked_candidate(source_system="prevencion")
    gct = _linked_candidate(source_system="gct")
    buffers = detect_action_plan_candidates([prevencion, gct])
    assert buffers[0].id != buffers[1].id


def test_mismo_source_historical_id_en_modulos_distintos_no_colisiona():
    a = _linked_candidate(source_module="module:eventos", source_migration_object="migration_object:eventos.events")
    b = _linked_candidate(source_module="module:inspecciones", source_migration_object="migration_object:inspecciones.inspections")
    buffers = detect_action_plan_candidates([a, b])
    assert buffers[0].id != buffers[1].id


# ---------------------------------------------------------------------------
# Un módulo pendiente no bloquea acciones confirmadas de otro módulo
# ---------------------------------------------------------------------------

def test_visitas_seguridad_y_otros_pendiente_no_bloquea_acciones_de_otro_modulo():
    pendiente = _linked_candidate(
        source_module="module:visitas_seguridad_y_otros",
        source_migration_object="migration_object:visitas_seguridad_y_otros.visitas",
        source_historical_id="VIS-1",
        action_plan_historical_id="AP-300",
    )
    confirmada = _linked_candidate(
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        source_historical_id="EVT-777",
        action_plan_historical_id="AP-400",
    )
    buf_pendiente, buf_confirmada = detect_action_plan_candidates([pendiente, confirmada])

    # Procesar la pendiente como bloqueada (idorigenac no clasificable) no
    # debe afectar en nada al procesamiento independiente de la otra.
    buf_pendiente = validate_action_plan_fields(
        buf_pendiente, FieldValidationResult(is_valid=False, blocking_reasons=["módulo visitas_seguridad_y_otros sin analizar"])
    )
    buf_confirmada = validate_action_plan_fields(buf_confirmada, FieldValidationResult(is_valid=True))
    buf_confirmada = resolve_parent_reference(
        buf_confirmada, target_enablon_reference="MOEVE > ... > Evento777",
        resolution_status=ResolutionStatus.CONFIRMED, evidence_ids=["evidence:x#1"],
    )

    assert buf_pendiente.processing_status == ActionPlanProcessingStatus.BLOCKED
    assert buf_confirmada.processing_status == ActionPlanProcessingStatus.PARENT_RESOLVED
    assert buf_confirmada.relationship_status == ResolutionStatus.CONFIRMED
    # Ningún campo de una entrada se filtró a la otra (objetos independientes).
    assert buf_pendiente.id != buf_confirmada.id
    assert buf_pendiente.source_module != buf_confirmada.source_module


# ---------------------------------------------------------------------------
# mark_excluded exige motivo documentado
# ---------------------------------------------------------------------------

def test_mark_excluded_registra_motivo():
    buf = detect_action_plan_candidates([_standalone_candidate()])[0]
    buf = mark_excluded(buf, reason="Decisión funcional: código en rollback conocido (Site Canarias)", evidence_ids=["evidence:x#1"])
    assert buf.processing_status == ActionPlanProcessingStatus.EXCLUDED
    assert any("rollback" in w for w in buf.warnings)
