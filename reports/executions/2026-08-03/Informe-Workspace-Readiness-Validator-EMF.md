# Informe — Sprint 8.7: Workspace Readiness Validator

**Fecha:** 2026-08-03
**Rama:** `feature/drills-filtered-exports`
**HEAD de referencia (previo a este sprint):** `92f4120`
**Estado de referencia:** 647 passed, 7 skipped

## 1. Resumen ejecutivo

Se implementó un validador genérico de preparación operativa
(`WorkspaceReadinessValidator`, `src/core/readiness_validator.py`) que
compone `ModuleRegistry` + `WorkspaceManifest` + `ResourceResolver` (y lee,
sin mutar, el SQL Execution Guard) para responder, antes de intentar
cualquier operación: *¿está listo `<módulo>` en `<proyecto>` para
`<operación>`, y si no, qué falta exactamente y eso bloquea o solo advierte?*

Estados finales: `READY` / `READY_WITH_WARNINGS` / `BLOCKED` — nunca
describen el resultado de una migración, solo la preparación previa. Se
añadió el comando aditivo `python main.py workspace readiness`, sin tocar
ningún comando existente. La suite pasó de 647/7 a **714 passed / 7
skipped** (67 tests nuevos, cero regresiones). No se ejecutó SQL real en
ningún momento de este sprint; no se hizo commit.

## 2. Estado inicial (Fase 0, verificación)

- Branch: `feature/drills-filtered-exports`. Remoto: `origin` →
  `enablon-migration-framework`. HEAD: `92f4120`.
- `git diff --check`: limpio (sin problemas de espacio en blanco).
- Suite inicial: **647 passed, 7 skipped** — coincide exactamente con la
  referencia del encargo.
- `.claude/settings.local.json`: sin cambios manuales; los cambios
  automáticos de permisos acumulados durante la sesión se restauraron con
  `git restore` antes de cerrar el sprint (Fase 0, punto 2 del encargo).
- Cinco archivos sin trackear de Sprint 8.1 (`drills-csv-contract.md`,
  `knowledge-coverage-matrix.md`, `knowledge-traceability-matrix.md`,
  `Informe-Knowledge-Audit-EMF.{md,txt}`) identificados como **fuera de
  alcance** — no se tocaron, no se incluyen en este commit propuesto.
- No se detectaron otros cambios inesperados. SQL Execution Guard activo
  por defecto (verificado sin abrir conexión real).

## 3. Inventario de requisitos (Fase 1)

Se investigó, con lectura directa de código (`src/core/module_registry.py`,
`src/core/workspace_manifest.py`, `src/core/resource_resolver.py`,
`src/cli.py`, `src/bootstrap/module_registry.py`) y de los tests/docs
existentes, dónde se declaraban hoy los requisitos por operación. Hallazgo
central: **existían dos vocabularios de "obligatorio" sin relación
programática entre ellos, y ninguno de los dos se aplicaba en runtime**:

| Fuente | Concepto | Semántica actual (antes de este sprint) | Conflicto | Decisión de este sprint |
|---|---|---|---|---|
| `ModuleDefinition.required_artifact_types` (`module_registry.py:231`) | Set plano, sin distinguir sample/full/comparison | Validado al construir, nunca leído para bloquear nada (solo `modules show` lo imprime) | Doc decía "bloquea sample/full" — ningún código lo hacía | Señal de alerta no bloqueante (`ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`, WARNING) |
| `ArtifactSpec.required_for_sample/full/comparison` (`workspace_manifest.py:151-153`) | Booleano por artefacto, por operación | Solo comprobado por un guard de esquema al cargar (`not_applicable` + required → error) | Nunca aplicado en runtime pese a tener la granularidad correcta | **Única fuente real de bloqueo por operación** (aplicada por primera vez) |
| `ensure_module_runnable()` (`module_registry.py:433-473`) | Software conoce + proyecto declara + habilitado + capacidad | Totalmente testeada, **sin ningún llamador real** | Documentado como deuda en `module-registry.md` § 20 | Primer llamador real: `WorkspaceReadinessValidator._run_gate()` |
| Drills `sql`/`mapping` (`config/exports/drills.yaml`, `inputs/entity_catalog/`) | Declarados `required_artifact_types` pero resueltos fuera de `ResourceResolver` | El manifest real los declara `status=present`, `path=null`, `source: git:...` | `required=True` contra el resolver habría lanzado `ArtifactMissingError` incorrectamente | El validador nunca llama a `resolve()` con `required=True`; decide severidad él mismo a partir de `status` |
| `ContractsSpec.project_artifact` vs. `ArtifactSpec.required_for_comparison` | Dos formas de señalar "esto es el artefacto de comparación" | Podían divergir sin ninguna validación | Detectado en el inventario, no forzado antes | `ContractCheck` emite `CONTRACT_ARTIFACT_NOT_MARKED_REQUIRED` (WARNING) si divergen |

## 4. Precedencia fijada

`ModuleRegistry` (¿el software es capaz?) → `WorkspaceManifest` (¿el
proyecto lo declara/exige para esta operación?) → `ResourceResolver` (¿se
resuelve/existe?) → `WorkspaceReadinessValidator` agrega. Ningún nivel
reimplementa al anterior — el validador solo compone.

**Decisión de diseño explícita, desviación documentada del boceto literal
de la Fase 6 del encargo:** no se introdujo un bloque `operation_requirements:`
nuevo en el manifest. `ArtifactSpec.required_for_sample/full/comparison`
(existente desde Sprint 8.4) ya tenía exactamente esa granularidad —
introducir un segundo mecanismo paralelo habría violado "no duplica sus
responsabilidades" (criterio de aceptación #5) y creado una tercera fuente
de verdad. Se promovieron esos tres flags a la única fuente real, en vez de
inventar un cuarto vocabulario.

## 5. Arquitectura

Ver `docs/01-architecture/workspace-readiness-validator.md` § 4 para el
diagrama completo. Resumen: `ReadinessRequest` entra, `_run_gate()` resuelve
`ModuleImplementationCheck`+`ProjectModuleDeclarationCheck` (cortan el resto
si fallan), después siete checks se ejecutan siempre en orden fijo
(`CapabilityCheck`, `ArtifactDeclarationCheck`, `ArtifactStatusCheck`,
`ResourceResolutionCheck`, `PhysicalExistenceCheck`, `ContractCheck`,
`SecurityCheck`), acumulando `ReadinessIssue`; el resultado se agrega en un
`ReadinessAssessment` con deduplicación por `(code, artifact_type)`.

## 6. Modelo Python (`src/core/readiness_validator.py`)

`ReadinessOperation`, `ReadinessStatus`, `ReadinessSeverity` (vocabularios
cerrados); `ReadinessIssue`, `ReadinessRequest`, `ReadinessAssessment`
(dataclasses `frozen`); nueve clases de check; `WorkspaceReadinessValidator`
con un único método público `assess()`. Sin estado global (ADR-010) — cada
`assess()` es independiente. ~700 líneas, sin ningún `if module_id ==
"drills"` (verificado por test de inspección AST/texto).

## 7. Operaciones evaluables

`sample`, `full`, `comparison`, `evidence`, `validation`, `export` — ver
tabla completa (capacidades exigidas + fuente del artefacto obligatorio) en
`workspace-readiness-validator.md` § 6.

## 8. Checks implementados

Los nueve pedidos por la Fase 5 del encargo, todos deterministas e
independientes: `ModuleImplementationCheck` (distingue `MODULE_UNKNOWN` de
`MODULE_NOT_EXECUTABLE` — este último nuevo, necesario para diferenciar
"roadmap/planned" de "artefacto ausente", Fase 8E), `ProjectModuleDeclarationCheck`,
`CapabilityCheck`, `ArtifactDeclarationCheck`, `ArtifactStatusCheck`,
`ResourceResolutionCheck`, `PhysicalExistenceCheck`, `ContractCheck`,
`SecurityCheck`.

## 9. Política por operación

Ver § 4 (precedencia) y `workspace-readiness-validator.md` § 11. Reglas
confirmadas por los tests: ETL nunca bloquea; Template CSV no bloquea
`sample`; Operational CSV no bloquea `sample` pero sí `comparison` cuando es
el Project Contract; un output generado nunca se exige pre-existente; un
mapping git-tracked sin `path` no bloquea (se acepta la declaración,
`INFO`).

## 10. Resultado agregado

`blockers` → `BLOCKED`; sin blockers pero con `warnings` → `READY_WITH_WARNINGS`
(o `BLOCKED` si `strict=True`); sin issues → `READY`. Orden de checks
determinista (verificado por test); issues deduplicados por
`(code, artifact_type)` (verificado por test).

## 11. Drills

Verificado en `tests/test_readiness_validator_drills_integration.py`
(11 tests) usando `build_default_module_registry()` real: `sample` sin
comparación → READY/READY_WITH_WARNINGS, nunca bloqueado por ETL/Template/
Operational ausentes; `comparison` bloquea sin `operational_csv`; `full`
evalúa sin pedir autorización SQL; módulo deshabilitado → BLOCKED; módulo no
registrado → `MODULE_UNKNOWN`, distinto de cualquier `ARTIFACT_*`.

## 12. CLI

`python main.py workspace readiness --manifest <path> --module <id>
--operation <op> [--require-files] [--format text|json] [--strict]`. Exit
codes: `0` READY, `1` READY_WITH_WARNINGS, `2` BLOCKED, `3` error técnico.
Nunca requiere ni acepta `--allow-real-sql`. Comandos existentes
(`workspace validate/resolve`, `modules list/show`, `run`, `export drills`)
verificados sin cambios de comportamiento (tests dedicados en
`test_cli_workspace_readiness.py`).

## 13. SQL Execution Guard

El validador nunca llama a `grant()`/`revoke()`/`get_engine()` — solo lee
`current_authorization()` para una nota informativa
(`SQL_AUTHORIZATION_INFO`). Verificado por dos tests: análisis AST del
fichero fuente (nunca aparece una llamada real a esas funciones) y
comprobación de que `sql_execution_guard.is_authorized()` no cambia antes/
después de `assess()`.

## 14. Tests creados

- `tests/test_readiness_validator.py` — 42 tests unitarios (fixtures
  sintéticas, sin Drills).
- `tests/test_readiness_validator_drills_integration.py` — 11 tests de
  integración con Drills real (`build_default_module_registry()`), sin SQL.
- `tests/test_cli_workspace_readiness.py` — 14 tests de CLI (exit codes,
  `--format json`, `--require-files`, `--strict`, no-regresión del resto de
  comandos).

Total: **67 tests nuevos**.

## 15. Resultados de la suite

```
714 passed, 7 skipped in ~21s
```

647 (referencia) + 67 (nuevos) = 714. Cero regresiones, cero tests
eliminados o modificados.

## 16. Compatibilidad con criterios de aceptación

| # | Criterio | Cumplido |
|---|---|---|
| 1 | Existe `WorkspaceReadinessValidator` genérico | Sí |
| 2 | Usa `ModuleRegistry` | Sí |
| 3 | Usa `WorkspaceManifest` | Sí |
| 4 | Usa `ResourceResolver` | Sí |
| 5 | No duplica sus responsabilidades | Sí — ver § 4 (decisión de precedencia) |
| 6 | No contiene lógica específica de Drills en el Core | Sí — verificado por test |
| 7 | Distingue READY/READY_WITH_WARNINGS/BLOCKED | Sí |
| 8 | Evalúa sample, comparison y full | Sí (+ evidence/validation/export) |
| 9 | ETL no bloquea si no es dependencia runtime | Sí |
| 10 | Template no bloquea sample si no se consume | Sí |
| 11 | Operational CSV bloquea comparison cuando es Project Contract | Sí |
| 12 | Output generado no debe existir previamente | Sí |
| 13 | No abre SQL | Sí |
| 14 | No modifica SQL Execution Guard | Sí |
| 15 | CLI aditiva con exit codes definidos | Sí |
| 16 | Tests nuevos en verde | Sí (67/67) |
| 17 | Suite previa continúa pasando | Sí (647/647) |
| 18 | No accede a datos reales | Sí |
| 19 | Documentación e informes generados | Sí |
| 20 | No hace commit sin aprobación | Sí — pendiente de aprobación |

## 17. Archivos creados

- `src/core/readiness_validator.py`
- `tests/test_readiness_validator.py`
- `tests/test_readiness_validator_drills_integration.py`
- `tests/test_cli_workspace_readiness.py`
- `docs/01-architecture/workspace-readiness-validator.md`
- `reports/executions/2026-08-03/Informe-Workspace-Readiness-Validator-EMF.md`
- `reports/executions/2026-08-03/Informe-Workspace-Readiness-Validator-EMF.txt`

## 18. Archivos modificados

- `src/cli.py` — nuevo subcomando `workspace readiness` (aditivo).
- `docs/01-architecture/module-registry.md` — § 20, `ensure_module_runnable`
  ahora tiene un llamador real.
- `docs/01-architecture/workspace-manifest.md` — tabla de `ArtifactSpec`,
  corregido el sobre-reclamo "bloquea sample/full" (ahora aclara que lo
  aplica el nuevo validador, no el propio manifest).
- `docs/01-architecture/resource-resolver.md` — § 19.2, nuevo consumidor.
- `docs/01-architecture/external-data-workspace.md` — § 24, referencia
  cruzada.
- `docs/07-developer-guide/getting-started.md` — fila nueva en la tabla de
  estado real del código.
- `docs/07-developer-guide/drills-real-data-inventory.md` — actualización
  de § 8 con qué queda automatizado y qué sigue siendo manual.

## 19. Riesgos

- El validador depende de que el manifest declare `required_for_sample/
  full/comparison` correctamente — un manifest mal declarado (p. ej. sin
  marcar nada como requerido) producirá un falso READY. Mitigado por
  `workspace validate` (forma) siendo un paso previo recomendado, no
  sustituido por este validador.
- `validation` reutilizando `required_for_sample` es una aproximación
  documentada, no una regla de negocio confirmada por el cliente.

## 20. Deuda técnica

Ver `workspace-readiness-validator.md` § 21 (documentada en el propio doc
de arquitectura, no repetida aquí en detalle). Punto verificado
explícitamente para esta autorización de commit (relación entre
`ModuleDefinition.required_artifact_types`/`optional_artifact_types` y
`ArtifactSpec.required_for_sample/full/comparison`, ver § 11.1 del doc de
arquitectura):

- **Fuente efectiva de obligatoriedad por operación**: únicamente
  `ArtifactSpec.required_for_sample/full/comparison` (nivel manifest/
  proyecto). Es la única que puede producir un `BLOCKER`.
- `ModuleDefinition.required_artifact_types` (nivel software): nunca
  bloquea, solo emite `WARNING` (`ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`) si
  el proyecto no declara en absoluto un kind que el software espera para
  `sample`/`full`. No contradice ni sobrescribe los requisitos por
  operación -- vive en una capa distinta, nunca se funde con ellos.
- `ModuleDefinition.optional_artifact_types`: **completamente redundante**
  hoy -- ningún check de `readiness_validator.py` lo lee (verificado por
  `grep`); el validador calcula sus propios "opcionales" por operación
  directamente del manifest (`ctx.optional_kinds`). Se mantiene como
  metadato general del software (usado solo por `modules show` y por la
  validación de no-solape en `ModuleDefinition.__post_init__`), documentado
  como candidato a simplificar/retirar en un futuro sprint si un segundo
  módulo real confirma que nunca hace falta ("No Abstraction Without a Real
  Consumer") -- no se retira en este sprint por no formar parte del alcance
  pedido.
- Resto de la deuda ya documentada sin cambios: reutilización de
  `required_for_sample` para `validation`; `export`/`evidence` sin
  artefactos obligatorios modelados; credenciales/conectividad SQL siguen
  sin modelarse como artefacto.

## 21. Siguiente paso

Conectar `--manifest` a `python main.py run` para que también pase por
`ensure_module_runnable()`/el nuevo validador antes de ejecutar (deuda ya
señalada en `module-registry.md` § 20, sin resolver en este sprint por no
haber sido pedido explícitamente).

## 22. Propuesta de commit

Un único commit (CLI+Core+tests+docs cohesionados, mismo criterio que
sprints anteriores de este repositorio — revisar diff antes de confirmar):

```
feat(core): add workspace readiness validator

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

Excluye explícitamente los cinco archivos de Knowledge Audit de Sprint 8.1
(fuera de alcance, sin tocar).

## 23. `git diff --check`

```
(limpio — sin advertencias de espacio en blanco)
```

## 24. `git status --short`

```
 M docs/01-architecture/external-data-workspace.md
 M docs/01-architecture/module-registry.md
 M docs/01-architecture/resource-resolver.md
 M docs/01-architecture/workspace-manifest.md
 M docs/07-developer-guide/drills-real-data-inventory.md
 M docs/07-developer-guide/getting-started.md
 M src/cli.py
?? docs/01-architecture/drills-csv-contract.md          (fuera de alcance, Sprint 8.1)
?? docs/01-architecture/knowledge-coverage-matrix.md    (fuera de alcance, Sprint 8.1)
?? docs/01-architecture/knowledge-traceability-matrix.md (fuera de alcance, Sprint 8.1)
?? docs/01-architecture/workspace-readiness-validator.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md  (fuera de alcance, Sprint 8.1)
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt (fuera de alcance, Sprint 8.1)
?? reports/executions/2026-08-03/
?? src/core/readiness_validator.py
?? tests/test_cli_workspace_readiness.py
?? tests/test_readiness_validator.py
?? tests/test_readiness_validator_drills_integration.py
```

## 25. `git diff --stat`

```
 docs/01-architecture/external-data-workspace.md    |   9 ++
 docs/01-architecture/module-registry.md            |  16 ++-
 docs/01-architecture/resource-resolver.md          |  14 ++
 docs/01-architecture/workspace-manifest.md         |   6 +-
 docs/07-developer-guide/drills-real-data-inventory.md | 18 +++
 docs/07-developer-guide/getting-started.md         |   1 +
 src/cli.py                                         | 147 +++++++++++++++++++++
 7 files changed, 210 insertions(+), 1 deletion(-)
```

(`.claude/settings.local.json`, modificado automáticamente durante la
sesión por el registro de permisos, se restauró con `git restore` antes de
este corte — no aparece en el diff final.)
