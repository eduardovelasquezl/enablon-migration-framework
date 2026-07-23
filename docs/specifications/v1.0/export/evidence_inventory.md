# Inventario de evidencias — Export Specifications v1.0

> Resumen narrativo de `evidence/evidence_catalog.yaml` (108 entradas, tras
> el incremento de validación de `Reference`) y de
> `evidence/mapping_catalog.yaml` (10 entradas, añadido en el incremento de
> mapping evidence). Este documento no repite cada entrada — la referencia
> por `evidence_id`/`mapping_id` y explica qué significa en conjunto. Toda
> afirmación aquí es **observed** salvo que se marque explícitamente como
> **inferred**, **recommended** o **pending_confirmation**.
>
> **Actualización — incremento de mapping evidence (Bloque2)**: se abrieron
> y verificaron los 9 ZIP de `Bloque2_Mappings_SQL_ENA/` (previamente
> `evidence_pending`, sin abrir). El resultado se documenta en detalle en
> [`mapping_evidence_assessment.md`](mapping_evidence_assessment.md) — en
> resumen, **ninguno contiene mapping de campo**: los 34 archivos `.sql` de
> primer nivel son duplicados byte a byte de `sql/source_queries/`, y
> `Simulacros.zip` contiene además una copia completa anidada de
> `Reunionesdegrupo.zip`. Las 9 entradas correspondientes de
> `evidence_catalog.yaml` se reclasificaron de `mapping_definition`
> (`evidence_pending`) a `source_sql` (`validated`, salvo
> `evidence:mapping.bloque2_zip_simulacros`, marcada `conflicting` por la
> anomalía del ZIP anidado).
>
> **Actualización — incremento de evidencia ETL/entidad (Bloque1 y
> Bloque3)**: se abrieron y analizaron los 10 workbooks de `Bloque1_ETL/` y
> los 2 de `Bloque3_Mappings_Entidades/` — ver
> [`etl_evidence_assessment.md`](etl_evidence_assessment.md) y
> [`entity_mapping_assessment.md`](entity_mapping_assessment.md). A
> diferencia de Bloque2, **estos SÍ contienen mapping de campo y de
> entidad real** — el patrón de 5 columnas (`DatoOrigen/DatoDestino/
> EsCondicion/ReglaEspecial/Parametro`) y el patrón de lookup ES→XML (G:H)
> se confirman con fórmula real, no solo por comparación de datos. Las 10
> entradas `etl_definition` pasan de `identified`/`confidence: medium` (sin
> abrir) a `partially_reviewed` o `validated` (Simulacros, prioridad de este
> incremento) con `confidence: high` donde corresponde. Las 2 entradas
> `mapping_definition` de Bloque3 pasan de `identified` a `validated`. Ver
> `evidence/etl_catalog.yaml`, `evidence/entity_mapping_catalog.yaml` y
> `evidence/traceability_catalog.yaml`.
>
> **Actualización — este incremento (validación de `Reference` + análisis
> profundo de los 9 ETL restantes + validación cuantitativa de Action
> Plans)**: se registra 1 nueva entrada en `evidence_catalog.yaml`
> (`AFD-DRILLS-REFERENCE-001`, `approved_functional_decision`, `validated`)
> que valida contra el ETL real una regla de negocio ya aprobada
> externamente para `simulacros.Drills.Reference` — ver
> `decision_packages/drills_reference_decision_package.md`. Se profundizó
> además, más allá de la hoja Index, en 27 hojas (3 por workbook) de los 9
> ETL no-Simulacros — ver `etl_deep_analysis.md` — confirmando un patrón
> transversal de resolución de entidad (`RutaEnablon`/`Entidades_Enablon_ITP`)
> repetido en 4 de ellos. Se validaron además, por primera vez, cifras
> reales (no solo estructurales) sobre el CSV completo de Action Plans
> (31444 filas) — ver `evidence/action_plan_relationship_assessment.yaml` y
> `action_plan_relationship_analysis.md`.

## 1. Qué se inspeccionó

Se revisó el repositorio completo salvo binarios pesados (`.xlsx`/`.xlsm`/`.zip`),
que se catalogan por existencia y metadatos (ruta, tamaño, módulo probable)
pero no se abrieron en este incremento. Fuentes revisadas en profundidad:

- 21 documentos de `docs/architecture/v1.0/` (núcleo + 6 ADR + 4 diagramas) +
  `docs/changelog/architecture_changelog.md`.
- `src/knowledge_base/model.py` y los 6 módulos de `src/analysis/` +
  `src/etl/` que implementan el Knowledge Engine.
- Los 4 ficheros de configuración de `config/`.
- 13 archivos de test en `tests/` (267 tests recolectados, 0 errores de
  colección — ver [`observed`] en el resultado de
  `pytest --collect-only -q`, sección 5).
- 34 ficheros `.sql` en `sql/source_queries/` (2 leídos línea a línea:
  el `FULL JOIN` de Eventos Antiguos y `Acciones_correctoras.sql` de AP; el
  resto identificado por nombre y carpeta).
- Cabeceras verbatim de los 17 CSV de
  `inputs/_incoming_claude_web/Bloque4_CSV_Enablon/` — la evidencia más
  valiosa de este inventario, ver sección 3.
- Los 3 ficheros de `inputs/entity_catalog/`.
- `inputs/csv_enablon/CONTENIDO_ESPERADO.txt`.
- `outputs/reports/00_...md` y `03_...md` completos; el resto de reportes
  markdown en sus primeras líneas; todas las cabeceras de los reportes CSV.
- `outputs/inventory/{gct,prevencion}/.../manifest.yaml` (inventario técnico
  real ya ejecutado contra ambas bases).

En el incremento de mapping evidence se abrieron y verificaron además los 9
ZIP de `Bloque2_Mappings_SQL_ENA/` (43 archivos de primer nivel + 1 ZIP
anidado con 3 archivos más, ver
[`mapping_evidence_assessment.md`](mapping_evidence_assessment.md)). En el
incremento de evidencia ETL/entidad se abrieron y analizaron, además, los
10 workbooks de `Bloque1_ETL/` (prioridad: Simulacros, en profundidad; el
resto, estructuralmente + su hoja Index) y los 2 workbooks de
`Bloque3_Mappings_Entidades/` (ambos analizados en profundidad, por ser
pequeños) — ver [`etl_evidence_assessment.md`](etl_evidence_assessment.md)
y [`entity_mapping_assessment.md`](entity_mapping_assessment.md). Sigue sin
abrirse contenido de: el xlsx de incidencias, ni el xlsx/zip de
`Bloque5_Errores`. Son evidencia **identified**, no **validated**.

## 2. Calidad de la evidencia por tipo

| Tipo | Nº entradas | Confianza dominante | Nota |
|---|---:|---|---|
| `architecture_documentation` | 17 | high | Todo `Implemented` confirmado línea por línea contra el código; `Approved Design` confirmado por grep (cero ocurrencias en `src/`). |
| `approved_functional_decision` | 12 | high/medium | Incluye 6 ADR + `config/modules.yaml` + `config/validation_rules.yaml` + 3 reportes narrativos + `AFD-DRILLS-REFERENCE-001` (nuevo, este incremento — regla de `Reference` de Drills validada contra el ETL real). |
| `validated_output_csv` | 27 | high | Los 17 de Bloque4 + 9 reportes de volumetría + el catálogo de entidades resuelto. |
| `source_sql` | 21 | high | 2 ficheros leídos línea a línea + los 9 zips de Bloque2 (reclasificados de `mapping_definition`, ahora `validated` por hash byte a byte) + el resto identificado por carpeta/nombre, más el inventario técnico real ya ejecutado. |
| `etl_definition` | 10 | high/medium | Los 10 se abrieron y analizaron (Simulacros en profundidad, `validated`; el resto vía su hoja Index + estructura, `partially_reviewed`). Confirman con fórmula real el patrón de 5 columnas, titlefix, cloneorigin, lookup en 2 pasos — ver `etl_evidence_assessment.md`. |
| `mapping_definition` | 3 | high/low | Los 2 xlsx de Bloque3 se abrieron y validaron (entidad, no campo — ver `entity_mapping_assessment.md`); el catálogo antiguo permanece obsoleto. Los 9 zips de Bloque2 se reclasificaron a `source_sql` tras abrirlos. |
| `enablon_configuration` | 1 | high | El export bruto de `First_Axis`, fuente de verdad del árbol de entidades. |
| `automated_test` | 10 | high | Los tests **son** el contrato más duro disponible — varios hard-assertan invariantes por inspección del propio código fuente (`"config/modules.yaml" not in source`). |
| `client_rule` | 1 | medium | El export de Help Desk, solo 107/834 tickets categorizados. |
| `unknown` | 6 | variable | Config técnica sin valor de evidencia funcional, o binarios sin abrir. |

No se encontró ninguna entrada que encaje limpiamente en `enablon_template`
u `official_documentation` en sentido estricto — ver sección 3.

## 3. El hallazgo central de este inventario: no hay ningún template de importación confirmado

Las instrucciones de este incremento piden explícitamente no asumir que un
nombre de archivo demuestra que algo es un template Enablon. Aplicado a los
17 CSV de `Bloque4_CSV_Enablon`:

- **observed**: sus cabeceras usan la nomenclatura real de Enablon (`CS_`
  como prefijo de campo personalizado, `Id`, `LevelNo`, `Entity`,
  `FirstAxis`), coinciden con módulos Enablon conocidos (Action Plans,
  Change Register, Drills, Events, JSO...) y están codificados/delimitados
  exactamente como Enablon exporta de forma nativa (UTF-16LE tab-delimited
  para la mayoría; ISO-8859-1/ASCII semicolon-delimited para un subconjunto:
  Causes Data, Checklists Data, Inspection Data, PSM forms, Update External
  Meeting Participations).
- **observed**: `inputs/csv_enablon/CONTENIDO_ESPERADO.txt` confirma que
  estos 17 ficheros son precisamente los CSV reales que el proyecto ya
  posee por módulo, y que se evitó duplicarlos en `inputs/csv_enablon/`
  (~430MB).
- **inferred, no confirmado**: que estos ficheros sean aptos como sustituto
  de un *template de importación en blanco* validado por Enablon. Son
  **exportaciones de datos reales**, no plantillas — Enablon puede exigir en
  importación columnas obligatorias, orden o formato distintos de los que
  aparecen en un export (p. ej. columnas de solo lectura calculadas por el
  sistema, como `GOS` en Bypass, que `config/modules.yaml:161` marca
  explícitamente como "NO importable").
- Un caso ya **confirma** esta distinción de forma directa: `Inspection
  Data-20072026-38.csv` es, según la propia nota del cliente registrada en
  `config/modules.yaml:247`, un "export parcial, no se puede exportar
  completo" — es decir, ni siquiera como export es una representación
  completa del objeto real (`evidence:csv_enablon.inspection_data`, estado
  `conflicting`).

**Conclusión de esta sección**: los 17 CSV de Bloque4 son la mejor evidencia
disponible hoy de la *forma* de cada objeto Enablon, y deben tratarse como
`validated_output_csv` (export real, útil para inferir columnas/encoding),
no como `enablon_template` (plantilla de importación confirmada). Esta
distinción se traslada íntegra a `export_readiness_matrix.md`
(`template_status: candidate`, nunca `validated`, para ningún objeto) y a
`open_questions.md`.

## 4. Carencias detectadas

- **Los 9 zips de `Bloque2_Mappings_SQL_ENA/` ya no son una carencia — son
  un resultado negativo confirmado.** Se abrieron en el incremento de
  mapping evidence: no contienen mapping de campo, solo duplicados de
  `sql/source_queries/`.
- **Los 10 workbooks de `Bloque1_ETL/` y los 2 de
  `Bloque3_Mappings_Entidades/` ya no son una carencia — se abrieron en el
  incremento de evidencia ETL/entidad.** A diferencia de Bloque2, SÍ
  contienen mapping de campo y de entidad real (ver
  `etl_evidence_assessment.md`, `entity_mapping_assessment.md`,
  `evidence/etl_catalog.yaml`, `evidence/entity_mapping_catalog.yaml`).
  Restante: solo Simulacros se analizó en profundidad fila a fila; los
  otros 9 ETL solo vía su hoja Index + estructura — sus hojas de mapeo/dato
  internas siguen sin leerse en detalle.
- **727 de 834 tickets de Help Desk** siguen sin categorizar por módulo.
- **`visitas_seguridad_y_otros`** no tiene ningún SQL, ETL o CSV
  identificado que lo respalde como módulo propio — solo existe como código
  `idorigenac` anidado bajo `ap` (ver Tarea 6, `open_questions.md`).
- **`Causes Data` y `Checklists Data`** (Bloque4) no tienen módulo/objeto
  asignado en `config/modules.yaml` — su relación con Investigations y MOC
  respectivamente es **inferred**, no confirmada.

## 5. Conflictos detectados

- **Naming**: `config/modules.yaml` usa la clave `ap`; código y tests usan
  el slug `action_plans` (p. ej. `migration_object:action_plans.action_plans`
  en `tests/test_knowledge_base_model.py`). `config/modules.yaml` usa
  `safety_meetings`; `tests/test_project_analysis.py` usa
  `reuniones_de_grupo` para el mismo módulo (coincide con el nombre del
  fichero ETL `ETL- reunionesdegrupo-fixEntities_SITECAN.xlsx`). Ningún
  fichero reconcilia estas dos convenciones — **pending_confirmation**.
- **Estructural**: `sql/source_queries/PSM/` existe como carpeta de primer
  nivel, al mismo nivel que `Eventos/`, `MOC/`, etc., pero
  `config/modules.yaml` modela "psm" como submódulo interno de `eventos`
  (`tablas_origen.psm`). No hay evidencia que confirme si esto es una
  decisión deliberada o un artefacto de organización de carpetas —
  **pending_confirmation**.
- **Evidencia parcialmente no verificada**: el agente de investigación no
  pudo confirmar literalmente la columna `CS_HistImpactID`/`CS_HistImpactIDOH`
  (citada en `config/modules.yaml:191` como `clave_correlacion` de Impacts)
  dentro de la cabecera real leída de `Impacts-20072026-9.csv`. Se marca
  `evidence:csv_enablon.impacts` con esta limitación explícita — no se
  asume la coincidencia sin re-verificar.
- **Packaging (nuevo, incremento de mapping evidence)**: `Simulacros.zip`
  contiene una entrada anidada `SM.zip` que es, byte a byte, una copia
  íntegra de `Reunionesdegrupo.zip`. `Simulacros.zip` tiene fecha de
  modificación un día posterior a los otros 8 ZIP. No se ha determinado si
  fue intencional o accidental — clasificado `conflicting`, ver
  `open_questions.md` OQ-GLOBAL-06.
- **Naming interno (nuevo)**: `Reunionesdegrupo.zip` empaqueta sus archivos
  bajo la carpeta interna `SM/`, igual que `sql/source_queries/SM/` — ni el
  ZIP ni las queries usan el slug `reuniones_de_grupo`, que solo aparece en
  `tests/` y en el nombre del ETL Excel. Dato adicional para
  `open_questions.md` OQ-GLOBAL-03, no resolutivo.
- **Ubicación del mojibake corregida (nuevo)**: el mojibake ("├ô") en el
  nombre de dos archivos de Eventos existe únicamente en la copia suelta de
  `sql/source_queries/Eventos/` — dentro de `Eventos.zip` el mismo archivo
  tiene el nombre correctamente codificado en UTF-8 ("Ó"). La corrupción de
  nombre no proviene del ZIP; ocurrió en algún paso posterior no
  identificado.
- **Dos identificadores distintos para Action Plans (nuevo, incremento de
  evidencia ETL)**: el Index de `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN.xlsx`
  confirma que `CS_HistoricalAPID` (identidad propia del Action Plan, vía
  `IDAccionCorrectora`) y `CS_HistoricalOriginID` (referencia al registro
  padre en el módulo de origen) son campos distintos con roles distintos —
  ambos presentes en `Action Plans-*.csv`. Aporta evidencia estructural a
  favor de que el 63% de duplicación de `CS_HistoricalOriginID` sea un
  patrón de agrupación legítimo (varias acciones por un mismo padre), sin
  confirmarlo cuantitativamente — ver `action_plans_assessment.md`.
- ~~**Fórmulas inconsistentes para el mismo campo conceptual entre hojas de
  salida sucesivas**~~ — **resuelto (este incremento)**: en
  `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`, el campo `Reference` de
  Drills se genera con hasta 3 variantes de fórmula según la hoja de
  salida. Se validó contra evidencia real una decisión funcional ya
  aprobada externamente (`AFD-DRILLS-REFERENCE-001`,
  `<CS_Typology>-HIST-<CS_HistoricalOriginID>-<StartingDate(dd/MM/yyyy)>`):
  2 de las 3 variantes coinciden con ella, la tercera
  (`CSV_Generated_BCM_SIM`) se clasifica `residual_rule_candidate` (no
  vigente — falta el literal `HIST` y el orden de componentes difiere).
  `trace_status` pasa de `ambiguous` a `fully_traced` en
  `evidence/traceability_catalog.yaml`. Persiste como pregunta nueva (no
  reapertura) el tratamiento de componentes NULL/vacíos dentro del patrón
  aprobado (`OQ-ETL-06`). Ver
  `evidence/drills_reference_variant_catalog.yaml` y
  `decision_packages/drills_reference_decision_package.md`.
- **Mecanismo de resolución de entidad deprecado repetido sin nota de
  aceptación equivalente (nuevo, este incremento)**: el mismo mecanismo de
  lookup en 2 pasos contra la tabla estructurada `Entidades_Enablon_ITP`
  (= el catálogo deprecado `Entidades_Mapeo`, ya aceptado explícitamente
  para `simulacros.Drills` vía `config/modules.yaml:84`) se encontró
  idéntico en bypass, eventos_antiguos, ops y reuniones de grupo — sin una
  nota de aceptación equivalente para estos módulos. Ver
  `etl_deep_analysis.md` §1 y `open_questions.md` OQ-ENT-04.
- **Referencia rota confirmada por el propio log del ETL (nuevo)**: el
  Index de `ETL_OPS_ArregloEntidad_SIETCAN.xlsx` registra literalmente
  `"Update: columna origen no encontrada (IdOpsAdaptado) (1)"` — un error
  ya presente en el archivo original, no inferido.
- **Copia sin limpiar entre módulos, con evidencia nueva y localizada
  (refuerza hallazgo ya conocido)**: la hoja `CamposXmlBES_SIMS_exportado`
  de Simulacros lleva el acrónimo de Bypass ("BES") en su nombre y contiene
  datos de prueba; la hoja `Mapeo_Letra` de Simulacros conserva la etiqueta
  `"Letra (Reunión de Grupo)"` sin actualizar. Ambos casos confirman con
  cita exacta el patrón ya documentado en CLAUDE.md.

## 6. Limitaciones de este inventario

- No es exhaustivo a nivel de fila/columna para ETL y mappings binarios —
  es un inventario de **existencia y clasificación**, no un análisis
  columna-a-columna (eso corresponde a la especificación por objeto, fuera
  de alcance de este incremento).
- Los recuentos de filas de CSV (`wc -l`) incluyen la cabecera; se han
  usado tal cual, sin restar 1, en toda esta documentación por consistencia
  con las cifras ya citadas en `outputs/reports/`.
- Los archivos con datos de producción reales (`Bloque4_CSV_Enablon/`,
  `Bloque1_ETL/`, `inputs/incidents/`, `Bloque5_Errores/`) pueden contener
  información personal de empleados del cliente (nombres, emails,
  responsables) — señalado por archivo en `evidence_catalog.yaml`, ningún
  valor de esas columnas se ha citado en esta documentación.
