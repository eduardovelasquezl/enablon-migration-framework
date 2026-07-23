# Modelo de dominio

Todas las entidades viven en `src/knowledge_base/model.py`, salvo las propias de
la orquestación de módulo/proyecto (`module_analysis.py`, `project_analysis.py`),
que se documentan igual pero se señalan aparte. Esta página es una explicación
funcional — para la forma exacta de cada campo, leer el propio código
(deliberadamente no se duplica aquí).

**Status de todo lo listado: Implemented**, salvo que se indique lo contrario.

## Principio estructural: tres capas que nunca se mezclan

1. **Catálogo** — entidades de existencia pura ("qué existe"): `Module`,
   `SourceObject`, `MigrationObject`, `Mapping`, `CSVSchema`... Ninguna lleva
   claves foráneas embebidas hacia otra entidad.
2. **Relaciones** — aristas tipadas entre IDs de catálogo (`Relation`), "cómo se
   relaciona". Vive aparte, nunca embebida en el catálogo.
3. **Evidencia** — procedencia de un hecho de catálogo o de una relación
   (`Evidence`), "por qué lo sabemos". Puede haber varias evidencias para el
   mismo hecho, incluso contradictorias entre sí.

## Entidades centrales

### `MigrationObject`
Objeto funcional granular dentro de un módulo — p. ej. dentro del módulo
"eventos": `Events`, `Impacts`, `Investigations`, `PSM Forms` son cuatro
`MigrationObject` distintos del mismo módulo. Existe para poder tratar un módulo
compuesto como un único módulo funcional sin perder la distinción entre sus
objetos internos. Lleva `processing_scope` (`module` | `cross_module`) y
`load_phase` (`normal` | `final`) — hoy, solo Action Plans es
`cross_module`/`final`. Ver [ADR-001](decisions/ADR-001-migration-object-centric-model.md)
y [ADR-003](decisions/ADR-003-action-plans-cross-module.md).

### `Relation`
Arista tipada entre dos IDs de catálogo (`subject_id` → `relation_type` →
`object_id`), con su propio `resolution_status` (independiente del de cualquier
entidad que relacione) y su propia lista de evidencias. Ejemplos de
`relation_type`: `functional_hierarchy` (con `order`),
`action_plan_object_depends_on_migration_object` (con `dependency_scope` y
`source_idorigenac_values`).

### `MappingDecision`
Decisión **estable** sobre una clave (simple o compuesta) frente a una tabla de
equivalencias: `mapped`, `do_not_migrate`, `fallback_value`, `pending_mapping`,
`default_value`, `conflicting` o `not_applicable` (`decision_type`), cruzado con
`mapping_status` y `load_status`. **No contiene recuentos ni ejemplos de
registro** — eso es responsabilidad de `MappingCoverageFinding`. Regla dura que
encierra: ninguna ausencia de correspondencia puede convertirse en NULL, vacío,
"No migra" o un valor por defecto no documentado (`validate_mapping_decision_
consistency` la hace cumplir). Ver [ADR-002](decisions/ADR-002-mapping-decision-vs-coverage-finding.md).

### `MappingCoverageFinding`
Resultado **observado** de aplicar una `MappingDecision` en una corrida de
análisis concreta, sobre un snapshot de datos concreto (un BAK/freeze). Aquí sí
viven `affected_record_count` y `example_historical_ids`. La separación permite
que la misma decisión produzca resultados distintos en corridas distintas sin
reescribir la decisión en sí.

### `CrossModuleActionPlanBuffer`
Estructura de **trabajo transitoria**, no de catálogo — representa una acción
candidata a Action Plans mientras se consolida entre módulos. Produce entidades
de catálogo (o se descarta) solo cuando termina de resolverse. Separa
`relationship_status` (estado de la evidencia de la relación con el objeto
origen) de `processing_status` (estado operativo del workflow:
`discovered` → `validated`/`waiting_for_parent` → `parent_resolved` →
`ready_for_final_load`, o `blocked`/`excluded` en cualquier punto). Distingue
`linked_action_plan` (depende de un objeto padre) de `standalone_action_plan`
(no depende de nadie, pero igualmente espera a la fase final). Ver
[ADR-003](decisions/ADR-003-action-plans-cross-module.md) y
[ADR-004](decisions/ADR-004-exact-parent-resolution.md).

### `ModuleAnalysisResult`
Resultado del análisis de un único módulo (producido por `module_analysis.py`,
o proporcionado ya calculado a `project_analysis.py`): sus
`CrossModuleActionPlanBuffer`, sus `MigrationObject`, sus `Validation`/
`OpenQuestion`, y — si aplica — sus valores `idorigenac` sin clasificar y sus
relaciones de dependencia pendientes. Vive en `project_analysis.py`, no en
`model.py` (es un contrato de orquestación, no una entidad de catálogo estable).

### `ProjectAnalysisResult`
Resultado de orquestar el proyecto completo: todos los `ModuleAnalysisResult`,
el buffer transversal ya consolidado y finalizado, la cobertura global
(`ActionPlanGlobalCoverage`), el resumen de ejecución y las rutas de salida (si
se generaron). Vive en `project_analysis.py`.

### `Validation`
Comprobación de calidad de datos documentada (equivalente estructurado a
`config/validation_rules.yaml → data_quality_checks`): qué comprueba y qué
acción corresponde si falla. Nunca corrige el dato por sí sola, solo reporta.

### `Warning`
**No es una clase propia** — es un patrón estructural: un campo `warnings:
list[str]` presente en casi toda entidad/resultado del framework
(`MappingDecision`, `CrossModuleActionPlanBuffer`, `Relation` vía `notes`,
`ProjectAnalysisResult`...). Se documenta aquí como concepto porque el propio
incremento lo pide, pero no debe buscarse una clase `Warning` en el código
—no existe, y no hace falta que exista.

### `OpenQuestion`
Pregunta pendiente de respuesta humana sobre uno o más elementos del modelo
(`affected_entity_ids`), con su propio `status` (`open`/`resolved`). Es el
mecanismo formal para "no decidir automáticamente" cuando dos fuentes
autoritativas discrepan.

## Entidades de apoyo (catálogo físico y de Enablon)

Documentadas en conjunto por brevedad — cada una es una entidad de existencia
pura, sin relaciones embebidas: `Module`, `SourceSystem`, `SourceObject`,
`SourceField` (estructura física real del SQL de origen); `Query`,
`SelectExpression` (una query y sus columnas SELECT analizadas); `ETLWorkbook`,
`ETLSheet` (un libro Excel y sus hojas); `Mapping` (una fila de mapeo de campo ya
resuelta); `MigrationRule` (regla documentada — transformación, exclusión,
fallback, default o validación, con `rule_kind`); `EntityMapping` (equivalencia
de entidad origen↔Enablon); `EnablonObject`, `EnablonField` (catálogo de
destino); `CSVSchema`, `CSVColumn` (estructura de un CSV real observado);
`KnownError` (incidencia documentada del cliente); `FunctionalDecision`
(decisión de negocio documentada, p. ej. una exclusión "No migra").

## Entidades de apoyo de la orquestación (viven en `project_analysis.py`)

`ProjectAnalysisRequest`, `ModuleRequest`, `ModuleExecutionSpec`,
`ParentResolutionInput` (modelo de entrada); `ActionPlanConsolidationResult`,
`ActionPlanGlobalCoverage` (resultados intermedios de la consolidación
transversal). Ver [`analysis_engine.md`](analysis_engine.md) para su rol exacto
en el flujo.

## Relaciones principales

```
Module 1───N MigrationObject
MigrationObject 1───N Mapping (vía ETLSheet)
MigrationObject ──Relation(functional_hierarchy)──> MigrationObject (padre-hijo)
MigrationObject(Action Plans) ──Relation(action_plan_object_depends_on_migration_object)──> MigrationObject (módulo que genera acciones)
MappingDecision 1───N MappingCoverageFinding (misma decisión, corridas distintas)
CrossModuleActionPlanBuffer ──(tras consolidar/resolver/finalizar)──> insumo de ProjectAnalysisResult
Evidence N───1 (cualquier entidad de catálogo O cualquier Relation)
OpenQuestion N───N (cualquier entidad, vía affected_entity_ids)
```
