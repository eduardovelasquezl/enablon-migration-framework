"""Tests de integración LOCAL (sin SQL Server real) del Framework Core v1
aplicado a Drills (Fase 11): usan un `DataFrame` fake vía monkeypatch de
`run_query` -- mismo patrón ya establecido en
`test_drills_export_prototype.py::test_modo_sample_respeta_el_limite` --
y comparan el resultado contra `pipeline.run()` llamado directamente
(regresión), y contra la ejecución de referencia real ya existente
(lectura pura, nunca se sobrescribe).

Ejecutar con: pytest tests/test_drills_core_pipeline.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

import src.export.prototype.drills.extractor as extractor_mod
from src.config import PROJECT_ROOT
from src.core.contracts import ExecutionRequest, ExecutionStatus, StageStatus
from src.core.orchestrator import PipelineOrchestrator
from src.core.registry import StageRegistry
from src.export.prototype.drills.core_adapters import (
    DEFAULT_PIPELINE_STAGES,
    build_drills_pipeline_definition,
    build_execution_context,
    register_drills_stages,
)
from src.export.prototype.drills.pipeline import OUTPUT_COLUMNS
from src.export.prototype.drills.pipeline import run as run_drills_pipeline


def _fake_dataframe() -> pd.DataFrame:
    """Filas deliberadamente construidas para resolver de forma conocida
    contra la configuración y los catálogos REALES del repositorio (no un
    fixture aparte): IDUnidadOrg=278 -> 'MCPF.HIS' ya está confirmado en
    `test_drills_export_prototype.py::test_mapping_de_entidad_resuelto` /
    `test_catalogo_real_del_repositorio_carga_sin_conflictos_conocidos`."""
    return pd.DataFrame({
        "IDSimulacro": [440, 441],
        "IDTipo": [365, 366],       # -> CS_Typology: PEI, GEN (reference_data.typology_lookup)
        "Fecha": ["08/03/2010", "09/03/2010"],
        "IDLetra": [258, 259],      # -> CS_Letter: A, B
        "IDUnidadOrg": [278, 278],  # -> CS_ImpactedEntities: MCPF.HIS (catálogo real)
        "Estado": ["Terminado", "En Curso"],  # -> Validated, Pending validation
    })


@pytest.fixture(autouse=True)
def _patch_run_query(monkeypatch):
    fake_df = _fake_dataframe()
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: fake_df.copy())
    yield


# --------------------------------------------------------------------------
# Pipeline definition / registro
# --------------------------------------------------------------------------

def test_pipeline_definition_por_defecto_coincide_con_config_yaml():
    """`config/exports/drills.yaml` ya declara `pipeline.stages` (Fase 4)
    -- confirma que se lee de ahí, no de la constante Python, cuando la
    sección existe."""
    definition = build_drills_pipeline_definition()
    assert definition.stages == DEFAULT_PIPELINE_STAGES


def test_las_cuatro_etapas_de_drills_quedan_registradas():
    registry = StageRegistry()
    register_drills_stages(registry)
    for stage_name in DEFAULT_PIPELINE_STAGES:
        assert registry.is_registered(stage_name)


# --------------------------------------------------------------------------
# Pipeline completo vía Core, sin SQL real
# --------------------------------------------------------------------------

def test_pipeline_completo_via_core_sin_sql_real(tmp_path):
    registry = StageRegistry()
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()

    request = ExecutionRequest(
        project="moeve", object_type="drills", module="simulacros",
        mode="sample", limit=10, output_dir=str(tmp_path),
    )
    context = build_execution_context(request)
    result = PipelineOrchestrator(registry).run(definition, context)

    assert result.status == ExecutionStatus.SUCCESS
    assert [r.stage for r in result.stage_results] == list(DEFAULT_PIPELINE_STAGES)
    # 'evidence' se omite (SKIPPED) porque generate_evidence=False por defecto.
    assert result.stage_results[-1].status == StageStatus.SKIPPED

    csv_path = context.output_dir / "drills.csv"
    assert csv_path.is_file()
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert header == OUTPUT_COLUMNS

    assert (context.output_dir / "validation_report.yaml").is_file()
    assert (context.output_dir / "export_manifest.yaml").is_file()
    assert (context.output_dir / "issues.jsonl").is_file()

    assert context.statistics.per_stage["transform_and_export"].output_record_count == 2
    assert str(context.output_dir).startswith(str(tmp_path))  # nunca bajo outputs/ real


def test_pipeline_completo_via_core_con_evidencia(tmp_path):
    request = ExecutionRequest(
        project="moeve", object_type="drills", mode="sample", limit=10,
        output_dir=str(tmp_path), generate_evidence=True, evidence_audience="both",
    )
    registry = StageRegistry()
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()
    context = build_execution_context(request)

    result = PipelineOrchestrator(registry).run(definition, context)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.stage_results[-1].stage == "evidence"
    assert result.stage_results[-1].status == StageStatus.SUCCESS
    assert (context.output_dir / "evidence_internal.xlsx").is_file()
    assert (context.output_dir / "evidence_client.xlsx").is_file()


# --------------------------------------------------------------------------
# Regresión: Core vs. pipeline.run() directo (mismo run_id/timestamp)
# --------------------------------------------------------------------------

def test_core_produce_el_mismo_csv_que_pipeline_run_directo(tmp_path):
    fixed_run_id = "regressiontest1"
    fixed_timestamp = "20260101T000000Z"

    legacy_root = tmp_path / "legacy"
    legacy_result = run_drills_pipeline(
        mode="sample", limit=10, output_root=legacy_root,
        run_id=fixed_run_id, timestamp=fixed_timestamp,
    )

    core_root = tmp_path / "core"
    request = ExecutionRequest(
        project="moeve", object_type="drills", mode="sample", limit=10,
        output_dir=str(core_root), execution_id=fixed_run_id,
    )
    registry = StageRegistry()
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()
    context = build_execution_context(request)
    context.output_dir = core_root / fixed_timestamp  # alinear con el camino legado para comparar 1:1

    pipeline_result = PipelineOrchestrator(registry).run(definition, context)
    assert pipeline_result.status == ExecutionStatus.SUCCESS

    core_csv_path = context.output_dir / "drills.csv"
    assert core_csv_path.read_bytes() == legacy_result.csv_path.read_bytes()

    legacy_report = yaml.safe_load(legacy_result.validation_report_path.read_text(encoding="utf-8"))
    core_report = yaml.safe_load((context.output_dir / "validation_report.yaml").read_text(encoding="utf-8"))
    # 'output.path' difiere porque legacy_root/core_root son distintos bajo
    # tmp_path -- es la única diferencia esperada, se excluye antes de comparar.
    legacy_report["output"].pop("path", None)
    core_report["output"].pop("path", None)
    assert legacy_report == core_report

    legacy_manifest = yaml.safe_load(legacy_result.manifest_path.read_text(encoding="utf-8"))
    core_manifest = yaml.safe_load((context.output_dir / "export_manifest.yaml").read_text(encoding="utf-8"))
    assert legacy_manifest == core_manifest  # incluye hashes -- deben coincidir exactamente


def test_core_no_ejecuta_la_query_dos_veces(tmp_path, monkeypatch):
    """La etapa 'query' extrae una vez; 'transform_and_export' debe
    REUTILIZAR esa extracción (parámetro `extraction=` de `pipeline.run()`,
    Fase 5) en vez de volver a consultar la fuente."""
    call_count = {"n": 0}
    fake_df = _fake_dataframe()

    def _counting_run_query(*args, **kwargs):
        call_count["n"] += 1
        return fake_df.copy()

    monkeypatch.setattr(extractor_mod, "run_query", _counting_run_query)

    request = ExecutionRequest(project="moeve", object_type="drills", mode="sample", limit=10, output_dir=str(tmp_path))
    registry = StageRegistry()
    register_drills_stages(registry)
    definition = build_drills_pipeline_definition()
    context = build_execution_context(request)
    PipelineOrchestrator(registry).run(definition, context)

    assert call_count["n"] == 1


# --------------------------------------------------------------------------
# Regresión contra la ejecución de referencia real (solo lectura)
# --------------------------------------------------------------------------

def test_columnas_de_referencia_no_han_cambiado():
    """Compara contra `outputs/prototype/drills/20260723T195418Z/` (la
    ejecución real ya existente, ver drills-operational-mvp.md § 0) --
    NUNCA se escribe en esa carpeta, solo se lee."""
    ref_dir = PROJECT_ROOT / "outputs" / "prototype" / "drills" / "20260723T195418Z"
    manifest_path = ref_dir / "export_manifest.yaml"
    validation_path = ref_dir / "validation_report.yaml"
    if not manifest_path.is_file() or not validation_path.is_file():
        pytest.skip("La ejecución de referencia no está disponible en este entorno.")

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    validation = yaml.safe_load(validation_path.read_text(encoding="utf-8"))

    assert manifest["output"]["columns"] == OUTPUT_COLUMNS
    assert validation["status"]["result"] == "SUCCESS"
    assert validation["output"]["columns"] == OUTPUT_COLUMNS


# --------------------------------------------------------------------------
# Etapa inexistente / CLI genérico
# --------------------------------------------------------------------------

def test_ejecutar_via_cli_generico_sin_sql_real(tmp_path):
    """Sprint 8.6.1: run_query está mockeado (fixture autouse de este
    fichero) -- ninguna conexión SQL real se abre -- pero el SQL
    Execution Guard de la CLI (src/cli.py) no distingue eso de una
    ejecución real, así que --allow-real-sql sigue siendo obligatorio
    para pasar la puerta de la CLI (el mock vive más abajo, en
    extractor.run_query, no en la CLI). Sin credenciales reales, sin
    riesgo -- solo autoriza el flujo de la CLI."""
    from src.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, [
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--limit", "10", "--output-dir", str(tmp_path), "--allow-real-sql",
    ])

    assert result.exit_code == 0, result.output
    assert "Resultado:          success" in result.output
    assert (tmp_path / next(p.name for p in tmp_path.iterdir()) / "drills.csv").is_file()


def test_cli_run_rechaza_objeto_no_soportado(tmp_path):
    """Sprint 8.6: la selección de módulo pasa por ModuleRegistry -- un
    object_type no registrado produce UnknownModuleError, no un
    condicional propio de la CLI (ver docs/01-architecture/module-registry.md)."""
    from src.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--project", "moeve", "--object", "eventos", "--output-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "UnknownModuleError" in result.output
    assert "eventos" in result.output
