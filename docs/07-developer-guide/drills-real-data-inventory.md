# Inventario mínimo de datos reales — Drills (Sprint 8, Fase 1 — actualizado en Sprint 8.2)

**Status:** Planned

Este inventario se ha construido leyendo únicamente el código y la
configuración YA versionados del pipeline de Drills (`src/export/prototype/drills/`,
`config/exports/drills.yaml`, `config/databases.yaml`,
`docs/01-architecture/external-data-workspace.md`,
`docs/07-developer-guide/local-data-recovery-checklist.md`). No se ha
inventado ningún nombre de archivo que no aparezca explícitamente en esas
fuentes. Donde el nombre exacto no puede determinarse con certeza, se marca
`PENDIENTE DE IDENTIFICACIÓN`.

Recordatorio de alcance (CLAUDE.md, `external-data-workspace.md` § 8): ningún
archivo de este inventario se copia, descarga, reconstruye o inventa
automáticamente — la recuperación es 100% manual, responsabilidad del
usuario, desde sus fuentes originales (Descargas, Teams, SharePoint,
OneDrive, correo, copias locales previas).

## 1. Tabla de inventario

| # | Categoría | Nombre lógico | Nombre de archivo esperado | Obligatorio | Opcional | Finalidad | Configuración que lo referencia | Formato | Columnas mínimas esperadas | Fuente probable de recuperación | Destino propuesto en el workspace |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ETL / documentación de transformación | Libro ETL de Simulacros/BCM | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` | No (solo auditoría — los lookups ya están extraídos y versionados en `config/exports/drills.yaml`) | Sí | Re-auditar/verificar `typology_lookup`, `letter_lookup`, `workflow_status_lookup` si se cuestiona algún valor; no se relee en cada ejecución | `config/exports/drills.yaml` (comentario líneas 57-69, cita hojas `Mapeo_Tipo_sim`/`Mapeo_Letra`/`Mapeo_Estado`) | XLSX | Hojas `Mapeo_Tipo_sim` (DatoOrigen/DatoDestino), `Mapeo_Letra`, `Mapeo_Estado` | Entrega original del cliente ("Bloque1_ETL"), perdida en el incidente `filter-repo` — recuperar de Teams/SharePoint/OneDrive/copia local previa | `EMF_DATA_ROOT/projects/moeve/ETL/ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` |
| 2 | CSV histórico de Enablon (comparación) | CSV histórico Drills | `Drills-22072026-41.csv` | No (la comparación es y sigue siendo opcional, ver `pipeline.py::_resolve_comparison_csv_path`, migrada a `ResourceResolver` en Sprint 8.5 — ver `docs/01-architecture/resource-resolver.md` § 15) | Sí — obligatorio solo si se quiere `comparison_report.yaml` | Comparar el CSV generado por el prototipo contra el Project Contract (`operational_csv`) | `src/export/prototype/drills/pipeline.py` (`_build_drills_comparison_manifest`/`_resolve_comparison_csv_path`); `docs/01-architecture/external-data-workspace.md` § 6, § 13, § 21, § 23 | CSV, UTF-16LE con BOM, delimitador tabulador (confirmado en `comparison.py::detect_historical_csv`, CLAUDE.md) | Al menos las 8 columnas de `OUTPUT_COLUMNS` (`CS_Typology`, `Reference`, `StartingDate`, `CS_HistoricalOriginID`, `CS_Letter`, `CS_ImpactedEntities`, `CS_WorkflowStatus`, `CS_HistoricalDataOrigin`) entre las 36 reales | Entrega del cliente ("Bloque4_CSV_Enablon"), perdida en el incidente — el usuario ya la tenía contrastada según CLAUDE.md ("CSV reales recibidos y contrastados para todos los módulos") | Desde Sprint 8.5, el código busca `CSV_Enablon_Operational/Drills.csv` (Project Contract) — no `CSV_Enablon_Template/`. **Pendiente de clasificar** (ver § 6): el nombre real conocido (`Drills-22072026-41.csv`) encaja por convención en `CSV_Enablon_Template/`, no en `CSV_Enablon_Operational/` — ver `docs/01-architecture/project-contract-model.md` § 4 y `resource-resolver.md` § 15, pregunta abierta sin resolver |
| 2b | — | ⚠️ Discrepancia de nombre — **resuelta por decisión del usuario (Sprint 8, autorización del 2026-07-27)** | Nombre operativo adoptado: **`Drills-22072026-41.csv`** | — | — | Ver § 4 más abajo para la decisión completa y sus condiciones | `inputs/csv_enablon/CONTENIDO_ESPERADO.txt` vs `pipeline.py` | — | — | Resuelta — no se trata ya como pendiente | — |
| 3 | Mapping de entidades | Catálogo de entidad (esquema antiguo, válido para Simulacros) | `entidades_mapeo_ANTIGUO_referencia_historica.csv` | **Sí**, para sample y para full | No | Resolver `IDUnidadOrg` → `CS_ImpactedEntities` | `config/exports/drills.yaml` (`reference_data.entity_catalog_csv`, línea 72) | CSV | `IDUnidadOrg` (clave), `Code` (valor), marcador literal `"No migra"` | **Ya presente localmente** en `inputs/entity_catalog/` (166 733 bytes, gitignored) — no requiere recuperación, nunca estuvo en el historial de Git | Permanece en `inputs/entity_catalog/` por ahora (deuda técnica documentada en `external-data-workspace.md` § 20 — migración futura, no urgente) |
| 4 | Catálogos necesarios | `First_Axis_export_bruto.csv` / `catalogo_resuelto_code_ruta_site.csv` | (nombres ya conocidos) | No requerido por el pipeline actual | No | N/A para Drills — CLAUDE.md confirma explícitamente: *"Simulacros no lo necesita (usa el esquema antiguo de sufijo -XXH... su migración ya está cerrada)"* | No referenciado por `config/exports/drills.yaml` | CSV | N/A | Ya presente localmente en `inputs/entity_catalog/` (gitignored) | No aplica a Drills — no mover |
| 5 | Archivos de comparación | (igual a fila 2 — CSV histórico) | `Drills-22072026-41.csv` | No | Sí | Ver fila 2 | Ver fila 2 | Ver fila 2 | Ver fila 2 | Ver fila 2 | Ver fila 2 |
| 6 | Errores/evidencias históricas | Export Help Desk cliente | `helpdesk_export_834_tickets.xlsx` | No requerido por el pipeline actual | Solo documental | Correlación de hallazgos con tickets (CLAUDE.md), no consumido en tiempo de ejecución del pipeline de Drills | No referenciado por `config/exports/drills.yaml` ni por código de `drills/` | XLSX | N/A | **Ya presente localmente** en `inputs/incidents/` (gitignored) — no requiere recuperación | Sin cambios — permanece en `inputs/incidents/` |
| 7 | SQL / queries requeridas | Query fuente de Drills (creación) | `SQLQuery - DATASET SIMULACRO.sql` | **Sí**, para sample y para full | No | Única fuente SQL del prototipo — "fuente única, sin joins" | `config/exports/drills.yaml` (`source.sql_file`, línea 37) | SQL (texto plano) | N/A (ya es la query completa) | **Ya versionado en Git** (`git ls-files` lo confirma) — no requiere recuperación | Sin cambios — permanece en `sql/source_queries/Simulacros/` |
| 7b | SQL / queries requeridas | Acciones correctoras de Simulacros (tabla de actualización) | `SQLQuery4.sql` (`ITP_SIM_ACCIONES_CORRECTORAS`) | No requerido por el pipeline actual | No | Rol "actualización" documentado en `config/modules.yaml` para Simulacros, pero el prototipo actual solo implementa la etapa de creación (fuente única, sin joins) — no se usa todavía | No referenciado por `config/exports/drills.yaml` | SQL | N/A | Ya versionado en Git | Sin cambios |
| 7c | SQL / queries requeridas | Acciones correctoras (genérico, transversal) | `SQLQuery6.sql` (`ITP_ACCIONES_CORRECTORAS`) / `Acciones correctoras.sql` (join) | No requerido por el pipeline actual de Drills | No | Corresponde al módulo transversal "Action Plans" (`ap` en `config/modules.yaml`), no a Drills | No referenciado por `config/exports/drills.yaml` | SQL | N/A | Ya versionado en Git | Sin cambios |
| 7d | SQL / queries requeridas | Usuarios (lookup de responsable) | `SQLQuery9.sql` (`ITP_USUARIOS`) | No requerido por el pipeline actual | No | Mecanismo confirmado (`historical_user_lookup`) pero las columnas `CS_HistoricalUserId/UserName/DrillResponsibleName` están explícitamente fuera de alcance del prototipo (`excluded_columns` en `drills.yaml`, contienen datos personales) | No referenciado por `config/exports/drills.yaml` (citado solo como excluido) | SQL | N/A | Ya versionado en Git | Sin cambios |
| 8 | Configuración ya versionada — NO recuperar | `config/exports/drills.yaml`, `config/modules.yaml`, `config/databases.yaml`, `config/data_workspace.yaml`, `sql/source_queries/Simulacros/*.sql` | — | — | — | Ya contienen todas las reglas, lookups y queries necesarias para ejecutar el sample | — | YAML / SQL | — | Ya en Git | No aplica — nunca va al workspace externo |

## 2. Resumen de bloqueos para Fase 2/3

Archivos que el usuario debe recuperar manualmente antes de poder ejecutar
un sample real con comparación completa:

1. **Obligatorio para ejecutar sample/full de Drills:** ninguno pendiente —
   la SQL fuente (fila 7) y el catálogo de entidad (fila 3) ya están
   disponibles localmente/en Git.
2. **Opcional, recomendado para comparación:** CSV histórico `Drills-22072026-41.csv`
   (fila 2) — sin él, `comparison_report.yaml` simplemente no se genera
   (comportamiento ya soportado, no es un bloqueo).
3. **Opcional, solo auditoría:** libro ETL `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`
   (fila 1) — solo necesario si se quiere re-verificar el origen de los
   lookups ya congelados en `config/exports/drills.yaml`.

## 4. Decisión — nombre operativo del CSV histórico (Sprint 8, 2026-07-27)

**Nombre operativo adoptado: `Drills-22072026-41.csv`.**

Motivo (decisión del usuario, no una inferencia del análisis):

- es el nombre referenciado por el código/configuración operativa vigente
  (`pipeline.py::HISTORICAL_CSV_RELATIVE_PATH`);
- `simulacros_Drills.csv` aparece únicamente en
  `inputs/csv_enablon/CONTENIDO_ESPERADO.txt`, que documenta una convención
  histórica del ZIP inicial de Claude Web — no necesariamente el contrato
  vigente del pipeline.

Reglas que se mantienen a partir de esta decisión:

- **No se asume que ambos nombres correspondan a conjuntos de datos
  distintos** — pueden ser (o no) la misma exportación con dos convenciones
  de nombre superpuestas; esto sigue sin confirmarse.
- Si al recuperar los archivos reales solo aparece `simulacros_Drills.csv`
  (y no `Drills-22072026-41.csv`), **no se renombra ni se copia
  automáticamente**. En ese caso: detenerse y proponer al usuario una de
  dos vías — (a) actualizar `pipeline.py::HISTORICAL_CSV_RELATIVE_PATH`
  para que apunte al nombre real recuperado, o (b) generar una copia
  operativa explícita con el nombre esperado, documentando la
  correspondencia. Ninguna de las dos se ejecuta sin aprobación.
- Destino previsto (sin crear el archivo — la recuperación sigue siendo
  manual): ver § 6 — pendiente de decidir entre `CSV_Enablon_Template/` y
  `CSV_Enablon_Operational/` (Sprint 8.2 introduce esta distinción, no
  existía cuando se escribió esta sección en Sprint 8).
  **No se crea un CSV vacío o ficticio con este nombre bajo ninguna
  circunstancia.**

## 5. Archivo ETL — estado (sin cambios respecto a Fase 1)

`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` sigue siendo **opcional** para
el pipeline actual (no bloquea sample ni full). Útil para auditoría
funcional, revisión de mappings, contraste con la lógica histórica y
trazabilidad de reglas. Destino previsto (no creado, no descargado, no
modificado): `EMF_DATA_ROOT/projects/moeve/ETL/ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`.

## 6. Ubicaciones Sprint 8.2 — estructura de workspace evolucionada

El workspace externo real de este equipo (`EMF_DATA_ROOT`, ver
`external-data-workspace.md` § 5, § 21) tiene, desde Sprint 8.2, estas
carpetas ya creadas (vacías — ningún archivo colocado todavía):

```
EMF_DATA_ROOT/projects/moeve/
    ETL/                          <- fila 1 de este inventario
    CSV_Enablon_Template/         <- Platform Contract (ver project-contract-model.md)
    CSV_Enablon_Operational/      <- Project Contract (ver project-contract-model.md)
    Mappings/                     <- reglas de correspondencia (no confundir con
                                      inputs/entity_catalog/, que sigue siendo la
                                      ubicación real del catálogo de Simulacros, fila 3)
    Catalogs/
    Errors/                       <- fila 6 de este inventario (helpdesk_export_834_tickets.xlsx)
    Evidence/                     <- evidence_internal.xlsx/evidence_client.xlsx de una
                                      ejecución REAL (no de test) generados por Drills
    SQL/
    Outputs/
    Archive/                      <- ya contiene env-backup-before-sprint8.txt (metadatos, sin datos reales)
```

**Dónde debe colocar el usuario cada tipo de documento pendiente de
recuperar** (ninguno recuperado todavía, ninguna carpeta con contenido
real a la fecha de este documento):

| Documento | Carpeta destino | Estado |
|---|---|---|
| ETL (`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`) | `ETL/` | Pendiente de recuperación (opcional, § 5) |
| CSV Template (export completo de Enablon, si se consigue uno distinto del ya conocido) | `CSV_Enablon_Template/` | Pendiente — no se sabe todavía si existe un fichero distinto de `Drills-22072026-41.csv` para este rol |
| CSV Operacional (`Drills-22072026-41.csv`, si se confirma que es el realmente cargado) | `CSV_Enablon_Operational/` | Pendiente de clasificación — ver fila 2 de § 1 y `project-contract-model.md` § 4 |
| Mappings adicionales (si se recuperan reglas de correspondencia más allá del catálogo ya presente en `inputs/entity_catalog/`) | `Mappings/` | No requerido hoy — el catálogo real ya usado por Drills permanece en `inputs/entity_catalog/` (fila 3, deuda técnica ya documentada) |
| Evidencias de una ejecución real | `Evidence/` | No aplica todavía — no se ha ejecutado ningún sample/full real desde que existe el workspace |
| Errores (`helpdesk_export_834_tickets.xlsx`) | `Errors/` | Ya presente localmente en `inputs/incidents/` (gitignored) — no requiere recuperación ni movimiento a este workspace |

**Ningún archivo se ha movido, copiado ni generado de forma ficticia en
esta actualización** — esta sección solo documenta destinos previstos
para cuando el usuario recupere manualmente el material pendiente.

**Nota de nomenclatura (Sprint 8.3)**: al incorporar el ETL a `ETL/`, el
nombre destino sigue `workspace-naming-convention.md` § 2 —
`Drills.xlsx`, no el nombre original del cliente
(`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`). El CSV Operacional, si se
confirma, se incorpora como `Drills.csv` (§ 4 de la misma convención). El
CSV Template conserva su nombre original de Enablon sin cambios (§ 3).

## 7. Inventario operativo por módulo (Sprint 8.3, Fase 3)

Extiende el inventario de Drills a los demás módulos conocidos de
`config/modules.yaml`, para dar visión completa del estado del workspace
operativo. **Ningún nombre de archivo se asume** para los módulos sin
código todavía — se marca `PENDIENTE` cuando no hay evidencia de un
nombre real.

| Módulo | ETL | Template | Operational | SQL | Mapping | Estado | Comentarios |
|---|---|---|---|---|---|---|---|
| **Drills** (simulacros) | PENDIENTE (`Drills.xlsx` esperado, no recuperado) | PENDIENTE (clasificación de `Drills-22072026-41.csv` sin resolver, ver § 4) | PENDIENTE | Disponible en Git (`sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql`) — no en el workspace externo | Disponible en `inputs/entity_catalog/` (repo, gitignored) — no en el workspace externo | **Implementado** (único módulo con `config/exports/drills.yaml` y pipeline ejecutable) | Único módulo con pipeline real; ver `drills-csv-contract.md` para el contrato de 8/36 columnas |
| **Safety Meetings** | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/SM/*.sql`, 3 ficheros) | Catálogo real aplicado según CLAUDE.md (0% no catalogado tras aplicar `First_Axis`) — mecanismo no portado a código | No implementado (sin `config/exports/`) | — |
| **MOC** | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/MOC/*.sql`, 8 ficheros) | Catálogo real aplicado según CLAUDE.md; `idcentro_map_gct` embebido en `config/modules.yaml` | No implementado | Hallazgo #1 (infra-migración La Rábida/Palos) confirmado para este módulo — ver CLAUDE.md |
| **Bypass** | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/bypass/*.sql`, 2 ficheros) | Catálogo real aplicado según CLAUDE.md | No implementado | — |
| **Eventos** (antiguos+nuevos+PSM) | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/Eventos/*.sql` + `sql/source_queries/PSM/*.sql`, 12 ficheros) | No confirmado si el catálogo real ya se aplicó a este módulo (`OQ-ENT-04`, ver `knowledge-traceability-matrix.md`) | No implementado | `FULL JOIN` de la query de Eventos Antiguos infla el "origen" — ver CLAUDE.md |
| **OPS** | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/OPS/*.sql`, 2 ficheros) | No confirmado (`OQ-ENT-04`) | No implementado | — |
| **Inspecciones** | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/Inspecciones/*.sql`, 6 ficheros) | No confirmado (`OQ-ENT-04`) | No implementado | Mayor volumen del proyecto (641224 filas de respuestas de checklist, CLAUDE.md) |
| **Acciones Correctoras** (AP) | PENDIENTE | PENDIENTE | PENDIENTE | Disponible en Git (`sql/source_queries/AP/Acciones_correctoras.sql`) | Transversal — depende de la resolución de entidad de cada módulo origen | No implementado | Módulo transversal, alimentado por `ITP_Acciones_correctoras` clasificada por `idorigenac` (CLAUDE.md) |

**Lectura de la tabla**: "SQL" y "Mapping" para los 7 módulos no-Drills
se refieren a material **ya versionado en Git o ya presente localmente**
(no en el workspace externo `EMF_DATA_ROOT`) — ninguno de estos 7 módulos
tiene todavía una carpeta de código (`config/exports/<módulo>.yaml`) que
los consuma en tiempo de ejecución, a diferencia de Drills.

## 8. Checklist de artefactos mínimos para el primer sample (Sprint 8.3, Fase 8)

Extiende `docs/01-architecture/drills-operational-mvp.md` § 2 (Sprint 5,
sin cambios de código desde entonces) con la clasificación pedida por
Sprint 8.3:

| Artefacto | Clasificación | Estado actual |
|---|---|---|
| Query SQL de origen (`SQLQuery - DATASET SIMULACRO.sql`) | **Imprescindible** | Disponible (Git) |
| Catálogo de entidad (`entidades_mapeo_ANTIGUO_referencia_historica.csv`) | **Imprescindible** | Disponible (`inputs/entity_catalog/`, local) |
| Credenciales SQL de solo lectura (`.env`) | **Imprescindible** | Presente localmente (no verificado su vigencia en este sprint — Sprint 8.2/8.3 no tocaron `.env`) |
| Conectividad de red real a SQL Server desde el entorno de ejecución | **Imprescindible** | No verificable desde este entorno de análisis (CLAUDE.md, "Estado de los accesos") |
| CSV histórico de comparación (`Drills-22072026-41.csv`) | **Recomendable** | Pendiente de recuperación e incorporación al workspace (§ 2, § 6) — sin él, `comparison_report.yaml` no se genera, pero el sample sí se ejecuta |
| Libro ETL (`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` → `Drills.xlsx`) | **Solo auditoría** | Pendiente de recuperación — no bloquea el sample (los lookups ya están congelados en `config/exports/drills.yaml`) |
| CSV Operacional (`Drills.csv`, Project Contract) | **Solo auditoría / futura validación** | Pendiente — su ausencia no bloquea el sample; su presencia habilitaría la futura comparación de 3 vías (`project-contract-model.md` § 5), no implementada |
| CSV Template adicional (distinto del ya conocido) | **Solo histórico** | No se sabe si existe; no requerido para ejecutar nada |
| Documento de incidencias (`helpdesk_export_834_tickets.xlsx`) | **Solo histórico** | Ya presente localmente (`inputs/incidents/`), no consumido por el pipeline |

**Conclusión**: los 4 artefactos "Imprescindible" para un sample real de
Drills están, en su mayoría, ya disponibles — el único punto no
verificado en este sprint es la conectividad de red real a SQL Server y
la vigencia de las credenciales (ninguna de las dos se comprobó, por
estar fuera de alcance de un sprint que no ejecuta SQL).
