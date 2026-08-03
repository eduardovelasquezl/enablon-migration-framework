"""Tests del comando CLI `workspace readiness` (Sprint 8.7). Nunca accede a
SQL Server, nunca requiere --allow-real-sql -- solo invoca el comando sobre
el ejemplo versionado `examples/workspace/workspace.example.yaml` o
manifests temporales, mismo patrón que `tests/test_cli_workspace_resolve.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from click.testing import CliRunner

from src.cli import cli

EXAMPLE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace" / "workspace.example.yaml"

_DRILLS_MANIFEST_TEMPLATE = """
project:
  id: moeve
  display_name: Moeve
  status: active
  version: "1.0"
workspace:
  schema_version: "1.0"
  project_root: projects/moeve
modules:
  drills:
    display_name: Drills
    enabled: {enabled}
    status: in_progress
    artifacts:
      sql:
        path: null
        status: present
        required_for_sample: true
        required_for_full: true
        source: "git:x.sql"
      mapping:
        path: null
        status: present
        required_for_sample: true
        required_for_full: true
        source: "repo:x.csv"
      operational_csv:
        path: {operational_path}
        status: {operational_status}
        required_for_comparison: true
        contract_role: project
    contracts:
      project:
        artifact: operational_csv
"""


def _run(*args):
    runner = CliRunner()
    return runner.invoke(cli, ["workspace", "readiness", *args])


def _write_manifest(tmp_path, *, enabled="true", operational_path="null", operational_status="missing") -> Path:
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text(
        _DRILLS_MANIFEST_TEMPLATE.format(
            enabled=enabled, operational_path=operational_path, operational_status=operational_status,
        ),
        encoding="utf-8",
    )
    return manifest_path


# ---------------------------------------------------------------------------
# Exit codes por estado
# ---------------------------------------------------------------------------

def test_sample_ready_with_warnings_exit_code_1(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run("--manifest", str(manifest_path), "--module", "drills", "--operation", "sample")
    assert result.exit_code == 1
    assert "Status:" in result.output
    assert "ready_with_warnings" in result.output


def test_comparison_bloqueado_exit_code_2(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run("--manifest", str(manifest_path), "--module", "drills", "--operation", "comparison")
    assert result.exit_code == 2
    assert "blocked" in result.output


def test_modulo_desconocido_exit_code_2(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run("--manifest", str(manifest_path), "--module", "moc", "--operation", "sample")
    assert result.exit_code == 2
    assert "MODULE_UNKNOWN" in result.output


def test_manifest_inexistente_exit_code_3(tmp_path):
    result = _run(
        "--manifest", str(tmp_path / "no_existe.yaml"), "--module", "drills", "--operation", "sample",
    )
    assert result.exit_code == 3


def test_operacion_desconocida_es_rechazada_por_click():
    result = _run(
        "--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--operation", "no_es_una_operacion",
    )
    assert result.exit_code != 0
    assert result.exit_code not in (0, 1)  # click.Choice rechaza antes de construir la petición


# ---------------------------------------------------------------------------
# --format json
# ---------------------------------------------------------------------------

def test_format_json_produce_json_valido(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run(
        "--manifest", str(manifest_path), "--module", "drills", "--operation", "sample", "--format", "json",
    )
    payload = json.loads(result.output)
    assert payload["module_id"] == "drills"
    assert payload["operation"] == "sample"
    assert payload["status"] == "ready_with_warnings"
    assert "issues" in payload and isinstance(payload["issues"], list)
    # Nunca credenciales ni connection strings en la salida.
    assert "password" not in result.output.lower()
    assert "pwd=" not in result.output.lower()


# ---------------------------------------------------------------------------
# --require-files
# ---------------------------------------------------------------------------

def test_require_files_bloquea_si_operational_csv_declarado_sin_archivo_fisico(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(
        tmp_path, operational_path='"Drills.csv"', operational_status="present",
    )
    result = _run(
        "--manifest", str(manifest_path), "--module", "drills", "--operation", "comparison", "--require-files",
    )
    assert result.exit_code == 2
    assert "PHYSICAL_FILE_MISSING" in result.output


def test_require_files_no_bloquea_si_el_archivo_existe(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    real_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon_Operational"
    real_dir.mkdir(parents=True)
    (real_dir / "Drills.csv").write_text("x", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, operational_path='"Drills.csv"', operational_status="present",
    )
    result = _run(
        "--manifest", str(manifest_path), "--module", "drills", "--operation", "comparison", "--require-files",
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --strict
# ---------------------------------------------------------------------------

def test_strict_convierte_warnings_en_exit_code_bloqueado(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run(
        "--manifest", str(manifest_path), "--module", "drills", "--operation", "sample", "--strict",
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Nunca requiere/toca SQL real
# ---------------------------------------------------------------------------

def test_readiness_nunca_menciona_allow_real_sql_como_requisito_de_la_propia_evaluacion(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = _write_manifest(tmp_path)
    result = _run("--manifest", str(manifest_path), "--module", "drills", "--operation", "sample")
    assert "--allow-real-sql" not in result.output or "requerirá" in result.output.lower()


# ---------------------------------------------------------------------------
# No rompe el resto de la CLI (comandos ya existentes)
# ---------------------------------------------------------------------------

def test_workspace_validate_sigue_funcionando():
    runner = CliRunner()
    result = runner.invoke(cli, ["workspace", "validate", "--manifest", str(EXAMPLE_MANIFEST_PATH)])
    assert result.exit_code == 0


def test_workspace_resolve_sigue_funcionando():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["workspace", "resolve", "--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--artifact", "sql"],
    )
    assert result.exit_code == 0


def test_modules_list_sigue_funcionando():
    runner = CliRunner()
    result = runner.invoke(cli, ["modules", "list"])
    assert result.exit_code == 0


def test_modules_show_sigue_funcionando():
    runner = CliRunner()
    result = runner.invoke(cli, ["modules", "show", "drills"])
    assert result.exit_code == 0
