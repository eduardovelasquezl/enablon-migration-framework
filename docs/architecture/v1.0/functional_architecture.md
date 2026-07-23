# Arquitectura funcional

Describe **comportamiento**, no implementación. Para el detalle técnico, ver
[`technical_architecture.md`](technical_architecture.md).

## Objetivo del framework

Convertir el conocimiento disperso de una migración histórica a Enablon —queries
SQL, ETL Excel, catálogos de entidades, CSV ya exportados, incidencias del
cliente— en una base de conocimiento estructurada y auditable, y a partir de ella
determinar, campo a campo y registro a registro, qué está listo para migrar, qué
requiere una decisión del cliente y qué no puede migrar sin más información.

**Status: Implemented** (el motor de análisis y consolidación); **Approved
Design** (la generación del CSV final, ver `export_engine.md`).

## Entradas

| Entrada | Naturaleza |
|---|---|
| Queries SQL de extracción | Texto `.sql`, provisto por el cliente |
| ETL Excel históricos | Libros `.xlsx`/`.xlsm` con hojas de mapeo, reglas y datos |
| CSV reales exportados de Enablon | Export de referencia, para contrastar estructura |
| Catálogo de entidades | Export `First_Axis` de Enablon + mapeos de código→ruta |
| Incidencias del cliente (Help Desk) | Ticket export, para relacionar defectos conocidos |
| Inventario SQL | Metadatos de tablas/vistas/FKs ya extraídos (solo lectura) |

Ninguna entrada se modifica nunca. El framework no tiene conectividad de escritura
al SQL de origen ni a Enablon.

## Procesamiento

El framework analiza estas entradas en capas sucesivas (ver
[`processing_flow.md`](processing_flow.md) para el detalle fase a fase):

1. Entiende la estructura física del origen (SQL) y de los ETL (Excel).
2. Resuelve, campo a campo, cuál es el destino real en Enablon — nunca por
   coincidencia de nombre, siempre por evidencia verificable.
3. Clasifica cada valor/clave real frente a las tablas de equivalencia: mapeado,
   "No migra", sin correspondencia (bloqueado) o sin correspondencia con
   fallback documentado.
4. Consolida esa clasificación por módulo y, para los objetos que cruzan varios
   módulos (hoy, únicamente Action Plans), a nivel de proyecto completo.
5. Determina qué registros están listos para generar su CSV final y cuáles no,
   y por qué.

## Salidas

| Salida | Estado |
|---|---|
| Informes de cobertura de mapeo (`unmapped_entities.csv`, `records_blocked_by_mapping.csv`, `client_mapping_questions.xlsx`, etc.) | **Implemented** |
| Resultado de orquestación de proyecto (`project_analysis_summary.json`, `manifest.yaml`, CSV de Action Plans ready/blocked/excluded) | **Implemented** — son salidas de *análisis/readiness*, no el CSV de importación a Enablon |
| CSV definitivo de carga a Enablon | **Approved Design** — no se genera todavía, ver `export_engine.md` |

## Usuarios

- **Analista/consultor de migración**: usa los informes de cobertura y bloqueo
  para decidir cómo resolver cada excepción y para comunicarlas al cliente.
- **Cliente**: recibe `client_mapping_questions.xlsx` y los CSV de bloqueados/
  excluidos como base para tomar decisiones funcionales documentadas.
- **Desarrollador del framework**: extiende el motor de análisis módulo a
  módulo, sin tocar la orquestación global.

## Responsabilidades

- El framework **decide y clasifica**, nunca **carga**. La entrega a Enablon
  (manual o vía API) queda fuera de su responsabilidad, al menos en esta versión.
- El framework **nunca resuelve una ausencia de evidencia inventando un valor**
  — la marca como bloqueada, pendiente o requiere revisión del cliente.
- El framework **conserva siempre la trazabilidad** desde el registro histórico
  de origen hasta la clasificación final.
