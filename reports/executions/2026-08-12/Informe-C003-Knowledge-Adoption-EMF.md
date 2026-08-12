# Informe de Ejecución — Sprint 8.9: C003 Knowledge Adoption & Action Plans Native Design

**Fecha:** 2026-08-12
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Incorporación de conocimiento funcional descubierto en C003
(`C:\Users\EduardoVelásquez\Desktop\C003-ActionPlans-Tool-v3\`, herramienta
nativa que reemplaza el ETL Excel de Action Plans) al modelo de
conocimiento del EMF, y diseño arquitectónico del futuro adaptador AP
nativo. C003 no se integra, no se ejecuta, no se copia su runtime. Sin
ejecución de SQL Server. Sin commit — Sprint 8.8 y 8.8.1 siguen
pendientes de commit.

## 1. Resumen ejecutivo

C003 es una reimplementación nativa (T-SQL + PowerShell + Python, sin
Excel salvo una extracción puntual y única de configuración) del proceso
de Action Plans, construida para corregir defectos ya conocidos del ETL
Excel. Se inspeccionó en solo lectura (código fuente, 1 `manifest.json`
real de estructura, ningún dato de fila de `runs/`) y se reconstruyeron
30 reglas de mapeo con evidencia textual exacta (archivo + línea). Se
reconciliaron contra el conocimiento ya acumulado en Sprint 8.8/8.8.1: 1
ítem de backlog se cerró (`P2-06`), 3 reglas coinciden con evidencia ya
validada, y el resto se incorpora como conocimiento nuevo sin
promocionarse a `CURRENT_VERIFIED` sin más verificación.

Se diseñó (no implementó) el futuro Adaptador AP nativo:
`docs/01-architecture/action-plans-native-design.md` — identidad global
de AP, AP como objeto transversal, política de relaciones de padre,
reconciliación del Project Contract (69 vs. 31-33 columnas), diseño del
`MappingSet`, `PipelineStages` propuestas, y requisitos mínimos de una
UI futura. Se abrieron 5 nuevos ítems de backlog de diseño (`P1-11` a
`P1-13`, `P2-09`, `P2-10`).

Se resolvió finalmente el estado de los 5 documentos de Sprint 8.1 (§ 21
de este informe) — ninguno se elimina sin autorización explícita.

## 2. Reglas C003

30 reglas reconstruidas por lectura estática de código real (`sql/*.sql`,
`Run-Pilot.ps1`, `Run-ActionPlans.ps1`, `Extract-*.py`), con archivo y
línea citados para cada una. Tabla completa en
`docs/07-developer-guide/c003-knowledge-adoption.md` § 2. **Nota
importante:** el encargo asumía la existencia de un assessment previo
("Codex") que ya habría identificado estas 30 reglas — ese documento no
estaba disponible en esta sesión; el inventario es una reconstrucción
propia e independiente, no un cotejo contra ese assessment.

Estados iniciales usados (nunca `CURRENT_VERIFIED` solo por ejecutarse en
C003): 3 `MATCHES_CURRENT_EVIDENCE`, ~15 `HISTORICAL_VERIFIED`/`NEW_KNOWLEDGE`
con evidencia de código fuerte, 1 `CONFLICT` (generación HTML de
adjuntos sin escapar), el resto `NEW_KNOWLEDGE` sin verificación cruzada
todavía.

## 3. Reconciliación

Tabla completa en `c003-knowledge-adoption.md` § 3. Resultado más
relevante: `cfg.ActionPlanFlowOrigin` (C003) da el mapeo exacto
`FlowCode`+`idorigenac` → `Sources`/columna de enlace de padre para los
8 flujos de AP — cierra el backlog `P2-06` de Sprint 8.8 ("mapeo exacto
a `idorigenac` no confirmado"), coincide con `config/modules.yaml` en
los IDs ya conocidos y añade `HAZOPS=6`, no documentado antes.

## 4. Conocimiento nuevo

- Namespace inconsistente de `CS_HistoricalAPID` entre el piloto ITPII2
  (`ITPII2.<id>`) y los 8 flujos genéricos (sin prefijo) — motiva el
  diseño de identidad global de § 7.
- Reglas de `Status`/`LevelNo` por finalización (`FechaRealFin`).
- Concatenación etiquetada de `DetailedDescription` (Nombre + Descripción
  + Orden de trabajo + Coste + Proyecto + Evidencias).
- Formato de fecha exacto `dd/MM/yyyy H:mm` (sin cero a la izquierda en
  la hora).
- Regla de desempate para eventos duplicados en el cruce (Id numérico de
  Enablon más alto gana).
- Resolución de `Owner` vía email (`ITP_USUARIOS_map` × `UsersEnablon_PROD`).
- Hash de fila (SHA2_256) para detección de cambios, por fila — más
  granular que el hash de fichero completo que ya usa el EMF.

## 5. Conflictos

| ID | Estado | Resumen |
|---|---|---|
| `KC-AP-001` | `OPEN` (tercera confirmación) | C003 extrae explícitamente `Entidades_Mapeo` por nombre de hoja — ni la reimplementación nativa más reciente adoptó el catálogo vivo. No cierra el conflicto. |
| `C003-AP-020` (generación HTML sin escapar) | `CONFLICT` con buena práctica esperada | Defecto real confirmado — no se hereda, ver § 9 |
| (nuevo, informativo) `AllowPartial` forzado desde UI | No es un `KNOWLEDGE_CONFLICT` formal, es un antipatrón a documentar | Ver § 10 |

## 6. `KC-AP-001`

Ver § 3 y `config/knowledge/moeve/ap/knowledge-conflicts.yaml`
(`status_note_8_9`). La pregunta pendiente no cambia respecto al cierre
de Sprint 8.8.1: si los ETL/procesos de ámbito ITP-genérico se
resincronizaron con el catálogo vivo después de la "version 4" del
workbook dedicado, o quedaron congelados en ella. C003 aporta una
tercera fuente independiente en la misma dirección (usa `Entidades_Mapeo`),
sin decidir la pregunta.

## 7. Identidad AP

Diseño propuesto (no implementado) en `action-plans-native-design.md`
§ 1: 4 identificadores distintos — identidad global
(`source_system.source_object_type.source_record_id`), identidad local
(`IDAccionCorrectora`/`IDAccion` tal cual), historical identifier
(`CS_HistoricalAPID` proyectado desde la identidad global) y
display/reference identifier (`Id` de Enablon, post-carga). No se
modifica el CDM — no se encontró una contradicción real, solo una
ausencia de patrón de identidad compuesta que Drills (un solo origen) no
necesitó. Pendiente de decisión humana: si namespacear
`CS_HistoricalAPID` retroactivamente o solo hacia adelante (backlog
`P1-11`).

## 8. Flujos

Matriz completa en `action-plans-native-design.md` § 2.2: 8 `FlowCode`
de C003 + el piloto ITPII2 + MOC/GCT (no cubierto por C003), 15
combinaciones flujo+origen, cruzadas contra `config/modules.yaml`. 3
orígenes (`HAZOPS`, 2 de `OTROS`) sin módulo EMF equivalente confirmado
— quedan `UNKNOWN`, no se inventa uno. **No se asume que los nombres de
flujo de C003 deban convertirse en módulos EMF** — la tabla los
emparienta por tabla origen, no por decreto.

## 9. Relaciones de padre

Antipatrón confirmado en C003 (`event-link-warnings.csv`): un AP con
padre no resuelto se exporta igual, con referencia vacía y una
advertencia en fichero aparte — comportamiento por defecto, no una
excepción consciente. Política EMF propuesta (`action-plans-native-design.md`
§ 3): 4 estados (`RESOLVED`/`UNRESOLVED`/`AMBIGUOUS`/`NOT_REQUIRED`), un
AP `UNRESOLVED` **no** finaliza en el lote — se aísla, nunca se
convierte silenciosamente en referencia vacía. Backlog `P1-12`.

## 10. Project Contract

C003 usa la plantilla fija de 69 columnas (idéntica a la hoja
`Import_XML_AP` del ETL). La evidencia EMF observa 31-33 columnas reales
en los exports Operational. **No se adopta la plantilla de 69** — se
clasificó la diferencia (`action-plans-native-design.md` § 8): en su
mayoría son columnas `NON_IMPORTABLE`/no usadas por este proyecto
(checklists de riesgo, integraciones con otros módulos de Enablon), no
un error. 3 columnas (`TeamMembers`, `CS_SpecifyEffectivenessReviewer`,
`CS_ReasonForExtension`) quedan `LEGACY_C003` — presentes en C003, sin
confirmar en los exports Operational reales por nombre exacto de
columna, no solo por conteo. Backlog `P1-13`.

## 11. SIMS

Origen `12` ("Simulacros", automáticos): C003 fija `Sources =
'\BC\Crisis\CrisisActionPlan'` y `LinkTargetColumn = NULL` — no enlaza
vía ningún campo directo del AP, a diferencia del origen `18`
("O-SIMULACROS-MANUALES"), que sí enlaza vía `CS_Drills`. Hipótesis
concreta: el origen 12 se vincula indirectamente a través del objeto
`Crisis` (BCM). No verificado contra un CSV Operational real — se
registra como `PARTIAL_MATCH`, no como pregunta sin pistas (era el
estado hasta este sprint). Backlog `P2-09`.

## 12. Attachments

Separación conocimiento/implementación en
`c003-knowledge-adoption.md` § 5: la regla de clave compuesta
(`Idinforme`+`Tipo de Informe=8`+`Visible=1`) es conocimiento funcional
confirmado y reutilizable. La generación HTML **sin escapar**
`WebUrl`/`FileName` es un defecto real, confirmado en ambos
procedimientos SQL de C003 — **no se hereda**. Diseño del componente
transversal futuro en `action-plans-native-design.md` § 4 (identidad,
validación de URI, escaping, deduplicación, lineage), con la porción
`report_type=8` marcada explícitamente como específica de AP y el resto
como transversal (aplica a 8 de los 11 ETL de Sprint 8.8).

## 13. Rejects

**Reclasificación respecto a la premisa del encargo:** no es
`LEGACY_INOPERATIVE` sin más — `rej.ActionPlan`, `rejects.csv` y el gate
`AllowPartial` están correctamente cableados entre sí y son código
activo; simplemente ninguna regla de negocio implementada hoy produce
una fila de rechazo. Se clasifica `SCAFFOLDED_BUT_UNUSED`. Diseño
propuesto: reutilizar el modelo `ValidationIssue`/`issues.jsonl` ya
existente en el EMF (Drills, Sprint 8.1), extendido con 3 tipos nuevos
(`UNRESOLVED_PARENT`, `INVALID_ATTACHMENT_REFERENCE`, `AMBIGUOUS_PARENT`)
— no se crea un segundo sistema de errores.

## 14. `AllowPartial`

Hallazgo concreto: `Start-ActionPlansUI.ps1` (líneas 126 y 131) añade
`-AllowPartial` a **toda** invocación lanzada desde la UI WPF, de forma
incondicional — sin checkbox, sin confirmación. Los scripts CLI sí lo
exponen como decisión consciente del operador. Política EMF propuesta:
la decisión de permitir ejecución parcial procede del Project
Contract/configuración versionada, nunca de un valor por defecto de la
UI; si una futura UI la expone, debe requerir una acción explícita y
visible en cada ejecución.

## 15. `MappingSet`

Draft, no publicación definitiva (quedan P1 abiertos):
`action-plans-native-design.md` § 9 mapea las reglas C003 más
verificadas contra los `rule_type` ya existentes de
`mapping-specification.md` (`lookup`, `direct`, `constant`, `conditional`,
`registered_transform`, `concatenate`, `reference`, `date_conversion`).
Los catálogos (`cfg.ActionPlanEntity`, `cfg.ActionPlanFlowOrigin`,
`cfg.ActionPlanPriority`) se representarían como recursos gobernados por
`ResourceResolver`, nunca embebidos como filas en el `MappingSet`.

## 16. Algoritmos reutilizables

Tabla completa en `c003-knowledge-adoption.md` § 6. Destacados:
`ALREADY_EXISTS` (hash de integridad, patrón de manifest declarativo,
extracción de Excel vía XML crudo sin `openpyxl`/COM — todos coinciden,
de forma independiente, con patrones ya presentes en el EMF);
`REUSE_CONCEPT` (resolución de entidad con comodín de especificidad,
enrutado dinámico de columna destino, concatenación etiquetada,
desempate determinista de duplicados); `DO_NOT_USE` (HTML sin escapar,
tabla de rejects vacía copiada tal cual).

## 17. Diseño del Adaptador AP

`action-plans-native-design.md` § 10: consumidor del Framework Core
(`ModuleRegistry`, `WorkspaceManifest`, `ResourceResolver`, SQL
Execution Guard — todos ya existen en el repositorio), soporta múltiples
`source_object_type` desde el primer incremento (no como Drills), 8
`PipelineStages` conceptuales (`ExtractActionPlanCandidates` →
`CanonicalizeActionPlan` → `BufferCrossModuleActionPlans` →
`ResolveParentRelationships` → `ApplyActionPlanMappingSet` →
`FinalizeActionPlans` → `ValidateActionPlanBatch` →
`WriteActionPlanProjectContract`). No depende de WPF/PowerShell/`sqlcmd`
ni de una base de datos de staging al estilo `C003_Migration`.

**Nota de honestidad:** el encargo citaba "ADR-003 Action Plans Cross
Module" como si ya existiera — no existe en este repositorio (`docs/02-adr/`
llega hasta `ADR-016`). Se documenta explícitamente en
`action-plans-native-design.md` § 0 en vez de fingir una integración con
algo que no está ahí. Si se aprueba este diseño, correspondería
`ADR-017`.

## 18. UI futura

Pospuesta, como pedía el encargo. C003 confirma un patrón correcto (UI
= construcción de comando, sin lógica de negocio embebida) y uno
incorrecto a no repetir (`AllowPartial` forzado). 8 requisitos mínimos
listados en `action-plans-native-design.md` § 11 antes de cualquier UI
EMF futura.

## 19. Coverage

No se publica un nuevo porcentaje — sigue la misma metodología (y la
misma razón para no publicarlo) fijada en `moeve-mapping-backlog.md`
§ 1 desde Sprint 8.8. C003 aporta reglas nuevas de campo pero no cierra
la verificación celda-a-celda pendiente en 7 de 9 módulos.

## 20. Backlog

24 ítems abiertos (era 20 tras Sprint 8.8.1): 1 cerrado en este sprint
(`P2-06`), 5 nuevos (`P1-11`, `P1-12`, `P1-13`, `P2-09`, `P2-10`). Tabla
completa de evolución en `moeve-mapping-backlog.md` § 3.

## 21. Estado de Sprint 8.1 (resolución final)

| Documento | Decisión final |
|---|---|
| `docs/01-architecture/knowledge-traceability-matrix.md` | **`UPDATE_AND_COMMIT`** — ya actualizado en Sprint 8.8.1 (`OQ-ETL-01`/`02` `RESOLVED`, filas 🟡→🟢); incluir en la propuesta de commit de § 25 |
| `docs/01-architecture/drills-csv-contract.md` | **`KEEP_AND_COMMIT`** — sigue siendo una descripción correcta de las 8 columnas implementadas; no requiere cambio de contenido |
| `docs/01-architecture/knowledge-coverage-matrix.md` | **`KEEP_AND_COMMIT`** — su alcance (código/config) no cambia por Sprint 8.8/8.8.1/8.9 |
| `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md` | **`ARCHIVE`** — informe de ejecución puntual, registro histórico inmutable; su tabla de cobertura usa un denominador (Template 8/36) superado por `project-contract-model.md` (posterior), pero no es un error, no se edita retroactivamente |
| `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt` | **`ARCHIVE`** — misma razón |

Ninguno se elimina — `DELETE_CANDIDATE` no se aplicó a ninguno. Los 5
quedan listos para incluirse en la propuesta de commit combinada (§ 25),
pendiente de aprobación del usuario.

## 22. Riesgos

- El "assessment de Codex" citado en el encargo no estaba disponible —
  si existe y numera las 30 reglas de forma distinta, ambos inventarios
  deben reconciliarse en una sesión futura.
- Ningún dato real de `runs/` de C003 se leyó más allá de un
  `manifest.json` (solo estructura) — cualquier conclusión sobre volumen
  real de datos no se puede sostener con lo inspeccionado.
- El diseño del Adaptador AP (§ 17) es conceptual — no se ha validado
  contra una implementación real, ni siquiera un prototipo.

## 23. Decisiones requeridas

1. `KC-AP-001` — confirmar con el cliente si los ETL ITP-genérico se
   resincronizaron con el catálogo vivo después de la "version 4".
2. `P1-11` — política de namespace para `CS_HistoricalAPID` (retroactiva
   o solo hacia adelante).
3. `P1-12` — aprobar la política de padres no resueltos propuesta
   (bloquear/aislar en vez de exportar vacío).
4. Confirmar con el cliente si el documento de asunciones/procedimientos
   encontrado en el zip de Mappings (Sprint 8.8.1) ya le fue entregado
   (ticket `#7581`).
5. Aprobar (o no) la propuesta de commit combinada de § 25.

## 24. Roadmap propuesto (no vinculante)

1. Cerrar `P1-13` (Project Contract AP columna a columna) — desbloquea
   publicar un `MappingSet` AP real.
2. Confirmar `P1-11`/`P1-12` con el cliente — desbloquea el diseño de
   identidad y la política de padres.
3. Implementar el Adaptador AP nativo siguiendo `action-plans-native-design.md`
   § 10, empezando por `ExtractActionPlanCandidates`/`CanonicalizeActionPlan`
   para un solo `source_system` (ITP-genérico) antes de añadir los otros
   2.
4. Formalizar `ADR-017` si el diseño de identidad/transversalidad se
   aprueba tal cual.

## 25. Archivos creados

```
docs/01-architecture/action-plans-native-design.md
docs/07-developer-guide/c003-knowledge-adoption.md
reports/executions/2026-08-12/Informe-C003-Knowledge-Adoption-EMF.md
reports/executions/2026-08-12/Informe-C003-Knowledge-Adoption-EMF.txt
```

## 26. Archivos modificados

```
docs/01-architecture/mapping-governance.md          (§ 13 nueva, renumeración § 11→14)
docs/07-developer-guide/moeve-source-inventory.md    (§ 12 nueva)
docs/07-developer-guide/moeve-mapping-backlog.md     (P2-06 cerrado, 5 ítems nuevos, resumen actualizado)
config/knowledge/moeve/ap/knowledge-conflicts.yaml   (status_note_8_9)
config/knowledge/moeve/ap/source-inventory.yaml      (c003_actionplans_tool)
config/knowledge/moeve/ap/mapping-set.yaml           (3 reglas nuevas)
config/knowledge/moeve/ap/unresolved-rules.yaml      (hipótesis SIMS)
```

`.claude/settings.local.json` sigue apareciendo modificado en `git
status` (permisos de herramientas de sesión) — ajeno a los 3 sprints,
no se incluye en ninguna propuesta de commit.

## 27. Tests

`pytest tests/ -v` → **714 passed, 7 skipped** (idéntico antes y después
de este sprint). No se modificó ni se añadió código funcional. No se
creó ningún parser/helper nuevo en `src/` — toda la evidencia se leyó
con herramientas de sesión (scratchpad), consistente con Sprint 8.8/8.8.1.

## 28. Propuesta de commits (consolidada 8.8 + 8.8.1 + 8.9, no ejecutados)

1. **Mapping governance**: `docs/01-architecture/mapping-governance.md`
   (contenido íntegro de los 3 sprints en un único archivo coherente),
   `docs/01-architecture/knowledge-source-governance.md`.
2. **Moeve source inventory / knowledge**:
   `docs/07-developer-guide/moeve-source-inventory.md`,
   `docs/07-developer-guide/moeve-mapping-backlog.md`,
   `config/knowledge/moeve/ap/` (contenido acumulado de los 3 sprints).
3. **Action Plans native design (nuevo en 8.9)**:
   `docs/01-architecture/action-plans-native-design.md`,
   `docs/07-developer-guide/c003-knowledge-adoption.md`.
4. **Sprint 8.1 — actualización de conocimiento**:
   `docs/01-architecture/knowledge-traceability-matrix.md` (`UPDATE_AND_COMMIT`),
   `docs/01-architecture/drills-csv-contract.md` (`KEEP_AND_COMMIT`),
   `docs/01-architecture/knowledge-coverage-matrix.md` (`KEEP_AND_COMMIT`).
5. **Sprint 8.1 — archivo histórico**:
   `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md`/`.txt`
   (`ARCHIVE` — se commitean tal cual, sin editar, como registro
   histórico).
6. **Código genérico nuevo**: ninguno en los 3 sprints.
7. **Documentación e informes**: los informes de los 3 sprints
   (`Informe-Mapping-Governance-Moeve-EMF.*`,
   `Informe-Knowledge-Closure-Moeve-EMF.*`,
   `Informe-C003-Knowledge-Adoption-EMF.*`).

Ningún dato real de ningún workspace externo (Moeve o C003) se incluye
en ninguno de los commits propuestos.

## 29. `git status --short`

```
 M .claude/settings.local.json
?? config/knowledge/
?? docs/01-architecture/action-plans-native-design.md
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-source-governance.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/mapping-governance.md
?? docs/07-developer-guide/c003-knowledge-adoption.md
?? docs/07-developer-guide/moeve-mapping-backlog.md
?? docs/07-developer-guide/moeve-source-inventory.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt
?? reports/executions/2026-08-12/
```

## 30. `git diff --stat`

```
 .claude/settings.local.json | 18 +++++++++++++++++-
 1 file changed, 17 insertions(+), 1 deletion(-)
```

Único archivo con diff — todo lo demás sin versionar todavía.
`git diff --check`: sin salida, 0 problemas de espacio en blanco.
