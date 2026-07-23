"""
Detección de duplicados por clave de correlación histórica
(CS_HistoricalOriginID o equivalente).

Confirmado en este proyecto (ver CLAUDE.md): Eventos (585 casos) y OPS (423
casos) tienen registros duplicados reales — mismo contenido, distinto Id de
Enablon — probablemente por una re-ejecución del paso de creación sin
protección de idempotencia.

CUIDADO — excepción conocida: en Inspecciones/Observations, varias filas
comparten el mismo OriginID de forma LEGÍTIMA (a nivel de inspección, no de
observación individual). Antes de reportar "duplicado", comprobar si el
módulo en cuestión tiene ese patrón de agregación esperado — ver el
parámetro `expected_group_field` más abajo.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class DuplicateReport:
    total_filas: int
    ids_unicos: int
    ids_duplicados: int
    filas_afectadas: int
    ejemplos: pd.DataFrame


def find_duplicates(
    df: pd.DataFrame,
    id_col: str,
    content_cols: list[str] | None = None,
    n_examples: int = 5,
) -> DuplicateReport:
    """Encuentra valores de `id_col` que aparecen más de una vez.

    Si se pasan `content_cols`, los ejemplos devueltos muestran ese
    contenido para poder confirmar a ojo si es un duplicado real (contenido
    idéntico) o una agregación legítima (contenido distinto por fila).
    """
    counts = df[id_col].value_counts()
    dup_ids = counts[counts > 1]

    cols_to_show = [id_col] + (content_cols or [])
    cols_to_show = [c for c in cols_to_show if c in df.columns]
    ejemplos = (
        df[df[id_col].isin(dup_ids.index[:n_examples])][cols_to_show]
        if len(dup_ids)
        else pd.DataFrame(columns=cols_to_show)
    )

    return DuplicateReport(
        total_filas=len(df),
        ids_unicos=df[id_col].nunique(),
        ids_duplicados=len(dup_ids),
        filas_afectadas=int(dup_ids.sum()) if len(dup_ids) else 0,
        ejemplos=ejemplos,
    )


def is_legitimate_grouping(
    df: pd.DataFrame,
    id_col: str,
    group_key_col: str,
) -> bool:
    """Comprueba si el 'duplicado' de id_col en realidad corresponde a un
    agrupamiento legítimo por otra clave (p. ej. varias observaciones de una
    misma inspección comparten el OriginID de la inspección).

    Devuelve True si, para una muestra de IDs duplicados, todas las filas con
    el mismo id_col también comparten el mismo group_key_col (agregación
    esperada) en vez de tener groups distintos con contenido idéntico
    (duplicado real).
    """
    counts = df[id_col].value_counts()
    dup_ids = counts[counts > 1].index[:20]
    if len(dup_ids) == 0 or group_key_col not in df.columns:
        return False

    for _id in dup_ids:
        sub = df[df[id_col] == _id]
        if sub[group_key_col].nunique() > 1:
            # mismo id_col, pero referenciando cosas distintas -> no es
            # una agregación limpia, hay que revisar caso a caso
            return False
    return True
