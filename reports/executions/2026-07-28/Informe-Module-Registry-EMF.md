# Informe de ejecución — Sprint 8.6: Module Registry

**Fecha:** 2026-07-28
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Registro genérico de módulos ejecutables sobre el Framework
Core v1. Ningún acceso a SQL Server planeado; un incidente registrado y
corregido (§ 2).

## 1. Resumen ejecutivo

Se implementó `ModuleRegistry` (`src/core/module_registry.py`): un
registro explícito de módulos migrables ejecutables, con
`ModuleDefinition`/`ModuleCapabilities` tipados, vocabulario cerrado de
capacidades y de estado de implementación, y errores tipados. Un
composition root nuevo (`src/bootstrap/module_registry.py`) registra
Drills como único módulo ejecutable hoy, con el alias `simulacros`
(verificado contra `config/exports/drills.yaml`) y explícitamente SIN el
alias `SM` (verificado y descartado -- ver § 3, es Safety Meetings en
CLAUDE.md, un módulo distinto). El comando CLI genérico `python main.py
run` ya no contiene ningún condicional propio de Drills ni imports
directos de su `core_adapters.py` -- resuelve el módulo a través del
registro. Se añadieron los comandos de inspección `modules list`/`modules
show`. La suite pasó de 557 a 612 casos en verde (+55), 7 skipped sin
cambios. No se hizo ningún commit.

## 2. Estado inicial

- Rama `feature/drills-filtered-exports`, remoto correcto.
- `git diff --check`: sin errores de espacio en blanco.
- Único cambio automático: `.claude/settings.local.json` (permisos
  locales acumulados) — restaurado con `git restore` antes de empezar.
- Suite completa antes de empezar: **557 passed, 7 skipped** — confirma
  la referencia dada por el encargo.
- Sprints 8.4 y 8.5 confirmados sin commit, no tocados salvo extensión
  puntual de archivos ya compartidos (`src/cli.py`,
  `external-data-workspace.md`, ya extendidos en Sprint 8.5).
- **Incidente durante la Fase 10** (verificación manual de la CLI): se
  invocó `python main.py run --project moeve --object simulacros --mode
  sample ...` directamente en shell, sin el mock de `run_query` que sí
  usa la suite de tests -- este entorno SÍ tiene conectividad real a SQL
  Server (a diferencia de lo asumido inicialmente), y la ejecución
  extrajo 5 filas reales, generando `reports/20260728T083255Z/` con datos
  reales. Detectado de inmediato, comunicado explícitamente al usuario, y
  el directorio (nunca añadido a git, `git status` lo confirma) se borró
  con `rm -rf` antes de continuar. A partir de ese punto, toda
  verificación de CLI se hizo exclusivamente vía `--help`, `CliRunner`
  con `run_query` mockeado (mismo patrón que la suite existente), o
  `py_compile` -- nunca una invocación real sin mock.

## 3. Inventario de selección de módulos (Fase 1)

| Archivo | Función/clase | Selección actual (antes de este sprint) | Acoplamiento | Migrar ahora |
|---|---|---|---|---|
| `src/cli.py::run_pipeline` | `_CORE_SUPPORTED_OBJECT_TYPES = ("drills",)` + `if object_type not in (...)` | Tupla hardcoded de un elemento | Alto — único punto de decisión "¿qué objetos soporta el Core?", en la CLI | **Sí** — hecho |
| `src/cli.py` (imports de módulo) | `from src.export.prototype.drills.core_adapters import (build_drills_pipeline_definition, build_execution_context, register_drills_stages)` | Import directo e incondicional de Drills en la ruta genérica `run` | Alto — la CLI genérica conocía Drills por nombre | **Sí** — hecho |
| `src/export/prototype/drills/core_adapters.py::register_drills_stages` | Registro de etapas en `StageRegistry` | Explícito, ya correcto (Sprint anterior) | Ninguno — patrón ya alineado con el principio de registro explícito | No — se reutiliza tal cual desde la nueva `pipeline_factory` |
| `src/export/prototype/drills/core_adapters.py::OBJECT_TYPE` | Constante `"drills"` | Constante local del módulo funcional | Ninguno | No — se reutiliza como `module_id` en el composition root, no se duplica |
| `config/modules.yaml` | Clave `simulacros` | Análisis manual consolidado (hallazgos, volumetría) | Ninguno — no es código ejecutable | No aplica — fuente de evidencia para el alias, no un punto de selección de código |
| `config/exports/drills.yaml` | `object_id: drills`, `module: simulacros` | Configuración declarativa ya usada por `config.py` | Ninguno | No aplica — pero confirma `module_id`/alias con evidencia directa |
| `src/export/prototype/drills/pipeline.py::run` | Llamada directa, sin capa de selección | Invocación directa desde `export drills` (comando legacy) | Bajo — deliberadamente fuera del alcance de este sprint | Mantener por compatibilidad (`legacy_cli`, ver `ModuleCapability.LEGACY_CLI`) |
| `src/core/registry.py::StageRegistry` | Registro de *etapas*, no de módulos | Ya explícito, ya correcto | Ninguno | No aplica — capa distinta, no se duplica (ver § 6 de `module-registry.md`) |
| `examples/workspace/workspace.example.yaml` | 8 módulos declarados (`drills` + 7 `planned`) | Declarativo, sin código ejecutable asociado | Ninguno | No aplica a `ModuleRegistry` — es responsabilidad de `WorkspaceManifest`, orthogonal (§ 9) |

Clasificación: **migrar ahora** → los dos puntos de `src/cli.py`. **No
aplica** → todo lo demás (o ya estaba correctamente explícito, o
pertenece a una capa distinta que no debe duplicarse). Ningún `if module
==`/`if object_type ==` adicional se encontró en el resto de `src/`
(grep exhaustivo, ver metodología completa en el hilo de trabajo).

## 4. Arquitectura

```
WorkspaceManifest → declara recursos del proyecto
ResourceResolver  → resuelve recursos declarados
ModuleRegistry    → resuelve la implementación ejecutable del módulo
PipelineOrchestrator → ejecuta el pipeline registrado
```

`ModuleRegistry` no importa Drills ni `src.export`/`src.etl`/
`src.evidence` (verificado por test arquitectónico, § 14). El único lugar
que sí los importa es el composition root, `src/bootstrap/module_registry.py`.

## 5. Modelo Python

- `ModuleDefinition` (frozen dataclass): `module_id`, `display_name`,
  `version`, `status`, `capabilities`, `canonical_name`, `aliases`,
  `pipeline_factory`, `supported_modes`, `required_artifact_types`,
  `optional_artifact_types`, `description`, `metadata`.
- `ModuleCapabilities`: envuelve un `frozenset[str]` validado contra
  `ModuleCapability.ALL`; expone `supports()`.
- `ModuleRegistry`: `register`, `get`, `contains`, `list_modules`,
  `list_executable`, `capabilities`, `supports`, `ensure_capability`,
  `get_pipeline_factory`.
- `ensure_module_runnable()`: función libre que compone `ModuleRegistry` +
  `WorkspaceManifest` (Fase 11), sin que `ModuleRegistry` dependa de
  `WorkspaceManifest` para su propio funcionamiento básico.

## 6. Capabilities

Vocabulario cerrado (`ModuleCapability`, 11 valores): `export`, `sample`,
`full`, `evidence`, `comparison`, `validation`,
`manifest_driven_resources`, `legacy_cli`, `canonicalization`, `mapping`,
`import`. Drills declara 9 de las 11 -- **no** `canonicalization`
(`DrillsCanonicalizeStage` es un *pass-through* documentado, no
transformación real) ni `import` (el repositorio no ejecuta cargas
contra Enablon, CLAUDE.md). Ningún módulo registrado declara `import` hoy
(verificado por test).

## 7. Status

Dos vocabularios ortogonales, nunca fundidos: `ModuleImplementationStatus`
(software: `implemented`/`experimental`/`planned`/`deprecated`) vs.
`ModuleStatus` de `workspace_manifest.py` (proyecto:
`planned`/`ready`/`blocked`/`in_progress`/`validated`/`deprecated`).
Drills = `experimental` en software (código real,
`prototype_status: review_only`) frente a `in_progress` en el ejemplo de
proyecto -- valores distintos, a propósito, en ejes distintos.

## 8. Registry

Reglas de registro implementadas y testeadas: `module_id` único; alias
únicos globalmente (contra otros alias Y contra cualquier `module_id`,
en ambas direcciones); `canonical_name` único cuando se declara; ningún
duplicado se sobrescribe salvo `overwrite=True` explícito; `deprecated`
resoluble con `logger.warning()`; listado (`list_modules()`)
alfabético, determinista.

## 9. Composition root

`src/bootstrap/module_registry.py` -- único fichero que importa
`src.export.prototype.drills.core_adapters` para construir el
`ModuleDefinition` de Drills y registrarlo. `build_default_module_registry()`
es el único punto de entrada.

## 10. Drills

`module_id="drills"`, `canonical_name="Drills"`,
`display_name="Drills (Business Continuity Management / Simulacros)"`,
`version="0.1.0"`, `status=experimental`, `aliases={"simulacros"}` (**sin**
`"SM"` -- verificado explícitamente contra CLAUDE.md antes de
descartarlo, ver § 3), `supported_modes={"sample","full"}`,
`required_artifact_types={"sql","mapping"}`,
`optional_artifact_types={"operational_csv","etl","errors"}`.
`pipeline_factory` adapta exactamente el flujo que antes vivía inline en
`src/cli.py::run_pipeline` (mismo comportamiento, ahora detrás de un
registro).

## 11. CLI

`run` ahora: `build_default_module_registry()` →
`ensure_capability(object, "export")` →
`ensure_capability(module_id, mode)` → `get_pipeline_factory(module_id)`
→ `pipeline_factory(request, StageRegistry())` →
`PipelineOrchestrator.run()`. `--object` acepta `module_id` o alias
(`drills` o `simulacros`, verificado). `export drills` (legacy) sin
cambios. Nuevos comandos de solo lectura: `modules list`, `modules show
<module_id_or_alias>` — nunca imprimen rutas físicas ni credenciales
(verificado por test).

## 12. Integración con Manifest

`ensure_module_runnable(registry, module_id, manifest=..., capability=...)`
implementa el orden exacto de la Fase 11: (1) `ModuleRegistry.get()` →
`UnknownModuleError`; (2) si se pasa manifest, `manifest.get_module()`
(reutiliza `WorkspaceManifestError` tal cual, sin inventar un error
nuevo para lo mismo); (3) `enabled=False` → `ModuleDisabledForProjectError`;
(4) `ensure_capability()` → `UnsupportedCapabilityError`. Implementada y
testeada, **no conectada todavía a ningún comando CLI real** (`run` hoy
solo consulta `ModuleRegistry`) -- deuda técnica explícita, § 20.

## 13. Integración con Resolver

Sin integración directa de código: `ModuleDefinition.required_artifact_types`/
`optional_artifact_types` usan el mismo vocabulario cerrado
(`ARTIFACT_KINDS`) que `ResourceResolver`/`WorkspaceManifest`, reutilizado
vía import, nunca duplicado -- pero `ModuleRegistry` no resuelve rutas por
sí mismo en ningún punto (responsabilidad exclusiva de `ResourceResolver`).

## 14. Tests

Nuevos:

- `tests/test_module_registry.py` — 36 tests (registro válido, module_id/
  alias duplicados en sus 3 variantes, canonical_name duplicado, módulo
  desconocido, alias, listado determinista, capabilities/supports/
  ensure_capability, capability desconocida en 2 puntos, planned sin
  factory, planned CON factory -- error, implemented/experimental sin
  factory -- error, deprecated con warning, factory registrada sin
  ejecutarse, `list_executable`, integración completa con
  `ensure_module_runnable` en sus 5 variantes, validaciones adicionales
  de `ModuleDefinition`).
- `tests/test_bootstrap_module_registry.py` — 11 tests (prueba
  arquitectónica de no-import de Drills en Core, no duplicación de
  `StageRegistry`, Drills registrado y ejecutable, alias `simulacros`,
  ausencia explícita de alias `SM`, capacidades demostrables únicamente,
  ningún módulo declara `import`, los 7 módulos futuros NO registrados,
  `pipeline_factory` construye definition/context sin SQL real y sin
  crear carpetas, factory no ejecutada por consultarla).
- `tests/test_cli_modules.py` — 8 tests (`modules list`/`show`, salida
  sin secretos/rutas, determinismo, alias, módulo desconocido, no rompe
  comandos existentes).

Modificado: `tests/test_drills_core_pipeline.py` — 1 test adaptado
(`test_cli_run_rechaza_objeto_no_soportado`: el mensaje de error cambió
de un `if` propio de la CLI a `UnknownModuleError` del registro, mismo
comportamiento observable -- exit code ≠ 0 -- distinto texto).

## 15. Resultados

```
557 passed, 7 skipped   (referencia inicial, confirmada al empezar)
612 passed, 7 skipped   (al terminar -- +55, 0 nuevos skipped, 0 fallos)
```

`py_compile` sin errores. CLI verificada con `--help` en todos los
comandos y con `CliRunner` (SQL mockeado) para los casos de éxito/error.
Ningún acceso real a SQL Server tras el incidente de § 2.

## 16. Compatibilidad

- `python main.py export drills ...` sin cambios de interfaz ni de
  comportamiento (camino legacy, `ModuleCapability.LEGACY_CLI` documenta
  su existencia continuada).
- `python main.py run --object drills ...` mismo comportamiento
  observable; `--object simulacros` ahora también funciona (antes no
  existía ningún alias).
- `python main.py run --object <no-registrado>` sigue devolviendo exit
  code ≠ 0, con mensaje distinto (más específico: `UnknownModuleError`).
- `workspace validate`/`workspace resolve` sin cambios.

## 17. Archivos creados

- `src/core/module_registry.py`
- `src/bootstrap/__init__.py`
- `src/bootstrap/module_registry.py`
- `docs/01-architecture/module-registry.md`
- `tests/test_module_registry.py`
- `tests/test_bootstrap_module_registry.py`
- `tests/test_cli_modules.py`
- `reports/executions/2026-07-28/Informe-Module-Registry-EMF.md` (+ `.txt`)

## 18. Archivos modificados

- `src/cli.py` (imports de Drills retirados de `run_pipeline`; comando
  `modules` añadido)
- `tests/test_drills_core_pipeline.py` (1 test adaptado)
- `docs/01-architecture/framework-core-v1.md` (§ 11, § 20 -- punteros)
- `docs/01-architecture/workspace-manifest.md` (§ 5, § 6 -- corrección de
  contenido desactualizado por Sprint 8.5/8.6, con el texto original
  tachado por trazabilidad)
- `docs/01-architecture/resource-resolver.md` (§ 19.1 -- puntero)
- `docs/01-architecture/extensibility-model.md` (§ 6 -- puntero)
- `docs/07-developer-guide/getting-started.md` (tabla § 4 corregida y
  ampliada -- el Core ya existe, contradiciendo lo que decía antes)

No se modificaron `src/export/prototype/drills/pipeline.py` ni
`tests/test_drills_data_workspace_integration.py` EN ESTE SPRINT (sus
diffs pendientes en `git status` son de Sprint 8.5, ya informados el
2026-07-28 en `Informe-Resource-Resolver-EMF.md`).

## 19. Riesgos

- El mensaje de error de `run --object <no soportado>` cambió de texto
  (aunque no de exit code) -- cualquier script externo que hiciera
  `grep` sobre "no soportado" literal dejaría de coincidir. Mitigado:
  ningún script de este repositorio lo hacía (verificado por grep), y el
  nuevo mensaje es más preciso (nombra el tipo de excepción).
- `ensure_module_runnable()` no está conectado a la CLI todavía --
  `run` no valida hoy si un módulo está `enabled` en un manifest de
  proyecto real (porque no toma `--manifest`) -- mismo perfil de riesgo
  que ya existía antes de este sprint (la CLI tampoco lo hacía).

## 20. Deuda técnica

- `ensure_module_runnable()` implementada y testeada, sin consumidor CLI
  real todavía.
- `PipelineFactory` no recibe `WorkspaceManifest`/`ResourceResolver` --
  extensión aditiva pendiente de un segundo módulo real.
- `version="0.1.0"` de Drills es una convención nueva sin política de
  versionado de módulos más amplia todavía.
- El incidente de § 2 revela que este entorno de trabajo SÍ tiene
  conectividad real a SQL Server (contradice la nota de CLAUDE.md
  "este entorno de análisis no tiene conectividad de red directa a SQL
  Server") -- recomendado actualizar esa nota o confirmar con el usuario
  si cambió recientemente.

## 21. Propuesta de commits (NO ejecutados -- requieren aprobación explícita)

Tres sprints (8.4, 8.5, 8.6) siguen sin commit. Se recomienda **mantener
commits separados por sprint** (consistente con lo ya recomendado en
Sprint 8.5), en este orden (cada uno deja el repositorio funcionando):

**Commit 1 — Sprint 8.4 (Workspace Manifest):** sin cambios respecto a
lo ya propuesto en `Informe-Workspace-Manifest-EMF.md` (2026-07-27).

**Commit 2 — Sprint 8.5 (Resource Resolver):** sin cambios respecto a lo
ya propuesto en `Informe-Resource-Resolver-EMF.md` (2026-07-28), salvo
que ahora incluye también las correcciones de § 5/§ 6 de
`workspace-manifest.md` hechas en Sprint 8.6 (ver nota abajo).

**Commit 3 — Sprint 8.6 (Module Registry), este incremento:**

```
feat(core): add explicit ModuleRegistry over the Framework Core

Adds ModuleRegistry/ModuleDefinition/ModuleCapabilities
(src/core/module_registry.py) with typed errors and a closed capability
vocabulary. Adds the composition root (src/bootstrap/module_registry.py)
that registers Drills as the sole executable module, with a verified
"simulacros" alias (and explicitly not "SM", which is Safety Meetings).
Removes the hardcoded object_type check and direct Drills imports from
the generic `run` CLI command in favor of ModuleRegistry lookups. Adds
`modules list`/`modules show` inspection commands.
```

Archivos: `src/core/module_registry.py`, `src/bootstrap/`, `src/cli.py`
(hunks de `modules`/`run_pipeline`), `tests/test_module_registry.py`,
`tests/test_bootstrap_module_registry.py`, `tests/test_cli_modules.py`,
`tests/test_drills_core_pipeline.py`,
`docs/01-architecture/module-registry.md`,
`docs/01-architecture/framework-core-v1.md`,
`docs/01-architecture/extensibility-model.md`,
`docs/07-developer-guide/getting-started.md`,
`reports/executions/2026-07-28/Informe-Module-Registry-EMF.md` (+`.txt`).

**Nota de solape:** `docs/01-architecture/workspace-manifest.md` § 5/§ 6
se corrigieron en este sprint porque describían un Module Registry/
Resource Resolver inexistentes -- ese archivo ya pertenece,
mayoritariamente, al commit de Sprint 8.4; se recomienda incluir ESTE
hunk concreto (§ 5/§ 6) en el commit de Sprint 8.6 en su lugar (`git add
-p`), ya que documenta una decisión de este sprint, no de aquel.

**Excluir de cualquier commit:** `.claude/settings.local.json`.

## 22. `git diff --check`

Sin errores de espacio en blanco (exit code 0) -- solo warnings de
conversión de fin de línea LF→CRLF de Git en Windows.

## 23. `git status --short` (al terminar este informe)

```
 M .claude/settings.local.json
 M config/data_workspace.yaml
 M docs/01-architecture/extensibility-model.md
 M docs/01-architecture/external-data-workspace.md
 M docs/01-architecture/framework-core-v1.md
 M docs/07-developer-guide/getting-started.md
 M src/cli.py
 M src/export/prototype/drills/pipeline.py
 M tests/test_drills_core_pipeline.py
 M tests/test_drills_data_workspace_integration.py
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/module-registry.md
?? docs/01-architecture/project-contract-model.md
?? docs/01-architecture/resource-resolver.md
?? docs/01-architecture/workspace-manifest.md
?? docs/01-architecture/workspace-naming-convention.md
?? docs/01-architecture/workspace-validation-checklist.md
?? docs/07-developer-guide/drills-real-data-inventory.md
?? examples/
?? reports/executions/2026-07-27/...
?? reports/executions/2026-07-28/
?? src/bootstrap/
?? src/core/module_registry.py
?? src/core/resource_resolver.py
?? src/core/workspace_manifest.py
?? tests/test_bootstrap_module_registry.py
?? tests/test_cli_modules.py
?? tests/test_cli_workspace_resolve.py
?? tests/test_cli_workspace_validate.py
?? tests/test_module_registry.py
?? tests/test_resource_resolver.py
?? tests/test_workspace_manifest.py
```

(`src/export/prototype/drills/pipeline.py` y
`tests/test_drills_data_workspace_integration.py` son cambios de Sprint
8.5, ya informados; `config/data_workspace.yaml` y varios `docs/*.md`/
`examples/` son de Sprint 8.4.)

## 24. `git diff --stat` (archivos tocados por Sprint 8.6)

```
 src/core/module_registry.py                nuevo (~370 líneas)
 src/bootstrap/__init__.py                   nuevo
 src/bootstrap/module_registry.py            nuevo (~100 líneas)
 src/cli.py                                  +~85 -~15
 tests/test_module_registry.py               nuevo (~290 líneas)
 tests/test_bootstrap_module_registry.py     nuevo (~155 líneas)
 tests/test_cli_modules.py                   nuevo (~80 líneas)
 tests/test_drills_core_pipeline.py          +~4 -~2
 docs/01-architecture/module-registry.md     nuevo (~250 líneas)
 docs/01-architecture/framework-core-v1.md   +~18
 docs/01-architecture/workspace-manifest.md  +~15 -~15 (corrección)
 docs/01-architecture/resource-resolver.md   +~8
 docs/01-architecture/extensibility-model.md +~9
 docs/07-developer-guide/getting-started.md  +~4 -~1
```

## 25. Recomendación del siguiente paso

Sprint 8.6 completo según los criterios de aceptación del encargo.
Siguientes pasos recomendados, en orden de valor: (a) confirmar con el
usuario si este entorno debe seguir teniendo conectividad real a SQL
Server (§ 20, contradice CLAUDE.md) y actualizar esa nota si es
intencional; (b) considerar conectar `ensure_module_runnable()` a `run`
con un `--manifest` opcional cuando exista un caso de uso real que lo
necesite; (c) proceder con los tres commits propuestos en § 21, en orden,
tras revisión del usuario.
