"""Modelos de datos y excepciones del Query Engine.

Sin dependencias internas del propio paquete `src.query` -- el resto de
módulos (`catalog.py`, `parser.py`, `operators.py`, `validator.py`,
`sql_builder.py`) importan de aquí, nunca al revés.

`FilterDefinition` / `ObjectFilterCatalog` (la parte "catálogo cerrado")
viven en `catalog.py`, no en este módulo -- ver ese fichero.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class QueryEngineError(Exception):
    """Base común de todas las excepciones del Query Engine.

    Permite un `except QueryEngineError` genérico en la CLI sin enumerar
    cada subtipo -- mismo patrón que `DatabaseError` en `src/db/exceptions.py`.
    """


class FilterSyntaxError(QueryEngineError):
    """El texto `campo:operador:valor` de un `--filter` no tiene una forma
    sintácticamente válida (partes vacías, faltan separadores, elemento
    vacío en una lista de `in`...). Se lanza antes de conocer ningún
    catálogo -- es un error puramente de forma."""


class UnknownFilterFieldError(QueryEngineError):
    """El campo funcional no existe en el catálogo cerrado del objeto.
    Nunca hay fallback a una columna libre aportada por el usuario."""


class OperatorNotAllowedError(QueryEngineError):
    """El operador no está reconocido globalmente por el motor, o no está
    declarado en `allowed_operators` para el campo concreto solicitado."""


class InvalidFilterValueError(QueryEngineError):
    """El valor no puede convertirse al `data_type` declarado en el
    catálogo para ese campo (o excede un límite estructural, p. ej. más de
    200 valores en un `in`). Nunca se convierte "en silencio"."""


class UnsupportedQueryStructureError(QueryEngineError):
    """La SQL de origen tiene una forma que el compositor v0.1 no sabe
    combinar de manera segura con un `WHERE` dinámico (p. ej. ya tiene un
    `WHERE` de nivel superior, o más de una sentencia). Se rechaza de forma
    explícita en vez de intentar una inserción no verificada."""


@dataclass(frozen=True)
class FilterExpression:
    """Resultado puro de parsear un token `--filter` (sin tocar ningún
    catálogo todavía).

    `raw_value` es un `str` para `eq` y una `tuple[str, ...]` para `in`
    (ya separada por comas, con espacios externos de cada elemento ya
    eliminados) -- ambos siguen siendo texto sin convertir: la conversión
    de tipo depende del `data_type` del campo, que solo se conoce tras
    resolver el catálogo (ver `validator.py`).
    """

    field: str
    operator: str
    raw_value: str | tuple[str, ...]


@dataclass(frozen=True)
class CompiledFilter:
    """Un `FilterExpression` ya validado, con tipo convertido y compilado a
    un fragmento SQL parametrizado, listo para combinarse con otros
    mediante `AND` (ver `sql_builder.py`).

    `parameters` usa siempre nombres únicos (`filter_N` para `eq`,
    `filter_N_0`, `filter_N_1`, ... para `in`) -- nunca se reutiliza un
    nombre de parámetro entre dos filtros distintos de la misma ejecución.
    """

    field: str
    operator: str
    sql_fragment: str
    parameters: dict[str, Any]
    manifest_value: Any  # escalar (eq) o list (in) -- listo para volcar a YAML

    @property
    def manifest_entry(self) -> dict[str, Any]:
        """Representación normalizada para `export_manifest.yaml` ->
        `query_filters.expressions` -- nunca incluye el fragmento SQL ni
        los nombres de parámetro, solo el filtro tal como lo entendió el
        motor."""
        return {"field": self.field, "operator": self.operator, "value": self.manifest_value}
