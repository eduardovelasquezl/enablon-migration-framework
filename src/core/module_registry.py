"""Module Registry -- registro explícito de módulos migrables ejecutables
del EMF (Sprint 8.6, ver `docs/01-architecture/module-registry.md`).

Responde a "¿qué módulos sabe ejecutar el software, con qué capacidades,
y cómo construyo su pipeline?" -- nunca "¿qué recursos de datos tiene un
proyecto concreto?" (eso es `WorkspaceManifest`) ni "¿dónde está un
artefacto?" (eso es `ResourceResolver`) ni "¿qué etapas de pipeline
existen?" (eso es `StageRegistry`, que sigue registrando *etapas*, nunca
*módulos*). Vive en `src/core/` como infraestructura genérica: ninguna
clase de este fichero importa `src.export`, `src.etl` ni ningún objeto
migrable concreto (verificado por inspección, ver
`tests/test_module_registry.py::test_module_registry_no_importa_drills_ni_export`)
-- quien SÍ conoce Drills es el composition root
(`src/bootstrap/module_registry.py`), nunca este módulo.

Registro explícito, deliberadamente SIN:
- descubrimiento dinámico de carpetas ni `importlib` sobre un paquete;
- reflexión automática ni búsqueda de clases por nombre/convención;
- carga automática de plugins ni entry points.

Un `module_id` se resuelve contra una `ModuleDefinition` solo si alguien
llamó explícitamente a `register()` antes, en código auditable -- mismo
principio ya fijado por `StageRegistry` (`src/core/registry.py`) y por
`extensibility-model.md` § 5 para el futuro `ObjectRegistry` de Sprint
4.1 (este `ModuleRegistry` es, en la práctica, esa pieza ya implementada,
con el vocabulario `module_id` que `WorkspaceManifest` ya usaba desde
Sprint 8.4 -- ver § 10 de `docs/01-architecture/module-registry.md`).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from src.core.contracts import ExecutionContext, ExecutionRequest, PipelineDefinition
from src.core.exceptions import CoreError
from src.core.registry import StageRegistry
from src.core.workspace_manifest import ARTIFACT_KINDS, WorkspaceManifest, WorkspaceManifestError

logger = logging.getLogger(__name__)

SUPPORTED_EXECUTION_MODES = frozenset({"sample", "full"})


class ModuleCapability:
    """Vocabulario cerrado de operaciones que un módulo puede declarar
    como soportadas -- mismo patrón (clase + `frozenset` `ALL`) que
    `ArtifactStatus`/`ModuleStatus` en `workspace_manifest.py`.

    `IMPORT` se declara aquí como capacidad de vocabulario (Fase 3 del
    encargo la pide explícitamente como "futura") pero ningún módulo debe
    marcarla como soportada hoy -- este repositorio no ejecuta cargas
    contra Enablon (CLAUDE.md, restricción no negociable)."""

    EXPORT = "export"
    SAMPLE = "sample"
    FULL = "full"
    EVIDENCE = "evidence"
    COMPARISON = "comparison"
    VALIDATION = "validation"
    MANIFEST_DRIVEN_RESOURCES = "manifest_driven_resources"
    LEGACY_CLI = "legacy_cli"
    CANONICALIZATION = "canonicalization"
    MAPPING = "mapping"
    IMPORT = "import"
    ALL = frozenset({
        EXPORT, SAMPLE, FULL, EVIDENCE, COMPARISON, VALIDATION,
        MANIFEST_DRIVEN_RESOURCES, LEGACY_CLI, CANONICALIZATION, MAPPING, IMPORT,
    })


class ModuleImplementationStatus:
    """Estado de la IMPLEMENTACIÓN en software -- deliberadamente
    distinto de `ModuleStatus` de `workspace_manifest.py` (que describe el
    estado del MÓDULO EN EL PROYECTO: planned/ready/blocked/in_progress/
    validated/deprecated, en función de qué recursos de datos tiene ese
    proyecto concreto). Un módulo puede estar `implemented` en el software
    y `planned` en el proyecto (código lista para ejecutar, datos del
    cliente todavía sin llegar) -- son dos ejes ortogonales, nunca se
    funden en un único vocabulario (ver
    `docs/01-architecture/module-registry.md` § 9)."""

    IMPLEMENTED = "implemented"
    EXPERIMENTAL = "experimental"
    PLANNED = "planned"
    DEPRECATED = "deprecated"
    ALL = frozenset({IMPLEMENTED, EXPERIMENTAL, PLANNED, DEPRECATED})

    #: Estados que requieren una `pipeline_factory` real -- el software
    #: sabe ejecutarlos de verdad, no son solo un anuncio de roadmap.
    EXECUTABLE = frozenset({IMPLEMENTED, EXPERIMENTAL})


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------

class ModuleRegistryError(CoreError):
    """Base común de todas las excepciones de este módulo -- permite un
    `except ModuleRegistryError` genérico, mismo patrón que
    `DataWorkspaceError`/`WorkspaceManifestError`/`ResourceResolutionError`
    ya establecido en el resto del repositorio."""


class UnknownModuleError(ModuleRegistryError):
    """`module_id_or_alias` no está registrado en este `ModuleRegistry`.

    Deliberadamente el mismo nombre que
    `src.core.resource_resolver.UnknownModuleError`, pero una jerarquía
    DISTINTA e independiente (esta hereda de `ModuleRegistryError`, no de
    `ResourceResolutionError`) -- representan preguntas distintas
    ("¿el software sabe ejecutar este módulo?" vs. "¿el manifest de un
    proyecto concreto lo declara?", ver Fase 11 del encargo de este
    sprint: son dos comprobaciones separadas con motivos de fallo
    distintos). Ningún fichero de este repositorio importa ambas bajo el
    mismo nombre sin cualificar el módulo de origen -- ver
    `docs/01-architecture/module-registry.md` § 17."""


class DuplicateModuleError(ModuleRegistryError):
    """Se intentó registrar dos veces el mismo `module_id` sin pedir
    explícitamente sobrescritura (`overwrite=True`) -- mismo criterio que
    `DuplicateStageRegistrationError` de `StageRegistry`."""


class DuplicateModuleAliasError(ModuleRegistryError):
    """Un alias declarado ya está en uso -- por otro alias, por su propio
    `module_id`, o por el `module_id` de otro módulo ya registrado. Los
    alias son únicos GLOBALMENTE (mismo espacio de nombres que
    `module_id`), nunca solo dentro de un módulo."""


class UnsupportedCapabilityError(ModuleRegistryError):
    """La capacidad pedida no pertenece al vocabulario cerrado
    `ModuleCapability.ALL` (petición mal formada), o el módulo no la
    declara como soportada (`ensure_capability`, ver § "capacidad no
    soportada" de la Fase 11 del encargo)."""


class ModuleNotImplementedError(ModuleRegistryError):
    """Se intentó obtener/ejecutar el `pipeline_factory` de un módulo
    cuyo `status` no está en `ModuleImplementationStatus.EXECUTABLE`
    (`planned`, o `deprecated` sin factory real) -- el software no sabe
    ejecutarlo todavía, o ya no debería hacerlo."""


class ModuleDisabledForProjectError(ModuleRegistryError):
    """El módulo es ejecutable por el software (`ModuleRegistry` lo
    conoce), pero el `WorkspaceManifest` del proyecto lo declara
    `enabled: false` -- distinto de `UnknownModuleError` (el software SÍ
    lo conoce) y de `WorkspaceManifestError` (el proyecto SÍ lo declara,
    solo que deshabilitado)."""


class MissingPipelineFactoryError(ModuleRegistryError):
    """Invariante de `ModuleDefinition`: un módulo con `status` ejecutable
    (`implemented`/`experimental`) fue construido sin `pipeline_factory`.
    Nunca debería ocurrir si `register()` se usó correctamente -- señal de
    un error de programación en el composition root, no una condición de
    negocio esperada."""


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModuleCapabilities:
    """Conjunto de capacidades declaradas por un módulo, validado contra
    el vocabulario cerrado `ModuleCapability.ALL`. Nunca se declara una
    capacidad "porque existe un seam/adaptador" -- solo si el
    comportamiento es demostrable hoy (ver `module-registry.md` § 8)."""

    values: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        unknown = self.values - ModuleCapability.ALL
        if unknown:
            raise UnsupportedCapabilityError(
                f"Capacidad(es) fuera del vocabulario cerrado: {sorted(unknown)} "
                f"(válidas: {sorted(ModuleCapability.ALL)})."
            )

    def supports(self, capability: str) -> bool:
        return capability in self.values

    def __contains__(self, capability: str) -> bool:
        return self.supports(capability)

    def __iter__(self):
        return iter(sorted(self.values))


# ---------------------------------------------------------------------------
# ModuleDefinition
# ---------------------------------------------------------------------------

#: Firma de la factory de pipeline que un módulo registra. Recibe la
#: petición de ejecución y un `StageRegistry` recién creado por quien
#: orquesta (mismo contrato que `StageRegistry` ya exige: "quien orquesta
#: una ejecución crea su propio StageRegistry"); la factory registra sus
#: propias etapas en él y devuelve la `PipelineDefinition` + el
#: `ExecutionContext` listos para `PipelineOrchestrator.run()`. No incluye
#: `WorkspaceManifest`/`ResourceResolver` porque ningún módulo real los
#: necesita inyectados hoy (Drills los resuelve internamente cuando le
#: hacen falta, ver `resource-resolver.md` § 15) -- ampliar la firma es
#: una extensión aditiva cuando exista un segundo caso real que lo pida
#: (mismo principio "No Abstraction Without a Real Consumer" ya aplicado
#: en `resource_resolver.py`).
PipelineFactory = Callable[[ExecutionRequest, StageRegistry], "tuple[PipelineDefinition, ExecutionContext]"]


@dataclass(frozen=True)
class ModuleDefinition:
    """Definición tipada y auditable de un módulo migrable ejecutable.

    Nunca contiene credenciales, rutas físicas, contenido de mappings,
    `DataFrame`s, conexiones SQL ni datos de cliente -- solo metadatos
    declarativos sobre QUÉ sabe ejecutar el software y CÓMO construir su
    pipeline (la factory), nunca el resultado de ejecutarlo."""

    module_id: str
    display_name: str
    version: str
    status: str
    capabilities: ModuleCapabilities
    canonical_name: str | None = None
    aliases: frozenset[str] = field(default_factory=frozenset)
    pipeline_factory: PipelineFactory | None = None
    supported_modes: frozenset[str] = field(default_factory=frozenset)
    required_artifact_types: frozenset[str] = field(default_factory=frozenset)
    optional_artifact_types: frozenset[str] = field(default_factory=frozenset)
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ModuleRegistryError("ModuleDefinition.module_id no puede estar vacío.")
        if self.status not in ModuleImplementationStatus.ALL:
            raise ModuleRegistryError(
                f"ModuleDefinition[{self.module_id}].status={self.status!r} no es válido "
                f"(vocabulario cerrado: {sorted(ModuleImplementationStatus.ALL)})."
            )
        if self.module_id in self.aliases:
            raise ModuleRegistryError(
                f"ModuleDefinition[{self.module_id}]: module_id no puede aparecer también "
                "en sus propios aliases."
            )
        unsupported_modes = self.supported_modes - SUPPORTED_EXECUTION_MODES
        if unsupported_modes:
            raise ModuleRegistryError(
                f"ModuleDefinition[{self.module_id}].supported_modes declara modo(s) "
                f"desconocido(s): {sorted(unsupported_modes)} (válidos: {sorted(SUPPORTED_EXECUTION_MODES)})."
            )
        for field_name, kinds in (
            ("required_artifact_types", self.required_artifact_types),
            ("optional_artifact_types", self.optional_artifact_types),
        ):
            unknown_kinds = kinds - ARTIFACT_KINDS
            if unknown_kinds:
                raise ModuleRegistryError(
                    f"ModuleDefinition[{self.module_id}].{field_name} declara kind(s) de "
                    f"artefacto fuera del vocabulario de WorkspaceManifest: {sorted(unknown_kinds)}."
                )
        overlap = self.required_artifact_types & self.optional_artifact_types
        if overlap:
            raise ModuleRegistryError(
                f"ModuleDefinition[{self.module_id}]: {sorted(overlap)} declarado a la vez "
                "en required_artifact_types y optional_artifact_types -- ambiguo."
            )

        if self.status in ModuleImplementationStatus.EXECUTABLE and self.pipeline_factory is None:
            raise MissingPipelineFactoryError(
                f"ModuleDefinition[{self.module_id}]: status={self.status!r} exige un "
                "pipeline_factory real -- no puede registrarse como ejecutable sin él."
            )
        if self.status == ModuleImplementationStatus.PLANNED and self.pipeline_factory is not None:
            raise ModuleRegistryError(
                f"ModuleDefinition[{self.module_id}]: status=planned no debe declarar "
                "pipeline_factory -- todavía no es una implementación real (Fase 9 del encargo)."
            )

    def supports(self, capability: str) -> bool:
        return self.capabilities.supports(capability)

    @property
    def is_executable(self) -> bool:
        return self.status in ModuleImplementationStatus.EXECUTABLE and self.pipeline_factory is not None


# ---------------------------------------------------------------------------
# ModuleRegistry
# ---------------------------------------------------------------------------

class ModuleRegistry:
    """Instancia explícita, nunca un registro global de módulo (ADR-010,
    No Hidden State) -- mismo criterio que `StageRegistry`: quien
    construye un `ModuleRegistry` decide qué registrar en él."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleDefinition] = {}
        self._alias_to_module_id: dict[str, str] = {}
        self._canonical_names: dict[str, str] = {}

    def register(self, definition: ModuleDefinition, *, overwrite: bool = False) -> None:
        module_id = definition.module_id

        if not overwrite and module_id in self._modules:
            raise DuplicateModuleError(
                f"El módulo {module_id!r} ya está registrado -- usa overwrite=True si el "
                "reemplazo es intencional (p. ej. en un test)."
            )
        if not overwrite and module_id in self._alias_to_module_id:
            raise DuplicateModuleAliasError(
                f"module_id={module_id!r} ya está en uso como alias de "
                f"{self._alias_to_module_id[module_id]!r}."
            )

        for alias in definition.aliases:
            existing_owner = self._alias_to_module_id.get(alias)
            if not overwrite:
                if existing_owner is not None and existing_owner != module_id:
                    raise DuplicateModuleAliasError(
                        f"alias={alias!r} ya apunta al módulo {existing_owner!r}, no se puede "
                        f"reasignar a {module_id!r}."
                    )
                if alias in self._modules and alias != module_id:
                    raise DuplicateModuleAliasError(
                        f"alias={alias!r} colisiona con el module_id de otro módulo ya registrado."
                    )

        if definition.canonical_name is not None:
            other = self._canonical_names.get(definition.canonical_name)
            if not overwrite and other is not None and other != module_id:
                raise ModuleRegistryError(
                    f"canonical_name={definition.canonical_name!r} ya está en uso por el "
                    f"módulo {other!r}."
                )

        if overwrite:
            self._unregister_aliases_of(module_id)

        self._modules[module_id] = definition
        for alias in definition.aliases:
            self._alias_to_module_id[alias] = module_id
        if definition.canonical_name is not None:
            self._canonical_names[definition.canonical_name] = module_id

    def _unregister_aliases_of(self, module_id: str) -> None:
        stale = [alias for alias, owner in self._alias_to_module_id.items() if owner == module_id]
        for alias in stale:
            del self._alias_to_module_id[alias]

    def _resolve_module_id(self, module_id_or_alias: str) -> str:
        if module_id_or_alias in self._modules:
            return module_id_or_alias
        if module_id_or_alias in self._alias_to_module_id:
            return self._alias_to_module_id[module_id_or_alias]
        raise UnknownModuleError(
            f"Módulo no registrado en el ModuleRegistry: {module_id_or_alias!r} "
            f"(disponibles: {self.list_modules()})."
        )

    def get(self, module_id_or_alias: str) -> ModuleDefinition:
        module_id = self._resolve_module_id(module_id_or_alias)
        definition = self._modules[module_id]
        if definition.status == ModuleImplementationStatus.DEPRECATED:
            logger.warning(
                "Resolviendo módulo deprecated %r (%s) -- considerar su reemplazo.",
                module_id, definition.display_name,
            )
        return definition

    def contains(self, module_id_or_alias: str) -> bool:
        return module_id_or_alias in self._modules or module_id_or_alias in self._alias_to_module_id

    def list_modules(self) -> tuple[str, ...]:
        return tuple(sorted(self._modules))

    def list_executable(self) -> tuple[str, ...]:
        """Módulos con `status` en `ModuleImplementationStatus.EXECUTABLE`
        (`implemented`/`experimental`) Y `pipeline_factory` real -- no
        literalmente solo `status == "implemented"` (ver
        `ModuleImplementationStatus.EXECUTABLE`)."""
        return tuple(
            module_id for module_id in self.list_modules()
            if self._modules[module_id].is_executable
        )

    def capabilities(self, module_id_or_alias: str) -> ModuleCapabilities:
        return self.get(module_id_or_alias).capabilities

    def supports(self, module_id_or_alias: str, capability: str) -> bool:
        if capability not in ModuleCapability.ALL:
            raise UnsupportedCapabilityError(
                f"capability={capability!r} no pertenece al vocabulario cerrado "
                f"(válidas: {sorted(ModuleCapability.ALL)})."
            )
        return self.get(module_id_or_alias).supports(capability)

    def ensure_capability(self, module_id_or_alias: str, capability: str) -> ModuleDefinition:
        """Igual que `supports()`, pero lanza `UnsupportedCapabilityError`
        si el módulo NO la soporta -- pensado para código de integración
        (CLI, composition root) que necesita un fallo bloqueante, no una
        consulta booleana silenciosa."""
        definition = self.get(module_id_or_alias)
        if not self.supports(module_id_or_alias, capability):
            raise UnsupportedCapabilityError(
                f"El módulo {definition.module_id!r} no soporta la capacidad {capability!r} "
                f"(soportadas: {sorted(definition.capabilities.values)})."
            )
        return definition

    def get_pipeline_factory(self, module_id_or_alias: str) -> PipelineFactory:
        """Devuelve la `pipeline_factory` de un módulo -- NUNCA la
        ejecuta (Fase 14 del encargo: "factory no ejecutada durante
        consulta"). Lanza `ModuleNotImplementedError` si el módulo no es
        ejecutable hoy (`planned`, o `deprecated` sin factory real)."""
        definition = self.get(module_id_or_alias)
        if not definition.is_executable:
            raise ModuleNotImplementedError(
                f"El módulo {definition.module_id!r} no es ejecutable hoy "
                f"(status={definition.status!r}) -- no tiene una implementación real."
            )
        assert definition.pipeline_factory is not None  # garantizado por is_executable
        return definition.pipeline_factory


# ---------------------------------------------------------------------------
# Integración con WorkspaceManifest (Fase 11) -- compone, no duplica
# ---------------------------------------------------------------------------

def ensure_module_runnable(
    registry: ModuleRegistry,
    module_id_or_alias: str,
    *,
    manifest: WorkspaceManifest | None = None,
    capability: str | None = None,
) -> ModuleDefinition:
    """Comprobación compuesta, en el orden que pide la Fase 11 del
    encargo, antes de ejecutar un módulo de forma genérica:

    1. ¿El software conoce el módulo? -- `ModuleRegistry.get()`
       (`UnknownModuleError` si no).
    2. Si se pasa `manifest`: ¿el proyecto lo declara? --
       `WorkspaceManifest.get_module()` (`WorkspaceManifestError` si no,
       reutilizado tal cual -- no se inventa un error nuevo para lo mismo).
    3. Si se pasa `manifest`: ¿está habilitado en ese proyecto? --
       `ModuleDisabledForProjectError` si `enabled=False`.
    4. Si se pasa `capability`: ¿la implementación la soporta? --
       `ModuleRegistry.ensure_capability()` (`UnsupportedCapabilityError`
       si no).

    Nunca comprueba existencia física de recursos -- eso es
    `ResourceResolver`, una responsabilidad distinta (Fase 10 de
    `resource-resolver.md`), fuera del alcance de esta función."""
    definition = registry.get(module_id_or_alias)

    if manifest is not None:
        try:
            module_spec = manifest.get_module(definition.module_id)
        except WorkspaceManifestError:
            raise
        if not module_spec.enabled:
            raise ModuleDisabledForProjectError(
                f"El módulo {definition.module_id!r} está deshabilitado "
                f"(enabled=false) en el manifest del proyecto {manifest.project.id!r}."
            )

    if capability is not None:
        registry.ensure_capability(definition.module_id, capability)

    return definition
