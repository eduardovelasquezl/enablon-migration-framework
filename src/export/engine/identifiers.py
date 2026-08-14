"""Normalización de identificadores históricos numéricos (Sprint 9.8).

Extraído de `drills/transformations.py::to_historical_id` tras su TERCERA
reutilización real e idéntica (Drills origen, Bypass Sprint 9.4, Safety
Meetings Sprint 9.7 -- las tres únicamente lo IMPORTABAN de
`drills.transformations`, nunca lo copiaron; este movimiento no elimina
duplicación de código, corrige el acoplamiento módulo-a-módulo que eso
producía: Bypass y Safety Meetings dependían de un módulo hermano
(`drills`) para una utilidad sin ninguna lógica de Drills, en vez de
depender del Engine -- mismo criterio ya aplicado en Sprint 9.6 a
`build_query_filters_section`/`write_yaml_atomic`, ver `engine/manifest.py`).

Cero lógica específica de ningún módulo: limpia un ID numérico (origen
`IDSimulacro`/`IDBES`/`IDReunionGrupo`, etc., según el módulo) a texto sin
representación decimal artificial (`440.0` -> `"440"`), sin inventar ni
truncar un ID con parte decimal real.
"""
from __future__ import annotations

import re

from .values import is_missing, to_native


def to_historical_id(value) -> str | None:
    """Convierte un ID numérico de origen a texto sin resto decimal
    artificial (p. ej. `440.0` -> `"440"`). Devuelve `None` si el valor
    está vacío o si tiene una parte decimal real (no se trunca en
    silencio)."""
    if is_missing(value):
        return None
    value = to_native(value)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return None
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+", text):
            return text
        if re.fullmatch(r"-?\d+\.0+", text):
            return text.split(".")[0]
        return None
    return None
