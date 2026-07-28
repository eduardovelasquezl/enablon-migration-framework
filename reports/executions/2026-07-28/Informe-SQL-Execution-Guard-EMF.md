# Informe de ejecución — Sprint 8.6.1: SQL Execution Guard

**Fecha:** 2026-07-28
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Corrección de seguridad — autorización explícita obligatoria
para cualquier ejecución que pueda abrir una conexión SQL Server real.
Ningún SQL real ejecutado durante este sprint.

## 1. Resumen ejecutivo

Se implementó el SQL Execution Guard: un único punto de bloqueo
(`src/db/connection.py::get_engine()`, justo antes de `create_engine()`)
que exige una autorización explícita y vigente
(`src/db/sql_execution_guard.py`) antes de permitir la construcción de
cualquier motor de conexión real. La CLI (`run`, `export drills`) exige
`--allow-real-sql` (o `EMF_ALLOW_REAL_SQL=1`) para `sample` y `full` por
igual — `full` sigue exigiendo, además, la confirmación ya existente
`--confirm-full-export`. Sin autorización: bloqueo antes de tocar SQL, sin
outputs generados, mensaje seguro sin secretos. `CLAUDE.md` se corrigió
para reflejar la realidad del entorno (sí tiene conectividad SQL real;
la disponibilidad no implica autorización). La suite pasó de 612 a 647
casos en verde (+35), 7 skipped sin cambios. No se hizo ningún commit.

## 2. Estado inicial

- Rama y remoto correctos. `git diff --check`: sin errores.
- Único cambio automático: `.claude/settings.local.json` — restaurado.
- Suite completa antes de empezar: **612 passed, 7 skipped** — confirma
  la referencia dada por el encargo.
- Sprints 8.4, 8.5 y 8.6 confirmados sin commit.
- Confirmado: no existen outputs del incidente en el árbol de trabajo
  (`reports/20260728T083255Z/` ya no existía, eliminado durante Sprint
  8.6 antes de que este sprint empezara) y ningún dato real está
  versionado (`git status`/`git log` revisados).
- Ningún comando que pudiera abrir SQL se ejecutó durante la Fase 0/1
  (inventario realizado por lectura de código, no por ejecución).

## 3. Inventario de puntos de conexión (Fase 1)

| Archivo | Función | Puede abrir SQL | Protección actual (antes de este sprint) | Cambio requerido |
|---|---|---|---|---|
| `src/db/connection.py::get_engine()` | Motor de conexión (`create_engine`) | **Sí** — único chokepoint universal | Ninguna (solo credenciales resueltas antes) | **Gateado aquí** — único punto de cambio real |
| `src/db/query_runner.py::run_query()` | Ejecución de query | Sí, vía `get_engine()` | `validate_read_only_sql` (contenido), sin autorización de conexión | Cubierto automáticamente por el gate de `get_engine()`, sin tocar este fichero |
| `src/db/query_runner.py::run_query_file()`/`grouped_count()` | Atajos sobre `run_query` | Sí, vía `run_query` | Igual que `run_query` | Cubierto automáticamente |
| `src/db/metadata.py::list_tables()`/`describe_table()`/`row_count()` | Introspección de esquema | Sí, vía `get_engine()` directo (bypassa `validate_read_only_sql`, usa el inspector de SQLAlchemy) | Solo `validate_identifier` | Cubierto automáticamente por el gate de `get_engine()` — sin este único chokepoint, habría quedado sin cubrir |
| `src/analysis/sql_inventory.py::run_sql_inventory()` | Inventario SQL Server (11 queries de diagnóstico) | Sí, vía `run_query_file` | Igual que `run_query`; sin comando CLI que lo use hoy | Cubierto automáticamente |
| `src/export/prototype/drills/extractor.py::extract_drills()` | Extracción de Drills | Sí, vía `run_query` | Igual que `run_query` | Cubierto automáticamente |
| `src/export/prototype/drills/core_adapters.py::DrillsQueryStage` | Etapa `query` del Core | Sí, vía `extract_drills` | Ninguna adicional | Cubierto automáticamente |
| `src/cli.py::run_pipeline` (`run`) | Comando genérico | Sí, cadena completa | `--confirm-full-export` (solo volumen de `full`, no gateaba `sample`) | **`--allow-real-sql` añadido**, comprobado tras resolución de módulo/capacidad |
| `src/cli.py::export_drills` (`export drills`) | Comando legacy | Sí, cadena completa | Igual que `run` (mismo hueco: `sample`, el modo por defecto, sin gate) | **`--allow-real-sql` añadido**, comprobado tras validaciones baratas (limit/modo/filtros) |
| `tests/test_db_connection.py` (no-integración) | Tests de `get_engine`/caché | Solo con `fake_config` (env sintético) | N/A | Fixture actualizada para conceder autorización `source="test"` |
| `tests/test_db_query_runner.py`/`test_db_metadata.py` | Tests de `run_query`/metadata | No — mockean `get_engine` directamente, nunca llegan al real | N/A | Sin cambios (exentos por diseño, ver § 5) |
| `tests/test_db_connection.py`/`test_sql_inventory.py`/`test_drills_export_integration.py` (integración) | Tests reales contra SQL Server | Sí, si se activan | `RUN_SQL_INTEGRATION_TESTS=1`/`RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1`, `skipif`, desactivados por defecto | Sin cambios — mecanismo ya correcto, confirmado que sigue `skip` por defecto |
| `workspace validate`/`workspace resolve`/`modules list`/`modules show`/`evidence drills` | Comandos sin SQL | No | N/A | Sin cambios — no se añadió `--allow-real-sql` (no aplica) |

Clasificación: el ÚNICO cambio de código necesario es en `get_engine()` —
todo lo demás queda cubierto automáticamente por ser un único chokepoint
universal (ver § 4 del diseño).

## 4. Causa raíz

`--confirm-full-export` protegía el VOLUMEN de una exportación `full`,
nunca la DECISIÓN de abrir una conexión SQL real — y `sample` (el modo
por defecto de ambos comandos) no tenía ninguna comprobación equivalente.
El entorno de trabajo tiene conectividad real legítima (usuario readonly
`ClaudeReadOnly`), así que cualquier invocación manual de `run`/
`export drills` sin mock, incluso en modo `sample`, abría una conexión
real sin que nada lo impidiera ni lo advirtiera de antemano. La
documentación (`CLAUDE.md`) además afirmaba lo contrario ("este entorno
no tiene conectividad de red directa a SQL Server"), lo que reforzó la
falsa sensación de seguridad que llevó al incidente de Sprint 8.6.

## 5. Modelo de autorización

`src/db/sql_execution_guard.py`:

```python
@dataclass(frozen=True)
class SqlExecutionAuthorization:
    source: str        # "cli_flag" | "env_var" | "test"
    granted_at: datetime

def grant(*, source: str) -> SqlExecutionAuthorization: ...
def revoke() -> None: ...
def is_authorized() -> bool: ...
def require(connection_name: str) -> None:  # RealSqlNotAuthorizedError si no autorizado
```

Estado de módulo controlado (no un parámetro enhebrado por
`ExecutionRequest`/`PipelineFactory`/`DrillsQueryStage`/`extract_drills`/
`run_query` — cambio de alto riesgo evitado deliberadamente), expuesto
únicamente a través de esa API. Empieza en `None` en cada proceso nuevo
(fail closed). `tests/conftest.py` lo revoca de forma `autouse` antes y
después de cada test — ninguna autorización sobrevive entre tests.

## 6. Comandos protegidos

`run` y `export drills`: `--allow-real-sql` (flag) o `EMF_ALLOW_REAL_SQL=1`
(variable de entorno, equivalente, no se exigen ambos). Comprobado
DESPUÉS de las validaciones baratas y sin efectos secundarios que ya
existían (resolución de módulo/capacidad en `run`; `--limit`, modo +
`--confirm-full-export`, filtros en `export drills`) — mejor mensaje de
error si el problema real es, p. ej., un `--object` mal escrito, sin
tener que resolver primero la autorización SQL — y ANTES de construir la
petición real o invocar el pipeline. `workspace validate`/
`workspace resolve`/`modules list`/`modules show`/`evidence drills`: sin
cambios, nunca requieren la bandera (no tocan SQL).

## 7. Comportamiento `sample`

Requiere `--allow-real-sql` igual que `full` — antes de este sprint no
requería nada (la causa raíz exacta del incidente, § 4). Sin la bandera:
bloqueo antes de `create_engine()`, sin outputs, exit code 1.

## 8. Comportamiento `full`

Requiere `--allow-real-sql` Y `--confirm-full-export` — ninguno sustituye
al otro (verificado por test en sus 4 combinaciones: ninguno, solo
autorización SQL, solo confirmación full, ambos).

## 9. Incidente (Sprint 8.6) — tratamiento formal

**Clasificación:** *Accidental readonly execution — contained.*

- **Comando ejecutado:** `python main.py run --project moeve --object simulacros --mode sample --limit 5 --output-dir "$(pwd)/reports"`, en shell, fuera de la suite de tests (sin el mock de `run_query`).
- **Resultado:** conexión SQL real abierta contra la conexión `prevencion`; **cinco filas leídas**. Ningún contenido de esas filas se incluye en este informe ni en ningún otro documento.
- **Escrituras:** ninguna — el login SQL usado (`ClaudeReadOnly`) solo tiene `db_datareader`; la consulta ejecutada fue la misma `SELECT` de siempre (sin filtros de escritura posibles).
- **Outputs:** `reports/20260728T083255Z/` (CSV + manifiesto + reporte de validación) se generó localmente y se eliminó de inmediato con `rm -rf` en el mismo turno en que se detectó — nunca se ejecutó `git add`, nunca se hizo commit (`git status` antes y después del incidente, y de nuevo al empezar este sprint, lo confirma: el directorio no aparece en ningún momento).
- **Causa raíz:** ver § 4 — ausencia de una comprobación de autorización de conexión, independiente de la comprobación de volumen (`--confirm-full-export`), combinada con documentación (`CLAUDE.md`) que afirmaba incorrectamente que el entorno no tenía conectividad real.
- **Corrección aplicada:** SQL Execution Guard (este sprint completo, § 5-§ 8).
- **Tests añadidos:** 35 (§ 12) — incluyen específicamente la reproducción del escenario del incidente (`run --object simulacros` sin autorización → bloqueado, sin outputs) y su contraparte autorizada.
- **Riesgo residual:** ver § 17.

No se calificó como pérdida ni exposición de datos porque no hay
evidencia de ello — el archivo nunca salió del disco local, nunca se
compartió, nunca se versionó.

## 10. Modelo de commits futuro afectado

Sin cambios de diseño adicionales — ver § 18 para la propuesta
consolidada de los cuatro sprints.

## 11. Verificación readonly

`query_runner.validate_read_only_sql()` y `_BLOCKED_TERMS` sin
modificar — se confirmó por inspección y por la suite existente
(`tests/test_db_query_runner.py`, sin cambios, sigue en verde) que el SQL
Execution Guard no las duplica ni las degrada. Ninguna prueba de este
sprint ejecuta esa validación contra SQL real.

## 12. Tests

Nuevos:

- `tests/test_sql_execution_guard.py` — 12 tests (estado por defecto,
  grant/revoke, `source` inválido, `require()` sin/con autorización,
  mensaje sin secretos, `RealSqlNotAuthorizedError` es `DatabaseError`,
  `get_engine()` bloquea antes de `create_engine` -- verificado con
  `create_engine` sustituido por una función que falla si se llama --,
  `get_engine()` autorizado construye un `Engine` perezoso con
  credenciales sintéticas sin tocar red, excepción no cacheada permite
  reintentar tras autorizar).
- `tests/test_cli_sql_execution_guard.py` — 23 tests (bloqueo por
  defecto en `run`/`export drills`, sin outputs, sin estado de
  autorización filtrado; alias `simulacros` protegido igual;
  autorización vía flag y vía variable de entorno permite llegar al
  mock; `sample` y las 4 combinaciones de `full`×confirmación×
  autorización; comando legacy protegido igual; factory invocada
  directamente en Python con SQL mockeado NO requiere autorización
  -- confirma la regla 5 del encargo con una prueba explícita --;
  comandos sin SQL nunca la requieren; mensajes sin secretos; exit codes
  diferenciados bloqueo-vs-módulo-desconocido; confirmación de que los
  tests de integración real siguen gateados por variable de entorno).

Modificados (adaptación necesaria, no cambio de intención):

- `tests/test_db_connection.py` — fixture `fake_config` concede
  autorización `source="test"` (los dos tests que llaman a `get_engine()`
  real, con credenciales sintéticas, la necesitan ahora).
- `tests/test_drills_core_pipeline.py` — `test_ejecutar_via_cli_generico_sin_sql_real`
  añade `--allow-real-sql` (SQL mockeado más abajo, pero la puerta de la
  CLI no distingue eso).
- `tests/test_drills_export_query_engine.py` — `test_cli_filtro_valido_se_incluye_en_el_resumen`
  añade `--allow-real-sql` por el mismo motivo.
- `tests/conftest.py` (nuevo) — fixture `autouse` que revoca cualquier
  autorización antes/después de cada test de toda la suite.

## 13. Resultados

```
612 passed, 7 skipped   (referencia inicial, confirmada al empezar)
647 passed, 7 skipped   (al terminar -- +35, 0 nuevos skipped, 0 fallos)
```

`py_compile` sin errores. CLI verificada exclusivamente con `--help` y
`CliRunner` (SQL mockeado) — ningún acceso real a SQL Server en ningún
momento de este sprint (verificado explícitamente antes de cada comando
ejecutado manualmente).

## 14. Compatibilidad

- Comandos sin SQL: sin cambios de interfaz ni comportamiento.
- `workspace validate`/`resolve`, `modules list`/`show`, `evidence drills`:
  sin cambios (confirmado por test).
- `run`/`export drills`: **cambio de comportamiento deliberado** — ambos
  exigen ahora `--allow-real-sql` (o la variable de entorno) incluso en
  `sample`. Cualquier script/automatización externa que invocara estos
  comandos sin esa bandera empezará a fallar — es la corrección
  pretendida, no una regresión.
- Tests de integración real: mecanismo de opt-in sin cambios, confirmado
  que siguen `skip` por defecto.

## 15. Archivos creados

- `src/db/sql_execution_guard.py`
- `tests/conftest.py`
- `tests/test_sql_execution_guard.py`
- `tests/test_cli_sql_execution_guard.py`
- `docs/01-architecture/sql-execution-guard.md`
- `reports/executions/2026-07-28/Informe-SQL-Execution-Guard-EMF.md` (+ `.txt`)

## 16. Archivos modificados

- `src/db/connection.py` (gate en `get_engine()`)
- `src/cli.py` (`--allow-real-sql` en `run`/`export drills`, banner de
  autorización no sensible)
- `tests/test_db_connection.py`, `tests/test_drills_core_pipeline.py`,
  `tests/test_drills_export_query_engine.py` (adaptaciones, § 12)
- `CLAUDE.md` (corrección de la fila de "Acceso SQL de solo lectura" +
  nueva restricción no negociable)
- `docs/07-developer-guide/getting-started.md` (fila nueva en tabla § 4)
- `docs/01-architecture/module-registry.md` (§ 14, flujo de la CLI
  actualizado con el nuevo paso)

No se modificó `docs/01-architecture/resource-resolver.md` — no aplica
(`ResourceResolver` no toca SQL en ningún punto).

## 17. Riesgos

- El estado de autorización es un booleano de proceso, no atado a una
  conexión concreta (`prevencion` vs. `gct`) — aceptable hoy (una única
  conexión real por ejecución); documentado como deuda técnica (§ 19 de
  `sql-execution-guard.md`) si algún día hace falta distinguir.
- Cualquier script/automatización externa que invocara `run`/
  `export drills` sin `--allow-real-sql` empezará a fallar — es el
  comportamiento pretendido; se avisa aquí por si existiera alguno no
  descubierto en este repositorio (no se encontró ninguno).

## 18. Deuda técnica

Ver `docs/01-architecture/sql-execution-guard.md` § 13 (estado de
autorización no atado a conexión concreta; `query_timeout_seconds`
declarado en `config/databases.yaml` pero no aplicado en
`query_runner.run_query()`, detectado durante el inventario de este
sprint, no relacionado con autorización).

## 19. Propuesta de commits consolidada — Sprints 8.4, 8.5, 8.6 y 8.6.1 (NO ejecutados)

Cuatro commits separados, en este orden (cada uno deja el repositorio
funcionando y con su propia suite en verde si se aplica de forma aislada
sobre el commit anterior):

**Commit 1 — Sprint 8.4 (Workspace Manifest):** sin cambios respecto a
`Informe-Workspace-Manifest-EMF.md` (2026-07-27).

**Commit 2 — Sprint 8.5 (Resource Resolver):** sin cambios respecto a
`Informe-Resource-Resolver-EMF.md` (2026-07-28), incluyendo el hunk de
`workspace-manifest.md` § 5/§ 6 corregido en Sprint 8.6 (ya señalado en
ese informe).

**Commit 3 — Sprint 8.6 (Module Registry):** sin cambios respecto a
`Informe-Module-Registry-EMF.md` (2026-07-28).

**Commit 4 — Sprint 8.6.1 (SQL Execution Guard), este incremento:**

```
fix(security): require explicit authorization for real SQL execution

Adds a single chokepoint gate (src/db/connection.py::get_engine()) that
requires an explicit, per-execution authorization
(src/db/sql_execution_guard.py) before constructing a real SQLAlchemy
engine -- fail closed, independent of sample/full mode. Wires
--allow-real-sql (and EMF_ALLOW_REAL_SQL=1 as an equivalent) into both
`run` and `export drills`, checked after cheap/side-effect-free
validation and before any pipeline work. Corrects CLAUDE.md, which
incorrectly stated this environment lacks real SQL connectivity --
contained incident: an unmocked manual `run` invocation read 5 real rows
during Sprint 8.6 verification; no writes, outputs deleted before
versioning.
```

Archivos: `src/db/sql_execution_guard.py`, `src/db/connection.py`
(hunk del gate), `src/cli.py` (hunks de `--allow-real-sql`),
`tests/conftest.py`, `tests/test_sql_execution_guard.py`,
`tests/test_cli_sql_execution_guard.py`, `tests/test_db_connection.py`
(hunk de `fake_config`), `tests/test_drills_core_pipeline.py` (hunk de
1 test), `tests/test_drills_export_query_engine.py` (hunk de 1 test),
`CLAUDE.md`, `docs/01-architecture/sql-execution-guard.md`,
`docs/07-developer-guide/getting-started.md` (hunk de 1 fila),
`docs/01-architecture/module-registry.md` (hunk de § 14),
`reports/executions/2026-07-28/Informe-SQL-Execution-Guard-EMF.md` (+`.txt`).

**Excluir de cualquier commit:** `.claude/settings.local.json`.

## 20. `git diff --check`

Sin errores de espacio en blanco (exit code 0) — solo warnings de
conversión de fin de línea LF→CRLF de Git en Windows.

## 21. `git status --short` (al terminar este informe)

```
 M .claude/settings.local.json
 M CLAUDE.md
 M config/data_workspace.yaml
 M docs/01-architecture/extensibility-model.md
 M docs/01-architecture/external-data-workspace.md
 M docs/01-architecture/framework-core-v1.md
 M docs/07-developer-guide/getting-started.md
 M src/cli.py
 M src/db/connection.py
 M src/export/prototype/drills/pipeline.py
 M tests/test_db_connection.py
 M tests/test_drills_core_pipeline.py
 M tests/test_drills_data_workspace_integration.py
 M tests/test_drills_export_query_engine.py
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/module-registry.md
?? docs/01-architecture/project-contract-model.md
?? docs/01-architecture/resource-resolver.md
?? docs/01-architecture/sql-execution-guard.md
?? docs/01-architecture/workspace-manifest.md
?? docs/01-architecture/workspace-naming-convention.md
?? docs/01-architecture/workspace-validation-checklist.md
?? docs/07-developer-guide/drills-real-data-inventory.md
?? examples/
?? reports/executions/2026-07-27/...
?? reports/executions/2026-07-28/
?? src/bootstrap/
?? src/core/module_registry.py
?? src/core/resource_resolver.py
?? src/core/workspace_manifest.py
?? src/db/sql_execution_guard.py
?? tests/conftest.py
?? tests/test_bootstrap_module_registry.py
?? tests/test_cli_modules.py
?? tests/test_cli_sql_execution_guard.py
?? tests/test_cli_workspace_resolve.py
?? tests/test_cli_workspace_validate.py
?? tests/test_module_registry.py
?? tests/test_resource_resolver.py
?? tests/test_sql_execution_guard.py
?? tests/test_workspace_manifest.py
```

(`src/export/prototype/drills/pipeline.py` y
`tests/test_drills_data_workspace_integration.py` son cambios de Sprint
8.5; `config/data_workspace.yaml` y varios `docs/`/`examples/` son de
Sprint 8.4; `extensibility-model.md`, `external-data-workspace.md`,
`framework-core-v1.md` mezclan hunks de Sprint 8.5/8.6 ya informados
previamente.)

## 22. `git diff --stat` (archivos tocados por Sprint 8.6.1)

```
 src/db/sql_execution_guard.py                nuevo (~120 líneas)
 src/db/connection.py                          +~17
 src/cli.py                                    +~90 -~15 (de los +317/-15 totales de src/cli.py, el resto es Sprint 8.6)
 tests/conftest.py                             nuevo (~25 líneas)
 tests/test_sql_execution_guard.py             nuevo (~170 líneas)
 tests/test_cli_sql_execution_guard.py         nuevo (~250 líneas)
 tests/test_db_connection.py                   +~13
 tests/test_drills_core_pipeline.py            +~7 -~1
 tests/test_drills_export_query_engine.py      +~4
 CLAUDE.md                                     +~11
 docs/01-architecture/sql-execution-guard.md   nuevo (~180 líneas)
 docs/07-developer-guide/getting-started.md    +~2
 docs/01-architecture/module-registry.md       +~12
```

## 23. Recomendación

Sprint 8.6.1 completo según los criterios de aceptación del encargo. El
riesgo que motivó este sprint queda cerrado: `sample` y `full` requieren
autorización explícita por igual, el gate está en el único chokepoint
real, y `CLAUDE.md` ya no induce a error sobre la conectividad del
entorno. Recomendado, antes de proceder con los 4 commits de § 19:
confirmación explícita del usuario de que el flujo `--allow-real-sql`
es el que espera usar en el día a día (o si prefiere fijar
`EMF_ALLOW_REAL_SQL=1` de forma más permanente en su entorno local, fuera
de este repositorio).
