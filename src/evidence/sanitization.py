"""Utilidades de saneamiento compartidas por `workbook.py`.

Nada aquí decide QUÉ mostrar (eso es `catalog.py`, vía
`include_in_internal`/`include_in_client`) -- solo CÓMO mostrarlo de forma
limpia: rutas relativas (nunca absolutas de máquina local), números sin
decimales artificiales, y la comprobación de audiencia válida.
"""
from __future__ import annotations

from pathlib import Path

from src.config import PROJECT_ROOT

VALID_AUDIENCES = ("internal", "client")


def relative_to_project(path: str | Path) -> str:
    """Convierte una ruta a relativa a la raíz del repo. Si no está dentro
    del repo (p. ej. un directorio temporal de test), devuelve solo el
    nombre de fichero -- nunca la ruta absoluta completa de la máquina."""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return p.name


def clean_numeric_display(value) -> str:
    """`"286.0"` -> `"286"`; cualquier otro texto se devuelve tal cual.
    Corrige el efecto visual de columnas SQL nullable que pandas sube a
    float64 (ver `src/export/prototype/drills/transformations.py`)."""
    if value is None:
        return ""
    text = str(value)
    body = text[:-2] if text.endswith(".0") else text
    if body.lstrip("-").isdigit() and text.endswith(".0"):
        return body
    return text


def validate_audience(audience: str) -> None:
    if audience not in VALID_AUDIENCES:
        raise ValueError(
            f"Audiencia desconocida: {audience!r} -- valores válidos: {VALID_AUDIENCES}"
        )


def category_allowed_for_audience(category_def, audience: str) -> bool:
    validate_audience(audience)
    return category_def.include_in_internal if audience == "internal" else category_def.include_in_client
