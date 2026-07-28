"""Tests unitarios del Module Registry (Sprint 8.6). Genérico, sin Drills
-- ver `tests/test_bootstrap_module_registry.py` para el registro real de
Drills y la prueba arquitectónica de que `src/core/` no lo importa.

Ejecutar con: pytest tests/test_module_registry.py -v
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.contracts import ExecutionContext, ExecutionRequest, PipelineDefinition
from src.core.module_registry import (
    DuplicateModuleAliasError,
    DuplicateModuleError,
    ModuleCapabilities,
    ModuleCapability,
    ModuleDefinition,
    ModuleDisabledForProjectError,
    ModuleImplementationStatus,
    ModuleNotImplementedError,
    ModuleRegistry,
    ModuleRegistryError,
    MissingPipelineFactoryError,
    UnknownModuleError,
    UnsupportedCapabilityError,
    ensure_module_runnable,
)
from src.core.registry import StageRegistry
from src.core.workspace_manifest import WorkspaceManifestError, WorkspaceManifestLoader


def _noop_factory(request: ExecutionRequest, registry: StageRegistry):
    raise AssertionError("La factory no debe ejecutarse solo por consultar el registro.")


def _definition(
    module_id: str = "widgets", *, status: str = ModuleImplementationStatus.IMPLEMENTED,
    aliases: frozenset[str] = frozenset(), canonical_name: str | None = None,
    capabilities: frozenset[str] = frozenset({ModuleCapability.EXPORT}),
    pipeline_factory=_noop_factory,
) -> ModuleDefinition:
    return ModuleDefinition(
        module_id=module_id, display_name=module_id.title(), version="0.1.0",
        status=status, capabilities=ModuleCapabilities(capabilities),
        aliases=aliases, canonical_name=canonical_name, pipeline_factory=pipeline_factory,
    )


# --------------------------------------------------------------------------
# Registro válido / duplicados
# --------------------------------------------------------------------------

def test_registro_valido():
    registry = ModuleRegistry()
    registry.register(_definition())
    assert registry.contains("widgets")
    assert registry.get("widgets").module_id == "widgets"


def test_module_id_duplicado_lanza_duplicate_module_error():
    registry = ModuleRegistry()
    registry.register(_definition())
    with pytest.raises(DuplicateModuleError):
        registry.register(_definition())


def test_module_id_duplicado_con_overwrite_reemplaza():
    registry = ModuleRegistry()
    registry.register(_definition(status=ModuleImplementationStatus.PLANNED, pipeline_factory=None))
    registry.register(_definition(), overwrite=True)
    assert registry.get("widgets").status == ModuleImplementationStatus.IMPLEMENTED


def test_alias_duplicado_lanza_duplicate_module_alias_error():
    registry = ModuleRegistry()
    registry.register(_definition("a", aliases=frozenset({"shared"})))
    with pytest.raises(DuplicateModuleAliasError):
        registry.register(_definition("b", aliases=frozenset({"shared"})))


def test_alias_contra_module_id_existente_lanza_error():
    registry = ModuleRegistry()
    registry.register(_definition("a"))
    with pytest.raises(DuplicateModuleAliasError):
        registry.register(_definition("b", aliases=frozenset({"a"})))


def test_module_id_contra_alias_existente_lanza_error():
    registry = ModuleRegistry()
    registry.register(_definition("a", aliases=frozenset({"legacy_a"})))
    with pytest.raises(DuplicateModuleAliasError):
        registry.register(_definition("legacy_a"))


def test_canonical_name_duplicado_lanza_error():
    registry = ModuleRegistry()
    registry.register(_definition("a", canonical_name="Shared"))
    with pytest.raises(ModuleRegistryError):
        registry.register(_definition("b", canonical_name="Shared"))


# --------------------------------------------------------------------------
# Consulta: módulo desconocido / por alias / listado determinista
# --------------------------------------------------------------------------

def test_modulo_desconocido_lanza_unknown_module_error():
    registry = ModuleRegistry()
    with pytest.raises(UnknownModuleError):
        registry.get("no_existe")


def test_consulta_por_alias_resuelve_al_module_id_real():
    registry = ModuleRegistry()
    registry.register(_definition("widgets", aliases=frozenset({"gadgets"})))
    assert registry.get("gadgets").module_id == "widgets"
    assert registry.contains("gadgets")


def test_listado_es_determinista():
    registry = ModuleRegistry()
    registry.register(_definition("zeta"))
    registry.register(_definition("alpha"))
    registry.register(_definition("mu"))
    assert registry.list_modules() == ("alpha", "mu", "zeta")
    assert registry.list_modules() == registry.list_modules()  # repetible


# --------------------------------------------------------------------------
# Capabilities / supports
# --------------------------------------------------------------------------

def test_capabilities_devuelve_el_conjunto_declarado():
    registry = ModuleRegistry()
    registry.register(_definition(capabilities=frozenset({ModuleCapability.EXPORT, ModuleCapability.SAMPLE})))
    caps = registry.capabilities("widgets")
    assert caps.supports(ModuleCapability.EXPORT)
    assert caps.supports(ModuleCapability.SAMPLE)
    assert not caps.supports(ModuleCapability.FULL)


def test_supports_true_false():
    registry = ModuleRegistry()
    registry.register(_definition(capabilities=frozenset({ModuleCapability.EXPORT})))
    assert registry.supports("widgets", ModuleCapability.EXPORT) is True
    assert registry.supports("widgets", ModuleCapability.IMPORT) is False


def test_supports_capability_desconocida_lanza_unsupported_capability_error():
    registry = ModuleRegistry()
    registry.register(_definition())
    with pytest.raises(UnsupportedCapabilityError):
        registry.supports("widgets", "not_a_real_capability")


def test_capabilities_con_valor_fuera_de_vocabulario_lanza_al_construir():
    with pytest.raises(UnsupportedCapabilityError):
        ModuleCapabilities(frozenset({"not_a_real_capability"}))


def test_ensure_capability_lanza_si_no_soportada():
    registry = ModuleRegistry()
    registry.register(_definition(capabilities=frozenset({ModuleCapability.EXPORT})))
    with pytest.raises(UnsupportedCapabilityError):
        registry.ensure_capability("widgets", ModuleCapability.FULL)


def test_ensure_capability_devuelve_definicion_si_soportada():
    registry = ModuleRegistry()
    registry.register(_definition(capabilities=frozenset({ModuleCapability.EXPORT})))
    definition = registry.ensure_capability("widgets", ModuleCapability.EXPORT)
    assert definition.module_id == "widgets"


# --------------------------------------------------------------------------
# Status / factory
# --------------------------------------------------------------------------

def test_modulo_planned_sin_factory_se_registra_sin_error():
    registry = ModuleRegistry()
    registry.register(_definition(status=ModuleImplementationStatus.PLANNED, pipeline_factory=None))
    assert registry.get("widgets").status == ModuleImplementationStatus.PLANNED


def test_modulo_planned_con_factory_lanza_error():
    with pytest.raises(ModuleRegistryError):
        _definition(status=ModuleImplementationStatus.PLANNED, pipeline_factory=_noop_factory)


def test_modulo_implemented_sin_factory_lanza_missing_pipeline_factory_error():
    with pytest.raises(MissingPipelineFactoryError):
        _definition(status=ModuleImplementationStatus.IMPLEMENTED, pipeline_factory=None)


def test_modulo_experimental_sin_factory_lanza_missing_pipeline_factory_error():
    with pytest.raises(MissingPipelineFactoryError):
        _definition(status=ModuleImplementationStatus.EXPERIMENTAL, pipeline_factory=None)


def test_modulo_deprecated_resoluble_y_emite_warning(caplog):
    registry = ModuleRegistry()
    registry.register(_definition(status=ModuleImplementationStatus.DEPRECATED, pipeline_factory=_noop_factory))
    with caplog.at_level(logging.WARNING):
        definition = registry.get("widgets")
    assert definition.status == ModuleImplementationStatus.DEPRECATED
    assert any("deprecated" in r.message for r in caplog.records)


def test_factory_registrada_se_puede_obtener():
    registry = ModuleRegistry()
    registry.register(_definition())
    factory = registry.get_pipeline_factory("widgets")
    assert factory is _noop_factory


def test_factory_no_se_ejecuta_durante_la_consulta():
    """`_noop_factory` lanza AssertionError si se invoca -- ninguna
    consulta de este test la invoca, solo la referencia."""
    registry = ModuleRegistry()
    registry.register(_definition())
    registry.get("widgets")
    registry.capabilities("widgets")
    registry.supports("widgets", ModuleCapability.EXPORT)
    registry.get_pipeline_factory("widgets")  # obtiene la referencia, no la llama
    registry.list_executable()
    # Si cualquiera de las líneas anteriores hubiera ejecutado la factory,
    # habría lanzado AssertionError -- llegar aquí confirma que no.


def test_get_pipeline_factory_de_modulo_planned_lanza_not_implemented():
    registry = ModuleRegistry()
    registry.register(_definition(status=ModuleImplementationStatus.PLANNED, pipeline_factory=None))
    with pytest.raises(ModuleNotImplementedError):
        registry.get_pipeline_factory("widgets")


def test_list_executable_excluye_planned():
    registry = ModuleRegistry()
    registry.register(_definition("a", status=ModuleImplementationStatus.IMPLEMENTED))
    registry.register(_definition("b", status=ModuleImplementationStatus.PLANNED, pipeline_factory=None))
    assert registry.list_executable() == ("a",)


# --------------------------------------------------------------------------
# Integración con WorkspaceManifest (Fase 11) -- ensure_module_runnable
# --------------------------------------------------------------------------

def _manifest_con_widgets(*, enabled: bool = True):
    return WorkspaceManifestLoader.load_from_dict({
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {
            "widgets": {"display_name": "Widgets", "enabled": enabled, "status": "ready"},
        },
    })


def test_ensure_module_runnable_sin_manifest_solo_comprueba_registry():
    registry = ModuleRegistry()
    registry.register(_definition())
    definition = ensure_module_runnable(registry, "widgets")
    assert definition.module_id == "widgets"


def test_ensure_module_runnable_modulo_no_declarado_en_proyecto_lanza_workspace_manifest_error():
    registry = ModuleRegistry()
    registry.register(_definition())
    manifest = WorkspaceManifestLoader.load_from_dict({
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {"otro": {"display_name": "Otro", "enabled": True, "status": "ready"}},
    })
    with pytest.raises(WorkspaceManifestError):
        ensure_module_runnable(registry, "widgets", manifest=manifest)


def test_ensure_module_runnable_modulo_deshabilitado_lanza_module_disabled_for_project_error():
    registry = ModuleRegistry()
    registry.register(_definition())
    manifest = _manifest_con_widgets(enabled=False)
    with pytest.raises(ModuleDisabledForProjectError):
        ensure_module_runnable(registry, "widgets", manifest=manifest)


def test_ensure_module_runnable_modulo_habilitado_pasa():
    registry = ModuleRegistry()
    registry.register(_definition())
    manifest = _manifest_con_widgets(enabled=True)
    definition = ensure_module_runnable(registry, "widgets", manifest=manifest)
    assert definition.module_id == "widgets"


def test_ensure_module_runnable_capability_no_soportada_lanza():
    registry = ModuleRegistry()
    registry.register(_definition(capabilities=frozenset({ModuleCapability.EXPORT})))
    with pytest.raises(UnsupportedCapabilityError):
        ensure_module_runnable(registry, "widgets", capability=ModuleCapability.FULL)


def test_ensure_module_runnable_modulo_no_registrado_lanza_unknown_module_error():
    registry = ModuleRegistry()
    with pytest.raises(UnknownModuleError):
        ensure_module_runnable(registry, "no_existe")


# --------------------------------------------------------------------------
# ModuleDefinition -- validaciones adicionales
# --------------------------------------------------------------------------

def test_module_id_vacio_lanza_error():
    with pytest.raises(ModuleRegistryError):
        _definition("")


def test_status_invalido_lanza_error():
    with pytest.raises(ModuleRegistryError):
        ModuleDefinition(
            module_id="x", display_name="X", version="0.1.0", status="not_a_real_status",
            capabilities=ModuleCapabilities(frozenset()),
        )


def test_required_y_optional_artifact_types_solapados_lanza_error():
    with pytest.raises(ModuleRegistryError):
        ModuleDefinition(
            module_id="x", display_name="X", version="0.1.0",
            status=ModuleImplementationStatus.PLANNED, pipeline_factory=None,
            capabilities=ModuleCapabilities(frozenset()),
            required_artifact_types=frozenset({"sql"}),
            optional_artifact_types=frozenset({"sql"}),
        )


def test_artifact_type_fuera_de_vocabulario_lanza_error():
    with pytest.raises(ModuleRegistryError):
        ModuleDefinition(
            module_id="x", display_name="X", version="0.1.0",
            status=ModuleImplementationStatus.PLANNED, pipeline_factory=None,
            capabilities=ModuleCapabilities(frozenset()),
            required_artifact_types=frozenset({"not_a_real_kind"}),
        )


def test_supported_mode_invalido_lanza_error():
    with pytest.raises(ModuleRegistryError):
        ModuleDefinition(
            module_id="x", display_name="X", version="0.1.0",
            status=ModuleImplementationStatus.PLANNED, pipeline_factory=None,
            capabilities=ModuleCapabilities(frozenset()),
            supported_modes=frozenset({"turbo"}),
        )
