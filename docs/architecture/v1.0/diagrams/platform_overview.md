# Diagrama — Visión general de la plataforma

Diagrama ASCII únicamente, sin imágenes.

```
                         ┌───────────────────────────┐
                         │        INPUT LAYER        │  Implemented
                         │ sql/  inputs/  config/    │
                         │ (solo lectura, siempre)   │
                         └─────────────┬─────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
   ┌──────────▼─────────┐   ┌──────────▼─────────┐   ┌──────────▼─────────┐
   │  schema_analyzer.py │   │  query_analyzer.py │   │ mapping_resolver.py│
   │  (+_sheet_taxonomy) │   │  (+_select_parser)  │   │                     │
   │     Implemented      │   │     Implemented      │   │     Implemented      │
   └──────────┬─────────┘   └──────────┬─────────┘   └──────────┬─────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │   src/knowledge_base/      │  Implemented
                         │   model.py                 │
                         │   (catálogo/relaciones/    │
                         │    evidencia)               │
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │  mapping_coverage.py        │  Implemented
                         │  (MappingDecision +         │
                         │   MappingCoverageFinding)   │
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │  module_analysis.py         │  Implemented
                         │  (por módulo, nunca         │
                         │   ready_for_final_load)     │
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │  project_analysis.py        │  Implemented
                         │  (orquestación global,      │
                         │   Action Plans en fase       │
                         │   final)                    │
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │      EXPORT ENGINE          │  Approved Design
                         │  (no existe código todavía) │  (no implementado)
                         └─────────────┬─────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │       DELIVERABLES          │  Implemented (parcial)
                         │ outputs/ -- informes,       │
                         │ CSV de análisis/readiness,  │
                         │ manifest.yaml                │
                         │ (el CSV de importación a     │
                         │  Enablon: Approved Design)   │
                         └─────────────────────────────┘
```

Ver también [`record_lifecycle.md`](record_lifecycle.md),
[`action_plan_flow.md`](action_plan_flow.md) y [`export_flow.md`](export_flow.md)
para el detalle de cada tramo.
