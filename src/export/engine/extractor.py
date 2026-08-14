"""Extracción SQL de solo lectura, genérica (Sprint 9.6).

Núcleo idéntico ya demostrado por `drills/extractor.py::extract_drills` y
`bypass/extractor.py::extract_bypass` (Sprint 9.5.1 § Fase 2, ítem 2): leer
el fichero `.sql` declarado, componer un `WHERE` parametrizado si hay
filtros (`src.query.sql_builder.compose_filtered_sql`, nunca se modifica el
fichero en disco), ejecutar, y truncar localmente en modo `sample`.

Diferencia real entre Drills y Bypass, preservada aquí como parámetro
explícito (`sort_column`), NUNCA como una rama `if module == ...`: la SQL de
Drills ya trae su propio `ORDER BY`, así que Drills no necesita ordenar en
pandas (`sort_column=None`); la de Bypass no tiene `ORDER BY` propio, así
que Bypass SÍ ordena en pandas antes de truncar (`sort_column="FechaCreacion"`).

`query_runner` se recibe como parámetro (nunca importado aquí) para que cada
módulo conserve su propio `run_query` importado a nivel de módulo -- los
tests existentes hacen `monkeypatch.setattr(<módulo>.extractor, "run_query",
fake)`; si esta función importara `run_query` directamente, ese monkeypatch
dejaría de tener efecto. Ver `docs/07-developer-guide/` para el detalle de
este constraint (Sprint 9.6 § Fase 4).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

import pandas as pd

from src.export.engine.config import SourceSpec
from src.query.models import CompiledFilter
from src.query.sql_builder import ComposedQuery, compose_filtered_sql

MODE_SAMPLE = "sample"
MODE_FULL = "full"
DEFAULT_SAMPLE_LIMIT = 100


class QueryRunner(Protocol):
    def __call__(
        self, sql_text: str, *, connection: str, params: dict[str, Any] | None, source_file: str,
    ) -> pd.DataFrame: ...


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


def sql_hash(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def extract_via_sql(
    source: SourceSpec,
    *,
    query_runner: Callable[..., pd.DataFrame],
    mode: str = MODE_SAMPLE,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    compiled_filters: Sequence[CompiledFilter] | None = None,
    sort_column: str | None = None,
) -> ExtractionResult:
    """Extrae vía SQL, opcionalmente filtrado por `compiled_filters` (Query
    Engine v0.1 -- ver `src.query`).

    Sin `compiled_filters` (o con una secuencia vacía) el comportamiento es
    idéntico a ejecutar `sql_text` tal cual se leyó del fichero, sin ningún
    `WHERE` añadido. Con filtros, se compone en memoria un `WHERE` sobre
    `sql_text` (nunca se reescribe el fichero en disco), y la SQL resultante
    se ejecuta con los valores como parámetros nombrados -- nunca
    concatenados.

    `sort_column`: si se declara y existe en el resultado, se ordena en
    pandas (orden estable) antes de truncar en modo `sample` -- para SQL sin
    `ORDER BY` propio. Si es `None`, no se ordena (se confía en el `ORDER
    BY` de la propia SQL, o en su ausencia deliberada).
    """
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo de extracción no soportado: {mode!r} (usar 'sample' o 'full')")
    if mode == MODE_SAMPLE and limit <= 0:
        raise ValueError(f"El límite de 'sample' debe ser positivo, se recibió {limit}")

    sql_text = source.sql_path.read_text(encoding="utf-8-sig")
    sql_sha = sql_hash(sql_text)

    compiled_filters = tuple(compiled_filters or ())
    composed: ComposedQuery | None = None
    if compiled_filters:
        composed = compose_filtered_sql(sql_text, compiled_filters)

    df_full = query_runner(
        composed.sql_text if composed else sql_text,
        connection=source.connection,
        params=composed.parameters if composed else None,
        source_file=str(source.sql_path),
    )
    rows_available = len(df_full)

    if mode == MODE_SAMPLE:
        if sort_column and sort_column in df_full.columns:
            df_full = df_full.sort_values(sort_column, kind="stable").reset_index(drop=True)
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
        sql_sha256=sql_sha,
        connection_name=source.connection,
        source_file=str(source.sql_path),
        compiled_filters=compiled_filters,
        composed_sql_text=composed.sql_text if composed else None,
    )
