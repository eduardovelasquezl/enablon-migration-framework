# ADR-012 — Source Agnostic, Enablon Oriented

**Status:** Approved Design

> Nota: esta ADR complementa y refuerza a
> [ADR-006 legado](../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md)
> ("Generar CSV en vez de cargar directamente en Enablon"), sin ser la misma
> decisión ni compartir su número (la numeración de ADR es única en todo el
> repositorio — ver [ADR-007](ADR-007-framework-first.md) y
> [`02-adr/README.md`](README.md)). Son coherentes entre sí: esta ADR fija
> que la *entrada* es plural y la *salida* es siempre Enablon; la legada
> fija que esa salida es siempre un CSV, nunca una carga directa.

## Context

El Blueprint exige que EMF procese, en el futuro, SQL Server, Excel, CSV,
Word, PDF y JSON — pero el propósito final del framework sigue siendo
producir CSV de importación válidos para Enablon, no un sistema genérico de
ETL sin destino fijo. Hace falta fijar explícitamente que la generalización
es de la **entrada**, no del **destino**.

## Decision

EMF es **agnóstico de fuente, orientado a Enablon**: cualquier Connector de
entrada es válido en la capa de Connectors, pero el pipeline entero converge
siempre en el mismo destino — un CSV de importación que cumple exactamente
el contrato de una plantilla del Enablon Template Registry (Blueprint §
11). No se diseña EMF como una plataforma de transformación de datos de
propósito general con Enablon como "un destino más entre varios" — Enablon
es el único destino contemplado en esta versión del producto.

## Consequences

- El Modelo de Datos Canónico (ver
  [`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md))
  se diseña para representar cualquier registro migrable de origen, pero su
  forma está influida por lo que el Export Engine necesitará producir —
  no es un modelo de datos neutral pensado para cualquier consumidor
  imaginable.
- Un futuro destino distinto de Enablon (otro sistema GRC, por ejemplo) no
  está descartado para siempre, pero requeriría su propia ADR — no se
  diseña el Export Engine hoy pensando en múltiples destinos posibles sin
  un caso real (principio 8).
- La combinación con ADR-006 legado significa que, sea cual sea la fuente,
  el resultado sigue siendo siempre un artefacto de revisión (CSV +
  evidencia), nunca una escritura directa en Enablon.

## Alternatives Rejected

- **Diseñar el Canonical Data Model como un formato neutral, sin ningún
  sesgo hacia la forma de salida de Enablon.** Rechazado: añadiría una capa
  de indirección (mapeo modelo-neutral → modelo-orientado-a-Enablon) sin
  ningún consumidor que necesite ese nivel de generalidad hoy.
