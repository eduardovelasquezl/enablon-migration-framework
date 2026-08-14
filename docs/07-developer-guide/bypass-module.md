# Bypass — segundo módulo real del EMF (Sprint 9.4)

**Status:** `BYPASS_OFFLINE_SAMPLE_READY`. Ningún SQL real ejecutado
todavía contra este módulo.

## 0. Objetivo

Replicar el patrón vertical de Drills para un segundo objeto real
(`bypass.By_Passes`), demostrando si la arquitectura genérica del EMF
soporta un segundo módulo sin cambios de Core, y clasificando cada
pieza usada como `REUSED_AS_IS` / `MODULE_SPECIFIC` /
`DUPLICATED_FROM_DRILLS` / `CORE_GAP`.

## 1. Evidencia encontrada

### 1.1 Fuente / sistema

- Sistema origen: `prevencion` (ITP), tabla `ITP_BES`.
- `config/modules.yaml`: `tablas_origen: DBLink_BES, 7202 filas conocidas`.
  `DBLink_BES` es el nombre de una **Power Query interna** del ETL
  (`xl/connections.xml`: `Consulta - DBLink_BES`), no un nombre de tabla
  SQL Server -- confirmado leyendo el XML interno del `.xlsx`, sin abrir
  Excel. El M-code que define esa Power Query no quedó localizable como
  texto plano dentro del `.xlsx` (no es una carencia de búsqueda menor,
  se intentó explícitamente).

### 1.2 SQL — discrepancia registrada, no resuelta

Dos ficheros candidatos para el mismo objeto, **estructuralmente
distintos**:

| | `SQLQuery-dataset_BES.sql` | `query_Bypass_prev2025.sql` |
|---|---|---|
| JOIN | `INNER JOIN` × 5 tablas de dimensión | `FULL JOIN` × 5 tablas de dimensión |
| Fechas | Crudas (`datetime`) | Formateadas (`format(..., 'dd/MM/yyyy HH:mm:ss')`) |
| `ORDER BY` | Ninguno | `ITP_BES.FechaCreacion asc` |
| `WHERE` | Ninguno | Comentado (`-- where ... < '31/12/2024'`) |

**Elegido: `SQLQuery-dataset_BES.sql`** (INNER JOIN) — mismo motivo ya
documentado en `CLAUDE.md` para el `FULL JOIN` de Eventos: un `FULL
JOIN` sobre 5 tablas de dimensión arriesga inflar el recuento con
combinaciones huérfanas, y no se puede descartar ese riesgo sin
ejecutar la consulta (no autorizado en este sprint). Ninguna columna
del contrato de este incremento depende de las tablas JOINadas -- todas
usan el `IDxxx` crudo + un lookup propio del ETL, no el texto ya unido
por SQL.

Sin `ORDER BY` propio (a diferencia de Drills): el extractor ordena en
pandas por `FechaCreacion` tras traer los datos, nunca modifica el
fichero `.sql` en disco (ver `extractor.py`).

### 1.3 Mapping (hoja `MapeoBypass` + hojas satélite del ETL real)

7 campos con evidencia primaria directa (fórmula/tabla del ETL,
cruzados contra el CSV Operational real donde fue posible):

| Campo destino | Origen | Regla | Evidencia |
|---|---|---|---|
| `CS_HistoricalOriginID` | `IDBES` | `cloneorigin` (passthrough) | `map_BES_Fix`, fila `ReglaEspecial=cloneorigin` |
| `ByPassType` | `IDTipoBypass` | lookup 3 valores + nullcontrol | `Mapeo_TipoBypass`; cruzado 3/3 contra Operational real |
| `Cause` | `IDCausa` | lookup 5 valores + nullcontrol | `Mapeo_CausaBypass`; cruzado contra Operational real |
| `ElementType` | `IDTipoSCE` | lookup 8 valores + nullcontrol | `Mapeo_ElementType`; cruzado contra Operational real |
| `RealizationMethods` | `IDMetodoBypass` | lookup NUMÉRICO (no letra) + nullcontrol | `Mapeo_RealizationMethods` -- ver hallazgo § 1.4 |
| `Reason` | `Motivo` | nullcontrol genérico, sin tabla | `NullControlException` |
| `CS_HistoricalDataOrigin` | constante | `"Prevención.ITP_BES"` | verificado directamente en el Operational real (valor único, 25/25 filas) |

### 1.4 Hallazgo — `Mapeo_RealizationMethods` casi se leyó mal

La hoja tiene una columna `InfoIgnore-clave` con códigos de letra
(`PL`/`EPD`/`DOE`/`OT`/`CP`) que **parecen** el `DatoDestino` a simple
vista -- pero el nombre "InfoIgnore" ya avisa que no se usa. El
`DatoDestino` real es un **número** (remapeo `IDMetodoBypass -> otro
número`). Confirmado cruzando contra el Operational real: sus valores
observados son `'2'`,`'3'`,`'4'`,`'5'` (números), no letras. Corregido
antes de escribir `config/exports/bypass.yaml` -- ver ese fichero para
el detalle.

### 1.5 Entity — mecanismo NO reproducible localmente (UNRESOLVED)

`config/modules.yaml`: `IDUnidadOrg -> RutaEnablon (formato Code
corto)`, resultado ya validado en producción (7202→7040, -2,2%, "sano
tras aplicar catálogo real"). Pero, a diferencia de Drills (que usa un
catálogo antiguo con columna `IDUnidadOrg` directa), Bypass usa el
catálogo First_Axis **vigente**
(`inputs/entity_catalog/catalogo_resuelto_code_ruta_site.csv` /
`First_Axis_export_bruto.csv`) -- ambos son catálogos **solo de
destino** (`Code`/`Ruta1`/`Centro`), sin ninguna columna `IDUnidadOrg`
de origen. No existe en este repositorio un artefacto local que
reproduzca la resolución `IDUnidadOrg -> Code` para el catálogo
vigente. **El resultado está confirmado; el mecanismo no es
reproducible offline hoy.** `Entity` queda excluida de este incremento
(`excluded_columns` en `bypass.yaml`), no inventada.

### 1.6 Hallazgo — anomalía de datos en `CS_HistoricalOriginID` del Operational real

El único CSV Operational real (`By pass new .bak.csv`, 25 filas, mismo
patrón CCE-scoped que el Operational de Drills) tiene su columna
`CS_HistoricalOriginID` con valores con apariencia de **fecha**
(`'17/11/1907 0:00'`) en vez de un `IDBES` entero. Decodificados como
número de serie de fecha de Excel (época 1899-12-30), dan números
pequeños y plausibles como `IDBES` (2878, 2881, 2942...) -- consistente
con un entero reinterpretado como fecha por la herramienta de
exportación. **No se intentó revertir esta corrupción** -- se registra
como hallazgo de calidad de datos del propio export, no una regla de
mapping. Afecta a la comparación futura (§ 4), no a esta generación.

### 1.7 Volumetría

Operational real: 25 filas -- muy por debajo de las 7.202 conocidas
(`config/modules.yaml`) -- mismo patrón que el Operational CCE-scoped
de Drills (subconjunto, no el histórico completo).

## 2. Matriz Bypass vs. Drills

| Capability | Drills | Bypass | Clasificación |
|---|---|---|---|
| Module registration | `bootstrap/module_registry.py` | Mismo patrón, mismo fichero | REUSED_AS_IS (mecanismo) |
| Query (extracción SQL) | `extractor.py` propio | `extractor.py` propio, misma forma | DUPLICATED_FROM_DRILLS |
| Filters | `DRILLS_FILTER_CATALOG` | `BYPASS_FILTER_CATALOG`, mismas clases | REUSED_AS_IS (mecanismo) / MODULE_SPECIFIC (datos) |
| Canonicalization | `DrillsCanonicalizeStage` (pass-through) | No implementada (no aporta valor demostrado, mismo motivo que Drills) | MODULE_SPECIFIC (omitida) |
| Transformation | 6 funciones propias | 2 funciones reutilizadas + 1 nueva | REUSED_AS_IS + MODULE_SPECIFIC |
| Mapping lookup | `resolve_typology`/`resolve_letter` | `resolve_letter` reutilizado (4×) | REUSED_AS_IS |
| Entity resolution | `EntityCatalog` (catálogo antiguo) | No implementada -- sin artefacto local | UNRESOLVED (no encaja limpio en las 4 categorías -- ver § 1.5) |
| Date handling | `parse_starting_date` (Fecha+Hora) | No aplica -- Bypass no tiene un campo de fecha en el contrato de este incremento | N/A |
| Validation | `validator.py` propio | `validator.py` propio, más genérico (recibe `OutputSpec`, no el config completo) | DUPLICATED_FROM_DRILLS (mejorado) |
| CSV generation | `exporter.py::write_csv` | Reutilizado tal cual | REUSED_AS_IS |
| Project Contract | Resuelto vía `ResourceResolver` | Mismo mecanismo (no ejercitado con `--manifest` en este sprint, sí confirmado por `workspace readiness`) | REUSED_AS_IS |
| Comparison | `comparison.py` (solo CSV) | No implementada | MODULE_SPECIFIC (diferida, ver § 4) |
| Evidence | `evidence/collector.py`+`workbook.py` | No implementada | MODULE_SPECIFIC (diferida, ver § 4) |
| Execution manifest | `manifest.py::build_export_manifest` | `manifest.py` propio, más pequeño (7 campos, no 8+entidad) | DUPLICATED_FROM_DRILLS |
| Issues | `issues.jsonl` por fila | No implementado (warnings agregados en `RunStats`, suficiente para este incremento) | MODULE_SPECIFIC (alcance reducido) |
| Readiness | `WorkspaceReadinessValidator` | Mismo validador, sin cambios | REUSED_AS_IS |
| Outputs | `outputs/prototype/drills/` | `outputs/prototype/bypass/`, mismo patrón timestamp | REUSED_AS_IS (mecanismo) |

## 3. Decisión Fase 3: **GO**

Ningún `CORE_GAP` bloqueante encontrado. `BYPASS_OFFLINE_SAMPLE_READY`
alcanzado con: Core existente sin cambios + `config/exports/bypass.yaml`
nuevo + `src/export/prototype/bypass/` nuevo (mismo patrón de Drills) +
tests. `pipeline.run()` se duplicó (estructura), deuda ya conocida
desde el cierre de Sprint 9.3, no un hallazgo nuevo.

## 4. Comparison / Project Contract (análisis, sin implementar)

El Operational real (`By pass new .bak.csv`) es CSV (no `.xlsx` como el
de Drills) -- el comparador automático de Drills (`comparison.py`) SÍ
sabría leerlo formalmente, pero **no se conectó a Bypass en este
sprint** (fuera de alcance de `BYPASS_OFFLINE_SAMPLE_READY`). Aunque se
conectara, la comparación por `CS_HistoricalOriginID` fallaría hoy por
la anomalía de datos de § 1.6 -- no es un problema del comparador, es
un problema del propio fichero Operational disponible.

**Filtro candidato para un futuro sample real** (Fase 6/12): dado que
`CS_HistoricalOriginID` en el Operational real decodifica a IDs
pequeños plausibles, se propone `historical_origin_id:in:<lista de IDs
decodificados>` -- ya soportado por `BYPASS_FILTER_CATALOG`
(`allowed_operators=("eq","in")`), sin ampliar el catálogo. No
ejecutado en este sprint.

## 5. Field Constraints -- candidatos registrados (sin implementar)

- `AutorizaOPoneEnServicioFase2/3/4`: valores observados solo `A`/`S`
  (nota del ETL: "si pone S el resto de campos no se rellenan") --
  candidato a `allowed_values: [A, S]` + una restricción de tipo
  REFERENCIA/CONDICIONAL (no solo `max_length`), refuerza que el
  esquema futuro de Field Constraints necesita más que
  `max_length`/`overflow_policy` para casos reales.
  Ver Fase 11 del encargo original -- ejemplo real, no hipotético.
- `GOS`: no es un caso de longitud/formato, es un campo
  **calculado por la plataforma** -- candidato a un tipo de restricción
  adicional (`system_managed: true`) distinto de los ya listados
  (`type`/`required`/`max_length`/`allowed_values`/`format`/
  `precision`/`reference`), no cubierto por el catálogo propuesto en el
  cierre de Sprint 9.3.
- No se encontró evidencia directa de un `max_length` numérico
  confirmado para ningún campo de Bypass en este incremento (a
  diferencia del ejemplo hipotético "Title max 20" del encargo) -- se
  registra la ausencia de evidencia, no se inventa un valor.

## 6. Clasificación agregada

| Clasificación | Count | Ejemplos |
|---|---:|---|
| `REUSED_AS_IS` | 15 | ModuleRegistry, StageRegistry, contratos Framework Core v1, WorkspaceManifest, ResourceResolver, SQL Execution Guard, Query Engine (mecanismo), `to_historical_id`, `resolve_letter`, `write_csv`/`OutputSpec`, `write_yaml_atomic`/`write_text_atomic`, `build_query_filters_section`, `render_generated_sql_file`, `FieldSpec`/`SourceSpec`, `WorkspaceReadinessValidator` |
| `MODULE_SPECIFIC` | 4 | `config/exports/bypass.yaml`, `BYPASS_FILTER_CATALOG` (datos), `nullcontrol_passthrough`, lookups propios de Bypass |
| `DUPLICATED_FROM_DRILLS` | 7 | `pipeline.py` (orquestación), `extractor.py` (forma), `core_adapters.py` (Stages+factory), `config.py` (loader), `manifest.py` (RunStats+builders), `validator.py` (validate_output_csv), `_is_missing()` (~10 líneas) |
| `CORE_GAP` (bloqueante) | 0 | Ninguno -- ver § 3 |
| `CORE_GAP` (blando, no bloqueante) | 2 | Sin Export Engine genérico (causa de la mayoría de `DUPLICATED_FROM_DRILLS`); sin artefacto local de entity resolution para el catálogo First_Axis vigente |

### Pregunta 1 — ¿La arquitectura actual soporta un segundo módulo sin cambios de Core?

**Sí.** Cero cambios en `src/core/`. El único cambio fuera de
`src/export/prototype/bypass/` fue el composition root
(`src/bootstrap/module_registry.py`), que por diseño es precisamente el
lugar donde se espera que un módulo nuevo se conecte.

### Pregunta 2 — ¿Cuánto código conceptual de Drills hubo que duplicar?

7 piezas concretas (§ 6), todas en la capa de orquestación/adaptación
(nunca en las transformaciones puras, donde SÍ hubo reutilización
directa). Ninguna duplicación fue "por comodidad" -- cada una está
registrada con el motivo concreto (§ 2).

### Pregunta 3 — ¿Hay evidencia suficiente para diseñar un Module Adapter Contract v0.x?

**Sí** -- reforzada respecto al informe de cierre de Sprint 9.3: la
propuesta v0.1 de ese informe se confirma con un segundo caso real, sin
ajustes necesarios. Sigue sin implementarse (mismo motivo: extraerlo
ahora, con solo 2 casos, arriesga generalizar sobre patrón incompleto).

### Pregunta 4 — ¿Sprint 9.5 real inmediato o micro-sprint de Export Engine antes?

**Recomendación: Sprint 9.5 (sample real) primero.** La duplicación
encontrada es real pero contenida (7 ficheros, ninguno de gran tamaño,
todos ya probados por tests). Extraer un Export Engine genérico ahora,
con solo 2 puntos de datos, arriesga diseñar sobre un patrón todavía
incompleto (YAGNI). Validar Bypass contra SQL real primero da un
TERCER punto de datos real (Drills, Bypass-config, Bypass-real) antes
de generalizar -- decisión de coste/riesgo, no de preferencia teórica,
tal como pedía el encargo.
