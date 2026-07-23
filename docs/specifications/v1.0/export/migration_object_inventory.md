# Inventario de Migration Objects — Export Specifications v1.0

> Todo objeto listado aquí es un `MigrationObject` reconocido por evidencia
> real del repositorio (código, config, CSV, SQL, ADR) — ninguno se ha
> inventado a partir de conocimiento general de Enablon. La columna
> **estado de evidencia** distingue **observed** (existe evidencia directa)
> de **inferred** (se deduce razonablemente de nombre/contexto, sin
> confirmación explícita).
>
> `MigrationObject` como concepto está definido en
> [`src/knowledge_base/model.py`](../../../../src/knowledge_base/model.py)
> (campos `processing_scope`, `load_phase`) y documentado en
> [`domain_model.md`](../../../architecture/v1.0/domain_model.md) /
> [ADR-001](../../../architecture/v1.0/decisions/ADR-001-migration-object-centric-model.md).
> Hoy **no existe en el repositorio ningún registro/instancia real de
> `MigrationObject`** — es un tipo definido en código, sin catálogo poblado
> todavía; este documento es el primer intento de poblarlo a partir de
> evidencia dispersa en `config/modules.yaml`, ADR-001 y los CSV reales.

## 1. Módulos (8, fuente: [`config/modules.yaml`](../../../../config/modules.yaml))

| Módulo (clave config) | Nombre funcional | Sistema origen | Estado (config) |
|---|---|---|---|
| `simulacros` | Business Continuity Management (Simulacros) | prevencion (ITP) | cerrado — migración completa y validada |
| `safety_meetings` | Safety Meetings (Reuniones de grupo) | prevencion (ITP) | cerrado — gap de catálogo resuelto |
| `moc` | Management of Change | gct | abierto — pendiente confirmar CCP y resolver Hallazgo #1 |
| `bypass` | Bypass de Funciones y Elementos de Seguridad (BES) | prevencion (ITP) | cerrado tras aplicar catálogo real |
| `eventos` | Health & Safety Incidents (Eventos, Impactos, Investigaciones, PSM) | prevencion (ITP) | abierto — Hallazgo #1 confirmado |
| `ops` | Behaviour Based Safety (OPS) | prevencion (ITP) | abierto |
| `inspecciones` | Inspection Management | prevencion (ITP) | abierto — gap probablemente Hallazgo #1 |
| `ap` | Action Plans (transversal) | prevencion + gct (solo MOC) | abierto — gaps probablemente rollback |

`visitas_seguridad_y_otros` **no** es un módulo de primer nivel en
`config/modules.yaml` — existe únicamente como clave anidada bajo
`ap.idorigenac_por_modulo` (`[7, 14]`), marcada literalmente "módulo no
analizado en detalle todavía" (`config/modules.yaml:277`). Se documenta
aparte en la sección 3, por indicación explícita de la Tarea 6.

## 2. MigrationObject por módulo

### 2.1 `simulacros`

| Campo | Valor |
|---|---|
| **`Drills`** | |
| Nombre funcional | Drill / Simulacro |
| `processing_scope` / `load_phase` | `module` / `normal` (inferred — no hay entrada explícita de objeto en model.py, se aplica el default documentado) |
| Fuentes SQL | `sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql` (`FROM ITP_SIMULACRO`, sin joins) — `evidence:sql_source.simulacros_folder` |
| ETL asociado | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` — abierto y analizado en profundidad (prioridad del incremento de evidencia ETL): confirma con fórmula real 9 mappings de campo (`IDSimulacro→CS_HistoricalOriginID`, `IDTipo→CS_Typology` vía lookup en 2 pasos, `IDLetra→CS_Letter`, `Estado→CS_WorkflowStatus`, `Duracion→CS_Duration*`, `NombreAsistente→CS_HistoricalDrillAttendees`) — `evidence:etl.bcm_simulacros_updateeje`, ver `object_assessments/drills_evidence_assessment.md` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/Simulacros.zip` — abierto y verificado: NO contiene mapping de campo (solo duplicados SQL) + un ZIP anidado anómalo. El mapping de campo REAL está en el propio ETL (hoja `MapeoSims`), no en Bloque2 — `evidence:mapping.bloque2_zip_simulacros` |
| Clave de correlación | `CS_HistoricalOriginID = IDSimulacro` (confirmado por XLOOKUP resuelto en `MapeoSims`). El campo legible `Reference` (`CONCATENAR(Reference;"-";"HIST";"-";Centro;"-";FechaTexto)` de `config/modules.yaml:86`) tiene **3 fórmulas distintas confirmadas entre hojas de salida sucesivas** del propio ETL — `trace_status: ambiguous`, ver `evidence/traceability_catalog.yaml` |
| CSV real | `Drills-22072026-41.csv`, 40302 filas, tab-delim UTF-16LE — `evidence:csv_enablon.drills` |
| Relaciones | Alimenta Action Plans vía `idorigenac [12, 18]` (`config/modules.yaml:274`); campo de enlace `BCCrisis` en `Action Plans-*.csv`. Resolución de entidad (`IDCentro→CS_ImpactedEntities`) NO ocurre dentro de `MapeoSims` — proceso no identificado, `trace_status: missing` |
| Action Plans vinculados | Sí — `idorigenac 12, 18` |
| Estado de evidencia | **observed** — fuente, identidad, salida candidata, relación y ahora mapping de campo (con fórmula real) confirmados |
| Preguntas abiertas | `OQ-ETL-01` (lógica de `Asis_concat` no confirmada), `OQ-ETL-02` (recombinación de `CS_Duration`), `OQ-ETL-03` (cuál fórmula de `Reference` es la real), `OQ-ETL-04` (proceso de resolución de entidad) — ninguna bloqueante para `specification_readiness`, ver `object_assessments/drills_evidence_assessment.md` |

| Campo | Valor |
|---|---|
| **`List of Activities`** | |
| Nombre funcional | Lista de actividades (submódulo de continuidad de negocio) |
| `processing_scope` / `load_phase` | `module` / `normal` (inferred) |
| Fuentes SQL | **Confirmado en este incremento**: mismo `DB_OrigenSim` que Drills (Index del ETL, paso 3: "Rellenamos los datos de las actividades", fuente `DB_OrigenSim` → mapa `Mapeo_AL` → salida `CSV_SIM_AL_OTH`) — ya no es "sin desglose por objeto", es el mismo origen con un juego de campos distinto |
| ETL asociado | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` — **confirmado, no inferred**: la cabecera de la hoja `CamposXML_AL_Exportado` (`Crisis, BCP, Origin, NameEN..NameBR, DescriptionEN..DescriptionBR, CS_Order`) coincide exactamente con la cabecera real de `List of Activities-*.csv` |
| Mapping asociado | Hoja `Mapeo_AL` (mismo patrón XLOOKUP que `MapeoSims`) + `Mapeo_Titulo_AL`/`Mapeo_Desc_AL` (titlefix+cloneorigin) + `Mapeo_Estado_AL` (lookup de estado, **con vocabulario de destino DISTINTO al de Drills para el mismo campo origen** — ver `etl_evidence_assessment.md` §7, `evidence_status: conflicting`) |
| Clave de correlación | `CS_HistoricalOriginID = IDSimulacro` (confirmado en `Mapeo_AL`, mismo mecanismo que Drills — comparten clave porque comparten fila origen) |
| CSV real | `List of Activities-22072026-44.csv`, 72156 filas, tab-delim UTF-16LE — `evidence:csv_enablon.list_of_activities` |
| Relaciones | Comparte fuente y clave de correlación con `simulacros.Drills` (mismo `DB_OrigenSim`/`IDSimulacro`) — relación ahora **observed**, no solo plausible |
| Action Plans vinculados | No confirmado |
| Estado de evidencia | **observed** — fuente, ETL, mapping y clave de correlación confirmados en este incremento; sigue **no apareciendo en `config/modules.yaml`** como entrada propia |
| Preguntas abiertas | `OQ-OBJ-01` (persiste: sin entrada en config, pese a la nueva evidencia estructural) |

### 2.2 `safety_meetings`

| Campo | Valor |
|---|---|
| **`Group Meetings`** | |
| Fuentes SQL | `sql/source_queries/SM/SM2025.sql` (identified, no leído en detalle) |
| ETL asociado | `ETL- reunionesdegrupo-fixEntities_SITECAN.xlsx` — nota: nombre de archivo usa "reunionesdegrupo", no "safety_meetings" |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/Reunionesdegrupo.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/SM/` (carpeta interna del ZIP también usa el slug `SM`) — `evidence:mapping.bloque2_zip_reunionesdegrupo` |
| Clave de correlación | No explícita en config; campo `CS_HistoricalOriginID` presente en el CSV real |
| CSV real | `Group Meetings-20072026-3.csv`, 65600 filas — `evidence:csv_enablon.group_meetings` |
| Relaciones | Alimenta Action Plans vía `idorigenac [11]`; campo de enlace `CS_Meetings` |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Defecto confirmado: "solo se usa 1 de 2 campos origen posibles" para asistentes (ticket #7359) — no bloquea especificación, sí calidad de dato |

| Campo | Valor |
|---|---|
| **`Update External Meeting Participations`** | |
| Fuentes SQL | `sql/source_queries/SM/Asistentes_SM2025.sql` (**inferred** — nombre plausible, no confirmado en config) |
| CSV real | `Update External Meeting Participations-20072026-5.csv`, 17526 filas, semicolon-delim — `evidence:csv_enablon.update_external_meeting_participations` |
| Clave de correlación | No documentada |
| Relaciones | Participante externo de `Group Meetings` (inferred por nombre) |
| Estado de evidencia | **observed** para el CSV; **inferred** el resto |
| Preguntas abiertas | Ver `open_questions.md` OQ-OBJ-02 |

### 2.3 `moc`

| Campo | Valor |
|---|---|
| **`Change Register`** | |
| Fuentes SQL | `DB_MOC_CT.sql` / `DB_MOC_CTOLD.sql` / `DB_MOC_SC.sql` — 16 `LEFT JOIN` por fase de workflow en `DB_MOC_CT.sql` — `evidence:sql_source.moc_ct_folder` |
| ETL asociado | `ETL_MOC_m_NEW_SITECAN.xlsm` (VBA confirmado 100% vacío) — `evidence:etl.moc_m_new_sitecan` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/MOC.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/MOC/`; el mapeo de entidad real sigue en `260311 Mapeo gct Enablon-Match UORG ENTIDAD (1).xlsx` (sin abrir) |
| Clave de correlación | `CS_HistoricalOriginID = cloneorigin(IDSolicitudCambio)` — `config/modules.yaml:126` |
| CSV real | `Change Register-20072026-8.csv`, 80396 filas, ~110 columnas — `evidence:csv_enablon.change_register` |
| Relaciones | Alimenta Action Plans vía campo de enlace `MoCChange` |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Origen exacto del proceso que ejecuta `titlefix` (confirmado en dato, sin motor visible en Excel/VBA) — ver `CLAUDE.md` y `open_questions.md` OQ-GLOBAL-02 |

### 2.4 `bypass`

| Campo | Valor |
|---|---|
| **`By-Passes of functions and safety elements`** | |
| Fuentes SQL | `sql/source_queries/bypass/` (2 ficheros, identified) |
| ETL asociado | `ETL_Bypass_AjusteEntidadNEW_SITECAN.xlsx` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/bypass.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/bypass/` — `evidence:mapping.bloque2_zip_bypass` |
| Clave de correlación | No explícita en config; `CS_HistoricalOriginID` presente en CSV real |
| CSV real | `By-Passes of functions and safety elements-20072026-11.csv`, 8901 filas — `evidence:csv_enablon.by_passes` |
| Relaciones | Alimenta Action Plans vía campo de enlace `CS_ByPasses` |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Campos confirmados NO importables vía CSV/API (`FechaEnvioFase1..6`, `MotivoAprobacionFase2/3/5`, `Autorizar`, `GOS` calculado) — restricción dura para cualquier `ExportDefinition` futura, `config/modules.yaml:161-165` |

### 2.5 `eventos`

| Campo | Valor |
|---|---|
| **`Events`** | |
| Fuentes SQL | `ITP_ANALISIS` (antiguos, FULL JOIN con investigación) + `ITP_ANALISIS_EVENTO` (nuevos) — `evidence:sql_source.eventos_full_join` |
| ETL asociado | `ETL - Eventos Antiguos_FiltroEje_SITEPESR.xlsx` + `ETL- Eventos nuevos - FULL_AjusteEje_SITEPSER.xlsx` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/Eventos.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/Eventos/` (con nombre de archivo mejor codificado que su copia suelta — ver `mapping_evidence_assessment.md` §5) |
| Clave de correlación | `CS_HistoricalEventID` — `config/modules.yaml:190` |
| CSV real | `Events-20072026-6.csv`, 26295 filas — `evidence:csv_enablon.events` |
| Relaciones | Padre funcional de Impacts/Investigations; alimenta Action Plans vía `CS_IndependentManualEvents` |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Hallazgo #1: exposición 70.6% (`config/modules.yaml:205`) — bloquea calidad de dato, no la especificación en sí |

| Campo | Valor |
|---|---|
| **`Impacts`** | |
| Clave de correlación | `CS_HistImpactID / CS_HistImpactIDOH` según `config/modules.yaml:191` — **no re-verificada literal** en la cabecera real leída de `Impacts-20072026-9.csv` en este incremento |
| CSV real | `Impacts-20072026-9.csv`, 19363 filas, ~90 columnas — `evidence:csv_enablon.impacts` |
| Relaciones | Hijo de Events; 14% huérfanos confirmados (`config/modules.yaml:208`) |
| Estado de evidencia | **observed** el CSV; **pending_confirmation** la clave de correlación exacta |
| Preguntas abiertas | Ver `open_questions.md` OQ-OBJ-03 |

| Campo | Valor |
|---|---|
| **`Investigations`** | |
| Clave de correlación | `CS_HistoricalExtenalId` — `config/modules.yaml:192`, confirmado en cabecera real (`CS_HistoricalExtenalId` visible en `Investigations-20072026-14.csv`) |
| CSV real | `Investigations-20072026-14.csv`, 16603 filas — `evidence:csv_enablon.investigations` |
| Relaciones | Hijo de Events; 15% huérfanas confirmadas; posible relación con `Causes Data-*.csv` (**inferred**, no confirmada) |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Relación con `Causes Data` — ver `open_questions.md` OQ-OBJ-04 |

| Campo | Valor |
|---|---|
| **`PSM Forms`** | |
| Fuentes SQL | `sql/source_queries/PSM/` — carpeta propia de nivel superior, pero modelado en config como submódulo de `eventos` (inconsistencia estructural, ver `open_questions.md` OQ-GLOBAL-01) |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/PSM.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/PSM/`; no resuelve la ambigüedad estructural anterior — `evidence:mapping.bloque2_zip_psm` |
| CSV real | `PSM forms-20072026-16.csv`, 2415 filas, semicolon-delim — `evidence:csv_enablon.psm_forms` |
| Relaciones | Defecto confirmado: fan-out de `cloneorigin` a 5 idiomas falla, PSM queda con respuestas en inglés (ticket #7437) |
| Estado de evidencia | **observed**, pero **no volumetrizado** (CLAUDE.md: "recibido, no volumetrizado") |
| Preguntas abiertas | Ver OQ-GLOBAL-01 |

### 2.6 `ops`

| Campo | Valor |
|---|---|
| **`JSO`** (Job Safety Observations) | |
| Fuentes SQL | `DB-ITP_OPS` (antiguo) + `ITP_OPS2` (nuevo) — `evidence:sql_source.ops_folder` |
| ETL asociado | `ETL_OPS_ArregloEntidad_SIETCAN.xlsx` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/OPS.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/OPS/` |
| Clave de correlación | No explícita en config; `CS_HistoricalOriginID` presente en CSV real |
| CSV real | `JSO-20072026-19.csv`, 245303 filas (la más voluminosa) — `evidence:csv_enablon.jso` |
| Relaciones | Alimenta Action Plans vía `idorigenac [3, 8]` (ops) — `ops2` sin datos de enlace, gap reconocido por el propio ETL |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Lookup nuevo `ITP_CONTRATISTAS` (1928 filas) — confirmar si aplica a exportación |

### 2.7 `inspecciones`

| Campo | Valor |
|---|---|
| **`Inspections`** | |
| Fuentes SQL | `ITP_IPS` / `ITP_INFORMECHECKLISTPT` / `ITP_INFORMECHECKLISTGHK` — `evidence:sql_source.inspecciones_folder` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/Inspecciones.zip` — abierto y verificado: NO contiene mapping de campo, solo duplicados de `sql/source_queries/Inspecciones/` — `evidence:mapping.bloque2_zip_inspecciones` |
| CSV real | `Inspections-20072026-22.csv`, 35186 filas — `evidence:csv_enablon.inspections` |
| Relaciones | Padre de `Observations` (100% integridad referencial confirmada, `config/modules.yaml:261`) |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Defecto: progreso calculado incorrecto (ticket #7553) |

| Campo | Valor |
|---|---|
| **`Observations`** | |
| CSV real | `Observations-20072026-27.csv`, 35187 filas — `evidence:csv_enablon.observations` |
| Relaciones | 100% de 18382 observaciones cruzan con su inspección — el único dato de integridad referencial perfecta confirmado en todo el proyecto |
| Estado de evidencia | **observed** |
| Preguntas abiertas | Ninguna bloqueante |

| Campo | Valor |
|---|---|
| **`Inspection Data`** | |
| CSV real | `Inspection Data-20072026-38.csv`, 155336 filas, respuesta polimórfica por tipo de pregunta — `evidence:csv_enablon.inspection_data` |
| Estado de evidencia | **observed**, pero **el propio config lo marca "export parcial, no se puede exportar completo"** (`config/modules.yaml:247`) |
| Preguntas abiertas | Bloqueante para `template_status` — ver `export_readiness_matrix.md` y OQ-OBJ-05 |

### 2.8 `ap` (Action Plans — transversal)

Tratado en detalle en [`action_plans_assessment.md`](action_plans_assessment.md).
Resumen de campos de inventario:

| Campo | Valor |
|---|---|
| `processing_scope` / `load_phase` | `cross_module` / `final` — únicos valores no-default en todo el modelo (`config/modules.yaml` no lo declara así literalmente; es un hecho de `src/knowledge_base/model.py` + `ADR-003`, confirmado por test) |
| Fuente SQL única | `ITP_Acciones_correctoras` clasificada por `idorigenac` — `evidence:sql_source.ap_acciones_correctoras` |
| ETL asociado | `ETL- AP_GCT_NEW_SITECAN.xlsx` (solo MOC) + `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN.xlsx` (resto) — ambos analizados vía su hoja Index en este incremento: confirman `Update(IDAccionCorrectora,CS_HistoricalAPID)` como clave de correlación PROPIA de Action Plans para los 7 módulos de origen, vía la misma hoja `MAP-AP`/`MAP-updatedate` |
| Mapping asociado | `Bloque2_Mappings_SQL_ENA/AP.zip` — abierto y verificado: NO contiene mapping de campo, solo un duplicado de `sql/source_queries/AP/Acciones_correctoras.sql` — `evidence:mapping.bloque2_zip_ap` |
| Clave de correlación (nuevo, confirmado este incremento) | `CS_HistoricalAPID = IDAccionCorrectora` (identidad propia del Action Plan) — **distinta** de `CS_HistoricalOriginID` (referencia al registro padre en el módulo de origen). Ambos campos coexisten como columnas separadas en `Action Plans-*.csv`. Ver `action_plans_assessment.md` Tarea 8 y `evidence/traceability_catalog.yaml` |
| CSV real | `Action Plans-20072026-41.csv`, 31444 filas de datos (recuento corregido este incremento — el valor 65223 citado antes era `wc -l` inflado por campos multilínea entrecomillados; parseado respetando quoting CSV) — `evidence:csv_enablon.action_plans` |
| Relaciones | Depende de todos los demás módulos vía campos de enlace (`BCCrisis`, `CS_ByPasses`, `CS_Meetings`, `MoCChange`, `CS_IndependentManualEvents`, `CS_IndManualOPS`, `CS_IP`) |
| Estado de evidencia | **observed** — el más robusto de todos los objetos transversales, con lógica ya implementada y probada; ahora también con distinción clara entre identidad propia y referencia a padre |
| Preguntas abiertas | La mayoría de registros no tienen ningún campo de enlace poblado — `config/modules.yaml:290` reconoce que no se sabe si es esperado o defecto. El 63% de duplicación de `CS_HistoricalOriginID` (`OQ-AP-02`) tiene ahora un candidato de explicación estructural (varias acciones por un mismo padre) pero sin confirmación cuantitativa — ver `action_plans_assessment.md` Tarea 8. |

## 3. Objeto sin módulo confirmado

| Objeto candidato | Estado |
|---|---|
| `visitas_seguridad_y_otros` | Solo existe como valor `idorigenac [7, 14]` anidado bajo `ap` (`config/modules.yaml:277`). Sin SQL, ETL o CSV identificado que lo respalde como módulo independiente. `evidence_pending` total. Por indicación de la Tarea 6, esta carencia **no bloquea** la especificación de ningún otro objeto — se mantiene explícitamente incompleta. |
| `Causes Data` (CSV real, 189654 filas) | Sin módulo asignado en `config/modules.yaml`. Relación **inferred** con `eventos.Investigations` (patrón `Why`/`CS_Why..CS_Why5` compartido) — ver OQ-OBJ-04. |
| `Checklists Data` (CSV real, 4381 filas) | Sin módulo asignado. Relación **inferred** con `moc` (coincide con "Checklists de Risk Assessment" citado en `config/modules.yaml:143`) — ver OQ-OBJ-06. |

## 4. Resumen cuantitativo

- **8** módulos con entrada propia en `config/modules.yaml`.
- **15** MigrationObject identificados con evidencia directa o razonablemente inferida (2 en simulacros, 2 en safety_meetings, 1 en moc, 1 en bypass, 4 en eventos, 1 en ops, 3 en inspecciones, 1 en ap).
- **2** CSV reales de Bloque4 (`Causes Data`, `Checklists Data`) sin MigrationObject asignado todavía.
- **1** módulo (`visitas_seguridad_y_otros`) sin evidencia suficiente para ser considerado un módulo formal.
