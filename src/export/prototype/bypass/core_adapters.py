"""Adaptadores de Bypass para el Framework Core v1 (Sprint 9.4).

Solo dos etapas (`query`, `transform_and_export`) -- ni `canonicalize`
(pass-through puro en Drills, sin valor demostrado todavía) ni
`evidence` (no implementada para Bypass, ver
docs/07-developer-guide/bypass-module.md § 3) se declaran aquí. Vive en
la capa de Plugin (`src/export/prototype/bypass/`), nunca en
`src/core/` -- mismo principio de dirección de dependencia que Drills.

La etapa `query` ya NO es DUPLICATED_FROM_DRILLS desde Sprint 9.6: usa
`GenericQueryStage` (Export Engine, `src/export/engine/query_stage.py`),
el mismo bloque reutilizable que Drills -- ver
`reports/executions/2026-08-14/Informe-Minimal-Export-Engine-Extraction-EMF.md`.
`transform_and_export` sigue envolviendo `pipeline.run()` completo, deuda
técnica conocida y deliberadamente NO extraída todavía (Sprint 9.5.1: sin
una segunda forma real distinta a Drills, extraerla ahora sería diseñar sin
evidencia)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import PROJECT_ROOT
from src.core.contracts import (
    ArtifactReference,
    ExecutionContext,
    ExecutionRequest,
    PipelineDefinition,
    StageMetrics,
    StageResult,
    StageStatus,
)
from src.core.registry import StageRegistry
from src.export.engine.query_stage import GenericQueryStage, QueryStageSpec
from src.query.catalog import BYPASS_FILTER_CATALOG

from .config import load_bypass_config
from .extractor import ExtractionResult, extract_bypass
from .pipeline import PipelineResult as BypassRunResult
from .pipeline import run as run_bypass_pipeline

STAGE_QUERY = "query"
STAGE_TRANSFORM_AND_EXPORT = "transform_and_export"

DEFAULT_PIPELINE_STAGES = (STAGE_QUERY, STAGE_TRANSFORM_AND_EXPORT)

OBJECT_TYPE = "bypass"
SOURCE_SYSTEM = "prevencion"

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "prototype" / "bypass"

_LEGACY_FUNCTIONAL_ERRORS = (FileNotFoundError, ValueError, RuntimeError, FileExistsError)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_bypass_query_stage() -> GenericQueryStage:
    """Envuelve `extract_bypass()` sin ningún cambio de comportamiento --
    Sprint 9.6: mismo `GenericQueryStage` (Export Engine) que Drills, solo
    cambian los componentes que Bypass aporta (`QueryStageSpec`)."""
    return GenericQueryStage(QueryStageSpec(
        name=STAGE_QUERY,
        config_loader=load_bypass_config,
        state_key="bypass_config",
        filter_catalog=BYPASS_FILTER_CATALOG,
        extract_fn=extract_bypass,
    ))


class BypassTransformExportStage:
    """Envuelve `pipeline.run()` completo -- mismo rol que
    `DrillsTransformExportStage`, ADAPTADOR TEMPORAL sobre el mismo tipo
    de deuda ya documentada para Drills (framework-core-v1.md § 15)."""

    name = STAGE_TRANSFORM_AND_EXPORT

    def execute(self, context: ExecutionContext, stage_input: ExtractionResult) -> StageResult:
        start = _now()
        request = context.request
        timestamp = context.output_dir.name
        output_root = context.output_dir.parent

        try:
            result = run_bypass_pipeline(
                mode=request.mode, limit=request.limit, output_root=output_root,
                extraction=stage_input, run_id=context.execution_id, timestamp=timestamp,
            )
        except _LEGACY_FUNCTIONAL_ERRORS as exc:
            return StageResult(
                stage=self.name, status=StageStatus.FAILURE,
                issues=[{"stage": self.name, "severity": "blocking", "message": str(exc)}],
                message=str(exc),
            )

        stage_status = StageStatus.FAILURE if result.stats.errors else (
            StageStatus.WARNING if result.stats.warnings else StageStatus.SUCCESS
        )

        artifacts = [
            ArtifactReference(name="bypass.csv", path=result.csv_path, kind="csv", stage=self.name),
            ArtifactReference(name="validation_report.yaml", path=result.validation_report_path, kind="yaml", stage=self.name),
            ArtifactReference(name="export_manifest.yaml", path=result.manifest_path, kind="yaml", stage=self.name),
        ]

        metrics = StageMetrics(
            stage=self.name, start_time=start,
            input_record_count=result.stats.rows_read, output_record_count=result.stats.rows_exported,
            excluded_record_count=result.stats.rows_excluded,
            warning_count=len(result.stats.warnings), error_count=len(result.stats.errors),
            artifacts_generated=len(artifacts),
        )
        return StageResult(
            stage=self.name, status=stage_status, output=result, metrics=metrics, artifacts=artifacts,
        )


def register_bypass_stages(registry: StageRegistry, *, overwrite: bool = False) -> None:
    registry.register(STAGE_QUERY, _build_bypass_query_stage(), overwrite=overwrite)
    registry.register(STAGE_TRANSFORM_AND_EXPORT, BypassTransformExportStage(), overwrite=overwrite)


def build_bypass_pipeline_definition() -> PipelineDefinition:
    config = load_bypass_config()
    pipeline_cfg = config.raw.get("pipeline") or {}
    raw_stages = pipeline_cfg.get("stages") if pipeline_cfg else None
    stages = tuple(raw_stages) if raw_stages else DEFAULT_PIPELINE_STAGES
    return PipelineDefinition(name="bypass", stages=stages)


def build_execution_context(
    request: ExecutionRequest, *, logger: logging.Logger | None = None,
) -> ExecutionContext:
    execution_id = request.execution_id or uuid.uuid4().hex[:12]
    started_at = _now()
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    output_root = Path(request.output_dir) if request.output_dir else DEFAULT_OUTPUT_ROOT
    output_dir = output_root / timestamp

    return ExecutionContext(
        execution_id=execution_id, request=request, started_at=started_at,
        working_dir=PROJECT_ROOT, output_dir=output_dir,
        logger=logger or logging.getLogger("src.export.prototype.bypass.core_adapters"),
    )
