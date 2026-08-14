"""Extracción SQL de solo lectura para bypass.By_Passes.

El núcleo vive en `src.export.engine.extractor.extract_via_sql` desde
Sprint 9.6 (antes: DUPLICATED_FROM_DRILLS, forma casi idéntica a
`drills/extractor.py`). Este fichero es un wrapper delgado que aporta el
`SourceSpec` de Bypass, su propio `run_query` importado a nivel de módulo
(mismo motivo que en `drills/extractor.py`: preservar
`monkeypatch.setattr(bypass.extractor, "run_query", fake)`), y
`sort_column="FechaCreacion"`.

Nota de diseño (modo `sample`): a diferencia de Drills, el SQL de origen
(`SQLQuery-dataset_BES.sql`) NO tiene `ORDER BY` -- sin un orden
determinista en la propia SQL, un `.head(limit)` puro no sería reproducible
entre ejecuciones. El extractor genérico ordena en pandas, DESPUÉS de traer
los datos (nunca se modifica el fichero `.sql` en disco), por
`FechaCreacion`, la misma columna que Drills usa para su propio orden.
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

from .config import BypassExportConfig

__all__ = [
    "MODE_SAMPLE", "MODE_FULL", "DEFAULT_SAMPLE_LIMIT", "ExtractionResult", "extract_bypass",
]

_DETERMINISTIC_SORT_COLUMN = "FechaCreacion"


def extract_bypass(
    config: BypassExportConfig,
    mode: str = MODE_SAMPLE,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    compiled_filters: Sequence[CompiledFilter] | None = None,
) -> ExtractionResult:
    """Extrae Bypass, opcionalmente filtrado por `compiled_filters` (Query
    Engine, reutilizado tal cual de `src.query`).

    Sin `compiled_filters`, comportamiento idéntico a leer y ejecutar
    `sql_text` tal cual -- sin ningún `WHERE` añadido, mismo contrato que
    `extract_drills`."""
    return extract_via_sql(
        config.source, query_runner=run_query, mode=mode, limit=limit,
        compiled_filters=compiled_filters, sort_column=_DETERMINISTIC_SORT_COLUMN,
    )
