"""Tests del CLI de inspección `modules list` / `modules show` (Sprint
8.6). Solo lectura -- nunca accede a SQL Server, nunca ejecuta un
pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from click.testing import CliRunner

from src.cli import cli


def _run(*args):
    return CliRunner().invoke(cli, list(args))


def test_modules_list_exit_code_0_e_incluye_drills():
    result = _run("modules", "list")
    assert result.exit_code == 0
    assert "drills" in result.output
    assert "experimental" in result.output


def test_modules_list_no_muestra_rutas_ni_credenciales():
    result = _run("modules", "list")
    lowered = result.output.lower()
    for forbidden in ("password", "pwd=", "c:\\users", "connectionstring", "secret"):
        assert forbidden not in lowered


def test_modules_list_salida_deterministica():
    first = _run("modules", "list").output
    second = _run("modules", "list").output
    assert first == second


def test_modules_show_drills_exit_code_0():
    result = _run("modules", "show", "drills")
    assert result.exit_code == 0
    assert "module_id:        drills" in result.output
    assert "capabilities:" in result.output
    assert "comparison" in result.output


def test_modules_show_por_alias_simulacros():
    result = _run("modules", "show", "simulacros")
    assert result.exit_code == 0
    assert "module_id:        drills" in result.output


def test_modules_show_modulo_desconocido_exit_code_distinto_de_cero():
    result = _run("modules", "show", "no_existe")
    assert result.exit_code != 0
    assert "UnknownModuleError" in result.output


def test_modules_show_no_muestra_rutas_fisicas():
    result = _run("modules", "show", "drills")
    lowered = result.output.lower()
    assert "c:\\users" not in lowered
    assert "emf_data_root" not in lowered


def test_modules_no_rompe_comandos_existentes():
    result = _run("--help")
    assert result.exit_code == 0
    assert "modules" in result.output
    assert "workspace" in result.output

    result_export = _run("export", "drills", "--help")
    assert result_export.exit_code == 0
    result_run = _run("run", "--help")
    assert result_run.exit_code == 0
    result_workspace = _run("workspace", "validate", "--help")
    assert result_workspace.exit_code == 0
