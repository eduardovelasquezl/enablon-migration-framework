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
"""
from __future__ import annotations

import math

import pandas as pd

from src.export.prototype.drills.transformations import (
    LookupResult,
    resolve_letter as resolve_lookup,
    to_historical_id,
)

__all__ = ["LookupResult", "resolve_lookup", "to_historical_id", "nullcontrol_passthrough"]


def _is_missing(value) -> bool:
    # DUPLICATED_FROM_DRILLS (deliberado): idéntica a la función privada
    # `_is_missing` de `drills.transformations` -- no se importa porque
    # es privada de ese módulo (el guion bajo es una frontera real, no
    # solo convención). Duplicación mínima (10 líneas), registrada como
    # tal -- ver docs/07-developer-guide/bypass-module.md § 6. Candidata
    # a moverse a un lugar compartido si aparece una tercera necesidad.
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def nullcontrol_passthrough(value, null_default: str) -> LookupResult:
    """`Motivo` -> `Reason` (hoja `NullControlException` del ETL real):
    sin tabla de lookup -- si `value` está vacío, se usa `null_default`
    (literal exacto del `nullcontrol`); si no, se conserva tal cual
    (passthrough), sin transformación de formato."""
    if _is_missing(value):
        return LookupResult(value=null_default, status="null_default", raw_source_value=value)
    text = str(value).strip()
    return LookupResult(value=text, status="resolved", raw_source_value=value)
