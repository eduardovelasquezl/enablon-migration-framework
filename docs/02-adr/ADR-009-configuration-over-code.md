# ADR-009 — Configuration over Code

**Status:** Approved Design (patrón ya vigente parcialmente — ver
`config/*.yaml`; formalizado aquí como principio obligatorio de EMF).

## Context

El proyecto ya distingue, en `src/config/`, entre datos de configuración
(`config/*.yaml`) y su interpretación (código que los consume). El propio
`config/exports/drills.yaml` ya declara columnas, reglas de lookup y
exclusiones como datos, no como código Python. Al mismo tiempo, otras partes
del sistema (`src/etl/transformations.py`, reglas de tipología/letra/estado
de Drills) todavía mezclan estructura de datos con lógica Python específica
de un objeto.

## Decision

Todo lo que varía entre proyecto, módulo, objeto o versión de plantilla debe
representarse como **dato configurable**, nunca como una rama de código
(`if object_id == "drills"`) dentro de un Engine o del Core. Esto se aplica,
en particular, a:

- Mapeos de campo y de valor (ver
  [ADR-013](ADR-013-mappings-as-data.md) — principio hermano directo de
  este).
- Definición de qué columnas exige una plantilla de Enablon (Enablon
  Template Registry, Blueprint § 11).
- Metadatos de un objeto migrable (`ObjectMetadata`, Sprint 4.1) — declarado,
  no codificado por objeto.

`Configuration over Code` no significa "todo es YAML" — significa que la
**forma** de un dato de negocio (una regla de mapeo, una plantilla) vive
fuera del código Python que la ejecuta, de modo que añadir un objeto o un
proyecto nuevo sea, en el caso general, una operación de datos, no de
programación.

## Consequences

- Un Engine que necesite un `if`/`elif` creciente por cada objeto nuevo es
  una señal de que algo que debería ser configuración se quedó en código —
  se trata como deuda a resolver, no como diseño aceptable.
- La configuración sigue sujeta al mismo estándar de seguridad que el
  código: nunca contiene secretos (ya vigente, ver
  `config/databases.yaml` — "Los valores reales... NUNCA van aquí").
- No todo puede ser dato: la lógica de *cómo* se interpreta una regla de
  mapeo (el motor que ejecuta `concat`, `nullcontrol`...) sigue siendo
  código — lo que es dato es *qué* regla se aplica a *qué* campo, no cómo
  se implementa la regla en sí.

## Alternatives Rejected

- **Un lenguaje de expresiones propio (DSL) para reglas de mapeo, en vez de
  una tabla de datos declarativa.** Rechazado por ahora: añadiría una
  abstracción (un parser/intérprete) sin un consumidor real que la necesite
  hoy (principio 8) — el catálogo de reglas ya confirmado en `CLAUDE.md`
  se representa completo con una tabla de filas tipadas, sin necesidad de
  un lenguaje nuevo.
