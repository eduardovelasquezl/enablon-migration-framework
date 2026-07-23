"""Extracción SQL de solo lectura para simulacros.Drills.

Reutiliza `src.db.query_runner` (validación de solo lectura, límite de
filas, logging sin credenciales) -- no reimplementa ninguna de sus
salvaguardas. No se modifica `sql/source_queries/Simulacros/SQLQuery -
DATASET SIMULACRO.sql`: es una fuente única sin joins (confirmado en
`export_readiness_matrix.md` §7.1), no hace falta adaptarla.

Nota de diseño (modo `sample`): la consulta original ya trae toda la tabla
ordenada por `FechaCreacion asc`; el modo `sample` ejecuta la MISMA consulta
y trunca el resultado localmente a `limit` filas (las más antiguas, orden
determinista). Para el volumen real de Drills (~12k filas históricas) esto
es aceptable -- se documenta aquí en vez de reescribir la consulta con un
`TOP (n)` que obligaría a parsear y reconstruir su `ORDER BY`, un riesgo
mayor que el coste de leer la tabla completa una vez.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from src.db.query_runner import run_query

from .config import DrillsExportConfig

MODE_SAMPLE = "sample"
MODE_FULL = "full"
DEFAULT_SAMPLE_LIMIT = 100


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


def _sql_hash(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def extract_drills(
    config: DrillsExportConfig,
    mode: str = MODE_SAMPLE,
    limit: int = DEFAULT_SAMPLE_LIMIT,
) -> ExtractionResult:
    if mode not in (MODE_SAMPLE, MODE_FULL):
        raise ValueError(f"Modo de extracción no soportado: {mode!r} (usar 'sample' o 'full')")
    if mode == MODE_SAMPLE and limit <= 0:
        raise ValueError(f"El límite de 'sample' debe ser positivo, se recibió {limit}")

    sql_text = config.source.sql_path.read_text(encoding="utf-8-sig")
    sql_hash = _sql_hash(sql_text)

    df_full = run_query(
        sql_text,
        connection=config.source.connection,
        source_file=str(config.source.sql_path),
    )
    rows_available = len(df_full)

    if mode == MODE_SAMPLE:
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
    )
