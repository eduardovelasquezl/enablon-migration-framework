# Informe — Bypass: Second Module Replication (Sprint 9.4)

**Fecha:** 2026-08-13 · **Rama:** feature/drills-filtered-exports
**SQL real ejecutado:** 0. **Full ejecutado:** 0.

Documentación detallada (evidencia completa, matriz, clasificación):
`docs/07-developer-guide/bypass-module.md` — este informe resume el
resultado del sprint, sin repetir ese contenido íntegro.

## 1. Estado final

**`BYPASS_OFFLINE_SAMPLE_READY`**

- `ModuleRegistry` reconoce `bypass` (junto a `drills`), con
  `pipeline_factory` real.
- `workspace readiness --module bypass --operation sample` (offline,
  workspace.yaml real de Moeve): **`ready`, 0 blockers**, 3
  informativos (mismo patrón que Drills).
- Pipeline completo (offline, SQL mockeado): extrae → transforma → CSV
  → `validation_report.yaml` → `export_manifest.yaml`, sin errores.

## 2. Evidencia y mappings

Ver `docs/07-developer-guide/bypass-module.md` §§ 1.1-1.7 para la
evidencia completa (ETL real, SQL, cruces contra el Operational real).

**Confirmados (7 campos, VERIFIED)**: `CS_HistoricalOriginID` (IDBES,
cloneorigin), `ByPassType`, `Cause`, `ElementType`,
`RealizationMethods` (4 lookups del ETL real, cruzados contra el
Operational), `Reason` (nullcontrol), `CS_HistoricalDataOrigin`
(constante `"Prevención.ITP_BES"`, verificada en el Operational real).

**Unresolved**: `Entity` — resultado ya validado en producción, pero
sin artefacto local reproducible para el catálogo First_Axis vigente
(a diferencia del catálogo antiguo de Drills). No confundir con
`OUT_OF_SCOPE` — es una carencia de artefacto, no una decisión de
alcance.

**Excluidos con evidencia** (personal, no importable, condicional sin
confirmar): `CS_HistoricalUserId/UserName/Exec.../Auth...`, `GOS`,
`MotivoAprobaciónFase2/3/5`, `FechaEnvioFase1..6`, `Equipment`/`Tag`.

**Hallazgo de calidad de datos**: `CS_HistoricalOriginID` en el
Operational real contiene valores con apariencia de fecha (corrupción
de exportación, decodificable a IDs `IDBES` plausibles) — registrado,
no corregido.

## 3. Project Contract identificado

Operational real: `By pass new .bak.csv` (25 filas, mismo patrón
CCE-scoped que Drills). Sin Template en este workspace (gap ya
confirmado en Sprint 8.8, no nuevo).

## 4. Readiness sample

```
workspace validate                                    -> OK
workspace readiness bypass/sample   -> ready, 0 blockers, 3 info
workspace readiness bypass/full     -> ready_with_warnings, 0 blockers
workspace readiness bypass/comparison -> BLOCKED (2) -- correcto: ni
  'comparison' está declarada como capability ni hay contracts.project
  configurado -- el validador refleja fielmente que esa vía no está
  implementada todavía, no un error.
```

Nota: el `workspace.yaml` real (fuera de Git) tenía `bypass:
enabled=false/status=planned` desde Sprint 9.0 — actualizado localmente
a `enabled=true/status=in_progress` para reflejar que ahora SÍ tiene
pipeline real (edición autorizada explícitamente por el encargo,
fuera de Git, nunca versionada).

## 5. Tests nuevos

- `tests/test_bypass_transformations.py` — 10 tests, funciones puras,
  datos 100% sintéticos.
- `tests/test_bypass_pipeline.py` — 10 tests: ModuleRegistry,
  PipelineFactory, SQL Guard fail-closed, compilación de filtros,
  pipeline completo (columnas, exclusión por ID ausente), readiness
  offline con manifest sintético.
- `tests/test_bootstrap_module_registry.py` — 2 tests actualizados
  (ya no "solo Drills"; "bypass" ya no en la lista de "no registrado
  todavía").

**Suite completa: `775 passed, 7 skipped`** (765 tras las
correcciones de los 2 tests existentes, + 10 nuevos de
`test_bypass_pipeline.py`; 755 baseline + 10 de
`test_bypass_transformations.py` = 765; 765 + 10 = 775). Cero
regresiones en Drills.

## 6. Archivos creados/modificados

**Nuevos:**
```
config/exports/bypass.yaml
src/export/prototype/bypass/__init__.py
src/export/prototype/bypass/config.py
src/export/prototype/bypass/transformations.py
src/export/prototype/bypass/extractor.py
src/export/prototype/bypass/manifest.py
src/export/prototype/bypass/validator.py
src/export/prototype/bypass/pipeline.py
src/export/prototype/bypass/core_adapters.py
tests/test_bypass_transformations.py
tests/test_bypass_pipeline.py
docs/07-developer-guide/bypass-module.md
reports/executions/2026-08-13/Informe-Bypass-Second-Module-Replication-EMF.{md,txt}
```

**Modificados:**
```
src/bootstrap/module_registry.py   (+ registro de Bypass, junto a Drills)
src/query/catalog.py               (+ BYPASS_FILTER_CATALOG)
tests/test_bootstrap_module_registry.py  (2 tests actualizados a la nueva realidad de 2 módulos)
```

**Fuera de Git (edición local autorizada, nunca versionada):**
```
<EMF_DATA_ROOT>/projects/moeve/workspace.yaml  (bypass: enabled true, status in_progress)
```

## 7. Clasificación agregada

Ver `docs/07-developer-guide/bypass-module.md` § 6 para la tabla completa
y las respuestas detalladas a las 4 preguntas de la Fase 12. Resumen:

| Clasificación | Count |
|---|---:|
| REUSED_AS_IS | 15 |
| MODULE_SPECIFIC | 4 |
| DUPLICATED_FROM_DRILLS | 7 |
| CORE_GAP (bloqueante) | 0 |
| CORE_GAP (blando, no bloqueante) | 2 |

**P1 — ¿Segundo módulo sin cambios de Core?** Sí, cero cambios en `src/core/`.
**P2 — ¿Cuánto se duplicó?** 7 piezas concretas, todas en la capa de orquestación, nunca en transformaciones puras.
**P3 — ¿Evidencia para un Module Adapter Contract v0.x?** Sí, confirmada con un segundo caso real; no implementado todavía.
**P4 — ¿Sprint 9.5 real ya, o micro-sprint de Export Engine antes?** **Recomendación: Sprint 9.5 primero** — duplicación real pero contenida; generalizar con solo 2 puntos de datos es prematuro.

## 8. Candidato de filtro para el primer sample real (NO ejecutado)

`CS_HistoricalOriginID` corrupto en el Operational real se decodificó
(hipótesis de fecha-serial de Excel) a estos IDs `IDBES` candidatos:
`2878, 2881, 2942, 2943, 2966, 2992, 3086, 3301, 3371, 3816, 3842,
3880, 4615, 4622, 5305, 26040, 26557, 26969, 27103, 27454, 27556,
27884, 28014, 28031, 28239` (25 valores, todo el Operational real).

**Comando propuesto** (no ejecutado, requiere nueva autorización):
```
python main.py --verbose run --project moeve --object bypass --mode sample --limit 15 \
  --filter "historical_origin_id:in:2878,2881,2942,2943,2966,2992,3086,3301,3371,3816" \
  --allow-real-sql
```
(sublista de 10 de los 25 IDs, dentro del rango 5-20 ya usado en Drills;
sin `--generate-evidence` -- Evidence no está implementada para Bypass
en este incremento, ver § 4 de `bypass-module.md`).

## 9. Riesgos / deuda técnica

1. Discrepancia de 2 ficheros SQL candidatos para Bypass, resuelta por
   criterio conservador (INNER JOIN), no por confirmación definitiva.
2. `Entity` sin mecanismo local reproducible (catálogo First_Axis
   vigente).
3. Anomalía de datos en `CS_HistoricalOriginID` del único Operational
   real disponible.
4. 7 piezas `DUPLICATED_FROM_DRILLS` — deuda conocida, cuantificada,
   no bloqueante.
5. Sin Evidence ni Comparison implementadas para Bypass todavía
   (alcance deliberadamente reducido para este incremento).

## 10. Acciones expresamente NO realizadas

- No se ejecutó SQL real en ningún momento.
- No se ejecutó full export.
- No se tocó Action Plans ni ningún otro módulo.
- No se hizo ningún refactor amplio de Core.
- No se diseñó UI.
- No se resolvió deuda de Drills no necesaria para Bypass (NameEN
  sigue sin reabrirse).
- No se implementó soporte de comparison/Evidence para Bypass.
- No se extrajo un Export Engine genérico.
- No se hizo commit. No se hizo push.
