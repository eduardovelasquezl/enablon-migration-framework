# Informe de Ejecución — Sprint 8.4: Workspace Manifest

**Fecha:** 2026-07-27
**Rama:** `feature/drills-filtered-exports`
**Remoto:** `origin` → `enablon-migration-framework`

## 1. Resumen ejecutivo

Se diseñó e implementó un **Workspace Manifest** genérico
(`src/core/workspace_manifest.py`): un modelo declarativo tipado que
describe, para cualquier proyecto, qué módulos lo forman, qué artefactos
corresponde a cada uno (ETL, CSV Template/Operacional, SQL, Mapping,
Catálogos, Errores, Evidencia, Outputs), cuáles son obligatorios, cuáles
existen, y qué artefacto representa cada nivel de contrato
(Platform/Project/EMF). Se implementó también un validador de reglas de
negocio (`validate_manifest`), integración con `DataWorkspace` ya
existente (reutilizada, no duplicada), un ejemplo versionable completo
para Moeve con sus 8 módulos conocidos, un comando CLI aditivo
(`python main.py workspace validate`), y 39 tests nuevos, todos en verde.
La suite completa del proyecto pasa de 474 a **513 passed, 7 skipped**
(mismos skips de siempre). No se creó ningún `workspace.yaml` real fuera
del repositorio, no se accedió a SQL Server, no se ejecutó ningún
pipeline ni sample, y no se hizo ningún commit.

## 2. Estado inicial (Fase 0)

- Rama: `feature/drills-filtered-exports` ✓
- Remoto: `origin` → `https://github.com/eduardovelasquezl/enablon-migration-framework.git` ✓
- `git diff --check`: limpio.
- Suite previa: **474 passed, 7 skipped** (confirmado antes de tocar nada).
- Único cambio inesperado: `.claude/settings.local.json` (permisos
  automáticos de Claude Code) — restaurado con `git restore` según
  instrucción. El resto de cambios pendientes (documentación de Sprints
  8.1-8.3, todavía sin commitear a petición explícita del usuario en esos
  sprints) no son "inesperados" — son trabajo previo conocido, no se
  tocaron.

## 3. Diseño aprobado

Ver `docs/01-architecture/workspace-manifest.md` (nuevo, 19 secciones
completas: propósito, alcance, relación con `DataWorkspace`/Module
Registry/Resource Resolver, estructura, metadata de proyecto/módulo,
artefactos, contract roles, naming conventions, status model,
validation rules, seguridad de rutas, ejemplo Moeve, evolución futura,
criterios de aceptación, deuda técnica).

## 4. Modelo YAML

Tres niveles: `project` (id/display_name/status/version/owner opcional/
last_reviewed_at opcional), `workspace` (schema_version/project_root/
naming_convention/deprecated_paths), `modules` (mapa `module_id ->`
display_name/enabled/status/source_system/target_object/canonical_name/
artifacts/contracts/validation/notes). Cada artefacto: kind/path/
required_for_sample/required_for_full/required_for_comparison/status/
description/contract_role/source/checksum/last_reviewed_at.

## 5. Modelo Python

`src/core/workspace_manifest.py` (nuevo, ~470 líneas). Dataclasses
`frozen=True`: `ProjectMeta`, `WorkspaceMeta`, `ArtifactSpec`,
`ContractsSpec`, `ModuleSpec`, `WorkspaceManifest`. Vocabularios cerrados
como clase + `frozenset`: `ModuleStatus` (6 valores), `ArtifactStatus`
(6 valores), `ARTIFACT_KINDS` (9 valores), `CONTRACT_ROLES` (3 valores) —
mismo patrón ya establecido en `src/core/contracts.py`
(`StageStatus`/`ExecutionStatus`). `WorkspaceManifestLoader` carga desde
`dict` o desde ruta de fichero, sin abrir ningún archivo referenciado por
el manifest. Solo `PyYAML` (ya instalado, usado también por
`src/config/loader.py` y `src/export/prototype/drills/manifest.py`) —
ninguna dependencia nueva instalada.

## 6. Integración DataWorkspace

`resolve_artifact_path(manifest, module_id, artifact_kind, workspace, *,
required=False)` traduce el `kind` de artefacto a la categoría de
`config/data_workspace.yaml` correspondiente
(`ARTIFACT_KIND_TO_CATEGORY`, único punto de esa correspondencia) y
delega toda la resolución/seguridad de ruta en
`DataWorkspace.resolve()` ya existente — **no reimplementa** la
protección de escape ni de rutas absolutas (verificado por
`test_resolve_artifact_path_reutiliza_proteccion_de_escape_de_data_workspace`).
`config/data_workspace.yaml` ganó dos categorías nuevas, puramente
aditivas: `csv_enablon_template`, `csv_enablon_operational` — la
categoría legacy `csv_enablon` se conserva sin cambios (Drills sigue
funcionando exactamente igual, confirmado por
`tests/test_drills_data_workspace_integration.py`, 6/6 en verde).

## 7. Validaciones implementadas

**A nivel de esquema** (`ManifestSchemaError`, lanzada al cargar): claves
obligatorias de proyecto/workspace/módulo, vocabularios cerrados de
estado, `kind` de artefacto conocido, rutas relativas y sin escapes,
artefacto obligatorio no puede ser `not_applicable`, contrato referencia
un artefacto declarado, módulo `deprecated`+`enabled` exige
justificación, clave de módulo coincide con su `module_id`.

**A nivel de negocio** (`validate_manifest`, devuelve lista de
violaciones, nunca lanza): ruta dentro de carpeta `deprecated_paths`
desde módulo no deprecated; nombre de artefacto que no cumple
`naming_convention`; `template_csv` con `preserve_source_name` nunca
produce violación; dos módulos con el mismo `canonical_name`; dos
módulos con la misma ruta para el mismo `kind`.

No se comprueba, en producción, si los archivos físicos existen — solo
en tests con `DataWorkspace` temporal, tal como pedía el encargo.

## 8. CLI

`python main.py workspace validate --manifest <path>` (nuevo grupo
`workspace`, comando `validate`, en `src/cli.py`). Carga + valida;
`exit code 0` si no hay violaciones, `1` si hay error de esquema o
violaciones de negocio; mensajes de error legibles por `stderr`. No lee
ningún dato real, no ejecuta SQL, no modifica nada. Comandos existentes
(`export drills`, `run`, `evidence drills`) verificados sin cambios
(`test_workspace_validate_no_rompe_comandos_existentes`).

## 9. Ejemplo Moeve

`examples/workspace/workspace.example.yaml` (nuevo) — 8 módulos:
`drills`, `safety_meetings`, `moc`, `bypass`, `events`, `ops`,
`inspections`, `corrective_actions`. Solo `drills` tiene artefactos
parcialmente definidos (`sql`/`mapping` en `present`, resto `missing`);
los otros 7 usan `status: planned`, artefactos `missing`, sin ningún
nombre de archivo inventado. `canonical_name` solo se declara para 3
módulos (`drills`→`Drills`, `events`→`Events`,
`corrective_actions`→`Action_Plans`) — los únicos con un objeto real de
Enablon confirmado sin ambigüedad en `config/modules.yaml`; los otros 5
lo omiten explícitamente con una nota. Sin rutas absolutas, sin nombres
de usuario, sin credenciales. Carga y valida sin violaciones.

## 10. Tests

Dos ficheros nuevos:

- `tests/test_workspace_manifest.py` — 35 tests: manifest válido;
  project id/schema_version ausentes; módulo sin artefactos declarados;
  artefacto de kind desconocido; status de artefacto/módulo inválido;
  4 variantes de path absoluto/con escape (parametrizado); artefacto
  obligatorio `not_applicable`; contrato a artefacto inexistente/existente;
  módulo deprecated habilitado con y sin justificación; módulo deprecated
  deshabilitado; módulo desconocido; manifest limpio sin violaciones;
  operational_csv con nombre correcto/incorrecto; template_csv preservado;
  dos módulos con mismo canonical_name; ruta en carpeta deprecated; dos
  módulos con misma ruta; integración con DataWorkspace (resolución,
  ausencia de path, reutilización de protección de escape, archivo real
  en workspace temporal); Unicode y espacios; carga del ejemplo Moeve sin
  violaciones; solo Drills con artefactos no-missing; sin imports de
  `src.db`/`src.export`/`src.etl` (verificado por AST, no por substring);
  ninguna carpeta creada al cargar/validar/resolver.
- `tests/test_cli_workspace_validate.py` — 4 tests: ejemplo Moeve exit
  code 0; manifest inexistente exit code distinto de 0; manifest con
  violación exit code distinto de 0; comandos existentes de la CLI no
  rotos.

## 11. Resultados

```
39 tests nuevos, todos PASSED.
Suite completa: 513 passed, 7 skipped (antes: 474 passed, 7 skipped).
```

## 12. Archivos creados

- `src/core/workspace_manifest.py`
- `examples/workspace/workspace.example.yaml`
- `tests/test_workspace_manifest.py`
- `tests/test_cli_workspace_validate.py`
- `docs/01-architecture/workspace-manifest.md`
- `reports/executions/2026-07-27/Informe-Workspace-Manifest-EMF.md`
- `reports/executions/2026-07-27/Informe-Workspace-Manifest-EMF.txt`

(Además, sin relación con este sprint pero sin commitear todavía de
sprints anteriores: `docs/01-architecture/drills-csv-contract.md`,
`knowledge-coverage-matrix.md`, `knowledge-traceability-matrix.md`,
`project-contract-model.md`, `workspace-naming-convention.md`,
`workspace-validation-checklist.md`,
`docs/07-developer-guide/drills-real-data-inventory.md`,
`reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.{md,txt}`.)

## 13. Archivos modificados

- `config/data_workspace.yaml` — 2 categorías nuevas añadidas
  (`csv_enablon_template`, `csv_enablon_operational`), puramente
  aditivo, categoría legacy `csv_enablon` sin cambios.
- `src/cli.py` — nuevo grupo `workspace` + comando `validate`, aditivo,
  sin tocar ningún comando existente.
- `docs/01-architecture/external-data-workspace.md` — nueva § 27
  (Sprint 8.4) + referencias cruzadas actualizadas.
- `docs/01-architecture/project-contract-model.md` — nueva § 6.1
  (representación en el Workspace Manifest).
- `docs/01-architecture/workspace-naming-convention.md` — nueva § 5.1
  (validación automática).

## 14. Compatibilidad

- `config/exports/drills.yaml`, `pipeline.py::HISTORICAL_CSV_CATEGORY`
  y todo el comportamiento existente de Drills **sin cambios** —
  verificado por la suite completa de Drills (todos los tests previos
  siguen en verde) y específicamente por
  `tests/test_drills_data_workspace_integration.py` (6/6).
- `test_data_workspace.py` usa una configuración sintética inyectada
  (no lee el `config/data_workspace.yaml` real), por lo que añadir
  categorías nuevas al fichero real no le afecta — confirmado (17/17 en
  verde).
- CLI: `export drills`, `run`, `evidence drills` sin cambios de
  comportamiento — verificado con `click.testing.CliRunner`.

## 15. Riesgos

- El manifest es, hoy, puramente declarativo — no hay ningún código que
  lo consuma en el pipeline real de Drills todavía (ni falta, en esta
  fase: es infraestructura para el futuro motor de comparación de tres
  vías, no un requisito de Drills hoy).
- `canonical_name` ambiguo para 5 de 8 módulos del ejemplo Moeve — riesgo
  aceptado y documentado explícitamente (mejor no declarar un nombre que
  declarar uno inventado).
- La categoría legacy `csv_enablon` de `config/data_workspace.yaml`
  convive ahora con las dos nuevas sin que ningún código decida todavía
  cuál usar para Drills — deuda técnica ya señalada en
  `external-data-workspace.md` § 22, sin resolver en este sprint (fuera
  de alcance, no bloqueante).

## 16. Deuda técnica

Ver `docs/01-architecture/workspace-manifest.md` § 19 (no se duplica
aquí): `ModuleSpec.validation` sin interpretar; sin generador automático
de `workspace.yaml` desde escaneo real; `project.status` no es
vocabulario cerrado; motor de comparación de tres vías sin implementar;
`checksum`/`last_reviewed_at` de artefacto sin cálculo/verificación.

## 17. Siguiente paso

1. Confirmar con el usuario si se aprueban los 2 (o 3, con la propuesta
   de commits separados) commits de este sprint.
2. Cuando el usuario recupere manualmente los primeros artefactos reales
   (ETL, CSV Template/Operacional de Drills), crear un `workspace.yaml`
   real (fuera de Git, dentro del workspace externo) siguiendo la
   plantilla de `examples/workspace/workspace.example.yaml`, y validarlo
   con `python main.py workspace validate --manifest <ruta real>`.
3. Decidir si `pipeline.py::HISTORICAL_CSV_CATEGORY` migra de
   `csv_enablon` a `csv_enablon_template`/`csv_enablon_operational`
   (pendiente desde Sprint 8.2, sigue pendiente).

## 18. `git diff --check`

Limpio (`exit=0`) — solo warnings de conversión de fin de línea
(LF→CRLF), no errores de espacios en blanco.

## 19. `git status --short`

```
 M .claude/settings.local.json
 M config/data_workspace.yaml
 M docs/01-architecture/external-data-workspace.md
 M src/cli.py
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/project-contract-model.md
?? docs/01-architecture/workspace-manifest.md
?? docs/01-architecture/workspace-naming-convention.md
?? docs/01-architecture/workspace-validation-checklist.md
?? docs/07-developer-guide/drills-real-data-inventory.md
?? examples/
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt
?? src/core/workspace_manifest.py
?? tests/test_cli_workspace_validate.py
?? tests/test_workspace_manifest.py
```

## 20. `git diff --stat`

```
 .claude/settings.local.json                     |  13 +-
 config/data_workspace.yaml                      |   9 +-
 docs/01-architecture/external-data-workspace.md | 291 ++++++++++++++++++++++--
 src/cli.py                                      |  53 +++++
 4 files changed, 346 insertions(+), 20 deletions(-)
```

(`git diff --stat` solo cubre ficheros ya trackeados y modificados —
los ficheros nuevos, `??` en `git status`, se listan en § 12.)

## Propuesta de commits (Sprint 8.4, sin ejecutar)

**Commit A — código:**
```
feat(core): add workspace manifest model

- add WorkspaceManifest/WorkspaceManifestLoader/validate_manifest
- add resolve_artifact_path integration with DataWorkspace
- add csv_enablon_template/csv_enablon_operational categories to
  config/data_workspace.yaml (additive, legacy csv_enablon unchanged)
```
Archivos: `src/core/workspace_manifest.py`, `config/data_workspace.yaml`,
`tests/test_workspace_manifest.py`.

**Commit B — CLI:**
```
feat(cli): add workspace manifest validation command
```
Archivos: `src/cli.py`, `tests/test_cli_workspace_validate.py`.

**Commit C — documentación:**
```
docs(workspace): document workspace manifest model and example
```
Archivos: `docs/01-architecture/workspace-manifest.md`,
`examples/workspace/workspace.example.yaml`,
`docs/01-architecture/external-data-workspace.md`,
`docs/01-architecture/project-contract-model.md`,
`docs/01-architecture/workspace-naming-convention.md`,
`reports/executions/2026-07-27/Informe-Workspace-Manifest-EMF.{md,txt}`.

**No incluidos en esta propuesta** (pendientes de aprobación de sprints
anteriores, ya expuestos al usuario en sus respectivos informes):
`drills-csv-contract.md`, `knowledge-coverage-matrix.md`,
`knowledge-traceability-matrix.md`, `workspace-validation-checklist.md`,
`drills-real-data-inventory.md`, `Informe-Knowledge-Audit-EMF.{md,txt}`.

No se ha ejecutado ningún `git add`/`git commit`/`git push` — solo se
presenta la propuesta, a la espera de aprobación explícita.
