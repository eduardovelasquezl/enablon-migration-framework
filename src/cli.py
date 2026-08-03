"""CLI del proyecto -- Migración Histórica a Enablon.

Punto de entrada único (invocado desde `main.py` en la raíz del repo).
Hoy solo expone el prototipo de exportación de Drills (`export drills`) --
no existe todavía un `export all` ni soporte genérico para otros objetos;
ver `docs/specifications/v1.0/export/closing_recommendation.md`.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import click

from src.config import PROJECT_ROOT
from src.core.contracts import ExecutionRequest
from src.core.exceptions import CoreError
from src.core.module_registry import ModuleCapability, ModuleRegistryError
from src.core.orchestrator import PipelineOrchestrator
from src.core.registry import StageRegistry
from src.bootstrap.module_registry import build_default_module_registry
from src.db.exceptions import DatabaseError
from src.evidence.collector import resolve_run_dir, load_run
from src.evidence.models import EvidenceSourceError
from src.evidence.workbook import build_workbook, save_workbook
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
from src.core.readiness_validator import (
    ReadinessOperation,
    ReadinessRequest,
    ReadinessStatus,
    ReadinessValidatorError,
    WorkspaceReadinessValidator,
)
from src.db import sql_execution_guard

_ALLOWED_OUTPUT_ROOT = PROJECT_ROOT / "outputs"
_AUDIENCES = ("internal", "client", "both")


def _authorize_real_sql(allow_real_sql: bool, *, command: str) -> bool:
    """Comprobación previa a cualquier operación que pueda abrir una
    conexión SQL real (Sprint 8.6.1 -- SQL Execution Guard). Se llama al
    principio del comando, ANTES de construir cualquier `ExecutionRequest`,
    registro o directorio de salida -- sin outputs generados si se
    bloquea.

    Devuelve `True`/imprime nada si se concede autorización (y la deja
    concedida en `sql_execution_guard` para el resto del proceso, que es
    el chokepoint real que aplica el bloqueo en
    `src.db.connection.get_engine()`). Devuelve `False` e imprime un
    mensaje seguro (sin credenciales, sin cadenas de conexión) si no.

    Independiente de `sample`/`full`: ambos modos pueden abrir SQL real,
    ambos requieren esta autorización -- `--confirm-full-export` es una
    confirmación ADICIONAL, específica de `full`, nunca un sustituto.
    """
    if allow_real_sql:
        sql_execution_guard.grant(source="cli_flag")
        return True
    if os.environ.get(sql_execution_guard.ENV_VAR) == "1":
        sql_execution_guard.grant(source="env_var")
        return True

    click.echo(f"=== {command} -- SQL Execution Guard ===", err=True)
    click.echo("ERROR: esta operación puede abrir una conexión SQL Server real.", err=True)
    click.echo("Está bloqueada por defecto -- la disponibilidad de credenciales", err=True)
    click.echo("no implica autorización de uso.", err=True)
    click.echo("", err=True)
    click.echo("Añade --allow-real-sql tras recibir autorización técnica explícita", err=True)
    click.echo(f"(o exporta {sql_execution_guard.ENV_VAR}=1).", err=True)
    click.echo("", err=True)
    click.echo("No se abrió ninguna conexión. No se generó ningún output.", err=True)
    return False


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
@click.option(
    "--allow-real-sql", is_flag=True, default=False,
    help=(
        "Obligatorio (junto con EMF_ALLOW_REAL_SQL=1 como alternativa) para autorizar "
        "esta ejecución a abrir una conexión SQL Server real -- bloqueado por defecto, "
        "para 'sample' y 'full' por igual. Ver docs/01-architecture/sql-execution-guard.md."
    ),
)
def export_drills(
    mode: str, limit: int, confirm_full_export: bool, output_dir: str | None,
    generate_evidence: bool, audience: str, filters: tuple[str, ...], allow_real_sql: bool,
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

    # SQL Execution Guard (Sprint 8.6.1): último control antes de tocar SQL
    # real -- todas las validaciones de entrada anteriores (limit, modo,
    # filtros) son baratas y sin efectos secundarios, así que se
    # comprueban primero (mejores mensajes de error); esta es la última
    # comprobación antes de generar cualquier output real.
    if not _authorize_real_sql(allow_real_sql, command="export drills"):
        sys.exit(1)

    auth = sql_execution_guard.current_authorization()
    click.echo("=== Prototype Export -- simulacros.Drills ===")
    click.echo(f"  objeto:            Drills (simulacros)")
    click.echo(f"  conexion:          prevencion (readonly)")
    click.echo(f"  autorizacion SQL:  concedida (fuente={auth.source}, {auth.granted_at.isoformat()})")
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


@cli.command("run")
@click.option("--project", required=True, help="Nombre del proyecto (p. ej. 'moeve').")
@click.option(
    "--object", "object_type", required=True,
    help=(
        "Objeto migrable a ejecutar a través del Framework Core -- module_id o alias "
        "registrado en el ModuleRegistry (ver 'python main.py modules list')."
    ),
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
@click.option(
    "--allow-real-sql", is_flag=True, default=False,
    help=(
        "Obligatorio (junto con EMF_ALLOW_REAL_SQL=1 como alternativa) para autorizar "
        "esta ejecución a abrir una conexión SQL Server real -- bloqueado por defecto, "
        "para 'sample' y 'full' por igual. Ver docs/01-architecture/sql-execution-guard.md."
    ),
)
def run_pipeline(
    project: str, object_type: str, module_: str | None, mode: str, limit: int,
    confirm_full_export: bool, output_dir: str | None, generate_evidence: bool,
    audience: str, filters: tuple[str, ...], allow_real_sql: bool,
) -> None:
    """Ejecuta un objeto migrable a través del Framework Core v1
    (Execution Pipeline genérico, Fase 6 del roadmap EMF -- ver
    docs/01-architecture/framework-core-v1.md).

    La selección del módulo pasa por `ModuleRegistry` (Sprint 8.6, ver
    docs/01-architecture/module-registry.md) -- ningún condicional
    específico de Drills vive ya en este comando. El comando
    'export drills' sigue siendo el camino existente sin cambios -- este
    comando es una entrada NUEVA que demuestra la integración genérica,
    no un reemplazo.
    """
    module_registry = build_default_module_registry()
    try:
        module_def = module_registry.ensure_capability(object_type, ModuleCapability.EXPORT)
        module_registry.ensure_capability(module_def.module_id, mode)
    except ModuleRegistryError as exc:
        click.echo(f"ERROR de módulo ({type(exc).__name__}): {exc}", err=True)
        sys.exit(1)

    # SQL Execution Guard (Sprint 8.6.1): último control antes de tocar SQL
    # real -- la resolución de módulo/capacidad anterior es barata y sin
    # efectos secundarios (mejor mensaje de error si --object es un typo);
    # esta es la última comprobación antes de construir la petición y
    # ejecutar el pipeline real.
    if not _authorize_real_sql(allow_real_sql, command="run"):
        sys.exit(1)

    try:
        request = ExecutionRequest(
            project=project, object_type=module_def.module_id, module=module_, mode=mode, limit=limit,
            output_dir=output_dir, confirm_full_export=confirm_full_export,
            generate_evidence=generate_evidence, evidence_audience=audience, filters=tuple(filters),
        )
    except CoreError as exc:
        click.echo(f"ERROR de configuración: {exc}", err=True)
        sys.exit(1)

    stage_registry = StageRegistry()
    try:
        pipeline_factory = module_registry.get_pipeline_factory(module_def.module_id)
    except ModuleRegistryError as exc:
        click.echo(f"ERROR de módulo ({type(exc).__name__}): {exc}", err=True)
        sys.exit(1)
    definition, context = pipeline_factory(request, stage_registry)
    orchestrator = PipelineOrchestrator(stage_registry)

    auth = sql_execution_guard.current_authorization()
    click.echo("=== Framework Core v1 -- Execution Pipeline ===")
    click.echo(f"  proyecto:        {project}")
    click.echo(f"  objeto:          {object_type} (module_id={module_def.module_id})")
    click.echo(f"  autorizacion SQL: concedida (fuente={auth.source}, {auth.granted_at.isoformat()})")
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


_READINESS_EXIT_CODES = {
    ReadinessStatus.READY: 0,
    ReadinessStatus.READY_WITH_WARNINGS: 1,
    ReadinessStatus.BLOCKED: 2,
}


def _issue_to_dict(issue) -> dict:
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "project_id": issue.project_id,
        "module_id": issue.module_id,
        "operation": issue.operation,
        "artifact_type": issue.artifact_type,
        "declared_path": issue.declared_path,
        "required": issue.required,
        "source_component": issue.source_component,
        "remediation": issue.remediation,
        "reference": issue.reference,
    }


def _resolved_resource_to_dict(resolved) -> dict:
    return {
        "artifact_type": resolved.artifact_type,
        "declared_path": resolved.declared_path,
        "resolved_path": str(resolved.resolved_path) if resolved.resolved_path else None,
        "artifact_status": resolved.artifact_status,
        "exists": resolved.exists,
        "generated": resolved.generated,
        "contract_role": resolved.contract_role,
    }


def _assessment_to_dict(assessment) -> dict:
    return {
        "assessment_id": assessment.assessment_id,
        "timestamp": assessment.timestamp.isoformat(),
        "project_id": assessment.project_id,
        "module_id": assessment.module_id,
        "operation": assessment.operation,
        "status": assessment.status,
        "checks": list(assessment.checks),
        "issues": [_issue_to_dict(i) for i in assessment.issues],
        "required_artifacts": list(assessment.required_artifacts),
        "optional_artifacts": list(assessment.optional_artifacts),
        "resolved_resources": [_resolved_resource_to_dict(r) for r in assessment.resolved_resources],
        "missing_resources": list(assessment.missing_resources),
        "generated_resources": list(assessment.generated_resources),
        "summary": assessment.summary,
        "recommended_next_action": assessment.recommended_next_action,
    }


@workspace.command("readiness")
@click.option(
    "--manifest", "manifest_path", type=str, required=True,
    help="Ruta al fichero workspace.yaml (p. ej. examples/workspace/workspace.example.yaml).",
)
@click.option("--module", "module_id", type=str, required=True, help="module_id o alias declarado/registrado.")
@click.option(
    "--operation", type=click.Choice(sorted(ReadinessOperation.ALL)), required=True,
    help="Operación a evaluar: sample, full, comparison, evidence, validation o export.",
)
@click.option(
    "--require-files", is_flag=True, default=False,
    help="Comprueba también existencia física de los recursos resolubles (nunca abre su contenido).",
)
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True,
    help="Formato de salida -- 'json' para consumo automatizado.",
)
@click.option(
    "--strict", is_flag=True, default=False,
    help="Trata cualquier advertencia como bloqueo (útil para gates de CI/automatización).",
)
def workspace_readiness(
    manifest_path: str, module_id: str, operation: str,
    require_files: bool, output_format: str, strict: bool,
) -> None:
    """Evalúa si un módulo/operación está listo para EMPEZAR -- nunca
    ejecuta nada, nunca abre SQL, nunca requiere --allow-real-sql.

    Compone `ModuleRegistry` + `WorkspaceManifest` + `ResourceResolver`
    (Sprint 8.7, ver docs/01-architecture/workspace-readiness-validator.md).
    Exit codes (distintos del resto de la CLI, documentado deliberadamente):
    0=READY, 1=READY_WITH_WARNINGS, 2=BLOCKED, 3=error técnico/config.
    """
    path = Path(manifest_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    try:
        manifest = WorkspaceManifestLoader.load_from_path(path)
    except WorkspaceManifestError as exc:
        click.echo(f"ERROR de esquema: {exc}", err=True)
        sys.exit(3)

    registry = build_default_module_registry()
    resolver = ResourceResolver(manifest, get_default_data_workspace())

    try:
        request = ReadinessRequest(
            project_id=manifest.project.id, module_id=module_id, operation=operation,
            manifest=manifest, registry=registry, resolver=resolver,
            require_physical_files=require_files, strict=strict,
        )
        assessment = WorkspaceReadinessValidator().assess(request)
    except ReadinessValidatorError as exc:
        click.echo(f"ERROR de configuración ({type(exc).__name__}): {exc}", err=True)
        sys.exit(3)

    if output_format == "json":
        click.echo(json.dumps(_assessment_to_dict(assessment), indent=2, ensure_ascii=False))
        sys.exit(_READINESS_EXIT_CODES[assessment.status])

    click.echo("=== Workspace Readiness ===")
    click.echo(f"Project:            {assessment.project_id}")
    click.echo(f"Module:             {assessment.module_id}")
    click.echo(f"Operation:          {assessment.operation}")
    click.echo(f"Status:             {assessment.status}")
    click.echo("")
    click.echo(f"Blockers ({len(assessment.blockers)}):")
    for issue in assessment.blockers:
        click.echo(f"  - [{issue.code}] {issue.message}")
    click.echo(f"Warnings ({len(assessment.warnings)}):")
    for issue in assessment.warnings:
        click.echo(f"  - [{issue.code}] {issue.message}")
    click.echo("")
    click.echo(f"Required resources: {', '.join(assessment.required_artifacts) or '(ninguno)'}")
    click.echo(f"Missing resources:  {', '.join(assessment.missing_resources) or '(ninguno)'}")
    click.echo("")
    click.echo(f"Next action:        {assessment.recommended_next_action}")

    sys.exit(_READINESS_EXIT_CODES[assessment.status])


@cli.group()
def modules() -> None:
    """Inspección del Module Registry (Sprint 8.6). Solo lectura -- nunca
    ejecuta un pipeline, nunca accede a SQL Server, nunca modifica nada."""


@modules.command("list")
def modules_list() -> None:
    """Lista, en orden determinista, todos los módulos que el software
    sabe ejecutar (registrados en el ModuleRegistry) -- no confundir con
    los módulos declarados en un Workspace Manifest de un proyecto
    concreto (`workspace validate` cubre eso)."""
    registry = build_default_module_registry()
    click.echo("=== Module Registry -- list ===")
    click.echo("")
    for module_id in registry.list_modules():
        definition = registry.get(module_id)
        click.echo(
            f"  {definition.module_id:<20} status={definition.status:<12} "
            f"version={definition.version:<8} {definition.display_name}"
        )
    click.echo("")
    click.echo(f"Total: {len(registry.list_modules())} (ejecutables: {len(registry.list_executable())})")


@modules.command("show")
@click.argument("module_id_or_alias")
def modules_show(module_id_or_alias: str) -> None:
    """Muestra la definición completa de un módulo -- nunca rutas físicas
    ni credenciales, solo metadatos declarativos del ModuleRegistry."""
    registry = build_default_module_registry()
    try:
        definition = registry.get(module_id_or_alias)
    except ModuleRegistryError as exc:
        click.echo(f"ERROR de módulo ({type(exc).__name__}): {exc}", err=True)
        sys.exit(1)

    click.echo(f"=== Module Registry -- show {definition.module_id} ===")
    click.echo("")
    click.echo(f"module_id:        {definition.module_id}")
    click.echo(f"canonical_name:   {definition.canonical_name or '(ninguno)'}")
    click.echo(f"display_name:     {definition.display_name}")
    click.echo(f"version:          {definition.version}")
    click.echo(f"status:           {definition.status}")
    click.echo(f"aliases:          {', '.join(sorted(definition.aliases)) or '(ninguno)'}")
    click.echo(f"supported_modes:  {', '.join(sorted(definition.supported_modes)) or '(ninguno)'}")
    click.echo(f"capabilities:     {', '.join(sorted(definition.capabilities.values)) or '(ninguna)'}")
    click.echo(f"required_artifact_types: {', '.join(sorted(definition.required_artifact_types)) or '(ninguno)'}")
    click.echo(f"optional_artifact_types: {', '.join(sorted(definition.optional_artifact_types)) or '(ninguno)'}")
    if definition.description:
        click.echo(f"description:      {definition.description}")


if __name__ == "__main__":
    cli()
