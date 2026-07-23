# Knowledge Repository

## Qué información almacena el framework

Hoy, el "repositorio" es el conjunto de objetos Python en memoria que produce
una ejecución (`ProjectAnalysisResult` y todo lo que contiene) más los ficheros
de análisis que se escriben a `outputs/` cuando se pide explícitamente
(`generate_outputs=True`). **No existe todavía una persistencia definitiva del
repositorio** (Status: **Planned**, ver `roadmap.md` Fase 5) — cada ejecución
reconstruye su conocimiento desde las entradas (SQL, ETL, CSV, config), no desde
un almacén propio acumulado.

Lo que sí modela y transporta, de forma normalizada, en cada ejecución:

- Estructura física del origen (tablas, columnas, queries y sus expresiones SELECT).
- Estructura de los ETL Excel (hojas, su clasificación, sus mappings resueltos).
- Reglas de transformación/exclusión/fallback documentadas.
- Decisiones de cobertura de mapeo (`MappingDecision`) y sus resultados
  observados (`MappingCoverageFinding`).
- Objetos de migración y sus relaciones (jerarquía funcional, dependencias
  transversales de Action Plans).
- Evidencia de cada afirmación anterior, y preguntas abiertas cuando la
  evidencia no basta.

## Cómo se relacionan las entidades

Mediante tres capas separadas, nunca mezcladas — ver
[`domain_model.md`](domain_model.md) para el detalle de cada entidad:

```
┌───────────┐     ┌────────────┐     ┌───────────┐
│ CATÁLOGO  │     │ RELACIONES │     │ EVIDENCIA │
│ qué existe│◄────┤ Relation   ├────►│ Evidence  │
└───────────┘     └────────────┘     └───────────┘
```

Una entidad de catálogo (p. ej. `MigrationObject`) nunca lleva un campo
`parent_id` embebido — esa relación vive como un registro `Relation`
independiente, con su propio `resolution_status` y su propia lista de
`Evidence`. Esto permite que dos fuentes discrepen sobre la misma relación sin
que el catálogo tenga que "elegir" una versión: el conflicto se registra
(`resolution_status=conflicting`) y genera una `OpenQuestion`.

## Cómo se conserva la trazabilidad

Cada nivel de transformación conserva una referencia explícita al nivel
anterior:

```
SourceField (columna real de una tabla SQL)
    ▲
    │ referenced_columns / source_column (SelectExpression, query_analyzer.py)
    │
Mapping (fila de hoja de mapeo, resuelta por mapping_resolver.py)
    ▲
    │ mapping_decision_uses_mapping (conceptual, vía MappingDecision)
    │
MappingDecision (mapping_coverage.py) ──► MappingCoverageFinding (recuentos, ejemplos de ID histórico)
    ▲
    │ source_historical_id, source_module, source_system
    │
CrossModuleActionPlanBuffer (module_analysis.py / project_analysis.py)
    ▲
    │ action_plan_historical_id, evidence_ids
    │
ProjectAnalysisResult (salida final de análisis)
```

Cada eslabón conserva el identificador del anterior (`source_historical_id`,
`action_plan_historical_id`, `evidence_ids`) — nunca se sustituye ni se
resume, precisamente para poder responder "¿de qué fila de qué tabla SQL, de
qué hoja de qué Excel, salió este resultado?" en cualquier punto.

## Cómo se llega desde un registro SQL al CSV final

Hoy (Status: **Implemented** hasta donde se indica):

```
Fila real de una tabla SQL (fuera de alcance leerla directamente aquí)
   → SourceField / SelectExpression (query_analyzer.py)                    Implemented
   → Mapping resuelto (mapping_resolver.py)                                Implemented
   → MappingDecision + MappingCoverageFinding (mapping_coverage.py)        Implemented
   → CrossModuleActionPlanBuffer si es un objeto transversal (module_analysis.py)  Implemented
   → ProjectAnalysisResult, ready_for_final_load si corresponde (project_analysis.py)  Implemented
   → CSV de importación a Enablon                                          Approved Design (export_engine.md)
```

El framework, en esta versión, **llega hasta "listo para generar el CSV"**, no
hasta el CSV de importación en sí.
