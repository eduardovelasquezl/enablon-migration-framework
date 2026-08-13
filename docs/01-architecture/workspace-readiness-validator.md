# Workspace Readiness Validator

Sprint 8.7. Implementación: `src/core/readiness_validator.py`. CLI:
`python main.py workspace readiness`. Tests: `tests/test_readiness_validator.py`,
`tests/test_readiness_validator_drills_integration.py`,
`tests/test_cli_workspace_readiness.py`.

## 1. Propósito

Responder, antes de intentar cualquier operación, a una única pregunta
compuesta: *"¿puede empezar `<operación>` para `<módulo>` en `<proyecto>`, y
si no, qué falta exactamente, y eso bloquea o solo advierte?"*.

Antes de este sprint, esa pregunta no tenía una única respuesta: `ModuleRegistry`
sabía si el software podía ejecutar un módulo, `WorkspaceManifest` declaraba
qué artefactos exigía un proyecto, y `ResourceResolver` resolvía un artefacto
a la vez -- pero ningún componente los combinaba. `ensure_module_runnable()`
(`src/core/module_registry.py:433-473`) era la pieza más cercana, pero
llevaba desde su creación (Sprint 8.6) sin ningún llamador real (ver
`module-registry.md` § 20) y nunca comprobaba artefactos.

## 2. Alcance

- Evalúa preparación PREVIA a una operación -- nunca el resultado de
  ejecutarla.
- Compone `ModuleRegistry` + `WorkspaceManifest` + `ResourceResolver`
  (`SecurityCheck` además lee, sin mutar, `SqlExecutionGuard`).
- Genérico: ningún módulo concreto (Drills u otro) está mencionado dentro de
  `src/core/readiness_validator.py`.
- Opcionalmente comprueba existencia física (`require_physical_files=True`),
  reutilizando `ResourceResolver`, nunca reimplementando esa comprobación.

## 3. Fuera de alcance

- No ejecuta ningún pipeline, no llama a `pipeline_factory`.
- No abre SQL, no llama a `sql_execution_guard.grant()`/`revoke()`, no
  concede autorización -- solo lee `current_authorization()` para una nota
  informativa (verificado por
  `tests/test_readiness_validator.py::test_readiness_no_llama_a_grant_ni_revoke_del_guard`,
  análisis AST, no de texto).
- No lee contenido de archivos, no calcula checksums, no crea directorios ni
  archivos.
- No valida reglas de negocio de un módulo (esas viven en su propio
  pipeline/validator).
- No sustituye `workspace validate` (forma del manifest) ni
  `workspace resolve` (un artefacto suelto) -- los complementa.

## 4. Arquitectura

```
ModuleRegistry            WorkspaceManifest           ResourceResolver
(¿sabe el software?)  →   (¿lo declara el proyecto,   →  (¿resuelve/existe?)
                           qué exige por operación?)
        \_______________________  |  ________________________/
                                   v
                    WorkspaceReadinessValidator
                    (agrega, decide severidad, nunca
                     delega la decisión en una excepción
                     de las capas anteriores)
                                   |
                                   v
                          ReadinessAssessment
```

Precedencia (Fase 1/2 del encargo, fijada tras el inventario de este
sprint): `ModuleRegistry` decide si el software es capaz → `WorkspaceManifest`
decide qué exige el proyecto para esa operación concreta → `ResourceResolver`
confirma resolución/existencia → el validador agrega. Ningún nivel reimplementa
al anterior.

## 5. `ReadinessRequest`

Campos: `project_id, module_id, operation, manifest, registry, resolver,
require_physical_files=False, mode=None, strict=False`. Nunca contiene
credenciales, conexiones, `DataFrame`s ni filas SQL -- solo referencias a los
tres componentes que ya conocen esos datos.

`strict=True`: escala cualquier `WARNING` a bloqueo del estado final --
pensado para un gate de CI/automatización que exige cero advertencias, no
solo cero bloqueos.

## 6. `ReadinessOperation`

Vocabulario cerrado: `sample, full, comparison, evidence, validation, export`.
Distinto de `ModuleCapability` ("lo que el software puede hacer"): una
operación puede exigir varias capacidades a la vez.

| Operación | Capacidades exigidas | Artefactos obligatorios (fuente) |
|---|---|---|
| `sample` | EXPORT, SAMPLE, VALIDATION (+ modo `sample`) | `ArtifactSpec.required_for_sample` |
| `full` | EXPORT, FULL, VALIDATION (+ modo `full`) | `ArtifactSpec.required_for_full` |
| `comparison` | COMPARISON | `contracts.project.artifact` (no un kind fijo) |
| `validation` | VALIDATION | `ArtifactSpec.required_for_sample` (sin flag propio; ver § 11) |
| `evidence` | EVIDENCE | ninguno (lee un `run_dir` ya completado, no el manifest) |
| `export` | EXPORT | ninguno (agnóstico de modo) |

## 7. `ReadinessStatus`

`READY` / `READY_WITH_WARNINGS` / `BLOCKED`. Nunca describen el resultado de
una migración -- solo si puede EMPEZAR.

## 8. `ReadinessCheck`

Nueve checks, clases con `name` + `run(ctx) -> list[ReadinessIssue]`, en
orden fijo (mismo orden que Fase 7 del encargo): `ModuleImplementationCheck`,
`ProjectModuleDeclarationCheck` (ambos dentro de `_run_gate`, cortan el resto
si fallan -- nada más es computable sin un `ModuleDefinition`+`ModuleSpec`
resueltos), `CapabilityCheck`, `ArtifactDeclarationCheck`,
`ArtifactStatusCheck`, `ResourceResolutionCheck`, `PhysicalExistenceCheck`,
`ContractCheck`, `SecurityCheck` -- estos últimos siete siempre se ejecutan
todos, acumulando issues, para devolver la lista completa de problemas en una
sola llamada.

## 9. `ReadinessIssue`

`code, severity, message, project_id, module_id, operation, artifact_type,
declared_path, required, source_component, remediation, reference`. Nunca una
excepción -- mismo patrón que `validate_manifest()`. Deduplicado por
`(code, artifact_type)`.

## 10. `ReadinessAssessment`

`assessment_id, timestamp, project_id, module_id, operation, status, checks,
issues, blockers, warnings, informational, required_artifacts,
optional_artifacts, resolved_resources, missing_resources,
generated_resources, summary, recommended_next_action`. `module_id` es
siempre el canónico (si `ReadinessRequest.module_id` fue un alias como
`simulacros`, el assessment reporta `drills`).

## 11. Política de requisitos por operación

**Decisión de diseño (deliberada, documentada explícitamente por desviarse
del boceto literal de la Fase 6 del encargo):** no se introduce un bloque
`operation_requirements:` nuevo en el manifest. `ArtifactSpec.required_for_sample
/required_for_full/required_for_comparison` (existente desde Sprint 8.4) ya
tiene exactamente esa granularidad por operación -- introducir un segundo
mecanismo paralelo habría violado "no duplica sus responsabilidades"
(criterio de aceptación #5) y creado una tercera fuente de verdad. Este
sprint promueve esos tres flags a la única fuente REAL de qué bloquea cada
operación (antes solo los comprobaba un guard de esquema al cargar, nunca
en runtime -- ver Fase 1 del informe de este sprint).

### 11.1 Relación exacta entre los cinco campos (verificada por inspección de código, 2026-08-03)

| Campo | Nivel | Granularidad de operación | Leído por el validador | Efecto |
|---|---|---|---|---|
| `ArtifactSpec.required_for_sample` | Manifest (proyecto) | Sí (`sample`) | Sí -- `_artifact_required_kinds()` | **Bloquea** (`ARTIFACT_MISSING` si falta) |
| `ArtifactSpec.required_for_full` | Manifest (proyecto) | Sí (`full`) | Sí -- `_artifact_required_kinds()` | **Bloquea** |
| `ArtifactSpec.required_for_comparison` | Manifest (proyecto) | Sí (`comparison`, indirectamente vía `contracts.project_artifact`) | Sí -- `ContractCheck` | **Bloquea** |
| `ModuleDefinition.required_artifact_types` | Software (`ModuleRegistry`) | No (set plano, mismo para toda operación) | Sí, pero solo para `sample`/`full` -- `ArtifactDeclarationCheck` | **Nunca bloquea** -- solo `WARNING` (`ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`) si el manifest no declara en absoluto un kind que el software espera |
| `ModuleDefinition.optional_artifact_types` | Software (`ModuleRegistry`) | No | **No** -- ningún check de `readiness_validator.py` lo lee (confirmado por `grep`, único uso real del repo es `modules_show`/validación de solape en `module_registry.py`) | Ninguno -- metadato puramente informativo hoy |

**Confirmación explícita:** la fuente EFECTIVA (la única que puede producir
un `BLOCKER`) de obligatoriedad por operación es
`ArtifactSpec.required_for_sample/full/comparison`. Los dos campos de
`ModuleDefinition` (`required_artifact_types`/`optional_artifact_types`) se
mantienen como metadatos generales del software -- no contradicen ni
sobrescriben los requisitos por operación (viven en una capa distinta,
nunca se funden con ellos, ver § 4 "precedencia"), y no se usan como una
segunda fuente de bloqueo. `required_artifact_types` se degrada a una señal
de alerta no bloqueante (`ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`, `WARNING`)
cuando el proyecto no declara en absoluto un kind que el software espera.
`optional_artifact_types` ha quedado **completamente redundante** frente al
cálculo que ya hace el propio validador (`ctx.optional_kinds =
artefactos_declarados - required_kinds`, por operación) -- no aporta ninguna
información que el validador no derive ya del manifest. Se documenta como
deuda técnica en § 21 para una futura simplificación (candidato a
deprecar/retirar de `ModuleDefinition` si un segundo módulo real confirma
que nunca hace falta, "No Abstraction Without a Real Consumer").

`comparison` no asume `operational_csv` -- su artefacto obligatorio es
`contracts.project.artifact`, lo que apunte el manifest (Core genérico, sin
nombres de kind de Drills hardcodeados).

`validation` reutiliza `required_for_sample`: no existe un flag propio en el
manifest, y el `validation_report` se produce como parte de un sample/full
real, nunca de forma aislada -- decisión documentada aquí para no inventar
una regla de negocio no verificada (CLAUDE.md).

Reglas confirmadas por los tests de integración (`tests/test_readiness_validator_drills_integration.py`):
ETL nunca bloquea (nunca aparece en `required_for_*` de ningún manifest real);
Template CSV no bloquea `sample` (por dato, no por código especial-casing
`kind="template_csv"`); Operational CSV no bloquea `sample` pero sí `comparison`
cuando es el Project Contract; un output generado nunca se exige pre-existente
(mismo comportamiento que ya tenía `ResourceResolver` para `generated=True`);
un mapping sin `path` (git-tracked, `status=present`) no bloquea -- se acepta
la declaración (`ARTIFACT_PRESENT_NOT_PATH_RESOLVABLE`, `INFO`).

## 12. `ModuleRegistry`

`ModuleImplementationCheck` distingue dos bloqueos: `MODULE_UNKNOWN` (el
software no registra el módulo en absoluto) y `MODULE_NOT_EXECUTABLE` (lo
registra, pero `status` es `planned` o `deprecated` sin `pipeline_factory` --
roadmap, no implementación real). `CapabilityCheck` comprueba capacidades
múltiples por operación + `supported_modes` para `sample`/`full`.
`ProjectModuleDeclarationCheck` reutiliza `ensure_module_runnable()` --
primer llamador real de esa función (cierra la deuda de `module-registry.md`
§ 20).

## 13. `WorkspaceManifest`

Fuente de `required_for_sample/full/comparison`, `status` por artefacto,
`contracts.platform/project/emf`. El validador nunca crea, modifica ni
revalida la forma del manifest -- eso sigue siendo `WorkspaceManifestLoader`
+ `validate_manifest()`, sin cambios en este sprint.

## 14. `ResourceResolver`

`ResourceResolutionCheck` siempre llama a `resolve()` con `required=False`
-- la severidad la decide el validador a partir de `ArtifactStatus`, nunca
una excepción del resolver (evita el caso real detectado en la Fase 1: un
artefacto `status=present`/`path=None` -- p. ej. `sql`/`mapping` de Drills,
resueltos vía `source: "git:..."` -- haría que `required=True` lanzara
`ArtifactMissingError` incorrectamente). Cualquier `ResourceResolutionError`
real (ruta insegura, categoría no configurada) se traduce a un `BLOCKER`
`RESOURCE_RESOLUTION_ERROR`, nunca se deja escapar.

## 15. Contratos

`ContractCheck`: `comparison` exige `contracts.project.artifact` declarado
(`PROJECT_CONTRACT_MISSING` si no); además, si el artefacto referenciado no
tiene `required_for_comparison=true`, emite `CONTRACT_ARTIFACT_NOT_MARKED_REQUIRED`
(`WARNING`) -- refleja el hallazgo de la Fase 1 de que ambos campos podían
divergir sin ninguna validación previa.

## 16. Recursos generados

`kind="outputs"` con `contracts.emf.generated=true`: `PhysicalExistenceCheck`
nunca lo bloquea aunque `require_physical_files=True` y el archivo no exista
todavía (`GENERATED_RESOURCE_NOT_YET_PRESENT`, `INFO`) -- mismo comportamiento
que ya tenía `ResourceResolver` para recursos generados, el validador no lo
reimplementa.

## 17. Seguridad

`SecurityCheck`: (a) nunca llama a `grant()`/`revoke()`/`get_engine()` --
solo lee `sql_execution_guard.current_authorization()` para una nota
informativa (`SQL_AUTHORIZATION_INFO`); (b) defensa en profundidad: si algún
`resolved_path` cayera dentro de `PROJECT_ROOT` (no debería ocurrir --
`DataWorkspace`/`ManifestSchemaError` ya lo impiden en dos capas anteriores),
emite `DATA_ROOT_ESCAPE` (`BLOCKER`). El validador nunca abre, lee ni
calcula el checksum de ningún archivo.

## 18. CLI

```
python main.py workspace readiness --manifest <path> --module <id> --operation <op>
    [--require-files] [--format text|json] [--strict]
```

Exit codes (deliberadamente distintos del resto de la CLI, que usa 0/1
binario): `0` READY, `1` READY_WITH_WARNINGS, `2` BLOCKED, `3` error
técnico/config (manifest inválido, etc.). Nunca requiere ni acepta
`--allow-real-sql`. `--format json` sirve para automatización -- nunca
incluye credenciales ni connection strings.

## 19. Drills

Único módulo con pipeline ejecutable hoy -- comportamiento verificado en
`tests/test_readiness_validator_drills_integration.py` sin ningún
`if module_id == "drills"` en `src/core/`: `sample` sin comparación →
READY/READY_WITH_WARNINGS, nunca bloqueado por ETL/Template/Operational
ausentes; `comparison` bloquea sin `operational_csv`; `full` evalúa sin
pedir autorización SQL; módulo deshabilitado → BLOCKED; módulo no
registrado (`ModuleRegistry` vacío) → `MODULE_UNKNOWN`, distinto de
cualquier `ARTIFACT_*`.

## 20. Extensión a otros módulos

Cualquier módulo nuevo que se registre en `ModuleRegistry` (composition
root, `src/bootstrap/module_registry.py`) y se declare en un
`WorkspaceManifest` obtiene readiness automáticamente -- no requiere tocar
`src/core/readiness_validator.py`. Solo depende de que su manifest declare
`required_for_sample/full/comparison` correctamente por artefacto.

## 21. Deuda técnica

- `validation` reutilizando `required_for_sample` es una aproximación
  documentada, no una regla de negocio confirmada por el cliente -- revisar
  si en el futuro se necesita un flag propio.
- `ModuleDefinition.required_artifact_types` sigue sin una relación
  programática fuerte con `required_for_sample/full` del manifest (por
  diseño, ver § 11) -- si en el futuro se detectan falsos negativos de la
  señal `ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED`, revisar.
- `ModuleDefinition.optional_artifact_types` ha quedado completamente
  redundante frente al cálculo que ya hace el validador
  (`ctx.optional_kinds`, por operación, a partir del manifest) -- ningún
  check de este sprint lo lee (ver tabla de § 11.1). Candidato a
  simplificar/retirar de `ModuleDefinition` en un futuro sprint si un
  segundo módulo real confirma que nunca hace falta como metadato
  independiente; no se retira en este sprint por no ser parte del alcance
  pedido y para no tocar `module_registry.py` más de lo necesario.
- `export`/`evidence` no tienen artefactos obligatorios modelados -- si
  aparece un caso real que lo necesite, extender `_ARTIFACT_FLAG_FOR_OPERATION`.
- Las credenciales/conectividad SQL (`drills-real-data-inventory.md` § 8,
  "Imprescindible") siguen sin modelarse como artefacto -- se surfacean solo
  como nota informativa vía `SecurityCheck`, nunca como bloqueo de readiness
  (decisión consciente: disponibilidad de credenciales nunca implica
  autorización de uso, CLAUDE.md).

## 22. Criterios de aceptación

Ver `reports/executions/2026-08-03/Informe-Workspace-Readiness-Validator-EMF.md`
§ 16 para el cotejo punto por punto contra los 20 criterios del encargo de
este sprint.

## 23. Sprint 9.0 — primera evaluación real (Moeve)

Primera vez que `WorkspaceReadinessValidator` se ejecuta contra un
workspace físico real, no un ejemplo. Confirma en la práctica el
comportamiento diseñado: Drills (único módulo en `ModuleRegistry`)
devuelve `ready_with_warnings` en `sample`/`comparison`/`full`, sin
bloquear nunca por falta de `--allow-real-sql`; los 7 módulos restantes
devuelven `blocked`/`MODULE_UNKNOWN` de forma limpia, sin ningún ruido de
artefactos (el gate de implementación bloquea antes de evaluarlos) —
exactamente la distinción "el software no lo sabe ejecutar" vs. "faltan
datos" que motivó este validador. Ver
`docs/07-developer-guide/moeve-workspace-activation.md` §§ 8-10 para la
matriz completa.
