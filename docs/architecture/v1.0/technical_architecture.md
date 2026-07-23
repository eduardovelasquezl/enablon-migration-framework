# Arquitectura técnica

## Capas

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT LAYER                                            Implemented │
│ sql/, inputs/, config/ -- SQL de solo lectura, ETL Excel, CSV,     │
│ catálogo de entidades, configuración declarativa                  │
└───────────────────────────────┬─────────────────────────────────┘
                                 │ (solo lectura, nunca se escribe aquí)
┌───────────────────────────────▼─────────────────────────────────┐
│ KNOWLEDGE ENGINE                                        Implemented │
│ src/analysis/*, src/etl/mapping_resolver.py,                       │
│ src/knowledge_base/model.py                                       │
│ -- entiende estructura, resuelve mappings, clasifica cobertura,   │
│    consolida objetos transversales                                │
└───────────────────────────────┬─────────────────────────────────┘
                                 │ (ProjectAnalysisResult, en memoria)
┌───────────────────────────────▼─────────────────────────────────┐
│ EXPORT ENGINE                                      Approved Design │
│ (no existe código todavía)                                        │
│ -- transformaría el resultado de análisis en el CSV de carga a    │
│    Enablon, con su propia validación de plantilla                 │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
┌───────────────────────────────▼─────────────────────────────────┐
│ DELIVERABLES                                            Implemented │
│ (parcial: informes de análisis sí; CSV de carga, no)               │
│ outputs/ -- informes, CSV de cobertura/readiness, manifest.yaml    │
└─────────────────────────────────────────────────────────────────┘
```

## Responsabilidades por capa

### Input Layer — `Implemented`
Contiene todo lo que el proyecto recibe: `sql/source_queries/` (queries reales),
`inputs/` (ETL, CSV, catálogo de entidades, incidencias), `config/*.yaml`
(configuración declarativa de módulos, conexiones y reglas). No contiene lógica,
solo datos y configuración. Nunca se escribe desde ninguna otra capa.

### Knowledge Engine — `Implemented`
El núcleo del framework. Ver el detalle completo de cada componente en
[`analysis_engine.md`](analysis_engine.md). En resumen:

- Analiza la estructura física (SQL, ETL Excel) — `query_analyzer.py`, `schema_analyzer.py`.
- Resuelve el destino real de cada campo mapeado — `mapping_resolver.py`.
- Clasifica la cobertura de cada valor/clave real — `mapping_coverage.py`.
- Detecta y prepara candidatos a Action Plans por módulo — `module_analysis.py`.
- Orquesta el proyecto completo y consolida lo transversal — `project_analysis.py`.
- Modela todo lo anterior de forma normalizada (catálogo/relaciones/evidencia) —
  `src/knowledge_base/model.py`.

### Export Engine — `Approved Design` (no implementado)
Capa que, una vez aprobado un template de importación de Enablon, generaría el
CSV de carga definitivo a partir del `ProjectAnalysisResult`. Ver
[`export_engine.md`](export_engine.md) para el diseño completo. **No existe
ningún código de esta capa en `src/` hoy.**

### Deliverables — `Implemented` (parcial)
Los informes de cobertura (`outputs/*.csv`, `client_mapping_questions.xlsx`) y
los resultados de orquestación de proyecto (`outputs/analysis/<project_id>/
<analysis_run_id>/`) sí se generan. El CSV de importación a Enablon, no.

## Dependencias entre capas

```
Deliverables  --depende de-->  Export Engine (cuando exista)  --depende de-->  Knowledge Engine  --depende de-->  Input Layer
```

Cada flecha es de una sola dirección: una capa nunca depende de la que está por
encima de ella en este diagrama. El Knowledge Engine no sabe nada de cómo se
verá el CSV final; el Export Engine (cuando exista) no leerá Excel/SQL
directamente, consumirá `ProjectAnalysisResult`.

## Desacoplamiento

- **Dentro del Knowledge Engine**, cada componente tiene un único punto público
  (`query_analyzer.py`, `schema_analyzer.py`) aunque internamente delegue en
  helpers privados (`_select_parser.py`, `_sheet_taxonomy.py`) — nadie fuera del
  módulo público importa esos privados.
- **`module_analysis.py` nunca decide por sí solo que algo está listo para
  carga** (`ready_for_final_load`) — esa decisión es exclusiva de
  `project_analysis.py`, precisamente para que un módulo no pueda adelantarse a
  la consolidación transversal.
- **`project_analysis.py` no reimplementa** la resolución de mappings ni la
  clasificación de cobertura — las reutiliza a través de sus resultados ya
  calculados (`ModuleAnalysisResult`, `FieldValidationResult`,
  `ParentResolutionInput`).
- El modelo de dominio separa **catálogo** (qué existe), **relaciones** (cómo se
  relaciona) y **evidencia** (por qué se sabe) en conceptos distintos — nunca
  embebidos unos en otros. Ver [`knowledge_repository.md`](knowledge_repository.md).
