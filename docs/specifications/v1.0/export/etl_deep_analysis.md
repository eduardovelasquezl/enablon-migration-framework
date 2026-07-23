# Análisis profundo de los 9 ETL restantes — Export Specifications v1.0

> Complementa `etl_evidence_assessment.md` (que cubrió los 10 workbooks
> mediante estructura + hoja `Index`). Este documento profundiza, **más
> allá del Index**, en 3 hojas representativas por cada uno de los 9
> workbooks distintos de Simulacros (1 fuente, 1 mapeo, 1 salida — 27
> hojas en total, sobre las 655 hojas del inventario completo en
> `evidence/etl_sheet_catalog.yaml`). No es una cobertura exhaustiva
> hoja por hoja de los 655 — es una profundización dirigida, con la
> profundidad de lectura declarada explícitamente en cada hallazgo. No se
> crea ninguna especificación por objeto en este documento.

## 1. Hallazgo transversal más importante: el mecanismo de resolución de entidad se repite igual en 6 de los 9 workbooks

**observed**, con fórmula idéntica en su estructura, en `bypass` (`DBLink_BES`),
`eventos_antiguos` (`ITP-EVENTOS_OLDv2`), `ops` (`DB-ITP_OPS`), `reuniones`
(`ITP-SM-DBC`), además de `simulacros` (`DB_OrigenSim`, ver
`object_assessments/drills_entity_resolution_assessment.md`):

```
RutaEnablon = IF(IDUnidadOrg<>"", XLOOKUP(IDUnidadOrg, Entidades_Enablon_ITP[IDUnidadOrg], Entidades_Enablon_ITP[RutaSimple|Ruta1]), "")
Nombre Entidad = XLOOKUP(RutaEnablon, Entidades_Enablon_ITP[RutaSimple|Ruta1], Entidades_Enablon_ITP[ENABLON])
```

`Entidades_Enablon_ITP` es, en todos los casos observados, una tabla
Excel estructurada de 681 filas — el mismo recuento de filas que
`inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv`
(el catálogo **deprecado**, per CLAUDE.md: "no usar Entidades_Mapeo de
ningún ETL individual"). Esto **confirma, con evidencia de fórmula en 6
workbooks distintos**, que la resolución de entidad de todos estos módulos
usa el catálogo antiguo embebido en cada ETL, no el catálogo resuelto y
validado (`catalogo_resuelto_code_ruta_site.csv`). Para `simulacros` esto
ya estaba documentado y aceptado como correcto para su época
(`config/modules.yaml:84`); para `bypass`, `eventos_antiguos`, `ops` y
`reuniones` **no hay una nota equivalente** que confirme si es igualmente
aceptable — se registra como pregunta nueva (`OQ-ENT-04`).

`moc` (`DB_MOC_CT`, columna `MapeoEnablonRuta`) y `ap` (`CT_ACCIONES_CR1`,
columna `MapeoEnablonRuta`) usan una fórmula distinta, no leída en detalle
en este incremento (truncada en la muestra) — no se confirma si usan el
mismo mecanismo u otro. `inspecciones` (`DB_ITP-IPS`) no mostró una columna
de resolución de entidad en las primeras 14 columnas muestreadas — no se
descarta que exista más allá de esa muestra.

## 2. Claves de correlación confirmadas por workbook (más allá de lo ya documentado)

| Módulo/objeto | Campo origen | Campo destino | Hoja donde se confirma |
|---|---|---|---|
| `bypass.By_Passes` | `IDBES` | `CS_HistoricalOriginID` | `MapeoBypass` |
| `eventos.Events` (antiguos) | `IDAnalisisA` | *(sin destino en `MAP-ITPOLD-EVT-PCO`, resuelto en otra hoja no leída)* | `MAP-ITPOLD-EVT-PCO` |
| `eventos.Events` (nuevos) | `IDEvento` | `CS_HistoricalEventID` | `MAP-ITPNew-EVT-00` |
| `inspecciones.Inspections` | `IDIps` | `CS_HistoricalOriginID` | `MAP-ITP-IPSBase` |
| `moc.Change_Register` | `IDSolicitudCambio` | `CS_HistoricalOriginID` (vía `Map_CR_NEW_Base`) | `Mapeo_MOC_CT` |
| `ops.JSO` | `IDOps` | `CS_HistoricalOriginID` | `MapeoOpsOLD` |
| `safety_meetings.Group_Meetings` | `IDReunionGrupo` | `CS_HistoricalOriginID` (vía `Mapeo_IDIns`) | `MAP-SM` |
| `ap.Action_Plans` (ambos ETL) | `IDAccion`/`IDAccionCorrectora` | `CS_HistoricalAPID` | `MAP-AP-CR`, `MAP-AP` |

Todas estas coinciden con el patrón ya conocido — ninguna contradice lo
documentado en `config/modules.yaml`, y **`safety_meetings.Group_Meetings`
no tenía su clave de correlación confirmada explícitamente en ningún
incremento anterior** — esta es la primera confirmación directa.

## 3. Reglas de negocio confirmadas con comentario del propio autor del ETL

- **OPS** (`MapeoOpsOLD`, fila `IDCentro`): comentario literal "campo solo
  sale si unsafe behaviour es YES, ESTE CAMPO ha de ser YES" — confirma
  con la propia anotación del autor la regla ya documentada en
  `config/modules.yaml:232` (`CS_CongratulatedWorker` condicional a
  `Unsafe Behavior = YES`).
- **AP-Con Ajuste Entidad** (`MAP-AP`, campo `IDOrigenAC`): resuelto vía
  `Mapeo_Sources` a `Families`/`Type of Origin` — primera confirmación
  directa de que `IDOrigenAC` (la clasificación por `idorigenac` ya
  documentada en `config/modules.yaml:270-278`) alimenta el campo
  `Families` del CSV de Action Plans, no solo la clasificación interna del
  ETL.

## 4. El patrón "//" como convención del autor, no como error técnico (reinterpretación de un hallazgo anterior)

El incremento anterior señaló el prefijo `//` en algunas claves del log de
`Index` (Eventos) como una posible referencia rota. Este incremento
encuentra el mismo prefijo `//` en **nombres de columna reales** dentro de
hojas de mapeo y de salida de **MOC** (`Mapeo_MOC_CT`: `//Template`,
`//IDRef`, `//CS_LevelNo`, `//CS_Reference`; `CSV_MOC_CT2_FULL`: las
mismas 4 como cabecera real de columna) y de **Safety Meetings**
(`CSV_SM_FULL`: columna `//Duration` coexistiendo junto a una columna
`Duration` ya resuelta). **inferred**: el prefijo `//` parece ser una
convención propia del autor del ETL para marcar "nombre de campo
provisional/no confirmado con Enablon", no un error de fórmula — coexiste
sistemáticamente junto a la versión ya resuelta del mismo campo cuando
existe. **pending_confirmation**: no se ha preguntado al autor/cliente si
esta es efectivamente la convención.

**observed, hallazgo de calidad**: en `CSV_MOC_CT2_FULL` las columnas
`//Template`, `//CS_LevelNo` y `//CS_Reference` **no tienen una versión
resuelta alternativa visible** en la muestra de 14 columnas leída — a
diferencia de Safety Meetings, donde si aparece la columna ya resuelta.
Esto sugiere que, para MOC específicamente, estos 3 campos podrían haber
quedado sin resolver en la hoja de trabajo interna del ETL. No se ha
confirmado si esto afecta al CSV real finalmente entregado (Bloque4)
—`Change Register-20072026-8.csv` no se ha vuelto a inspeccionar columna a
columna en este incremento para confirmar o descartar la presencia de
equivalentes sin el prefijo `//`.

## 5. Fórmulas dependientes del orden de filas — confirmado en un segundo módulo

El incremento anterior encontró en Simulacros (`CSV_SIM_full`) fórmulas
`INDICE(...;FILA())` (INDEX/ROW) dependientes de la posición de la fila.
Este incremento confirma el MISMO patrón en **OPS**
(`CSV_OPSOLD_FULL`): `$=SI(INDICE(J:J;FILA())=1;"No";"Yes")` para
`CS_UnsafeBehavior`/`CS_CongratulatedWorker`/`CS_ConversationWithWorker` —
tres columnas booleanas derivadas de una columna J no identificada en la
muestra leída, mediante una comparación posicional. Confirma que este
patrón de fragilidad (Task 11: candidate_obsolete/fórmula dependiente del
orden de filas) no es exclusivo de Simulacros.

## 6. Posible resolución (parcial, inferred) de un CSV huérfano: "Causes Data"

`OQ-OBJ-04` (incremento de mapping evidence) especulaba una relación entre
`Causes Data-22072026-73.csv` e Investigations, basada solo en el patrón
compartido `Why`. Este incremento localiza una fuente **más plausible**:
la hoja `CSV_PSM_ANS-2026-FULL` (dentro del workbook de Eventos Nuevos,
mapeando datos de PSM) tiene cabecera `Causes, RowNo, Question \,
Answer Checkbox \, Answer List \, Title Why \, Why \, Info \, Other PSM
Elements, Id, \HistoricalImpactID, //HistEvtRel` — comparte **las dos
primeras columnas exactas** (`Causes`, `RowNo`) con `Causes Data-*.csv`
(`Causes;RowNo;CheckBox;AnswerListAnswer;Why;CS_Other;CS_Entity;
CS_Incident;Id`), y el patrón temático (preguntas de "5 whys"/causas
raíz) es idéntico. **inferred, confianza media**: `Causes Data` es más
probablemente el destino de las respuestas de PSM (`eventos.PSM_Forms`)
que un hijo directo de `Investigations` — los nombres de columna no
coinciden exactamente (`CheckBox` vs `Answer Checkbox`, `AnswerListAnswer`
vs `Answer List`), por lo que no se declara resuelto, solo se actualiza la
hipótesis principal en `open_questions.md` (`OQ-OBJ-04`, actualizada, no
reabierta como nueva).

## 7. Residuos, versiones y contenido ajeno (Tarea 11)

Todos clasificados `candidate_obsolete` (nunca `obsolete` definitivo):

- **Hojas `MAP-ITPOLD-*` / `MAP_UPDATE_ID-IMP`**: confirmadas de nuevo,
  presentes y ocultas en Eventos Antiguos, Eventos Nuevos, AP-Con Ajuste
  Entidad, AP_GCT, Inspecciones, Simulacros (6 de 9 workbooks distintos de
  este análisis, más el ya confirmado en Simulacros) — ver
  `evidence/etl_sheet_catalog.yaml` (`obsolete_candidate`, 30 hojas en
  total con esta cita).
- **`CSV_Generated_BCM_SIM`** (Simulacros): variante de `Reference` sin el
  literal `HIST`, descartada como regla vigente — ver
  `decision_packages/drills_reference_decision_package.md` §6.
- **Columnas `//`-prefijadas sin resolver** en `CSV_MOC_CT2_FULL` (ver §4).
- **Ningún error de fórmula (`#REF!`, `#N/A`, `#VALUE!`, `#NAME?`)** se
  encontró en ninguna de las hojas muestreadas en este incremento (0 casos
  en un escaneo de las primeras 200 filas de 6 hojas de Simulacros y
  lectura completa de cabecera de las 27 hojas de los 9 workbooks
  restantes) — esto **no** descarta errores en filas no muestreadas.
- **Ningún vínculo a archivo externo** se resolvió ni se intentó resolver
  en los 9 workbooks de este análisis (ver `evidence/etl_catalog.yaml`
  para el recuento de `externalLinks` por workbook, ya reportado en el
  incremento anterior).

## 8. Limitaciones de este análisis

- Cobertura: 27 de 655 hojas leídas en detalle en este documento (más las
  ~44 de Simulacros ya leídas en el incremento anterior = 87 de 655 en
  total, ver `evidence/etl_sheet_catalog.yaml:summary`). El resto se
  clasifica solo por patrón de nombre.
- Ninguna hoja de validación dedicada (`validation` en la taxonomía) se
  identificó con confianza alta en ningún workbook — las 53 hojas
  clasificadas `lookup` y las 159 `mapping` podrían contener lógica de
  validación no separada en una hoja propia.
- No se ha vuelto a abrir ningún CSV real de Bloque4 para contrastar
  columna a columna con estas hojas internas de ETL, salvo Action Plans
  (ver `action_plan_relationship_analysis.md`) — la hipótesis de §6 sobre
  Causes Data no se ha verificado contra el CSV real completo.
