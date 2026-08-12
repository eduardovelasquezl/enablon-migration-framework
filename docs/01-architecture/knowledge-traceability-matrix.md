# Knowledge Traceability Matrix — simulacros.Drills

**Status:** Implemented (auditoría, Sprint 8.1). Cubre las **36 columnas
reales** del CSV de Drills (`drills_evidence_assessment.md` § 10), no solo
las 8 implementadas — construida cruzando `config/exports/drills.yaml`,
`src/export/prototype/drills/*.py` y
`docs/specifications/v1.0/export/evidence/traceability_catalog.yaml`
(catálogo documental SQL→ETL→CSV, 9 trazas propias de Drills ya
registradas). Ningún ETL ni CSV real fue reabierto para este documento —
toda "columna ETL" citada aquí ya estaba documentada en
`traceability_catalog.yaml`/`drills_evidence_assessment.md` antes de esta
auditoría.

## Vocabulario de estado

- 🟢 **Totalmente trazable**: origen SQL confirmado, mecanismo de
  transformación confirmado (por código ejecutable o por evidencia de
  fórmula ETL igualmente concluyente), y destino CSV confirmado — sin
  pregunta abierta que bloquee la trazabilidad (aunque pueda quedar una
  pregunta menor no bloqueante).
- 🟡 **Parcialmente trazable**: al menos una etapa (origen, transformación
  o destino) tiene evidencia incompleta, una pregunta abierta relevante, o
  el campo tiene mecanismo confirmado en el ETL pero **no está
  implementado en código**.
- 🔴 **Solo documentado en ETL** (o ni siquiera eso): sin mecanismo SQL/ETL
  confirmado — solo un nombre de columna observado en el CSV real y, como
  mucho, una razón genérica de por qué queda fuera de alcance.

## Matriz completa (36 columnas)

| Campo CSV | SQL | Canonical | Mapping | Transformación | Validation | ETL | Estado |
|---|---|---|---|---|---|---|---|
| `CS_Typology` | `IDTipo` ✓ | N/A (CDM no implementado) | `config/exports/drills.yaml::fields[0]` | `resolve_typology` (código) | `must_resolve_or_use_documented_default` | `trace:simulacros.drills.cs_typology` = `fully_traced` | 🟢 |
| `Reference` | `[IDTipo, IDSimulacro, Fecha]` ✓ (compuesto) | N/A | `fields[1]` | `build_reference` (`AFD-DRILLS-REFERENCE-001`) | patrón regex | `trace:simulacros.drills.reference` = `fully_traced` | 🟢 |
| `StartingDate` | `Fecha` ✓ | N/A | `fields[2]` | `parse_starting_date`/`format_starting_date` | `required_valid_date` | Componente confirmado de la traza `reference` (arriba) | 🟢 |
| `CS_HistoricalOriginID` | `IDSimulacro` ✓ | N/A | `fields[3]` | `to_historical_id` | `required_non_null` | `trace:simulacros.drills.cs_historicaloriginid` = `fully_traced` | 🟢 |
| `CS_Letter` | `IDLetra` ✓ | N/A | `fields[4]` | `resolve_letter` | `warn_if_unresolved` | `trace:simulacros.drills.cs_letter` = `fully_traced` | 🟢 |
| `CS_ImpactedEntities` | `IDUnidadOrg` ✓ | N/A | `fields[5]` | `resolve_entity` | `warn_if_unresolved_or_conflicting` | `trace:simulacros.drills.entity_field` = `fully_traced` (catálogo deprecado, uso aceptado explícitamente, `OQ-ENT-04` no bloqueante) | 🟢 |
| `CS_WorkflowStatus` | `Estado` ✓ | N/A | `fields[6]` | `resolve_workflow_status` | `warn_if_unresolved` | `trace:simulacros.drills.cs_workflowstatus` = `fully_traced` | 🟢 |
| `CS_HistoricalDataOrigin` | Ninguno (constante) | N/A | `fields[7]` | `constant` | `constant_literal` | `evidence_id` declarado (`etl_transform:simulacros.multifielduser.historical_user_lookup`) **coincide literalmente con el `transformation_id` de la traza `cs_historicaluserid`** (un campo distinto, `CS_HistoricalUserId`) — posible reutilización/cita cruzada sin aclarar, no confirmado como error | 🟡 |
| `Id` | — (no aplica) | N/A | `excluded_columns` | — | — | Exclusión **completamente entendida** (ID asignado por Enablon tras la carga) — no es una laguna de conocimiento, es un hecho estructural confirmado | 🟢 |
| `CS_Duration` | `Duracion` ✓ | N/A | `excluded_columns` (no implementado, pero ya no por falta de evidencia) | **RESUELTO Sprint 8.8.1**: passthrough directo (`Adaptación=No` en `MapeoSims`, fila 27 del ETL de Simulacros) — sin recombinación, sin redondeo. La hoja `CalculoHorasDiasMinutos` NO alimenta este campo (alimenta 4 campos separados de `List of Activities`, un objeto distinto) | — | `trace:simulacros.drills.cs_duration_fields` = `fully_traced` (actualizado, ver `mapping-governance.md` § 12.3), `OQ-ETL-02` = `RESOLVED` | 🟢 |
| `CS_HistoricalUserId` | `IDUsuarioUltimaModificacion` ✓ | N/A | `excluded_columns` (excluido por diseño, PII — no por falta de evidencia) | `MultiField_User` (ETL, confirmado) | — | `trace:simulacros.drills.cs_historicaluserid` = `fully_traced` en ETL, pero **sin implementación de código** | 🟡 |
| `CS_HistoricalUserName` | No confirmado separadamente | N/A | `excluded_columns` | Presumiblemente mismo mecanismo que `CS_HistoricalUserId`, sin traza propia | — | Sin `trace_id` propio en `traceability_catalog.yaml` | 🟡 |
| `CS_HistoricalDrillAttendees` | `Asistentes` (passthrough) ✓ + `NombreAsistente` (concat) ✓ | N/A | `excluded_columns` (no implementado, pero ya no por falta de evidencia) | **RESUELTO Sprint 8.8.1**: 2 mecanismos independientes al mismo destino — (1) passthrough directo del texto libre `Asistentes` de `DB_OrigenSim` (`Adaptación=No`, `MapeoSims` fila 35); (2) concatenación fila-a-fila de `NombreAsistente` desde `ITP_ASIST_SIMS`/`ITP_ASIST_SIMS_EXT` vía regla `concat` (`Mapeo_asistentes`/`Mapeo_asistentes_EXT`, `Transformation From=Asis_concat`), que añade sin sobrescribir, separador `\r\n` | — | `trace:simulacros.drills.cs_historicaldrillattendees` = `fully_traced` (actualizado, ver `mapping-governance.md` § 12.3), `OQ-ETL-01` = `RESOLVED` (orden exacto create/update y deduplicación entre los 2 mecanismos quedan como ítem residual menor, ver `moeve-mapping-backlog.md`) | 🟢 |
| `CS_HistoricalDrillResponsibleName` | No confirmado separadamente | N/A | `excluded_columns` | Sin mecanismo propio confirmado | — | Sin `trace_id` propio | 🟡 |
| `NameEN` | No identificado | N/A | `excluded_columns` | `titlefix` + `cloneorigin` fan-out (mecanismo del ETL conocido, pero SQL origen de "Titulo" no confirmado) | — | Sin `trace_id`; solo mencionado en `drills_evidence_assessment.md` § 7 (confianza `high` del mecanismo, no del origen) | 🔴 |
| `NameFR` | No identificado | N/A | `excluded_columns` | (mismo fan-out que `NameEN`) | — | Sin `trace_id` propio | 🔴 |
| `NameES` | No identificado | N/A | `excluded_columns` | (ídem) | — | Sin `trace_id` propio | 🔴 |
| `NameZH` | No identificado | N/A | `excluded_columns` | (ídem) | — | Sin `trace_id` propio | 🔴 |
| `NameBR` | No identificado | N/A | `excluded_columns` | (ídem) | — | Sin `trace_id` propio | 🔴 |
| `GroupsList` | No identificado | N/A | `excluded_columns` (motivo genérico) | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_OtherContacts` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_ExternalParticipants` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_OtherParticipants` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_HistoricalAttachedFiles` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_EnvConsequences` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_FirefightingAndSpillContainment` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_ObservationsFirefighting` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_AttitudeOfPersonnel` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_ObservationsPersonnel` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_StaffTraining` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_ObservationsTraining` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_Communication` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_ObservationsCommunication` | No identificado | N/A | `excluded_columns` | No confirmado | — | Sin `trace_id` | 🔴 |
| `CS_HistoricalRecord` | No identificado | N/A | `excluded_columns` (valor `'Yes'` observado, constancia no confirmada) | No confirmado | — | Sin `trace_id` | 🔴 |
| `EstimatedLoss` | No identificado | N/A | **Ninguna** — ni `fields` ni `excluded_columns` | No confirmado | — | Sin `trace_id`; sin mención en ningún assessment de Drills | 🔴 |
| `RealLoss` | No identificado | N/A | **Ninguna** — ni `fields` ni `excluded_columns` | No confirmado | — | Sin `trace_id`; sin mención en ningún assessment de Drills | 🔴 |

## Resumen numérico (36 campos)

| Estado | Cantidad | Campos |
|---|---:|---|
| 🟢 Totalmente trazable | 10 (+2 desde Sprint 8.8.1) | `CS_Typology`, `Reference`, `StartingDate`, `CS_HistoricalOriginID`, `CS_Letter`, `CS_ImpactedEntities`, `CS_WorkflowStatus`, `Id`, `CS_Duration`, `CS_HistoricalDrillAttendees` |
| 🟡 Parcialmente trazable | 4 (−2 desde Sprint 8.8.1) | `CS_HistoricalDataOrigin`, `CS_HistoricalUserId`, `CS_HistoricalUserName`, `CS_HistoricalDrillResponsibleName` |
| 🔴 Solo documentado en ETL (o ni eso) | 22 | Las 5 `Name*`, `GroupsList`, `CS_OtherContacts`, `CS_ExternalParticipants`, `CS_OtherParticipants`, `CS_HistoricalAttachedFiles`, las 9 columnas de checklist (`CS_EnvConsequences`…`CS_ObservationsCommunication`), `CS_HistoricalRecord`, `EstimatedLoss`, `RealLoss` |

**Nota Sprint 8.8.1:** `CS_Duration` y `CS_HistoricalDrillAttendees`
pasaron de 🟡 a 🟢 tras leer, sin truncar, las celdas de regla completas
del ETL de Simulacros (`OQ-ETL-01`/`OQ-ETL-02`, ambas `RESOLVED`) — ver
`docs/01-architecture/mapping-governance.md` § 12.3 para la evidencia
completa. Ninguno de los dos está todavía implementado en
`config/exports/drills.yaml` (siguen en `excluded_columns`) — la
resolución es de **conocimiento**, no de código; implementarlos es un
paso posterior, no automático por este cierre.

**Nota de lectura importante**: 🔴 no significa "conocimiento perdido" en
la mayoría de los 22 casos — significa "nunca hubo evidencia SQL/ETL
concluyente que trazar, con o sin ETL disponible". Solo 2 de esos 22
(`EstimatedLoss`, `RealLoss`) representan una laguna de *documentación del
contrato* genuina y nueva descubierta en esta auditoría (ver
`drills-csv-contract.md` § 3 y la sección de campos huérfanos del informe
de ejecución) — el resto (20) ya estaba correctamente clasificado como
fuera de alcance, con o sin ETL, desde incrementos anteriores.
