"""Extracción SQL de solo lectura para simulacros.Drills.

El núcleo (leer el fichero SQL, componer filtros, ejecutar, truncar en modo
`sample`) vive en `src.export.engine.extractor.extract_via_sql` desde
Sprint 9.6 -- este fichero es un wrapper delgado que aporta el `SourceSpec`
de Drills y su propio `run_query` importado a nivel de módulo (necesario
para que `monkeypatch.setattr(drills.extractor, "run_query", fake)`, ya
usado por varios tests, siga funcionando: la función genérica recibe
`run_query` como parámetro en cada llamada, nunca lo importa ella misma).

Nota de diseño (modo `sample`): la consulta original de Drills ya trae toda
la tabla ordenada por `FechaCreacion asc`; el modo `sample` ejecuta la MISMA
consulta y trunca el resultado localmente a `limit` filas -- por eso Drills
pasa `sort_column=None` al extractor genérico (a diferencia de Bypass, cuya
SQL no tiene `ORDER BY` propio).
"""
from __future__ import annotations

from typing import Sequence

from src.db.query_runner import run_query
from src.export.engine.extractor import (
    DEFAULT_SAMPLE_LIMIT,
    MODE_FULL,
    MODE_SAMPLE,
    ExtractionResult,
    extract_via_sql,
)
from src.query.models import CompiledFilter

from .config import DrillsExportConfig

__all__ = [
    "MODE_SAMPLE", "MODE_FULL", "DEFAULT_SAMPLE_LIMIT", "ExtractionResult", "extract_drills",
]


def extract_drills(
    config: DrillsExportConfig,
    mode: str = MODE_SAMPLE,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    compiled_filters: Sequence[CompiledFilter] | None = None,
) -> ExtractionResult:
    """Extrae Drills, opcionalmente filtrado por `compiled_filters` (Query
    Engine v0.1 -- ver `src.query`).

    Sin `compiled_filters`, comportamiento idéntico a leer y ejecutar
    `sql_text` tal cual -- sin ningún `WHERE` añadido."""
    return extract_via_sql(
        config.source, query_runner=run_query, mode=mode, limit=limit,
        compiled_filters=compiled_filters, sort_column=None,
    )
