# Resource Resolver — capa genérica de resolución de artefactos

**Status:** Implemented (Sprint 8.5). Construido sobre `WorkspaceManifest`
(Sprint 8.4, ver `workspace-manifest.md`) y `DataWorkspace` (Sprint 7, ver
`external-data-workspace.md`) -- no los sustituye, los orquesta.

## 1. Propósito

Responder, de forma tipada y trazable, a la pregunta "dame el artefacto
`operational_csv` del módulo `drills`, obligatorio, comprobando que existe
físicamente" -- sin que quien pregunta tenga que conocer `DataWorkspace`,
las categorías de `config/data_workspace.yaml`, ni construir una ruta a
mano. Antes de este sprint, cada consumidor (hoy solo
`src/export/prototype/drills/pipeline.py`) resolvía sus propias rutas
llamando directamente a `DataWorkspace.resolve()` con constantes propias
(`HISTORICAL_CSV_CATEGORY`, ver § 10) -- sin un vocabulario común de
errores, sin distinguir "no declarado" de "declarado pero ausente" de
"ausente físicamente", y sin ningún punto único donde razonar sobre todos
los artefactos de un módulo a la vez.

## 2. Alcance

- Un `ResourceResolver` genérico (`src/core/resource_resolver.py`) que
  resuelve `ResourceRequest` -> `ResolvedResource` contra un
  `WorkspaceManifest` + `DataWorkspace` concretos.
- Errores tipados que distinguen cada motivo de fallo (§ 8).
- Soporte para el único recurso generado real conocido hoy: el CSV de
  salida del EMF (`contracts.emf`, Fase 5, § 12).
- Migración de la resolución del CSV de comparación de Drills
  (`HISTORICAL_CSV_CATEGORY`) a este mecanismo (§ 10, § 15).
- Un comando CLI aditivo, `workspace resolve` (§ 18).

## 3. Fuera de alcance

- No ejecuta SQL, no abre Excel, no lee CSV reales, no calcula filas ni
  columnas -- exclusivamente resolución de rutas y metadatos declarativos.
- No calcula checksums físicos (solo expone el `checksum` ya declarado en
  el manifest, si existe).
- No mueve, renombra ni crea archivos o directorios -- ni siquiera para un
  recurso generado (el patrón se resuelve, nunca se materializa).
- No generaliza `generated`/`path_pattern` a nivel de artefacto individual
  (ver § 12, § 19) -- solo cubre el caso real de `contracts.emf`.
- No implementa la comparación de tres vías (Template → Operational →
  EMF) de `project-contract-model.md` § 5 -- sigue siendo diseño, no
  código.
- No sustituye la resolución de SQL (`SourceSpec.sql_path`, repo-interno,
  git-versionado) ni de `entity_catalog_csv` de Drills (deuda ya conocida,
  ver `external-data-workspace.md` § 20) -- ninguno de los dos es hoy un
  recurso de `DataWorkspace` (ver § 15).

## 4. Arquitectura

```
EMF_DATA_ROOT (variable de entorno)
    │
    ▼
DataWorkspace              -- proyecto + categoría + ruta relativa -> Path
    │                          (seguridad de rutas: nunca reimplementada)
    ▼
WorkspaceManifest          -- qué proyecto, qué módulos, qué artefactos,
    │                          qué status, qué contrato representa cada uno
    ▼
ResourceResolver            -- ResourceRequest -> ResolvedResource
    │                          (declaración + resolución + existencia física,
    │                           tres responsabilidades separadas, ver § 16)
    ▼
Pipeline / Validation / Comparison
    (hoy: src/export/prototype/drills/pipeline.py, único consumidor real)
```

`ResourceResolver` no conoce Drills ni ningún objeto migrable concreto
(verificado por inspección, mismo criterio que `data_workspace.py`/
`workspace_manifest.py`, ver `tests/test_resource_resolver.py`): vive en
`src/core/` como infraestructura reutilizable.

## 5. `ResourceRequest`

```python
@dataclass(frozen=True)
class ResourceRequest:
    module_id: str
    artifact_type: str
    project_id: str | None = None        # None => proyecto del manifest resuelto
    required: bool = False
    require_physical_file: bool = False
    allowed_statuses: frozenset[str] | None = None
    allow_deprecated: bool = False
    purpose: str | None = None            # metadato informativo, no cambia la lógica
    execution_id: str | None = None       # solo para recursos generados, ver § 12
```

Nunca contiene credenciales, conexiones, `DataFrame`s ni contenido de
archivo -- solo coordenadas declarativas.

## 6. `ResolvedResource`

```python
@dataclass(frozen=True)
class ResolvedResource:
    project_id: str
    module_id: str
    artifact_type: str
    declared_path: str | None      # tal cual en el manifest (o el patrón, si generado)
    resolved_path: Path | None     # ruta absoluta ya resuelta, o None si no resoluble
    artifact_status: str           # ArtifactStatus, o "generated" para recursos generados
    exists: bool | None            # None = no comprobado; True/False = comprobado
    required: bool
    contract_role: str | None
    source: str | None
    description: str
    checksum: str | None           # declarado en el manifest, nunca calculado aquí
    warnings: tuple[str, ...]
    manifest_ref: str              # "<project>/<module>/<artifact_type>"
    generated: bool = False
```

## 7. Estados

| Estado del artefacto | Comportamiento de `resolve()` |
|---|---|
| `missing`, sin `path` | `required=True` → `ArtifactMissingError`. `required=False` → `ResolvedResource` con `resolved_path=None`, warning explícito. |
| `missing`, con `path` (inconsistencia rara) | Se resuelve la ruta igualmente; sigue siendo `missing` en `artifact_status`, con warning. |
| `optional` | Nunca lanza por ausencia física, ni siquiera con `required=True` -- solo warning. Es la única excepción a la regla de `required`. |
| `deprecated` | Lanza `DeprecatedArtifactError` salvo `allow_deprecated=True`. |
| `not_applicable` | Siempre lanza `InvalidArtifactStatusError` -- nunca es un recurso resoluble. |
| `present` / `validated` | Se resuelve con normalidad. |
| Recurso generado (§ 12) | Nunca lanza por ausencia física (ni con `required=True`): antes de ejecutar, no existir es el estado normal. |

## 8. Errores

Todos heredan de `ResourceResolutionError` (a su vez de `CoreError`, mismo
patrón que `DataWorkspaceError`/`WorkspaceManifestError`):

| Excepción | Motivo |
|---|---|
| `UnknownProjectError` | `project_id` de la petición no coincide con el proyecto del manifest resuelto. |
| `UnknownModuleError` | `module_id` no declarado en `manifest.modules`. |
| `UnknownArtifactError` | `artifact_type` fuera del vocabulario cerrado `ARTIFACT_KINDS`. |
| `ArtifactNotDeclaredError` | Kind válido, pero el módulo no lo declara en `artifacts`. |
| `ArtifactMissingError` | `required=True` y no hay ruta resoluble. |
| `PhysicalResourceMissingError` | `required=True` + `require_physical_file=True` y no existe en disco (nunca para `optional` ni para recursos generados). |
| `DeprecatedArtifactError` | `status=deprecated` sin `allow_deprecated=True`. |
| `InvalidArtifactStatusError` | `status=not_applicable`, o status fuera de `allowed_statuses`. |
| `ResourcePathError` | Falla la resolución de ruta contra `DataWorkspace` (categoría/proyecto desconocidos, escape), o falla la validación de un patrón/`execution_id` de recurso generado. |

Ningún mensaje de error incluye más que la propia ruta/identificador
involucrado -- nunca credenciales ni contenido.

## 9. Integración con el Manifest

`ResourceResolver` reutiliza `manifest.get_module()` y
`resolve_artifact_path()` de `workspace_manifest.py` -- no reimplementa la
carga ni la validación de forma del manifest, solo añade la capa de
petición/resultado tipado y las reglas de estado de § 7. Un
`ResourceResolver` está ligado a un único `WorkspaceManifest` (de un único
proyecto); para otro proyecto se construye otro resolver.

## 10. Integración con `DataWorkspace`

Toda resolución de ruta física pasa, sin excepción, por
`DataWorkspace.resolve()` -- la protección de rutas absolutas y de escape
(`..`) vive únicamente ahí (§ 17). `ResourceResolver` nunca concatena
rutas a mano ni usa `glob`/`rglob` para encontrar un archivo.

## 11. Recursos físicos

`require_physical_file=False` (por defecto): el resolver nunca toca el
filesystem más allá de construir la ruta -- `exists=None` en el resultado
("no comprobado", distinto de `False`). `require_physical_file=True`
comprueba `Path.is_file()` una sola vez, nunca recorre el workspace ni
calcula tamaño/hash/filas (Fase 10 del encargo: Manifest Validation,
Resource Resolution y Physical Validation son responsabilidades
separadas, nunca mezcladas).

## 12. Recursos generados

Alcance deliberadamente acotado al único caso real conocido: el CSV de
salida del EMF, declarado en `contracts.emf` del manifest
(`emf_generated: true`, `emf_output_pattern: "Drills_{execution_id}.csv"`
-- ya existía desde Sprint 8.4, sin motor de resolución hasta ahora). Se
activa cuando `artifact_type == "outputs"` y el módulo declara
`contracts.emf.generated`.

Placeholders soportados (cerrados, sin motor de plantillas general):
`{module}` (resuelto a `canonical_name` o `module_id`) y `{execution_id}`
(tomado de `ResourceRequest.execution_id`, obligatorio para este caso).
Cualquier otro placeholder (`{foo}`) lanza `ResourcePathError` al cargar
el patrón. `execution_id` se valida contra
`^[A-Za-z0-9_-]+$` -- rechaza separadores de ruta, `..`, espacios y
cualquier carácter que permita escapar del nombre de archivo resultante.
El archivo/directorio nunca se crea.

**No generalizado** a `artifact.generated`/`artifact.path_pattern` por
artefacto individual (mencionado como ejemplo conceptual en el encargo de
este sprint) -- "No Abstraction Without a Real Consumer": solo hay un
caso real hoy. Ver § 19 para el registro de esta decisión como deuda
técnica explícita, no como omisión.

## 13. Naming

La convención de `workspace-naming-convention.md` (`{module}.xlsx`,
`{module}.csv`, `preserve_source_name`, `{module}_{execution_id}.csv`) se
valida en `validate_manifest()` (Sprint 8.4) -- `ResourceResolver` no la
revalida ni la reinterpreta, solo resuelve la ruta ya declarada. La ruta
efectiva siempre está en el manifest; el resolver nunca adivina un nombre
ni usa `glob` para elegir "la versión más reciente" de `template_csv`
(que, por diseño, admite varias versiones coexistentes).

## 14. Contratos

`ResolvedResource.contract_role` expone el `contract_role` del artefacto
(`platform`/`project`/`emf`, ver `project-contract-model.md`) tal cual
está en el manifest -- el resolver no decide cuál es "el contrato
correcto" para ningún propósito; eso lo decide quien construye la
`ResourceRequest` (ver § 15).

## 15. Integración con Drills

Único consumidor real hoy. `src/export/prototype/drills/pipeline.py`
sustituye su antigua resolución directa por `DataWorkspace` (constantes
`HISTORICAL_CSV_PROJECT`/`HISTORICAL_CSV_CATEGORY`/
`HISTORICAL_CSV_RELATIVE_PATH`, categoría deprecated `csv_enablon`) por
una petición explícita al `operational_csv` (Project Contract) de
`drills`, vía `ResourceResolver` (ver § 8 "Criterios de aceptación" #12:
"Drills usa Project Contract para la comparación operativa" -- directriz
de este mismo sprint, alineada con `project-contract-model.md` § 2.2: "El
Project Contract es la referencia principal para validar el EMF").

**No existe todavía un `workspace.yaml` real** para este proyecto (solo
`examples/workspace/workspace.example.yaml`, una plantilla). Por eso
`pipeline.py::_build_drills_comparison_manifest()` construye, en código,
el fragmento mínimo de manifest que necesita (un único módulo, un único
artefacto) -- deliberadamente transitorio, documentado como deuda técnica
explícita en § 19, nunca importa el YAML de ejemplo como si fuera real.

Consecuencia práctica: la carpeta física consultada cambia de
`CSV_Enablon/` (Sprint 7, deprecated) a `CSV_Enablon_Operational/`
(Sprint 8.2+), y el nombre de archivo esperado cambia de
`Drills-22072026-41.csv` a `Drills.csv` (convención `{module}.csv` de
`CSV_Enablon_Operational/`, ver `workspace-naming-convention.md` § 4).
Ninguna carpeta contiene hoy un archivo real (§ 6 de
`project-contract-model.md`), así que el comportamiento observable no
cambia: la comparación sigue siendo opcional y sigue devolviendo "sin
comparación" hasta que alguien coloque un `Drills.csv` real ahí. **No se
mueve, copia ni renombra ningún archivo real por este cambio.**

Nota abierta, no resuelta por este sprint: el único archivo histórico
conocido, `Drills-22072026-41.csv`, encaja por su propio nombre en la
convención de `CSV_Enablon_Template/` (`<Modulo>-<DDMMAAAA>-<n>.csv`), no
en la de `CSV_Enablon_Operational/` -- si se confirma que ese archivo es
en realidad el Project Contract, es una decisión del usuario (colocarlo
como `Drills.csv` en `CSV_Enablon_Operational/`), nunca una inferencia de
este documento ni del código.

## 16. Compatibilidad

- `python main.py export drills ...` y `python main.py run --project
  moeve --object drills ...` siguen funcionando sin cambios de interfaz
  (ninguna opción nueva, ningún requisito nuevo).
- Sin `EMF_DATA_ROOT` declarado, o sin el archivo físico presente, el
  comportamiento es idéntico a antes de este sprint: la comparación se
  omite en silencio, nunca un error, nunca un fallback a `inputs/`.
- `workspace validate` no cambia; `workspace resolve` es aditivo.
- `resolve_artifact_path()` (Sprint 8.4) sigue existiendo y sigue siendo
  usada -- por `ResourceResolver` internamente y, sin cambios, por sus
  tests previos (`tests/test_workspace_manifest.py`).

## 17. Seguridad

- Ninguna ruta absoluta de un equipo concreto en `src/core/` ni en
  `pipeline.py` -- verificado por inspección.
- Protección de escape (`..`) heredada de `DataWorkspace.resolve()`,
  nunca reimplementada.
- `execution_id` de un recurso generado se valida contra un patrón
  cerrado (`^[A-Za-z0-9_-]+$`) antes de interpolarse en el patrón de
  nombre -- ver `tests/test_resource_resolver.py::test_generated_output_execution_id_con_intento_de_escape_lanza`.
  Placeholders desconocidos en el patrón se rechazan.
- Ningún mensaje de error revela credenciales ni contenido de archivo.
- El comando CLI `workspace resolve` no imprime nada del contenido del
  recurso -- solo metadatos declarativos.

## 18. Ejemplos

```python
from src.core.data_workspace import get_default_data_workspace
from src.core.workspace_manifest import WorkspaceManifestLoader
from src.core.resource_resolver import ResourceRequest, ResourceResolver

manifest = WorkspaceManifestLoader.load_from_path(Path("examples/workspace/workspace.example.yaml"))
resolver = ResourceResolver(manifest, get_default_data_workspace())

resolved = resolver.resolve(ResourceRequest(
    module_id="drills", artifact_type="operational_csv",
    required=False, require_physical_file=True,
))
if resolved.exists:
    ...  # resolved.resolved_path
```

CLI:

```
python main.py workspace resolve --manifest examples/workspace/workspace.example.yaml \
    --module drills --artifact operational_csv [--require-exists] [--allow-deprecated]
```

## 19. Deuda técnica

- `pipeline.py::_build_drills_comparison_manifest()` construye un
  manifest mínimo en código porque no existe un `workspace.yaml` real
  todavía -- en cuanto exista, debe sustituirse por
  `WorkspaceManifestLoader.load_from_path(...)` apuntando a él (ver § 15).
- Recursos generados acotados a `contracts.emf` (§ 12) -- generalizar a
  `artifact.generated`/`artifact.path_pattern` por artefacto queda
  pendiente hasta que exista un segundo caso real.
- `entity_catalog_csv` de Drills y el SQL de origen (`SourceSpec.sql_path`)
  siguen fuera del `ResourceResolver` -- el primero por decisión ya
  documentada en `external-data-workspace.md` § 20 (no migrado al
  workspace externo), el segundo porque vive en Git, no en
  `DataWorkspace` (ver § 3).
- El CLI `workspace resolve` no expone `--execution-id` -- no puede
  resolver hoy un recurso generado (`artifact_type=outputs`) desde la
  línea de comandos, solo desde código. Añadir la opción es una extensión
  aditiva de bajo riesgo, aplazada por no tener un caso de uso CLI real
  todavía (mismo principio de § 12).
- La clasificación real de `Drills-22072026-41.csv` (Platform vs. Project
  Contract) sigue sin confirmar (ver § 15) -- no resuelta por este
  sprint, igual que en `project-contract-model.md` § 4.

## 19.1 Sprint 8.6 — Module Registry

`ResourceResolver` sigue sin cambios. `ModuleDefinition.required_artifact_types`/
`optional_artifact_types` (`src/core/module_registry.py`) declaran QUÉ
`ARTIFACT_KINDS` necesita un módulo (mismo vocabulario cerrado que este
documento, reutilizado, nunca duplicado) -- pero no los resuelven: seguir
resolviéndolos de verdad sigue siendo trabajo exclusivo de
`ResourceResolver`. Ver `docs/01-architecture/module-registry.md` § 5.

## 19.2 Sprint 8.7 — Workspace Readiness Validator

`ResourceResolver` sigue sin cambios de comportamiento. Tiene un nuevo
consumidor genérico, `WorkspaceReadinessValidator`
(`src/core/readiness_validator.py`, ver
`docs/01-architecture/workspace-readiness-validator.md`), que llama a
`resolve()` siempre con `required=False` -- decide la severidad
(bloqueo/advertencia) él mismo a partir de `ArtifactStatus`, nunca deja que
una excepción del resolver la decida. Esto evita un caso real detectado en
la Fase 1 de ese sprint: un artefacto `status=present`/`path=None`
(git-tracked, resuelto vía `source: "git:..."`, como `sql`/`mapping` de
Drills) haría que `required=True` lanzara `ArtifactMissingError` de forma
incorrecta si se usara tal cual.

## 20. Criterios de aceptación

Ver `reports/executions/2026-07-28/Informe-Resource-Resolver-EMF.md` § 14
para el detalle verificado (tests, suite completa, git status/diff).
