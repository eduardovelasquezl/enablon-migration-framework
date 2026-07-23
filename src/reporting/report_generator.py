"""
Genera informes markdown con el mismo formato usado durante todo el
análisis manual: Resumen ejecutivo / Hallazgos / Riesgos / Recomendaciones /
Automatizaciones propuestas / Próximos pasos (ver el prompt original del
proyecto).

No pretende sustituir el juicio de quien revisa — genera la estructura y
las tablas a partir de los resultados de src/analysis/*, dejando el texto
interpretativo como plantilla a rellenar o como notas ya conocidas de
CLAUDE.md / config/modules.yaml.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown()
    except ImportError:
        # to_markdown requiere 'tabulate'; fallback simple si no está instalado.
        header = "| " + " | ".join([str(df.index.name or "")] + list(df.columns)) + " |"
        sep = "|" + "---|" * (len(df.columns) + 1)
        rows = [
            "| " + " | ".join([str(idx)] + [str(v) for v in row]) + " |"
            for idx, row in df.iterrows()
        ]
        return "\n".join([header, sep] + rows)


def volumetry_report(
    modulo: str,
    comparison_df: pd.DataFrame,
    hallazgos: list[str] | None = None,
    riesgos: list[str] | None = None,
    recomendaciones: list[str] | None = None,
    proximos_pasos: list[str] | None = None,
) -> str:
    """Genera el markdown de un informe de volumetría para un módulo,
    siguiendo el formato estándar del proyecto."""
    hallazgos = hallazgos or []
    riesgos = riesgos or []
    recomendaciones = recomendaciones or []
    proximos_pasos = proximos_pasos or []

    lines = [
        f"# Volumetría — {modulo}",
        f"**Fecha:** {date.today().isoformat()}",
        "",
        "## Resumen ejecutivo",
        (
            f"Comparación de volumetría origen SQL vs. Enablon real para "
            f"{modulo}, desglosada por site (nunca solo el total agregado — "
            "ver Hallazgo #1 en CLAUDE.md)."
        ),
        "",
        "## Tabla de volumetría por site",
        "",
        _df_to_markdown_table(comparison_df),
        "",
    ]

    def _section(title: str, items: list[str]) -> list[str]:
        if not items:
            return []
        return [f"## {title}", "", *[f"- {i}" for i in items], ""]

    lines += _section("Hallazgos", hallazgos)
    lines += _section("Riesgos", riesgos)
    lines += _section("Recomendaciones", recomendaciones)
    lines += _section("Próximos pasos", proximos_pasos)

    return "\n".join(lines)


def save_report(markdown: str, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
