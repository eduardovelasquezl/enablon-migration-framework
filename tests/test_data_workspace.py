"""Tests unitarios de DataWorkspace (Sprint 7 -- Workspace Separation,
Fase 9). Sin datos reales, sin SQL Server, sin dependencia de
C:\\Users\\EduardoVelásquez ni de ninguna ruta específica de este equipo.

Ejecutar con: pytest tests/test_data_workspace.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.data_workspace import (
    DataRootNotConfiguredError,
    DataWorkspace,
    PathEscapesWorkspaceError,
    RequiredPathNotFoundError,
    UnknownCategoryError,
    UnknownProjectError,
)

_TEST_ROOT_ENV = "EMF_DATA_ROOT_TEST_ONLY"


def _config():
    return {
        "root_env": _TEST_ROOT_ENV,
        "projects": {
            "moeve": {
                "base": "projects/moeve",
                "categories": {"csv_enablon": "CSV_Enablon", "etl": "ETL"},
            },
        },
    }


# --------------------------------------------------------------------------
# Data root: definido / ausente
# --------------------------------------------------------------------------

def test_data_root_definido_via_variable_de_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv(_TEST_ROOT_ENV, str(tmp_path))
    ws = DataWorkspace(_config())
    assert ws.data_root() == tmp_path


def test_data_root_ausente_lanza_error_explicito(monkeypatch):
    monkeypatch.delenv(_TEST_ROOT_ENV, raising=False)
    ws = DataWorkspace(_config())
    with pytest.raises(DataRootNotConfiguredError):
        ws.data_root()


def test_data_root_via_override_no_requiere_variable_de_entorno(tmp_path, monkeypatch):
    monkeypatch.delenv(_TEST_ROOT_ENV, raising=False)
    ws = DataWorkspace(_config(), root_override=tmp_path)
    assert ws.data_root() == tmp_path


# --------------------------------------------------------------------------
# Resolución de rutas relativas
# --------------------------------------------------------------------------

def test_ruta_relativa_valida_no_requerida(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(project="moeve", category="csv_enablon", relative_path="Drills.csv", required=False)
    assert resolved == (tmp_path / "projects" / "moeve" / "CSV_Enablon" / "Drills.csv").resolve()


def test_categoria_sin_relative_path_devuelve_la_carpeta(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(project="moeve", category="csv_enablon", required=False)
    assert resolved == (tmp_path / "projects" / "moeve" / "CSV_Enablon").resolve()


def test_ruta_con_espacios(tmp_path):
    category_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon"
    category_dir.mkdir(parents=True)
    target = category_dir / "Historical Export 2026.csv"
    target.write_text("A,B\n1,2\n", encoding="utf-8")

    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(
        project="moeve", category="csv_enablon", relative_path="Historical Export 2026.csv", required=True,
    )
    assert resolved == target.resolve()


def test_ruta_con_caracteres_unicode(tmp_path):
    category_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon"
    category_dir.mkdir(parents=True)
    target = category_dir / "Exportación_Año_2026_Ñoño.csv"
    target.write_text("A,B\n1,2\n", encoding="utf-8")

    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(
        project="moeve", category="csv_enablon",
        relative_path="Exportación_Año_2026_Ñoño.csv", required=True,
    )
    assert resolved == target.resolve()
    assert resolved.is_file()


# --------------------------------------------------------------------------
# Requerida vs opcional
# --------------------------------------------------------------------------

def test_ruta_requerida_existente_se_resuelve(tmp_path):
    category_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon"
    category_dir.mkdir(parents=True)
    (category_dir / "Drills.csv").write_text("A\n1\n", encoding="utf-8")

    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(project="moeve", category="csv_enablon", relative_path="Drills.csv", required=True)
    assert resolved.is_file()


def test_ruta_requerida_inexistente_lanza_error(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    with pytest.raises(RequiredPathNotFoundError):
        ws.resolve(project="moeve", category="csv_enablon", relative_path="no_existe.csv", required=True)


def test_ruta_opcional_inexistente_no_lanza(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    resolved = ws.resolve(project="moeve", category="csv_enablon", relative_path="no_existe.csv", required=False)
    assert not resolved.exists()
    assert resolved.name == "no_existe.csv"


# --------------------------------------------------------------------------
# Seguridad: escape de la categoría / rutas absolutas
# --------------------------------------------------------------------------

def test_intento_de_escape_con_puntos_dobles_se_rechaza(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    with pytest.raises(PathEscapesWorkspaceError):
        ws.resolve(project="moeve", category="csv_enablon", relative_path="../../etc/passwd", required=False)


def test_ruta_absoluta_no_permitida_como_relative_path(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    otro_absoluto = str((tmp_path / "fuera_de_la_categoria.csv").resolve())
    with pytest.raises(PathEscapesWorkspaceError):
        ws.resolve(project="moeve", category="csv_enablon", relative_path=otro_absoluto, required=False)


def test_no_crea_directorios_automaticamente(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    ws.resolve(project="moeve", category="csv_enablon", relative_path="Drills.csv", required=False)
    assert not (tmp_path / "projects" / "moeve" / "CSV_Enablon").exists()


# --------------------------------------------------------------------------
# Proyecto / categoría desconocidos
# --------------------------------------------------------------------------

def test_proyecto_desconocido_lanza_error_explicito(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    with pytest.raises(UnknownProjectError):
        ws.resolve(project="cliente_inexistente", category="csv_enablon", required=False)


def test_categoria_desconocida_lanza_error_explicito(tmp_path):
    ws = DataWorkspace(_config(), root_override=tmp_path)
    with pytest.raises(UnknownCategoryError):
        ws.resolve(project="moeve", category="categoria_inexistente", required=False)


# --------------------------------------------------------------------------
# root_env es configurable, no fijo
# --------------------------------------------------------------------------

def test_root_env_es_configurable():
    ws = DataWorkspace({"root_env": "OTRA_VARIABLE", "projects": {}})
    assert ws.root_env == "OTRA_VARIABLE"


def test_root_env_por_defecto_si_no_se_declara():
    from src.core.data_workspace import DEFAULT_ROOT_ENV
    ws = DataWorkspace({"projects": {}})
    assert ws.root_env == DEFAULT_ROOT_ENV == "EMF_DATA_ROOT"
