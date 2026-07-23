# ADR-002 — Separar MappingDecision de MappingCoverageFinding

**Status:** Implemented

## Context

Clasificar una clave real (p. ej. `IDCentro`+`IDUnidadOrg`) frente a una tabla
de equivalencias produce dos tipos de información de naturaleza distinta: (a)
una decisión conceptualmente estable — "esta clave está mapeada / es No migra
/ no tiene correspondencia / usa un fallback documentado" — y (b) el resultado
observado de esa decisión en un momento concreto — cuántos registros la usan
en este BAK/freeze, con qué IDs históricos de ejemplo. Modelar ambas cosas en
una única entidad obligaría a reescribir la decisión cada vez que cambia el
recuento, o a perder el recuento si se conserva solo la decisión.

## Decision

`MappingDecision` representa exclusivamente la decisión (sin
`affected_record_count` ni `example_historical_ids`). `MappingCoverageFinding`
representa el resultado observado en una `analysis_run_id`/
`source_snapshot_id` concretos, referenciando a la decisión que interpreta
(`mapping_decision_id`). Las 7 salidas de `mapping_coverage.py` se generan
siempre desde la unión de ambas, nunca desde `MappingDecision` sola.

## Consequences

- La misma decisión puede tener múltiples `MappingCoverageFinding` a lo largo
  del tiempo (distintos BAK/freezes) sin duplicar ni perder la decisión en sí.
- Permite, en el futuro (Fase 6 — Versioning), sustituir un `finding` sin tocar
  la decisión que lo originó, o viceversa.
- Obliga a que cualquier consumidor de "cuántos registros hay bloqueados" pase
  siempre por la unión Finding+Decision, nunca por un atajo sobre la decisión.

## Alternatives Rejected

- **Una única entidad `MappingDecision` con recuentos embebidos.** Rechazado
  explícitamente: "de esta forma una misma decisión puede producir distintos
  resultados en diferentes BAK o freezes" (requisito explícito del proyecto).
- **Recalcular recuentos siempre al vuelo, sin persistir ningún finding.**
  Rechazado: pierde la trazabilidad de cuándo se detectó por primera vez un
  problema de cobertura (`first_detected_at`/`last_detected_at`).
