"""Tests del composition root del Module Registry (Sprint 8.6):
`src/bootstrap/module_registry.py`, el único registro real hoy (Drills).

Incluye la prueba arquitectónica que pide el encargo (Fase 7): `src/core/`
no puede importar Drills. Ejecutar con:
pytest tests/test_bootstrap_module_registry.py -v
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

import src.core.module_registry as core_module_registry_mod
import src.export.prototype.drills.extractor as extractor_mod
from src.bootstrap.module_registry import build_default_module_registry
from src.core.contracts import ExecutionRequest
from src.core.module_registry import (
    ModuleCapability,
    ModuleImplementationStatus,
    ModuleNotImplementedError,
)
from src.core.registry import StageRegistry


# --------------------------------------------------------------------------
# Prueba arquitectónica: src/core/ no importa Drills ni src.export
# --------------------------------------------------------------------------

def test_core_module_registry_no_importa_drills_ni_export():
    """Verificado por inspección de las sentencias `import` reales del
    propio fichero fuente (no de comentarios/docstrings) -- mismo patrón
    ya usado por
    `tests/test_workspace_manifest.py::test_modulo_no_importa_nada_de_src_db_ni_src_export`."""
    tree = ast.parse(Path(core_module_registry_mod.__file__).read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_prefixes = ("src.export", "src.etl", "src.evidence")
    offending = [m for m in imported_modules if m.startswith(forbidden_prefixes)]
    assert offending == []


def test_stage_registry_no_se_duplica_en_module_registry():
    """`ModuleRegistry` no reimplementa el registro de etapas -- delega
    en `StageRegistry` a través de la `pipeline_factory` (que recibe uno
    nuevo por ejecución, nunca uno propio guardado en el módulo)."""
    import inspect

    source = inspect.getsource(core_module_registry_mod)
    # ModuleRegistry importa StageRegistry solo para tipar PipelineFactory,
    # nunca instancia uno propio dentro de la clase.
    assert "self._stages" not in source
    assert "class StageRegistry" not in source


# --------------------------------------------------------------------------
# Drills registrado
# --------------------------------------------------------------------------

def test_drills_registrado_como_modulo_ejecutable():
    registry = build_default_module_registry()
    assert registry.contains("drills")
    definition = registry.get("drills")
    assert definition.is_executable
    assert definition.status == ModuleImplementationStatus.EXPERIMENTAL


def test_drills_alias_simulacros_resuelve():
    registry = build_default_module_registry()
    assert registry.get("simulacros").module_id == "drills"


def test_drills_no_tiene_alias_sm():
    """CLAUDE.md / config/modules.yaml usan 'SM' para Safety Meetings, un
    módulo DISTINTO -- ver Fase 1 del informe de este sprint. Confirma que
    no se coló como alias de Drills."""
    registry = build_default_module_registry()
    definition = registry.get("drills")
    assert "SM" not in definition.aliases
    assert "sm" not in definition.aliases


def test_drills_capabilities_solo_las_demostrables():
    registry = build_default_module_registry()
    caps = registry.capabilities("drills")
    for expected in (
        ModuleCapability.EXPORT, ModuleCapability.SAMPLE, ModuleCapability.FULL,
        ModuleCapability.EVIDENCE, ModuleCapability.COMPARISON, ModuleCapability.VALIDATION,
        ModuleCapability.MANIFEST_DRIVEN_RESOURCES, ModuleCapability.LEGACY_CLI, ModuleCapability.MAPPING,
    ):
        assert caps.supports(expected), f"Drills debería declarar {expected!r}"
    # No demostrables hoy -- ver docstring de _build_drills_definition.
    assert not caps.supports(ModuleCapability.CANONICALIZATION)
    assert not caps.supports(ModuleCapability.IMPORT)


def test_ningun_modulo_declara_import():
    """El repositorio no ejecuta cargas contra Enablon (CLAUDE.md) -- por
    diseño, ningún módulo registrado debe declarar la capacidad 'import'."""
    registry = build_default_module_registry()
    for module_id in registry.list_modules():
        assert not registry.supports(module_id, ModuleCapability.IMPORT)


def test_modulos_futuros_del_manifest_no_estan_registrados():
    """Los 5 módulos restantes del Workspace Manifest de ejemplo (Sprint
    8.4) no tienen pipeline real -- no deben aparecer en el ModuleRegistry
    (Fase 9 del encargo: 'no confundir presencia en el proyecto con
    soporte del software'). 'bypass' se retiró de esta lista en Sprint
    9.4, 'safety_meetings' en Sprint 9.7 -- ambos SÍ tienen un
    pipeline_factory real, ver test_registry_tiene_drills_bypass_y_safety_meetings."""
    registry = build_default_module_registry()
    for module_id in (
        "moc", "events", "ops", "inspections", "corrective_actions",
    ):
        assert not registry.contains(module_id), f"{module_id!r} no debería estar registrado todavía"


def test_registry_tiene_drills_bypass_y_safety_meetings():
    """Sprint 9.7: Safety Meetings es el tercer módulo real registrado,
    junto a Drills y Bypass -- ver
    docs/07-developer-guide/safety-meetings-module.md."""
    registry = build_default_module_registry()
    assert set(registry.list_modules()) == {"drills", "bypass", "safety_meetings"}
    assert set(registry.list_executable()) == {"drills", "bypass", "safety_meetings"}


# --------------------------------------------------------------------------
# pipeline_factory de Drills -- integración local, sin SQL real
# --------------------------------------------------------------------------

def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDSimulacro": [440], "IDTipo": [365], "Fecha": ["08/03/2010"], "Hora": ["12:30"],
        "IDLetra": [258], "IDUnidadOrg": [278], "Estado": ["Terminado"],
    })


@pytest.fixture(autouse=True)
def _patch_run_query(monkeypatch):
    fake_df = _fake_dataframe()
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: fake_df.copy())
    yield


def test_pipeline_factory_construye_definition_y_context_sin_sql_real(tmp_path):
    registry = build_default_module_registry()
    factory = registry.get_pipeline_factory("drills")
    request = ExecutionRequest(
        project="moeve", object_type="drills", mode="sample", limit=5, output_dir=str(tmp_path),
    )
    stage_registry = StageRegistry()
    definition, context = factory(request, stage_registry)

    assert definition.name == "drills"
    assert context.request is request
    assert stage_registry.is_registered("query")
    # Construir la factory no ejecuta el pipeline -- ninguna carpeta se crea.
    assert list(tmp_path.iterdir()) == []


def test_get_pipeline_factory_no_ejecuta_nada_por_si_sola(tmp_path):
    registry = build_default_module_registry()
    registry.get_pipeline_factory("drills")  # solo obtiene la referencia
    assert list(tmp_path.iterdir()) == []
