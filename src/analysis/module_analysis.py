"""
Análisis por módulo de candidatos a Action Plans -- único punto público.

Detecta candidatos, valida sus campos y resuelve la referencia al objeto
origen (padre) para acciones `linked_action_plan`, produciendo entradas de
`CrossModuleActionPlanBuffer`. Reutiliza la misma disciplina ya establecida
en `mapping_resolver.py`/`mapping_coverage.py`: nunca resuelve una relación
por coincidencia parcial, nunca sustituye una ausencia por un valor
inventado.

Contrato duro (verificado en tests/test_module_analysis.py):

- NUNCA produce `processing_status=ready_for_final_load` -- esa transición
  es exclusiva de `project_analysis.py` (no implementado todavía), incluso
  para acciones `standalone_action_plan`. Action Plans es siempre la última
  fase funcional de la migración, sin atajos por módulo.
- NUNCA genera ningún CSV.
- NUNCA resuelve `target_enablon_reference` por coincidencia parcial.
- NUNCA sustituye un padre ausente por un registro histórico no documentado.
- NUNCA convierte una acción `linked_action_plan` en `standalone_action_plan`
  por no encontrar su padre -- sigue siendo `linked`, sigue `waiting_for_parent`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from src.knowledge_base.model import (
    ActionPlanProcessingStatus,
    ActionPlanRelationshipType,
    CrossModuleActionPlanBuffer,
    ResolutionStatus,
    make_cross_module_action_plan_buffer_id,
)


@dataclass
class ActionPlanCandidate:
    """Entrada cruda detectada en un módulo, antes de validar campos ni
    resolver la relación con el objeto origen."""
    source_system: str
    source_module: str
    source_migration_object: str
    source_historical_id: str
    action_plan_historical_id: str
    relationship_type: str  # ver ActionPlanRelationshipType
    target_historical_reference: str | None = None


@dataclass
class FieldValidationResult:
    """Resultado de validar los campos PROPIOS de una acción (reutilizando
    `mapping_resolver.py`/`mapping_coverage.py` para la resolución real de
    mappings -- este dataclass es el resultado ya calculado, no lo calcula
    `module_analysis.py` por sí mismo)."""
    is_valid: bool
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


def detect_action_plan_candidates(candidates: list[ActionPlanCandidate]) -> list[CrossModuleActionPlanBuffer]:
    """Convierte candidatos crudos en entradas de buffer en estado
    `discovered`. No valida campos todavía (ver `validate_action_plan_fields`)
    ni resuelve la relación con el padre (ver `resolve_parent_reference`).

    Para `standalone_action_plan`, `relationship_status` es
    `not_applicable` desde el principio -- no hay relación que resolver.
    Para `linked_action_plan`, `pending` hasta que se demuestre lo
    contrario.
    """
    buffers = []
    for c in candidates:
        relationship_status = (
            ResolutionStatus.NOT_APPLICABLE
            if c.relationship_type == ActionPlanRelationshipType.STANDALONE
            else ResolutionStatus.PENDING
        )
        buffers.append(
            CrossModuleActionPlanBuffer(
                id=make_cross_module_action_plan_buffer_id(
                    source_system=c.source_system,
                    source_module=c.source_module,
                    source_migration_object=c.source_migration_object,
                    action_plan_historical_id=c.action_plan_historical_id,
                    source_historical_id=c.source_historical_id,
                ),
                action_plan_historical_id=c.action_plan_historical_id,
                source_system=c.source_system,
                source_module=c.source_module,
                source_migration_object=c.source_migration_object,
                source_historical_id=c.source_historical_id,
                relationship_type=c.relationship_type,
                target_historical_reference=c.target_historical_reference,
                target_enablon_reference=None,
                relationship_status=relationship_status,
                processing_status=ActionPlanProcessingStatus.DISCOVERED,
            )
        )
    return buffers


def validate_action_plan_fields(
    buffer: CrossModuleActionPlanBuffer,
    field_validation: FieldValidationResult,
) -> CrossModuleActionPlanBuffer:
    """Aplica el resultado de validar los campos propios de la acción.

    "validated" describe únicamente que los campos están bien -- NUNCA que
    el padre esté resuelto ni que la acción esté lista para carga. Por eso,
    para una acción `linked_action_plan` con campos válidos, el estado
    almacenado pasa directamente a `waiting_for_parent` (con
    `relationship_status=pending`) en vez de quedarse en un `validated`
    "de descanso" -- solo las acciones `standalone_action_plan` reposan en
    `validated` hasta que `project_analysis.py` las recoja.

    Nunca produce `ready_for_final_load` -- ver contrato del módulo.
    """
    if not field_validation.is_valid:
        return replace(
            buffer,
            processing_status=ActionPlanProcessingStatus.BLOCKED,
            blocking_reasons=[*buffer.blocking_reasons, *field_validation.blocking_reasons],
            warnings=[*buffer.warnings, *field_validation.warnings],
            evidence_ids=[*buffer.evidence_ids, *field_validation.evidence_ids],
        )

    if buffer.relationship_type == ActionPlanRelationshipType.STANDALONE:
        return replace(
            buffer,
            processing_status=ActionPlanProcessingStatus.VALIDATED,
            warnings=[*buffer.warnings, *field_validation.warnings],
            evidence_ids=[*buffer.evidence_ids, *field_validation.evidence_ids],
        )

    # linked_action_plan: campos correctos, pero el padre sigue sin resolver
    # hasta que resolve_parent_reference() diga lo contrario.
    return replace(
        buffer,
        processing_status=ActionPlanProcessingStatus.WAITING_FOR_PARENT,
        relationship_status=ResolutionStatus.PENDING,
        warnings=[*buffer.warnings, *field_validation.warnings],
        evidence_ids=[*buffer.evidence_ids, *field_validation.evidence_ids],
    )


def resolve_parent_reference(
    buffer: CrossModuleActionPlanBuffer,
    *,
    target_enablon_reference: str | None,
    resolution_status: str,
    evidence_ids: list[str],
) -> CrossModuleActionPlanBuffer:
    """Intenta resolver la referencia del objeto origen (padre) para una
    acción `linked_action_plan`. `resolution_status` debe venir de
    evidencia ya verificada (coincidencia exacta) -- esta función no decide
    por sí sola si la referencia es válida, solo aplica el resultado.

    Si `target_enablon_reference is None` (padre no encontrado), la acción
    SIGUE siendo `linked_action_plan` y queda `waiting_for_parent` --
    NUNCA se reclasifica como `standalone_action_plan` por no encontrar el
    padre. Esa es una regla dura, no una conveniencia de implementación.
    """
    if buffer.relationship_type != ActionPlanRelationshipType.LINKED:
        raise ValueError(
            "resolve_parent_reference solo aplica a acciones linked_action_plan "
            f"(esta es {buffer.relationship_type!r})"
        )

    if target_enablon_reference is None:
        return replace(
            buffer,
            processing_status=ActionPlanProcessingStatus.WAITING_FOR_PARENT,
            relationship_status=ResolutionStatus.PENDING,
            evidence_ids=[*buffer.evidence_ids, *evidence_ids],
        )

    return replace(
        buffer,
        processing_status=ActionPlanProcessingStatus.PARENT_RESOLVED,
        relationship_status=resolution_status,
        target_enablon_reference=target_enablon_reference,
        evidence_ids=[*buffer.evidence_ids, *evidence_ids],
    )


def mark_excluded(buffer: CrossModuleActionPlanBuffer, *, reason: str, evidence_ids: list[str]) -> CrossModuleActionPlanBuffer:
    """Marca una acción como excluida (decisión funcional documentada, p.
    ej. 'No migra') -- requiere `reason` explícita, nunca se excluye sin
    motivo registrado."""
    return replace(
        buffer,
        processing_status=ActionPlanProcessingStatus.EXCLUDED,
        warnings=[*buffer.warnings, reason],
        evidence_ids=[*buffer.evidence_ids, *evidence_ids],
    )
