"""
Implementación de cada `ReglaEspecial` del catálogo (ver
config/validation_rules.yaml). Cada función es pura y testeable de forma
aislada — nada de fórmulas de Excel encadenadas.

Todas las funciones reciben una fila de origen (dict-like, p. ej. una
Series de pandas) y devuelven el valor ya transformado para el campo
destino. El motor de mapeo (mapping_engine.py) es quien decide qué función
llamar según la columna `ReglaEspecial` de la hoja de mapeo.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

import pandas as pd


def _norm_rule_name(name: str) -> str:
    """Normaliza el nombre de una regla: en el proyecto original aparece
    escrita de formas distintas en cada módulo (Titlefix/titlefix/TitleFix...).
    """
    return re.sub(r"[^a-z]", "", name.lower())


def nullcontrol(value: Any, default: Any = None) -> Any:
    """Sustituye NULL/NaN/vacío por un valor por defecto."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return default
    return value


def concat(row: dict, fields: list[str], separator: str = " ") -> str:
    """Concatena varios campos origen, ignorando los que estén vacíos.

    Fan-in máximo confirmado en el proyecto original: 4 campos
    (AP-Con Ajuste Entidad: OrdenTrabajo + Coste + Descripcion + NumeroProyecto
    -> Definition).
    """
    parts = [str(row[f]) for f in fields if f in row and row[f] not in (None, "", "NULL") and not (
        isinstance(row[f], float) and pd.isna(row[f])
    )]
    return separator.join(parts)


def barconcat(row: dict, fields: list[str]) -> str:
    """Variante de concat con separador ' | ' (confirmada en MOC/OPS,
    para agregar múltiples observaciones de checklist bajo una misma
    entrada)."""
    return concat(row, fields, separator=" | ")


# --- titlefix -----------------------------------------------------------
# CONFIRMADO con datos reales (MOC, 76/5207 casos): al menos hace stripping
# de comillas dobles. Riesgo conocido: pierde el significado de pulgadas
# (8" -> 8) en textos técnicos. No se ha confirmado ningún otro
# comportamiento — no inventar más limpieza de la que está verificada.
#
# Decisión pendiente de negocio: ¿sustituir '"' por algo (p.ej. ' in') en
# vez de borrarlo? Por ahora replicamos el comportamiento observado
# (stripping simple) para no divergir del histórico ya migrado, y se deja
# el parámetro `preserve_inches` para poder activarlo cuando el cliente
# decida el comportamiento correcto hacia adelante.
def titlefix(value: str | None, preserve_inches: bool = False) -> str | None:
    if value is None:
        return None
    if preserve_inches:
        # Sustituye 8" (número seguido de comillas) por "8 in" antes de
        # quitar el resto de comillas sueltas.
        value = re.sub(r'(\d+)"', r"\1 in", value)
    return value.replace('"', "")


def cloneorigin(value: Any) -> Any:
    """Passthrough directo."""
    return value


def cloneorigin_fanout(value: Any, n_targets: int) -> list[Any]:
    """Variante fan-out: un origen -> N destinos idénticos (visto: 5 idiomas).

    Defecto conocido en el proyecto original (Eventos Nuevos / PSM, ticket
    cliente #7437): el fan-out no traducía y algunos destinos quedaban en
    inglés. Esta implementación siempre replica el mismo valor a los N
    destinos — si se requiere traducción real, debe hacerse ANTES de
    llamar a esta función, no asumir que el fan-out traduce.
    """
    return [value] * n_targets


def replaceinreference(value: Any, reference_table: dict) -> Any:
    """Sustituye el valor origen usando una tabla de referencia cruzada.

    No confirmado con datos reales todavía (ver validation_rules.yaml) —
    probar contra un CSV real antes de confiar en esta implementación para
    producción.
    """
    return reference_table.get(value, value)


def boolorigin(value: Any, mapping: dict, default: Any = None) -> Any:
    """Convierte un flag Sí/No (o equivalente) en un valor categórico
    destino usando una tabla de referencia adicional.

    No confirmado con datos reales todavía — ver validation_rules.yaml.
    """
    truthy = {"yes", "sí", "si", "true", "1", True, 1}
    key = str(value).strip().lower() if not isinstance(value, bool) else value
    is_true = key in truthy
    return mapping.get(is_true, default)


def lookup_simple(value: Any, table: dict, default: Any = None) -> Any:
    return table.get(value, default)


# Registro de funciones por nombre normalizado de regla, para que el motor
# de mapeo (mapping_engine.py) pueda resolver `ReglaEspecial` -> función sin
# tener que hacer un if/elif gigante disperso por el código.
RULE_REGISTRY: dict[str, Callable] = {
    _norm_rule_name("nullcontrol"): nullcontrol,
    _norm_rule_name("concat"): concat,
    _norm_rule_name("barconcat"): barconcat,
    _norm_rule_name("titlefix"): titlefix,
    _norm_rule_name("cloneorigin"): cloneorigin,
    _norm_rule_name("replaceinreference"): replaceinreference,
    _norm_rule_name("boolorigin"): boolorigin,
    _norm_rule_name("lookup"): lookup_simple,
}


def resolve_rule(rule_name: str) -> Callable:
    key = _norm_rule_name(rule_name)
    if key not in RULE_REGISTRY:
        raise KeyError(
            f"Regla '{rule_name}' no está en el registro. Si es una regla nueva "
            "vista en un ETL, añádela primero a config/validation_rules.yaml "
            "documentando si está confirmada con datos reales, y luego "
            "impleméntala aquí — no improvisar comportamiento sin documentarlo."
        )
    return RULE_REGISTRY[key]
