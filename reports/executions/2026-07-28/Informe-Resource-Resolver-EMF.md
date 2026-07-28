# Informe de ejecución — Sprint 8.5: Resource Resolver

**Fecha:** 2026-07-28
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Capa genérica de resolución de artefactos sobre el
Workspace Manifest (Sprint 8.4) y `DataWorkspace` (Sprint 7). Ninguna
migración real ejecutada, ningún dato real leído, ningún commit creado.

## 1. Resumen ejecutivo

Se implementó `ResourceResolver` (`src/core/resource_resolver.py`): una
capa genérica que resuelve `ResourceRequest` → `ResolvedResource` contra
un `WorkspaceManifest` + `DataWorkspace`, con errores tipados, soporte de
recursos generados (el CSV de salida del EMF) y un comando CLI aditivo
(`workspace resolve`). Como parte del mismo incremento se eliminó la
deuda `HISTORICAL_CSV_CATEGORY` de `src/export/prototype/drills/pipeline.py`:
la comparación opcional de Drills ahora pide explícitamente el artefacto
`operational_csv` (Project Contract), no la categoría deprecated
`csv_enablon`. La suite de tests pasó de 513 a 557 casos en verde (+44,
sin ningún test previo modificado en su intención, solo renombrado donde
la propia función cambió de nombre), 7 skipped sin cambios. No se hizo
ningún commit.

## 2. Estado inicial

- Rama `feature/drills-filtered-exports`, remoto
  `origin` → `github.com/eduardovelasquezl/enablon-migration-framework`
  (fetch/push), correctos.
- `git diff --check`: sin errores de espacio en blanco.
- Único cambio automático detectado: `.claude/settings.local.json`
  (permisos locales acumulados) — restaurado con `git restore` antes de
  empezar, tal como pide el encargo. Ha vuelto a acumular permisos
  durante esta misma sesión (uso normal de la herramienta) — no forma
  parte de este incremento, no debe commitearse.
- Suite completa antes de empezar: **513 passed, 7 skipped** — confirma
  la referencia dada por el encargo.
- Cambios de Sprint 8.4 confirmados sin commit (`config/data_workspace.yaml`,
  `docs/01-architecture/external-data-workspace.md`, `src/cli.py`,
  `src/core/workspace_manifest.py`, `examples/workspace/`, tests y
  reports asociados) — no se tocaron ni se mezclaron con este incremento
  salvo donde Sprint 8.5 necesitaba extender el mismo archivo (`src/cli.py`,
  `external-data-workspace.md`, ver § 16/§ 17).

## 3. Inventario de rutas (Fase 1)

| Archivo | Función/clase | Recurso | Resolución actual (antes de este sprint) | Riesgo | Migrar ahora |
|---|---|---|---|---|---|
| `src/export/prototype/drills/pipeline.py` | `_resolve_historical_csv_path` + `HISTORICAL_CSV_PROJECT/CATEGORY/RELATIVE_PATH` | CSV de comparación de Drills | Llamada directa a `DataWorkspace.resolve()` con categoría deprecated `csv_enablon` | Alto — deuda explícitamente nombrada por el encargo de este sprint | **Sí** — hecho (§ 10) |
| `src/core/workspace_manifest.py` | `resolve_artifact_path()` | Cualquier artefacto de un manifest | Ya reutiliza `DataWorkspace.resolve()`, sin tipado de petición/resultado ni reglas de estado | Bajo — ya correcto, solo le faltaba una capa encima | Reutilizado internamente por `ResourceResolver`, no duplicado |
| `src/core/data_workspace.py` | `DataWorkspace.resolve()` | Cualquier ruta física del workspace externo | Correcto, base de todo lo demás | Ninguno | No — se mantiene como única fuente de seguridad de rutas |
| `src/cli.py` | grupo `workspace` | — | Solo `validate` existía | Ninguno | Extendido (aditivo): `workspace resolve` |
| `src/export/prototype/drills/config.py` | `SourceSpec.sql_path` | SQL de origen | `PROJECT_ROOT / sql_file`, repo-interno, git-versionado | Ninguno — no es un recurso de `DataWorkspace` | No aplica — fuera del alcance de `ResourceResolver` (§ 3 del diseño) |
| `src/export/prototype/drills/mappings.py` | `get_entity_catalog` (vía `reference_data.entity_catalog_csv`) | Catálogo de entidad de Simulacros | `PROJECT_ROOT`-relativo, `inputs/entity_catalog/`, gitignored | Bajo — deuda ya documentada y deliberadamente aplazada (`external-data-workspace.md` § 20) | No — se mantiene la decisión previa, no se fuerza sin evidencia nueva |
| `src/evidence/collector.py` | `resolve_run_dir`/`load_run` | Directorio de una ejecución local (`outputs/prototype/drills/<timestamp>`) | `Path.resolve()` sobre `outputs/` del propio repo | Ninguno — dominio distinto (ejecuciones locales, no workspace externo) | No aplica |
| `src/analysis/query_analyzer.py` | `review_query_directory` | Ficheros `.sql` de `sql/source_queries/` | `dir_path.glob("*.sql")` | Ninguno — herramienta de análisis puntual, no pipeline de resolución en tiempo de ejecución | No aplica (solo test/análisis) |
| `src/config/loader.py` | `PROJECT_ROOT`, `load_yaml` | Ficheros de configuración del propio repo | `Path(__file__).resolve()` | Ninguno | No aplica — no es un recurso de datos del workspace externo |

Clasificación por archivo: **migrar ahora** → `pipeline.py` (único caso
real). **Mantener temporalmente** → `entity_catalog_csv` (deuda ya
documentada, sin evidencia nueva que justifique moverla ahora). **No
aplica** → SQL (repo-interno), `evidence/collector.py` (dominio distinto,
ejecuciones locales), `query_analyzer.py` (herramienta de análisis, no
pipeline), `config/loader.py` (configuración del propio repo).

## 4. Diseño

```
EMF_DATA_ROOT → DataWorkspace → WorkspaceManifest → ResourceResolver → Pipeline/Validation/Comparison
```

`ResourceResolver` no conoce Drills ni ningún objeto migrable concreto —
vive en `src/core/`, reutiliza `resolve_artifact_path()`/`DataWorkspace.resolve()`
para toda la seguridad de rutas, nunca la reimplementa. Ver
`docs/01-architecture/resource-resolver.md` para el diseño completo
(20 secciones, según lo pedido).

## 5. Modelo Python

- `ResourceRequest` (frozen dataclass): `module_id`, `artifact_type`,
  `project_id`, `required`, `require_physical_file`, `allowed_statuses`,
  `allow_deprecated`, `purpose`, `execution_id`.
- `ResolvedResource` (frozen dataclass): `project_id`, `module_id`,
  `artifact_type`, `declared_path`, `resolved_path`, `artifact_status`,
  `exists`, `required`, `contract_role`, `source`, `description`,
  `checksum`, `warnings`, `manifest_ref`, `generated`.
- `ResourceResolver.resolve(request) -> ResolvedResource`.

## 6. Errores

9 excepciones tipadas, todas bajo `ResourceResolutionError(CoreError)`:
`UnknownProjectError`, `UnknownModuleError`, `UnknownArtifactError`,
`ArtifactNotDeclaredError`, `ArtifactMissingError`,
`PhysicalResourceMissingError`, `DeprecatedArtifactError`,
`InvalidArtifactStatusError`, `ResourcePathError`. Detalle de motivo por
excepción en `resource-resolver.md` § 8.

## 7. Resolución de recursos

Tres responsabilidades separadas, nunca mezcladas (Fase 10 del encargo):
declaración (¿el manifest lo declara?), resolución (¿a qué ruta
absoluta?), existencia física (¿está en disco?, solo si se pide
explícitamente). Reglas de estado completas en `resource-resolver.md` § 7.

## 8. Recursos generados

Acotado al único caso real conocido: el CSV de salida del EMF
(`contracts.emf.generated`/`emf_output_pattern`, ya declarado desde
Sprint 8.4). Placeholders cerrados (`{module}`, `{execution_id}`),
`execution_id` validado contra `^[A-Za-z0-9_-]+$` (rechaza `..`,
separadores de ruta, espacios). Nunca crea archivo ni directorio. No se
generalizó a `artifact.generated`/`artifact.path_pattern` por artefacto
individual — registrado como deuda técnica explícita (§ 18), no como
omisión (principio "No Abstraction Without a Real Consumer").

## 9. Naming

Sin cambios de comportamiento: `validate_manifest()` (Sprint 8.4) sigue
siendo quien valida la convención de nombre; `ResourceResolver` no la
reinterpreta ni usa `glob` para elegir versión.

## 10. Migración de `HISTORICAL_CSV_CATEGORY`

`src/export/prototype/drills/pipeline.py`:

- Eliminadas las constantes `HISTORICAL_CSV_PROJECT`,
  `HISTORICAL_CSV_CATEGORY` (`"csv_enablon"`, deprecated),
  `HISTORICAL_CSV_RELATIVE_PATH`, y la función
  `_resolve_historical_csv_path()`.
- Añadidas `_COMPARISON_PROJECT_ID`/`_COMPARISON_MODULE_ID`/
  `_COMPARISON_ARTIFACT_TYPE`/`_COMPARISON_CANONICAL_NAME`,
  `_build_drills_comparison_manifest()` (manifest mínimo construido en
  código — no existe todavía un `workspace.yaml` real, ver § 15) y
  `_resolve_comparison_csv_path()`, que pide `operational_csv` vía
  `ResourceResolver`.
- **Cambio de comportamiento físico**: la carpeta consultada pasa de
  `CSV_Enablon/Drills-22072026-41.csv` a
  `CSV_Enablon_Operational/Drills.csv`. Ninguna de las dos carpetas
  contiene hoy un archivo real, así que el comportamiento observable no
  cambia (la comparación sigue devolviendo "omitida" en ambos casos) —
  confirmado por
  `tests/test_drills_data_workspace_integration.py::test_fichero_en_categoria_deprecated_csv_enablon_no_se_resuelve`
  (un archivo colocado en la carpeta vieja ya NO se resuelve, por diseño).
- Directiva de acatamiento explícito de este sprint: "Drills usa Project
  Contract para la comparación operativa" — implementado pidiendo
  `operational_csv`, nunca `template_csv`.

## 11. Integración Drills

Único consumidor real. Prioridad 1 (CSV operativo de comparación) —
implementada. Prioridad 2 (catálogo de entidad) — **no migrada**,
decisión previa ya documentada mantenida sin cambios (§ 3). Prioridad 3
(SQL) — **no migrada**, vive en Git, no es un recurso de `DataWorkspace`
(§ 3). Ningún archivo real movido. `python main.py export drills ...` y
`python main.py run --project moeve --object drills ...` verificados con
`--help` (sin acceso a SQL Server real en este entorno) — interfaz sin
cambios.

## 12. CLI

Comando aditivo `python main.py workspace resolve --manifest <path>
--module <id> --artifact <kind> [--require-exists] [--allow-deprecated]`.
No abre el archivo resuelto, no modifica nada, exit code 0/≠0 según
resolución. `workspace validate` sin cambios de comportamiento
(verificado por test de no regresión). No expone `--execution-id`
(recursos generados no resolubles desde CLI en este sprint — deuda
explícita, § 18).

## 13. Tests

Nuevos:

- `tests/test_resource_resolver.py` — 33 tests: proyecto/módulo/artefacto
  válidos y desconocidos; los 6 estados de artefacto (`missing`
  requerido/opcional, `optional` nunca bloquea por ausencia física,
  `deprecated` con/sin `allow_deprecated`, `not_applicable`,
  `allowed_statuses`); resolución con/sin path declarado; existencia
  física en sus 4 combinaciones; envoltura de `DataWorkspaceError` en
  `ResourcePathError`; Unicode/espacios; recursos generados (`execution_id`
  válido, ausente, con intento de escape parametrizado en 6 variantes,
  placeholder desconocido, no-crea-nada, ausencia física nunca bloqueante).
- `tests/test_cli_workspace_resolve.py` — 10 tests: resolución válida,
  ausencia no bloqueante sin `--require-exists`, módulo/artefacto
  desconocidos, `--require-exists` en sus dos desenlaces,
  `--allow-deprecated`, manifest inexistente, no revela secretos, no
  rompe `workspace validate`.

Modificados (renombrado de símbolos, mismo comportamiento verificado, un
test nuevo añadido):

- `tests/test_drills_data_workspace_integration.py` — de 6 a 7 tests: se
  añadió `test_fichero_en_categoria_deprecated_csv_enablon_no_se_resuelve`
  (confirma que no hay fallback oculto a la carpeta vieja); el resto se
  adaptó al nuevo nombre de función/categoría física, sin cambiar la
  intención de cada test.

## 14. Resultados

```
513 passed, 7 skipped   (referencia inicial, confirmada al empezar)
557 passed, 7 skipped   (al terminar -- +44, 0 nuevos skipped, 0 fallos)
```

`python -m py_compile` sin errores sobre los tres ficheros de producción
modificados/creados. CLI verificada manualmente: `workspace resolve`
sobre artefactos `present`/`missing`/`not_applicable`/`deprecated`,
módulo desconocido, `--require-exists` en ambos desenlaces,
`--allow-deprecated`, `--help` de `workspace`/`workspace resolve`;
`export drills --help`, `run --help`, `--help` raíz sin regresión.

## 15. Compatibilidad

- Sin `EMF_DATA_ROOT`: comportamiento idéntico a antes (comparación
  omitida, nunca error).
- Con `EMF_DATA_ROOT` pero sin archivo: comportamiento idéntico (omitida).
- Con archivo presente **en la carpeta nueva** (`CSV_Enablon_Operational/Drills.csv`):
  se genera `comparison_report.yaml` como antes.
- Con archivo presente **solo en la carpeta vieja** (`CSV_Enablon/`): ya
  NO se genera — cambio de comportamiento deliberado y documentado (§ 10),
  no una regresión (ninguna carpeta tenía datos reales).
- `resolve_artifact_path()` (Sprint 8.4) sin cambios, sigue usada por sus
  propios tests y ahora también internamente por `ResourceResolver`.

## 16. Archivos creados

- `src/core/resource_resolver.py`
- `docs/01-architecture/resource-resolver.md`
- `tests/test_resource_resolver.py`
- `tests/test_cli_workspace_resolve.py`
- `reports/executions/2026-07-28/Informe-Resource-Resolver-EMF.md` (+ `.txt`)

## 17. Archivos modificados

- `src/export/prototype/drills/pipeline.py` (migración HISTORICAL_CSV_CATEGORY)
- `src/cli.py` (comando `workspace resolve`)
- `tests/test_drills_data_workspace_integration.py` (adaptado + 1 test nuevo)
- `docs/01-architecture/workspace-manifest.md` (§ 20, puntero)
- `docs/01-architecture/external-data-workspace.md` (§ 23, puntero + cierre de punto pendiente de § 22)
- `docs/01-architecture/project-contract-model.md` (§ 6.0, puntero)
- `docs/07-developer-guide/drills-real-data-inventory.md` (fila 2, referencias actualizadas)

No se modificó `getting-started.md` — no referencia comandos de
`workspace` hoy, así que no había un punto de anclaje útil para una
actualización mínima sin duplicar contenido.

## 18. Riesgos

- El manifest mínimo construido en código dentro de `pipeline.py`
  (`_build_drills_comparison_manifest`) es una duplicación deliberada y
  acotada (un módulo, un artefacto) del mismo patrón que
  `examples/workspace/workspace.example.yaml` — si diverge sin querer del
  ejemplo real en el futuro, ambos deben revisarse juntos. Mitigado por
  quedar documentado explícitamente en `resource-resolver.md` § 15/§ 19.
- El cambio de carpeta física consultada (`CSV_Enablon` → `CSV_Enablon_Operational`)
  es invisible para cualquier equipo que ya hubiera colocado el CSV
  histórico en la carpeta vieja pensando que sería recogido — mitigado
  porque, según la documentación existente, ninguna de las dos carpetas
  tiene datos reales todavía.

## 19. Deuda técnica

- Manifest de Drills embebido en código en vez de cargado desde un
  `workspace.yaml` real (no existe todavía) — sustituir en cuanto exista.
- Recursos generados acotados a `contracts.emf` — no generalizado a nivel
  de artefacto individual, sin segundo caso real todavía.
- `entity_catalog_csv` y el SQL de origen de Drills siguen fuera del
  `ResourceResolver` (decisiones previas ya documentadas, sin evidencia
  nueva que las revierta).
- CLI sin `--execution-id` — no resuelve recursos generados desde línea
  de comandos todavía.
- Clasificación real de `Drills-22072026-41.csv` (Platform vs. Project
  Contract) sigue abierta — no resuelta por este sprint.

## 20. Recomendación

Sprint 8.5 completo según los criterios de aceptación del encargo. La
capa es genérica, tipada, sin fallback oculto, y no introduce ninguna
dependencia nueva. Recomendado seguir con: (a) un `workspace.yaml` real
del proyecto en cuanto el usuario decida crearlo, para retirar el
manifest embebido de `pipeline.py`; (b) confirmar con el cliente la
clasificación de `Drills-22072026-41.csv` para cerrar la pregunta abierta
de `project-contract-model.md` § 4. Ver § 21 de este informe (propuesta
de commits) para cómo aislar Sprint 8.4 de Sprint 8.5 en el historial.

## 21. Propuesta de commits (NO ejecutados — requieren aprobación explícita)

Sprint 8.4 sigue sin commit. Se recomienda **mantener commits
separados** (opción A del encargo) porque Sprint 8.4 (Manifest) y Sprint
8.5 (Resolver) son aislables limpiamente por archivo, con una única
excepción real de solape (`src/cli.py`, que Sprint 8.4 ya modificó para
añadir el grupo `workspace`/`validate`, y este sprint extiende con
`resolve` en el mismo archivo) — no bloqueante, `git add -p` puede
separar los hunks si se prefiere estrictamente por sprint; si no, un
commit de Sprint 8.5 que incluya el hunk de `resolve` en `src/cli.py` es
razonable y se documenta así.

**Commit 1 (Sprint 8.4, ya pendiente, sin tocar por este informe):**
mensaje sugerido ya cubierto por
`reports/executions/2026-07-27/Informe-Workspace-Manifest-EMF.md` — no se
repite aquí.

**Commit 2 (Sprint 8.5 — este incremento):**

```
feat(core): add generic ResourceResolver over the Workspace Manifest

Adds ResourceResolver/ResourceRequest/ResolvedResource
(src/core/resource_resolver.py) with typed errors, physical-existence
checks decoupled from declaration, and support for the one real
generated-resource case (EMF output pattern). Migrates Drills' historical
CSV comparison off the deprecated HISTORICAL_CSV_CATEGORY constant to an
explicit operational_csv (Project Contract) request. Adds `workspace
resolve` CLI command.
```

Archivos sugeridos para este commit: `src/core/resource_resolver.py`,
`src/export/prototype/drills/pipeline.py`, `src/cli.py`,
`tests/test_resource_resolver.py`, `tests/test_cli_workspace_resolve.py`,
`tests/test_drills_data_workspace_integration.py`,
`docs/01-architecture/resource-resolver.md`,
`docs/01-architecture/workspace-manifest.md` (§ 20),
`docs/01-architecture/external-data-workspace.md` (§ 23),
`docs/01-architecture/project-contract-model.md` (§ 6.0),
`docs/07-developer-guide/drills-real-data-inventory.md` (fila 2),
`reports/executions/2026-07-28/Informe-Resource-Resolver-EMF.md` (+ `.txt`).

**Excluir de cualquier commit:** `.claude/settings.local.json` (permisos
locales, no forma parte del trabajo de ningún sprint).

## 22. `git diff --check`

Sin errores de espacio en blanco (exit code 0) — solo warnings de
conversión de fin de línea LF→CRLF de Git en Windows, no errores.

## 23. `git status --short` (al terminar este informe)

```
 M .claude/settings.local.json
 M config/data_workspace.yaml
 M docs/01-architecture/external-data-workspace.md
 M src/cli.py
 M src/export/prototype/drills/pipeline.py
 M tests/test_drills_data_workspace_integration.py
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/project-contract-model.md
?? docs/01-architecture/resource-resolver.md
?? docs/01-architecture/workspace-manifest.md
?? docs/01-architecture/workspace-naming-convention.md
?? docs/01-architecture/workspace-validation-checklist.md
?? docs/07-developer-guide/drills-real-data-inventory.md
?? examples/
?? reports/executions/2026-07-27/...
?? reports/executions/2026-07-28/Informe-Resource-Resolver-EMF.md
?? reports/executions/2026-07-28/Informe-Resource-Resolver-EMF.txt
?? src/core/resource_resolver.py
?? src/core/workspace_manifest.py
?? tests/test_cli_workspace_resolve.py
?? tests/test_cli_workspace_validate.py
?? tests/test_resource_resolver.py
?? tests/test_workspace_manifest.py
```

(`config/data_workspace.yaml`, `docs/01-architecture/drills-csv-contract.md`,
`knowledge-*.md`, `workspace-manifest.md`, `workspace-naming-convention.md`,
`workspace-validation-checklist.md`, `examples/`,
`src/core/workspace_manifest.py`, `tests/test_workspace_manifest.py`,
`tests/test_cli_workspace_validate.py` y los informes de 2026-07-27 son
Sprint 8.4, no tocados por este incremento salvo la extensión puntual ya
descrita en § 17.)

## 24. `git diff --stat` (archivos tocados por Sprint 8.5)

```
 src/core/resource_resolver.py                    | nuevo (~350 líneas)
 src/export/prototype/drills/pipeline.py           | +~95 -~30
 src/cli.py                                        | +~76
 tests/test_drills_data_workspace_integration.py   | +~35 -~20
 tests/test_resource_resolver.py                   | nuevo (~330 líneas)
 tests/test_cli_workspace_resolve.py                | nuevo (~150 líneas)
 docs/01-architecture/resource-resolver.md          | nuevo (~230 líneas)
 docs/01-architecture/workspace-manifest.md         | +~9
 docs/01-architecture/external-data-workspace.md    | +~19
 docs/01-architecture/project-contract-model.md     | +~13
 docs/07-developer-guide/drills-real-data-inventory.md | +~1 -~1
```
