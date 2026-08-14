# Sprint 9.6 — Minimal Export Engine Extraction

**Refactor behavior-preserving.** Cero funcionalidad de negocio nueva, cero
SQL real, cero `full`, cero implementación de Safety Meetings, cero
resolución del Entity de Bypass, cero cambio de mappings, cero multi-object,
cero Field Constraints, cero UI. **Cero cambios en `src/core/`.** Sin
commit, sin push — a la espera de autorización explícita.

---

## Fase 0 — Preflight

- Rama: `feature/drills-filtered-exports`. Commit `e5f8a91` presente
  (`git log --oneline -10` confirmado).
- `git status --short` (antes de tocar código): solo `.claude/settings.local.json`
  y `reports/executions/2026-08-14/` (informes de Sprint 9.5/9.5.1, sin
  datos reales). `git diff --check`: sin marcadores de conflicto.
- Baseline: **775 passed, 7 skipped**.
- `workspace.yaml` real, `.env`, `.claude/settings.local.json`: confirmados
  fuera de Git (ninguno aparece en `git status` como nuevo/staged salvo el
  `.local.json` ya excluido de commits desde Sprint 9.5).

## Fase 1 — Inventario reconciliado (la discrepancia "5 de 7" vs. "6 capacidades")

**Resuelto, con código como fuente de verdad, no la numeración del informe
anterior:**

| # | Pieza (Sprint 9.4, `DUPLICATED_FROM_DRILLS`) | Drills file | Bypass file | Clasificación Sprint 9.5.1 | ¿Extraer ahora? |
|---|---|---|---|---|---|
| 1 | `pipeline.py` (orquestación completa) | `drills/pipeline.py` (687 líneas, 6 responsabilidades) | `bypass/pipeline.py` (238 líneas, 3 responsabilidades) | WAIT_FOR_THIRD_MODULE | **No** |
| 2 | `extractor.py` (forma) | `drills/extractor.py` | `bypass/extractor.py` | EXTRACT_NOW | **Sí** |
| 3 | `core_adapters.py` (Stages + factory) | `drills/core_adapters.py` (4 stages) | `bypass/core_adapters.py` (2 stages, subconjunto) | **Mixta** -- ver abajo | **Parcial** |
| 4 | `config.py` (loader) | `drills/config.py` | `bypass/config.py` | EXTRACT_NOW | **Sí** |
| 5 | `manifest.py` (RunStats + builders) | `drills/manifest.py` | `bypass/manifest.py` | EXTRACT_NOW (núcleo) | **Sí (núcleo)** |
| 6 | `validator.py` (`validate_output_csv`) | `drills/validator.py` | `bypass/validator.py` | EXTRACT_NOW (núcleo) | **Sí (núcleo)** |
| 7 | `_is_missing()` (~10 líneas) | `drills/transformations.py` | `bypass/transformations.py` | EXTRACT_NOW | **Sí** |

**La discrepancia explicada:** la pieza #3 (`core_adapters.py`) no es
uniforme por dentro -- contiene DOS stages con evidencia muy distinta:

- **`Query Stage`** (`DrillsQueryStage`/`BypassQueryStage`): casi línea a
  línea idéntica (cargar config → `context.state` → compilar filtros →
  extraer → `StageResult`). **Esto SÍ se extrae** -- es la "6ª capacidad"
  que el resumen de Sprint 9.5.1 nombraba por separado de "`core_adapters.py`"
  en general.
- **`Transform/Export Stage`** (`DrillsTransformExportStage`/
  `BypassTransformExportStage`): envuelve `pipeline.run()` completo -- NO
  se extrae (mismo motivo que la pieza #1: Drills todavía no tiene una 2ª
  forma real de Mapping/Validation/Export/Manifest desacoplados).

**Número correcto: de las 7 piezas originales, 5 tienen extracción completa
de bajo riesgo (#2, #4, #5-núcleo, #6-núcleo, #7), 1 se divide en dos mitades
con destino distinto (#3: Query Stage sí, Transform/Export Stage no), y 1
queda intacta (#1).** El "5 de 7" y las "6 capacidades" del informe de
Sprint 9.5.1 describían la MISMA conclusión desde dos ángulos distintos
(piezas completas vs. capacidades individuales) -- no eran contradictorios,
solo estaban expresados sin esta tabla explícita. Confirmado leyendo las
implementaciones reales antes de mover una sola línea, tal como exigía el
encargo.

## Fase 2 — Frontera del Engine

`src/export/engine/` (nuevo), 7 ficheros, 745 líneas:

```
src/export/engine/
├── __init__.py       (18 líneas -- solo docstring de la regla del paquete)
├── config.py          (138 líneas -- FieldSpec/OutputSpec/SourceSpec + load_export_config)
├── extractor.py        (128 líneas -- ExtractionResult + extract_via_sql)
├── values.py            (54 líneas -- to_native/is_missing)
├── manifest.py          (250 líneas -- hashing/git/atomic-write, BaseRunStats,
│                          determine_status, build_*_section, build_query_filters_section)
├── validator.py          (71 líneas -- CsvStructureResult + validate_csv_structure)
└── query_stage.py        (86 líneas -- QueryStageSpec + GenericQueryStage)
```

Verificado por 2 tests arquitectónicos nuevos (`tests/test_export_engine.py`):
- `test_engine_no_importa_drills_ni_bypass`: ningún fichero de `engine/`
  importa nada de `src.export.prototype.*`.
- `test_engine_no_tiene_condicionales_por_module_id`: análisis AST (no texto
  crudo, para no confundir con docstrings) -- ningún `ast.Compare` del
  Engine compara contra un literal `"drills"`/`"bypass"`/otro `module_id`
  conocido.

Ningún fichero del Engine contiene SQL, nombres de tabla, mappings, lookup
catalogs, reglas de negocio, Project Contract ni `excluded_columns` -- toda
la diferenciación entre Drills y Bypass llega por parámetros
(`SourceSpec`, `query_runner`, `sort_column`, `QueryStageSpec`).

## Fase 3 — Config loader

`load_export_config(config_file: str, container_cls: type[T]) -> T`
(`engine/config.py`) reemplaza el cuerpo ~95% idéntico de
`load_drills_config`/`load_bypass_config`. `DrillsExportConfig`/
`BypassExportConfig` se conservan como dataclasses propias (mismo nombre,
mismos campos) -- solo delegan la construcción, no se fusionan en una única
clase, para no romper ningún `isinstance`/tipo esperado por callers
existentes. `FieldSpec`/`OutputSpec`/`SourceSpec` se movieron (no se
duplicaron) a `engine/config.py`; `drills.config`/`bypass.config` las
re-exportan vía import -- `tests/test_export_engine.py::test_drills_y_bypass_usan_las_mismas_dataclasses_de_config`
confirma que son el MISMO objeto, no clases equivalentes por casualidad.

Compatibilidad: `load_drills_config()`/`load_bypass_config()` conservan su
firma (cero args) y tipo de retorno exactos. 5 tests unitarios nuevos.

## Fase 4 — Extractor genérico

`extract_via_sql(source, *, query_runner, mode, limit, compiled_filters, sort_column)`
(`engine/extractor.py`). Conserva:

- **SQL Execution Guard**: sin cambios -- sigue viviendo en
  `src/db/connection.py::get_engine()`, nunca tocado por este refactor.
- **Query Engine / filtros parametrizados / server-side filtering**: sin
  cambios -- `compose_filtered_sql` se sigue llamando exactamente igual.
- **`sample` limit**: misma semántica exacta -- trunca localmente tras
  ejecutar la query completa, nunca un `TOP (n)` en SQL.
- **Composición SQL**: nunca se modifica el fichero `.sql` en disco, igual
  que antes.
- **`query_hash`/trazabilidad**: `sql_hash()` (antes `_sql_hash`), mismo
  algoritmo (`sha256` del texto).
- **Comportamiento de excepciones**: mismos `ValueError` con los mismos
  mensajes para modo inválido / límite no positivo.

**Constraint crítico descubierto y respetado:** varios tests existentes
hacen `monkeypatch.setattr(drills.extractor, "run_query", fake)` /
`monkeypatch.setattr(bypass.extractor, "run_query", fake)` -- si
`extract_via_sql` importara `run_query` directamente, ese monkeypatch
dejaría de tener efecto. Solución: `query_runner` se recibe como parámetro
en cada llamada; `drills/extractor.py`/`bypass/extractor.py` conservan su
propio `from src.db.query_runner import run_query` a nivel de módulo y lo
pasan explícitamente -- confirmado que los 8 tests que usan este patrón
siguen pasando sin cambios.

**Diferencia real preservada, nunca por `if module`:** Drills pasa
`sort_column=None` (su SQL ya tiene `ORDER BY`); Bypass pasa
`sort_column="FechaCreacion"` (su SQL no lo tiene). 5 tests unitarios
nuevos, incluyendo uno que verifica explícitamente que sin `sort_column` el
orden de origen se conserva, y otro que con `sort_column` sí se reordena
antes de truncar.

## Fase 5 — RunStats / Manifest core

`BaseRunStats` (`engine/manifest.py`): 17 campos idénticos en Drills y
Bypass antes de este refactor (`run_id`/`timestamp`/`mode`/
`connection_name`/`rows_*`/`warnings`/`errors`/`missing_historical_origin_id`/
`output_*`). `drills.manifest.RunStats`/`bypass.manifest.RunStats` ahora
EXTIENDEN `BaseRunStats` (herencia de dataclass, campos con default
preservando el orden) con sus propios campos -- `reference_*`/`entities_*`/
`dates_*` en Drills, `lookups_*` en Bypass. Ningún campo eliminado, ningún
manifest existente cambia de forma.

`build_run_section`/`build_counts_section`/`build_output_section`/
`build_connection_section`/`build_query_filters_section`: sub-diccionarios
de forma y valores ya idénticos, verificados literal contra literal antes de
extraer.

**`build_query_filters_section` -- hallazgo adicional de este sprint:**
vivía en `drills/manifest.py` y `bypass/pipeline.py` la importaba
DIRECTAMENTE de ahí (acoplamiento bypass → drills, no descrito
explícitamente en Sprint 9.4/9.5.1). Movida al Engine junto con las demás
-- ahora ningún módulo importa de otro módulo hermano para esto.

## Fase 6 — Validator core

`validate_csv_structure(path, expected_columns, output_spec) ->
CsvStructureResult` (`engine/validator.py`): núcleo extraído de
`bypass/validator.py::validate_output_csv`, que YA era, de las dos
implementaciones existentes, la forma correcta de un validador genérico
(recibe `OutputSpec`, no el config completo).

`bypass/validator.py::validate_output_csv` ahora es un wrapper de 6 líneas
que delega en el núcleo y traduce el resultado a su propia
`PostWriteValidation` (misma forma que antes).

`drills/validator.py::validate_output_csv` ENVUELVE el mismo núcleo con sus
propias comprobaciones de negocio (BOM, `expected_row_count`, columnas por
fila, patrón `Reference`, re-lectura con pandas) -- ninguna de estas se
movió al Engine (module-specific, confirmado que ninguna aplica a Bypass).
Se eliminó, además, un bloque de código sin ningún efecto observable que
existía en la versión original de Drills (un `try/except: pass` de
decodificación ASCII que nunca modificaba `result` ni el flujo -- verificado
por inspección antes de quitarlo, no una suposición).

**Hallazgo del estado de `determine_status` -- clasificado, NO corregido:**
Drills distingue 3 estados (`SUCCESS`/`SUCCESS_WITH_WARNINGS`/
`FAILED_VALIDATION`); Bypass, inline, solo 2 (`SUCCESS`/`FAILED_VALIDATION`,
sin distinguir warnings). `engine.manifest.determine_status` implementa la
lógica de 3 estados (la de Drills, sin cambios para Drills). **Bypass NO se
migra a esta función en este sprint** -- hacerlo le haría empezar a devolver
`SUCCESS_WITH_WARNINGS` en vez de `SUCCESS` cuando hay warnings, un cambio
de comportamiento observable no autorizado en un refactor
behavior-preserving. Clasificación: **A (diferencia accidental, no hay
ninguna decisión de diseño documentada que justifique 2 estados) Y C
(capability genérica que faltaba declarar) a la vez** -- no B. Queda
documentado en el docstring de `bypass/manifest.py` para que un sprint
posterior decida migrarlo explícitamente, en su propio commit, visible.

## Fase 7 — `_is_missing()`

Movida a `engine/values.py::is_missing`/`to_native`. **Hallazgo real, no
asumido:** la copia de Bypass (Sprint 9.4) decía en su propio comentario
"idéntica a la función privada `_is_missing` de `drills.transformations`" --
pero OMITÍA el paso `_to_native` (conversión de escalares numpy) que la de
Drills sí tiene. Verificado leyendo ambas antes de mover una línea. Se
conserva la versión de Drills (más completa) como la canónica -- no cambia
ningún resultado observable para los tipos reales que maneja este proyecto
(`numpy.float64`/`numpy.str_` ya son subclases de `float`/`str` en CPython),
pero cierra una laguna de robustez que la copia de Bypass tenía sin
saberlo. `drills/transformations.py` conserva `_is_missing`/`_to_native`
como alias privados (4 llamadas internas a `_to_native` en ese fichero, no
solo desde `_is_missing`, verificado antes de tocar nada).

Tests de borde añadidos (`test_is_missing_reconoce_todas_las_formas_de_ausencia`/
`test_is_missing_no_confunde_valores_reales_con_ausencia`): `None`, `NaN`
(float y `numpy.float64`), `pd.NA`, cadena vacía/solo espacios (ausentes) vs.
`0`, `1`, `"x"`, `"0"`, `numpy.int64(42)`, `False` (presentes) -- 13 casos.

## Fase 8 — Query Stage

`GenericQueryStage`/`QueryStageSpec` (`engine/query_stage.py`). Cada módulo
aporta `config_loader`/`state_key`/`filter_catalog`/`extract_fn` -- el
lifecycle (cargar → `context.state` → compilar filtros → extraer →
`StageResult`/`StageMetrics`) es idéntico al de `DrillsQueryStage`/
`BypassQueryStage` antes de este sprint. `register_drills_stages`/
`register_bypass_stages` ahora registran `GenericQueryStage(QueryStageSpec(...))`
en vez de una clase propia por módulo.

**No se creó un segundo sistema de plugins.** `ModuleAdapter` sigue siendo
`ModuleDefinition.pipeline_factory` (`src/core/module_registry.py`, sin
tocar) -- `GenericQueryStage` es un bloque que ese `pipeline_factory` ya
existente compone, no una abstracción nueva de nivel superior.

2 tests unitarios nuevos (lifecycle completo + compilación de filtros del
`ExecutionRequest`).

## Fase 9 — Migrar Drills

Migrado: `config.py`, `extractor.py`, `transformations.py` (`_is_missing`/
`_to_native`), `manifest.py`, `validator.py`, `core_adapters.py` (Query
Stage). NO tocado: `pipeline.py`, `mappings.py` (entity resolution),
`comparison.py`, `exporter.py`, el resto de `transformations.py`
(`resolve_typology`, `parse_starting_date`, `build_reference`...),
`DrillsCanonicalizeStage`, `DrillsEvidenceStage`, `DrillsTransformExportStage`.

**Verificación de equivalencia funcional -- no solo "los tests pasan":** el
test `test_core_produce_el_mismo_csv_que_pipeline_run_directo`
(`tests/test_drills_core_pipeline.py`, preexistente) compara **byte a
byte** el CSV y **por igualdad de diccionario completa** el
`validation_report.yaml`/`export_manifest.yaml` (incluyendo hashes) entre
una ejecución vía `pipeline.run()` directo y vía el Core/Orchestrator
completo -- este test sigue pasando sin ninguna modificación después de
migrar `config`/`extractor`/`manifest`/`validator`/Query Stage. Es la prueba
más fuerte disponible en el repositorio de que el refactor es
behavior-preserving para Drills.

## Fase 10 — Migrar Bypass

Migrado: `config.py`, `extractor.py`, `transformations.py` (`_is_missing`),
`manifest.py`, `validator.py`, `core_adapters.py` (Query Stage), y
`pipeline.py` (solo el import de `build_query_filters_section`, movido de
`drills.manifest` a `src.export.engine.manifest` -- una línea). NO tocado:
el resto de `pipeline.py` (`_transform_rows`, `run`), `resolve_lookup`/
`to_historical_id`/`nullcontrol_passthrough`.

Confirmado explícitamente, ejecutando `tests/test_bypass_pipeline.py`
completo (9 tests, todos verdes):
- **`Entity = UNRESOLVED`**: sin cambios -- `Entity` no está en
  `OUTPUT_COLUMNS`, ni se tocó `config/exports/bypass.yaml`.
- **`INNER JOIN` actual**: sin cambios -- `sql/source_queries/bypass/SQLQuery-dataset_BES.sql`
  no se tocó, y `extract_via_sql` nunca reescribe el fichero SQL en disco
  (mismo comportamiento que antes).
- **Anomalía de fechas del Operational**: sigue documentada como hallazgo
  externo en `pipeline.py::limitations` -- sin normalizar, sin tocar.
- **`report["status"]["result"] == "SUCCESS"`** (test
  `test_pipeline_completo_produce_columnas_esperadas`): sigue pasando con
  la lógica de 2 estados intacta.

## Fase 11 — Evidence: diagnóstico (sin implementación)

Verificado leyendo `src/evidence/{collector,catalog,workbook,models,sanitization,__init__}.py`
en su totalidad (6 ficheros, 1305 líneas):

| Fichero | Concepto hardcodeado | Por qué no es genérico | Abstracción futura |
|---|---|---|---|
| `collector.py:18` | `DEFAULT_RUNS_ROOT = .../outputs/prototype/drills` | Ruta raíz de ejecuciones fija a un módulo | Parámetro `runs_root: Path` en `load_run`/`resolve_run_dir` |
| `collector.py:23` | `EXPECTED_MIGRATION_OBJECT = "Drills"` | Validación de que la ejecución cargada es de Drills | Parámetro `expected_migration_object: str` |
| `collector.py:158` | `output_path = run_dir / "drills.csv"` | Nombre de fichero CSV fijo | Derivar de `OutputSpec.filename` (ya disponible vía config) en vez de un literal |
| `collector.py:111,147,160` | Mensajes de error con "Drills"/"drills" literal | Copys de error no parametrizados | Interpolar `migration_object`/`csv_filename` |
| `catalog.py:1,62-63,75,280,290,294,319,322` | Catálogo de categorías de incidencia (`IssueCategory`) íntegro escrito para Drills (36 columnas, 8 implementadas, referencias a `drills.csv`) | Las categorías de issue SON conocimiento de negocio de Drills, no infraestructura -- no se pueden "parametrizar" sin decidir qué son las de Bypass | Un `IssueCategoryProvider`/`EvidenceCategoryCatalog` por módulo, inyectado igual que `QueryStageSpec.filter_catalog` |
| `workbook.py:231,321,374,544,586` | Títulos de hoja Excel ("Drills (uso interno)"), nombre de fichero `drills.csv` en la hoja de trazabilidad | Presentación acoplada al nombre del objeto | Parámetros `migration_object_display_name`/`csv_filename` en `build_workbook` |
| `models.py:12` | Docstring de excepción menciona "Drills" como el único origen válido | Cosmético, sin efecto en runtime | N/A -- no requiere cambio funcional |
| `sanitization.py:31` | Referencia a `drills/transformations.py` en un comentario | Cosmético (comentario, no import) | N/A |
| `__init__.py:3-9` | Docstring del paquete completo describe el alcance como "limitado a Drills" | Documental | Actualizar cuando se generalice |

**Contrato mínimo para un futuro `EvidenceProvider`/`EvidenceRenderer`
(nombre NO decidido -- sin evidencia suficiente todavía, un solo caso real):**
recibiría `runs_root: Path`, `migration_object: str`, `csv_filename: str`,
`category_catalog: IssueCategoryProvider` (inyectado, igual patrón que
`QueryStageSpec`) -- el resto del motor (lectura de `validation_report.yaml`/
`export_manifest.yaml`, construcción del workbook, sanitización de tipos)
ya es genérico por estructura, solo le faltan estos 4 parámetros para dejar
de asumir Drills. **No implementado en este sprint.** Bypass sigue sin
Evidence -- `--generate-evidence` sigue siendo un no-op para
`run --object bypass` (no se ha tocado `ModuleCapabilities`, que sigue sin
declarar `EVIDENCE` para Bypass).

## Fase 12 — Output location: solo preparación

Confirmado por inspección (`grep -rn outputs src/export/engine/`): el Engine
NO contiene ninguna ruta hardcodeada a `outputs/prototype/...` -- las únicas
2 funciones que escriben a disco (`write_yaml_atomic`/`write_text_atomic`)
reciben un `Path` completo como parámetro; la decisión de la raíz
(`DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "prototype" / "<módulo>"`)
sigue viviendo enteramente en `core_adapters.py` de cada módulo, sin tocar.
**Migrar a `%EMF_DATA_ROOT%/projects/<client>/runs/<module>/<execution_id>/`
en el futuro no requeriría ningún cambio en `src/export/engine/`** -- solo
en la construcción de `DEFAULT_OUTPUT_ROOT` de cada `core_adapters.py` (o,
mejor, centralizando esa construcción en una función del Engine cuando haya
un segundo caso real de esa migración -- no hecho aquí, sin evidencia
todavía). Ubicación observable: sin cambios en este sprint.

## Fase 13 — Field Constraints: punto de extensión

Verificado, no implementado: `FieldSpec` (`engine/config.py`) es un
dataclass `frozen`, construido siempre por `load_export_config` con
argumentos de palabra clave (nunca posicionales) -- añadir un campo nuevo
`constraints: FieldConstraintSpec | None = None` al final, con default,
sería un cambio aditivo puro: ni `load_export_config` ni ningún caller
existente (Drills/Bypass no leen `.constraints` hoy) se rompería.
`validate_csv_structure` es una función libre (no un método de clase
cerrada) -- añadir un parámetro opcional `field_specs: Sequence[FieldSpec] |
None = None` en un sprint futuro, para ejecutar constraints por fila, es
igualmente aditivo. **No se añade ningún campo/parámetro nuevo en este
sprint** -- solo se confirma que el punto de extensión es viable sin romper
nada existente.

## Fase 14 — Tests arquitectónicos

`tests/test_export_engine.py` (40 tests nuevos, todos verdes):

1. ✅ `test_engine_no_importa_drills_ni_bypass`.
2. ✅ `test_engine_no_tiene_condicionales_por_module_id` (AST, no texto crudo).
3. ✅ `test_drills_y_bypass_consumen_el_engine` (ambos importan de `src.export.engine`).
4. ✅ Ídem, específico para `config`/`extractor`/`manifest`/`validator`/`core_adapters`.
5. ✅ `test_bypass_ya_no_importa_directamente_de_drills_para_utilidades_genericas`
   (permite solo los 2 acoplamientos ya documentados y deliberados:
   `exporter.write_csv`, `transformations.resolve_letter`/`to_historical_id`).
6. ✅ Ambos siguen registrados vía `ModuleRegistry`/`pipeline_factory` --
   cubierto por `tests/test_bootstrap_module_registry.py` y
   `tests/test_bypass_pipeline.py`, preexistentes, sin tocar, siguen en verde.
7. ✅ Query Engine sigue parametrizando filtros (`test_generic_query_stage_compila_filtros_del_request`).
8. ✅ Sample limit conserva semántica (`test_extract_via_sql_*`, 5 tests).
9. ✅ SQL Guard sigue bloqueando -- cubierto por `test_cli_sql_execution_guard.py`, sin tocar, sigue en verde.
10. ✅ Manifests siguen generándose con contrato compatible -- cubierto por
    el test golden byte-a-byte de Drills (Fase 9) + `test_pipeline_completo_produce_columnas_esperadas`
    de Bypass, ambos sin tocar, ambos en verde.

No se crearon tests frágiles de texto donde una verificación semántica era
posible (el test de "no branching por módulo" usa AST, no substring, tras
detectar en el primer intento un falso positivo en un docstring).

## Fase 15 — Suite completa

```
775 passed, 7 skipped   (baseline, antes del refactor)
815 passed, 7 skipped   (después -- +40 tests nuevos de src/export/engine)
```

**Cero regresiones** -- los 775 tests preexistentes pasan sin ninguna
modificación de su código. `git diff --check`: sin marcadores de conflicto
(solo avisos de fin de línea LF/CRLF, esperados en Windows).

## Fase 16 — Medir resultado

| Capability | Before (líneas aprox. duplicadas) | After | Drills-specific | Bypass-specific |
|---|---:|---|---|---|
| Config loader | ~65 líneas × 2 módulos | 1 función en Engine (68 líneas) + 2 contenedores de ~15 líneas | `DrillsExportConfig` (nombre) | `BypassExportConfig` (nombre) |
| Extractor | ~110 líneas × 2 (con diferencias reales de sort) | 1 función en Engine (128 líneas, con Protocol) + 2 wrappers de ~20 líneas | `sort_column=None` | `sort_column="FechaCreacion"` |
| RunStats/manifest | ~340 líneas total (2 ficheros) | `BaseRunStats`+helpers en Engine (250 líneas) + 2 ficheros de ~110/95 líneas | `reference_*`/`entities_*`/`dates_*`, `determine_status` 3 estados, hashes extendidos, `rules_applied` | `lookups_*`, `determine_status` 2 estados (sin migrar) |
| Validator | ~186 + ~65 líneas | Núcleo en Engine (71 líneas) + Drills 165 líneas (con BOM/Reference/pandas-reread) + Bypass 34 líneas | BOM, `Reference`, row-count, pandas re-read | -- (usa el núcleo casi sin extensión) |
| `_is_missing` | ~14 líneas × 2 (con 1 diferencia real: `_to_native`) | 1 función en Engine (54 líneas con `to_native`) | Alias privado, 4 usos de `_to_native` | Alias privado, 1 uso |
| Query Stage | ~30 líneas × 2 | `GenericQueryStage`/`QueryStageSpec` en Engine (86 líneas) + 2 factories de ~10 líneas | `state_key="drills_config"`, filtro `DRILLS_FILTER_CATALOG` | `state_key="bypass_config"`, filtro `BYPASS_FILTER_CATALOG` |

**Archivos duplicados eliminados:** 0 ficheros enteros (ninguna de las 5-6
piezas ocupaba un fichero completo por sí sola) -- **duplicación de código
eliminada:** sí, sustancial, ver diff real:

```
13 files changed, 304 insertions(+), 796 deletions(-)
```

(archivos de `src/export/prototype/{drills,bypass}/`, sin contar los 745
líneas nuevas de `src/export/engine/` ni las 523 de
`tests/test_export_engine.py`, que son la contrapartida de esa reducción,
no duplicación).

**Imports nuevos:** 12 (los `from src.export.engine.* import ...` añadidos
en `drills/`+`bypass/`). **Dependencias externas:** ninguna nueva (mismas
`pandas`/`pyyaml`/`numpy` ya usadas). **Cambios en Core:**

```
src/core/  ->  0 archivos modificados (git status confirmado)
```

Ningún blocker arquitectónico obligó a tocar `src/core/` en este sprint.

**Duplicación restante, deliberada (Fase 1):**
- `pipeline.py` completo (Drills 687 líneas / Bypass 238 líneas) -- WAIT_FOR_THIRD_MODULE.
- `Transform/Export Stage` en `core_adapters.py` de ambos -- mismo motivo.
- `write_csv` (`bypass` sigue importándolo de `drills.exporter`, no del
  Engine) -- fuera del alcance de las 5-6 piezas identificadas en Sprint
  9.5.1, no tocado deliberadamente (no autorizado a ampliar el alcance).
- `mappings.py`/`comparison.py` de Drills -- module-specific por diseño,
  sin equivalente en Bypass.

## Fase 17 — Safety Meetings readiness preview

Evaluado, SIN implementar, qué necesitaría Safety Meetings usando
`ModuleRegistry`+`pipeline_factory`+Engine (ya reducido) +
config/SQL/mappings/validator module-specific:

| Pieza | Con el Engine (Sprint 9.6) | Sin el Engine (como Bypass en Sprint 9.4) |
|---|---|---|
| `safety_meetings/config.py` | ~15 líneas (1 dataclass contenedor + `load_export_config`) | ~65 líneas (loader completo copiado) |
| `safety_meetings/extractor.py` | ~20 líneas (wrapper de `extract_via_sql`, decidir `sort_column` según si su SQL tiene `ORDER BY`) | ~110 líneas |
| `safety_meetings/manifest.py` | `RunStats` propio (`attendees_*` u otros contadores SM) + `build_export_manifest` reutilizando `build_run_section`/`build_counts_section`/`build_output_section`/`build_connection_section` | ~130-260 líneas |
| `safety_meetings/validator.py` | Wrapper de `validate_csv_structure`, probablemente casi idéntico al de Bypass (~35 líneas) | ~65 líneas |
| `safety_meetings/core_adapters.py` (Query Stage) | `GenericQueryStage(QueryStageSpec(...))`, ~10 líneas | ~30 líneas |
| **`safety_meetings/pipeline.py`** (Transform/Export) | **Sigue sin reducirse -- se escribe siguiendo el patrón de `bypass/pipeline.py`, ~150-250 líneas** | Igual |
| **`safety_meetings/core_adapters.py`** (Transform/Export Stage) | **Sigue sin reducirse** | Igual |
| `SAFETY_MEETINGS_FILTER_CATALOG` (`src/query/catalog.py`) | Nuevo, datos propios (mecanismo ya genérico) | Igual |
| `config/exports/safety_meetings.yaml` | Nuevo, contenido de negocio | Igual |
| Entity resolution | Posible tercera confirmación del gap ya visto en Bypass (`IDUnidadOrg -> RutaEnablon`, formato `Ruta1` completo -- distinto del `Code corto` de Bypass, y del catálogo antiguo de Drills) -- module-specific en cualquier caso | Igual |

**Conclusión de la preview:** el Engine mínimo reduce sustancialmente el
código de "arranque" (config/extractor/validator/manifest-core/Query Stage)
que un tercer módulo necesitaría escribir -- de los ~400 líneas que Bypass
tuvo que copiar+adaptar de Drills en esas piezas, Safety Meetings
necesitaría del orden de ~70-90 líneas de wrappers delgados. La pieza que
SIGUE siendo cara (`pipeline.py`/Transform-Export Stage) es exactamente la
que Sprint 9.5.1 y este sprint coinciden en NO extraer todavía -- Safety
Meetings sería precisamente la 3ª confirmación de forma que permitiría, en
un sprint posterior, decidir cómo separarla con evidencia real (Sprint 9.7
en adelante).

## Fase 18 — Documentación

Este documento (`Informe-Minimal-Export-Engine-Extraction-EMF.md` + `.txt`)
es el entregable de esta fase. No se ha modificado ninguna documentación
arquitectónica existente como aspiracional -- las menciones nuevas en
docstrings de código (`drills/core_adapters.py`, `bypass/core_adapters.py`,
`bypass/manifest.py`) describen exactamente lo que el código hace hoy, no
un diseño futuro.

---

# PUERTA FINAL — 18 PUNTOS

1. **Baseline tests:** 775 passed, 7 skipped.
2. **Tests finales:** 815 passed, 7 skipped (+40 nuevos, 0 regresiones).
3. **Inventario reconciliado:** 7 piezas originales -- 5 EXTRACT_NOW completas
   (extractor, config, núcleo manifest, núcleo validator, `_is_missing`), 1
   dividida (Query Stage sí / Transform-Export Stage no), 1 intacta
   (`pipeline.py`). Ver Fase 1 para la tabla completa.
4. **Piezas extraídas:** `engine/config.py`, `engine/extractor.py`,
   `engine/values.py`, `engine/manifest.py` (núcleo), `engine/validator.py`
   (núcleo), `engine/query_stage.py`.
5. **Piezas que siguen module-specific:** `pipeline.py` completo de ambos,
   Transform/Export Stage de ambos, `mappings.py`/`comparison.py` de Drills,
   todas las transformaciones de negocio, `RunStats` de extensión
   (`reference_*`/`entities_*`/`dates_*` en Drills, `lookups_*` en Bypass),
   `determine_status` de Bypass (2 estados, deliberadamente no migrado),
   validaciones de negocio de Drills (BOM/`Reference`/row-count/pandas-reread).
6. **Estructura final de `src/export/engine/`:** ver Fase 2 (7 ficheros, 745 líneas).
7. **Cambios Drills:** `config.py`/`extractor.py`/`transformations.py`
   (`_is_missing`/`_to_native`)/`manifest.py`/`validator.py`/`core_adapters.py`
   (Query Stage) -- `pipeline.py` sin tocar.
8. **Cambios Bypass:** mismos 6 ficheros + 1 línea de import en `pipeline.py`
   (`build_query_filters_section` ahora del Engine, no de `drills.manifest`).
9. **Confirmación de equivalencia funcional:** test golden byte-a-byte de
   Drills (CSV + YAML por igualdad de diccionario completa, incluidos
   hashes) sigue en verde sin modificarse; los 9 tests de
   `test_bypass_pipeline.py` (incluida la comprobación explícita de
   `Entity`/`INNER JOIN`/anomalía de fechas como hallazgos sin tocar) siguen
   en verde.
10. **Evidence hardcodes encontrados:** 9 puntos concretos en 5 ficheros de
    `src/evidence/` (tabla completa en Fase 11) -- ninguno corregido,
    contrato mínimo de una futura abstracción documentado, no implementado.
11. **Estado output-location:** sin cambios observables; confirmado que el
    Engine no bloquea la futura migración a `%EMF_DATA_ROOT%/projects/<client>/runs/...`
    (ninguna ruta hardcodeada dentro de `src/export/engine/`).
12. **Punto de extensión Field Constraints:** confirmado viable
    (`FieldSpec.constraints` aditivo, `validate_csv_structure` con parámetro
    opcional futuro) -- nada añadido todavía.
13. **Cambios en `src/core/`:** ninguno (`git status`/`git diff --stat`
    confirmados vacíos para `src/core/`). No apareció ningún blocker
    arquitectónico que lo exigiera.
14. **Duplicación restante:** `pipeline.py` completo (687/238 líneas),
    Transform/Export Stage, `write_csv` (bypass sigue importándolo de
    drills en vez del Engine, fuera de alcance de este sprint).
15. **Safety Meetings readiness preview:** ~70-90 líneas de wrappers
    delgados en vez de ~400 líneas copiadas -- la pieza cara
    (`pipeline.py`/Transform-Export Stage) sigue sin reducirse, sería la 3ª
    confirmación de forma necesaria para abordarla en un sprint posterior.
16. **Archivos modificados/nuevos:**
    - Nuevos: `src/export/engine/{__init__,config,extractor,values,manifest,validator,query_stage}.py`,
      `tests/test_export_engine.py`,
      `reports/executions/2026-08-14/Informe-Minimal-Export-Engine-Extraction-EMF.{md,txt}`.
    - Modificados: `src/export/prototype/{drills,bypass}/{config,extractor,transformations,manifest,validator,core_adapters}.py`,
      `src/export/prototype/bypass/pipeline.py` (1 línea de import).
17. **Propuesta de commit(s):** un único commit,
    `refactor(export): extract minimal Export Engine shared by Drills and Bypass`,
    con el detalle de las 6 piezas extraídas y "0 cambio funcional" en el
    cuerpo del mensaje -- a la espera de autorización explícita, no creado
    todavía.
18. **Confirmaciones:**
    - 0 SQL real ejecutado.
    - 0 `full` ejecutado.
    - 0 datos reales versionados.
    - 0 workspace real versionado.
    - 0 secretos.
    - 0 push.

**NO se ha hecho commit. Esperando autorización explícita para el commit
propuesto en el punto 17.**
