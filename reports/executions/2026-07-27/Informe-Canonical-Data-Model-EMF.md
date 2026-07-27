# Informe — Canonical Data Model (EMF)

**Proyecto:** Enablon Migration Framework (EMF)
**Fecha:** 2026-07-27
**Tarea:** Diseño arquitectónico del Canonical Data Model (sin implementación de código)

---

## 1. Hallazgos del repositorio que influyeron en el diseño

- **No existe hoy un tipo de "registro normalizado" real.** El propio documento
  `data-processing-lifecycle.md` (§ 6) ya lo admite: el pipeline de Drills opera
  directamente sobre un `pandas.DataFrame` crudo con las columnas de la query SQL.
  El Canonical Data Model (CDM) cierra exactamente esa brecha.

- `src/knowledge_base/model.py` es el precedente más rico del repositorio en
  cuanto a patrones (IDs deterministas `make_*_id`/`short_hash`, vocabularios
  cerrados como clase + `frozenset`, `Evidence`/`Relation` con estado
  categórico) pero pertenece a una capa distinta: cataloga el panorama de
  ETL/mapeos a nivel de análisis, no los datos que fluyen durante una
  ejecución de migración. Se reutilizan sus **patrones**, nunca sus entidades.

- `src/export/prototype/drills/` ya materializa, sin nombrarlas así, piezas
  embrionarias del CDM: `LookupResult.status` (una traza de transformación),
  `EntityResolution`/`EntityCatalog` (lookup dinámico con estado categórico:
  `resolved`/`do_not_migrate`/`unresolved`/`conflicting`), `issues.jsonl` (ya
  con la forma casi exacta de una entidad `Issue`, con `run_id`, `row_key`,
  `category`, `severity`, `source_value`, `mapped_value`, `evidence_id`).

- `src/query/models.py` confirma el patrón de separar "expresión sin validar"
  de "expresión ya validada y compilada", con una propiedad que decide qué se
  serializa (`manifest_entry`) — el mismo principio de "no serializar más de
  lo necesario" se aplica en el CDM a `Issue` y `Provenance`.

- `src/evidence/models.py` confirma que el Evidence Engine construye su
  contexto leyendo exclusivamente artefactos ya escritos por el pipeline
  (`validation_report`, `export_manifest`, `comparison_report`, `issues`) —
  nunca vuelve a tocar la fuente. El CDM debe poder serializarse sin romper
  ese principio.

- `config/exports/drills.yaml` + `config.py` (`FieldSpec`) ya es, de facto,
  el Mapping Model / Template Contract de Drills. El CDM **no** lo duplica:
  `FieldSpec` pertenece a la capa de configuración de proyecto, nunca al Core.

---

## 2. Entidades inicialmente consideradas

Las 13 candidatas propuestas en el encargo, evaluadas una a una sin dar por
supuesto que todas fueran necesarias:

`Execution`, `Source`, `SourceLocation`, `CanonicalRecord`, `CanonicalField`,
`FieldValue`, `Provenance`, `Relationship`, `Issue`, `Review`,
`TransformationTrace`, `MappingReference`, `ValidationResult`.

---

## 3. Entidades finalmente seleccionadas

Cinco entidades con identidad propia:

| Entidad | Qué representa |
|---|---|
| `Execution` | Una ejecución completa del pipeline EMF. |
| `CanonicalRecord` | Un registro migrable individual. |
| `CanonicalField` | Un campo de un registro, con sus tres estados de valor y su procedencia. |
| `Relationship` | Una relación tipada entre dos registros (o entre un registro y una referencia aún no resuelta). |
| `Issue` | Un problema detectado en cualquier etapa del pipeline. |

Dos entidades embebidas (sin identidad ni colección propia, viven dentro de
`CanonicalField`):

| Entidad embebida | Qué representa |
|---|---|
| `Provenance` | De dónde vino un valor y con qué certeza. |
| `TransformationTrace` | Qué regla de mapeo/transformación produjo un valor y con qué resultado. |

Cada una de las 5 con identidad propia tiene un consumidor real ya
identificado (Mapping/Transformation/Validation/Export/Evidence Engine, o el
patrón ya implementado de Action Plans transversales).

---

## 4. Entidades descartadas o combinadas, y justificación

| Candidata | Decisión | Justificación |
|---|---|---|
| `Source` + `SourceLocation` | Fusionadas en `Provenance.source_type` + `Provenance.locator` (diccionario de atributos estructurados, no una clase por tipo de fuente). | No existe hoy, ni en la fase de roadmap prevista, un consumidor que necesite un catálogo de fuentes independiente del propio dato. Crear una jerarquía `SqlLocation`/`ExcelLocation`/`PdfLocation` sería la abstracción prematura que "No Abstraction Without a Real Consumer" prohíbe con un solo Connector implementado (SQL Server). |
| `FieldValue` | No se crea. | Los tres estados de un valor (original, normalizado, transformado) son atributos **explícitos** de `CanonicalField`, no una secuencia genérica de estados. El número de estados es fijo y conocido (exactamente 3, ligados a 3 etapas fijas del pipeline); una secuencia genérica sería event sourcing sin necesidad, y el encargo lo prohíbe explícitamente. |
| `MappingReference` | Fusionada en `TransformationTrace.rule_reference`. | Una referencia a "qué entrada de mapeo se aplicó" solo tiene sentido junto al resultado de aplicarla — separarlas obligaría a mantener sincronizados dos objetos por cada valor transformado sin que nadie hoy necesite consultar la referencia de forma aislada de su resultado. |
| `ValidationResult` | No se crea. | `engineering-standards.md` § 4 ya fija que una función `validate_*` devuelve una lista de violaciones, nunca un objeto propio. Se representa como `Issue` con `stage=validation` + `CanonicalRecord.status` — una `ValidationResult` sería una envoltura redundante sobre algo que ya existe. |
| `Review` | No se crea como entidad de primer nivel. | Se representa como tres atributos de `CanonicalField` (`review_required`, `review_status`, `review_note`). Ningún flujo de trabajo actual, ni el previsto para la primera fuente documental (Word/PDF), necesita más de una ronda de revisión por valor. Si en el futuro aparece un consumidor real que necesite historial de varias rondas, se promueve a entidad con su propia ADR — no antes. |

---

## 5. Resumen del modelo

```
Execution (run_id, object_type, started_at, mode, status)
  │
  │ produce N
  ▼
CanonicalRecord (record_id, object_type, source_record_id,
                 functional_key?, source_reference, status, metadata)
  │
  ├── fields: { field_name -> CanonicalField }
  │              │
  │              ├── original_value / normalized_value / transformed_value
  │              ├── data_type (detectado)
  │              ├── provenance            (embebida)
  │              ├── transformation_trace? (embebida)
  │              └── review_required / review_status / review_note
  │
  ├── relationships: [ Relationship, ... ]   (referencian record_id, no objetos completos)
  │
  └── issues: consultables por record_id     (colección de nivel superior, no embebida)

Relationship (relationship_type, source_record, target_record?,
              target_reference?, direction, required, resolution_status)

Issue (issue_id, execution_id, stage, severity, code, message,
       record_id, field_name?, rule_reference?, status, resolution?,
       source_value?, transformed_value?, blocks_export)
```

Ninguna flecha representa herencia — todo es composición o referencia por
identificador. `CanonicalField` no tiene identidad global propia: se
direcciona siempre como `(record_id, field_name)`.

**Tipos canónicos mínimos:** `string`, `integer`, `decimal`, `boolean`,
`date`, `datetime`, `identifier`, `reference`, `list`, `object`, `null`.
Deliberadamente menor que el conjunto de tipos de cualquier fuente concreta
(no se reproducen todos los tipos posibles de SQL/Excel/JSON/Enablon).

**Ciclo de vida** (un único campo de estado, no flags independientes):

```
extracted → normalized → mapped → transformed → validated → exportable
                                                            ↘ excluded
                                                            ↘ failed
```

No todo registro recorre todas las etapas (p. ej. una entidad "No migra"
puede pasar directo a `excluded`).

---

## 6. Decisiones de identidad

Tres identidades distintas, que nunca se confunden entre sí:

| Identidad | Campo | Naturaleza |
|---|---|---|
| Técnica | `record_id` | Hash determinista |
| Del origen | `source_record_id` | Valor verbatim tal como existe en la fuente |
| Funcional | `functional_key` (opcional) | Valor de negocio; lo rellena el Mapping Engine |

Estrategia de `record_id`:

```
record_id = "record:" + slugify(object_type) + "." + slugify(source_system)
            + "." + short_hash(source_record_id_o_locator)
```

Reutiliza el patrón ya implementado en `src/knowledge_base/model.py`
(`slugify`, `short_hash`, familia `make_*_id`) — no se inventa un segundo
mecanismo de hashing en el mismo repositorio.

`run_id` de `Execution` es una **cuarta** identidad, de naturaleza distinta:
aleatoria (`uuid4`), nunca determinista.

Riesgos evaluados explícitamente antes de aceptar el hash (pedido expreso
del encargo, para no proponer un hash "universal" sin análisis):

- **Cambios del origen**: el hash se calcula sobre la identidad, nunca sobre
  el contenido — que un valor se corrija entre ejecuciones no cambia el
  `record_id`. Permite que un futuro Comparison Engine detecte "mismo
  registro, valor distinto".
- **Registros duplicados**: el defecto ya confirmado en `CLAUDE.md`
  (duplicados de `CS_HistoricalOriginID` en Eventos/OPS) produce, con esta
  estrategia, el **mismo** `record_id` para las filas duplicadas del origen
  — esto es correcto, no un error: el CDM no oculta la duplicación, la hace
  visible para que Validation/Comparison la reporten como `Issue`.
- **Claves incompletas**: cuando la fuente no aporta una `source_record_id`
  estable (típico de un párrafo de PDF/Word), el hash cae al `locator`
  (archivo+página+bloque). Este `record_id` es menos estable — se documenta
  con un valor auxiliar `identity_basis: source_key | locator_derived`.
- **Reproducibilidad**: el hash nunca incluye `run_id` ni ningún valor que
  cambie entre ejecuciones sobre el mismo origen.
- **Datos sensibles**: cuando `source_record_id` es en sí mismo sensible, el
  hash actúa además como seudonimización segura — mismo patrón ya
  implementado hoy en `comparison.py` (`sample_keys_hashed`).

---

## 7. Decisiones de provenance

Modelo común, único para cualquier fuente (nunca una clase por tipo de fuente):

```
Provenance
├── source_type          ("sql_server" | "excel" | "csv" | "word" | "pdf" | "json")
├── locator                (dict de atributos estructurados, forma según source_type)
├── extraction_method
├── original_value          (copia de evidencia, autocontenida)
├── confidence               (float 0.0-1.0)
└── captured_at               (UTC)
```

`locator` es un diccionario plano de claves conocidas por convención, no una
clase — la propia forma que el encargo pedía evaluar explícitamente
("`source_type` / `locator` / atributos estructurados") en vez de una clase
por fuente.

`Provenance` vive **embebido por campo**, no por registro — justificado con
el caso real ya existente en Drills: el campo `Reference` se construye a
partir de tres columnas de origen distintas (`CS_Typology`,
`CS_HistoricalOriginID`, `StartingDate`), cada una potencialmente con su
propia procedencia.

Para fuentes estructuradas (SQL/CSV/JSON) la mayoría de estos campos son
triviales (`confidence=1.0`, `locator` sin página/sección) — es el mismo
modelo, no uno simplificado aparte, solo con valores por defecto.

---

## 8. Decisiones de confianza y revisión humana

Cinco conceptos distintos, nunca comprimidos en un único número ambiguo:

| # | Concepto | Dónde vive | Naturaleza |
|---|---|---|---|
| 1 | Certeza del dato origen | Propiedad de referencia del `source_type` (documentación, no un campo almacenado por registro) | Descriptiva |
| 2 | Confianza de la extracción | `Provenance.confidence` | Numérica 0.0–1.0 — el único valor continuo del modelo |
| 3 | Confianza del mapeo | `TransformationTrace.status` | Categórica (`resolved`\|`resolved_with_fallback`\|`default_applied`\|`unresolved`\|`conflicting`) |
| 4 | Resultado de validación | `Issue(stage=validation)` + `CanonicalRecord.status` | Presencia/ausencia de violaciones, no un score |
| 5 | Revisión humana | `CanonicalField.review_required`/`review_status`/`review_note` | Categórica, independiente de las cuatro anteriores |

El vocabulario de `TransformationTrace.status` generaliza literalmente
`LookupResult.status` ya implementado en `transformations.py`.

Motivo de no usar un único `confidence_score` (0-100), pese a existir ya ese
patrón en `knowledge_base/model.py` con otro propósito: un valor extraído
con confianza 1.0 (SQL) puede fallar mapeo o validación — comprimir ambos en
un número ocultaría cuál de los dos falló.

---

## 9. Compatibilidad con issues.jsonl, manifests y Evidence Engine

| `issues.jsonl` actual | `Issue` (CDM) | Nota |
|---|---|---|
| `run_id` | `execution_id` | Renombrado |
| `row_key` | `record_id` | Renombrado, usa identidad § 6 |
| `category` | `code` | Renombrado |
| `severity` | `severity` | Sin cambio |
| `message` | `message` | Sin cambio |
| `source_value` | `source_value` | Sin cambio, denormalizado |
| `mapped_value` | `transformed_value` | Renombrado |
| `evidence_id` | `rule_reference` | Renombrado |
| `included_in_csv` | `blocks_export` | Renombrado e invertido: expresa "esta incidencia es la razón del rechazo" |
| — | `issue_id` | Nuevo |
| — | `stage` | Nuevo: `extraction`\|`normalization`\|`mapping`\|`transformation`\|`validation`\|`export` |
| — | `status` | Nuevo: `open`\|`acknowledged`\|`resolved`\|`wont_fix` |
| — | `resolution` | Nuevo |
| — | `field_name` | Nuevo (opcional; antes implícito en `category`) |

Ningún campo actual se pierde sin equivalente.

`export_manifest.yaml`: su bloque `run` (`run_id`, `timestamp`, `mode`,
`connection`) es la forma ya existente del concepto `Execution` — no se
propone un fichero nuevo para `Execution`, solo se nombra formalmente el
concepto que ya representa.

`RunEvidenceContext` (`src/evidence/models.py`): ya construye su contexto
leyendo artefactos ya escritos, nunca la fuente — el CDM serializado (un
futuro `canonical_records.jsonl`, un objeto por línea) es exactamente el
tipo de artefacto que ese patrón espera consumir cuando se generalice, sin
romper el principio Evidence First.

Drills **no** se migra a esta forma en esta fase (fuera de alcance del
Blueprint) — la compatibilidad es conceptual, preparada para cuando el
Evidence Engine se generalice.

---

## 10. ADR creada o justificación de por qué no fue necesaria

Se creó la **ADR-014** — "Canonical Data Model: conjunto de entidades y
estrategia de identidad" (`docs/02-adr/ADR-014-canonical-data-model.md`).

**Justificación:** aunque el Blueprint y `data-processing-lifecycle.md` ya
esbozaban el CDM a nivel conceptual, ninguna ADR existente fijaba el
conjunto exacto de entidades, la estrategia de hash para `record_id`, ni la
descomposición de la confianza en 5 ejes independientes — son decisiones
estructurales nuevas, no cubiertas por ninguna decisión previa, y afectan
directamente a cómo deberá construirse cualquier Connector futuro. Cumple el
criterio del propio proceso de EMF: "toda decisión estructural requiere
ADR" (principio 10).

Índice actualizado: `docs/02-adr/README.md`, fila nueva para ADR-014,
próximo número libre actualizado a **ADR-015**.

---

## 11. Archivos creados

- `docs/01-architecture/canonical-data-model.md`
- `docs/02-adr/ADR-014-canonical-data-model.md`
- `reports/executions/2026-07-27/Informe-Canonical-Data-Model-EMF.md` (este informe)
- `reports/executions/2026-07-27/Informe-Canonical-Data-Model-EMF.txt` (mismo informe, texto plano)

## 12. Archivos modificados

- `docs/02-adr/README.md` (una fila nueva en la tabla de índice + número de
  próxima ADR actualizado de 014 a 015)

Ningún archivo de `src/`, `tests/`, `config/`, `sql/`, `main.py`,
`requirements.txt` ni `CLAUDE.md` fue tocado.

---

## 13. Riesgos y cuestiones abiertas

- **Diseño no validado empíricamente todavía**: sin un segundo Connector
  real, este modelo es arquitectura, no un hecho probado (mismo riesgo ya
  reconocido en ADR-011). El primer consumidor real (fase de roadmap
  "segundo Connector") puede forzar ajustes.
- **Las fusiones de entidad** (`Review`, `ValidationResult`,
  `MappingReference`, `Source`/`SourceLocation`) podrían resultar
  insuficientes si el primer caso documental real (Word/PDF) necesita más
  granularidad de la prevista — riesgo aceptado deliberadamente por el
  principio "No Abstraction Without a Real Consumer", no un defecto de
  diseño.
- **Identidad basada en `locator` para fuentes sin clave estable** es
  inherentemente frágil: un documento que se re-pagina cambia el
  `record_id` de sus registros. No se resuelve en el documento — es un
  límite del propio problema, no un defecto de la estrategia elegida.
- **`Provenance` embebido por campo** (no por registro) incrementa el
  tamaño de cada registro serializado — aceptado porque ya hay evidencia
  real (columna `Reference` de Drills) de que un registro combina valores
  de distinta procedencia.
- **Riesgo de confusión** entre este CDM y `src/knowledge_base/model.py` por
  vocabulario superficialmente similar — mitigado documentando
  explícitamente que son capas distintas con propósitos distintos.

**Decisiones aplazadas** (no resueltas ahora, documentadas para revisitar
cuando exista consumidor real):

- `Review` como entidad con historial de varias rondas.
- Separación `Issue` (definición estable) / observación por ejecución,
  análoga a `MappingDecision`/`MappingCoverageFinding`.
- Interfaz formal de `Connector` (`Protocol`/clase base).
- Algoritmo exacto de hash y longitud de `short_hash` para `record_id`.
- Reconciliación `data_type` detectado vs. tipo esperado por el futuro
  Enablon Template Registry.
- Persistencia del CDM más allá de una ejecución (futuro Knowledge
  Repository).

---

## 14. Resultado de validaciones

- [OK] El modelo no depende de SQL Server (`Provenance` es agnóstico de
  fuente; SQL es un `source_type` entre varios).
- [OK] Sin lógica específica de Drills o Moeve en la definición estructural
  (solo aparecen en ejemplos, marcados explícitamente como configuración de
  Plugin).
- [OK] No duplica el Mapping Model (ADR-013) ni el Template Contract /
  Enablon Template Registry.
- [OK] Las 5 entidades seleccionadas tienen consumidor real o futuro ya
  aprobado identificado explícitamente.
- [OK] Los ejemplos (SQL, Excel, PDF/Word, relación no resuelta) usan la
  misma estructura conceptual en los cuatro casos.
- [OK] Enlaces relativos de los documentos nuevos revisados uno a uno —
  todos resuelven a ficheros existentes.
- [OK] `git diff --check`: sin errores de formato.
- [OK] `git status --short`: solo los archivos declarados en § 11-12
  corresponden a esta tarea.

---

## 15. git status --short

```
?? docs/01-architecture/canonical-data-model.md
?? docs/02-adr/ADR-014-canonical-data-model.md
   docs/02-adr/README.md   (modificado)
?? reports/executions/2026-07-27/
```

(el resto de `docs/00-blueprint`, `01-architecture`, `02-adr`,
`03-engineering-standards`, `04-roadmap`, `05-sprint-reviews`,
`06-releases`, `07-developer-guide`, `08-user-guide` ya figuraban sin
trackear antes de esta tarea — no fueron creados ni modificados por ella)

## 16. git diff --stat

No aplica de forma útil: los ficheros de esta tarea son nuevos (no
trackeados en git), por lo que `git diff` no tiene una versión previa
contra la que comparar. Verificado en su lugar con `git diff --no-index
--check` contra cada fichero nuevo: sin errores de espacio en blanco (único
aviso: normalización de fin de línea LF→CRLF, propia de la configuración de
git en este entorno, no un problema de contenido).

---

## 17. Recomendación del siguiente paso

No implementar tipos Python todavía — esta tarea era, por encargo explícito,
solo diseño conceptual. El siguiente paso natural según el roadmap del
proyecto (`docs/04-roadmap/roadmap.md`) es la fase de "Segundo Connector":
implementar el primer Connector no-SQL (candidato recomendado: CSV, por ser
el más simple estructuralmente) que produzca `CanonicalRecord` reales según
esta especificación. Es el primer punto en el que este diseño se valida
empíricamente con un segundo caso real, tal como exige el principio "No
Abstraction Without a Real Consumer" antes de tocar el Core.

No se realizó commit de ningún cambio.
