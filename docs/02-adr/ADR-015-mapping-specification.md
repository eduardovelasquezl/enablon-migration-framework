# ADR-015 — Mapping Specification: modelo de reglas, conflictos y TransformationTrace

**Status:** Proposed

## Context

[ADR-013](ADR-013-mappings-as-data.md) ya fija, como principio de
producto, que los mapeos son datos configurables y versionables, nunca
lógica embebida — y enumera, a alto nivel, qué debe conservar como mínimo
cada entrada de mapeo (proyecto, módulo, objeto, fuente, campo origen,
campo destino, tipo de regla, valores, obligatoriedad, prioridad, default,
observaciones, versión, estado de validación). No fija, sin embargo, el
modelo exacto: cuántos `rule_type` distintos hacen falta, cómo se detecta
y resuelve un conflicto entre dos reglas para el mismo campo, dónde está
la frontera entre lo declarativo y lo que exige código, cómo se versiona
una regla individual frente al conjunto completo, ni — la pregunta que
[ADR-014](ADR-014-canonical-data-model.md) dejó explícitamente abierta —
si `TransformationTrace` debe ser un objeto único o una secuencia de
pasos.

Estas preguntas se resuelven en
[`mapping-specification.md`](../01-architecture/mapping-specification.md),
a partir de revisar el catálogo de reglas ya confirmado con datos reales
(`config/validation_rules.yaml`, `CLAUDE.md`) y el código real existente
(`src/etl/transformations.py` — `RULE_REGISTRY`/`resolve_rule`;
`src/etl/mapping_resolver.py`/`excel_reader.py` — los dos patrones de hoja
Excel de 8 y 5 columnas ya confirmados con ETL reales;
`config/exports/drills.yaml` — el patrón `reference_data` ya separado de
`fields`). Esta ADR registra las decisiones estructurales de ese documento
que no estaban ya fijadas por ADR-013 — no repite el detalle completo, que
vive en el documento de arquitectura.

## Decision

1. **Doce `rule_type`** (`direct`, `constant`, `default`, `value_map`,
   `lookup`, `conditional`, `concatenate`, `type_conversion`,
   `date_conversion`, `reference`, `exclusion`, `registered_transform`),
   cada uno generalizando evidencia real ya confirmada — se descartan como
   tipos independientes `boolorigin`/`replaceinreference`/`lookup_simple`
   (fundidos en `value_map`, sin comportamiento distinguible entre sí con
   la evidencia disponible) y el "fan-out" de `cloneorigin` (se representa
   como varias reglas `direct`, una por campo destino, nunca un tipo
   nuevo).

2. **Frontera declarativo/código fijada en `registered_transform`**:
   cualquier comportamiento que no se pueda expresar con seguridad como
   dato (el caso confirmado es `titlefix`, sin motor visible en ningún
   Excel/VBA auditado) se referencia por nombre contra un catálogo de
   funciones ya implementadas y revisadas — nunca código nuevo dentro de
   una celda. Generaliza literalmente el patrón `RULE_REGISTRY`/
   `resolve_rule` ya implementado.

3. **Conflictos nunca se resuelven por orden de aparición**: `priority`
   explícita entre reglas del mismo campo destino; misma prioridad con
   condiciones potencialmente simultáneas es error de validación
   (`OVERLAPPING_RULES`); una exclusión de alcance `record` tiene
   precedencia fija y documentada sobre cualquier transformación de campo
   para ese registro; un lookup/value map con más de un resultado posible
   nunca elige uno automáticamente (`status=conflicting`).

4. **Identidad en cuatro conceptos**, análogos a los ya fijados para el
   CDM en ADR-014: `mapping_set_id` (identidad estable del conjunto),
   `MappingSet.version` (snapshot concreto), `rule_id` (identidad estable
   de una regla — determinista, reutilizando el patrón
   `slugify`/`short_hash`/`make_*_id` ya implementado), `revision`
   (cambios sin alterar identidad). Una regla que cambia `target_field` o
   `rule_type` es, por definición, una regla nueva — la anterior se marca
   `retired`, nunca desaparece en silencio.

5. **`TransformationTrace` resuelve la decisión diferida por ADR-014**:
   se adopta una lista ordenada y **acotada** de `TraceStep`, cuya
   longitud se deriva directamente de la forma que la regla aplicada ya
   declara (nunca dinámica ni decidida en tiempo de ejecución) — ni un
   objeto único (pierde la señal de pasos intermedios fallidos, como un
   lookup que cae a un fallback) ni una secuencia genérica sin límite
   conocido de antemano (sería event sourcing).

6. **`value_map`/`lookup`/`reference` quedan claramente diferenciados**:
   tabla estática pequeña; catálogo externo cargado por separado
   (potencialmente en varios pasos); enlace a otro `CanonicalRecord`
   (produce una `Relationship`, no un valor plano) — nunca un único
   concepto "referencia" ambiguo.

Ver el documento de arquitectura para el detalle completo, la plantilla
Excel conceptual (§ 21) y los once ejemplos (§ 25), incluyendo el ejemplo
explícito de un conflicto detectado y no resuelto en silencio.

## Consequences

- Ningún Mapping Engine futuro puede diseñarse sin producir exactamente
  esta forma de `MappingRule`/`TransformationTrace` — es el contrato que
  permite que la validación de una especificación (§ 22 del documento) sea
  posible antes de ejecutar una migración real.
- El coste de doce tipos de regla (en vez de un lenguaje de expresiones
  único y más flexible) es tener que añadir un `rule_type` nuevo, con su
  propia ADR o revisión de esta, si aparece un comportamiento real que
  ninguno de los doce cubre — se acepta porque la alternativa (un lenguaje
  de expresiones libre) es exactamente lo que el encargo prohíbe
  explícitamente (Excel como lenguaje de programación inseguro).
- La imposibilidad de validar `target_field` contra una plantilla de
  Enablon real (sin el Enablon Template Contract, todavía no diseñado)
  queda como limitación explícita y documentada, no oculta — ninguna
  Mapping Specification puede declararse "verificada contra Enablon" hasta
  que ese componente exista.
- Cualquier necesidad futura de un decimotercer `rule_type`, o de una
  forma distinta de `TransformationTrace`, requiere revisar esta ADR o
  crear una nueva — no una extensión silenciosa del vocabulario cerrado.

## Alternatives Rejected

- **Un lenguaje de expresiones propio para condiciones y reglas** (un DSL
  tipo "fórmula"), en vez de una tabla de datos con un vocabulario cerrado
  de `rule_type`/`operator`. Rechazado explícitamente por el encargo y por
  [ADR-009](ADR-009-configuration-over-code.md) § Alternatives Rejected,
  que ya rechazó esta misma idea para el catálogo de reglas de
  transformación — un DSL añade una abstracción (parser/intérprete) sin
  consumidor real que la necesite hoy, y reintroduce exactamente el riesgo
  de seguridad que este documento existe para evitar.
- **Un único `rule_type` genérico con un campo `expression` de texto
  libre**, delegando toda la lógica a una cadena interpretada en tiempo de
  ejecución. Rechazado: es indistinguible de un lenguaje de programación
  embebido en Excel — el riesgo explícito que el encargo pide evitar.
- **Resolver conflictos de prioridad "la última regla del fichero gana"**.
  Rechazado: oculta exactamente el tipo de ambigüedad que ya ha causado
  defectos reales documentados (fases de flujo incorrectas en MOC,
  cambios anulados migrados como activos) — se prefiere un error de
  validación explícito a un comportamiento determinista pero silencioso.
- **`TransformationTrace` como objeto único** (solo el resultado final).
  Rechazado: no explica el caso real "lookup falla → cae a fallback",
  información que ya se necesita hoy para auditar `letter_lookup`/
  `workflow_status_lookup` sin coincidencia.
- **`TransformationTrace` como secuencia genérica sin límite de pasos**
  (una entrada por cada micro-operación que el motor decida registrar).
  Rechazado: coincide con "event sourcing", explícitamente en la lista de
  complejidad a evitar — la longitud de la traza debe poder predecirse
  leyendo la regla, no depender de decisiones del motor en tiempo de
  ejecución.
