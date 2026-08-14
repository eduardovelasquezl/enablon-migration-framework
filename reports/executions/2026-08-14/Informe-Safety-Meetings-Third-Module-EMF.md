# Sprint 9.7 — Safety Meetings, tercer módulo sobre el Export Engine mínimo

**Status alcanzado:** `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY`. Ningún SQL
real ejecutado. Sin commit, sin push. Cero cambios en `src/core/`.

---

## Fase 0 — Preflight

Rama `feature/drills-filtered-exports`. Commits `e5f8a91`/`f24f5fd`
presentes, ambos sin `push` (`ahead 2`). Baseline: **815 passed, 7
skipped**. `.claude/settings.local.json`/informes 9.5/9.5.1 confirmados
fuera de alcance de este sprint. `git diff --check` limpio.

## Fase 1/2/3 — Inventario, single vs. multi-object, decisión

Ver `docs/07-developer-guide/safety-meetings-module.md` para el detalle
completo con evidencia (ETL de 40 hojas, SQL, CSV Template/Operational
reales, `workspace.yaml` real).

**Conclusión decisiva:** Safety Meetings **es genuinamente multi-object**
(2 objetos Enablon reales: `Group_Meetings` y
`Update_External_Meeting_Participations`) -- confirmado por 3 fuentes
independientes (el propio `workspace.yaml` real ya lo documentaba antes de
este sprint, 3 ficheros SQL distintos en `sql/source_queries/SM/`, y
cabeceras de CSV reales estructuralmente distintas). `Update_External_Meeting_Participations`
además referencia al `Id` que Enablon asigna DESPUÉS de cargar la reunión
(no un `CS_HistoricalOriginID`) -- es un paso de enlace posterior a la
migración, no un export histórico paralelo.

**Decisión: GO, acotado al objeto principal inequívoco (`Group_Meetings`).**
No es forzar un artefacto único falso -- es exactamente el mismo criterio de
"incremento vertical" que Drills/Bypass ya aplicaron a nivel de columna,
aplicado aquí a nivel de objeto. `Update_External_Meeting_Participations`
se registra explícitamente como `MULTI_OBJECT_GAP` (en
`ModuleDefinition.metadata`, en `workspace.yaml`, y en la documentación) --
no bloquea este incremento, sí bloquea la cobertura completa de "Safety
Meetings" como concepto de negocio.

## Fase 4 — Registro del módulo

`module_id = "safety_meetings"` (verificado contra `config/modules.yaml` y
`workspace.yaml` reales -- **no** `"SM"`, que en este proyecto identifica
Safety Meetings dentro de la nomenclatura genérica del sistema ITP, no un
alias de otro módulo). `canonical_name = "Group_Meetings"` (nombre real del
objeto Enablon, confirmado en los CSV Template/Operational). Registrado en
`src/bootstrap/module_registry.py::_build_safety_meetings_definition()`,
mismo patrón exacto que Drills/Bypass. **Cero cambios en `src/core/`.**

## Fase 5 — Export config

`config/exports/safety_meetings.yaml`: 7 campos (4 VERIFIED, 3
STRONGLY_EVIDENCED), 8 grupos de `excluded_columns` con evidencia
individual, más 1 discrepancia registrada aparte (`CS_HistoricalDataOrigin`
declarado por el ETL pero ausente de los 2 CSV reales verificados). Ningún
campo copiado de Drills/Bypass y renombrado -- cada regla tiene su propia
hoja del ETL real de Safety Meetings como evidencia.

## Fase 6 — Query / filter catalog

`sql/source_queries/SM/SM2025.sql`: `SELECT` directo sobre
`ITP_REUNION_GRUPO`, **sin `JOIN`** (la SQL más simple de los 3 módulos
reales -- cero riesgo de inflación/sub-conteo, a diferencia del hallazgo de
Bypass). SELECT-only confirmado (grep de verbos DML/DDL, sin
coincidencias). Sin `ORDER BY` propio -- mismo patrón que Bypass, orden en
pandas por `FechaCreacion`. `SAFETY_MEETINGS_FILTER_CATALOG`
(`src/query/catalog.py`): 4 campos (`historical_origin_id`/`center_id`/
`origin_org_unit_id`/`workflow_phase_id`), mismo mecanismo cerrado/tipado/
parametrizado/server-side ya usado por Drills/Bypass.

## Fase 7 — Reutilización del Engine

Ver tabla completa en `safety-meetings-module.md` § 2. Resumen: **7 piezas
REUSED_ENGINE** (config loader, extractor, `is_missing`, `BaseRunStats`+
`build_*_section`, `determine_status`, validator core, `GenericQueryStage`),
**0 ENGINE_GAP bloqueante**, **0 piezas copiadas** de las ya extraídas en
Sprint 9.6. `to_historical_id`/`resolve_workflow_status`/`LookupResult` se
reutilizan de `drills.transformations` (mismo precedente cross-módulo que
Bypass ya estableció, NO del Engine todavía) -- clasificado explícitamente
como evidencia para Sprint 9.8, no como gap de este sprint (ver Fase 17).

## Fase 8 — Transformaciones

`safety_meetings/transformations.py` (55 líneas): 2 funciones reutilizadas
sin cambios (`to_historical_id`, `resolve_workflow_status` renombrado
`resolve_lookup`), 1 función nueva genuina (`passthrough_or_empty`, ~10
líneas, sin equivalente exacto en Drills/Bypass). Sin acceso a SQL, sin
acceso al workspace real desde los tests -- 9 tests unitarios con datos
100% sintéticos (`tests/test_safety_meetings_transformations.py`).

## Fase 9 — Pipeline wrapper: métrica real, no la estimación

**La estimación de Sprint 9.6 ("~70-90 líneas en vez de ~400") no se
cumplió tal cual -- la métrica real es más matizada y más honesta:**

| Fichero | Bypass ANTES del Engine (Sprint 9.4, commit `e5f8a91`) | Safety Meetings CON el Engine (Sprint 9.7) | Reducción |
|---|---:|---:|---:|
| `config.py` | 105 | 45 | **-57%** |
| `extractor.py` | 112 | 52 | **-54%** |
| `validator.py` | 64 | 36 | **-44%** |
| `manifest.py` | 135 | 115 | -15% |
| `core_adapters.py` | 157 | 142 | -10% |
| **Subtotal "infraestructura"** | **573** | **390** | **-32%** |
| `pipeline.py` (orquestación) | 237 | 218 | -8% (ruido, no reducción real) |
| `transformations.py` | 69 | 55 | -20% (parcial, no por el Engine) |
| **Total módulo** | **879** (incl. `__init__.py`) | **674** | **-23%** |

**Lectura honesta:** el Engine SÍ reduce sustancialmente los ficheros que
extrajo (`config`/`extractor`/`validator`, -44% a -57%) -- esa parte de la
hipótesis de Sprint 9.6 se confirma con creces. Pero `manifest.py` y
`core_adapters.py` se redujeron mucho menos de lo esperado (-15%/-10%)
porque la mayoría de su contenido ya era module-specific incluso antes
(secciones de manifest propias, `StageResult`/`ArtifactReference`
específicos). Y `pipeline.py` -- la pieza más grande y la que Sprint 9.5.1/
9.6 ya habían clasificado `WAIT_FOR_THIRD_MODULE` -- **prácticamente no se
redujo** (237→218, -8%, diferencia de contenido real, no de mecanismo):
confirma con un tercer punto de datos que esta es exactamente la pieza que
falta generalizar, y que hacerlo tendrá el mayor impacto de los pendientes.

**Ningún pipeline.py.a-medias**: se registra tal cual, sin perseguir
artificialmente el 70-90 estimado -- la métrica real (-32% en la parte
extraída, -8% en la que no) es más valiosa que forzar el número.

## Fase 10 — Validation y `determine_status`

Ver `safety-meetings-module.md` § 4. Decisión propia, no copiada: Safety
Meetings usa el `determine_status` de 3 estados del Engine (como Drills),
NO el de 2 estados de Bypass -- porque ninguno de sus 3 lookups tiene
default documentado, así que `unresolved`/`empty` son casos reales y
frecuentes (confirmado: ~19 filas con `CS_Level`/`CS_Letter` vacíos en el
Operational real) que un `SUCCESS` sin matices ocultaría. Confirmado con
test dedicado. **Esta es la 2ª de 3 implementaciones reales que elige 3
estados** (Drills por herencia histórica, Safety Meetings por análisis
propio) -- refuerza que 3 estados debería ser el default del Engine, y que
el 2-estados de Bypass es la excepción que debería revisarse (ver Fase 17).

## Fase 11 — Evidence

Sin cambios respecto a Sprint 9.5.1/9.6: `src/evidence/` sigue hardcodeado
a Drills. Safety Meetings alcanza `OFFLINE_SAMPLE_READY` sin Evidence
(`ModuleCapabilities` no la declara). `EVIDENCE_ENGINE_GAP` registrado, no
resuelto -- 3ª confirmación de que esto bloqueará cualquier módulo nuevo
hasta que se generalice.

## Fase 12 — Project Contract / comparison

Operational real: `Reuniones de grupo import completo.csv`, **1734 filas**
(contadas con `csv` module respetando multilínea -- `wc -l` da 9013,
incorrecto, mismo error metodológico ya evitado para Bypass).
`CS_HistoricalOriginID` **sin corrupción** (IDs limpios: 5303, 5305,
5310...) -- a diferencia de Bypass, ningún hallazgo de formato aquí.
`comparison.py` sigue sin conectar a este módulo. No se ha modificado el
Operational. No se ha normalizado nada silenciosamente.

## Fase 13 — Field Constraint candidates

`TitleEN` (regla `titlefix`, `Parametro=239`) registrado como candidato --
posible `max_length=239`, no confirmado. Ningún `value[:N]` implementado
en el módulo -- ver `safety-meetings-module.md` § 5.

## Fase 14 — Offline pipeline test end-to-end

`tests/test_safety_meetings_pipeline.py` (12 tests, todos verdes) cubre
los 11 puntos del checklist: ModuleRegistry reconoce el módulo,
`pipeline_factory` construye definición+contexto, `GenericQueryStage`
funciona (vía el test de filtros + el test de CLI con SQL mockeado),
filtros compilan server-side, transformaciones producen las columnas
esperadas, validator funciona, CSV/manifest se generan, SQL Guard permanece
fail-closed sin autorización, y la suite completa (836 tests) confirma sin
regresiones en Drills/Bypass.

## Fase 15 — Readiness real offline

`workspace.yaml` real editado localmente (fuera de Git, mismo patrón que
Bypass en Sprint 9.4): `enabled: false/status: planned` →
`enabled: true/status: in_progress`, `template_csv`/`operational_csv`
resueltos a los 2 artefactos reales de `Group_Meetings` específicamente
(no un pick arbitrario -- ver Fase 2/3).

```
$ python main.py workspace validate --manifest <workspace.yaml real>
Resultado: OK -- sin violaciones.

$ python main.py workspace readiness --manifest <workspace.yaml real> \
    --module safety_meetings --operation sample
Status: ready
Blockers (0):
Warnings (0):
EXITCODE=0
```

`ResourceResolver` confirma `operational_csv` único, existente
(`exists=True`), sin ambigüedad -- exactamente el mismo patrón ya probado
para Bypass.

## Fase 16 — Métrica del Engine: tabla consolidada

| Métrica | Drills (Sprint 8.6, sin Engine) | Bypass (Sprint 9.4, sin Engine / Sprint 9.6, con Engine) | Safety Meetings (Sprint 9.7, con Engine desde el inicio) |
|---|---:|---:|---:|
| Líneas módulo (config+extractor+validator+manifest+core_adapters) | N/A (base histórica, no medida en el mismo formato) | 573 (antes) → 390 (después) | 390 |
| Líneas `pipeline.py` | 687 | 237 (sin cambios por el Engine) | 218 |
| Líneas `transformations.py` propias (no reutilizadas) | 296 (toda propia, es la fuente) | ~15 nuevas (`nullcontrol_passthrough`) de 69 (antes)/52 (después) | ~10 nuevas (`passthrough_or_empty`) de 55 |
| Generic code reused (Engine) | 0 (Sprint 8.6, Engine no existía) | 6 piezas (tras Sprint 9.6) | 7 piezas (desde el inicio) |
| Duplicated generic code | N/A | 0 (tras Sprint 9.6) | 0 |
| Tests nuevos | (histórico) | 9 (Sprint 9.4) | 21 (9 transformaciones + 12 pipeline) |
| Core changes | 0 | 0 | 0 |
| Engine changes | N/A (no existía) | 0 (en Sprint 9.4; el Engine se creó DESPUÉS, en Sprint 9.6, a partir de Drills+Bypass) | 0 |

**¿Fue Safety Meetings realmente más barato gracias al Engine?**
**Parcialmente sí, de forma medible y honesta -- no dramáticamente.** Los 3
ficheros que el Engine extrajo limpiamente (`config`/`extractor`/
`validator`) costaron un 44-57% menos escribirlos que la primera vez
(Bypass, sin Engine). Los otros 2 (`manifest`/`core_adapters`) costaron
bastante menos que eso (10-15%) porque una parte grande de su contenido
siempre fue, correctamente, module-specific. Y la pieza más cara con
diferencia (`pipeline.py`, ~220-240 líneas en los 2 módulos con Engine)
**no se abarató en absoluto** -- confirma que el Engine resolvió la
duplicación de "andamiaje" (config/extracción/validación estructural) pero
NO la de "orquestación de negocio" (mapear filas, decidir inclusión/
exclusión, montar el manifest final), que sigue costando lo mismo módulo
tras módulo.

## Fase 17 — Tercer punto de datos: reevaluación de generalización

| Pieza | Clasificación (3 módulos) | Evidencia |
|---|---|---|
| Config loader | **PROVEN_GENERIC** | 3/3 módulos, -44% a -57% de coste al añadir el 3º -- evidencia sólida y repetida |
| Extractor | **PROVEN_GENERIC** | 3/3 módulos, mismo patrón `sort_column` param (2 de 3 lo necesitan, 1 no) |
| Query Stage | **PROVEN_GENERIC** | 3/3 módulos, cero clase propia por módulo desde Sprint 9.6 |
| Validator (núcleo estructural) | **PROVEN_GENERIC** | 3/3 módulos; Drills sigue envolviendo con reglas propias (esperado, correcto) |
| Manifest (núcleo: hashing/sections) | **PROVEN_GENERIC** | 3/3 módulos; la parte NO genérica (secciones propias, `determine_status` de 2 vs. 3 estados) también se confirma real y recurrente |
| `determine_status` (2 vs. 3 estados) | **PROBABLY_GENERIC (3 estados, no 2)** | 2 de 3 módulos (Drills, Safety Meetings) llegan independientemente a 3 estados; Bypass es la excepción sin migrar, no la norma -- evidencia de que el DEFAULT del Engine (ya 3 estados) es el correcto, y Bypass debería migrarse |
| `to_historical_id`/`resolve_letter`-familia (`LookupResult`) | **PROVEN_GENERIC, todavía NO en el Engine** | 3/3 módulos las necesitan idénticas, vía import cross-módulo desde `drills.transformations` -- cruza el umbral de evidencia que Sprint 9.6 fijó para `_is_missing` ("esperar una 3ª necesidad real") |
| `pipeline.py` (orquestación completa) | **STILL_INSUFFICIENT_EVIDENCE (para extraer TODO), pero con forma más clara** | 3/3 módulos con forma MUY similar (extraer→transformar fila a fila→escribir CSV→validar→manifest) -- suficiente para diseñar una interfaz, aún no para garantizar que generalizarla no pierda flexibilidad real (Drills tiene comparison+issues que los otros 2 no) |
| Transform/Export Stage | **STILL_INSUFFICIENT_EVIDENCE** | Mismo motivo que `pipeline.py` -- lo envuelve 1:1 |
| CSV writer (`write_csv`) | **PROVEN_GENERIC, ya reutilizado** | 3/3 módulos importan literalmente la misma función de `drills.exporter` -- nunca se copió, solo falta moverla formalmente al Engine |
| Comparison | **STILL_INSUFFICIENT_EVIDENCE** | 0/3 módulos la tienen conectada fuera de Drills |
| Evidence | **STILL_INSUFFICIENT_EVIDENCE (motor), MODULE_SPECIFIC (necesidad)** | 3/3 módulos la necesitarían, 0/3 la tienen -- sigue hardcodeada a Drills |
| Output management (ubicación) | **MODULE_SPECIFIC hoy, PROVEN que el patrón es idéntico** | 3/3 módulos usan `outputs/prototype/<módulo>/<timestamp>/` con la misma lógica de creación/no-overwrite -- centralizable sin romper nada |

## Fase 18 — Siguiente generalización (no implementada aquí)

**Prioridad recomendada, basada exclusivamente en la evidencia de 3
módulos:**

1. **Mover `to_historical_id`/`resolve_letter`/`resolve_workflow_status`/
   `LookupResult` al Engine** (`src/export/engine/transformations.py` o
   ampliar `values.py`) -- riesgo mínimo (3/3 idénticas, ya
   cross-importadas sin fricción), esfuerzo bajo, elimina el último
   acoplamiento módulo→módulo (`bypass`/`safety_meetings` → `drills`)
   que quedó fuera de alcance en Sprint 9.6.
2. **Migrar Bypass a `determine_status` de 3 estados** -- ahora con 2/3
   módulos ya usándolo de forma independiente, mantener la excepción de 2
   estados es la anomalía, no la norma. Cambio de comportamiento
   observable menor y ya documentado -- decisión explícita de un sprint
   dedicado (nunca silenciosa).
3. **Generalizar `pipeline.py`/Transform-Export Stage** -- ahora con 3
   formas reales para comparar (no 2), pero AÚN sin la señal más fuerte
   posible (ninguna tiene comparison+issues+evidence simultáneamente salvo
   Drills). Recomendación: diseñar la interfaz ahora que hay 3 puntos de
   datos, pero validarla contra un 4º módulo antes de migrar Drills (el
   único con la forma completa) -- mayor riesgo de las 3 opciones.
4. **NO priorizar todavía**: Evidence genérica (sigue siendo 0/3, sin
   mover el mecanismo hasta que algún módulo lo necesite de verdad) ni
   output a DataWorkspace (cambio de infraestructura, no de código
   compartido).

**Elegir un 4º módulo antes que (3)** si se prioriza seguir acumulando
evidencia de bajo riesgo; elegir (3) antes que un 4º módulo si se prioriza
reducir deuda ahora que el patrón ya es visible 3 veces. Este informe no
elige por el usuario -- ambas son defendibles con la evidencia disponible.

## Fase 19 — Suite completa

```
815 passed, 7 skipped   (baseline)
836 passed, 7 skipped   (final -- +21 tests nuevos: 9 transformaciones + 12 pipeline)
```

Cero regresiones. `git diff --check`: limpio (solo avisos LF/CRLF).

## Fase 20 — Documentación

`docs/07-developer-guide/safety-meetings-module.md` (nuevo) +
`reports/executions/2026-08-14/Informe-Safety-Meetings-Third-Module-EMF.{md,txt}`
(este documento). No se ha creado documentación redundante -- el detalle
de evidencia completo vive en el doc de desarrollador, este informe se
centra en las decisiones y métricas del sprint.

---

# PUERTA FINAL — 21 PUNTOS

1. **Estado:** `SAFETY_MEETINGS_OFFLINE_SAMPLE_READY`.
2. **Single-object / multi-object:** multi-object confirmado (2 objetos
   Enablon reales); este incremento cubre únicamente `Group_Meetings`
   (objeto principal inequívoco); `Update_External_Meeting_Participations`
   registrado como `MULTI_OBJECT_GAP`, no implementado.
3. **Artifacts reales identificados:** ETL (`ETL- Reunionesdegrupo-fixEntities_SITECAN.xlsx`,
   40 hojas), SQL (`sql/source_queries/SM/SM2025.sql` + 2 más fuera de
   alcance), Template (`Group Meetings-40.csv`), Operational (`Reuniones
   de grupo import completo.csv`, 1734 filas), catálogo First_Axis
   (compartido con Drills/Bypass).
4. **Project Contract:** `Reuniones de grupo import completo.csv`,
   resuelto vía `ResourceResolver` contra el `workspace.yaml` real
   (`exists=True`, único, `contract_role=project`).
5. **Mappings VERIFIED:** `CS_HistoricalOriginID` (IDReunionGrupo),
   `CS_WorkflowStatus` (FaseActual, 4 valores), `CS_Level` (IDNivel, 7
   valores), `CS_Letter` (IDLetra, 7 valores) -- los 4 cruzados contra
   datos reales.
6. **Mappings unresolved:** `CS_Entity` (mismo gap sistémico que Bypass),
   `CS_Scope`, `TitleEN` (titlefix), `CS_PendingIssues` (concat sin
   parámetros), `Duration` (2 fuentes en conflicto) -- ver tabla completa
   en `safety-meetings-module.md`.
7. **Query seleccionada:** `SM2025.sql`, SELECT directo sobre
   `ITP_REUNION_GRUPO`, sin JOIN, sin ORDER BY propio.
8. **Filter catalog:** `SAFETY_MEETINGS_FILTER_CATALOG` -- 4 campos
   (`historical_origin_id`, `center_id`, `origin_org_unit_id`,
   `workflow_phase_id`).
9. **Readiness sample:** `ready`, 0 blockers, 0 warnings (offline, contra
   `workspace.yaml` real).
10. **Tests nuevos:** 21 (9 `test_safety_meetings_transformations.py` + 12
    `test_safety_meetings_pipeline.py`).
11. **Suite completa:** 815 → 836 passed, 7 skipped, 0 regresiones.
12. **Líneas module-specific aprox.:** 674 líneas totales del módulo (390
    "infraestructura" ya reducida por el Engine + ~218 `pipeline.py` +
    ~55 `transformations.py`, con solapamiento de contenido reutilizado
    dentro de esos ficheros).
13. **Engine reutilizado:** 7 piezas (config loader, extractor, `is_missing`,
    `BaseRunStats`+`build_*_section`, `determine_status`, validator core,
    `GenericQueryStage`) -- 0 copiadas.
14. **Engine gaps:** `to_historical_id`/`resolve_letter`-familia todavía
    fuera del Engine (3ª necesidad real, candidato fuerte para Sprint
    9.8); Evidence sigue sin generalizar; `pipeline.py`/Transform-Export
    Stage siguen sin evidencia suficiente para extraer con confianza.
15. **Core changes:** ninguno.
16. **Comparación Drills/Bypass/Safety Meetings:** ver Fase 16 -- el
    Engine reduce 32% la "infraestructura" (config/extractor/validator),
    prácticamente 0% la orquestación (`pipeline.py`).
17. **Qué generalizar después (3 puntos de datos):** (1) mover
    `to_historical_id`/`resolve_letter`-familia al Engine, (2) migrar
    Bypass a `determine_status` de 3 estados, (3) diseñar (no implementar
    todavía) la interfaz de `pipeline.py`/Transform-Export Stage.
18. **Candidate filter para primer sample real:** `historical_origin_id:in:5303,5305,5310,5364,5607,5613,5721,5722,5723,5724`
    (los 10 IDs más bajos del Operational real, sin decodificación
    necesaria).
19. **Comando propuesto, NO ejecutado:**
    ```
    python main.py --verbose run --project moeve --object safety_meetings --mode sample --limit 15 \
      --filter "historical_origin_id:in:5303,5305,5310,5364,5607,5613,5721,5722,5723,5724" \
      --allow-real-sql
    ```
    Verificado offline (sin `--allow-real-sql`): parser acepta objeto/modo/
    filtro sin error, SQL Execution Guard bloquea limpiamente, exit code 1,
    "No se abrió ninguna conexión."
20. **Propuesta de commit(s):** un único commit,
    `feat(safety-meetings): implement third EMF module on the minimal Export Engine`,
    incluyendo módulo nuevo, config YAML, filter catalog, registro en
    ModuleRegistry, tests, documentación -- **no creado todavía**, a la
    espera de autorización explícita.
21. **Confirmaciones:**
    - 0 SQL real ejecutado.
    - 0 `full` ejecutado.
    - 0 push.
    - 0 datos reales versionados en Git (el CSV Operational/ETL permanecen
      en `%EMF_DATA_ROOT%`, fuera del repositorio).
    - 0 secretos.
    - `workspace.yaml` real: editado localmente, fuera de Git (mismo
      patrón ya usado para Bypass).
    - Outputs reales: ninguno generado (todas las ejecuciones de este
      sprint usan `tmp_path`/datos sintéticos).

**NO se ha ejecutado SQL, aunque el módulo queda READY. La ejecución real
requiere autorización explícita posterior.**
