# Matriz de preparación para exportación — Export Specifications v1.0

> Ningún objeto se clasifica `ready_for_draft` sin evidencia mínima sobre
> (1) su fuente, (2) su identidad, (3) su posible salida y (4) sus
> relaciones principales. Esto **no** exige que todas sus columnas estén ya
> resueltas.
>
> **Historial de actualizaciones**: (1) incremento inicial — matriz base;
> (2) incremento de mapping evidence (Bloque2) — `mapping_status` bajó de
> `partial` a `not_started` para todos los objetos tras confirmar que los 9
> ZIP no contenían mapping de campo, se corrigió `visitas_seguridad_y_otros`
> (Tarea 9) y se añadió `ready_for_approved_specification`; (3) incremento de
> evidencia ETL/Bloque1 + entidad/Bloque3 (Tarea 16) — se añaden
> `etl_status` y `traceability_status`, se recalcula `mapping_status` donde
> la nueva evidencia lo justifica, y se reformula
> `approved_specification_readiness` con el vocabulario
> `ready`/`partially_ready`/`evidence_pending`/`blocked` fijado por esa
> tarea (sustituye el valor único `blocked_no_validated_template` usado
> antes); (4) **este incremento** (validación de `Reference` como decisión
> funcional aprobada + resolución de la entidad de Drills + análisis
> profundo de los 9 ETL restantes + validación cuantitativa de Action
> Plans) — se recalcula la decisión de Tarea 16 sobre `simulacros.Drills`
> en §7 (de `evidence_assessment_only` a `object_specification_draft_ready`)
> y se actualiza su `traceability_status` a la luz de
> `AFD-DRILLS-REFERENCE-001` y de la resolución de entidad confirmada en
> `object_assessments/drills_entity_resolution_assessment.md`.

## Vocabularios usados

- **`specification_readiness`**: `ready_for_draft` | `partially_ready` |
  `evidence_pending` | `blocked` | `not_applicable`.
- **`approved_specification_readiness`** (recalculado en este incremento
  con nuevo vocabulario): `ready` | `partially_ready` | `evidence_pending` |
  `blocked`. **Regla dura: ningún objeto puede quedar `ready` si falta
  evidencia sobre el formato o destino Enablon** — como ningún objeto tiene
  hoy un template de importación validado (`template_status: validated`),
  ninguno puede ser `ready` todavía.
- **`template_status`**: `validated` | `candidate` | `missing` |
  `conflicting` | `not_applicable`.
- **`source_definition_status`**: `confirmed` | `partial` | `inferred` |
  `evidence_pending`.
- **`etl_status`** (nuevo en este incremento — si el ETL de ese objeto fue
  analizado y si confirma mapping de campo con fórmula real, no solo con
  comparación de datos): `confirmed` | `partial` | `not_reviewed` |
  `evidence_pending`.
- **`mapping_status`**: `confirmed` | `partial` | `not_started` |
  `evidence_pending`. `not_started` significa "se buscó evidencia de
  mapping de campo en la fuente más probable y se confirmó que no estaba
  ahí" (Bloque2) o "no se ha buscado todavía en la fuente que sí la tiene"
  (ETL no revisado en detalle).
- **`traceability_status`** (nuevo en este incremento — rollup a nivel de
  objeto del `trace_status` de sus campos en
  `evidence/traceability_catalog.yaml`): `confirmed` | `partial` |
  `evidence_pending`.
- **`relationship_status`**: `confirmed` | `partial` | `evidence_pending` |
  `not_applicable`.
- **`validation_rule_status`**: `confirmed` | `partial` | `conflicting` |
  `evidence_pending`.
- **`client_override_status`**: `documented` | `partial` | `none_known` |
  `evidence_pending`.

Importante: ningún objeto tiene hoy `template_status: validated` — los 17
CSV de `Bloque4_CSV_Enablon` son exportaciones de datos reales, no
plantillas de importación en blanco confirmadas por Enablon (ver
`evidence_inventory.md` §3).

## 1. Matriz resumen

| Módulo.Objeto | specification_readiness | approved_specification_readiness | template_status | source_definition_status | etl_status | mapping_status | traceability_status | relationship_status | validation_rule_status | client_override_status |
|---|---|---|---|---|---|---|---|---|---|---|
| simulacros.Drills | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `confirmed` | `confirmed` | `partial` | `confirmed` | `confirmed` | `documented` |
| simulacros.List_of_Activities | `partially_ready` | `blocked` | `candidate` | `confirmed` | `confirmed` | `confirmed` | `evidence_pending` | `confirmed` | `conflicting` | `none_known` |
| safety_meetings.Group_Meetings | `partially_ready` | `blocked` | `candidate` | `partial` | `not_reviewed` | `not_started` | `evidence_pending` | `confirmed` | `evidence_pending` | `documented` |
| safety_meetings.Update_External_Meeting_Participations | `evidence_pending` | `evidence_pending` | `candidate` | `inferred` | `not_reviewed` | `not_started` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `none_known` |
| moc.Change_Register | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `partial` | `partial` | `evidence_pending` | `confirmed` | `partial` | `documented` |
| bypass.By_Passes | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `not_reviewed` | `not_started` | `evidence_pending` | `confirmed` | `confirmed` | `documented` |
| eventos.Events | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `partial` | `partial` | `evidence_pending` | `confirmed` | `evidence_pending` | `documented` |
| eventos.Impacts | `partially_ready` | `blocked` | `candidate` | `partial` | `partial` | `partial` | `partial` | `confirmed` | `evidence_pending` | `documented` |
| eventos.Investigations | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `partial` | `partial` | `evidence_pending` | `partial` | `evidence_pending` | `documented` |
| eventos.PSM_Forms | `partially_ready` | `blocked` | `candidate` | `partial` | `not_reviewed` | `not_started` | `evidence_pending` | `partial` | `conflicting` | `documented` |
| ops.JSO | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `partial` | `partial` | `evidence_pending` | `confirmed` | `confirmed` | `documented` |
| inspecciones.Inspections | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `not_reviewed` | `not_started` | `evidence_pending` | `confirmed` | `evidence_pending` | `documented` |
| inspecciones.Observations | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `not_reviewed` | `not_started` | `evidence_pending` | `confirmed` | `evidence_pending` | `none_known` |
| inspecciones.Inspection_Data | `blocked` | `blocked` | `conflicting` | `confirmed` | `not_reviewed` | `not_started` | `evidence_pending` | `partial` | `partial` | `documented` |
| ap.Action_Plans | `ready_for_draft` | `blocked` | `candidate` | `confirmed` | `partial` | `partial` | `partial` | `confirmed` | `partial` | `documented` |
| visitas_seguridad_y_otros | `evidence_pending` | `evidence_pending` | `missing` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` |
| (sin módulo) Causes Data | `evidence_pending` | `evidence_pending` | `candidate` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `none_known` |
| (sin módulo) Checklists Data | `evidence_pending` | `evidence_pending` | `candidate` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `evidence_pending` | `none_known` |

## 2. Objetos cuya preparación mejoró en este incremento

- **`simulacros.Drills`**: `etl_status` `not_reviewed`→`confirmed`,
  `mapping_status` `not_started`→`confirmed` (9 mappings de campo con
  fórmula real confirmados, ver `object_assessments/drills_evidence_assessment.md`),
  `traceability_status` (campo nuevo) `partial` (6/9 trazas
  `fully_traced`). **No** mejora `specification_readiness` (ya era
  `ready_for_draft`) ni `approved_specification_readiness` (sigue
  `blocked` — falta template validado, condición que ningún incremento de
  análisis puede resolver por sí solo).
  **Actualización (este incremento):** `Reference` pasa de `ambiguous` a
  `fully_traced` (decisión funcional aprobada `AFD-DRILLS-REFERENCE-001`,
  ver §7) y el campo de entidad pasa de `missing` a `fully_traced`
  (mecanismo localizado, ver `object_assessments/drills_entity_resolution_assessment.md`).
  `traceability_status` sube a **7/9 `fully_traced`** (se mantiene el
  valor de rollup `partial` porque `CS_HistoricalDrillAttendees` y los
  campos de duración siguen `partially_traced` — no hay ningún campo en
  estado `missing` o `ambiguous` restante). Esta mejora es la que permite
  recalcular la decisión de Tarea 16 en §7.
- **`simulacros.List_of_Activities`**: mejora más marcada de todo el
  incremento. `source_definition_status` `evidence_pending`→`confirmed`,
  `etl_status` `evidence_pending`→`confirmed`, `mapping_status`
  `not_started`→`confirmed`, `relationship_status`
  `evidence_pending`→`confirmed`. `specification_readiness` mejora de
  `evidence_pending` a **`partially_ready`** — sigue sin `ready_for_draft`
  porque `Mapeo_Estado_AL` usa un vocabulario de destino distinto al de
  Drills para el mismo campo origen, sin confirmar si es deliberado
  (`validation_rule_status: conflicting`, ver `etl_evidence_assessment.md` §7).
- **`ap.Action_Plans`**: `etl_status`/`mapping_status` mejoran de
  `evidence_pending`/`not_started` a `partial` (clave `CS_HistoricalAPID`
  confirmada, distinta de `CS_HistoricalOriginID`). `traceability_status`
  (campo nuevo) `partial`.
- **`eventos.Impacts`**: `etl_status`/`mapping_status`/`traceability_status`
  mejoran a `partial` — se confirmaron 2 pares clave-destino distintos
  (`CS_HistImpactID`/`CS_HistImpactIDOH`), resolviendo parcialmente
  `OQ-OBJ-03` (sin determinar cuál es la "correcta").
- **`eventos.Events` / `eventos.Investigations` / `moc.Change_Register` /
  `ops.JSO`**: `etl_status`/`mapping_status` mejoran de `evidence_pending`/
  `not_started` a `partial` — sus hojas Index confirman al menos la clave
  de correlación real, aunque no el mapping de campo completo.

## 3. Objetos que continúan bloqueados o pendientes (sin cambio en este incremento)

- **`inspecciones.Inspection_Data`**: sigue `blocked` — la razón (export
  parcial reconocido por el cliente, `config/modules.yaml:247`) no depende
  de evidencia ETL adicional; ningún workbook analizado la resuelve.
- **`safety_meetings.Update_External_Meeting_Participations`**: sigue
  `evidence_pending` — el ETL de Safety Meetings no se analizó en detalle
  (solo su Index) en este incremento; su clave de correlación sigue sin
  documentar.
- **`bypass.By_Passes`, `inspecciones.Inspections`, `inspecciones.Observations`,
  `eventos.PSM_Forms`**: `etl_status`/`mapping_status` permanecen
  `not_reviewed`/`not_started` — sus workbooks se analizaron solo
  estructuralmente (hoja Index), no se profundizó en sus hojas de mapeo
  internas (fuera de la prioridad de este incremento, que era Simulacros).
- **`visitas_seguridad_y_otros`** y los 2 CSV huérfanos (`Causes Data`,
  `Checklists Data`): sin cambio — ninguno de los 12 workbooks analizados
  aportó evidencia nueva sobre ellos.

## 4. `ready_for_draft` vs. `ready_for_approved_specification` (heredado, vocabulario actualizado)

Estos son dos niveles distintos, deliberadamente separados:

- **`ready_for_draft`** (`specification_readiness`) — puede empezar a
  escribirse un borrador de especificación por objeto, sabiendo que
  quedarán huecos. Requiere los 4 mínimos: fuente, identidad, salida
  candidata, relaciones principales.
- **`approved_specification_readiness`** — la especificación de ese objeto
  podría aprobarse como definitiva. **Regla dura: ningún objeto puede
  alcanzar `ready` sin un template de importación de Enablon validado, o
  una decisión funcional equivalente que lo sustituya.**

Consecuencia directa: los 12 objetos con `specification_readiness:
ready_for_draft` o `partially_ready` quedan en
`approved_specification_readiness: blocked`, sin excepción — ningún
incremento de análisis (Bloque2, Bloque1, Bloque3) puede levantar este
bloqueo por sí solo; requiere una acción del cliente (confirmar un
template real) o una decisión funcional documentada que lo sustituya.
`visitas_seguridad_y_otros` y los 2 CSV huérfanos quedan
`approved_specification_readiness: evidence_pending` (no `blocked`) porque
ni siquiera tienen la evidencia mínima de especificación — `blocked`
implica un obstáculo puntual sobre evidencia por lo demás suficiente; aquí
la carencia es total.

## 5. Corrección de `visitas_seguridad_y_otros` (heredada del incremento de mapping evidence, sin cambio en este incremento)

`visitas_seguridad_y_otros` se corrigió de `specification_readiness:
not_applicable` a `evidence_pending` y `template_status: missing` (antes
`not_applicable`) porque no existe una decisión funcional explícita que lo
excluya del alcance — `config/modules.yaml:277` lo describe literalmente
como "módulo no analizado en detalle todavía", que es ausencia de análisis,
no una decisión de exclusión. Ninguno de los 12 workbooks de este
incremento (ETL o entidad) mencionó ni aportó evidencia sobre este módulo
— la corrección se mantiene sin cambios. Por indicación de la Tarea 6
original, esta carencia **no bloquea** la especificación de ningún otro
objeto de esta matriz.

## 6. Action Plans / `CS_HistoricalOriginID` — estado acumulado (Tarea 10 del incremento anterior + Tarea 8 de este incremento)

Resultado del incremento de mapping evidence (Bloque2): `AP.zip` no aportó
evidencia nueva sobre el 63% de duplicación de `CS_HistoricalOriginID`.

Resultado de **este** incremento (ETL, Bloque1): se abrió el Index de
`ETL- AP-Con Ajuste Entidad_NEW_SIETCAN.xlsx` y se confirmó que Action
Plans usa **dos identificadores distintos**: `CS_HistoricalAPID` (identidad
propia, vía `IDAccionCorrectora`) y `CS_HistoricalOriginID` (referencia al
registro padre en el módulo de origen). Esto **aporta evidencia
estructural** a favor de que la duplicación de `CS_HistoricalOriginID` sea
un patrón de agrupación legítimo — varias acciones (`IDAccionCorrectora`
distintos) pueden compartir el mismo padre (`CS_HistoricalOriginID` igual),
tal como ya se observó directamente en `ITP_SIM_ACCIONES_CORRECTORAS`
(múltiples `IDAccionCorrectora` con el mismo `IDSimulacro`, una fila por
fase). **No se confirma cuantitativamente** — no se ha contado si el 63%
observado coincide con el patrón de "varias acciones por simulacro/evento/
inspección", solo se confirma que el mecanismo que lo permitiría existe y
es de uso normal en el diseño del ETL, no un accidente.

Respecto a las cuatro posibilidades planteadas por la Tarea 8 de este
incremento:

- ¿Queda explicado? **No del todo** — hay un mecanismo plausible, no una
  confirmación cuantitativa.
- ¿Se reduce el porcentaje? **No** — sigue siendo 63% (11905 únicos de
  31444, cifra inalterada).
- ¿Continúa sin resolver? **Parcialmente** — la pregunta de "¿es un
  defecto?" ahora tiene una hipótesis estructural sólida en contra (no es
  un defecto, es agrupación por diseño), pero sin conteo que la confirme.
- ¿Era producto de una interpretación incorrecta? **No hay evidencia para
  afirmar esto tampoco** — se mantiene sin asumir ni error ni
  confirmación, tal como exige la instrucción de no suponer sin evidencia
  funcional.

`ap.Action_Plans` mantiene `specification_readiness: ready_for_draft` —
sin cambios, este hallazgo no afecta los 4 mínimos, pero mejora
`etl_status`/`mapping_status`/`traceability_status` (ver §2).

## 7. Decisión sobre Drills (Tarea 17 del incremento anterior; recalculada en la Tarea 16 de este incremento)

Ver justificación completa en `object_assessments/drills_evidence_assessment.md`
§21. Estados posibles: `object_specification_draft_ready` |
`evidence_assessment_only` | `blocked`.

### 7.1 Decisión original (incremento anterior) — conservada como histórico, no borrada

**Decisión entonces: `evidence_assessment_only`.**

| Criterio | Evaluación |
|---|---|
| Cobertura SQL | Alta — fuente única, sin joins, confirmada |
| Cobertura ETL | Alta — 9 reglas de campo confirmadas con fórmula real |
| Cobertura mapping | Alta para campos simples; **ambigua** para `Reference` (3 fórmulas distintas confirmadas) y **missing** para el campo de entidad (`CS_ImpactedEntities`) |
| Cobertura CSV | Alta — CSV real con 36 columnas, cabecera completa confirmada |
| Destino Enablon | **Sin confirmar** — ningún template de importación validado (regla dura, aplica a todos los objetos por igual) |
| Relaciones | Confirmadas (Action Plans vía idorigenac; List of Activities comparte fuente y clave) |
| Validaciones | Ninguna hoja de validación dedicada identificada |
| Preguntas abiertas | 4 nuevas (`OQ-ETL-01..04`), ninguna resuelta todavía |
| Conflictos | 1 directo (`Reference`, `ambiguous`) + 1 heredado de alcance ampliado (mecanismo de `titlefix`, ahora aplicable a Simulacros/Bypass/OPS, no solo MOC) |

Esta decisión fue correcta con la evidencia disponible en su momento — no
se reinterpreta retroactivamente, se sustituye por una nueva evaluación
con evidencia nueva (ver 7.2).

### 7.2 Recálculo (este incremento) — evidencia nueva: `Reference` resuelto + entidad localizada

Dos de los tres motivos que sostenían `evidence_assessment_only` ya no
aplican:

1. `Reference` dejó de ser `ambiguous`: se validó contra evidencia real
   una decisión funcional ya aprobada externamente (`AFD-DRILLS-REFERENCE-001`,
   patrón `<CS_Typology>-HIST-<CS_HistoricalOriginID>-<StartingDate(dd/MM/yyyy)>`)
   y se confirmó que 2 de las 3 variantes de fórmula del ETL coinciden con
   ella (la tercera, `CSV_Generated_BCM_SIM`, se clasifica
   `residual_rule_candidate`, no vigente). `trace_status` pasa a
   `fully_traced`. `OQ-ETL-03` se cierra como `resolved` (no se reabre).
2. El campo de entidad dejó de ser `missing`: se localizó el mecanismo de
   resolución de 2 pasos (`RutaEnablon` vía `Entidades_Enablon_ITP`,
   destino `CS_ImpactedEntities`) leyendo más profundamente `MapeoSims`
   (fila 44) y `DB_OrigenSim` (columnas U/V) — ver
   `object_assessments/drills_entity_resolution_assessment.md`.
   `trace_status` pasa a `fully_traced`.

**Reevaluación contra los 4 criterios explícitos de la Tarea 16:**

| Criterio de la Tarea 16 | Evaluación |
|---|---|
| (a) `Reference` es `fully_traced` | **Sí** — `AFD-DRILLS-REFERENCE-001`, ver 7.2.1 arriba. |
| (b) No existe otro conflicto crítico en una columna ya exportada | **Sí, se cumple** — de los 9 campos trazados, 7 están `fully_traced` y 2 (`CS_HistoricalDrillAttendees`, campos de duración) están `partially_traced`, pero ninguno está `missing`, `ambiguous` ni `conflicting`. Los 2 campos `partially_traced` corresponden a defectos sistémicos ya documentados y aceptados como tales (redondeo de duración a 5 min/mes de 30 días fijos; asistentes incompletos por usar solo 1 de 2 campos origen posibles — ver CLAUDE.md "Defectos sistémicos ya confirmados") — no son ambigüedades nuevas sin explicación, son limitaciones conocidas del propio ETL origen. |
| (c) La resolución de entidad, si sigue faltando, puede documentarse como campo pendiente sin bloquear el resto | **No aplica ya** — la entidad ya no falta, se resolvió (ver 7.2.2 arriba). El campo `CS_HistoricalDrillAttendees` (el único que sigue con cobertura parcial genuina, no por defecto conocido) se documenta como campo pendiente en el borrador, sin bloquear el resto — cumple el espíritu del criterio aunque no sea estrictamente el mismo campo. |
| (d) Se distingue claramente borrador vs. especificación aprobada | **Sí** — `specification_readiness` (borrador) y `approved_specification_readiness` (aprobada) son columnas separadas en esta matriz desde el incremento de mapping evidence; `approved_specification_readiness` sigue `blocked` para Drills (ver más abajo) precisamente para mantener esa distinción. |

**Decisión recalculada: `object_specification_draft_ready`.**

**Por qué SÍ ahora**: los dos huecos que impedían fijar columnas de
destino con estabilidad (fórmula de `Reference` sin decidir, entidad sin
localizar) están cerrados con evidencia — uno por decisión funcional
aprobada y validada contra el ETL real, el otro por lectura más profunda
del propio workbook. Lo que queda pendiente (asistentes, precisión de
duración, tratamiento de componentes NULL/vacíos en `Reference` —
`OQ-ETL-06`) son huecos acotados y documentables como campos/columnas
pendientes dentro de un borrador, no ambigüedades que obliguen a adivinar
la regla de negocio completa.

**Por qué NO `ready` en `approved_specification_readiness`**: sigue sin
existir un template de importación de Enablon validado para ningún
objeto de este inventario (regla dura, ver §4) — `object_specification_draft_ready`
es un estado de **borrador**, no de especificación aprobada. Ambos
estados coexisten sin contradicción: Drills puede tener ya un borrador
razonable y seguir `blocked` en la vía de aprobación definitiva.

**Por qué NO `blocked`**: sigue sin haber ningún obstáculo estructural
confirmado (a diferencia de `inspecciones.Inspection_Data`) — todo lo
pendiente es evidencia adicional deseable, no un impedimento.

**Conclusión**: `simulacros.Drills` avanza de **Object Evidence
Assessment** a **borrador de especificación de objeto** en este
incremento — el primer objeto del inventario en cruzar ese umbral. Sigue
siendo, con diferencia, el objeto con más evidencia acumulada y menos
preguntas abiertas de prioridad alta de todo el inventario. Preguntas
abiertas restantes específicas de Drills tras este recálculo: `OQ-ETL-05`,
`OQ-ETL-06`, `OQ-ENT-04` (ninguna bloqueante para el borrador, per (c)/(d)
arriba).

## 8. Justificación por objeto heredada (incremento de mapping evidence, sin cambio salvo lo indicado en §2)

### simulacros.Drills — ver §2 y §7 para las actualizaciones de este incremento.
### simulacros.List_of_Activities — ver §2 para la actualización de este incremento (mejora más marcada).

### safety_meetings.Group_Meetings — `partially_ready`
Sin cambio de fondo. `Reunionesdegrupo.zip` (Bloque2) confirmado sin
mapping de campo; el ETL de Safety Meetings (Bloque1) se analizó solo vía
su Index en este incremento, confirmando estructuralmente
ITP-SM-DBC→MAP-SM→CSV_SM_FULL, sin llegar a mapping de campo.

### safety_meetings.Update_External_Meeting_Participations — `evidence_pending`
Sin cambio — el Index de Safety Meetings confirma que
ITP_ASISTENTES_RG→MAP-Asist→CSV_Asistentes_FULL es un paso de ETL propio,
reafirmando (no confirmando por primera vez) la hipótesis de que
`Asistentes_SM2025.sql` es su fuente, pero sin clave de correlación
documentada todavía.

### moc.Change_Register — `ready_for_draft`
Sin cambio de fondo. `MOC.zip` (Bloque2) confirmado sin mapping de campo;
el ETL de MOC (Bloque1) analizado vía su Index en este incremento —
confirma admisión explícita del autor de trabajo inconcluso en Risk
Assessment (relevante para `OQ-TPL-03`), sin resolver el CCP pendiente ni
el mecanismo de `titlefix`.

### bypass.By_Passes — `ready_for_draft`
Sin cambio de fondo. Confirmado que su ETL también usa la hoja
`CharacterFix`/`titlefix`, igual que Simulacros — amplía el alcance de
`OQ-GLOBAL-02` (ver `etl_evidence_assessment.md` §6).

### eventos.Events / Impacts / Investigations / PSM_Forms
Sin cambio de fondo en `specification_readiness`. Ver §2 para las mejoras
de `etl_status`/`mapping_status`. Nuevo hallazgo colateral: nombre de
archivo mejor codificado (UTF-8 correcto) dentro de `Eventos.zip` que en su
copia suelta de `sql/source_queries/Eventos/` (mojibake genuino) — no
cambia ningún estado de esta matriz.

### ops.JSO — `ready_for_draft`
Sin cambio de fondo. Ver §2 — mejora `etl_status`/`mapping_status` por la
clave `IdOpsAdaptado/IdOps↔CS_HistoricalOriginID` confirmada y por el error
de referencia rota registrado en el propio log del ETL.

### inspecciones.Inspections / Observations / Inspection_Data
Sin cambio de fondo. `inspecciones.Inspection_Data` se mantiene `blocked`
— la razón sigue siendo la propia admisión del cliente de que su export es
parcial, no algo que este incremento pudiera resolver abriendo el ETL.

### ap.Action_Plans — `ready_for_draft`
Sin cambio en `specification_readiness`. Ver §2 y §6 para el resultado
específico de Tarea 8 sobre `CS_HistoricalOriginID`/`CS_HistoricalAPID`.

### visitas_seguridad_y_otros — `evidence_pending`
Sin cambio — ver §5.

### Causes Data / Checklists Data (sin módulo) — `evidence_pending`
Sin cambio — ninguno de los 12 workbooks de este incremento mencionó ni
aportó evidencia sobre estos dos CSV huérfanos.
