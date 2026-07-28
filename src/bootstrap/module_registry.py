"""Composition root del Module Registry (Sprint 8.6).

Único lugar central del repositorio que importa un módulo funcional
concreto (Drills) para registrarlo en el `ModuleRegistry` genérico del
Core. `src/core/module_registry.py` no importa nada de aquí -- es este
fichero quien importa de ambos lados (Core y Drills) y los conecta, mismo
patrón de dirección de dependencia ya establecido por
`src/export/prototype/drills/core_adapters.py` para `StageRegistry` (ver
`docs/01-architecture/architecture-overview.md` § 1).

Cuando exista un segundo módulo migrable real con pipeline ejecutable,
su registro se añade aquí junto al de Drills -- nunca dentro de
`src/core/`.
"""
from __future__ import annotations

from src.core.contracts import ExecutionContext, ExecutionRequest, PipelineDefinition
from src.core.module_registry import (
    ModuleCapabilities,
    ModuleCapability,
    ModuleDefinition,
    ModuleImplementationStatus,
    ModuleRegistry,
)
from src.core.registry import StageRegistry
from src.export.prototype.drills.core_adapters import (
    OBJECT_TYPE as DRILLS_OBJECT_TYPE,
    build_drills_pipeline_definition,
    build_execution_context,
    register_drills_stages,
)

# Alias verificado contra config/exports/drills.yaml (`module: simulacros`)
# y config/modules.yaml (clave `simulacros`) -- NO se incluye "SM": en
# CLAUDE.md y config/modules.yaml, "SM" identifica Safety Meetings, un
# módulo DISTINTO ("Sistema ITP/Prevención (Simulacros, SM, Eventos,
# Inspecciones, OPS)") -- añadirlo aquí como alias de Drills sería un
# error de identificación, no una simplificación (ver Fase 1 del informe
# de este sprint, tabla de inventario).
DRILLS_ALIASES = frozenset({"simulacros"})


def _drills_pipeline_factory(
    request: ExecutionRequest, registry: StageRegistry,
) -> tuple[PipelineDefinition, ExecutionContext]:
    """Adapta el flujo ya existente en `src/cli.py::run_pipeline` (Fase 5
    de Framework Core v1) a la firma `PipelineFactory` del Module
    Registry -- mismo comportamiento, ahora detrás de un registro
    explícito en vez de estar inline en la CLI."""
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()
    context = build_execution_context(request)
    return definition, context


def _build_drills_definition() -> ModuleDefinition:
    return ModuleDefinition(
        module_id=DRILLS_OBJECT_TYPE,
        canonical_name="Drills",
        display_name="Drills (Business Continuity Management / Simulacros)",
        version="0.1.0",
        status=ModuleImplementationStatus.EXPERIMENTAL,
        # 'experimental', no 'implemented': config/exports/drills.yaml
        # declara prototype_status=review_only -- el pipeline es real y
        # ejecutable, pero el CSV que produce NO está aprobado para carga
        # en Enablon (ver README.md / docstring de src/cli.py::export_drills).
        capabilities=ModuleCapabilities(frozenset({
            ModuleCapability.EXPORT,
            ModuleCapability.SAMPLE,
            ModuleCapability.FULL,
            ModuleCapability.EVIDENCE,
            ModuleCapability.COMPARISON,
            ModuleCapability.VALIDATION,
            ModuleCapability.MANIFEST_DRIVEN_RESOURCES,
            ModuleCapability.LEGACY_CLI,
            ModuleCapability.MAPPING,
            # NO 'canonicalization': DrillsCanonicalizeStage es un seam
            # pass-through documentado (core_adapters.py), no reescribe
            # ninguna transformación -- declararla sería falsear una
            # capacidad no demostrable (Fase 8 del encargo).
            # NO 'import': este repositorio no ejecuta cargas contra
            # Enablon (CLAUDE.md) -- ningún módulo la declara hoy.
        })),
        aliases=DRILLS_ALIASES,
        pipeline_factory=_drills_pipeline_factory,
        supported_modes=frozenset({"sample", "full"}),
        required_artifact_types=frozenset({"sql", "mapping"}),
        optional_artifact_types=frozenset({"operational_csv", "etl", "errors"}),
        description=(
            "Simulacros / Business Continuity Management -- prototipo de "
            "exportación review_only (8 de 36 columnas reales, ver "
            "docs/01-architecture/drills-csv-contract.md). Único módulo con "
            "pipeline ejecutable a fecha de Sprint 8.6."
        ),
        metadata={
            "source_system": "prevencion",
            "prototype_status": "review_only",
            "object_id": DRILLS_OBJECT_TYPE,
        },
    )


def build_default_module_registry() -> ModuleRegistry:
    """Registro por defecto del EMF: hoy, únicamente Drills. Los 7 módulos
    restantes del Workspace Manifest de ejemplo (`safety_meetings`, `moc`,
    `bypass`, `events`, `ops`, `inspections`, `corrective_actions`) NO se
    registran aquí todavía -- ninguno tiene un `pipeline_factory` real
    (Fase 9 del encargo: "no confundir presencia en el proyecto con
    soporte del software"). Su presencia en
    `examples/workspace/workspace.example.yaml` (status=planned) describe
    el ROADMAP del proyecto, no lo que el software sabe ejecutar hoy."""
    registry = ModuleRegistry()
    registry.register(_build_drills_definition())
    return registry
