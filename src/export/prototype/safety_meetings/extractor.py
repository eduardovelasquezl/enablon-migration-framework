"""Extracción SQL de solo lectura para safety_meetings.Group_Meetings.

El núcleo vive en `src.export.engine.extractor.extract_via_sql` (Sprint
9.6). Este fichero es un wrapper delgado que aporta el `SourceSpec` de
Safety Meetings, su propio `run_query` importado a nivel de módulo (para
que `monkeypatch.setattr(safety_meetings.extractor, "run_query", fake)`
funcione en tests, mismo motivo documentado en
`drills/extractor.py`/`bypass/extractor.py`), y `sort_column="FechaCreacion"`.

Nota de diseño (modo `sample`): igual que Bypass, la SQL de origen
(`SM2025.sql`) NO tiene `ORDER BY` propio -- el extractor genérico ordena
en pandas por `FechaCreacion` (columna real de `ITP_REUNION_GRUPO`, ver la
SQL) antes de truncar, nunca se modifica el fichero `.sql` en disco."""
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

from .config import SafetyMeetingsExportConfig

__all__ = [
    "MODE_SAMPLE", "MODE_FULL", "DEFAULT_SAMPLE_LIMIT", "ExtractionResult", "extract_safety_meetings",
]

_DETERMINISTIC_SORT_COLUMN = "FechaCreacion"


def extract_safety_meetings(
    config: SafetyMeetingsExportConfig,
    mode: str = MODE_SAMPLE,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    compiled_filters: Sequence[CompiledFilter] | None = None,
) -> ExtractionResult:
    """Extrae Safety Meetings, opcionalmente filtrado por `compiled_filters`
    (Query Engine, reutilizado tal cual de `src.query`).

    Sin `compiled_filters`, comportamiento idéntico a leer y ejecutar
    `sql_text` tal cual -- sin ningún `WHERE` añadido, mismo contrato que
    `extract_drills`/`extract_bypass`."""
    return extract_via_sql(
        config.source, query_runner=run_query, mode=mode, limit=limit,
        compiled_filters=compiled_filters, sort_column=_DETERMINISTIC_SORT_COLUMN,
    )
