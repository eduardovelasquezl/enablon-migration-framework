"""
Chequeos de calidad de datos (Función 4 del framework original) sobre un
CSV real ya exportado de Enablon, o sobre un DataFrame de origen SQL.

Ejecuta los checks definidos en config/validation_rules.yaml a nivel
conceptual; aquí van las implementaciones reutilizables.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class DataQualityReport:
    total_filas: int
    campos_siempre_vacios: list[str] = field(default_factory=list)
    tags_origen_inconsistentes: dict[str, list[str]] = field(default_factory=dict)
    huerfanos_pct: float | None = None
    notas: list[str] = field(default_factory=list)


def campos_siempre_vacios(df: pd.DataFrame, umbral_pct: float = 100.0) -> list[str]:
    """Campos 100% vacíos (o >= umbral_pct% vacíos) — candidatos a excluir
    del mapeo activo. Confirmado útil en Simulacros/OPS/Bypass: varios
    campos destino nunca se usan en producción."""
    vacio_pct = df.isna().mean() * 100
    return sorted(vacio_pct[vacio_pct >= umbral_pct].index.tolist())


def tags_inconsistentes(df: pd.DataFrame, col: str) -> dict[str, list[str]]:
    """Detecta variantes de un mismo valor que difieren solo por
    tildes/mayúsculas (patrón confirmado en CS_HistoricalDataOrigin de
    Eventos: 'Prevencion...' vs 'Prevención...').

    Devuelve {forma_normalizada: [variantes encontradas]} solo para los
    casos con más de una variante.
    """
    if col not in df.columns:
        return {}

    def normalize(v: str) -> str:
        import unicodedata

        return "".join(
            c for c in unicodedata.normalize("NFKD", v) if not unicodedata.combining(c)
        ).lower().strip()

    values = df[col].dropna().unique()
    groups: dict[str, set[str]] = {}
    for v in values:
        groups.setdefault(normalize(str(v)), set()).add(str(v))

    return {k: sorted(v) for k, v in groups.items() if len(v) > 1}


def referential_integrity(
    child_df: pd.DataFrame,
    child_key_col: str,
    parent_df: pd.DataFrame,
    parent_key_col: str,
) -> tuple[int, int, float]:
    """Comprueba que child_key_col en child_df siempre exista en
    parent_key_col de parent_df. Devuelve (huérfanos, total, % huérfanos).

    Ejemplo confirmado en este proyecto: Observations.Inspection debe
    existir en Inspections.Id (en la realidad, 100% de integridad — un
    ejemplo de módulo sano frente a Eventos, donde Impacts/Investigations sí
    tienen huérfanos: ~14-15%).
    """
    parent_keys = set(parent_df[parent_key_col].dropna())
    is_orphan = ~child_df[child_key_col].isin(parent_keys)
    total = len(child_df)
    huerfanos = int(is_orphan.sum())
    pct = round(huerfanos / total * 100, 1) if total else 0.0
    return huerfanos, total, pct


def run_full_report(
    df: pd.DataFrame,
    origen_tag_col: str | None = None,
) -> DataQualityReport:
    report = DataQualityReport(total_filas=len(df))
    report.campos_siempre_vacios = campos_siempre_vacios(df)
    if origen_tag_col:
        report.tags_origen_inconsistentes = tags_inconsistentes(df, origen_tag_col)
    if report.campos_siempre_vacios:
        report.notas.append(
            f"{len(report.campos_siempre_vacios)} campo(s) 100% vacío(s) en esta "
            "muestra — confirmar con el cliente antes de retirarlos del mapeo activo."
        )
    if report.tags_origen_inconsistentes:
        report.notas.append(
            "Hay variantes de tilde/mayúscula en el campo de origen — "
            "normalizar antes de agrupar por él."
        )
    return report
