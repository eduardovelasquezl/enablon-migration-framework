# Moeve Mapping Backlog — Sprint 8.8 (actualizado en Sprint 8.8.1)

**Status:** Implemented, actualizado en Sprint 8.8.1 (Knowledge
Closure). Deriva de `moeve-source-inventory.md` y `mapping-governance.md`.
Metodología de cobertura (§ 1) y backlog priorizado P1–P4 (§ 2). Los
ítems no mencionados en § 0 no cambiaron respecto a Sprint 8.8 — no se
ha rehecho el backlog completo, solo se actualizaron los ítems con
evidencia nueva.

## 0. Registro de cambios (Sprint 8.8 → 8.8.1)

| ID | Estado anterior | Estado nuevo | Evidencia | Motivo |
|---|---|---|---|---|
| P1-02 | `OPEN` — 2 zip sin abrir, pendiente de autorización | **`RESOLVED`** | `mapping-governance.md` § 12.1, § 12.4 | Autorización recibida en el encargo de Sprint 8.8.1; ambos zip inspeccionados, hasheados, inventariados y reconciliados |
| P1-03 | `OPEN` — fórmula `DuraciónAjustada` truncada a 200 caracteres | **`RESOLVED`** | `mapping-governance.md` § 12.3 | Lectura completa sin truncar: `CS_Duration` = passthrough directo de `Duracion`, sin recombinación |
| P1-04 | `OPEN` — hoja `Asis_concat` sin contenido capturado | **`RESOLVED`** | `mapping-governance.md` § 12.3 | Lectura completa: 2 mecanismos (passthrough + concat) resueltos y documentados |
| P1-01 | `OPEN` — sin caracterizar más allá de la discrepancia estructural | `OPEN`, **mejor caracterizado, no cerrado** | `mapping-governance.md` § 12.1, `config/knowledge/moeve/ap/knowledge-conflicts.yaml` (`status_note_8_8_1`) | Se encontró el origen documental real de `Entidades_Mapeo` (instantánea de `MAPEOFINAL` del workbook ITP "version 4") — sigue sin confirmarse si los ETL ITP-genérico se resincronizaron después de esa versión |
| P3-08 | `OPEN` — matiz de `cloneorigin` con lookup sin explicar | **`RESOLVED`** | `mapping-governance.md` § 6 (tabla actualizada), `config/knowledge/moeve/ap/mapping-set.yaml` | Código fuente real del motor (`Script ETL.txt`) confirma que `cloneorigin` no es un `ReglaEspecial` — es un literal en la celda de referencia; el `BUSCARX` es la resolución normal de la fila de match |
| P3-01 | `OPEN` — mecanismo de `replaceinreference`/`boolorigin` totalmente desconocido | `OPEN`, **downgrade** (mecanismo conocido, uso en Moeve sin confirmar) | `mapping-governance.md` § 6 | Ambas reglas confirmadas con código real; ninguna hoja de Moeve inspeccionada las usa por nombre todavía |
| (nuevo) `KC-MOC-002` | `OPEN` — VBA vs. motor real sin resolver | **`RESOLVED`** | `mapping-governance.md` § 8, § 12.2 | El motor real es un Office Script (`Script ETL.txt`), no VBA — confirmado con código fuente completo, no con inferencia |

Detalle completo de cada resolución en `mapping-governance.md` § 12. Las
tablas de § 1.1 y § 2 de este documento ya reflejan los estados nuevos.

## 1. Metodología de cobertura ("Operational Mapping Coverage")

Definición fijada por el encargo:

```
Operational Mapping Coverage =
    campos importables del Project Contract con mapping o justificación válida
    / campos importables totales del Project Contract
```

No cuentan como gap de mapping los campos `SYSTEM`, `ENABLON_AUTOMATIC`,
`ENABLON_CALCULATED` ni `NON_IMPORTABLE` (ver `mapping-governance.md`
§ 3.1, `rule_type`).

**Por qué este sprint no publica un porcentaje por módulo:** calcular el
numerador exige, por campo, saber si tiene mapping/justificación válida
— es decir, haber cerrado la Fase 5 (identidad de regla) para cada
columna del Project Contract de cada módulo. Este sprint llegó a nivel de
**hoja** (qué hoja de regla existe, qué patrón usa) para los 11 ETL, pero
no a nivel de **celda** (qué regla exacta resuelve cada columna) más que
para los dos casos obligatorios del encargo (AP, MOC) y las dos preguntas
heredadas de Drills (`OQ-ETL-01`/`02`). Publicar un porcentaje agregado
hoy —por ejemplo, dividiendo cuántas columnas del Operational Simulacros
ya están implementadas en `config/exports/drills.yaml` (8) entre las 36
reales— reutilizaría el número ya publicado en
`knowledge-coverage-matrix.md`, sin metodología nueva, y para los otros 8
módulos el numerador sería en la práctica cero (nada implementado
todavía en código fuera de Drills) — un porcentaje que confundiría "no
implementado en el motor" con "sin mapping conocido", que no es lo mismo
(el mapping sí se conoce a nivel de patrón de hoja para la mayoría). Se
prefiere no publicar un número que necesite esta nota tan larga para no
malinterpretarse — la cobertura real, honesta, es la tabla de § 1.1.

### 1.1 Cobertura real, por lo que sí puede afirmarse hoy

| Módulo | Project Contract identificado (Operational, § 6.2 del inventario) | Mecanismo de mapeo de eje | Reglas de campo confirmadas con evidencia de celda | Motor EMF implementado |
|---|---|---|---|---|
| `simulacros` | Sí (Drills-34, aunque el Operational `.xlsx` no se inventarió columna a columna) | `Entidades_Mapeo`, instantánea confirmada de `mapping:mapeo_itp_primer_eje_v4` (Sprint 8.8.1) | 10 de 36 columnas reales (8 de `config/exports/drills.yaml` + `CS_Duration`/`CS_HistoricalDrillAttendees` resueltos en Sprint 8.8.1, aún no implementados en código) | Sí (prototipo) |
| `safety_meetings` | Sí | `Entidades_Mapeo`, misma procedencia | 0 confirmadas a nivel de celda este sprint (patrón de hoja sí) | No |
| `moc` | Sí | Catálogo vivo (`Niveles`+`Exportación eje`) — 2 versiones ETL, ver § 2 P2-03 | 1 (`titlefix`, ya confirmado en Sprint anterior) | No |
| `bypass` | Sí (sin Template) | `Entidades_Mapeo`, misma procedencia | 0 confirmadas a nivel de celda este sprint | No |
| `eventos` | Sí (12 exports distintos) | `Entidades_Mapeo` + parcialmente catálogo vivo (`eventos_nuevos`) | 0 confirmadas a nivel de celda este sprint | No |
| `ops` | Sí (sin Template) | `Entidades_Mapeo`, misma procedencia | 0 confirmadas a nivel de celda este sprint | No |
| `inspecciones` | Sí | `Entidades_Mapeo`, misma procedencia | 0 confirmadas a nivel de celda este sprint | No |
| `ap` | Sí (3 variantes, sin Template) | Mixto — ver `KC-AP-001` (mejor caracterizado, no cerrado en 8.8.1) | 1 (`ap.user_clone_with_lookup`, resuelto en Sprint 8.8.1) | No |

"0 confirmadas a nivel de celda este sprint" no significa "sin mapping" —
significa que la hoja de regla (`MAP-*`/`Mapeo_*`) se localizó y su
**patrón** se confirmó (§ 5 del inventario), pero no se leyó celda por
celda contra cada columna del Project Contract real. Ese trabajo es
exactamente el contenido de P1-05 a P1-08 abajo.

## 2. Backlog priorizado

### P1 — BLOCKING (necesario para ejecutar correctamente un Project Contract)

| ID | Estado | Módulo | Objeto/Campo | Descripción | Fuente | Impacto | Responsable sugerido | Acción recomendada |
|---|---|---|---|---|---|---|---|---|
| P1-01 | `OPEN` | `ap` | `entity_axis_resolution` | `KC-AP-001` — confirmar si los 7 ETL de ámbito ITP-genérico (incluido AP) se resincronizaron desde el workbook dedicado "Mapeo ITP primer eje enablon...version 4" en algún momento posterior a esa entrega, o si quedaron congelados en ella | `mapping-governance.md` § 7, § 12.1 | Alto — riesgo de repetir el patrón de infra-migración (Hallazgo #1) si quedaron congelados | Consultor funcional + cliente | Confirmar con el cliente; comparar fecha de la "version 4" contra fecha de construcción de cada ETL ITP-genérico |
| ~~P1-02~~ | `RESOLVED` | (transversal) | `Mappings/OneDrive_2...zip`, `SQL/OneDrive_1...zip` | ~~Dos paquetes sin abrir~~ | `mapping-governance.md` § 12.1, § 12.4 | — | — | Cerrado en Sprint 8.8.1 — ambos inspeccionados y reconciliados |
| ~~P1-03~~ | `RESOLVED` | `simulacros` | `CS_Duration` (Drills) | ~~Leer fórmula `DuraciónAjustada` sin truncar~~ | `mapping-governance.md` § 12.3 | — | — | Cerrado — passthrough directo confirmado, sin recombinación |
| ~~P1-04~~ | `RESOLVED` | `simulacros` | `CS_HistoricalDrillAttendees` (Drills) | ~~Leer contenido real de `Asis_concat`~~ | `mapping-governance.md` § 12.3 | — | — | Cerrado — 2 mecanismos (passthrough + concat) confirmados |
| P1-05 | `OPEN` | `safety_meetings` | Todas las columnas del Project Contract | Cruzar cada columna de `Reuniones de grupo import completo.csv`/`Update External Meeting Participations-42.csv` contra la hoja `MAP-SM`/`MAP-Asist` real (celda por celda) | `moeve-source-inventory.md` § 3, § 6 | Alto — módulo sin ninguna regla de campo confirmada a nivel de celda todavía | Consultor funcional | Sesión dedicada de extracción, igual que se hizo para AP/Simulacros en 8.8/8.8.1 |
| P1-06 | `OPEN` | `moc` | Todas las columnas del Project Contract | Cruzar `MoC-CR-CCE-NoExistentesEnProd.csv` (61 columnas) contra `Mapeo_MOC_CT`/`Mapeo_MOC_CTOLD`/`Mapeo_MOC_SC` | `moeve-source-inventory.md` § 3 | Alto | Consultor funcional | Sesión dedicada |
| P1-07 | `OPEN` | `eventos` | Todas las columnas del Project Contract (12 exports) | Cruzar contra `MAP-ITPNew-*`/`MAP-ITPOLD-*` reales (no las huérfanas) | `moeve-source-inventory.md` § 3, § 6.4 | Alto — módulo con mayor volumen de exports distintos | Consultor funcional | Sesión dedicada, priorizar `Events-05082026_NEW` (43 cols, el export más completo) |
| P1-08 | `OPEN` | `inspecciones`, `bypass`, `ops` | Todas las columnas del Project Contract | Igual que P1-05/06/07 para los 3 módulos restantes sin regla de celda confirmada | `moeve-source-inventory.md` § 3, § 6 | Alto | Consultor funcional | Sesión dedicada por módulo |
| P1-09 (nuevo) | `OPEN` | `simulacros` | `CS_HistoricalDrillAttendees` (Drills) | Orden exacto de ejecución (create vs. update) entre el passthrough de `Asistentes` y la concatenación vía `Asis_concat`, y si hay deduplicación entre ambos resultados | `mapping-governance.md` § 12.3 | Bajo — ambos mecanismos ya identificados, este es un detalle de implementación fino | Desarrollador EMF | Confirmar con el orden real de filas del `Index` (`Crear` antes que `Update(...)`) |
| P1-10 (nuevo) | `OPEN` | (transversal) | Ticket cliente `#7581` | `Información detallada sobre todas las asunciones y procedimientos a tener en cuenta para la carga de históricos.docx` (dentro del zip de Mappings) es candidato directo a resolver el ticket del cliente que pide documentación de mapeo | `mapping-governance.md` § 12.2 | Alto para relación con cliente — puede cerrar un ticket de 834 pendiente sin trabajo adicional | Project manager | Confirmar con el cliente si este documento (o una versión suya) ya le fue entregado; si no, es la respuesta más directa disponible |
| P1-11 (nuevo, 8.9) | `OPEN` | `ap` | Identidad global de AP | Decidir si `CS_HistoricalAPID` debe namespacearse siempre (riesgo de duplicar lo ya cargado sin prefijo en los 8 flujos genéricos) o solo en orígenes nuevos aún no cargados | `action-plans-native-design.md` § 1.3 | Alto — afecta a cualquier carga futura que combine más de un `source_system` de AP | Cliente + consultor funcional | Confirmar con el cliente el estado real de lo ya cargado en Enablon antes de fijar la regla |
| P1-12 (nuevo, 8.9) | `OPEN` | `ap` (transversal) | Política de padres no resueltos | C003 exporta AP con padre no resuelto y referencia vacía por defecto (`event-link-warnings.csv`) — el EMF debe decidir formalmente bloquear/aislar en vez de exportar vacío, ver diseño propuesto | `action-plans-native-design.md` § 3 | Alto — afecta a la calidad de cualquier carga de AP transversal | Arquitecto EMF | Aprobar (o ajustar) la política de estados `RESOLVED/UNRESOLVED/AMBIGUOUS/NOT_REQUIRED` propuesta antes de implementar el Adaptador |
| P1-13 (nuevo, 8.9) | `OPEN` | `ap` | Project Contract AP, columna a columna | Confirmar, columna por columna (no solo por conteo), los 3 exports Operational reales (33/31/31) contra la clasificación IMPORTABLE/SYSTEM/.../LEGACY_C003 propuesta | `action-plans-native-design.md` § 8.2 | Alto — condición previa a publicar un `MappingSet` AP definitivo | Consultor funcional | Sesión dedicada de lectura de cabecera exacta de los 3 exports |

### P2 — DIFFERENCE (produce una diferencia conocida contra CSV Operational o carga validada)

| ID | Módulo | Descripción | Fuente | Acción recomendada |
|---|---|---|---|---|
| P2-03 | `moc` | Confirmar exactamente qué columnas añadió `ETL_MOC_NewColumns.xlsm` sobre `ETL_MOC_m_NEW_SITECAN.xlsm` (mismas 80 hojas, contenido de columna no comparado) | `moeve-source-inventory.md` § 4.2 | Diff columna a columna de las hojas `Mapeo_*`/`CSV_MOC_*` entre ambos ficheros |
| P2-04 | (transversal) | Encoding de CSV Operational no es uniforme por módulo (mezcla UTF-8/UTF-16/latin-1 incluso dentro del mismo módulo) | `moeve-source-inventory.md` § 6.1 | Cualquier lector debe detectar encoding por archivo; documentar en el futuro export contract |
| P2-05 | `safety_meetings` | Columna sin nombre en `Reuniones de grupo import completo.csv`, posición 19/22 | `moeve-source-inventory.md` § 6.3 | Confirmar con cliente/ETL qué representa antes de asumir que es descartable |
| ~~P2-06~~ | `ap` | ~~3 exports Operational con 33/31/31 columnas distintas — mapeo exacto a `idorigenac` no confirmado~~ | `c003-knowledge-adoption.md` § 3 (`C003-AP-007`/`009`) | **`RESOLVED` (Sprint 8.9)** — `cfg.ActionPlanFlowOrigin` de C003 da el mapeo completo `idorigenac`→`Sources`/columna de enlace, coincide con `config/modules.yaml` y añade `HAZOPS=6` |
| P2-07 | (transversal, Attachments) | `Centro` en `AttachmentsLast.csv` no resuelto contra `idcentro_map_itp`/`idcentro_map_gct` — numeración ambigua sin saber de qué módulo viene cada fila | `moeve-source-inventory.md` § 8 | Cruzar por `Idinforme`/`Ruta` contra el módulo de origen antes de resolver `Centro` |
| P2-08 | (transversal, Errors) | Solo 3 de 28 filas de `Requests-12082026-28.csv` clasificadas en este sprint | `moeve-source-inventory.md` § 10 | Clasificar las 25 filas restantes una por una (no en lote) |
| P2-09 (nuevo, 8.9) | `simulacros`/`ap` | `SIMS`/origen 12: hipótesis de enlace vía objeto `Crisis` en vez de `CS_Drills` directo (a diferencia del origen 18) — no verificada contra CSV Operational real | `action-plans-native-design.md` § 5 | Confirmar contra un export real de AP con filas de origen 12 (¿`BCCrisis` poblado, `CS_Drills` vacío?) |
| P2-10 (nuevo, 8.9) | `ap` (transversal, Attachments) | Generación de `CS_HistoricalAttachments` en C003 no escapa `WebUrl`/`FileName` al construir el HTML — defecto real confirmado, no heredar en el diseño EMF | `c003-knowledge-adoption.md` § 5 (`C003-AP-020`) | Ya diseñado (escaping obligatorio) en `action-plans-native-design.md` § 4 — este ítem es solo para la implementación futura |

### P3 — KNOWLEDGE GAP (regla conocida pero todavía no formalizada)

| ID | Estado | Descripción | Acción recomendada |
|---|---|---|---|
| P3-01 | `OPEN` (downgrade) | `replaceinreference` y `boolorigin` ya confirmados a nivel de motor (`Script ETL.txt`, Sprint 8.8.1) — pero ninguna hoja de mapping de Moeve inspeccionada usa esos nombres de `ReglaEspecial` todavía | Búsqueda dedicada del uso concreto en las ~150 hojas `Mapeo_*`/`MAP-*` no leídas celda a celda |
| P3-05 | `OPEN` | El inspector Python usado en Sprint 8.8/8.8.1 (openpyxl read-only, sin ejecutar nada) vivió en scratchpad, no en el repositorio | Decidir si merece formalizarse como `src/analysis/etl_inventory.py` con tests — ampliación de alcance no pedida todavía |
| P3-06 | `OPEN` | `Simulacros CCE.xlsx` e `Inspection_Data_06082026_PT_4_pestanas.xlsx` (Operational) no se inventariaron columna a columna | Aplicar el mismo inspector de cabecera a estos dos ficheros |
| P3-07 | `OPEN` | Solo se leyó el contenido de texto de `connections.xml` en 1 de los 10 ETL que lo tienen (`eventos_nuevos`) — las conexiones Power Query encontradas allí son internas tabla-a-tabla, no queries SQL nuevas | Repetir en los 9 restantes solo si se sospecha una query de extracción distinta de las ya versionadas — prioridad baja tras la reconciliación SQL 100% duplicada (§ 12.4 de `mapping-governance.md`) |
| ~~P3-08~~ | `RESOLVED` | ~~`cloneorigin` con `BUSCARX` en `Map_UserEnablon`~~ | Cerrado — confirmado como comportamiento estándar del motor, no una variante |
| P3-09 (nuevo) | `OPEN` | Las 3 hojas GCT del zip de Mappings (`260311 Mapeo gct Enablon.xlsx`, `-Match UORG ENTIDAD.xlsx`, `Mapeo_Eje_GCT_Enablon.xlsx`) no se compararon en profundidad entre sí ni contra `MapeoEje_uorg` del ETL — solo se confirmó que una de ellas es el origen de `Exportación eje` | Diff dedicado si se necesita entender la evolución interna del mapeo GCT |
| P3-10 (nuevo) | `OPEN` | `Documentos de explicación...` incluye una imagen (`Cambiar la referencia de la base de datos.png`) y un workbook de utilidades (`Scripts y como adaptar base de datos.xlsx`, 4 hojas: "Cambiar ruta de base de datos", "Script 1", "Script 2", "Pestañas transformadores") no inspeccionados en profundidad en este sprint | Revisar si contienen algo más allá de instrucciones operativas (cambiar cadena de conexión, script de limpieza de "$") |

### P4 — HISTORICAL (auditoría, no bloqueante para ejecución actual)

| ID | Descripción |
|---|---|
| P4-01 | `Events-05082026-30.csv` (2 columnas, solo IDs) probablemente es un artefacto de un trabajo de deduplicación anterior, no un export de carga — valor de auditoría sobre los 585 duplicados ya documentados en `CLAUDE.md`, no de mapping |
| P4-02 (nuevo) | 2 archivos en `sql/source_queries/Eventos/` tienen nombre de archivo con mojibake (doble-codificación UTF-8→cp1252→UTF-8 de "Ó") desde que se commitearon — contenido idéntico al del zip, sin impacto funcional, solo cosmético | Renombrar los 2 archivos a UTF-8 correcto en un commit de limpieza aparte, sin relación con este sprint |

## 3. Resumen de gaps por prioridad

| Prioridad | Sprint 8.8 | Tras 8.8.1 | Cerrados en 8.9 | Abiertos tras 8.9 |
|---|---:|---:|---:|---:|
| P1 (Blocking) | 8 | 7 | 0 | 7 + 3 nuevos (P1-11, P1-12, P1-13) = **10** |
| P2 (Difference) | 6 | 6 | 1 (P2-06) | 5 + 2 nuevos (P2-09, P2-10) = **7** |
| P3 (Knowledge gap) | 4 | 5 | 0 | **5** |
| P4 (Historical) | 1 | 2 | 0 | **2** |
| **Total abiertos** | 19 | 20 | 1 | **24** |

Sprint 8.9 cerró 1 ítem (`P2-06`, gracias a `cfg.ActionPlanFlowOrigin`
de C003) y abrió 5 nuevos — esperable: C003 es la primera evidencia de
código de una reimplementación *nativa* completa de Action Plans, y el
diseño del futuro Adaptador (`action-plans-native-design.md`) generó
preguntas de diseño (identidad, política de padres, Project Contract)
que no existían como preguntas formuladas antes de tener ese diseño.

El total de ítems abiertos sube de 19 a 20 pese a cerrar 4 — Sprint 8.8.1
descubrió más superficie de la que cerró (esperable: el zip de Mappings
aportó una fuente de conocimiento completamente nueva, no solo
respuestas a preguntas ya formuladas). Ningún ítem de este backlog se
resolvió por inferencia sin marcarlo — cada uno referencia la fuente
exacta donde se detectó y qué evidencia adicional falta para cerrarlo.
