# ADR-014 — Canonical Data Model: conjunto de entidades y estrategia de identidad

**Status:** Proposed (revisión arquitectónica en curso — ver
`docs/01-architecture/canonical-data-model.md` § 28, Historial de
revisión). No aprobar ni dar por definitiva ninguna decisión de esta ADR
hasta que la revisión del 2026-07-27 quede cerrada.

## Context

El Blueprint (§ 9) y [`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md)
(§ 2-3) ya fijan, a nivel de producto, que EMF necesita un Modelo de Datos
Canónico y esbozan su forma general (`RegistroNormalizado` con
`source_system`/`source_object`/`source_record_id`/`fields`/`provenance`).
Eso es suficiente para razonar sobre el pipeline en abstracto, pero no fija
las preguntas que un futuro Connector o Engine necesita resueltas de forma
concreta antes de escribir código: cuántas entidades distintas hacen falta,
si `provenance` vive por registro o por campo, cómo se genera un `record_id`
estable y reproducible sin caer en un hash universal ingenuo, y cómo se
evita comprimir certeza-de-extracción, certeza-de-mapeo, resultado-de-
validación y revisión humana en un único número ambiguo.

Estas preguntas se han resuelto en
[`canonical-data-model.md`](../01-architecture/canonical-data-model.md), a
partir de revisar tanto la documentación EMF ya aprobada como el código real
existente (`src/query/models.py`, `src/evidence/models.py`,
`src/export/prototype/drills/`, `src/knowledge_base/model.py`). Esta ADR
registra las decisiones estructurales de ese documento que no estaban ya
fijadas por ninguna ADR anterior — no repite el detalle completo, que vive
en el documento de arquitectura.

### Revisión del 2026-07-27

Una revisión arquitectónica formal (Architectural Design Review) encontró
diez problemas en la versión inicial de esta ADR y del documento de
arquitectura asociado, todos corregidos antes de que esta ADR se considere
lista para aprobación. Se listan aquí porque cambian directamente el
contenido de la sección Decision:

1. `record_id` colisionaba entre dos filas físicas distintas del origen
   que compartían `source_record_id` (el defecto de duplicados ya
   confirmado en Eventos/OPS, `CLAUDE.md`) — presentado entonces como
   comportamiento correcto. Es un error de diseño: dos ocurrencias físicas
   distintas nunca pueden compartir identidad técnica.
2. `CanonicalField.original_value` y `Provenance.original_value`
   duplicaban el mismo valor sin necesidad funcional real.
3. `CanonicalField` se presentaba, en una tabla, como una de las
   "entidades con identidad propia" mientras otra sección del mismo
   documento afirmaba que no tenía identidad global — contradicción
   directa sin resolver. Tampoco se resolvía si `Relationship` necesitaba
   identidad propia.
4. `CanonicalRecord.status` mezclaba en una única escala dos preguntas
   independientes: progreso por el pipeline y resultado final.
5. `Execution` llevaba un único `object_type` estructural, impidiendo
   representar una ejecución que produce varios objetos relacionados (caso
   real ya existente: Eventos produce 4 `MigrationObject` en una misma
   corrida).
6. `source_type` se presentaba de forma ambigua entre "vocabulario
   convención" y "lista cerrada", y no incluía explícitamente `api` como
   fuente.
7. La revisión humana no distinguía "quién revisó" y "cuándo" de forma
   explícita.
8. Se resolvía de forma implícita, sin evidencia suficiente, si
   `TransformationTrace` es un objeto único o una secuencia de pasos.
9. El documento y esta ADR se marcaban como "Approved Design" sin haber
   pasado por una revisión arquitectónica formal.
10. La recomendación de siguiente paso proponía saltar directamente a un
    segundo Connector, sin pasar antes por la Mapping Specification, el
    Enablon Template Contract, ni la implementación del Core.

Las diez correcciones están aplicadas en la versión actual de
`canonical-data-model.md` y se reflejan en la Decision de esta ADR.

## Decision

1. **Conjunto mínimo de entidades**, con una taxonomía explícita de tres
   niveles de identidad (no dos, como en la versión inicial):

   - **Identidad global, con colección propia**: `Execution`
     (`execution_id`), `CanonicalRecord` (`record_id`), `Issue`
     (`issue_id`).
   - **Identidad local, direccionada dentro de un padre, sin colección
     global propia**: `CanonicalField` — coordenada `(record_id,
     field_name)`; `Relationship` — `relationship_id` determinista con
     alcance limitado a su `source_record` (necesario para que un `Issue`
     señale una relación concreta cuando un registro tiene varias del
     mismo `relationship_type`).
   - **Sin identidad, valor embebido puro**: `Provenance`,
     `TransformationTrace`.

   Se descartan como entidades independientes `Source`/`SourceLocation`
   (fundidas en `Provenance` vía `source_type` + `locator`), `FieldValue`
   (los tres estados de un valor son atributos explícitos de
   `CanonicalField`), `MappingReference` (fundida en
   `TransformationTrace.rule_reference`) y `ValidationResult`/`Review`
   como entidades de primer nivel (atributos de `CanonicalField`/`Issue`
   — ver documento § 7 para la justificación completa).

2. **Identidad en cuatro conceptos, con un invariante duro de no
   colisión física**: `record_id` (identidad técnica — hash determinista
   de la *ocurrencia física*, nunca del `source_record_id` de negocio en
   solitario; **nunca compartido entre dos filas físicas distintas**),
   `source_record_id` (identidad del origen, valor verbatim, **puede
   repetirse** — es la señal de un duplicado), `functional_key` (identidad
   funcional, opcional, la rellena el Mapping Engine), `duplicate_group_key`
   (agrupación opcional de registros que comparten identidad declarada,
   sin fusionarlos). `Execution.execution_id` sigue siendo `uuid4`
   aleatorio, sin relación con `record_id`.

3. **`Provenance` localiza y explica, nunca duplica el valor**:
   `CanonicalField.original_value` es la única fuente de verdad del valor
   extraído. `Provenance` conserva `source_type` (vocabulario controlado
   pero **abierto** — un Connector nuevo declara su propio valor sin tocar
   el Core, incluye `api` junto a `sql_server`/`excel`/`csv`/`word`/`pdf`/
   `json`), `locator`, `extraction_method`, `confidence`, `captured_at`, y
   opcionalmente `evidence_excerpt` (un fragmento más amplio de contexto
   documental, para revisión humana — nunca sustituye a `original_value`).

4. **Estado del registro en dos conceptos separados**: `processing_stage`
   (`extracted → normalized → mapped → transformed → validated →
   exported` — progreso por el pipeline) y `disposition` (`pending →
   exportable | excluded | failed` — resultado/veredicto), sin máquina de
   estados formal ni transiciones especificadas en este documento.

5. **`Execution` no depende de un único `object_type`**: el `object_type`
   vive únicamente en `CanonicalRecord`. `Execution` incorpora, opcionales
   e informativos, `scope` (descripción declarada por configuración de
   proyecto) y `object_types` (conjunto de tipos efectivamente producidos).

6. **Revisión humana con trazabilidad mínima**: `review_required`,
   `review_status`, `review_note`, y — nuevos en esta revisión —
   `reviewed_by`/`reviewed_at`, ambos opcionales y presentes únicamente
   tras una revisión. Sigue sin existir una entidad `Review` con historial
   de varias rondas (decisión aplazada, ver documento § 25).

7. **Forma de `TransformationTrace` diferida**: esta ADR no fija si es un
   objeto único o una secuencia ordenada de pasos — se traslada
   explícitamente a una futura Mapping Specification.

Ver el documento de arquitectura para el detalle completo, los ejemplos
(SQL con registro individual y con duplicados, Excel, PDF/Word, relación
no resuelta) y la tabla de compatibilidad con `issues.jsonl`/
`export_manifest.yaml` ya existentes.

## Consequences

- Ningún Connector futuro (Excel, CSV, Word, PDF, JSON, API — Fases P3/P6
  del roadmap) puede diseñarse sin producir esta forma exacta de
  `CanonicalRecord`/`CanonicalField`, incluyendo el invariante de
  no-colisión de `record_id` entre ocurrencias físicas — es el contrato
  que hace posible que el resto del pipeline no conozca la fuente ni
  fusione duplicados del origen.
- `issues.jsonl` evoluciona (renombra/añade campos, ver documento § 24) en
  vez de mantenerse literal — es un cambio de forma, no de comportamiento
  observable, y solo se aplica cuando el Evidence Engine se generalice
  (Fase P2), nunca retroactivamente sobre Drills sin una decisión explícita
  de esa fase.
- El coste de la identidad en cuatro conceptos (en vez de un solo hash
  ingenuo) es más código de construcción de `record_id` — se acepta porque
  la alternativa (colisionar duplicados del origen en un solo registro
  canónico) oculta exactamente el tipo de defecto que `CLAUDE.md` ya pide
  no dar nunca por bueno sin desglosar.
- **Orden aprobado de próximos pasos** (corrige la recomendación inicial,
  que proponía saltar directamente a un segundo Connector):
  1. Aprobar este Canonical Data Model (cerrar esta revisión).
  2. Diseñar la Mapping Specification (resuelve, entre otras cosas, la
     forma exacta de `TransformationTrace`, decisión aplazada en el punto
     7).
  3. Diseñar el Enablon Template Contract (Enablon Template Registry,
     Blueprint § 11).
  4. Implementar el Framework Core (Sprint 4.1 — `ObjectRegistry`,
     `FrameworkContext`, etc.).
  5. Validar con consumidores reales (Engines genéricos operando sobre el
     CDM, incluso antes de un segundo Connector).
  6. Incorporar un segundo Connector cuando corresponda.

  Este orden refleja que el CDM, la Mapping Specification y el Template
  Contract son contratos de datos que preceden a la implementación del
  Core — implementar el Core o un Connector antes de fijar estos contratos
  arriesgaría tener que rehacerlos.
- Cualquier necesidad futura de más granularidad en `Review` o
  `TransformationTrace` (por ejemplo, múltiples rondas de revisión humana
  en la Fase P6, o pasos intermedios de mapeo en la Mapping Specification)
  requiere revisar esta ADR o crear una nueva, no una extensión silenciosa
  de los atributos actuales.

## Alternatives Rejected

- **Trece entidades separadas** (una por cada concepto evaluado:
  `Source`, `SourceLocation`, `FieldValue`, `MappingReference`,
  `ValidationResult`, `Review` como clases independientes). Rechazado por el
  principio 8 ("No Abstraction Without a Real Consumer") — ninguna de esas
  seis tiene hoy, ni en la Fase P3/P6 previsible, un consumidor que necesite
  su propia identidad, su propio ciclo de vida o su propia colección
  independiente separada de la entidad en la que se fusionó.
- **`record_id` = hash de `object_type + source_system + source_record_id`**
  (versión inicial de esta ADR, antes de la revisión). Rechazado: permite
  que dos filas físicas distintas del origen colisionen en el mismo
  `record_id` cuando comparten `source_record_id` — exactamente el defecto
  de duplicados ya confirmado en `CLAUDE.md` para Eventos/OPS, que quedaría
  oculto en vez de hecho visible.
- **`record_id` como UUID aleatorio**, igual que `execution_id`. Rechazado:
  impediría que el Comparison Engine (ya existente para Drills como
  `comparison.py`, a generalizar) reconozca "el mismo registro" entre dos
  ejecuciones sin depender de que el propio origen aporte una clave estable.
- **Duplicar el valor extraído en `Provenance.original_value`** además de
  en `CanonicalField.original_value` (versión inicial de esta ADR).
  Rechazado tras la revisión: no tiene una razón funcional real —
  `Provenance` y el valor siempre viajan juntos dentro del mismo
  `CanonicalField`, duplicar el valor solo añade una segunda fuente de
  verdad que puede desincronizarse.
- **Un único campo `status` para progreso y resultado** (versión inicial).
  Rechazado: mezcla dos preguntas independientes bajo la misma escala,
  obligando a tratar resultados (`exportable`, `excluded`, `failed`) como
  si fueran etapas del pipeline.
- **Un único `confidence_score` numérico de 0 a 100** cubriendo extracción,
  mapeo y validación a la vez (el patrón ya usado, con otro propósito, en
  `src/knowledge_base/model.py` para `Evidence.confidence_score`/
  `Relation.confidence_score`). Rechazado para el CDM: mezclaría "qué tan
  bien se extrajo el valor" con "qué tan bien se mapeó" y "si pasó
  validación", que son afirmaciones independientes y pueden discrepar.
- **Resolver ya la forma de `TransformationTrace`** (objeto único) sin
  haber diseñado la Mapping Specification. Rechazado tras la revisión: el
  catálogo de reglas ya confirmado incluye lookups dinámicos en 2 pasos
  que podrían necesitar más de un paso de traza — decidir esto sin ese
  diseño sería adivinar.
