# Contrato funcional del CSV final — simulacros.Drills

**Status:** Implemented (reconstrucción a partir de código y configuración
únicamente — ningún CSV real, ETL ni SQL Server consultado para producir
este documento, Sprint 8.1). Fuente única: `config/exports/drills.yaml`,
`src/export/prototype/drills/*.py`, `tests/test_drills_export_prototype.py`.

## 0. Alcance

El CSV real de Enablon para Drills tiene **36 columnas** confirmadas
(`docs/specifications/v1.0/export/object_assessments/drills_evidence_assessment.md`
§ 10, evidencia `evidence:csv_enablon.drills`). Este prototipo implementa
**8** de esas 36, por decisión de alcance documentada (no por carencia
descubierta ahora) — ver § 3 para las 28 restantes.

## 1. Contrato de las 8 columnas implementadas (orden de salida real)

Orden fijado por `OUTPUT_COLUMNS` en
`src/export/prototype/drills/pipeline.py:58-67` — es una decisión propia
de este prototipo, **no** una copia del orden del CSV histórico real.

| Orden | Campo CSV | Tipo | Standard/CS | Obligatorio | Origen SQL | Origen Canonical | Mapping utilizado | Transformación | Lookup | Default | Validación | Responsable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `CS_Typology` | string | CS_ | Sí | `IDTipo` | (no aplica — CDM no implementado) | `reference_data.typology_lookup` (15 entradas) | `resolve_typology` (2-step XLOOKUP confirmado) | `typology_lookup` | `"NADA"` (`typology_default_no_match`, documentado, no inventado) | `must_resolve_or_use_documented_default` | `transformations.py::resolve_typology` |
| 2 | `Reference` | string | Standard | Sí | `[IDTipo, IDSimulacro, Fecha]` (compuesto, no columna única) | — | — (regla propia, no tabla) | `build_reference` (`AFD-DRILLS-REFERENCE-001`, decisión funcional aprobada) | Ninguno | Ninguno — si falta cualquier componente, la fila se excluye del CSV (sin fallback artificial) | `pattern:^[^-]+-HIST-[^-]+-\d{2}/\d{2}/\d{4}$` | `transformations.py::build_reference` |
| 3 | `StartingDate` | datetime | Standard | Sí | `Fecha` | — | — | `parse_starting_date` + `format_starting_date` (`dd/MM/yyyy HH:mm`) | Ninguno | Ninguno — `None` si no interpretable, fila excluida | `required_valid_date` | `transformations.py::parse_starting_date` |
| 4 | `CS_HistoricalOriginID` | string (identifier) | CS_ | Sí | `IDSimulacro` | — | — | `to_historical_id` (normaliza representación decimal, p. ej. `440.0`→`"440"`) | Ninguno | Ninguno — `None` si vacío o no numérico, fila excluida | `required_non_null` | `transformations.py::to_historical_id` |
| 5 | `CS_Letter` | string | CS_ | No | `IDLetra` | — | `reference_data.letter_lookup` (7 entradas) | `resolve_letter` | `letter_lookup` | `"NOLETTER-WRONG"` (`letter_null_default`, literal exacto del `nullcontrol` original — solo si `IDLetra` vacío; si presente y sin coincidencia, queda `unresolved`, no se le aplica este default) | `warn_if_unresolved` | `transformations.py::resolve_letter` |
| 6 | `CS_ImpactedEntities` | string | CS_ | No | `IDUnidadOrg` | — | `reference_data.entity_catalog_csv` (681 filas, `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv`) | `resolve_entity` | Catálogo `IDUnidadOrg`→`Code` | Ninguno — `unresolved`/`conflicting`/`empty` se reportan, nunca se inventa un valor | `warn_if_unresolved_or_conflicting` | `mappings.py::resolve_entity` |
| 7 | `CS_WorkflowStatus` | string | CS_ | No | `Estado` | — | `reference_data.workflow_status_lookup` (4 entradas) | `resolve_workflow_status` | `workflow_status_lookup` | Ninguno confirmado — un `Estado` no listado queda `unresolved`, no se inventa | `warn_if_unresolved` | `transformations.py::resolve_workflow_status` |
| 8 | `CS_HistoricalDataOrigin` | string | CS_ | Sí | Ninguno (constante) | — | — | `constant` | Ninguno | `"Prevención.ITP_SIM+ITP_SIM_ACCIONES_CORRECTORAS"` (literal fijo, documentado) | `constant_literal` | `config/exports/drills.yaml` (valor declarado, no código) |

**Columna "Origen Canonical" vacía en las 8 filas**: no hay `CanonicalField`
ni `CanonicalRecord` implementados (ver `knowledge-coverage-matrix.md`,
área "Canonical Data Model" = PENDIENTE) — el pipeline opera directamente
sobre un `pandas.DataFrame` con columnas SQL crudas
(`canonical-data-model.md` § 0 lo confirma explícitamente como brecha ya
identificada, no nueva).

## 2. Campos estándar vs. campos `CS_` (de las 8 implementadas)

| Grupo | Campos |
|---|---|
| Standard (2) | `Reference`, `StartingDate` |
| `CS_` (6) | `CS_Typology`, `CS_HistoricalOriginID`, `CS_Letter`, `CS_ImpactedEntities`, `CS_WorkflowStatus`, `CS_HistoricalDataOrigin` |

## 3. Las 28 columnas reales NO implementadas

26 de 28 tienen exclusión explícita con motivo (`config/exports/drills.yaml::excluded_columns`):

| Columnas | Motivo documentado |
|---|---|
| `NameEN`, `NameFR`, `NameES`, `NameZH`, `NameBR` | La fuente real de "Titulo" no es una columna SQL directa identificada con certeza — incluirlas sería inventar el origen. |
| `CS_Duration` | `OQ-ETL-02` abierta — no se ha localizado la fórmula que recombina meses/días/horas/minutos en el valor único esperado. |
| `CS_HistoricalAttachedFiles`, `GroupsList`, `CS_OtherContacts`, `CS_ExternalParticipants`, `CS_HistoricalDrillAttendees`, `CS_OtherParticipants` | Requieren resolución de adjuntos/asistentes/grupos no evidenciada en este incremento. |
| `CS_EnvConsequences`, `CS_FirefightingAndSpillContainment`, `CS_ObservationsFirefighting`, `CS_AttitudeOfPersonnel`, `CS_ObservationsPersonnel`, `CS_StaffTraining`, `CS_ObservationsTraining`, `CS_Communication`, `CS_ObservationsCommunication` | Sin columna SQL correspondiente identificada ni mapping documentado. |
| `CS_HistoricalRecord` | Valor observado en el CSV histórico (`'Yes'`) sin confirmar si es constante o condicional. |
| `CS_HistoricalUserId`, `CS_HistoricalUserName`, `CS_HistoricalDrillResponsibleName` | Requieren lookup contra `ITP_USUARIOS` (datos personales) — fuera de alcance por diseño, no por falta de mecanismo. |
| `Id` | Identificador propio de Enablon, asignado DESPUÉS de la carga — este prototipo genera un CSV previo a cualquier carga. |

**2 columnas SIN ninguna entrada de contrato** (ni en `fields` ni en
`excluded_columns`) — hallazgo de esta auditoría, ver
`knowledge-traceability-matrix.md` § "Campos huérfanos" para el detalle:

| Columna | Observación |
|---|---|
| `EstimatedLoss` | Presente en el CSV real (columna 13, confirmada en `drills_evidence_assessment.md` § 10). No aparece en `fields` ni en `excluded_columns` de `config/exports/drills.yaml` — ninguna razón documentada de por qué está fuera de alcance. |
| `RealLoss` | Igual que `EstimatedLoss` (columna 14). |

Esto **no** es un campo huérfano en el CSV *generado* (el CSV generado
solo tiene 8 columnas fijas, ninguna sin contrato) — es una brecha de
completitud del **contrato de exclusión**: dos columnas reales de Enablon
que ni se implementan ni se declaran excluidas con motivo. Ver Fase 6 del
informe de ejecución de esta auditoría.

## 4. Verificación de "no inventar nombres"

Los 36 nombres de columna de este documento provienen literalmente de
`config/exports/drills.yaml` (`fields`/`excluded_columns`) y de
`drills_evidence_assessment.md` § 10 (lectura de cabecera real del CSV
histórico) — ninguno fue inferido o completado por este documento.
