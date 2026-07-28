"""Tests del comando CLI `workspace resolve` (Sprint 8.5). Nunca accede a
SQL Server, nunca abre el recurso resuelto -- solo invoca el comando sobre
el ejemplo versionado `examples/workspace/workspace.example.yaml` o
manifests temporales.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from click.testing import CliRunner

from src.cli import cli

EXAMPLE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace" / "workspace.example.yaml"


def _run(*args):
    runner = CliRunner()
    return runner.invoke(cli, ["workspace", "resolve", *args])


def test_resolucion_valida_exit_code_0():
    result = _run("--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--artifact", "sql")
    assert result.exit_code == 0
    assert "manifest_ref:" in result.output
    assert "status:" in result.output


def test_recurso_ausente_sin_require_exists_exit_code_0():
    """Sin --require-exists, un artefacto declarado pero sin path (status
    missing) es una ausencia explícita, no un error -- exit 0."""
    result = _run("--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--artifact", "operational_csv")
    assert result.exit_code == 0
    assert "no declarado" in result.output


def test_modulo_desconocido_exit_code_distinto_de_cero():
    result = _run("--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "no_existe", "--artifact", "sql")
    assert result.exit_code != 0
    assert "UnknownModuleError" in result.output


def test_artefacto_desconocido_exit_code_distinto_de_cero():
    result = _run("--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--artifact", "no_es_un_kind")
    assert result.exit_code != 0
    assert "UnknownArtifactError" in result.output


def test_require_exists_sobre_recurso_sin_path_declarado_exit_code_distinto_de_cero():
    result = _run(
        "--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills",
        "--artifact", "operational_csv", "--require-exists",
    )
    assert result.exit_code != 0


def test_require_exists_sobre_recurso_fisico_presente_exit_code_0(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text(
        """
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
    enabled: true
    status: ready
    artifacts:
      sql:
        path: Drills.sql
        status: present
""",
        encoding="utf-8",
    )
    real_dir = tmp_path / "projects" / "moeve" / "SQL"
    real_dir.mkdir(parents=True)
    (real_dir / "Drills.sql").write_text("SELECT 1", encoding="utf-8")

    result = _run("--manifest", str(manifest_path), "--module", "drills", "--artifact", "sql", "--require-exists")
    assert result.exit_code == 0
    assert "exists:          True" in result.output


def test_artefacto_deprecated_sin_allow_deprecated_exit_code_distinto_de_cero(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text(
        """
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
    enabled: true
    status: ready
    artifacts:
      mapping:
        path: legacy.csv
        status: deprecated
""",
        encoding="utf-8",
    )
    result = _run("--manifest", str(manifest_path), "--module", "drills", "--artifact", "mapping")
    assert result.exit_code != 0
    assert "DeprecatedArtifactError" in result.output

    result_allowed = _run(
        "--manifest", str(manifest_path), "--module", "drills",
        "--artifact", "mapping", "--allow-deprecated",
    )
    assert result_allowed.exit_code == 0


def test_manifest_inexistente_exit_code_distinto_de_cero():
    result = _run("--manifest", "no/existe/workspace.yaml", "--module", "drills", "--artifact", "sql")
    assert result.exit_code != 0


def test_salida_no_revela_secretos():
    """La salida no debe incluir credenciales, cadenas de conexión ni
    contenido de archivo -- solo metadatos declarativos de resolución."""
    result = _run("--manifest", str(EXAMPLE_MANIFEST_PATH), "--module", "drills", "--artifact", "sql")
    lowered = result.output.lower()
    for forbidden in ("password", "pwd=", "connectionstring", "secret"):
        assert forbidden not in lowered


def test_no_rompe_workspace_validate():
    runner = CliRunner()
    result = runner.invoke(cli, ["workspace", "validate", "--manifest", str(EXAMPLE_MANIFEST_PATH)])
    assert result.exit_code == 0
    assert "OK" in result.output
