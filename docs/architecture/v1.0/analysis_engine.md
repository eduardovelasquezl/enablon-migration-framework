# Analysis Engine

Los seis componentes del Knowledge Engine. Todos con **Status: Implemented**,
con tests en `tests/`.

## `query_analyzer.py`

**Qué hace**: revisión estática de una query `.sql` (JOIN, WHERE activo/comentado,
columnas de entidad conocidas) y, además, extracción sintáctica de las
expresiones del `SELECT` (posición, expresión original, alias, si es calculada,
funciones usadas, columnas referenciadas, wildcard, tabla origen resuelta cuando
no hay ambigüedad).

**Qué no hace**: no ejecuta la query, no se conecta a ningún servidor, no infiere
significado funcional de una expresión calculada, no resuelve subqueries/CTE en
profundidad (los detecta y avisa).

**Qué consume**: el texto de un fichero `.sql`.

**Qué produce**: `QueryReview` (revisión estructural) y `SelectParseResult`
(lista de `SelectExpressionInfo` + alias de tabla).

Internamente delega en `_select_parser.py` (privado, no importar directamente
fuera de este módulo).

## `schema_analyzer.py`

**Qué hace**: inventaría las hojas de un ETL Excel (tipo, tamaño, si son
huérfanas conocidas) y clasifica cada hoja/sección según una taxonomía de 18
categorías (mapeo de campo, catálogo de referencia de Enablon, tabla de
equivalencias, regla de transformación, exclusiones, vista previa de CSV,
datos origen, auxiliar, pendiente de clasificar...), pudiendo devolver más de
una clasificación para una misma hoja física cuando hay secciones lógicas
superpuestas.

**Qué no hace**: no modifica ni renombra el Excel original, no fuerza una
clasificación cuando no hay señal suficiente (queda `pending_classification`).

**Qué consume**: la ruta de un `.xlsx`/`.xlsm`.

**Qué produce**: `EtlInventory`/`SheetInfo` (inventario) y
`list[SheetClassification]` por hoja.

Internamente delega en `_sheet_taxonomy.py` (privado).

## `mapping_resolver.py`

**Qué hace**: resuelve el destino XML real de cada fila de una hoja de mapeo de
campo (patrón `CampoOrigen | ... | Field Destiny ES | ... | XML | ES`),
construyendo explícitamente el catálogo ES→XML a partir de TODAS las filas de
las columnas de referencia — nunca leyendo la columna de fórmula ni una
posición fija de fila.

**Qué no hace**: no elige silenciosamente una coincidencia ambigua (etiqueta ES
duplicada con XML distintos → `ambiguous`), no inventa un destino cuando no hay
correspondencia exacta (→ `unresolved`), no toca `read_field_mapping_sheet()`
(la función anterior, con el defecto ya documentado, sigue intacta para
compatibilidad).

**Qué consume**: una hoja de Excel (ruta + nombre de hoja).

**Qué produce**: `list[ResolvedFieldMapping]`, cada uno con
`resolution_status` (`resolved_exact`/`unresolved`/`ambiguous`/
`missing_destination`/`invalid_row`) y `resolution_method`.

## `mapping_coverage.py`

**Qué hace**: clasifica cada clave real (simple o compuesta) frente a una tabla
de equivalencias en una de cuatro situaciones — correspondencia válida, "No
migra" documentado, sin correspondencia y sin fallback (bloqueado), o sin
correspondencia con fallback documentado — y genera los 7 informes de
diagnóstico (`unmapped_entities.csv`, `unmapped_field_values.csv`,
`records_marked_no_migrate.csv`, `records_with_mapping_fallback.csv`,
`records_blocked_by_mapping.csv`, `mapping_summary.csv`,
`client_mapping_questions.xlsx`).

**Qué no hace**: nunca convierte una ausencia de correspondencia en NULL, vacío,
"No migra" o un valor por defecto no documentado; nunca decide `mapping_scope`
por una lista fija de nombres de campo (lo determina la evidencia de la
definición del mapping).

**Qué consume**: `MappingDecision` + `MappingCoverageFinding` ya construidos
(unidos vía `CoverageRow`) — nunca genera las 7 salidas desde `MappingDecision`
sola.

**Qué produce**: los 7 ficheros de diagnóstico, en `utf-8-sig`.

## `module_analysis.py`

**Qué hace**: dentro de un módulo, detecta candidatos a Action Plans, valida sus
campos (reutilizando `mapping_resolver.py`/`mapping_coverage.py` como insumo
externo, no los reimplementa) y produce entradas de
`CrossModuleActionPlanBuffer`.

**Qué no hace** (contrato duro, verificado en tests): nunca produce
`processing_status=ready_for_final_load`; nunca genera ningún CSV; nunca
resuelve una relación por coincidencia parcial; nunca sustituye un padre
ausente por un registro histórico no documentado; nunca convierte una acción
`linked_action_plan` en `standalone_action_plan` por no encontrar su padre.

**Qué consume**: `ActionPlanCandidate` + `FieldValidationResult` (ya calculados
fuera de este módulo).

**Qué produce**: `list[CrossModuleActionPlanBuffer]`, en estados que van hasta
`waiting_for_parent`/`validated`/`blocked`/`excluded` — nunca más allá.

## `project_analysis.py`

**Qué hace**: orquesta el proyecto completo — ejecuta o integra los resultados
de `module_analysis.py` por módulo (en el orden declarado), consolida el buffer
transversal de todos los módulos (deduplicando por una clave configurable,
nunca solo por `action_plan_historical_id`), resuelve referencias de padre
entre módulos, y — únicamente si ningún módulo del alcance declarado quedó sin
analizar— finaliza Action Plans (`ready_for_final_load`).

**Qué no hace**: no reimplementa `module_analysis.py`/`mapping_resolver.py`/
`mapping_coverage.py`/`query_analyzer.py`/`schema_analyzer.py`, los reutiliza;
no fusiona duplicados por similitud (título/descripción/fecha); no bloquea las
acciones ya resueltas de un módulo por un problema de otro módulo no
relacionado; no sobrescribe una ejecución anterior (usa `analysis_run_id`).

**Qué consume**: `ProjectAnalysisRequest` (módulos ya resueltos o pendientes de
ejecutar, orden de ejecución, índice de referencias de padre, clave de
deduplicación).

**Qué produce**: `ProjectAnalysisResult` y, si `generate_outputs=True`, las 14
salidas descritas en [`export_engine.md`](export_engine.md) — que son informes
de análisis/readiness, no el CSV de importación a Enablon.
