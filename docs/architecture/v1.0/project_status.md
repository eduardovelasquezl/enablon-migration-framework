# Estado del proyecto

Matriz de referencia rápida. Para el detalle de cada elemento, ver
[`analysis_engine.md`](analysis_engine.md), [`export_engine.md`](export_engine.md)
y [`domain_model.md`](domain_model.md).

## IMPLEMENTADO

| Elemento | Módulo |
|---|---|
| Inventario y análisis de SQL de origen | `src/analysis/sql_inventory.py`, `src/db/*` |
| Schema Analysis (estructura y taxonomía de ETL Excel) | `src/analysis/schema_analyzer.py` (+ `_sheet_taxonomy.py`) |
| Query Analysis (JOIN/WHERE + columnas SELECT) | `src/analysis/query_analyzer.py` (+ `_select_parser.py`) |
| Mapping Resolution (destino ES→XML correcto) | `src/etl/mapping_resolver.py` |
| Knowledge Model (catálogo/relaciones/evidencia) | `src/knowledge_base/model.py` |
| Mapping Coverage (clasificación + 7 informes de diagnóstico) | `src/analysis/mapping_coverage.py` |
| Module Analysis (candidatos a Action Plans por módulo) | `src/analysis/module_analysis.py` |
| Cross-module Action Plans (buffer transversal) | `src/knowledge_base/model.py` (`CrossModuleActionPlanBuffer`), `module_analysis.py` |
| Project Analysis (orquestación global, consolidación, finalización) | `src/analysis/project_analysis.py` |
| Global Coverage (estado complete/incomplete/conflicting) | `src/analysis/project_analysis.py` |
| Validation (comprobaciones de calidad de datos, como entidad) | `src/knowledge_base/model.py` (`Validation`) |
| Volumetría y duplicados (análisis previos ya existentes) | `src/analysis/volumetry.py`, `src/analysis/duplicates.py`, `src/analysis/data_quality.py` |
| Motor de transformaciones de campo | `src/etl/transformations.py`, `src/etl/mapping_engine.py` (uso futuro, no migrado a `mapping_resolver.py` todavía) |

## APROBADO EN DISEÑO (no implementado)

| Elemento | Documento |
|---|---|
| Export Planner (`ExportPlan`/`ExportDefinition`) | [`export_engine.md`](export_engine.md) |
| CSV Generator | [`export_engine.md`](export_engine.md) |
| CSV Writer | [`export_engine.md`](export_engine.md) |
| CSV Validator | [`export_engine.md`](export_engine.md) |
| Export Package + Manifest de exportación | [`export_engine.md`](export_engine.md) |

## PENDIENTE (planificado, sin diseño detallado aprobado todavía)

| Elemento | Fase de roadmap |
|---|---|
| Versioning (motor de versionado de evidencia/decisiones) | Fase 6 |
| Repository Persistence (persistencia definitiva del Knowledge Repository) | Fase 5 |
| QA formal de CSV generado contra plantilla real de Enablon | Fase 3-4 |
| Comparación entre exportaciones | Fase 4 (no confirmado como parte del roadmap aprobado, ver `roadmap.md`) |
| IA / asistente de análisis | Fase 7 |
| API | Fuera de las 7 fases — no hay fase asignada todavía |
| UI | Fuera de las 7 fases — no hay fase asignada todavía |

## Notas de precisión

- `src/etl/mapping_engine.py` (el motor de aplicación de mappings anterior a
  `mapping_resolver.py`) sigue existiendo y sigue siendo funcional para su
  propósito original, pero **no se ha migrado** a usar `mapping_resolver.py` —
  esa migración es progresiva y todavía no se ha ejecutado. No confundir con
  "pendiente de implementar": ya está implementado, solo no actualizado.
- `read_field_mapping_sheet()` (en `src/etl/excel_reader.py`) sigue teniendo el
  defecto de lectura posicional ya documentado — se mantiene intacto por
  compatibilidad, `mapping_resolver.py` es la vía correcta nueva.
