# Module Registry — registro explícito de módulos ejecutables del EMF

**Status:** Implemented (Sprint 8.6). Implementa, con el vocabulario
`module_id` ya en uso desde Sprint 8.4, la pieza que
`extensibility-model.md` § 6 y `workspace-manifest.md` § 5 anticipaban
como "un futuro Module Registry de código" (relacionado con el
`ObjectRegistry` de Sprint 4.1, ver § 10).

## 1. Propósito

Responder, de forma tipada y auditable, a "¿qué módulos sabe ejecutar
este software, con qué capacidades, y cómo construyo su pipeline?" --
antes de este sprint esa pregunta se respondía con un `if object_type not
in ("drills",)` en `src/cli.py` y tres imports directos de
`core_adapters.py` de Drills en la ruta genérica del comando `run`.

## 2. Alcance

- `ModuleDefinition`/`ModuleCapabilities`/`ModuleRegistry` genéricos
  (`src/core/module_registry.py`).
- Vocabulario cerrado de capacidades (`ModuleCapability`) y de estado de
  implementación (`ModuleImplementationStatus`).
- Errores tipados (§ 17).
- `ensure_module_runnable()`: composición con `WorkspaceManifest` (Fase 11).
- Composition root (`src/bootstrap/module_registry.py`) que registra
  Drills como primer y único módulo ejecutable.
- Integración de la CLI genérica (`run`) con el registro; comandos
  aditivos de inspección (`modules list`/`modules show`).

## 3. Fuera de alcance

- No ejecuta ningún pipeline por sí mismo -- `get_pipeline_factory()`
  devuelve la factory, nunca la invoca (verificado por test, § "factory no
  ejecutada durante consulta").
- No descubre módulos dinámicamente (sin `importlib` sobre paquetes, sin
  reflexión, sin entry points) -- cada módulo se registra con una línea
  de código explícita y auditable en el composition root.
- No resuelve rutas de artefactos (`ResourceResolver`) ni declara qué
  recursos tiene un proyecto concreto (`WorkspaceManifest`) -- solo
  compone con ambos cuando hace falta (§ 4, § 5).
- No registra los 7 módulos restantes del Workspace Manifest de ejemplo
  (`safety_meetings`, `moc`, `bypass`, `events`, `ops`, `inspections`,
  `corrective_actions`) -- ninguno tiene `pipeline_factory` real (§ 16).

## 4. Separación respecto a `WorkspaceManifest`

`WorkspaceManifest` declara **qué recursos de datos tiene un proyecto
concreto** (`moeve`) y en qué estado -- es información por-proyecto.
`ModuleRegistry` declara **qué sabe ejecutar el software**, independiente
de cualquier proyecto -- el mismo `ModuleRegistry` serviría para un
segundo cliente que usara los mismos módulos. Los dos vocabularios de
estado son intencionalmente distintos y ortogonales (§ 9). La única
composición entre ambos es `ensure_module_runnable()` (§ 11 del encargo),
que nunca reimplementa `validate_manifest()` ni `get_module()` -- los
llama.

## 5. Separación respecto a `ResourceResolver`

`ResourceResolver` resuelve **dónde está** un artefacto concreto
(`operational_csv` de `drills` → una `Path`). `ModuleRegistry` no resuelve
rutas en absoluto -- `ModuleDefinition.required_artifact_types`/
`optional_artifact_types` declaran QUÉ TIPOS de artefacto necesita un
módulo (usando el mismo vocabulario cerrado `ARTIFACT_KINDS` de
`workspace_manifest.py`, reutilizado, no duplicado), nunca dónde
encontrarlos. Resolverlos de verdad sigue siendo trabajo exclusivo de
`ResourceResolver`.

## 6. Separación respecto a `StageRegistry`

`StageRegistry` registra **etapas de pipeline** (`query`, `canonicalize`,
`transform_and_export`, `evidence`) -- unidades de ejecución dentro de UN
pipeline. `ModuleRegistry` registra **módulos** -- la composición completa
de un objeto migrable (qué etapas, en qué orden, con qué configuración).
Un `ModuleDefinition.pipeline_factory` recibe un `StageRegistry` recién
creado y es responsable de poblarlo -- `ModuleRegistry` nunca guarda ni
posee un `StageRegistry` propio (verificado por
`tests/test_bootstrap_module_registry.py::test_stage_registry_no_se_duplica_en_module_registry`).

## 7. `ModuleDefinition`

```python
@dataclass(frozen=True)
class ModuleDefinition:
    module_id: str
    display_name: str
    version: str
    status: str                                  # ModuleImplementationStatus
    capabilities: ModuleCapabilities
    canonical_name: str | None = None
    aliases: frozenset[str] = frozenset()
    pipeline_factory: PipelineFactory | None = None
    supported_modes: frozenset[str] = frozenset()          # subconjunto de {"sample", "full"}
    required_artifact_types: frozenset[str] = frozenset()  # subconjunto de ARTIFACT_KINDS
    optional_artifact_types: frozenset[str] = frozenset()
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

Nunca contiene credenciales, rutas físicas, contenido de mappings,
`DataFrame`s, conexiones SQL ni datos de cliente -- solo metadatos
declarativos. Validado al construir (`__post_init__`): `status` dentro del
vocabulario cerrado; ningún módulo se declara alias de sí mismo;
`supported_modes`/`required_artifact_types`/`optional_artifact_types`
dentro de sus respectivos vocabularios cerrados; `required` y `optional`
nunca se solapan; un `status` ejecutable (`implemented`/`experimental`)
exige `pipeline_factory` real; un `status=planned` no debe declararla.

## 8. Capabilities

`ModuleCapability` (vocabulario cerrado, mismo patrón `clase + frozenset
ALL` que `ArtifactStatus`): `export`, `sample`, `full`, `evidence`,
`comparison`, `validation`, `manifest_driven_resources`, `legacy_cli`,
`canonicalization`, `mapping`, `import`.

`ModuleCapabilities` envuelve el conjunto declarado, validado contra ese
vocabulario al construir. `ModuleRegistry.supports(module_id, capability)`
consulta sin ejecutar nada; `ensure_capability()` lanza
`UnsupportedCapabilityError` si no la soporta -- pensado para código de
integración que necesita un fallo bloqueante.

**Ninguna capacidad se declara "porque existe un seam o adaptador"**:
Drills NO declara `canonicalization` aunque `DrillsCanonicalizeStage`
existe -- esa etapa es un *pass-through* documentado explícitamente como
seam mínimo hacia un futuro CDM (`core_adapters.py`), no reescribe ninguna
transformación real. Tampoco declara `import` -- este repositorio no
ejecuta cargas contra Enablon (CLAUDE.md).

## 9. Status model

Dos ejes ortogonales, nunca fundidos en un único vocabulario:

| | `ModuleImplementationStatus` (este documento) | `ModuleStatus` (`workspace-manifest.md`) |
|---|---|---|
| Pregunta | ¿Sabe el SOFTWARE ejecutar este módulo? | ¿En qué punto está este módulo PARA ESTE PROYECTO? |
| Valores | `implemented`, `experimental`, `planned`, `deprecated` | `planned`, `ready`, `blocked`, `in_progress`, `validated`, `deprecated` |
| Ejemplo real | Drills = `experimental` (código real, `prototype_status: review_only`) | Drills = `in_progress` en `workspace.example.yaml` (datos del proyecto todavía incompletos) |

Un módulo puede ser `implemented` en software y `planned` en un proyecto
concreto (código listo, datos del cliente sin llegar) -- son
independientes por diseño. `EXECUTABLE = {implemented, experimental}`:
solo estos dos exigen `pipeline_factory` real.

## 10. Aliases

Únicos globalmente (mismo espacio de nombres que `module_id` -- un alias
no puede colisionar con ningún `module_id` ni con otro alias ya
registrado). Drills registra exactamente `{"simulacros"}`, verificado
contra `config/exports/drills.yaml` (`module: simulacros`) y
`config/modules.yaml` (clave `simulacros`) -- evidencia directa, no
inferencia.

**Nota de verificación explícita** (Fase 8 del encargo pedía comprobar
"SM" antes de asumirlo): "SM" **no** se registró como alias. CLAUDE.md
usa "SM" para **Safety Meetings**, un módulo distinto ("Sistema
ITP/Prevención (Simulacros, SM, Eventos, Inspecciones, OPS)" -- los lista
por separado). Añadirlo como alias de Drills habría sido un error de
identificación real, no una simplificación -- ver
`tests/test_bootstrap_module_registry.py::test_drills_no_tiene_alias_sm`.

## 11. Registry

`ModuleRegistry`: instancia explícita (ADR-010, No Hidden State), mismo
criterio que `StageRegistry` -- quien la construye decide qué registrar.
API: `register(definition, *, overwrite=False)`, `get(module_id_or_alias)`,
`contains(...)`, `list_modules()` (orden determinista, alfabético),
`list_executable()`, `capabilities(...)`, `supports(...)`,
`ensure_capability(...)`, `get_pipeline_factory(...)`.

Reglas de registro: `module_id` único; alias únicos globalmente (contra
otros alias Y contra cualquier `module_id`); `canonical_name` único
cuando se declara; ningún duplicado se sobrescribe salvo
`overwrite=True` explícito (nunca silencioso); un módulo `deprecated` es
resoluble pero emite `logger.warning()` en cada `get()`.

## 12. Pipeline factories

```python
PipelineFactory = Callable[[ExecutionRequest, StageRegistry], tuple[PipelineDefinition, ExecutionContext]]
```

Recibe la petición y un `StageRegistry` recién creado por quien orquesta
(mismo contrato que `StageRegistry` ya exige); la factory registra sus
propias etapas en él y devuelve la `PipelineDefinition` + el
`ExecutionContext` listos para `PipelineOrchestrator.run()`. No incluye
`WorkspaceManifest`/`ResourceResolver` en la firma porque ningún módulo
real los necesita inyectados hoy (Drills los resuelve internamente
cuando le hacen falta, ver `resource-resolver.md` § 15) -- ampliar la
firma es una extensión aditiva para cuando exista un segundo caso real
("No Abstraction Without a Real Consumer", `extensibility-model.md` § 5).

## 13. Composition root

`src/bootstrap/module_registry.py` -- único lugar central que importa un
módulo funcional concreto (Drills) para registrarlo. `src/core/` no
importa nada de `src/bootstrap/` ni de `src.export`/`src.etl`/
`src.evidence` (verificado por
`tests/test_bootstrap_module_registry.py::test_core_module_registry_no_importa_drills_ni_export`).
`build_default_module_registry()` es el único punto de entrada: construye
un `ModuleRegistry` nuevo y registra Drills en él.

## 14. Integración CLI

`python main.py run --project ... --object <module_id_or_alias> ...`:

```
CLI → build_default_module_registry() → ensure_capability(object, "export")
    → ensure_capability(module_id, mode) → SQL Execution Guard (--allow-real-sql)
    → get_pipeline_factory(module_id) → pipeline_factory(request, StageRegistry())
    → PipelineOrchestrator.run()
```

**Sprint 8.6.1**: entre la resolución de capacidades y la construcción de
la petición se añadió el SQL Execution Guard (`--allow-real-sql`/
`EMF_ALLOW_REAL_SQL=1`, ver `docs/01-architecture/sql-execution-guard.md`)
-- deliberadamente DESPUÉS de las comprobaciones de `ModuleRegistry` (que
son baratas y sin efectos secundarios: un `--object` mal escrito da un
`UnknownModuleError` claro sin necesitar primero resolver la autorización
SQL) y ANTES de construir el `ExecutionRequest`/invocar la
`pipeline_factory` -- es la última puerta antes de cualquier trabajo real.
`ModuleRegistry` en sí no conoce el guard (siguen siendo capas
separadas); la composición vive en `src/cli.py`.

Ningún condicional específico de Drills queda en la ruta genérica de
`run` -- ni el `if object_type not in (...)` ni los imports directos de
`core_adapters.py` (ambos retirados de `src/cli.py`). `--object` acepta
`module_id` o cualquier alias registrado. `python main.py export drills
...` (comando legacy) sigue sin cambios -- sigue llamando directamente a
`pipeline.run()`, documentado como camino existente, no reemplazado (ver
`ModuleCapability.LEGACY_CLI`, que Drills declara precisamente para dejar
constancia de que ese camino sigue vivo en paralelo).

Comandos aditivos de solo lectura: `modules list`, `modules show
<module_id_or_alias>` (§ 18: nunca imprimen rutas ni credenciales).

## 15. Integración de Drills

`src/bootstrap/module_registry.py::_build_drills_definition()`:
`module_id="drills"`, `canonical_name="Drills"`, `status=experimental`
(no `implemented`: `config/exports/drills.yaml` declara
`prototype_status: review_only` -- el pipeline es real y ejecutable, pero
su CSV no está aprobado para carga en Enablon), `aliases={"simulacros"}`,
capacidades listadas en § 8, `required_artifact_types={"sql", "mapping"}`
(bloquean sample/full si faltan, mismo criterio que
`required_for_sample`/`required_for_full` del Workspace Manifest),
`optional_artifact_types={"operational_csv", "etl", "errors"}`.

## 16. Módulos futuros

`safety_meetings`, `moc`, `bypass`, `events`, `ops`, `inspections`,
`corrective_actions` (presentes en `workspace.example.yaml` con
`status=planned`) **no** se registran en el `ModuleRegistry` -- ninguno
tiene `pipeline_factory` real. Su presencia en el manifest de ejemplo
describe el ROADMAP del proyecto (qué se planea migrar), no lo que el
software sabe ejecutar hoy (verificado por
`test_modulos_futuros_del_manifest_no_estan_registrados`). Cuando alguno
tenga un pipeline real, se registra con una línea nueva en el composition
root -- nunca inventando una `pipeline_factory` de relleno.

## 17. Errores

Todos bajo `ModuleRegistryError(CoreError)`: `UnknownModuleError`,
`DuplicateModuleError`, `DuplicateModuleAliasError`,
`UnsupportedCapabilityError`, `ModuleNotImplementedError`,
`ModuleDisabledForProjectError`, `MissingPipelineFactoryError`.

`UnknownModuleError` reutiliza deliberadamente el mismo nombre que
`src.core.resource_resolver.UnknownModuleError`, en una jerarquía
independiente (`ModuleRegistryError`, no `ResourceResolutionError`) --
representan preguntas distintas ("¿el software sabe ejecutar este
módulo?" vs. "¿el manifest de un proyecto lo declara?"). Para "módulo no
declarado en el proyecto" se reutiliza `WorkspaceManifestError` tal cual
(ya cubre exactamente ese caso, `manifest.get_module()`) -- no se inventa
un tercer nombre para lo mismo.

## 18. Seguridad

Ningún `ModuleDefinition` contiene credenciales, rutas físicas ni
contenido de datos -- solo metadatos declarativos. `modules list`/`modules
show` nunca imprimen una ruta absoluta ni una variable de entorno
(verificado por test). `get_pipeline_factory()` nunca ejecuta la factory
-- solo la CLI, al construir realmente un `ExecutionContext` y llamar a
`PipelineOrchestrator.run()`, dispara ejecución real.

## 19. Extensibilidad

Añadir un segundo módulo real: (1) implementar su
`core_adapters.py`-equivalente (etapas + `pipeline_factory`) en su propio
paquete funcional; (2) añadir su `ModuleDefinition` al composition root;
(3) `src/core/` no cambia. Mismo principio que `extensibility-model.md`
§ 2 ya fijaba para el futuro `ObjectRegistry`: "el Core no cambia (el
Registry ya admite cualquier `object_id` sin código nuevo)".

## 20. Deuda técnica

- `ensure_module_runnable()` (composición con `WorkspaceManifest`) existe
  y está testeada, pero no está todavía conectada a ningún comando CLI
  real -- `run` hoy solo consulta `ModuleRegistry`, no un
  `WorkspaceManifest`. Conectar `--manifest` a `run` es una extensión
  aditiva de bajo riesgo, aplazada por no tener un caso de uso CLI real
  todavía (mismo principio que `resource-resolver.md` § 19 aplicó a
  `--execution-id`).
- La firma de `PipelineFactory` no recibe `WorkspaceManifest`/
  `ResourceResolver` -- ampliarla espera un segundo módulo real que lo
  necesite (§ 12).
- `version="0.1.0"` de Drills es una convención nueva de este sprint, sin
  precedente previo en el repositorio -- no hay todavía una política de
  versionado de módulos más allá de este primer valor.
- `modules show` no distingue en su salida los artefactos ya resueltos
  físicamente (eso seguiría siendo trabajo de `workspace resolve`,
  deliberadamente no duplicado aquí).

## 21. Criterios de aceptación

Ver `reports/executions/2026-07-28/Informe-Module-Registry-EMF.md` § 15
para el detalle verificado (tests, suite completa, git status/diff).
