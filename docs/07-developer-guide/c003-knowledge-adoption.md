# C003 Knowledge Adoption — Sprint 8.9

**Status:** Implemented (inventario de conocimiento), Sprint 8.9 — C003
Knowledge Adoption & Action Plans Native Design. C003 se trata como
**evidencia histórica externa, nunca como autoridad automática ni como
base tecnológica del EMF** (ver `mapping-governance.md` § 2, nivel de
precedencia 7 — "evidencia histórica no validada" — salvo que una regla
coincida con evidencia de precedencia mayor, en cuyo caso esa evidencia
mayor manda). C003 **no se integra, no se copia su runtime, no se
ejecuta**. Este documento registra qué conocimiento aporta y cómo se
reconcilia contra lo que el EMF ya sabía de Sprint 8.8/8.8.1.

## 0. Nota sobre el origen de este documento

El encargo de este sprint asume la existencia de un "assessment" previo
(de "Codex") que ya habría identificado 30 reglas `C003-AP-001`…`030`.
Esa evidencia externa **no estaba disponible en esta sesión** — no se ha
leído ningún assessment previo, solo el código fuente real de C003 en
`C:\Users\EduardoVelásquez\Desktop\C003-ActionPlans-Tool-v3\`. El
inventario de § 2 es una **reconstrucción propia, independiente**, hecha
por lectura directa y de solo lectura de ese código (SQL, PowerShell,
Python, config, un `manifest.json` real). Coincide en número (30) con lo
que pedía el encargo, pero no se ha cotejado contra ningún documento de
assessment externo porque no se dispuso de él. Si existe un assessment
real con una numeración distinta, ambos documentos deberían
reconciliarse en una sesión futura — no se asume que coinciden campo a
campo.

## 1. C003 como Knowledge Source (Fase 1)

```yaml
source_system:
  id: c003_actionplans_tool
  type: historical_migration_tool
  client: moeve
  module: ap
  scope: >
    Piloto ITP_II2 (Investigación de Eventos, NumFase=3) + 8 flujos
    genéricos (EVT_NEW, EVT_OLD, IPS, SIMS, OPS, SM, HAZOPS, OTROS)
    sobre la tabla compartida Prevencion.dbo.ITP_ACCIONES_CORRECTORAS.
  technology: >
    PowerShell (orquestación + UI WPF mínima) + T-SQL (procedimientos
    almacenados, base propia C003_Migration, nunca escribe en
    Prevencion) + Python (extracción puntual, una sola vez, de 2 hojas
    del Excel legado a CSV de configuración) + CSV (config y salida).
  provenance: >
    Herramienta nativa construida para reemplazar el ETL Excel de
    Action Plans. No forma parte de este repositorio ni de
    EMF_DATA_ROOT — vive en una carpeta local separada del consultor.
  purpose: >
    Generar CSV de Action Plans para Enablon directamente desde SQL
    Server, sin depender de fórmulas de Excel ni de datos cacheados.
  version_evidence: >
    MappingVersion registrado por el propio proceso: '1.4.0' (pilot,
    etl.BuildActionPlansITPII2) y '2.0.0' (flujos genéricos,
    etl.BuildActionPlansGeneric) — versión de la lógica de mapeo, no
    del repositorio C003 en su conjunto (sin control de versiones
    visible en la carpeta inspeccionada).
  hashes: >
    No se calculó un hash del árbol completo de C003 (no es una fuente
    de un solo archivo como los ETL de Sprint 8.8). Los propios scripts
    de C003 sí registran SHA-256 de cada CSV de entrada que consumen
    (EvidenceReference en cfg.*, outputSha256/rejectsSha256 en
    manifest.json) — ese hábito de evidencia ya es, en sí mismo, un
    patrón a valorar (ver § 6, REUSE_CONCEPT).
  confidence: medium-high
  validation_status: HISTORICAL_UNVERIFIED
  limitations: >
    No se ha ejecutado C003 (prohibido). Todo lo aquí registrado se
    infirió leyendo código SQL/PowerShell/Python estático — nunca un
    resultado real observado. Los 6 directorios en runs/ contienen
    salidas reales de ejecuciones pasadas (CSV con datos de cliente,
    manifest.json) — se inspeccionó únicamente la ESTRUCTURA de un
    manifest.json (sin datos de fila) como evidencia de formato; ningún
    CSV de runs/ se leyó ni se copió.
```

No se guarda la ruta absoluta de Windows como identidad — `c003_actionplans_tool`
es el identificador estable usado en el resto de este documento y en
`config/knowledge/moeve/ap/`.

## 2. Inventario de reglas C003 (Fase 2)

30 reglas reconstruidas desde evidencia estática (código SQL/PowerShell/
Python real, citado por archivo). Estado inicial: ninguna se marca
`CURRENT_VERIFIED` solo porque C003 la ejecutaba — ver § 3 para la
reconciliación caso a caso.

| ID | Objeto/Campo | Flujo(s) | Regla (evidencia textual) | Fuente | Estado inicial |
|---|---|---|---|---|---|
| `C003-AP-001` | Resolución de entidad | Ambos | `CenterId`+`OrganizationalUnitId` → `EnablonEntity` vía `cfg.ActionPlanEntity`, con `OrganizationalUnitId=-1` como comodín de "centro sin unidad específica", prioridad a la coincidencia exacta sobre el comodín | `sql/40-...sql` L84-91, `Extract-CommonConfiguration.py` (fuente: hoja `Entidades_Mapeo` del Excel, no `Exportación eje`) | `HISTORICAL_VERIFIED` |
| `C003-AP-002` | `CS_HistoricalAPID` (pilot) | ITP_II2 | `CONCAT('ITPII2.', IDAccionCorrectora)` — **namespaced** | `sql/20-build.sql` L168 | `HISTORICAL_VERIFIED` |
| `C003-AP-003` | `CS_HistoricalAPID` (genérico) | 8 flujos | `IDAccionCorrectora` sin prefijo — `HistoricalApPrefix` existe como columna en `cfg.ActionPlanFlow` pero se carga vacío (`N''`) para los 8 flujos | `sql/30-...sql` L124-132, `sql/40-...sql` L158-161 | `HISTORICAL_VERIFIED` — ver `KC-AP-ID-004` (Fase 5) |
| `C003-AP-004` | `CS_HistoricalOriginID` (pilot) | ITP_II2 | `ITP_INFORME_INV2.IDEvento` (no `IDInformeInv`) | `sql/20-build.sql` L169 | `HISTORICAL_VERIFIED` |
| `C003-AP-005` | `CS_HistoricalOriginID` (genérico) | 8 flujos | `CodOrigen` | `sql/40-...sql` L162 | `HISTORICAL_VERIFIED` |
| `C003-AP-006` | `CS_HistoricalDataOrigin` | Ambos | Constante `'Prevención.ITP_ACCIONES_CORRECTORAS'` (construida con `NCHAR(243)` para la "ó") | `sql/20-build.sql` L167, `sql/40-...sql` L157 | `HISTORICAL_VERIFIED` |
| `C003-AP-007` | Enrutado de padre (genérico) | 8 flujos | `LinkTargetColumn` (por origen, en `cfg.ActionPlanFlowOrigin`) enruta dinámicamente la referencia resuelta a una de: `Incidents`, `ACSObservation`, `CS_IndependentManualEvents`, `CS_IndManualOPS`, `CS_IP`, `CS_Drills`, `CS_Meetings` | `sql/40-...sql` L131-137 | `HISTORICAL_VERIFIED` |
| `C003-AP-008` | Enrutado de padre (pilot) | ITP_II2 | `Incidents = EnablonEventId` vía `LEFT JOIN cfg.EventCrosswalk` — nulo si no hay cruce, la fila **no se bloquea** | `sql/20-build.sql` L59-60 | `HISTORICAL_VERIFIED` — ver Fase 7 (política a NO replicar tal cual) |
| `C003-AP-009` | `Sources` por origen | 8 flujos | Valor externalizado por `(FlowCode, LegacyOriginId, LegacyOriginName)`, p. ej. `\IMS\EHSActionPlansEvents`, `AP@AP`, `\BC\Crisis\CrisisActionPlan`, `OPS does not contain action plans in Enablon` (!) | `sql/30-...sql` L169-191 | `PARTIAL_MATCH` (ver § 4, SIMS y anomalía OPS) |
| `C003-AP-010` | `Families` por origen | 8 flujos | Valor externalizado, p. ej. `TO-M01`…`TO-M08` | `sql/30-...sql` L176-189 | `UNRESOLVED` (sin evidencia EMF equivalente) |
| `C003-AP-011` | `CS_SpecifyEffectivenessReviewer` por origen | 8 flujos | `Yes`/`No` externalizado por origen | `sql/30-...sql` L176-189 | `UNRESOLVED` |
| `C003-AP-012` | `Priority` | Ambos (tabla compartida) | `LegacyPriorityId=438` → `Code3` directo; `439/440/441` → escalado por `DATEDIFF(MONTH, FechaCreacion, FechaPrevistaFin)`: `<3`→`Code2`, `≤12`→`Code3`, `>12`→`Code0` | `sql/30-...sql` L77-89, `sql/40-...sql` L139-149 | `MATCHES_CURRENT_EVIDENCE` (coincide con la fórmula ya vista en `Priorities_Map` del ETL AP_GCT, Sprint 8.8) |
| `C003-AP-013` | `Status` (genérico) | 8 flujos | `FechaRealFin IS NULL` → `Not Started`; si no, `Completed` | `sql/40-...sql` L150 | `NEW_KNOWLEDGE` |
| `C003-AP-014` | `Status` (pilot) | ITP_II2 | Constante `Not Started` (el piloto solo cubre `NumFase=3`, en curso) | `sql/20-build.sql` L142 | `NEW_KNOWLEDGE` |
| `C003-AP-015` | `LevelNo` (genérico) | 8 flujos | `FechaRealFin IS NULL` → `'13'`; si no, `'-1'` | `sql/40-...sql` L121 | `NEW_KNOWLEDGE` |
| `C003-AP-016` | `LevelNo` (pilot) | ITP_II2 | Constante `'13'` | `sql/20-build.sql` L141 | `NEW_KNOWLEDGE` |
| `C003-AP-017` | Limpieza de `Name` | Ambos | Elimina `# ¤ ¦ \| §` (pilot añade comillas `" '`), `CR`/`LF`; trunca a 240 caracteres | `sql/20-build.sql` L102-108, `sql/40-...sql` L123 | `PARTIAL_MATCH` (mismo espíritu que `titlefix` del motor Office Script de Sprint 8.8.1, límite distinto: 240 vs 149 por defecto) |
| `C003-AP-018` | `DetailedDescription` (genérico) | 8 flujos | Concatenación etiquetada vía `CONCAT_WS`: `Nombre` + `Descripcion` + `"Orden de trabajo: "+OrdenTrabajo` + `"Coste: "+Coste` + `"Proyecto: "+NumeroProyecto` + `DescripcionEvidencias`, separador salto de línea, componentes vacíos omitidos | `sql/40-...sql` L124-129 | `NEW_KNOWLEDGE` |
| `C003-AP-019` | Clave de adjunto | Ambos | `Idinforme = IDAccionCorrectora` AND `Tipo de Informe = 8` AND `Visible = 1` | `sql/20-build.sql` L84-86, `sql/40-...sql` L98-99, README | `MATCHES_CURRENT_EVIDENCE` (coincide con `CLAUDE.md`/Sprint 8.8) |
| `C003-AP-020` | Generación HTML de adjuntos | Ambos | `STRING_AGG('<a href="'+WebUrl+'" target="_blank">'+FileName+'</a>')` — **sin escapar** `WebUrl`/`FileName` | `sql/20-build.sql` L76-87, `sql/40-...sql` L96-100 | `CONFLICT` — ver § 5 (Fase 10), defecto real |
| `C003-AP-021` | Formato de fecha | Ambos | `dd/MM/yyyy H:mm` construido manualmente (`CONVERT(...,103)` + `DATEPART(HOUR)`+`DATEPART(MINUTE)` con padding), sin cero a la izquierda en la hora | `sql/20-build.sql` L143-147, `sql/40-...sql` L151-156 | `NEW_KNOWLEDGE` |
| `C003-AP-022` | `ApplyTimeLag` | Ambos | `Yes` si existe historial de fecha revisada (`IDHistoricoFecha`/`FechaPrevistaFinAct`), si no vacío | `sql/20-build.sql` L155, `sql/40-...sql` L155 | `NEW_KNOWLEDGE` |
| `C003-AP-023` | `CS_ReasonForExtension` (pilot) | ITP_II2 | `ITP_HISTORICO_FECHAS_ACCIONES_CORRECTORAS.Motivo`, fila más reciente por `FechaModificacion DESC, IDHistoricoFecha DESC` | `sql/20-build.sql` L64-73, L175 | `NEW_KNOWLEDGE` |
| `C003-AP-024` | `RevisedDueDate`/`CS_RequestedDueDate` (pilot) | ITP_II2 | Mismo valor histórico (`FechaPrevistaFinAct`) formateado en ambas columnas | `sql/20-build.sql` L148-161 | `NEW_KNOWLEDGE` |
| `C003-AP-025` | Resolución de `Owner` (genérico) | 8 flujos | `LegacyUserId` → `EnablonOwnerId` vía `cfg.ActionPlanOwner`, poblada por `Extract-UserOwnerMap.py` (XLOOKUP de `ITP_USUARIOS_map` contra `UsersEnablon_PROD` por email) | `sql/40-...sql` L69, `Extract-UserOwnerMap.py` | `NEW_KNOWLEDGE` |
| `C003-AP-026` | `CS_HistoricalUserName` | Ambos | `ITP_USUARIOS.Nombre` por `IDUsuarioResponsable` | `sql/20-build.sql` L61-62, `sql/40-...sql` L81 | `MATCHES_CURRENT_EVIDENCE` |
| `C003-AP-027` | `TeamMembers` | Ambos | `NULLIF(OtroResponsable, '')` | `sql/20-build.sql` L173, `sql/40-...sql` L162 | `NEW_KNOWLEDGE` |
| `C003-AP-028` | Alcance del piloto | ITP_II2 | `NumFase = 3` AND no existe otra fila del mismo `IDInformeInv` con `NumFase <> 3` | `sql/20-build.sql` L88-95, README | `MATCHES_CURRENT_EVIDENCE` |
| `C003-AP-029` | Alcance de los flujos genéricos | 8 flujos | `(sin filtros → todo) OR IDCentro IN (...) OR IDUnidadOrg IN (...)` — OR, no AND | `sql/40-...sql` L101-106, README | `NEW_KNOWLEDGE` |
| `C003-AP-030` | Hash de fila para detección de cambios | Ambos | `SHA2_256` sobre la concatenación de campos de negocio clave, por fila, guardado como `SourceRowHash` | `sql/20-build.sql` L49-54, `sql/40-...sql` L72-75 | `NEW_KNOWLEDGE` — ver § 6 (REUSE_CONCEPT) |

Dos hallazgos adicionales, fuera de la numeración 001-030 (no bloquean
el conteo pedido, se registran igual por su relevancia):

- **Deduplicación de eventos** (`Run-Pilot.ps1` L152-166): si el export
  de eventos trae varias filas para el mismo `LegacyEventId`, gana el
  `Id` numérico de Enablon más alto — regla determinista, documentada
  en `manifest.json::eventDuplicateRule`.
- **`AllowPartial` forzado desde la UI WPF** (`Start-ActionPlansUI.ps1`
  L126, L131): cada invocación lanzada desde la UI añade `-AllowPartial`
  de forma **incondicional** — no hay checkbox, no hay confirmación. Ver
  Fase 12 en `action-plans-native-design.md`.

## 3. Reconciliación contra conocimiento EMF/Moeve (Fase 3)

| C003 rule | Clasificación | Contra qué se comparó | Resultado |
|---|---|---|---|
| `C003-AP-001` (entidad) | `PARTIAL_MATCH` | `config/knowledge/moeve/ap/mapping-set.yaml` (`ap.entity_axis_resolution`), `KC-AP-001` | C003 usa explícitamente `Entidades_Mapeo` (confirmado por el propio código de `Extract-CommonConfiguration.py`, que apunta a esa hoja por nombre) — **nunca** el mecanismo `MapeoEje_uorg`/`Exportación eje`. Tercera confirmación independiente (tras el ETL y el workbook dedicado de Sprint 8.8.1) de que `Entidades_Mapeo` es una fuente real y deliberadamente usada, no un fragmento accidental — pero también confirma que ni siquiera la reimplementación nativa más reciente adoptó el mecanismo de catálogo vivo. Ver § 4. |
| `C003-AP-002`/`003` (identidad) | `NEW_KNOWLEDGE` | `Fase 5` (identidad AP) | Sin equivalente previo en conocimiento EMF — ver `action-plans-native-design.md` § 1 |
| `C003-AP-004`/`005` (origin ID) | `MATCHES_CURRENT_EVIDENCE` | `config/modules.yaml::ap` | Coincide con el patrón ya conocido (`CS_HistoricalOriginID` distinto por submódulo) |
| `C003-AP-006` | `MATCHES_CURRENT_EVIDENCE` | `sql/20-build.sql` de C003 usa literalmente el mismo patrón de constante que el ETL Excel (`N'Prevenci'+NCHAR(243)+N'n...'`) | Confirma que ambas implementaciones (ETL y C003) resolvieron el mismo problema de encoding de la misma forma — indicio de que quien construyó C003 conocía el ETL |
| `C003-AP-007`/`009` (Sources/LinkTargetColumn por origen) | `NEW_KNOWLEDGE`, alto valor | `config/modules.yaml::ap::idorigenac_por_modulo` | **Resuelve backlog P2-06** (Sprint 8.8, "mapeo exacto a `idorigenac` no confirmado") — `cfg.ActionPlanFlowOrigin` de C003 da el mapeo completo `FlowCode` → `LegacyOriginId` → `Sources`/`LinkTargetColumn`, coincide en los IDs de origen con `config/modules.yaml` (16/17 EVT_NEW, 2/13 EVT_OLD, 4/9 IPS, 12/18 SIMS, 3/8 OPS, 11 SM, 7/14 OTROS) y **añade** `HAZOPS=6`, que `config/modules.yaml` no tenía identificado |
| `C003-AP-012` (Priority) | `MATCHES_CURRENT_EVIDENCE` | Hoja `Priorities_Map` del ETL AP_GCT (Sprint 8.8) | Misma regla de negocio (umbrales 3/12 meses), implementada dos veces de forma independiente con el mismo resultado — alta confianza |
| `C003-AP-019` (clave de adjunto) | `MATCHES_CURRENT_EVIDENCE` | `CLAUDE.md`, `moeve-source-inventory.md` § 8 (Attachments) | Confirma exactamente la regla ya conocida (`Idinforme`+`Tipo de Informe`, `Tipo de Informe=8`, `Visible=1`) |
| `C003-AP-020` (HTML sin escapar) | `CONFLICT` (con la buena práctica esperada, no con otra fuente EMF) | Ninguna fuente EMF define todavía esta regla — se registra como defecto conocido a NO heredar | Ver Fase 10 |
| `C003-AP-021` (formato fecha) | `PARTIAL_MATCH` | `CLAUDE.md` (no especifica formato exacto de fecha para AP) | Nueva precisión (`H:mm`, sin cero a la izquierda) no documentada antes |
| Resto de reglas (008, 010, 011, 013-018, 022-030) | `NEW_KNOWLEDGE` | Sin equivalente previo en `config/knowledge/moeve/ap/` | Se incorporan como candidatas, ninguna `CURRENT_VERIFIED` |

Ninguna regla se promovió a `CURRENT_VERIFIED` — la más alta alcanzada es
`MATCHES_CURRENT_EVIDENCE` (coincide con una fuente de precedencia ≥ 4
ya existente) o `HISTORICAL_VERIFIED` (confirmada por código real de
C003, pero C003 en sí mismo es precedencia 7, no suficiente en solitario).

## 4. `KC-AP-001` — actualización con evidencia C003 (Fase 4)

La pregunta pendiente sigue siendo la formulada al cierre de Sprint
8.8.1: **si los ETL/procesos de ámbito ITP-genérico se resincronizaron
con la versión vigente del catálogo de eje después de la "version 4",
o quedaron congelados en ella.** C003 no responde esa pregunta —
la profundiza en una dirección concreta: la reimplementación nativa más
reciente y mejor construida de Action Plans (C003, que corrige
explícitamente varios defectos del ETL Excel, ver README "Diferencias
corregidas respecto al Excel") **también** usa `Entidades_Mapeo`,
extraído una sola vez del mismo Excel legado (`ETL- AP-0308.xlsx`), no
el mecanismo de catálogo vivo.

Dos lecturas posibles, ninguna confirmada:

1. `Entidades_Mapeo` seguía siendo, a la fecha de construcción de C003,
   la mejor fuente disponible y conocida — el mecanismo de catálogo vivo
   (`MapeoEje_uorg`/`Exportación eje`) podría no haber estado
   documentado o accesible para quien construyó C003.
2. Quien construyó C003 desconocía el mecanismo de catálogo vivo (ya
   usado en MOC/AP-GCT) y replicó, sin saberlo, la misma limitación que
   Sprint 8.8.1 ya había señalado.

No se elige entre las dos — se registra como evidencia adicional del
mismo conflicto, no como su resolución. `KC-AP-001` permanece `OPEN`.
Ver `config/knowledge/moeve/ap/knowledge-conflicts.yaml` para el
registro actualizado.

## 5. Attachments — conocimiento vs. implementación legacy (Fase 10)

**A. Conocimiento funcional (confirmado, reutilizable):**

- Clave compuesta `Idinforme` + `Tipo de Informe` (un `Idinforme` puede
  repetirse entre módulos — ya sabido desde `CLAUDE.md`/Sprint 8.8).
- Para Action Plans específicamente: `Idinforme = IDAccionCorrectora`,
  `Tipo de Informe = 8`.
- Solo se listan adjuntos con `Visible = 1`.
- Validación de entrada ya existe en C003 (a nivel de mapping, no de
  generación): `INVALID_IDINFORME`, `MISSING_FILENAME`, `MISSING_WEBURL`
  como códigos de rechazo explícitos antes de cargar el cruce.

**B. Implementación legacy (NO portar):**

- La generación de `CS_HistoricalAttachments` concatena
  `<a href="{WebUrl}" target="_blank">{FileName}</a>` con `STRING_AGG`
  **sin escapar** `WebUrl` ni `FileName` — un nombre de fichero o URL
  con `"`, `<`, `>` rompe el HTML generado o permite inyectar marcado
  adicional en el campo. Confirmado en ambos procedimientos SQL
  (`sql/20-build.sql` L76-87, `sql/40-...sql` L96-100). Este defecto
  **no se hereda** en ningún diseño futuro.

**Diseño del componente transversal futuro:** ver
`action-plans-native-design.md` § 4 (Attachments no es AP-specific,
aparece en al menos 8 de los 11 ETL de Sprint 8.8 con el mismo patrón
`TablaAdjuntos`).

## 6. Algoritmos/patrones reutilizables (Fase 13)

| Candidato | Evidencia | Clasificación | Nota |
|---|---|---|---|
| Hash de fila para detección de cambios (`SourceRowHash`, SHA2_256) | `C003-AP-030` | `ALREADY_EXISTS` (en espíritu) | El EMF ya usa hashes de integridad en `export_manifest.yaml` (Drills, Sprint 8.1) — mismo principio, aplicarlo a nivel de fila en vez de a nivel de fichero completo es un refinamiento válido, `REUSE_CONCEPT` para un futuro motor incremental |
| `manifest.json` con reglas declaradas como texto (`historicalApIdRule`, `attachmentRule`, `dateFormat`...) | Todos los `manifest.json` de C003 | `ALREADY_EXISTS` | Coincide, de forma independiente, con el patrón ya usado por `manifest.py`/`export_manifest.yaml` del EMF — validación cruzada de que el diseño EMF actual va en la dirección correcta |
| Resolución de entidad con comodín de especificidad (`OrganizationalUnitId=-1`, ORDER BY especificidad) | `C003-AP-001` | `REUSE_CONCEPT` | Patrón limpio de "match exacto preferido sobre comodín" — más simple que las cadenas `XLOOKUP` anidadas del Excel; útil como referencia de diseño para el `ResourceResolver`, no para copiar el SQL literal |
| Enrutado dinámico de columna destino (`LinkTargetColumn` vía `CASE WHEN`) | `C003-AP-007` | `REUSE_CONCEPT` | Patrón de "N columnas destino posibles, una tabla de configuración decide cuál" — aplicable al diseño de `finalize_action_plans` (Fase 6) |
| Concatenación etiquetada de campos narrativos (`DetailedDescription`) | `C003-AP-018` | `REUSE_CONCEPT` | Coincide en espíritu con la regla `concat` ya confirmada en Sprint 8.8.1 (motor Office Script) — párrafo estructurado con etiquetas, componentes vacíos omitidos |
| Deduplicación de eventos por "Id numérico más alto" | Hallazgo adicional § 2 | `REUSE_CONCEPT` | Regla de desempate determinista y documentada — aplicable a cualquier reconciliación de claves duplicadas |
| Extracción de Excel vía XML crudo del OOXML (sin abrir el libro con Excel/COM) | `Extract-CommonConfiguration.py`, `Extract-UserOwnerMap.py` | `ALREADY_EXISTS` | Mismo principio que el inspector de solo lectura usado en Sprint 8.8 (`openpyxl`, sin ejecutar fórmulas) — C003 llega aún más lejos, sin dependencia de `openpyxl` siquiera (XML + `zipfile` de la librería estándar) |
| Generación de HTML de adjuntos sin escapar | `C003-AP-020` | `DO_NOT_USE` | Ver § 5 |
| `rej.ActionPlan` (tabla) sin ningún `INSERT` en ningún procedimiento | `sql/00-setup.sql`, `20-build.sql`, `40-...sql` | `DO_NOT_USE` (tal cual) | Ver Fase 11 en `action-plans-native-design.md` — no es "legacy inoperativo heredado de otro sistema", es infraestructura preparada pero sin ninguna regla que la dispare todavía en C003 — matiz importante, no se copia el patrón vacío |

No se copió ningún script completo — cada fila de la tabla es una
observación de patrón, no una cita de implementación a trasladar.
