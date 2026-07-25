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
from src.evidence.collector import resolve_run_dir, load_run
from src.evidence.models import EvidenceSourceError
from src.evidence.workbook import build_workbook, save_workbook
from src.export.prototype.drills.extractor import MODE_FULL, MODE_SAMPLE
from src.export.prototype.drills.pipeline import run as run_drills_export
from src.query.catalog import DRILLS_FILTER_CATALOG
from src.query.models import QueryEngineError
from src.query.validator import compile_filter_tokens

_ALLOWED_OUTPUT_ROOT = PROJECT_ROOT / "outputs"
_AUDIENCES = ("internal", "client", "both")


def _generate_evidence(run_dir: Path, audience: str) -> list[Path]:
    """Genera evidence_internal.xlsx y/o evidence_client.xlsx para
    `run_dir`, sin volver a consultar SQL Server -- todo sale de los
    artefactos ya escritos por la exportación (ver `src.evidence.collector`).
    """
    ctx = load_run(run_dir)
    audiences = ("internal", "client") if audience == "both" else (audience,)
    written = []
    for aud in audiences:
        wb = build_workbook(ctx, aud)
        path = run_dir / f"evidence_{aud}.xlsx"
        save_workbook(wb, path)
        written.append(path)
    return written


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
@click.option(
    "--generate-evidence", is_flag=True, default=False,
    help="Genera evidence_internal.xlsx / evidence_client.xlsx al terminar la exportación.",
)
@click.option(
    "--audience", type=click.Choice(_AUDIENCES), default="both", show_default=True,
    help="Con --generate-evidence: qué versión(es) del Excel generar.",
)
@click.option(
    "--filter", "filters", multiple=True, default=(),
    help=(
        "Filtro reutilizable 'campo:operador:valor' (repetible; varios filtros se "
        "combinan con AND). Operadores: eq, in (máx. 200 valores). Campos permitidos: "
        "historical_origin_id, center_id, origin_org_unit_id, typology_id, letter_id, "
        "workflow_status_source -- ver 'Filtered exports' en README.md."
    ),
)
def export_drills(
    mode: str, limit: int, confirm_full_export: bool, output_dir: str | None,
    generate_evidence: bool, audience: str, filters: tuple[str, ...],
) -> None:
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

    # Los filtros se parsean y validan contra el catálogo cerrado ANTES de
    # tocar SQL Server -- una petición inválida no debe llegar nunca al
    # Query Runner (ver src/query/validator.py, sin dependencias de red).
    try:
        compiled_filters = compile_filter_tokens(filters, DRILLS_FILTER_CATALOG)
    except QueryEngineError as exc:
        click.echo(f"ERROR de filtro: {exc}", err=True)
        sys.exit(1)

    click.echo("=== Prototype Export -- simulacros.Drills ===")
    click.echo(f"  objeto:            Drills (simulacros)")
    click.echo(f"  conexion:          prevencion")
    click.echo(f"  modo:              {mode}")
    click.echo(f"  limite (sample):   {limit if mode == MODE_SAMPLE else 'N/A'}")
    click.echo(f"  salida (raiz):     {resolved_output_dir or (PROJECT_ROOT / 'outputs' / 'prototype' / 'drills')}")
    click.echo(f"  estado:            review_only (NO aprobado para carga en Enablon)")
    if compiled_filters:
        click.echo(f"  filtros ({len(compiled_filters)}):")
        for cf in compiled_filters:
            click.echo(f"    - {cf.field}:{cf.operator}:{cf.manifest_value}")
    else:
        click.echo(f"  filtros:           ninguno")
    click.echo("")

    try:
        result = run_drills_export(
            mode=mode, limit=limit, output_root=resolved_output_dir, compiled_filters=compiled_filters,
        )
    except DatabaseError as exc:
        click.echo(f"ERROR de base de datos: {exc}", err=True)
        sys.exit(1)
    except QueryEngineError as exc:
        click.echo(f"ERROR de filtro: {exc}", err=True)
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
    if result.manifest.get("query_filters", {}).get("generated_sql_file"):
        click.echo(f"generated_query.sql: {result.output_dir / result.manifest['query_filters']['generated_sql_file']}")

    if generate_evidence:
        try:
            written = _generate_evidence(result.output_dir, audience)
        except EvidenceSourceError as exc:
            click.echo(f"ERROR generando evidencia: {exc}", err=True)
            sys.exit(1)
        for path in written:
            click.echo(f"evidencia:          {path}")

    if status in ("FAILED_VALIDATION", "FAILED_EXECUTION"):
        sys.exit(1)


@cli.group()
def evidence() -> None:
    """Generación del Evidence Engine (Excel interno/cliente) a partir de
    una ejecución ya completada -- nunca vuelve a consultar SQL Server."""


@evidence.command("drills")
@click.option(
    "--run", "run_ref", type=str, default=None,
    help="Ruta de la ejecución (outputs/prototype/drills/<timestamp>) o su run_id. "
         "Por defecto: la ejecución más reciente.",
)
@click.option(
    "--audience", type=click.Choice(_AUDIENCES), default="both", show_default=True,
    help="Qué versión(es) del Excel generar.",
)
def evidence_drills(run_ref: str | None, audience: str) -> None:
    """Regenera evidence_internal.xlsx / evidence_client.xlsx para una
    ejecución existente de Drills, sin volver a consultar SQL Server."""
    try:
        run_dir = resolve_run_dir(run_ref)
    except EvidenceSourceError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    click.echo("=== Evidence Engine -- simulacros.Drills ===")
    click.echo(f"  ejecucion:         {run_dir}")
    click.echo(f"  audiencia:         {audience}")
    click.echo("")

    try:
        written = _generate_evidence(run_dir, audience)
    except EvidenceSourceError as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    for path in written:
        click.echo(f"evidencia:          {path}")


if __name__ == "__main__":
    cli()
