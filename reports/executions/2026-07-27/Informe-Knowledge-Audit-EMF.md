# Informe de Ejecución — Sprint 8.1: Knowledge Coverage & Traceability Audit

**Fecha:** 2026-07-27
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Auditoría documental y de código únicamente. Fuentes
permitidas y efectivamente usadas: `src/`, `config/`, `docs/`, `tests/`.
**No se ejecutó SQL. No se ejecutó el pipeline. No se recuperó
documentación externa. No se creó ningún workspace. No se modificó
configuración. No se creó ningún commit.**

## 0. Objetivo principal — respuesta directa

> **"¿Puede el EMF explicar completamente cómo construye el CSV final de
> Drills sin necesidad de consultar los ETL originales?"**

**Respuesta: sí, para las 8 columnas que el prototipo genera hoy — no,
para las 28 columnas reales restantes (26 de ellas por decisión de
alcance ya documentada, 2 por una laguna de documentación descubierta en
esta misma auditoría).**

Evidencia que sostiene el "sí" parcial: las 8 columnas generadas por
`src/export/prototype/drills/pipeline.py` tienen, cada una, una función de
transformación ejecutable y testeada (`transformations.py`/`mappings.py`),
un `evidence_id` propio en `config/exports/drills.yaml`, y — en 7 de los 8
casos — una traza de conocimiento independiente ya registrada en
`docs/specifications/v1.0/export/evidence/traceability_catalog.yaml` con
`trace_status: fully_traced`, calculada **antes** de escribir una sola
línea de código de este prototipo. El código no depende de reabrir el
ETL para producir esas 8 columnas — la evidencia ya fue extraída una vez
y congelada en YAML/código (`reference_data` de `drills.yaml`). Ver
`docs/01-architecture/drills-csv-contract.md` y
`docs/01-architecture/knowledge-traceability-matrix.md` para el detalle
campo a campo.

## 1. Knowledge Coverage Matrix

Ver `docs/01-architecture/knowledge-coverage-matrix.md` (14 áreas
evaluadas: 8 IMPLEMENTADO, 5 IMPLEMENTADO PARCIALMENTE, 1 PENDIENTE, 0 NO
APLICA).

## 2. Dependencias reales del Framework (leídas del código, no listadas por existencia)

| Archivo externo | Módulo consumidor | Función | Cuándo se usa | Obligatorio/Opcional | Tipo |
|---|---|---|---|---|---|
| `sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql` | `src/export/prototype/drills/extractor.py` | `extract_drills()` → `config.source.sql_path.read_text()` | Siempre, etapa `query`, toda ejecución sample/full | **Obligatorio** — `config.py::load_drills_config` lanza `FileNotFoundError` si falta | **DEPENDENCIA OPERATIVA** |
| `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv` | `src/export/prototype/drills/mappings.py` | `get_entity_catalog()` → `load_entity_catalog()` | Siempre, etapa `transform_and_export`, antes de iterar filas | **Obligatorio** — `FileNotFoundError` si falta | **DEPENDENCIA OPERATIVA** |
| `.env` (credenciales SQL) | `src/db/connection.py` (vía `src/db/query_runner.py`, invocado por `extractor.py`) | `load_dotenv()` + construcción de conexión SQLAlchemy | Siempre que se ejecuta una query real | **Obligatorio** para ejecución real (no para tests, que usan `monkeypatch`) | **DEPENDENCIA OPERATIVA** |
| `Drills-22072026-41.csv` (CSV histórico, resuelto vía `DataWorkspace` desde Sprint 7) | `pipeline.py::_resolve_historical_csv_path`, `comparison.py::build_comparison_report` | Llamada tras escribir el CSV, antes de `issues.jsonl` | Solo si `EMF_DATA_ROOT` está declarado Y el fichero existe en el workspace | **Opcional** — su ausencia nunca detiene el pipeline (`comparison_report.yaml` simplemente no se genera) | **DEPENDENCIA DE COMPARACIÓN** (no operativa, no documental) |
| `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` | **Ninguno** — verificado por `Grep` sin resultados de `read_excel`/`openpyxl` en `src/export/prototype/drills/*.py` | — | **Nunca**, en ninguna ejecución del pipeline | No aplica en tiempo de ejecución | **DEPENDENCIA DOCUMENTAL** (se leyó UNA VEZ, manualmente, fuera del pipeline, para poblar `reference_data` de `drills.yaml`; no se vuelve a leer) |
| `config/modules.yaml` | **Ninguno en tiempo de ejecución** — única mención es un comentario de texto en `mappings.py:3` (`Ver config/modules.yaml:84` como referencia humana) | — | Nunca (no hay `load_yaml("config/modules.yaml")` en ningún fichero de `src/export/prototype/drills/`) | No aplica | **DEPENDENCIA DOCUMENTAL** |

**Conclusión de Fase 2**: el pipeline de Drills tiene exactamente **3
dependencias operativas reales** (query SQL, catálogo de entidad, `.env`),
**1 dependencia de comparación opcional** (CSV histórico), y **2
dependencias puramente documentales** que el código nunca lee en tiempo de
ejecución (ETL, `modules.yaml`). Ninguna ejecución del pipeline de Drills
—sample o full— necesita abrir el ETL original.

## 3. Contrato completo del CSV final de Drills

Ver `docs/01-architecture/drills-csv-contract.md` — 8 columnas
implementadas con contrato campo a campo completo; 28 columnas reales
restantes clasificadas (26 excluidas con motivo, 2 sin ninguna entrada de
contrato — ver Fase 6).

## 4. Inventario completo de campos estándar (no-`CS_`) del CSV real

11 columnas no-`CS_` de las 36 reales:

| Campo | Implementado | Estado de trazabilidad |
|---|---|---|
| `Reference` | Sí | 🟢 |
| `StartingDate` | Sí | 🟢 |
| `NameEN`/`NameFR`/`NameES`/`NameZH`/`NameBR` (5) | No | 🔴 |
| `EstimatedLoss` | No | 🔴 (sin contrato, ver Fase 6) |
| `RealLoss` | No | 🔴 (sin contrato, ver Fase 6) |
| `GroupsList` | No | 🔴 |
| `Id` | No (por diseño — Enablon lo asigna después) | 🟢 (exclusión totalmente entendida) |

2 de 11 implementados; ninguno de los 9 restantes tiene mecanismo SQL/ETL
confirmado (a diferencia de varios campos `CS_` excluidos, que sí lo
tienen — ver Fase 5).

## 5. Inventario completo de campos `CS_` (25 de las 36 columnas reales)

| Campo `CS_` | Documentado | Mapping | Validación | Default | Lookup | ETL | Estado |
|---|---|---|---|---|---|---|---|
| `CS_Typology` | Sí | `fields[0]` | `must_resolve_or_use_documented_default` | `"NADA"` | `typology_lookup` | `fully_traced` | 🟢 |
| `CS_HistoricalOriginID` | Sí | `fields[3]` | `required_non_null` | Ninguno | Ninguno | `fully_traced` | 🟢 |
| `CS_Letter` | Sí | `fields[4]` | `warn_if_unresolved` | `"NOLETTER-WRONG"` (solo si vacío) | `letter_lookup` | `fully_traced` | 🟢 |
| `CS_ImpactedEntities` | Sí | `fields[5]` | `warn_if_unresolved_or_conflicting` | Ninguno | `entity_catalog` | `fully_traced` | 🟢 |
| `CS_WorkflowStatus` | Sí | `fields[6]` | `warn_if_unresolved` | Ninguno confirmado | `workflow_status_lookup` | `fully_traced` | 🟢 |
| `CS_HistoricalDataOrigin` | Sí | `fields[7]` | `constant_literal` | Literal fijo | Ninguno | `evidence_id` posiblemente reutilizado de otra traza (ver § 6) | 🟡 |
| `CS_Duration` | Sí (en `excluded_columns`) | No implementado | — | — | — | `partially_traced`, `OQ-ETL-02` | 🟡 |
| `CS_HistoricalUserId` | Sí (en `excluded_columns`) | No implementado (PII, por diseño) | — | — | — | `fully_traced` en ETL | 🟡 |
| `CS_HistoricalUserName` | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` propio | 🟡 |
| `CS_HistoricalDrillAttendees` | Sí (en `excluded_columns`) | No implementado | — | — | — | `partially_traced`, `OQ-ETL-01` | 🟡 |
| `CS_HistoricalDrillResponsibleName` | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` propio | 🟡 |
| `CS_HistoricalAttachedFiles` | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` | 🔴 |
| `CS_OtherContacts` / `CS_ExternalParticipants` / `CS_OtherParticipants` (3) | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` | 🔴 |
| `CS_HistoricalRecord` | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` | 🔴 |
| `CS_EnvConsequences`…`CS_ObservationsCommunication` (9) | Sí (en `excluded_columns`) | No implementado | — | — | — | Sin `trace_id` | 🔴 |

**Respuestas explícitas a las 3 preguntas de Fase 5:**

1. **¿Existe algún campo `CS_` que llegue al CSV sin contrato?** No. Los 6
   campos `CS_` que sí llegan al CSV generado (`CS_Typology`,
   `CS_HistoricalOriginID`, `CS_Letter`, `CS_ImpactedEntities`,
   `CS_WorkflowStatus`, `CS_HistoricalDataOrigin`) tienen los 6 una
   entrada completa en `fields` de `drills.yaml` — `OUTPUT_COLUMNS` en
   `pipeline.py` es una lista fija que coincide exactamente con esas 6 más
   `Reference`/`StartingDate`, verificado por lectura directa del código.
2. **¿Existe algún `CS_` soportado pero no documentado?** No. Los 6
   implementados tienen `evidence_id` propio; ninguno carece de
   documentación.
3. **¿Existe algún `CS_` documentado pero no implementado?** Sí — **19 de
   25**. Todos con motivo explícito en `excluded_columns` (no es una
   omisión silenciosa) salvo por el matiz de `CS_HistoricalDataOrigin`
   (implementado, pero con la anomalía de cita cruzada de § 6).

## 6. Campos huérfanos

**En el CSV generado: cero.** Las 8 columnas que produce el prototipo
tienen las 8 una entrada completa en `fields` — verificado por inspección
directa de `OUTPUT_COLUMNS` (`pipeline.py:58-67`) contra
`config.fields` (`config.py::load_drills_config`, que falla con
`ValueError` si faltan claves obligatorias en cualquier entrada). No hay
ninguna columna sin mapping, sin transformación o sin validación en la
salida real.

**Hallazgo adyacente (no un huérfano de salida, sino de contrato):** 2 de
las 36 columnas reales de Enablon —`EstimatedLoss` y `RealLoss`— **no
tienen ninguna entrada** en `config/exports/drills.yaml`, ni en `fields`
ni en `excluded_columns`, y tampoco aparecen en ningún `trace_id` de
`traceability_catalog.yaml`. A diferencia de las otras 26 columnas
excluidas (todas con una razón documentada, aunque sea "sin columna SQL
identificada"), estas 2 no tienen ni siquiera esa constancia — es una
brecha real de completitud del Mapping Model, descubierta por esta
auditoría, no heredada de un análisis anterior. **No implica ningún
riesgo operativo hoy** (el prototipo nunca las genera), pero sí una
brecha de documentación pendiente de cerrar antes de declarar el
Template Contract "completo" en cualquier sentido formal.

**Anomalía adicional detectada (evidence_id reutilizado):** el campo
implementado `CS_HistoricalDataOrigin` declara
`evidence_id: "etl_transform:simulacros.multifielduser.historical_user_lookup"`
en `config/exports/drills.yaml`. Ese mismo identificador aparece en
`traceability_catalog.yaml` como `transformation_ids` de la traza
`trace:simulacros.drills.cs_historicaluserid` — que documenta el mecanismo
de un campo **distinto** (`CS_HistoricalUserId`, no implementado). No se
puede confirmar con la evidencia disponible si esto es una reutilización
deliberada (el mecanismo "MultiField_User" podría, plausiblemente,
producir a la vez el identificador de usuario Y una descripción del
origen histórico) o una cita incorrecta heredada de un incremento
anterior. Se deja marcado como pregunta abierta, no como error confirmado
— no se asume ninguna de las dos posibilidades.

## 7. Cobertura razonada por área

| Área | Cobertura | Evidencia | Riesgos | Pendiente |
|---|---|---|---|---|
| Query Extraction | Alta — única tabla, sin joins, hash de integridad, ejecutado realmente | `extractor.py`, ejecución 2026-07-23 | Ninguno identificado para modo `sample`; modo `full` contra SQL real nunca probado a través del Core (`framework-core-v1.md` § 19) | Ejecución real en modo `full` |
| Canonical Model | Baja — solo diseño conceptual, sin tipos implementados | `canonical-data-model.md` (Status: Proposed) | Ninguno urgente — Drills funciona sin él; riesgo aparece solo si se necesita reutilizar el pipeline para un segundo objeto sin CDM | Implementación de `CanonicalRecord`/`CanonicalField`/`Provenance` — explícitamente diferida (principio 8, "sin consumidor real todavía") |
| Mappings | Alta para Drills, nula como motor genérico | `transformations.py`/`mappings.py` (ejecutable); `mapping-specification.md` (Proposed, sin motor) | Bajo para Drills (funciona); alto para un segundo objeto, que reescribiría las mismas funciones en vez de reutilizar una especificación declarativa | Motor de `MappingRule`/`rule_type` — Fase P2 del roadmap EMF |
| Transformaciones | Alta | `transformations.py`, 28 tests unitarios | Bajo — funciones puras, testeadas de forma aislada | Ninguno bloqueante |
| Lookups | Alta | `reference_data` + `mappings.py`, ejecución real (93/100 entidades resueltas) | Catálogo de entidad usa una tabla deprecada (`Entidades_Enablon_ITP`) — aceptado explícitamente para Simulacros, no para otros 4 objetos (`OQ-ENT-04`) | Confirmar `OQ-ENT-04` antes de reutilizar el mismo mecanismo en bypass/eventos_antiguos/ops/safety_meetings |
| Template Contract | Media — 8/36 columnas, con 2 sin ninguna entrada de contrato | `drills-csv-contract.md` | Bajo hoy (el prototipo no promete más de 8); documentación incompleta si se presenta como "contrato cerrado" sin aclarar las 28 restantes | Documentar `EstimatedLoss`/`RealLoss` en `excluded_columns` (mínimo, no requiere nueva evidencia) |
| Validation | Alta para el CSV de salida, nula para `data_quality_checks` transversal | `validator.py` (ejecutable, testeado); `config/validation_rules.yaml::data_quality_checks` (sin motor) | Bajo para Drills (ya se valida antes/después de escribir); alto si se asume que `data_quality_checks` ya protege algo — no protege nada todavía | Conectar `data_quality_checks` a un motor ejecutable, o marcarlo explícitamente como "solo catálogo de referencia humana" en su propio YAML |
| Comparison | Alta | `comparison.py`, ejecutado realmente contra `Drills-22072026-41.csv` | Bajo — opcional por diseño, nunca bloquea | Ninguno |
| Evidence | Alta | `evidence/collector.py`/`workbook.py`, ejecutado realmente | Bajo | Ninguno |
| Campos estándar | Baja-Media — 2/11 implementados | `drills-csv-contract.md` § 4 | Bajo (el prototipo nunca prometió más) | Ninguno bloqueante — decisión de alcance, no carencia |
| Campos `CS_` | Media — 6/25 implementados, 19 excluidos con motivo, 0 sin documentar | `drills-csv-contract.md` § 3, este informe § 5 | Bajo — ninguna exclusión es silenciosa | Cerrar `OQ-ETL-01`/`OQ-ETL-02` si se decide ampliar alcance |
| Outputs | Alta | `exporter.py`/`manifest.py`, ejecución real con hashes verificados | Bajo | Ninguno |
| Workspace | Alta | `data_workspace.py`, validado este mismo Sprint (9/9 categorías) | Bajo | Ninguno bloqueante |

## 8. ETL Gap Analysis

**¿Qué conocimiento sigue dependiendo de los ETL?**

| Clasificación | Campos/áreas | Motivo |
|---|---|---|
| **No depende** | Las 8 columnas implementadas + su lógica de negocio | Evidencia ya extraída una vez y congelada en `config/exports/drills.yaml`/código — ninguna ejecución del pipeline necesita reabrir el ETL. |
| **Depende parcialmente** | `CS_Duration` (`OQ-ETL-02`), `CS_HistoricalDrillAttendees` (`OQ-ETL-01`), `CS_HistoricalUserId`/`UserName` (mecanismo conocido, PII, no portado a código), `CS_HistoricalDataOrigin` (anomalía de `evidence_id`, § 6) | El ETL ya documentó el mecanismo (total o parcialmente), pero portar ese conocimiento a un `fields`/`transformations.py` ejecutable sigue pendiente. |
| **Depende totalmente** | Las 5 columnas `Name*` (origen SQL de "Titulo" nunca confirmado), las 9 columnas de checklist (`CS_EnvConsequences`…`CS_ObservationsCommunication`), `CS_OtherContacts`/`CS_ExternalParticipants`/`CS_OtherParticipants`/`GroupsList`/`CS_HistoricalAttachedFiles`, `CS_HistoricalRecord` | Ningún mecanismo SQL/ETL fue localizado en ningún incremento de análisis anterior — reabrir el ETL (o una fuente equivalente) es la única vía conocida para avanzar, si se decide ampliar el alcance del prototipo. |
| **No aplica / no depende de ETL en absoluto** | `EstimatedLoss`, `RealLoss` | Ni siquiera el ETL las documenta explícitamente en los assessments ya realizados — su ausencia no es "conocimiento en el ETL pendiente de portar", es una laguna de análisis completo (nueva). |

## 9. Recuperación recomendada del material ETL/CSV/documentación pendiente

| Material | Clasificación | Justificación |
|---|---|---|
| `Drills-22072026-41.csv` (CSV histórico real) | **IMPORTANTE** | Habilita `comparison_report.yaml` (ya implementado y probado) — mejora la confianza de cualquier ejecución nueva, pero el pipeline funciona sin él (comparación opcional). No es crítico porque no bloquea ni sample ni full. |
| `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` | **ÚTIL** | Permitiría cerrar `OQ-ETL-01`/`OQ-ETL-02` (asistentes, duración) y documentar `Name*`/checklist si se decide ampliar el alcance del prototipo más allá de las 8 columnas actuales — pero las 8 columnas ya implementadas no lo necesitan en absoluto. |
| ETL de bypass/eventos_antiguos/ops/safety_meetings (para resolver `OQ-ENT-04`) | **ÚTIL** | Confirmaría si el uso del catálogo deprecado es igualmente aceptable en esos 4 módulos — no afecta a Drills, que ya tiene esta cuestión resuelta explícitamente. |
| `helpdesk_export_834_tickets.xlsx` (incidencias del cliente) | **SOLO HISTÓRICO** | Ya presente localmente, correlacionado con hallazgos técnicos en `CLAUDE.md` — no es un insumo que el pipeline de Drills consuma nunca. |
| Los 3 ficheros SQL sin usar (`SQLQuery4.sql`, `SQLQuery6.sql`, `SQLQuery9.sql`, `Acciones correctoras.sql`) | **NO NECESARIO** (para Drills) | Ya identificados en `drills-operational-mvp.md` § 4 como pertenecientes a un futuro objeto Action Plans/actualización, no a este prototipo — recuperarlos no aporta nada a Drills.Reference/CS_Typology/etc. |
| Cualquier ETL adicional solo para volver a verificar las 8 columnas ya implementadas | **NO NECESARIO** | Estas 8 columnas ya tienen `trace_status: fully_traced` o decisión funcional aprobada (`AFD-DRILLS-REFERENCE-001`) — reabrir el Excel no añadiría certeza, solo repetiría un análisis ya cerrado. |

## 10. Riesgos — si todos los ETL desaparecieran definitivamente

| Qué se perdería | Impacto | Justificación |
|---|---|---|
| Capacidad de producir las 8 columnas ya implementadas | **Sin impacto** | El conocimiento ya está congelado en `config/exports/drills.yaml` (`reference_data`) y en código (`transformations.py`/`mappings.py`) — el pipeline no vuelve a leer el ETL nunca. |
| Capacidad de auditar/verificar por qué esas 8 columnas son correctas, desde cero | **Impacto bajo** | Se perdería la posibilidad de re-derivar la evidencia desde la fórmula original, pero no la capacidad de operar — los documentos de assessment (`drills_entity_resolution_assessment.md`, `drills_reference_decision_package.md`, `traceability_catalog.yaml`) ya son un resumen suficiente y versionado en Git, independiente del Excel. |
| Capacidad de resolver `OQ-ETL-01`/`OQ-ETL-02` (asistentes, duración) | **Impacto medio** | Sin el ETL, no hay ninguna otra fuente conocida (SQL solo no basta — las fórmulas de recombinación viven en el propio Excel) para cerrar estas 2 preguntas; quedarían permanentemente `partially_traced`. |
| Capacidad de implementar las 22 columnas `🔴` (checklist, `Name*`, adjuntos, `CS_HistoricalRecord`) | **Impacto alto** | Ningún mecanismo SQL/ETL fue localizado — sin el ETL, la única vía sería inventar la regla (prohibido explícitamente por `CLAUDE.md`) o declarar esas columnas permanentemente fuera de alcance. |
| Capacidad de resolver `OQ-ENT-04` para los otros 4 módulos que comparten el mismo mecanismo de entidad | **Impacto medio** (fuera del alcance de Drills, pero relevante al proyecto) | Sin el ETL de esos módulos, la pregunta queda abierta indefinidamente. |
| `EstimatedLoss`/`RealLoss` | **Impacto crítico** en términos relativos — es la única laguna donde ni siquiera existe un punto de partida documental | Ya hoy, sin que desaparezca nada, no hay ninguna evidencia de estas 2 columnas — su "impacto de pérdida" es, en la práctica, ya el escenario actual. |

## 11. Recomendaciones

1. **Documentar `EstimatedLoss`/`RealLoss` en `excluded_columns`** (o
   iniciar su análisis si se decide ampliar el prototipo) — la acción de
   menor esfuerzo y mayor cierre de esta auditoría, no requiere ETL ni
   SQL, solo una entrada de configuración con motivo honesto
   (`NO_ANALYSIS_PERFORMED` o equivalente).
2. **Aclarar la anomalía de `evidence_id` de `CS_HistoricalDataOrigin`**
   (§ 6) — confirmar con quien mantiene `traceability_catalog.yaml` si es
   una reutilización intencional o una cita heredada incorrecta.
3. **Ninguna validación falta** para las 8 columnas ya implementadas — el
   par pre-escritura/post-escritura (`validator.py`) ya cubre lo que el
   incremento actual necesita.
4. **Ningún contrato falta** para lo ya implementado — sí falta,
   explícitamente, el contrato de `EstimatedLoss`/`RealLoss` (punto 1).
5. **Partes del Framework ya completamente desacopladas de Excel**: el
   99% del camino operativo de Drills (extracción, transformación,
   validación, exportación, comparación, evidencia, workspace) — ninguna
   de estas etapas lee un `.xlsx` en tiempo de ejecución (verificado por
   `Grep`, § 2). El único acoplamiento restante a Excel es **conceptual y
   ya resuelto**: los valores de `reference_data` se extrajeron una vez
   del ETL y ahora viven como datos versionados, no como dependencia
   activa.
6. **No ampliar el alcance de Drills sin recuperar el ETL** si se decide
   perseguir las 22 columnas `🔴` — no hay atajo: la evidencia SQL/ETL no
   existe todavía para esas columnas, y `CLAUDE.md` prohíbe inventar
   reglas no documentadas.

## 12. Acciones pendientes antes de recuperar la documentación original

1. Confirmar con el usuario si `EstimatedLoss`/`RealLoss` deben
   clasificarse como excluidas ahora mismo (acción de configuración, sin
   ETL) o si se prefiere investigarlas cuando se recupere el ETL.
2. Priorizar, si se recupera el ETL, resolver primero `OQ-ETL-01`
   (asistentes) y `OQ-ETL-02` (duración) — son las 2 únicas columnas
   `partially_traced` con mecanismo ya parcialmente confirmado, el menor
   esfuerzo de cierre.
3. No recuperar los ETL de bypass/eventos_antiguos/ops/safety_meetings
   solo para Drills — son relevantes para `OQ-ENT-04`, una pregunta que
   no bloquea a Drills.
4. Aclarar la anomalía de `evidence_id` (§ 6, recomendación 2) antes de
   asumir que `CS_HistoricalDataOrigin` está tan sólidamente trazado como
   los otros 5 campos `CS_` implementados.

## Confirmaciones finales

- No se ejecutó SQL Server.
- No se ejecutó ningún sample ni full del pipeline.
- No se recuperó ni se intentó recuperar ningún ETL, CSV real ni
  documentación externa.
- No se creó ningún workspace ni carpeta nueva.
- No se modificó ninguna configuración (`config/*.yaml`, `.env`).
- No se creó ningún commit — los 3 ficheros de `docs/01-architecture/` y
  este informe quedan sin commitear, a la espera de revisión.
