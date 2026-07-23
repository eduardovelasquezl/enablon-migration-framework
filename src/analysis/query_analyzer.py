"""
Revisión estática de las queries de extracción (.sql) que aporta el cliente.

No modifica ni ejecuta las queries — solo las lee como texto y detecta
patrones que ya sabemos que importan para este proyecto:

- Tipo de JOIN (un FULL/LEFT JOIN puede inflar el "origen" aparente frente
  a lo que realmente debería migrar — ver el caso de Eventos en CLAUDE.md).
- Presencia/ausencia de WHERE (si no hay, el recuento de la tabla es el
  origen real, sin scope oculto).
- Columnas de entidad disponibles (IDCentro, IDUnidadOrg, IDDepartamento,
  IDEmpresa, IDInstalacion) — para saber qué se puede agrupar sin más JOINs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.analysis._select_parser import (
    SelectExpressionInfo,
    SelectParseResult,
    extract_table_aliases,
    parse_select_list,
    resolve_source_table,
)

ENTITY_COLUMN_PATTERNS = [
    r"IDCentro", r"IdCentro", r"IDUnidadOrg(?:anizativa)?", r"IdUnidadOrg(?:anizativa)?",
    r"IDDepartamento", r"IdDepartamento", r"IDEmpresa", r"IdEmpresa", r"IDInstalacion", r"IdInstalacion",
]

JOIN_PATTERN = re.compile(r"\b(FULL|LEFT|RIGHT|INNER)?\s*JOIN\b", re.IGNORECASE)
WHERE_PATTERN = re.compile(r"\bWHERE\b", re.IGNORECASE)
FROM_PATTERN = re.compile(r"\bFROM\s+\[?([\w.\[\]]+)\]?", re.IGNORECASE)
COMMENTED_LINE = re.compile(r"--.*")


@dataclass
class QueryReview:
    path: str
    joins: list[str] = field(default_factory=list)
    has_active_where: bool = False
    has_commented_where: bool = False
    from_tables: list[str] = field(default_factory=list)
    entity_columns_found: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)


def review_query_file(path: str | Path) -> QueryReview:
    path = Path(path)
    sql = path.read_text(encoding="utf-8-sig")

    # separar líneas comentadas para no confundir un WHERE desactivado con uno activo
    active_lines = []
    commented_lines = []
    for line in sql.splitlines():
        m = COMMENTED_LINE.search(line)
        if m and m.start() == 0:
            commented_lines.append(line)
        elif m:
            active_lines.append(line[: m.start()])
            commented_lines.append(line[m.start():])
        else:
            active_lines.append(line)
    active_sql = "\n".join(active_lines)
    commented_sql = "\n".join(commented_lines)

    review = QueryReview(path=str(path))
    review.joins = [
        (m.group(1) or "INNER").upper() for m in JOIN_PATTERN.finditer(active_sql)
    ]
    review.has_active_where = bool(WHERE_PATTERN.search(active_sql))
    review.has_commented_where = bool(WHERE_PATTERN.search(commented_sql))
    review.from_tables = list({m.group(1) for m in FROM_PATTERN.finditer(active_sql)})
    review.entity_columns_found = sorted(
        {
            pat.strip(r"\b")
            for pat in ENTITY_COLUMN_PATTERNS
            if re.search(pat, active_sql, re.IGNORECASE)
        }
    )

    if "FULL" in review.joins:
        review.risk_notes.append(
            "Contiene FULL JOIN: el recuento de filas de esta query puede NO "
            "representar 'registros a migrar' de forma fiable si la relación "
            "no es 1:1 — verificar cardinalidad antes de usarlo como base de "
            "una comparación de volumetría (ver caso Eventos en CLAUDE.md)."
        )
    if not review.has_active_where and review.has_commented_where:
        review.risk_notes.append(
            "Tiene un WHERE comentado (desactivado) — alguien consideró un "
            "filtro de scope y lo dejó apagado. Confirmar con el cliente si "
            "debería estar activo."
        )
    if not review.entity_columns_found:
        review.risk_notes.append(
            "No se detecta ninguna columna de entidad/centro conocida — la "
            "volumetría por site para esta query requerirá un JOIN adicional "
            "o localizar la columna de entidad con otro nombre."
        )

    return review


def review_directory(dir_path: str | Path) -> dict[str, QueryReview]:
    """Revisa todos los .sql de un directorio (p. ej. sql/source_queries/<modulo>/)."""
    dir_path = Path(dir_path)
    return {p.name: review_query_file(p) for p in sorted(dir_path.glob("*.sql"))}


def analyze_select_columns(path: str | Path) -> SelectParseResult:
    """Extrae sintácticamente las expresiones del SELECT de nivel superior
    de una query (posición, expresión original, alias, si es calculada,
    funciones y columnas referenciadas, wildcard...) y resuelve la tabla
    origen de cada columna simple cuando no hay ambigüedad.

    No ejecuta la query -- solo análisis de texto (vía `sqlparse`-style,
    implementado en `_select_parser.py`, privado). No infiere significado
    funcional ni convierte una expresión calculada en una columna simple.
    """
    path = Path(path)
    sql = path.read_text(encoding="utf-8-sig")
    result = parse_select_list(sql)
    for expr in result.expressions:
        table, warnings = resolve_source_table(expr, result.table_aliases)
        expr.source_table = table
        expr.warnings.extend(warnings)
    return result
