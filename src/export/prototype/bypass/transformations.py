"""Transformaciones de campo para bypass.By_Passes (Sprint 9.4).

Reutiliza deliberadamente dos funciones genéricas del Export Engine:

- `to_historical_id`: limpieza de un ID numérico a texto (sin resto
  decimal artificial). Cero lógica de ningún módulo concreto.
- `resolve_letter`: `null_default` solo para el caso vacío; un valor
  presente pero sin coincidencia en la tabla queda `unresolved`, SIN
  aplicarle el default (nunca se mezclan los dos casos). Esta semántica
  -- no la de `resolve_typology` (Drills), que sí aplica el mismo default
  a ambos casos -- es la que corresponde a los lookups de Bypass: las
  hojas `Mapeo_TipoBypass`/`Mapeo_CausaBypass`/`Mapeo_ElementType`/
  `Mapeo_RealizationMethods` del ETL real solo documentan un
  `nullcontrol` para `DatoOrigen=NULL`, nunca para "sin coincidencia" --
  aplicar el default también a ese segundo caso sería inventar una
  regla no evidenciada.

Hasta Sprint 9.8, ambas funciones se importaban de
`src.export.prototype.drills.transformations` (acoplamiento bypass ->
drills para utilidades sin ninguna lógica de Drills, documentado como tal
desde Sprint 9.4) -- movidas a `src.export.engine.identifiers`/
`src.export.engine.lookups` tras confirmar una tercera reutilización real
e idéntica (Safety Meetings, Sprint 9.7). Bypass ya no importa nada de
`drills` para utilidades genéricas.

Solo `nullcontrol_passthrough` es nueva -- ningún otro módulo usa
exactamente este patrón (null -> literal, no vacío -> passthrough sin
lookup).

`_is_missing`: hasta Sprint 9.6 era una copia local (DUPLICATED_FROM_DRILLS,
~10 líneas) -- movida a `src.export.engine.values.is_missing` (Export
Engine mínimo, Sprint 9.6). Hallazgo al mover el código, no antes: esta
copia OMITÍA el paso `_to_native` que sí tiene la de Drills -- ver
`engine/values.py` para el análisis de por qué no cambia ningún resultado
observable en este proyecto.
"""
from __future__ import annotations

from src.export.engine.identifiers import to_historical_id
from src.export.engine.lookups import LookupResult, resolve_letter as resolve_lookup
from src.export.engine.values import is_missing as _is_missing

__all__ = ["LookupResult", "resolve_lookup", "to_historical_id", "nullcontrol_passthrough"]


def nullcontrol_passthrough(value, null_default: str) -> LookupResult:
    """`Motivo` -> `Reason` (hoja `NullControlException` del ETL real):
    sin tabla de lookup -- si `value` está vacío, se usa `null_default`
    (literal exacto del `nullcontrol`); si no, se conserva tal cual
    (passthrough), sin transformación de formato."""
    if _is_missing(value):
        return LookupResult(value=null_default, status="null_default", raw_source_value=value)
    text = str(value).strip()
    return LookupResult(value=text, status="resolved", raw_source_value=value)
