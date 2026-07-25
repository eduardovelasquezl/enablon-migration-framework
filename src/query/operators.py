"""Registro de operadores soportados por el Query Engine v0.1: `eq` e `in`.

Cada builder recibe una `FilterDefinition` ya resuelta por el catálogo (por
tanto una `sql_source_expression` de confianza, nunca aportada por el
usuario) y un valor ya convertido al tipo correcto (por `validator.py`) --
solo construye el fragmento SQL parametrizado y el diccionario de
parámetros. Nunca concatena el valor: siempre va como parámetro nombrado.
"""
from __future__ import annotations

from typing import Sequence

from src.query.catalog import FilterDefinition
from src.query.models import CompiledFilter, InvalidFilterValueError

OP_EQ = "eq"
OP_IN = "in"

SUPPORTED_OPERATORS = (OP_EQ, OP_IN)

MAX_IN_VALUES = 200


def build_compiled_filter(
    field_def: FilterDefinition,
    operator: str,
    coerced_value,
    param_base: str,
) -> CompiledFilter:
    """Punto de entrada único: despacha al builder del operador.

    `operator` ya debe haber sido validado contra `SUPPORTED_OPERATORS` y
    contra `field_def.allowed_operators` por `validator.py` -- este
    despachador no repite esa validación de negocio, solo defiende contra
    un uso directo indebido del módulo."""
    if operator == OP_EQ:
        return _build_eq(field_def, coerced_value, param_base)
    if operator == OP_IN:
        return _build_in(field_def, coerced_value, param_base)
    raise InvalidFilterValueError(
        f"Operador '{operator}' no soportado por operators.py (soportados: {SUPPORTED_OPERATORS})."
    )


def _build_eq(field_def: FilterDefinition, value, param_name: str) -> CompiledFilter:
    fragment = f"{field_def.sql_source_expression} = :{param_name}"
    return CompiledFilter(
        field=field_def.field_name,
        operator=OP_EQ,
        sql_fragment=fragment,
        parameters={param_name: value},
        manifest_value=value,
    )


def _build_in(field_def: FilterDefinition, values: Sequence, param_base: str) -> CompiledFilter:
    values = tuple(values)
    if not values:
        raise InvalidFilterValueError(
            f"El operador 'in' requiere al menos un valor (campo '{field_def.field_name}')."
        )
    if len(values) > MAX_IN_VALUES:
        raise InvalidFilterValueError(
            f"El operador 'in' admite como máximo {MAX_IN_VALUES} valores "
            f"(campo '{field_def.field_name}', se recibieron {len(values)})."
        )

    names = [f"{param_base}_{i}" for i in range(len(values))]
    placeholders = ", ".join(f":{name}" for name in names)
    fragment = f"{field_def.sql_source_expression} IN ({placeholders})"
    parameters = {name: value for name, value in zip(names, values)}

    return CompiledFilter(
        field=field_def.field_name,
        operator=OP_IN,
        sql_fragment=fragment,
        parameters=parameters,
        manifest_value=list(values),
    )
