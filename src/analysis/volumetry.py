"""
Volumetría origen vs Enablon real, desglosada por site.

Regla de oro de este proyecto (ver CLAUDE.md, "Hallazgo #1"): NUNCA
comparar solo el total agregado. Un total sano puede esconder un site con
un problema severo — es exactamente lo que pasó con Servicio Prevención
LA RABIDA y MC-Palos de la Frontera en varios módulos.

Este módulo generaliza el proceso manual que se repitió para Simulacros,
Safety Meetings, MOC, Bypass, Eventos, OPS e Inspecciones:
1. Resolver el campo de entidad de origen (Code o Ruta1) a un "site" usando
   el catálogo real de Enablon.
2. Resolver el campo de entidad del CSV real de Enablon de la misma forma.
3. Comparar recuentos por site, no solo el total.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EntityCatalog:
    """Envuelve el catálogo real de entidades ya resuelto
    (ver inputs/entity_catalog/ y el proceso descrito en CLAUDE.md).

    Espera un CSV con, como mínimo, columnas: Code, Ruta1, Centro.
    """
    code_to_site: dict[str, str]
    ruta_to_site: dict[str, str]

    @classmethod
    def from_csv(cls, path: str | Path) -> "EntityCatalog":
        df = pd.read_csv(path, dtype=str)
        code_to_site = dict(zip(df["Code"], df["Centro"]))
        ruta_to_site = dict(zip(df["Ruta1"], df["Centro"])) if "Ruta1" in df.columns else {}
        return cls(code_to_site=code_to_site, ruta_to_site=ruta_to_site)

    def resolve(self, value: str | None) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "SIN DATO"
        if value in self.ruta_to_site:
            return self.ruta_to_site[value]
        if value in self.code_to_site:
            return self.code_to_site[value]
        return "NO CATALOGADO"


NO_SITE_SCOPE_LABELS = {
    "no migra": "FUERA DE ALCANCE (No Migra)",
    "sin match": "SIN DATO / ERROR ORIGEN",
    "unidad organizativa es null": "SIN DATO / ERROR ORIGEN",
}


def resolve_site_series(series: pd.Series, catalog: EntityCatalog) -> pd.Series:
    def _resolve(v):
        if isinstance(v, str) and v.strip().lower() in NO_SITE_SCOPE_LABELS:
            return NO_SITE_SCOPE_LABELS[v.strip().lower()]
        return catalog.resolve(v)

    return series.apply(_resolve)


def compare_volumetry(
    origen_df: pd.DataFrame,
    origen_entity_col: str,
    enablon_df: pd.DataFrame,
    enablon_entity_col: str,
    catalog: EntityCatalog,
) -> pd.DataFrame:
    """Devuelve una tabla Site | Origen_SQL | Enablon_real | Delta | Delta_%,
    ordenada por volumen de origen descendente, con fila TOTAL.

    Además registra un warning si algún site representa más de un 15% del
    origen y tiene un delta negativo mayor al 30% — ese es exactamente el
    patrón del Hallazgo #1 del proyecto (La Rábida / Palos de la Frontera).
    """
    origen_site = resolve_site_series(origen_df[origen_entity_col], catalog)
    enablon_site = resolve_site_series(enablon_df[enablon_entity_col], catalog)

    origen_counts = origen_site.value_counts()
    enablon_counts = enablon_site.value_counts()

    comp = pd.DataFrame({"Origen_SQL": origen_counts, "Enablon_real": enablon_counts}).fillna(0)
    comp = comp.astype(int)
    comp["Delta"] = comp["Enablon_real"] - comp["Origen_SQL"]
    comp["Delta_%"] = (comp["Delta"] / comp["Origen_SQL"].replace(0, pd.NA) * 100).round(1)
    comp = comp.sort_values("Origen_SQL", ascending=False)

    total = comp[["Origen_SQL", "Enablon_real", "Delta"]].sum()
    total["Delta_%"] = round(total["Delta"] / total["Origen_SQL"] * 100, 1) if total["Origen_SQL"] else None
    comp.loc["TOTAL"] = total

    _warn_if_hallazgo_1_pattern(comp)
    return comp


def _warn_if_hallazgo_1_pattern(comp: pd.DataFrame) -> None:
    if "TOTAL" not in comp.index:
        return
    total_origen = comp.loc["TOTAL", "Origen_SQL"]
    if not total_origen:
        return
    for site, row in comp.drop(index="TOTAL").iterrows():
        share = row["Origen_SQL"] / total_origen * 100
        delta_pct = row["Delta_%"]
        if share >= 15 and pd.notna(delta_pct) and delta_pct <= -30:
            logger.warning(
                "PATRÓN HALLAZGO #1: '%s' representa %.1f%% del origen y tiene "
                "un delta de %.1f%%. Revisar si es el mismo problema de "
                "infra-migración ya confirmado en Eventos/Inspecciones/MOC "
                "para La Rábida y Palos de la Frontera, ANTES de asumir que "
                "es un problema de catálogo o de rollback.",
                site, share, delta_pct,
            )


def save_report(comp: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    comp.to_csv(out_path, encoding="utf-8-sig")
    logger.info("Volumetría guardada en %s", out_path)
