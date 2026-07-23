# Flujo de procesamiento

Cada fase indica su estado real. Ninguna fase marcada `Approved Design` o
`Planned` tiene código en `src/` a día de esta versión.

```
SQL de origen (solo lectura)
        │
        ▼
Schema Analysis  ─────────────────────────────  Implemented
  (schema_analyzer.py: estructura y taxonomía
   de hojas de ETL Excel; inventario SQL ya
   existente por separado)
        │
        ▼
Query Analysis  ──────────────────────────────  Implemented
  (query_analyzer.py: JOIN/WHERE, columnas
   SELECT, alias, tabla origen resuelta)
        │
        ▼
Mapping Resolution  ───────────────────────────  Implemented
  (mapping_resolver.py: destino real ES→XML,
   nunca por coincidencia posicional)
        │
        ▼
Migration Objects  ────────────────────────────  Implemented
  (MigrationObject en el modelo de dominio:
   objeto funcional granular dentro de un
   módulo -- Events, Impacts, Drills...)
        │
        ▼
Module Analysis  ──────────────────────────────  Implemented
  (module_analysis.py: detecta candidatos a
   Action Plans, valida campos, intenta
   resolver el padre -- NUNCA declara nada
   listo para carga)
        │
        ▼
Project Analysis  ─────────────────────────────  Implemented
  (project_analysis.py: consolida el buffer
   transversal, resuelve padres entre módulos,
   calcula cobertura global)
        │
        ▼
Export Planning (pendiente)  ──────────────────  Approved Design
  (ExportPlan/ExportDefinition -- decidiría
   QUÉ se exporta y con qué reglas, a partir
   de ProjectAnalysisResult)
        │
        ▼
CSV Generation (pendiente)  ───────────────────  Approved Design
  (CSV Generator/Writer/Validator -- produciría
   el CSV de importación real a Enablon)
        │
        ▼
QA  ────────────────────────────────────────────  Planned
  (validación del CSV generado contra la
   plantilla real de Enablon antes de entregar)
        │
        ▼
Entrega  ───────────────────────────────────────  Planned
  (entrega manual o vía API a Enablon -- fuera
   de alcance de este framework por ahora)
```

## Notas de flujo importantes

- **Mapping Coverage** (`mapping_coverage.py`) corre en paralelo a Mapping
  Resolution/Migration Objects, no es una fase secuencial propia: clasifica cada
  clave real observada (mapeada / No migra / bloqueada / fallback) usando el
  resultado de `mapping_resolver.py` como una de sus entradas.
- **Action Plans es siempre la última fase funcional dentro de Project
  Analysis** — no se finaliza (`ready_for_final_load`) mientras quede algún
  módulo del alcance declarado sin analizar. Ver
  [`diagrams/action_plan_flow.md`](diagrams/action_plan_flow.md).
- El corte entre lo **Implemented** y lo **Approved Design** de este diagrama es
  exactamente el corte entre el Knowledge Engine y el Export Engine descrito en
  [`technical_architecture.md`](technical_architecture.md).
