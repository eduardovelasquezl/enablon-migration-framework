# ADR-013 — Mappings as Data

**Status:** Approved Design (generaliza un patrón ya validado con datos
reales — ver Context).

## Context

`CLAUDE.md` documenta un catálogo de reglas de transformación (`nullcontrol`,
`concat`/`barconcat`, `titlefix`, `cloneorigin`, `replaceinreference`,
`boolorigin`, lookup simple, lookup dinámico en 2 pasos) **ya confirmado
contra ETL Excel reales y datos reales**, siguiendo el patrón de columnas
`DatoOrigen / DatoDestino / EsCondicion / ReglaEspecial / Parametro` que el
propio cliente ya usa. `config/exports/drills.yaml` ya representa parte de
esto como datos (`reference_data.typology_lookup`, etc.), pero mezclado con
la definición de la plantilla de salida en un único YAML por objeto.

## Decision

Los mapeos (de campo, de valor, condicionales, de concatenación, de
conversión de tipo/fecha, de referencia a tabla maestra, de relación entre
objetos, de exclusión justificada, o cualquier transformación específica
registrable) son **datos configurables y versionables**, nunca lógica
Python embebida por objeto. Excel es el formato funcional preferido para
definirlos — es el formato con el que ya trabaja el cliente y con el que ya
se auditan los ETL originales — sin excluir otros formatos de datos
declarativos (YAML) para casos donde Excel no sea natural.

Cada entrada de mapeo conserva, como mínimo: proyecto, módulo, objeto,
fuente, campo origen, campo destino, tipo de regla, valor origen, valor
destino, obligatoriedad, prioridad, valor por defecto, observaciones,
versión y estado de validación — ver Blueprint § 10 para el detalle
completo y la trazabilidad de cada tipo de regla al catálogo ya confirmado.

El **motor** que interpreta cada tipo de regla (qué hace `concat`, qué hace
un lookup dinámico en 2 pasos) sigue siendo código — lo que es dato es la
declaración de *qué* regla se aplica a *qué* campo con *qué* parámetros,
igual que ya distingue [ADR-009](ADR-009-configuration-over-code.md).

## Consequences

- Añadir o corregir un mapeo, en el caso general, no requiere desplegar
  código nuevo — requiere una fila nueva o corregida en el fichero de
  mapeos, sujeta a su propio versionado.
- El estado de validación de un mapeo (`confirmed`/`inferred`/`pending`/...)
  viaja con el propio dato de mapeo, reforzando Evidence First
  ([ADR-008](ADR-008-evidence-first.md)) — un mapeo `pending` puede
  aplicarse en un entorno de prueba pero debe quedar señalado como tal en
  la evidencia de la ejecución.
- Regla no confirmada con datos reales queda excluida del alcance de esta
  ADR hasta confirmarse (p. ej. `titlefix`, cuyo motor real sigue sin
  identificarse según `CLAUDE.md`) — esta ADR no resuelve esa pregunta
  abierta, solo fija que, cuando se resuelva, su representación seguirá
  siendo datos, no código.

## Alternatives Rejected

- **Mantener los mapeos como diccionarios Python embebidos por objeto (el
  patrón actual de `config/exports/drills.yaml` → `reference_data`),
  generalizado copiando el mismo patrón para cada objeto nuevo.**
  Rechazado como destino final: funciona para un objeto, pero no escala a
  "cualquier objeto, cualquier proyecto" sin una fuente de mapeos unificada
  y versionable — se acepta como estado transicional ya existente, no como
  arquitectura objetivo.
