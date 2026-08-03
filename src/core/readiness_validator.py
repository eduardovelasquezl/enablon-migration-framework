"""Workspace Readiness Validator -- comprobación compuesta de preparación
operativa (Sprint 8.7, ver
`docs/01-architecture/workspace-readiness-validator.md`).

Responde a "¿puede empezar esta operación (sample/full/comparison/evidence/
validation/export) para este módulo, en este proyecto, con estos datos?" --
nunca "¿cómo salió la migración?" (los estados `READY`/`READY_WITH_WARNINGS`/
`BLOCKED` describen preparación PREVIA, nunca el resultado de una
ejecución).

Compone, sin duplicar, las tres capas ya existentes -- mismo principio ya
aplicado por `ResourceResolver` sobre `WorkspaceManifest`/`DataWorkspace`:

- `ModuleRegistry` -- ¿el SOFTWARE sabe ejecutar este módulo, con qué
  capacidades? (`src/core/module_registry.py`)
- `WorkspaceManifest` -- ¿este PROYECTO lo declara, está habilitado, qué
  artefactos son obligatorios para cada operación?
  (`src/core/workspace_manifest.py`, campos
  `required_for_sample/full/comparison` -- Fase 1 de este sprint confirmó que
  son la única fuente con granularidad por operación, y que hoy no los
  aplica nadie; este módulo es quien por fin los aplica).
- `ResourceResolver` -- ¿ese artefacto resuelve, existe físicamente si se
  pide? (`src/core/resource_resolver.py`)

Vive en `src/core/` como infraestructura genérica: ninguna clase de este
fichero conoce Drills ni ningún otro objeto migrable concreto -- verificable
por inspección (`tests/test_readiness_validator.py::
test_readiness_validator_no_importa_drills_ni_export`), mismo criterio que
`module_registry.py`/`workspace_manifest.py`/`resource_resolver.py`.

Garantías deliberadas:
- Nunca abre SQL, nunca llama a `sql_execution_guard.grant()`/`revoke()` --
  solo LEE `current_authorization()` para anotar una nota informativa.
- Nunca crea directorios ni archivos, nunca lee el contenido de ningún
  recurso -- delega toda existencia física a `ResourceResolver`, que ya
  garantiza esas mismas propiedades.
- `ResourceResolver.resolve()` se llama siempre con `required=False`: este
  módulo decide la severidad (BLOCKER/WARNING/INFO) él mismo a partir de
  `ArtifactStatus`, nunca deja que una excepción del resolver decida por él
  -- evita el caso real detectado en la Fase 1 de este sprint (un artefacto
  `status=present`, `path=None`, resuelto vía `source: "git:..."` como
  `sql`/`mapping` de Drills, haría que `required=True` lanzara
  `ArtifactMissingError` de forma incorrecta).
- `ArtifactSpec.required_for_sample/required_for_full/required_for_comparison`
  es la ÚNICA fuente de qué artefactos bloquean cada operación --
  `ModuleDefinition.required_artifact_types` (nivel software, sin
  granularidad de operación) se usa solo como señal de alerta no
  bloqueante (`ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`), nunca como una
  segunda fuente de verdad paralela (Fase 1/6 de este sprint: dos
  mecanismos ya existían sin relación programática entre ellos -- este
  módulo fija la precedencia en vez de fundirlos).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from src.config import PROJECT_ROOT
from src.core.exceptions import CoreError
from src.core.module_registry import (
    ModuleCapability,
    ModuleDefinition,
    ModuleDisabledForProjectError,
    ModuleRegistry,
    UnknownModuleError as ModuleRegistryUnknownModuleError,
    ensure_module_runnable,
)
from src.core.resource_resolver import (
    ResolvedResource,
    ResourceRequest,
    ResourceResolutionError,
    ResourceResolver,
)
from src.core.workspace_manifest import (
    ArtifactSpec,
    ArtifactStatus,
    ModuleSpec,
    WorkspaceManifest,
    WorkspaceManifestError,
)
from src.db import sql_execution_guard

# ---------------------------------------------------------------------------
# Vocabularios cerrados
# ---------------------------------------------------------------------------


class ReadinessOperation:
    """Vocabulario cerrado de operaciones evaluables -- "lo que se quiere
    preparar o ejecutar", distinto de `ModuleCapability` ("lo que el
    software puede hacer", ver `module_registry.py`). Una operación puede
    requerir varias capacidades a la vez (p. ej. `sample` requiere
    `EXPORT`+`SAMPLE`+`VALIDATION`, ver `_OPERATION_CAPABILITIES`)."""

    SAMPLE = "sample"
    FULL = "full"
    COMPARISON = "comparison"
    EVIDENCE = "evidence"
    VALIDATION = "validation"
    EXPORT = "export"
    ALL = frozenset({SAMPLE, FULL, COMPARISON, EVIDENCE, VALIDATION, EXPORT})

    #: Subconjunto que además es un `mode` de `ModuleDefinition.supported_modes`
    #: (mismo vocabulario que `SUPPORTED_EXECUTION_MODES` en module_registry.py).
    MODES = frozenset({SAMPLE, FULL})


class ReadinessStatus:
    """Estado final de preparación -- nunca describe el resultado de una
    migración, solo si puede EMPEZAR."""

    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    BLOCKED = "blocked"
    ALL = frozenset({READY, READY_WITH_WARNINGS, BLOCKED})


class ReadinessSeverity:
    """Severidad de un `ReadinessIssue` -- solo `BLOCKER` cambia el estado
    final a `BLOCKED`; `WARNING` lo baja a `READY_WITH_WARNINGS` (o a
    `BLOCKED` si `ReadinessRequest.strict=True`); `INFO` nunca afecta al
    estado."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"
    ALL = frozenset({BLOCKER, WARNING, INFO})


# Qué capacidades (`ModuleCapability`) exige cada operación -- todas deben
# estar soportadas por el módulo para que la operación se considere
# soportada por el software. Deliberadamente estático y cerrado (Fase 3 del
# encargo: "no crear operaciones redundantes con ModuleCapability sin
# justificarlo") -- no se lee de `ModuleDefinition.metadata` ni de ningún
# YAML: es la misma relación conceptual para cualquier módulo futuro, no un
# dato del proyecto.
_OPERATION_CAPABILITIES: Mapping[str, frozenset[str]] = {
    ReadinessOperation.SAMPLE: frozenset(
        {ModuleCapability.EXPORT, ModuleCapability.SAMPLE, ModuleCapability.VALIDATION}
    ),
    ReadinessOperation.FULL: frozenset(
        {ModuleCapability.EXPORT, ModuleCapability.FULL, ModuleCapability.VALIDATION}
    ),
    ReadinessOperation.COMPARISON: frozenset({ModuleCapability.COMPARISON}),
    ReadinessOperation.EVIDENCE: frozenset({ModuleCapability.EVIDENCE}),
    ReadinessOperation.VALIDATION: frozenset({ModuleCapability.VALIDATION}),
    ReadinessOperation.EXPORT: frozenset({ModuleCapability.EXPORT}),
}

# Qué atributo booleano de `ArtifactSpec` gobierna "obligatorio para esta
# operación" -- `None` significa "esta operación no tiene artefactos
# obligatorios a nivel de manifest" (evidence lee un run_dir ya completado,
# nunca artefactos declarados; export es agnóstico de modo). `comparison`
# no aparece aquí -- su artefacto obligatorio es `contracts.project_artifact`
# (ver `_required_kinds_for_comparison`), no un `required_for_*` fijo, para
# no asumir que siempre es `operational_csv` (Core genérico, Fase 4 del
# encargo). `validation` reutiliza `required_for_sample` -- no existe un
# flag propio en el manifest y el informe de validación se produce como
# parte de un sample/full real, nunca de forma aislada (ver
# docs/01-architecture/workspace-readiness-validator.md § 11).
_ARTIFACT_FLAG_FOR_OPERATION: Mapping[str, str | None] = {
    ReadinessOperation.SAMPLE: "required_for_sample",
    ReadinessOperation.FULL: "required_for_full",
    ReadinessOperation.VALIDATION: "required_for_sample",
    ReadinessOperation.COMPARISON: None,
    ReadinessOperation.EVIDENCE: None,
    ReadinessOperation.EXPORT: None,
}


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class ReadinessValidatorError(CoreError):
    """Base común de las excepciones técnicas de este módulo -- reservada a
    errores de configuración de la propia petición (nunca a hallazgos de
    negocio esperados, que se representan como `ReadinessIssue`, nunca como
    excepción)."""


class UnknownReadinessOperationError(ReadinessValidatorError):
    """`ReadinessRequest.operation` no pertenece al vocabulario cerrado
    `ReadinessOperation.ALL`."""


class ReadinessRequestError(ReadinessValidatorError):
    """La propia petición es inconsistente (p. ej. `project_id` no coincide
    con el proyecto del `WorkspaceManifest` pasado) -- error de quien
    construye la petición, no una condición de negocio evaluable."""


# ---------------------------------------------------------------------------
# Modelo: petición / resultado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadinessIssue:
    """Un hallazgo individual de preparación. Nunca se usa una excepción
    para representar esto -- mismo patrón que `validate_manifest()`
    (`workspace_manifest.py`): una lista de hallazgos, nunca un fallo que
    interrumpe la evaluación."""

    code: str
    severity: str
    message: str
    project_id: str
    module_id: str
    operation: str
    artifact_type: str | None = None
    declared_path: str | None = None
    required: bool = False
    source_component: str = ""
    remediation: str = ""
    reference: str | None = None

    def __post_init__(self) -> None:
        if self.severity not in ReadinessSeverity.ALL:
            raise ReadinessValidatorError(
                f"ReadinessIssue.severity={self.severity!r} no es válido "
                f"(vocabulario cerrado: {sorted(ReadinessSeverity.ALL)})."
            )

    @property
    def dedup_key(self) -> tuple[str, str | None]:
        return (self.code, self.artifact_type)


@dataclass(frozen=True)
class ReadinessRequest:
    """Qué se quiere evaluar y con qué condiciones. Deliberadamente sin
    credenciales, conexiones, DataFrames, contenido de archivo ni filas
    SQL -- solo coordenadas declarativas hacia los tres componentes que ya
    conocen esos datos (`manifest`, `registry`, `resolver`)."""

    project_id: str
    module_id: str
    operation: str
    manifest: WorkspaceManifest
    registry: ModuleRegistry
    resolver: ResourceResolver
    require_physical_files: bool = False
    mode: str | None = None
    strict: bool = False


@dataclass(frozen=True)
class ReadinessAssessment:
    """Resultado agregado de una evaluación de preparación. Serializable
    (JSON/YAML) sin exponer nunca contenido de datos, connection strings ni
    secretos -- solo metadatos declarativos y rutas locales, mismo criterio
    que `ResolvedResource`."""

    assessment_id: str
    timestamp: datetime
    project_id: str
    module_id: str
    operation: str
    status: str
    checks: tuple[str, ...]
    issues: tuple[ReadinessIssue, ...]
    blockers: tuple[ReadinessIssue, ...]
    warnings: tuple[ReadinessIssue, ...]
    informational: tuple[ReadinessIssue, ...]
    required_artifacts: tuple[str, ...]
    optional_artifacts: tuple[str, ...]
    resolved_resources: tuple[ResolvedResource, ...]
    missing_resources: tuple[str, ...]
    generated_resources: tuple[str, ...]
    summary: str
    recommended_next_action: str


# ---------------------------------------------------------------------------
# Contexto interno compartido entre checks
# ---------------------------------------------------------------------------


class _CheckContext:
    """Estado mutable compartido entre checks durante una única evaluación
    -- nunca sobrevive más allá de una llamada a `WorkspaceReadinessValidator
    .assess()`, nunca se comparte entre evaluaciones (sin estado oculto,
    ADR-010)."""

    def __init__(
        self,
        request: ReadinessRequest,
        module_def: ModuleDefinition,
        module_spec: ModuleSpec,
    ) -> None:
        self.request = request
        self.module_def = module_def
        self.module_spec = module_spec
        self.required_kinds: frozenset[str] = frozenset()
        self.optional_kinds: frozenset[str] = frozenset()
        self.resolved: dict[str, ResolvedResource] = {}


def _artifact_required_kinds(ctx: _CheckContext) -> frozenset[str]:
    operation = ctx.request.operation
    if operation == ReadinessOperation.COMPARISON:
        contracts = ctx.module_spec.contracts
        if contracts is None or contracts.project_artifact is None:
            return frozenset()
        return frozenset({contracts.project_artifact})

    flag_name = _ARTIFACT_FLAG_FOR_OPERATION.get(operation)
    if flag_name is None:
        return frozenset()
    return frozenset(
        kind
        for kind, artifact in ctx.module_spec.artifacts.items()
        if getattr(artifact, flag_name)
    )


# ---------------------------------------------------------------------------
# Checks (Fase 5 -- orden fijo, Fase 7)
# ---------------------------------------------------------------------------


class CapabilityCheck:
    """¿La operación está soportada por el software? -- capacidades
    (`ModuleCapability`) + modo (`supported_modes`, solo para
    sample/full). "full no admitido si el módulo no lo declara" se cubre
    aquí, no reinventando un vocabulario nuevo."""

    name = "CapabilityCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        issues: list[ReadinessIssue] = []
        required_capabilities = _OPERATION_CAPABILITIES.get(request.operation, frozenset())
        for capability in sorted(required_capabilities):
            if not ctx.module_def.supports(capability):
                issues.append(
                    ReadinessIssue(
                        code="CAPABILITY_UNSUPPORTED",
                        severity=ReadinessSeverity.BLOCKER,
                        message=(
                            f"El módulo {ctx.module_def.module_id!r} no declara la "
                            f"capacidad {capability!r}, requerida para la operación "
                            f"{request.operation!r}."
                        ),
                        project_id=request.project_id,
                        module_id=ctx.module_def.module_id,
                        operation=request.operation,
                        source_component="ModuleRegistry",
                        remediation=(
                            "Esta capacidad no está implementada por el software para "
                            "este módulo -- no es un problema de datos del proyecto."
                        ),
                    )
                )
        if request.operation in ReadinessOperation.MODES and request.operation not in ctx.module_def.supported_modes:
            issues.append(
                ReadinessIssue(
                    code="MODE_UNSUPPORTED",
                    severity=ReadinessSeverity.BLOCKER,
                    message=(
                        f"El módulo {ctx.module_def.module_id!r} no declara el modo "
                        f"{request.operation!r} en supported_modes."
                    ),
                    project_id=request.project_id,
                    module_id=ctx.module_def.module_id,
                    operation=request.operation,
                    source_component="ModuleRegistry",
                    remediation="Ver 'python main.py modules show <modulo>' -- supported_modes.",
                )
            )
        return issues


class ArtifactDeclarationCheck:
    """Calcula qué kinds son obligatorios/opcionales para esta operación.

    No comprueba "obligatorio pero no declarado en absoluto": por
    construcción, `required_for_sample/full` vive DENTRO de un
    `ArtifactSpec` ya declarado, y `contracts.project_artifact` (fuente de
    lo obligatorio para `comparison`) ya está validado como declarado por
    `ModuleSpec.__post_init__` al cargar el manifest -- ese estado no es
    alcanzable en runtime, así que este check no reimplementa una
    comprobación que el esquema ya garantiza (mismo principio del resto del
    repositorio: no validar condiciones que no pueden ocurrir)."""

    name = "ArtifactDeclarationCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        ctx.required_kinds = _artifact_required_kinds(ctx)
        ctx.optional_kinds = frozenset(ctx.module_spec.artifacts) - ctx.required_kinds

        issues: list[ReadinessIssue] = []
        # Señal de alerta no bloqueante (Fase 1/6): el software declara este
        # kind como necesario a nivel general, pero el proyecto no lo marca
        # obligatorio para NINGUNA operación conocida hoy en su manifest.
        if request.operation in (ReadinessOperation.SAMPLE, ReadinessOperation.FULL):
            for kind in sorted(ctx.module_def.required_artifact_types):
                if kind not in ctx.module_spec.artifacts:
                    issues.append(
                        ReadinessIssue(
                            code="ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED",
                            severity=ReadinessSeverity.WARNING,
                            message=(
                                f"El software declara {kind!r} como required_artifact_types "
                                f"de {ctx.module_def.module_id!r}, pero el manifest del "
                                "proyecto no lo declara en absoluto."
                            ),
                            project_id=request.project_id,
                            module_id=ctx.module_def.module_id,
                            operation=request.operation,
                            artifact_type=kind,
                            required=False,
                            source_component="ModuleRegistry",
                            remediation=(
                                "Revisar si el manifest del proyecto debería declarar "
                                f"este artefacto (ver 'modules show {ctx.module_def.module_id}')."
                            ),
                        )
                    )
        return issues


class ArtifactStatusCheck:
    """Interpreta `ArtifactSpec.status` para cada artefacto declarado --
    missing/present/validated/optional/deprecated/not_applicable -- y
    decide severidad. Nunca llama a `ResourceResolver` (eso es
    `ResourceResolutionCheck`)."""

    name = "ArtifactStatusCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        issues: list[ReadinessIssue] = []

        for kind in sorted(ctx.required_kinds):
            artifact = ctx.module_spec.artifact(kind)
            if artifact is None:
                continue  # ya reportado por ArtifactDeclarationCheck
            issues.extend(self._evaluate_required(ctx, kind, artifact))

        for kind in sorted(ctx.optional_kinds):
            artifact = ctx.module_spec.artifact(kind)
            if artifact is None:
                continue
            issues.extend(self._evaluate_optional(ctx, kind, artifact))

        return issues

    def _evaluate_required(
        self, ctx: _CheckContext, kind: str, artifact: ArtifactSpec
    ) -> list[ReadinessIssue]:
        request = ctx.request
        base = dict(
            project_id=request.project_id,
            module_id=ctx.module_def.module_id,
            operation=request.operation,
            artifact_type=kind,
            declared_path=artifact.path,
            required=True,
            source_component="WorkspaceManifest",
        )
        if artifact.status == ArtifactStatus.NOT_APPLICABLE:
            return [
                ReadinessIssue(
                    code="ARTIFACT_NOT_APPLICABLE_BUT_REQUIRED",
                    severity=ReadinessSeverity.BLOCKER,
                    message=(
                        f"{kind!r} es obligatorio para {request.operation!r}, pero el "
                        "manifest lo declara status=not_applicable."
                    ),
                    remediation="Revisar la declaración -- un artefacto obligatorio no puede ser not_applicable.",
                    **base,
                )
            ]
        if artifact.status == ArtifactStatus.MISSING:
            return [
                ReadinessIssue(
                    code="ARTIFACT_MISSING",
                    severity=ReadinessSeverity.BLOCKER,
                    message=f"{kind!r} es obligatorio para {request.operation!r} y el manifest lo declara status=missing.",
                    remediation=f"Completar el artefacto '{kind}' (path + status) en el manifest.",
                    **base,
                )
            ]
        if artifact.status == ArtifactStatus.OPTIONAL:
            return [
                ReadinessIssue(
                    code="ARTIFACT_OPTIONAL_DESPITE_REQUIRED",
                    severity=ReadinessSeverity.WARNING,
                    message=(
                        f"{kind!r} está marcado required_for_{request.operation}, pero "
                        "status=optional -- se trata como advertencia, nunca bloqueante "
                        "(mismo criterio que ResourceResolver)."
                    ),
                    remediation="Alinear required_for_* y status en el manifest si la discrepancia no es intencional.",
                    **base,
                )
            ]
        if artifact.status == ArtifactStatus.DEPRECATED:
            return [
                ReadinessIssue(
                    code="ARTIFACT_DEPRECATED",
                    severity=ReadinessSeverity.WARNING,
                    message=f"{kind!r} es obligatorio para {request.operation!r} y está marcado status=deprecated.",
                    remediation="Actualizar el manifest para apuntar al artefacto de reemplazo.",
                    **base,
                )
            ]
        # PRESENT / VALIDATED
        if artifact.path is None:
            return [
                ReadinessIssue(
                    code="ARTIFACT_PRESENT_NOT_PATH_RESOLVABLE",
                    severity=ReadinessSeverity.INFO,
                    message=(
                        f"{kind!r} está declarado status={artifact.status} sin 'path' "
                        f"(source={artifact.source!r}) -- existencia no comprobable "
                        "físicamente por este validador, se acepta la declaración tal cual."
                    ),
                    **base,
                )
            ]
        return []

    def _evaluate_optional(
        self, ctx: _CheckContext, kind: str, artifact: ArtifactSpec
    ) -> list[ReadinessIssue]:
        request = ctx.request
        base = dict(
            project_id=request.project_id,
            module_id=ctx.module_def.module_id,
            operation=request.operation,
            artifact_type=kind,
            declared_path=artifact.path,
            required=False,
            source_component="WorkspaceManifest",
        )
        if artifact.status == ArtifactStatus.MISSING:
            return [
                ReadinessIssue(
                    code="ARTIFACT_OPTIONAL_MISSING",
                    severity=ReadinessSeverity.WARNING,
                    message=f"{kind!r} no es obligatorio para {request.operation!r} y está ausente (status=missing).",
                    remediation="No bloquea -- completar si se dispone del artefacto.",
                    **base,
                )
            ]
        if artifact.status == ArtifactStatus.NOT_APPLICABLE:
            return [
                ReadinessIssue(
                    code="ARTIFACT_NOT_APPLICABLE_INFO",
                    severity=ReadinessSeverity.INFO,
                    message=f"{kind!r} no aplica a este módulo/proyecto ({artifact.description or 'sin descripción'}).",
                    **base,
                )
            ]
        return []


class ResourceResolutionCheck:
    """Resuelve (nunca ejecuta acciones de negocio) cada artefacto
    declarado -- required u optional -- vía `ResourceResolver`, siempre con
    `required=False` (la severidad la decide este módulo, no el resolver).
    Nunca usa glob ni fallback -- delega esa garantía íntegramente al
    resolver."""

    name = "ResourceResolutionCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        issues: list[ReadinessIssue] = []
        candidate_kinds = sorted(ctx.required_kinds | ctx.optional_kinds)

        for kind in candidate_kinds:
            artifact = ctx.module_spec.artifact(kind)
            if artifact is None:
                continue
            if artifact.status == ArtifactStatus.NOT_APPLICABLE:
                continue  # el resolver siempre lanza para not_applicable; ya reportado
            if artifact.path is None:
                continue  # nada que resolver (git-tracked / no declarado todavía)

            resource_request = ResourceRequest(
                module_id=ctx.module_def.module_id,
                artifact_type=kind,
                project_id=request.project_id,
                required=False,
                require_physical_file=request.require_physical_files,
                allow_deprecated=True,
            )
            try:
                resolved = request.resolver.resolve(resource_request)
            except ResourceResolutionError as exc:
                issues.append(
                    ReadinessIssue(
                        code="RESOURCE_RESOLUTION_ERROR",
                        severity=ReadinessSeverity.BLOCKER,
                        message=f"{kind!r}: error resolviendo el recurso ({type(exc).__name__}): {exc}",
                        project_id=request.project_id,
                        module_id=ctx.module_def.module_id,
                        operation=request.operation,
                        artifact_type=kind,
                        declared_path=artifact.path,
                        required=kind in ctx.required_kinds,
                        source_component="ResourceResolver",
                        remediation="Revisar la ruta declarada y la configuración del DataWorkspace.",
                    )
                )
                continue
            ctx.resolved[kind] = resolved
        return issues


class PhysicalExistenceCheck:
    """Interpreta `ResolvedResource.exists` -- solo tiene efecto cuando
    `require_physical_files=True` (si no, no hace nada: la comprobación de
    existencia física es explícita y opcional, igual que en
    `ResourceResolver`)."""

    name = "PhysicalExistenceCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        if not request.require_physical_files:
            return []

        issues: list[ReadinessIssue] = []
        for kind, resolved in ctx.resolved.items():
            if resolved.exists is not False:
                continue
            required = kind in ctx.required_kinds
            base = dict(
                project_id=request.project_id,
                module_id=ctx.module_def.module_id,
                operation=request.operation,
                artifact_type=kind,
                declared_path=resolved.declared_path,
                required=required,
                source_component="ResourceResolver",
            )
            if resolved.generated:
                issues.append(
                    ReadinessIssue(
                        code="GENERATED_RESOURCE_NOT_YET_PRESENT",
                        severity=ReadinessSeverity.INFO,
                        message=f"{kind!r} es un recurso generado por el EMF -- normal que no exista todavía antes de ejecutar.",
                        **base,
                    )
                )
            elif not required or resolved.artifact_status == ArtifactStatus.OPTIONAL:
                issues.append(
                    ReadinessIssue(
                        code="PHYSICAL_FILE_MISSING_OPTIONAL",
                        severity=ReadinessSeverity.WARNING,
                        message=f"{kind!r} no existe físicamente en {resolved.resolved_path} (no obligatorio).",
                        remediation="No bloquea -- completar si se dispone del archivo.",
                        **base,
                    )
                )
            else:
                issues.append(
                    ReadinessIssue(
                        code="PHYSICAL_FILE_MISSING",
                        severity=ReadinessSeverity.BLOCKER,
                        message=f"{kind!r} es obligatorio para {request.operation!r} y no existe físicamente en {resolved.resolved_path}.",
                        remediation="Copiar/generar el archivo en la ruta declarada del workspace externo.",
                        **base,
                    )
                )
        return issues


class ContractCheck:
    """Coherencia de `ContractsSpec` con la operación pedida --
    `comparison` exige `contracts.project_artifact` declarado (Platform/
    Project/EMF Contract, ver `project-contract-model.md`); nunca asume que
    el artefacto de comparación se llama `operational_csv`."""

    name = "ContractCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        issues: list[ReadinessIssue] = []
        contracts = ctx.module_spec.contracts

        if request.operation == ReadinessOperation.COMPARISON:
            if contracts is None or contracts.project_artifact is None:
                issues.append(
                    ReadinessIssue(
                        code="PROJECT_CONTRACT_MISSING",
                        severity=ReadinessSeverity.BLOCKER,
                        message=(
                            f"El módulo {ctx.module_spec.module_id!r} no declara "
                            "contracts.project.artifact -- no hay Project Contract "
                            "configurado para comparar."
                        ),
                        project_id=request.project_id,
                        module_id=ctx.module_def.module_id,
                        operation=request.operation,
                        source_component="WorkspaceManifest",
                        remediation="Declarar contracts.project.artifact en el manifest, apuntando al kind usado como referencia real.",
                    )
                )

        if contracts is not None and contracts.project_artifact is not None:
            artifact = ctx.module_spec.artifact(contracts.project_artifact)
            if artifact is not None and not artifact.required_for_comparison:
                issues.append(
                    ReadinessIssue(
                        code="CONTRACT_ARTIFACT_NOT_MARKED_REQUIRED",
                        severity=ReadinessSeverity.WARNING,
                        message=(
                            f"contracts.project.artifact={contracts.project_artifact!r}, "
                            "pero ese artefacto no tiene required_for_comparison=true -- "
                            "declaraciones inconsistentes."
                        ),
                        project_id=request.project_id,
                        module_id=ctx.module_def.module_id,
                        operation=request.operation,
                        artifact_type=contracts.project_artifact,
                        source_component="WorkspaceManifest",
                        remediation="Alinear required_for_comparison con contracts.project.artifact.",
                    )
                )
        return issues


class SecurityCheck:
    """Nunca abre SQL, nunca concede autorización -- solo LEE el estado
    actual del SQL Execution Guard para una nota informativa, y comprueba
    defensivamente que ninguna ruta resuelta cae dentro del repositorio
    (los datos reales deben vivir fuera de Git, ver CLAUDE.md)."""

    name = "SecurityCheck"

    def run(self, ctx: _CheckContext) -> list[ReadinessIssue]:
        request = ctx.request
        issues: list[ReadinessIssue] = []
        repo_root = PROJECT_ROOT.resolve()

        for kind, resolved in ctx.resolved.items():
            if resolved.resolved_path is None:
                continue
            try:
                inside_repo = resolved.resolved_path.resolve().is_relative_to(repo_root)
            except (OSError, ValueError):
                inside_repo = False
            if inside_repo:
                issues.append(
                    ReadinessIssue(
                        code="DATA_ROOT_ESCAPE",
                        severity=ReadinessSeverity.BLOCKER,
                        message=(
                            f"{kind!r} resuelve dentro del repositorio Git "
                            f"({resolved.resolved_path}) -- los datos reales deben vivir "
                            "fuera de Git (EMF_DATA_ROOT)."
                        ),
                        project_id=request.project_id,
                        module_id=ctx.module_def.module_id,
                        operation=request.operation,
                        artifact_type=kind,
                        source_component="SecurityCheck",
                        remediation="Revisar la configuración de DataWorkspace/EMF_DATA_ROOT.",
                    )
                )

        authorized = sql_execution_guard.is_authorized()
        needs_full_confirm = request.operation == ReadinessOperation.FULL
        next_step = "--allow-real-sql (o EMF_ALLOW_REAL_SQL=1)"
        if needs_full_confirm:
            next_step += " y --confirm-full-export"
        issues.append(
            ReadinessIssue(
                code="SQL_AUTHORIZATION_INFO",
                severity=ReadinessSeverity.INFO,
                message=(
                    f"Autorización SQL actualmente {'concedida' if authorized else 'NO concedida'} "
                    f"en este proceso -- una ejecución real requerirá {next_step}. "
                    "Esto es un prerrequisito de EJECUCIÓN posterior, nunca de este readiness "
                    "(el validador no la concede ni la comprueba como bloqueo)."
                ),
                project_id=request.project_id,
                module_id=ctx.module_def.module_id,
                operation=request.operation,
                source_component="SqlExecutionGuard",
            )
        )
        return issues


# ---------------------------------------------------------------------------
# WorkspaceReadinessValidator
# ---------------------------------------------------------------------------

_POST_GATE_CHECKS = (
    CapabilityCheck(),
    ArtifactDeclarationCheck(),
    ArtifactStatusCheck(),
    ResourceResolutionCheck(),
    PhysicalExistenceCheck(),
    ContractCheck(),
    SecurityCheck(),
)


class WorkspaceReadinessValidator:
    """Evalúa una `ReadinessRequest` y devuelve un `ReadinessAssessment`.
    Sin estado propio entre llamadas -- una instancia se puede reutilizar
    libremente, cada `assess()` es independiente (ADR-010)."""

    def assess(self, request: ReadinessRequest) -> ReadinessAssessment:
        if request.operation not in ReadinessOperation.ALL:
            raise UnknownReadinessOperationError(
                f"operation={request.operation!r} no pertenece al vocabulario cerrado "
                f"{sorted(ReadinessOperation.ALL)}."
            )
        if request.project_id != request.manifest.project.id:
            raise ReadinessRequestError(
                f"ReadinessRequest.project_id={request.project_id!r} no coincide con "
                f"el proyecto del manifest ({request.manifest.project.id!r})."
            )

        executed: list[str] = ["ModuleImplementationCheck", "ProjectModuleDeclarationCheck"]
        issues: list[ReadinessIssue] = []

        module_def, module_spec, gate_issues = self._run_gate(request)
        issues.extend(gate_issues)

        if module_def is None or module_spec is None:
            return self._build_assessment(
                request, executed, issues, module_id=request.module_id,
                required=(), optional=(), resolved=(),
            )

        ctx = _CheckContext(request=request, module_def=module_def, module_spec=module_spec)
        for check in _POST_GATE_CHECKS:
            executed.append(check.name)
            issues.extend(check.run(ctx))

        return self._build_assessment(
            request, executed, issues, module_id=module_def.module_id,
            required=tuple(sorted(ctx.required_kinds)),
            optional=tuple(sorted(ctx.optional_kinds)),
            resolved=tuple(ctx.resolved[kind] for kind in sorted(ctx.resolved)),
        )

    # -- gate: ModuleImplementationCheck + ProjectModuleDeclarationCheck ----

    def _run_gate(
        self, request: ReadinessRequest
    ) -> tuple[ModuleDefinition | None, ModuleSpec | None, list[ReadinessIssue]]:
        # ModuleImplementationCheck (Fase 5.1): módulo conocido, status
        # ejecutable (implemented/experimental) + pipeline_factory real --
        # comprobación puramente de SOFTWARE, deliberadamente antes de tocar
        # el manifest (Fase 7: "1. implementación" precede a "2. proyecto").
        # Distingue "el software no conoce este módulo en absoluto"
        # (MODULE_UNKNOWN) de "lo conoce como roadmap/planned, todavía sin
        # implementación real" (MODULE_NOT_EXECUTABLE) -- Fase 8E del
        # encargo pide explícitamente diferenciar ambos de un artefacto
        # ausente.
        try:
            module_def = request.registry.get(request.module_id)
        except ModuleRegistryUnknownModuleError as exc:
            return None, None, [
                ReadinessIssue(
                    code="MODULE_UNKNOWN",
                    severity=ReadinessSeverity.BLOCKER,
                    message=f"El software no conoce el módulo {request.module_id!r}: {exc}",
                    project_id=request.project_id,
                    module_id=request.module_id,
                    operation=request.operation,
                    source_component="ModuleRegistry",
                    remediation="Ver 'python main.py modules list' -- módulos que el software sabe ejecutar hoy.",
                )
            ]

        if not module_def.is_executable:
            return None, None, [
                ReadinessIssue(
                    code="MODULE_NOT_EXECUTABLE",
                    severity=ReadinessSeverity.BLOCKER,
                    message=(
                        f"El módulo {module_def.module_id!r} está registrado "
                        f"(status={module_def.status!r}) pero el software todavía no "
                        "sabe ejecutarlo -- no tiene una implementación real hoy."
                    ),
                    project_id=request.project_id,
                    module_id=module_def.module_id,
                    operation=request.operation,
                    source_component="ModuleRegistry",
                    remediation="Este módulo es roadmap/planned -- no es un problema de datos del proyecto.",
                )
            ]

        # ProjectModuleDeclarationCheck (Fase 5.2): ¿el proyecto lo declara
        # y está habilitado? Reutiliza `ensure_module_runnable` (Fase 11 de
        # module-registry.md, hasta ahora sin ningún llamador real, ver
        # docs/01-architecture/module-registry.md § 20) en vez de
        # reimplementar la misma lógica.
        try:
            ensure_module_runnable(request.registry, module_def.module_id, manifest=request.manifest)
        except ModuleRegistryUnknownModuleError as exc:
            # Ya descartado arriba -- nunca debería ocurrir aquí; se
            # mantiene por completitud si `ensure_module_runnable` cambiara
            # de orden en el futuro.
            return None, None, [
                ReadinessIssue(
                    code="MODULE_UNKNOWN",
                    severity=ReadinessSeverity.BLOCKER,
                    message=str(exc),
                    project_id=request.project_id,
                    module_id=module_def.module_id,
                    operation=request.operation,
                    source_component="ModuleRegistry",
                )
            ]
        except WorkspaceManifestError as exc:
            return None, None, [
                ReadinessIssue(
                    code="MODULE_NOT_DECLARED_IN_PROJECT",
                    severity=ReadinessSeverity.BLOCKER,
                    message=f"El proyecto no declara el módulo {module_def.module_id!r} en su manifest: {exc}",
                    project_id=request.project_id,
                    module_id=module_def.module_id,
                    operation=request.operation,
                    source_component="WorkspaceManifest",
                    remediation="Declarar el módulo en workspace.yaml -> modules.",
                )
            ]
        except ModuleDisabledForProjectError as exc:
            return None, None, [
                ReadinessIssue(
                    code="MODULE_DISABLED",
                    severity=ReadinessSeverity.BLOCKER,
                    message=str(exc),
                    project_id=request.project_id,
                    module_id=module_def.module_id,
                    operation=request.operation,
                    source_component="WorkspaceManifest",
                    remediation="Marcar enabled: true en el manifest si el proyecto ya debe operar este módulo.",
                )
            ]

        module_spec = request.manifest.get_module(module_def.module_id)
        return module_def, module_spec, []

    # -- agregación -----------------------------------------------------

    def _build_assessment(
        self,
        request: ReadinessRequest,
        executed: list[str],
        issues: list[ReadinessIssue],
        *,
        module_id: str,
        required: tuple[str, ...],
        optional: tuple[str, ...],
        resolved: tuple[ResolvedResource, ...],
    ) -> ReadinessAssessment:
        deduped: list[ReadinessIssue] = []
        seen: set[tuple[str, str | None]] = set()
        for issue in issues:
            if issue.dedup_key in seen:
                continue
            seen.add(issue.dedup_key)
            deduped.append(issue)

        blockers = tuple(i for i in deduped if i.severity == ReadinessSeverity.BLOCKER)
        warnings = tuple(i for i in deduped if i.severity == ReadinessSeverity.WARNING)
        informational = tuple(i for i in deduped if i.severity == ReadinessSeverity.INFO)

        if blockers:
            status = ReadinessStatus.BLOCKED
        elif warnings:
            status = ReadinessStatus.BLOCKED if request.strict else ReadinessStatus.READY_WITH_WARNINGS
        else:
            status = ReadinessStatus.READY

        missing_resources = tuple(
            sorted({i.artifact_type for i in blockers if i.artifact_type and "MISSING" in i.code})
        )
        generated_resources = tuple(sorted(r.artifact_type for r in resolved if r.generated))

        summary = (
            f"{module_id} / {request.operation}: "
            f"{len(blockers)} blocker(s), {len(warnings)} warning(s), {len(informational)} informational."
        )
        recommended_next_action = self._next_action(status, blockers, request)

        return ReadinessAssessment(
            assessment_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            project_id=request.project_id,
            module_id=module_id,
            operation=request.operation,
            status=status,
            checks=tuple(executed),
            issues=tuple(deduped),
            blockers=blockers,
            warnings=warnings,
            informational=informational,
            required_artifacts=required,
            optional_artifacts=optional,
            resolved_resources=resolved,
            missing_resources=missing_resources,
            generated_resources=generated_resources,
            summary=summary,
            recommended_next_action=recommended_next_action,
        )

    @staticmethod
    def _next_action(status: str, blockers: tuple[ReadinessIssue, ...], request: ReadinessRequest) -> str:
        if status == ReadinessStatus.BLOCKED:
            if blockers:
                return f"Resolver {len(blockers)} bloqueo(s) antes de intentar esta operación."
            return "Resolver las advertencias (modo --strict) antes de intentar esta operación."
        sql_hint = "--allow-real-sql (o EMF_ALLOW_REAL_SQL=1)"
        if request.operation == ReadinessOperation.FULL:
            sql_hint += " y --confirm-full-export"
        if status == ReadinessStatus.READY_WITH_WARNINGS:
            return f"Revisar advertencias; se puede proceder. Ejecución real requerirá {sql_hint}."
        return f"Listo para proceder. Ejecución real requerirá {sql_hint}."
