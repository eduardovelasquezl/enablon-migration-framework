"""Tests unitarios (sin red) de la integración del Query Engine v0.1 con el
pipeline de exportación de Drills: `pipeline.run(..., compiled_filters=...)`
escribe `generated_query.sql` y registra `query_filters` en el manifiesto,
sin tocar SQL Server real ni `sql/source_queries/`.

Ejecutar con: pytest tests/test_drills_export_query_engine.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
from click.testing import CliRunner

import src.export.prototype.drills.extractor as extractor_mod
from src.cli import cli
from src.export.prototype.drills.extractor import MODE_SAMPLE
from src.export.prototype.drills.pipeline import run as run_pipeline
from src.query.catalog import DRILLS_FILTER_CATALOG
from src.query.validator import compile_filter_tokens

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRILLS_SQL_PATH = (
    PROJECT_ROOT / "sql" / "source_queries" / "Simulacros" / "SQLQuery - DATASET SIMULACRO.sql"
)

_FAKE_ROWS = pd.DataFrame(
    {
        "IDTipo": [365, 366],
        "IDSimulacro": [1001, 1002],
        "Fecha": ["01/06/2020 10:00:00", "02/06/2020 11:00:00"],
        "IDLetra": [None, None],
        "IDUnidadOrg": [None, None],
        "Estado": [None, None],
    }
)


@pytest.fixture
def fake_run_query(monkeypatch):
    """Sustituye `run_query` dentro de `extractor.py` -- captura la SQL y
    los parámetros con los que se llamó, sin tocar SQL Server real."""
    calls = []

    def _fake(sql, connection=None, params=None, source_file=None, **kwargs):
        calls.append({"sql": sql, "connection": connection, "params": params, "source_file": source_file})
        return _FAKE_ROWS.copy()

    monkeypatch.setattr(extractor_mod, "run_query", _fake)
    return calls


# --------------------------------------------------------------------------
# Sin --filter: comportamiento IDÉNTICO al de antes de este incremento
# --------------------------------------------------------------------------

def test_export_sin_filtros_no_pasa_where_ni_params(fake_run_query, tmp_path):
    result = run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path)

    assert len(fake_run_query) == 1
    assert "WHERE" not in fake_run_query[0]["sql"]
    assert fake_run_query[0]["params"] is None

    assert result.manifest["query_filters"] == {
        "applied": False,
        "count": 0,
        "expressions": [],
        "generated_sql_file": None,
        "generated_sql_sha256": None,
        "source_sql_sha256": result.manifest["hashes"]["sql_sha256"],
    }
    assert result.manifest["source"]["source_sql_modified"] is False
    assert result.manifest["source"]["runtime_sql_composed"] is False
    assert not (result.output_dir / "generated_query.sql").exists()


# --------------------------------------------------------------------------
# Con --filter: WHERE parametrizado, generated_query.sql, manifest
# --------------------------------------------------------------------------

def test_export_con_filtros_ejecuta_where_parametrizado(fake_run_query, tmp_path):
    compiled = compile_filter_tokens(["historical_origin_id:eq:1001"], DRILLS_FILTER_CATALOG)
    run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path, compiled_filters=compiled)

    assert len(fake_run_query) == 1
    call = fake_run_query[0]
    assert "WHERE [ITP_SIMULACRO].[IDSimulacro] = :filter_1" in call["sql"]
    assert call["params"] == {"filter_1": 1001}
    assert "1001" not in call["sql"]  # el valor nunca va concatenado en el texto SQL


def test_export_con_filtros_escribe_generated_query_sql(fake_run_query, tmp_path):
    # Valor deliberadamente largo y poco probable de colisionar por azar con
    # un fragmento del hash/timestamp de la cabecera del fichero generado.
    compiled = compile_filter_tokens(["center_id:eq:87654321"], DRILLS_FILTER_CATALOG)
    result = run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path, compiled_filters=compiled)

    generated_path = result.output_dir / "generated_query.sql"
    assert generated_path.is_file()
    text = generated_path.read_text(encoding="utf-8")
    assert ":filter_1" in text
    assert "87654321" not in text
    assert "Query Engine v0.1" in text


def test_export_con_filtros_manifest_registra_query_filters(fake_run_query, tmp_path):
    compiled = compile_filter_tokens(
        ["center_id:eq:25", "typology_id:in:1,2"], DRILLS_FILTER_CATALOG
    )
    result = run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path, compiled_filters=compiled)

    qf = result.manifest["query_filters"]
    assert qf["applied"] is True
    assert qf["count"] == 2
    assert qf["expressions"] == [
        {"field": "center_id", "operator": "eq", "value": 25},
        {"field": "typology_id", "operator": "in", "value": [1, 2]},
    ]
    assert qf["generated_sql_file"] == "generated_query.sql"
    assert qf["generated_sql_sha256"] is not None
    assert qf["source_sql_sha256"] == result.manifest["hashes"]["sql_sha256"]
    assert result.manifest["source"]["runtime_sql_composed"] is True
    assert result.manifest["source"]["source_sql_modified"] is False


def test_export_con_filtros_manifest_no_incluye_credenciales_ni_sql_completo(fake_run_query, tmp_path):
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    result = run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path, compiled_filters=compiled)

    import yaml
    manifest_text = (result.manifest_path).read_text(encoding="utf-8")
    reparsed = yaml.safe_load(manifest_text)
    forbidden_keys = {"password", "pwd", "secret", "connection_string"}

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _walk(item)

    assert not (set(_walk(reparsed)) & forbidden_keys)
    assert "SELECT" not in manifest_text  # no se vuelca la SQL completa dentro del YAML


def test_export_con_filtros_no_modifica_la_sql_fuente(fake_run_query, tmp_path):
    before = DRILLS_SQL_PATH.read_bytes()
    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    run_pipeline(mode=MODE_SAMPLE, limit=10, output_root=tmp_path, compiled_filters=compiled)
    after = DRILLS_SQL_PATH.read_bytes()
    assert before == after


# --------------------------------------------------------------------------
# CLI: un filtro inválido se rechaza ANTES de tocar SQL Server
# --------------------------------------------------------------------------

def test_cli_filtro_invalido_nunca_llega_al_query_runner(monkeypatch, tmp_path):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("run_query no debía llamarse -- el filtro inválido debía rechazarse antes.")

    monkeypatch.setattr(extractor_mod, "run_query", _must_not_be_called)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export", "drills",
            "--output-dir", str(Path("outputs") / "prototype" / "drills"),
            "--filter", "campo_que_no_existe:eq:1",
        ],
    )
    assert result.exit_code == 1
    assert "ERROR de filtro" in result.output


def test_cli_operador_no_permitido_nunca_llega_al_query_runner(monkeypatch):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("run_query no debía llamarse -- el operador no permitido debía rechazarse antes.")

    monkeypatch.setattr(extractor_mod, "run_query", _must_not_be_called)

    runner = CliRunner()
    result = runner.invoke(cli, ["export", "drills", "--filter", "center_id:contains:25"])
    assert result.exit_code == 1
    assert "ERROR de filtro" in result.output


def test_cli_filtro_valido_se_incluye_en_el_resumen(fake_run_query, monkeypatch, tmp_path):
    import src.cli as cli_mod

    # Redirige la raíz de salida permitida a un directorio temporal -- una
    # ejecución de CLI real (aunque con SQL mockeado) no debe escribir
    # nunca bajo el outputs/ real del repositorio durante los tests.
    monkeypatch.setattr(cli_mod, "_ALLOWED_OUTPUT_ROOT", tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export", "drills", "--mode", "sample", "--limit", "10",
            "--filter", "center_id:eq:25",
            "--output-dir", str(tmp_path),
            "--allow-real-sql",  # Sprint 8.6.1: run_query está mockeado (fake_run_query),
            # pero el SQL Execution Guard de la CLI sigue exigiendo la bandera --
            # el mock vive en extractor.run_query, no en la CLI. Ver
            # docs/01-architecture/sql-execution-guard.md.
        ],
    )
    assert result.exit_code == 0, result.output
    assert "center_id:eq:25" in result.output
    assert "generated_query.sql" in result.output
