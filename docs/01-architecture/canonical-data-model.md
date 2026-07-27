# Canonical Data Model — EMF

**Status:** Proposed — en revisión arquitectónica (ver
[ADR-014](../02-adr/ADR-014-canonical-data-model.md), también en estado
Proposed). Especificación conceptual completa, sin tipos Python
implementados todavía; pendiente de aprobación final tras la revisión
arquitectónica del 2026-07-27 (ver § 28 — Historial de revisión).

Este documento reemplaza, con precisión de diseño, el esbozo conceptual de
[`data-processing-lifecycle.md`](data-processing-lifecycle.md) § 2-3 (que
sigue vigente como resumen de alto nivel y no se modifica aquí). Antes de
leer este documento, familiarízate con la terminología del
[Blueprint](../00-blueprint/emf-blueprint-v1.0.md#terminología--no-confundir)
y con la disciplina de capas de
[`architecture-overview.md`](architecture-overview.md) — no se repiten aquí.

## 0. Hallazgos que informan este diseño

Antes de proponer una sola entidad se revisó: los tres documentos de
`docs/01-architecture/`, las siete ADR de producto (`docs/02-adr/007-013`),
los cuatro documentos de `docs/03-engineering-standards/`, el roadmap, y el
código real de `src/query/`, `src/evidence/`, `src/export/prototype/drills/`
y `src/knowledge_base/model.py`. Resumen de lo encontrado:

- **No existe hoy un tipo de "registro normalizado" real.** Confirmado
  explícitamente en `data-processing-lifecycle.md` § 6: el pipeline de
  Drills opera directamente sobre un `pandas.DataFrame` con las columnas
  crudas de la query SQL. Esta es exactamente la brecha que este documento
  cierra — no hay ningún código que migrar o generalizar para el registro
  en sí, solo el conjunto de conceptos ya usados alrededor de él.
- **`src/knowledge_base/model.py` es el precedente más rico del repositorio**
  para patrones de identidad y evidencia — pero es un modelo de un problema
  distinto (el "Migration Metadata Repository": cataloga el propio panorama
  de ETL/mapeos/queries a nivel de análisis, no los datos que fluyen en una
  ejecución de migración). De ahí se reutilizan **patrones**, no entidades:
  IDs deterministas (`make_*_id` + `short_hash`, nunca UUID aleatorio),
  vocabularios cerrados como clases con `ALL: frozenset` en vez de
  `enum.Enum`, `Evidence`/`Relation` con `confidence_score` 0-100 y estados
  categóricos separados de la evidencia, y la separación explícita entre
  una decisión estable (`MappingDecision`) y su observación en una corrida
  concreta (`MappingCoverageFinding`) — separación que este documento no
  reintroduce todavía para `Issue` (ver § 25) por no tener consumidor real,
  pero que queda documentada como extensión natural futura.
- **`src/export/prototype/drills/` ya materializa, sin nombrarlos así,**
  varios de los conceptos que este documento formaliza: `LookupResult`
  (`transformations.py`) es un `TransformationTrace` embrionario de un solo
  campo; `ReferenceResult.missing_components` es una traza de por qué un
  valor calculado no se pudo construir; `EntityResolution`/`EntityCatalog`
  (`mappings.py`) es un lookup dinámico con estado categórico
  (`resolved`/`do_not_migrate`/`unresolved`/`conflicting`); `issues.jsonl`
  (`pipeline.py`) ya tiene la forma de una lista de `Issue` por fila, con
  `run_id`, `row_key`, `category`, `severity`, `source_value`,
  `mapped_value`, `evidence_id`. Todo esto informa directamente el diseño
  del § 11 y § 15 — no se inventa forma nueva donde ya hay una probada con
  datos reales.
- **`src/query/models.py`** confirma el patrón ya vigente de separar
  "expresión sin validar" (`FilterExpression`) de "expresión ya validada y
  compilada" (`CompiledFilter`, con una propiedad `manifest_entry` que
  decide qué se serializa) — el mismo principio de "no serializar más de lo
  necesario" se aplica a `Issue`/`Provenance` en este documento.
- **`src/evidence/models.py`** confirma que el Evidence Engine construye su
  contexto (`RunEvidenceContext`) leyendo exclusivamente artefactos ya
  escritos (`validation_report`, `export_manifest`, `comparison_report`,
  `issues`) — nunca vuelve a tocar la fuente. El CDM debe poder serializarse
  de forma que ese patrón se mantenga sin cambios (ver § 19, § 24).
- **`config/exports/drills.yaml` + `config.py` (`FieldSpec`)** ya es, de
  facto, el Mapping Model / Template Contract de Drills. Este documento no
  lo duplica: `FieldSpec` (columna origen → columna destino, formato,
  `evidence_id` de la regla) pertenece a la capa de configuración de
  proyecto, nunca al CDM — ver § 3 y § 24.

Distinción explícita pedida por el encargo:

| Categoría | Conceptos |
|---|---|
| **Reutilizables tal cual (patrón, no código)** | IDs deterministas + `short_hash`/`slugify` (`knowledge_base/model.py`), vocabularios cerrados como clase+`frozenset` (todo el repo), `validate_*` devuelve lista de violaciones (ya un estándar, § 4 `engineering-standards.md`), escritura atómica de artefactos (`manifest.py`), estado categórico en vez de score único (`EntityResolution`, `LookupResult`, `MappingStatus`). |
| **Específicos de Drills (no entran en el Core)** | `DrillsExportConfig`/`FieldSpec` (Mapping Model concreto), `REFERENCE_PATTERN` y `build_reference` (regla de negocio de un objeto), `EntityCatalog` (catálogo de un proyecto concreto), cualquier columna `CS_*` con nombre literal. |
| **Futuros, no implementados todavía** | Todo lo que este documento define: `CanonicalRecord`, `CanonicalField`, `Provenance`, `TransformationTrace`, `Relationship`, `Execution`, `Issue` como tipos formales; el propio `Connector` como interfaz; el Enablon Template Registry. |

## 1. Propósito

Definir, con precisión suficiente para orientar una implementación futura
sin comprometerla todavía, la forma única en la que EMF representa
cualquier registro migrable — independientemente de si vino de SQL Server,
Excel, CSV, Word, PDF, JSON o una API — desde el momento en que un
Connector lo extrae hasta el momento en que el Export Engine lo convierte
en una fila de CSV de Enablon.

## 2. Alcance

- El conjunto de entidades conceptuales del Canonical Data Model (CDM) y su
  justificación individual.
- El modelo de identidad (qué identifica a una ejecución, a un registro, a
  un valor) y su estrategia de generación.
- El modelo de campo y valores (cómo conviven valor original, normalizado y
  transformado).
- El modelo de `provenance` común a cualquier tipo de fuente.
- El modelo de confianza, descompuesto en sus cinco dimensiones distintas.
- El modelo de revisión humana.
- El modelo de incidencias (`Issue`), compatible con `issues.jsonl`.
- El modelo de relaciones entre registros, incluyendo el caso de una
  relación cuyo destino no está resuelto todavía.
- Un ciclo de vida mínimo de estados para un registro.
- Un conjunto mínimo de tipos canónicos de dato.
- La forma conceptual de serialización (JSONL/depuración/evidencia).

## 3. Fuera de alcance

Explícitamente, el CDM **no** representa ni contiene:

- Credenciales ni cadenas de conexión (viven en `.env`, nunca en un dato
  que se serialice — ver `security-standards.md` § 4).
- Conexiones vivas, cursores SQL, sesiones HTTP, manejadores de fichero
  abiertos — el CDM es el resultado de una extracción ya completada, nunca
  un objeto con estado de I/O activo (ver ADR-010, No Hidden State).
- `DataFrame`s de pandas ni ninguna estructura propia de una librería de
  terceros — el CDM es una forma de datos, no una dependencia de
  implementación concreta.
- Plantillas CSV completas (columnas esperadas, orden, encoding) — eso es
  el Enablon Template Registry (Blueprint § 11), un contrato de **salida**,
  no de dato canónico intermedio.
- Reglas de mapeo completas (qué `ReglaEspecial`/`Parametro` aplica a qué
  campo) — eso es el Mapping Model (ADR-013), datos configurables
  separados. El CDM solo lleva la **traza** de que una regla se aplicó
  (`TransformationTrace.rule_reference`), nunca la definición de la regla.
- Configuración de cliente/proyecto (`config/*.yaml`, `.env`, rutas de
  Excel de mapeo) — capa superior, el CDM no la conoce.
- Lógica de extracción, de transformación o de exportación — el CDM es la
  forma del dato que esas lógicas producen/consumen, nunca el código que
  las ejecuta.
- Objetos específicos de Drills o de ningún módulo de Enablon concreto —
  ningún nombre de columna `CS_*`, ningún `object_id: "drills"` aparece en
  la definición estructural del modelo (sí puede aparecer en los ejemplos
  del § 20-23, marcados explícitamente como ejemplo de configuración).

## 4. Principios de diseño aplicados

Los 14 principios del Blueprint aplican todos; los más determinantes para
este documento en concreto:

- **No Abstraction Without a Real Consumer** (principio 8): cada entidad
  del § 7 tiene un consumidor real identificado (un Engine ya existente o
  una fase del roadmap ya aprobada) — ninguna se añadió "por si acaso".
- **Source Agnostic, Enablon Oriented** ([ADR-012](../02-adr/ADR-012-source-agnostic-enablon-oriented.md)):
  el modelo está sesgado hacia lo que el Export Engine necesitará producir,
  no es un formato neutral de propósito general.
- **Mappings as Data** ([ADR-013](../02-adr/ADR-013-mappings-as-data.md)):
  el CDM referencia mapeos (`rule_reference`), nunca los contiene.
- **Evidence First** ([ADR-008](../02-adr/ADR-008-evidence-first.md)): todo
  registro conserva su procedencia hasta el final del pipeline, sin
  excepción, incluso cuando es trivial (fuentes estructuradas).
- **No Hidden State** ([ADR-010](../02-adr/ADR-010-no-hidden-state.md)): un
  `CanonicalRecord` es un valor inmutable una vez construido en cada etapa
  — una etapa produce una nueva versión del registro, no muta la anterior
  en memoria compartida entre etapas.
- Restricción de complejidad del encargo: sin herencia, sin jerarquías de
  clase por tipo de fuente, sin event sourcing, sin grafo genérico, sin
  ontología, sin sistema universal de tipos. Cada vez que el encargo
  ofrecía una opción "genérica" y una "mínima", este documento justifica
  explícitamente por qué se optó por la mínima (ver § 7, § 11, § 13, § 14).

## 5. Terminología

Además de la terminología ya fijada en el Blueprint, este documento usa:

| Término | Significado |
|---|---|
| **CDM** | Canonical Data Model — el conjunto de entidades de este documento. |
| **Registro canónico** | Sinónimo de `CanonicalRecord` en prosa. |
| **Valor de campo** | El contenido de un `CanonicalField` en cualquiera de sus tres estados (original/normalizado/transformado) — no es una entidad `FieldValue` separada (ver § 11). |
| **Locator** | La ubicación de un valor dentro de su fuente (fila+columna, celda, página+bloque...) — parte de `Provenance`, nunca una entidad propia (ver § 12). |
| **Traza** | Registro de qué regla de mapeo/transformación produjo un valor y con qué resultado — `TransformationTrace`. |
| **Entidad embebida** | Una estructura de datos sin identidad ni ciclo de vida propios, que solo existe dentro de otra entidad (`Provenance` y `TransformationTrace` son entidades embebidas de `CanonicalField`). |
| **Identidad local** | Identidad direccionable dentro de un padre concreto (p. ej. `CanonicalField` por `(record_id, field_name)`, `Relationship` por `relationship_id` con alcance de su `source_record`), sin colección global propia — distinta de la identidad global de `Execution`/`CanonicalRecord`/`Issue` (§ 7). |
| **Ocurrencia física** | Una fila/celda/bloque concreto del origen, tal como existe físicamente en la fuente — la unidad que `record_id` identifica de forma única, incluso cuando dos ocurrencias físicas distintas declaran el mismo `source_record_id` (duplicado del origen, § 9). |

## 6. Modelo conceptual

```
Execution (execution_id, started_at, mode, status, scope?, object_types?)
  │
  │ produce N -- puede ser de varios object_type distintos en la misma Execution
  ▼
CanonicalRecord (record_id, object_type, source_record_id,
                 functional_key?, duplicate_group_key?, identity_basis,
                 source_reference, processing_stage, disposition, metadata)
  │
  ├── fields: { field_name -> CanonicalField }        -- direccionado por (record_id, field_name),
  │              │                                        sin identidad global propia
  │              ├── original_value / normalized_value / transformed_value
  │              ├── data_type (detectado)
  │              ├── provenance                (embebida, sin identidad -- ver § 12)
  │              ├── transformation_trace?      (embebida, sin identidad -- forma exacta
  │              │                               diferida a la Mapping Specification, ver § 25)
  │              └── review_required / review_status / review_note / reviewed_by? / reviewed_at?
  │
  ├── relationships: [ Relationship, ... ]   (embebidas, identidad LOCAL -- relationship_id
  │                                            con alcance de este record_id, ver § 16)
  │
  └── issues: consultables por record_id     (Issue vive como colección de nivel
                                               superior, con issue_id global -- no embebida, ver § 10)

Relationship (relationship_id, relationship_type, source_record, target_record?,
              target_reference?, direction, required, resolution_status)

Issue (issue_id, execution_id, stage, severity, code, message,
       record_id, field_name?, relationship_id?, rule_reference?, status,
       resolution?, source_value?, transformed_value?, blocks_export)
```

Ninguna flecha de este diagrama representa herencia — todas son
composición o referencia por identificador. `CanonicalField` no tiene
identidad global propia: se direcciona siempre como `(record_id,
field_name)`, nunca de forma aislada. `Relationship` tampoco tiene
identidad global: `relationship_id` es determinista pero con alcance
local a su `source_record` — ver § 7 para la taxonomía completa de
identidad por entidad.

## 7. Entidades seleccionadas

**Corrección de esta revisión**: la versión anterior de este documento
presentaba a las cinco entidades de la tabla siguiente bajo el título
"entidades con identidad propia", lo que contradecía directamente al § 6/§ 8
(`CanonicalField` sin identidad global) y dejaba sin resolver si
`Relationship` necesita o no una identidad. Se corrige aquí con una
taxonomía explícita de tres niveles de identidad — nunca dos documentos de
este mismo fichero pueden volver a decir cosas distintas sobre lo mismo:

| Nivel de identidad | Entidades | Característica |
|---|---|---|
| **Global, con colección propia consultable de forma independiente** | `Execution` (`execution_id`), `CanonicalRecord` (`record_id`), `Issue` (`issue_id`) | Se pueden listar/consultar sin pasar por ningún padre — cada una es, hoy o en un futuro artefacto, una colección de nivel superior (`export_manifest.yaml`, un futuro `canonical_records.jsonl`, `issues.jsonl`). |
| **Local, direccionada dentro de un padre, sin colección global propia** | `CanonicalField` — coordenada `(record_id, field_name)`; `Relationship` — `relationship_id` determinista con alcance limitado a su `source_record` (ver § 16) | Se necesita poder señalar "este campo exacto" o "esta relación exacta" (p. ej. desde un `Issue`, cuando un registro tiene varias relaciones del mismo `relationship_type`), pero nadie hoy necesita listar "todos los `CanonicalField` del sistema" o "todas las `Relationship` del sistema" como colección independiente — por eso no reciben una colección de nivel superior propia. |
| **Sin identidad, valor embebido puro** | `Provenance`, `TransformationTrace` | Ninguna existe fuera de un `CanonicalField` concreto; no se referencian nunca desde otro sitio, ni siquiera localmente. |

Tabla de entidades con su consumidor real (independientemente de su nivel
de identidad):

| Entidad | Qué representa | Consumidor real identificado |
|---|---|---|
| `Execution` | Una ejecución completa del pipeline EMF — puede producir varios `object_type` relacionados, no uno solo (§ 9.1). | Ya existe como concepto disperso (`run_id`, bloque `run`/`hashes` de `export_manifest.yaml`, `RunStats`) — se consolida en una sola entidad. |
| `CanonicalRecord` | Un registro migrable individual, en cualquier punto del pipeline desde la extracción hasta la exportación. | Mapping/Transformation/Validation/Export/Evidence Engine — todos operan sobre esta forma, nunca sobre SQL/Excel/PDF directamente (principio central del encargo). |
| `CanonicalField` | Un campo de un registro, con sus tres estados de valor y su procedencia. Identidad local, no global (ver tabla anterior). | Mismo conjunto de Engines; en particular el Evidence Engine, que hoy (Drills) ya necesita mostrar valor origen vs. valor final. |
| `Relationship` | Una relación tipada entre dos registros (o entre un registro y una referencia todavía no resuelta). Identidad local (`relationship_id`), no global (ver tabla anterior y § 16). | Generaliza el patrón ya implementado de Action Plans transversales (`CrossModuleActionPlanBuffer`, `config/modules.yaml`) sin codificar su nombre en el Core. Necesita `relationship_id` para que un `Issue` pueda señalar una relación concreta cuando un registro tiene más de una del mismo `relationship_type`. |
| `Issue` | Un problema detectado en cualquier etapa del pipeline, sobre un registro, un campo o una relación concreta. | Generaliza `issues.jsonl`, ya implementado y consumido por `src/evidence/workbook.py`. |

### Entidades evaluadas y descartadas (fusionadas), con justificación

| Candidata | Decisión | Justificación |
|---|---|---|
| `Source` | Fusionada en `Provenance.source_type`. | No hay hoy, ni en la Fase P3, un consumidor que necesite un catálogo de fuentes independiente del propio dato — la única pregunta que se hace sobre "de qué fuente vino" es "¿qué certeza tiene?", que ya resuelve `Provenance` (§ 12). Crear `Source` como entidad obligaría a inventar su ciclo de vida (¿se registra antes de leer? ¿vive más que la ejecución?) sin ningún caso real que lo exija. |
| `SourceLocation` | Fusionada en `Provenance.locator` (diccionario de atributos, no una clase por tipo de fuente). | El encargo mismo pide evaluar "un modelo común con `source_type`/`locator`/atributos estructurados" en vez de una clase por fuente — es exactamente lo que se adopta. Una jerarquía `SqlLocation`/`ExcelLocation`/`PdfLocation` sería la abstracción prematura que el principio 8 prohíbe con un solo Connector implementado. |
| `FieldValue` | No se crea; sus tres estados son atributos explícitos de `CanonicalField` (§ 11). | El encargo pregunta explícitamente si el valor debe ir dentro del campo, como secuencia de estados, o como valor actual + traza. Se elige "atributos explícitos" porque el número de estados es fijo y conocido (exactamente 3, ligados a 3 etapas fijas del pipeline) — una secuencia genérica de estados sería event sourcing sin necesidad, y el encargo lo prohíbe explícitamente. |
| `MappingReference` | Fusionada en `TransformationTrace.rule_reference`. | Una referencia a "qué entrada de mapeo se aplicó" solo tiene sentido junto al resultado de aplicarla — separarlas en dos entidades obligaría a mantener sincronizados dos objetos por cada valor transformado sin que nadie hoy necesite consultar la referencia de mapeo de forma aislada de su resultado. |
| `ValidationResult` | No se crea como entidad; se representa como `Issue` con `stage=validation` + `CanonicalRecord.disposition`. | `engineering-standards.md` § 4 ya fija que `validate_*` devuelve una lista de violaciones, nunca un objeto propio — una `ValidationResult` sería una envoltura redundante sobre "lista de `Issue`" + "el resultado del registro", ambos ya representados. |
| `Review` | No se crea como entidad; se representa como cinco atributos de `CanonicalField` (`review_required`/`review_status`/`review_note`/`reviewed_by`/`reviewed_at`, § 14). | Ningún flujo de trabajo actual ni de la Fase P6 (primer Connector documental) necesita más de una ronda de revisión por valor. Si en el futuro aparece un consumidor real que necesite historial de revisiones (varios revisores, versiones de la decisión), se promueve a entidad con su propia ADR — no antes (principio 8, ver § 25). |

Ninguna entidad se añadió "para completar la lista" del encargo — las tres
candidatas restantes (`CanonicalRecord`, `CanonicalField`, `Issue`) ya
tenían, además, una forma parcial confirmada en código real (§ 0), lo que
reduce el riesgo de diseñar a ciegas señalado como problema en
`extensibility-model.md` § 5.

## 8. Relaciones entre entidades

- `Execution` **1 —— N** `CanonicalRecord`: toda ejecución produce cero o
  más registros; un `CanonicalRecord` pertenece exactamente a una
  `Execution` (no se reutiliza entre ejecuciones — cada ejecución es
  independiente, ADR-010).
- `CanonicalRecord` **1 —— N** `CanonicalField`: por nombre de campo,
  nunca por posición (evita depender del orden de columnas de la fuente).
- `CanonicalField` **1 —— 1** `Provenance`: siempre presente, nunca
  opcional (Evidence First) — ver § 12.
- `CanonicalField` **0 —— 1 (o secuencia — forma exacta diferida)**
  `TransformationTrace`: ausente hasta que el Mapping/Transformation Engine
  procesa el campo; presente después, incluso si el resultado fue "no se
  pudo mapear" (la ausencia de traza nunca significa "no se intentó", sino
  "todavía no ha llegado a esa etapa" — ver § 17). Esta revisión **no**
  fija si es un objeto único o una secuencia ordenada de pasos — ver § 11.1
  y § 25 (decisión diferida a la futura Mapping Specification).
- `CanonicalRecord` **0 —— N** `Relationship` (como `source_record`):
  un registro puede originar varias relaciones (un Event con su
  Investigation y sus Action Plans, por ejemplo). Cada `Relationship`
  recibe un `relationship_id` local (con alcance de ese `source_record`,
  nunca global) precisamente para distinguir varias relaciones del mismo
  `relationship_type` sobre el mismo registro (§ 16).
- `Relationship.target_record` **0 —— 1** `CanonicalRecord`: puede estar
  vacío (relación no resuelta, § 16).
- `CanonicalRecord`/`CanonicalField`/`Relationship` **0 —— N** `Issue`, por
  referencia (`Issue.record_id`/`field_name`/`relationship_id`), nunca
  embebidas dentro del registro — ver § 10 para la justificación de no
  embeber.

## 9. Identidad

**Corrección de esta revisión**: la versión anterior definía `record_id`
como hash de `object_type + source_system + source_record_id`, lo que
hacía que dos filas físicas distintas del origen que comparten
`source_record_id` (el defecto de duplicados ya confirmado en `CLAUDE.md`
para Eventos/OPS) **colisionaran en el mismo `record_id`** — presentado
entonces como "correcto". Es un error: dos registros físicos distintos
nunca pueden compartir identidad técnica, o el CDM estaría fusionando en
uno solo lo que el origen trata como dos hechos distintos (dos filas, dos
`Provenance.locator` distintos, potencialmente dos valores distintos en
otros campos). Se corrige con un cuarto concepto (`duplicate_group_key`)
que separa "quién es cada registro" de "qué registros dicen tener la misma
identidad declarada por la fuente".

Cuatro identidades/claves distintas, que nunca se confunden entre sí:

| Concepto | Campo | Naturaleza | Puede repetirse entre `CanonicalRecord` distintos |
|---|---|---|---|
| Identidad técnica | `CanonicalRecord.record_id` | Hash determinista de la **ocurrencia física** | **Nunca** — invariante duro (ver más abajo) |
| Identidad del origen | `CanonicalRecord.source_record_id` | Valor verbatim declarado por la fuente | **Sí** — es precisamente la señal de un duplicado del origen |
| Identidad funcional | `CanonicalRecord.functional_key` (opcional) | Valor de negocio, la rellena el Mapping Engine | Depende del objeto |
| Agrupación de duplicados | `CanonicalRecord.duplicate_group_key` (opcional) | Normalmente = `source_record_id` normalizado (o `functional_key` si es más significativo) | Por diseño — agrupa registros que comparten identidad declarada |

`Execution.execution_id` (antes `run_id`, ver § 9.1) es una quinta
identidad, de naturaleza distinta a las cuatro anteriores: **aleatoria**
(`uuid4`), nunca determinista — representa "esta ejecución concreta en el
tiempo", no un dato de negocio (mismo principio ya fijado en
`engineering-standards.md` § 5).

**Invariante duro**: dos `CanonicalRecord` que representan filas físicas
distintas del origen **nunca** comparten `record_id`, incluso cuando
comparten `source_record_id`. La duplicación del origen se hace visible
mediante `duplicate_group_key` compartido + un `Issue` (`stage=validation`,
`code=DUPLICATE_SOURCE_RECORD_ID`), nunca fusionando silenciosamente dos
filas en un único registro canónico. Ver ejemplo completo en § 20.2.

### Estrategia de `record_id`

```
record_id = "record:" + slugify(object_type) + "." + slugify(source_system)
            + "." + short_hash(occurrence_key)
```

`occurrence_key` es lo que cambia respecto a la versión anterior: es un
valor que el Connector garantiza único **por fila física** dentro de su
`source_object`, no necesariamente el mismo que `source_record_id`
(el identificador de negocio, que sí puede repetirse). Según lo que la
fuente exponga:

1. **Clave física nativa** (`identity_basis: physical_key`): si la fuente
   tiene un identificador técnico distinto del identificador de negocio
   (p. ej. una columna `IDENTITY`/clave interna de SQL Server, o la
   dirección absoluta de una celda de Excel) que por construcción no se
   repite, se usa ese valor. Es el caso preferente.
2. **Clave de negocio + ordinal de extracción** (`identity_basis:
   source_key_with_ordinal`): si la fuente no expone una clave física
   propia, se combina `source_record_id` con la posición de esa fila
   dentro de esta extracción (p. ej. "es la 2ª fila con este
   `source_record_id` en esta ejecución"). Esto no fija todavía el
   algoritmo exacto de la posición — es una decisión de implementación,
   no de este documento — pero sí fija que el Connector debe garantizar
   que nunca asigna el mismo `occurrence_key` a dos filas físicas
   distintas leídas en la misma extracción.
3. **Derivada del `locator`** (`identity_basis: locator_derived`): cuando
   ni 1 ni 2 son aplicables (fuentes documentales sin clave estable, ver
   más abajo), se usa el `locator` (archivo+página+bloque).

Reutiliza literalmente el patrón de hashing ya implementado y probado en
`src/knowledge_base/model.py` (`slugify`, `short_hash`, familia
`make_*_id`) — no se inventa un segundo mecanismo de hashing en el mismo
repositorio. El algoritmo exacto de `short_hash` y la forma exacta del
ordinal de extracción se dejan como decisión de implementación (§ 25) —
lo que esta ADR fija es el invariante ("nunca colisiona entre filas
físicas distintas"), no el algoritmo.

Evaluación explícita de los riesgos que el encargo pide considerar antes de
aceptar un hash como solución:

- **Cambios del origen**: el hash se calcula sobre la *identidad física*
  (tipo de objeto + sistema origen + ocurrencia), nunca sobre el
  *contenido* del registro — que un valor se corrija en el origen entre
  dos ejecuciones no cambia `record_id`. Esto permite que el futuro
  Comparison Engine detecte "mismo registro, valor distinto" en vez de ver
  dos registros distintos.
- **Registros duplicados**: el defecto ya confirmado en `CLAUDE.md`
  (duplicados de `CS_HistoricalOriginID` en Eventos/OPS) produce, con esta
  estrategia corregida, **dos `record_id` distintos** (una ocurrencia física
  cada uno) que comparten el mismo `duplicate_group_key` — el CDM no funde
  la duplicación en un solo registro ni la oculta: la hace visible como un
  grupo detectable, y `Validation`/`Comparison` la reportan como `Issue`.
- **Claves incompletas**: cuando la fuente no aporta ninguna clave física
  ni de negocio estable (el caso típico de un párrafo de PDF/Word), el
  hash cae a `locator` (archivo+página+bloque, `identity_basis:
  locator_derived`). Este `record_id` es **menos estable** — un cambio en
  la paginación del documento origen lo cambia. Se documenta como
  limitación aceptada, no como problema resuelto (ver § 25/§ 26).
- **Reproducibilidad**: el hash nunca incluye `execution_id`, timestamp de
  extracción, ni ningún valor que cambie entre ejecuciones sobre el mismo
  origen — dos ejecuciones sobre el mismo dato producen siempre el mismo
  `record_id` para la misma ocurrencia física, precondición para que el
  Comparison Engine tenga sentido. Cuando `identity_basis:
  source_key_with_ordinal` depende de un orden de lectura que la fuente no
  garantiza explícitamente (sin `ORDER BY` estable, por ejemplo), la
  reproducibilidad de *ese* `record_id` concreto queda limitada por esa
  circunstancia del origen, no por el diseño del hash — riesgo documentado
  en § 26, no resuelto aquí.
- **Datos sensibles**: cuando `source_record_id` es en sí mismo un dato
  sensible (un identificador de persona, por ejemplo), el hash actúa además
  como seudonimización segura para cualquier artefacto que necesite listar
  claves sin exponer el valor real — mismo patrón ya implementado hoy en
  `comparison.py` (`sample_keys_hashed`, hash corto de claves para no volcar
  `CS_HistoricalOriginID` reales en un reporte de evidencia).

No se propone un hash único "universal" sin esta evaluación explícita,
como pide el encargo — la tabla anterior es la evaluación. El algoritmo
exacto (función de hash, longitud, forma exacta del ordinal) se deja como
decisión de implementación (§ 25); lo que esta sección fija de forma no
negociable es el invariante de no colisión entre ocurrencias físicas
distintas.

### 9.1 `Execution`: identificador y alcance (no depende de un único `object_type`)

`Execution.execution_id` sustituye a `run_id` como nombre formal del
concepto (mismo valor, mismo `uuid4` aleatorio — ver § 24 para la
correspondencia literal con el `run_id` ya usado en el código actual).

**Corrección de esta revisión**: la versión anterior incluía `object_type`
como campo estructural de `Execution` (`Execution (run_id, object_type,
...)`), lo que asumía implícitamente que una ejecución produce un único
tipo de objeto. Eso no es cierto en general — ya existe un precedente real
en el propio proyecto: `MigrationObject.processing_scope` en
`src/knowledge_base/model.py` distingue explícitamente objetos
`cross_module` (Action Plans, que se procesan cruzando varios módulos a la
vez), y el módulo Eventos produce cuatro `MigrationObject` distintos
(Events, Impacts, Investigations, PSM Forms) que conceptualmente forman
parte de una misma corrida de análisis. Obligar a `Execution` a declarar
un único `object_type` habría impedido representar exactamente ese caso.

Se corrige eliminando `object_type` de `Execution` — `object_type` vive
**únicamente** en `CanonicalRecord` (§ 10), donde siempre fue obligatorio
y correcto. `Execution` incorpora en su lugar dos campos, ambos opcionales
y meramente informativos (nunca usados por un Engine para decidir su
comportamiento — eso seguiría siendo una violación de Configuration over
Code):

- `scope: str | None` — descripción declarada por la configuración de
  proyecto/Plugin de qué abarca esta ejecución (p. ej. `"moeve.eventos"` o
  `"moeve.eventos+action_plans"`), nunca un literal reconocido por el
  Core.
- `object_types: tuple[str, ...] | None` — el conjunto de `object_type`
  efectivamente producidos por esta ejecución; puede poblarse
  progresivamente (no hace falta conocerlo por completo antes de empezar
  a extraer) o derivarse al final agregando los `CanonicalRecord.object_type`
  ya vistos.

Con esto, una `Execution` que produce Events, Investigations y Action
Plans en la misma corrida es una representación válida y directa, no un
caso límite forzado.

## 10. Modelo de registro

`CanonicalRecord`:

| Campo | Obligatorio | Quién lo genera | Estable entre ejecuciones | Alcance de unicidad |
|---|---|---|---|---|
| `record_id` | Sí | Connector, en el momento de la extracción | Sí (§ 9) | Global — **nunca compartido entre dos ocurrencias físicas distintas**, incluso si comparten `source_record_id` (§ 9) |
| `object_type` | Sí | Connector, a partir de configuración de Plugin (nunca hardcodeado) | Sí | — |
| `source_record_id` | No* | Connector | Sí, si la fuente lo es | No único — puede repetirse entre registros distintos (§ 9) |
| `functional_key` | No | Mapping Engine (se rellena más tarde en el pipeline) | Depende del objeto | — |
| `duplicate_group_key` | No | Connector (a partir de `source_record_id` normalizado) o Mapping Engine (a partir de `functional_key`, si es más significativo) | Sí, si la clave que lo origina lo es | No único por diseño — agrupa registros que comparten identidad declarada (§ 9) |
| `identity_basis` | Sí | Connector | Sí | — (`physical_key` \| `source_key_with_ordinal` \| `locator_derived`, ver § 9) |
| `source_reference` | Sí | Connector | Sí | — |
| `fields` | Sí (puede ser vacío solo en registros `failed`) | Cada Engine añade/actualiza los campos que le corresponden | No — cambia en cada etapa | Scope del registro |
| `relationships` | No | Mapping Engine (referencias) | Parcial (`target_record` puede resolverse más tarde) | Scope del registro |
| `processing_stage` | Sí | El Engine que actúa en cada etapa | No — es lo que avanza en cada etapa (§ 17) | Scope del registro |
| `disposition` | Sí | Validation/Export Engine (transición desde `pending`) | No | Scope del registro |
| `metadata` | No | Cualquier Engine, para información de depuración no promovida a campo de primera clase | No | Scope del registro |

`*` `source_record_id` es obligatorio salvo para fuentes documentales sin
clave estable, en cuyo caso `identity_basis=locator_derived` es obligatorio
en su lugar (§ 9) — nunca ambos ausentes.

**Decisión: `relationships` e `issues` no se embeben con su contenido
completo dentro del registro.** `relationships` almacena referencias
tipadas (no el `CanonicalRecord` destino completo — evita duplicar datos y
que una copia quede desactualizada); `issues` ni siquiera se almacena como
lista dentro del registro — es una colección de nivel superior consultable
por `record_id`, exactamente como ya ocurre hoy (`issues.jsonl` es un
artefacto separado del CSV de salida, no una columna del CSV). Esto evita
la duplicación de información en dos sitios que el encargo pide evitar
explícitamente en el modelo de campo, aplicada aquí también al registro.

`source_reference` es deliberadamente más ligero que `Provenance`: agrupa
identificación de *dónde viene el registro como conjunto* (sistema origen,
objeto origen, método de extracción), mientras que la procedencia detallada
de *cada valor* (que puede diferir campo a campo, como ya ocurre con
`Reference` en Drills, construido a partir de tres columnas distintas) vive
en `Provenance`, por campo (§ 12).

## 11. Modelo de campo y valores

`CanonicalField`:

| Atributo | Presente desde | Quién lo escribe |
|---|---|---|
| `field_name` | Extracción | Connector |
| `original_value` | Extracción | Connector — nunca se modifica después |
| `normalized_value` | Extracción (Connector aplica limpieza determinista) | Connector |
| `transformed_value` | Mapping/Transformation | Mapping/Transformation Engine |
| `data_type` (detectado) | Extracción | Connector |
| `provenance` | Extracción | Connector (embebida, § 12) |
| `transformation_trace` | Mapping/Transformation | Mapping/Transformation Engine (embebida; forma exacta —única o secuencia— diferida, § 11.1/§ 25) |
| `review_required` / `review_status` / `review_note` | Extracción (flag) / revisión humana (estado) | Connector inicia el flag; una persona (fuera de EMF) resuelve el estado — ver § 14 |
| `reviewed_by` / `reviewed_at` | Solo tras una revisión humana | La persona que revisa (o el proceso que registra la revisión); ausentes mientras `review_status != reviewed` — ver § 14 |

### 11.1 Por qué tres atributos explícitos y no una secuencia de estados

El encargo pregunta explícitamente si los valores deben ir dentro del
campo, como una secuencia de estados, o como un valor actual más una traza
separada. Se elige **valores explícitos dentro del campo** (no una lista
genérica de estados, no event sourcing) porque:

1. El número de estados es fijo y conocido de antemano: exactamente tres,
   correspondientes a tres etapas fijas del pipeline (extracción →
   normalización → mapeo/transformación). No hay un caso real, hoy ni en
   ninguna fase del roadmap, que necesite un número variable de estados
   intermedios.
2. Cada estado tiene un consumidor distinto y ya identificado:
   `original_value` lo necesita el Evidence Engine (mostrar "qué había en
   el origen"); `normalized_value` lo necesita el Mapping Engine (mapear
   sobre datos ya limpios, no sobre ruido de formato); `transformed_value`
   lo necesita el Export Engine (es lo que se escribe en el CSV).
3. Una secuencia de estados genérica sería la abstracción sin consumidor
   real que el principio 8 prohíbe, y coincide exactamente con "event
   sourcing" en la lista de complejidad a evitar del encargo.

`transformation_trace` (no `MappingReference` separado, ver § 7) contiene,
como mínimo: `rule_reference` (identificador + versión de la entrada de
mapeo aplicada, apuntando al Mapping Model de ADR-013 — nunca la regla en
sí), `engine_stage` (`mapping` | `transformation`), y `status`, con el
mismo vocabulario categórico ya confirmado en `transformations.py`
(`LookupResult.status`): `resolved` | `resolved_with_fallback` |
`default_applied` | `unresolved` | `conflicting`. Este vocabulario
generaliza literalmente el ya usado en
`resolve_typology`/`resolve_letter`/`resolve_entity` — no se inventa uno
nuevo.

**Decisión diferida (corrección de esta revisión)**: esta versión del
documento **no** resuelve si `transformation_trace` es un único objeto
(el resultado de la última regla aplicada) o una secuencia ordenada de
pasos (necesaria, por ejemplo, para un lookup dinámico en 2 pasos como el
ya confirmado en Safety Meetings/MOC — `CLAUDE.md`, catálogo de reglas).
Ambas opciones son compatibles con el resto de este documento (el
diagrama del § 6 ya lo marca como "0 —— 1 (o secuencia)"). La decisión se
traslada explícitamente a una futura **Mapping Specification** (§ 25),
que es quien conoce el catálogo completo de reglas multi-paso y puede
decidir con evidencia si un único objeto basta o si hace falta conservar
cada paso intermedio.

## 12. Provenance

**Corrección de esta revisión**: la versión anterior duplicaba el valor
extraído en dos sitios (`CanonicalField.original_value` y
`Provenance.original_value`), justificado como "autocontención para el
Evidence Engine". Se elimina esa duplicación: `CanonicalField.original_value`
es la **única** fuente de verdad del valor extraído — `Provenance` **localiza
y explica** la procedencia (dónde, cómo, con qué certeza), nunca vuelve a
guardar el valor en sí. Cualquier componente que necesite "el valor y su
procedencia juntos" los obtiene leyendo ambos del mismo `CanonicalField`
(que siempre viajan juntos, al ser atributos del mismo objeto) — no hace
falta una copia adicional para eso.

Modelo común, único para cualquier fuente — nunca una clase por tipo de
fuente (ver § 7, entidad `SourceLocation` descartada):

```
Provenance
├── source_type          -- vocabulario controlado y EXTENSIBLE, no una enumeración
│                            cerrada del Core (ver nota más abajo) -- p.ej. "sql_server" |
│                            "excel" | "csv" | "word" | "pdf" | "json" | "api"
├── locator               -- dict de atributos estructurados, forma según source_type (ver tabla)
├── extraction_method     -- p.ej. "sql_query" | "openpyxl_cell" | "native_text" | "ocr" |
│                            "json_path" | "http_request"
├── confidence            -- float 0.0-1.0 (§ 13)
├── captured_at           -- momento de la extracción, UTC
└── evidence_excerpt?     -- opcional -- ver justificación más abajo, NUNCA sustituye a
                             CanonicalField.original_value
```

`locator` es un diccionario plano de claves conocidas por convención, no
una clase — evita una jerarquía `SqlLocator`/`ExcelLocator`/`PdfLocator`
sin un segundo Connector real que la justifique (principio 8):

| `source_type` | Claves típicas de `locator` |
|---|---|
| `sql_server` | `connection`, `database`, `schema`, `table_or_view`, `column`, `record_key`, `query_reference` |
| `excel` | `file`, `sheet`, `cell_or_range` |
| `csv` | `file`, `row`, `column` |
| `word` | `file`, `section`, `paragraph_or_table`, `row`, `column` |
| `pdf` | `file`, `page`, `block_or_table`, `row`, `column` |
| `json` | `resource_or_endpoint` (ruta de fichero), `json_path`, `element_id` |
| `api` | `resource_or_endpoint` (URL/endpoint lógico, nunca con credenciales embebidas), `http_method`, `request_reference` (hash de los parámetros de la petición, nunca el valor crudo si es sensible), `json_path`, `element_id` |

**`source_type` es un vocabulario controlado pero abierto, no una
enumeración cerrada del Core.** Un Connector nuevo declara su propio valor
de `source_type` (y las claves de `locator` que le correspondan) sin
necesidad de modificar ninguna lista, `enum` ni validador dentro del Core
— igual que `relationship_type` (§ 16), es dato declarado por la capa que
añade el Connector, nunca una rama de código (`if source_type == "..."`)
dentro de un Engine (Configuration over Code, ADR-009; Extensibility by
Design, ADR-011). La tabla anterior es ilustrativa de los `source_type`
previstos hoy, no una lista cerrada que agotar antes de añadir uno nuevo.

`api` se distingue de `json` en que implica una llamada activa de solo
lectura a un recurso remoto (nunca una conexión que persista más allá de
esa llamada — ver § 3, "conexiones vivas" sigue fuera de alcance: lo que
el CDM conserva es el resultado ya capturado de la llamada, igual que con
cualquier otra fuente).

### `evidence_excerpt` — cuándo hace falta algo más que `original_value`

Para fuentes documentales (Word/PDF), el valor de un campo suele ser una
**interpretación** de un fragmento más amplio de texto crudo — por ejemplo,
`ResponsibleRole` puede ser el resultado de identificar el rol dentro de un
párrafo completo de varias frases (ver ejemplo § 22). `evidence_excerpt` es
ese fragmento más amplio, conservado en `Provenance` **solo cuando aporta
algo que `original_value` no aporta** — permite que un revisor humano
verifique la interpretación contra el contexto completo, no contra el
valor ya recortado. Para fuentes estructuradas (SQL/CSV/JSON/API),
`evidence_excerpt` no aplica casi nunca: el valor extraído ya *es* el
contenido íntegro de la celda/columna, sin interpretación intermedia, por
lo que duplicarlo en `evidence_excerpt` no aportaría nada — se deja
`None`.

Para fuentes estructuradas (SQL/CSV/JSON), la mayoría de estos campos son
triviales (`confidence=1.0`, `locator` sin página/sección, `evidence_excerpt`
ausente) — es el mismo modelo, no uno "simplificado", solo con valores por
defecto (ya fijado en `data-processing-lifecycle.md` § 3, este documento no
lo cambia).

## 13. Confianza

Cinco conceptos, nunca comprimidos en un único número:

| # | Concepto | Dónde vive | Naturaleza |
|---|---|---|---|
| 1 | Certeza del dato origen | Documentación del `source_type` (tabla de referencia, no un campo almacenado por registro) | Descriptiva — "SQL Server es un hecho, PDF es una interpretación" no cambia registro a registro |
| 2 | Confianza de la extracción | `Provenance.confidence` | Numérica 0.0-1.0 — el único valor continuo de todo el modelo |
| 3 | Confianza del mapeo | `TransformationTrace.status` | Categórica (§ 11.1) — nunca un número |
| 4 | Resultado de validación | `Issue` con `stage=validation` + `CanonicalRecord.disposition` (§ 17) | Presencia/ausencia de violaciones, no un score |
| 5 | Revisión humana | `CanonicalField.review_status` (§ 14) | Categórica, independiente de las cuatro anteriores |

Por qué no un único `confidence_score`: un valor extraído con confianza 1.0
(SQL) puede fallar mapeo (`unresolved`) o validación — comprimir ambos en
un número escondería cuál de los dos falló. Ver
[ADR-014](../02-adr/ADR-014-canonical-data-model.md) § Alternatives
Rejected para el rechazo explícito de reutilizar el patrón de
`confidence_score` 0-100 de `knowledge_base/model.py` para este propósito
distinto.

## 14. Revisión humana

No existe una entidad `Review` (§ 7). En su lugar, cinco atributos
embebidos en `CanonicalField` — la trazabilidad mínima pedida, sin llegar
a modelar un historial de varias rondas:

- `review_required: bool` — lo fija el Connector (o el Mapping Engine)
  cuando `Provenance.confidence` cae bajo un umbral declarado por el
  Connector, o cuando el método de extracción no puede autoevaluarse
  (mismo criterio ya fijado en `data-processing-lifecycle.md` § 3).
- `review_status: not_required | pending | reviewed` — el único estado
  mutable de este grupo.
- `review_note: str | None` — texto libre, opcional.
- `reviewed_by: str | None` — **opcional, presente únicamente después de
  una revisión** (`review_status=reviewed`); identifica a quien revisó de
  la forma más simple posible (un nombre o identificador de texto libre,
  no una referencia a un sistema de usuarios propio — EMF no tiene hoy
  autenticación/autorización, fuera de alcance, no se inventa una solo
  para este campo).
- `reviewed_at: datetime | None` — **opcional, presente únicamente
  después de una revisión**, mismo criterio que `reviewed_by`; ambos
  viajan juntos (uno sin el otro sería un dato de auditoría incompleto).

Se documenta como decisión aplazada (§ 25) promover esto a una entidad
`Review` con historial de varias rondas si la Fase P6 (primer Connector
documental) demuestra que una sola ronda no basta.

## 15. Issues

`Issue` (entidad de nivel superior, no embebida — § 10):

| Campo | Generaliza (issues.jsonl actual) | Notas |
|---|---|---|
| `issue_id` | — (no existía) | Determinista, alcance de una ejecución: `execution_id` + `record_id` + `field_name` + `stage` + `code` + secuencia |
| `execution_id` | `run_id` | Renombrado por consistencia con `Execution` (§ 7) |
| `stage` | — (no existía) | `extraction \| normalization \| mapping \| transformation \| validation \| export` — pedido explícitamente por el encargo |
| `severity` | `severity` | Mismo concepto, vocabulario a confirmar por Validation Engine |
| `code` | `category` | Renombrado — mismo propósito (categoría corta, máquina-legible) |
| `message` | `message` | Sin cambios |
| `record_id` | `row_key` | Renombrado para usar la identidad del § 9, no un identificador ad hoc de fila |
| `field_name` | — (implícito en `category`) | Ahora explícito y opcional (nulo si el problema es de todo el registro, p.ej. "0 columnas") |
| `relationship_id` | — (no existía) | Opcional — apunta a una `Relationship` local concreta (§ 16) cuando la incidencia es sobre una relación, no sobre un campo (ver ejemplo § 23) |
| `rule_reference` | `evidence_id` | Renombrado — apunta a la regla/spec/mapeo que originó o gobierna la incidencia, no necesariamente a "evidencia" en el sentido de `src/evidence/` |
| `source_value` / `transformed_value` | `source_value` / `mapped_value` | Copias denormalizadas por conveniencia para una vista de depuración plana — la fuente autoritativa sigue siendo `CanonicalField`, esto es una comodidad documentada, no una segunda fuente de verdad |
| `status` | — (no existía) | `open \| acknowledged \| resolved \| wont_fix` |
| `resolution` | — (no existía) | Texto libre opcional |
| `blocks_export` | `included_in_csv` | Renombrado e invertido semánticamente: expresa "esta incidencia es la razón por la que el registro no se exportó", no un booleano de resultado |

Ver § 24 para la tabla de compatibilidad completa y qué implica este
cambio de forma para `src/evidence/`.

## 16. Relaciones entre registros

`Relationship`:

```
Relationship
├── relationship_id         -- determinista, alcance LOCAL a este source_record
│                              (nunca una colección global independiente -- ver § 7/§ 9)
├── relationship_type      -- declarado por Plugin/configuración de proyecto,
│                             nunca un nombre de módulo hardcodeado en el Core
├── source_record          -- record_id
├── target_record           -- record_id | None (relación no resuelta)
├── target_reference        -- valor crudo que apunta al destino, conservado
│                              verbatim incluso si no se resuelve nunca
├── direction                -- "source_to_target" (fijo -- sin grafo bidireccional genérico)
├── required                 -- bool
└── resolution_status         -- resolved | pending | unresolved | conflicting | not_applicable
```

**`relationship_id` (corrección de esta revisión)**: la versión anterior no
resolvía si `Relationship` necesitaba identidad propia. La respuesta es sí,
pero **local**, no global: un mismo `CanonicalRecord` puede tener varias
relaciones del mismo `relationship_type` (p. ej. dos referencias a
entidades organizativas distintas), y un `Issue` necesita poder señalar
"esta relación exacta", no solo "alguna relación de este tipo en este
registro". `relationship_id` se calcula de forma determinista con alcance
de su `source_record` (p. ej. `relationship:{record_id}.{relationship_type}.
{short_hash(target_reference_o_target_record)}`) — nunca se registra en una
colección global ni se consulta de forma independiente fuera del contexto
de su registro (a diferencia de `Issue`, que sí tiene esa colección — ver
tabla de § 7).

`relationship_type` es siempre una cadena declarada por la capa de
configuración de proyecto/Plugin — el Core nunca compara contra literales
como `"action_plan_for_event"`. Ejemplos de uso (nunca definidos en el
Core): Action Plan asociado a un Event, Investigation asociada a un Event,
respuesta asociada a un checklist, referencia a entidad organizativa,
referencia a usuario — el mismo campo `relationship_type` cubre todos sin
una clase por tipo de relación (generaliza directamente el patrón ya
implementado de forma ad hoc en `CrossModuleActionPlanBuffer` del
Knowledge Engine legado, sin repetir su nombre en el Core).

**Relación no resuelta**: cuando el registro destino todavía no se ha
migrado o no se ha podido encontrar, `target_record` queda `None` y
`target_reference` conserva el valor original que lo identificaría (una
referencia histórica, un ID de negocio) — nunca se descarta ese valor
solo porque no se resolvió. `resolution_status=pending` (se espera
resolver más adelante) o `unresolved` (se intentó y no se encontró) según
corresponda; `conflicting` si hay más de un candidato. Si `required=true`
y la relación sigue sin resolver al llegar a validación, el Validation
Engine la reporta como `Issue` (`stage=validation`) — `Relationship` en sí
misma nunca decide si eso bloquea la exportación, solo documenta el hecho
(mismo principio que `validate_*` nunca lanza excepción por regla de
negocio).

## 17. Estados y ciclo de vida

**Corrección de esta revisión**: la versión anterior usaba un único campo
`status` que mezclaba dos preguntas distintas — "¿hasta dónde ha llegado
este registro en el pipeline?" y "¿qué va a pasar con él?" — bajo los
mismos valores (`exportable`/`excluded`/`failed` conviviendo con
`extracted`/`normalized`/... como si fueran la misma escala). Son dos
preguntas independientes: un registro puede estar en `processing_stage:
validated` y su `disposition` puede ser `exportable` o `excluded`, según
lo que decidió la validación — mezclarlas obligaba a "etapas" que en
realidad eran resultados (`exportable`, `excluded`, `failed` no son un
lugar del pipeline, son un veredicto). Se separan en dos conceptos
mínimos, sin construir una máquina de estados formal ni especificar aquí
sus transiciones válidas (eso es una decisión de implementación
posterior, no de este documento):

```
processing_stage:  extracted → normalized → mapped → transformed → validated → exported

disposition:       pending → exportable | excluded | failed
```

`processing_stage` responde **"¿hasta qué etapa del pipeline ha llegado
este registro?"** — representa la etapa más avanzada ya completada, nunca
una lista de etapas completadas (el detalle de qué ocurrió en cada una se
reconstruye a partir de los `Issue` con ese `record_id`, § 15, no de flags
adicionales). No todo registro recorre todas las etapas: una entidad
resuelta como "No migra" (ya confirmado como comportamiento real en
`mappings.resolve_entity` → `DO_NOT_MIGRATE`) puede detenerse en
`processing_stage: mapped` sin llegar nunca a `transformed`.

`disposition` responde **"¿qué va a pasar (o pasó) con este registro?"**
— independiente de en qué etapa de procesamiento se detuvo. Empieza en
`pending` para todo registro nuevo; se resuelve a `exportable` (pasó
validación y está listo para el Export Engine), `excluded` (una regla de
negocio decide no exportarlo — p. ej. `DO_NOT_MIGRATE`, o una relación
requerida sin resolver), o `failed` (un error de infraestructura, no una
regla de negocio — coherente con que las excepciones del Core se reservan
para eso). `disposition` puede resolverse antes de que `processing_stage`
llegue a `validated` (un registro puede excluirse tempranamente sin pasar
por transformación completa) — no hay una regla que obligue a esperar a
`processing_stage: validated` para fijar `disposition`.

No se especifica aquí ninguna máquina de estados formal (transiciones
permitidas, validación de que un salto de estado sea legal) — eso es una
decisión de implementación, deliberadamente fuera de este documento de
diseño conceptual.

## 18. Tipos canónicos

Conjunto mínimo, deliberadamente menor que el de cualquier fuente concreta:

`string`, `integer`, `decimal`, `boolean`, `date`, `datetime`,
`identifier`, `reference`, `list`, `object`, `null`.

Notas de por qué este conjunto y no más:

- `identifier` es distinto de `string` a propósito: un identificador nunca
  se normaliza como número aunque parezca uno (`"440"` vs `440.0` — el
  mismo problema que ya resuelve `to_historical_id` en
  `transformations.py`, generalizado aquí como tipo, no como función ad
  hoc por campo).
- `reference` marca que un valor *nombra* otro registro (una clave foránea
  en crudo), distinto de `Relationship` (§ 16), que es el enlace ya
  resuelto/en proceso de resolverse — `reference` es lo que hay en el
  campo antes de que EMF decida construir una `Relationship` a partir de
  él.
- No se modela `currency`, `email`, `percentage` ni ningún tipo semántico
  adicional — son responsabilidad de una regla de `validation` sobre un
  `decimal`/`string`, no de un tipo canónico nuevo (evita reproducir todos
  los tipos posibles de SQL/Excel/JSON/Enablon, como pide explícitamente
  el encargo).
- El CDM solo conserva `data_type` **detectado** (lo que el Connector
  observó). El tipo **esperado** por la plantilla de Enablon pertenece al
  futuro Enablon Template Registry, no al CDM (§ 3) — una discrepancia
  entre ambos se reporta como `Issue` (`stage=mapping` o `transformation`,
  `code=TYPE_CONVERSION_ERROR`), nunca como un campo adicional en
  `CanonicalField`.

## 19. Serialización conceptual

- **`CanonicalRecord`** (y sus `CanonicalField` embebidos): un objeto JSON
  por línea en un futuro `canonical_records.jsonl` (artefacto nuevo,
  Planned — no existe hoy), un registro por línea, mismo patrón de
  escritura atómica ya usado para `issues.jsonl` (`pipeline.py`).
  `relationships` se serializa como lista de referencias (`record_id`
  destino, nunca el registro completo anidado — evita una serialización
  recursiva sin límite).
- **`Issue`** sigue viviendo en su propio `issues.jsonl`, no embebido
  dentro de cada línea de `canonical_records.jsonl` — mismo razonamiento
  que en § 10 (no duplicar la misma información en dos sitios).
- **`Execution`** no necesita un artefacto nuevo: se serializa en el bloque
  `run`/cabecera ya existente de `export_manifest.yaml` — este documento no
  propone sustituir ese fichero, solo nombra formalmente el concepto que ya
  representa.

## 20. Ejemplo conceptual — fuente SQL

### 20.1 Registro individual

Fila real de la query de Simulacros (`ITP_SIMULACRO`), representada como
`CanonicalRecord` (valores ilustrativos, no un registro real del origen).
En este caso la fuente expone una clave física propia (`IDSimulacro`, una
columna `IDENTITY` que no se repite), así que `identity_basis: physical_key`:

```
CanonicalRecord
  record_id: record:drill.prevencion_itp.a1b2c3d4e5
  object_type: "Drill"                    -- ejemplo de configuración de Plugin, no del Core
  source_record_id: "440"
  duplicate_group_key: null                -- no hace falta: identity_basis=physical_key ya garantiza unicidad
  identity_basis: physical_key
  source_reference: { source_system: "prevencion_itp", source_object: "ITP_SIMULACRO",
                       extraction_method: "sql_query" }
  processing_stage: extracted
  disposition: pending

  fields.IDTipo:
    original_value: 3
    normalized_value: 3
    transformed_value: null              -- todavía no pasó por Mapping Engine
    data_type: integer
    provenance:
      source_type: sql_server
      locator: { connection: "moeve_prod_ro", table_or_view: "ITP_SIMULACRO",
                 column: "IDTipo", record_key: "IDSimulacro=440" }
      extraction_method: sql_query
      confidence: 1.0
    review_required: false
```

### 20.2 Ejemplo corregido — registros duplicados del origen

Caso real generalizado del defecto ya confirmado en `CLAUDE.md` (duplicados
de `CS_HistoricalOriginID` en Eventos/OPS): dos filas físicas de
`ITP_EVENTOS` declaran el mismo `IDEvento=10532`, y la tabla **no** tiene
una columna física independiente que las distinga
(`identity_basis: source_key_with_ordinal`). El invariante del § 9 exige
que, aun así, cada una reciba un `record_id` distinto:

```
CanonicalRecord  (primera ocurrencia física)
  record_id: record:event.prevencion_itp.7f1a2b3c4d      -- DISTINTO del segundo
  object_type: "Event"
  source_record_id: "10532"                                -- IGUAL en ambos -- es la señal del duplicado
  duplicate_group_key: event.prevencion_itp.10532          -- IGUAL en ambos -- agrupa sin fusionar
  identity_basis: source_key_with_ordinal
  source_reference: { source_system: "prevencion_itp", source_object: "ITP_EVENTOS",
                       extraction_method: "sql_query" }
  processing_stage: extracted
  disposition: pending

CanonicalRecord  (segunda ocurrencia física -- el duplicado)
  record_id: record:event.prevencion_itp.9c8d7e6f5a      -- DISTINTO del primero
  object_type: "Event"
  source_record_id: "10532"                                -- IGUAL que el anterior
  duplicate_group_key: event.prevencion_itp.10532          -- IGUAL que el anterior
  identity_basis: source_key_with_ordinal
  source_reference: { source_system: "prevencion_itp", source_object: "ITP_EVENTOS",
                       extraction_method: "sql_query" }
  processing_stage: extracted
  disposition: pending
```

`Issue` que el Validation Engine genera al detectar el grupo (una por cada
`record_id` del grupo, o agregada — la estrategia exacta de agregación es
decisión de implementación del futuro Validation Engine, no de este
documento):

```
Issue
  stage: validation
  severity: warning
  code: DUPLICATE_SOURCE_RECORD_ID
  message: "2 registros comparten duplicate_group_key=event.prevencion_itp.10532
            (source_record_id=10532) -- defecto sistémico ya confirmado en
            Eventos/OPS, ver CLAUDE.md."
  record_id: record:event.prevencion_itp.7f1a2b3c4d
  field_name: null
  status: open
  blocks_export: false                     -- decisión de negocio pendiente: no se
                                             -- excluye automáticamente por estar duplicado
```

Ningún `record_id` colisiona; la duplicación queda visible y trazable, no
oculta ni fusionada.

## 21. Ejemplo conceptual — fuente Excel

Fila hipotética de un futuro Excel Connector usado como **fuente de
registros** (distinto del uso actual de Excel solo como fuente de mapeos,
ver Blueprint § 8) — por ejemplo, un listado de asistentes a una reunión
mantenido en un Excel de control, no en SQL:

```
CanonicalRecord
  record_id: record:meeting_attendee.excel_control_asistencia.f9e8d7c6b5
  object_type: "MeetingAttendee"           -- ejemplo de configuración de Plugin
  source_record_id: null
  duplicate_group_key: null
  identity_basis: locator_derived           -- Excel de control sin columna de ID estable
  source_reference: { source_system: "excel_control_asistencia",
                       source_object: "Asistentes_2024.xlsx", extraction_method: "openpyxl_cell" }
  processing_stage: extracted
  disposition: pending

  fields.EmployeeName:
    original_value: "García, Ana"
    normalized_value: "García, Ana"
    data_type: string
    provenance:
      source_type: excel
      locator: { file: "Asistentes_2024.xlsx", sheet: "Marzo", cell_or_range: "B14" }
      extraction_method: openpyxl_cell
      confidence: 1.0
    review_required: false

  fields.HoursAttended:
    original_value: "=SUM(C14:C16)"          -- celda con fórmula, no valor literal
    normalized_value: 4.5
    data_type: decimal
    provenance:
      source_type: excel
      locator: { file: "Asistentes_2024.xlsx", sheet: "Marzo", cell_or_range: "D14" }
      extraction_method: openpyxl_cell
      confidence: 0.8                        -- menor: depende de que la fórmula se evaluara bien
    review_required: false
```

## 22. Ejemplo conceptual — fuente PDF/Word

Valor extraído de un procedimiento de emergencia en PDF (fuente
documental, Fase P6 — no implementada, solo diseño):

```
CanonicalRecord
  record_id: record:emergency_procedure.pdf_procedimientos.3c4d5e6f70
  object_type: "EmergencyProcedure"         -- ejemplo de configuración de Plugin
  source_record_id: null
  duplicate_group_key: null
  identity_basis: locator_derived
  source_reference: { source_system: "pdf_procedimientos",
                       source_object: "PR-EMG-014.pdf", extraction_method: "native_text" }
  processing_stage: extracted
  disposition: pending

  fields.ResponsibleRole:
    original_value: "El Jefe de Turno, o en su ausencia el Responsable de Planta"   -- ÚNICA fuente de verdad del valor
    normalized_value: "Jefe de Turno / Responsable de Planta"
    data_type: string
    provenance:
      source_type: pdf
      locator: { file: "PR-EMG-014.pdf", page: 4, block_or_table: "párrafo 2" }
      extraction_method: native_text
      confidence: 0.55                       -- extracción de texto libre, no de tabla estructurada
      evidence_excerpt: "En caso de emergencia, la coordinación inicial corresponde
                          al Jefe de Turno, o en su ausencia el Responsable de Planta,
                          quien activará el protocolo PR-EMG-014 sección 3."
                          -- párrafo completo, más amplio que original_value -- permite
                          -- a un revisor humano verificar la interpretación en contexto,
                          -- SIN duplicar el valor del campo (§ 12)
    review_required: true
    review_status: pending
    reviewed_by: null                          -- ausente: todavía no se ha revisado
    reviewed_at: null
```

Una `Issue` asociada a este mismo campo, `stage=extraction`:

```
Issue
  execution_id: <execution_id de esta ejecución>
  stage: extraction
  severity: review_required
  code: LOW_CONFIDENCE_TEXT_EXTRACTION
  message: "Texto extraído de párrafo libre, no de tabla -- confianza por debajo del umbral (0.55 < 0.70)."
  record_id: record:emergency_procedure.pdf_procedimientos.3c4d5e6f70
  field_name: ResponsibleRole
  status: open
  blocks_export: false
```

## 23. Ejemplo conceptual — relación no resuelta

Un ActionPlan (objeto de ejemplo, configuración de Plugin, no concepto del
Core) que referencia a su Event de origen, cuando el Event todavía no ha
sido migrado en esta ejecución:

```
Relationship
  relationship_id: relationship:action_plan.gct_acciones.9a8b7c6d5e.action_plan_for_object.4e5f6a7b8c
  relationship_type: "action_plan_for_object"   -- declarado por config de proyecto
  source_record: record:action_plan.gct_acciones.9a8b7c6d5e
  target_record: null                            -- el Event aún no tiene record_id asignado
  target_reference: "EVT-2019-00231"             -- referencia histórica cruda, conservada verbatim
  direction: source_to_target
  required: true
  resolution_status: pending
```

`Issue` que resulta de validar esta relación, si al llegar a la etapa de
validación sigue sin resolverse — apunta al `relationship_id` concreto, no
solo al registro, porque este `ActionPlan` podría tener más de una
relación pendiente al mismo tiempo:

```
Issue
  stage: validation
  severity: blocking
  code: UNRESOLVED_REQUIRED_RELATIONSHIP
  message: "ActionPlan referencia a EVT-2019-00231, que no se ha resuelto a ningún record_id en esta ejecución."
  record_id: record:action_plan.gct_acciones.9a8b7c6d5e
  field_name: null                                -- problema de la relación, no de un campo
  relationship_id: relationship:action_plan.gct_acciones.9a8b7c6d5e.action_plan_for_object.4e5f6a7b8c
  rule_reference: "relationship:action_plan_for_object"
  status: open
  blocks_export: true
```

## 24. Compatibilidad con componentes existentes

| Componente existente | Relación con el CDM |
|---|---|
| `issues.jsonl` (`src/export/prototype/drills/pipeline.py`) | Ancestro directo de `Issue` (§ 15) — tabla de renombrados arriba. Ningún campo actual se elimina sin equivalente; `stage`, `issue_id`, `status`, `resolution` son adiciones puras. Drills no se migra a esta forma en esta fase (Blueprint § 4, fuera de alcance) — la compatibilidad es conceptual, para cuando el Evidence Engine se generalice (Fase P2). |
| `export_manifest.yaml` (`manifest.py`) | Su bloque `run` (`run_id`, `timestamp`, `mode`, `connection`) es la forma ya existente de `Execution` (`run_id` → `execution_id`, § 9.1) — este documento no propone un fichero nuevo para `Execution`, solo nombra el concepto. Sus campos `migration_object`/`module` (hoy un único valor por ejecución, específico de Drills) son la instanciación concreta, para un caso de un solo objeto, del `scope`/`object_types` opcionales de `Execution` (§ 9.1) — no se contradicen, el manifiesto actual es el caso particular donde `object_types` tiene un único elemento. |
| `RunStats` (`manifest.py`) | Acumulador de contadores planos, específico de Drills. El CDM no lo sustituye — un futuro Evidence Engine genérico podría derivarlo agregando `CanonicalRecord.processing_stage`/`disposition`/`Issue` de una ejecución, pero eso es una capacidad futura (Fase P2), no una migración de este documento. |
| `RunEvidenceContext` (`src/evidence/models.py`) | Ya construye su contexto leyendo artefactos ya escritos, nunca la fuente — el CDM serializado (§ 19) es exactamente el tipo de artefacto que este patrón espera consumir cuando se generalice. |
| `LookupResult`/`EntityResolution`/`ReferenceResult` (`transformations.py`, `mappings.py`) | Ancestros directos de `TransformationTrace.status` (§ 11.1) — mismo vocabulario categórico, generalizado. |
| `FieldSpec`/`DrillsExportConfig` (`config.py`) | Mapping Model / Template Contract de un objeto concreto — el CDM lo referencia (`rule_reference`) pero nunca lo contiene ni lo duplica (§ 3). |
| `src/knowledge_base/model.py` (`Evidence`, `Relation`, `MappingDecision`...) | Capa distinta (Migration Metadata Repository, análisis del panorama de ETL) — no se fusiona con el CDM (que modela datos en tránsito por el pipeline de una ejecución). Se reutilizan patrones (IDs deterministas, vocabularios categóricos), nunca las entidades en sí — ver § 0. |
| `CompiledFilter`/`FilterExpression` (`src/query/models.py`) | Ortogonal al CDM — el Query Engine filtra qué se extrae, antes de que exista ningún `CanonicalRecord`. Sin relación estructural directa. |

## 25. Decisiones aplazadas

- **Forma exacta de `TransformationTrace`** (objeto único vs. secuencia
  ordenada de pasos, § 11.1): diferida explícitamente a una futura
  **Mapping Specification** — el catálogo de reglas ya confirmado en
  `CLAUDE.md` incluye lookups dinámicos en 2 pasos (Safety Meetings/MOC)
  que podrían necesitar conservar cada paso, pero decidirlo aquí sin haber
  diseñado todavía la Mapping Specification sería adivinar.
- **Algoritmo exacto del ordinal de extracción** para `identity_basis:
  source_key_with_ordinal` (§ 9): qué garantiza exactamente que dos filas
  con el mismo `source_record_id` reciban ordinales distintos y estables
  dentro de una misma ejecución (orden de lectura, número de fila del
  cursor, otro criterio) es una decisión de implementación del Connector
  SQL, no de este documento — lo que este documento fija es el invariante
  ("nunca colisiona"), no el mecanismo.
- **`Review` como entidad con historial de varias rondas**: aplazado hasta
  que la Fase P6 (primer Connector documental) demuestre que una sola
  ronda de revisión por campo no es suficiente.
- **Separación `Issue` (definición estable) / observación por ejecución**,
  análoga a `MappingDecision`/`MappingCoverageFinding` en
  `knowledge_base/model.py`: aplazada — no hay hoy un consumidor que
  necesite rastrear "esta incidencia es recurrente en las últimas N
  ejecuciones", solo detectarla en la ejecución actual.
- **Interfaz formal de `Connector`** (`Protocol`/clase base) que se
  comprometa a producir `CanonicalRecord`: aplazada hasta el segundo
  Connector real (Fase P3), ya documentado como pospuesto en
  `extensibility-model.md` § 5 — este documento no lo adelanta.
- **Algoritmo exacto de hash y longitud de `short_hash`** para
  `record_id`: se recomienda reutilizar la función ya implementada en
  `src/knowledge_base/model.py` (SHA-1 truncado a 10 caracteres) en vez de
  definir una segunda convención de hashing en el mismo repositorio, pero
  la elección final es de implementación, no de esta ADR.
- **Reconciliación `data_type` detectado vs. tipo esperado por el Enablon
  Template Registry**: aplazada hasta que el Registry exista como
  componente (Blueprint § 11, Planned).
- **Persistencia del CDM más allá de una ejecución** (un futuro Knowledge
  Repository que conserve `CanonicalRecord` entre corridas): mismo estado
  que la Fase 5 legada ("Repository") — sin fase EMF asignada todavía.

## 26. Riesgos

- **Diseño no validado empíricamente todavía**: sin un segundo Connector
  real, este modelo es arquitectura, no un hecho probado — mismo riesgo ya
  reconocido explícitamente en [ADR-011](../02-adr/ADR-011-extensibility-by-design.md).
  El primer consumidor real (Fase P3) puede forzar ajustes a este
  documento; se tratarán como una ADR nueva si cambian algo estructural
  (principio 10), no como una corrección silenciosa.
- **Las fusiones de entidad (§ 7) podrían resultar insuficientes**: si el
  primer caso documental real (Fase P6) necesita más granularidad de la
  que ofrecen los atributos de `CanonicalField` para revisión/validación,
  habría que promover `Review` o `ValidationResult` a entidades — riesgo
  aceptado deliberadamente por el principio 8, no un defecto de diseño.
- **Identidad basada en `locator` para fuentes sin clave estable es
  inherentemente frágil** (§ 9): un documento que se re-pagina cambia el
  `record_id` de sus registros. No se resuelve en este documento — se
  documenta como limitación conocida del propio problema (una fuente sin
  clave estable no tiene una identidad perfectamente estable posible,
  cualquier estrategia tendría este límite).
- **`identity_basis: source_key_with_ordinal` depende de que la fuente
  ofrezca un orden de lectura estable entre ejecuciones** (§ 9): si una
  query SQL sin `ORDER BY` explícito no garantiza el mismo orden de filas
  en dos ejecuciones distintas, el `record_id` de un registro duplicado
  (mismo `source_record_id`, distinto ordinal) podría no ser reproducible
  entre ejecuciones — aunque sí seguiría cumpliendo el invariante de no
  colisionar *dentro* de una misma ejecución. Riesgo documentado, no
  resuelto (la solución robusta, forzar un `ORDER BY` determinista en cada
  Connector, es una decisión de implementación, no de este documento).
- **`Provenance` embebido por campo, no por registro, incrementa el
  tamaño de cada registro serializado** frente a una procedencia única por
  fila. Se acepta porque ya hay evidencia real (columna `Reference` de
  Drills, compuesta de tres campos de distinta procedencia lógica) de que
  un registro puede combinar valores con procedencias distintas dentro de
  sí mismo.
- **Confusión potencial entre este CDM y `src/knowledge_base/model.py`**
  por su vocabulario superficialmente similar (ambos usan IDs
  deterministas y estados categóricos) — mitigado documentando
  explícitamente en § 0 y § 24 que son capas distintas con propósitos
  distintos; el riesgo real es que una implementación futura los mezcle
  por conveniencia, algo que este documento prohíbe explícitamente.

## 27. Criterios de aceptación

Este diseño se considera completo si:

1. Un `CanonicalRecord` puede representar, sin cambiar su forma
   estructural, una fila de SQL Server, una fila de Excel y un valor
   extraído de PDF/Word — demostrado en § 20-22 con la misma estructura de
   campos en los tres casos.
2. Ninguna definición estructural de este documento (§ 6-19) menciona un
   nombre de tabla, un módulo de Enablon, "Drills" o "Moeve" — solo
   aparecen en ejemplos (§ 20-23), marcados explícitamente como
   configuración de Plugin.
3. El modelo no duplica el Mapping Model (ADR-013) ni el futuro Template
   Contract/Enablon Template Registry (Blueprint § 11) — verificado en § 3
   y en que ningún ejemplo incluye una definición de columnas de plantilla.
4. `Issue` es conceptualmente compatible con `issues.jsonl` sin romper
   ningún campo que `src/evidence/workbook.py` ya consuma hoy — verificado
   en la tabla de § 24 (todo campo actual tiene equivalente nombrado).
5. Cada entidad seleccionada (§ 7) tiene un consumidor real o futuro ya
   aprobado identificado explícitamente — sin excepciones.
6. Todo campo obligatorio de `CanonicalRecord`/`CanonicalField` (§ 10-11)
   declara quién lo genera y en qué etapa del pipeline aparece.
7. Los cinco conceptos de confianza (§ 13) están representados en campos
   distintos, nunca combinados en un único número.
8. Dos `CanonicalRecord` que representan filas físicas distintas del
   origen nunca comparten `record_id`, incluso si comparten
   `source_record_id` — demostrado en § 20.2.
9. `processing_stage` y `disposition` están separados en dos campos
   independientes, sin mezclar progreso de pipeline con resultado final
   (§ 17), y sin definir una máquina de estados formal.
10. Ninguna entidad de este documento se presenta con un nivel de
    identidad distinto en dos sitios (§ 7 y § 9 usan la misma taxonomía de
    tres niveles de forma consistente en todo el documento).

## 28. Historial de revisión

| Fecha | Cambio | Origen |
|---|---|---|
| 2026-07-27 | Versión inicial (Status: Approved Design). | Diseño inicial del CDM. |
| 2026-07-27 | Revisión arquitectónica — 10 correcciones: (1) `record_id` ya no colisiona entre ocurrencias físicas distintas, se añade `duplicate_group_key`; (2) se elimina la duplicación de `original_value` entre `CanonicalField` y `Provenance`, se añade `evidence_excerpt` opcional; (3) se corrige la contradicción de identidad de `CanonicalField` (local, no global) y se resuelve `Relationship.relationship_id` (local); (4) `status` único se separa en `processing_stage` + `disposition`; (5) `Execution` deja de depender de un único `object_type`, se añaden `scope`/`object_types`; (6) `source_type` se declara vocabulario abierto y se añade `api`; (7) revisión humana gana `reviewed_by`/`reviewed_at`; (8) forma de `TransformationTrace` (única vs. secuencia) se declara decisión diferida a la Mapping Specification; (9) `Status` del documento y de ADR-014 pasan a `Proposed`; (10) se corrige la recomendación de siguiente paso (ver ADR-014, Consequences). | Architectural Design Review — Canonical Data Model (revisor externo al equipo de diseño inicial). |
