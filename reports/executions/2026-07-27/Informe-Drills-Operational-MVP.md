# Informe — Drills Operational MVP (Sprint 5)

**Proyecto:** Enablon Migration Framework (EMF) / Migración Histórica a Enablon
**Fecha:** 2026-07-27
**Tarea:** Organización y consolidación de configuración para ejecutar por
primera vez una extracción completa (`full`) de Drills. Sin implementación
de código, sin modificar Query/Evidence/Export Engine ni `src/`.

---

## 0. Hallazgo central (reencuadra toda la tarea)

Antes de inventariar nada, se encontró que **ya existe una ejecución
completa y exitosa** del pipeline de Drills en modo `sample`:
`outputs/prototype/drills/20260723T195418Z/` — `status.result: SUCCESS`,
0 errores, 0 warnings, 100/100 filas exportadas, con `drills.csv`,
`validation_report.yaml`, `export_manifest.yaml`, `comparison_report.yaml`,
`issues.jsonl`, `evidence_internal.xlsx` y `evidence_client.xlsx` ya
generados y correctos. Esto significa que el prototipo **no está por
probar — ya está probado con datos reales**. El resto de este informe se
apoya en esa evidencia, no en inferencia sobre si el código "debería"
funcionar.

---

## 1. Flujo operativo

```
Fuente SQL (config/databases.yaml + .env, conexión "prevencion")
  -> Query (sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql)
  -> Extracción (extractor.py -- sample trunca local; full exporta todo)
  -> Transformación + mapeo (transformations.py, mappings.py, drills.yaml)
  -> Validación pre-escritura (validator.py)
  -> Escritura CSV (exporter.py)
  -> Validación post-escritura (validator.py)
  -> validation_report.yaml / export_manifest.yaml (manifest.py)
  -> comparison_report.yaml (comparison.py, si hay histórico)
  -> issues.jsonl (pipeline.py)
  -> [opcional] Evidence Engine: evidence_internal.xlsx / evidence_client.xlsx
```

Un único comando (`python main.py export drills ...`) ejecuta toda la
cadena sin pasos manuales intermedios (salvo, opcionalmente, generar
evidencia).

---

## 2. Configuración requerida y su estado

Las 9 piezas de configuración necesarias (conexión SQL, query, mapeo de
campos, catálogos de referencia, formato de salida, política de
validación, registro de proyecto/módulo, directorio de salida, CSV
histórico de comparación) **ya están todas presentes, configuradas con
datos reales y confirmadas funcionales** por la ejecución del
2026-07-23. Ninguna requiere configuración nueva para repetir el
resultado ya obtenido en modo `sample`.

---

## 3. Dependencias

Cadena de dependencia real (no de importancia):

```
.env -> databases.yaml -> extractor.py -> transformations.py/mappings.py
  -> (entity_catalog.csv, reference_data de drills.yaml)
  -> validator.py (pre) -> exporter.py -> validator.py (post)
  -> manifest.py (validation_report -> export_manifest)
  -> comparison.py (opcional) -> pipeline.py (issues.jsonl)
  -> evidence/collector.py + workbook.py (opcional, último eslabón)
```

Ninguna etapa se salta ni se reordena — el pipeline ya implementado
respeta esta cadena exactamente.

---

## 4. Duplicidades y configuración dispersa detectadas

1. `config/exports/drills.yaml` mezcla 6 responsabilidades en un único
   fichero (proyecto, fuente, plantilla, mapeo de valores, reglas de
   campo, validación) — manejable con un objeto, riesgo señalado para
   cuando llegue un segundo.
2. `HISTORICAL_CSV_PATH` (ruta del CSV histórico de comparación) es una
   **constante Python dentro de `pipeline.py`**, no una entrada YAML —
   inconsistente con el resto de la configuración de Drills.
3. `config/modules.yaml` mezcla registro de módulo con catálogos de
   traducción IDCentro→Site (`idcentro_map_itp`/`idcentro_map_gct`) —
   son conceptualmente catálogos, no metadatos de módulo.
4. `config/validation_rules.yaml` mezcla un catálogo documental de reglas
   ETL legado (no ejecutado por el prototipo) con validaciones de calidad
   de datos genéricas (tampoco conectadas a ningún motor todavía).
5. `sql/source_queries/Simulacros/` tiene 4 ficheros sin usar por el
   pipeline actual (`SQLQuery4.sql`, `SQLQuery6.sql`, `SQLQuery9.sql`,
   `Acciones correctoras.sql`), sin documentación de su propósito.
6. `inputs/mappings/` e `inputs/etl/` están declarados en
   `config/settings.yaml` pero **vacíos** — el contenido real equivalente
   vive en `inputs/_incoming_claude_web/`, nunca consolidado en las rutas
   canónicas declaradas.
7. `inputs/entity_catalog/` tiene 3 ficheros; Drills solo usa 1
   (`entidades_mapeo_ANTIGUO_referencia_historica.csv`) — los otros 2 son
   el catálogo vigente para OTROS módulos, deliberadamente no aplicable a
   Simulacros (esquema histórico ya cerrado, según `CLAUDE.md`) — no es
   un error, pero podría parecerlo sin este documento.

Ninguna de estas 7 es bloqueante para ejecutar Drills.

---

## 5. Inventario completo

- **Configuración existente y funcional**: conexión SQL, `.env`, todo
  `drills.yaml`, la query de origen, el catálogo de entidad, el CSV
  histórico de comparación, y todo el código de
  `src/export/prototype/drills/`, `src/evidence/`, `src/query/`, `src/db/`.
- **Configuración reutilizable** (para un segundo objeto): el patrón
  `output:`/`invalid_row_policy`, `config/databases.yaml`, la separación
  `reference_data`/`fields`, el catálogo cerrado de filtros del Query
  Engine.
- **Configuración obsoleta o sin confirmar**: los 3 ficheros SQL sin usar
  en Simulacros; las reglas de `validation_rules.yaml` marcadas
  `confirmado_con_datos_reales: false`.
- **Configuración que falta**: una ejecución real en modo `full` (nunca
  realizada); `HISTORICAL_CSV_PATH` declarado en YAML en vez de en
  código; un manifiesto que aclare qué SQL de Simulacros está en uso.
  Ninguna de estas bloquea la ejecución.

---

## 6. Estructura de configuración propuesta (sin mover archivos)

```
config/
├── projects/moeve/{project.yaml, modules.yaml}
├── sources/{databases.yaml, site_catalogs.yaml}
├── queries/simulacros.yaml       (declara objeto->fichero .sql->hash esperado,
│                                   el .sql en sí sigue en sql/source_queries/)
├── mappings/drills.yaml           (reference_data + fields)
├── templates/drills.yaml           (output: + excluded_columns + HISTORICAL_CSV_PATH)
└── validation/{drills.yaml, validation_rules.yaml}
```

Documentado, no ejecutado en esta tarea (el encargo pide documentar
primero). Su beneficio real se materializa con un segundo objeto migrable
— con un único objeto, el fichero único actual no es un problema urgente
(mismo principio "No Abstraction Without a Real Consumer" ya aplicado en
el resto de la documentación EMF de este repositorio).

---

## 7-8. Artefactos y validaciones

7 artefactos posibles por ejecución (`drills.csv`, `validation_report.yaml`,
`export_manifest.yaml`, `issues.jsonl` obligatorios; `comparison_report.yaml`
condicional al histórico; `evidence_*.xlsx` condicional a
`--generate-evidence`; `generated_query.sql` condicional a `--filter`).
Todas las validaciones (pre-escritura, post-escritura, duplicados de
`Reference`, comparación cuantitativa) ya se ejecutan sin cambios
necesarios para modo `full`.

---

## 9. Checklist operativa (orden de dependencia real)

```
[x] Fuente            -- config/databases.yaml + .env               IMPLEMENTADO Y CONFIGURADO
[x] Query validada      -- SQLQuery - DATASET SIMULACRO.sql          IMPLEMENTADO Y VALIDADO
[x] Catalogos            -- entity_catalog + reference_data          IMPLEMENTADO Y CONFIGURADO
[x] Mapping completo       -- 7 reglas / 8 columnas en alcance        IMPLEMENTADO (alcance definido)
[x] Template definido       -- output: block de drills.yaml           IMPLEMENTADO Y VALIDADO
[x] Validation Profile        -- invalid_row_policy + validator.py    IMPLEMENTADO Y VALIDADO
[x] Proyecto                   -- object_id/module + modules.yaml     IMPLEMENTADO (disperso, no bloqueante)
[x] Output                      -- outputs/prototype/drills/          IMPLEMENTADO Y FUNCIONAL
[x] Manifest                     -- export_manifest.yaml               IMPLEMENTADO Y VALIDADO
[x] Evidence                      -- evidence_internal/client.xlsx     IMPLEMENTADO Y VALIDADO
[ ] Reports                        -- resumen ejecutivo distinto       NO EXISTE COMO ARTEFACTO (ver nota)
[ ] Ejecucion en modo FULL          -- nunca realizada                 PENDIENTE -- unico paso real
```

Nota "Reports": no existe un artefacto técnico distinto de
`evidence_client.xlsx`, que ya cumple ese propósito. Si se necesita un
resumen ejecutivo adicional, es comunicación humana, no configuración o
código faltante.

**Todos los puntos marcados están, a la vez, implementados en código Y
configurados con datos reales** — el único punto genuinamente pendiente
es la ejecución en modo `full` en sí.

---

## 10. Camino más corto al primer `drills.csv` completo

1. Confirmar conectividad de red real a SQL Server desde el entorno de
   ejecución — `CLAUDE.md` documenta explícitamente que el entorno de
   análisis actual **no** tiene esa conectividad; la ejecución exitosa
   del 23/07 se hizo desde otro entorno.
2. Confirmar que `.env` sigue teniendo credenciales de solo lectura
   válidas para `prevencion`.
3. Ejecutar: `python main.py export drills --mode full --confirm-full-export --generate-evidence --audience both`
4. Revisar `validation_report.yaml` (`status.result` en `SUCCESS`/`SUCCESS_WITH_WARNINGS`).
5. Revisar `comparison_report.yaml` contra el histórico.
6. Entregar `drills.csv` + `evidence_client.xlsx` — sigue
   `prototype_status: review_only`, `approved_for_enablon_import: false`.

No hace falta ninguna configuración nueva entre el paso 2 y el 3.

---

## 11. Qué no se hizo en esta tarea

No se ejecutó la exportación en modo `full` (acción real, fuera del
alcance de "organización y consolidación"). No se movió ningún fichero a
la estructura propuesta. No se modificó `src/`, Query/Evidence/Export
Engine, ni se implementó el Framework Core. No se creó ninguna ADR (tarea
operativa, sin decisión arquitectónica nueva).

---

## 12. Archivos creados y modificados

**Creados:**
- `docs/01-architecture/drills-operational-mvp.md`
- `reports/executions/2026-07-27/Informe-Drills-Operational-MVP.md` (este informe)
- `reports/executions/2026-07-27/Informe-Drills-Operational-MVP.txt` (mismo informe, texto plano)

**Modificados:** ninguno.

Ningún archivo de `src/`, `tests/`, `config/`, `sql/`, `inputs/`,
`outputs/` fue tocado ni movido.

---

## 13. Rutas de los informes

- MD: `reports/executions/2026-07-27/Informe-Drills-Operational-MVP.md`
- TXT: `reports/executions/2026-07-27/Informe-Drills-Operational-MVP.txt`

Contenido idéntico entre ambos — solo difiere el formato (Markdown vs.
texto plano con separadores ASCII).

---

## 14. Resultado de validaciones

- [OK] No se modificó `src/`, Query/Evidence/Export Engine.
- [OK] No se implementó el Framework Core.
- [OK] No se movió ningún fichero de configuración.
- [OK] Checklist ordenada por dependencia real, no por importancia.
- [OK] Cada punto de la checklist indica su estado real (implementado vs.
  pendiente), sustentado en evidencia (la ejecución del 2026-07-23), no en
  suposición.
- [OK] Camino mínimo propuesto sin mejoras arquitectónicas, motores
  nuevos ni plugins.

---

## 15. git status --short

```
?? docs/01-architecture/drills-operational-mvp.md   (nuevo)
?? reports/executions/2026-07-27/Informe-Drills-Operational-MVP.md   (nuevo)
?? reports/executions/2026-07-27/Informe-Drills-Operational-MVP.txt  (nuevo)
```

(el resto de `docs/*` y `reports/executions/2026-07-27/*` de tareas
anteriores ya figuraban sin trackear antes de esta tarea)

## 16. git diff --stat

No aplica de forma útil: ningún fichero del repositorio está trackeado
todavía en git. Verificado con `git diff --no-index --check`: sin errores
de espacio en blanco (solo aviso de normalización LF→CRLF).

No se realizó commit de ningún cambio.
