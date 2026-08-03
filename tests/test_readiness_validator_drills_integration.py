"""Tests de integración del Workspace Readiness Validator con Drills real
(Sprint 8.7) -- usa `build_default_module_registry()` (composition root
real) contra manifests temporales en `tmp_path`, mismo patrón que
`tests/test_cli_workspace_resolve.py`. Nunca SQL Server, nunca ETL/CSV
reales, nunca escribe en el workspace externo del usuario (siempre
`EMF_DATA_ROOT` apuntando a `tmp_path`).

Ejecutar con: pytest tests/test_readiness_validator_drills_integration.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.bootstrap.module_registry import build_default_module_registry
from src.core.data_workspace import get_default_data_workspace
from src.core.module_registry import ModuleRegistry
from src.core.readiness_validator import (
    ReadinessRequest,
    ReadinessStatus,
    WorkspaceReadinessValidator,
)
from src.core.resource_resolver import ResourceResolver
from src.core.workspace_manifest import WorkspaceManifestLoader

_BASE_MANIFEST = """
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
    display_name: "Drills (Business Continuity Management / Simulacros)"
    enabled: {enabled}
    status: in_progress
    canonical_name: Drills
    artifacts:
      etl:
        path: null
        status: missing
      template_csv:
        path: null
        status: missing
        contract_role: platform
      operational_csv:
        path: {operational_path}
        status: {operational_status}
        {operational_required}
        contract_role: project
      sql:
        path: null
        status: {sql_status}
        required_for_sample: true
        required_for_full: true
        source: "git:sql/source_queries/Simulacros/x.sql"
      mapping:
        path: null
        status: present
        required_for_sample: true
        required_for_full: true
        source: "repo:inputs/entity_catalog/x.csv"
      catalogs:
        path: null
        status: not_applicable
      errors:
        path: null
        status: missing
      evidence:
        path: null
        status: missing
      outputs:
        path: null
        status: missing
    contracts:
      platform:
        artifact: template_csv
      project:
        artifact: operational_csv
      emf:
        generated: true
        output_pattern: "Drills_{{execution_id}}.csv"
"""


def _write_manifest(
    tmp_path: Path, *, enabled: bool = True,
    operational_path: str | None = None, operational_status: str = "missing",
    operational_required_for_comparison: bool = True,
    sql_status: str = "present",
) -> Path:
    manifest_path = tmp_path / "workspace.yaml"
    manifest_path.write_text(
        _BASE_MANIFEST.format(
            enabled=str(enabled).lower(),
            operational_path=(f'"{operational_path}"' if operational_path else "null"),
            operational_status=operational_status,
            operational_required=(
                "required_for_comparison: true" if operational_required_for_comparison else ""
            ),
            sql_status=sql_status,
        ),
        encoding="utf-8",
    )
    return manifest_path


def _load(manifest_path: Path):
    return WorkspaceManifestLoader.load_from_path(manifest_path)


def _validate(manifest, registry: ModuleRegistry, *, operation: str, **kw):
    resolver = ResourceResolver(manifest, get_default_data_workspace())
    request = ReadinessRequest(
        project_id=manifest.project.id, module_id="drills", operation=operation,
        manifest=manifest, registry=registry, resolver=resolver, **kw
    )
    return WorkspaceReadinessValidator().assess(request)


# ---------------------------------------------------------------------------
# A. Drills sample sin comparison
# ---------------------------------------------------------------------------

def test_drills_sample_listo_sin_bloqueos(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="sample")
    assert assessment.status in (ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS)
    assert not assessment.blockers


def test_drills_sample_con_warnings_por_opcionales_ausentes(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="sample")
    assert assessment.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(i.artifact_type == "template_csv" for i in assessment.warnings)
    assert any(i.artifact_type == "operational_csv" for i in assessment.warnings)


def test_drills_sample_bloqueado_si_sql_falta(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path, sql_status="missing"))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="sample")
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "ARTIFACT_MISSING" and i.artifact_type == "sql" for i in assessment.blockers)


# ---------------------------------------------------------------------------
# B. Drills comparison
# ---------------------------------------------------------------------------

def test_drills_comparison_sin_operational_csv_bloquea(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path, operational_status="missing"))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="comparison")
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.artifact_type == "operational_csv" for i in assessment.blockers)


def test_drills_comparison_con_operational_csv_presente_no_bloquea(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(
        tmp_path, operational_path="Drills.csv", operational_status="present",
    ))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="comparison")
    assert assessment.status != ReadinessStatus.BLOCKED


def test_drills_comparison_operational_ausente_no_bloquea_un_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path, operational_status="missing"))
    registry = build_default_module_registry()
    sample_assessment = _validate(manifest, registry, operation="sample")
    comparison_assessment = _validate(manifest, registry, operation="comparison")
    assert sample_assessment.status != ReadinessStatus.BLOCKED
    assert comparison_assessment.status == ReadinessStatus.BLOCKED


# ---------------------------------------------------------------------------
# C. Drills full readiness -- evalúa recursos, nunca ejecuta
# ---------------------------------------------------------------------------

def test_drills_full_readiness_no_requiere_autorizacion_sql(tmp_path, monkeypatch):
    from src.db import sql_execution_guard

    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    sql_execution_guard.revoke()
    manifest = _load(_write_manifest(tmp_path))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="full")
    assert assessment.status in (ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS)
    assert sql_execution_guard.is_authorized() is False
    assert "--confirm-full-export" in assessment.recommended_next_action
    sql_execution_guard.revoke()


# ---------------------------------------------------------------------------
# D. Módulo deshabilitado en el proyecto
# ---------------------------------------------------------------------------

def test_drills_deshabilitado_en_el_proyecto_bloquea(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path, enabled=False))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="sample")
    assert assessment.status == ReadinessStatus.BLOCKED
    assert [i.code for i in assessment.blockers] == ["MODULE_DISABLED"]


# ---------------------------------------------------------------------------
# E. Declarado pero software no implementado
# ---------------------------------------------------------------------------

def test_drills_declarado_pero_registro_vacio_es_module_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(tmp_path))
    empty_registry = ModuleRegistry()  # el software no registra Drills en absoluto
    assessment = _validate(manifest, empty_registry, operation="sample")
    assert assessment.status == ReadinessStatus.BLOCKED
    assert [i.code for i in assessment.blockers] == ["MODULE_UNKNOWN"]
    # Distinto de un artefacto ausente -- ningún ARTIFACT_* en los blockers.
    assert not any(i.code.startswith("ARTIFACT_") for i in assessment.blockers)


# ---------------------------------------------------------------------------
# Project Contract mal declarado / archivo fuera del data root
# ---------------------------------------------------------------------------

def test_project_contract_apuntando_a_artefacto_no_marcado_required_genera_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _load(_write_manifest(
        tmp_path, operational_path="Drills.csv", operational_status="present",
        operational_required_for_comparison=False,
    ))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="comparison")
    assert any(i.code == "CONTRACT_ARTIFACT_NOT_MARKED_REQUIRED" for i in assessment.warnings)


def test_archivo_declarado_dentro_del_repositorio_no_escapa_el_data_root(tmp_path, monkeypatch):
    """Con EMF_DATA_ROOT apuntando a tmp_path (fuera del repo), toda ruta
    resuelta cae dentro de tmp_path -- SecurityCheck nunca debería marcar
    DATA_ROOT_ESCAPE en un escenario normal."""
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    real_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon_Operational"
    real_dir.mkdir(parents=True)
    (real_dir / "Drills.csv").write_text("x", encoding="utf-8")
    manifest = _load(_write_manifest(
        tmp_path, operational_path="Drills.csv", operational_status="present",
    ))
    registry = build_default_module_registry()
    assessment = _validate(manifest, registry, operation="comparison", require_physical_files=True)
    assert not any(i.code == "DATA_ROOT_ESCAPE" for i in assessment.issues)
