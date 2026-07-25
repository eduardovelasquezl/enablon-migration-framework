"""Parser puramente sintáctico de tokens `--filter campo:operador:valor`.

No conoce ningún catálogo ni ningún `data_type` -- solo separa el texto en
sus tres partes, valida su forma (nada vacío, `in` produce una lista sin
elementos vacíos) y normaliza espacios externos. La conversión de tipo y la
validación contra el catálogo cerrado son responsabilidad de `validator.py`.
"""
from __future__ import annotations

from src.query.models import FilterExpression, FilterSyntaxError

OPERATOR_IN = "in"

_MAX_SPLITS = 2  # separa solo los dos primeros ":" -- el resto queda dentro del valor


def parse_filter_token(raw: str) -> FilterExpression:
    """Convierte un token `--filter` en un `FilterExpression`.

    Formato esperado: `campo:operador:valor`. Solo se separan los dos
    primeros `:` (`str.split(":", 2)`), para que un valor de tipo string
    pueda contener `:` en el futuro sin romper el parseo. Los espacios
    externos de `campo`, `operador` y `valor` se eliminan; el contenido
    interno del valor se conserva tal cual.
    """
    if not isinstance(raw, str):
        raise FilterSyntaxError(f"Un filtro debe ser texto, se recibió {type(raw).__name__}.")

    parts = raw.split(":", _MAX_SPLITS)
    if len(parts) < 3:
        raise FilterSyntaxError(
            f"Formato de filtro inválido (se esperaba 'campo:operador:valor'): {raw!r}"
        )

    field_raw, operator_raw, value_raw = parts
    field = field_raw.strip()
    operator = operator_raw.strip().lower()
    value_text = value_raw.strip()

    if not field:
        raise FilterSyntaxError(f"El campo del filtro no puede estar vacío: {raw!r}")
    if not operator:
        raise FilterSyntaxError(f"El operador del filtro no puede estar vacío: {raw!r}")
    if not value_text:
        raise FilterSyntaxError(f"El valor del filtro no puede estar vacío: {raw!r}")

    raw_value: str | tuple[str, ...]
    if operator == OPERATOR_IN:
        raw_value = _parse_in_list(value_text, original=raw)
    else:
        raw_value = value_text

    return FilterExpression(field=field, operator=operator, raw_value=raw_value)


def _parse_in_list(value_text: str, *, original: str) -> tuple[str, ...]:
    items = [item.strip() for item in value_text.split(",")]
    if any(item == "" for item in items):
        raise FilterSyntaxError(
            f"El operador 'in' no admite elementos vacíos en la lista de valores: {original!r}"
        )
    return tuple(items)
