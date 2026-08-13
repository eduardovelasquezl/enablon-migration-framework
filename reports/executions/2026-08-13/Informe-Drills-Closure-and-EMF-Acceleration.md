# Informe — Drills Closure & EMF Acceleration

**Fecha:** 2026-08-13
**Rama:** feature/drills-filtered-exports
**SQL real ejecutado en este cierre:** 0 (todo el trabajo es documental/arquitectónico, sobre lo ya validado en Sprint 9.1-9.3.1)

---

## 1. Estado final de Drills

**`DRILLS_FUNCTIONALLY_VALIDATED`**

### Validado (evidencia real, no simulada)
- Pipeline real ejecutado 3 veces contra SQL Server (Sprint 9.1/9.2/9.3), login readonly `ClaudeReadOnly`, SQL Execution Guard verificado.
- Filtro server-side (`WHERE` parametrizado) verificado end-to-end.
- Sample comparable repetido de forma idéntica (`origin_org_unit_id:eq:147`, `limit=15`) antes y después del fix de StartingDate.
- 110 filas recuperadas server-side, 15 exportadas, 0 exclusiones, 0 warnings, 0 errores — en ambas ejecuciones del sample comparable.
- Evidence internal/client generada correctamente en las 3 ejecuciones reales.
- `ResourceResolver`/`WorkspaceManifest` real (Sprint 9.2): Project Contract resuelto desde `workspace.yaml` real, sin uso del manifest sintético legacy (confirmado por `baseline.path` en `comparison_report.yaml` de cada ejecución).
- Entity resolution: 15/15 resueltas a entidad viva en el sample de `origin_org_unit_id:eq:147`; comportamiento `No migra` confirmado como `EXPECTED` con evidencia de catálogo (74% de las unidades de Centro 4 marcadas `No migra`, no un fallo).
- Mappings implementados: `CS_Typology`, `Reference`, `CS_Letter`, `CS_ImpactedEntities`, `CS_WorkflowStatus`, `CS_HistoricalDataOrigin`, `CS_HistoricalOriginID` — 15/15 en ambas ejecuciones.
- `StartingDate`: regla `Fecha+Hora` reconstruida (ETL real, `MapeoSims`) y verificada (12.091 filas históricas, 99,97%), implementada, y **reconfirmada contra SQL real**: 15/15 exacto.
- Resultado total del sample comparable: **120/120 comparaciones semánticas correctas (100%)**.
- Outputs reales (`outputs/prototype/drills/*`) fuera de Git en las 3 ejecuciones — confirmado en cada checkpoint.

### Pendiente — separado en dos categorías distintas

#### BLOCKER de `DRILLS_ACCEPTED_FOR_FULL_READINESS`

**`NameEN`** → `UNRESOLVED_BLOCKING — EXTERNAL CONFIRMATION REQUIRED`

Hipótesis fuerte, **NO regla verificada**: `BreveDescripcion + Titlefix -> NameEN` (99,2% / 11.957 filas históricas). El ETL no nombra un `DatoOrigen` concreto (usa `"*"`, comodín). Decisión humana ya tomada (Micro-Sprint 9.3.1): **confirmar origen antes de implementar** — no se implementa hasta obtener confirmación externa. Las fuentes locales disponibles ya están agotadas para esta pregunta; no se reabre en este cierre.

#### Deuda no bloqueante / incremental (clasificada individualmente)

| Deuda | Clasificación | Bloquea full |
|---|---|---|
| Comparison automático no procesa `.xlsx` | Automatización de validation, no de full — la comparación manual ya demostró 120/120 | No |
| `CS_Duration` | `FUTURE_INCREMENT` (regla conocida — passthrough directo, no reabierta) | No |
| `CS_HistoricalDrillAttendees` | `FUTURE_INCREMENT` (regla conocida — `Asis_concat`, contiene datos personales, no reabierta) | No |
| `CS_HistoricalRecord` | `FUTURE_INCREMENT` (constante `"Yes"`, 340/340, bajo riesgo) | No |
| `CS_EnvConsequences`, `CS_ObservationsCommunication` | `UNRESOLVED_NON_BLOCKING` (sin columna SQL identificada) | No |
| `CS_HistoricalAttachedFiles` | `FUTURE_INCREMENT` (fase transversal de adjuntos) | No |
| `CS_HistoricalUserId/UserName/DrillResponsibleName` | `OUT_OF_SCOPE_CONFIRMED` (datos personales, decisión de diseño ya tomada) | No |
| Environment bootstrap (`EMF_DATA_ROOT` no cargado vía `dotenv` para comandos `workspace`) | `IMPROVEMENT`, ya documentado (Sprint 9.0) | No |
| Export Engine monolítico (`pipeline.run()` de Drills) | Deuda arquitectónica, ver §3.C | No (bloquea velocidad del *siguiente* módulo, no a Drills) |

No se ha inventado ningún blocker nuevo. La lista es idéntica a la ya cerrada en Sprint 9.3/9.3.1, sin reabrir NameEN.

---

## 2. Readiness estructural vs. readiness funcional — análisis, sin implementar

**El hallazgo es real**: `workspace readiness --module drills --operation full` devuelve `ready_with_warnings`, 0 blockers — mientras la evaluación funcional de este cierre dice que `NameEN` bloquea `DRILLS_ACCEPTED_FOR_FULL_READINESS`. No es una contradicción del software: son dos preguntas distintas respondidas correctamente cada una.

**Respuestas a las 3 preguntas planteadas:**

1. **¿Son dos conceptos distintos que debemos conservar? Sí.** `WorkspaceReadinessValidator` responde "¿existen los artefactos declarados, están donde el manifest dice, y hay autorización para tocar SQL?" — una pregunta **estructural, objetiva, binaria** (el archivo existe o no). La pregunta que `NameEN` plantea es **funcional/de conocimiento, subjetiva, evolutiva** (¿es esta fila de datos suficientemente confiable para cargarse?) — depende de una regla de negocio no verificada, no de la presencia de un fichero. Fusionarlas perdería la garantía actual de que "0 blockers estructurales" es una afirmación *simple y siempre verificable offline*.

2. **¿Debería el futuro `WorkspaceReadinessValidator` incorporar blockers de conocimiento gobernado? No, tal cual está diseñado hoy.** Haría que un validador pensado para I/O/estructura (nunca abre ni lee contenido, según su propio diseño) tuviera que interpretar el contenido semántico de `config/exports/*.yaml` y del estado de cada `KC-*`/hallazgo — un tipo de conocimiento que cambia con cada decisión humana, no con la presencia de un fichero.

3. **Recomendación: capa separada**, con el mismo patrón ya validado (validador puro, vocabulario cerrado `frozenset`, nunca abre SQL) pero operando sobre una entrada distinta: no el `WorkspaceManifest`, sino la combinación `config/exports/<módulo>.yaml` (`fields[]`, `excluded_columns[]`) + un registro ligero de conocimiento por campo (algo como `field_status: VERIFIED | STRONGLY_EVIDENCED | UNRESOLVED_BLOCKING | ...`, exactamente el vocabulario ya usado manualmente en Sprint 9.3/9.3.1). Produciría un veredicto **independiente** (p. ej. `MAPPING_READY` / `MAPPING_READY_WITH_ACCEPTED_RISK` / `MAPPING_BLOCKED`), compuesto **junto a**, nunca dentro de, `WorkspaceReadinessValidator`. No se fija el nombre definitivo — se documenta la necesidad y el patrón a seguir.

**No implementado en este cierre** — no es trivial ni corrige una inconsistencia peligrosa (la inconsistencia es de *expectativa*, no de seguridad: nadie puede cargar nada a Enablon desde este repo, y `approved_for_enablon_import: false` ya es un cierre estructural adicional). Queda documentado como diseño para un sprint posterior.

---

## 3. Drills como Golden Reference Module — inventario

### A. Core genérico ya reutilizable (sin cambios necesarios)
`WorkspaceManifest`/`WorkspaceManifestLoader` · `ResourceResolver` · `DataWorkspace` · `ModuleRegistry`/`ModuleDefinition` · `StageRegistry` · Contratos del Framework Core v1 (`ExecutionRequest`/`ExecutionContext`/`PipelineDefinition`/`StageResult`/`ArtifactReference`/`StageMetrics`) · SQL Execution Guard · `query_runner.py`/`connection.py` (con la observabilidad de Sprint 9.1) · `WorkspaceReadinessValidator` (en su alcance estructural) · `evidence/collector.py`.

Verificado por inspección en varios de estos módulos (ya documentado en su propio código): cero imports de `src.export`/Drills.

### B. Drills-specific pero con interfaz correcta (patrón a replicar, no a copiar literal)
- `src/bootstrap/module_registry.py` (composition root: `_build_drills_definition` + `_drills_pipeline_factory`) — es exactamente la forma que debe tomar el registro de cualquier módulo nuevo.
- `src/export/prototype/drills/core_adapters.py` (`DrillsQueryStage`/`DrillsCanonicalizeStage`/`DrillsTransformExportStage`/`DrillsEvidenceStage`, `register_drills_stages`, `build_drills_pipeline_definition`, `build_execution_context`) — implementa las interfaces de `Stage`/`PipelineFactory` correctamente.
- `DRILLS_FILTER_CATALOG` (`src/query/catalog.py`) — datos específicos de Drills, pero el mecanismo (`ObjectFilterCatalog`, `compile_filter_tokens`, `compose_filtered_sql`) ya es genérico y reutilizable tal cual.
- `config/exports/drills.yaml` — datos específicos, pero el esquema (`source`/`output`/`fields`/`excluded_columns`/`reference_data`) sirve de plantilla.

### C. Drills-specific que debería generalizarse antes del segundo/tercer módulo
- **`pipeline.py::run()`** — monolítico (mapping+validation+export+comparison+manifest en una función), ya señalado como "adaptador temporal, deuda técnica documentada" en el propio código. Hoy **no existe un Export Engine genérico**: un segundo módulo tendría que escribir su propio equivalente monolítico desde cero.
- **`comparison.py`** — solo procesa `.csv` (Sprint 9.3, backlog P2 ya documentado).
- **`mappings.py::EntityCatalog`** — genérico en forma (patrón `resolved`/`do_not_migrate`/`unresolved`/`conflicting`/`empty`, nunca fallback silencioso), pero atado a la estructura del catálogo antiguo de Simulacros. Un módulo que use el catálogo First_Axis vigente (Safety Meetings, MOC, Bypass) necesita su propia función de resolución sobre esa estructura distinta.
- **El "Project Contract definitivo"** (tabla de 18 columnas, Sprint 9.3) es hoy un documento **manual** — no se deriva automáticamente de Template+Operational+config.

### D. Prototipo/deuda que no debemos copiar
- Copiar-pegar `pipeline.run()` para el siguiente módulo duplicaría la deuda en vez de resolverla — al menos extraer las partes genéricas (escritura atómica de YAML, cálculo de hashes, construcción de manifest) sería preferible cuando se aborde.
- El manifest sintético de comparación (`_build_drills_comparison_manifest`, hoy fallback) — patrón a no repetir; el siguiente módulo debe usar `--manifest` desde el diseño inicial.
- Los `"HALLAZGO: ..."` embebidos como strings sueltos en `limitations` — funcionan, pero no son estructurados; ver Fase 7 (Field Constraints) para una alternativa declarativa.

---

## 4. Module Adapter Contract v0.1 (propuesta, no implementada)

Derivado de lo que Drills ya demuestra en la práctica, no de una lista genérica:

**Lo que Core ya provee (el módulo no lo reimplementa):**
`ExecutionRequest`/`ExecutionContext`/`PipelineDefinition`/`StageResult`, `StageRegistry`, `ModuleRegistry`, `WorkspaceManifest`+`ResourceResolver`, SQL Execution Guard, Query Engine (parser/validator/sql_builder — el módulo solo aporta su catálogo), `evidence/collector.py` (si el módulo escribe `validation_report.yaml`/`export_manifest.yaml`/`comparison_report.yaml` con el esquema esperado), `WorkspaceReadinessValidator`.

**Lo que cada módulo declara (config, sin código):**
`module_id`/`canonical_name`/`aliases`; `source` (conexión, SQL, `max_rows`); `output` (encoding/delimiter/quoting); `fields[]` (`source`/`target`/`transformation`/`validation`/`evidence_id`/`default`); `excluded_columns[]` (mismo patrón ya usado); `reference_data` (catálogos/lookups estáticos).

**Lo que cada módulo programa (código mínimo, mismo patrón que Drills):**
Su `ObjectFilterCatalog` propio; sus funciones de transformación puras; su composition root (3 funciones: `register_stages`, `build_pipeline_definition`, `build_execution_context`); su función de extracción (`extract_<módulo>`).

**Lo que se obtiene del workspace (sin código nuevo):** Project Contract (`operational_csv`) vía `ResourceResolver`+`--manifest`; Template (`template_csv`) como control secundario.

**Lo que se obtiene de knowledge (hoy solo documental, no automatizado):** catálogo de entidad aceptado por módulo (`config/modules.yaml`); conflictos de conocimiento (`KC-*`) — sin conectar todavía a readiness (§2).

**Lo que el framework valida automáticamente hoy:** estructura del manifest; presencia física de artefactos requeridos; autorización SQL antes de cualquier conexión real; sintaxis de filtros contra el catálogo cerrado.

**Lo que el framework NO valida automáticamente todavía:** fidelidad de mapping por campo (Sprint 9.2/9.3: manual); estado de conocimiento gobernado por campo (§2).

No se implementa — es un refactor no trivial (extraer el Export Engine de `pipeline.run()`), correctamente fuera de alcance de este cierre.

---

## 5. Siguiente módulo — recomendación basada en evidencia

| Candidato | Conocimiento | ETL | SQL | Operational | Template | Mapping | Conflictos abiertos | Cross-module | Complejidad | Valor generalidad |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bypass** | Alto, cerrado | Sí, 31 hojas, sin huérfanas | Sí | Único, sin ambigüedad | **Ausente** (gap, no ambigüedad) | Resuelto (First_Axis) | Ninguno | Bajo | **Baja** | Alto — 2º objeto real de un solo target, sin forzar cambios de Core |
| Safety Meetings | Alto, cerrado | Sí, 40 hojas | Sí | 2 candidatos (ambiguo) | 2 candidatos (ambiguo) | Resuelto (First_Axis) | Ninguno crítico | Bajo | Media | Alto — pero **fuerza** resolver el límite de esquema "1 artefacto por kind" (§2) como prerrequisito |
| MOC | Alto, con defectos documentados | Sí, 2 versiones | Sí | 2 candidatos | 2 candidatos | Resuelto (First_Axis) | **Sí** — hallazgo_1 sin resolver, sistema GCT con `IDCentro` propio | Alimenta Acciones (AP_GCT) | Alta | Medio — arrastra Hallazgo #1 |
| OPS | Medio | Sí, 62 hojas | Sí | Único, sin ambigüedad | Ausente (gap) | Resuelto (First_Axis) | Nombre real "JSO" no "OPS" | Bajo | Baja-media | Medio |
| Events | Alto pero disperso | Sí, 2 versiones (`FULL JOIN`) | Sí | **12 candidatos** (backlog P1-07) | 6 candidatos | Resuelto (First_Axis) | **Sí** — Hallazgo #1 confirmado aquí | Alto | **Muy alta** | Alto, pero no como #2 |
| Inspections | Alto | Sí, 85 hojas | Sí | **9 candidatos** (backlog P1-08) | 3 candidatos | Resuelto (First_Axis) | Probable Hallazgo #1 | Medio | Alta | Medio |
| Action Plans | Muy alto (C003, Sprint 8.9) | Sí, 2 ETL de **ámbitos distintos** | Sí | 3 candidatos, columnas distintas (33/31/31) | **Ausente** | **Bloqueado por KC-AP-001** | **Sí, abierto** | **Transversal a todos los módulos** | **Muy alta** | Alto, pero de alto coste/riesgo |

### Recomendación: **Bypass** como segundo módulo

No es la opción con más conocimiento acumulado (Action Plans lo tiene), pero es la que minimiza fricción **sin** dejar de ser una prueba real de generalidad: mismo patrón de un-solo-objeto que Drills, sin Hallazgo #1, sin conflictos de conocimiento abiertos, sin ambigüedad de candidato Operational, mapping ya resuelto. Es el camino más corto para demostrar `DRILLS WAS NOT A ONE-OFF` sin arrastrar ninguna de las complejidades ya conocidas de los demás.

**Action Plans explícitamente descartado como #2** (tal como advertía el propio encargo): mucho conocimiento no compensa la complejidad transversal + `KC-AP-001` abierto — sería repetir el patrón de Events/Inspections (ambigüedad + conflicto sin resolver) justo cuando el objetivo es demostrar velocidad.

**Safety Meetings recomendado como #3** — específicamente porque **fuerza** a resolver el límite de esquema "un solo artefacto por kind" (§2), y conviene abordarlo como su propia pieza de trabajo, no mezclado con la primera repetición del patrón Drills.

---

## 6. Roadmap conceptual (sin falsa precisión)

| Área | Estado actual | Qué falta | Qué bloquea | Incremental |
|---|---|---|---|---|
| 1. Core/architecture | Sólido, probado con datos reales | Export Engine genérico; capa `ContractReadiness`; soporte XLSX en comparison | Nada crítico hoy | Sí |
| 2. Drills reference implementation | `DRILLS_FUNCTIONALLY_VALIDATED` | `NameEN` (bloqueo externo) | Solo `ACCEPTED_FOR_FULL_READINESS` | Sí |
| 3. Knowledge ingestion/governance | Metodología probada (KC-*, C003) | Conectar a readiness automatizada | Automatización, no el trabajo manual ya hecho | Sí |
| 4. Multi-module capability | 1 módulo registrado (Drills) | Registrar un 2º módulo real (single-object primero) | Los 3 límites de esquema bloquean módulos multi-objeto, no single-object | Sí, por partes |
| 5. Action Plans/cross-module | Mucho conocimiento, adaptador solo diseñado | Resolver `KC-AP-001`; implementar el adaptador nativo | Es el más complejo — no priorizar como #2 | Sí, alto coste |
| 6. Validation/comparison | 120/120 demostrado manualmente | Soporte XLSX genérico (diseño ya propuesto, P2) | Solo automatización | Sí |
| 7. Evidence | Generado correctamente 3 veces | Confirmar genericidad completa de `workbook.py` (no verificado a fondo) | Nada conocido | Sí |
| 8. Readiness | Estructural, probado | Capa funcional/conocimiento (§2) | Distinción automática "puede ejecutar" vs. "es confiable" | Sí |
| 9. UI | Sin empezar | Todo | Nada todavía (objetivo, no bloqueante) | Sí, no prioritario ahora |
| 10. Packaging/distribution | Sin empezar | Todo | Nada todavía | Sí, más adelante |

### Hitos

- **A — Segundo módulo ejecutable offline/sample**: registrar Bypass en `ModuleRegistry` (mismo patrón que Drills) + su `config/exports/bypass.yaml` + su filter catalog + sus transformaciones. No requiere resolver ningún gap de Core.
- **B — Segundo módulo validado contra datos reales**: mismo patrón de Sprint 9.2/9.3 — autorización SQL real + comparación manual contra su Operational único.
- **C — EMF procesa varios módulos de Moeve de forma consistente**: requiere resolver el límite "1 artefacto por kind" (§2) antes de Safety Meetings/MOC/Events, y decidir la capa `ContractReadiness`/`MappingReadiness` para no repetir la comparación manual campo a campo en cada módulo.
- **D — Primer EMF "usable" en migraciones reales**: requiere Action Plans (transversal, alto valor) y probablemente el Export Engine generalizado (§3.C) para no multiplicar `pipeline.run()` monolíticos.
- **E — Producto amigable para usuario final**: UI web local + backend EMF desacoplado + empaquetado como aplicación de escritorio/`.exe` — decisión de producto ya tomada, **objetivo arquitectónico conservado, sin diseñar todavía**.

---

## 7. Mejora futura — Field Constraints (documentada, no implementada)

Necesidad real (no hipotética): Enablon impone restricciones por campo (p. ej. longitud máxima de un `Title`/`Name`) que hoy solo se resolverían con lógica ad hoc dispersa (`value[:20]`) si empezáramos a implementar campos de texto libre como `NameEN`.

**Recomendación de ubicación arquitectónica**: vivir en el Project Contract / Field Contract — como una extensión declarativa de las entradas `fields[]` que ya existen en `config/exports/*.yaml` (mismo lugar que ya declara `source`/`target`/`transformation`/`validation`/`default`), aplicada por un paso de transformación genérico compartido (no por módulo).

**Conceptualmente:**
```yaml
max_length: 20
overflow_policy: truncate   # una de varias, NO asumir truncate por defecto
```

**Políticas a soportar, sin asumir cuál es la de defecto**: `truncate` · `reject` · `warn` · `null` · `manual_review`. La decisión de cuál aplica por campo es de negocio, no técnica — el motor debe soportar las cinco, nunca fijar una.

Cualquier aplicación de esta regla debe quedar trazada en Evidence (qué valor original, qué política se aplicó, qué valor final) — mismo principio ya vigente en todo el resto del pipeline ("nunca silencioso").

No implementado — documentado como necesidad para un sprint futuro, más relevante en cuanto se aborde `NameEN` o cualquier otro campo de texto libre.

---

## 8. Commits y push

| Commit | Alcance |
|---|---|
| `90d7c89` | `fix(db): add safe SQL failure diagnostics` (Sprint 9.1) |
| `f240a7e` | `feat(drills): resolve comparison Project Contract from real workspace manifest` (Sprint 9.2) |
| `dff14f2` | `fix(drills): derive StartingDate from combined date and time` (Sprint 9.3) |
| `da6d9b3` | `docs(moeve): document Sprint 9.0 workspace activation findings` (Sprint 9.0, identificado y comiteado en este cierre) |

Los 4 commits verificados individualmente (antes y en este cierre) sin datos reales, sin outputs reales, sin `workspace.yaml` real, sin `.env`, sin `.claude/settings.local.json`, sin credenciales.

**Push realizado**: `git push origin feature/drills-filtered-exports` → `799da9d..da6d9b3`. Confirmado `local HEAD == remote HEAD` = `da6d9b371fcbc4ca0a8b6b6a9d285d2c29632001`. Sin force push, sin rebase, sin tags, sin cambio de rama.

## 9. Tests finales

`755 passed, 7 skipped` — confirmado antes y después de cada commit de este cierre. Sin cambios de código en este cierre (solo documentación), por lo que el número no varió respecto al checkpoint de Sprint 9.3.1.

## 10. Riesgos / deuda técnica (resumen)

1. `NameEN` — bloqueo externo, no técnico, ya escalado a decisión humana.
2. Export Engine monolítico — ralentiza al segundo módulo si se copia tal cual (§3.C/D).
3. Comparison sin soporte XLSX — automatización pendiente, P2.
4. Límite de esquema "1 artefacto por kind" — bloqueará Safety Meetings/MOC/Events hasta resolverse (§2, §6 Hito C).
5. Sin capa `ContractReadiness`/`MappingReadiness` — la distinción estructural/funcional sigue siendo manual (§2).
6. Field Constraints — necesidad identificada, no implementada (§7).

## 11. Acciones expresamente NO realizadas (por instrucción explícita)

- No se ejecutó SQL real en ningún momento de este cierre.
- No se ejecutó `full` export.
- No se investigó más a fondo `NameEN` (Micro-Sprint 9.3.1 ya se consideró agotado).
- No se implementó Module Adapter Contract, `ContractReadiness`/`MappingReadiness`, soporte XLSX, ni Field Constraints — todo quedó documentado como propuesta/diseño para sprints futuros.
- No se empezó Action Plans ni ningún otro módulo.
- No se realizaron refactors oportunistas del Export Engine ni de `pipeline.run()`.
- No se tocó `.claude/settings.local.json`.
- No se versionó ningún dato real de cliente, `workspace.yaml` real, ni output real.
