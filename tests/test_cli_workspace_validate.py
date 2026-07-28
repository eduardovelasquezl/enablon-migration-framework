"""Tests del comando CLI `workspace validate` (Sprint 8.4). Nunca accede a
SQL Server, nunca ejecuta el pipeline -- solo invoca el comando sobre
ficheros YAML de prueba (`tmp_path`) o el ejemplo versionado
`examples/workspace/workspace.example.yaml`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from click.testing import CliRunner

from src.cli import cli

EXAMPLE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace" / "workspace.example.yaml"


def test_workspace_validate_ejemplo_moeve_exit_code_0():
    runner = CliRunner()
    result = runner.invoke(cli, ["workspace", "validate", "--manifest", str(EXAMPLE_MANIFEST_PATH)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_workspace_validate_manifest_inexistente_exit_code_distinto_de_cero():
    runner = CliRunner()
    result = runner.invoke(cli, ["workspace", "validate", "--manifest", "no/existe/workspace.yaml"])
    assert result.exit_code != 0


def test_workspace_validate_manifest_con_violacion_exit_code_distinto_de_cero(tmp_path):
    bad_manifest = tmp_path / "workspace.yaml"
    bad_manifest.write_text(
        """
project:
  id: moeve
  display_name: Moeve
  status: active
  version: "1.0"
workspace:
  schema_version: "1.0"
  project_root: projects/moeve
  naming_convention:
    operational_csv: "{module}.csv"
modules:
  drills:
    display_name: Drills
    enabled: true
    status: ready
    canonical_name: Drills
    artifacts:
      operational_csv:
        path: nombre_incorrecto.csv
""",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["workspace", "validate", "--manifest", str(bad_manifest)])
    assert result.exit_code != 0
    assert "Violaciones" in result.output or "Violaciones" in (result.exception and str(result.exception) or "")


def test_workspace_validate_no_rompe_comandos_existentes():
    """El comando 'export drills --help' debe seguir funcionando
    exactamente igual tras añadir el grupo 'workspace' -- verificación de
    no regresión de la CLI existente."""
    runner = CliRunner()
    result = runner.invoke(cli, ["export", "drills", "--help"])
    assert result.exit_code == 0
    assert "drills.csv" in result.output

    result_run = runner.invoke(cli, ["run", "--help"])
    assert result_run.exit_code == 0
