# Paquete de decisión funcional — `simulacros.Drills.Reference`

> **Estado: decisión funcional registrada** (`approved_functional_decision`).
> Este documento no existía en un estado "pendiente" en este repositorio —
> se crea directamente en su estado de decisión registrada, incorporando la
> aprobación funcional comunicada por el consultor responsable de la
> migración durante este incremento. Evidence ID:
> **`AFD-DRILLS-REFERENCE-001`**.

## 1. Regla aprobada

El campo `Reference` de `simulacros.Drills` se construye exactamente como:

```
<CS_Typology>-HIST-<CS_HistoricalOriginID>-<StartingDate(dd/MM/yyyy)>
```

## 2. Ejemplo aprobado

```
PEI1-HIST-440-08/03/2010
```

## 3. Componentes de la referencia

| Componente | Origen | Descripción |
|---|---|---|
| `PEI1` | `CS_Typology` | Código de tipología del simulacro, ya resuelto (ver `evidence/traceability_catalog.yaml`, `trace:simulacros.drills.cs_typology`). |
| `HIST` | Literal fijo | Constante para todos los registros históricos migrados — no varía por registro. |
| `440` | `CS_HistoricalOriginID` | Identificador histórico de origen del simulacro (`IDSimulacro`), ya resuelto (`trace:simulacros.drills.cs_historicaloriginid`). |
| `08/03/2010` | `StartingDate` | Fecha de inicio, sin componente de hora, formateada `dd/MM/yyyy`. |

Todos los componentes se separan con un guion (`-`), sin espacios entre
componentes.

## 4. Fórmula conceptual

```
Reference =
    CS_Typology
    + "-HIST-"
    + CS_HistoricalOriginID
    + "-"
    + format(StartingDate, "dd/MM/yyyy")
```

## 5. Variante del ETL que coincide con la regla

Dos variantes de fórmula localizadas en
`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` **reproducen exactamente** esta
regla (mismo componente inicial, literal `HIST`, mismo orden, mismo
separador, mismo formato de fecha):

- `refvar:drills.csv_sim_full.array_concat` (hoja `CSV_SIM_full`, 12302
  filas): `$=CONCATENAR(INDICE(J:J;FILA());"-";"HIST";"-";INDICE(AD:AD;FILA());"-";TEXTO(INDICE(K:K;FILA());"dd/mm/aaaa"))`
- `refvar:drills.csv_sim.classic_concat` (hoja `CSV_SIM`, 12104 filas):
  `=CONCATENATE(J2,"-","HIST","-",AD2,"-",TEXT(K2,"dd/mm/aaaa"))`

Ambas son, en esencia, la MISMA regla expresada con dos mecanismos de
fórmula de Excel distintos (array dinámico vs. fórmula clásica arrastrada
por fila) — no dos reglas distintas. Una tercera hoja
(`refvar:drills.export_sim_uat.values_only`, `Export sim UAT`, 11965
filas) contiene únicamente valores ya calculados con esta misma forma, sin
fórmula viva. Ver `evidence/drills_reference_variant_catalog.yaml` para el
detalle completo con ejemplos anonimizados y confianza por variante.

## 6. Variantes descartadas como regla vigente

- `refvar:drills.csv_generated_bcm_sim.no_hist_literal` (hoja
  `CSV_Generated_BCM_SIM`, 10575 filas):
  `=CONCATENATE(J2,"-",I2,"-",TEXT(K2,"dd/mm/aaaa"),"-",AD2)` — **NO
  reproduce la regla aprobada**: omite el literal `HIST`, inserta el código
  de entidad (`CS_ImpactedEntities`) como segundo componente, y coloca
  `CS_HistoricalOriginID` en cuarta posición en vez de tercera. Clasificada
  `residual_rule_candidate` — coexiste en el mismo workbook y para el mismo
  objeto que las variantes vigentes, sin evidencia de que sirva a otro
  objeto Enablon; la hipótesis más simple es que es una versión anterior o
  un intento sustituido, no una regla para otro `MigrationObject`.

No se ha seleccionado ninguna variante como vigente por frecuencia de uso
— la selección se basa exclusivamente en la coincidencia exacta con la
regla ya aprobada por el consultor responsable, tal como exige el
principio de este incremento.

## 7. Tratamiento pendiente de NULL o componentes vacíos

**No confirmado explícitamente por el consultor.** La muestra de filas
inspeccionada (14 filas entre las 3 hojas vigentes) no contenía ningún
componente vacío (`CS_Typology`, `CS_HistoricalOriginID` y `StartingDate`
poblados en el 100% de la muestra). No se ha verificado el comportamiento
de la fórmula ante un componente NULL (p. ej. si `CS_Typology` estuviera
vacío, el resultado sería `-HIST-440-08/03/2010`, con un guion inicial
duplicado — no confirmado si esto ocurre realmente en producción). Se deja
como pregunta residual — ver §15, no reabre `OQ-ETL-03`.

## 8. Impacto en el CSV

`Reference` es la columna B del CSV real de Drills
(`Drills-22072026-41.csv`, `evidence:csv_enablon.drills`) y de las 4 hojas
de salida internas del ETL. Confirmar esta regla no cambia ninguna otra
columna del CSV — es un campo derivado, no afecta a `CS_HistoricalOriginID`
(columna independiente, ya resuelta) ni a `CS_Typology`/`StartingDate` en
sí mismos.

## 9. Impacto en unicidad

`Reference` NO es la clave de correlación/actualización real de Drills —
esa es `CS_HistoricalOriginID` (`IDSimulacro`), confirmada de forma
independiente (`Update(IDSimulacro,CS_HistoricalOriginID)` en la hoja
`Index` del ETL). `Reference` es un campo legible derivado para mostrar al
usuario, no una clave técnica — su unicidad depende enteramente de la
unicidad de `CS_HistoricalOriginID`, ya evaluada aparte (sin duplicados
confirmados para Drills en este incremento, ver
`object_assessments/drills_evidence_assessment.md` §17).

## 10. Impacto en trazabilidad

Con esta decisión registrada, la traza de `Reference` en
`evidence/traceability_catalog.yaml` pasa de `ambiguous` a `fully_traced`
(ver `trace:simulacros.drills.reference`, actualizada en este mismo
incremento) — los 3 componentes (`CS_Typology`, `CS_HistoricalOriginID`,
`StartingDate`) tienen fuente SQL/ETL confirmada de forma independiente
(ver §3), la fórmula de combinación está confirmada y coincide con la
decisión aprobada, y la columna de salida CSV está confirmada.

## 11. Fuente de la decisión

Aprobación funcional comunicada como contexto de este incremento por el
**Functional Migration Team** (aprobador genérico, sin nombre de persona
individual, siguiendo la instrucción de no usar nombres de personas no
autorizados para documentación).

## 12. Estado de aprobación

`approved` — decisión funcional aprobada, aplicable sin reinterpretación.

## 13. Fecha de registro

**2026-07-23** — fecha de incorporación de esta decisión a este
repositorio. La fecha de aprobación funcional original (cuándo el
consultor validó la regla por primera vez, posiblemente antes de este
incremento) **no está documentada** en ningún archivo de este repositorio
— no se inventa una fecha histórica; se distingue explícitamente de la
fecha de registro documental.

## 14. Limitaciones

- El tratamiento de componentes vacíos (§7) no está confirmado — no se
  asume un comportamiento, se deja como pregunta residual.
- Esta decisión no sustituye a un template oficial de importación de
  Enablon — sigue sin existir ningún template validado para Drills ni para
  ningún otro objeto (ver `evidence_inventory.md` §3). La decisión resuelve
  la regla de construcción del CAMPO `Reference`, no certifica que Enablon
  acepte esta columna con este nombre/formato en una importación real.
- La variante descartada (`CSV_Generated_BCM_SIM`) no se ha eliminado del
  workbook original — sigue existiendo como evidencia histórica, sin
  modificar el archivo Excel.
- No se ha confirmado la fecha ni el motivo por el que se generaron 3
  hojas de salida distintas para el mismo objeto — sigue como pregunta
  abierta (`OQ-ETL-05`, ver `open_questions.md`).

## 15. Preguntas residuales

- **`OQ-ETL-05`**: ¿por qué existen 3 hojas de salida distintas
  (`CSV_SIM_full`, `CSV_SIM`, `CSV_Generated_BCM_SIM`) para Drills, y en
  qué orden/momento se generó cada una? (Nueva, ver `open_questions.md`,
  no bloquea esta decisión.)
- **Tratamiento de NULL/vacío en `Reference`** (§7): si `CS_Typology`,
  `CS_HistoricalOriginID` o `StartingDate` estuvieran vacíos para algún
  registro histórico, ¿qué valor debe producir `Reference`? Pendiente de
  confirmación explícita del consultor — se registra como pregunta nueva y
  separada (`OQ-ETL-06`), **sin reabrir `OQ-ETL-03`**, tal como exige la
  Tarea 5 de este incremento.
