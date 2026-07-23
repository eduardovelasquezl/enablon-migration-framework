# Trazabilidad SQL → ETL → mapping → CSV — Export Specifications v1.0

> Sintetiza `evidence/traceability_catalog.yaml`. Vocabulario de
> `trace_status`: `fully_traced` | `partially_traced` | `source_only` |
> `output_only` | `ambiguous` | `missing`. **`fully_traced` nunca se usa si
> el destino Enablon no está respaldado por evidencia real** (regla dura de
> este incremento) — un campo con fórmula clara pero sin CSV real que lo
> confirme, o viceversa, no puede ser `fully_traced`.

## 1. simulacros.Drills — resumen de trazas

| Campo Enablon | SQL origen | Hoja ETL | Regla | trace_status | Confianza |
|---|---|---|---|---|---|
| `CS_HistoricalOriginID` | `IDSimulacro` | `MapeoSims` | lookup directo (XLOOKUP) | `fully_traced` | high |
| `CS_HistoricalUserId` | `IDUsuarioUltimaModificacion` | `MapeoSims` → `MultiField_User` | lookup + literal fijo | `fully_traced` | high |
| `CS_Typology` | `IDTipo` | `Mapeo_Tipo_sim` | lookup dinámico en 2 pasos (vía `ITP_MAESTROS`) | `fully_traced` | high |
| `CS_Letter` | `IDLetra` | `Mapeo_Letra` | lookup simple | `fully_traced` | high |
| `CS_WorkflowStatus` | `Estado` | `Mapeo_Estado` | lookup simple (muchos-a-uno) | `fully_traced` | high |
| `CS_HistoricalDrillAttendees` | `NombreAsistente` | `Mapeo_asistentes` → `Asis_concat` | lookup + concat (lógica de concat no confirmada en detalle) | `partially_traced` | high |
| `CS_Duration` | `Duracion` | `CalculoHorasDiasMinutos` | conversión numérica (4 componentes, recombinación no localizada) | `partially_traced` | medium |
| `Reference` | `IDSimulacro`+`IDTipo`+`Fecha` (composición no unívoca) | `CSV_SIM`/`CSV_SIM_full`/`CSV_Generated_BCM_SIM` | 3 fórmulas distintas observadas | `ambiguous` | low |
| Entidad (`CS_ImpactedEntities`) | `IDCentro` | — (no resuelto dentro de `MapeoSims`) | resolución de entidad, proceso no identificado | `missing` | low |

Ver `evidence/traceability_catalog.yaml` para el detalle completo de cada
fila (evidencia citada, limitaciones, preguntas abiertas).

## 2. Por qué `Reference` es `ambiguous` y no `fully_traced`

Es el hallazgo más importante de trazabilidad de este incremento. Tres
hojas de salida sucesivas del mismo workbook de Simulacros (`CSV_SIM_full`,
`CSV_SIM`, `CSV_Generated_BCM_SIM`) contienen **fórmulas distintas** para
lo que documentalmente es "el mismo campo" (la referencia legible del
Drill, que incorpora el `CS_HistoricalOriginID` numérico):

- `CSV_SIM_full` / `CSV_SIM`: `CONCATENAR(Tipología;"-";"HIST";"-";IDSimulacro;"-";Fecha)`
  → ejemplo cacheado `'PEI-HIST-3-18/09/2008'`.
- `CSV_Generated_BCM_SIM`: `CONCATENAR(Tipología;"-";Entidad;"-";Fecha;"-";IDSimulacro)`,
  **sin el literal "HIST"** → ejemplo cacheado
  `'PEI-EPSR.SYMEC.P01-A01-18/09/2008-3'`.

Los recuentos de fila de estas hojas (12302, 12104, 10575 respectivamente,
más `Export sim UAT` con 11965) coinciden exactamente con las 4 etapas de
exportación decrecientes ya señaladas como pregunta abierta en
`outputs/reports/01_Analisis_ETL_BCM_SIM_UpdateEje_SITECANARIAS.md`. Este
incremento **confirma la existencia física de las 4 hojas y sus 2 fórmulas
distintas**, pero **no determina cuál produjo el dato realmente cargado en
Enablon**, ni por qué el recuento decrece entre etapas. Por eso
`possible_enablon_field` se deja vacío en la traza correspondiente — llenar
ese campo con una suposición sería exactamente lo que este principio
prohíbe.

## 3. ap.Action_Plans — `CS_HistoricalAPID` vs. `CS_HistoricalOriginID`

Hallazgo nuevo de trazabilidad con impacto directo en Task 8
(`action_plans_assessment.md`, actualizado por separado): el Index del
workbook `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN.xlsx` declara la clave de
actualización `Update(IDAccionCorrectora,CS_HistoricalAPID)` para los 7
módulos de origen de Action Plans. Esto confirma que:

- `CS_HistoricalAPID` (desde `IDAccionCorrectora`) es la **identidad
  propia** del registro de Action Plan.
- `CS_HistoricalOriginID` (desde el ID del registro padre, p. ej.
  `IDSimulacro`) es la **referencia al objeto de origen**, no la identidad
  del Action Plan en sí.

`trace_status: partially_traced` — confirmado el rol de cada campo, no
confirmado el mecanismo exacto de generación de `CS_HistoricalAPID` (la
hoja `MAP-updatedate` no se leyó en detalle).

## 4. eventos.Impacts — dos pares clave-destino confirmados, no uno

El Index de `ETL - Eventos Antiguos_FiltroEje_SITEPESR.xlsx` y de
`ETL- Eventos nuevos - FULL_AjusteEje_SITEPSER.xlsx` confirman, entre los
dos, **tres** nombres de columna origen distintos (`IdImpactoGenerado`,
`IdImpactoGenerado2`, `StandardPersonalImpactKey`) mapeados a **dos**
campos destino distintos (`CS_HistImpactID`, `CS_HistImpactIDOH`) según la
fase del pipeline. Esto resuelve parcialmente `OQ-OBJ-03` del incremento
anterior (confirma que ambos campos destino se usan realmente, con reglas
de generación distintas por fase) sin determinar si esa coexistencia es
intencional. `trace_status: ambiguous`.

## 5. Objetos sin traza nueva en este incremento

No se profundizó en trazabilidad campo a campo para `moc.Change_Register`,
`bypass.By_Passes`, `ops.JSO`, `inspecciones.*`,
`safety_meetings.Group_Meetings` más allá de lo ya confirmado
estructuralmente por su propia hoja `Index` (ver
`etl_evidence_assessment.md` §2 y `evidence/etl_catalog.yaml`). Sus
`trace_status` individuales no se han recalculado — siguen sin traza de
campo específica más allá de la fuente/mapa/salida a nivel de hoja ya
documentado.

## 6. Limitaciones

- Toda traza de este catálogo se basa en una **muestra** de 2-8 filas por
  hoja, nunca en el archivo completo.
- Ninguna traza asume un campo destino Enablon que no esté respaldado por
  al menos: (a) una hoja de mapeo con XLOOKUP resuelto en caché, o (b) la
  cabecera real de un CSV de Bloque4. Donde solo existía uno de los dos, se
  marcó `partially_traced` o `ambiguous`, nunca `fully_traced`.
