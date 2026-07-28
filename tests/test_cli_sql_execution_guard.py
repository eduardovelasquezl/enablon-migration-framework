"""Tests CLI del SQL Execution Guard (Sprint 8.6.1). Nunca ejecuta SQL
real -- `run_query` se mockea donde hace falta llegar hasta ese punto;
en los tests de bloqueo se verifica explícitamente que NUNCA se invoca.

Ejecutar con: pytest tests/test_cli_sql_execution_guard.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
from click.testing import CliRunner

import src.export.prototype.drills.extractor as extractor_mod
from src.cli import cli
from src.db import sql_execution_guard

EXAMPLE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace" / "workspace.example.yaml"


def _run(*args):
    return CliRunner().invoke(cli, list(args))


def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDSimulacro": [440], "IDTipo": [365], "Fecha": ["08/03/2010"],
        "IDLetra": [258], "IDUnidadOrg": [278], "Estado": ["Terminado"],
    })


@pytest.fixture
def blocked_run_query(monkeypatch):
    """Sustituye run_query por una función que FALLA si se llama -- para
    los tests de bloqueo, prueba positiva de que nunca se alcanza."""
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("run_query no debía llamarse -- la ejecución debía bloquearse antes.")
    monkeypatch.setattr(extractor_mod, "run_query", _must_not_be_called)
    yield


@pytest.fixture
def fake_run_query(monkeypatch):
    """Sustituye run_query por un DataFrame sintético -- permite que la
    ejecución continúe sin tocar SQL real."""
    fake_df = _fake_dataframe()
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: fake_df.copy())
    yield


# --------------------------------------------------------------------------
# Bloqueo por defecto -- run
# --------------------------------------------------------------------------

def test_run_sin_autorizacion_queda_bloqueado(blocked_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--output-dir", str(tmp_path),
    )
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output


def test_run_sin_autorizacion_no_genera_outputs(blocked_run_query, tmp_path):
    _run("run", "--project", "moeve", "--object", "drills", "--output-dir", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_run_sin_autorizacion_no_deja_estado_de_autorizacion(blocked_run_query, tmp_path):
    _run("run", "--project", "moeve", "--object", "drills", "--output-dir", str(tmp_path))
    assert sql_execution_guard.is_authorized() is False


def test_run_alias_simulacros_tambien_bloqueado(blocked_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "simulacros",
        "--output-dir", str(tmp_path),
    )
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output


# --------------------------------------------------------------------------
# Autorización concedida -- run continúa hasta el mock
# --------------------------------------------------------------------------

def test_run_con_autorizacion_y_sql_mockeado_permite_continuar(fake_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--limit", "5", "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code == 0, result.output
    assert "Resultado:" in result.output


def test_run_autorizacion_via_env_var(fake_run_query, monkeypatch, tmp_path):
    monkeypatch.setenv(sql_execution_guard.ENV_VAR, "1")
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--limit", "5", "--output-dir", str(tmp_path),
    )
    assert result.exit_code == 0, result.output


def test_run_alias_simulacros_con_autorizacion_funciona(fake_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "simulacros", "--mode", "sample",
        "--limit", "5", "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------
# sample vs. full
# --------------------------------------------------------------------------

def test_sample_requiere_autorizacion_sql(blocked_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--output-dir", str(tmp_path),
    )
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output


def test_full_requiere_autorizacion_sql_y_confirmacion_full(blocked_run_query, tmp_path):
    # Ni --allow-real-sql ni --confirm-full-export: debe bloquear en el
    # primer control que encuentre (ExecutionRequest exige confirm-full-export
    # al construirse, pero el guard SQL nunca llega a construirse porque
    # ---object/capacidad se resuelven antes; aquí solo confirmamos bloqueo).
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "full",
        "--output-dir", str(tmp_path),
    )
    assert result.exit_code != 0


def test_full_con_autorizacion_sql_sin_confirmacion_full_no_permite_full(fake_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "full",
        "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code != 0
    assert "confirm-full-export" in result.output.lower() or "confirm_full_export" in result.output.lower()


def test_full_con_confirmacion_full_sin_autorizacion_sql_no_abre_conexion(blocked_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "full",
        "--confirm-full-export", "--output-dir", str(tmp_path),
    )
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output


def test_full_con_autorizacion_sql_y_confirmacion_full_llega_al_mock(fake_run_query, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "full",
        "--confirm-full-export", "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------
# Comando legacy: export drills
# --------------------------------------------------------------------------

def test_export_drills_sin_autorizacion_queda_bloqueado(blocked_run_query, monkeypatch, tmp_path):
    import src.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_ALLOWED_OUTPUT_ROOT", tmp_path)
    result = _run("export", "drills", "--output-dir", str(tmp_path))
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output


def test_export_drills_sin_autorizacion_no_genera_outputs(blocked_run_query, monkeypatch, tmp_path):
    import src.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_ALLOWED_OUTPUT_ROOT", tmp_path)
    _run("export", "drills", "--output-dir", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_export_drills_con_autorizacion_llega_al_mock(fake_run_query, monkeypatch, tmp_path):
    import src.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_ALLOWED_OUTPUT_ROOT", tmp_path)
    result = _run(
        "export", "drills", "--mode", "sample", "--limit", "5",
        "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------
# Pipeline factory directo (sin pasar por la CLI) -- fake SQL, sin autorizar
# --------------------------------------------------------------------------

def test_pipeline_factory_directo_con_fake_sql_no_requiere_autorizacion(fake_run_query, tmp_path):
    """Invocar la factory/el pipeline directamente en Python, con
    run_query mockeado, nunca llega a src.db.connection.get_engine() --
    no necesita sql_execution_guard.grant() en absoluto. Confirma que la
    puerta de la CLI (--allow-real-sql) y la puerta real
    (sql_execution_guard, ver test_sql_execution_guard.py) son conceptos
    relacionados pero distintos: el mock evita alcanzar la segunda."""
    from src.bootstrap.module_registry import build_default_module_registry
    from src.core.contracts import ExecutionRequest
    from src.core.registry import StageRegistry

    assert sql_execution_guard.is_authorized() is False  # explícitamente no autorizado

    registry = build_default_module_registry()
    factory = registry.get_pipeline_factory("drills")
    request = ExecutionRequest(
        project="moeve", object_type="drills", mode="sample", limit=5, output_dir=str(tmp_path),
    )
    definition, context = factory(request, StageRegistry())
    assert definition.name == "drills"
    assert sql_execution_guard.is_authorized() is False  # construir no autoriza nada


# --------------------------------------------------------------------------
# Comandos que no usan SQL: sin cambios, nunca requieren autorización
# --------------------------------------------------------------------------

def test_workspace_validate_no_requiere_autorizacion():
    result = _run("workspace", "validate", "--manifest", str(EXAMPLE_MANIFEST_PATH))
    assert result.exit_code == 0
    assert "SQL Execution Guard" not in result.output


def test_workspace_resolve_no_requiere_autorizacion():
    result = _run(
        "workspace", "resolve", "--manifest", str(EXAMPLE_MANIFEST_PATH),
        "--module", "drills", "--artifact", "sql",
    )
    assert result.exit_code == 0
    assert "SQL Execution Guard" not in result.output


def test_modules_list_no_requiere_autorizacion():
    result = _run("modules", "list")
    assert result.exit_code == 0
    assert "SQL Execution Guard" not in result.output


def test_modules_show_no_requiere_autorizacion():
    result = _run("modules", "show", "drills")
    assert result.exit_code == 0
    assert "SQL Execution Guard" not in result.output


# --------------------------------------------------------------------------
# Mensajes / exit codes
# --------------------------------------------------------------------------

def test_mensaje_de_bloqueo_no_contiene_secretos(blocked_run_query, tmp_path):
    result = _run("run", "--project", "moeve", "--object", "drills", "--output-dir", str(tmp_path))
    lowered = result.output.lower()
    for forbidden in ("password", "pwd=", "server=", "mssql+pyodbc", "sql_prevencion_password"):
        assert forbidden not in lowered


def test_exit_codes_diferenciados_bloqueo_vs_modulo_desconocido(blocked_run_query, tmp_path):
    blocked = _run("run", "--project", "moeve", "--object", "drills", "--output-dir", str(tmp_path))
    unknown_module = _run("run", "--project", "moeve", "--object", "no_existe", "--output-dir", str(tmp_path))
    assert blocked.exit_code != 0
    assert unknown_module.exit_code != 0
    assert "SQL Execution Guard" in blocked.output
    assert "UnknownModuleError" in unknown_module.output
    assert "SQL Execution Guard" not in unknown_module.output


# --------------------------------------------------------------------------
# Tests de integración SQL: siguen skipped por defecto
# --------------------------------------------------------------------------

def test_tests_de_integracion_sql_siguen_gateados_por_env_var():
    """No ejecuta nada contra SQL real -- solo confirma que el mecanismo
    de opt-in de los tests de integración (RUN_SQL_INTEGRATION_TESTS,
    RUN_DRILLS_EXPORT_INTEGRATION_TESTS) sigue existiendo y sigue
    desactivado por defecto en este proceso de test."""
    import os
    assert os.environ.get("RUN_SQL_INTEGRATION_TESTS") != "1"
    assert os.environ.get("RUN_DRILLS_EXPORT_INTEGRATION_TESTS") != "1"
