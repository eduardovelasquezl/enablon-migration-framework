# ADR-007 — Framework First

**Status:** Approved Design

> Nota de numeración: la numeración de ADR es única en todo el repositorio.
> `docs/architecture/v1.0/decisions/` (legado) ocupa `ADR-001`…`ADR-006`,
> documentando decisiones del primer proyecto (Moeve, previo a EMF) — no se
> renumeran ni se modifican. Esta ADR y las siguientes seis
> (`docs/02-adr/ADR-007`…`ADR-013`) documentan decisiones a nivel de
> **producto EMF**, y continúan el consecutivo a partir del número más alto
> ya usado. Ver [`02-adr/README.md`](README.md) para el índice completo de
> las 13 ADR del repositorio.

## Context

El proyecto nació para resolver la migración histórica de un único cliente
(Moeve) sobre una única fuente (SQL Server). Existe una tentación natural,
en ese punto, de escribir el camino más corto: un script específico de
Moeve, con nombres de tabla y reglas de negocio embebidos directamente en
Python. Ese camino ya ha sido rechazado una vez, implícitamente, al
construir `src/db/`, `src/etl/` y `src/analysis/` como paquetes separados
con responsabilidades propias en vez de un único script monolítico.

## Decision

Todo componente nuevo de EMF, incluso cuando hoy solo tiene un consumidor
(Moeve, Drills), se diseña como si fuera a tener un segundo consumidor
distinto en el futuro — sin llegar a construir esa generalización antes de
que el segundo consumidor exista realmente (ver principio 8, "No
Abstraction Without a Real Consumer", que actúa como contrapeso directo de
este principio). "Framework First" no significa "generalizar todo ya" —
significa "no cerrar la puerta a generalizar después metiendo conocimiento
de un cliente/objeto concreto donde no corresponde".

En términos de capas (ver
[`architecture-overview.md`](../01-architecture/architecture-overview.md)):
el Core no puede depender de Engines, Connectors, Plugins ni Project
Configuration. Esta es la forma operativa y verificable de "Framework
First" — no una declaración de intenciones, sino una regla de dependencias
comprobable por un test automatizado (ver `test_core_dependency_boundaries`
propuesto en el diseño de Sprint 4.1).

## Consequences

- Cada incremento nuevo debe declarar explícitamente en qué capa vive
  (Core / Engine / Connector / Plugin / Project Configuration) antes de
  escribir código.
- El coste de este principio es velocidad a corto plazo: es más lento
  escribir `ObjectMetadata`/`ObjectRegistry` genéricos que hardcodear
  `"drills"` en un `if`. El beneficio se cobra cuando llega el segundo
  objeto/proyecto real.
- Ningún componente de capa inferior puede "asomarse" a una capa superior
  ni siquiera para un caso de conveniencia puntual (p. ej., el Core no
  puede importar `src.config` para resolver una ruta, aunque sería más
  cómodo — ver el informe de diseño de Sprint 4.1, sección de dependencias).

## Alternatives Rejected

- **Seguir escribiendo específicamente para Moeve/Drills hasta que aparezca
  un segundo cliente real.** Rechazado: el coste de desacoplar después de
  que el acoplamiento ya está extendido por todo el código (como ocurre hoy
  con `src/export/prototype/drills/`) es sistemáticamente mayor que
  diseñar las fronteras de capa desde el principio, incluso con un único
  consumidor.
