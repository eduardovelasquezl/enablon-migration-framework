# Object Evidence Assessment — simulacros.Drills

> Esto es una **Object Evidence Assessment**, no una especificación
> definitiva. No define un `ExportDefinition` ejecutable ni fija columnas
> de destino como aprobadas — reúne y organiza toda la evidencia disponible
> hoy sobre `simulacros.Drills`, con su nivel de confianza y sus huecos,
> como paso previo a una especificación futura. Fuentes:
> `sql/source_queries/Simulacros/`, `config/modules.yaml:75-94`,
> `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`, `Drills-22072026-41.csv`,
> `evidence/traceability_catalog.yaml`.

## 1. Fuente SQL

`sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql` —
`SELECT` de una única tabla, `[Prevencion].[dbo].[ITP_SIMULACRO]`, sin
`JOIN` (`evidence:sql_source.simulacros_folder`). **observed**: es la query
estructuralmente más simple de todo el proyecto.

## 2. Tabla o tablas

Cuatro tablas de origen documentadas en `config/modules.yaml:79-83` y
confirmadas como hojas de Power Query en el ETL:

| Tabla | Filas conocidas | Rol |
|---|---:|---|
| `DB_OrigenSim` | 12501 (config) / 12502 con cabecera (ETL) | Creación — dataset principal |
| `ITP_SIM_ACCIONES_CORRECTORAS` | 5604 / 5605 | Actualización (acciones correctoras) |
| `ITP_ASIST_SIMS` | 21955 / 21956 | Asistentes internos |
| `ITP_ASIST_SIMS_EXT` | 21955 / 21956 | Asistentes externos |

**pending_confirmation**: el nombre `DB_OrigenSim` (nombre de la hoja/query
de Power Query) no coincide literalmente con `ITP_SIMULACRO` (nombre de
tabla en la query SQL) — es plausible que sea el mismo objeto con un alias
de query distinto, pero no se ha confirmado.

## 3. Campos extraídos

`DB_OrigenSim` tiene 45 columnas confirmadas por lectura de cabecera
completa (ver `evidence/etl_catalog.yaml`), incluyendo `IDSimulacro`,
`IDFlujo`, `IDCentro`, `IDEmpresa`, `FechaCreacion`,
`FechaUltimaModificacion`, `IDUsuarioUltimaModificacion`, `IDTipo`,
`Fecha`, `Hora`, `Estado`, `IDLetra`, `Duracion`, `BreveDescripcion`,
`HipotesisAccidental`, `Asistentes`, `NumAsistentes`, `Comentarios`,
`Observaciones`, y 4 columnas técnicas ya calculadas dentro de la propia
hoja (`CS_DurationMonths/Days/Hours/Minutes`) más `CS_HistoricalAttachedFiles`.

## 4. Filtros

No se observó ningún filtro `WHERE` en la query SQL de origen (coherente
con `config/modules.yaml` describiendo el gap de Simulacros como "sano" y
sin exposición documentada al Hallazgo #1). El nombre del workbook
(`UpdateEje_SITECAN`) sugiere un ajuste de eje de entidad específico para
Site Canarias — no se localizó un filtro de fila correspondiente en la
query, solo en el propio mapeo de entidad (fuera de esta hoja).

## 5. ETL asociado

`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` (28.9 MB, 49 hojas, sin
macros, con Power Query). Autodocumentado por su propia hoja `Index`: 6
pasos (crear Drills, actualizar con acciones, crear List of Activities,
rellenar asistentes ×2 variantes) — ver `evidence/etl_catalog.yaml`.

## 6. Hojas del ETL relevantes para Drills

`DB_OrigenSim`, `ITP_SIM_ACCIONES_CORRECTORAS`, `ITP_ASIST_SIMS(_EXT)`,
`CamposXmlBES_SIMS_exportado` (catálogo de campos de salida — nombre
heredado de Bypass, ver §16), `MapeoSims`, `MapeoSims_ConAcciones`,
`Mapeo_asistentes(_EXT)`, `Mapeo_Tipo_sim`, `Mapeo_Letra`, `Mapeo_Estado`,
`Mapeo_Titulo`, `CalculoHorasDiasMinutos`, `Mapeo_UserHistorical`,
`MultiField_User(_Name)`, `NullControlException`, `Ref_YN_Format`,
`CharacterFix`, `CSV_SIM` / `CSV_SIM_full` / `CSV_Generated_BCM_SIM` /
`Export sim UAT` (cuatro hojas de salida distintas, ver §21).

## 7. Fórmulas y transformaciones

Ver `evidence/etl_catalog.yaml` (`transformations`) para el detalle
completo con fórmula original + interpretación + confianza. Resumen:

| Regla | Campo | Confianza |
|---|---|---|
| Lookup directo (XLOOKUP) | `IDSimulacro` → `CS_HistoricalOriginID` | high |
| Lookup + literal fijo | `IDUsuarioUltimaModificacion` → `CS_HistoricalUserId`/`CS_HistoricalDataOrigin` | high |
| Lookup dinámico en 2 pasos | `IDTipo` → `CS_Typology` | high |
| Lookup simple | `IDLetra` → `CS_Letter`; `Estado` → `CS_WorkflowStatus` | high |
| titlefix + cloneorigin (fan-out) | `Nombre`/título → `NameEN`+fan-out FR/ES/ZH/BR | high |
| Conversión numérica (mes=30d, minutos redondeados a 5) | `Duracion` → `CS_DurationMonths/Days/Hours/Minutes` | high (fórmula), medium (recombinación a `CS_Duration` no localizada) |
| nullcontrol | Campos NULL → texto de reserva (3 textos distintos según campo) | high |
| Concat + cloneorigin | `NombreAsistente` → `CS_HistoricalDrillAttendees`/`CS_ExternalParticipants` (vía `Asis_concat`, lógica interna no confirmada) | medium |

## 8. Mappings de entidad utilizados

**No confirmado dentro de este ETL.** `MapeoSims` declara explícitamente
`IDCentro` sin destino (`Field Destiny XML` vacío, `Adaptación='No'`) — la
resolución de `IDCentro`/`IDUnidadOrg` hacia el campo de entidad real
(`CS_ImpactedEntities` en el CSV real) no ocurre en la hoja de mapeo de
campo. Candidato: `entity_mapping:itp_primer_eje.mapeo_eje_final_modificado`
(Bloque3), pero no se ha confirmado el enlace exacto entre ambos archivos
(`trace_status: missing`, ver `traceability_catalog.yaml`).

## 9. CSV histórico disponible

`Drills-22072026-41.csv` (Bloque4, 40302 filas, tab-delimited UTF-16LE) —
export real de datos de producción, **no** una plantilla de importación en
blanco confirmada (ver `evidence_inventory.md` §3, principio heredado sin
cambios en este incremento).

## 10. Columnas y orden del CSV

36 columnas confirmadas por lectura de cabecera completa (ver
`evidence/etl_catalog.yaml`, hoja `CSV_SIM`): `CS_WorkflowStatus`,
`Reference`, `NameEN..NameBR`, `CS_Letter`, `CS_ImpactedEntities`,
`CS_Typology`, `StartingDate`, `CS_Duration`, `EstimatedLoss`, `RealLoss`,
`GroupsList`, `CS_OtherContacts`, `CS_ExternalParticipants`,
`CS_OtherParticipants`, `CS_EnvConsequences`,
`CS_FirefightingAndSpillContainment`, `CS_ObservationsFirefighting`,
`CS_AttitudeOfPersonnel`, `CS_ObservationsPersonnel`, `CS_StaffTraining`,
`CS_ObservationsTraining`, `CS_Communication`,
`CS_ObservationsCommunication`, `CS_HistoricalRecord`,
`CS_HistoricalDataOrigin`, `CS_HistoricalOriginID`, `CS_HistoricalUserId`,
`CS_HistoricalUserName`, `CS_HistoricalDrillAttendees`,
`CS_HistoricalDrillResponsibleName`, `CS_HistoricalAttachedFiles`/`Id`
(orden de las dos últimas invertido entre `CSV_SIM` y `CSV_SIM_full` —
ver §21).

## 11. Campos obligatorios observados

No se ha localizado ninguna declaración explícita de "campo obligatorio"
en el ETL (ni en `MapeoSims` ni en `CamposXmlBES_SIMS_exportado`) —
**pending_confirmation**, requeriría el template de importación real de
Enablon (inexistente hoy, ver `open_questions.md` OQ-TPL-01).

## 12. Defaults

- `Estado` sin traducción reconocida: no se observó un default explícito en
  `Mapeo_Estado` (solo 4 valores mapeados, `Terminado/En Curso/Iniciado/Aprobado`).
- `IDTipo` sin coincidencia: default literal `"NADA"` (`Mapeo_Tipo_sim`).
- Campos NULL genéricos: `"Not specified in Migration Data Origin"`
  (`NullControlException`).

## 13. Fallbacks

- Nombre nulo: `"No name defined in historical data"` (`Mapeo_Titulo`,
  fila 3).
- Booleano nulo: `No` (`Ref_YN_Format`, fila 4).

## 14. Exclusiones

No se identificó ninguna regla de exclusión explícita (`do_not_migrate`)
dentro de las hojas de Drills analizadas — a diferencia de `bypass` o del
catálogo de entidad ITP (donde "No migra" es explícito y frecuente), en
Simulacros no se observó ningún caso en la muestra leída.

## 15. Claves

- **Clave de correlación / actualización**: `IDSimulacro` ↔
  `CS_HistoricalOriginID` (confirmada tanto en el Index del ETL —
  `Update(IDSimulacro,CS_HistoricalOriginID)` — como en `MapeoSims`).
- **Clave compuesta del campo `Reference`** (legible, no de correlación):
  Tipología + literal + IDSimulacro + Fecha — **no se reduce a una única
  columna en esta documentación**, seguido de la instrucción explícita de
  la Tarea 5 de un incremento anterior, precisamente porque varía entre
  hojas de salida (ver §21).

## 16. Relaciones

- Alimenta `ap.Action_Plans` vía `idorigenac [12, 18]`
  (`config/modules.yaml:274`) y el campo de enlace `BCCrisis` en
  `Action Plans-*.csv`.
- Comparte fuente (`DB_OrigenSim`) y varias hojas de transformación
  (`Titlefix`, `cloneorigin`, `Mapeo_Estado_AL`) con
  `simulacros.List_of_Activities` — ambos objetos se generan del mismo
  workbook y, en parte, de las mismas filas origen.
- Hoja `CamposXmlBES_SIMS_exportado` lleva el acrónimo de `bypass` en su
  nombre — evidencia de que este ETL se construyó copiando el de Bypass,
  sin relación funcional real con ese módulo.

## 17. Duplicados

No se ha ejecutado en este incremento una comprobación de duplicados sobre
`Drills-22072026-41.csv` (a diferencia de Events/OPS/AP, donde
`config/modules.yaml` ya documenta cifras exactas de duplicación por
`CS_HistoricalOriginID` compartido). `config/modules.yaml:92-93` describe
el gap de volumetría de Drills como "sano" (-4.6%), sin mencionar
duplicados como causa — **no verificado de forma independiente en este
incremento**.

## 18. Validaciones

Ninguna hoja de validación dedicada identificada (a diferencia de
`data_quality_checks` de `config/validation_rules.yaml`, que son
transversales al proyecto, no específicas de este ETL).

## 19. Preguntas abiertas

- `OQ-ETL-01`: la regla `Asis_concat` referenciada como `Transformation
  From` para `CS_HistoricalDrillAttendees` no muestra su lógica de
  concatenación en la muestra leída.
- `OQ-ETL-02`: cómo (o si) los 4 componentes de `CalculoHorasDiasMinutos`
  se recombinan en el único campo `CS_Duration` del CSV real.
- ~~`OQ-ETL-03`: cuál de las 3 fórmulas de `Reference` observadas produjo
  realmente el dato cargado en Enablon.~~ **Resuelta (este incremento)** —
  `resolution_type: approved_functional_decision`,
  `resolution_evidence_id: AFD-DRILLS-REFERENCE-001`. No reabierta. Ver
  `open_questions.md` y `decision_packages/drills_reference_decision_package.md`.
- ~~`OQ-ETL-04`: qué proceso resuelve `IDCentro` → `CS_ImpactedEntities`,
  dado que no ocurre dentro de `MapeoSims`.~~ **Resuelta (este
  incremento)** — mecanismo localizado en `MapeoSims` fila 44 y
  `DB_OrigenSim` columnas U/V (fuente real es `IDUnidadOrg`, no
  `IDCentro`). Ver `object_assessments/drills_entity_resolution_assessment.md`.
- **Nuevas (este incremento)**: `OQ-ETL-05` (por qué existen 3 hojas de
  salida distintas para `Reference`), `OQ-ETL-06` (tratamiento de
  componentes NULL/vacíos en el patrón de `Reference` — no confirmado,
  explícitamente NO es una reapertura de `OQ-ETL-03`), `OQ-ENT-04` (uso
  del catálogo deprecado `Entidades_Mapeo`/`Entidades_Enablon_ITP` — ya
  aceptado para Drills vía `config/modules.yaml:84`, pero repetido sin
  nota equivalente en bypass/eventos_antiguos/ops/reuniones).
- `OQ-OBJ-01` (heredada, sin cambios): `List_of_Activities` no tiene
  entrada propia en `config/modules.yaml` — este incremento SÍ confirma
  estructuralmente que comparte workbook y fuente con Drills, pero no
  resuelve la carencia de config.

## 20. Riesgos

- ~~**Riesgo de especificación prematura sobre `Reference`**~~ — **mitigado
  (este incremento)**: la fórmula vigente ya no se elige por frecuencia ni
  presencia en el workbook, sino que se validó contra una decisión
  funcional aprobada externamente (`AFD-DRILLS-REFERENCE-001`). Riesgo
  residual, no bloqueante: el tratamiento de componentes NULL/vacíos
  dentro de ese patrón sigue sin confirmar (`OQ-ETL-06`).
- ~~**Riesgo de entidad no resuelta**~~ — **mitigado (este incremento)**:
  el proceso real que resuelve `CS_ImpactedEntities` fue localizado (§8 de
  `drills_entity_resolution_assessment.md`). Riesgo residual, no
  bloqueante: el mecanismo usa el catálogo deprecado
  `Entidades_Mapeo`/`Entidades_Enablon_ITP` — aceptado para Drills
  (`config/modules.yaml:84`), pero su uso repetido en otros módulos sin
  nota equivalente queda abierto en `OQ-ENT-04`.
- **Riesgo de recálculo destructivo**: el propio workbook de Inspecciones
  advierte explícitamente sobre desactivar el cálculo automático antes de
  tocar el dataset — aunque esa advertencia está en otro workbook, sugiere
  que el mismo riesgo (fórmulas volátiles dependientes de orden de fila,
  ej. `INDICE(...;FILA())`) podría aplicar igual en Simulacros si se
  reabre y edita con Excel en modo de cálculo automático. Confirmado un
  segundo caso independiente del mismo patrón en OPS (`CSV_OPSOLD_FULL`),
  lo que eleva la prioridad de este riesgo como transversal al proyecto,
  no exclusivo de Simulacros.

## 21. Readiness actualizado

Sin cambio en `specification_readiness` (`ready_for_draft`, sin cambios
respecto al incremento anterior — los 4 mínimos seguían cubiertos incluso
antes de este análisis). Cambios acumulados hasta el incremento anterior:

- `mapping_status`: de `not_started` (tras el incremento de Bloque2, que no
  aportó nada) a **`partial`** — este incremento SÍ aportó evidencia real
  de mapping de campo (fórmulas XLOOKUP, reglas de 5 columnas, lookup en 2
  pasos), la primera vez que este objeto tiene mapping de campo confirmado
  con fórmula, no solo con comparación de datos.
- `template_status`: sin cambio (`candidate` — sigue sin existir un
  template de importación validado).
- `traceability_status` (nuevo campo, ver `export_readiness_matrix.md`):
  entonces **`partial`** — 6 de 9 campos trazados con `fully_traced`, 2 con
  `partially_traced`, 1 (`Reference`) `ambiguous` y 1 (entidad) `missing`.
- `approved_specification_readiness`: **`blocked`** — ningún template de
  importación validado existe todavía (regla dura de la Tarea 16, aplica a
  todos los objetos por igual). Ver §17 de `sql_etl_csv_traceability.md`
  para la justificación.

### Actualización (este incremento — validación de `Reference` + resolución de entidad)

- `traceability_status`: sube a **7 de 9 campos `fully_traced`** — el
  campo `Reference` pasa de `ambiguous` a `fully_traced`
  (`AFD-DRILLS-REFERENCE-001`) y el campo de entidad pasa de `missing` a
  `fully_traced` (mecanismo localizado). Se mantiene el valor de rollup
  `partial` en la matriz (no `confirmed`) porque `CS_HistoricalDrillAttendees`
  y los campos de duración siguen `partially_traced` — no hay ningún
  campo restante en `missing`, `ambiguous` ni `conflicting`.
- `mapping_status`: sin cambio (`partial` — sigue sin resolverse
  `Asis_concat` ni la recombinación completa de `CS_Duration`, `OQ-ETL-01`/`OQ-ETL-02`).
- `approved_specification_readiness`: sin cambio, **`blocked`** — sigue sin
  existir un template de importación validado (regla dura, no depende de
  este análisis).
- **Nuevo estado de la Tarea 16**: `object_specification_draft_ready`
  (antes `evidence_assessment_only`). Justificación completa contra los 4
  criterios explícitos de la Tarea 16 en `export_readiness_matrix.md` §7.2
  — en resumen: los dos huecos que impedían fijar columnas de destino con
  estabilidad (`Reference` sin decidir, entidad sin localizar) están
  cerrados con evidencia; lo que queda pendiente (asistentes, precisión de
  duración, tratamiento de NULL en `Reference`) son huecos documentables
  como campos pendientes dentro de un borrador, no ambigüedades que
  obliguen a adivinar una regla de negocio completa.

Ver la decisión completa (histórico + recálculo) en
`export_readiness_matrix.md` §7.
