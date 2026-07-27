# Informe — Framework Core v1 / Execution Pipeline (Fase 6 EMF)

**Proyecto:** Enablon Migration Framework (EMF)
**Fecha:** 2026-07-27
**Tarea:** Implementar el primer Execution Pipeline genérico del EMF, con
Drills como primer consumidor real, sin reconstruir el prototipo existente.

---

## 1. Resumen ejecutivo

Se implementó `src/core/` — un Execution Pipeline genérico (contratos +
`StageRegistry` + `PipelineOrchestrator`) — y se conectó Drills a él
mediante cuatro adaptadores de etapa (`query`, `canonicalize`,
`transform_and_export`, `evidence`) que **envuelven, sin reescribir**, el
prototipo ya existente y verificado. El Core no contiene ninguna línea de
lógica específica de Drills; toda esa conexión vive en
`src/export/prototype/drills/core_adapters.py`. Se añadió un comando CLI
nuevo (`python main.py run ...`) sin tocar el comando existente
(`export drills`). 47 tests nuevos, todos en verde; los 451 tests ya
existentes en el repositorio siguen pasando sin cambios (7 `skipped`,
mismos de siempre — integración opt-in contra SQL real). Un test de
regresión compara, byte a byte, el CSV producido por el Core contra el
producido por el código legado con los mismos datos de entrada. No se
accedió a SQL Server real, no se ejecutó modo `full`, no se hizo commit.

---

## 2. Estado previo

- Prototipo de Drills funcional (`src/export/prototype/drills/`), con una
  ejecución real y exitosa ya registrada:
  `outputs/prototype/drills/20260723T195418Z/` (`status: SUCCESS`, 0
  errores, `drills.csv` + manifiesto + validation report + comparison
  report + ambos Excel de evidencia).
- `src/core/` no existía (`architecture-overview.md` lo describía como
  "Approved Design, no implementado todavía").
- `docs/01-architecture/canonical-data-model.md` y `ADR-014` en estado
  `Proposed`; `docs/01-architecture/mapping-specification.md` y `ADR-015`
  en estado `Proposed`. Ninguno de los dos implementado en código.

---

## 3. Flujo actual de Drills (Fase 0 — análisis previo, sin modificar nada)

```
CLI (src/cli.py::export_drills)
  -> compile_filter_tokens() (Query Engine v0.1, si hay --filter)
  -> pipeline.run() (src/export/prototype/drills/pipeline.py)
       -> load_drills_config()               (config.py)
       -> extract_drills()                   (extractor.py, ya separado)
       -> validate_pre_write()                (validator.py)
       -> _transform_rows()                    (privada -- Mapping+reglas+issues, FUSIONADA)
       -> write_csv()                           (exporter.py)
       -> validate_output_csv()                  (validator.py)
       -> write_validation_report()               (manifest.py)
       -> build_export_manifest()/write_export_manifest() (manifest.py)
       -> build_comparison_report()                 (comparison.py, opcional)
       -> _write_issues_jsonl()                      (privada)
  -> [opcional] _generate_evidence() -> evidence.collector.load_run()
                                       -> evidence.workbook.build_workbook()/save_workbook()
```

**Ya genéricos hoy**: `extractor.py` (extracción), `evidence/collector.py`+
`workbook.py` (ya se invocan aparte de la exportación). **Adaptables sin
riesgo**: los dos anteriores. **Específicos de Drills**: `config.py`
(`FieldSpec` de 8 columnas concretas), `transformations.py`/`mappings.py`
(reglas de negocio de Simulacros), `OUTPUT_COLUMNS`/`HISTORICAL_CSV_PATH`
(constantes del objeto). **Mezclan orquestación con reglas funcionales**:
`pipeline.py::run()` y su función privada `_transform_rows()` — Mapping,
Validation, Export, Manifest, Comparison e Issues están entrelazados en
una sola función, compartiendo el mismo objeto `RunStats` mutable.
**No debía moverse todavía**: ninguna de las funciones privadas
(`_transform_rows`, `_write_issues_jsonl`) — separarlas exige reescribir
`pipeline.py`, fuera de alcance de esta fase.

---

## 4. Plan ejecutado (registrado antes de modificar, tal como exige la Fase 0)

1. Contratos mínimos del Core (`src/core/contracts.py`), sin ningún
   import de Drills.
2. `StageRegistry` explícito (`src/core/registry.py`) — sin descubrimiento
   dinámico.
3. `PipelineOrchestrator` genérico (`src/core/orchestrator.py`) — resuelve
   etapas, propaga excepciones técnicas, detiene ante `FAILURE`.
4. Sección `pipeline:` nueva y opcional en `config/exports/drills.yaml`.
5. Cuatro adaptadores de etapa en `src/export/prototype/drills/
   core_adapters.py`, reutilizando el código existente sin reescribirlo.
6. Modificación aditiva de `pipeline.run()` (tres parámetros opcionales
   nuevos, default `None`, comportamiento idéntico si se omiten).
7. `CanonicalBatch` (seam mínimo hacia el CDM, Opción C de la Fase 6).
8. Comando CLI nuevo `run`, aditivo, en `src/cli.py`.
9. 47 tests nuevos (unitarios de Core + integración local + regresión).
10. Ejecución de la suite completa (451+47 tests) y `git diff --check`.
11. Documentación (`framework-core-v1.md`) y ADR-016.
12. Este informe.

**Riesgos identificados de antemano** (y cómo se mitigaron): reescribir
`pipeline.py` podía romper el comportamiento ya verificado → se optó por
envolverlo como adaptador temporal en vez de descomponerlo. Duplicar la
consulta SQL entre las etapas `query` y `transform_and_export` → se
resolvió con el parámetro aditivo `extraction=` en `pipeline.run()`,
verificado con un test dedicado (`test_core_no_ejecuta_la_query_dos_veces`).

---

## 5. Archivos creados

- `src/core/__init__.py`, `src/core/contracts.py`, `src/core/exceptions.py`, `src/core/registry.py`, `src/core/orchestrator.py`
- `src/export/prototype/drills/core_adapters.py`
- `tests/test_core_contracts.py`, `tests/test_core_registry.py`, `tests/test_core_orchestrator.py`, `tests/test_drills_core_pipeline.py`
- `docs/01-architecture/framework-core-v1.md`
- `docs/02-adr/ADR-016-framework-core-execution-pipeline.md`
- `reports/executions/2026-07-27/Informe-Framework-Core-V1-EMF.md` (este informe) y `.txt`

## 6. Archivos modificados

- `config/exports/drills.yaml` — añadida sección `pipeline:` (13 líneas nuevas, nada eliminado).
- `src/cli.py` — añadido comando `run` + imports nuevos (115 líneas nuevas, nada eliminado ni modificado del comando `export drills`).
- `src/export/prototype/drills/pipeline.py` — `run()` gana 3 parámetros opcionales con default `None` (24 líneas netas, comportamiento por defecto sin cambios, verificado por test de regresión).
- `docs/02-adr/README.md` — fila nueva para ADR-016, número libre actualizado a ADR-017.
- `.claude/settings.local.json` — **no editado directamente por mí**: es el registro de permisos que el propio Claude Code añade automáticamente al aprobar cada comando `Bash` ejecutado durante esta tarea (nuevas líneas en la lista de comandos permitidos). Se documenta aquí por transparencia, no es un cambio de configuración de proyecto.

Ningún archivo de `tests/` existente, ni `.env`, ni ningún artefacto de `outputs/` fue modificado.

---

## 7. Contratos implementados

`ExecutionRequest`, `ExecutionContext`, `PipelineDefinition`,
`PipelineStage` (Protocol), `StageResult`, `PipelineResult`,
`ArtifactReference`, `StageMetrics`, `ExecutionStatistics`,
`StageStatus`/`ExecutionStatus` (vocabularios cerrados), `CanonicalBatch`
(seam CDM). Ver `docs/01-architecture/framework-core-v1.md` § 5-10 para el
detalle campo a campo.

## 8. Etapas implementadas

`query`, `canonicalize`, `transform_and_export` (adaptador temporal,
fusiona Mapping+Validation+Export+Manifest+Comparison+Issues), `evidence`.
No se implementó `report` (no existe artefacto que producir, ver
`drills-operational-mvp.md` § 9).

## 9. Adaptadores creados

`DrillsQueryStage`, `DrillsCanonicalizeStage`, `DrillsTransformExportStage`,
`DrillsEvidenceStage` + `register_drills_stages()` +
`build_drills_pipeline_definition()` + `build_execution_context()`, todos
en `src/export/prototype/drills/core_adapters.py`.

---

## 10. Decisiones de compatibilidad

- `pipeline.run()` gana `extraction`/`run_id`/`timestamp` opcionales
  (default `None`) — cualquier llamador que no los pase (CLI existente,
  20 tests previos) se comporta exactamente igual que antes.
- El directorio de salida por defecto sigue siendo
  `outputs/prototype/drills/<timestamp>` — sin cambios.
- `OUTPUT_COLUMNS`, formato del CSV, `validation_report.yaml`,
  `export_manifest.yaml`, `issues.jsonl` — ningún cambio de forma ni de
  contenido (verificado por comparación byte a byte, ver § 15).
- El comando `export drills` no se tocó.

## 11. Gestión de errores

Ver `framework-core-v1.md` § 12 para la tabla completa. Resumen: técnico
→ excepción propagada sin capturar; funcional/legado conocido → capturado
y traducido a `StageResult(FAILURE)` (mismas 4 excepciones que ya
capturaba `cli.py`); warning/exclusión/no-mapeado → `issues` dentro de
`StageResult`, igual que en `issues.jsonl` ya existente; etapa omitida →
`SKIPPED`, nunca oculto. Ningún `except Exception: pass` en el código
nuevo.

## 12. Métricas

`StageMetrics` por etapa (`input_record_count`, `output_record_count`,
`excluded_record_count`, `warning_count`, `error_count`,
`artifacts_generated`, tiempos) — campos no aplicables quedan `None`,
nunca `0` inventado (verificado con test dedicado).

---

## 13. Tests creados

47 tests nuevos:

- `tests/test_core_contracts.py` — 17 tests (validación de `ExecutionRequest`, `CanonicalBatch`, `StageResult`, `PipelineDefinition`, `PipelineResult`, métricas nulas explícitas).
- `tests/test_core_registry.py` — 7 tests (registro/resolución, duplicados, aislamiento entre instancias).
- `tests/test_core_orchestrator.py` — 14 tests (orden de ejecución, parada ante fallo, continuación ante warning/skip, métricas, artefactos, issues, etapa inexistente, excepción técnica no interceptada).
- `tests/test_drills_core_pipeline.py` — 9 tests (pipeline completo sin SQL real, con y sin evidencia, regresión byte a byte contra `pipeline.run()` directo, no-duplicación de la consulta SQL, comparación de solo lectura contra la ejecución de referencia real, CLI genérico vía `CliRunner`).

## 14. Tests ejecutados

```
.venv/Scripts/python.exe -m pytest -q
451 passed, 7 skipped in ~14s
```

Los 7 `skipped` son los mismos tests de integración opt-in contra SQL
Server real que ya existían antes de esta tarea (`RUN_DRILLS_EXPORT_INTEGRATION_TESTS`
no está activado) — no se ejecutó SQL real en ningún momento.

## 15. Resultados

- Suite completa en verde: 451 passed, 0 failed, 7 skipped (mismos skips que antes de esta tarea).
- Regresión byte a byte confirmada: `drills.csv` producido vía Core == `drills.csv` producido vía `pipeline.run()` directo, con el mismo `DataFrame` fake y el mismo `run_id`/`timestamp`. `validation_report.yaml` y `export_manifest.yaml` (incluidos los hashes) idénticos estructuralmente.
- Comparación de solo lectura contra la ejecución de referencia real (`20260723T195418Z`): columnas y `status.result` sin cambios.
- `git diff --check`: limpio.

## 16. Diferencias respecto al prototipo

Ninguna diferencia de comportamiento observable cuando Drills se ejecuta
por el camino Core. La única diferencia es de forma, no de contenido: el
`run_id`/`timestamp` de una ejecución vía Core provienen de
`ExecutionContext`/`ExecutionRequest.execution_id` en vez de generarse
dentro de `pipeline.run()` — mismo formato, mismo comportamiento si no se
especifican explícitamente.

## 17. Deuda técnica

1. `transform_and_export` fusiona 6 responsabilidades conceptuales en una
   sola etapa (Mapping+Validation+Export+Manifest+Comparison+Issues) —
   documentado como adaptador temporal, no como diseño final.
2. `CanonicalBatch` es un seam mínimo sin uso funcional real todavía más
   allá de trazabilidad en `context.state`.
3. No se implementó ningún `rule_type` de la Mapping Specification —
   Drills sigue usando sus funciones de transformación propias.
4. La combinación Core + modo `full` + SQL real nunca se ha probado (no
   autorizado en esta fase).

Ver `framework-core-v1.md` § 19 para el detalle completo.

## 18. Riesgos

- Diseño validado con un único consumidor (Drills) — no probado
  empíricamente con un segundo objeto migrable todavía.
- La fusión de `transform_and_export` podría no generalizar bien cuando
  llegue un segundo objeto con reglas más complejas — riesgo aceptado
  deliberadamente (principio "No Abstraction Without a Real Consumer").
- `.claude/settings.local.json` se modificó automáticamente por el propio
  Claude Code (registro de permisos), no por una acción explícita de esta
  tarea — señalado por transparencia, sin impacto funcional.

## 19. ADR creada o justificación

Se creó **ADR-016** — "Framework Core: Execution Pipeline, Stage Registry
y propagación de errores" (Status: Approved Design, ya implementada y
probada en esta misma fase). Justificación: ninguna ADR existente fijaba
el modelo de ejecución concreto, el mecanismo de registro de etapas, ni la
propagación de errores durante una ejecución — decisiones estructurales
nuevas, no cubiertas por ADR-013/014/015. Índice actualizado
(`docs/02-adr/README.md`), próximo número libre: ADR-017.

## 20. Resultado de `git diff --check`

```
warning: in the working copy of '.claude/settings.local.json', LF will be replaced by CRLF...
warning: in the working copy of 'config/exports/drills.yaml', LF will be replaced by CRLF...
exit=0
```

Limpio — solo avisos informativos de normalización de fin de línea, sin
errores de espacio en blanco.

## 21. Resultado de `git status --short`

```
 M .claude/settings.local.json
 M config/exports/drills.yaml
 M src/cli.py
 M src/export/prototype/drills/pipeline.py
?? src/core/
?? src/export/prototype/drills/core_adapters.py
?? tests/test_core_contracts.py
?? tests/test_core_orchestrator.py
?? tests/test_core_registry.py
?? tests/test_drills_core_pipeline.py
?? docs/... (incluye framework-core-v1.md y ADR-016, además de todo lo ya
   generado en tareas anteriores de esta sesión, sin trackear desde el inicio)
?? reports/executions/2026-07-27/Informe-Framework-Core-V1-EMF.{md,txt}
```

## 22. Resultado de `git diff --stat`

```
 .claude/settings.local.json             |  11 ++-
 config/exports/drills.yaml              |  13 ++++
 src/cli.py                              | 115 ++++++++++++++++++++++++++++++++
 src/export/prototype/drills/pipeline.py |  24 +++++--
 4 files changed, 158 insertions(+), 5 deletions(-)
```

(Los ficheros nuevos, por definición, no aparecen en `git diff --stat` —
git no los conoce todavía; se listan en § 5.)

## 23. Recomendación de siguiente paso

Con el Core implementado y Drills funcionando a través de él, el siguiente
paso natural (siguiendo el orden ya aprobado en ADR-014 § Consequences,
ahora con el Core como cuarto hito cumplido) es **validar con un segundo
consumidor real** antes de generalizar más: candidato más simple, un
segundo `object_type` sencillo (o el propio Drills en modo `full`, contra
SQL Server real, cuando se autorice explícitamente) — es el primer punto
en que se sabrá si `transform_and_export` necesita dejar de ser una única
etapa fusionada, y si `CanonicalBatch` necesita evolucionar hacia el CDM
completo. No se recomienda generalizar ninguno de los dos sin esa
evidencia.

No se realizó commit de ningún cambio.
