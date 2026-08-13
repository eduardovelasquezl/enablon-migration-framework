"""Adaptadores de Drills para el Framework Core v1 (Fase 5).

Vive en la capa de Plugin/objeto migrable (`src/export/prototype/drills/`),
NUNCA dentro de `src/core/` -- el Core no debe conocer Drills; es este
módulo el que conoce ambos lados (Core y Drills) y los conecta. Ver
`docs/01-architecture/framework-core-v1.md` § 11/§ 17.

Cuatro etapas registradas, deliberadamente no ocho (Fase 5 permite elegir
"el mínimo corte útil" cuando separar más implica alto riesgo):

- `query`: extracción SQL -- ya estaba limpiamente separada en
  `extractor.py`; se envuelve sin ningún cambio de comportamiento.
- `canonicalize`: seam mínimo hacia el futuro CDM (`CanonicalBatch`,
  Fase 6 Opción C) -- hoy es un paso de paso (pass-through) documentado,
  no reescribe ninguna transformación de Drills.
- `transform_and_export`: ADAPTADOR TEMPORAL que envuelve, sin modificar
  su lógica interna, la función `pipeline.run()` ya existente -- cubre a
  la vez Mapping + Validation + Export + Manifest + Comparison + Issues,
  porque separarlas hoy exigiría reescribir `pipeline.py` (alto riesgo,
  explícitamente desaconsejado por el encargo). Ver "Deuda técnica" en
  `framework-core-v1.md`.
- `evidence`: ya estaba limpiamente separada hoy (la CLI ya la invoca
  aparte de la exportación); se envuelve sin cambios.

No existe una etapa `report` registrada aquí -- no hay artefacto de
"reporte" distinto del Excel de evidencia (ver
`drills-operational-mvp.md` § 9); se añadirá cuando exista un consumidor
real.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT
from src.core.contracts import (
    ArtifactReference,
    CanonicalBatch,
    ExecutionContext,
    ExecutionRequest,
    PipelineDefinition,
    StageMetrics,
    StageResult,
    StageStatus,
)
from src.core.registry import StageRegistry
from src.core.workspace_manifest import WorkspaceManifestLoader
from src.evidence.collector import load_run
from src.evidence.models import EvidenceSourceError
from src.evidence.workbook import build_workbook, save_workbook
from src.query.catalog import DRILLS_FILTER_CATALOG
from src.query.validator import compile_filter_tokens

from .config import load_drills_config
from .extractor import ExtractionResult, extract_drills
from .pipeline import PipelineResult as DrillsRunResult
from .pipeline import run as run_drills_pipeline

STAGE_QUERY = "query"
STAGE_CANONICALIZE = "canonicalize"
STAGE_TRANSFORM_AND_EXPORT = "transform_and_export"
STAGE_EVIDENCE = "evidence"

DEFAULT_PIPELINE_STAGES = (STAGE_QUERY, STAGE_CANONICALIZE, STAGE_TRANSFORM_AND_EXPORT, STAGE_EVIDENCE)

OBJECT_TYPE = "drills"
SOURCE_SYSTEM = "prevencion"

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "prototype" / "drills"

# Excepciones ya conocidas y documentadas que `pipeline.run()` lanza para
# comunicar un fallo funcional/de escritura (mismo conjunto que ya captura
# `src/cli.py::export_drills` hoy) -- se traducen a StageResult(FAILURE).
# Cualquier otra excepción (DatabaseError, QueryEngineError, un error de
# programación no previsto) se propaga sin capturar (Fase 8).
_LEGACY_FUNCTIONAL_ERRORS = (FileNotFoundError, ValueError, RuntimeError, FileExistsError)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DrillsQueryStage:
    """Envuelve `extract_drills()` sin ningún cambio de comportamiento."""

    name = STAGE_QUERY

    def execute(self, context: ExecutionContext, stage_input: Any) -> StageResult:
        start = _now()
        request = context.request

        config = load_drills_config()
        context.state["drills_config"] = config

        compiled_filters = ()
        if request.filters:
            compiled_filters = compile_filter_tokens(request.filters, DRILLS_FILTER_CATALOG)

        # Errores técnicos (DatabaseError, QueryEngineError) se propagan tal
        # cual -- no se capturan aquí (Fase 8).
        extraction = extract_drills(
            config, mode=request.mode, limit=request.limit, compiled_filters=compiled_filters,
        )

        metrics = StageMetrics(
            stage=self.name,
            start_time=start,
            input_record_count=extraction.rows_available_before_truncation,
            output_record_count=len(extraction.dataframe),
        )
        return StageResult(stage=self.name, status=StageStatus.SUCCESS, output=extraction, metrics=metrics)


class DrillsCanonicalizeStage:
    """Seam mínimo hacia el futuro CDM (Fase 6, Opción C): envuelve el
    `DataFrame` ya extraído en un `CanonicalBatch` PROVISIONAL (guardado en
    `context.state` para trazabilidad) y deja pasar la `ExtractionResult`
    original sin tocarla -- la etapa siguiente todavía necesita sus campos
    completos (`sql_text`, `sql_sha256`, `compiled_filters`...), que
    `CanonicalBatch` no reproduce por diseño (ver `contracts.py`)."""

    name = STAGE_CANONICALIZE

    def execute(self, context: ExecutionContext, stage_input: ExtractionResult) -> StageResult:
        start = _now()
        batch = CanonicalBatch(
            object_type=OBJECT_TYPE,
            source_system=SOURCE_SYSTEM,
            rows=stage_input.dataframe,
            row_count=len(stage_input.dataframe),
            extracted_at=start,
        )
        context.state["canonical_batch"] = batch
        metrics = StageMetrics(
            stage=self.name, start_time=start,
            input_record_count=batch.row_count, output_record_count=batch.row_count,
        )
        return StageResult(stage=self.name, status=StageStatus.SUCCESS, output=stage_input, metrics=metrics)


class DrillsTransformExportStage:
    """ADAPTADOR TEMPORAL (deuda técnica documentada, § 15 de
    framework-core-v1.md): envuelve `pipeline.run()` completo sin modificar
    su lógica interna."""

    name = STAGE_TRANSFORM_AND_EXPORT

    def execute(self, context: ExecutionContext, stage_input: ExtractionResult) -> StageResult:
        start = _now()
        request = context.request
        timestamp = context.output_dir.name
        output_root = context.output_dir.parent

        try:
            result = run_drills_pipeline(
                mode=request.mode,
                limit=request.limit,
                output_root=output_root,
                extraction=stage_input,
                run_id=context.execution_id,
                timestamp=timestamp,
                workspace_manifest=context.state.get("workspace_manifest"),
            )
        except _LEGACY_FUNCTIONAL_ERRORS as exc:
            return StageResult(
                stage=self.name, status=StageStatus.FAILURE,
                issues=[{"stage": self.name, "severity": "blocking", "message": str(exc)}],
                message=str(exc),
            )

        status_result = result.validation_report["status"]["result"]
        if status_result in ("FAILED_VALIDATION", "FAILED_EXECUTION"):
            stage_status = StageStatus.FAILURE
        elif result.stats.warnings or result.stats.errors:
            stage_status = StageStatus.WARNING
        else:
            stage_status = StageStatus.SUCCESS

        artifacts = [
            ArtifactReference(name="drills.csv", path=result.csv_path, kind="csv", stage=self.name),
            ArtifactReference(name="validation_report.yaml", path=result.validation_report_path, kind="yaml", stage=self.name),
            ArtifactReference(name="export_manifest.yaml", path=result.manifest_path, kind="yaml", stage=self.name),
            ArtifactReference(name="issues.jsonl", path=result.issues_path, kind="jsonl", stage=self.name),
        ]
        if result.comparison_report_path is not None:
            artifacts.append(
                ArtifactReference(
                    name="comparison_report.yaml", path=result.comparison_report_path,
                    kind="yaml", stage=self.name, required=False,
                )
            )

        metrics = StageMetrics(
            stage=self.name, start_time=start,
            input_record_count=result.stats.rows_read,
            output_record_count=result.stats.rows_exported,
            excluded_record_count=result.stats.rows_excluded,
            warning_count=len(result.stats.warnings),
            error_count=len(result.stats.errors),
            artifacts_generated=len(artifacts),
        )
        return StageResult(
            stage=self.name, status=stage_status, output=result,
            issues=list(result.issues), metrics=metrics, artifacts=artifacts,
        )


class DrillsEvidenceStage:
    """Genera `evidence_internal.xlsx`/`evidence_client.xlsx` a partir de
    los artefactos YA escritos por la etapa anterior -- nunca vuelve a
    consultar SQL Server (Evidence First). `SKIPPED` si el
    `ExecutionRequest` no pidió evidencia -- no es un fallo, es una
    decisión explícita de la petición."""

    name = STAGE_EVIDENCE

    def execute(self, context: ExecutionContext, stage_input: DrillsRunResult) -> StageResult:
        start = _now()
        request = context.request
        if not request.generate_evidence:
            return StageResult(
                stage=self.name, status=StageStatus.SKIPPED, output=stage_input,
                metrics=StageMetrics(stage=self.name, start_time=start),
                message="generate_evidence=False -- etapa omitida por petición explícita.",
            )

        audiences = ("internal", "client") if request.evidence_audience == "both" else (request.evidence_audience,)
        try:
            ctx = load_run(stage_input.output_dir)
        except EvidenceSourceError as exc:
            return StageResult(
                stage=self.name, status=StageStatus.FAILURE,
                issues=[{"stage": self.name, "severity": "blocking", "message": str(exc)}],
                message=str(exc),
            )

        artifacts = []
        for audience in audiences:
            wb = build_workbook(ctx, audience)
            path = save_workbook(wb, stage_input.output_dir / f"evidence_{audience}.xlsx")
            artifacts.append(ArtifactReference(name=path.name, path=path, kind="xlsx", stage=self.name))

        metrics = StageMetrics(stage=self.name, start_time=start, artifacts_generated=len(artifacts))
        return StageResult(
            stage=self.name, status=StageStatus.SUCCESS, output=stage_input,
            metrics=metrics, artifacts=artifacts,
        )


def register_drills_stages(registry: StageRegistry, *, overwrite: bool = False) -> None:
    """Único punto donde el Core "aprende" a ejecutar Drills -- ninguna
    clase de `src/core/` importa nada de este módulo; es este módulo quien
    importa del Core y se registra en él (dirección de dependencia
    correcta, ver `architecture-overview.md` § 1)."""
    registry.register(STAGE_QUERY, DrillsQueryStage(), overwrite=overwrite)
    registry.register(STAGE_CANONICALIZE, DrillsCanonicalizeStage(), overwrite=overwrite)
    registry.register(STAGE_TRANSFORM_AND_EXPORT, DrillsTransformExportStage(), overwrite=overwrite)
    registry.register(STAGE_EVIDENCE, DrillsEvidenceStage(), overwrite=overwrite)


def build_drills_pipeline_definition() -> PipelineDefinition:
    """Lee `config/exports/drills.yaml` -> `pipeline.stages` (Fase 4); si
    la sección no existe (compatibilidad con configuraciones anteriores a
    este incremento), usa `DEFAULT_PIPELINE_STAGES`."""
    config = load_drills_config()
    pipeline_cfg = config.raw.get("pipeline") or {}
    raw_stages = pipeline_cfg.get("stages") if pipeline_cfg else None
    stages = tuple(raw_stages) if raw_stages else DEFAULT_PIPELINE_STAGES
    return PipelineDefinition(name="drills", stages=stages)


def build_execution_context(
    request: ExecutionRequest, *, logger: logging.Logger | None = None,
) -> ExecutionContext:
    """Construye el `ExecutionContext` para una petición de Drills.

    El directorio de salida por defecto (`outputs/prototype/drills/`) es
    deliberadamente el MISMO que ya usa `pipeline.run()` hoy -- preservar
    la estructura de outputs existente es un requisito explícito de
    compatibilidad de esta fase, no una elección libre de este adaptador.

    Sprint 9.2: si `request.workspace_manifest_path` está declarado, este
    es el único punto donde se hace I/O para cargarlo (`ExecutionRequest`
    solo transporta la ruta, nunca el manifest ya cargado -- ver su
    docstring). El objeto `WorkspaceManifest` resultante se deja en
    `context.state["workspace_manifest"]` -- el cauce genérico ya
    documentado para que una etapa posterior lo recoja sin que el Core
    tenga que conocer qué es un `WorkspaceManifest`. Un fallo al cargar
    (fichero inexistente, YAML inválido) se propaga tal cual -- quien pasó
    `--manifest` pidió explícitamente ese fichero; no hay fallback
    silencioso a "sin manifest".
    """
    execution_id = request.execution_id or uuid.uuid4().hex[:12]
    started_at = _now()
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    output_root = Path(request.output_dir) if request.output_dir else DEFAULT_OUTPUT_ROOT
    output_dir = output_root / timestamp

    state: dict[str, Any] = {}
    if request.workspace_manifest_path:
        state["workspace_manifest"] = WorkspaceManifestLoader.load_from_path(
            Path(request.workspace_manifest_path)
        )

    return ExecutionContext(
        execution_id=execution_id,
        request=request,
        started_at=started_at,
        working_dir=PROJECT_ROOT,
        output_dir=output_dir,
        logger=logger or logging.getLogger("src.export.prototype.drills.core_adapters"),
        state=state,
    )
