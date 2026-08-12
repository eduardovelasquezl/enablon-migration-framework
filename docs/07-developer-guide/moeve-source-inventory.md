# Moeve Source Inventory — Sprint 8.8

**Status:** Implemented (inventario), Sprint 8.8 — Mapping Governance &
Knowledge Consolidation. Construido por inspección de solo lectura de
`EMF_DATA_ROOT/projects/moeve/` (ruta real fuera de este repositorio,
resuelta vía `EMF_DATA_ROOT` — ver `external-data-workspace.md`). No se
ha modificado, movido, renombrado ni recalculado ningún archivo fuente.
No se ha ejecutado SQL Server, macros ni Power Query. Vocabulario y
esquema de identidad: ver `mapping-governance.md`.

Cómo se generó la evidencia estructural de los ETL: un inspector Python
de solo lectura (`openpyxl`, `read_only=True`, `data_only=False` — nunca
evalúa fórmulas), que lee nombre/visibilidad de hoja, dimensiones,
nombres definidos y una muestra acotada de filas (1 fila en hojas de
datos, hasta 8 en hojas identificadas como `mapping-like` por nombre).
Para la detección de conexiones/Power Query/VBA se listó el contenido
interno del contenedor ZIP/OOXML del propio `.xlsx`/`.xlsm` (metadata de
nombres de parte, nunca contenido ejecutado). El script vivió en el
scratchpad de la sesión, no se ha incorporado al repositorio (ver
`moeve-mapping-backlog.md` P3-05 sobre si merece formalizarse).

## 1. Inventario físico

### 1.1 Resumen por categoría

| Categoría (`config/data_workspace.yaml`) | Carpeta real | Archivos | Notas |
|---|---|---:|---|
| `etl` | `ETL/` | 11 | Todos `.xlsx`/`.xlsm`, 21 MB–361 MB |
| `csv_enablon_template` | `CSV_Enablon_Template/` | 14 CSV + 0 | Platform Contract — export completo de Enablon |
| `csv_enablon_operational` | `CSV_Enablon_Operational/` | 30 CSV + 2 XLSX | Project Contract — lo realmente cargado |
| `mappings` | `Mappings/` | 1 CSV + 1 ZIP | `AttachmentsLast.csv` + zip sin abrir |
| `sql` | `SQL/` | 1 ZIP | Sin abrir — ver § 1.4 |
| `errors` | `Errors/` | 1 CSV | 28 tickets, ver § 8 |
| `catalogs`, `evidence`, `outputs`, `archive` | — | 0 | Carpetas vacías, placeholders del manifest de categorías |
| `csv_enablon` (legacy) | `CSV_Enablon/` | 0 | Deprecated, ver `external-data-workspace.md` § 24 |

Total: 61 archivos inventariados, 0 modificados.

### 1.2 ETL — inventario completo

| `source_document_id` | Archivo | Tamaño | Módulo(s) probable(s) | `source_status` |
|---|---|---:|---|---|
| `etl:eventos_antiguos_filtroeje_sitepesr` | `ETL - Eventos Antiguos_FiltroEje_SITEPESR.xlsx` | 63 MB | eventos (submódulo antiguos) | `CURRENT_UNVERIFIED` |
| `etl:ap_gct_new_sitecan` | `ETL- AP_GCT_NEW_SITECAN.xlsx` | 63 MB | ap (origen MOC/GCT) | `CURRENT_UNVERIFIED` |
| `etl:ap_con_ajuste_entidad_new_sietcan` | `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN (1).xlsx` | 361 MB | ap (origen ITP-genérico) | `CURRENT_UNVERIFIED` |
| `etl:eventos_nuevos_full_ajusteeje_sitepser` | `ETL- Eventos nuevos - FULL_AjusteEje_SITEPSER.xlsx` | 65 MB | eventos (submódulo nuevos + PSM) | `CURRENT_UNVERIFIED` |
| `etl:inspeccionesnew_version_formulas_sietcan` | `ETL- InspeccionesNEW (version formulas)_SIETCAN.xlsx` | 201 MB | inspecciones | `CURRENT_UNVERIFIED` |
| `etl:reunionesdegrupo_fixentities_sitecan` | `ETL- Reunionesdegrupo-fixEntities_SITECAN.xlsx` | 21 MB | safety_meetings | `CURRENT_UNVERIFIED` |
| `etl:bcm_simulacros_updateeje_sitecan` | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` | 29 MB | simulacros | `CURRENT_UNVERIFIED` |
| `etl:bypass_ajusteentidadnew_sitecan` | `ETL_Bypass_AjusteEntidadNEW_SITECAN.xlsx` | 29 MB | bypass | `CURRENT_UNVERIFIED` |
| `etl:moc_m_new_sitecan` | `ETL_MOC_m_NEW_SITECAN.xlsm` | 52 MB | moc | `HISTORICAL` (ver § 4.2) |
| `etl:moc_newcolumns` | `ETL_MOC_NewColumns.xlsm` | 53 MB | moc | `CURRENT_UNVERIFIED` (ver § 4.2) |
| `etl:ops_arregloentidad_sietcan` | `ETL_OPS_ArregloEntidad_SIETCAN.xlsx` | 201 MB | ops | `CURRENT_UNVERIFIED` |

Ninguno se marca `CURRENT_VERIFIED` en este sprint: la inspección
estructural (hoja+cabecera+muestra) sin confirmación humana ni ejecución
real es, por `mapping-governance.md` § 2, evidencia de nivel 4 o 8 según
el caso — nunca suficiente por sí sola para ese estado (ver
`knowledge-source-governance.md` § 2.6).

### 1.3 CSV — inventario completo

Ver § 6 (Template vs Operational) para el detalle columna por columna.
Conteo por categoría: 14 Template + 30 Operational (CSV) + 2 Operational
(`.xlsx`: `Inspection_Data_06082026_PT_4_pestanas.xlsx`, `Simulacros
CCE.xlsx` — no inventariados a nivel de columna en este sprint, quedan
`OTHER`/pendiente, ver backlog P3-06).

### 1.4 Los dos `.zip` — inspeccionados en Sprint 8.8.1

| Archivo | Tamaño | Ubicación | SHA-256 | Entradas | Estado |
|---|---:|---|---|---:|---|
| `OneDrive_2_12-8-2026.zip` | 2.3 MB | `Mappings/` | `4e0d5a8e3d1b75be9ce9e7efdf06b3f053fa38f77e79db3322eac3066f12c01c` | 10 | Inspeccionado (Sprint 8.8.1) |
| `OneDrive_1_12-8-2026.zip` | 88 KB | `SQL/` | `8d8e214f20a8dff3df0c89464b5da6d2e3a879fb53829c0fc5780d6c57b15438` | 43 | Inspeccionado (Sprint 8.8.1) |

Sprint 8.8 dejó ambos sin abrir (prohibido sin autorización explícita,
no solicitada). Sprint 8.8.1 recibió esa autorización — extracción de
solo lectura a una carpeta temporal fuera del repositorio y de las
carpetas fuente originales, `testzip()` verificado sin entradas
corruptas antes y después, copia temporal eliminada al finalizar. Ver
`mapping-governance.md` § 12.1 (mappings) y § 12.4 (SQL) para el
resultado completo. Resumen: el SQL zip es 100% duplicado byte-a-byte
del repositorio (0 hallazgos nuevos de query); el Mappings zip aportó
evidencia sustancial nueva — el motor real del ETL (Office Script, no
VBA) y los workbooks dedicados de mapeo de eje ITP/GCT.

## 2. Clasificación por módulo (Fase 2)

| `module_id` | ETL | CSV Template | CSV Operational | `fuente_sistema` (`config/modules.yaml`) |
|---|---|---|---|---|
| `simulacros` | 1 | Drills-34, List of Activities-38 | Simulacros CCE.xlsx | prevencion |
| `safety_meetings` | 1 | Group Meetings-40, Update External Meeting Participations-42 | Asistentes_ReunionesGrupo, Reuniones de grupo import completo | prevencion |
| `moc` | 2 | Change Register-17, Checklists Data-24 | ChecklistsData_MoC, MoC-CR-CCE-NoExistentesEnProd | gct |
| `bypass` | 1 | — (sin Template en este workspace) | By pass new .bak | prevencion |
| `eventos` (+ impactos, investigaciones, PSM) | 2 | Events-4, Impact Injuries-26, Impacts-9, Investigations-11, Causes Data-64, PSM forms-13 | Events×4, Impact Injuries-05082026-136, Impacts×2, Investigations×2, PSM forms-14052026-135, RespuestasPSM | prevencion |
| `ops` | 1 | — (sin Template en este workspace) | JSO-11052026-30 | prevencion |
| `inspecciones` (+ observaciones) | 1 | Inspection Data-58, Inspections-51, Observations-60 | Inspection Data×3, Inspections×3, Observations×3, Inspection_Data...xlsx | prevencion |
| `ap` | 2 | — (sin Template en este workspace) | Action Plans×3 | prevencion + gct |

**Gap de evidencia (no un hallazgo de mapping, un hallazgo de
inventario):** `bypass`, `ops` y `ap` no tienen ningún CSV Template
(Platform Contract) en este workspace — solo Operational. La comparación
Template-vs-Operational de la Fase 6 del encargo, por tanto, **no puede
hacerse** para esos tres módulos con lo disponible hoy; el Project
Contract de esos tres se construye solo a partir de Operational (§ 6.2).

## 3. Sheet taxonomy — patrón confirmado por ETL (Fase 4)

| ETL (`source_document_id`, abreviado) | # hojas | `Entidades_Mapeo` (estático) | `MapeoEje_uorg`/`Exportación eje`/`Niveles` (catálogo vivo) | `MAP-ITPOLD-EVT/IMP/MED/MED-2` huérfanas | VBA (`vbaProject.bin`) | Conexiones/Power Query |
|---|---:|:---:|:---:|:---:|:---:|---:|
| `ap_con_ajuste_entidad` | 72 | ✅ | — | ✅ (4 ocultas) | — | 15 queryTables |
| `ap_gct` | 52 | — | ✅ (ambas) | ✅ (4 ocultas) | — | 11 queryTables + 1 externalLink |
| `eventos_antiguos` | 71 | ✅ | — | ✅ (4 ocultas, + variantes propias `MAP-ITPOLD-EVT-PCO/ICO`) | — | 0 (sin `connections.xml`) |
| `eventos_nuevos` | 112 | ✅ | ✅ (solo `MapeoEje_uorg`, sin `Exportación eje` propia) | ✅ (4 ocultas) | — | 14 queryTables + 2 externalLinks |
| `inspecciones` | 85 | ✅ | — | ✅ (4 ocultas) | — | 12 queryTables |
| `safety_meetings` | 40 | ✅ | — | ✅ (4 ocultas) | — | 5 queryTables |
| `simulacros` | 50 | ✅ | — | — (no aplica, módulo sin forma de evento) | — | 6 queryTables |
| `bypass` | 31 | ✅ | — | — | — | 2 queryTables |
| `ops` | 62 | ✅ | — | — | — | 7 queryTables |
| `moc_m_new` | 80 | — | ✅ (`Niveles` + `Exportación eje`) | — | ✅ | 14 queryTables |
| `moc_newcolumns` | 80 | — | ✅ (`Niveles` + `Exportación eje`) | — | ✅ | 14 queryTables + 1 externalLink |

**Lectura de la tabla — 3 hallazgos que no estaban en `CLAUDE.md`:**

1. **El patrón de hojas huérfanas `MAP-ITPOLD-*` aparece en 6 de los 11
   ETL** (`ap_con_ajuste_entidad`, `ap_gct`, `eventos_antiguos`,
   `eventos_nuevos`, `inspecciones`, `safety_meetings`) — confirma y
   acota la afirmación de `CLAUDE.md` ("aparecen sin uso en 7 de 7
   libros con checklists/eventos auditados"; el denominador de aquella
   afirmación era un subconjunto más estrecho). No aparecen en `bypass`,
   `ops`, `simulacros` ni en ninguno de los dos MOC.
2. **El mecanismo de catálogo vivo (`MapeoEje_uorg`/`Exportación eje`/
   `Niveles`) no es exclusivo de AP** — está en `ap_gct`, en ambos ETL
   de `moc` y parcialmente en `eventos_nuevos`. Es decir: es un patrón de
   modernización que avanzó primero en los módulos de origen GCT (MOC,
   AP-GCT) y llegó parcialmente a Eventos Nuevos, pero **no** a
   Simulacros, Safety Meetings, Bypass, Inspecciones, OPS ni a la parte
   ITP-genérica de AP — los 7 restantes siguen con `Entidades_Mapeo`
   estático como único mecanismo visible. Esto generaliza el
   `KNOWLEDGE_CONFLICT KC-AP-001` de `mapping-governance.md` § 7 a un
   patrón de proyecto, no un caso aislado — ver backlog P1-01.
3. **Los dos `.xlsm` de MOC son los únicos con `vbaProject.bin`
   presente** — ver `mapping-governance.md` § 8 (`KC-MOC-002`).

## 4. Versionado de ETL (Fase 3)

### 4.1 Action Plans — ver `mapping-governance.md` § 7 (caso obligatorio)

### 4.2 MOC — dos `.xlsm` con idéntica estructura de 80 hojas

| Documento | `mtime` | Hojas | Estado |
|---|---|---:|---|
| `ETL_MOC_m_NEW_SITECAN.xlsm` | 2026-07-28 | 80 | `HISTORICAL` — anterior por fecha, mismo esqueleto |
| `ETL_MOC_NewColumns.xlsm` | 2026-08-11 | 80 (mismos nombres, mismo orden) | `CURRENT_UNVERIFIED` — posterior por fecha; el nombre ("NewColumns") es coherente con una revisión que añade columnas sin rehacer hojas |

Sin diferencia de **nombres** de hoja entre ambos con esta inspección —
confirmar diferencia de **columnas dentro de las mismas hojas** requiere
una comparación dedicada (backlog P2-03). No se asume qué columnas se
añadieron sin verificarlo.

## 5. Catálogo de reglas observadas (Fase 5)

Ver `mapping-governance.md` § 6 para la tabla completa con evidencia. Dos
patrones de hoja de regla confirmados en múltiples ETL:

- **Patrón A** (`CampoOrigen | Field Destiny XML | Field Destiny ES |
  Adaptación | Transformation From | ... | XML | ES`): hojas `MAP-*`.
- **Patrón B** (`DatoOrigen | DatoDestino | EsCondicion | ReglaEspecial |
  Parametro`): hojas `Mapeo_*`/`Map_*`, incluida `MapeoEje_uorg`.

Ambos coinciden exactamente con los dos patrones ya documentados en
`CLAUDE.md`.

## 6. CSV Template vs. CSV Operational (Fase 6)

Comparación de **estructura únicamente** (cabeceras, orden, encoding) —
ningún dato de fila se ha copiado a este documento ni al repositorio.

### 6.1 Encoding observado (relevante para cualquier motor de exportación)

| Origen | Encoding | Delimitador |
|---|---|---|
| CSV Template (todos) | `UTF-16` (con BOM) | Tab (`\t`) |
| CSV Operational — mayoría | `UTF-8` (con BOM) | `;` |
| CSV Operational — algunos (Events×4 antiguos, Investigations-03082026, JSO, Group Meetings) | `UTF-16` | Tab |
| CSV Operational — 2 casos (`By pass new .bak.csv`, `Update External Meeting Participations-42.csv` está en Template no Operational — ver nota) | `latin-1` | `;` |
| `AttachmentsLast.csv` | `UTF-8` (sin BOM) | `;` |

No hay un encoding único para "Operational" — varía por export individual,
no por módulo. Cualquier lector debe detectar encoding por archivo, no
asumirlo por categoría (ver backlog P2-04).

### 6.2 Comparación por módulo

| Módulo | Template (cols) | Operational (cols, por export) | Columnas exclusivas Template relevantes | Columnas exclusivas Operational relevantes |
|---|---|---|---|---|
| `simulacros` | Drills-34: 36 | (Simulacros CCE.xlsx sin inventariar, P3-06) | — | — |
| `safety_meetings` | Group Meetings-40: 26; Update External...-42: 6 | Asistentes_ReunionesGrupo: 4; Reuniones de grupo: 22 | `CS_Scope`, `CS_MeetingPlace`, `ProcessHazardAnalysis` presentes en Template y en el Operational completo | El Operational trae una columna vacía sin nombre entre `CS_HistoricalOriginID` y `CS_HistoricalUserId` (ver § 6.3) |
| `moc` | Change Register-17: 106 | ChecklistsData_MoC: 6; MoC-CR-CCE-NoExistentesEnProd: 61 | 45 columnas del Template no aparecen en el export Operational muestreado (`CS_MotivatedBy`, `CS_EnvlImpact`, checklist-related, etc.) — coherente con que el Operational es un **subconjunto real usado**, no el Platform Contract completo (ver `project-contract-model.md` § 2.2) | — |
| `eventos` | Events-4: 71; Impacts-9: 92; Investigations-11: 33; Impact Injuries-26: 5; Causes Data-64: 9; PSM forms-13: 8 | 12 exports distintos, 1–43 columnas cada uno (ver § 6.4) | Numerosas — el Template es un superset amplio | `CS_HistImpactID`/`CS_HistImpactIDOH` (Impacts) presentes en Operational y Template |
| `inspecciones` | Inspection Data-58: 19; Inspections-51: 47; Observations-60: 10 | 9 exports, 3–24 columnas | Numerosas | — |
| `bypass` | — | By pass new .bak: 24 (latin-1, ver § 6.5) | N/A (sin Template) | N/A |
| `ops` | — | JSO-11052026-30: 26 | N/A | N/A |
| `ap` | — | 3 exports: 33 / 31 / 31 columnas, **distintos entre sí** (ver § 6.6) | N/A | N/A |

### 6.3 Anomalía puntual — columna sin nombre en Safety Meetings Operational

`Reuniones de grupo import completo.csv` trae una columna vacía (`""`)
en la posición 19 de 22, entre `CS_HistoricalOriginID` y
`CS_HistoricalUserId`. No se interpreta su propósito — se registra como
`UNRESOLVED_RULE`, backlog P2-05.

### 6.4 Eventos — 12 exports Operational con forma muy distinta entre sí

`Events-05082026-30.csv` tiene **solo 2 columnas** (`Historical Event
ID`, `Id`) — no es un export de evento completo, es una tabla de
reconciliación id-histórico↔id-Enablon. Esto es coherente con el patrón
de duplicados ya documentado en `CLAUDE.md` (585 eventos duplicados) y
sugiere que este export concreto pudo generarse como parte de un trabajo
de deduplicación, no como carga. Se registra como `EVIDENCE`, no como
`CSV_OPERATIONAL` de carga, backlog P4-01 (valor de auditoría, no
bloqueante).

### 6.5 Bypass Operational — confirma campos no importables ya documentados

`By pass new .bak.csv` (24+ columnas, lista truncada en la inspección de
cabecera) incluye `GOS`, coherente con `config/modules.yaml` (`GOS:
"calculado automáticamente por Enablon al asociar documento — NO
importable"`). No incluye `FechaEnvioFase1..6` en las columnas
capturadas — coherente también con la lista de `campos_no_importables_confirmados`
ya documentada.

### 6.6 Action Plans Operational — tres exports con contrato distinto

| Export | Columnas | Diferencia notable |
|---|---:|---|
| `Action Plans-10082026-163.csv` | 33 | Incluye `CS_IndependentManualEvents`, `AbandonedDate`, `CS_CancellationReason` |
| `Action Plans-10082026_2.csv` | 31 | Incluye `RelatedDocuments`, sin `AbandonedDate` |
| `Action Plans-10082026_3.csv` | 31 | Incluye `ACSObservation`, `CS_IP` (en vez de `CS_IndependentManualEvents`) |

Consistente con el hallazgo de `mapping-governance.md` § 7: AP no es un
único Project Contract, son al menos 3 variantes por submódulo de
origen. No se asume cuál corresponde a cuál `idorigenac` sin
confirmarlo — backlog P2-06.

## 7. Mappings de entidades (Fase 9) — incluye caso ITP

Fuente de verdad ya fijada por `CLAUDE.md`: `inputs/entity_catalog/`
(export real `First_Axis`). Este sprint no reabre esa decisión — la
confirma y la matiza:

- El patrón `ruta / Parent / Code / EntityEN / ... / EntityStatus` de
  `First_Axis` es **el mismo patrón exacto** encontrado en las hojas
  `Exportación eje` de `ap_gct`, `moc_m_new` y `moc_newcolumns` — esos
  ETL ya llevan embebida una copia (a fecha de export del ETL) del mismo
  catálogo vigente, no una copia divergente.
- `Entidades_Mapeo`, presente en 8 de los 11 ETL, sigue siendo el
  mecanismo estático deprecado que `CLAUDE.md` ya identificó — este
  sprint no encontró ningún ETL adicional que lo sustituyera fuera de
  los ya señalados en § 3.

**`KNOWLEDGE_CONFLICT` (caso ITP, Fase 9 explícitamente pedida por el
encargo):** el mapping de entidades "vigente" para el sistema ITP (7 de
9 módulos) sigue siendo, según la evidencia de ETL de este sprint,
`Entidades_Mapeo` estático dentro de cada libro — **no** el mecanismo de
catálogo vivo que sí adoptaron MOC y AP-GCT. Esto no contradice la
decisión ya tomada sobre `inputs/entity_catalog/` como fuente de verdad
para *este repositorio* (que ya resuelve el problema mejor que
`Entidades_Mapeo`), pero sí confirma que, **dentro de los ETL originales
del cliente**, la modernización del mapeo de eje es parcial y
desigual entre sistemas de origen (GCT modernizado, ITP-genérico no). Se
registra como `KC-ITP-003`:

```yaml
conflict_id: KC-ITP-003
module_id: [simulacros, safety_meetings, bypass, eventos, inspecciones, ops]
rule_id_or_field: entity_axis_resolution
source_a:
  source_document_id: "inputs/entity_catalog/catalogo_resuelto_code_ruta_site.csv"
  summary: "Fuente de verdad ya fijada en este repositorio (CLAUDE.md), resuelve 0% no catalogado en SM/MOC/Bypass."
source_b:
  source_document_id: "etl:* (8 ETL con hoja Entidades_Mapeo)"
  summary: "El ETL original del cliente para estos 6 módulos nunca migró al mecanismo de catálogo vivo que sí tienen MOC y AP-GCT."
impact: >
  Ninguno sobre este repositorio (ya usa la fuente correcta). Sí es
  relevante como antecedente de por qué el Hallazgo #1
  (infra-migración La Rábida/Palos) pudo originarse en el ETL del
  cliente: 6 de 9 módulos dependían de un catálogo que el propio cliente
  ya había dejado de actualizar en al menos 2 módulos (MOC, AP-GCT) para
  el momento de este export.
recommendation: >
  Ninguna acción sobre este repositorio. Sí vale la pena que el cliente
  sepa que la inconsistencia no fue puntual de un módulo — fue
  estructural entre familias de ETL (GCT modernizó su mapeo de eje,
  ITP-genérico no).
human_review_required: false
status: OPEN (informativo, no bloqueante)
```

**Actualización Sprint 8.8.1:** la inspección autorizada de
`Mappings/OneDrive_2_12-8-2026.zip` matiza esta conclusión — ver
`mapping-governance.md` § 12.1. El sistema ITP **sí tuvo** un esfuerzo de
mapeo de eje dedicado y versionado ("Mapeo ITP primer eje enablon...
version 4, final1"), tan real como el de GCT, con un catálogo vivo
propio (`Eje final 2`, 3038 filas) y mapeos revisados por site
(incluidos `MCPF`/`MC-Palos de la Frontera` y `Site Canarias`, ambos del
Hallazgo #1). Se confirmó, comparando contenido real de fila (no
fórmula), que `Entidades_Mapeo` (embebido en 8 de los 11 ETL) es una
**instantánea de valores** de la hoja `MAPEOFINAL` de ese workbook — no
un fragmento inconexo. La modernización de GCT no fue "ITP se quedó sin
mapear"; fue "ambos sistemas tuvieron un mapeo dedicado, pero solo GCT
adoptó un mecanismo que se re-sincroniza en cada build del ETL en vez de
quedar congelado en una entrega puntual". `KC-ITP-003` se mantiene
`OPEN` (informativo) con esta caracterización más precisa.

## 8. Documento de Attachments (Fase 10)

`Mappings/AttachmentsLast.csv` (31 MB, `UTF-8` sin BOM, `;`) — cabecera:
`Ruta; Centro; Tipo de Informe; TipoNombre; Idinforme; IdSharpoint;
Nombre de fichero; WebUrl; Visible` (9 columnas).

**Esto no es un mapping de entidades ni pertenece solo a Drills.** Es
estructuralmente idéntico al patrón de hoja `TablaAdjuntos` /
`AdjuntosSITECANARIAS` / `AdjuntosGCT` / `TablaAdjuntosCCE` que aparece
embebido en **8 de los 11 ETL** (todos excepto `moc_newcolumns` —
aunque `moc_m_new` sí lo tiene vía `AdjuntosGCT1/2/3` — y `ap_gct` que
usa `AdjuntosGCT` en singular). Es decir: es el **catálogo consolidado y
más reciente** de referencias a adjuntos en SharePoint (`Ruta` es una
ruta `/drives/b!.../root:`, `WebUrl` un enlace directo) usado
transversalmente por todos los módulos que cargan adjuntos, no un
mapping 1:1 de un objeto.

`Centro` es un código numérico — dado que este archivo es transversal a
módulos de origen ITP y GCT, **no puede asumirse qué numeración de
`IDCentro` usa sin cruzarlo módulo a módulo** (ver `CLAUDE.md`: los dos
sistemas usan numeraciones incompatibles). Se marca `UNRESOLVED_RULE`,
backlog P2-07.

Requisito de carga que el EMF hoy no soporta: ninguno de los módulos
implementados (`src/export/prototype/drills/`) genera ni resuelve
columnas de adjunto (`CS_HistoricalAttachedFiles`, `Attachment`,
`Documents`) — confirma la exclusión ya documentada en
`drills-csv-contract.md` § 3, ahora con evidencia de que el mecanismo
real (`WebUrl` + `SUBTOTAL(103,...)` como fórmula de conteo visible,
vista en `TablaAdjuntos` de Safety Meetings) sí existe en el ETL, solo
no está implementado en código.

## 9. SQL Inventory ampliado (Fase 11)

### 9.1 Queries versionadas en el repositorio

Ya inventariadas por módulo en `sql/source_queries/` (48 ficheros `.sql`,
9 subcarpetas por módulo — sin cambios en este sprint).

### 9.2 Queries en `EMF_DATA_ROOT/projects/moeve/SQL` — reconciliado (Sprint 8.8.1)

`OneDrive_1_12-8-2026.zip` (88 KB, 43 entradas) inspeccionado y
comparado archivo por archivo (nombre + SHA-256 de contenido) contra
`sql/source_queries/`: **43 de 43 son `SQL_DUPLICATE`** (contenido
idéntico), 0 `SQL_VARIANT`, 0 `SQL_ONLY_IN_ZIP`, 0
`SQL_ONLY_IN_REPOSITORY`, 0 `SQL_CONFLICT`. Ver `mapping-governance.md`
§ 12.4 para la tabla completa y el hallazgo cosmético de 2 nombres de
archivo con mojibake en el repositorio (contenido idéntico, solo el
nombre de archivo en disco está mal codificado).

### 9.3 Conexiones/Power Query dentro de los ETL

10 de 11 ETL tienen `connections.xml` interno (solo
`eventos_antiguos` no). Se inspeccionó el contenido de texto (estático,
sin ejecutar) de `xl/connections.xml` en `eventos_nuevos` — las
conexiones encontradas son **de tabla a tabla dentro del mismo libro**
(`Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;
Location=DB-ITP-EVT-00;...`, `command="SELECT * FROM [DB-ITP-EVT-00]"`)
— es decir, Power Query interno para encadenar hojas, **no** una
conexión viva a SQL Server ni una query de extracción original distinta
de las ya versionadas en `sql/source_queries/`. No se detectó
`SQL_ONLY_IN_ETL` con contenido de extracción nuevo en la muestra
inspeccionada (1 de 11 ETL con contenido de texto real leído — el resto
solo se verificó por presencia de la parte, no por contenido, backlog
P3-07).

### 9.4 Clasificación

| Categoría | Resultado |
|---|---|
| `SQL_DUPLICATE` | No evaluado — requiere abrir `SQL/OneDrive_1_12-8-2026.zip` |
| `SQL_VARIANT` | No evaluado |
| `SQL_ONLY_IN_ETL` | Ninguno confirmado con contenido real (solo conexiones internas tabla-a-tabla, § 9.3) |
| `SQL_ONLY_IN_REPOSITORY` | Los 48 `.sql` de `sql/source_queries/`, por defecto, hasta poder comparar contra el zip |
| `SQL_CONFLICT` | Ninguno detectado |

## 10. Errors — clasificación de conocimiento (Fase 12)

`Errors/Requests-12082026-28.csv` — 28 filas, `UTF-16`, tab-delimited.
Columnas: `Module, Environment, Service, URL, Title, Type, Description,
VirtualFiles, ProductionNeedsToBeUpdated`.

Muestra inspeccionada (3 primeras filas, sin copiar el resto a este
documento):

| `Module` (tal cual en el CSV) | `Title` | `Type` | Clasificación |
|---|---|---|---|
| Inspection Management | Faltan Inspecciones en Producción | Incidence | `MIGRATION_RELATED` — coincide con gap ya documentado en `config/modules.yaml` (inspecciones, -48.4%) |
| Behaviour Based Safety | Simulacros | Incidence | `MIGRATION_RELATED`, pero **`Module` mal etiquetado** — el contenido describe Simulacros (participantes históricos, tipología), no OPS/BBS. Confirma el patrón ya conocido de incidencias mal categorizadas (`CLAUDE.md`: "107 categorizados... el resto sin etiquetar") |
| Shared Functions | Campos "Creado por" y "Persona responsable" | Help Request | `PROBABLY_MIGRATION_RELATED` — pregunta funcional sobre correspondencia de campos, no un defecto de datos |

No se clasifican las 25 filas restantes en este documento sin
inspeccionarlas individualmente (evitar clasificación automática en
lote, prohibida por el encargo) — backlog P2-08 para completar la
clasificación de las 28 filas una por una.

## 11. Estado de los documentos Sprint 8.1

`docs/01-architecture/drills-csv-contract.md`,
`knowledge-coverage-matrix.md`, `knowledge-traceability-matrix.md`
(no trackeados en git) siguen **vigentes como auditoría de lo que el
código sabía sin ETL** — no se sobrescriben. Este sprint aporta evidencia
real de ETL que **no estaba disponible** cuando se escribieron y que
permite avanzar (no cerrar) algunas de sus preguntas abiertas:

| Pregunta abierta (Sprint 8.1) | Evidencia nueva (Sprint 8.8) | Estado tras Sprint 8.8.1 |
|---|---|---|
| `OQ-ETL-02` (`CS_Duration`, recombinación de meses/días/horas/minutos) | Hoja `CalculoHorasDiasMinutos` confirmada real en el ETL de Simulacros; fórmula truncada a 200 caracteres en la muestra de 8.8 | **`RESOLVED`** — lectura completa (Sprint 8.8.1): `CS_Duration` es passthrough directo de `Duracion` (`Adaptación=No`), sin recombinación. `CalculoHorasDiasMinutos` alimenta un objeto distinto (`List of Activities`), no Drills. Ver `mapping-governance.md` § 12.3 |
| `OQ-ETL-01` (`CS_HistoricalDrillAttendees`, lógica de `Asis_concat`) | Confirmado que la hoja `Asis_concat` existe realmente, solo cabecera capturada | **`RESOLVED`** — lectura completa (Sprint 8.8.1): 2 mecanismos al mismo destino, passthrough de `Asistentes` + concatenación de `NombreAsistente` vía `Asis_concat`/regla `concat`. Ver `mapping-governance.md` § 12.3 |
| Mecanismo de `NameEN/FR/ES/ZH/BR` (Drills) | Hoja `Mapeo_Titulo` (Simulacros) confirma `titlefix` + `cloneorigin` en la misma fila de regla | **Parcial, sin cambio en 8.8.1** — mecanismo 🟢, origen SQL exacto de "Título" sigue 🔴. El motor real (`Script ETL.txt`, Sprint 8.8.1) confirma el comportamiento exacto de `titlefix` (§ 6 de `mapping-governance.md`) pero no aporta el nombre de columna SQL origen |
| `CS_HistoricalDataOrigin` cita cruzada con `cs_historicaluserid` (`knowledge-traceability-matrix.md` fila 🟡) | No investigado | Sin cambio |

**Actualización:** `knowledge-traceability-matrix.md` **sí se actualizó**
en Sprint 8.8.1 (filas `CS_Duration` y `CS_HistoricalDrillAttendees`,
🟡→🟢) — la recomendación de Sprint 8.8 de esperar a tener evidencia
completa se cumplió: la lectura sin truncar de las celdas relevantes
cerró ambas preguntas con evidencia concluyente, no con un estado a
medias. `drills-csv-contract.md` **no** se actualizó — su alcance (qué
columnas implementa el motor) no cambia solo por resolver de dónde viene
el conocimiento; implementar `CS_Duration`/`CS_HistoricalDrillAttendees`
en `config/exports/drills.yaml` sigue siendo trabajo de código pendiente
(ver `moeve-mapping-backlog.md`), ahora sin bloqueo de conocimiento.

`docs/01-architecture/knowledge-coverage-matrix.md` no requiere cambio —
su alcance (código/config, no ETL) no se ve afectado por este sprint.

## 12. Sprint 8.9 — C003 como fuente adicional (Action Plans)

C003 (herramienta nativa de reemplazo del ETL de Action Plans, ajena a
este repositorio y a `EMF_DATA_ROOT`) se registró como fuente histórica
externa — ver `docs/07-developer-guide/c003-knowledge-adoption.md` para
el registro completo y las 30 reglas reconstruidas, y
`docs/01-architecture/action-plans-native-design.md` para el diseño
resultante del futuro Adaptador AP. Resume aquí solo el impacto sobre
este inventario:

- **Backlog P2-06 cerrado**: `cfg.ActionPlanFlowOrigin` de C003 da el
  mapeo completo `idorigenac` → `Sources`/columna de enlace de padre
  para los 8 flujos de AP, coincide con `config/modules.yaml` y añade
  `HAZOPS=6` (no documentado antes).
- **`KC-AP-001`** (§ 7 de este documento): tercera confirmación
  independiente de que `Entidades_Mapeo` es una fuente real y
  deliberada — C003 la extrae explícitamente por nombre de hoja del
  mismo Excel legado. No cierra el conflicto.
- **Ningún dato real de C003** (`runs/`, CSV de configuración) se copió
  a este repositorio.
