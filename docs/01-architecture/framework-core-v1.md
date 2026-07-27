# Framework Core v1 — Execution Pipeline

**Status:** Implemented — ver
[ADR-016](../02-adr/ADR-016-framework-core-execution-pipeline.md). Primera
implementación real de código del Core descrito conceptualmente en
[`architecture-overview.md`](architecture-overview.md) § 2.1 (hasta ahora
"Approved Design, `src/core/` no existe todavía") — con esta fase,
`src/core/` existe, con un único consumidor real: Drills.

## 1. Propósito

Introducir un **Execution Pipeline genérico** — `src/core/` — capaz de
coordinar Project Configuration → Source → Query → Canonicalization →
Mapping → Validation → Export → Evidence → Manifest → Reports, y hacer que
Drills lo use como primer consumidor real, **sin reconstruir Drills**:
envolviendo, adaptando y reutilizando el prototipo ya existente y
verificado (`outputs/prototype/drills/20260723T195418Z/`, `status:
SUCCESS`).

## 2. Alcance

- Contratos mínimos del Core (`ExecutionRequest`, `ExecutionContext`,
  `PipelineDefinition`, `PipelineStage`, `StageResult`, `PipelineResult`,
  `ArtifactReference`, `ExecutionStatistics`/`StageMetrics`).
- Un `PipelineOrchestrator` genérico que ejecuta etapas en orden,
  resueltas contra un `StageRegistry` explícito.
- Cuatro adaptadores de etapa que envuelven el código ya existente de
  Drills (`query`, `canonicalize`, `transform_and_export`, `evidence`).
- Una sección `pipeline:` nueva y opcional en `config/exports/drills.yaml`.
- Un seam mínimo hacia el futuro Canonical Data Model (`CanonicalBatch`).
- Un comando CLI nuevo (`python main.py run ...`), aditivo, sin tocar
  `python main.py export drills ...`.
- Tests unitarios, de integración local (sin SQL real) y de regresión
  contra el comportamiento ya existente.

## 3. Fuera de alcance

Explícitamente no se implementa en esta fase (lista literal del encargo,
confirmada respetada):

Plugin system con carga dinámica; paralelismo; ejecución distribuida;
interfaz gráfica; API web; múltiples pipelines concurrentes; caché;
rollback automático; reintentos complejos; Excel Mapping Editor; Enablon
Template Registry completo; los 12 `rule_type` de la Mapping
Specification; un segundo módulo/objeto migrable real; migración completa
de la estructura `config/`; el Canonical Data Model completo
(`CanonicalRecord`/`CanonicalField`/`Provenance` por fila); ejecución
`full` real contra SQL Server; ningún commit.

## 4. Arquitectura

```
                    ExecutionRequest
                           │
                           ▼
              build_execution_context()   (Drills-specific factory,
                           │                vive en core_adapters.py,
                           ▼                NO en src/core/)
                    ExecutionContext
                           │
    PipelineDefinition ────┤
    (config/exports/       │
     drills.yaml →         ▼
     pipeline.stages)  PipelineOrchestrator.run()
                           │
         ┌─────────────────┼─────────────────┬─────────────────┐
         ▼                 ▼                 ▼                 ▼
   StageRegistry     StageRegistry     StageRegistry     StageRegistry
   .resolve("query") .resolve(         .resolve(         .resolve(
                      "canonicalize")   "transform_        "evidence")
         │                 │            and_export")           │
         ▼                 ▼                 ▼                 ▼
  DrillsQueryStage  DrillsCanonicalize  DrillsTransform  DrillsEvidence
  (extract_drills)  Stage (CanonicalBatch) ExportStage    Stage
                                          (pipeline.run() (evidence/
                                           envuelto)       collector+
                                                           workbook)
```

Dirección de dependencia (verificada por inspección de imports, no solo
declarada): `src/core/*.py` no importa nada de `src.export`, `src.etl`,
`src.evidence` ni ningún módulo con lógica de negocio. `core_adapters.py`
(dentro de `src/export/prototype/drills/`, la capa de Plugin/objeto
migrable) es quien importa **de ambos lados** — del Core y de Drills — y
los conecta con `register_drills_stages()`. Esta dirección es la exigida
por `architecture-overview.md` § 1 y verificable ejecutando
`grep -rn "from src.export\|from src.etl\|from src.evidence" src/core/`
(sin resultados).

## 5. `ExecutionRequest`

`src/core/contracts.py::ExecutionRequest` — dataclass **frozen**,
serializable, sin I/O:

`project`, `object_type`, `module` (opcional), `mode` (`sample`\|`full`),
`limit`, `source_override` (opcional, no usado todavía por Drills),
`output_dir` (opcional), `confirm_full_export`, `generate_evidence`,
`evidence_audience`, `filters` (tupla de tokens `campo:operador:valor`,
mismo formato que `export drills --filter`), `execution_id` (opcional).

Invariantes verificados en `__post_init__` (lanzan
`PipelineConfigurationError`, nunca fallan en silencio): `project`/
`object_type` no vacíos; `mode` es uno de los dos valores válidos;
`mode="full"` exige `confirm_full_export=True` explícito (mismo criterio
ya vigente en `src/cli.py::export_drills`); `limit` positivo en modo
`sample`.

**No contiene** (verificado en `test_core_contracts.py::
test_execution_request_no_contiene_dataframes_ni_credenciales`):
conexiones abiertas, `DataFrame`s, credenciales, ni reglas funcionales
(qué columna mapea a qué campo) — todo eso lo resuelve la configuración de
proyecto que el propio pipeline carga a partir de `object_type`.

## 6. `ExecutionContext`

`src/core/contracts.py::ExecutionContext` — el contexto compartido durante
UNA ejecución. Distinción explícita, pedida por el encargo, entre:

- **Inmutable** (fijado una vez al construir el contexto): `execution_id`,
  `request`, `started_at`, `working_dir`, `output_dir`, `logger`,
  `resolved_config`.
- **Mutable** (se acumula a medida que las etapas se ejecutan):
  `statistics`, `artifacts`, `issues`, `state`.

`state: dict[str, Any]` es el único lugar donde una etapa puede dejar
información para otra que no viaje por la cadena `stage_input`/`output`
(hoy: `drills_config` y `canonical_batch`) — documentado como excepción
acotada, no como "un contenedor global sin control": cada clave que una
etapa escribe se documenta en el propio adaptador que la escribe (ver
`core_adapters.py`).

## 7. `PipelineDefinition`

`src/core/contracts.py::PipelineDefinition` — `name` + `stages: tuple[str,
...]`, una secuencia de **nombres lógicos**, nunca instancias de etapa
(evita acoplar la definición a una implementación concreta). Rechaza una
lista vacía de etapas (`PipelineConfigurationError`).

Para Drills, se construye leyendo `config/exports/drills.yaml` →
`pipeline.stages` (Fase 4, ver § 17) — sección nueva y opcional; si no
existe, cae a `DEFAULT_PIPELINE_STAGES = (query, canonicalize,
transform_and_export, evidence)`.

## 8. `PipelineStage`

`src/core/contracts.py::PipelineStage` — un `Protocol` (`runtime_checkable`),
no una clase base obligatoria: cualquier objeto con un atributo `name` y
un método `execute(context, stage_input) -> StageResult` sirve, sin forzar
herencia. Cada etapa real (`DrillsQueryStage`, etc., en
`core_adapters.py`) declara su `name`, qué espera como `stage_input`, qué
produce como `StageResult.output`, y puede detener el pipeline devolviendo
`StageResult(status=FAILURE)`.

## 9. `StageResult`

Distingue `success`/`warning`/`failure`/`skipped` (`StageStatus`, § 12) —
nunca usa una excepción como único canal para un error funcional. Campos:
`stage`, `status`, `output`, `issues` (lista de `dict`, mismo esquema que
`issues.jsonl` ya existente), `metrics` (`StageMetrics`, § 13),
`artifacts` (lista de `ArtifactReference`, § 14), `duration_seconds`,
`message`. `is_blocking` es `True` únicamente cuando `status == FAILURE`.

## 10. `PipelineResult`

Resumen de la ejecución completa, devuelto por
`PipelineOrchestrator.run()`: `execution_id`, `status`
(`ExecutionStatus`, derivado de los `StageResult` acumulados — nunca fijado
a mano), `stage_results` (tupla ordenada), `statistics`, `artifacts`,
`issues`, `started_at`/`ended_at`/`duration_seconds`, `output_dir`.

## 11. Stage Registry

`src/core/registry.py::StageRegistry` — registro **explícito**, sin
descubrimiento dinámico de plugins, sin recorrer directorios, sin
importaciones mágicas (verificado: `registry.py` no usa `importlib` ni
`pkgutil`). `register(name, stage, overwrite=False)` /
`resolve(name)` (lanza `StageNotRegisteredError` si no existe) /
`is_registered(name)` / `registered_names()`. Instancia explícita, nunca
un registro global de módulo (ADR-010, No Hidden State) — dos
`StageRegistry` no comparten estado (verificado en
`test_core_registry.py::test_dos_registries_no_comparten_estado`).

El único registro real que existe hoy es
`core_adapters.py::register_drills_stages()` — cuatro líneas, auditables a
simple vista.

## 12. Gestión de errores

Distinción aplicada consistentemente (Fase 8):

| Tipo | Cómo se representa | Detiene la ejecución |
|---|---|---|
| Error técnico (fallo de conexión, error de programación) | Excepción no controlada, se propaga sin capturar | Sí — el orquestador NO intercepta excepciones de `stage.execute()` (verificado en `test_core_orchestrator.py::test_excepcion_tecnica_no_controlada_se_propaga_sin_ocultarse`) |
| Error funcional/legado ya conocido (`FileNotFoundError`/`ValueError`/`RuntimeError`/`FileExistsError` de `pipeline.run()`) | Capturado por `DrillsTransformExportStage` (mismo conjunto que ya captura `src/cli.py::export_drills`), traducido a `StageResult(status=FAILURE)` | Sí, vía `StageStatus.FAILURE` |
| Warning (lookup sin coincidencia, etc.) | `StageResult(status=WARNING)` + entradas en `stats.warnings`/`issues` (sin cambios respecto al comportamiento ya existente de Drills) | No |
| Exclusión (`DO_NOT_MIGRATE`, `Reference` inválida) | `issue` con categoría propia dentro de `StageResult.issues` (idéntico a `issues.jsonl` ya existente) | No |
| Dato no mapeado (`unresolved`) | `issue` + warning (sin cambios) | No |
| Etapa deliberadamente omitida | `StageResult(status=SKIPPED)` (p. ej. `evidence` cuando `generate_evidence=False`) | No |

No hay ningún `except Exception: pass` en `src/core/` ni en
`core_adapters.py` (verificado por inspección — solo se capturan los
cuatro tipos de excepción legados, nombrados explícitamente).

## 13. Métricas

`StageMetrics` por etapa: `stage`, `start_time`, `end_time`,
`duration_seconds`, `input_record_count`, `output_record_count`,
`excluded_record_count`, `warning_count`, `error_count`,
`artifacts_generated`. Un campo que no aplica a una etapa concreta queda
`None`, nunca `0` inventado (p. ej. `excluded_record_count` es `None` en
la etapa `query`, que no excluye filas — verificado en
`test_stage_metrics_metrica_no_aplicable_queda_none_no_cero`).
`ExecutionStatistics.per_stage` conserva las métricas de cada etapa sin
fundirlas; `total_warning_count`/`total_error_count` son agregaciones
explícitas, no el único dato disponible.

## 14. Artefactos

`ArtifactReference(name, path, kind, stage, required)` — una referencia al
fichero ya escrito, nunca su contenido. La etapa `transform_and_export`
registra `drills.csv`, `validation_report.yaml`, `export_manifest.yaml`,
`issues.jsonl` (obligatorios) y `comparison_report.yaml` (opcional, solo
si existe el CSV histórico); la etapa `evidence` registra
`evidence_internal.xlsx`/`evidence_client.xlsx` cuando se generan.

## 15. Integración con el Canonical Data Model

Fase 6 del encargo, resuelta con la **Opción C**: `CanonicalBatch`
(`src/core/contracts.py`) es un **intermediate record provisional**, no el
CDM completo de
[`canonical-data-model.md`](canonical-data-model.md) — no hay
`CanonicalField`/`Provenance`/`Relationship` por fila. Contiene
`object_type`, `source_system`, `rows` (hoy: el mismo `pandas.DataFrame`
que ya produce `extract_drills()`), `row_count`, `extracted_at`.

`DrillsCanonicalizeStage` lo construye y lo guarda en
`context.state["canonical_batch"]` para trazabilidad, pero **deja pasar la
`ExtractionResult` original sin tocarla** hacia la siguiente etapa — no se
reescriben las transformaciones de Drills para producir campos canónicos
completos por fila, algo que el encargo prohíbe explícitamente en esta
fase ("no reescribas las transformaciones de Drills solo para forzar el
CDM completo"). Adoptar el CDM completo (`CanonicalField` con
`Provenance` por campo) queda como deuda técnica explícita (§ 19).

## 16. Integración con la Mapping Specification

Fase 7 del encargo: **no se implementa ningún `rule_type` de
[`mapping-specification.md`](mapping-specification.md)** — Drills no lo
necesita todavía (sus 7 reglas de campo siguen viviendo, sin cambios, en
`config/exports/drills.yaml` → `fields`, interpretadas por
`transformations.py`/`mappings.py`, exactamente como antes de esta fase).

La única conexión real con el catálogo de "transformaciones registradas"
(`registered_transform` en la terminología de la Mapping Specification) es
que `RULE_REGISTRY`/`resolve_rule()` (`src/etl/transformations.py`) ya
implementa ese patrón — no se duplica ni se sustituye, se deja
exactamente donde está. El Mapping Engine genérico sigue siendo trabajo
futuro (Fase P2 del roadmap EMF).

## 17. Integración con Drills

`src/export/prototype/drills/core_adapters.py` es el único punto de
conexión. Cuatro etapas registradas (no ocho — "el mínimo corte útil"
permitido por la Fase 5):

| Etapa | Envuelve | Separación real hoy |
|---|---|---|
| `query` | `extract_drills()` | Limpia — ya era una función independiente |
| `canonicalize` | Construcción de `CanonicalBatch` | Limpia — paso nuevo, mínimo |
| `transform_and_export` | `pipeline.run()` completo (Mapping+Validation+Export+Manifest+Comparison+Issues) | **Fusionada** — deuda técnica documentada (§ 19) |
| `evidence` | `evidence.collector.load_run` + `evidence.workbook.build_workbook/save_workbook` | Limpia — ya la invocaba aparte la CLI |

No existe una etapa `report` registrada — no hay artefacto de "reporte"
distinto del Excel de evidencia (ver `drills-operational-mvp.md` § 9); se
añadirá cuando exista un consumidor real.

`config/exports/drills.yaml` gana una sección nueva y opcional:

```yaml
pipeline:
  stages: [query, canonicalize, transform_and_export, evidence]
```

## 18. Compatibilidad

**Modificación aditiva única en código de Drills**: `pipeline.run()` gana
tres parámetros opcionales (`extraction`, `run_id`, `timestamp`), todos
con default `None` — si se omiten (cualquier llamador anterior a esta
fase: CLI `export drills`, los ~20 tests ya existentes), el comportamiento
es **idéntico** al de antes. Se usan únicamente cuando el Core orquesta la
ejecución, para no repetir la consulta SQL entre las etapas `query` y
`transform_and_export`, y para alinear `run_id`/`timestamp` con
`execution_id`/`output_dir` del Core.

**Verificado, no solo declarado**: `test_drills_core_pipeline.py::
test_core_produce_el_mismo_csv_que_pipeline_run_directo` ejecuta el mismo
`DataFrame` fake por los dos caminos (llamada directa a `pipeline.run()`
vs. a través del `PipelineOrchestrator`, con el mismo `run_id`/
`timestamp`) y compara **byte a byte** `drills.csv`, y por igualdad
estructural completa `validation_report.yaml` y `export_manifest.yaml`
(incluidos los hashes). Los 451 tests ya existentes en el repositorio
siguen pasando sin ninguna modificación (`.venv/Scripts/python.exe -m
pytest -q` → `451 passed, 7 skipped`, los 7 `skipped` son los tests de
integración opt-in contra SQL Server real, igual que antes de esta fase).

El comando `python main.py export drills ...` no se tocó — ni sus
argumentos, ni su código, ni una sola línea del fichero `cli.py` que ya
existía para él.

## 19. Deuda técnica

- **`transform_and_export` fusiona Mapping+Validation+Export+Manifest+
  Comparison+Issues en una sola etapa.** Separarlas exigiría reescribir
  `pipeline.py` internamente (sus funciones auxiliares `_transform_rows`/
  `_write_issues_jsonl` son privadas y no están pensadas para exponerse
  por separado) — alto riesgo, explícitamente desaconsejado por el
  encargo para esta fase. Se documenta como el corte de "adaptador
  temporal" permitido por la Fase 5.
- **`CanonicalBatch` es un seam mínimo, no el CDM completo.** No hay
  `CanonicalField` por columna, ni `Provenance`, ni `Relationship` — solo
  un contenedor de nivel de lote. Adoptar el CDM completo exigiría
  reescribir `_transform_rows` para producir campos canónicos, fuera de
  alcance de esta fase.
- **No se implementa ningún `rule_type` de la Mapping Specification.**
  Las reglas de Drills siguen siendo las funciones ya existentes de
  `transformations.py`/`mappings.py`.
- **El seam de `CanonicalBatch` no se usa realmente para nada todavía**
  más allá de trazabilidad en `context.state` — es, honestamente, un
  punto de extensión declarado, no una capacidad activa. Se documenta así
  en vez de simular que ya aporta valor funcional.
- **La ejecución `full` a través del Core nunca se ha probado contra SQL
  Server real** (ni la legada, ver `drills-operational-mvp.md` § 0) — el
  camino `full` del Core reutiliza exactamente el mismo código que el
  camino `sample` ya probado, pero la combinación completa
  Core+`full`+SQL real queda sin verificar por esta fase (prohibido
  expresamente ejecutar SQL real sin aprobación).

## 20. Extensión para un segundo módulo

Sin implementarlo en esta fase, el camino queda documentado: un segundo
objeto migrable (p. ej. Events) necesitaría (1) su propio módulo de
adaptadores (`src/export/<algo>/events/core_adapters.py`, mismo patrón que
`core_adapters.py` de Drills — el Core no cambia); (2) su propia sección
`pipeline:` en su configuración; (3) registrar sus etapas en un
`StageRegistry` propio de esa ejecución (nunca compartido con el de
Drills, por diseño — dos `StageRegistry` no interfieren, § 11); (4)
decidir, con evidencia real de ese segundo caso, si `canonicalize`
necesita dejar de ser un simple envoltorio y empezar a producir
`CanonicalField` reales — exactamente el criterio "No Abstraction Without
a Real Consumer" ya aplicado en todo el resto de esta documentación EMF.

## 21. Criterios de aceptación

1. Existe un pipeline genérico (`src/core/`) — verificado, implementado y con tests.
2. El pipeline no conoce Drills — verificado por inspección de imports de `src/core/*.py` (ninguno).
3. Drills se ejecuta a través del pipeline (`python main.py run --project moeve --object drills ...`), verificado con tests de integración local.
4. El comando actual no queda roto — `export drills` sin cambios, 451 tests previos siguen en verde.
5. No hay lógica funcional nueva incrustada en el Core — todas las reglas de Drills siguen en `transformations.py`/`mappings.py`, sin tocar.
6. Las etapas usan contratos uniformes — las 4 implementan el mismo `PipelineStage` Protocol.
7. Los fallos bloqueantes detienen la ejecución — verificado (`test_fallo_bloqueante_detiene_el_pipeline`).
8. Los warnings se acumulan sin ocultarse — verificado (`test_warning_no_detiene_el_pipeline`, `issues.jsonl` sin cambios).
9. Las métricas se generan por etapa — verificado (`context.statistics.per_stage`).
10. Los artefactos quedan registrados — verificado (`ArtifactReference` por cada fichero escrito).
11. Tests unitarios e integración local pasan — 9 + 38 = 47 tests nuevos, todos en verde.
12. Tests existentes continúan pasando — 451 passed, 7 skipped (mismos skips que antes).
13. No se accedió a SQL Server sin aprobación — todos los tests nuevos usan `monkeypatch` sobre `run_query`.
14. No se realizó exportación `full` — ningún test ni ejecución manual usó `mode="full"`.
15. Documentación e informes generados — este documento + `reports/executions/<fecha>/`.
16. `git diff --check` limpio — verificado.
17. No se hizo commit.
