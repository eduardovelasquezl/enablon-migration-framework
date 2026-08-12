# Knowledge Coverage Matrix — EMF / Drills

**Status:** Implemented (auditoría), basada exclusivamente en código y
documentación ya versionados (`src/`, `config/`, `docs/`, `tests/`). Ningún
ETL, CSV real, SQL Server o BAK fue consultado para producir este
documento — ver `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md`
para el alcance completo de esta auditoría (Sprint 8.1).

## Objetivo de este documento

Responder, con evidencia verificable en el repositorio (no estimación), a
si el EMF puede explicar completamente cómo construye el CSV final de
Drills sin consultar los ETL originales. La matriz de esta sección es el
insumo cuantificable de esa respuesta; la síntesis completa vive en el
informe de ejecución de esta auditoría.

## 1. Matriz de cobertura

| Área | Implementado | Fuente | Evidencia | Estado |
|---|---|---|---|---|
| Query SQL | Extracción de solo lectura de una única tabla, sin joins, con hash de integridad y límite de filas aplicado en modo `sample` | `src/export/prototype/drills/extractor.py::extract_drills`, `sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql` | Ejecución real confirmada 2026-07-23 (`outputs/prototype/drills/20260723T195418Z/`, `status.result: SUCCESS`); hash `sql_sha256` registrado en `export_manifest.yaml` | **IMPLEMENTADO** |
| Canonical Data Model | Diseño conceptual completo (entidades, identidad, provenance, issues); `CanonicalBatch` es un seam mínimo (DataFrame + metadatos de lote), no el CDM completo por fila | `docs/01-architecture/canonical-data-model.md` (Status: Proposed), `src/core/contracts.py::CanonicalBatch`, `core_adapters.py::DrillsCanonicalizeStage` | `canonical-data-model.md` § 0 confirma explícitamente: "No existe hoy un tipo de registro normalizado real"; `DrillsCanonicalizeStage` deja pasar la `ExtractionResult` original sin transformarla | **PENDIENTE** (diseño *Proposed*, sin implementación de `CanonicalRecord`/`CanonicalField`/`Provenance` por fila) |
| Mapping | 7 reglas de campo (una función pura por regla) ejecutables y testeadas contra datos reales; el Mapping Model formal (`MappingSet`/`MappingRule`, 12 `rule_type`) es diseño conceptual sin motor | `config/exports/drills.yaml` (`fields`), `src/export/prototype/drills/transformations.py`, `mappings.py`; `docs/01-architecture/mapping-specification.md` (Status: Proposed) | `framework-core-v1.md` § 16: *"no se implementa ningún `rule_type` de la Mapping Specification — Drills no lo necesita todavía"* | **IMPLEMENTADO PARCIALMENTE** (ejecutable y suficiente para Drills; el motor genérico no existe) |
| Lookup | 3 tablas estáticas (`typology_lookup` 15 filas, `letter_lookup` 7 filas, `workflow_status_lookup` 4 filas) + 1 catálogo dinámico (`entity_catalog`, 681 filas) | `config/exports/drills.yaml::reference_data`, `transformations.py::resolve_typology/resolve_letter/resolve_workflow_status`, `mappings.py::resolve_entity` | Ejecución real: 93/100 entidades resueltas, 5 `do_not_migrate`, 2 `empty`, 0 `unresolved`/`conflicting` (`validation_report.yaml` de la corrida 2026-07-23) | **IMPLEMENTADO** |
| Transformaciones | `build_reference`, `parse_starting_date`/`format_starting_date`, `to_historical_id`, resolución de tipología/letra/estado — funciones puras, testeadas de forma aislada | `transformations.py` | `tests/test_drills_export_prototype.py` (28 tests unitarios sobre estas funciones) | **IMPLEMENTADO** |
| Template Contract | 8 de 36 columnas reales implementadas; 26 de las 28 restantes excluidas con motivo documentado (`excluded_columns`); 2 columnas (`EstimatedLoss`, `RealLoss`) sin entrada en `fields` NI en `excluded_columns` | `config/exports/drills.yaml` (`fields` + `excluded_columns`), `docs/01-architecture/drills-csv-contract.md` (este Sprint) | Ver `drills-csv-contract.md` § 3 para el detalle exacto de la brecha de 2 columnas | **IMPLEMENTADO PARCIALMENTE** |
| Validation | Pre-escritura (columnas fuente, DataFrame no vacío) y post-escritura (encoding/BOM/cabecera/filas/patrón de `Reference`/reabribilidad con pandas) implementadas y testeadas; el catálogo transversal `data_quality_checks` (6 reglas) no está conectado a ningún motor ejecutable | `src/export/prototype/drills/validator.py`; `config/validation_rules.yaml::data_quality_checks` | `drills-operational-mvp.md` § 8 confirma las validaciones activas; `config/validation_rules.yaml` no tiene ningún consumidor en `src/` (verificado por `Grep` sin resultados fuera del propio YAML) | **IMPLEMENTADO PARCIALMENTE** |
| Comparison | Comparación estructural + celda a celda contra un CSV histórico real, opcional, resuelta vía `DataWorkspace` desde Sprint 7 | `src/export/prototype/drills/comparison.py::build_comparison_report` | Ejecutado realmente en la corrida 2026-07-23 (`comparison_report.yaml` generado contra `Drills-22072026-41.csv`) | **IMPLEMENTADO** |
| Evidence | Generación de `evidence_internal.xlsx`/`evidence_client.xlsx` a partir de artefactos ya escritos, nunca vuelve a tocar SQL Server | `src/evidence/collector.py`, `src/evidence/workbook.py`, `core_adapters.py::DrillsEvidenceStage` | Ejecutado realmente en la corrida 2026-07-23 (ambos ficheros listados en `drills-operational-mvp.md` § 0) | **IMPLEMENTADO** |
| Catálogos | Catálogo de entidad de Simulacros (`entidades_mapeo_ANTIGUO_referencia_historica.csv`, 681 filas) cargado, cacheado e indexado en memoria; catálogos vigentes (`First_Axis`) explícitamente no aplicables a este objeto | `mappings.py::load_entity_catalog/get_entity_catalog`; `CLAUDE.md` ("Simulacros no lo necesita") | `test_drills_export_prototype.py::test_catalogo_real_del_repositorio_carga_sin_conflictos_conocidos` | **IMPLEMENTADO** |
| Campos estándar | 2 de los ~11 campos no-`CS_` del CSV real implementados (`Reference`, `StartingDate`); no existe un vocabulario/registro formal que distinga "campo estándar" de `CS_*` en código — la distinción es solo documental | `config/exports/drills.yaml::fields`; `docs/07-developer-guide/local-data-recovery-checklist.md` § 6 | Ver `drills-csv-contract.md` § 2 | **IMPLEMENTADO PARCIALMENTE** |
| Campos CS_ | 6 de 25 campos `CS_*` reales implementados con contrato completo; 19 excluidos explícitamente con motivo; 0 sin contrato en absoluto | `config/exports/drills.yaml::fields` + `excluded_columns` | Ver `knowledge-traceability-matrix.md` y respuestas de Fase 5 en el informe de ejecución | **IMPLEMENTADO PARCIALMENTE** |
| Outputs | Escritura atómica de CSV, `validation_report.yaml`, `export_manifest.yaml` (con hashes), `issues.jsonl` — todos verificados en una ejecución real | `exporter.py::write_csv`, `manifest.py` | Ejecución real 2026-07-23, artefactos listados en `drills-operational-mvp.md` § 7 | **IMPLEMENTADO** |
| Workspace | Resolución de rutas de datos externos por proyecto/categoría, sin credenciales, sin fallback a `inputs/`, con protección de escape — validado este mismo Sprint contra una estructura real (vacía) | `src/core/data_workspace.py`, `config/data_workspace.yaml` | Sprint 8, Fase 4: 9/9 categorías de `moeve` resueltas correctamente, escape rechazado, proyecto desconocido rechazado (validación ejecutada en este mismo repositorio) | **IMPLEMENTADO** |

## 2. Lectura de la matriz

De las 14 áreas evaluadas: **8 IMPLEMENTADO**, **5 IMPLEMENTADO
PARCIALMENTE**, **1 PENDIENTE** (Canonical Data Model), **0 NO APLICA**.

Ninguna área queda en blanco por falta de evidencia — cada estado se apoya
en una ejecución real (`outputs/prototype/drills/20260723T195418Z/`), un
test automatizado, o una declaración explícita del propio código/documento
fuente (nunca una inferencia sin verificación directa).

Sin porcentajes en este documento — ver
`reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md` § 7 para la
cobertura razonada por área, que sí construye una valoración cualitativa
apoyada en esta matriz.
