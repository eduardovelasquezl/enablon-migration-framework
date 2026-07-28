"""Tests unitarios del Resource Resolver (Sprint 8.5). Sin datos reales,
sin SQL Server -- todo sobre manifests construidos en memoria y
`DataWorkspace` apuntando a `tmp_path`.

Ejecutar con: pytest tests/test_resource_resolver.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.data_workspace import DataWorkspace
from src.core.workspace_manifest import ArtifactStatus, WorkspaceManifestLoader
from src.core.resource_resolver import (
    ArtifactMissingError,
    ArtifactNotDeclaredError,
    DeprecatedArtifactError,
    GENERATED_ARTIFACT_KIND,
    InvalidArtifactStatusError,
    PhysicalResourceMissingError,
    ResolvedResource,
    ResourcePathError,
    ResourceRequest,
    ResourceResolver,
    UnknownArtifactError,
    UnknownModuleError,
    UnknownProjectError,
)

ENV_VAR = "EMF_DATA_ROOT_TEST_ONLY"


def _ws_config() -> dict:
    return {
        "root_env": ENV_VAR,
        "projects": {
            "moeve": {
                "base": "projects/moeve",
                "categories": {
                    "etl": "ETL",
                    "csv_enablon_template": "CSV_Enablon_Template",
                    "csv_enablon_operational": "CSV_Enablon_Operational",
                    "mappings": "Mappings",
                    "sql": "SQL",
                    "outputs": "Outputs",
                    "errors": "Errors",
                },
            },
        },
    }


def _manifest(**module_overrides) -> "WorkspaceManifest":  # type: ignore[name-defined]
    module = {
        "display_name": "Drills",
        "enabled": True,
        "status": "ready",
        "canonical_name": "Drills",
        "artifacts": {
            "operational_csv": {
                "path": "Drills.csv",
                "status": "missing",
                "contract_role": "project",
            },
            "template_csv": {
                "path": "Drills-22072026-41.csv",
                "status": "present",
                "contract_role": "platform",
            },
            "sql": {
                "path": None,
                "status": "present",
                "source": "git:sql/x.sql",
            },
            "catalogs": {
                "path": None,
                "status": "not_applicable",
                "description": "No usa First_Axis.",
            },
            "mapping": {
                "path": "legacy_catalog.csv",
                "status": "deprecated",
            },
            "errors": {
                "path": "helpdesk.xlsx",
                "status": "optional",
            },
        },
    }
    module.update(module_overrides)
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {"drills": module},
    }
    return WorkspaceManifestLoader.load_from_dict(raw)


def _resolver(tmp_path, monkeypatch, **module_overrides) -> ResourceResolver:
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    manifest = _manifest(**module_overrides)
    ws = DataWorkspace(_ws_config())
    return ResourceResolver(manifest, ws)


# --------------------------------------------------------------------------
# Proyecto / módulo / artefacto: válidos y desconocidos
# --------------------------------------------------------------------------

def test_proyecto_valido_no_lanza(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="sql", project_id="moeve"))
    assert resolved.project_id == "moeve"


def test_proyecto_desconocido_lanza_unknown_project(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(UnknownProjectError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="sql", project_id="otro_proyecto"))


def test_modulo_valido_resuelve(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="sql"))
    assert resolved.module_id == "drills"


def test_modulo_desconocido_lanza_unknown_module(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(UnknownModuleError):
        resolver.resolve(ResourceRequest(module_id="no_existe", artifact_type="sql"))


def test_artefacto_kind_desconocido_lanza_unknown_artifact(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(UnknownArtifactError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="not_a_real_kind"))


def test_artefacto_no_declarado_por_el_modulo_lanza_not_declared(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    # 'evidence' es un kind válido del vocabulario cerrado, pero este
    # módulo de prueba no lo declara en 'artifacts'.
    with pytest.raises(ArtifactNotDeclaredError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="evidence"))


# --------------------------------------------------------------------------
# Estados de artefacto
# --------------------------------------------------------------------------

def test_artefacto_missing_requerido_lanza_artifact_missing(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch, artifacts={
        "operational_csv": {"path": None, "status": "missing"},
    })
    with pytest.raises(ArtifactMissingError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="operational_csv", required=True))


def test_artefacto_missing_opcional_no_lanza_y_declara_ausencia(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch, artifacts={
        "operational_csv": {"path": None, "status": "missing"},
    })
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="operational_csv", required=False))
    assert resolved.resolved_path is None
    assert resolved.declared_path is None
    assert any("status=missing" in w for w in resolved.warnings)


def test_artefacto_deprecated_lanza_por_defecto(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(DeprecatedArtifactError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="mapping"))


def test_artefacto_deprecated_con_allow_deprecated_resuelve(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(
        ResourceRequest(module_id="drills", artifact_type="mapping", allow_deprecated=True)
    )
    assert resolved.artifact_status == ArtifactStatus.DEPRECATED


def test_artefacto_not_applicable_lanza_invalid_status(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(InvalidArtifactStatusError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="catalogs"))


def test_allowed_statuses_rechaza_status_no_permitido(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(InvalidArtifactStatusError):
        resolver.resolve(ResourceRequest(
            module_id="drills", artifact_type="template_csv",
            allowed_statuses=frozenset({ArtifactStatus.VALIDATED}),
        ))


# --------------------------------------------------------------------------
# Rutas: sin path declarado / con path / con proyección física
# --------------------------------------------------------------------------

def test_path_no_declarado_sin_required_devuelve_resolved_path_none(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="sql"))
    assert resolved.resolved_path is None
    assert resolved.declared_path is None


def test_path_declarado_resuelve_ruta_absoluta_dentro_del_workspace(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="template_csv"))
    expected = (tmp_path / "projects" / "moeve" / "CSV_Enablon_Template" / "Drills-22072026-41.csv").resolve()
    assert resolved.resolved_path == expected
    assert resolved.exists is None  # no se comprobó existencia física


def test_archivo_fisico_existente_se_marca_exists_true(tmp_path, monkeypatch):
    real_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon_Template"
    real_dir.mkdir(parents=True)
    (real_dir / "Drills-22072026-41.csv").write_text("x", encoding="utf-8")
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type="template_csv", require_physical_file=True,
    ))
    assert resolved.exists is True


def test_archivo_fisico_inexistente_requerido_lanza_physical_missing(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(PhysicalResourceMissingError):
        resolver.resolve(ResourceRequest(
            module_id="drills", artifact_type="template_csv",
            required=True, require_physical_file=True,
        ))


def test_archivo_fisico_inexistente_opcional_no_lanza(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type="template_csv",
        required=False, require_physical_file=True,
    ))
    assert resolved.exists is False


def test_status_optional_ausente_fisicamente_no_lanza_ni_con_required(tmp_path, monkeypatch):
    """'optional' no debe fallar únicamente por ausencia física -- ni
    siquiera si se pidió required=True (Fase 4 del encargo)."""
    resolver = _resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type="errors",
        required=True, require_physical_file=True,
    ))
    assert resolved.exists is False
    assert any("opcional" in w for w in resolved.warnings)


# --------------------------------------------------------------------------
# Integración con DataWorkspace / WorkspaceManifest
# --------------------------------------------------------------------------

def test_integra_con_data_workspace_no_crea_nada(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch)
    resolver.resolve(ResourceRequest(module_id="drills", artifact_type="template_csv"))
    assert not (tmp_path / "projects").exists()


def test_error_de_data_workspace_se_envuelve_en_resource_path_error(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    manifest = _manifest(artifacts={"sql": {"path": "x.sql", "status": "present"}})
    # DataWorkspace configurado SIN la categoría 'sql' -- fuerza UnknownCategoryError interno.
    ws = DataWorkspace({
        "root_env": ENV_VAR,
        "projects": {"moeve": {"base": "projects/moeve", "categories": {"etl": "ETL"}}},
    })
    resolver = ResourceResolver(manifest, ws)
    with pytest.raises(ResourcePathError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type="sql"))


def test_unicode_y_espacios_en_path_declarado(tmp_path, monkeypatch):
    resolver = _resolver(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Histórico Drills 2026 (versión final).csv", "status": "present"},
    })
    resolved = resolver.resolve(ResourceRequest(module_id="drills", artifact_type="template_csv"))
    assert resolved.resolved_path.name == "Histórico Drills 2026 (versión final).csv"


# --------------------------------------------------------------------------
# Recursos generados (Fase 5)
# --------------------------------------------------------------------------

def _manifest_con_generado() -> "WorkspaceManifest":  # type: ignore[name-defined]
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {
            "drills": {
                "display_name": "Drills", "enabled": True, "status": "in_progress",
                "canonical_name": "Drills",
                "artifacts": {
                    "operational_csv": {"path": "Drills.csv", "status": "missing", "contract_role": "project"},
                    "outputs": {"path": None, "status": "missing"},
                },
                "contracts": {
                    "project": {"artifact": "operational_csv"},
                    "emf": {"generated": True, "output_pattern": "Drills_{execution_id}.csv"},
                },
            },
        },
    }
    return WorkspaceManifestLoader.load_from_dict(raw)


def _generated_resolver(tmp_path, monkeypatch) -> ResourceResolver:
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    ws = DataWorkspace(_ws_config())
    return ResourceResolver(_manifest_con_generado(), ws)


def test_generated_output_resuelve_con_execution_id_valido(tmp_path, monkeypatch):
    resolver = _generated_resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND, execution_id="abc123",
    ))
    assert resolved.generated is True
    assert resolved.resolved_path.name == "Drills_abc123.csv"
    assert not resolved.resolved_path.exists()  # nunca se crea el archivo


def test_generated_output_sin_execution_id_lanza_resource_path_error(tmp_path, monkeypatch):
    resolver = _generated_resolver(tmp_path, monkeypatch)
    with pytest.raises(ResourcePathError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND))


@pytest.mark.parametrize("bad_execution_id", ["../escape", "a/b", "a\\b", "", "con espacio", "sub;rm"])
def test_generated_output_execution_id_con_intento_de_escape_lanza(tmp_path, monkeypatch, bad_execution_id):
    resolver = _generated_resolver(tmp_path, monkeypatch)
    with pytest.raises(ResourcePathError):
        resolver.resolve(ResourceRequest(
            module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND, execution_id=bad_execution_id,
        ))


def test_generated_output_no_crea_directorio_ni_archivo(tmp_path, monkeypatch):
    resolver = _generated_resolver(tmp_path, monkeypatch)
    resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND,
        execution_id="run1", require_physical_file=True,
    ))
    assert not (tmp_path / "projects").exists()


def test_generated_output_ausente_fisicamente_no_lanza_ni_con_required(tmp_path, monkeypatch):
    resolver = _generated_resolver(tmp_path, monkeypatch)
    resolved = resolver.resolve(ResourceRequest(
        module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND,
        execution_id="run1", required=True, require_physical_file=True,
    ))
    assert resolved.exists is False
    assert resolved.warnings


def test_placeholder_desconocido_en_patron_lanza_resource_path_error(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {
            "drills": {
                "display_name": "Drills", "enabled": True, "status": "in_progress",
                "artifacts": {"outputs": {"path": None, "status": "missing"}},
                "contracts": {"emf": {"generated": True, "output_pattern": "Drills_{unknown_placeholder}.csv"}},
            },
        },
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    ws = DataWorkspace(_ws_config())
    resolver = ResourceResolver(manifest, ws)
    with pytest.raises(ResourcePathError):
        resolver.resolve(ResourceRequest(
            module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND, execution_id="run1",
        ))


def test_modulo_sin_contracts_emf_no_se_trata_como_generado(tmp_path, monkeypatch):
    """Si el módulo no declara contracts.emf.generated, pedir el kind
    'outputs' cae en la resolución declarada normal (probablemente
    ArtifactNotDeclaredError o ArtifactMissingError, nunca en la rama
    generada)."""
    resolver = _resolver(tmp_path, monkeypatch)
    with pytest.raises(ArtifactNotDeclaredError):
        resolver.resolve(ResourceRequest(module_id="drills", artifact_type=GENERATED_ARTIFACT_KIND))
