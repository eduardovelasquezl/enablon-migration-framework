"""Tests de integración de bypass.By_Passes (Sprint 9.4) -- SIN SQL real,
SIN datos de cliente. Cubre el checklist de la Fase 9 del sprint:
ModuleRegistry, PipelineFactory, SQL Guard fail-closed, filtros,
transformación, validación, output contract, readiness, sin regresión
en Drills (esta última la confirma la suite completa, no este archivo).

Ejecutar con: pytest tests/test_bypass_pipeline.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

import src.export.prototype.bypass.extractor as extractor_mod
import src.export.prototype.bypass.pipeline as pipeline_mod
from src.bootstrap.module_registry import build_default_module_registry
from src.cli import cli
from src.core.module_registry import ModuleCapability
from src.db import sql_execution_guard
from src.query.catalog import BYPASS_FILTER_CATALOG
from src.query.validator import compile_filter_tokens


def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDBES": [2878, 2881, 2942],
        "IDCentro": [2, 2, 2],
        "IDUnidadOrg": [105, 105, 105],
        "IDTipoBypass": [1, 2, 3],
        "IDCausa": [2, 3, 1],
        "IDTipoSCE": [7, 6, 2],
        "IDMetodoBypass": [2, 3, 1],
        "Motivo": ["Mantenimiento programado", None, "Prueba funcional"],
        "FechaCreacion": ["2020-01-03", "2020-01-01", "2020-01-02"],
    })


# --------------------------------------------------------------------------
# 1. ModuleRegistry reconoce Bypass -- 2. PipelineFactory puede construirlo
# --------------------------------------------------------------------------

def test_module_registry_reconoce_bypass():
    registry = build_default_module_registry()
    assert registry.contains("bypass")
    definition = registry.get("bypass")
    assert definition.module_id == "bypass"
    assert registry.supports("bypass", ModuleCapability.SAMPLE)
    assert registry.supports("bypass", ModuleCapability.FULL)


def test_pipeline_factory_de_bypass_construye_definicion_y_contexto():
    from src.core.contracts import ExecutionRequest
    from src.core.registry import StageRegistry

    registry = build_default_module_registry()
    factory = registry.get_pipeline_factory("bypass")
    request = ExecutionRequest(project="moeve", object_type="bypass", mode="sample", limit=5)
    definition, context = factory(request, StageRegistry())
    assert definition.name == "bypass"
    assert definition.stages == ("query", "transform_and_export")
    assert context.execution_id


# --------------------------------------------------------------------------
# 3. SQL Guard sigue fail-closed para Bypass
# --------------------------------------------------------------------------

def test_run_bypass_sin_autorizacion_queda_bloqueado(tmp_path):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("run_query no debía llamarse -- la ejecución debía bloquearse antes.")

    import src.db.query_runner as qr_mod
    result = CliRunner().invoke(cli, [
        "run", "--project", "moeve", "--object", "bypass", "--mode", "sample",
        "--output-dir", str(tmp_path),
    ])
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output
    assert sql_execution_guard.is_authorized() is False


def test_run_bypass_con_autorizacion_y_sql_mockeado_permite_continuar(monkeypatch, tmp_path):
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: _fake_dataframe())
    result = CliRunner().invoke(cli, [
        "run", "--project", "moeve", "--object", "bypass", "--mode", "sample",
        "--limit", "3", "--output-dir", str(tmp_path), "--allow-real-sql",
    ])
    assert result.exit_code == 0, result.output
    assert "Resultado:" in result.output


# --------------------------------------------------------------------------
# 4. Filtros se compilan correctamente (Query Engine reutilizado)
# --------------------------------------------------------------------------

def test_filtro_historical_origin_id_compila():
    compiled = compile_filter_tokens(("historical_origin_id:eq:2878",), BYPASS_FILTER_CATALOG)
    assert compiled[0].sql_fragment == "[ITP_BES].[IDBES] = :filter_1"
    assert compiled[0].parameters == {"filter_1": 2878}


def test_filtro_historical_origin_id_in_list_compila():
    """Candidato de filtro para el primer sample real (Fase 12/checkpoint):
    los IDs decodificados de la anomalía de fecha del Operational real."""
    ids = "2878,2881,2942,2943,2966"
    compiled = compile_filter_tokens((f"historical_origin_id:in:{ids}",), BYPASS_FILTER_CATALOG)
    assert "IN" in compiled[0].sql_fragment.upper()


def test_filtro_campo_desconocido_rechazado():
    from src.query.models import UnknownFilterFieldError
    with pytest.raises(UnknownFilterFieldError):
        compile_filter_tokens(("campo_inventado:eq:1",), BYPASS_FILTER_CATALOG)


# --------------------------------------------------------------------------
# 5-7. Transformación produce columnas esperadas, validación y output
# contract funcionan (pipeline completo, sin SQL)
# --------------------------------------------------------------------------

def test_pipeline_completo_produce_columnas_esperadas(tmp_path):
    from src.export.prototype.bypass.extractor import ExtractionResult

    extraction = ExtractionResult(
        dataframe=_fake_dataframe(), mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_pipeline", timestamp="20260101T000000Z",
    )
    assert result.csv_path.is_file()
    header = result.csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header.split("\t") == pipeline_mod.OUTPUT_COLUMNS

    report = yaml.safe_load(result.validation_report_path.read_text(encoding="utf-8"))
    assert report["counts"]["rows_exported"] == 3
    assert report["counts"]["errors"] == 0
    assert report["status"]["result"] == "SUCCESS"

    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["module"] == "bypass"
    assert manifest["approved_for_enablon_import"] is False


def test_pipeline_fila_sin_idbes_se_excluye(tmp_path):
    from src.export.prototype.bypass.extractor import ExtractionResult

    df = _fake_dataframe()
    df.loc[0, "IDBES"] = None
    extraction = ExtractionResult(
        dataframe=df, mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_excl", timestamp="20260101T000001Z",
    )
    assert result.stats.rows_exported == 2
    assert result.stats.rows_excluded == 1
    assert result.stats.missing_historical_origin_id == 1


# --------------------------------------------------------------------------
# 9. Readiness funciona (offline, workspace de ejemplo sintético -- sin
# depender del workspace.yaml real de Moeve)
# --------------------------------------------------------------------------

def test_readiness_bypass_con_manifest_sintetico_sample_sin_blockers(tmp_path):
    """9. Readiness funciona -- manifest sintético (proyecto ficticio,
    sin depender del workspace.yaml real de Moeve), vía la misma CLI
    offline ya usada en todo este proyecto."""
    manifest_yaml = tmp_path / "workspace.yaml"
    manifest_yaml.write_text(
        "project:\n  id: acme\n  display_name: Acme\n  status: active\n  version: '1.0'\n"
        "workspace:\n  schema_version: '1.0'\n  project_root: projects/acme\n"
        "modules:\n  bypass:\n    display_name: Bypass\n    enabled: true\n"
        "    status: in_progress\n    canonical_name: By_Passes\n    artifacts:\n"
        "      sql:\n        path: null\n        status: present\n        required_for_sample: true\n"
        "      mapping:\n        path: null\n        status: present\n        required_for_sample: true\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, [
        "workspace", "readiness", "--manifest", str(manifest_yaml),
        "--module", "bypass", "--operation", "sample", "--format", "json",
    ])
    assert result.exit_code in (0, 1)  # 0=READY, 1=READY_WITH_WARNINGS -- nunca BLOCKED(2)
    assert '"status": "ready"' in result.output
    assert "0 blocker(s)" in result.output
    assert "MODULE_UNKNOWN" not in result.output
    assert "MODULE_DISABLED" not in result.output
