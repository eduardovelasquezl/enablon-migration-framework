"""Workspace Manifest -- modelo declarativo del contenido esperado del
workspace externo de datos (Sprint 8.4, ver
`docs/01-architecture/workspace-manifest.md`).

Responde a "¿qué proyecto, qué módulos, qué artefactos, cuáles son
obligatorios, cuáles existen, qué contrato representa cada CSV?" a partir
de un único fichero declarativo (`workspace.yaml`), sin tener que recorrer
el workspace a mano ni adivinar convenciones.

Vive en `src/core/` porque, igual que `data_workspace.py`, es
infraestructura genérica reutilizable por cualquier proyecto/módulo
futuro -- ninguna clase de este módulo conoce Drills ni ningún objeto
migrable concreto (verificable por inspección: no hay ningún import de
`src.export`, `src.etl` ni `src.evidence` aquí). Drills solo aparece,
como cualquier otro módulo, en el YAML de ejemplo
(`examples/workspace/workspace.example.yaml`), nunca en este código.

Garantías deliberadas (mismo espíritu que `data_workspace.py`):
- Nunca abre ni lee el contenido de ningún archivo *referenciado* por el
  manifest -- solo el propio YAML del manifest.
- Nunca crea directorios ni archivos.
- Nunca ejecuta SQL ni ninguna operación de red.
- Reutiliza `DataWorkspace.resolve()` para la seguridad de rutas
  (protección de escape, rutas absolutas) -- no duplica esa lógica.
- `validate_manifest()` devuelve una lista de violaciones, nunca lanza
  una excepción por una regla de negocio incumplida (mismo patrón que
  `validate_pre_write`/`validate_output_csv` de Drills, ya establecido en
  `docs/03-engineering-standards/engineering-standards.md` § 4). Los
  errores de FORMA (falta una clave obligatoria, un valor fuera de
  vocabulario cerrado) sí lanzan `ManifestSchemaError` al cargar --  un
  manifest mal formado no puede ni siquiera construirse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from src.core.data_workspace import DataWorkspace
from src.core.exceptions import CoreError

SCHEMA_VERSION = "1.0"

# Nombre lógico de artefacto -> categoría de DataWorkspace/config/data_workspace.yaml
# que lo resuelve. Único punto de esta correspondencia -- nunca se repite
# en otro sitio del código.
ARTIFACT_KIND_TO_CATEGORY: Mapping[str, str] = {
    "etl": "etl",
    "template_csv": "csv_enablon_template",
    "operational_csv": "csv_enablon_operational",
    "sql": "sql",
    "mapping": "mappings",
    "catalogs": "catalogs",
    "errors": "errors",
    "evidence": "evidence",
    "outputs": "outputs",
}
ARTIFACT_KINDS = frozenset(ARTIFACT_KIND_TO_CATEGORY)

CONTRACT_ROLES = frozenset({"platform", "project", "emf"})


class WorkspaceManifestError(CoreError):
    """Base común de las excepciones de este módulo -- permite un
    `except WorkspaceManifestError` genérico, mismo patrón que
    `DataWorkspaceError`/`QueryEngineError` ya establecido en el resto del
    repositorio."""


class ManifestSchemaError(WorkspaceManifestError):
    """El manifest (o un fragmento pasado directamente a un dataclass) no
    tiene una forma válida: falta una clave obligatoria, un valor está
    fuera de su vocabulario cerrado, o una ruta declarada es absoluta o
    intenta escapar. Se lanza al CARGAR/CONSTRUIR, nunca al validar reglas
    de negocio (eso es `validate_manifest`, que devuelve una lista)."""


class ModuleStatus:
    """Vocabulario cerrado de estado de un módulo. Alineado con el
    vocabulario ya usado en el resto del proyecto para "en qué punto del
    ciclo de vida está algo" (`StageStatus`/`ExecutionStatus` en
    `src/core/contracts.py`, `RESOLVED`/`UNRESOLVED`/... en
    `mappings.py`) -- ninguno de esos vocabularios sirve tal cual para un
    módulo completo, así que se define uno propio, del mismo tamaño
    mínimo que el encargo propuso (no se amplía sin evidencia)."""

    PLANNED = "planned"
    READY = "ready"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    ALL = frozenset({PLANNED, READY, BLOCKED, IN_PROGRESS, VALIDATED, DEPRECATED})


class ArtifactStatus:
    """Vocabulario cerrado de estado de un artefacto individual."""

    MISSING = "missing"
    PRESENT = "present"
    VALIDATED = "validated"
    OPTIONAL = "optional"
    DEPRECATED = "deprecated"
    NOT_APPLICABLE = "not_applicable"
    ALL = frozenset({MISSING, PRESENT, VALIDATED, OPTIONAL, DEPRECATED, NOT_APPLICABLE})


def _check_choice(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        raise ManifestSchemaError(
            f"{field_name}={value!r} no es un valor válido de {sorted(allowed)}"
        )


def _validate_relative_safe_path(value: str, field_name: str) -> None:
    """Rechaza una ruta absoluta o con componentes '..' a nivel de
    esquema -- la misma regla que aplicará después `DataWorkspace.resolve`
    (Fase 6), verificada aquí primero para dar un error temprano y claro
    sin necesitar todavía un `DataWorkspace` real. No duplica la lógica de
    resolución en sí (eso sigue viviendo únicamente en `data_workspace.py`)."""
    if not value:
        return
    if re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\"):
        raise ManifestSchemaError(
            f"{field_name}={value!r} parece una ruta absoluta de Windows -- debe ser relativa."
        )
    normalized = value.replace("\\", "/")
    p = PurePosixPath(normalized)
    if p.is_absolute():
        raise ManifestSchemaError(f"{field_name}={value!r} debe ser una ruta relativa, no absoluta.")
    if ".." in p.parts:
        raise ManifestSchemaError(f"{field_name}={value!r} no puede contener '..'.")


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactSpec:
    """Un artefacto de un módulo (p. ej. el ETL de Drills, o su CSV
    Operacional). `path` es relativo a la carpeta de categoría del
    workspace externo (ver `ARTIFACT_KIND_TO_CATEGORY`) -- nunca absoluto,
    nunca abierto por este módulo."""

    kind: str
    path: str | None = None
    required_for_sample: bool = False
    required_for_full: bool = False
    required_for_comparison: bool = False
    status: str = ArtifactStatus.MISSING
    description: str = ""
    contract_role: str | None = None
    source: str | None = None
    checksum: str | None = None
    last_reviewed_at: str | None = None

    def __post_init__(self) -> None:
        _check_choice(self.kind, ARTIFACT_KINDS, "ArtifactSpec.kind")
        _check_choice(self.status, ArtifactStatus.ALL, "ArtifactSpec.status")
        if self.contract_role is not None:
            _check_choice(self.contract_role, CONTRACT_ROLES, "ArtifactSpec.contract_role")
        if self.path is not None:
            _validate_relative_safe_path(self.path, f"ArtifactSpec[{self.kind}].path")
        if (self.required_for_sample or self.required_for_full) and self.status == ArtifactStatus.NOT_APPLICABLE:
            raise ManifestSchemaError(
                f"ArtifactSpec[{self.kind}]: un artefacto obligatorio "
                "(required_for_sample/required_for_full) no puede declararse status=not_applicable."
            )


@dataclass(frozen=True)
class ContractsSpec:
    """Qué artefacto del módulo representa cada nivel de contrato (ver
    `docs/01-architecture/project-contract-model.md`). `platform_artifact`/
    `project_artifact` son nombres de `kind` (`ARTIFACT_KINDS`), nunca una
    ruta -- el contrato apunta a un artefacto declarado, no a un fichero
    directamente."""

    platform_artifact: str | None = None
    project_artifact: str | None = None
    emf_generated: bool = False
    emf_output_pattern: str | None = None

    def __post_init__(self) -> None:
        if self.platform_artifact is not None:
            _check_choice(self.platform_artifact, ARTIFACT_KINDS, "ContractsSpec.platform_artifact")
        if self.project_artifact is not None:
            _check_choice(self.project_artifact, ARTIFACT_KINDS, "ContractsSpec.project_artifact")


@dataclass(frozen=True)
class ModuleSpec:
    """Un módulo migrable (Drills, Safety Meetings, MOC...). `canonical_name`
    es el nombre usado en las convenciones de fichero (`<Modulo>.xlsx`,
    `<Modulo>.csv`) -- opcional: si no se declara, la validación de
    nomenclatura (`validate_manifest`) simplemente no se aplica a ese
    módulo (nunca se adivina el nombre canónico a partir de `module_id`)."""

    module_id: str
    display_name: str
    enabled: bool
    status: str
    source_system: str | None = None
    target_object: str | None = None
    canonical_name: str | None = None
    artifacts: Mapping[str, ArtifactSpec] = field(default_factory=dict)
    contracts: ContractsSpec | None = None
    validation: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ManifestSchemaError("ModuleSpec.module_id no puede estar vacío.")
        _check_choice(self.status, ModuleStatus.ALL, f"ModuleSpec[{self.module_id}].status")
        if self.status == ModuleStatus.DEPRECATED and self.enabled and not self.notes.strip():
            raise ManifestSchemaError(
                f"ModuleSpec[{self.module_id}]: status=deprecated y enabled=true requieren "
                "'notes' con justificación explícita (regla dura de Sprint 8.4)."
            )
        if self.contracts is not None:
            for role, artifact_kind in (
                ("platform", self.contracts.platform_artifact),
                ("project", self.contracts.project_artifact),
            ):
                if artifact_kind is not None and artifact_kind not in self.artifacts:
                    raise ManifestSchemaError(
                        f"ModuleSpec[{self.module_id}]: contracts.{role} referencia el artefacto "
                        f"{artifact_kind!r}, que no está declarado en 'artifacts'."
                    )

    def artifact(self, kind: str) -> ArtifactSpec | None:
        return self.artifacts.get(kind)


@dataclass(frozen=True)
class ProjectMeta:
    id: str
    display_name: str
    status: str
    version: str
    owner: str | None = None
    last_reviewed_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ManifestSchemaError("project.id no puede estar vacío.")
        if not self.display_name:
            raise ManifestSchemaError("project.display_name no puede estar vacío.")
        if not self.status:
            raise ManifestSchemaError("project.status no puede estar vacío.")
        if not self.version:
            raise ManifestSchemaError("project.version no puede estar vacío.")


@dataclass(frozen=True)
class WorkspaceMeta:
    schema_version: str
    project_root: str
    naming_convention: Mapping[str, str] = field(default_factory=dict)
    deprecated_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.schema_version:
            raise ManifestSchemaError("workspace.schema_version no puede estar vacío.")
        if not self.project_root:
            raise ManifestSchemaError("workspace.project_root no puede estar vacío.")
        _validate_relative_safe_path(self.project_root, "workspace.project_root")
        for kind in self.naming_convention:
            if kind not in ARTIFACT_KINDS:
                raise ManifestSchemaError(
                    f"workspace.naming_convention declara una clave desconocida: {kind!r} "
                    f"(válidas: {sorted(ARTIFACT_KINDS)})"
                )


@dataclass(frozen=True)
class WorkspaceManifest:
    """Raíz del manifest ya cargado y validado estructuralmente."""

    project: ProjectMeta
    workspace: WorkspaceMeta
    modules: Mapping[str, ModuleSpec]

    def __post_init__(self) -> None:
        for key, module in self.modules.items():
            if key != module.module_id:
                raise ManifestSchemaError(
                    f"La clave de módulo {key!r} no coincide con el module_id declarado "
                    f"dentro de la propia entrada ({module.module_id!r})."
                )

    def module_ids(self) -> tuple[str, ...]:
        return tuple(self.modules.keys())

    def get_module(self, module_id: str) -> ModuleSpec:
        try:
            return self.modules[module_id]
        except KeyError:
            raise WorkspaceManifestError(
                f"Módulo no declarado en el manifest: {module_id!r} "
                f"(disponibles: {sorted(self.modules)})"
            ) from None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _build_artifact(kind: str, raw: Mapping[str, Any]) -> ArtifactSpec:
    return ArtifactSpec(
        kind=kind,
        path=raw.get("path"),
        required_for_sample=bool(raw.get("required_for_sample", False)),
        required_for_full=bool(raw.get("required_for_full", False)),
        required_for_comparison=bool(raw.get("required_for_comparison", False)),
        status=raw.get("status", ArtifactStatus.MISSING),
        description=raw.get("description", "") or "",
        contract_role=raw.get("contract_role"),
        source=raw.get("source"),
        checksum=raw.get("checksum"),
        last_reviewed_at=raw.get("last_reviewed_at"),
    )


def _build_contracts(raw: Mapping[str, Any] | None) -> ContractsSpec | None:
    if not raw:
        return None
    platform = raw.get("platform") or {}
    project = raw.get("project") or {}
    emf = raw.get("emf") or {}
    return ContractsSpec(
        platform_artifact=platform.get("artifact"),
        project_artifact=project.get("artifact"),
        emf_generated=bool(emf.get("generated", False)),
        emf_output_pattern=emf.get("output_pattern"),
    )


def _build_module(module_id: str, raw: Mapping[str, Any]) -> ModuleSpec:
    missing = {"display_name", "enabled", "status"} - set(raw)
    if missing:
        raise ManifestSchemaError(f"Módulo {module_id!r} no declara: {sorted(missing)}")
    raw_artifacts = raw.get("artifacts") or {}
    artifacts = {kind: _build_artifact(kind, spec or {}) for kind, spec in raw_artifacts.items()}
    return ModuleSpec(
        module_id=module_id,
        display_name=raw["display_name"],
        enabled=bool(raw["enabled"]),
        status=raw["status"],
        source_system=raw.get("source_system"),
        target_object=raw.get("target_object"),
        canonical_name=raw.get("canonical_name"),
        artifacts=artifacts,
        contracts=_build_contracts(raw.get("contracts")),
        validation=dict(raw.get("validation") or {}),
        notes=raw.get("notes", "") or "",
    )


class WorkspaceManifestLoader:
    """Carga un `workspace.yaml` (o un `dict` ya parseado) a un
    `WorkspaceManifest` tipado. Nunca abre ningún archivo referenciado por
    el manifest -- solo el propio YAML de entrada."""

    @staticmethod
    def load_from_dict(raw: Mapping[str, Any]) -> WorkspaceManifest:
        missing_top = {"project", "workspace", "modules"} - set(raw)
        if missing_top:
            raise ManifestSchemaError(
                f"El manifest no declara las claves obligatorias de nivel superior: {sorted(missing_top)}"
            )

        project_raw = raw["project"] or {}
        missing_project = {"id", "display_name", "status", "version"} - set(project_raw)
        if missing_project:
            raise ManifestSchemaError(f"'project' no declara: {sorted(missing_project)}")
        project = ProjectMeta(
            id=project_raw["id"],
            display_name=project_raw["display_name"],
            status=project_raw["status"],
            version=str(project_raw["version"]),
            owner=project_raw.get("owner"),
            last_reviewed_at=project_raw.get("last_reviewed_at"),
        )

        workspace_raw = raw["workspace"] or {}
        missing_workspace = {"schema_version", "project_root"} - set(workspace_raw)
        if missing_workspace:
            raise ManifestSchemaError(f"'workspace' no declara: {sorted(missing_workspace)}")
        workspace = WorkspaceMeta(
            schema_version=str(workspace_raw["schema_version"]),
            project_root=workspace_raw["project_root"],
            naming_convention=dict(workspace_raw.get("naming_convention") or {}),
            deprecated_paths=tuple(workspace_raw.get("deprecated_paths") or ()),
        )

        modules_raw = raw["modules"] or {}
        if not modules_raw:
            raise ManifestSchemaError("El manifest no declara ningún módulo en 'modules'.")
        modules = {mid: _build_module(mid, mspec or {}) for mid, mspec in modules_raw.items()}

        return WorkspaceManifest(project=project, workspace=workspace, modules=modules)

    @staticmethod
    def load_from_path(path: Path) -> WorkspaceManifest:
        if not path.is_file():
            raise WorkspaceManifestError(f"No existe el fichero de manifest: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return WorkspaceManifestLoader.load_from_dict(raw)


# ---------------------------------------------------------------------------
# Validación de negocio (devuelve lista de violaciones, nunca lanza)
# ---------------------------------------------------------------------------

def _pattern_to_regex(pattern: str, module_name: str) -> str:
    """Convierte un patrón de nomenclatura declarativo (`{module}.csv`,
    `{module}_{execution_id}.csv`) a una regex, sustituyendo los
    placeholders ANTES de escapar el resto -- nunca se interpreta el
    patrón como código, solo como texto con dos marcadores conocidos."""
    tokens = re.split(r"(\{module\}|\{execution_id\})", pattern)
    parts: list[str] = []
    for token in tokens:
        if token == "{module}":
            parts.append(re.escape(module_name))
        elif token == "{execution_id}":
            parts.append(r"[^/\\]+")
        else:
            parts.append(re.escape(token))
    return "".join(parts)


def _matches_naming_pattern(pattern: str, path: str, module_name: str) -> bool:
    regex = _pattern_to_regex(pattern, module_name)
    return re.fullmatch(regex, path) is not None


def validate_manifest(manifest: WorkspaceManifest) -> list[str]:
    """Validaciones de negocio sobre un manifest YA cargado con éxito (la
    carga, ver `WorkspaceManifestLoader`, ya garantiza la forma
    estructural básica: claves obligatorias, vocabularios cerrados, rutas
    relativas y sin escapes). Devuelve una lista de violaciones -- nunca
    lanza excepción por una regla de negocio incumplida, mismo patrón que
    `validate_pre_write`/`validate_output_csv` de Drills.

    No comprueba si los archivos físicos existen -- eso es
    responsabilidad de quien integra este manifest con un `DataWorkspace`
    real (ver `resolve_artifact_path`), nunca de esta función."""
    violations: list[str] = []

    seen_paths_by_kind: dict[str, dict[str, str]] = {}
    seen_canonical_names: dict[str, str] = {}

    for module_id, module in manifest.modules.items():
        if module.canonical_name:
            other = seen_canonical_names.get(module.canonical_name)
            if other is not None and other != module_id:
                violations.append(
                    f"Los módulos {other!r} y {module_id!r} declaran el mismo "
                    f"canonical_name={module.canonical_name!r} -- colisionarían en el "
                    "nombre de fichero (ver workspace-naming-convention.md)."
                )
            else:
                seen_canonical_names[module.canonical_name] = module_id

        for kind, artifact in module.artifacts.items():
            if artifact.path is None:
                continue

            if module.status != ModuleStatus.DEPRECATED:
                for deprecated in manifest.workspace.deprecated_paths:
                    normalized_deprecated = deprecated.rstrip("/\\")
                    if artifact.path == normalized_deprecated or artifact.path.startswith(
                        normalized_deprecated + "/"
                    ):
                        violations.append(
                            f"{module_id}.{kind}: la ruta {artifact.path!r} usa una carpeta "
                            f"marcada deprecated ({deprecated!r}) desde un módulo no deprecated."
                        )

            seen_for_kind = seen_paths_by_kind.setdefault(kind, {})
            other_module = seen_for_kind.get(artifact.path)
            if other_module is not None and other_module != module_id:
                violations.append(
                    f"Los módulos {other_module!r} y {module_id!r} declaran la misma ruta "
                    f"{artifact.path!r} para el artefacto {kind!r} -- ambigüedad de cuál es "
                    "el vigente."
                )
            else:
                seen_for_kind[artifact.path] = module_id

            pattern = manifest.workspace.naming_convention.get(kind)
            if pattern and pattern != "preserve_source_name" and module.canonical_name:
                if not _matches_naming_pattern(pattern, artifact.path, module.canonical_name):
                    violations.append(
                        f"{module_id}.{kind}: la ruta {artifact.path!r} no cumple la "
                        f"convención {pattern!r} para el módulo "
                        f"canonical_name={module.canonical_name!r}."
                    )

    return violations


# ---------------------------------------------------------------------------
# Integración con DataWorkspace (Fase 6) -- reutiliza, no duplica
# ---------------------------------------------------------------------------

def resolve_artifact_path(
    manifest: WorkspaceManifest,
    module_id: str,
    artifact_kind: str,
    workspace: DataWorkspace,
    *,
    required: bool = False,
) -> Path:
    """Resuelve la ruta absoluta de un artefacto declarado en el manifest
    contra un `DataWorkspace` real. Reutiliza `DataWorkspace.resolve()`
    para toda la seguridad de rutas (protección de escape, rechazo de
    rutas absolutas) -- este módulo no reimplementa esa lógica.

    Nunca abre el archivo resuelto. `required=False` por defecto: este
    módulo no exige que el archivo físico exista salvo que quien llama lo
    pida explícitamente (p. ej. un test de integración con workspace
    temporal)."""
    module = manifest.get_module(module_id)
    artifact = module.artifact(artifact_kind)
    if artifact is None or artifact.path is None:
        raise WorkspaceManifestError(
            f"El módulo {module_id!r} no declara una ruta para el artefacto {artifact_kind!r}."
        )
    category = ARTIFACT_KIND_TO_CATEGORY[artifact_kind]
    return workspace.resolve(
        project=manifest.project.id,
        category=category,
        relative_path=artifact.path,
        required=required,
    )
