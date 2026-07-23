# ADR-006 — Generar CSV en vez de cargar directamente en Enablon

**Status:** Implemented (como restricción ya vigente en todo el proyecto)

## Context

El proceso original que este framework sustituye era un ETL en Excel pesado y
frágil, pero el objetivo declarado del proyecto desde su origen (ver
`CLAUDE.md`) nunca fue automatizar la carga a Enablon — fue sustituir el
análisis y la preparación de datos por algo repetible y auditable. Enablon no
ofrece hoy, dentro del alcance de este proyecto, una vía de carga directa
verificada y aprobada por el cliente.

## Decision

El framework, en todas sus fases (actuales y futuras), produce como máximo un
CSV de importación — nunca ejecuta una carga directa contra Enablon (API o
UI). La entrega final a Enablon queda fuera de este repositorio, manual o vía
API, decidida por el cliente.

## Consequences

- Cada salida del framework, sin excepción, es un fichero que un humano (o un
  proceso externo, fuera de este repo) revisa antes de entrar en Enablon.
- No se necesita gestionar credenciales de escritura a Enablon dentro de este
  proyecto.
- Cualquier futura integración de carga directa sería un incremento
  explícitamente nuevo y aprobado, no una extensión implícita del Export
  Engine ya diseñado.

## Alternatives Rejected

- **Integración directa vía API de Enablon dentro del Export Engine.**
  Rechazado para esta versión — no hay acceso de escritura a Enablon
  solicitado ni aprobado, y mezclar generación con carga rompería ADR-005.
