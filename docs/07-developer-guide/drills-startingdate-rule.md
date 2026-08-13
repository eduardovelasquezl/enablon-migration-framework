# StartingDate de Drills — regla reconstruida (Sprint 9.3)

## Hallazgo previo (Sprint 8.x — 9.2)

`StartingDate` se generaba solo a partir de `Fecha`, que en SQL Server llega
con la hora truncada a `00:00`. La consulta de origen ya selecciona `Hora`
(`varchar(5)`) y reserva una columna `FechaHoraCombinado` (`'' as
FechaHoraCombinado`), pero nunca la combina. No se adivinó la regla —
quedó documentado como hallazgo abierto (antes `OQ-ETL-07-NEW-FECHA-HORA`).

## Reconstrucción de la regla (Sprint 9.3)

Orden de autoridad seguido (Fase 1 del sprint):

1. **ETL real** (`ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`, hoja `MapeoSims`,
   fila 11): el origen declarado para el campo destino `"Start Date"` es
   `FechaHoraCombinado`, **no** `Fecha` sola (fila 9, sin transformación
   asociada). Confirma la intención original: combinar fecha + hora.
2. **Verificación empírica cruzada**, dentro del mismo workbook, sin SQL:
   hoja `DB_OrigenSim` (origen, `Fecha`/`Hora` crudos) vs. hoja `CSV_SIM`
   (destino ya generado, `StartingDate` como valor materializado, no
   fórmula). **12.091 filas comparadas — 12.087 coinciden exactamente
   (99,97%)** con la regla `StartingDate = fecha(Fecha) + hora:minuto(Hora)`,
   interpretando `Hora` como texto `H:MM`/`HH:MM`, 24h, sin segundos
   (consistente con el tipo `varchar(5)`).
3. Las 4 filas discordantes tienen `Hora` corrupta en origen: `'11:'`,
   `'1:'` (minutos ausentes), `'2:.30'` (formato inválido), o un caso
   (`Hora='9:50'` → destino `18:50`) sin explicación mecánica simple —
   posible corrección manual puntual en el histórico. Ninguna sigue un
   patrón alternativo consistente — no se interpretan como una regla
   distinta, sino como ruido de datos de origen (0,033% de las filas).

**No existe ninguna fórmula Excel/VBA visible que compute la combinación**
(mismo patrón ya documentado para `titlefix` en `CLAUDE.md`) — se
reconstruyó por evidencia cruzada de datos, no por lectura de fórmula.

## Clasificación de la evidencia

- Regla central (`Fecha` + `Hora` → `StartingDate`): **VERIFIED** —
  cruzada contra 12.091 filas reales, 99,97% de coincidencia exacta, causa
  raíz de las discrepancias identificada (datos corruptos, no la regla).
- Comportamiento con `Hora` NULL/vacía: **UNRESOLVED** — 0 casos
  observados en las 12.091 filas disponibles; no hay precedente histórico
  que confirmar. Implementación: conservadora (degrada a fecha sin hora,
  igual que el comportamiento anterior a este incremento), nunca inventa
  una hora.
- Timezone: sin evidencia de transformación — valores "naive", sin offset
  detectado en ninguna de las 12.087 coincidencias exactas.
- Segundos: siempre `:00` — `Hora` no tiene componente de segundos.

## Implementación

`src/export/prototype/drills/transformations.py::parse_starting_date(value, hora=None)`
— `hora=None` (o no interpretable) reproduce el comportamiento exacto de
antes de este incremento. Nueva categoría de incidencia no bloqueante,
`HORA_MISSING_OR_INVALID` (`issues.jsonl`, `validation_report.yaml ->
dates.hora_missing_or_invalid`), para que la degradación quede visible en
vez de indistinguible del caso "coincide".

`config/exports/drills.yaml`: `source` de `StartingDate` pasa de `"Fecha"`
a `["Fecha", "Hora"]`.
