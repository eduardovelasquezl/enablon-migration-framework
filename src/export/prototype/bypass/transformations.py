"""Transformaciones de campo para bypass.By_Passes (Sprint 9.4).

Reutiliza deliberadamente, sin copiar, dos funciones de
`src.export.prototype.drills.transformations` que resultaron ser
genéricas pese a su nombre -- verificado leyendo su implementación, no
asumido por el nombre:

- `to_historical_id`: limpieza de un ID numérico a texto (sin resto
  decimal artificial). Cero lógica de Drills.
- `resolve_letter`: `null_default` solo para el caso vacío; un valor
  presente pero sin coincidencia en la tabla queda `unresolved`, SIN
  aplicarle el default (nunca se mezclan los dos casos). Esta semántica
  -- no la de `resolve_typology`, que sí aplica el mismo default a
  ambos casos -- es la que corresponde a los lookups de Bypass: las
  hojas `Mapeo_TipoBypass`/`Mapeo_CausaBypass`/`Mapeo_ElementType`/
  `Mapeo_RealizationMethods` del ETL real solo documentan un
  `nullcontrol` para `DatoOrigen=NULL`, nunca para "sin coincidencia" --
  aplicar el default también a ese segundo caso sería inventar una
  regla no evidenciada.

Solo `nullcontrol_passthrough` es nueva -- ningún campo de Drills usa
exactamente este patrón (null -> literal, no vacío -> passthrough sin
lookup).

`_is_missing`: hasta Sprint 9.6 era una copia local de la de
`drills.transformations` (DUPLICATED_FROM_DRILLS, ~10 líneas) -- movida a
`src.export.engine.values.is_missing` (Export Engine mínimo, Sprint 9.6).
Hallazgo al mover el código, no antes: esta copia OMITÍA el paso
`_to_native` que sí tiene la de Drills -- ver `engine/values.py` para el
análisis de por qué no cambia ningún resultado observable en este proyecto.
"""
from __future__ import annotations

from src.export.engine.values import is_missing as _is_missing
from src.export.prototype.drills.transformations import (
    LookupResult,
    resolve_letter as resolve_lookup,
    to_historical_id,
)

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
