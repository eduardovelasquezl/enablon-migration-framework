# Roadmap

Basado únicamente en las fases ya aprobadas a lo largo del proyecto — no se
añade ninguna funcionalidad nueva no discutida previamente.

## Phase 1 — Knowledge Engine
**Status: Implemented**

Análisis de SQL/ETL, resolución de mappings, clasificación de cobertura,
modelo de dominio normalizado (catálogo/relaciones/evidencia). Ver
[`analysis_engine.md`](analysis_engine.md), [`domain_model.md`](domain_model.md).

## Phase 2 — Project Analysis
**Status: Implemented**

Análisis por módulo (`module_analysis.py`), orquestación global
(`project_analysis.py`), Action Plans como objeto transversal de fase final,
cobertura global del proyecto.

## Phase 3 — Export Engine
**Status: Approved Design**

`ExportPlan`, `ExportDefinition`, CSV Generator/Writer/Validator, `ExportPackage`
y su `Manifest`. Ver [`export_engine.md`](export_engine.md). Pendiente de
plantillas de importación de Enablon validadas por el cliente, objeto por
objeto.

## Phase 4 — Validation
**Status: Planned**

QA formal del CSV generado por el Export Engine contra la plantilla real de
Enablon (`CSV Validator`, ya anticipado en el diseño de Fase 3) y cualquier
validación adicional de calidad de datos que no quede cubierta por
`mapping_coverage.py`/`Validation` (ya implementados en Fase 1).

## Phase 5 — Repository
**Status: Planned**

Persistencia definitiva del Knowledge Repository (hoy, todo vive en memoria
durante una ejecución y se descarta, salvo lo que se escribe explícitamente a
`outputs/`). Incluiría el almacenamiento normalizado catálogo/relaciones/
evidencia descrito en [`knowledge_repository.md`](knowledge_repository.md) de
forma duradera entre ejecuciones.

## Phase 6 — Versioning
**Status: Planned**

Motor de versionado de evidencia y decisiones (detectar archivo idéntico /
modificado / nuevo / evidencia retirada / conflicto entre versiones) —
diseñado conceptualmente en incrementos previos (campos `valid_from`/
`valid_to`/`supersedes_decision_id` ya reservados en `MappingDecision`), pero
sin motor implementado. Introduciría `schema_version` como concepto real (ver
`README.md`).

## Phase 7 — AI Assistant
**Status: Planned**

Fase final del roadmap aprobado. Sin diseño detallado todavía.

## Elementos sin fase asignada

`API` y `UI` se han mencionado como fuera de alcance en incrementos previos,
pero no tienen una fase numerada asignada en el roadmap aprobado — se
documentan en [`project_status.md`](project_status.md) como pendientes, sin
comprometerlos a ninguna de las 7 fases anteriores.
