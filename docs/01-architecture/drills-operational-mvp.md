# Drills Operational MVP — Sprint 5

**Status:** Approved Design (documento operativo — organización y
consolidación de configuración existente, sin cambios de código). No
implementa el Framework Core ni modifica Query Engine, Evidence Engine,
Export Engine ni ningún fichero de `src/`.

Este documento responde a una pregunta concreta y operativa: **¿qué hace
falta exactamente, y en qué orden, para producir el primer `drills.csv`
completo (modo `full`) con el prototipo ya existente?** — no diseña nada
nuevo, inventaria y ordena lo que ya existe.

## 0. Hallazgo que reencuadra toda la tarea

**Ya existe una ejecución completa y exitosa del pipeline de Drills**, en
modo `sample` (100 filas), en `outputs/prototype/drills/20260723T195418Z/`:

```
run_id: c65d5c2a1261        timestamp: 20260723T195418Z
mode: sample                 connection: prevencion
status.result: SUCCESS       blocking_errors: []    warnings: []
rows_read/transformed/exported: 100/100/100          rows_excluded: 0
entities: resolved=93, do_not_migrate=5, unresolved=0, conflicting=0, empty=2
artefactos: drills.csv, validation_report.yaml, export_manifest.yaml,
            comparison_report.yaml, issues.jsonl,
            evidence_internal.xlsx, evidence_client.xlsx
```

Esto demuestra, con evidencia real y no con inferencia, que: la conexión
SQL funciona con credenciales reales; la query de origen es correcta; el
mapeo, la resolución de entidad, la validación pre/post-escritura, el
manifiesto y el Evidence Engine funcionan de extremo a extremo. **El
prototipo no está "por probar" — ya está probado.** Lo que falta para
"Drills Operational MVP" no es, en su mayor parte, configuración nueva:
es la ejecución del mismo pipeline ya verificado, en modo `full` en vez de
`sample`, más la organización de la configuración dispersa que este
documento inventaría. Este reencuadre se mantiene explícito en todo el
documento para no inflar artificialmente la lista de pendientes.

## 1. Flujo operativo

```
1. Fuente SQL (config/databases.yaml -> conexión "prevencion" + .env)
     │
2. Query de origen (sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql)
     │  extract_drills() -- src/export/prototype/drills/extractor.py
     │  modo sample: trunca localmente a --limit filas (orden ya determinista, FechaCreacion asc)
     │  modo full:   exporta todas las filas devueltas, sujeto a max_rows_per_query (2.000.000)
     ▼
3. Transformación + mapeo (config/exports/drills.yaml -> fields + reference_data)
     │  transformations.py (build_reference, resolve_typology/letter/workflow_status)
     │  mappings.py (resolve_entity contra inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv)
     ▼
4. Validación pre-escritura (validator.py: validate_pre_write, check_duplicate_references)
     ▼
5. Escritura CSV (exporter.py -> write_csv, escritura atómica)
     ▼
6. Validación post-escritura (validator.py: validate_output_csv -- reabre el fichero, verifica encoding/BOM/columnas)
     ▼
7. validation_report.yaml (manifest.py)
     ▼
8. export_manifest.yaml (manifest.py -- incluye hashes, reglas aplicadas, limitaciones, open questions)
     ▼
9. comparison_report.yaml (comparison.py, SOLO si existe el CSV histórico declarado)
     ▼
10. issues.jsonl (pipeline.py -- una incidencia por fila con problema real, nunca por filas sin problema)
     ▼
11. Evidence Engine (opcional, --generate-evidence): evidence_internal.xlsx / evidence_client.xlsx
     -- lee EXCLUSIVAMENTE los artefactos ya escritos (3-10), nunca vuelve a tocar SQL Server
```

Todo el flujo se invoca con un único comando (`main.py` → `src/cli.py` →
`src/export/prototype/drills/pipeline.py::run`) — no hay pasos manuales
intermedios salvo, opcionalmente, la generación de evidencia.

## 2. Configuración requerida (y su estado real)

| Configuración | Fichero(s) | Estado |
|---|---|---|
| Conexión SQL | `config/databases.yaml` (conexión `prevencion`) + `.env` (`SQL_PREVENCION_HOST/DB/USER/PASSWORD`) | **Ya configurado** — `.env` existe y está poblado; confirmado funcional por la ejecución real del 2026-07-23. |
| Query de origen | `sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql` | **Ya validado** — hash (`a1c5203e...`) registrado en el manifiesto real, fuente única sin joins. |
| Mapeo de campos | `config/exports/drills.yaml` → `fields` (7 reglas) | **Ya implementado** para las 8 columnas en alcance de este incremento (nunca pretendió cubrir las 36 del CSV real de Enablon — decisión de alcance documentada, no una carencia). |
| Catálogos de referencia | `reference_data` embebido en `drills.yaml` (typology/letter/workflow_status) + `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv` | **Ya presentes y usados** — 93/100 entidades resueltas en la ejecución real. |
| Formato de salida ("template" de este prototipo) | `drills.yaml` → `output:` (encoding/delimiter/BOM/quoting/line_terminator) | **Ya implementado y validado** por `validate_output_csv` en la ejecución real. |
| Política de validación | `drills.yaml` → `invalid_row_policy` + `validator.py` | **Ya implementado** — 0 errores, 0 warnings en la ejecución real. |
| Registro de proyecto/módulo | `config/modules.yaml` → `simulacros` + campos top-level de `drills.yaml` (`object_id`/`module`/`migration_object`) | **Ya presente**, aunque disperso entre dos ficheros (ver § 4). |
| Directorio de salida | `outputs/prototype/drills/` | **Ya funcional**, escritura atómica confirmada. |
| CSV histórico de comparación | `inputs/_incoming_claude_web/Bloque4_CSV_Enablon/Drills-22072026-41.csv` | **Presente** — usado en la ejecución real (`comparison_report.yaml` generado). |

**Ninguna fila de esta tabla requiere configuración nueva** para repetir
lo ya conseguido en modo `sample`. La pregunta real de esta tarea es si
algo cambia al pasar a modo `full` — ver § 8.

## 3. Dependencias

```
.env (credenciales)
  └─requerido por→ config/databases.yaml (conexión "prevencion")
        └─requerido por→ extractor.py (ejecuta la query)
              └─requerido por→ transformations.py + mappings.py (necesitan las columnas ya extraídas)
                    │              └─requerido por→ inputs/entity_catalog/*.csv (catálogo de entidad)
                    │              └─requerido por→ reference_data de drills.yaml (value maps embebidos)
                    ▼
              validator.py (pre-escritura, necesita el DataFrame ya transformado)
                    ▼
              exporter.py (escribe el CSV -- necesita drills.yaml -> output:)
                    ▼
              validator.py (post-escritura, reabre el CSV ya escrito)
                    ▼
              manifest.py (validation_report.yaml -- necesita las stats acumuladas)
                    ▼
              manifest.py (export_manifest.yaml -- necesita el CSV ya escrito, para sus hashes)
                    ▼
              comparison.py (opcional -- necesita el CSV histórico Y el manifiesto de columnas)
                    ▼
              pipeline.py (issues.jsonl -- se escribe en paralelo a lo anterior, con las mismas incidencias detectadas durante la transformación)
                    ▼
              evidence/collector.py + workbook.py (opcional -- necesita TODOS los artefactos anteriores ya escritos en disco)
```

Ninguna etapa se salta ni se paraleliza de forma que rompa esta cadena —
el pipeline ya implementado (`pipeline.py::run`) las ejecuta en este orden
exacto.

## 4. Duplicidades y configuración dispersa detectadas

Ninguna de estas es bloqueante para ejecutar Drills — se documentan porque
el encargo pide explícitamente detectarlas antes de proponer una
estructura definitiva (§ 6).

1. **`config/exports/drills.yaml` mezcla seis responsabilidades distintas
   en un único fichero**: identidad de proyecto/objeto (`object_id`/
   `module`/`migration_object`), referencia a la fuente (`source:`),
   formato de salida/plantilla (`output:`), mapeo de valores
   (`reference_data`), reglas de mapeo de campo (`fields`), y política de
   validación (`invalid_row_policy`) + exclusiones documentadas
   (`excluded_columns`). Con un único objeto en producción esto es
   manejable; es exactamente el patrón que, con un segundo objeto, ya se
   señaló como riesgo en `data-processing-lifecycle.md` (Fase P4/P5 del
   roadmap EMF).
2. **`HISTORICAL_CSV_PATH` (la ruta del CSV histórico de comparación) es
   una constante Python dentro de `pipeline.py`**, no una entrada de
   `config/exports/drills.yaml` — es el único valor de configuración de
   todo el pipeline de Drills que vive en código en vez de en YAML,
   inconsistente con el resto del fichero.
3. **`config/modules.yaml` mezcla un registro de proyecto/módulo con datos
   de catálogo** (`idcentro_map_itp`/`idcentro_map_gct`, tablas de
   traducción IDCentro→Site) que son, conceptualmente, catálogos de
   referencia, no metadatos de módulo — están en el mismo fichero por
   conveniencia histórica, no por diseño.
4. **`config/validation_rules.yaml` mezcla dos conceptos distintos**:
   `transformation_rules` (catálogo documental de reglas de ETL legado,
   consultado como referencia humana — no leído en tiempo de ejecución
   por el prototipo de Drills) y `data_quality_checks` (validaciones
   genéricas, aplicables a cualquier módulo, tampoco conectadas todavía a
   ningún motor ejecutable).
5. **`sql/source_queries/Simulacros/` contiene 4 ficheros sin usar por el
   pipeline actual** (`SQLQuery4.sql`, `SQLQuery6.sql`, `SQLQuery9.sql`,
   `Acciones correctoras.sql`), sin ningún comentario o manifiesto que
   indique si son exploratorios, legado, o pendientes de otro incremento
   (Acciones Correctoras de Simulacros, posiblemente para el futuro
   objeto Action Plans). Solo `SQLQuery - DATASET SIMULACRO.sql` está
   conectado a `drills.yaml`.
6. **`inputs/mappings/` e `inputs/etl/` están declarados en
   `config/settings.yaml` (`folders.mappings`, `folders.etl_originals`)
   pero están vacíos** (solo `.gitkeep`) — el contenido real equivalente
   vive en `inputs/_incoming_claude_web/Bloque1_ETL/` y
   `Bloque2_Mappings_SQL_ENA/`/`Bloque3_Mappings_Entidades/`, una carpeta
   de "recepción bruta" que nunca se consolidó en las rutas que la propia
   configuración declara como canónicas.
7. **`inputs/entity_catalog/` contiene tres ficheros, pero Drills solo usa
   uno** (`entidades_mapeo_ANTIGUO_referencia_historica.csv`) — los otros
   dos (`catalogo_resuelto_code_ruta_site.csv`, `First_Axis_export_bruto.csv`)
   son el catálogo **vigente**, correcto para otros módulos (Safety
   Meetings, MOC, Bypass — ver `CLAUDE.md`), pero deliberadamente no
   aplicable a Simulacros (esquema histórico ya cerrado). No es un error,
   pero sin este documento podría parecer configuración obsoleta o
   redundante a quien no conozca `CLAUDE.md`.

## 5. Inventario completo

| Categoría | Elemento |
|---|---|
| **Configuración existente y funcional** | `config/databases.yaml`, `.env` (poblado), `config/exports/drills.yaml` completo, `sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql`, `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv`, `inputs/_incoming_claude_web/Bloque4_CSV_Enablon/Drills-22072026-41.csv` (baseline de comparación), todo `src/export/prototype/drills/*.py`, `src/evidence/*.py`, `src/query/*.py`, `src/db/*.py`. |
| **Configuración reutilizable** (para un segundo objeto, sin cambiar su contenido) | El patrón `output:`/`invalid_row_policy` de `drills.yaml` (aplicable a cualquier objeto); `config/databases.yaml` (ya sirve a cualquier módulo del sistema `prevencion`/`gct`); el patrón de `reference_data` separado de `fields`; el `DRILLS_FILTER_CATALOG` del Query Engine (`src/query/catalog.py`) como patrón de catálogo cerrado de filtros. |
| **Configuración obsoleta o sin confirmar** | `sql/source_queries/Simulacros/SQLQuery4.sql`, `SQLQuery6.sql`, `SQLQuery9.sql` (sin documentar su propósito — candidatos a archivar o documentar, no a borrar sin confirmar); `config/validation_rules.yaml` → reglas con `confirmado_con_datos_reales: false` (`barconcat`, `replaceinreference`, `boolorigin`) — documentadas como no confirmadas, no deben tratarse como listas para usar. |
| **Configuración que falta** | Una ejecución real en modo `full` (nunca se ha hecho — ver § 0/§ 8); una declaración explícita, fuera de código, de `HISTORICAL_CSV_PATH`; un manifiesto o `README` dentro de `sql/source_queries/Simulacros/` que aclare qué ficheros están en uso y cuáles no. Ningún elemento de esta fila bloquea la ejecución de Drills en modo `full` — son mejoras de higiene de configuración, no requisitos. |

## 6. Estructura de configuración propuesta (sin mover archivos todavía)

```
config/
├── projects/
│   └── moeve/
│       ├── project.yaml         -- NUEVO: consolidaría object_id/module/migration_object
│       │                            (hoy top-level en drills.yaml) + la entrada "simulacros"
│       │                            de modules.yaml, sin los catálogos idcentro_map_*
│       └── modules.yaml          -- = config/modules.yaml actual, SIN los idcentro_map_*
│                                    (que se moverían a sources/ o a un catálogo aparte)
├── sources/
│   ├── databases.yaml            -- = config/databases.yaml actual, sin cambio de contenido
│   └── site_catalogs.yaml         -- NUEVO: idcentro_map_itp/idcentro_map_gct extraídos
│                                     de modules.yaml (son datos de catálogo, no de módulo)
├── queries/
│   └── simulacros.yaml            -- NUEVO: declara qué fichero .sql (bajo sql/source_queries/,
│                                     que NO se mueve -- ver nota) usa cada objeto, con su hash
│                                     esperado -- reemplaza el bloque `source:` de drills.yaml
├── mappings/
│   └── drills.yaml                 -- = reference_data + fields de drills.yaml actual
├── templates/
│   └── drills.yaml                  -- = output: + excluded_columns de drills.yaml actual
│                                        (incluiría también HISTORICAL_CSV_PATH, hoy en código)
└── validation/
    ├── drills.yaml                   -- = invalid_row_policy de drills.yaml actual
    └── validation_rules.yaml          -- = config/validation_rules.yaml actual, sin cambio
```

**Nota deliberada**: `sql/source_queries/` **no se propone mover** dentro
de `config/` — el texto SQL en sí sigue viviendo donde ya lo espera
`config/settings.yaml` (`folders.sql_source_queries`); `config/queries/`
solo declara la asociación objeto→fichero→hash esperado, nunca una
segunda copia del texto SQL (evitar que dos copias del mismo SQL diverjan
con el tiempo).

**Advertencia explícita de alcance**: esta reestructuración **no se
ejecuta en esta tarea** (el encargo pide documentar primero, no mover
archivos) y su beneficio real solo se materializa con un segundo objeto
migrable — con un único objeto (Drills), el fichero único actual
(`drills.yaml`) no es, en sí mismo, un problema urgente. Se documenta
ahora para no repetir la dispersión ya señalada en § 4 cuando se
incorpore el segundo objeto (mismo principio "No Abstraction Without a
Real Consumer" ya aplicado en el resto de la documentación EMF de este
repositorio — no se ejecuta la migración de configuración hasta que haya
un segundo caso real que la justifique empíricamente).

## 7. Artefactos generados por una ejecución

| Artefacto | Generado por | Obligatorio |
|---|---|---|
| `drills.csv` | `exporter.py` | Sí |
| `validation_report.yaml` | `manifest.py` | Sí |
| `export_manifest.yaml` | `manifest.py` | Sí |
| `issues.jsonl` | `pipeline.py` | Sí (vacío si no hay incidencias) |
| `comparison_report.yaml` | `comparison.py` | Solo si existe el CSV histórico declarado |
| `evidence_internal.xlsx` / `evidence_client.xlsx` | `evidence/workbook.py` | Solo con `--generate-evidence` |
| `generated_query.sql` | `sql_builder.py` | Solo si se usaron `--filter` |

## 8. Validaciones que ya se ejecutan (sin cambios necesarios)

- **Pre-escritura**: columnas fuente esperadas presentes; DataFrame no vacío (`validate_pre_write`).
- **Post-escritura**: encoding/BOM correctos, cabecera igual al orden esperado, número de filas igual al esperado, todas las filas con el mismo número de columnas que la cabecera, `Reference` cumple su patrón, el CSV es reabrible con pandas (`validate_output_csv`).
- **Duplicados de `Reference`** (`check_duplicate_references`).
- **Comparación cuantitativa contra el histórico** (`comparison.py`), si el fichero de referencia existe.

Ninguna validación nueva es necesaria para ejecutar en modo `full` — son
las mismas funciones, sin ninguna rama de código condicionada al modo
salvo el propio tamaño del resultado.

## 9. Checklist operativa (ordenada por dependencia real, no por importancia)

```
☑ Fuente          -- config/databases.yaml + .env (prevencion)          [IMPLEMENTADO Y CONFIGURADO]
☑ Query validada   -- SQLQuery - DATASET SIMULACRO.sql, hash confirmado  [IMPLEMENTADO Y VALIDADO]
☑ Catálogos         -- entidades_mapeo_ANTIGUO_referencia_historica.csv  [IMPLEMENTADO Y CONFIGURADO]
                        + reference_data embebido en drills.yaml
☑ Mapping completo   -- 7 reglas de campo en drills.yaml (8 columnas)    [IMPLEMENTADO -- alcance
                                                                           de este incremento, no de
                                                                           las 36 columnas del CSV real]
☑ Template definido   -- output: block de drills.yaml                    [IMPLEMENTADO Y VALIDADO]
☑ Validation Profile   -- invalid_row_policy + validator.py              [IMPLEMENTADO Y VALIDADO]
☑ Proyecto               -- object_id/module/migration_object            [IMPLEMENTADO (dispersión
                             + entrada en modules.yaml                    documentada en §4, no bloqueante)]
☑ Output                  -- outputs/prototype/drills/                    [IMPLEMENTADO Y FUNCIONAL]
☑ Manifest                 -- export_manifest.yaml                        [IMPLEMENTADO Y VALIDADO]
☑ Evidence                  -- evidence_internal.xlsx / evidence_client.xlsx [IMPLEMENTADO Y VALIDADO]
☐ Reports                    -- resumen ejecutivo de ESTA ejecución        [NO EXISTE COMO ARTEFACTO
                                                                             DISTINTO -- ver nota]
☐ Ejecución en modo FULL      -- nunca realizada todavía                   [PENDIENTE -- único paso
                                                                             operativo real que falta]
```

**Nota sobre "Reports"**: no existe un artefacto técnico llamado
"reporte de Drills" distinto de `evidence_client.xlsx` (que ya cumple ese
propósito: es el Excel pensado para compartir con el cliente). Si se
necesita además un resumen ejecutivo en otro formato, es una tarea de
comunicación humana a partir de artefactos ya generados, no una pieza de
configuración o código que falte.

**Todos los puntos marcados `☑` están, a la vez, implementados en código
Y configurados con datos reales** — no hay ningún punto de esta lista que
esté "implementado mas sin configurar" en este proyecto: la única
distinción real que aporta valor aquí es "ya hecho" (☑) vs. "falta
ejecutar" (☐, un único punto).

## 10. Camino más corto al primer `drills.csv` (modo `full`)

Sin proponer mejoras arquitectónicas, motores nuevos ni plugins — el
camino mínimo con lo que ya existe:

1. **Confirmar que la ejecución se lanza desde un entorno con
   conectividad de red real a SQL Server.** `CLAUDE.md` ("Estado de los
   accesos") documenta explícitamente que el entorno de análisis actual
   **no tiene** esa conectividad — el flujo real es "alguien ejecuta la
   query y sube el resultado". La ejecución exitosa del 2026-07-23 se
   hizo, por tanto, desde un entorno distinto a este. Este paso no es una
   pieza de configuración que falte: es una condición de entorno que debe
   verificarse antes del siguiente paso, en la máquina donde se vaya a
   ejecutar.
2. **Confirmar que `.env` sigue teniendo credenciales de solo lectura
   válidas** para la conexión `prevencion` (ya con esta forma, sin cambio
   de contenido necesario salvo que hayan expirado desde el 23/07).
3. **Ejecutar**:
   ```
   python main.py export drills --mode full --confirm-full-export --generate-evidence --audience both
   ```
4. **Revisar `validation_report.yaml`**: confirmar `status.result` en
   `SUCCESS` o `SUCCESS_WITH_WARNINGS` (nunca `FAILED_*`).
5. **Revisar `comparison_report.yaml`** contra el CSV histórico ya
   disponible — mismo criterio de lectura ya aplicado en la ejecución de
   muestra (§ 0).
6. **Entregar** `drills.csv` + `evidence_client.xlsx` como primer
   resultado completo — sigue siendo `prototype_status: review_only`,
   `approved_for_enablon_import: false`: ningún paso de este documento
   cambia esa condición, que sigue exigiendo una decisión humana explícita
   fuera de este pipeline.

No hace falta ninguna configuración nueva entre el paso 2 y el paso 3 —
es la conclusión operativa central de este documento, sustentada en que
el mismo código, con la misma configuración, ya produjo un resultado
`SUCCESS` real cuatro días antes de esta tarea.

## 11. Qué NO se hace en este documento

- No se ejecuta la exportación en modo `full` (acción real, con
  consecuencias sobre `outputs/`, fuera del alcance de una tarea de
  "organización y consolidación de configuración").
- No se mueve ningún fichero a la estructura propuesta en § 6.
- No se modifica `src/`, Query Engine, Evidence Engine ni Export Engine.
- No se implementa el Framework Core.
- No se crea ninguna ADR — esta tarea es operativa, no fija ninguna
  decisión arquitectónica nueva no cubierta ya por las ADR existentes
  (ADR-006 legado, ADR-008, ADR-012).
