"""Tests unitarios del PipelineOrchestrator (Fase 2), con etapas FAKE --
sin SQL Server, sin Drills, sin ningún módulo funcional real.

Ejecutar con: pytest tests/test_core_orchestrator.py -v
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.contracts import (
    ArtifactReference,
    ExecutionContext,
    ExecutionRequest,
    ExecutionStatus,
    PipelineDefinition,
    StageMetrics,
    StageResult,
    StageStatus,
)
from src.core.exceptions import StageNotRegisteredError
from src.core.orchestrator import PipelineOrchestrator
from src.core.registry import StageRegistry


def _context() -> ExecutionContext:
    request = ExecutionRequest(project="test-project", object_type="fake-object")
    now = datetime.now(timezone.utc)
    return ExecutionContext(
        execution_id="fixed-exec-id",
        request=request,
        started_at=now,
        working_dir=Path("."),
        output_dir=Path("./_test_output"),
        logger=logging.getLogger("test.core.orchestrator"),
    )


class _RecordingStage:
    """Etapa fake que registra su propia invocación en una lista
    compartida -- usada para comprobar orden de ejecución."""

    def __init__(self, name: str, calls: list[str], status: str = StageStatus.SUCCESS):
        self.name = name
        self._calls = calls
        self._status = status

    def execute(self, context: ExecutionContext, stage_input):
        self._calls.append(self.name)
        return StageResult(stage=self.name, status=self._status, output=self.name)


class _MetricsStage:
    def __init__(self, name: str, status: str = StageStatus.SUCCESS):
        self.name = name
        self._status = status

    def execute(self, context: ExecutionContext, stage_input):
        metrics = StageMetrics(
            stage=self.name, start_time=datetime.now(timezone.utc),
            output_record_count=42,
        )
        artifact = ArtifactReference(
            name=f"{self.name}.txt", path=Path(f"{self.name}.txt"), kind="txt", stage=self.name,
        )
        return StageResult(
            stage=self.name, status=self._status, output=self.name,
            metrics=metrics, artifacts=[artifact],
        )


class _ExplodingStage:
    """Etapa fake que lanza una excepción técnica no controlada --
    confirma que el orquestador NO la intercepta (Fase 8)."""

    name = "exploding"

    def execute(self, context: ExecutionContext, stage_input):
        raise RuntimeError("fallo técnico simulado, no debe ocultarse")


# --------------------------------------------------------------------------
# Orden de ejecución
# --------------------------------------------------------------------------

def test_las_etapas_se_ejecutan_en_el_orden_declarado():
    calls: list[str] = []
    registry = StageRegistry()
    registry.register("a", _RecordingStage("a", calls))
    registry.register("b", _RecordingStage("b", calls))
    registry.register("c", _RecordingStage("c", calls))

    definition = PipelineDefinition(name="test", stages=("c", "a", "b"))
    orchestrator = PipelineOrchestrator(registry)
    orchestrator.run(definition, _context())

    assert calls == ["c", "a", "b"]


def test_la_salida_de_una_etapa_se_transfiere_a_la_siguiente():
    received_inputs: list = []

    class _EchoStage:
        def __init__(self, name, output):
            self.name = name
            self._output = output

        def execute(self, context, stage_input):
            received_inputs.append(stage_input)
            return StageResult(stage=self.name, status=StageStatus.SUCCESS, output=self._output)

    registry = StageRegistry()
    registry.register("first", _EchoStage("first", "output-of-first"))
    registry.register("second", _EchoStage("second", "output-of-second"))

    definition = PipelineDefinition(name="test", stages=("first", "second"))
    PipelineOrchestrator(registry).run(definition, _context())

    assert received_inputs == [None, "output-of-first"]


# --------------------------------------------------------------------------
# Parada ante fallo bloqueante / continuación ante warning / skip
# --------------------------------------------------------------------------

def test_fallo_bloqueante_detiene_el_pipeline():
    calls: list[str] = []
    registry = StageRegistry()
    registry.register("a", _RecordingStage("a", calls))
    registry.register("b", _RecordingStage("b", calls, status=StageStatus.FAILURE))
    registry.register("c", _RecordingStage("c", calls))

    definition = PipelineDefinition(name="test", stages=("a", "b", "c"))
    result = PipelineOrchestrator(registry).run(definition, _context())

    assert calls == ["a", "b"]  # 'c' nunca se ejecuta
    assert len(result.stage_results) == 2
    assert result.status == ExecutionStatus.FAILED


def test_warning_no_detiene_el_pipeline():
    calls: list[str] = []
    registry = StageRegistry()
    registry.register("a", _RecordingStage("a", calls, status=StageStatus.WARNING))
    registry.register("b", _RecordingStage("b", calls))

    definition = PipelineDefinition(name="test", stages=("a", "b"))
    result = PipelineOrchestrator(registry).run(definition, _context())

    assert calls == ["a", "b"]
    assert result.status == ExecutionStatus.SUCCESS_WITH_WARNINGS


def test_etapa_skipped_no_detiene_el_pipeline_y_no_cuenta_como_warning():
    calls: list[str] = []
    registry = StageRegistry()
    registry.register("a", _RecordingStage("a", calls, status=StageStatus.SKIPPED))
    registry.register("b", _RecordingStage("b", calls))

    definition = PipelineDefinition(name="test", stages=("a", "b"))
    result = PipelineOrchestrator(registry).run(definition, _context())

    assert calls == ["a", "b"]
    assert result.status == ExecutionStatus.SUCCESS


def test_todas_las_etapas_exitosas_da_status_success():
    registry = StageRegistry()
    calls: list[str] = []
    registry.register("a", _RecordingStage("a", calls))
    definition = PipelineDefinition(name="test", stages=("a",))
    result = PipelineOrchestrator(registry).run(definition, _context())
    assert result.status == ExecutionStatus.SUCCESS


# --------------------------------------------------------------------------
# Acumulación de métricas y artefactos
# --------------------------------------------------------------------------

def test_metricas_se_acumulan_por_etapa_en_el_contexto():
    registry = StageRegistry()
    registry.register("a", _MetricsStage("a"))
    registry.register("b", _MetricsStage("b"))
    definition = PipelineDefinition(name="test", stages=("a", "b"))
    context = _context()

    PipelineOrchestrator(registry).run(definition, context)

    assert set(context.statistics.per_stage.keys()) == {"a", "b"}
    assert context.statistics.per_stage["a"].output_record_count == 42


def test_artefactos_se_acumulan_en_el_resultado_final():
    registry = StageRegistry()
    registry.register("a", _MetricsStage("a"))
    registry.register("b", _MetricsStage("b"))
    definition = PipelineDefinition(name="test", stages=("a", "b"))

    result = PipelineOrchestrator(registry).run(definition, _context())

    assert len(result.artifacts) == 2
    assert {a.stage for a in result.artifacts} == {"a", "b"}


def test_issues_se_acumulan_en_el_resultado_final():
    class _IssueStage:
        name = "with-issues"

        def execute(self, context, stage_input):
            return StageResult(
                stage=self.name, status=StageStatus.WARNING,
                issues=[{"code": "SOME_ISSUE", "message": "algo pasó"}],
            )

    registry = StageRegistry()
    registry.register("with-issues", _IssueStage())
    definition = PipelineDefinition(name="test", stages=("with-issues",))

    result = PipelineOrchestrator(registry).run(definition, _context())

    assert len(result.issues) == 1
    assert result.issues[0]["code"] == "SOME_ISSUE"


# --------------------------------------------------------------------------
# Registro de etapas / etapa inexistente
# --------------------------------------------------------------------------

def test_etapa_inexistente_en_la_definicion_lanza_error_explicito():
    registry = StageRegistry()
    registry.register("a", _RecordingStage("a", []))
    definition = PipelineDefinition(name="test", stages=("a", "no_existe"))

    with pytest.raises(StageNotRegisteredError):
        PipelineOrchestrator(registry).run(definition, _context())


# --------------------------------------------------------------------------
# Excepciones técnicas no controladas -- Fase 8
# --------------------------------------------------------------------------

def test_excepcion_tecnica_no_controlada_se_propaga_sin_ocultarse():
    registry = StageRegistry()
    registry.register("exploding", _ExplodingStage())
    definition = PipelineDefinition(name="test", stages=("exploding",))

    with pytest.raises(RuntimeError, match="fallo técnico simulado"):
        PipelineOrchestrator(registry).run(definition, _context())


# --------------------------------------------------------------------------
# ExecutionContext -- construcción y distinción mutable/inmutable
# --------------------------------------------------------------------------

def test_execution_context_arranca_con_colecciones_mutables_vacias():
    context = _context()
    assert context.artifacts == []
    assert context.issues == []
    assert context.statistics.per_stage == {}
    assert context.state == {}


def test_execution_context_conserva_la_request_sin_mutarla():
    context = _context()
    assert context.request.project == "test-project"
    with pytest.raises(Exception):
        context.request.project = "otro"  # ExecutionRequest es frozen
