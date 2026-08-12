# Informe de Ejecución — Sprint 8.8.1: Knowledge Closure

**Fecha:** 2026-08-12
**Rama:** `feature/drills-filtered-exports`
**Alcance:** Cierre de los 3 grupos de trabajo abiertos por Sprint 8.8
(`KC-AP-001`, los 2 `.zip` sin inspeccionar, `OQ-ETL-01`/`OQ-ETL-02`). Sin
ejecución de SQL Server, macros ni recálculo. Sin commit — Sprint 8.8
sigue pendiente de commit, ver § 16 para la estrategia combinada.

## 1. `KC-AP-001`

**No se cierra — pero queda sustancialmente mejor caracterizado.** La
inspección autorizada de `Mappings/OneDrive_2_12-8-2026.zip` encontró un
tercer grupo de fuentes: workbooks de mapeo de eje **dedicados y
versionados**, independientes de los ETL —
`Mapeo ITP primer eje enablon_revisado _final1 (version 4).xlsx` para
ITP-genérico y 3 workbooks `Mapeos Eje - GCT/` para GCT.

Comparando **contenido real de fila** (no fórmula) se confirmó que la
hoja `Entidades_Mapeo` embebida en 8 de los 11 ETL es una **instantánea
de valores** de la hoja `MAPEOFINAL` de ese workbook ITP "version 4"
(fila 2 idéntica: `IDCentro=7`/`IDDepartamento=77`/`IDUnidadOrg=278`,
"MC-Palos de la Frontera"/"CONTRATAS GENERICAS"/"MCPF Histórico") — y que
la hoja `Exportación eje` embebida en `ap_gct`/`moc_m_new`/
`moc_newcolumns` es, del mismo modo, una instantánea de
`260311 Mapeo gct Enablon-Match UORG ENTIDAD.xlsx`.

**Conclusión revisada:** el sistema ITP **sí tuvo** un esfuerzo de mapeo
de eje dedicado, tan real y tan versionado ("version 4, final1") como el
de GCT — no es cierto que "GCT se modernizó y a ITP no se le hizo caso".
Lo que distingue a los dos sistemas es que el mecanismo de GCT
(`MapeoEje_uorg`/`Exportación eje`) **se re-sincroniza en cada
regeneración del ETL** contra un catálogo vivo, mientras que
`Entidades_Mapeo` es una instantánea congelada en el momento de esa
"version 4" — lo que explica, sin contradecir, el hallazgo ya validado
empíricamente en `CLAUDE.md` (42–59% "no catalogado" al usarla
directamente): no es que el mapeo ITP nunca fuera real, es que quedó fijo
mientras el eje de Enablon seguía evolucionando después de esa entrega.

**Pregunta que sigue abierta:** si los 7 ETL de ámbito ITP-genérico se
resincronizaron desde esa "version 4" en algún momento posterior, o si
quedaron congelados en ella. `KC-AP-001` permanece `OPEN`, con esta
caracterización nueva registrada en
`config/knowledge/moeve/ap/knowledge-conflicts.yaml` (`status_note_8_8_1`)
y en `docs/01-architecture/mapping-governance.md` § 12.1.

## 2. Estado MOC/GCT

Confirmado y sin cambio respecto a Sprint 8.8: el mecanismo de catálogo
vivo (`MapeoEje_uorg`+`Exportación eje` para AP-GCT; `Niveles`+
`Exportación eje` para MOC) es la evidencia funcional más reciente para
el ámbito MOC/GCT. La inspección del ZIP confirma además que ese
mecanismo tiene un origen documental propio y mantenido (los workbooks
`Mapeos Eje - GCT/`), no solo una copia embebida sin trazabilidad.

## 3. Estado ITP

Ver § 1. Actualizado de "mecanismo desconocido/quizás nunca actualizado"
a "mecanismo real y versionado, pero potencialmente congelado en el
tiempo desde su última entrega verificada (version 4)". No se etiqueta
el ETL ITP-genérico como obsoleto en su totalidad — la posible
obsolescencia afecta específicamente al mecanismo de mapeo del eje, no
al resto de sus reglas (que siguen siendo la evidencia funcional válida
para todos los demás campos).

## 4. ZIP inspeccionados

| ZIP | SHA-256 | Entradas | Método |
|---|---|---:|---|
| `Mappings/OneDrive_2_12-8-2026.zip` | `4e0d5a8e3d1b75be9ce9e7efdf06b3f053fa38f77e79db3322eac3066f12c01c` | 10 | Solo lectura, extracción a carpeta temporal fuera del repositorio y de las carpetas fuente, `testzip()` verificado antes/después, copia temporal eliminada al finalizar |
| `SQL/OneDrive_1_12-8-2026.zip` | `8d8e214f20a8dff3df0c89464b5da6d2e3a879fb53829c0fc5780d6c57b15438` | 43 | Igual método |

Ningún contenido se ejecutó (sin macros, sin SQL, sin recálculo, sin
Power Query). Ningún dato real de fila se copió al repositorio — solo
metadata, identidad de hoja/regla y fórmulas/código tal cual (que son
código, no datos personales o de fila).

## 5. Nuevos mappings

- 2 workbooks de mapeo de eje ITP/GCT dedicados (§ 1).
- El motor real del ETL: `Script ETL.txt` (código TypeScript/Office
  Script completo) — resuelve `KC-MOC-002` (el motor **no es VBA**, ver
  § 7) y confirma con código real el comportamiento exacto de
  `titlefix`, `nullcontrol`, `concat`/`barconcat`, `replaceinreference`
  (antes "no verificado"), `boolorigin` (antes "no verificado"). Revela
  2 reglas nuevas no documentadas en `CLAUDE.md` (`cloneto`,
  `countIterations`/`countIterationList`) y 2 operadores de condición
  nuevos (`igualvalor`, `contains`). Tabla completa en
  `docs/01-architecture/mapping-governance.md` § 6.
- Dos documentos de asunciones/procedimientos del consultor original —
  candidatos directos a resolver el ticket de cliente `#7581`
  (documentación de mapeo ya solicitada, ver `CLAUDE.md`). Ver backlog
  P1-10.

## 6. Nuevas queries

Ninguna. La reconciliación SQL (§ 4bis más abajo) confirmó que el 100%
del contenido del zip de SQL ya está versionado en el repositorio.

## 7. Conflictos

| ID | Estado antes de 8.8.1 | Estado después | Resumen |
|---|---|---|---|
| `KC-AP-001` | `OPEN`, sin caracterizar | `OPEN`, bien caracterizado | Ver § 1 |
| `KC-MOC-002` | `OPEN` | **`RESOLVED`** | Motor = Office Script, no VBA (código fuente real encontrado) |
| `KC-ITP-003` | `OPEN` (informativo) | `OPEN` (informativo, más preciso) | Ver § 3 |

## 8. `OQ-ETL-01`

**`RESOLVED`.** Dos mecanismos independientes alimentan
`CS_HistoricalDrillAttendees`:

- Workbook: `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`. Hoja `MapeoSims`,
  fila 27 (`CampoOrigen=Asistentes`): `Adaptación=No` → passthrough
  directo del texto libre `Asistentes` de `DB_OrigenSim`.
- Hojas `Mapeo_asistentes`/`Mapeo_asistentes_EXT`
  (`CampoOrigen=NombreAsistente`, `Adaptación=Sí`,
  `Transformation From=Asis_concat`): concatenación fila a fila (una por
  asistente en `ITP_ASIST_SIMS`/`ITP_ASIST_SIMS_EXT`) vía la regla
  `concat`, que **añade** (no sobrescribe) al valor ya presente,
  separador `\r\n` por defecto.

Interpretación: el resultado esperado es el texto libre histórico más,
a continuación, los nombres individuales concatenados. Confianza: alta
(mecanismo confirmado por celda real + código del motor). Orden exacto
de ejecución y deduplicación entre ambos mecanismos queda como ítem
residual de baja prioridad (backlog P1-09).

## 9. `OQ-ETL-02`

**`RESOLVED`.** Workbook: `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`.
Hoja `MapeoSims`, fila 27 (`CampoOrigen=Duracion`, resolviendo
manualmente la fórmula `XLOOKUP` de la fila → destino real `CS_Duration`,
fila 13 de la misma hoja): `Adaptación=No` → **passthrough directo, sin
recombinación**.

La hoja `CalculoHorasDiasMinutos` (candidata identificada en Sprint 8.8)
**no** alimenta `CS_Duration` de Drills — alimenta 4 campos separados
(`CS_DurationMonths/Days/Hours/Minutes`) de un objeto distinto
(`List of Activities`, BCM), con fórmulas confirmadas: mes fijo de 30
días, redondeo a 5 minutos — igual al comportamiento ya documentado en
`CLAUDE.md`, pero para ese objeto, no para Drills. Confianza: alta
(`Adaptación=No` es un flag explícito, sin necesidad de evaluar
fórmulas).

## 10. Backlog actualizado

Registro completo de cambios (estado anterior → nuevo, evidencia,
motivo) en `docs/07-developer-guide/moeve-mapping-backlog.md` § 0.
Resumen:

| Prioridad | Ítems Sprint 8.8 | Cerrados en 8.8.1 | Abiertos tras 8.8.1 |
|---|---:|---:|---:|
| P1 | 8 | 3 | 7 (5 originales + 2 nuevos) |
| P2 | 6 | 0 | 6 |
| P3 | 4 | 1 | 5 (3 originales + 2 nuevos) |
| P4 | 1 | 0 | 2 (1 original + 1 nuevo) |
| **Total** | 19 | 4 | **20** |

No se recalculó ninguna cobertura global (`Operational Mapping
Coverage`) — sigue sin metodología suficiente para publicarse de forma
honesta (ver `moeve-mapping-backlog.md` § 1, sin cambios de fondo en
8.8.1 salvo 2 filas de la tabla § 1.1 actualizadas con las reglas
recién resueltas).

## 11. Estado de los documentos Sprint 8.1

| Documento | Decisión | Motivo |
|---|---|---|
| `docs/01-architecture/knowledge-traceability-matrix.md` | **`KEEP_AND_UPDATE`** — actualizado en este sprint | Filas `CS_Duration` y `CS_HistoricalDrillAttendees` pasaron de 🟡 a 🟢 con la evidencia de `OQ-ETL-01`/`02` resueltas (§ 8, § 9). Resumen numérico actualizado (10 🟢, 4 🟡, 22 🔴). |
| `docs/01-architecture/drills-csv-contract.md` | `KEEP_AND_UPDATE` (no editado todavía) | Sigue siendo una descripción correcta de las 8 columnas implementadas. No requiere cambio solo porque se resolvió *conocimiento* de 2 columnas más — cambiará cuando ese conocimiento se convierta en código (`config/exports/drills.yaml`), que es trabajo de un incremento futuro, no de este sprint de solo-inspección. |
| `docs/01-architecture/knowledge-coverage-matrix.md` | `KEEP_AND_UPDATE` (no editado todavía) | Su alcance (código/config, no ETL) no cambia por este sprint. Ya usa una metodología correcta (no cuenta las 28 columnas Template no implementadas como "gaps" sin más — distingue exclusión documentada de brecha real). |
| `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md` | **`ARCHIVE`** | Informe de ejecución puntual del Sprint 8.1 — por diseño, un registro histórico inmutable, no un documento vivo. Su § 7 usa "Template Contract — 8/36 columnas" como medida de cobertura, un denominador que `project-contract-model.md` (Sprint 8.2, posterior) desaconseja como objetivo del EMF. Esto **no es un error del informe** (fue honesto con la metodología disponible en su momento) — es metodología superada, no un hecho falso. No se edita un informe de ejecución fechado para "arreglarlo" retroactivamente; se archiva con esta nota y se dirige al lector actual hacia `project-contract-model.md` + `moeve-mapping-backlog.md` § 1 para la metodología vigente. |
| `reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt` | **`ARCHIVE`** | Misma razón — versión `.txt` del mismo informe. |

Ninguno de los 5 se borra ni se commitea en este sprint — la decisión
queda registrada aquí para que el commit propuesto (§ 16) la incluya
explícitamente cuando el usuario lo apruebe.

## 12. Readiness para Sprint 9.0

**No se ejecuta `workspace readiness` contra recursos reales** (no existe
todavía un manifest real de Moeve — el único manifest de ejemplo en el
repositorio es `tests/fixtures`/documentación, no uno declarado para el
workspace real inspeccionado en 8.8/8.8.1).

| Requisito Sprint 9.0 | Estado |
|---|---|
| ETL disponibles | ✅ 11/11 inventariados y clasificados por módulo |
| CSV Operational disponibles | ✅ 30 CSV + 2 XLSX, inventariados por módulo |
| CSV Template disponibles | ⚠️ Parcial — 14 de 9 módulos; `bypass`, `ops`, `ap` sin Template en este workspace |
| Mappings disponibles | ✅ `AttachmentsLast.csv` + workbooks de eje ITP/GCT dedicados (recién inventariados) |
| Errors disponibles | ⚠️ Parcial — 28 tickets inventariados, solo 3 clasificados individualmente |
| SQL disponibles | ✅ 48 queries versionadas en el repositorio, reconciliadas 100% contra el zip de origen |
| Knowledge governance establecido | ✅ `mapping-governance.md` + `knowledge-source-governance.md`, con esquema de identidad de regla y precedencia de evidencia |
| Conflictos P1 conocidos | ✅ 3 `KNOWLEDGE_CONFLICT` registrados (1 resuelto, 2 abiertos y caracterizados) |
| Workspace manifest real pendiente | ❌ No existe todavía un `config/knowledge/moeve/<módulo>/`completo para los 9 módulos — solo `ap` materializado como ejemplo |
| Project Contracts identificables | ✅ 8 de 9 módulos con Project Contract identificado a nivel de columnas (falta profundidad celda-a-celda en 7) |

**Clasificación: `NOT_READY_FOR_ACTIVATION`.**

Razón: el conocimiento de gobierno (precedencia, identidad de regla,
conflictos) está listo, y el inventario físico está completo — pero
faltan 2 cosas estructurales antes de activar Sprint 9.0 formalmente:
(1) el manifest de workspace real de Moeve no está declarado en
`config/data_workspace.yaml`/`config/modules.yaml` con el detalle
columna-a-columna que Sprint 9.0 necesitaría para operar sobre datos
reales; (2) 7 de 9 módulos no tienen ninguna regla de campo confirmada a
nivel de celda (solo a nivel de patrón de hoja) — backlog P1-05 a P1-08.
Esto **no** significa "no ready para sample" en el sentido de
autorización SQL (eso lo rige `sql-execution-guard.md`, sin relación con
este sprint) — significa que la base de conocimiento todavía no
sostendría una implementación de motor confiable para 7 de 9 módulos.

## 13. Tests

`pytest tests/ -v` → **714 passed, 7 skipped** (idéntico antes y después
de este sprint). No se modificó ni se añadió código funcional — todo el
trabajo de 8.8.1 fue inspección y documentación.

## 14. `git status --short`

```
 M .claude/settings.local.json
?? config/knowledge/
?? docs/01-architecture/drills-csv-contract.md
?? docs/01-architecture/knowledge-coverage-matrix.md
?? docs/01-architecture/knowledge-source-governance.md
?? docs/01-architecture/knowledge-traceability-matrix.md
?? docs/01-architecture/mapping-governance.md
?? docs/07-developer-guide/moeve-mapping-backlog.md
?? docs/07-developer-guide/moeve-source-inventory.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.md
?? reports/executions/2026-07-27/Informe-Knowledge-Audit-EMF.txt
?? reports/executions/2026-08-12/
```

`.claude/settings.local.json` es configuración de permisos de la sesión
de herramientas, ajena a ambos sprints — no se incluye en ninguna
propuesta de commit.

## 15. `git diff --stat`

```
 .claude/settings.local.json | 10 +++++++++-
 1 file changed, 9 insertions(+), 1 deletion(-)
```

(único archivo con diff — todo lo demás es `??`, sin versionar todavía).
`git diff --check`: sin salida, 0 problemas de espacio en blanco.

## 16. Propuesta de commits (combinada 8.8 + 8.8.1, no ejecutados)

Sprint 8.8 quedó sin commitear por diseño. Sprint 8.8.1 modificó 2 de
los archivos que 8.8 había creado (`mapping-governance.md`,
`moeve-source-inventory.md`, `moeve-mapping-backlog.md`, y los YAML de
`config/knowledge/moeve/ap/`) antes de que existiera ningún commit —
por lo que la estrategia lógica es **combinar ambos sprints en la misma
serie de commits**, no crear una serie paralela de "fixups":

1. **Mapping governance**: `docs/01-architecture/mapping-governance.md`
   (ya incluye el contenido de 8.8 y el cierre de 8.8.1 en un único
   archivo coherente), `docs/01-architecture/knowledge-source-governance.md`.
2. **Moeve source inventory / knowledge**:
   `docs/07-developer-guide/moeve-source-inventory.md`,
   `docs/07-developer-guide/moeve-mapping-backlog.md`,
   `config/knowledge/moeve/ap/` (con el contenido ya actualizado por
   8.8.1, no dos commits separados por sprint).
3. **Sprint 8.1 — actualización de conocimiento**:
   `docs/01-architecture/knowledge-traceability-matrix.md` (única
   edición real a un artefacto de Sprint 8.1 en este sprint).
4. **Código genérico nuevo**: ninguno en 8.8 ni en 8.8.1 — los
   inspectores Python usados en ambos quedaron en scratchpad de sesión.
5. **Documentación e informes**: los 2 informes de Sprint 8.8
   (`Informe-Mapping-Governance-Moeve-EMF.md/.txt`) + los 2 de Sprint
   8.8.1 (este informe, `.md`/`.txt`).
6. **Decisión pendiente, no incluida en ningún commit todavía**: los 5
   documentos de Sprint 8.1 restantes (`drills-csv-contract.md`,
   `knowledge-coverage-matrix.md`, los 2 informes `Informe-Knowledge-Audit-EMF.*`)
   quedan clasificados (§ 11) pero **no** se incluyen en la propuesta de
   commit hasta que el usuario confirme que quiere incorporarlos ahora
   (fueron creados en un sprint anterior a este, fuera del control de
   cambios de 8.8/8.8.1).

Ningún dato real del workspace externo se incluye en ninguno de los
commits propuestos.
