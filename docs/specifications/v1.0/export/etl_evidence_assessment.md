# Evaluación de evidencia ETL — Bloque1_ETL/

> Analiza los 10 workbooks de `inputs/_incoming_claude_web/Bloque1_ETL/`,
> con prioridad analítica en `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`
> (simulacros.Drills), sin ignorar los demás. Todo hallazgo distingue
> **observed** (leído directamente del archivo), **inferred** (deducido con
> apoyo parcial), **recommended** (sugerencia de este análisis) y
> **pending_confirmation** (requiere al cliente o al equipo). Ver
> `evidence/etl_catalog.yaml` para el detalle estructurado.

## 1. Método y alcance

Los 10 workbooks se abrieron con `openpyxl` en modo `read_only=True`
(streaming, sin recalcular fórmulas) en dos pasadas por archivo:
`data_only=False` (fórmula almacenada) y `data_only=True` (valor cacheado
de la última vez que Excel calculó el archivo). Ningún archivo fue escrito,
guardado, recalculado ni tuvo sus macros ejecutadas. Los archivos originales
se abrieron directamente desde `inputs/_incoming_claude_web/Bloque1_ETL/`
sin copiarlos ni modificarlos; no fue necesario extraer nada (no son ZIP).

- **Simulacros** (28.9 MB, prioridad): análisis profundo de 45 hojas —
  cabecera completa + muestra de 2-8 filas en fórmula y en valor cacheado,
  para las hojas identificadas como relevantes a partir de su propia hoja
  `Index` autodescriptiva.
- **Los otros 9 workbooks** (21 MB a 342 MB): análisis estructural completo
  (lista de hojas, estado oculto, macros, conexiones, tablas, vínculos
  externos, metadatos) vía inspección directa del paquete OOXML (zip
  interno), más lectura completa de su propia hoja `Index` (presente en
  9 de los 10, ver §2) — no se leyeron sus hojas de mapeo/datos en detalle.

Esta asimetría es deliberada, por instrucción explícita de este incremento
("dar prioridad analítica a Simulacros/Drills, sin ignorar los demás
módulos").

## 2. Hallazgo estructural: cada workbook se autodocumenta con una hoja "Index"

**observed**: 9 de los 10 workbooks (todos salvo, potencialmente, alguno
donde no se confirmó) tienen una hoja llamada `Index` con las columnas
`Desc | SOURCES DATA | DESTINY NAME HEADERS | MAPS | FINAL DATA | Crear? |
Log | Debug` — es, en efecto, un log de ejecución/documentación por paso
del propio pipeline ETL, generado por quien construyó el workbook. Cada
fila declara: qué hace el paso, de qué tabla/hoja fuente lee, a qué "cabecera
de destino" (hoja de campos Enablon) apunta, qué hoja de mapeo aplica, a
qué hoja de salida final escribe, si es una creación o una actualización
(y con qué clave), y el resultado de la última ejecución conocida (`✅`/`OK`
o un mensaje de error).

Esto es, con diferencia, la evidencia más valiosa de todo este incremento:
**no hubo que inferir el pipeline de ningún módulo — cada workbook lo
declara explícitamente.** El catálogo completo por workbook está en
`evidence/etl_catalog.yaml`; el detalle fila a fila de Simulacros y una
muestra de los otros 9 está documentado en las líneas citadas más abajo.

## 3. El patrón de reglas de 5 columnas se confirma en el ETL, no solo en Bloque2

CLAUDE.md documentaba el patrón `DatoOrigen | DatoDestino | EsCondicion |
ReglaEspecial | Parametro` como uno de los dos formatos de hoja de mapeo del
proyecto. **observed** en Simulacros: las hojas `Mapeo_UserHistorical`,
`CharacterFix`, `Mapeo_Titulo`, `AL_finalizar`, `Mapeo_Titulo_AL`,
`Mapeo_Desc_AL`, `NullControlException`, `Mapeo_Estado`(_AL),
`Ref_YN_Format`, `Text_concatenation`, `Asis_concat` siguen exactamente este
patrón. Confirmaciones concretas de reglas ya documentadas solo por
comportamiento de dato, ahora confirmadas por fórmula:

- **`titlefix`**: `CharacterFix` aplica la regla a `*` (todos los campos),
  condicional (`EsCondicion=Sí`). La misma hoja "CharacterFix" existe
  también en los workbooks de Bypass y OPS (confirmado por su listado de
  hojas) — **esto amplía la pregunta abierta sobre quién ejecuta titlefix
  de "solo MOC" a "cualquier módulo del sistema ITP que la use"**, ver
  §6 y `open_questions.md` (OQ-GLOBAL-02, alcance ampliado).
- **`nullcontrol`**: confirmado en `NullControlException` con el texto de
  reserva literal `"Not specified in Migration Data Origin"`, y en
  `Ref_YN_Format` (`NULL → No`) y `Mapeo_Titulo` (`NULL → "No name defined
  in historical data"`) — **tres textos de reserva DISTINTOS** según el
  campo, no uno genérico único.
- **`cloneorigin`** (fan-out a 5 idiomas): confirmado en `Mapeo_Titulo`,
  `Mapeo_Titulo_AL`, `Mapeo_Desc_AL`, aplicado tras `titlefix` sobre el
  campo `NameEN`/`DescriptionEN` origen.
- **`concat`**: confirmado en `Text_concatenation`, con prefijos de etiqueta
  fijos en español ("Breve Descripción: ", "Hipótesis del Accidente: ")
  antepuestos al valor de origen antes del fan-out.
- **Lookup dinámico en 2 pasos**: confirmado con fórmula real en
  `Mapeo_Tipo_sim` — primer XLOOKUP resuelve descripción vía tabla
  estructurada `ITP_MAESTROS`, segundo XLOOKUP resuelve el código Enablon
  final (`CS_Typology`) con reserva literal `"NADA"`.

## 4. El defecto de duración ahora tiene fórmula, no solo comparación de dato

La hoja `CalculoHorasDiasMinutos` (Simulacros) contiene, en fórmula real:

```
CS_DurationMonths  = INT(NUMBERVALUE(C2)/(24*30))
CS_DurationDays    = INT(MOD(NUMBERVALUE(C2),24*30)/24)
CS_DurationHours   = INT(MOD(NUMBERVALUE(C2),24))
CS_DurationMinutes = MROUND(INT(MOD(NUMBERVALUE(C2),1)*60),5)
```

Esto **confirma con evidencia de fórmula** (no solo de comparación de
totales) el defecto ya documentado en `config/modules.yaml:88` ("redondeo a
múltiplos de 5 min, mes de 30 días fijo"). Sin embargo, **el CSV real de
Drills solo tiene una columna `CS_Duration` numérica**, no 4 columnas — no
se ha localizado en este incremento la fórmula que recombina estos 4
componentes en el valor único final (ver `traceability_catalog.yaml`,
`trace:simulacros.drills.cs_duration_fields`, `partially_traced`).

## 5. Copia sin limpiar de un módulo a otro — nueva evidencia localizada

CLAUDE.md ya documentaba, por auditoría manual, que "todos los ETL nuevos
se construyen copiando el libro de un módulo anterior sin limpiar". Este
incremento localiza dos instancias **concretas y citables**:

- La hoja `CamposXmlBES_SIMS_exportado` del workbook de **Simulacros**
  lleva "BES" en el nombre — el acrónimo del objeto de **Bypass** — y
  contiene datos de prueba, no de producción (valores como `'test'`,
  `'TEST - Please Ignore'`). Confirma que el ETL de Simulacros se construyó
  copiando el de Bypass.
- La hoja `Mapeo_Letra` del mismo workbook de Simulacros tiene, en su
  columna descriptiva `InfoIgnore-Nombre`, el texto literal `'Letra
  (Reunión de Grupo)'` — la etiqueta nunca se actualizó al adaptar la hoja
  desde el ETL de Safety Meetings.

## 6. Ampliación de la pregunta sobre `titlefix` (antes solo MOC)

El incremento anterior (mapping evidence, Bloque2) dejó abierta la pregunta
de quién ejecuta `titlefix` en MOC, dado que su VBA está confirmado vacío.
Este incremento confirma que la hoja `CharacterFix`/`Mapeo_Titulo` con la
misma regla `titlefix` existe también en Simulacros, Bypass y OPS — sistema
ITP, no GCT. Esto **no resuelve** la pregunta, pero **la reformula
correctamente**: no es "¿qué ejecuta titlefix en MOC?" sino "¿qué ejecuta
titlefix en cualquier ETL que declare la regla, dado que ningún workbook
auditado (ITP o GCT) tiene el motor visible?" — ver `open_questions.md`
OQ-GLOBAL-02, alcance ampliado.

## 7. Conflictos y problemas de calidad detectados (Tarea 9)

Ninguno de estos se corrige — se documentan como observados, con su cita
exacta.

- **Referencia rota confirmada por el propio log del ETL** (OPS): fila 5
  del Index de `ETL_OPS_ArregloEntidad_SIETCAN.xlsx` registra literalmente
  `"Update: columna origen no encontrada (IdOpsAdaptado) (1)"` — no es una
  inferencia, es un mensaje de error que el propio proceso generador del
  log ya escribió en el archivo original.
- **Prefijo "//" recurrente en claves de actualización** (Eventos Antiguos
  y Eventos Nuevos): varias filas del Index muestran claves como
  `IDInformeMed↔//infMed`, `IDEvento+IDInfFase4↔CS_HistoricalEventID+//histphaseID`,
  `infMedico↔//HistInfMed` — el prefijo `//` no es sintaxis estándar de
  referencia de columna Excel/SQL; sugiere que el proceso que genera este
  log no pudo resolver completamente esas referencias concretas y usó un
  marcador de posición. Patrón repetido en 2 workbooks distintos, no un
  caso aislado.
- **Fórmulas inconsistentes para el mismo campo entre hojas de salida
  sucesivas** (Simulacros, campo `Reference`): 3 fórmulas distintas
  observadas entre `CSV_SIM_full`, `CSV_SIM` y `CSV_Generated_BCM_SIM` —
  ver §4 de `sql_etl_csv_traceability.md` y
  `traceability_catalog.yaml:trace:simulacros.drills.reference`
  (`ambiguous`). Los 4 recuentos de fila decrecientes ya documentados en
  `outputs/reports/01_...md` (12302→12104→11965→10575) corresponden
  exactamente a estas 4 hojas de salida (`CSV_SIM_full`, `CSV_SIM`,
  `Export sim UAT`, `CSV_Generated_BCM_SIM`) — se confirma la existencia
  de 4 etapas físicas distintas, pero no la causa de la reducción entre
  ellas (deduplicación, filtro, o export en momentos distintos — sin
  resolver, `pending_confirmation`).
- **Inconsistencia Desc vs. Crear?/Log** (AP GCT): fila 5 del Index de
  `ETL- AP_GCT_NEW_SITECAN.xlsx` tiene `Desc='Nunca'` pero `Crear?='sí'` y
  `Log='✅'/'OK'` — la descripción dice que ese paso nunca se ejecuta, pero
  el registro de ejecución dice que sí se ejecutó correctamente.
- **Vocabulario de estado distinto para el mismo campo origen**
  (Simulacros): `Mapeo_Estado` (Drills) traduce `Estado` a
  `{Validated, Pending validation, Draft}`; `Mapeo_Estado_AL` (List of
  Activities) traduce el MISMO campo origen a `{Completed, In Progress,
  Not Started}`, con una correspondencia distinta incluso en los valores
  compartidos (p. ej. `'Aprobado'` → `'Validated'` en uno, → `'Not
  Started'` en el otro). No se asume que sea un defecto — puede ser una
  decisión funcional correcta al ser objetos Enablon distintos — pero no
  hay evidencia que lo confirme como deliberado. `evidence_status:
  conflicting`.
- **Registro de log incompleto** (OPS, fila 2 del Index): columnas
  `Crear?`/`Log` vacías mientras `Debug='OK'` — registro parcial.
- **Advertencia operativa del propio autor** (Inspecciones): fila 2 del
  Index contiene, en mayúsculas, "IMPORTANTE: DESACTIVAR CALCULO
  AUTOMATICO DE FORMULAS ANTES DE ACTUALIZAR DATASET O GENERAR VALORES" —
  confirma que el riesgo de recalcular fórmulas de forma destructiva
  (que este incremento evita por diseño) ya era una preocupación conocida
  de quien construyó el ETL.

## 8. Incidencias de apertura, packaging y protección

- Ningún workbook tiene protección de hoja/libro activa
  (`workbookProtection` ausente en los 10).
- Solo `ETL_MOC_m_NEW_SITECAN.xlsm` contiene `xl/vbaProject.bin` — no se
  abrió ni ejecutó su contenido en este incremento (regla dura de la
  Tarea 2). La afirmación de que su VBA está "100% vacío" proviene de un
  análisis manual previo (CLAUDE.md), no reverificada aquí.
- 4 hojas ocultas (`MAP-ITPOLD-EVT`, `MAP-ITPOLD-IMP`, `MAP-ITPOLD-MED`,
  `MAP-ITPOLD-MED-2`) aparecen en los workbooks de Eventos Antiguos,
  Eventos Nuevos, AP-Con Ajuste Entidad, AP_GCT, Inspecciones y Simulacros
  — no referenciadas en ningún paso del respectivo Index. Confirma, con
  nombres de hoja exactos, el hallazgo ya documentado de "7/7 libros" en
  CLAUDE.md.
- Todos los workbooks usan Power Query / conexiones externas
  (`xl/connections.xml`, `queryTables`, `customXml` con DataMashup) para
  cargar datos SQL — salvo los 2 workbooks de Bloque3 (mapeo de entidad),
  que no tienen conexión activa (los datos ya están pegados como valores).
- 4 workbooks tienen `externalLinks` sin resolver (AP-Con Ajuste Entidad:
  1, AP_GCT: 1, Eventos Nuevos: 2, más el de Bloque3 ITP primer eje: 1) —
  pueden apuntar a archivos externos no incluidos en este repositorio; no
  se intentó resolverlos (fuera de alcance, y podría requerir acceso de
  red).
- Ninguna incidencia de apertura (ningún archivo falló al abrir, ningún
  error de formato).

## 9. Limitaciones de este documento

- Los 9 workbooks no priorizados se analizaron solo mediante su hoja
  `Index` y su listado estructural de hojas — no se leyeron sus hojas de
  mapeo/dato en detalle. Cualquier regla de transformación específica de
  esos módulos que no aparezca resumida en su Index queda sin documentar
  en este incremento.
- No se abrieron los `vbaProject.bin`, `externalLinks`, ni el contenido de
  `customXml` (Power Query DataMashup) de ningún workbook.
- Las cifras de fila (`max_row`) de las hojas grandes (p. ej.
  `DB_ITP-PW_upd` en Inspecciones, no leída en detalle) no se han
  verificado contra las cifras ya citadas en `config/modules.yaml`.
