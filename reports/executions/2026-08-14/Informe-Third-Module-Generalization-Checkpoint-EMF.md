# Sprint 9.8 — Third-Module Generalization Checkpoint

**Estado de partida confirmado:** `26724fb` (Safety Meetings) presente, `f24f5fd` (Export Engine), `e5f8a91` (Bypass). Rama `feature/drills-filtered-exports`, `ahead 3` de `origin` — sin push inesperado. Baseline: **836 passed, 7 skipped**.

**Estado final:** **844 passed, 7 skipped** (+8 tests nuevos), cero regresiones. Ningún cambio en `src/core/`. Ningún SQL ejecutado. Ningún push.

---

## Fase 0 — Preflight

Confirmado antes de tocar nada:
- `git log --oneline -10` → `26724fb`/`f24f5fd`/`e5f8a91` presentes en ese orden.
- `git status -sb` → `ahead 3` de `origin/feature/drills-filtered-exports`, sin push inesperado.
- `git diff --check` → limpio (solo avisos de normalización LF→CRLF, no conflictos).
- `.claude/settings.local.json` modificado pero fuera de alcance de cualquier commit de este sprint.
- No hay `workspace.yaml` real, outputs reales, datos de cliente ni secretos trackeados (`git ls-files` cruzado contra `.gitignore`).
- 6 informes sueltos de Sprints 9.5/9.5.1 (`Informe-Export-Engine-Generalization-Assessment-EMF.*`, `Informe-Sprint9.5-Bypass-*.*`) seguían untracked desde antes de este sprint — no tocados, no son de Sprint 9.8.
- Suite completa: **836 passed, 7 skipped** — baseline confirmado.

---

## Fase 1 — Inventario exacto de helpers duplicados

Hallazgo previo a cualquier extracción: **no había duplicación de código** en `to_historical_id`/`resolve_letter`/`resolve_workflow_status`/`LookupResult`. Bypass y Safety Meetings ya los **importaban** directamente de `drills/transformations.py` (nunca los copiaron) — documentado así en sus propios docstrings desde que se escribieron (Sprint 9.4 y 9.7 respectivamente). El problema real no era duplicación, era **acoplamiento módulo-a-módulo**: dos módulos "hermanos" dependiendo el uno del otro para utilidades sin ninguna lógica de Drills, en vez de depender de una capa neutral.

| Helper | Drills | Bypass | Safety Meetings | Semántica | Diferencias | Tests | Clasificación |
|---|---|---|---|---|---|---|---|
| `to_historical_id` | Definición original | Import directo | Import directo | Limpieza de ID numérico a texto, sin resto decimal artificial | Ninguna — mismo código, 3 usos reales | `test_drills_export_prototype.py`, `test_bypass_transformations.py`, `test_safety_meetings_transformations.py` | **PROVEN_GENERIC** |
| `LookupResult` | Definición original | Import directo | Import directo | Dataclass de resultado de lookup (`value`/`status`/`raw_source_value`) | Ninguna | Cubierta indirectamente por los tests de cada `resolve_*` | **PROVEN_GENERIC** |
| `resolve_letter` | Uso propio (`CS_Letter`) | Reutilizada 4× (`ByPassType`/`Cause`/`ElementType`/`RealizationMethods`) | No usada | `null_default` SOLO para vacío; presente-sin-coincidencia = `unresolved`, sin default | Ninguna en su lógica — sí en cuántos campos la usan | `test_drills_export_prototype.py`, `test_bypass_transformations.py` | **PROVEN_GENERIC** |
| `resolve_workflow_status` | Uso propio (`CS_WorkflowStatus`) | No usada | Reutilizada 3× (`CS_WorkflowStatus`/`CS_Level`/`CS_Letter`) | SIN default en ningún caso (ni vacío ni sin coincidencia) | Ninguna | `test_drills_export_prototype.py`, `test_safety_meetings_transformations.py` | **PROVEN_GENERIC** |
| `_normalize_lookup_key` (interno) | Usado por `resolve_typology`/`resolve_letter`/`resolve_workflow_status` | Heredado transitivamente | Heredado transitivamente | Normaliza clave numérica/string para lookup | Ninguna | Sin test directo — cubierto por los `resolve_*` | **PROVEN_GENERIC** (pieza de soporte de las anteriores) |
| `resolve_typology` | Uso propio (`CS_Typology`) | No usada | No usada | Aplica el MISMO default a vacío y a sin-coincidencia (a diferencia de `resolve_letter`) | — | `test_drills_export_prototype.py` | **MODULE_SPECIFIC** — un solo uso real, sin 2ª/3ª confirmación |
| `write_csv` (`drills/exporter.py`) | Definición original | Import directo | Import directo | Escritura CSV atómica, encoding/delimiter/quoting/BOM desde `OutputSpec` | Ninguna | `test_drills_export_prototype.py` (indirecto tras Fase 6) | **PROVEN_GENERIC** |
| `_is_missing`/`_to_native` | Ya en `engine/values.py` desde Sprint 9.6 | Ya en `engine/values.py` | Ya en `engine/values.py` | — | — | — | Ya extraído (Sprint 9.6), sin cambios |

No se encontró ningún helper `SEMANTICALLY_DIFFERENT` con el mismo nombre en dos módulos — a diferencia de lo que la Fase 1 del encargo advertía como riesgo, los tres módulos fueron disciplinados: cuando la semántica difería (`resolve_letter` vs `resolve_workflow_status` vs `resolve_typology`), cada módulo usó la función correcta en vez de forzar la que ya tenía importada.

---

## Fase 2 — Extracción de lo PROVEN_GENERIC

Movido a `src/export/engine/`:
- **`identifiers.py`** (48 líneas): `to_historical_id`.
- **`lookups.py`** (84 líneas): `LookupResult`, `normalize_lookup_key` (renombrado desde `_normalize_lookup_key`, ahora público al cruzar el límite del paquete), `resolve_letter`, `resolve_workflow_status`.

`resolve_typology` permanece en `drills/transformations.py` — un solo uso real, sin evidencia de una 2ª/3ª necesidad. Forzar su extracción habría sido abstracción prematura.

Cambios por módulo (comportamiento IDÉNTICO, verificado por identidad de objeto, no solo por tests de comportamiento — ver Fase 11):
- `drills/transformations.py`: las 4 funciones y la dataclase ahora se importan del Engine y se re-exportan con el mismo nombre — `pipeline.py` de Drills sigue llamando `tr.to_historical_id`/`tr.resolve_letter`/`tr.resolve_workflow_status` sin ningún cambio.
- `bypass/transformations.py`: importa de `src.export.engine.identifiers`/`src.export.engine.lookups` en vez de `src.export.prototype.drills.transformations`.
- `safety_meetings/transformations.py`: mismo cambio.

Nombres de fichero elegidos por contenido real (`identifiers.py`/`lookups.py`), no un `utils.py` genérico — tal como pedía el encargo.

---

## Fase 3 — `determine_status`: divergencia Drills/Bypass/Safety Meetings

| | Drills | Bypass | Safety Meetings |
|---|---|---|---|
| Función | `engine.manifest.determine_status` (3 estados) | Cálculo inline propio (2 estados) | `engine.manifest.determine_status` (3 estados) |
| Estados posibles | `SUCCESS` / `SUCCESS_WITH_WARNINGS` / `FAILED_VALIDATION` | `SUCCESS` / `FAILED_VALIDATION` | `SUCCESS` / `SUCCESS_WITH_WARNINGS` / `FAILED_VALIDATION` |
| ¿Genera warnings reales? | Sí (`stats.warnings.append`, varios puntos) | Sí — `pipeline.py:118`, un warning por cada lookup `unresolved` (valor presente sin coincidencia, de sus 4 lookups) | Sí — `pipeline.py:103`, un warning por cada lookup `unresolved`/`empty` |
| ¿El status.result refleja esos warnings? | Sí | **No** — el cálculo inline de Bypass solo mira `errors`, ignora `warnings` por completo | Sí |
| Motivo documentado de la diferencia | — | Decisión explícita de Sprint 9.6: "migrarlo cambiaría el comportamiento observable... no autorizado en un refactor behavior-preserving" | Decisión propia de Sprint 9.7 (no migración): ninguno de sus 3 lookups tiene default documentado |

**Evidencia real cruzada contra el único sample real ejecutado** (`outputs/prototype/bypass/20260814T061625Z/validation_report.yaml`, Sprint 9.5, `run_id=e7617f04710e`): 10 filas, 50 lookups resueltos, **0 warnings**. Con los datos reales vistos hasta ahora, migrar Bypass a 3 estados no habría cambiado el resultado de esa ejecución concreta — pero es una muestra de 10 filas, no prueba a escala completa.

**Conclusión (A/B/C):** **A — diferencia accidental**, no una política module-specific deliberada. No hay ninguna razón de negocio documentada por la que un lookup de Bypass "presente pero sin coincidencia" deba tratarse de forma distinta al mismo caso en Drills o Safety Meetings — es simplemente código de Sprint 9.4 (anterior al `determine_status` del Engine) que nunca se migró. La función a la que Bypass necesitaría llamar (`engine.manifest.determine_status`) ya existe, ya es la misma que usan los otros dos módulos, y el cambio en `bypass/manifest.py::write_validation_report` sería de una sola línea.

**No implementado en este sprint** (instrucción explícita: no migrar solo por conteo 2-de-3; tratar como cambio funcional si altera outputs observables). El cambio SÍ altera un output observable (`status.result` podría pasar de `SUCCESS` a `SUCCESS_WITH_WARNINGS` en ejecuciones con lookups sin resolver) — queda diseñado, no aplicado:

```python
# bypass/manifest.py::write_validation_report -- cambio propuesto, NO aplicado:
result, blocking_errors, warnings = determine_status(stats.errors, stats.warnings)
# sustituye a: "FAILED_VALIDATION" if stats.errors else "SUCCESS"
```

Recomendación: commit propio y visible en un sprint futuro, idealmente después de un sample real de Bypass con más de 10 filas que confirme con qué frecuencia aparecen lookups `unresolved` en producción.

---

## Fase 4 — Entity Resolution: tercera confirmación

`CS_Entity` queda `UNRESOLVED`/excluido en Bypass y Safety Meetings — confirmado como el **mismo gap sistémico**, no una coincidencia de nombre:

- Ambos catálogos de filtros (`src/query/catalog.py`, campo `origin_org_unit_id`) documentan la MISMA causa palabra por palabra: *"este repositorio NO tiene hoy un artefacto local IDUnidadOrg->Code[/Ruta1] para ese catálogo"*.
- Verificado contra los ficheros reales presentes en `inputs/entity_catalog/` (gitignored, no versionados): existe `First_Axis_export_bruto.csv` (1724 filas, columnas `Parent`/`Code`/`EntityStatus`...) y `catalogo_resuelto_code_ruta_site.csv` (mismo contenido + `Ruta1`/`Centro` ya calculados) — **ninguno de los dos tiene una columna `IDUnidadOrg`**. Es decir: existe el catálogo Enablon (`Code -> Ruta1 -> Centro`), pero no existe la tabla de traducción `IDUnidadOrg (numérico, sistema ITP/GCT origen) -> Code (First_Axis)` que permitiría entrar a ese catálogo desde las filas SQL de Bypass/Safety Meetings.

**Qué SÍ existe y es reutilizable:** `drills/mappings.py` (`EntityCatalog`/`resolve_entity`/`load_entity_catalog`) es **ya 100% genérico en su código** — parametrizado por `key_column`/`value_column`/`do_not_migrate_literal`, sin ninguna referencia a Drills o Simulacros en su lógica, con 5 estados bien definidos (`resolved`/`do_not_migrate`/`unresolved`/`conflicting`/`empty`). Usa, eso sí, el catálogo ANTIGUO específico de Simulacros (`entidades_mapeo_ANTIGUO_referencia_historica.csv`, 681 filas, esquema retirado del árbol vigente pero correcto para su momento — ver CLAUDE.md), que SÍ tiene `IDUnidadOrg` directo porque es el catálogo propio del sistema de origen de Drills.

**Respuesta a la pregunta de la Fase 4:** el Engine **ya podría alojar `resolve_entity`/`EntityCatalog` tal cual** si tuviéramos el catálogo correcto — no falta arquitectura, falta el **artefacto de datos** (`ENTITY_RESOLUTION_CAPABILITY_GAP` = `MISSING_ARTIFACT`, no `MISSING_ENGINE_CAPABILITY`). No se mueve `mappings.py` al Engine en este sprint: solo tiene un uso real (Drills) — la misma regla de evidencia que mantiene `resolve_typology` fuera. Moverlo ahora, sin que Bypass/Safety Meetings lo ejerciten de verdad, sería generalizar sobre un patrón todavía no confirmado por un segundo caso real.

**No se implementa resolución inferida** (instrucción explícita) — el gap queda documentado, no rellenado con una heurística.

---

## Fase 5 — `pipeline.py`: diseño, no implementación

Tamaños actuales: Drills 687 líneas, Bypass 237, Safety Meetings 218.

| Responsabilidad | Drills | Bypass | Safety Meetings | Clasificación |
|---|---|---|---|---|
| request/context (run_id, timestamp, output_dir) | Propio | Idéntico en forma | Idéntico en forma | **PROVEN_GENERIC** |
| query/extracción | `extract_via_sql` (Engine) vía `extract_drills` | `extract_via_sql` (Engine) vía `extract_bypass` | `extract_via_sql` (Engine) vía `extract_safety_meetings` | Ya en el Engine (Sprint 9.6) |
| generated_sql + `build_query_filters_section` | Propio, mismo patrón | Idéntico en forma | Idéntico en forma | **PROVEN_GENERIC** (ya usa piezas del Engine) |
| canonicalización/transformación de filas | `_transform_rows`, ~220 líneas, entidad+referencia+fechas | `_transform_rows`, ~60 líneas, 5 lookups | `_transform_rows`, ~50 líneas, 3 lookups | **MODULE_SPECIFIC** (el corazón real de cada módulo) |
| validación post-CSV | `validate_output_csv`/`validate_csv_structure` (Engine) | Igual | Igual | Ya en el Engine |
| escritura CSV | `write_csv` (Engine, Fase 6) | Igual | Igual | **PROVEN_GENERIC** (Fase 6) |
| manifest/validation report | `build_export_manifest`/`write_validation_report` — forma común + secciones propias | Igual | Igual | **HOOK_REQUIRED** (esqueleto común, secciones inyectadas) |
| comparación contra histórico/Operational | `comparison.py`, Project Contract XLSX | Manual (Sprint 9.5, sin código) | Identificado, sin ejecutar | **INSUFFICIENT_EVIDENCE** (ver Fase 7) |
| evidence | `src/evidence/` | No conectado | No conectado | **INSUFFICIENT_EVIDENCE** (ver Fase 8, hardcoded a Drills) |
| output paths | `outputs/prototype/<módulo>/<timestamp>/` | Idéntico | Idéntico | **PROVEN_GENERIC** |
| stats/issues | `RunStats` (Engine) + extensión propia + `issues.jsonl` (solo Drills) | `RunStats` (Engine) + extensión propia | `RunStats` (Engine) + extensión propia | Base **PROVEN_GENERIC**, extensión **MODULE_SPECIFIC**, `issues.jsonl` **MODULE_SPECIFIC** (solo Drills lo tiene) |
| manejo de errores | `FileExistsError` si el output_dir existe; excepción no controlada = `FAILED_EXECUTION` | Igual | Igual | **PROVEN_GENERIC** |
| status | 3 estados (Engine) | 2 estados (propio, ver Fase 3) | 3 estados (Engine) | **HOOK_REQUIRED** vía `determine_status`, política de warnings module-specific |

**Diseño conceptual** (pseudofirma, NO implementada):

```
ExportPipeline(
    extract=extract_via_sql,          # ya genérico (Engine)
    transform_rows=<callable module>, # MODULE_SPECIFIC -- el corazón real
    write_csv=write_csv,              # ya genérico (Engine, Fase 6)
    validate=validate_output_csv,     # ya genérico (Engine)
    build_manifest=<callable module>, # HOOK_REQUIRED -- forma común + secciones inyectadas
    determine_status=determine_status,# ya genérico (Engine) -- Bypass pendiente de adoptarlo (Fase 3)
    hooks={
        "before_write": ...,   # p. ej. resolución de entidad, cuando exista el artefacto (Fase 4)
        "after_manifest": ..., # p. ej. comparación (Fase 7), evidence (Fase 8)
    },
)
```

Preferencia por **composición/hooks sobre una clase base grande**: la evidencia de 3 módulos reales muestra que la única pieza genuinamente grande y variable es `_transform_rows` (220/60/50 líneas) — envolverla en una jerarquía de herencia obligaría a los 3 módulos a heredar de una clase pensada sobre todo para Drills (el único con comparación/evidence/issues.jsonl reales). Composición permite que Drills siga siendo "más grande" sin forzar esa forma en Bypass/Safety Meetings.

Respuestas explícitas:
- **Qué controla el Engine:** extracción, escritura CSV, validación estructural, cálculo de status, secciones de manifest ya comunes (`run`/`counts`/`output`/`connection`/`query_filters`).
- **Qué aporta el módulo:** `_transform_rows` (la regla de negocio real), sus propias secciones de manifest (`entities`/`dates` en Drills, `lookups` en Bypass/SM), sus propios `RunStats` de extensión, y — solo Drills por ahora — comparación/evidence/issues.
- **Qué vive en `context.state`:** nada todavía — ninguno de los 3 pipelines usa `ExecutionContext.state` para pasar información entre stages más allá de lo que ya orquesta `core_adapters.py` (Query Stage -> Transform/Export Stage). No hay evidencia hoy de que un `ExportPipeline` genérico necesite más que eso.
- **Action Plans a futuro:** encajaría como un cuarto `_transform_rows`-equivalente module-specific, más una `manifest.py` propia (patrón ya usado 3 veces) — el diseño de arriba no necesita cambios para admitirlo.
- **Multi-object:** un `ExportPipeline` por objeto (no por módulo) — ver Fase 10, el gap está en `WorkspaceManifest`, no en `pipeline.py`.
- **Cancelación futura (UI/.exe):** el punto natural es entre filas dentro de `_transform_rows`/`extract_via_sql` (ya iterativo) — ningún módulo lo necesita hoy, no se diseña más allá de señalar el punto de inserción.
- **Evitar branching por `module_id`:** igual que el Engine actual — todo por inyección de callables/config, nunca `if module_id == ...` (regla ya verificada por tests arquitectónicos, Fase 11).

---

## Fase 6 — CSV Writer

`drills/exporter.py::write_csv` resultó ser **PROVEN_GENERIC** y pequeño (73 líneas): cero lógica de Drills, solo `OutputSpec` (ya compartida desde Sprint 9.6) + `csv`/`os`/`tempfile` de librería estándar. Bypass y Safety Meetings ya la importaban directamente sin copiarla.

**Extraído** a `src/export/engine/writer.py` (81 líneas, incluye docstring de evidencia). `drills/exporter.py` queda como shim de re-export (15 líneas) — mismo patrón que `_is_missing`/`_to_native` en Sprint 9.6, para no tocar el import ya existente en `drills/pipeline.py` ni en `tests/test_drills_export_prototype.py`.

No se encontraron diferencias reales de delimiter/encoding/BOM/quoting/line endings/column ordering/null representation entre los 3 módulos — todas vienen ya de `OutputSpec`, sin ningún caso observado que necesite algo que `OutputSpec` no exprese hoy.

---

## Fase 7 — Comparison

Estado por módulo:
- **Drills:** `comparison.py` completo (253 líneas) contra Project Contract real (XLSX, con las limitaciones ya documentadas de no soportar XLSX directamente — ver su propio docstring).
- **Bypass:** comparación manual realizada en Sprint 9.5 (10/10 filas MATCH contra Operational real) — **sin código**, hecha a mano fuera del pipeline.
- **Safety Meetings:** Operational real identificado y localizado (Sprint 9.7), comparación **no ejecutada** todavía, ni manual ni en código.

**Conclusión: `INSUFFICIENT_EVIDENCE`** para decidir entre A/B/C/D con confianza. Solo hay UNA implementación de código real (Drills) y NINGUNA comparación en código para Bypass/Safety Meetings todavía — extraer o diseñar una interfaz genérica de comparación ahora sería generalizar sobre un solo punto de datos, exactamente el riesgo que este sprint evita en otras fases.

**Recomendación:** antes de diseñar `comparison` como capability del Engine, escribir una segunda implementación real (probablemente Bypass, que ya tiene un resultado manual de Sprint 9.5 como referencia para verificar equivalencia) — entonces sí habrá 2 puntos de datos reales para clasificar correctamente A/B/C/D.

---

## Fase 8 — Evidence

Confirmado: **sigue hardcoded a Drills**, sin cambios desde la nota de memoria de Sprint 9.5.1 ("Evidence engine is secretly Drills-only"). Evidencia concreta en `src/evidence/`:
- `collector.py`: `DEFAULT_RUNS_ROOT = PROJECT_ROOT / "outputs" / "prototype" / "drills"`, `EXPECTED_MIGRATION_OBJECT = "Drills"`, busca literalmente `drills.csv`.
- `catalog.py`: descripciones de categoría con texto literal ("Registros incluidos en drills.csv...", "8 de 36 columnas del objeto Drills...").
- `workbook.py`: títulos de hoja hardcoded ("Resumen de la ejecución -- Drills").

**Separación GENERIC / MODULE-SPECIFIC (para cuando se aborde, no en este sprint):**
- **GENERIC EVIDENCE ENGINE** (mecánica reutilizable): localizar la última ejecución bajo `outputs/prototype/<módulo>/`, leer `validation_report.yaml`/`export_manifest.yaml`/CSV de esa ejecución, construir el workbook XLSX (dos hojas, interna/cliente) a partir de esos datos.
- **MODULE-SPECIFIC EVIDENCE CONTENT**: el catálogo de categorías de incidencia (`catalog.py`, hoy con IDs/descripciones pensados solo para los `open_questions`/limitaciones de Drills), el nombre del CSV de salida, el `migration_object` esperado, los títulos.

No se refactoriza en este sprint (instrucción explícita). Con Bypass y Safety Meetings ya reales, la parametrización necesaria (`runs_root`, `expected_migration_object`, `output_csv_filename`, catálogo de categorías inyectado) ya es visible — candidato claro para un sprint futuro, no el de mayor prioridad (ver Fase 13).

---

## Fase 9 — Field Constraints: candidatos registrados

Sin implementar (instrucción explícita). Candidatos reales acumulados hasta ahora, de los tres módulos:

| Módulo | Campo | Evidencia | Candidato |
|---|---|---|---|
| Bypass | `AutorizaOPoneEnServicioFase2/3/4` | Valores observados solo `A`/`S`; nota ETL "si pone S el resto de campos no se rellenan" | `allowed_values: [A, S]` + restricción REFERENCIA/CONDICIONAL — refuerza que el esquema necesita más que `max_length`/`overflow_policy` |
| Bypass | `GOS` | Campo calculado por la plataforma, no por este ETL | Tipo de restricción nuevo, no listado: `system_managed: true` |
| Safety Meetings | `TitleEN` (`Parametro=239`, hoja `Title_map`, regla `titlefix`) | `239` podría ser un `max_length`, sin confirmar — mismo motor `titlefix` no documentado ya registrado en CLAUDE.md | Candidato a `max_length`, **no confirmado** |
| Drills | — | No se encontró ningún candidato de `max_length`/truncamiento en las evidencias ya escritas de Drills | Sin candidato — se registra la ausencia, no se inventa uno |

El caso hipotético del encargo ("Title max 20", `LEFT(valor, N)`/`IZQUIERDA`) **no tiene todavía un ejemplo real confirmado** en ninguno de los 3 módulos — el candidato más cercano (`TitleEN`/`239`) es plausible pero no verificado. El esquema futuro (`constraints: {max_length, overflow_policy}`) NO se fija en este sprint porque la evidencia (`AutorizaOPoneEnServicioFase2/3/4`, `GOS`) ya muestra que `max_length`/`overflow_policy` por sí solos no bastarían para los casos reales encontrados — haría falta al menos `allowed_values`/tipo condicional y `system_managed`, no solo longitud.

---

## Fase 10 — Multi-object

`WorkspaceManifest.ModuleSpec` hoy: `module_id` 1:1, `target_object: str | None` 1:1, `artifacts: Mapping[str, ArtifactSpec]` — un solo artefacto por `kind` por módulo. Esto es exactamente lo que bloquea a Safety Meetings: no hay forma de declarar un `operational_csv` distinto para `Group_Meetings` y para `Update_External_Meeting_Participations` bajo el mismo `module_id`.

**Comparación con gaps conocidos:**
- **MOC:** su gap documentado (dos numeraciones `IDCentro` distintas, ITP vs GCT) es de **traducción de sistema de origen**, no de artefactos por objeto de destino — forma distinta a la de Safety Meetings, no debe asumirse el mismo modelo.
- **Events (antiguos+nuevos+PSM) / Inspections:** CLAUDE.md los documenta como teniendo múltiples variantes de ETL/origen, pero **ninguno de los dos ha sido auditado todavía por este prototipo** — no hay evidencia de código propia (a diferencia de Safety Meetings) para confirmar si su gap tiene la misma forma (múltiples objetos Enablon de destino) o una distinta (como MOC). Se registra como pendiente de su propia auditoría, no se asume.

**Modelo mínimo propuesto (diseño, NO implementado, NO se toca el schema):** añadir un nivel opcional `objects: Mapping[str, ObjectSpec]` dentro de `ModuleSpec`, donde `ObjectSpec` repite la forma de `target_object`+`artifacts` que hoy vive directamente en `ModuleSpec`. Para módulos single-object (Drills, Bypass), `target_object`/`artifacts` siguen funcionando exactamente igual que hoy — sin `objects` declarado, sin cambio de comportamiento. Para Safety Meetings, `objects={"group_meetings": ObjectSpec(target_object="Group_Meetings", artifacts={...}), "update_participations": ObjectSpec(...)}`. Esto no rompe ningún módulo single-object existente y da a MOC/Events/Inspections un modelo disponible el día que su propia auditoría confirme si lo necesitan.

---

## Fase 11 — Tests

8 tests nuevos en `tests/test_export_engine.py`:
- 5 tests de comportamiento directo sobre `identifiers.py`/`lookups.py`/`writer.py` (incluye `test_write_csv_nunca_sobrescribe`).
- 1 test de identidad cruzada (`test_drills_bypass_y_safety_meetings_comparten_la_misma_funcion_no_una_copia`) — compara por `is`, no solo por comportamiento, que los 3 módulos apuntan al MISMO objeto función del Engine.
- 2 tests arquitectónicos actualizados (`test_bypass_ya_no_importa_directamente_de_drills` reforzado a "cero" en vez de una lista de excepciones permitidas; `test_safety_meetings_ya_no_importa_directamente_de_drills`, nuevo).

Los tests arquitectónicos ya existentes (`test_engine_no_importa_drills_ni_bypass`, `test_engine_no_tiene_condicionales_por_module_id`) recogen automáticamente los 3 ficheros nuevos por glob (`_ENGINE_FILES`), sin necesidad de listarlos a mano — confirmado que `identifiers.py`/`lookups.py`/`writer.py` no importan de `src.export.prototype` y no tienen ningún `if module_id == ...`.

Ningún test existente de Drills/Bypass/Safety Meetings necesitó modificarse — todos siguen accediendo a los helpers vía el namespace de su propio `transformations`/`exporter` (`tr.to_historical_id`, etc.), que ahora delega en el Engine.

**Resultado: 836 -> 844 passed (+8), 7 skipped, cero regresiones.**

---

## Fase 12 — Métrica post-9.8

| | Antes de 9.8 | Después de 9.8 |
|---|---|---|
| `drills/transformations.py` | 281 líneas | 220 líneas (-22%) |
| `bypass/transformations.py` | 52 líneas | 54 líneas (+4%, más docstring de evidencia) |
| `safety_meetings/transformations.py` | 55 líneas | 50 líneas (-9%) |
| `drills/exporter.py` | 73 líneas | 15 líneas (shim, -79%) |
| **Subtotal módulos** | **461 líneas** | **339 líneas (-26,5%)** |
| `engine/identifiers.py` + `engine/lookups.py` + `engine/writer.py` | 0 | 213 líneas |
| **Total (módulos + Engine)** | **461 líneas** | **552 líneas (+19,7%)** |

**Lectura honesta, sin inventar precisión:** el total NETO de líneas sube, no baja — la ganancia de este sprint no es "menos código", es la eliminación del acoplamiento módulo-a-módulo (Bypass y Safety Meetings ya no importan nada de `drills` para utilidades genéricas, confirmado por los 2 tests arquitectónicos nuevos) y una reducción real del código que cada módulo tiene que mantener por su cuenta (-26,5%). El incremento en el total se explica casi enteramente por los docstrings de evidencia de los 3 ficheros nuevos del Engine (convención ya establecida del proyecto, no bloat accidental).

**Duplicación relevante restante:** ninguna en `identifiers`/`lookups`/`writer` (0 copias, solo imports). La duplicación real que queda es **estructural, no textual**: la forma del `run()` de cada `pipeline.py` (setup -> extract -> transform -> write -> validate -> manifest -> return) es casi idéntica entre Bypass y Safety Meetings (237 vs 218 líneas totales, de las cuales `_transform_rows` module-specific es ~60/~50) — esa es la duplicación que la Fase 5 diseña pero no implementa.

---

## Fase 13 — Decisión del siguiente sprint

Opciones evaluadas: A (Safety Meetings sample real) / B (pipeline genérico) / C (Evidence genérico) / D (entity-resolution capability) / E (cuarto módulo) / F (multi-object manifest).

- **B (pipeline genérico):** el diseño de la Fase 5 muestra que solo hay evidencia sólida para 2 piezas más (`_transform_rows` como hook, `determine_status` ya resuelto) — implementarlo ahora con 3 módulos reales pero sin un 4º que lo ponga a prueba arriesga sobregeneralizar sobre Drills (el único con comparación/evidence/issues.jsonl).
- **C (Evidence genérico):** requiere decisiones de diseño (Fase 8) que todavía no tienen un segundo caso de uso real que las valide.
- **D (entity-resolution):** bloqueado por un artefacto de datos ausente (Fase 4), no por trabajo de ingeniería — no hay nada que implementar hasta que exista el crosswalk `IDUnidadOrg->Code` para Bypass/Safety Meetings.
- **E (cuarto módulo):** daría un 4º punto de datos real para B, pero antes de invertir en un módulo nuevo sin validar ninguno de los 3 ya construidos contra SQL real, el riesgo es acumular más superficie sin confirmar que el patrón aguanta producción.
- **F (multi-object manifest):** el diseño de la Fase 10 ya está listo para implementarse, pero solo tiene un caso real confirmado (Safety Meetings) — implementarlo ahora sin un segundo caso (Events/Inspections, pendientes de su propia auditoría) tiene el mismo riesgo que B.

**Recomendación principal: A — Safety Meetings first real sample.** Coincide con mi hipótesis inicial, confirmada por la evidencia del sprint, no asumida: es la única opción que no requiere ninguna decisión de diseño nueva (el módulo ya está `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY` desde Sprint 9.7), da un 3er punto de datos real de comparación (Fase 7) y de volumen de warnings/status (Fase 3, útil para decidir la migración de Bypass con datos en vez de con una muestra de 10 filas), y no tiene ninguna dependencia bloqueante (a diferencia de D). Requiere autorización explícita de SQL real, no incluida en este sprint.

---

## Confirmaciones finales

- No se ha ejecutado SQL real.
- No se ha ejecutado modo `full`.
- No se ha implementado multi-object (solo diseñado, Fase 10).
- No se ha tocado Evidence genérica (solo analizado, Fase 8).
- No se han implementado Field Constraints (solo candidatos registrados, Fase 9).
- No se ha tocado DataWorkspace/runs.
- No se han tocado Action Plans.
- No se ha hecho push.
- No se ha modificado `src/core/` — cero blockers que lo requirieran.
- No hay workspace real, outputs reales, datos de cliente ni secretos versionados en los cambios de este sprint.
