"""CLI del proyecto -- Migración Histórica a Enablon.

Punto de entrada único (invocado desde `main.py` en la raíz del repo).
Hoy solo expone el prototipo de exportación de Drills (`export drills`) --
no existe todavía un `export all` ni soporte genérico para otros objetos;
ver `docs/specifications/v1.0/export/closing_recommendation.md`.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from src.config import PROJECT_ROOT
from src.db.exceptions import DatabaseError
from src.export.prototype.drills.extractor import MODE_FULL, MODE_SAMPLE
from src.export.prototype.drills.pipeline import run as run_drills_export

_ALLOWED_OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@click.group()
@click.option("--verbose", is_flag=True, default=False, help="Logging en nivel DEBUG.")
def cli(verbose: bool) -> None:
    """CLI del proyecto de migración histórica a Enablon (solo lectura)."""
    _configure_logging(verbose)


@cli.group()
def export() -> None:
    """Comandos de exportación (prototipo, review_only)."""


def _validate_output_dir(value: str | None) -> Path | None:
    if value is None:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(_ALLOWED_OUTPUT_ROOT.resolve())
    except ValueError:
        raise click.BadParameter(
            f"La ruta de salida debe estar dentro de {_ALLOWED_OUTPUT_ROOT} "
            f"(se recibió: {candidate})."
        )
    return candidate


@export.command("drills")
@click.option(
    "--mode", type=click.Choice([MODE_SAMPLE, MODE_FULL]), default=MODE_SAMPLE,
    show_default=True, help="'sample' trunca localmente a --limit filas; 'full' exporta todo.",
)
@click.option("--limit", type=int, default=100, show_default=True, help="Filas máximas en modo 'sample'.")
@click.option(
    "--confirm-full-export", is_flag=True, default=False,
    help="Obligatorio junto con --mode full -- evita ejecutar una exportación completa por accidente.",
)
@click.option(
    "--output-dir", type=str, default=None,
    help="Directorio raíz de salida (debe estar dentro de outputs/). Por defecto: outputs/prototype/drills/.",
)
def export_drills(mode: str, limit: int, confirm_full_export: bool, output_dir: str | None) -> None:
    """Genera drills.csv + validation_report.yaml + export_manifest.yaml
    (+ comparison_report.yaml si hay CSV histórico) para simulacros.Drills.

    Prototipo de revisión (`prototype_status: review_only`) -- el CSV
    resultante NO es un fichero aprobado para carga en Enablon.
    """
    if limit <= 0:
        raise click.BadParameter("--limit debe ser un entero positivo.", param_hint="--limit")

    if mode == MODE_FULL and not confirm_full_export:
        raise click.UsageError(
            "El modo 'full' requiere --confirm-full-export explícito "
            "(evita exportar todo el histórico por accidente)."
        )

    resolved_output_dir = _validate_output_dir(output_dir)

    click.echo("=== Prototype Export -- simulacros.Drills ===")
    click.echo(f"  objeto:            Drills (simulacros)")
    click.echo(f"  conexion:          prevencion")
    click.echo(f"  modo:              {mode}")
    click.echo(f"  limite (sample):   {limit if mode == MODE_SAMPLE else 'N/A'}")
    click.echo(f"  salida (raiz):     {resolved_output_dir or (PROJECT_ROOT / 'outputs' / 'prototype' / 'drills')}")
    click.echo(f"  estado:            review_only (NO aprobado para carga en Enablon)")
    click.echo("")

    try:
        result = run_drills_export(mode=mode, limit=limit, output_root=resolved_output_dir)
    except DatabaseError as exc:
        click.echo(f"ERROR de base de datos: {exc}", err=True)
        sys.exit(1)
    except (FileNotFoundError, ValueError, RuntimeError, FileExistsError) as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    status = result.validation_report["status"]["result"]
    click.echo(f"Resultado:          {status}")
    click.echo(f"Filas exportadas:   {result.stats.rows_exported}")
    click.echo(f"Filas excluidas:    {result.stats.rows_excluded}")
    click.echo(f"Warnings:           {len(result.stats.warnings)}")
    click.echo(f"CSV:                {result.csv_path}")
    click.echo(f"validation_report:  {result.validation_report_path}")
    click.echo(f"export_manifest:    {result.manifest_path}")
    if result.comparison_report_path:
        click.echo(f"comparison_report:  {result.comparison_report_path}")

    if status in ("FAILED_VALIDATION", "FAILED_EXECUTION"):
        sys.exit(1)


if __name__ == "__main__":
    cli()
