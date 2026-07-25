"""Validación contra el catálogo cerrado + conversión de tipos + orquestación
de extremo a extremo: texto crudo de `--filter` -> `CompiledFilter`.

Es el único módulo que conoce el `ObjectFilterCatalog` a la vez que el
`FilterExpression` recién parseado -- por eso es también el punto de
entrada natural para la CLI (`compile_filter_tokens`), que debe poder
validar todos los filtros ANTES de abrir ninguna conexión SQL.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from src.query import operators
from src.query.catalog import DATA_TYPE_INTEGER, DATA_TYPE_STRING, FilterDefinition, ObjectFilterCatalog
from src.query.models import (
    CompiledFilter,
    FilterExpression,
    InvalidFilterValueError,
    OperatorNotAllowedError,
)
from src.query.parser import parse_filter_token

_INTEGER_PATTERN = re.compile(r"^-?\d+$")


def _coerce_integer(raw: str) -> int:
    if not isinstance(raw, str) or not _INTEGER_PATTERN.match(raw):
        raise InvalidFilterValueError(
            f"Valor {raw!r} no es un entero válido (no se admiten decimales ni texto no numérico)."
        )
    return int(raw)


def _coerce_string(raw: str) -> str:
    value = raw.strip() if isinstance(raw, str) else raw
    if not isinstance(value, str) or value == "":
        raise InvalidFilterValueError("El valor de tipo string no puede estar vacío.")
    return value


def _coerce_scalar(raw: str, data_type: str) -> Any:
    if data_type == DATA_TYPE_INTEGER:
        return _coerce_integer(raw)
    if data_type == DATA_TYPE_STRING:
        return _coerce_string(raw)
    raise InvalidFilterValueError(f"Tipo de dato de catálogo no soportado: {data_type!r}.")


def validate_and_coerce(expr: FilterExpression, catalog: ObjectFilterCatalog) -> tuple[FilterDefinition, Any]:
    """Resuelve `expr.field` contra `catalog`, valida que `expr.operator`
    esté permitido para ese campo, y convierte `expr.raw_value` al tipo
    declarado en el catálogo.

    Devuelve `(FilterDefinition, valor_convertido)` -- un `int`/`str` para
    `eq`, una `tuple[int, ...]`/`tuple[str, ...]` para `in`. Nunca convierte
    en silencio: cualquier fallo de tipo o de catálogo lanza una excepción
    de `src.query.models`.
    """
    field_def = catalog.get_field(expr.field)  # UnknownFilterFieldError si no existe

    if expr.operator not in operators.SUPPORTED_OPERATORS:
        raise OperatorNotAllowedError(
            f"Operador {expr.operator!r} no reconocido por el Query Engine. "
            f"Operadores soportados: {operators.SUPPORTED_OPERATORS}."
        )
    if expr.operator not in field_def.allowed_operators:
        raise OperatorNotAllowedError(
            f"El campo '{field_def.field_name}' no admite el operador {expr.operator!r}. "
            f"Operadores permitidos para este campo: {field_def.allowed_operators}."
        )

    if expr.operator == operators.OP_IN:
        raw_items = expr.raw_value if isinstance(expr.raw_value, tuple) else (expr.raw_value,)
        if len(raw_items) > operators.MAX_IN_VALUES:
            raise InvalidFilterValueError(
                f"El operador 'in' admite como máximo {operators.MAX_IN_VALUES} valores "
                f"(campo '{field_def.field_name}', se recibieron {len(raw_items)})."
            )
        coerced: Any = tuple(_coerce_scalar(item, field_def.data_type) for item in raw_items)
    else:
        assert isinstance(expr.raw_value, str)  # eq siempre trae un único valor de texto
        coerced = _coerce_scalar(expr.raw_value, field_def.data_type)

    return field_def, coerced


def compile_filter_tokens(raw_filters: Sequence[str], catalog: ObjectFilterCatalog) -> list[CompiledFilter]:
    """Punto de entrada de extremo a extremo para la CLI: una lista de
    tokens `campo:operador:valor` -> una lista de `CompiledFilter` lista
    para `sql_builder.compose_filtered_sql`.

    Cada filtro recibe un nombre de parámetro base único (`filter_1`,
    `filter_2`, ...) en el orden en que se declaró en la línea de comandos
    -- garantiza que no haya colisión de nombres al combinar varios
    filtros con `AND`. No abre ninguna conexión SQL ni importa nada de
    `src.db` -- es una función pura sobre texto y catálogo.
    """
    compiled: list[CompiledFilter] = []
    for index, raw in enumerate(raw_filters, start=1):
        expr = parse_filter_token(raw)
        field_def, coerced_value = validate_and_coerce(expr, catalog)
        compiled.append(
            operators.build_compiled_filter(
                field_def, expr.operator, coerced_value, param_base=f"filter_{index}"
            )
        )
    return compiled
