"""Composición en memoria del `WHERE` dinámico sobre la SQL de origen.

Nunca escribe sobre `sql/source_queries/` -- lee el texto original tal cual
lo entrega el llamador (normalmente `Path.read_text()` en
`src/export/prototype/drills/extractor.py`) y devuelve un texto nuevo,
compuesto solo en memoria. El fichero en disco no se toca en ningún punto
de este módulo.

Estrategia (aprobada en el incremento de diseño previo, v0.1 limitada a la
forma exacta de la SQL de Drills -- sin `WHERE` propio):

1. Parsear la SQL con `sqlparse` y exigir una única sentencia.
2. Si ya existe un `WHERE` de nivel superior -> `UnsupportedQueryStructureError`
   explícito (no se intenta fusionar con `AND` en v0.1).
3. Si hay un `ORDER BY` de nivel superior, insertar el `WHERE` justo antes,
   conservando el `ORDER BY` original tal cual (mismo texto, mismo caso).
4. Si no hay `ORDER BY`, insertar el `WHERE` al final (antes de un `;`
   final si lo hay).
5. Nunca se envuelve la consulta original como subconsulta -- eso solo
   expondría los alias ya transformados del `SELECT` (p. ej. fechas ya
   convertidas a texto vía `FORMAT()`), no las columnas base declaradas en
   el catálogo.
6. Revalidar el texto compuesto con `validate_read_only_sql` antes de
   devolverlo -- las mismas salvaguardas que cualquier otra SQL del
   proyecto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import sqlparse
from sqlparse import tokens as T
from sqlparse.sql import Statement, Where

from src.db.query_runner import validate_read_only_sql
from src.query.models import CompiledFilter, UnsupportedQueryStructureError


@dataclass(frozen=True)
class ComposedQuery:
    """Resultado de componer filtros sobre la SQL original.

    `sql_text` contiene únicamente placeholders con nombre (`:filter_1`,
    ...) -- nunca un valor real interpolado. `parameters` es el diccionario
    ya fusionado de todos los `CompiledFilter`, listo para
    `src.db.query_runner.run_query(sql, params=parameters, ...)`.
    """

    sql_text: str
    parameters: dict[str, Any]


def _parse_single_statement(sql: str) -> Statement:
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise UnsupportedQueryStructureError(
            "El compositor de filtros del Query Engine v0.1 solo admite un fichero "
            f"SQL con una única sentencia; se detectaron {len(statements)}."
        )
    return statements[0]


def _locate_insertion_index(tokens: list) -> tuple[int, bool]:
    """Devuelve `(índice_de_inserción, hay_order_by)` sobre la lista de
    tokens de nivel superior de la sentencia.

    Lanza `UnsupportedQueryStructureError` si ya existe un `WHERE` de nivel
    superior -- v0.1 no intenta fusionar con `AND` sobre una estructura ya
    existente."""
    for tok in tokens:
        if isinstance(tok, Where):
            raise UnsupportedQueryStructureError(
                "La consulta original ya tiene una cláusula WHERE de nivel superior -- "
                "esta estructura todavía no está soportada por el Query Engine v0.1 "
                "(no se inserta automáticamente un AND sobre un WHERE existente)."
            )

    for idx, tok in enumerate(tokens):
        if tok.ttype is T.Keyword and (tok.normalized or tok.value).upper() == "ORDER BY":
            return idx, True

    # Sin ORDER BY de nivel superior: insertar al final, antes de un ';' final si lo hay.
    for idx in range(len(tokens) - 1, -1, -1):
        tok = tokens[idx]
        if tok.is_whitespace or tok.ttype in T.Comment:
            continue
        if tok.ttype is T.Punctuation and tok.value == ";":
            return idx, False
        break

    return len(tokens), False


def compose_filtered_sql(original_sql: str, compiled_filters: Sequence[CompiledFilter]) -> ComposedQuery:
    """Inserta un `WHERE <condiciones combinadas con AND>` en `original_sql`
    sin modificar el texto original en disco (el llamador es responsable de
    no volver a escribirlo sobre `sql/source_queries/`).

    Si `compiled_filters` está vacío, devuelve `original_sql` sin ningún
    cambio y `parameters={}` -- una ejecución sin `--filter` debe producir
    exactamente la misma SQL que antes de este incremento.
    """
    if not compiled_filters:
        return ComposedQuery(sql_text=original_sql, parameters={})

    stmt = _parse_single_statement(original_sql)
    tokens = list(stmt.tokens)
    insertion_index, _has_order_by = _locate_insertion_index(tokens)

    conditions = " AND ".join(cf.sql_fragment for cf in compiled_filters)
    where_clause = f"\nWHERE {conditions}\n"

    before = "".join(str(tok) for tok in tokens[:insertion_index])
    after = "".join(str(tok) for tok in tokens[insertion_index:])
    composed_sql = before + where_clause + after

    # Revalidación obligatoria: el texto compuesto vuelve a pasar por las
    # mismas salvaguardas de solo lectura que cualquier otra SQL del proyecto.
    validate_read_only_sql(composed_sql)

    parameters: dict[str, Any] = {}
    for cf in compiled_filters:
        parameters.update(cf.parameters)

    return ComposedQuery(sql_text=composed_sql, parameters=parameters)


def render_generated_sql_file(
    *,
    sql_text: str,
    source_sql_relpath: str,
    source_sql_sha256: str,
    run_id: str,
    timestamp: str,
) -> str:
    """Texto completo de `generated_query.sql` -- función pura, sin I/O.

    `sql_text` es el texto ya compuesto (`ComposedQuery.sql_text`) --
    contiene únicamente placeholders con nombre, nunca valores reales.
    Incluye una cabecera que deja explícito que es SQL generada (nunca el
    fichero original) y que los valores de los filtros no aparecen aquí,
    solo los placeholders con nombre."""
    header = (
        "-- ============================================================\n"
        "-- SQL generada en memoria por el Query Engine v0.1 (src/query/).\n"
        "-- Este fichero es una copia compuesta para trazabilidad -- NO es,\n"
        "-- ni sustituye a, el fichero SQL original, que permanece intacto:\n"
        f"--   {source_sql_relpath}\n"
        f"-- SQL fuente (sha256): {source_sql_sha256}\n"
        f"-- run_id: {run_id}\n"
        f"-- timestamp: {timestamp}\n"
        "-- Los valores de los filtros NO aparecen en este fichero -- solo\n"
        "-- parámetros con nombre (:filter_N), sustituidos por SQLAlchemy en\n"
        "-- tiempo de ejecución. Nunca se concatenan valores en este texto.\n"
        "-- ============================================================\n\n"
    )
    return header + sql_text
