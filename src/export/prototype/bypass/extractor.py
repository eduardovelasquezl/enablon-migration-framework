"""Extracción SQL de solo lectura para bypass.By_Passes.

DUPLICATED_FROM_DRILLS (estructura completa, deliberadamente): mismo
patrón que `drills.extractor.extract_drills` -- no existe todavía un
extractor genérico parametrizado por `ExportConfig` (ver
docs/07-developer-guide/bypass-module.md § 6). Lo que SÍ se reutiliza
tal cual, sin copiar código, son las piezas realmente genéricas:
`src.db.query_runner.run_query`, `src.query.models.CompiledFilter`,
`src.query.sql_builder.compose_filtered_sql`.

Nota de diseño (modo `sample`): igual que Drills, el SQL de origen
(`SQLQuery-dataset_BES.sql`) NO tiene `ORDER BY` -- a diferencia de
Drills, que sí lo tenía (`FechaCreacion asc`). Sin un orden determinista
en la propia SQL, un `.head(limit)` puro no sería reproducible entre
ejecuciones. Se añade una ordenación en pandas, DESPUÉS de traer los
datos (nunca se modifica el fichero .sql en disco) -- por
`FechaCreacion`, la misma columna que Drills usa para su propio orden,
ya seleccionada por esta consulta.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Sequence

import pandas as pd

from src.db.query_runner import run_query
from src.query.models import CompiledFilter
from src.query.sql_builder import ComposedQuery, compose_filtered_sql

from .config import BypassExportConfig

MODE_SAMPLE = "sample"
MODE_FULL = "full"
DEFAULT_SAMPLE_LIMIT = 100

_DETERMINISTIC_SORT_COLUMN = "FechaCreacion"


@dataclass(frozen=True)
class ExtractionResult:
    dataframe: pd.DataFrame
    mode: str
    limit: int | None
    rows_available_before_truncation: int
    sql_text: str
    sql_sha256: str
    connection_name: str
    source_file: str
    compiled_filters: tuple[CompiledFilter, ...] = field(default_factory=tuple)
    composed_sql_text: str | None = None


def _sql_hash(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


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
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo de extracción no soportado: {mode!r} (usar 'sample' o 'full')")
    if mode == MODE_SAMPLE and limit <= 0:
        raise ValueError(f"El límite de 'sample' debe ser positivo, se recibió {limit}")

    sql_text = config.source.sql_path.read_text(encoding="utf-8-sig")
    sql_hash = _sql_hash(sql_text)

    compiled_filters = tuple(compiled_filters or ())
    composed: ComposedQuery | None = None
    if compiled_filters:
        composed = compose_filtered_sql(sql_text, compiled_filters)

    df_full = run_query(
        composed.sql_text if composed else sql_text,
        connection=config.source.connection,
        params=composed.parameters if composed else None,
        source_file=str(config.source.sql_path),
    )
    rows_available = len(df_full)

    if mode == MODE_SAMPLE:
        if _DETERMINISTIC_SORT_COLUMN in df_full.columns:
            df_full = df_full.sort_values(_DETERMINISTIC_SORT_COLUMN, kind="stable").reset_index(drop=True)
        df = df_full.head(limit).reset_index(drop=True)
        effective_limit = limit
    else:
        df = df_full
        effective_limit = None

    return ExtractionResult(
        dataframe=df,
        mode=mode,
        limit=effective_limit,
        rows_available_before_truncation=rows_available,
        sql_text=sql_text,
        sql_sha256=sql_hash,
        connection_name=config.source.connection,
        source_file=str(config.source.sql_path),
        compiled_filters=compiled_filters,
        composed_sql_text=composed.sql_text if composed else None,
    )
