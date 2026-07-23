# ADR-001 — MigrationObject como unidad central del modelo

**Status:** Implemented

## Context

Varios módulos del proyecto no son un único objeto Enablon: "Eventos" produce
`Events`, `Impacts`, `Investigations` y `PSM Forms`; "Simulacros" produce
`Drills` y `List of Activities`. Modelar cada módulo como un bloque monolítico
obligaba a tratar estos objetos internos de forma implícita (por convención de
nombre de hoja/CSV), perdiendo la posibilidad de declarar dependencias,
jerarquía funcional o alcance de procesamiento a ese nivel.

## Decision

Introducir `MigrationObject` como la unidad granular real de trabajo, por
debajo de `Module`: un módulo tiene uno o más `MigrationObject`, cada uno con
su propio `processing_scope` (`module`/`cross_module`) y `load_phase`
(`normal`/`final`). Las relaciones de jerarquía funcional y de dependencia
transversal (ver ADR-003) se expresan siempre entre `MigrationObject`, nunca
entre `Module`.

## Consequences

- Un módulo compuesto (Eventos, Simulacros, Action Plans) se sigue tratando
  como un único módulo funcional de cara al usuario, sin perder la distinción
  interna que el análisis necesita.
- Permite declarar que Action Plans es transversal (`cross_module`) y de fase
  final (`final`) sin necesitar un tipo de entidad aparte.
- Añade un nivel más de identificador (`migration_object_id`) que debe
  propagarse en cascada (`Mapping`, `MappingDecision`,
  `CrossModuleActionPlanBuffer` lo incluyen en su ID determinista).

## Alternatives Rejected

- **Modelar cada objeto interno como su propio `Module`.** Rechazado: rompería
  la correspondencia funcional ya validada con el cliente (Eventos es "un"
  módulo, no cuatro proyectos distintos).
- **No modelar el objeto interno, solo el CSV de salida.** Rechazado: impedía
  declarar jerarquía funcional (Inspections → Inspection Data → Observations)
  y dependencias de Action Plans de forma explícita y trazable.
