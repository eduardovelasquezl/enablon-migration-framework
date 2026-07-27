# ADR-010 — No Hidden State

**Status:** Approved Design

## Context

El diseño de Sprint 4.1 para `ObjectRegistry` (Core) evaluó explícitamente
si debía implementarse como singleton o instancia explícita, y recomendó
instancia explícita — sin estado de módulo global implícito — precisamente
para que dos tests, o dos ejecuciones, no compartan estado sin saberlo. Esta
ADR eleva esa decisión puntual a principio de producto.

## Decision

Ningún componente de EMF depende de estado global mutable implícito:

- `ObjectRegistry` se instancia explícitamente por quien lo necesita (la
  CLI, un test); nunca existe como variable de módulo compartida entre
  ejecuciones.
- `FrameworkContext` (Core, Sprint 4.1) es inmutable una vez construido —
  no es un contenedor donde distintos componentes van dejando estado
  mutable a medida que se ejecutan.
- Ningún Engine mantiene resultados de una ejecución anterior en memoria de
  proceso entre invocaciones — cada ejecución (`run_id` propio) es
  independiente y su resultado se persiste explícitamente en artefactos.
- Los handlers de logging que se añaden temporalmente (patrón ya existente
  en `src/analysis/sql_inventory.py`: añadir un `FileHandler` al root
  logger y quitarlo en `finally`) deben seguir ese mismo patrón
  explícito de alta/baja — nunca un handler que quede pegado al logger
  global de forma permanente y no documentada.

## Consequences

- Cualquier función pública de un Engine o Connector debe poder llamarse
  dos veces seguidas, con datos distintos, sin que la segunda llamada vea
  restos de la primera — condición necesaria para "Everything Must Be
  Testable" (paralela).
- El coste es tener que pasar explícitamente por parámetro lo que un
  singleton daría "gratis" (p. ej., el registro de objetos) — se acepta
  ese coste porque hace visible, en la firma de cada función, de qué
  depende realmente.
- La caché de solo-lectura ya existente en `src/config/loader.py`
  (`lru_cache` sobre YAML inmutable, congelado con `MappingProxyType`) no
  se considera estado oculto: es una caché de datos **inmutables**
  derivados determinísticamente de un fichero en disco, no estado mutable
  entre ejecuciones — se documenta aquí la distinción para que no se
  confunda con lo que esta ADR prohíbe.

## Alternatives Rejected

- **Un `ObjectRegistry` global de conveniencia, con un `register()` a nivel
  de módulo.** Rechazado: impediría que dos tests con catálogos distintos
  se ejecuten en el mismo proceso sin interferirse, y ocultaría en el
  import (no en la firma de función) de dónde viene el estado que un
  componente usa.
