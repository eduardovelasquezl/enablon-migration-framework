# Action Plans — Diseño del Adaptador Nativo (Sprint 8.9)

**Status:** Proposed. Diseño arquitectónico — **nada de este documento
está implementado**. No depende de C003 como base tecnológica; usa C003
únicamente como evidencia (ver `c003-knowledge-adoption.md`) y la
evidencia real de ETL/CSV/mappings ya recogida en Sprint 8.8/8.8.1. Se
apoya en el vocabulario ya aprobado de `mapping-governance.md`,
`mapping-specification.md` y `project-contract-model.md`, sin
redefinirlos.

## 0. Nota sobre referencias del encargo que no existen todavía

El encargo de este sprint pide integrar conceptualmente con "ADR-003
Action Plans Cross Module", `CrossModuleActionPlanBuffer` y
`finalize_action_plans`. **Ninguno de los tres existe en este
repositorio** (verificado: `docs/02-adr/` llega hasta `ADR-016`, no hay
ningún `ADR-003` sobre Action Plans; no hay ningún símbolo
`CrossModuleActionPlanBuffer` ni `finalize_action_plans` en `src/` ni en
`docs/`). Se tratan aquí como lo que realmente son en el estado actual
del repositorio: **diseño nuevo, propuesto por primera vez en este
documento**, no una integración con algo preexistente. Si se aprueba
este diseño, un ADR formal debería numerarse `ADR-017` (siguiente
disponible), no `ADR-003` — el número citado en el encargo no
corresponde a la secuencia real de este repositorio.

## 1. Identidad de Action Plans (Fase 5)

### 1.1 El problema, con evidencia concreta

C003 usa `CS_HistoricalAPID` sin namespace consistente:

- Piloto ITP_II2: `CONCAT('ITPII2.', IDAccionCorrectora)` — namespaced.
- Los 8 flujos genéricos: `IDAccionCorrectora` a secas —
  `HistoricalApPrefix` existe como columna en `cfg.ActionPlanFlow` pero
  se deja vacía para los 8 (`c003-knowledge-adoption.md`, `C003-AP-003`).

Dentro de C003 esto no colisiona hoy porque los 8 flujos genéricos leen
todos de la **misma** tabla origen (`Prevencion.dbo.ITP_ACCIONES_CORRECTORAS`,
con `IDAccionCorrectora` como clave única de esa tabla) y el piloto lee
de una tabla **distinta** (`ITP_II2_ACCIONES_CORRECTORAS`, con su propia
numeración) — el prefijo `ITPII2.` existe precisamente para separar esas
dos secuencias de identificadores. Pero además existe un **tercer**
origen ya conocido por Sprint 8.8: el ETL `AP_GCT` (ámbito MOC/GCT), que
lee de `CT_ACCIONES_*` — una **cuarta** secuencia de IDs, sin ningún
prefijo visible en las hojas `MAP-AP-CR` inspeccionadas en Sprint 8.8. Si
alguna vez estos tres orígenes (ITP-genérico, ITPII2, MOC/GCT) confluyen
en el mismo Project Contract o en el mismo proceso de carga sin
namespace, dos `IDAccionCorrectora`/`IDAccion` numéricamente iguales de
orígenes distintos colisionarían en `CS_HistoricalAPID`.

### 1.2 Diseño propuesto (no implementado)

Distinguir 4 identificadores, nunca confundirlos:

| Identificador | Propósito | Estabilidad | Ejemplo conceptual |
|---|---|---|---|
| **Identidad global** (`global_record_id`) | Clave única dentro de todo el EMF, a través de clientes/proyectos/módulos/orígenes | Estable mientras exista el registro | `moeve.ap.itp_generico.evt_new.<IDAccionCorrectora>` |
| **Identidad local** (`source_record_id`) | Clave dentro del sistema origen únicamente | Estable dentro de ese origen, puede colisionar entre orígenes | `IDAccionCorrectora=42` |
| **Historical identifier** (`CS_HistoricalAPID`/`CS_HistoricalOriginID`) | Lo que se escribe en el CSV de Enablon — debe ser legible y trazable para un humano que audite datos migrados | Definido por el Project Contract de Enablon, no por el EMF | `ITPII2.42`, o `EVT_NEW.42` si se namespacea |
| **Display/reference identifier** | Lo que ve un usuario de Enablon en la UI (`Id` asignado por Enablon tras la carga) | Asignado por Enablon, fuera del control del EMF | (numérico interno de Enablon) |

**Identidad global — propuesta conceptual, consistente con el CDM**
(`canonical-data-model.md`, sin modificarlo salvo que se confirme una
contradicción real — no se ha encontrado ninguna en este sprint):

```
global_record_id = source_system + "." + source_object_type + "." + source_record_id
```

Donde:

- `source_system`: `itp_generico` | `itp_ii2` | `gct` (los 3 orígenes ya
  confirmados con IDs propios — ver § 1.1).
- `source_object_type`: `ap` (Action Plans es, en sí, ya un tipo dentro
  de cada sistema origen — no hace falta un cuarto nivel salvo que en el
  futuro aparezca un segundo tipo de objeto por sistema).
- `source_record_id`: el identificador local tal cual existe en el
  origen (`IDAccionCorrectora` o `IDAccion`).

Esto **no** reemplaza `CS_HistoricalAPID` (que sigue siendo lo que
Enablon espera recibir, con el formato que el Project Contract exija) —
es la clave interna que el EMF usaría para no confundir dos registros de
orígenes distintos durante el procesamiento, **antes** de proyectar al
formato de salida de Enablon. `CS_HistoricalAPID` se derivaría de
`global_record_id` (o de una función determinista equivalente), nunca al
revés.

### 1.3 Qué se decide y qué queda pendiente

**Estado: `PROPOSED DESIGN`** — el esquema de 4 identificadores de § 1.2
es una propuesta, no una decisión adoptada ni una implementación. No se
modifica el CDM (`canonical-data-model.md`) — no se encontró una
contradicción real, solo una ausencia de un patrón de identidad
compuesta para objetos transversales, que es exactamente lo que un
objeto como Action Plans necesita y Drills (de un solo origen) no
necesitó hasta ahora.

**Criterio para revisar esto en el futuro:** si la implementación real
del Adaptador AP (§ 10) demuestra que el CDM actual no puede representar
esta identidad sin ambigüedad — por ejemplo, si `global_record_id` no
encaja de forma limpia en el modelo de `CanonicalRecord`/`Provenance` ya
definido — deberá abrirse una revisión formal del CDM y, si procede, una
ADR nueva (siguiente número libre real del repositorio, no un número
retrospectivo — ver § 0). No se abre esa revisión preventivamente en
este sprint, porque todavía no existe una implementación que la exija.
- Pendiente de decisión humana: si `CS_HistoricalAPID` en el CSV final
  debe namespacearse **siempre** (rompiendo con lo que ya está cargado
  en Enablon con el formato sin prefijo de los 8 flujos genéricos —
  riesgo de duplicar registros si se re-namespacea algo ya cargado) o
  solo en los orígenes nuevos que todavía no se han cargado — backlog
  P1 nuevo, ver `moeve-mapping-backlog.md`.

## 2. Action Plans como objeto transversal (Fase 6)

### 2.1 El patrón, evaluado formalmente

```
múltiples módulos/orígenes (Eventos, Simulacros, Inspecciones, OPS,
Safety Meetings, HAZOPS, MOC, Otros — 3 sistemas origen: ITP-genérico,
ITP_II2, GCT)
        ↓
Canonical Records (uno por AP, con source_system/source_object_type/
source_record_id — ver § 1.2)
        ↓
Cross-Module AP Buffer (acumula registros de todos los orígenes antes
de resolver relaciones de padre — nombre propuesto, no existe hoy)
        ↓
Resolución de padres (ver § 3)
        ↓
Finalización (nombre propuesto: `finalize_action_plans` — no existe
hoy; aplica reglas transversales: Priority, Status, LevelNo, limpieza
de Name, fecha, adjuntos — todas ya confirmadas como compartidas entre
orígenes en `c003-knowledge-adoption.md` § 2)
        ↓
Action Plans Project Contract (columnas reales observadas en
`CSV_Enablon_Operational`, no las 69 del Template — ver § 3 de
`moeve-source-inventory.md` § 6.6 y Fase 8 más abajo)
        ↓
CSV
```

**No se diseña AP como copia de Drills.** Drills es de un solo origen
(`Prevencion.dbo.DB_OrigenSim`), un solo `source_system`, con una
resolución de entidad y una regla por campo, 1:1. AP es transversal por
diseño — la evidencia de C003 (`cfg.ActionPlanFlowOrigin`, 8 flujos × 2-3
orígenes cada uno = 15 combinaciones `FlowCode`+`LegacyOriginId`, más el
piloto ITPII2, más MOC/GCT) confirma que cualquier adaptador de AP debe
aceptar múltiples `source object type` como entrada desde el diseño, no
como una ampliación posterior.

### 2.2 Matriz de flujos (evidencia C003 + `config/modules.yaml`)

| `FlowCode` (C003) | `LegacyOriginId` | Origen lógico | `LinkTargetColumn` | Módulo EMF equivalente |
|---|---:|---|---|---|
| `EVT_NEW` | 16 | Investigación Eventos | `Incidents` | `eventos` (submódulo nuevos) |
| `EVT_NEW` | 17 | Near Miss / O-INV-EVENTOS-MANUALES | `Incidents` / `CS_IndependentManualEvents` (según nombre exacto) | `eventos` |
| `EVT_OLD` | 2 | Informe de Investigación | `Incidents` | `eventos` (submódulo antiguos) |
| `EVT_OLD` | 13 | O-INV-MANUALES | `CS_IndependentManualEvents` | `eventos` |
| `IPS` | 4 | Inspección Preventiva | `ACSObservation` | `inspecciones` |
| `IPS` | 9 | O-IPS-MANUALES | `CS_IP` | `inspecciones` |
| `SIMS` | 12 | Simulacros | *(ninguno — ver § 5, Fase 9)* | `simulacros` |
| `SIMS` | 18 | O-SIMULACROS-MANUALES | `CS_Drills` | `simulacros` |
| `OPS` | 3 | Observación de Trabajo | `CS_IndManualOPS` (nota: `SourcesValue` marca "OPS does not contain action plans in Enablon") | `ops` |
| `OPS` | 8 | O-OPS-MANUALES | `CS_IndManualOPS` | `ops` |
| `SM` | 11 | Reuniones de Grupo | `CS_Meetings` | `safety_meetings` |
| `HAZOPS` | 6 | HAZOP/WHAT IF | *(ninguno)* | sin módulo EMF equivalente confirmado — nuevo |
| `OTROS` | 7 | O-AUD-EXT / Otros | *(ninguno)* | sin módulo EMF equivalente confirmado |
| `OTROS` | 14 | Visitas Seguros | *(ninguno)* | sin módulo EMF equivalente confirmado |
| *(pilot)* `ITP_II2` | — | Investigación Eventos (fase 3) | `Incidents` | `eventos` (piloto, subconjunto NumFase=3) |
| *(no cubierto por C003)* MOC/GCT | — | `CT_ACCIONES_*` | — | `moc` |

**No se asume que los nombres de flujo de C003 deban convertirse en
módulos EMF** — la tabla los mapea contra los módulos EMF ya conocidos
por nombre de tabla origen (`config/modules.yaml`), no por decreto. 3
orígenes (`HAZOPS`, y las 2 filas de `OTROS`) no tienen todavía un módulo
EMF con el que emparejarse — quedan `UNKNOWN`, no se inventa uno.

## 3. Parent Relationships (Fase 7)

### 3.1 El anti-patrón confirmado en C003 — no replicar

`event-link-warnings.csv` (C003, ver `c003-knowledge-adoption.md`
`C003-AP-008`): cuando el evento histórico de un AP `ITP_II2` no aparece
todavía en el último export de Enablon, la fila **igual se exporta** —
`Incidents` queda vacío, se registra una advertencia en un fichero
aparte, pero el `AP` sale en el CSV final con una referencia de padre
vacía. `AllowPartial` no es necesario para que esto ocurra — es el
comportamiento **por defecto**, no una excepción consciente.

### 3.2 Política EMF propuesta

```
parent resuelto
  → AP puede finalizar (referencia de padre presente y válida)

parent no resuelto
  → registrar como UNRESOLVED relationship (no como referencia vacía)
  → bloquear el AP de ese lote, o aislarlo en una cola separada,
    según lo que declare el Project Contract del módulo
  → NUNCA convertir silenciosamente a "" en el CSV de salida
```

Estados conceptuales:

| Estado | Significado | Acción |
|---|---|---|
| `RESOLVED` | La referencia de padre se resolvió a una entidad Enablon real | AP puede finalizar y pasar a `finalize_action_plans` |
| `UNRESOLVED` | El padre existe en el origen pero no se encontró en el cruce disponible (igual que el caso de C003) | AP **no** finaliza en este lote — se registra en la cola de pendientes, con referencia a qué falta (igual que `event-link-warnings.csv`, pero bloqueando en vez de solo advertir) |
| `AMBIGUOUS` | Más de una coincidencia posible sin regla de desempate clara (a diferencia del caso ya resuelto de duplicados de evento en C003, que sí tiene desempate determinista — ver `c003-knowledge-adoption.md` § 2) | Requiere revisión humana explícita, nunca una elección automática sin regla documentada |
| `NOT_REQUIRED` | El tipo de AP no requiere padre por diseño (p. ej. `HAZOPS`/`OTROS`, sin `LinkTargetColumn` en absoluto) | AP finaliza sin bloqueo — la ausencia de padre es esperada, no un fallo |

### 3.3 Integración conceptual con el resto del pipeline

- **Cross-Module AP Buffer** (§ 2.1): acumula candidatos de los 3
  `source_system` antes de intentar resolver padres — permite que la
  resolución de padre sea un paso único, no repetido por origen.
- **`finalize_action_plans`** (§ 2.1, nombre propuesto): solo procesa
  registros en estado `RESOLVED` o `NOT_REQUIRED`. Los `UNRESOLVED`
  quedan fuera del CSV de ese lote hasta resolverse — a diferencia de
  C003, que los incluye con el campo vacío.
- **Evidence**: cada transición de estado (`RESOLVED`/`UNRESOLVED`/
  `AMBIGUOUS`) queda en el manifest/evidence del lote, igual que C003 ya
  hace (ver `c003-knowledge-adoption.md` § 6, patrón de manifest
  reutilizable) — el EMF adopta ese hábito de evidencia, no la política
  de "exportar igual".
- **Readiness/validation**: un lote con AP en estado `UNRESOLVED` no
  debería marcarse `READY_FOR_ACTIVATION`/listo para carga sin que un
  humano confirme que aislarlos es aceptable para ese lote concreto.

## 4. Attachments — componente transversal futuro (Fase 10, continuación)

Conocimiento ya separado en `c003-knowledge-adoption.md` § 5. Diseño
propuesto del componente (no implementado):

```
CanonicalAttachmentReference
  source_system + source_object_type + source_record_id  (mismo
    esquema de identidad de § 1.2 — un adjunto pertenece a un registro)
  report_type            # ej. 8 para Action Plans; otros valores para
                          # otros módulos (Eventos, Inspecciones...)
  file_name               # validado: no vacío, longitud razonable
  uri                      # validado como URI bien formada, no solo
                          # "no vacío" (C003 valida "no vacío" pero no
                          # valida forma de URI)
  visible: bool
  evidence: {source_document_id, sha256}
  parent_relationship: (mismo estado RESOLVED/UNRESOLVED/... de § 3)
```

- **Escaping**: la composición HTML (`<a href="...">...</a>`) debe
  escapar `WebUrl` y `FileName` antes de insertarlos en el marcado — la
  ausencia de esto es exactamente el defecto confirmado en C003
  (`C003-AP-020`).
- **Deduplication**: clave compuesta (`source_record_id`, `report_type`,
  `uri`) — ya el patrón que C003 usa para su propio diccionario interno
  (`"$legacyActionRaw|$webUrl"` en `Run-Pilot.ps1`), reutilizable como
  concepto.
- **AP-specific vs. transversal**: la regla `report_type=8` es
  específica de Action Plans; el resto del componente (validación de
  URI, escaping, deduplicación, lineage) es transversal — aplica a
  cualquier módulo con adjuntos (8 de los 11 ETL de Sprint 8.8 usan el
  mismo patrón `TablaAdjuntos`).

## 5. SIMS — origen 12 (Fase 9)

Evidencia reunida (C003 + ETL + `config/modules.yaml`):

- **C003** (`sql/30-generic-action-plans.sql` L182, ver
  `c003-knowledge-adoption.md` `C003-AP-009`): el origen `SIMS`/`12`
  ("Simulacros") tiene `SourcesValue = '\BC\Crisis\CrisisActionPlan'` y
  `LinkTargetColumn = NULL` — es decir, **no** enlaza a través de ningún
  campo directo del AP (ni `CS_Drills` ni otro); el enlace ocurre, según
  el propio valor de `Sources`, a través del objeto `Crisis` (BCM) y su
  propia relación con planes de acción, no directamente con el registro
  de Simulacro. El origen `SIMS`/`18` ("O-SIMULACROS-MANUALES", AP
  manuales) sí enlaza vía `CS_Drills`.
- **ETL** (Sprint 8.8, `AP-Con Ajuste Entidad` — hoja `Import_XML_AP`):
  confirma la existencia de la columna `CS_Drills` en el Project
  Contract Template de AP, coherente con el origen 18, no con el 12.
- **`config/modules.yaml`**: `idorigenac_por_modulo::simulacros: [12, 18]`
  — ya tenía ambos IDs, sin distinguir el mecanismo de enlace de cada
  uno.

**Conclusión (parcial, no forzada):** el origen 12 (Simulacros
"automáticos", vinculados vía flujo del sistema) no se enlaza al AP a
través de un campo del propio AP — se enlaza indirectamente vía el
objeto `Crisis`. El origen 18 (Simulacros manuales) sí. Esto **no se
cierra como `RESOLVED`** porque no se ha verificado contra un CSV
Operational real de AP que contenga filas de origen 12 con `BCCrisis`
poblado y `CS_Drills` vacío — sería la confirmación final. Se registra
como `PARTIAL_MATCH` en `config/knowledge/moeve/ap/unresolved-rules.yaml`,
con la hipótesis concreta arriba, no como pregunta abierta sin pistas
(que era el estado hasta este sprint).

## 6. Rejects (Fase 11)

**Reclasificación respecto a la premisa del encargo:** el encargo asume
"C003 crea/consulta `rej.ActionPlan` pero ningún SQL inserta rejects" →
`LEGACY_INOPERATIVE`. La evidencia real es más precisa:
`rej.ActionPlan` (tabla), `rejects.csv` (export) y el gate `AllowPartial`
(`Run-Pilot.ps1` L464-466) **sí están conectados entre sí y son código
activo** — simplemente **ninguna regla de negocio implementada hoy en
`BuildActionPlansITPII2`/`BuildActionPlansGeneric` produce una fila de
rechazo** (todo lo que entra en el alcance SQL se acepta). Es
infraestructura preparada y correctamente cableada, sin ningún caso de
uso que la dispare todavía — no es código muerto heredado de otro
sistema. Se clasifica `SCAFFOLDED_BUT_UNUSED`, no `LEGACY_INOPERATIVE`.

**Diseño EMF propuesto** (reutilizando, no copiando, el mismo esqueleto):

| Concepto C003 | Equivalente EMF propuesto |
|---|---|
| `rej.ActionPlan` (tabla SQL, vacía) | `ValidationIssue` — modelo ya implícito en `src/export/prototype/drills/validator.py`/`issues.jsonl` (Sprint 8.1) — **reutilizar ese modelo**, no crear uno nuevo específico de AP |
| `event-link-warnings.csv` | Un `ValidationIssue` de severidad `warning`, tipo `UNRESOLVED_PARENT` (ver § 3) |
| Rechazo por `AllowPartial` no concedido | Un `ValidationIssue` de severidad `blocking` |
| `attachment-mapping-rejects.csv` | Un `ValidationIssue` de severidad `warning`/`blocking` según el campo faltante, tipo `INVALID_ATTACHMENT_REFERENCE` |

No se crea un segundo sistema de errores — se extiende el ya existente
(`issues.jsonl`/`validator.py`) con los tipos de issue que Action Plans
necesita (`UNRESOLVED_PARENT`, `INVALID_ATTACHMENT_REFERENCE`,
`AMBIGUOUS_PARENT`), consistente con Fase 11 del encargo ("Reutilizar
modelos existentes si ya existen").

## 7. `AllowPartial` (Fase 12)

**Evidencia:** `Start-ActionPlansUI.ps1` (L126, L131) añade
`-AllowPartial` a **toda** invocación lanzada desde la UI WPF, sin
checkbox ni confirmación — el usuario de la UI nunca decide esto
conscientemente, a diferencia de un operador de la CLI que debe escribir
el flag explícitamente. Los scripts CLI (`Run-Pilot.ps1`,
`Run-ActionPlans.ps1`) sí lo exponen como una decisión consciente
(`switch` explícito, con el README advirtiendo "su CSV no debe enviarse
a Enablon como lote final").

**Política EMF propuesta:**

- La política de ejecución (permitir parcial / bloquear en cualquier
  rechazo) **procede del Project Contract o de configuración
  versionada**, nunca de un estado por defecto de la UI.
- Una futura UI del EMF **nunca** debe adjuntar un flag de este tipo de
  forma incondicional — si expone la opción, debe ser una decisión
  explícita y visible del operador en cada ejecución (checkbox
  desmarcado por defecto, o requerir confirmación con texto, no un
  parámetro oculto en la llamada de fondo).
- Ejecución parcial autorizada debe quedar en el `Evidence`/manifest del
  lote de forma tan visible como cualquier otro parámetro — igual que
  C003 sí documenta `RejectedRows` en su manifest (eso es correcto y se
  mantiene), la ausencia de rechazo bloqueante debe ser trazable a
  "quién lo autorizó y cuándo", no solo "cuántos se saltaron".

## 8. Project Contract AP (Fase 8)

### 8.1 Los números en contexto

- C003 usa la plantilla fija de 69 columnas (`out.ActionPlan` en
  `sql/00-setup.sql` — Entity … CS_ReasonForExtension), la misma
  plantilla que la hoja `Import_XML_AP` del ETL (Sprint 8.8).
- La evidencia EMF de `CSV_Enablon_Operational` (Sprint 8.8,
  `moeve-source-inventory.md` § 6.6) observa 3 exports reales con
  31-33 columnas cada uno.

**No se adopta la plantilla de 69 columnas** — sigue el mismo principio
ya fijado en `project-contract-model.md`: el EMF construye el Project
Contract (lo que el cliente realmente carga), no el Platform Contract
(lo que Enablon podría aceptar).

### 8.2 Por qué existe la diferencia 69 vs. 31-33 (no se asume error)

Comparando la plantilla de C003 (69, `out.ActionPlan`) contra un export
Operational real (33 columnas, `Action Plans-10082026-163.csv`, Sprint
8.8):

| Categoría | Ejemplos | Explicación de la diferencia |
|---|---|---|
| `SYSTEM`/`ENABLON_AUTOMATIC` | `Id` | Asignado por Enablon tras la carga — nunca en un CSV previo a la carga |
| `NON_IMPORTABLE`/no usado en este proyecto | `MapsData`, `BCCrisis`, `CS_ByPasses`, `MoCChange`, `CS_MoCFaults`, `AnalysisChecklist`, `Question`, `MocRiskAssessments`, `PHA`, `Node`, `SRM*`, `ACSCampaign`, `EMSHazardsAnalysis`, `AnalysisErgo`, `ICIndicators`, `RMLocalRisks`, `RCA*`, `ApplyTimeLag` (en C003 sí se rellena, en el Operational real no aparece), `AbandonedDate`, `CS_CancellationReason`, `CS_ExtensionApprover`, `CS_ResponsibleAgreement`, `ResultOfEffectivenessReview`, `EffectivenessComment*` (5 idiomas), `IDChangeBeforeUpload` (explícitamente excluida por ambos, ETL y C003) | Columnas del Platform Contract de Action Plans (funcionalidades de Enablon — checklists de riesgo, integraciones con otros módulos) que este proyecto de migración histórica no usa — coherente con `project-contract-model.md` § 2.1 |
| `CUSTOM_CS` presentes en ambos | `CS_HistoricalRecord`, `CS_HistoricalDataOrigin`, `CS_HistoricalAPID`, `CS_HistoricalOriginID`, `CS_HistoricalUserId`, `CS_HistoricalUserName`, `CS_HistoricalTeam`, `CS_HistoricalAttachments` | Núcleo de trazabilidad histórica — presentes en C003, en el ETL y en el Operational real |
| `LEGACY_C003` (presentes en C003, sin confirmar si el cliente los usa) | `TeamMembers`, `CS_SpecifyEffectivenessReviewer`, `CS_ReasonForExtension` | C003 las rellena; no se confirmó su presencia en los 3 exports Operational muestreados en Sprint 8.8 (serían necesarios los 33/31/31 nombres de columna exactos, no solo el conteo, para confirmar — pendiente, ver backlog) |

**No se considera automáticamente un error** — la diferencia es, en su
mayoría, exactamente la distinción Platform/Project Contract que
`project-contract-model.md` ya predice. La pieza pendiente es confirmar,
columna por columna (no solo por conteo), los 3 exports Operational
reales contra esta tabla — backlog nuevo, ver
`moeve-mapping-backlog.md`.

## 9. `MappingSet` AP — diseño, no publicación definitiva (Fase 14)

Las 30 reglas de `c003-knowledge-adoption.md` § 2 se representarían, si
se aprueban, usando los `rule_type` ya existentes:

| C003 rule | `rule_type` |
|---|---|
| `C003-AP-001` (entidad) | `lookup` (contra un `ResourceResolver` resource, no miles de filas embebidas en el `MappingSet` — ver abajo) |
| `C003-AP-002`/`003`/`004`/`005`/`006` | `direct` o `constant` según el caso |
| `C003-AP-007` | `conditional` (enrutado por `LinkTargetColumn`) |
| `C003-AP-012` (Priority) | `conditional` + `lookup` (directo para 438, condicional por fecha para 439-441) |
| `C003-AP-013`/`014`/`015`/`016` | `conditional` |
| `C003-AP-017` | `registered_transform` (limpieza de texto, mismo espíritu que `titlefix`) |
| `C003-AP-018` | `concatenate` |
| `C003-AP-019`/`020` | `reference` (adjuntos) — **sin** el defecto de escaping, ver § 4 |
| `C003-AP-021` | `date_conversion` |
| `C003-AP-025` (Owner) | `lookup` |
| `C003-AP-028`/`029` | Fuera del `MappingSet` — son reglas de **alcance** (scope), no de mapeo de campo; pertenecen a la definición del lote, no a `MappingRule` |

**Catálogos gobernados, no embebidos:** `cfg.ActionPlanEntity` (cientos
de filas Centro+Unidad→Entidad), `cfg.ActionPlanFlowOrigin` (15 filas,
manejable embebido si se quiere, pero mejor como resource por
consistencia), `cfg.ActionPlanPriority` (4 filas) — todos se
representarían como recursos gobernados por `ResourceResolver`
(`src/core/` ya existente, ver commits recientes "add manifest-driven
resource resolver"), nunca como listas literales dentro de un YAML de
`MappingSet`.

**No se publica un `MappingSet` definitivo** — quedan P1 abiertos
(`KC-AP-001` sin cerrar, identidad de AP sin decisión final, § 1.3,
Project Contract sin confirmar columna a columna, § 8.2). Lo que este
sprint entrega es el **draft** de arriba, no un YAML ejecutable.

## 10. Diseño del Adaptador AP nativo (Fase 15)

Debe:

- Ser un consumidor del Framework Core — `ModuleRegistry` (ya existe,
  commit reciente "add explicit module registry"), `WorkspaceManifest`
  (ya existe), `ResourceResolver` (ya existe), respetar el `SQL
  Execution Guard` (`src/db/sql_execution_guard.py`, ya existe) igual
  que cualquier otro módulo.
- Consumir Canonical Records de **múltiples** `source_object_type` (a
  diferencia de Drills) — ver § 2.
- Resolver relaciones de padre según la política de § 3 antes de
  finalizar cualquier registro.
- Usar un `MappingSet` (§ 9, cuando se apruebe) en vez de lógica de
  transformación embebida en código Python, siguiendo ADR-013.
- Producir un Project Contract propio (§ 8), no el Platform Contract
  completo.
- Generar `Evidence` con el mismo nivel de detalle que ya generan
  Drills (Sprint 8.1) y, de forma independiente, C003 (manifest.json) —
  ambos coinciden en qué hace falta (hashes, reglas aplicadas como
  texto, conteos de alcance/exportado/rechazado).
- Soportar múltiples `source object types` desde el primer incremento —
  no como ampliación posterior (a diferencia de Drills, donde un único
  origen fue una decisión de alcance válida).

No debe:

- Depender de WPF, PowerShell ni `sqlcmd` directo — el EMF ya tiene su
  propia capa de conexión SQL de solo lectura (`src/db/connection.py`).
- Usar una base de datos de staging al estilo `C003_Migration` — el EMF
  no escribe en SQL Server en ningún punto de su diseño actual (es
  analítico/generador de CSV, ver `CLAUDE.md`); si se necesita estado
  intermedio, debe vivir en `outputs/` versionado y auditable, no en una
  base de datos nueva.
- Usar estado global, rutas absolutas ni asumir Moeve en el Core — el
  Adaptador AP es un consumidor del Core, el Core permanece agnóstico de
  cliente (ADR-012).

**`PipelineStages` propuestas** (nombres conceptuales, sin firma de
código):

1. `ExtractActionPlanCandidates` — por `source_system`/`source_object_type`,
   usando las queries ya versionadas en `sql/source_queries/AP/`.
2. `CanonicalizeActionPlan` — produce un Canonical Record por candidato,
   con la identidad de § 1.2.
3. `BufferCrossModuleActionPlans` — acumula candidatos de todos los
   orígenes de un lote (el "Cross-Module AP Buffer" de § 2).
4. `ResolveParentRelationships` — aplica la política de § 3, produce
   `RESOLVED`/`UNRESOLVED`/`AMBIGUOUS`/`NOT_REQUIRED`.
5. `ApplyActionPlanMappingSet` — aplica el `MappingSet` de § 9 a los
   registros `RESOLVED`/`NOT_REQUIRED`.
6. `FinalizeActionPlans` — el paso conceptual `finalize_action_plans` de
   § 2: reglas transversales finales (limpieza de nombre, formato de
   fecha, adjuntos escapados correctamente).
7. `ValidateActionPlanBatch` — usando el modelo de `ValidationIssue`
   extendido de § 6, no un sistema nuevo.
8. `WriteActionPlanProjectContract` — CSV + manifest/evidence.

## 11. UI futura (Fase 16)

**No se implementa.** `Start-ActionPlansUI.ps1` (C003) se registra
únicamente como prototipo histórico — confirma un patrón correcto (UI
= construcción de comando + lanzamiento de proceso, sin lógica de
negocio embebida en la UI misma) y un patrón incorrecto a no repetir
(`AllowPartial` forzado, § 7).

Requisitos mínimos antes de cualquier UI EMF futura:

- **Readiness API**: consulta si un lote está listo para generar,
  reutilizando el patrón ya existente de "workspace readiness
  validator" (commit reciente).
- **Run API**: dispara la ejecución del pipeline de § 10 — nunca SQL
  directo desde la UI.
- **Status/progress**: consulta de estado, no push — evita el patrón de
  C003 de abrir una terminal nueva sin canal de estado estructurado.
- **Cancellation**: explícita, con estado intermedio auditable (no
  existe en C003 — el proceso, una vez lanzado, no se puede cancelar
  desde la propia UI).
- **Evidence API**: consulta de manifest/evidence de una ejecución
  pasada — C003 sí lo permite ("Abrir última ejecución"/"Abrir
  ejecuciones"), patrón correcto a mantener.
- **Workspace/resource browsing**: vía `WorkspaceManifest`/`ResourceResolver`,
  no diálogos de archivo apuntando a rutas arbitrarias del sistema
  operativo (C003 usa `OpenFileDialog` sin restricción de carpeta).
- **Explicit authorization**: cualquier flag equivalente a
  `AllowPartial` requiere una acción explícita y visible, nunca un
  parámetro por defecto (§ 7).
- **No business logic in UI**: mantener el único patrón que C003 ya
  hace bien — la UI construye una solicitud, nunca decide una regla de
  negocio.

La UI debe ser *thin client* — la validación de campos numéricos
(`Centers`/`Units` en C003) y la resolución de flujos ya viven,
correctamente, fuera de la UI en C003; ese patrón se mantiene.

## 12. Historial de revisión

- Sprint 8.9 (2026-08-12): creación. Primer diseño del Adaptador AP
  nativo, basado en evidencia C003 + Sprint 8.8/8.8.1.
