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
from src.core.contracts import ExecutionRequest
from src.core.exceptions import CoreError
from src.core.orchestrator import PipelineOrchestrator
from src.core.registry import StageRegistry
from src.db.exceptions import DatabaseError
from src.evidence.collector import resolve_run_dir, load_run
from src.evidence.models import EvidenceSourceError
from src.evidence.workbook import build_workbook, save_workbook
from src.export.prototype.drills.core_adapters import (
    build_drills_pipeline_definition,
    build_execution_context,
    register_drills_stages,
)
from src.export.prototype.drills.extractor import MODE_FULL, MODE_SAMPLE
from src.export.prototype.drills.pipeline import run as run_drills_export
from src.query.catalog import DRILLS_FILTER_CATALOG
from src.query.models import QueryEngineError
from src.query.validator import compile_filter_tokens
from src.core.workspace_manifest import (
    WorkspaceManifestError,
    WorkspaceManifestLoader,
    validate_manifest,
)
from src.core.data_workspace import get_default_data_workspace
from src.core.resource_resolver import (
    ResourceRequest,
    ResourceResolutionError,
    ResourceResolver,
)

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


_CORE_SUPPORTED_OBJECT_TYPES = ("drills",)


@cli.command("run")
@click.option("--project", required=True, help="Nombre del proyecto (p. ej. 'moeve').")
@click.option(
    "--object", "object_type", required=True,
    help=f"Objeto migrable a ejecutar a través del Framework Core (hoy: {_CORE_SUPPORTED_OBJECT_TYPES}).",
)
@click.option("--module", "module_", default=None, help="Módulo del objeto (p. ej. 'simulacros').")
@click.option(
    "--mode", type=click.Choice([MODE_SAMPLE, MODE_FULL]), default=MODE_SAMPLE, show_default=True,
    help="'sample' trunca localmente a --limit filas; 'full' exporta todo.",
)
@click.option("--limit", type=int, default=100, show_default=True, help="Filas máximas en modo 'sample'.")
@click.option(
    "--confirm-full-export", is_flag=True, default=False,
    help="Obligatorio junto con --mode full -- evita ejecutar una exportación completa por accidente.",
)
@click.option(
    "--output-dir", type=str, default=None,
    help="Directorio raíz de salida. Por defecto: el mismo que usa 'export drills' hoy.",
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
    help="Filtro reutilizable 'campo:operador:valor' (repetible) -- mismo catálogo que 'export drills'.",
)
def run_pipeline(
    project: str, object_type: str, module_: str | None, mode: str, limit: int,
    confirm_full_export: bool, output_dir: str | None, generate_evidence: bool,
    audience: str, filters: tuple[str, ...],
) -> None:
    """Ejecuta un objeto migrable a través del Framework Core v1
    (Execution Pipeline genérico, Fase 6 del roadmap EMF -- ver
    docs/01-architecture/framework-core-v1.md).

    Hoy solo 'drills' está registrado como consumidor del Core. El comando
    'export drills' sigue siendo el camino existente sin cambios -- este
    comando es una entrada NUEVA que demuestra la integración genérica,
    no un reemplazo.
    """
    if object_type not in _CORE_SUPPORTED_OBJECT_TYPES:
        click.echo(
            f"ERROR: objeto no soportado todavía por el Framework Core: {object_type!r} "
            f"(disponibles: {_CORE_SUPPORTED_OBJECT_TYPES}).", err=True,
        )
        sys.exit(1)

    try:
        request = ExecutionRequest(
            project=project, object_type=object_type, module=module_, mode=mode, limit=limit,
            output_dir=output_dir, confirm_full_export=confirm_full_export,
            generate_evidence=generate_evidence, evidence_audience=audience, filters=tuple(filters),
        )
    except CoreError as exc:
        click.echo(f"ERROR de configuración: {exc}", err=True)
        sys.exit(1)

    registry = StageRegistry()
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()
    context = build_execution_context(request)
    orchestrator = PipelineOrchestrator(registry)

    click.echo("=== Framework Core v1 -- Execution Pipeline ===")
    click.echo(f"  proyecto:        {project}")
    click.echo(f"  objeto:          {object_type}")
    click.echo(f"  modo:            {mode}")
    click.echo(f"  etapas:          {' -> '.join(definition.stages)}")
    click.echo(f"  execution_id:    {context.execution_id}")
    click.echo("")

    try:
        result = orchestrator.run(definition, context)
    except DatabaseError as exc:
        click.echo(f"ERROR de base de datos: {exc}", err=True)
        sys.exit(1)
    except QueryEngineError as exc:
        click.echo(f"ERROR de filtro: {exc}", err=True)
        sys.exit(1)
    except CoreError as exc:
        click.echo(f"ERROR del Core: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Resultado:          {result.status}")
    click.echo(f"Duración:           {result.duration_seconds:.2f}s")
    click.echo(f"Etapas ejecutadas:  {len(result.stage_results)}")
    for stage_result in result.stage_results:
        click.echo(f"  - {stage_result.stage}: {stage_result.status}")
    click.echo(f"Artefactos:")
    for artifact in result.artifacts:
        click.echo(f"  - [{artifact.stage}] {artifact.name}: {artifact.path}")
    click.echo(f"Incidencias acumuladas: {len(result.issues)}")

    if result.status == "failed":
        sys.exit(1)


@cli.group()
def workspace() -> None:
    """Comandos sobre el Workspace Manifest (Sprint 8.4). Nunca accede a
    SQL Server, nunca abre un archivo referenciado por el manifest --
    solo lee el propio YAML del manifest y valida su forma/reglas."""


@workspace.command("validate")
@click.option(
    "--manifest", "manifest_path", type=str, required=True,
    help="Ruta al fichero workspace.yaml a validar (p. ej. examples/workspace/workspace.example.yaml).",
)
def workspace_validate(manifest_path: str) -> None:
    """Carga y valida un Workspace Manifest: forma estructural
    (WorkspaceManifestLoader) + reglas de negocio (validate_manifest).

    Exit code 0 si es válido y sin violaciones; distinto de 0 en caso
    contrario. No lee ningún dato real referenciado por el manifest, no
    ejecuta SQL, no modifica nada.
    """
    path = Path(manifest_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    click.echo("=== Workspace Manifest -- validate ===")
    click.echo(f"  manifest: {path}")
    click.echo("")

    try:
        manifest = WorkspaceManifestLoader.load_from_path(path)
    except WorkspaceManifestError as exc:
        click.echo(f"ERROR de esquema: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Proyecto:  {manifest.project.id} ({manifest.project.display_name})")
    click.echo(f"Módulos:   {', '.join(manifest.module_ids())}")
    click.echo("")

    violations = validate_manifest(manifest)
    if violations:
        click.echo(f"Violaciones encontradas ({len(violations)}):", err=True)
        for violation in violations:
            click.echo(f"  - {violation}", err=True)
        sys.exit(1)

    click.echo("Resultado: OK -- sin violaciones.")


@workspace.command("resolve")
@click.option(
    "--manifest", "manifest_path", type=str, required=True,
    help="Ruta al fichero workspace.yaml (p. ej. examples/workspace/workspace.example.yaml).",
)
@click.option("--module", "module_id", type=str, required=True, help="module_id declarado en el manifest.")
@click.option(
    "--artifact", "artifact_type", type=str, required=True,
    help="Kind de artefacto a resolver (p. ej. operational_csv, template_csv, sql, mapping...).",
)
@click.option(
    "--require-exists", is_flag=True, default=False,
    help="Exige que el recurso exista físicamente -- si no, exit code distinto de 0.",
)
@click.option(
    "--allow-deprecated", is_flag=True, default=False,
    help="Permite resolver un artefacto marcado status=deprecated en el manifest.",
)
def workspace_resolve(
    manifest_path: str, module_id: str, artifact_type: str,
    require_exists: bool, allow_deprecated: bool,
) -> None:
    """Resuelve un único artefacto de un módulo contra el manifest y el
    workspace externo de datos real (`EMF_DATA_ROOT`) usando
    `ResourceResolver` (Sprint 8.5).

    Nunca abre el archivo resuelto, nunca modifica nada. Exit code 0 si
    el recurso se resuelve según lo pedido; distinto de 0 si el manifest
    no lo declara, está en un estado no resoluble, o (con
    --require-exists) no existe físicamente.
    """
    path = Path(manifest_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    click.echo("=== Workspace Manifest -- resolve ===")
    click.echo(f"  manifest: {path}")
    click.echo(f"  módulo:   {module_id}")
    click.echo(f"  artefacto:{artifact_type}")
    click.echo("")

    try:
        manifest = WorkspaceManifestLoader.load_from_path(path)
    except WorkspaceManifestError as exc:
        click.echo(f"ERROR de esquema: {exc}", err=True)
        sys.exit(1)

    resolver = ResourceResolver(manifest, get_default_data_workspace())
    request = ResourceRequest(
        module_id=module_id, artifact_type=artifact_type,
        required=require_exists, require_physical_file=require_exists,
        allow_deprecated=allow_deprecated,
    )

    try:
        resolved = resolver.resolve(request)
    except ResourceResolutionError as exc:
        click.echo(f"ERROR de resolución ({type(exc).__name__}): {exc}", err=True)
        sys.exit(1)

    click.echo(f"manifest_ref:    {resolved.manifest_ref}")
    click.echo(f"status:          {resolved.artifact_status}")
    click.echo(f"contract_role:   {resolved.contract_role or '(ninguno)'}")
    click.echo(f"declared_path:   {resolved.declared_path or '(no declarado)'}")
    click.echo(f"resolved_path:   {resolved.resolved_path or '(no resoluble sin path declarado)'}")
    click.echo(f"exists:          {resolved.exists if resolved.exists is not None else '(no comprobado)'}")
    click.echo(f"generated:       {resolved.generated}")
    if resolved.description:
        click.echo(f"description:     {resolved.description}")
    if resolved.warnings:
        click.echo(f"warnings ({len(resolved.warnings)}):")
        for warning in resolved.warnings:
            click.echo(f"  - {warning}")

    if require_exists and not resolved.exists:
        sys.exit(1)


if __name__ == "__main__":
    cli()
