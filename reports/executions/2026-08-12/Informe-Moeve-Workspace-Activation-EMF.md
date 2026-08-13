# Informe de Ejecución — Sprint 9.0: Moeve Workspace Activation

**Fecha:** 2026-08-12
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Activación formal del workspace real de Moeve mediante la
infraestructura ya implementada (`DataWorkspace`, `WorkspaceManifest`,
`ResourceResolver`, `ModuleRegistry`, `WorkspaceReadinessValidator`, SQL
Execution Guard). Ninguna migración ejecutada, ningún SQL Server
abierto, ningún `sample`/`full` real ejecutado. Sin commit.

## 1. Resumen

Se creó el primer `workspace.yaml` **real** de Moeve (fuera del
repositorio, en `%EMF_DATA_ROOT%/projects/moeve/`), reconciliando el
inventario físico ya construido en Sprint 8.8/8.8.1/8.9 contra el
esquema real de `WorkspaceManifest`. Validó sin violaciones a la primera
ejecución. Se ejecutó resolución de recursos real contra el workspace
externo y evaluación de readiness real (no simulada) para los 8 módulos
declarados. Resultado: `PROJECT_WORKSPACE_ACTIVE_WITH_WARNINGS` — el
proyecto está activo; Drills está `ready_with_warnings` en las 3
operaciones evaluadas; los 7 módulos restantes están `blocked` por
ausencia de software (`MODULE_UNKNOWN`), no por ausencia de datos.

## 2. Inventario

Reutilizado de Sprint 8.8 (`moeve-source-inventory.md`), sin reabrir
ningún archivo. 61 archivos ya inventariados; de ellos, 8 ETL + 4
Template + 4 Operational con candidato único resoluble en el manifest;
el resto declarado `status: missing` con la ambigüedad documentada (ver
§ 4, ningún candidato elegido sin evidencia).

## 3. Manifest

- Ruta: `%EMF_DATA_ROOT%/projects/moeve/workspace.yaml` (fuera de Git).
- SHA-256: `b2e1f0a57f224e51672e31264455c3f3947060bb44782cd0db23c0ac0ef55bcb`
- Tamaño: 20 864 bytes.
- `schema_version`: `1.0`. `project.version`: `1.1`.
- 8 módulos declarados, 0 inventados.

## 4. Modules

`module_id` reutilizados sin invención, de
`examples/workspace/workspace.example.yaml` y
`src/bootstrap/module_registry.py`: `drills` (alias `simulacros`),
`safety_meetings`, `moc`, `bypass`, `events`, `ops`, `inspections`,
`corrective_actions` (Action Plans — no `ap`). Tabla completa en
`docs/07-developer-guide/moeve-workspace-activation.md` § 2.

## 5. Templates

Candidato único y resoluble solo para `drills` (`Drills-34.csv`,
`exists=True`). Los otros 7 módulos tienen 0 (bypass, ops — gap de
evidencia ya confirmado en Sprint 8.8) o 2-6 candidatos ambiguos
(safety_meetings, moc, events, inspections — múltiples objetos Enablon
reales por módulo, el esquema no admite más de un `template_csv` por
`ModuleSpec`). Ninguno se eligió por fecha de filesystem ni por
conjetura.

## 6. Operational CSV

Candidato único y resoluble para `drills`, `bypass`, `ops`
(`exists=True` los 3). El resto ambiguo (2 a 12 candidatos según
módulo) — `corrective_actions` es el caso más documentado (3 candidatos,
33/31/31 columnas, backlog P1-13 de Sprint 8.9). Regla dura aplicada:
"un único Operational CURRENT por módulo o `BLOCKER` de ese módulo" —
nunca del proyecto entero.

## 7. ETL

8 de 11 ETL declarados (uno por módulo). 3 quedaron sin declarar por
cubrir un ámbito/versión distinto del ya declarado, no un histórico del
mismo artefacto (`moc`, `events`, `corrective_actions` — ver § 5 de
`moeve-workspace-activation.md`). Nunca marcado `required_for_sample`/
`required_for_full` salvo que el runtime realmente lo consuma (ninguno
lo hace hoy) — es Knowledge/Evidence, no requisito operacional.

## 8. Mappings

`mapping` declarado vía `source: "repo:..."` (git-tracked,
`path: null`) para 7 de 8 módulos — el catálogo First_Axis resuelto
(`catalogo_resuelto_code_ruta_site.csv`) para 6, el catálogo antiguo de
Simulacros para `drills`. `corrective_actions.mapping` queda
`status: missing` deliberadamente — `KC-AP-001` sigue abierto, no se
eligió una fuente de mapeo sin evidencia suficiente. `AttachmentsLast.csv`
(externo, transversal) no se declaró como artefacto — no encaja en
ningún `ARTIFACT_KIND` existente sin forzar su significado (hallazgo de
esquema, § 5 de `moeve-workspace-activation.md`).

## 9. SQL

48 queries ya versionadas en `sql/source_queries/` (Sprint 8.8), cada
módulo referencia su carpeta vía `source: "repo:..."`. El `.zip` externo
de `SQL/` no se declara — ya reconciliado 100% duplicado en Sprint 8.8.1,
no aporta nada nuevo. Ninguna query se ejecutó.

## 10. Errors

`Errors/Requests-12082026-28.csv` (28 filas, Sprint 8.8) declarado solo
bajo `drills`, con nota explícita de que es transversal a todos los
módulos — el esquema no admite un artefacto a nivel de proyecto (hallazgo
de esquema, mismo motivo que Mappings). Clasificación ya existente
(`MIGRATION_RELATED`/... , Sprint 8.8) reutilizada, no re-analizada.

## 11. Validation

```
python main.py workspace validate --manifest "%EMF_DATA_ROOT%/projects/moeve/workspace.yaml"
```

`Resultado: OK -- sin violaciones.` Exit code `0`, a la primera
ejecución (0 iteraciones de corrección necesarias).

## 12. Resolution

`workspace resolve` ejecutado contra el workspace externo real (con
`EMF_DATA_ROOT` exportado — ver § 15, hallazgo de configuración). Todos
los artefactos `drills` con `path` declarado resolvieron con
`exists=True`: `template_csv`, `operational_csv`, `etl`, `errors`. Los
git-sourced (`sql`, `mapping`) resuelven `status=present` sin
comprobación física (por diseño, sin `path`). `catalogs` (drills) resolvió
correctamente como `not_applicable` (Simulacros no usa First_Axis).
Smoke-resolution de los 7 módulos restantes confirmó el mismo patrón:
`present`+`exists=True` donde hay candidato único, `ArtifactMissingError`
limpio donde se declaró `missing` por ambigüedad — sin excepciones no
controladas en ningún caso.

## 13. Readiness

Ejecutado (real, no simulado) para los 8 módulos × operación relevante.
Ver § 14-16.

## 14. Drills

| Operación | Estado | Blockers | Recursos obligatorios |
|---|---|---:|---|
| `sample` | `ready_with_warnings` | 0 | `mapping`, `sql` |
| `comparison` | `ready_with_warnings` | 0 | `operational_csv` |
| `full` | `ready_with_warnings` | 0 | `mapping`, `sql` |

0 blockers en los 3 casos. Únicos warnings: `evidence`/`outputs` ausentes
(no obligatorios, esperado — ninguna ejecución archivada todavía). La
falta de `--allow-real-sql`/`--confirm-full-export` aparece solo como
*next action*, nunca como blocker — confirmado por observación real, no
por lectura de código.

## 15. AP (`corrective_actions`)

`blocked` en las 3 operaciones evaluadas, con un único blocker:
`MODULE_UNKNOWN` (`ModuleRegistry` no conoce el módulo). Distinción
correcta y automática entre "falta software" (este caso) y "faltan
datos" (`ARTIFACT_MISSING`, no se llegó a evaluar porque el gate de
implementación bloquea antes). P1 conocidos (`KC-AP-001`, identidad,
parent resolution, Project Contract, SIMS, attachments) registrados,
ninguno resuelto — ninguno bloquea el *workspace*, todos bloquean
*software* o *conocimiento*.

## 16. Otros módulos

`safety_meetings`, `moc`, `bypass`, `events`, `ops`, `inspections`:
mismo patrón que AP — `blocked`/`MODULE_UNKNOWN`, limpio, sin ruido de
artefactos. Distinción por tipo de gap (no todos convertidos en blocker
de activación):

| Tipo de gap | Módulos |
|---|---|
| Workspace artifact gap (candidatos ambiguos) | safety_meetings, moc, events, inspections |
| Workspace ready, solo falta software | bypass, ops |
| Software implementation gap (los 7) | safety_meetings, moc, bypass, events, ops, inspections, corrective_actions |
| Knowledge gap adicional | corrective_actions (`KC-AP-001`) |

## 17. Project activation

**`PROJECT_WORKSPACE_ACTIVE_WITH_WARNINGS`.** Sin bloqueo estructural
(manifest válido, sin escapes de `EMF_DATA_ROOT`, `project.id`
consistente). `_WITH_WARNINGS` por 4 motivos agregados no bloqueantes:
candidatos ambiguos en 6/8 módulos, `KC-AP-001` abierto, 3 límites de
esquema documentados (§ 5 del documento de activación), y el hallazgo de
configuración de `.env` (§ 15 de este informe).

## 18. Warnings

- 6 de 8 módulos con `template_csv`/`operational_csv` ambiguos, sin
  CURRENT elegido.
- Drills: `evidence`/`outputs` sin archivar (esperado en un workspace
  recién activado).
- 3 límites de esquema (artefacto único por kind, sin scope
  transversal/proyecto, naming basado en `{module}.ext` no representativo
  de la realidad).

## 19. Blockers

Ninguno a nivel de proyecto. A nivel de módulo: los 7 no-drills están
`blocked` por `MODULE_UNKNOWN` en toda operación (software, no datos).

## 20. Next actions

1. Sesiones dedicadas de reconciliación columna-a-columna para resolver
   los candidatos ambiguos de `safety_meetings`/`moc`/`events`/
   `inspections` (ya en backlog: P1-05 a P1-08, Sprint 8.8).
2. Confirmar con el cliente `KC-AP-001` antes de declarar un `mapping`
   para `corrective_actions`.
3. Ninguna acción de software en este sprint (prohibido crear adapters).
4. Exportar `EMF_DATA_ROOT` como variable de entorno real (no solo
   `.env`) al operar `workspace *` desde una shell nueva.

## 21. Tests

`pytest tests/ -v` → **714 passed, 7 skipped** (idéntico antes y después
de este sprint). No se modificó código funcional — el único código
"ejecutado" en este sprint fueron comandos ya existentes de la CLI
(`workspace validate/resolve/readiness`), nunca código nuevo.

## 22. Archivos creados/modificados

**Fuera de Git (no versionable, por diseño):**
```
%EMF_DATA_ROOT%/projects/moeve/workspace.yaml
```

**Dentro del repositorio (versionables):**
```
docs/07-developer-guide/moeve-workspace-activation.md   (nuevo)
docs/07-developer-guide/getting-started.md              (§ 5bis añadida)
docs/01-architecture/external-data-workspace.md         (§ 25 añadida)
docs/01-architecture/workspace-manifest.md              (§ 21 añadida)
docs/01-architecture/workspace-readiness-validator.md   (§ 23 añadida)
reports/executions/2026-08-12/Informe-Moeve-Workspace-Activation-EMF.md
reports/executions/2026-08-12/Informe-Moeve-Workspace-Activation-EMF.txt
```

## 23. `git status --short` / `git diff --stat`

Ver § 24 (control de cambios) — capturados tras la generación de
informes, antes de cualquier commit.

## 24. Recomendación

Aprobar la propuesta de commit de documentación (§ siguiente) —
`workspace.yaml` real permanece fuera de Git, como exige el encargo. No
crear ningún adapter todavía; los siguientes pasos productivos son de
reconciliación de conocimiento (candidatos ambiguos) y de confirmación
con cliente (`KC-AP-001`), no de código.

## 25. Propuesta de commit (documentación, no ejecutado)

```
docs(moeve): activate real workspace manifest and document activation

docs/07-developer-guide/moeve-workspace-activation.md
docs/07-developer-guide/getting-started.md
docs/01-architecture/external-data-workspace.md
docs/01-architecture/workspace-manifest.md
docs/01-architecture/workspace-readiness-validator.md
reports/executions/2026-08-12/Informe-Moeve-Workspace-Activation-EMF.md
reports/executions/2026-08-12/Informe-Moeve-Workspace-Activation-EMF.txt
```

`workspace.yaml` real **no** se incluye — vive fuera de Git por diseño.
Este commit se suma a la propuesta ya pendiente de Sprint 8.8/8.8.1/8.9
(todavía sin aprobar).
