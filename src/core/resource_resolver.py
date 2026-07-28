"""Resource Resolver -- capa genérica que resuelve los artefactos
declarados en un `WorkspaceManifest` (Sprint 8.5, ver
`docs/01-architecture/resource-resolver.md`).

Responde a "dame el CSV Operacional de Drills, obligatorio" y devuelve una
referencia tipada y trazable (`ResolvedResource`), nunca un simple string.
Vive en `src/core/` junto a `data_workspace.py`/`workspace_manifest.py`
porque es infraestructura reutilizable por cualquier módulo futuro --
ninguna clase de este fichero conoce Drills ni ningún objeto migrable
concreto (verificable por inspección: no hay ningún import de
`src.export`, `src.etl` ni `src.evidence` aquí).

Garantías deliberadas (mismo espíritu que `data_workspace.py` y
`workspace_manifest.py`):
- El manifest es la fuente de verdad -- este módulo nunca adivina un
  nombre de archivo ni usa `glob`/`rglob` como mecanismo de resolución.
- Nunca cae en silencio a `inputs/`, a una ruta legacy o a un archivo de
  nombre parecido -- una ausencia (no declarado / declarado missing /
  ausente físicamente) siempre se devuelve o se lanza de forma explícita,
  nunca se enmascara.
- Toda ruta se resuelve exclusivamente a través de `DataWorkspace.resolve()`
  (reutilizada de `workspace_manifest.resolve_artifact_path`) -- este
  módulo no reimplementa la protección de escape ni de rutas absolutas.
- Nunca abre, lee ni calcula el contenido/checksum físico de ningún
  recurso -- comprobar existencia (`Path.exists()`/`is_file()`) es la
  única operación de filesystem que este módulo realiza, y solo cuando se
  pide explícitamente (`require_physical_file=True`).
- Nunca crea directorios ni archivos, tampoco para un recurso generado
  (Fase 5): el patrón se valida y se resuelve, nunca se materializa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from src.core.data_workspace import DataWorkspace, DataWorkspaceError
from src.core.exceptions import CoreError
from src.core.workspace_manifest import (
    ARTIFACT_KIND_TO_CATEGORY,
    ARTIFACT_KINDS,
    ArtifactStatus,
    ModuleSpec,
    WorkspaceManifest,
    WorkspaceManifestError,
    resolve_artifact_path,
)

# Kind de artefacto usado como vehículo para un recurso generado (Fase 5).
# Deliberadamente acotado a este único caso real conocido hoy (el CSV de
# salida del EMF, ver `ContractsSpec.emf_generated`/`emf_output_pattern`)
# -- "No Abstraction Without a Real Consumer": no se generaliza a
# `artifact.generated`/`artifact.path_pattern` por artefacto sin un
# segundo caso real que lo justifique (ver § "Deuda técnica" del informe
# de este sprint).
GENERATED_ARTIFACT_KIND = "outputs"

_EXECUTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_ALLOWED_OUTPUT_PLACEHOLDERS = frozenset({"module", "execution_id"})


class ResourceResolutionError(CoreError):
    """Base común de todas las excepciones de este módulo -- permite un
    `except ResourceResolutionError` genérico, mismo patrón que
    `DataWorkspaceError`/`WorkspaceManifestError` ya establecido en el
    resto del repositorio."""


class UnknownProjectError(ResourceResolutionError):
    """`ResourceRequest.project_id` no coincide con el proyecto declarado
    en el manifest que resuelve esta petición (un `ResourceResolver` está
    ligado a un único `WorkspaceManifest`, de un único proyecto)."""


class UnknownModuleError(ResourceResolutionError):
    """`ResourceRequest.module_id` no está declarado en `manifest.modules`."""


class UnknownArtifactError(ResourceResolutionError):
    """`ResourceRequest.artifact_type` no pertenece al vocabulario cerrado
    de `ARTIFACT_KINDS` -- error de forma de la propia petición, distinto
    de `ArtifactNotDeclaredError` (petición válida, pero ese módulo en
    concreto no declara ese artefacto)."""


class ArtifactNotDeclaredError(ResourceResolutionError):
    """El `artifact_type` pedido es un kind válido, pero el módulo no lo
    declara en absoluto dentro de su sección `artifacts` del manifest."""


class ArtifactMissingError(ResourceResolutionError):
    """`required=True` y el artefacto no tiene una ruta resoluble
    (sin `path` declarado, o `status=missing` declarado explícitamente)."""


class PhysicalResourceMissingError(ResourceResolutionError):
    """`required=True` y `require_physical_file=True`, y el archivo
    resuelto no existe en disco."""


class DeprecatedArtifactError(ResourceResolutionError):
    """El artefacto está marcado `status=deprecated` en el manifest y la
    petición no pasó `allow_deprecated=True` explícitamente."""


class InvalidArtifactStatusError(ResourceResolutionError):
    """El artefacto tiene `status=not_applicable` (nunca resoluble como
    recurso utilizable) o su status no está entre
    `ResourceRequest.allowed_statuses`, si se pidieron."""


class ResourcePathError(ResourceResolutionError):
    """La ruta declarada o el patrón de un recurso generado no se pudo
    resolver de forma segura -- envuelve `DataWorkspaceError` (categoría/
    proyecto desconocidos en `data_workspace.yaml`, o intento de escape) y
    los propios errores de validación de patrón/`execution_id` de este
    módulo. Nunca revela más que la propia ruta/patrón involucrado."""


# ---------------------------------------------------------------------------
# Modelo de petición / resultado
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResourceRequest:
    """Qué recurso se pide y bajo qué condiciones. Deliberadamente sin
    credenciales, conexiones, DataFrames ni contenido de archivo -- solo
    coordenadas declarativas hacia el manifest.

    `project_id=None` (por defecto) usa el único proyecto del manifest que
    resuelve la petición -- un `ResourceResolver` está ligado a un
    manifest de un único proyecto, así que en la práctica casi ningún
    llamador necesita fijarlo; se admite explícito solo para que
    `UnknownProjectError` sea detectable si alguien pasa el proyecto
    equivocado por error.

    `execution_id` solo se usa para recursos generados (`artifact_type`
    igual a `GENERATED_ARTIFACT_KIND`, ver Fase 5) -- se ignora para
    cualquier otro artefacto.
    """

    module_id: str
    artifact_type: str
    project_id: str | None = None
    required: bool = False
    require_physical_file: bool = False
    allowed_statuses: frozenset[str] | None = None
    allow_deprecated: bool = False
    purpose: str | None = None
    execution_id: str | None = None


@dataclass(frozen=True)
class ResolvedResource:
    """Referencia tipada y trazable a un artefacto ya resuelto contra un
    `WorkspaceManifest` + `DataWorkspace` reales. Nunca contiene el
    contenido del recurso -- solo su ubicación y metadatos declarativos."""

    project_id: str
    module_id: str
    artifact_type: str
    declared_path: str | None
    resolved_path: Path | None
    artifact_status: str
    exists: bool | None
    required: bool
    contract_role: str | None
    source: str | None
    description: str
    checksum: str | None
    warnings: tuple[str, ...]
    manifest_ref: str
    generated: bool = False


# ---------------------------------------------------------------------------
# Resolución de recursos generados (Fase 5)
# ---------------------------------------------------------------------------

def _validate_execution_id(execution_id: str) -> None:
    if not execution_id or not _EXECUTION_ID_PATTERN.fullmatch(execution_id):
        raise ResourcePathError(
            f"execution_id={execution_id!r} no es válido -- solo se permiten "
            "letras, números, '_' y '-' (nunca separadores de ruta ni '..')."
        )


def _render_generated_relative_path(pattern: str, *, module_name: str, execution_id: str) -> str:
    """Sustituye `{module}`/`{execution_id}` en `pattern` de forma
    literal -- nunca interpreta el patrón como código ni como plantilla
    general (no hay motor de plantillas aquí, solo dos placeholders
    conocidos, ver Fase 5 del encargo)."""
    placeholders = set(re.findall(r"\{(\w+)\}", pattern))
    unknown = placeholders - _ALLOWED_OUTPUT_PLACEHOLDERS
    if unknown:
        raise ResourcePathError(
            f"El patrón {pattern!r} declara placeholder(s) desconocido(s): "
            f"{sorted(unknown)} (permitidos: {sorted(_ALLOWED_OUTPUT_PLACEHOLDERS)})."
        )
    return pattern.format(module=module_name, execution_id=execution_id)


# ---------------------------------------------------------------------------
# ResourceResolver
# ---------------------------------------------------------------------------

class ResourceResolver:
    """Resuelve `ResourceRequest` contra un `WorkspaceManifest` +
    `DataWorkspace` concretos. Ligado a un único manifest/proyecto -- para
    otro proyecto se construye otro `ResourceResolver`.

    Nunca abre ni lee el contenido de ningún recurso. Nunca crea
    directorios ni archivos. Comprobar existencia física es opcional y
    explícito (`require_physical_file`), nunca automático."""

    def __init__(self, manifest: WorkspaceManifest, workspace: DataWorkspace) -> None:
        self._manifest = manifest
        self._workspace = workspace

    def resolve(self, request: ResourceRequest) -> ResolvedResource:
        project_id = request.project_id or self._manifest.project.id
        if project_id != self._manifest.project.id:
            raise UnknownProjectError(
                f"El manifest resuelto es del proyecto {self._manifest.project.id!r}, "
                f"se pidió {project_id!r}."
            )

        if request.artifact_type not in ARTIFACT_KINDS:
            raise UnknownArtifactError(
                f"artifact_type={request.artifact_type!r} no pertenece al vocabulario "
                f"cerrado de artefactos: {sorted(ARTIFACT_KINDS)}."
            )

        try:
            module = self._manifest.get_module(request.module_id)
        except WorkspaceManifestError as exc:
            raise UnknownModuleError(str(exc)) from exc

        if self._is_generated_request(request, module):
            return self._resolve_generated(request, module, project_id)

        return self._resolve_declared(request, module, project_id)

    # -- artefacto declarado (caso general) ---------------------------------

    def _resolve_declared(
        self, request: ResourceRequest, module: ModuleSpec, project_id: str
    ) -> ResolvedResource:
        artifact = module.artifact(request.artifact_type)
        if artifact is None:
            raise ArtifactNotDeclaredError(
                f"El módulo {request.module_id!r} no declara el artefacto "
                f"{request.artifact_type!r} (declarados: {sorted(module.artifacts)})."
            )

        manifest_ref = f"{project_id}/{request.module_id}/{request.artifact_type}"

        if request.allowed_statuses is not None and artifact.status not in request.allowed_statuses:
            raise InvalidArtifactStatusError(
                f"{manifest_ref}: status={artifact.status!r} no está entre los "
                f"permitidos por la petición: {sorted(request.allowed_statuses)}."
            )

        if artifact.status == ArtifactStatus.NOT_APPLICABLE:
            raise InvalidArtifactStatusError(
                f"{manifest_ref}: status=not_applicable -- no es un recurso resoluble "
                f"para este módulo ({artifact.description or 'sin descripción'})."
            )

        if artifact.status == ArtifactStatus.DEPRECATED and not request.allow_deprecated:
            raise DeprecatedArtifactError(
                f"{manifest_ref}: status=deprecated -- pase allow_deprecated=True "
                "explícitamente si de verdad necesita resolverlo."
            )

        warnings: list[str] = []
        if artifact.status == ArtifactStatus.MISSING:
            warnings.append(f"{manifest_ref}: el manifest declara status=missing.")

        if artifact.path is None:
            if request.required:
                raise ArtifactMissingError(
                    f"{manifest_ref}: required=True pero el manifest no declara una "
                    "ruta (path) para este artefacto todavía."
                )
            return ResolvedResource(
                project_id=project_id, module_id=request.module_id,
                artifact_type=request.artifact_type, declared_path=None, resolved_path=None,
                artifact_status=artifact.status, exists=None, required=request.required,
                contract_role=artifact.contract_role, source=artifact.source,
                description=artifact.description, checksum=artifact.checksum,
                warnings=tuple(warnings), manifest_ref=manifest_ref,
            )

        try:
            resolved_path = resolve_artifact_path(
                self._manifest, request.module_id, request.artifact_type,
                self._workspace, required=False,
            )
        except DataWorkspaceError as exc:
            raise ResourcePathError(
                f"{manifest_ref}: no se pudo resolver la ruta declarada "
                f"({artifact.path!r}) contra el workspace externo: {exc}"
            ) from exc

        exists: bool | None = None
        if request.require_physical_file:
            exists = resolved_path.is_file()
            if not exists:
                if artifact.status == ArtifactStatus.OPTIONAL:
                    warnings.append(
                        f"{manifest_ref}: artefacto opcional, ausente físicamente en {resolved_path}."
                    )
                elif request.required:
                    raise PhysicalResourceMissingError(
                        f"{manifest_ref}: no existe físicamente en {resolved_path} "
                        "(required=True, require_physical_file=True)."
                    )
                else:
                    warnings.append(f"{manifest_ref}: no existe físicamente en {resolved_path}.")

        return ResolvedResource(
            project_id=project_id, module_id=request.module_id,
            artifact_type=request.artifact_type, declared_path=artifact.path,
            resolved_path=resolved_path, artifact_status=artifact.status, exists=exists,
            required=request.required, contract_role=artifact.contract_role,
            source=artifact.source, description=artifact.description, checksum=artifact.checksum,
            warnings=tuple(warnings), manifest_ref=manifest_ref,
        )

    # -- recurso generado (Fase 5) -------------------------------------------

    def _is_generated_request(self, request: ResourceRequest, module: ModuleSpec) -> bool:
        return (
            request.artifact_type == GENERATED_ARTIFACT_KIND
            and module.contracts is not None
            and module.contracts.emf_generated
            and module.contracts.emf_output_pattern is not None
        )

    def _resolve_generated(
        self, request: ResourceRequest, module: ModuleSpec, project_id: str
    ) -> ResolvedResource:
        manifest_ref = f"{project_id}/{request.module_id}/{request.artifact_type}"
        pattern = module.contracts.emf_output_pattern
        assert pattern is not None  # garantizado por _is_generated_request

        if request.execution_id is None:
            raise ResourcePathError(
                f"{manifest_ref}: es un recurso generado (patrón {pattern!r}) -- "
                "requiere execution_id explícito en la petición."
            )
        _validate_execution_id(request.execution_id)

        module_name = module.canonical_name or module.module_id
        relative_path = _render_generated_relative_path(
            pattern, module_name=module_name, execution_id=request.execution_id,
        )

        category = ARTIFACT_KIND_TO_CATEGORY[GENERATED_ARTIFACT_KIND]
        try:
            resolved_path = self._workspace.resolve(
                project=project_id, category=category,
                relative_path=relative_path, required=False,
            )
        except DataWorkspaceError as exc:
            raise ResourcePathError(
                f"{manifest_ref}: no se pudo resolver el patrón generado "
                f"({relative_path!r}) contra el workspace externo: {exc}"
            ) from exc

        warnings: list[str] = []
        exists: bool | None = None
        if request.require_physical_file:
            exists = resolved_path.is_file()
            if not exists:
                # Un output generado que todavía no existe es el estado
                # normal antes de ejecutar -- nunca bloqueante por sí solo,
                # ni siquiera con required=True (Fase 4: "tratar de forma
                # diferenciada").
                warnings.append(
                    f"{manifest_ref}: recurso generado, todavía no existe físicamente "
                    f"en {resolved_path} (normal antes de ejecutar)."
                )

        return ResolvedResource(
            project_id=project_id, module_id=request.module_id,
            artifact_type=request.artifact_type, declared_path=pattern,
            resolved_path=resolved_path, artifact_status="generated", exists=exists,
            required=request.required, contract_role=None, source=None,
            description=f"Recurso generado por el EMF a partir del patrón {pattern!r}.",
            checksum=None, warnings=tuple(warnings), manifest_ref=manifest_ref, generated=True,
        )
