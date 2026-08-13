# Informe — Drills Full Readiness Closure (Sprint 9.3)

**Fecha:** 2026-08-13
**Rama:** feature/drills-filtered-exports
**Ejecuciones SQL reales en este sprint:** 0 (todo el trabajo fue offline, solo lectura de ficheros locales — ETL, Operational, Template, catálogos ya presentes en el repositorio/workspace)

---

## 1. Resumen ejecutivo

Sprint 9.2 cerró con `DRILLS_FUNCTIONALLY_VALIDATED` (execution_id `8ba7eba9f65c`, 15/15 solapamiento real contra el Project Contract, 7/8 campos al 100% de coincidencia, `StartingDate` con una diferencia sistemática ya identificada — hora truncada).

Este sprint (9.3):

1. Reconstruyó y **verificó empíricamente** (12.091 filas reales del ETL, sin SQL) la regla exacta de `StartingDate`, y la implementó.
2. Clasificó individualmente las 10 columnas del Project Contract todavía no generadas por EMF.
3. Construyó el contrato definitivo de las 18 columnas reales de Drills.
4. Evaluó la deuda de soporte XLSX del comparador automático.
5. Confirmó readiness offline (`workspace validate` + `readiness full/comparison`): 0 blockers estructurales.
6. Determinó que **todavía no** procede declarar `DRILLS_ACCEPTED_FOR_FULL_READINESS` — dos motivos concretos, no genéricos (ver §9).

**Estado final de este sprint: `DRILLS_FUNCTIONALLY_VALIDATED`** (sin cambio de nivel respecto a Sprint 9.2 — reforzado con más evidencia, no degradado). No se declara `DRILLS_ACCEPTED_FOR_FULL_READINESS` ni `DRILLS_BLOCKED_*`: el pipeline sigue siendo correcto y funcional en todo lo ya validado; lo que falta son decisiones/verificaciones puntuales, no una regresión.

---

## 2. Fase 0 — Preflight y commits

- Rama `feature/drills-filtered-exports`, remote `origin` sin cambios.
- Suite completa antes de empezar: **739 passed, 7 skipped** (coincide con la referencia).
- Cambios de Sprint 9.1/9.2 separados, revisados campo a campo (sin `.claude/settings.local.json`, sin `workspace.yaml` real, sin outputs/evidence reales, sin datos de cliente — confirmado con `grep` dirigido antes de cada commit) y comiteados de forma independiente:

  - **Commit A** (`90d7c89`) — `fix(db): add safe SQL failure diagnostics`
    `src/db/connection.py`, `src/db/query_runner.py`, `tests/test_db_query_runner.py`, `tests/test_cli_verbose_diagnostics.py`
  - **Commit B** (`f240a7e`) — `feat(drills): resolve comparison Project Contract from real workspace manifest`
    `src/cli.py`, `src/core/contracts.py`, `src/export/prototype/drills/comparison.py`, `src/export/prototype/drills/core_adapters.py`, `src/export/prototype/drills/pipeline.py`, `tests/test_drills_comparison_real_manifest.py`

- Sin push. Sin cambio de rama.

---

## 3. Fase 1 — Evidencia de StartingDate

**Orden de autoridad seguido**: ETL real → mapping gobernado → Operational real → Template → ejecución 8ba7eba9f65c → código EMF actual.

1. **ETL real** (`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`, hoja `MapeoSims`, fila 11): el origen declarado del campo destino `"Start Date"` es `FechaHoraCombinado`, no `Fecha` sola (fila 9, sin transformación asociada). `FechaHoraCombinado` llega siempre vacía desde SQL (`'' as FechaHoraCombinado`) — la combinación nunca se materializó en la consulta.
2. **Verificación empírica cruzada**, dentro del mismo workbook, sin SQL: hoja `DB_OrigenSim` (origen crudo) vs. hoja `CSV_SIM` (destino ya generado, valores materializados, no fórmulas). **12.091 filas comparadas — 12.087 coinciden exactamente (99,97%)** con la regla `StartingDate = fecha(Fecha) + hora:minuto(Hora)` (`Hora` como texto `H:MM`/`HH:MM`, 24h, sin segundos — consistente con el tipo `varchar(5)`).
3. Las 4 filas discordantes: `Hora` corrupta en origen (`'11:'`, `'1:'`, `'2:.30'`) o un caso sin explicación mecánica simple (`'9:50'` → destino `18:50`) — 0,033% del total, sin patrón alternativo consistente.
4. **No existe ninguna fórmula Excel/VBA visible** que compute la combinación (mismo patrón ya documentado para `titlefix` en `CLAUDE.md`) — la regla se reconstruyó por evidencia cruzada de datos, no por lectura de fórmula.

**Clasificación de la evidencia**:
- Regla central (Fecha+Hora → StartingDate): **VERIFIED**.
- Comportamiento con `Hora` NULL/vacía: **UNRESOLVED** — 0 casos observados en las 12.091 filas disponibles.
- Timezone: sin evidencia de transformación (valores "naive").
- Segundos: siempre `:00`.

Documentado en `docs/07-developer-guide/drills-startingdate-rule.md`.

---

## 4. Fase 2-3 — Implementación y tests de StartingDate

**Cambio mínimo**, sin tocar SQL ni otros mappings:

- `transformations.py::parse_starting_date(value, hora=None)` — nuevo parámetro opcional; `hora=None`/vacía/no interpretable reproduce el comportamiento EXACTO de antes (retrocompatible). Nueva función `parse_hora()`.
- `pipeline.py`: pasa `row.get("Hora")`; nueva categoría de incidencia no bloqueante `HORA_MISSING_OR_INVALID` (`issues.jsonl`, nunca excluye la fila).
- `manifest.py`: nuevo contador `dates_hora_missing_or_invalid` en `RunStats` y en `validation_report.yaml`.
- `config/exports/drills.yaml`: `source` de `StartingDate` pasa de `"Fecha"` a `["Fecha", "Hora"]`.

**Tests nuevos** (datos 100% sintéticos, ningún dato real): 15 en `tests/test_drills_export_prototype.py` (Fecha+Hora normal, Hora `00:00`, Hora NULL/vacía ×3, Fecha NULL, formato `H:MM` de un dígito, ausencia de segundos, 6 formatos inválidos reales observados, formato final sin regresión) + 1 de integración en `tests/test_drills_data_workspace_integration.py` (fila con Hora inválida no se excluye, queda registrada).

Efecto colateral controlado: 6 archivos de test con dataframes sintéticos (`_fake_dataframe`) no incluían `Hora` — el validador de columnas fuente lo detectó correctamente (`Columnas fuente esperadas ausentes: ['Hora']`). Corregido añadiendo `Hora` a cada fixture, sin tocar ninguna aserción.

**Suite completa: 755 passed, 7 skipped** (739 + 16 nuevos, sin regresiones).

---

## 5. Fase 4-5 — Las 10 columnas diferidas, clasificadas individualmente

| Campo | Importable | En Template | En Operational | Fuente SQL/ETL | Mapping verificable | Poblado hist. | Datos personales | Fase transversal futura | Clasificación |
|---|---|---|---|---|---|---|---|---|---|
| NameEN | Sí | Sí | Sí (0% nulo) | Sin origen SQL confirmado (`Mapeo_Titulo` sin motor visible, mismo patrón que `titlefix`) | No | 100% | No | No | **UNRESOLVED_BLOCKING** |
| CS_Duration | Sí | Sí | Sí (0% nulo) | `Duracion` vía `CalculoHorasDiasMinutos` (regla ya conocida — no reabierta, ver Fase 5) | Sí (passthrough directo, confirmado previamente) | 100% | No | No | **FUTURE_INCREMENT** |
| CS_EnvConsequences | Sí | Sí | Sí (78% nulo) | Sin columna SQL identificada | No | 22% | No | No | **UNRESOLVED_NON_BLOCKING** |
| CS_ObservationsCommunication | Sí | Sí | Sí (26% nulo) | Sin columna SQL identificada | No | 74% | No | No | **UNRESOLVED_NON_BLOCKING** |
| CS_HistoricalRecord | Sí | Sí | Sí (0% nulo) | Constante — **`"Yes"` en 340/340 filas reales** (Sprint 9.3) | Sí (STRONGLY_EVIDENCED, 1 sola fuente) | 100% | No | No | **FUTURE_INCREMENT** (bajo riesgo) |
| CS_HistoricalUserId | Sí | Sí | Sí (0% nulo) | Usuario vía `multifielduser` | Sí (mecanismo confirmado) | 100% | **Sí** | No | **OUT_OF_SCOPE_CONFIRMED** |
| CS_HistoricalUserName | Sí | Sí | Sí (0% nulo) | `ITP_USUARIOS` (join) | Sí (mecanismo confirmado) | 100% | **Sí** (nombre) | No | **OUT_OF_SCOPE_CONFIRMED** |
| CS_HistoricalDrillResponsibleName | Sí | Sí | Sí (0% nulo) | `ITP_USUARIOS` (join) | Sí (mecanismo confirmado) | 100% | **Sí** (nombre) | No | **OUT_OF_SCOPE_CONFIRMED** |
| CS_HistoricalDrillAttendees | Sí | Sí | Sí (59% nulo) | `ITP_ASIST_SIMS`+`_EXT` vía `Asis_concat` (regla ya conocida — no reabierta) | Sí (STRONGLY_EVIDENCED) | 41% | **Sí** (nombres, confirmado en Operational real: `"Veras Gonzalez, José"`) | Parcial | **FUTURE_INCREMENT** |
| CS_HistoricalAttachedFiles | Sí | Sí | Sí (52% nulo) | Tablas de adjuntos (`TablaAdjuntos*`, requieren SQL adicional) | No | 48% | No (metadatos de fichero) | **Sí** | **FUTURE_INCREMENT** |

**Nota (Fase 5, sin reabrir conocimiento previo)**: conocer la regla (`CS_Duration`, `CS_HistoricalDrillAttendees`) no implica que pertenezca al primer full — ambas requieren, además, cambios de alcance (SQL adicional para Attendees; unidades/semántica sin confirmar para Duration) que no son necesarios para demostrar la fidelidad de las 8 columnas ya implementadas. Se clasifican `FUTURE_INCREMENT`, no `REQUIRED_BEFORE_FULL`.

**Único campo con clasificación bloqueante: `NameEN`.** Es el único de los 10 que es (a) 100% poblado históricamente, (b) altamente visible/crítico funcionalmente (es el título con el que un usuario identifica el registro en Enablon), y (c) sin ningún mecanismo de origen confirmado ni siquiera parcialmente — no hay decisión de negocio registrada que acepte cargar registros sin título.

---

## 6. Fase 6 — Contrato definitivo de Drills (18 columnas)

| Campo | Tipo | Importable | Generado hoy | Fuente | Mapping status | Required for load | Scope status | Full blocker | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| CS_Typology | string | Sí | Sí | IDTipo | RESOLVED | Sí | IN_SCOPE | No | etl_transform:simulacros.mapeotiposim |
| Reference | string | Sí | Sí | IDTipo+IDSimulacro+Fecha | RESOLVED | Sí | IN_SCOPE | No | AFD-DRILLS-REFERENCE-001 |
| StartingDate | datetime | Sí | Sí (Sprint 9.3) | Fecha+Hora | RESOLVED (VERIFIED 99,97%) | Sí | IN_SCOPE | No | drills-startingdate-rule.md |
| CS_HistoricalOriginID | string | Sí | Sí | IDSimulacro | RESOLVED | Sí (clave) | IN_SCOPE | No | evidence:sql_source.simulacros_dataset |
| CS_Letter | string | Sí | Sí | IDLetra | RESOLVED | No | IN_SCOPE | No | etl_transform:simulacros.mapeoletra |
| CS_ImpactedEntities | string | Sí | Sí | IDUnidadOrg+catálogo | RESOLVED (validado 15/15, Sprint 9.2) | No | IN_SCOPE | No | drills_entity_resolution_assessment.md |
| CS_WorkflowStatus | string | Sí | Sí | Estado | RESOLVED | No | IN_SCOPE | No | etl_transform:simulacros.mapeoestado |
| CS_HistoricalDataOrigin | string | Sí | Sí | constante | RESOLVED | Sí | IN_SCOPE | No | etl_transform:simulacros.multifielduser |
| NameEN | string | Sí | No | sin confirmar | UNRESOLVED | Probable | UNRESOLVED | **Sí** | — |
| CS_Duration | numeric | Sí | No | Duracion (ETL) | STRONGLY_EVIDENCED | No | FUTURE_INCREMENT | No | conocimiento previo |
| CS_EnvConsequences | string | Sí | No | sin origen | UNRESOLVED | No | UNRESOLVED_NON_BLOCKING | No | — |
| CS_ObservationsCommunication | string | Sí | No | sin origen | UNRESOLVED | No | UNRESOLVED_NON_BLOCKING | No | — |
| CS_HistoricalRecord | string | Sí | No | constante "Yes" | STRONGLY_EVIDENCED (Sprint 9.3) | No | FUTURE_INCREMENT | No | Operational real |
| CS_HistoricalUserId | numeric | Sí | No | usuario (SQL) | RESOLVED, no implementado | No | OUT_OF_SCOPE_CONFIRMED | No | multifielduser |
| CS_HistoricalUserName | string | Sí | No | ITP_USUARIOS | RESOLVED, no implementado | No | OUT_OF_SCOPE_CONFIRMED | No | multifielduser |
| CS_HistoricalDrillAttendees | string | Sí | No | ITP_ASIST_SIMS(+EXT) | STRONGLY_EVIDENCED | No | FUTURE_INCREMENT | No | Asis_concat |
| CS_HistoricalDrillResponsibleName | string | Sí | No | ITP_USUARIOS | RESOLVED, no implementado | No | OUT_OF_SCOPE_CONFIRMED | No | multifielduser |
| CS_HistoricalAttachedFiles | ref. archivo | Sí | No | tablas de adjuntos | UNRESOLVED | No | FUTURE_INCREMENT | No | — |

**Distinción explícita** (pedida en Fase 6): Project Contract (18, arriba) ≠ todas las columnas observadas en cualquier export (36 en Template, incluye `Id` — system, asignado por Enablon tras la carga, nunca generable por este prototipo) ≠ columnas que EMF debe generar en esta versión (8, ya validadas).

---

## 7. Fase 7 — Deuda del comparador XLSX

**Clasificación: B) blocker solo de automatización de validation — no de full.**

La comparación fila a fila **sí es posible** (se hizo manualmente en Sprint 9.2, con éxito, 15/15) — lo que falta es automatizarla para no depender de un script ad-hoc cada vez.

**Propuesta de diseño** (pequeña, genérica, no implementada en este sprint):
- Extraer una función `read_historical_table(path) -> HistoricalTableInfo` que despache por extensión: `.csv` reutiliza `detect_historical_csv`/`_read_all_rows` (sin cambios); `.xlsx` usa `pandas.read_excel` + normalización a texto (mismo tratamiento que `csv.DictReader`: todo string, `NaN` → `""`).
- `build_comparison_report` deja de leer bytes directamente — recibe la tabla ya normalizada (columnas + filas como texto), sea cual sea el origen.
- Ningún código específico de "Simulacros CCE.xlsx" en absoluto.

No implementado en este sprint (fuera del "cambio mínimo" de StartingDate; evitar ampliar alcance). Backlog **P2**.

---

## 8. Fase 8 — Readiness offline (sin SQL)

```
workspace validate --manifest <real>        -> OK, sin violaciones
workspace readiness --module drills --operation full        -> ready_with_warnings, 0 blockers
workspace readiness --module drills --operation comparison  -> ready_with_warnings, 0 blockers
```

Warnings en ambos casos: `evidence`/`outputs` ausentes (esperado — ninguna ejecución real archivada en el workspace externo todavía). Ningún blocker de manifest, módulo, contrato ni knowledge. La autorización SQL (`--allow-real-sql`) no aparece como blocker de readiness — correcto, es una autorización de ejecución, no un requisito estructural.

---

## 9. Fase 9 — Matriz de decisión

| # | Punto | Estado | Motivo |
|---|---|---|---|
| A | Pipeline real | **PASS** | Ejecutado con éxito en Sprint 9.1 y 9.2 |
| B | Query/filter | **PASS** | Filtro server-side verificado, `WHERE` parametrizado |
| C | Mapping | **PASS** | 7/8 campos = 100% match (Sprint 9.2); StartingDate corregido (Sprint 9.3) |
| D | Entity resolution | **PASS** | 15/15 resuelto (9.2); "No migra" confirmado EXPECTED con evidencia de catálogo (9.1) |
| E | Project Contract | **PASS** | Resuelto desde `workspace.yaml` real, legacy eliminado (9.2) |
| F | StartingDate | **PASS_WITH_ACCEPTED_RISK** | Regla VERIFIED (99,97%, 12.091 filas) e implementada, pero **no reconfirmada contra SQL real** tras el cambio (ver §10, gate condicional) |
| G | Excluded fields | **PASS_WITH_ACCEPTED_RISK**, con una excepción | 9/10 campos diferidos con decisión trazable (OUT_OF_SCOPE_CONFIRMED / FUTURE_INCREMENT); **`NameEN` es BLOCKED individualmente** (ver §5) |
| H | Comparison automation | **PASS_WITH_ACCEPTED_RISK** | Resuelve el contrato correctamente; no procesa `.xlsx` (mejora propuesta, no implementada) |
| I | Evidence | **PASS** | Generada correctamente en ambas ejecuciones reales |
| J | Workspace | **PASS** | 0 blockers en `validate`/`readiness` (§8) |
| K | SQL safety | **PASS** | Guard + sanitización + readonly, todo verificado (9.1) |
| L | Full-volume risk | **PASS_WITH_ACCEPTED_RISK** | Nunca ejecutado a volumen completo (~12.501 filas); sin evidencia de problema, pero no probado |

**Decisión**: existe un punto con clasificación `BLOCKED` a nivel de campo individual (`NameEN`, dentro de G) y un riesgo aceptado pendiente de reconfirmación (F). Ninguno de los dos representa una regresión de lo ya validado en Sprint 9.2 — ambos son items nuevos, acotados, con plan de cierre claro.

**No se declara `DRILLS_ACCEPTED_FOR_FULL_READINESS`** (dos motivos concretos, no genéricos: NameEN sin decisión de negocio; StartingDate sin reconfirmación real).
**No se declara `DRILLS_BLOCKED_<reason>`**: nada de lo ya validado en Sprint 9.2 se ha invalidado — el pipeline, el filtro, el 7/8 de mapping, la resolución de entidad, el Project Contract y el SQL safety siguen en PASS. Degradar el estado global por dos items acotados y ya identificados desvirtuaría la señal para quien lea el estado del módulo.

## **Estado final: `DRILLS_FUNCTIONALLY_VALIDATED`** (sin cambio de nivel respecto a Sprint 9.2, reforzado con evidencia adicional).

---

## 10. Fase 10 — Puerta de seguridad condicional (StartingDate sí fue modificado)

`StartingDate` fue corregido con evidencia suficiente (VERIFIED, §3-4). Preparo la puerta para repetir el sample comparable — **sin ejecutar SQL todavía**.

**Comando propuesto** (idéntico al de Sprint 9.2, sin cambios de filtro/límite):
```
python main.py --verbose run --project moeve --object drills --mode sample --limit 15 \
  --filter origin_org_unit_id:eq:147 --generate-evidence --audience both \
  --allow-real-sql --manifest "<EMF_DATA_ROOT>/projects/moeve/workspace.yaml"
```

**Resultado esperado** si no hay ninguna otra diferencia: **15/15 solapamiento**, **120/120 comparaciones exactas** (7 campos × 15 filas + `CS_HistoricalOriginID` como clave = 120; a diferencia de Sprint 9.2, `StartingDate` debería pasar de 0/15 a 15/15 exactos, dado que las 15 filas de Centro/unidad 147 no tienen `Hora` NULL/inválida conocida — sin verificar todavía, es la hipótesis a confirmar).

**No se ha ejecutado. Esperando autorización explícita.**

---

## 11. Fase 11 — Roadmap post-Drills (reutilización para los próximos módulos)

| Pieza | Estado | Reutilizable tal cual | Necesita adapter/interfaz antes de acelerar otros módulos |
|---|---|---|---|
| WorkspaceManifest | Genérico, probado | Sí | — |
| ResourceResolver | Genérico, probado (0 imports de `src.export`) | Sí | — |
| ModuleRegistry | Genérico | Sí | — |
| ReadinessValidator | Genérico | Sí | — |
| SQL Execution Guard | Genérico | Sí | — |
| Query Engine (filtros) | Genérico, catálogo cerrado por objeto | Sí (patrón), no el catálogo en sí | Cada módulo necesita su propio `ObjectFilterCatalog` |
| Mapping governance (knowledge conflicts) | Metodología probada (KC-AP-001, etc.) | Sí (proceso) | — |
| Project Contract (concepto) | Validado end-to-end con Drills | Sí (concepto) | El "contrato definitivo" (§6) es manual hoy — no hay generador automático desde Template+Operational |
| Evidence | Genérico (`evidence/collector.py`, `workbook.py`) | Sí | — |
| Comparison | Conectado a manifest real (9.2), **solo CSV** | Parcial | Necesita soporte XLSX genérico (§7) antes de que otro módulo con Operational en Excel lo aproveche sin trabajo manual |
| Execution lifecycle (Framework Core v1) | Genérico (`ExecutionRequest`/`ExecutionContext`/`StageRegistry`) | Sí | El `DrillsTransformExportStage` sigue siendo un "adaptador temporal" que envuelve `pipeline.run()` monolítico — separar Mapping/Validation/Export en stages propios sigue pendiente (deuda ya documentada en `framework-core-v1.md`) |

**Partes todavía Drills-specific que deberían convertirse en interfaz antes de acelerar el siguiente módulo**: (1) el propio `pipeline.run()` de Drills (mapeo+validación+export+comparison en una función monolítica); (2) el comparador (solo CSV); (3) el "contrato definitivo" de columnas (tabla manual, no derivada automáticamente de Template+Operational+config).

---

## 12. Riesgos aceptados (resumen)

1. `StartingDate` verificado offline (99,97%, 12.091 filas), pendiente de reconfirmación con SQL real (§10).
2. Comparación automática no soporta `.xlsx` — comparación manual sigue siendo necesaria (§7, backlog P2).
3. Volumen completo (~12.501 filas) nunca ejecutado — sin evidencia de problema, no probado (L).
4. 9 de 10 columnas diferidas con decisión trazable pero no implementadas — riesgo bajo, documentado, no bloqueante.

## 13. Blockers reales

1. **`NameEN`** — sin origen SQL/ETL confirmado, 100% poblado históricamente, sin decisión de negocio registrada que acepte omitirlo. Bloquea `DRILLS_ACCEPTED_FOR_FULL_READINESS`, no bloquea `DRILLS_FUNCTIONALLY_VALIDATED`.

## 14. Propuesta de siguiente acción

1. Decisión de negocio sobre `NameEN` (¿se acepta un primer full sin título, o se investiga su origen real primero?).
2. Autorización para repetir el sample comparable (§10) y confirmar `StartingDate` con SQL real.
3. Si ambos se resuelven favorablemente: nueva evaluación de Fase 9 con posibilidad real de `DRILLS_ACCEPTED_FOR_FULL_READINESS`.
4. Backlog no bloqueante: soporte XLSX en el comparador (P2); columnas `FUTURE_INCREMENT` (P3).

## 15. Commits

- Realizados en este sprint: **A** (`90d7c89`) y **B** (`f240a7e`) — ver §2.
- **Pendiente de autorización** (no comiteado todavía): cambio de `StartingDate` (§3-4) + este informe.
  Archivos: `src/export/prototype/drills/transformations.py`, `src/export/prototype/drills/pipeline.py`, `src/export/prototype/drills/manifest.py`, `config/exports/drills.yaml`, `docs/07-developer-guide/drills-startingdate-rule.md`, `tests/test_drills_export_prototype.py`, `tests/test_drills_data_workspace_integration.py`, `tests/test_bootstrap_module_registry.py`, `tests/test_cli_sql_execution_guard.py`, `tests/test_drills_comparison_real_manifest.py`, `tests/test_drills_core_pipeline.py`, `tests/test_drills_export_query_engine.py`, más este informe.
- Sin push en ningún momento de este sprint.

## 16. Archivos modificados (no comiteados)

```
config/exports/drills.yaml
docs/07-developer-guide/drills-startingdate-rule.md   (nuevo)
src/export/prototype/drills/transformations.py
src/export/prototype/drills/pipeline.py
src/export/prototype/drills/manifest.py
tests/test_drills_export_prototype.py
tests/test_drills_data_workspace_integration.py
tests/test_bootstrap_module_registry.py
tests/test_cli_sql_execution_guard.py
tests/test_drills_comparison_real_manifest.py
tests/test_drills_core_pipeline.py
tests/test_drills_export_query_engine.py
reports/executions/2026-08-13/Informe-Drills-Full-Readiness-Closure-EMF.md  (nuevo)
reports/executions/2026-08-13/Informe-Drills-Full-Readiness-Closure-EMF.txt  (nuevo)
```
