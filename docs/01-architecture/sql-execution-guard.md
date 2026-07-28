# SQL Execution Guard — autorización explícita de SQL real

**Status:** Implemented (Sprint 8.6.1). Corrige un riesgo detectado
durante Sprint 8.6 (ver § 12, "Incidente") — no una vulnerabilidad
explotada, un control de autorización que faltaba.

## 1. Propósito

Garantizar que **ninguna ejecución abra una conexión SQL Server real sin
autorización explícita, verificable, específica de esa ejecución** —
independientemente de si el entorno tiene credenciales/conectividad
válidas. La disponibilidad de acceso NUNCA implica autorización de uso;
son preguntas distintas, y hasta este sprint solo la primera estaba
controlada (permisos del login `ClaudeReadOnly` a nivel de servidor).

## 2. Principio de seguridad

> Una ejecución que pueda abrir una conexión SQL real debe estar
> bloqueada por defecto. La autorización debe ser explícita, verificable,
> específica de la ejecución, anterior a la apertura de conexión, e
> independiente de que el modo sea `sample` o `full`. No confiar
> únicamente en documentación, prompts o convenciones.

Este documento y el código que describe son la respuesta directa a ese
principio, palabra por palabra.

## 3. Alcance

- `src/db/sql_execution_guard.py`: contrato de autorización
  (`SqlExecutionAuthorization`, `grant`/`revoke`/`require`/`is_authorized`).
- Un único punto de bloqueo real: `src/db/connection.py::get_engine()`,
  justo antes de `create_engine()`.
- CLI: `--allow-real-sql` en `run` y `export drills`, más
  `EMF_ALLOW_REAL_SQL=1` como alternativa equivalente.
- Aislamiento de tests: `tests/conftest.py` revoca cualquier autorización
  antes y después de cada test (autouse).

## 4. Fuera de alcance

- No sustituye la garantía real de solo lectura (permisos del login SQL a
  nivel de servidor, `db_datareader` únicamente) — es una capa de
  autorización de USO, no de permisos de escritura (eso sigue siendo
  `query_runner.validate_read_only_sql` + la lista negra + el propio
  servidor, sin cambios, ver § 8).
- No autoriza nunca escritura (INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/
  CREATE/TRUNCATE/SELECT INTO/procedimientos con efectos secundarios) —
  autorizar SQL real solo habilita las operaciones readonly que
  `validate_read_only_sql` ya permitía; nunca amplía ese conjunto.
- No modifica `.env`, no gestiona credenciales, no cambia el usuario SQL
  usado — sigue siendo `ClaudeReadOnly` (u homólogo), sin cambios.
- No introduce autenticación multiusuario ni roles — es una bandera de
  autorización de proceso/ejecución, no un sistema de permisos de usuarios.

## 5. Arquitectura -- por qué un único chokepoint

Todo camino que puede abrir SQL real converge, directa o
transitivamente, en `src/db/connection.py::get_engine()`:

```
run --object drills/simulacros ─┐
export drills ───────────────────┼──> extract_drills() ──> run_query() ──┐
src.db.metadata.list_tables/     │                                        │
  describe_table/row_count ──────┤                                        ├──> get_engine() ──> create_engine()
src.analysis.sql_inventory ──────┘                                        │        ▲
                                                                            └────────┘
                                                                     (punto de bloqueo)
```

Gatear ahí, en vez de en cada llamador (`run_query`, `extract_drills`,
`DrillsQueryStage`, la CLI...), cubre automáticamente cualquier camino
presente **y futuro** sin tener que enhebrar un parámetro de
autorización por toda la pila de llamadas (`ExecutionRequest` →
`PipelineFactory` → `DrillsQueryStage` → `extract_drills` →
`run_query`) — un cambio de alto riesgo para un control de seguridad que
debe ser mínimo y auditable. Ver `docs/07-developer-guide/` (inventario
completo de puntos de conexión en el informe de este sprint).

## 6. `SqlExecutionAuthorization`

```python
@dataclass(frozen=True)
class SqlExecutionAuthorization:
    source: str        # "cli_flag" | "env_var" | "test"
    granted_at: datetime
```

Estado de módulo controlado (no un parámetro enhebrado, ver § 5),
expuesto ÚNICAMENTE a través de `grant()`/`revoke()`/`require()`/
`is_authorized()`/`current_authorization()` — nunca se muta `_current`
directamente desde fuera de `sql_execution_guard.py`. Empieza en `None`
en cada proceso nuevo (fail closed): no hay ningún valor por defecto que
autorice nada.

## 7. Reglas

1. Sin autorización: `get_engine()` lanza `RealSqlNotAuthorizedError`
   ANTES de `create_engine()` — ninguna conexión de red se intenta.
2. Con autorización: se permiten únicamente las operaciones readonly que
   `validate_read_only_sql` ya admitía (sin cambios ahí).
3. `full` exige, ADEMÁS de `--allow-real-sql`, la confirmación específica
   ya existente `--confirm-full-export` — ninguna sustituye a la otra.
4. La autorización de SQL real nunca autoriza escritura (§ 4).
5. Tests con mocks/fakes (`run_query`/`get_engine` monkeypatcheados) no
   requieren autorización — nunca llegan al chokepoint real.
6. Tests de integración real conservan su propio mecanismo opt-in
   (`RUN_SQL_INTEGRATION_TESTS=1`, `RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1`),
   sin cambios, y siguen `skip` por defecto.
7. La protección aplica también a alias del Module Registry (`drills`,
   `simulacros`) — el gate vive en `get_engine()`, aguas abajo de
   cualquier alias ya resuelto a `module_id`.
8. La comprobación ocurre antes de generar cualquier output de ejecución
   (ver § 9, orden de comprobaciones en la CLI).

## 8. Verificación readonly (sin cambios)

`query_runner.validate_read_only_sql()` (whitelist estructural: única
sentencia SELECT o WITH→SELECT, sin SELECT INTO, sin múltiples
sentencias) y la lista negra de palabras/funciones (`_BLOCKED_TERMS`)
siguen exactamente igual — este sprint no las toca ni las duplica. El SQL
Execution Guard responde "¿puedo intentar conectar?"; esas funciones
responden "¿es esto una lectura válida?" — preguntas ortogonales, ambas
necesarias, ninguna sustituye a la otra.

## 9. CLI

```
python main.py run --project moeve --object drills --mode sample --allow-real-sql
python main.py export drills --mode full --confirm-full-export --allow-real-sql
```

Orden de comprobaciones en ambos comandos: primero las validaciones
baratas y sin efectos secundarios que ya existían (resolución de módulo/
capacidad en `run`; `--limit`, modo+confirmación, filtros en
`export drills` — mejores mensajes de error si el problema es, p. ej., un
`--object` mal escrito), y el SQL Execution Guard **al final**, justo
antes de construir la petición real/invocar el pipeline — es la última
puerta antes de cualquier trabajo real. `EMF_ALLOW_REAL_SQL=1` es
equivalente a `--allow-real-sql` (no se exigen ambos). Sin ninguno de los
dos: mensaje seguro (§ 10), exit code 1, sin conexión abierta, sin
outputs generados.

Comandos sin SQL (`workspace validate`, `workspace resolve`,
`modules list`, `modules show`, `evidence drills`) no cambian — nunca
requieren `--allow-real-sql`, no se les añadió la opción.

## 10. Información previa segura

Al bloquear:

```
=== run -- SQL Execution Guard ===
ERROR: esta operación puede abrir una conexión SQL Server real.
Está bloqueada por defecto -- la disponibilidad de credenciales
no implica autorización de uso.

Añade --allow-real-sql tras recibir autorización técnica explícita
(o exporta EMF_ALLOW_REAL_SQL=1).

No se abrió ninguna conexión. No se generó ningún output.
```

Nunca contraseñas, cadenas de conexión, secretos ni contenido de `.env`
(verificado por test). Al autorizar, el banner de la CLI registra
únicamente información no sensible: nombre lógico de conexión (`prevencion`,
marcada `readonly`), fuente de la autorización (`cli_flag`/`env_var`),
timestamp, módulo, modo `sample`/`full` — nunca la cadena de conexión ni
credenciales.

## 11. Extensibilidad

Un futuro segundo módulo (o `src/db/metadata.py`/`src/analysis/sql_inventory.py`,
si algún día se conectan a un comando CLI) queda cubierto automáticamente
por el gate de `get_engine()` sin ningún cambio adicional — es la ventaja
directa de un único chokepoint (§ 5).

## 12. Incidente (Sprint 8.6, contenido)

**Clasificación:** *Accidental readonly execution — contained.*

Durante la verificación manual de Sprint 8.6 se ejecutó
`python main.py run --object simulacros` directamente en shell, sin el
mock de `run_query` que sí usa la suite de tests. El entorno tenía
conectividad real a SQL Server (usuario `ClaudeReadOnly`, permisos
`db_datareader` únicamente) y la ejecución leyó 5 filas reales. **Ninguna
escritura** — el login no tiene permisos de escritura, y la propia
consulta era la misma `SELECT` de siempre. El output local generado
(`reports/20260728T083255Z/`) se eliminó de inmediato con `rm -rf`, sin
llegar nunca a `git add`/commit (`git status` lo confirma antes y
después). Ver el detalle completo, incluida la causa raíz y la
corrección aplicada, en
`reports/executions/2026-07-28/Informe-SQL-Execution-Guard-EMF.md` § 9.

## 13. Deuda técnica

- El estado de autorización es un booleano de proceso, no está atado a
  qué conexión concreta (`prevencion` vs. `gct`) — una autorización
  concedida habilita cualquier conexión que la ejecución llegue a
  necesitar. Suficiente hoy (una única conexión real por ejecución); una
  autorización por-conexión es una extensión aditiva si algún día una
  misma ejecución necesita distinguir entre ambas.
- `query_timeout_seconds` (declarado en `config/databases.yaml`) sigue
  sin aplicarse en `query_runner.run_query()` — detectado durante el
  inventario de este sprint, no es un problema de autorización, se
  documenta aquí para no perderlo (fuera de alcance de este incremento).

## 14. Criterios de aceptación

Ver `reports/executions/2026-07-28/Informe-SQL-Execution-Guard-EMF.md`
§ 14 para el detalle verificado (tests, suite completa, git status/diff).
