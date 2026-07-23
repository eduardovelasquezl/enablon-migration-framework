# Evaluación de Action Plans — objeto transversal

> Action Plans es el único `MigrationObject` con `processing_scope:
> cross_module` y `load_phase: final` en todo el modelo. Este documento
> describe el comportamiento **ya implementado** tal cual existe, sin
> reinterpretarlo. No se cambia ningún estado del modelo. Fuentes:
> [`ADR-003`](../../../architecture/v1.0/decisions/ADR-003-action-plans-cross-module.md),
> [`ADR-004`](../../../architecture/v1.0/decisions/ADR-004-exact-parent-resolution.md),
> [`diagrams/action_plan_flow.md`](../../../architecture/v1.0/diagrams/action_plan_flow.md),
> `src/analysis/module_analysis.py`, `src/analysis/project_analysis.py`,
> `src/knowledge_base/model.py`, `tests/test_module_analysis.py`,
> `tests/test_project_analysis.py`.

## 1. Fuentes por módulo

Una única tabla origen, `ITP_Acciones_correctoras`, clasificada por el
campo `idorigenac` (`evidence:sql_source.ap_acciones_correctoras`). El
mapeo `idorigenac → módulo` (`config/modules.yaml:270-278`, **observed**):

| Módulo | Valores `idorigenac` |
|---|---|
| `eventos_antiguos` | 2, 13 |
| `eventos_nuevos` | 16, 17 |
| `inspecciones_hist` | 4, 9 |
| `simulacros` | 12, 18 |
| `ops` | 3, 8 |
| `ops2` | sin datos (gap reconocido explícitamente por el propio ETL) |
| `visitas_seguridad_y_otros` | 7, 14 (módulo no analizado en detalle todavía) |
| `safety_meetings` | 11 |

Dos ETL alimentan el objeto: `AP_GCT` (solo MOC, sistema `gct`) y
`AP-Con Ajuste Entidad` (resto de módulos, sistema `prevencion`) —
`config/modules.yaml:267-268`.

## 2. `relationship_type`

`ActionPlanRelationshipType` (`src/knowledge_base/model.py`) define dos
valores: `linked_action_plan` (depende de un registro padre en otro módulo)
y `standalone_action_plan` (no depende de nada). Confirmado por
`tests/test_module_analysis.py`: un candidato `standalone_action_plan`
recibe `relationship_status = ResolutionStatus.NOT_APPLICABLE` desde su
creación y **nunca se vuelve a tocar** después.

## 3. Resolución de padre (`parent resolution`)

`resolve_action_plan_parents()` (ver ADR-004) resuelve **solo por
coincidencia exacta** — mismo `source_system` + `target_historical_reference`
frente a un `parent_reference_index`. Nunca por similitud de texto, fecha o
fuzzy matching. Reglas observadas y confirmadas por test
(`tests/test_project_analysis.py`):

- Sin match + quedan módulos del scope sin analizar → `waiting_for_parent`.
- Sin match + scope ya cerrado → `blocked`.
- Más de un match distinto → `conflicting`/`blocked` — nunca se elige uno
  automáticamente.
- Una acción `linked_action_plan` **nunca** se reclasifica como
  `standalone_action_plan`.

## 4. `processing_status` (Action Plans)

`ActionPlanProcessingStatus` (`src/knowledge_base/model.py:292-306`, valores
verbatim): `discovered` → `validated` / `waiting_for_parent` →
`parent_resolved` → **`ready_for_final_load`**, o `blocked` / `excluded` en
cualquier punto.

**Regla dura confirmada por test de inspección de código fuente**
(`tests/test_module_analysis.py::test_module_analysis_nunca_produce_ready_for_final_load_en_el_codigo`):
la cadena literal `"ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD"` nunca
aparece como código ejecutable dentro de `module_analysis.py` — solo puede
asignarse desde `project_analysis.py::finalize_action_plans()`
(`src/analysis/project_analysis.py:389`). Confirmado también en tiempo de
ejecución por `tests/test_project_analysis.py::test_ready_for_final_load_nunca_aparece_antes_de_finalize`.

## 5. Relación entre `module_analysis` y `project_analysis`

- `module_analysis.py` opera **por módulo, de forma aislada**: detecta
  candidatos (`detect_action_plan_candidates`), valida campos
  (`validate_action_plan_fields`), resuelve referencia de padre **local**
  (`resolve_parent_reference`) y puede excluir (`mark_excluded`). Nunca
  produce `ready_for_final_load`, nunca escribe CSV, nunca resuelve por
  coincidencia parcial, nunca inventa un padre ausente — contrato reforzado
  por test de inspección de fuente
  (`tests/test_module_analysis.py`: `".csv" not in source.lower()`, sin
  `import csv`, sin `open(`).
- `project_analysis.py` **consolida** los buffers de todos los módulos
  (`consolidate_action_plan_buffers`, deduplicando por clave configurable —
  default `(source_system, source_module, action_plan_historical_id)`, línea
  52), resuelve padres a nivel **global** (`resolve_action_plan_parents`,
  con índice cruzado entre módulos) y solo entonces finaliza
  (`finalize_action_plans`).
- `finalize_action_plans()` es, según su propio comentario en el código
  (`project_analysis.py:362`), el **"ÚNICO punto que produce
  ready_for_final_load"**.

## 6. Condiciones para quedar preparado para generación de CSV

Confirmado por `tests/test_project_analysis.py`:

1. Un buffer individual solo alcanza `ready_for_final_load` tras pasar por
   `finalize_action_plans()`, nunca antes.
2. `finalize_action_plans()` no actúa mientras **algún módulo dentro del
   scope declarado** no haya reportado su propio `ModuleAnalysisResult` —
   es decir, Action Plans depende de que **todos** los módulos que lo
   alimentan hayan completado su análisis, no de que estén "listos para
   carga" cada uno por separado.
3. `test_action_plans_es_la_ultima_salida_funcional` hard-asserta que los
   ficheros `action_plan*` se escriben siempre **último** dentro de
   `manifest["output_files"]` — Action Plans es, por diseño y por prueba,
   la fase funcional final de todo el pipeline.

## 7. Exclusiones

`mark_excluded()` requiere un `reason: str` explícito y produce
`ActionPlanProcessingStatus.EXCLUDED`. No hay exclusión silenciosa —
siempre queda un motivo trazable.

## 8. Bloqueos

Un buffer queda `blocked` en dos escenarios distintos, ambos confirmados por
test:

- Validación de campos fallida (`FieldValidationResult.is_valid=False`) a
  nivel de `module_analysis.py`.
- Resolución de padre fallida con scope ya cerrado, o múltiples padres en
  conflicto, a nivel de `project_analysis.py`.

## 9. Deduplicación

`consolidate_action_plan_buffers()` deduplica por una clave **configurable**,
nunca fija solo a `action_plan_historical_id` — el docstring de
`analysis_engine.md` lo señala explícitamente ("nunca únicamente por
`action_plan_historical_id`"). El default observado en código es la tupla
`(source_system, source_module, action_plan_historical_id)` — permite que un
mismo `action_plan_historical_id` en `prevencion` y en `gct` no se fusione
por error.

## 10. Colisiones entre source systems

`tests/test_project_analysis.py::test_prueba_integral_seis_modulos_y_escenarios_especiales`
ejercita explícitamente una colisión de ID entre `prevencion` y `gct` con el
mismo `action_plan_historical_id` — confirmado que **nunca se fusionan**,
precisamente por la clave de deduplicación de la sección 9.

## 11. Evidencia disponible sobre el CSV final

- `Action Plans-20072026-41.csv` (Bloque4, 31444 filas de datos —
  recuento corregido en este incremento; `wc -l` naive da 65223 por
  campos multilínea entrecomillados, ver §16 — tab-delimited
  UTF-16LE) — su cabecera incluye, verbatim, todos los campos de enlace
  declarados en `config/modules.yaml:280-287` (`CS_ByPasses`, `CS_Meetings`,
  `MoCChange`, `CS_IndependentManualEvents`, `CS_IndManualOPS`, `CS_IP`,
  `CS_Drills`), más `CS_HistoricalRecord`, `CS_HistoricalDataOrigin`,
  `CS_HistoricalAPID`, `CS_HistoricalOriginID` — trazabilidad completa
  presente en la exportación real.
- Como con el resto de objetos, esto es un **export de datos reales**, no
  una plantilla de importación en blanco confirmada por Enablon — ver
  `evidence_inventory.md` §3.

## 12. Evidencia nueva del incremento de mapping evidence (Bloque2)

Se abrió `Bloque2_Mappings_SQL_ENA/AP.zip` (previamente sin abrir). Contiene
únicamente un duplicado byte a byte de
`sql/source_queries/AP/Acciones_correctoras.sql` — **no aporta ninguna
evidencia nueva** sobre `CS_HistoricalOriginID`, `parent reference`,
deduplicación, ni campos de enlace vacíos. Ver
`mapping_evidence_assessment.md` §10.

## 13. Evidencia nueva del incremento de evidencia ETL (Bloque1)

Se abrió la hoja `Index` de `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN.xlsx` y
de `ETL- AP_GCT_NEW_SITECAN.xlsx`. **Hallazgo confirmado**: ambos
workbooks declaran la clave de actualización
`Update(IDAccionCorrectora,CS_HistoricalAPID)` para los 7 módulos de origen
no-MOC y para los 3 de MOC respectivamente, siempre vía la misma hoja
`MAP-AP`(-CR)/`MAP-updatedate`.

Esto confirma con evidencia estructural (no solo con la cabecera del CSV,
que ya mostraba ambos campos sin explicar su relación) que:

- **`CS_HistoricalAPID`** (desde `IDAccionCorrectora`) es la **identidad
  propia** de cada registro de Action Plan — la clave que el propio ETL usa
  para decidir si un registro ya existe y debe actualizarse.
- **`CS_HistoricalOriginID`** (desde el ID del registro padre — p. ej.
  `IDSimulacro` para acciones de Simulacros, confirmado en
  `sql/source_queries/Simulacros/`) es la **referencia al objeto de
  origen**, no la identidad del propio Action Plan.

Esto **aporta evidencia estructural a favor** de que la duplicación del
63% de `CS_HistoricalOriginID` sea un patrón de agrupación legítimo:
varios `IDAccionCorrectora` distintos (identidad propia distinta) pueden
compartir el mismo `IDSimulacro`/`IDEvento`/etc. (mismo padre, mismo
`CS_HistoricalOriginID`) — exactamente el patrón ya observado directamente
en `ITP_SIM_ACCIONES_CORRECTORAS` durante el análisis de Drills (múltiples
`IDAccionCorrectora` con el mismo `IDSimulacro`, uno por fase/número de
acción). En el incremento en que se escribió este párrafo, esto **no se
había confirmado cuantitativamente** — ver §16 (este incremento) para el
conteo real sobre los 31444 registros del CSV, que sí aporta esa
confirmación cuantitativa (con las limitaciones descritas en §16.5).

Respuesta a las cuatro preguntas de la Tarea 8 del incremento anterior
(conservada como histórico — ver §16.3 para la respuesta actualizada con
datos reales):

- ¿Queda explicado? **No del todo** — hipótesis estructural sólida, sin
  conteo que la confirme.
- ¿Se reduce el porcentaje? **No** — sigue siendo 63% exactamente.
- ¿Continúa sin resolver? **Parcialmente** — la pregunta de "¿defecto o
  diseño?" ahora se inclina hacia "diseño", sin cerrarse.
- ¿Interpretación incorrecta? **Sin evidencia para afirmarlo** — no se
  asume, siguiendo la instrucción explícita de no suponer sin evidencia
  funcional.

## 14. Evidencia que todavía falta

- Por qué la mayoría de registros de Action Plans reales **no tienen
  ningún campo de enlace poblado** — reconocido como pendiente de
  investigar en `config/modules.yaml:288-290`, no explicado por el código,
  ningún ADR, ni por el Index de los ETL revisados en este incremento.
- ~~**Confirmación cuantitativa** de que el 63% de duplicación de
  `CS_HistoricalOriginID` coincide con el patrón "varias acciones por un
  mismo padre" (§13)~~ — **aportada en este incremento, ver §16.** Sigue
  sin poder derivarse de solo el CSV: cuál `source_module` originó cada
  fila (no es una columna del CSV final), ni el conteo de padres
  "no resolubles"/"excluidos" (esos casos, por definición, no llegan al
  CSV final) — ver §16.5.
- El mecanismo exacto de generación de `CS_HistoricalAPID` — la hoja
  `MAP-updatedate` no se ha leído en detalle, solo se confirmó la
  declaración de la clave en el Index. **Confirmado de forma independiente
  en este incremento** vía lectura directa de las hojas `MAP-AP` y
  `MAP-AP-CR` (no solo el Index) — ver `etl_catalog.yaml`
  `etl_transform:ap.map_ap_and_map_ap_cr.historical_apid_double_confirmation`.
- `visitas_seguridad_y_otros` como origen de acciones (`idorigenac 7, 14`)
  no tiene ningún análisis propio detrás — cualquier acción clasificada
  bajo esos códigos hereda esa misma carencia. Ninguno de los 12 workbooks
  analizados en el incremento de evidencia ETL/entidad aportó información
  sobre este módulo.

## 16. Validación cuantitativa sobre datos reales (este incremento)

Se parseó directamente `Action Plans-20072026-41.csv` (Python `csv`,
`encoding='utf-16'`, `delimiter='\t'`, `quotechar='"'` — respetando
quoting, a diferencia del recuento `wc -l` naive usado hasta ahora, ver
corrección en §11). Resultado completo en
`evidence/action_plan_relationship_assessment.yaml` y narrativa en
`action_plan_relationship_analysis.md`. Resumen:

### 16.1 Cifras base

| Métrica | Valor |
|---|---:|
| Total filas de datos | 31444 |
| Con `CS_HistoricalAPID` | 31384 (99.81%) |
| `CS_HistoricalAPID` únicos (global) | 29602 |
| Valores de `CS_HistoricalAPID` duplicados (2+ filas) | 1679 valores, 3461 filas |
| Con `CS_HistoricalOriginID` | 31443 (99.997%) |
| `CS_HistoricalOriginID` distintos (agrupación naive, solo por valor) | 11906 |
| `CS_HistoricalOriginID` distintos (agrupación compuesta, con más contexto) | 11920 |

### 16.2 Clasificación de agrupaciones (equivalente documentado de `is_legitimate_grouping()`)

No se ejecuta código — se aplica manualmente la misma lógica sobre los
datos reales, documentada en detalle en
`evidence/action_plan_relationship_assessment.yaml` (`groups:`) y en
`action_plan_relationship_analysis.md` §2-3. Categorías usadas:
`legitimate_one_to_many_candidate`, `standalone_action_candidate`,
`unresolved_parent`, `conflicting_parent`, `duplicate_action_candidate`,
`cross_system_collision_candidate`, `excluded`, `unknown`.

- **Candidato a agrupación legítima**: 76.17% de los padres (una acción
  propia por grupo, o varias con `CS_HistoricalAPID` todos distintos).
- **Candidato a duplicado**: 1.10% de los padres muestran repetición
  interna de `CS_HistoricalAPID` dentro del mismo grupo (95 grupos, 345
  filas) — incluye un patrón exacto de duplicación 2x observado en GCT.
- **Standalone** (grupo de tamaño 1): 55.35% de los padres.
- Distribución por tamaño de grupo: cubetas 1 / 2 / 3-5 / 6-10 / >10 —
  máximo observado: **179 acciones bajo un mismo padre** (outlier no
  confirmado como plausible, ver `OQ-AP-04`).

### 16.3 Qué representa realmente el "63%"

El 63% citado en incrementos anteriores es la **tasa de no-unicidad
naive** de `CS_HistoricalOriginID` (1 − distintos/total). Recalculado
sobre los datos reales: **62.14%** (agrupación naive) / **62.09%**
(agrupación compuesta) — prácticamente idéntico, la distinción de
sistema origen apenas cambia esta métrica. Esto **NO es lo mismo** que
"% de filas en grupos compartidos legítimamente" — esa cifra distinta es
**79.01%** (proporción de filas que pertenecen a un grupo de tamaño ≥2).
Se documentan ambas cifras por separado, explícitamente, para no repetir
el error de tratarlas como si respondieran la misma pregunta. Metodología
y limitaciones completas en
`evidence/action_plan_relationship_assessment.yaml` (`sixty_three_percent_finding`).

### 16.4 Hallazgo nuevo más relevante: colisión de `CS_HistoricalAPID` entre sistemas

**1437 valores de `CS_HistoricalAPID`** aparecen en más de un sistema de
origen (`source_system` inferido) — es decir, el mismo valor de la
identidad propia del Action Plan (no del padre) se repite entre
`prevencion` y `gct`. Esto es **distinto** de la duplicación de
`CS_HistoricalOriginID` (que es esperada y de diseño, ver §13): aquí es
la clave que en teoría identifica de forma única cada Action Plan la que
colisiona entre sistemas. `tests/test_project_analysis.py` confirma que
el código **nunca fusiona** estos casos gracias a la clave de
deduplicación compuesta (§9-10) — el riesgo no es de fusión indebida en
el motor, sino de **interpretación funcional** de si esta colisión es
esperada (mismo rango de IDs reutilizado en ambos sistemas de origen, sin
relación real) o un indicio de otro problema. Nueva pregunta abierta:
`OQ-AP-06` (prioridad alta).

### 16.5 Limitaciones de esta validación cuantitativa

- El CSV final **no contiene** una columna `source_module`/`idorigenac` —
  el sistema origen se infiere por rango/formato de
  `CS_HistoricalOriginID`, no se lee directamente. No permite reconstruir
  el desglose exacto por módulo (`eventos_antiguos`, `simulacros`, etc.)
  que sí tenía el análisis de código en §13.
- Los ítems 10 (padre no resoluble), 13 (tipos de objeto padre
  incompatibles) y 15 (excluidos/`do_not_migrate`) del checklist de la
  Tarea 8 de este incremento **no pueden contarse desde el CSV final** —
  por definición, un registro con padre no resuelto o excluido no llega a
  la exportación. Requerirían acceso a los buffers intermedios de
  `module_analysis.py`/`project_analysis.py` o a los datos SQL de origen,
  no solo al CSV. Se documentan como limitación, no se estima un valor.
- Esta validación es **estadística/estructural**, no una confirmación
  funcional de que el 63% (o el 79.01%) sea "correcto" — sigue sin
  determinarse si algún subconjunto de esas agrupaciones es en realidad
  un defecto no detectado. No se declara "validada" la relación por
  consistencia estadística sola, tal como exige la instrucción explícita
  de este incremento.

## 15. Recomendación futura (no aplicada en este incremento)

`docs/architecture/v1.0/naming_conventions.md:91` ya registra, como
**Future Improvement sin aplicar**, el rename de `ready_for_final_load` a
`ready_for_csv_generation` — "más preciso una vez exista el Export Engine:
'final' hoy significa 'listo para que el Export Engine lo tome', no
'cargado'". Este documento **recomienda** mantener esa dirección de cambio
para cuando se implemente el Export Engine, pero **no la ejecuta** — ni el
código ni la terminología del modelo se modifican en este incremento, tal
como exigen las instrucciones de esta tarea.
