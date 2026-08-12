# Informe de Ejecución — Sprint 8.8: Mapping Governance & Knowledge Consolidation

**Fecha:** 2026-08-12
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Inspección y documentación de solo lectura del workspace real
de Moeve (`EMF_DATA_ROOT/projects/moeve/`). Sin ejecución de SQL Server,
macros, Power Query ni recálculo. Sin commit.

## 1. Resumen ejecutivo

Este sprint tuvo, por primera vez, acceso de solo lectura a los 11 ETL
Excel reales de Moeve (21 MB–361 MB cada uno), los 44 CSV reales
(Template + Operational), el export de incidencias del cliente y los
mappings de entidad/attachments. El objetivo no era migrar ni ejecutar
nada — era convertir ese conocimiento, hasta ahora disperso en Excel
individuales, en documentación estructurada, versionada y auditable
dentro del EMF.

Resultado: 4 documentos nuevos (`mapping-governance.md`,
`knowledge-source-governance.md`, `moeve-source-inventory.md`,
`moeve-mapping-backlog.md`), un conjunto concreto de artefactos de
conocimiento para el caso obligatorio del encargo (Action Plans, en
`config/knowledge/moeve/ap/`), y este informe. Se confirmaron 3 hallazgos
nuevos no documentados en `CLAUDE.md` (§ 6), se abrieron 3
`KNOWLEDGE_CONFLICT` (ninguno resuelto en silencio) y se generó un
backlog de 19 ítems priorizados (8 P1, 6 P2, 4 P3, 1 P4). No se ha hecho
ningún commit — ver § 22 para la propuesta.

## 2. Fuentes inspeccionadas

61 archivos en `EMF_DATA_ROOT/projects/moeve/`: 11 ETL, 14 CSV Template,
30 CSV + 2 XLSX Operational, 1 CSV de Errors (28 tickets), 1 CSV de
Mappings (`AttachmentsLast.csv`, 31 MB) y 2 archivos `.zip` **no
extraídos** (`Mappings/OneDrive_2_12-8-2026.zip`,
`SQL/OneDrive_1_12-8-2026.zip` — prohibido extraer sin autorización, no
solicitada). Detalle completo, por categoría y con `source_document_id`,
en `docs/07-developer-guide/moeve-source-inventory.md` § 1.

Método de extracción de los ETL: inspector Python de solo lectura
(`openpyxl`, `read_only=True`, `data_only=False`), leyendo hoja,
visibilidad, cabecera y una muestra acotada de filas — nunca el libro
completo, dado el tamaño (hasta 361 MB). Detección de VBA/conexiones/
Power Query por listado de la estructura interna del contenedor ZIP del
propio `.xlsx`/`.xlsm` (metadata de nombres de parte, nunca ejecución).

## 3. Módulos detectados

`simulacros`, `safety_meetings`, `moc`, `bypass`, `eventos` (+ impactos,
investigaciones, PSM), `ops`, `inspecciones`, `ap` — los 9 ya conocidos
por `config/modules.yaml`. No se detectó ningún módulo adicional.
Clasificación completa (ETL/Template/Operational por módulo) en
`moeve-source-inventory.md` § 2.

**Gap de evidencia nuevo:** `bypass`, `ops` y `ap` no tienen ningún CSV
Template en este workspace — solo Operational. La comparación
Template-vs-Operational (Fase 6 del encargo) no pudo hacerse para esos 3
módulos.

## 4. Versiones ETL

Matriz completa en `moeve-source-inventory.md` § 3–4. Dos casos de
versionado identificados:

- **Action Plans**: 2 ETL, no secuenciales — cubren ámbitos de origen
  distintos (MOC/GCT vs. ITP-genérico). Ver § 5.
- **MOC**: 2 `.xlsm` con estructura idéntica de 80 hojas
  (`ETL_MOC_m_NEW_SITECAN.xlsm`, 2026-07-28; `ETL_MOC_NewColumns.xlsm`,
  2026-08-11) — mismo esqueleto, diferencia de columnas dentro de hoja no
  comparada en este sprint (backlog P2-03).

## 5. Action Plans — última versión verificada del mapping del eje

Caso obligatorio del encargo. Resumen (detalle completo en
`mapping-governance.md` § 7 y `config/knowledge/moeve/ap/mapping-evidence.md`):

El ETL de ámbito **MOC/GCT** (`ETL- AP_GCT_NEW_SITECAN.xlsx`) tiene dos
hojas que el ETL de ámbito **ITP-genérico**
(`ETL- AP-Con Ajuste Entidad_NEW_SIETCAN (1).xlsx`) no tiene:
`Exportación eje` (catálogo vivo, mismo patrón que `First_Axis`) y
`MapeoEje_uorg` (regla declarativa de resolución en 2 pasos). El ETL
ITP-genérico solo tiene la hoja `Entidades_Mapeo`, el mecanismo estático
ya marcado obsoleto en `CLAUDE.md`.

**Se registró como `mapping_revision` con `rule_revision: 2` (nueva,
`CURRENT_UNVERIFIED`) sustituyendo conceptualmente a `rule_revision: 1`
(`HISTORICAL`)** — pero **no** se marcó `CURRENT_VERIFIED` sin
confirmación humana: ambos ETL cubren ámbitos de origen distintos, y no
puede confirmarse solo con evidencia estructural si el mecanismo nuevo
debía alcanzar también al ámbito ITP-genérico y se quedó atrás, o si son
mecanismos deliberadamente distintos por sistema de origen. Se abrió
`KNOWLEDGE_CONFLICT KC-AP-001` (backlog P1-01) — no resuelto en silencio,
pendiente de confirmación del cliente/consultor.

## 6. CSV Template vs. Operational

Comparación completa por módulo en `moeve-source-inventory.md` § 6.
Hallazgos clave:

- Encoding **no uniforme**: Template siempre `UTF-16`/tab; Operational
  mezcla `UTF-8`/`UTF-16`/`latin-1` incluso dentro del mismo módulo.
- `moc`: el Template (`Change Register-17.csv`, 106 columnas) es un
  superset amplio del Operational real (61 columnas) — coherente con la
  distinción Platform/Project Contract ya fijada en
  `project-contract-model.md`.
- `ap`: 3 exports Operational con 33/31/31 columnas **distintas entre
  sí**, sin Template de referencia.
- `safety_meetings`: 1 columna sin nombre en el Operational real,
  posición 19/22 — `UNRESOLVED_RULE` (P2-05).

## 7. Project Contracts

Definidos (a nivel de columnas observadas) para los 8 módulos con CSV
Operational disponible. Ninguno tiene, en este sprint, sus columnas
cruzadas celda-a-celda contra la hoja de regla exacta más allá de los
casos AP/MOC/Drills ya trabajados — ver metodología de cobertura en
`moeve-mapping-backlog.md` § 1 y tabla de estado real en § 1.1.

## 8. Campos estándar

No se generó un catálogo formal de campos estándar por módulo en este
sprint (no pedido explícitamente más allá de distinguirlos de `CS_` en
las tablas de columnas ya producidas, `moeve-source-inventory.md` § 6).

## 9. Campos `CS_`

Contados por archivo (no deduplicados entre exports del mismo módulo, ni
tratados como el mismo concepto solo por compartir nombre — ver
`mapping-governance.md`, principio de independencia): de 71 columnas en
`Events-4.csv` (Template), 47 son `CS_`; de 106 en `Change Register-17.csv`
(Template MOC), 58 son `CS_`; de 92 en `Impacts-9.csv`, 43. Conteo
completo por los 46 CSV en el scratchpad de sesión (no incorporado al
repositorio — ver § 20). Ningún campo `CS_` se trató como idéntico a otro
por compartir `evidence_id` o nombre parecido, conforme a la Fase 8 del
encargo.

## 10. Mappings

Dos patrones de hoja de regla confirmados con evidencia real en múltiples
ETL: Patrón A (`CampoOrigen | Field Destiny XML | ... | Transformation
From`) y Patrón B (`DatoOrigen | DatoDestino | EsCondicion | ReglaEspecial
| Parametro`) — ambos ya descritos en `CLAUDE.md`, ahora confirmados con
evidencia de hoja real en los 11 ETL. Reglas confirmadas con evidencia de
celda (no solo de cabecera): `titlefix`+`cloneorigin` combinados en la
misma fila (Simulacros, AP, Safety Meetings), `nullcontrol` con el
literal `"No name defined in historical data"` (Simulacros). Detalle en
`mapping-governance.md` § 6.

## 11. Entity mappings

`inputs/entity_catalog/` (First_Axis) sigue siendo la fuente de verdad ya
fijada — no se reabre esa decisión. Se confirma que las hojas
`Exportación eje` embebidas en `ap_gct`/`moc_m_new`/`moc_newcolumns`
siguen el mismo patrón exacto que `First_Axis`, no uno divergente.
`Entidades_Mapeo` (estático, deprecado) sigue presente en 8 de los 11 ETL.

## 12. ITP

`KNOWLEDGE_CONFLICT KC-ITP-003` (informativo, no bloqueante para este
repositorio): la modernización del mapeo de eje (catálogo vivo) llegó a
MOC y AP-GCT (origen GCT) pero no a los 6 módulos restantes de origen
ITP-genérico, que siguen dependiendo de `Entidades_Mapeo` estático
**dentro del ETL original del cliente**. No afecta a este repositorio
(que ya usa la fuente correcta), pero es relevante como posible
antecedente del Hallazgo #1. Detalle en `moeve-source-inventory.md` § 7.

## 13. Attachments

`Mappings/AttachmentsLast.csv` (31 MB, 9 columnas: `Ruta; Centro; Tipo de
Informe; TipoNombre; Idinforme; IdSharpoint; Nombre de fichero; WebUrl;
Visible`) **no es un mapping de entidades ni pertenece solo a Drills** —
es el catálogo consolidado de referencias SharePoint, estructuralmente
idéntico al patrón `TablaAdjuntos`/`AdjuntosGCT`/`AdjuntosSITECANARIAS`
embebido en 8 de los 11 ETL, usado transversalmente por todos los módulos
que cargan adjuntos. `Centro` no se resolvió contra `IDCentro` de ningún
sistema (ITP/GCT) sin cruzarlo módulo a módulo — `UNRESOLVED_RULE`
(P2-07). Ningún módulo implementado en `src/` genera hoy columnas de
adjunto. Detalle en `moeve-source-inventory.md` § 8.

## 14. SQL inventory

48 queries ya versionadas en `sql/source_queries/` (sin cambios). El
`.zip` de `SQL/` no se abrió. Se inspeccionó el contenido de texto
(estático) de `connections.xml` en 1 de los 11 ETL (`eventos_nuevos`):
las conexiones encontradas son Power Query interno tabla-a-tabla dentro
del mismo libro, no queries de extracción SQL Server distintas de las ya
versionadas. Ningún `SQL_ONLY_IN_ETL` con contenido de extracción nuevo
confirmado. Detalle en `moeve-source-inventory.md` § 9.

## 15. Errors — clasificación

`Errors/Requests-12082026-28.csv`, 28 filas. Se clasificaron 3 de forma
detallada (2 `MIGRATION_RELATED`, 1 `PROBABLY_MIGRATION_RELATED`) — una
de ellas confirma el patrón ya conocido de incidencias mal etiquetadas
por módulo (`Module="Behaviour Based Safety"`, contenido real sobre
Simulacros). Las 25 filas restantes quedan pendientes de clasificación
individual (backlog P2-08) — no se clasificaron en lote. Detalle en
`moeve-source-inventory.md` § 10.

## 16. Knowledge conflicts (resumen)

| ID | Módulo | Estado | Bloqueante |
|---|---|---|---|
| `KC-AP-001` | ap | OPEN | Sí — backlog P1-01 |
| `KC-MOC-002` | moc | OPEN | No — solo reabre una nota de `CLAUDE.md` sobre VBA vacío |
| `KC-ITP-003` | 6 módulos ITP-genérico | OPEN (informativo) | No — no afecta a este repositorio |

## 17. Cobertura por módulo

No se publica un porcentaje de "Operational Mapping Coverage" agregado —
ver la nota de metodología completa en `moeve-mapping-backlog.md` § 1
(el numerador exige resolución a nivel de celda que este sprint no
completó para 7 de 9 módulos). Tabla de cobertura real (qué sí puede
afirmarse hoy, por módulo) en ese mismo documento, § 1.1.

## 18. Knowledge backlog

19 ítems: 8 P1 (blocking), 6 P2 (difference), 4 P3 (knowledge gap), 1 P4
(historical). Lista completa con fuente, impacto y acción recomendada en
`docs/07-developer-guide/moeve-mapping-backlog.md` § 2.

## 19. Gaps P1/P2/P3/P4

Ver § 18. Los dos ítems de mayor impacto: **P1-01** (confirmar el alcance
real de la modificación del mapping del eje de AP) y **P1-02**
(autorización para abrir los dos `.zip`, que podrían contener la
evidencia que resuelve P1-01 y otros conflictos).

## 20. Recomendaciones

1. Pedir al cliente/consultor la confirmación de `KC-AP-001` antes de dar
   por buena la carga real de Action Plans en el ámbito ITP-genérico.
2. Decidir explícitamente si se autoriza la extracción de los 2 `.zip`
   — sin esa decisión, el inventario SQL y de mappings de entidad queda
   incompleto por diseño (no por omisión).
3. Priorizar P1-03/P1-04 (Duración y Asistentes de Drills) en la próxima
   sesión — son las dos preguntas heredadas de Sprint 8.1 más cerca de
   cerrarse, y cerrarlas permite ampliar `config/exports/drills.yaml`.
4. No formalizar todavía el inspector Python de ETL como código de
   `src/` (P3-05) — es un script de análisis puntual, no un componente
   del motor; formalizarlo sin un segundo caso de uso sería
   sobre-ingeniería.
5. No generar el resto de `config/knowledge/moeve/<module>/` (8 módulos)
   sin las sesiones dedicadas de P1-05 a P1-08 — generarlos vacíos o por
   inferencia contradiría el principio de no inventar reglas.

## 21. Riesgos

- Los dos `.zip` sin abrir podrían contener información que invalide o
  matice conclusiones de este informe (en particular `KC-AP-001`) — el
  informe es correcto con la evidencia disponible, no necesariamente
  completo.
- La inspección de ETL fue de hoja+cabecera+muestra, no celda-por-celda
  completa — cualquier regla que dependa de una fórmula no capturada en
  las primeras filas de una hoja de datos podría no estar reflejada.

## 22. Archivos creados

```
docs/01-architecture/mapping-governance.md
docs/01-architecture/knowledge-source-governance.md
docs/07-developer-guide/moeve-source-inventory.md
docs/07-developer-guide/moeve-mapping-backlog.md
config/knowledge/moeve/ap/source-inventory.yaml
config/knowledge/moeve/ap/mapping-set.yaml
config/knowledge/moeve/ap/knowledge-conflicts.yaml
config/knowledge/moeve/ap/unresolved-rules.yaml
config/knowledge/moeve/ap/mapping-coverage.yaml
config/knowledge/moeve/ap/mapping-evidence.md
reports/executions/2026-08-12/Informe-Mapping-Governance-Moeve-EMF.md
reports/executions/2026-08-12/Informe-Mapping-Governance-Moeve-EMF.txt
```

## 23. Archivos modificados

Ninguno de código (`src/`, `tests/`, `sql/`). `.claude/settings.local.json`
aparece modificado en `git status` (permisos de herramientas de esta
sesión) — no forma parte de este sprint, no se toca ni se incluye en la
propuesta de commit de § 26.

## 24. Estado de Sprint 8.1

`drills-csv-contract.md`, `knowledge-coverage-matrix.md`,
`knowledge-traceability-matrix.md` (no trackeados en git) siguen
vigentes — no se sobrescriben. Se identificaron 2 preguntas abiertas
(`OQ-ETL-01`, `OQ-ETL-02`) que la evidencia de este sprint acerca a
resolverse pero no cierra (falta lectura de celda completa, no solo
cabecera). Recomendación explícita: no actualizar esos 3 documentos
todavía — ver `moeve-source-inventory.md` § 11 para el detalle completo
y por qué actualizar ahora sería documentar una conclusión a medias.

## 25. Próximo paso

Sesión dedicada a P1-03/P1-04 (lectura de celda completa de
`DuraciónAjustada` y `Asis_concat` en el ETL de Simulacros) — el camino
más corto para cerrar 2 preguntas heredadas y ampliar
`config/exports/drills.yaml` con evidencia real de ETL por primera vez.
En paralelo, decisión del usuario sobre autorización de los 2 `.zip`
(P1-02).

## 26. Propuesta de commits (no ejecutados)

1. **Mapping governance**: `docs/01-architecture/mapping-governance.md`,
   `docs/01-architecture/knowledge-source-governance.md`.
2. **Moeve source inventory / knowledge**:
   `docs/07-developer-guide/moeve-source-inventory.md`,
   `docs/07-developer-guide/moeve-mapping-backlog.md`,
   `config/knowledge/moeve/ap/`.
3. **Código genérico nuevo**: ninguno — el inspector de ETL usado
   quedó en el scratchpad de sesión, no se incorporó al repositorio (ver
   § 20, recomendación 4).
4. **Documentación e informes**: este informe (`.md` + `.txt`).

Ningún dato real del workspace externo se incluye en ninguno de los
commits propuestos — todos los YAML/MD contienen metadata, identidad de
regla y fórmulas tal cual aparecen en el ETL (código, no datos de fila),
nunca contenido de fila real.

## 27. `git diff --check`

Sin salida — 0 problemas de espacio en blanco.

## 28. `git status --short` (antes de cualquier commit de este sprint)

```
 M .claude/settings.local.json
?? config/knowledge/
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-source-governance.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/mapping-governance.md
?? docs/07-developer-guide/moeve-mapping-backlog.md
?? docs/07-developer-guide/moeve-source-inventory.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt
?? reports/executions/2026-08-12/
```

`git diff --stat`: solo `.claude/settings.local.json` (8 inserciones, 1
eliminación) — ajenas a este sprint, ver § 23.

## 29. Tests

`pytest tests/ -v` → **714 passed, 7 skipped** (idéntico antes y después
de este sprint — no se modificó código funcional). No se añadió código
de extracción nuevo al repositorio (§ 20), por lo que no se requieren
tests nuevos conforme a la Fase 20 del encargo ("si se crea código nuevo
de extracción documental, añadir tests" — no se creó).
