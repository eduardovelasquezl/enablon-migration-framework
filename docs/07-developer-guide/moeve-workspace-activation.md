# Moeve Workspace Activation — Sprint 9.0

**Status:** Implemented (activación real), Sprint 9.0. Convierte el
workspace físico de Moeve, ya inventariado en Sprint 8.8/8.8.1/8.9, en
un `workspace.yaml` real, cargado y validado por la infraestructura ya
existente (`WorkspaceManifest`, `ResourceResolver`, `ModuleRegistry`,
`WorkspaceReadinessValidator`). Este sprint **no ejecuta migraciones, no
abre SQL Server, no ejecuta `sample`/`full`** — solo activa el workspace
como estructura declarada y validable.

## 0. Dónde vive el manifest real

```
%EMF_DATA_ROOT%/projects/moeve/workspace.yaml
```

**Fuera del repositorio Git, deliberadamente** — nunca se commitea (ver
`docs/01-architecture/external-data-workspace.md`). Este documento usa
`%EMF_DATA_ROOT%` en vez de una ruta personal absoluta en todo momento.

- **SHA-256** (calculado tras la creación, Fase 11 del encargo):
  `b2e1f0a57f224e51672e31264455c3f3947060bb44782cd0db23c0ac0ef55bcb`
- **Tamaño:** 20 864 bytes
- **`schema_version`:** `1.0` (declarado dentro del propio manifest,
  `workspace.schema_version`)
- **`project.version`:** `1.1` (primer manifest real, distinto de la
  plantilla de ejemplo `1.0`)
- **`generated_at` (de este documento, no del propio YAML —
  deliberadamente no se auto-referencia):** 2026-08-12

## 1. Principio de activación

Un proyecto puede estar `PROJECT_WORKSPACE_ACTIVE`/`_WITH_WARNINGS`
mientras sus módulos individuales están en estados completamente
distintos entre sí — la activación es por proyecto, el readiness es por
módulo y por operación (`sample`/`full`/`comparison`/`evidence`/
`validation`/`export`). Ver § 8 para el resultado real de Moeve.

## 2. Módulos declarados (Fase 2 — normalización de `module_id`)

Reutilizados de `examples/workspace/workspace.example.yaml` y
`src/bootstrap/module_registry.py` — **ningún `module_id` se inventó**
en este sprint:

| `module_id` canónico | Display name | Alias conocido | Implementado por EMF | Evidencia de workspace |
|---|---|---|---|---|
| `drills` | Drills (BCM / Simulacros) | `simulacros` (`ModuleRegistry`) | **Sí** (experimental) | ETL, Template, Operational, SQL, mapping — todos presentes |
| `safety_meetings` | Safety Meetings (Reuniones de grupo) | — | No | ETL presente; Template/Operational ambiguos (2 objetos reales) |
| `moc` | MOC (Management of Change) | — | No | ETL presente (el más reciente de 2); Template/Operational ambiguos |
| `bypass` | Bypass (BES) | — | No | ETL + Operational presentes; sin Template |
| `events` | Health & Safety Incidents | — | No | ETL presente; Template (6 candidatos) y Operational (12 candidatos) ambiguos |
| `ops` | Behaviour Based Safety (OPS) | — | No | ETL + Operational presentes; sin Template |
| `inspections` | Inspection Management | — | No | ETL presente; Template (3) y Operational (9) ambiguos |
| `corrective_actions` | Action Plans (transversal) | (`ap`, informal, no registrado) | No | Sin ETL/Template/Operational/mapping resueltos a un único candidato — `KC-AP-001` |

**Ningún alias ambiguo se registró.** `ap` se usa coloquialmente en la
documentación de conocimiento (`config/knowledge/moeve/ap/`) pero el
`module_id` real, tanto en `ModuleRegistry` como en el `WorkspaceManifest`,
es `corrective_actions` — confirmado por `config/modules.yaml` y por el
ejemplo ya versionado, no inventado en este sprint.

## 3. Inventario físico reconciliado (Fase 1, 3-9)

El inventario físico completo ya existía (Sprint 8.8,
`moeve-source-inventory.md`) — este sprint lo reconcilió contra el
esquema real de `WorkspaceManifest`, sin volver a abrir ningún archivo.
Resumen por categoría:

| Categoría | Archivos reales | Declarados en el manifest |
|---|---:|---|
| ETL | 11 | 8 (uno por módulo — 3 módulos tienen un segundo ETL no modelable, ver § 5) |
| CSV Template | 15 | 3 módulos con candidato único resoluble (drills); el resto ambiguos por diseño (§ 5) |
| CSV Operational | 30 CSV + 2 XLSX | 4 módulos con candidato único (drills, bypass, ops); el resto ambiguos |
| Mappings | `AttachmentsLast.csv` + 1 `.zip` | No modelados como artefacto de módulo — ver § 5 (hallazgo de esquema) |
| SQL (externo) | 1 `.zip` (ya reconciliado 100% duplicado contra Git en Sprint 8.8.1) | No declarado — cada módulo referencia su SQL ya versionado en Git |
| Errors | 1 CSV | Declarado solo bajo `drills` (transversal, ver § 5) |
| Catalogs/Evidence/Outputs/Archive | 0 (carpetas vacías) | `catalogs` declarado vía `repo:inputs/entity_catalog/First_Axis_export_bruto.csv` para 6 de 8 módulos; `evidence`/`outputs` = `missing` en todos |

## 4. Naming (Fase 4-5)

**Ningún archivo real del workspace de Moeve sigue la convención
`{module}.ext`** de `examples/workspace/workspace.example.yaml` — todos
preservan su nombre de export/ETL original (p. ej.
`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`,
`Action Plans-10082026-163.csv`). El manifest real fija
`naming_convention: preserve_source_name` para **todos** los kinds (no
solo `template_csv`, como en la plantilla de ejemplo) — decisión basada
en evidencia observada, no en preferencia. `workspace validate` confirma
0 violaciones de nomenclatura con este ajuste (§ 6).

Ningún archivo se renombró, movió ni copió — todas las rutas del
manifest son los nombres reales, tal cual existen en el filesystem.

## 5. Hallazgos de esquema (no bugs — límites de diseño ya existentes)

Durante la reconciliación aparecieron 3 situaciones reales que el
esquema actual de `WorkspaceManifest` no modela limpiamente. Ninguna es
un defecto — son límites de un diseño pensado originalmente para un
módulo de un solo origen (Drills). Se documentan para una futura
extensión, no se corrigen en este sprint (fuera de alcance, y el encargo
prohíbe crear adapters/resolver `KC-AP-001`):

1. **Un solo artefacto por `kind` por módulo.** 6 de los 8 módulos
   (`safety_meetings`, `moc`, `events`, `inspections` por múltiples
   objetos Enablon reales; `corrective_actions` y `moc` también por
   múltiples ETL de ámbito/versión distintos) tienen más de un candidato
   real para `template_csv`/`operational_csv`/`etl`. El esquema no
   admite una lista — se optó por `status: missing` con la ambigüedad
   documentada en `description`, nunca por elegir un candidato sin
   evidencia (Fase 4/5 del encargo lo exige explícitamente).
2. **Sin concepto de artefacto transversal/a nivel de proyecto.** El
   documento de Attachments (`Mappings/AttachmentsLast.csv`) y el
   catálogo de errores (`Errors/Requests-12082026-28.csv`) son, por
   evidencia ya confirmada en Sprint 8.8, recursos usados por **todos**
   los módulos, no por uno — pero `ArtifactSpec` vive dentro de un único
   `ModuleSpec`. Se declaró `errors` solo bajo `drills` (con una nota
   explícita de que es transversal) y `AttachmentsLast.csv` **no se
   declaró en absoluto** (no encaja en ningún `ARTIFACT_KIND` existente
   sin forzar el significado). Backlog para una futura versión del
   esquema: un nivel `project.artifacts` o un `scope` en `ArtifactSpec`.
3. **`AttachmentsLast.csv` y el `.zip` de SQL no se declaran.** El `.zip`
   de SQL ya se reconcilió 100% duplicado contra `sql/source_queries/`
   en Sprint 8.8.1 — no aporta nada nuevo que declarar. El `.zip` de
   Mappings (workbooks de eje ITP/GCT + motor Office Script, Sprint
   8.8.1/8.9) es Knowledge/Evidence ya gobernado por
   `config/knowledge/moeve/ap/` y `mapping-governance.md` — no es
   responsabilidad del `WorkspaceManifest` volver a declararlo.

## 6. Validación del manifest (Fase 12)

```
python main.py workspace validate --manifest "%EMF_DATA_ROOT%/projects/moeve/workspace.yaml"
```

Resultado, primera ejecución, sin iteración necesaria:

```
Proyecto:  moeve (Moeve)
Módulos:   drills, safety_meetings, moc, bypass, events, ops, inspections, corrective_actions

Resultado: OK -- sin violaciones.
```

Exit code `0`.

## 7. Resolución de recursos (Fase 13)

**Hallazgo de configuración (no un bug de negocio):** `workspace
resolve`/`validate`/`readiness` no cargan `.env` automáticamente — solo
`src/db/connection.py` llama a `load_dotenv()`, y ningún comando de
`workspace` pasa por ahí (por diseño: nunca tocan SQL). Un usuario debe
tener `EMF_DATA_ROOT` como variable de entorno real de su shell (no solo
en `.env`) para que estos comandos vean el workspace externo. Se
documenta como **`IMPROVEMENT`** (posible `load_dotenv()` también en el
entrypoint de `workspace`), no como bug — no se corrige en este sprint
sin aprobación (Fase 23 del encargo).

Con `EMF_DATA_ROOT` exportado, resolución real contra el workspace
externo (Drills, todos los artefactos declarados):

| Artefacto | `status` | `exists` |
|---|---|---|
| `template_csv` (`Drills-34.csv`) | present | **True** |
| `operational_csv` (`Simulacros CCE.xlsx`) | present | **True** |
| `etl` (`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`) | present | **True** |
| `errors` (`Requests-12082026-28.csv`) | present | **True** |
| `sql` (git-sourced) | present | no comprobable (sin `path`, por diseño) |
| `mapping` (git-sourced) | present | no comprobable (sin `path`, por diseño) |
| `catalogs` | not_applicable | (no resoluble, esperado — Simulacros no usa First_Axis) |
| `evidence` | missing | (esperado — ninguna ejecución archivada todavía) |

Smoke-resolution del resto de módulos (`etl`/`template_csv`/
`operational_csv`) confirma exactamente los estados declarados en el
manifest — `present`+`exists=True` donde hay candidato único, error
`ArtifactMissingError` limpio (sin ruido) donde se declaró
`status=missing` por ambigüedad.

## 8. Readiness — Drills (Fase 14-15, caso operativo principal)

```
python main.py workspace readiness --manifest <manifest> --module drills --operation <sample|comparison|full> --require-files
```

| Operación | Estado | Blockers | Warnings | Recursos obligatorios |
|---|---|---:|---|---|
| `sample` | **`ready_with_warnings`** | 0 | `evidence`/`outputs` ausentes (no obligatorios) | `mapping`, `sql` |
| `comparison` | **`ready_with_warnings`** | 0 | ídem | `operational_csv` |
| `full` | **`ready_with_warnings`** | 0 | ídem | `mapping`, `sql` |

Confirmado exactamente lo que pedía Fase 15: **`sample` no bloquea por
ETL/Template/Operational** (no son `required_for_sample` en el manifest,
y el software solo exige `sql`+`mapping`, ambos git-sourced y presentes);
**`comparison` sí exige `operational_csv`** como Project Contract (ya
presente, `exists=True`); **`full` nunca se ejecuta** — solo se evalúa
preparación. En los 3 casos, la falta de `--allow-real-sql`/
`--confirm-full-export` aparece únicamente como *next action* de
ejecución posterior, nunca como blocker de readiness (`SQL_AUTHORIZATION_INFO`,
severidad `info`, nunca `blocker`).

## 9. Readiness — Action Plans (`corrective_actions`) (Fase 16)

```
=== Workspace Readiness ===
Module:             corrective_actions
Operation:          sample
Status:             blocked
Blockers (1):
  - [MODULE_UNKNOWN] El software no conoce el módulo 'corrective_actions'...
```

**Distinción correcta, confirmada por el propio validador (no
interpretada por este informe):** el bloqueo es `MODULE_UNKNOWN`
(`ModuleRegistry`, capa de software), no un `ARTIFACT_MISSING`
(`WorkspaceManifest`, capa de datos). El resultado nunca dice "faltan
datos" — dice explícitamente "el software no conoce este módulo",
exactamente la distinción que pedía el encargo. `required_artifacts:
(ninguno)` porque el gate de implementación bloquea *antes* de evaluar
ningún artefacto.

P1 conocidos registrados y **no resueltos** en este sprint (prohibido
explícitamente):

- `KC-AP-001` (mecanismo de mapeo de eje, `OPEN — CURRENT STATIC
  MECHANISM STRONGLY EVIDENCED`).
- Identidad AP (`PROPOSED DESIGN`, `action-plans-native-design.md` § 1).
- Política de resolución de padres (`PROPOSED DESIGN`, § 3).
- Project Contract AP (69 vs. 31-33 columnas, sin confirmar columna a
  columna — backlog P1-13).
- SIMS origen 12 (`PARTIAL_MATCH`, backlog P2-09).
- Attachments (conocimiento separado de implementación legacy, § 4/5 de
  `c003-knowledge-adoption.md`).

Ninguno de estos P1 bloquea la activación del **workspace** de Moeve —
todos son bloqueo de **software** (`corrective_actions` sin adaptador) o
de **conocimiento** (`KC-AP-001` abierto), categorías distintas de
"faltan artefactos en el workspace".

## 10. Readiness matrix completa (Fase 19)

| Module | Software | Workspace | Sample | Comparison | Full | Main blocker |
|---|---|---|---|---|---|---|
| `drills` | Implemented (experimental) | Ready (evidence/outputs sin archivar todavía) | `ready_with_warnings` | `ready_with_warnings` | `ready_with_warnings` | Ninguno bloqueante — autorización SQL es prerrequisito de ejecución, no de readiness |
| `safety_meetings` | Not implemented | Partial (ETL sí; Template/Operational ambiguos) | `blocked` (MODULE_UNKNOWN) | `blocked` | `blocked` | Software no implementado |
| `moc` | Not implemented | Partial (ETL sí, el más reciente de 2; Template/Operational ambiguos) | `blocked` | `blocked` | `blocked` | Software no implementado |
| `bypass` | Not implemented | Ready (ETL + Operational únicos; sin Template) | `blocked` | `blocked` | `blocked` | Software no implementado |
| `events` | Not implemented | Partial (ETL sí; 6+12 candidatos ambiguos) | `blocked` | `blocked` | `blocked` | Software no implementado |
| `ops` | Not implemented | Ready (ETL + Operational únicos; sin Template) | `blocked` | `blocked` | `blocked` | Software no implementado |
| `inspections` | Not implemented | Partial (ETL sí; 3+9 candidatos ambiguos) | `blocked` | `blocked` | `blocked` | Software no implementado |
| `corrective_actions` | Not implemented | Blocked (sin candidato único en ningún kind, por diseño — `KC-AP-001`) | `blocked` | `blocked` | `blocked` | Software no implementado (adaptador pendiente) + `KC-AP-001` |

Todos los resultados de esta tabla son evaluaciones reales
(`python main.py workspace readiness`), no inventadas.

## 11. Estado de activación del proyecto (Fase 18)

**`PROJECT_WORKSPACE_ACTIVE_WITH_WARNINGS`.**

No hay ningún bloqueo estructural: manifest válido (§ 6), ningún path
escapa del `EMF_DATA_ROOT` (`SecurityCheck` sin hallazgos de
`DATA_ROOT_ESCAPE` en ninguna de las evaluaciones realizadas),
`project.id` consistente en las 8 declaraciones de módulo, configuración
no corrupta. Se marca `_WITH_WARNINGS`, no `ACTIVE` a secas, por 4
motivos reales agregados a nivel de proyecto (ninguno bloqueante):

1. 6 de 8 módulos tienen candidatos ambiguos de Template/Operational sin
   resolver (§ 5, punto 1).
2. `corrective_actions` tiene `KC-AP-001` abierto y ningún adaptador de
   software.
3. Un límite de esquema real y documentado (artefactos transversales sin
   modelar, § 5, puntos 2-3).
4. Los comandos `workspace *` no cargan `.env` automáticamente (§ 7).

## 12. Project Contract de Drills (Fase 20)

Con el Operational CSV real ya registrado (`Simulacros CCE.xlsx`,
`exists=True`, § 7) — **no se leyó ninguna fila** en este sprint.
Estructura reutilizada de Sprint 8.1/8.8 (`drills-csv-contract.md`,
`knowledge-traceability-matrix.md`): 36 columnas reales confirmadas,
`Reference`/`StartingDate` como campos estándar, `CS_Typology`/
`CS_HistoricalOriginID`/`CS_Letter`/`CS_ImpactedEntities`/
`CS_WorkflowStatus`/`CS_HistoricalDataOrigin`/`CS_Duration`/
`CS_HistoricalDrillAttendees` entre los `CS_` ya trazados (10 de 36
🟢, tras la resolución de `OQ-ETL-01`/`OQ-ETL-02` en Sprint 8.8.1).
`contract_role: project` ya declarado en el manifest (§ 0 de este
documento), `uniqueness`: candidato único, sin otros ficheros
Operational reales en competencia para Drills.

**Advertencia pendiente, no resuelta aquí:** el candidato real es
`.xlsx`, no `.csv` (`Simulacros CCE.xlsx`) — su estructura columna a
columna no se ha confirmado (backlog P3-06, `moeve-mapping-backlog.md`).
Esto no bloquea `comparison` readiness (el artefacto existe y resuelve),
pero sí sería relevante antes de una comparación real dato a dato.

## 13. Cómo operar este workspace (guía de mantenimiento)

### Añadir un nuevo módulo

1. Confirmar el `module_id` canónico contra `config/modules.yaml` /
   `examples/workspace/workspace.example.yaml` — nunca inventar uno.
2. Añadir la entrada bajo `modules:` en `workspace.yaml`, con
   `enabled: false` hasta que exista un `pipeline_factory` real en
   `src/bootstrap/module_registry.py`.
3. Ejecutar `workspace validate` tras cada cambio.

### Actualizar un artefacto (ETL, mapping, SQL...)

1. Nunca mover, renombrar ni copiar el archivo real.
2. Actualizar `path`/`status`/`description` en el manifest para reflejar
   la realidad — nunca dejar un `status=present` que ya no corresponde a
   un archivo existente.
3. Re-ejecutar `workspace validate` + `workspace resolve --require-exists`.

### Cambiar el Template CURRENT

Si aparece una versión más reciente del CSV Template exportado de
Enablon: **no sobrescribir** el artefacto existente sin evidencia de
vigencia (Fase 4 del encargo, este sprint y Sprint 8.8 lo repiten
igual). Actualizar `path` solo cuando se confirme cuál es la versión
vigente — si hay ambigüedad, dejar `status: missing` con los candidatos
documentados en `description`, igual que se hizo aquí para 6 de 8
módulos.

### Cambiar el Operational CURRENT

Mismo principio — un módulo solo puede tener un `operational_csv`
`CURRENT` a la vez (regla dura de Fase 5). Si aparecen varios candidatos
sin evidencia de cuál es el vigente, es un `BLOCKER` de ese módulo, no
del proyecto.

### Backups del manifest

Política simple para este primer manifest (Fase 11 — no se crea todavía
un sistema de versionado complejo): SHA-256 calculado y registrado en
este documento (§ 0) tras cada creación/modificación relevante. Para
futuras modificaciones, backup en:

```
%EMF_DATA_ROOT%/projects/moeve/Archive/workspace-manifest/<timestamp>/workspace.yaml
```

No se ha creado ningún backup en este sprint (primera versión, nada que
respaldar todavía).

### Validación

```
python main.py workspace validate --manifest "%EMF_DATA_ROOT%/projects/moeve/workspace.yaml"
python main.py workspace resolve --manifest <manifest> --module <id> --artifact <kind> --require-exists
python main.py workspace readiness --manifest <manifest> --module <id> --operation <sample|full|comparison|evidence|validation|export> --require-files
```

Ninguno de los tres accede a SQL Server ni ejecuta nada.
