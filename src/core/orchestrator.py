"""Orquestador genérico del Framework Core (Fase 2).

Responsabilidades permitidas (y únicamente estas): resolver la definición
del pipeline contra el `StageRegistry`, ejecutar etapas en orden,
registrar inicio/fin, transferir la salida de una etapa a la siguiente,
detenerse ante un `StageResult.status == FAILURE`, acumular métricas/
issues/artefactos en el `ExecutionContext`, y devolver un `PipelineResult`.

Prohibido explícitamente, y verificable por inspección de este fichero:
no importa `src.export`, `src.etl` ni ningún módulo con lógica de negocio
de un objeto concreto; no conoce nombres de columnas, tablas, reglas de
mapeo ni contenido de Enablon. Si algún día este fichero necesita un
`import` de esa naturaleza, es una señal de que se ha violado la capa
Core -> Engine (ver `architecture-overview.md` § 1).
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.core.contracts import (
    ExecutionContext,
    ExecutionStatus,
    PipelineDefinition,
    PipelineResult,
    StageResult,
    StageStatus,
)
from src.core.registry import StageRegistry


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _determine_execution_status(stage_results: tuple[StageResult, ...]) -> str:
    if any(r.status == StageStatus.FAILURE for r in stage_results):
        return ExecutionStatus.FAILED
    if any(r.status == StageStatus.WARNING for r in stage_results):
        return ExecutionStatus.SUCCESS_WITH_WARNINGS
    return ExecutionStatus.SUCCESS


class PipelineOrchestrator:
    """Ejecuta una `PipelineDefinition` sobre un `ExecutionContext` dado,
    resolviendo cada nombre de etapa contra el `StageRegistry` recibido en
    el constructor."""

    def __init__(self, registry: StageRegistry) -> None:
        self._registry = registry

    def run(self, definition: PipelineDefinition, context: ExecutionContext) -> PipelineResult:
        stage_results: list[StageResult] = []
        stage_input = None

        context.logger.info(
            "Iniciando pipeline '%s' (execution_id=%s, etapas=%s)",
            definition.name, context.execution_id, definition.stages,
        )

        for stage_name in definition.stages:
            stage = self._registry.resolve(stage_name)  # StageNotRegisteredError se propaga tal cual

            start = _now()
            # Ninguna excepción técnica se intercepta aquí a propósito (Fase 8):
            # un fallo de programación o de infraestructura dentro de
            # `stage.execute` debe detener la ejecución de forma visible, no
            # convertirse en un StageResult silencioso. Cada adaptador de
            # etapa es responsable de capturar y traducir SOLO los errores
            # funcionales/legados que conoce (ver core_adapters.py).
            result = stage.execute(context, stage_input)
            end = _now()

            if result.duration_seconds is None:
                result.duration_seconds = (end - start).total_seconds()
            if result.metrics is not None and result.metrics.end_time is None:
                result.metrics.end_time = end
                result.metrics.duration_seconds = result.metrics.duration_seconds or result.duration_seconds

            context.artifacts.extend(result.artifacts)
            context.issues.extend(result.issues)
            if result.metrics is not None:
                context.statistics.per_stage[stage_name] = result.metrics

            stage_results.append(result)

            context.logger.info(
                "Etapa '%s' completada: status=%s, duration=%.3fs, issues=%d, artifacts=%d",
                stage_name, result.status, result.duration_seconds or 0.0,
                len(result.issues), len(result.artifacts),
            )

            if result.status == StageStatus.FAILURE:
                context.logger.error(
                    "Etapa '%s' devolvió FAILURE -- deteniendo el pipeline (etapas no ejecutadas: %s).",
                    stage_name, definition.stages[definition.stages.index(stage_name) + 1:],
                )
                break

            stage_input = result.output

        ended_at = _now()
        status = _determine_execution_status(tuple(stage_results))

        context.logger.info(
            "Pipeline '%s' finalizado (execution_id=%s, status=%s, duración=%.3fs)",
            definition.name, context.execution_id, status, (ended_at - context.started_at).total_seconds(),
        )

        return PipelineResult(
            execution_id=context.execution_id,
            status=status,
            stage_results=tuple(stage_results),
            statistics=context.statistics,
            artifacts=tuple(context.artifacts),
            issues=tuple(context.issues),
            started_at=context.started_at,
            ended_at=ended_at,
            duration_seconds=(ended_at - context.started_at).total_seconds(),
            output_dir=context.output_dir,
        )
