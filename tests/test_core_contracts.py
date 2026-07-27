"""Tests unitarios de los contratos mínimos del Framework Core v1
(Fase 1). Sin red, sin SQL Server, sin dependencias de Drills.

Ejecutar con: pytest tests/test_core_contracts.py -v
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.contracts import (
    ArtifactReference,
    CanonicalBatch,
    ExecutionRequest,
    ExecutionStatistics,
    ExecutionStatus,
    PipelineDefinition,
    PipelineResult,
    StageMetrics,
    StageResult,
    StageStatus,
)
from src.core.exceptions import PipelineConfigurationError


# --------------------------------------------------------------------------
# ExecutionRequest
# --------------------------------------------------------------------------

def test_execution_request_valida_con_defaults():
    req = ExecutionRequest(project="moeve", object_type="drills")
    assert req.mode == "sample"
    assert req.limit == 100
    assert req.confirm_full_export is False
    assert req.filters == ()


def test_execution_request_no_contiene_dataframes_ni_credenciales():
    """No es una prueba de tipo en tiempo de ejecución -- documenta que la
    forma del contrato (campos declarados) no tiene ningún hueco para
    conexiones/DataFrames/credenciales, tal como exige el encargo."""
    fields = ExecutionRequest.__dataclass_fields__.keys()
    forbidden_substrings = ("connection", "dataframe", "password", "credential", "df")
    for f in fields:
        assert not any(bad in f.lower() for bad in forbidden_substrings), f


def test_execution_request_rechaza_project_vacio():
    with pytest.raises(PipelineConfigurationError):
        ExecutionRequest(project="", object_type="drills")


def test_execution_request_rechaza_modo_desconocido():
    with pytest.raises(PipelineConfigurationError):
        ExecutionRequest(project="moeve", object_type="drills", mode="turbo")


def test_execution_request_full_exige_confirmacion_explicita():
    with pytest.raises(PipelineConfigurationError):
        ExecutionRequest(project="moeve", object_type="drills", mode="full")

    # Con confirmación explícita, no lanza.
    req = ExecutionRequest(project="moeve", object_type="drills", mode="full", confirm_full_export=True)
    assert req.mode == "full"


def test_execution_request_sample_rechaza_limite_no_positivo():
    with pytest.raises(PipelineConfigurationError):
        ExecutionRequest(project="moeve", object_type="drills", mode="sample", limit=0)


def test_execution_request_es_inmutable():
    req = ExecutionRequest(project="moeve", object_type="drills")
    with pytest.raises(Exception):
        req.project = "otro"  # frozen dataclass -> FrozenInstanceError


# --------------------------------------------------------------------------
# CanonicalBatch -- seam provisional del CDM (Fase 6)
# --------------------------------------------------------------------------

def test_canonical_batch_no_es_el_cdm_completo():
    """No expone CanonicalField/Provenance -- es deliberadamente mínimo,
    ver docstring de CanonicalBatch."""
    batch = CanonicalBatch(
        object_type="drills", source_system="prevencion", rows=[{"a": 1}],
        row_count=1, extracted_at=datetime.now(timezone.utc),
    )
    assert batch.row_count == 1
    assert not hasattr(batch, "fields")
    assert not hasattr(batch, "provenance")


# --------------------------------------------------------------------------
# StageResult / StageStatus
# --------------------------------------------------------------------------

def test_stage_result_status_valido():
    result = StageResult(stage="query", status=StageStatus.SUCCESS)
    assert result.is_blocking is False


def test_stage_result_failure_es_blocking():
    result = StageResult(stage="query", status=StageStatus.FAILURE)
    assert result.is_blocking is True


def test_stage_result_rechaza_status_desconocido():
    with pytest.raises(PipelineConfigurationError):
        StageResult(stage="query", status="not_a_real_status")


# --------------------------------------------------------------------------
# PipelineDefinition
# --------------------------------------------------------------------------

def test_pipeline_definition_rechaza_lista_vacia_de_etapas():
    with pytest.raises(PipelineConfigurationError):
        PipelineDefinition(name="drills", stages=())


def test_pipeline_definition_conserva_orden():
    definition = PipelineDefinition(name="drills", stages=("query", "canonicalize", "evidence"))
    assert definition.stages == ("query", "canonicalize", "evidence")


# --------------------------------------------------------------------------
# PipelineResult
# --------------------------------------------------------------------------

def test_pipeline_result_rechaza_status_desconocido():
    now = datetime.now(timezone.utc)
    with pytest.raises(PipelineConfigurationError):
        PipelineResult(
            execution_id="abc", status="not_a_real_status", stage_results=(),
            statistics=ExecutionStatistics(), artifacts=(), issues=(),
            started_at=now, ended_at=now, duration_seconds=0.0, output_dir=Path("."),
        )


def test_pipeline_result_acepta_status_valido():
    now = datetime.now(timezone.utc)
    result = PipelineResult(
        execution_id="abc", status=ExecutionStatus.SUCCESS, stage_results=(),
        statistics=ExecutionStatistics(), artifacts=(), issues=(),
        started_at=now, ended_at=now, duration_seconds=1.5, output_dir=Path("."),
    )
    assert result.status == "success"


# --------------------------------------------------------------------------
# ExecutionStatistics / StageMetrics -- métricas nulas explícitas (Fase 9)
# --------------------------------------------------------------------------

def test_stage_metrics_metrica_no_aplicable_queda_none_no_cero():
    metrics = StageMetrics(stage="evidence", start_time=datetime.now(timezone.utc))
    assert metrics.excluded_record_count is None
    assert metrics.input_record_count is None


def test_execution_statistics_agrega_warnings_y_errores_por_etapa():
    stats = ExecutionStatistics()
    stats.per_stage["query"] = StageMetrics(
        stage="query", start_time=datetime.now(timezone.utc), warning_count=2, error_count=0,
    )
    stats.per_stage["export"] = StageMetrics(
        stage="export", start_time=datetime.now(timezone.utc), warning_count=1, error_count=1,
    )
    assert stats.total_warning_count == 3
    assert stats.total_error_count == 1


def test_artifact_reference_es_inmutable():
    artifact = ArtifactReference(name="drills.csv", path=Path("drills.csv"), kind="csv", stage="export")
    with pytest.raises(Exception):
        artifact.name = "otro.csv"
