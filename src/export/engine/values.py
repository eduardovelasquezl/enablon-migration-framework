"""Comprobación genérica de "valor ausente" (Sprint 9.6).

Extraído de `drills/transformations.py::_is_missing`/`_to_native` -- la
versión de Bypass (`bypass/transformations.py::_is_missing`, añadida en
Sprint 9.4 con el comentario "idéntica a la función privada _is_missing de
drills.transformations") en realidad OMITÍA el paso `_to_native` -- hallazgo
propio de la comparación línea a línea de Sprint 9.5.1/9.6, no asumido por
el nombre ni por el comentario del propio código. Se conserva aquí la
versión MÁS COMPLETA (con `to_native`) como la canónica: para los tipos que
`pandas`/SQLAlchemy devuelven en la práctica (`numpy.float64`/`numpy.str_`,
ambos subclases de `float`/`str` en CPython), el resultado de `is_missing`
con o sin `to_native` ya coincidía en todos los casos reales de ambos
módulos -- añadirlo no cambia ningún resultado observable, solo hace
explícita una conversión que antes de este refactor no protegía a Bypass
frente a un escalar numpy que NO fuera subclase directa de `float`/`str`.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def to_native(value):
    """Convierte un escalar numpy (`numpy.int64`, `numpy.float64`...) al
    tipo Python nativo equivalente. pandas devuelve escalares numpy al leer
    columnas SQL bigint/numeric -- sin esto, `isinstance(value, int)`
    devuelve `False` para un `numpy.int64` y las comprobaciones de tipo de
    `is_missing` se saltarían en silencio para tipos que no sean ya
    subclase directa de `float`/`str`."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def is_missing(value) -> bool:
    """`True` si `value` representa "sin dato" en cualquiera de sus formas
    observadas en los CSV/DataFrames de origen de este proyecto: `None`,
    `NaN` (float o `numpy.float64`), cadena vacía/solo espacios, o cualquier
    otro valor que `pandas.isna` reconozca (`pd.NA`, `NaT`...)."""
    value = to_native(value)
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
