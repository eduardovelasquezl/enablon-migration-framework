"""
Orquestador global del proyecto -- único punto público de orquestación.

Consolida los resultados de `module_analysis.py` (que a su vez se apoya en
`mapping_resolver.py`/`mapping_coverage.py` antes de llegar aquí -- este
módulo no vuelve a resolver mappings ni a leer Excel/SQL, solo orquesta y
consolida lo que ya se resolvió) y finaliza Action Plans únicamente cuando
todos los módulos del alcance declarado han sido analizados.

No duplica lógica de `module_analysis.py`, `mapping_resolver.py`,
`mapping_coverage.py`, `query_analyzer.py` ni `schema_analyzer.py` -- los
reutiliza (a `module_analysis.py` lo llama directamente; los demás son
insumo de quien construye el `ProjectAnalysisRequest`, antes de que llegue
aquí).

Principio central: la disponibilidad de una acción para carga (`readiness`
individual) es independiente de la cobertura global del proyecto. Un módulo
sin analizar (`unresolved_modules`) bloquea la finalización de TODO el lote
(no sabemos qué depende de él); un módulo analizado pero con resultados
propios incompletos (p. ej. `visitas_seguridad_y_otros` con `idorigenac` sin
clasificar) NO bloquea las acciones ya resueltas de otros módulos -- solo
dejan la cobertura global en `incomplete`.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.analysis import module_analysis
from src.analysis.mapping_coverage import CSV_ENCODING
from src.analysis.module_analysis import ActionPlanCandidate, FieldValidationResult
from src.knowledge_base.model import (
    ActionPlanProcessingStatus,
    ActionPlanRelationshipType,
    CrossModuleActionPlanBuffer,
    MigrationObject,
    OpenQuestion,
    Relation,
    ResolutionStatus,
    Validation,
    slugify,
)

DEFAULT_DEDUP_KEY_FIELDS: tuple[str, ...] = ("source_system", "source_module", "action_plan_historical_id")


def make_parent_index_key(source_system: str, target_historical_reference: str | None) -> str:
    """Clave del índice de referencias de padre -- siempre cualificada por
    sistema origen (ITP/Prevención y GCT tienen numeraciones incompatibles,
    ver CLAUDE.md), nunca solo el identificador histórico a secas."""
    return f"{slugify(source_system)}|{target_historical_reference}"


# ---------------------------------------------------------------------------
# 2. Modelo de entrada
# ---------------------------------------------------------------------------

@dataclass
class ParentResolutionInput:
    """Resultado YA calculado (evidencia exacta, nunca coincidencia
    parcial) de intentar resolver el padre de una acción linked concreta."""
    target_enablon_reference: str | None
    resolution_status: str  # ver ResolutionStatus
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ModuleExecutionSpec:
    """Modo 1 de `ModuleRequest`: lo necesario para que
    `run_project_analysis` delegue en `module_analysis.py` (nunca
    reimplementa su lógica)."""
    candidates: list[ActionPlanCandidate] = field(default_factory=list)
    field_validation_by_source_historical_id: dict[str, FieldValidationResult] = field(default_factory=dict)
    parent_resolution_by_source_historical_id: dict[str, ParentResolutionInput] = field(default_factory=dict)


@dataclass
class ModuleAnalysisResult:
    """Resultado ya construido del análisis de un módulo -- modo 2 de
    `ModuleRequest`: se integra tal cual, sin volver a calcularlo."""
    module_id: str
    source_system: str
    action_plan_buffers: list[CrossModuleActionPlanBuffer] = field(default_factory=list)
    migration_objects: list[MigrationObject] = field(default_factory=list)
    validations: list[Validation] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unresolved_idorigenac_values: list[str] = field(default_factory=list)
    dependency_relations: list[Relation] = field(default_factory=list)


@dataclass
class ModuleRequest:
    """Une los dos modos: `already_resolved` (modo 2) tiene prioridad si se
    proporciona -- no se recalcula nada. Si no, se usa `execution_spec`
    (modo 1)."""
    module_id: str
    source_system: str
    already_resolved: ModuleAnalysisResult | None = None
    execution_spec: ModuleExecutionSpec | None = None
    migration_objects: list[MigrationObject] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.already_resolved is None and self.execution_spec is None:
            raise ValueError(
                f"ModuleRequest({self.module_id!r}) necesita already_resolved o execution_spec"
            )


@dataclass
class ProjectAnalysisRequest:
    project_id: str
    analysis_run_id: str
    module_requests: list[ModuleRequest]
    module_execution_order: list[str]
    parent_reference_index: dict[str, list[str]] = field(default_factory=dict)
    action_plan_deduplication_key: tuple[str, ...] = DEFAULT_DEDUP_KEY_FIELDS
    output_directory: str = "outputs/analysis"
    generate_outputs: bool = False
    source_snapshot_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Modelo de resultado
# ---------------------------------------------------------------------------

@dataclass
class ActionPlanConsolidationResult:
    consolidated_buffers: list[CrossModuleActionPlanBuffer]
    duplicate_groups: list[list[str]] = field(default_factory=list)
    conflicting_groups: list[list[str]] = field(default_factory=list)
    id_collisions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ActionPlanGlobalCoverage:
    status: str  # complete | incomplete | conflicting
    analyzed_modules: list[str]
    unresolved_modules: list[str]
    unresolved_idorigenac_values: list[str]
    total_action_count: int
    linked_action_count: int
    standalone_action_count: int
    ready_action_count: int
    blocked_action_count: int
    excluded_action_count: int
    conflicting_action_count: int
    pending_parent_count: int
    warnings: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class ProjectAnalysisResult:
    project_id: str
    analysis_run_id: str
    module_results: dict[str, ModuleAnalysisResult]
    module_execution_order: list[str]
    migration_objects: list[MigrationObject]
    validations: list[Validation]
    open_questions: list[OpenQuestion]
    warnings: list[str]
    action_plan_buffers: list[CrossModuleActionPlanBuffer]
    action_plan_consolidation_result: ActionPlanConsolidationResult
    global_coverage: ActionPlanGlobalCoverage
    execution_summary: dict
    output_paths: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5. Consolidación del buffer transversal
# ---------------------------------------------------------------------------

def _dedup_key(buffer: CrossModuleActionPlanBuffer, key_fields: tuple[str, ...]) -> tuple:
    return tuple(getattr(buffer, f) for f in key_fields)


def _buffers_are_compatible(a: CrossModuleActionPlanBuffer, b: CrossModuleActionPlanBuffer) -> bool:
    """Dos buffers con la misma clave de deduplicación son el MISMO registro
    visto dos veces solo si coinciden exactamente en lo que determina su
    identidad real -- nunca por similitud de título/descripción/fecha."""
    return (
        a.source_migration_object == b.source_migration_object
        and a.source_historical_id == b.source_historical_id
        and a.relationship_type == b.relationship_type
        and a.target_historical_reference == b.target_historical_reference
    )


def consolidate_action_plan_buffers(
    buffers: list[CrossModuleActionPlanBuffer],
    *,
    dedup_key_fields: tuple[str, ...] = DEFAULT_DEDUP_KEY_FIELDS,
) -> ActionPlanConsolidationResult:
    """Consolida buffers de todos los módulos. Nunca deduplica solo por
    `action_plan_historical_id` (puede no ser global entre Prevención y
    GCT) -- la clave es configurable, por defecto (source_system,
    source_module, action_plan_historical_id).

    Duplicados EXACTOS (misma clave, mismos datos determinantes) se
    consolidan en uno solo conservando TODAS las evidencias/warnings/razones
    de bloqueo. Duplicados con la misma clave pero datos incompatibles NUNCA
    se resuelven eligiendo uno -- se marcan `conflicting`/`blocked`,
    conservando ambas evidencias.
    """
    groups: dict[tuple, list[CrossModuleActionPlanBuffer]] = {}
    for b in buffers:
        groups.setdefault(_dedup_key(b, dedup_key_fields), []).append(b)

    consolidated: list[CrossModuleActionPlanBuffer] = []
    duplicate_groups: list[list[str]] = []
    conflicting_groups: list[list[str]] = []
    warnings: list[str] = []

    for key, group in groups.items():
        if len(group) == 1:
            consolidated.append(group[0])
            continue

        first = group[0]
        if all(_buffers_are_compatible(first, other) for other in group[1:]):
            merged_evidence: list[str] = []
            merged_warnings: list[str] = []
            merged_blocking: list[str] = []
            for g in group:
                merged_evidence.extend(e for e in g.evidence_ids if e not in merged_evidence)
                merged_warnings.extend(w for w in g.warnings if w not in merged_warnings)
                merged_blocking.extend(r for r in g.blocking_reasons if r not in merged_blocking)
            consolidated.append(
                replace(first, evidence_ids=merged_evidence, warnings=merged_warnings, blocking_reasons=merged_blocking)
            )
            duplicate_groups.append([g.id for g in group])
        else:
            conflict_ids = [g.id for g in group]
            all_evidence: list[str] = []
            for g in group:
                all_evidence.extend(e for e in g.evidence_ids if e not in all_evidence)
            consolidated.append(
                replace(
                    first,
                    relationship_status=ResolutionStatus.CONFLICTING,
                    processing_status=ActionPlanProcessingStatus.BLOCKED,
                    blocking_reasons=[*first.blocking_reasons, f"Duplicados incompatibles con clave {key}: {conflict_ids}"],
                    evidence_ids=all_evidence,
                )
            )
            conflicting_groups.append(conflict_ids)
            warnings.append(f"Conflicto de duplicados en clave {key}: {conflict_ids}")

    ids_seen: dict[str, CrossModuleActionPlanBuffer] = {}
    id_collisions: list[str] = []
    for b in consolidated:
        if b.id in ids_seen and ids_seen[b.id] is not b and ids_seen[b.id] != b:
            id_collisions.append(b.id)
        ids_seen[b.id] = b

    return ActionPlanConsolidationResult(
        consolidated_buffers=consolidated,
        duplicate_groups=duplicate_groups,
        conflicting_groups=conflicting_groups,
        id_collisions=id_collisions,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# 6. Resolución del padre
# ---------------------------------------------------------------------------

def resolve_action_plan_parents(
    buffers: list[CrossModuleActionPlanBuffer],
    *,
    parent_reference_index: dict[str, list[str]],
    all_modules_analyzed: bool,
) -> list[CrossModuleActionPlanBuffer]:
    """Resuelve la referencia al objeto origen para acciones
    `linked_action_plan`, únicamente mediante `parent_reference_index`
    (construido a partir de objetos ya procesados con evidencia exacta) --
    nunca por coincidencia parcial, similitud textual, título, descripción
    o fecha aproximada.

    `all_modules_analyzed=False`: un padre no encontrado deja la acción en
    `waiting_for_parent` (todavía podría aparecer). `all_modules_analyzed=
    True` (cierre del alcance declarado): un padre no encontrado pasa a
    `blocked` con razón explícita -- ya no hay más módulos que puedan
    aportarlo.
    """
    resolved: list[CrossModuleActionPlanBuffer] = []
    for buffer in buffers:
        if buffer.relationship_type == ActionPlanRelationshipType.STANDALONE:
            resolved.append(buffer)  # not_applicable, no requiere resolución de padre
            continue

        if buffer.processing_status != ActionPlanProcessingStatus.WAITING_FOR_PARENT:
            # Ya resuelto (parent_resolved, posiblemente por module_analysis.py),
            # ya bloqueado, ya excluido, o todavía sin validar -- en ningún caso
            # se reprocesa ni se sobrescribe aquí.
            resolved.append(buffer)
            continue

        key = make_parent_index_key(buffer.source_system, buffer.target_historical_reference)
        candidates = parent_reference_index.get(key)

        if not candidates:
            if all_modules_analyzed:
                resolved.append(
                    replace(
                        buffer,
                        processing_status=ActionPlanProcessingStatus.BLOCKED,
                        relationship_status=ResolutionStatus.PENDING,
                        blocking_reasons=[
                            *buffer.blocking_reasons,
                            "Padre no encontrado tras analizar todos los módulos del alcance declarado",
                        ],
                    )
                )
            else:
                resolved.append(
                    replace(
                        buffer,
                        processing_status=ActionPlanProcessingStatus.WAITING_FOR_PARENT,
                        relationship_status=ResolutionStatus.PENDING,
                    )
                )
            continue

        distinct = sorted(set(candidates))
        if len(distinct) > 1:
            resolved.append(
                replace(
                    buffer,
                    processing_status=ActionPlanProcessingStatus.BLOCKED,
                    relationship_status=ResolutionStatus.CONFLICTING,
                    blocking_reasons=[*buffer.blocking_reasons, f"Varios padres incompatibles encontrados: {distinct}"],
                )
            )
            continue

        resolved.append(
            replace(
                buffer,
                processing_status=ActionPlanProcessingStatus.PARENT_RESOLVED,
                relationship_status=ResolutionStatus.CONFIRMED,
                target_enablon_reference=distinct[0],
            )
        )

    return resolved


# ---------------------------------------------------------------------------
# 7. Finalización de Action Plans -- ÚNICO punto que produce ready_for_final_load
# ---------------------------------------------------------------------------

def finalize_action_plans(buffers: list[CrossModuleActionPlanBuffer]) -> list[CrossModuleActionPlanBuffer]:
    """Única función de todo el framework autorizada a producir
    `processing_status=ready_for_final_load`. Nunca convierte linked en
    standalone. Excluidas y bloqueadas se conservan tal cual."""
    finalized: list[CrossModuleActionPlanBuffer] = []
    for buffer in buffers:
        if buffer.processing_status in (ActionPlanProcessingStatus.BLOCKED, ActionPlanProcessingStatus.EXCLUDED):
            finalized.append(buffer)
            continue

        if buffer.relationship_type == ActionPlanRelationshipType.LINKED:
            ready = (
                buffer.processing_status == ActionPlanProcessingStatus.PARENT_RESOLVED
                and buffer.relationship_status == ResolutionStatus.CONFIRMED
                and not buffer.blocking_reasons
            )
        else:
            ready = (
                buffer.processing_status == ActionPlanProcessingStatus.VALIDATED
                and buffer.relationship_status == ResolutionStatus.NOT_APPLICABLE
                and not buffer.blocking_reasons
            )

        if ready:
            finalized.append(replace(buffer, processing_status=ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD))
        else:
            finalized.append(buffer)  # no listo todavía; no se inventa un estado nuevo

    return finalized


# ---------------------------------------------------------------------------
# 8. Cobertura global
# ---------------------------------------------------------------------------

def compute_global_coverage(
    *,
    analyzed_modules: list[str],
    unresolved_modules: list[str],
    unresolved_idorigenac_values: list[str],
    buffers: list[CrossModuleActionPlanBuffer],
    dependency_relations: list[Relation],
    warnings: list[str] | None = None,
    open_questions: list[str] | None = None,
) -> ActionPlanGlobalCoverage:
    warnings = list(warnings or [])

    linked = [b for b in buffers if b.relationship_type == ActionPlanRelationshipType.LINKED]
    standalone = [b for b in buffers if b.relationship_type == ActionPlanRelationshipType.STANDALONE]
    ready = [b for b in buffers if b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD]
    blocked = [b for b in buffers if b.processing_status == ActionPlanProcessingStatus.BLOCKED]
    excluded = [b for b in buffers if b.processing_status == ActionPlanProcessingStatus.EXCLUDED]
    conflicting = [b for b in buffers if b.relationship_status == ResolutionStatus.CONFLICTING]
    pending_parent = [b for b in buffers if b.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT]

    pending_dependencies = [
        r for r in dependency_relations if r.resolution_status in (ResolutionStatus.PENDING, ResolutionStatus.INFERRED)
    ]
    conflicting_dependencies = [r for r in dependency_relations if r.resolution_status == ResolutionStatus.CONFLICTING]

    if conflicting or conflicting_dependencies:
        status = "conflicting"
    elif unresolved_modules or unresolved_idorigenac_values or pending_dependencies:
        status = "incomplete"
    else:
        status = "complete"

    return ActionPlanGlobalCoverage(
        status=status,
        analyzed_modules=list(analyzed_modules),
        unresolved_modules=list(unresolved_modules),
        unresolved_idorigenac_values=list(unresolved_idorigenac_values),
        total_action_count=len(buffers),
        linked_action_count=len(linked),
        standalone_action_count=len(standalone),
        ready_action_count=len(ready),
        blocked_action_count=len(blocked),
        excluded_action_count=len(excluded),
        conflicting_action_count=len(conflicting),
        pending_parent_count=len(pending_parent),
        warnings=warnings,
        open_questions=list(open_questions or []),
    )


# ---------------------------------------------------------------------------
# Ejecución de un módulo en modo 1 (delega en module_analysis.py)
# ---------------------------------------------------------------------------

def _execute_module_analysis(request: ModuleRequest) -> ModuleAnalysisResult:
    spec = request.execution_spec
    assert spec is not None  # garantizado por ModuleRequest.__post_init__

    buffers = module_analysis.detect_action_plan_candidates(spec.candidates)

    processed: list[CrossModuleActionPlanBuffer] = []
    for buf in buffers:
        field_validation = spec.field_validation_by_source_historical_id.get(
            buf.source_historical_id,
            FieldValidationResult(is_valid=False, blocking_reasons=["Sin resultado de validación de campos suministrado"]),
        )
        buf = module_analysis.validate_action_plan_fields(buf, field_validation)

        if (
            buf.relationship_type == ActionPlanRelationshipType.LINKED
            and buf.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT
        ):
            parent_resolution = spec.parent_resolution_by_source_historical_id.get(buf.source_historical_id)
            if parent_resolution is not None:
                buf = module_analysis.resolve_parent_reference(
                    buf,
                    target_enablon_reference=parent_resolution.target_enablon_reference,
                    resolution_status=parent_resolution.resolution_status,
                    evidence_ids=parent_resolution.evidence_ids,
                )
        processed.append(buf)

    return ModuleAnalysisResult(
        module_id=request.module_id,
        source_system=request.source_system,
        action_plan_buffers=processed,
        migration_objects=list(request.migration_objects),
    )


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def run_project_analysis(request: ProjectAnalysisRequest) -> ProjectAnalysisResult:
    """Ejecuta el orden global de 6 pasos. Action Plans (pasos 4-6) solo se
    finaliza cuando ningún módulo del alcance declarado queda sin analizar
    -- ver docstring del módulo para la distinción entre "módulo sin
    analizar" (bloquea todo) y "módulo analizado con resultado incompleto"
    (no bloquea a los demás)."""
    module_results: dict[str, ModuleAnalysisResult] = {}
    all_buffers: list[CrossModuleActionPlanBuffer] = []
    all_migration_objects: list[MigrationObject] = []
    all_validations: list[Validation] = []
    all_open_questions: list[OpenQuestion] = []
    all_warnings: list[str] = list(request.warnings)
    all_dependency_relations: list[Relation] = []
    all_unresolved_idorigenac: list[str] = []

    analyzed_modules: list[str] = []
    unresolved_modules: list[str] = []
    requests_by_module = {r.module_id: r for r in request.module_requests}

    for module_id in request.module_execution_order:
        module_request = requests_by_module.get(module_id)
        if module_request is None:
            unresolved_modules.append(module_id)
            continue

        result = (
            module_request.already_resolved
            if module_request.already_resolved is not None
            else _execute_module_analysis(module_request)
        )

        module_results[module_id] = result
        analyzed_modules.append(module_id)
        all_buffers.extend(result.action_plan_buffers)
        all_migration_objects.extend(result.migration_objects)
        all_validations.extend(result.validations)
        all_open_questions.extend(result.open_questions)
        all_warnings.extend(result.warnings)
        all_dependency_relations.extend(result.dependency_relations)
        all_unresolved_idorigenac.extend(result.unresolved_idorigenac_values)

    consolidation = consolidate_action_plan_buffers(all_buffers, dedup_key_fields=request.action_plan_deduplication_key)
    all_warnings.extend(consolidation.warnings)

    all_modules_analyzed = not unresolved_modules
    resolved = resolve_action_plan_parents(
        consolidation.consolidated_buffers,
        parent_reference_index=request.parent_reference_index,
        all_modules_analyzed=all_modules_analyzed,
    )

    if all_modules_analyzed:
        final_buffers = finalize_action_plans(resolved)
    else:
        final_buffers = resolved
        all_warnings.append(
            "Action Plans no se finaliza todavía: quedan módulos del alcance declarado sin analizar "
            f"({unresolved_modules})."
        )

    global_coverage = compute_global_coverage(
        analyzed_modules=analyzed_modules,
        unresolved_modules=unresolved_modules,
        unresolved_idorigenac_values=all_unresolved_idorigenac,
        buffers=final_buffers,
        dependency_relations=all_dependency_relations,
        warnings=all_warnings,
        open_questions=[q.id for q in all_open_questions],
    )

    execution_summary = {
        "modules_analyzed": analyzed_modules,
        "modules_pending": unresolved_modules,
        "total_buffers": len(final_buffers),
        "duplicate_groups": len(consolidation.duplicate_groups),
        "conflicting_groups": len(consolidation.conflicting_groups),
        "id_collisions": len(consolidation.id_collisions),
    }

    result = ProjectAnalysisResult(
        project_id=request.project_id,
        analysis_run_id=request.analysis_run_id,
        module_results=module_results,
        module_execution_order=request.module_execution_order,
        migration_objects=all_migration_objects,
        validations=all_validations,
        open_questions=all_open_questions,
        warnings=all_warnings,
        action_plan_buffers=final_buffers,
        action_plan_consolidation_result=consolidation,
        global_coverage=global_coverage,
        execution_summary=execution_summary,
    )

    if request.generate_outputs:
        result.output_paths = generate_project_outputs(result, request)

    return result


# ---------------------------------------------------------------------------
# 9-11. Salidas -- solo si generate_outputs=True
# ---------------------------------------------------------------------------

OUTPUT_ENCODING = CSV_ENCODING  # utf-8-sig, mismo criterio que mapping_coverage.py


def generate_project_outputs(result: ProjectAnalysisResult, request: ProjectAnalysisRequest) -> dict[str, str]:
    """Escribe primero en una carpeta temporal; solo si TODO se genera sin
    error se publica en `outputs/analysis/<project_id>/<analysis_run_id>/`.
    Nunca sobrescribe una ejecución anterior (esa carpeta no debe existir
    ya). Ante cualquier error, la carpeta temporal se elimina y no se
    publica nada parcial.

    Action Plans (`action_plan_buffers.csv`, `action_plan_conflicts.csv`,
    `action_plan_parent_relationships.csv`, `action_plans_ready.csv`,
    `action_plans_blocked.csv`, `action_plans_excluded.csv`) se escribe
    siempre en último lugar entre las salidas funcionales.
    """
    final_dir = Path(request.output_directory) / request.project_id / request.analysis_run_id
    if final_dir.exists():
        raise FileExistsError(
            f"Ya existe una ejecución publicada en {final_dir!s} -- usa un "
            "analysis_run_id distinto, nunca se sobrescribe una corrida anterior."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="project_analysis_"))
    try:
        file_hashes: dict[str, str] = {}
        row_counts: dict[str, int] = {}

        def _write_csv(name: str, header: list[str], rows: list[list]) -> None:
            path = tmp_dir / name
            with open(path, "w", newline="", encoding=OUTPUT_ENCODING) as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            file_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            row_counts[name] = len(rows)

        # --- resumen agregado, primero (nunca después de Action Plans) ---
        summary = {
            "project_id": result.project_id,
            "analysis_run_id": result.analysis_run_id,
            "global_coverage": {
                "status": result.global_coverage.status,
                "total_action_count": result.global_coverage.total_action_count,
                "ready_action_count": result.global_coverage.ready_action_count,
                "blocked_action_count": result.global_coverage.blocked_action_count,
                "excluded_action_count": result.global_coverage.excluded_action_count,
                "conflicting_action_count": result.global_coverage.conflicting_action_count,
                "unresolved_modules": result.global_coverage.unresolved_modules,
            },
            "execution_summary": result.execution_summary,
        }
        summary_path = tmp_dir / "project_analysis_summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        file_hashes["project_analysis_summary.json"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
        row_counts["project_analysis_summary.json"] = 1

        # --- salidas no funcionales de Action Plans ---
        _write_csv(
            "module_execution_summary.csv",
            ["module_id", "status"],
            [[m, "analyzed"] for m in result.module_execution_order if m in result.module_results]
            + [[m, "unresolved"] for m in result.module_execution_order if m not in result.module_results],
        )
        _write_csv(
            "migration_objects.csv",
            ["id", "name", "processing_scope", "load_phase"],
            [[o.id, o.name, o.processing_scope, o.load_phase] for o in result.migration_objects],
        )
        _write_csv(
            "validations.csv",
            ["id", "description", "action"],
            [[v.id, v.description, v.action] for v in result.validations],
        )
        _write_csv(
            "open_questions.csv",
            ["id", "question_text", "status"],
            [[q.id, q.question_text, q.status] for q in result.open_questions],
        )
        _write_csv("warnings.csv", ["warning"], [[w] for w in result.warnings])
        _write_csv(
            "unresolved_idorigenac.csv",
            ["idorigenac_value"],
            [[v] for v in result.global_coverage.unresolved_idorigenac_values],
        )

        # --- Action Plans: última salida funcional ---
        _write_csv(
            "action_plan_buffers.csv",
            ["id", "source_system", "source_module", "source_migration_object", "relationship_type",
             "relationship_status", "processing_status"],
            [
                [b.id, b.source_system, b.source_module, b.source_migration_object, b.relationship_type,
                 b.relationship_status, b.processing_status]
                for b in result.action_plan_buffers
            ],
        )
        _write_csv(
            "action_plan_conflicts.csv",
            ["conflict_group_ids"],
            [[";".join(g)] for g in result.action_plan_consolidation_result.conflicting_groups],
        )
        _write_csv(
            "action_plan_parent_relationships.csv",
            ["id", "target_historical_reference", "target_enablon_reference", "relationship_status"],
            [
                [b.id, b.target_historical_reference, b.target_enablon_reference, b.relationship_status]
                for b in result.action_plan_buffers
                if b.relationship_type == ActionPlanRelationshipType.LINKED
            ],
        )
        ready = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD]
        _write_csv(
            "action_plans_ready.csv",
            ["id", "action_plan_historical_id", "source_system", "source_module", "target_enablon_reference"],
            [[b.id, b.action_plan_historical_id, b.source_system, b.source_module, b.target_enablon_reference] for b in ready],
        )
        blocked = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.BLOCKED]
        _write_csv(
            "action_plans_blocked.csv",
            ["id", "action_plan_historical_id", "source_system", "source_module", "blocking_reasons"],
            [[b.id, b.action_plan_historical_id, b.source_system, b.source_module, "; ".join(b.blocking_reasons)] for b in blocked],
        )
        excluded = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.EXCLUDED]
        _write_csv(
            "action_plans_excluded.csv",
            ["id", "action_plan_historical_id", "source_system", "source_module", "warnings"],
            [[b.id, b.action_plan_historical_id, b.source_system, b.source_module, "; ".join(b.warnings)] for b in excluded],
        )

        manifest = {
            "project_id": result.project_id,
            "analysis_run_id": result.analysis_run_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_snapshots": list(request.source_snapshot_ids),
            "modules_analyzed": list(result.module_results.keys()),
            "modules_pending": [m for m in result.module_execution_order if m not in result.module_results],
            "output_files": list(file_hashes.keys()),
            "file_hashes": file_hashes,
            "row_counts": row_counts,
            "encoding": OUTPUT_ENCODING,
            "global_coverage_status": result.global_coverage.status,
            "ready_action_count": result.global_coverage.ready_action_count,
            "blocked_action_count": result.global_coverage.blocked_action_count,
            "excluded_action_count": result.global_coverage.excluded_action_count,
            "warnings_count": len(result.warnings),
            "open_questions_count": len(result.open_questions),
        }
        manifest_path = tmp_dir / "manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_dir), str(final_dir))
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return {name: str(final_dir / name) for name in [*file_hashes.keys(), "manifest.yaml"]}
