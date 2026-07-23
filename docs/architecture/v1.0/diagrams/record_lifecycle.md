# Diagrama — Ciclo de vida de un registro

Sigue un campo/valor concreto desde el SQL de origen hasta el resultado de
análisis final. Diagrama ASCII únicamente.

```
Fila real de una tabla SQL
        │
        ▼
┌───────────────────────────┐
│ SelectExpression            │  query_analyzer.py -- Implemented
│ (columna simple o calculada,│
│  tabla origen resuelta si   │
│  no hay ambigüedad)          │
└──────────────┬─────────────┘
               │
               ▼
┌───────────────────────────┐
│ Mapping                      │  mapping_resolver.py -- Implemented
│ (destino XML real, resuelto  │
│  por catálogo ES→XML, nunca  │
│  por posición de fila)       │
└──────────────┬─────────────┘
               │
               ▼
┌───────────────────────────┐
│ MappingDecision               │  mapping_coverage.py -- Implemented
│ decision_type:                │
│   mapped | do_not_migrate |   │
│   pending_mapping |           │
│   fallback_value |            │
│   default_value | conflicting │
└──────────────┬─────────────┘
               │
               ▼
┌───────────────────────────┐
│ MappingCoverageFinding         │  mapping_coverage.py -- Implemented
│ (recuento real de registros   │
│  afectados en ESTA corrida,   │
│  muestra de IDs históricos)   │
└──────────────┬─────────────┘
               │
   ¿Es un objeto transversal (Action Plans)?
               │
       ┌───────┴────────┐
       │ sí              │ no
       ▼                 ▼
┌─────────────┐   (queda aquí -- informe de
│ Cross-Module │    cobertura, sin más pasos)
│ ActionPlan   │
│ Buffer        │  module_analysis.py + project_analysis.py -- Implemented
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│ ready_for_final_load  │  SOLO project_analysis.py -- Implemented
│  o blocked/excluded   │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────┐
│ CSV de importación     │  Approved Design -- NO implementado
│ a Enablon               │  (ver export_engine.md)
└─────────────────────┘
```

En cada flecha se conserva el identificador del nivel anterior — nunca se
pierde ni se resume la trazabilidad hasta el registro histórico de origen.
