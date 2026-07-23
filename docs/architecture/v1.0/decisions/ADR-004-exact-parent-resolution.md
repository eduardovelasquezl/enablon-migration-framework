# ADR-004 — Resolución exclusivamente exacta de referencias padre

**Status:** Implemented

## Context

Resolver a qué objeto padre pertenece una acción vinculada (`linked_action_plan`)
podría intentarse por aproximación — coincidencia parcial de texto, similitud
de título/descripción, fecha aproximada — especialmente cuando el padre vive
en otro módulo y no hay un identificador directo evidente. Este enfoque
introduciría exactamente el tipo de inferencia no verificable que el proyecto
ha rechazado en cada incremento anterior (mappings, entidades, cobertura).

## Decision

`resolve_action_plan_parents()` resuelve únicamamente contra un
`parent_reference_index` construido a partir de objetos ya procesados con
evidencia exacta (mismo `source_system` + `target_historical_reference`).
Nunca se usa similitud textual, título, descripción o fecha aproximada. Si no
hay coincidencia exacta: mientras queden módulos por analizar, la acción queda
`waiting_for_parent`; al cerrar el alcance declarado, pasa a `blocked` con
razón explícita. Si hay más de una coincidencia distinta para la misma clave,
la acción pasa a `conflicting`/`blocked` — nunca se elige una de las dos.

## Consequences

- Ninguna acción vinculada llega a `ready_for_final_load` por una suposición —
  siempre por una coincidencia exacta y trazable (`evidence_ids`).
- Puede dejar acciones legítimamente bloqueadas cuando el padre real no está
  en el alcance analizado — es el comportamiento correcto, no un defecto.
- Requiere que quien construye `parent_reference_index` haya resuelto antes,
  con evidencia real, las referencias que allí incluye — el propio
  `project_analysis.py` no inventa esas referencias.

## Alternatives Rejected

- **Coincidencia difusa (fuzzy matching) sobre título/descripción.**
  Rechazado explícitamente en el enunciado del incremento.
- **Asumir un único padre "más probable" ante varias coincidencias.**
  Rechazado: oculta un conflicto real de datos en vez de exponerlo.
