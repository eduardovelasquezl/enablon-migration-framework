"""Framework Core v1 -- Execution Pipeline genérico del EMF.

Este paquete no conoce ningún proyecto, módulo, objeto migrable ni fuente
concreta (cero imports de `src.export`, `src.etl`, `src.evidence` con
lógica de negocio). Ver `docs/01-architecture/framework-core-v1.md` para
el diseño completo y `docs/02-adr/ADR-016-framework-core-execution-pipeline.md`
para las decisiones estructurales.

Uso típico (desde una capa de proyecto/plugin, nunca desde aquí dentro):

    from src.core.contracts import ExecutionRequest, PipelineDefinition
    from src.core.registry import StageRegistry
    from src.core.orchestrator import PipelineOrchestrator
"""
from src.core.contracts import (
    ArtifactReference,
    CanonicalBatch,
    ExecutionContext,
    ExecutionRequest,
    ExecutionStatistics,
    ExecutionStatus,
    PipelineDefinition,
    PipelineResult,
    StageMetrics,
    StageResult,
    StageStatus,
)
from src.core.exceptions import CoreError, PipelineConfigurationError, StageNotRegisteredError
from src.core.orchestrator import PipelineOrchestrator
from src.core.registry import StageRegistry

__all__ = [
    "ArtifactReference",
    "CanonicalBatch",
    "ExecutionContext",
    "ExecutionRequest",
    "ExecutionStatistics",
    "ExecutionStatus",
    "PipelineDefinition",
    "PipelineOrchestrator",
    "PipelineResult",
    "StageMetrics",
    "StageRegistry",
    "StageResult",
    "StageStatus",
    "CoreError",
    "PipelineConfigurationError",
    "StageNotRegisteredError",
]
