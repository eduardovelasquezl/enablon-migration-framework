"""Composition root del Module Registry (Sprint 8.6; segundo módulo real
-- Bypass -- añadido en Sprint 9.4; tercer módulo real -- Safety Meetings
-- añadido en Sprint 9.7).

Único lugar central del repositorio que importa un módulo funcional
concreto (Drills, Bypass, Safety Meetings) para registrarlo en el
`ModuleRegistry` genérico del Core. `src/core/module_registry.py` no
importa nada de aquí -- es este fichero quien importa de ambos lados
(Core y cada módulo) y los conecta, mismo patrón de dirección de
dependencia ya establecido por `src/export/prototype/drills/core_adapters.py`
/ `src/export/prototype/bypass/core_adapters.py` /
`src/export/prototype/safety_meetings/core_adapters.py` para
`StageRegistry` (ver `docs/01-architecture/architecture-overview.md` § 1).

Safety Meetings confirma, con un TERCER módulo real, que este patrón se
replica sin tocar `src/core/` -- ver
docs/07-developer-guide/safety-meetings-module.md § 3/6.
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
from src.export.prototype.bypass.core_adapters import (
    OBJECT_TYPE as BYPASS_OBJECT_TYPE,
    build_bypass_pipeline_definition,
    build_execution_context as build_bypass_execution_context,
    register_bypass_stages,
)
from src.export.prototype.drills.core_adapters import (
    OBJECT_TYPE as DRILLS_OBJECT_TYPE,
    build_drills_pipeline_definition,
    build_execution_context,
    register_drills_stages,
)
from src.export.prototype.safety_meetings.core_adapters import (
    OBJECT_TYPE as SAFETY_MEETINGS_OBJECT_TYPE,
    build_execution_context as build_safety_meetings_execution_context,
    build_safety_meetings_pipeline_definition,
    register_safety_meetings_stages,
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


def _bypass_pipeline_factory(
    request: ExecutionRequest, registry: StageRegistry,
) -> tuple[PipelineDefinition, ExecutionContext]:
    """Mismo patrón que `_drills_pipeline_factory` -- Sprint 9.4 confirma
    que se replica sin cambios de Core."""
    register_bypass_stages(registry)
    definition = build_bypass_pipeline_definition()
    context = build_bypass_execution_context(request)
    return definition, context


def _build_bypass_definition() -> ModuleDefinition:
    return ModuleDefinition(
        module_id=BYPASS_OBJECT_TYPE,
        canonical_name="By_Passes",
        display_name="Bypass de Funciones y Elementos de Seguridad (BES)",
        version="0.1.0",
        status=ModuleImplementationStatus.EXPERIMENTAL,
        # 'experimental', no 'implemented': mismo motivo que Drills --
        # config/exports/bypass.yaml declara prototype_status=review_only,
        # y este incremento (Sprint 9.4) se detiene deliberadamente en
        # BYPASS_OFFLINE_SAMPLE_READY, sin sample real ejecutado todavía.
        capabilities=ModuleCapabilities(frozenset({
            ModuleCapability.EXPORT,
            ModuleCapability.SAMPLE,
            ModuleCapability.FULL,
            ModuleCapability.VALIDATION,
            ModuleCapability.MANIFEST_DRIVEN_RESOURCES,
            ModuleCapability.MAPPING,
            # NO 'evidence': no implementada para Bypass en Sprint 9.4
            # (no era necesaria para BYPASS_OFFLINE_SAMPLE_READY) --
            # declararla sería falsear una capacidad no demostrada.
            # NO 'comparison': el Project Contract real (Operational)
            # tiene una anomalía de datos confirmada en
            # CS_HistoricalOriginID (Sprint 9.4) que bloquea una
            # comparación automática fiable hoy -- ver
            # docs/07-developer-guide/bypass-module.md § 7.
            # NO 'legacy_cli': no existe un 'export bypass' heredado
            # (a diferencia de 'export drills') -- solo el camino
            # genérico 'run' aplica a Bypass desde el principio.
            # NO 'import': igual que Drills, este repositorio no ejecuta
            # cargas contra Enablon.
        })),
        aliases=frozenset(),
        pipeline_factory=_bypass_pipeline_factory,
        supported_modes=frozenset({"sample", "full"}),
        required_artifact_types=frozenset({"sql", "mapping"}),
        optional_artifact_types=frozenset({"operational_csv", "etl", "errors"}),
        description=(
            "Bypass de Funciones y Elementos de Seguridad -- prototipo de "
            "exportación review_only (7 de 43 columnas del Operational real, "
            "ver config/exports/bypass.yaml). Segundo módulo con pipeline "
            "ejecutable del EMF (Sprint 9.4), detenido en "
            "BYPASS_OFFLINE_SAMPLE_READY -- sin sample real ejecutado todavía."
        ),
        metadata={
            "source_system": "prevencion",
            "prototype_status": "review_only",
            "object_id": BYPASS_OBJECT_TYPE,
        },
    )


def _safety_meetings_pipeline_factory(
    request: ExecutionRequest, registry: StageRegistry,
) -> tuple[PipelineDefinition, ExecutionContext]:
    """Mismo patrón que `_drills_pipeline_factory`/`_bypass_pipeline_factory`
    -- Sprint 9.7 confirma, con un TERCER módulo real, que se replica sin
    cambios de Core."""
    register_safety_meetings_stages(registry)
    definition = build_safety_meetings_pipeline_definition()
    context = build_safety_meetings_execution_context(request)
    return definition, context


def _build_safety_meetings_definition() -> ModuleDefinition:
    return ModuleDefinition(
        module_id=SAFETY_MEETINGS_OBJECT_TYPE,
        canonical_name="Group_Meetings",
        display_name="Safety Meetings (Reuniones de grupo)",
        version="0.1.0",
        status=ModuleImplementationStatus.EXPERIMENTAL,
        # 'experimental', no 'implemented': mismo motivo que Drills/Bypass
        # -- config/exports/safety_meetings.yaml declara
        # prototype_status=review_only, y este incremento (Sprint 9.7) se
        # detiene deliberadamente en SAFETY_MEETINGS_OFFLINE_SAMPLE_READY,
        # sin sample real ejecutado todavía.
        capabilities=ModuleCapabilities(frozenset({
            ModuleCapability.EXPORT,
            ModuleCapability.SAMPLE,
            ModuleCapability.FULL,
            ModuleCapability.VALIDATION,
            ModuleCapability.MANIFEST_DRIVEN_RESOURCES,
            ModuleCapability.MAPPING,
            # NO 'evidence': no implementada (src/evidence/ sigue
            # hardcodeado a Drills, ver Sprint 9.5.1/9.6/9.7) --
            # declararla sería falsear una capacidad no demostrada.
            # NO 'comparison': el Project Contract real (Operational) es
            # uno de los DOS candidatos de un módulo genuinamente
            # multi-object (ver metadata['multi_object_gap']) -- conectar
            # comparison automática antes de resolver esa ambigüedad
            # arriesgaría comparar contra el objeto equivocado.
            # NO 'legacy_cli': solo el camino genérico 'run' aplica, igual
            # que Bypass.
            # NO 'canonicalization': mismo motivo que Bypass -- sin valor
            # demostrado todavía.
            # NO 'import': este repositorio no ejecuta cargas contra
            # Enablon (CLAUDE.md).
        })),
        aliases=frozenset(),
        pipeline_factory=_safety_meetings_pipeline_factory,
        supported_modes=frozenset({"sample", "full"}),
        required_artifact_types=frozenset({"sql", "mapping"}),
        optional_artifact_types=frozenset({"operational_csv", "etl", "errors"}),
        description=(
            "Safety Meetings / Group_Meetings -- prototipo de exportación "
            "review_only (7 de 26 columnas del Template real, ver "
            "config/exports/safety_meetings.yaml). Tercer módulo con "
            "pipeline ejecutable del EMF (Sprint 9.7), construido "
            "directamente sobre el Export Engine mínimo (Sprint 9.6), "
            "detenido en SAFETY_MEETINGS_OFFLINE_SAMPLE_READY -- sin "
            "sample real ejecutado todavía. Cubre únicamente el objeto "
            "Group_Meetings -- Update_External_Meeting_Participations "
            "(segundo objeto Enablon real de este módulo) queda fuera de "
            "alcance, registrado como MULTI_OBJECT_GAP."
        ),
        metadata={
            "source_system": "prevencion",
            "prototype_status": "review_only",
            "object_id": SAFETY_MEETINGS_OBJECT_TYPE,
            "multi_object_gap": (
                "Safety Meetings tiene 2 objetos Enablon reales "
                "(Group_Meetings, Update_External_Meeting_Participations); "
                "este módulo solo implementa el primero -- ver "
                "docs/07-developer-guide/safety-meetings-module.md."
            ),
        },
    )


def build_default_module_registry() -> ModuleRegistry:
    """Registro por defecto del EMF: Drills (Sprint 8.6), Bypass (Sprint
    9.4) y Safety Meetings (Sprint 9.7) -- los tres únicos módulos con
    `pipeline_factory` real. Los 5 restantes del Workspace Manifest de
    ejemplo (`moc`, `events`, `ops`, `inspections`, `corrective_actions`)
    NO se registran aquí todavía -- ninguno tiene un `pipeline_factory`
    real (Fase 9 del encargo original de Drills: "no confundir presencia
    en el proyecto con soporte del software"). Su presencia en
    `examples/workspace/workspace.example.yaml` (status=planned) describe
    el ROADMAP del proyecto, no lo que el software sabe ejecutar hoy."""
    registry = ModuleRegistry()
    registry.register(_build_drills_definition())
    registry.register(_build_bypass_definition())
    registry.register(_build_safety_meetings_definition())
    return registry
