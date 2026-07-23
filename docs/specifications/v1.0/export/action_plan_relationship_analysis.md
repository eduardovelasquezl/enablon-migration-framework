# Análisis cuantitativo de relaciones de Action Plans — Export Specifications v1.0

> Responde a las Tareas 8, 9 y 10 de este incremento. Calculado sobre el
> CSV real `Action Plans-20072026-41.csv` (31444 filas, Bloque4) mediante
> lectura directa en modo solo lectura — ningún archivo modificado, ninguna
> lógica de `src/` alterada. Ver `evidence/action_plan_relationship_assessment.yaml`
> para el detalle estructurado completo. Ningún identificador histórico
> completo se reproduce en este documento — todos los ejemplos usan hash
> SHA-256 truncado a 10 caracteres.

## 1. Método

Se leyó el CSV completo (tab-delimited, UTF-16LE) con `csv.reader` en modo
`quotechar='"'`, sin usar librerías que pudieran alterar el archivo. Se
usaron los índices de columna reales confirmados por lectura de cabecera:
`CS_HistoricalDataOrigin` (65), `CS_HistoricalAPID` (66),
`CS_HistoricalOriginID` (67), `Status` (38), y los 7 campos de enlace
(`BCCrisis`, `CS_ByPasses`, `CS_Meetings`, `MoCChange`,
`CS_IndependentManualEvents`, `CS_IndManualOPS`, `CS_IP`). "Padre" se
define como la clave compuesta `(CS_HistoricalDataOrigin,
CS_HistoricalOriginID)` — deliberadamente NO solo `CS_HistoricalOriginID`,
para no repetir el punto ciego de origen que ya causó el Hallazgo #1 en
otros módulos.

## 2. Resultado cuantitativo (Tarea 8)

| Métrica | Valor |
|---|---:|
| 1. Total de Action Plans | 31444 |
| 2. % con `CS_HistoricalAPID` | 99.81% (31384) |
| 3a. `CS_HistoricalAPID` distintos (global) | 29602 de 31384 no vacíos |
| 3b. Valores de APID duplicados | 1679 valores, afectando 3461 filas |
| 4. Total con `CS_HistoricalOriginID` | 99.997% (31443 de 31444) |
| 5. Padres distintos (compuesto sistema+OriginID) | 11920 |
| 6-7. Distribución de acciones por padre | 1: 6598 (55.35%) · 2: 2435 (20.43%) · 3-5: 1995 (16.74%) · 6-10: 554 (4.65%) · &gt;10: 338 (2.84%) |
| 8. Máximo de acciones por un mismo padre | 179 (sistema `Prevención.ITP_ACCIONES_CORRECTORAS`) |
| 9. Action Plans sin padre | 1 fila (0.003%) |
| 10. Action Plans con padre no resoluble | No cuantificable desde el CSV final — ver §5 |
| 11. APID asociado a varios padres | 1437 valores |
| 12. APID asociado a varios módulos/sistemas | 1437 valores (mismo conjunto que el punto 11 — ver §4) |
| 13. Padre asociado a tipos de objeto incompatibles | No evaluable — el CSV no tiene un campo de "tipo de objeto padre" independiente del sistema origen |
| 14. Colisiones entre source systems | 1437 valores de APID (ver §4) |
| 15. Excluidos / `do_not_migrate` | No medible desde este CSV (ver §5) |
| 16. Registros con identificadores vacíos | APID vacío: 60 filas (0.19%) · OriginID vacío: 1 fila (0.003%) |

## 3. Clasificación del 63% (Tarea 10)

El "63%" documentado en `config/modules.yaml:293` (11905 únicos de 31444)
**se reproduce casi exactamente** con la metodología naive (agrupar solo
por `CS_HistoricalOriginID`, ignorando el sistema origen): 11906 únicos de
31444 → 62.14%. Recalculando con la clave compuesta (sistema+OriginID) el
resultado es 62.09% — **prácticamente idéntico**. Esto significa que, para
esta métrica concreta, **la distinción de sistema origen no cambiaba el
resultado** — la colisión de `CS_HistoricalOriginID` entre Prevención y
GCT es rara.

**Aclaración metodológica importante**: el "63%" NO es "el 63% de las
filas comparten padre con otra fila" — esa proporción real es **79.01%**
(24845 de 31444 filas están en grupos de más de 1 acción). El "63%" es una
métrica distinta: la proporción de filas "excedentes" sobre una
representante por grupo — `(filas_en_grupos_compartidos - nº_de_grupos_
compartidos) / total`. Se documenta esta distinción para que ninguna
especificación futura reinterprete "63%" como "79%" ni viceversa.

**Clasificación**:

- **Porcentaje legítimo candidato**: 76.17% de las filas totales (23950 de
  31444) están en un grupo compartido donde **todos** los `CS_HistoricalAPID`
  son distintos — clasificado `legitimate_one_to_many_candidate`. Esto
  incluye 5227 de los 5322 grupos compartidos (98.2%).
- **Porcentaje conflictivo**: 1.10% de las filas (345 de 31444, en 95
  grupos) tienen `CS_HistoricalAPID` **repetido dentro del mismo padre** —
  clasificado `duplicate_action_candidate`. Adicionalmente, 1437 valores de
  APID (afectando potencialmente miles de filas, ver §4) presentan
  colisión cruzada entre sistemas — clasificado
  `cross_system_collision_candidate`, una categoría de anomalía DISTINTA
  de la duplicidad de `CS_HistoricalOriginID` ya conocida.
- **Porcentaje sin resolución**: 0.003% (1 fila sin `CS_HistoricalOriginID`).
- **Porcentaje independiente (standalone)**: 55.35% de los **padres** (no
  de las filas) tienen una única acción — en términos de filas, 6598 de
  31444 (20.98%).

**No se declara el 63%/79% como "validado"** en el sentido de aprobado
funcionalmente — la clasificación se apoya en un mecanismo estructural
observado (identidad `CS_HistoricalAPID` separada de la referencia al
padre `CS_HistoricalOriginID`, confirmada en el ETL, ver §4) y en
consistencia estadística, pero no en una confirmación explícita línea a
línea del cliente. Se marca `legitimate_one_to_many_candidate`, no
`legitimate_one_to_many` a secas, precisamente por esa distinción.

## 4. Hallazgo nuevo: colisión de identidad `CS_HistoricalAPID` entre sistemas (Tarea 8, puntos 11-12-14)

**El hallazgo más importante de este análisis.** 1437 valores de
`CS_HistoricalAPID` aparecen bajo **ambos** sistemas origen
(`Prevención.ITP_ACCIONES_CORRECTORAS` y `GCT.CT_ACCIONES`)
simultáneamente — es decir, el mismo número de identidad fue asignado
independientemente en dos sistemas distintos, sin ningún prefijo que los
distinga dentro de `CS_HistoricalAPID`. Esto es un hallazgo **distinto**
del ya conocido "63% comparten `CS_HistoricalOriginID`" — afecta la
IDENTIDAD de la acción (`CS_HistoricalAPID`), no la referencia a su padre.

**No se ha confirmado** si esto representa un riesgo funcional real —
es plausible que Enablon use su propio campo interno `Id` (no
`CS_HistoricalAPID`) como clave de unicidad real, en cuyo caso esta
colisión sería inocua para la carga ya realizada, pero relevante para
cualquier proceso futuro que use `CS_HistoricalAPID` como si fuera único
globalmente. Ver `open_questions.md` (`OQ-AP-06`, nueva).

## 5. Limitaciones que impiden cuantificar completamente Tarea 8 (puntos 10, 13, 15)

- **Padre no resoluble (punto 10)**: se localizó un mensaje de fallo
  literal (`"No se encuentra evento nuevo con ID hist: En eventos de
  enablon"`) en una hoja **intermedia** del ETL de Action Plans
  (`CSV_AP_EVT_NEW_SPEC`), confirmando que este modo de fallo existe en el
  proceso de construcción. **Ese literal no aparece en ninguna de las
  31444 filas del CSV final entregado** (0 casos) — sugiere que los casos
  de fallo se filtraron o corrigieron antes de la entrega, pero impide
  contar cuántos hubo originalmente.
- **Tipos de objeto incompatibles (punto 13)**: no evaluable — el CSV no
  tiene un campo independiente de "tipo de objeto padre" (solo el sistema
  origen, 2 valores), y `CS_HistoricalDataOrigin` no distingue sub-módulo
  (p. ej. no distingue "Simulacros" de "Eventos" dentro de
  `Prevención.ITP_ACCIONES_CORRECTORAS` — esa distinción vive en
  `idorigenac`, un campo del SQL de origen, no presente en el CSV final).
- **Excluidos/`do_not_migrate` (punto 15)**: por definición, un registro
  excluido nunca llega a un CSV ya exportado — esta categoría es
  estructuralmente inobservable desde este archivo. Requeriría acceso al
  SQL de origen completo (`ITP_Acciones_correctoras`) para contar cuántos
  registros existían allí y no llegaron al CSV final.

## 6. Conclusión

El 63% (y su métrica hermana del 79%) de repetición de
`CS_HistoricalOriginID` corresponde **mayoritariamente** a agrupación
legítima uno-a-muchos (76.17% de las filas, candidato de alta confianza
estructural), con una porción pequeña pero real de anomalías: 1.10% de
duplicidad exacta dentro del mismo padre, y un hallazgo nuevo y separado
de colisión de identidad (`CS_HistoricalAPID`) entre sistemas afectando
1437 valores. Ninguna de estas conclusiones se declara como validación
funcional aprobada — son candidatos estructurales respaldados por
evidencia cuantitativa real, pendientes de confirmación explícita del
cliente.
