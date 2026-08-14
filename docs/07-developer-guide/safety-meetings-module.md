# Safety Meetings — tercer módulo real del EMF (Sprint 9.7)

**Status:** `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY`. Ningún SQL real ejecutado
todavía. Primer módulo construido directamente sobre el Export Engine mínimo
(Sprint 9.6) -- no hubo migración, nació ya consumiéndolo.

## 0. Objetivo

Implementar Safety Meetings (objeto `Group_Meetings`) como tercer módulo real
del EMF, y usarlo para verificar con código real si el Export Engine mínimo
(`src/export/engine/`) reduce de verdad el coste de incorporar un módulo
nuevo.

## 1. Evidencia encontrada

### 1.1 Fuente / sistema y single-object vs. multi-object

- Sistema origen: `prevencion` (ITP), tabla `ITP_REUNION_GRUPO`.
- **Safety Meetings es, en Enablon, 2 objetos reales distintos** --
  confirmado por 3 fuentes independientes, no asumido:
  1. `workspace.yaml` real de Moeve ya lo documentaba (antes de este
     sprint): *"2 candidatos reales, sin artefacto único posible con el
     esquema actual"* para `template_csv` y `operational_csv`.
  2. `sql/source_queries/SM/` tiene 3 ficheros: `SM2025.sql`
     (`ITP_REUNION_GRUPO`, objeto principal), `Asistentes_SM2025.sql`
     (`ITP_ASISTENTES_RG`, tabla hija por `IDReunionGrupo`),
     `Acciones_SM2025.sql` (`ITP_RG_ACCIONES_CORRECTORAS`, alimenta Action
     Plans -- `config/modules.yaml::ap.idorigenac_por_modulo.safety_meetings: [11]`,
     fuera de alcance de este sprint por instrucción explícita).
  3. Los CSV reales confirman 2 objetos Enablon con ciclos de vida
     distintos: `Group Meetings-40.csv` (Template) / `Reuniones de grupo
     import completo.csv` (Operational, 1734 filas reales) para
     `Group_Meetings`; `Update External Meeting Participations-42.csv`
     (Template) / `Asistentes_ReunionesGrupo.csv` (Operational, cabecera
     `Meeting;Attendee;Type;Company;CompanyOther;Id`) para
     `Update_External_Meeting_Participations` -- este segundo objeto
     referencia al primero por el **`Id` que Enablon asigna tras la
     carga**, no por `CS_HistoricalOriginID` -- estructuralmente es un paso
     de enlace posterior a la migración, no un export histórico paralelo.

**Decisión (Fase 2/3 del encargo): GO, acotado a `Group_Meetings` --
objeto principal inequívoco** (tabla padre, sin dependencia de FK, mayor
volumen). `Update_External_Meeting_Participations` queda **fuera de
alcance, registrado como `MULTI_OBJECT_GAP`** -- no se fuerza un artefacto
único falso para representarlo (`workspace.yaml` real ya lo declaraba
explícitamente `status: missing` por este motivo antes de este sprint; este
sprint no "resuelve" esa ambigüedad inventando una respuesta, la resuelve
acotando el alcance del módulo a la parte que SÍ tiene una representación
limpia).

### 1.2 SQL

`sql/source_queries/SM/SM2025.sql`: `SELECT` directo sobre
`ITP_REUNION_GRUPO`, **sin ningún `JOIN`** -- confirmado SELECT-only (grep
de verbos DML/DDL, sin coincidencias), sin `ORDER BY` propio (igual que
Bypass, el extractor ordena en pandas por `FechaCreacion` antes de truncar
en modo `sample`). Es la SQL más simple de los 3 módulos reales hasta
ahora -- cero riesgo de inflación/sub-conteo por `JOIN`, a diferencia de
Bypass.

### 1.3 Mapping (hoja `MAP-SM` + hojas satélite del ETL real)

ETL: `ETL- Reunionesdegrupo-fixEntities_SITECAN.xlsx` (40 hojas, patrón
`MAP-ITPOLD-EVT/IMP/MED/MED-2` sin uso confirmado una **octava** vez -- ver
CLAUDE.md).

7 campos con evidencia primaria directa (hoja `MAP-SM` +
`Mapeo_Flujos`/`Mapeo_Nivel`/`Mapeo_Letra`, cruzados contra el Operational
real donde fue posible):

| Campo destino | Origen | Regla | Evidencia | Clasificación |
|---|---|---|---|---|
| `CS_HistoricalOriginID` | `IDReunionGrupo` | `cloneorigin` (passthrough) | `Mapeo_IDIns`, fila `ReglaEspecial=cloneorigin`; IDs limpios confirmados en el Operational real (5303, 5305...) | VERIFIED |
| `CS_WorkflowStatus` | `FaseActual` (NO `Estado`) | lookup 4 valores, sin nullcontrol | `Mapeo_Flujos`; 3/4 valores de destino observados en el Operational real | VERIFIED |
| `CS_Level` | `IDNivel` | lookup 7 valores, sin nullcontrol | `Mapeo_Nivel`; 7/7 valores de destino observados coinciden exactamente | VERIFIED |
| `CS_Letter` | `IDLetra` | lookup 7 valores, sin nullcontrol | `Mapeo_Letra`; 7/7 valores de destino observados coinciden exactamente | VERIFIED |
| `StartDate` | `Fecha` | passthrough (ya formateada por la SQL) | SQL (`FORMAT(...,'dd/MM/yyyy HH:mm:ss')`) | STRONGLY_EVIDENCED -- ver § 1.4 |
| `CS_MeetingPlace` | `Lugar` | passthrough | `MAP-SM`, sin adaptación marcada | STRONGLY_EVIDENCED |
| `CS_HistoricalAtendee` | `Asistentes` | passthrough | `MAP-SM`, sin adaptación marcada; coincide con el nombre exacto de columna del Template real | STRONGLY_EVIDENCED |

**Solo VERIFIED entra sin warning implícito** (los 4 primeros); los 3
STRONGLY_EVIDENCED entran igualmente en el incremento (no bloquean
readiness) pero con la limitación documentada en `config/exports/safety_meetings.yaml`.

### 1.4 Hallazgo -- `FechaHora` no existe en la SQL real

La hoja `MAP-SM` referencia un campo origen `FechaHora` para `StartDate`
-- ese campo **no existe** en `SM2025.sql` (solo existen `Fecha` y `Hora`
por separado). `Fecha` ya viene formateada como datetime completo por la
propia SQL, así que se usa tal cual; `Hora` queda **sin usar en este
incremento** -- no se inventa una fórmula de combinación sin evidencia de
cuál es. Mismo patrón general que el `titlefix` sin motor visible ya
documentado en CLAUDE.md: el ETL asume un paso previo no reproducible solo
con la SQL disponible.

### 1.5 Hallazgo -- discrepancia `CS_HistoricalDataOrigin`

La hoja `Mapeo_IDIns` declara un valor constante
`CS_HistoricalDataOrigin = "ITP_REUNION_GRUPO"` -- pero **ni el Template
real (`Group Meetings-40.csv`) ni el Operational real (`Reuniones de grupo
import completo.csv`) contienen esa columna**. El objeto Enablon
`Group_Meetings`, a diferencia de Drills/Bypass, no parece tener ese
campo. Se registra como discrepancia de conocimiento (`KNOWLEDGE_GAP`) --
no se incluye el campo (no hay destino real que lo reciba en los 2 CSV
reales verificados), no se asume que el ETL esté mal ni que el CSV esté
incompleto sin más evidencia.

### 1.6 CS_Entity -- UNRESOLVED, tercera confirmación del mismo gap

`IDUnidadOrg -> CS_Entity` requiere el catálogo First_Axis vigente en
formato `Ruta1` completo (`config/modules.yaml`). Confirmado, otra vez, que
`catalogo_resuelto_code_ruta_site.csv`/`First_Axis_export_bruto.csv` son
catálogos **solo de destino** (`Code`/`Ruta1`/`Centro`, columnas
verificadas por cabecera), sin ninguna columna `IDUnidadOrg` de origen --
**el mismo gap exacto que bloqueó Entity en Bypass (Sprint 9.5), ahora
confirmado independientemente una tercera vez**. Esto ya no es una
particularidad de un módulo -- es evidencia de que el gap es sistémico
(ver informe de cierre de este sprint § Fase 17).

### 1.7 Volumetría

Operational real: **1734 filas** (contadas con `csv` module respetando
campos multilínea -- un conteo ingenuo por `wc -l` da 9013, incorrecto,
mismo error ya documentado para Bypass en Sprint 9.5). `CS_Entity` en esta
muestra tiene valores centinela de texto libre ("No migra", "Unidad
organizativa es Null") en la mayoría de filas muestreadas -- consistente
con el patrón ya conocido de Operational CCE-scoped con alta proporción de
entidades con rollback (CLAUDE.md), no una anomalía nueva.

### 1.8 Campos excluidos de este incremento

Ver `config/exports/safety_meetings.yaml::excluded_columns` para el
detalle completo con evidencia. Resumen: `CS_Entity` (UNRESOLVED, § 1.6),
`CS_Scope` (UNRESOLVED, regla ambigua en `Mapeo_Nivel`), `TitleEN`
(UNRESOLVED, `titlefix` sin motor visible, candidato a Field Constraint --
ver § 5), `CS_PendingIssues` (UNRESOLVED, regla `concat` sin parámetros
capturados), `CS_HistoricalUserId`/`CS_HistoricalUserName`
(OUT_OF_SCOPE_CONFIRMED, datos personales, mismo criterio que
Drills/Bypass), `CS_HistoricalAttachedFiles` (OUT_OF_SCOPE_CONFIRMED,
transversal), `Duration` (UNRESOLVED, 2 campos origen en conflicto, uno de
ellos -- `DuraciónAjustada` -- ausente de la SQL real), resto del Template
(10 columnas, UNRESOLVED_NON_BLOCKING, acotado por tiempo).

## 2. Reutilización del Export Engine (Sprint 9.6)

| Pieza | Clasificación | Detalle |
|---|---|---|
| `load_export_config` (config loader) | REUSED_ENGINE | `safety_meetings/config.py` es un wrapper de 45 líneas -- mismo patrón exacto que `bypass/config.py` tras Sprint 9.6 |
| `extract_via_sql` | REUSED_ENGINE | `safety_meetings/extractor.py`, 52 líneas -- `sort_column="FechaCreacion"` (mismo motivo que Bypass: sin `ORDER BY` propio) |
| `is_missing`/`to_native` | REUSED_ENGINE | Usada dentro de `passthrough_or_empty` y, transitivamente, dentro de `resolve_workflow_status` (importada de Drills, que ya usa la versión canónica del Engine desde Sprint 9.6) |
| `BaseRunStats` + `build_*_section` | REUSED_ENGINE | `RunStats` extiende `BaseRunStats` con `lookups_resolved/unresolved/empty` (3 categorías propias) |
| `determine_status` (3 estados) | REUSED_ENGINE | Decisión propia de este módulo, no copiada -- ver § 4 |
| `validate_csv_structure` | REUSED_ENGINE | `safety_meetings/validator.py` es un wrapper de 36 líneas, sin comprobaciones de negocio adicionales (más simple aún que Bypass) |
| `GenericQueryStage`/`QueryStageSpec` | REUSED_ENGINE | `safety_meetings/core_adapters.py` usa `GenericQueryStage` desde el primer commit -- no hubo una `SafetyMeetingsQueryStage` propia que luego migrar |
| `ModuleDefinition.pipeline_factory` | REUSED_ENGINE (Core, sin cambios) | Mismo patrón que Drills/Bypass, sin ajustes |
| `to_historical_id`/`resolve_workflow_status`/`LookupResult` | REUSED (cross-módulo, no Engine todavía) | Importadas de `drills.transformations`, mismo precedente que Bypass ya estableció en Sprint 9.4 -- **3ª confirmación real de necesidad idéntica, ver § 6 del informe de cierre para la recomendación de moverlas al Engine en Sprint 9.8** |
| `pipeline.py` (orquestación) | MODULE_SPECIFIC | 218 líneas -- NO extraído del Engine (WAIT_FOR_THIRD_MODULE, confirmado, ver § 3 del informe de cierre) |
| `Transform/Export Stage` | MODULE_SPECIFIC | Envuelve `pipeline.run()`, mismo patrón que Bypass |
| `transformations.py` | MODULE_SPECIFIC (mayoría reused) | Solo `passthrough_or_empty` es código nuevo real (~10 líneas) |

**Ningún ENGINE_GAP bloqueante encontrado.** No hizo falta copiar ninguna
de las piezas ya extraídas en Sprint 9.6.

## 3. Filter catalog

`SAFETY_MEETINGS_FILTER_CATALOG` (`src/query/catalog.py`): `historical_origin_id`
(`IDReunionGrupo`), `center_id` (`IDCentro`), `origin_org_unit_id`
(`IDUnidadOrg`), `workflow_phase_id` (`FaseActual`, valor de ORIGEN, no el
`CS_WorkflowStatus` ya traducido) -- mismo mecanismo `ObjectFilterCatalog`/
`FilterDefinition`/`compile_filter_tokens`, datos propios.

## 4. `determine_status` -- decisión propia, no copiada

Safety Meetings usa el `determine_status` de 3 estados del Engine (el mismo
que Drills, distinto del de 2 estados que Bypass sigue usando sin migrar).
**No es una copia de Drills** -- es la conclusión independiente correcta
para este módulo: ninguno de sus 3 lookups tiene `nullcontrol`/default
documentado, así que un valor vacío o sin coincidencia queda genuinamente
`unresolved`/`empty` (nunca enmascarado). Con datos reales ya se observan
~19 filas con `CS_Level`/`CS_Letter` vacíos -- un `SUCCESS` sin distinguir
eso de un run perfectamente limpio sería engañoso. Confirmado con test
(`test_pipeline_status_success_with_warnings_cuando_hay_unresolved`).

## 5. Field Constraints -- candidato registrado (sin implementar)

`TitleEN` (`BreveDescripcion` vía hoja `Title_map`, regla `titlefix`,
`Parametro=239`) -- mismo motor no documentado que `titlefix` ya registrado
en CLAUDE.md para otros módulos. El valor `239` podría ser un
`max_length`, pero no está confirmado -- se registra como candidato para el
futuro esquema de Field Constraints (`FieldSpec.constraints`, diseñado en
Sprint 9.6, no implementado), no se implementa como `value[:239]` ad hoc en
este módulo.

## 6. Evidence -- sigue sin conectar (`EVIDENCE_ENGINE_GAP`)

`src/evidence/` sigue hardcodeado a Drills (Sprint 9.5.1/9.6, sin cambios
en este sprint). Safety Meetings alcanza `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY`
**sin Evidence** -- `ModuleCapabilities` no declara `EVIDENCE` para este
módulo (falsearía una capacidad no demostrada). `--generate-evidence` es
un no-op para `run --object safety_meetings`, igual que para Bypass.

## 7. Comparison / Project Contract (análisis, sin implementar)

Operational real: `Reuniones de grupo import completo.csv`, 1734 filas,
`;` como delimitador, UTF-8 con BOM. `CS_HistoricalOriginID` **sin
corrupción** (a diferencia de Bypass) -- IDs limpios enteros confirmados.
Campos comparables hoy: los 4 VERIFIED (`CS_HistoricalOriginID`,
`CS_WorkflowStatus`, `CS_Level`, `CS_Letter`). `comparison.py` (Drills)
sigue sin conectar a este módulo -- mismo estado que Bypass.

**Candidato de filtro para un futuro primer sample real** (Fase 12/18):
los 10 IDs más bajos observados en el Operational real, sin decodificación
necesaria (a diferencia de Bypass):

```
5303, 5305, 5310, 5364, 5607, 5613, 5721, 5722, 5723, 5724
```
