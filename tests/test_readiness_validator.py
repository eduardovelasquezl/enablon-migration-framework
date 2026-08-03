"""Tests unitarios del Workspace Readiness Validator (Sprint 8.7). Sin
datos reales, sin SQL Server -- todo sobre un `ModuleDefinition` sintético
("widget") y manifests construidos en memoria, mismo patrón que
`tests/test_resource_resolver.py`.

Ejecutar con: pytest tests/test_readiness_validator.py -v
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import src.core.readiness_validator as readiness_validator_module
from src.core.data_workspace import DataWorkspace
from src.core.module_registry import (
    ModuleCapabilities,
    ModuleCapability,
    ModuleDefinition,
    ModuleImplementationStatus,
    ModuleRegistry,
)
from src.core.resource_resolver import ResourceResolver
from src.core.workspace_manifest import WorkspaceManifestLoader
from src.core.readiness_validator import (
    ReadinessOperation,
    ReadinessRequest,
    ReadinessRequestError,
    ReadinessSeverity,
    ReadinessStatus,
    UnknownReadinessOperationError,
    WorkspaceReadinessValidator,
)
from src.db import sql_execution_guard

ENV_VAR = "EMF_DATA_ROOT_READINESS_TEST_ONLY"


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
                    "catalogs": "Catalogs",
                    "outputs": "Outputs",
                    "errors": "Errors",
                    "evidence": "Evidence",
                },
            },
        },
    }


def _pipeline_factory(request, registry):  # pragma: no cover -- nunca debe llamarse
    raise AssertionError("pipeline_factory no debe ejecutarse durante readiness.")


def _widget_definition(
    *,
    status: str = ModuleImplementationStatus.IMPLEMENTED,
    capabilities: frozenset[str] | None = None,
    supported_modes: frozenset[str] = frozenset({"sample", "full"}),
    required_artifact_types: frozenset[str] = frozenset(),
    optional_artifact_types: frozenset[str] = frozenset(),
) -> ModuleDefinition:
    if capabilities is None:
        capabilities = frozenset({
            ModuleCapability.EXPORT, ModuleCapability.SAMPLE, ModuleCapability.FULL,
            ModuleCapability.VALIDATION, ModuleCapability.COMPARISON, ModuleCapability.EVIDENCE,
        })
    factory = _pipeline_factory if status in ModuleImplementationStatus.EXECUTABLE else None
    return ModuleDefinition(
        module_id="widget", display_name="Widget", version="0.1.0", status=status,
        capabilities=ModuleCapabilities(capabilities), supported_modes=supported_modes,
        required_artifact_types=required_artifact_types, optional_artifact_types=optional_artifact_types,
        pipeline_factory=factory,
    )


def _registry(definition: ModuleDefinition | None) -> ModuleRegistry:
    registry = ModuleRegistry()
    if definition is not None:
        registry.register(definition)
    return registry


def _manifest(tmp_path, monkeypatch, *, enabled=True, status="ready", artifacts=None, contracts=None):
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    module = {"display_name": "Widget", "enabled": enabled, "status": status, "artifacts": artifacts or {}}
    if contracts is not None:
        module["contracts"] = contracts
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {"widget": module},
    }
    return WorkspaceManifestLoader.load_from_dict(raw)


def _resolver(manifest) -> ResourceResolver:
    return ResourceResolver(manifest, DataWorkspace(_ws_config()))


def _request(manifest, registry, *, operation="sample", module_id="widget", **kw) -> ReadinessRequest:
    return ReadinessRequest(
        project_id="moeve", module_id=module_id, operation=operation,
        manifest=manifest, registry=registry, resolver=_resolver(manifest), **kw
    )


@pytest.fixture(autouse=True)
def _reset_sql_guard():
    sql_execution_guard.revoke()
    yield
    sql_execution_guard.revoke()


# ---------------------------------------------------------------------------
# Genérico: sin conocimiento de Drills
# ---------------------------------------------------------------------------

def test_readiness_validator_no_importa_drills_ni_export():
    source = inspect.getsource(readiness_validator_module)
    assert "src.export" not in source
    assert "src.etl" not in source
    assert 'module_id == "drills"' not in source
    assert "simulacros" not in source


def test_operacion_desconocida_lanza_error_de_configuracion(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(_widget_definition())
    request = _request(manifest, registry, operation="no_es_una_operacion")
    with pytest.raises(UnknownReadinessOperationError):
        WorkspaceReadinessValidator().assess(request)


def test_project_id_no_coincide_con_manifest_lanza_error(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(_widget_definition())
    request = ReadinessRequest(
        project_id="otro_proyecto", module_id="widget", operation="sample",
        manifest=manifest, registry=registry, resolver=_resolver(manifest),
    )
    with pytest.raises(ReadinessRequestError):
        WorkspaceReadinessValidator().assess(request)


# ---------------------------------------------------------------------------
# ModuleImplementationCheck
# ---------------------------------------------------------------------------

def test_modulo_desconocido_por_software_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(None)
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert [i.code for i in assessment.blockers] == ["MODULE_UNKNOWN"]
    assert assessment.checks == ("ModuleImplementationCheck", "ProjectModuleDeclarationCheck")


def test_modulo_experimental_es_ejecutable_y_no_bloquea_por_status(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition(status=ModuleImplementationStatus.EXPERIMENTAL))
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert not any(i.code in ("MODULE_UNKNOWN", "MODULE_NOT_EXECUTABLE") for i in assessment.issues)


def test_modulo_planned_no_es_ejecutable_bloquea_distinto_de_artefacto_ausente(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    definition = ModuleDefinition(
        module_id="widget", display_name="Widget", version="0.1.0",
        status=ModuleImplementationStatus.PLANNED,
        capabilities=ModuleCapabilities(frozenset()),
    )
    registry = _registry(definition)
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert assessment.status == ReadinessStatus.BLOCKED
    codes = [i.code for i in assessment.blockers]
    assert codes == ["MODULE_NOT_EXECUTABLE"]
    assert "ARTIFACT_MISSING" not in codes


# ---------------------------------------------------------------------------
# ProjectModuleDeclarationCheck
# ---------------------------------------------------------------------------

def test_modulo_no_declarado_en_el_proyecto_bloquea(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {"otro_modulo": {"display_name": "Otro", "enabled": True, "status": "ready", "artifacts": {}}},
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert [i.code for i in assessment.blockers] == ["MODULE_NOT_DECLARED_IN_PROJECT"]


def test_modulo_declarado_pero_software_no_lo_implementa_es_distinto_de_no_declarado(tmp_path, monkeypatch):
    """Fase 8E: declarado en el proyecto, pero el software ni siquiera lo
    conoce -- MODULE_UNKNOWN, nunca MODULE_NOT_DECLARED_IN_PROJECT."""
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(None)
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert [i.code for i in assessment.blockers] == ["MODULE_UNKNOWN"]


def test_modulo_deshabilitado_en_el_proyecto_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, enabled=False)
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert [i.code for i in assessment.blockers] == ["MODULE_DISABLED"]


# ---------------------------------------------------------------------------
# CapabilityCheck
# ---------------------------------------------------------------------------

def test_capacidad_ausente_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(_widget_definition(capabilities=frozenset({ModuleCapability.EXPORT})))
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    codes = {i.code for i in assessment.blockers}
    assert "CAPABILITY_UNSUPPORTED" in codes


def test_modo_no_soportado_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(_widget_definition(supported_modes=frozenset({"sample"})))
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="full"))
    codes = {i.code for i in assessment.blockers}
    assert "MODE_UNSUPPORTED" in codes


def test_capacidad_presente_no_genera_issue(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch)
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert not any(i.code in ("CAPABILITY_UNSUPPORTED", "MODE_UNSUPPORTED") for i in assessment.issues)


# ---------------------------------------------------------------------------
# ArtifactDeclarationCheck / ArtifactStatusCheck
# ---------------------------------------------------------------------------

def test_required_kinds_se_limita_a_lo_declarado_en_el_manifest(tmp_path, monkeypatch):
    """`required_for_sample` solo puede vivir dentro de un ArtifactSpec ya
    declarado -- no existe un estado runtime de "obligatorio pero no
    declarado en absoluto" (garantizado por el esquema del manifest, ver
    docstring de ArtifactDeclarationCheck)."""
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.required_artifacts == ("sql",)
    assert assessment.status != ReadinessStatus.BLOCKED


def test_artefacto_declarado_missing_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "missing", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "ARTIFACT_MISSING" and i.artifact_type == "sql" for i in assessment.blockers)


def test_artefacto_opcional_missing_solo_genera_warning(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
        "etl": {"path": None, "status": "missing"},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(i.code == "ARTIFACT_OPTIONAL_MISSING" and i.artifact_type == "etl" for i in assessment.warnings)


def test_artefacto_deprecated_genera_warning_no_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": "x.sql", "status": "deprecated", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(i.code == "ARTIFACT_DEPRECATED" for i in assessment.warnings)


def test_artefacto_not_applicable_opcional_genera_info(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
        "catalogs": {"path": None, "status": "not_applicable"},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert any(i.code == "ARTIFACT_NOT_APPLICABLE_INFO" for i in assessment.informational)
    assert assessment.status != ReadinessStatus.BLOCKED


def test_software_expects_undeclared_es_warning_no_blocker(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition(required_artifact_types=frozenset({"sql", "mapping"})))
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(
        i.code == "ARTIFACT_SOFTWARE_EXPECTS_UNDECLARED" and i.artifact_type == "mapping"
        for i in assessment.warnings
    )


def test_artefacto_present_sin_path_no_bloquea_y_genera_info(tmp_path, monkeypatch):
    """Caso real de Drills: sql/mapping declarados status=present, path=None
    (git-tracked, fuera del workspace externo)."""
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "source": "git:x.sql", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status != ReadinessStatus.BLOCKED
    assert any(i.code == "ARTIFACT_PRESENT_NOT_PATH_RESOLVABLE" for i in assessment.informational)


def test_status_optional_con_required_flag_solo_genera_warning(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "optional", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.READY_WITH_WARNINGS
    assert any(i.code == "ARTIFACT_OPTIONAL_DESPITE_REQUIRED" for i in assessment.warnings)


# ---------------------------------------------------------------------------
# ResourceResolutionCheck / PhysicalExistenceCheck
# ---------------------------------------------------------------------------

def test_ruta_declarada_se_resuelve_dentro_del_workspace(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert len(assessment.resolved_resources) == 1
    resolved = assessment.resolved_resources[0]
    expected = (tmp_path / "projects" / "moeve" / "CSV_Enablon_Template" / "Widget.csv").resolve()
    assert resolved.resolved_path == expected


def test_archivo_requerido_presente_no_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    real_dir = tmp_path / "projects" / "moeve" / "CSV_Enablon_Template"
    real_dir.mkdir(parents=True)
    (real_dir / "Widget.csv").write_text("x", encoding="utf-8")
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", require_physical_files=True)
    )
    assert assessment.status != ReadinessStatus.BLOCKED
    assert not assessment.missing_resources


def test_archivo_requerido_inexistente_con_require_files_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", require_physical_files=True)
    )
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "PHYSICAL_FILE_MISSING" for i in assessment.blockers)
    assert "template_csv" in assessment.missing_resources


def test_archivo_opcional_inexistente_con_require_files_no_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
        "template_csv": {"path": "Widget.csv", "status": "present"},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", require_physical_files=True)
    )
    assert assessment.status != ReadinessStatus.BLOCKED
    assert any(i.code == "PHYSICAL_FILE_MISSING_OPTIONAL" for i in assessment.warnings)


def test_sin_require_files_no_se_comprueba_existencia_fisica(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status != ReadinessStatus.BLOCKED
    assert "PhysicalExistenceCheck" in assessment.checks
    assert not any(i.code.startswith("PHYSICAL_FILE_MISSING") for i in assessment.issues)


def test_output_generado_no_exige_existencia_previa(tmp_path, monkeypatch):
    manifest = _manifest(
        tmp_path, monkeypatch,
        artifacts={
            "sql": {"path": None, "status": "present", "required_for_sample": True},
        },
        contracts={"emf": {"generated": True, "output_pattern": "{module}_{execution_id}.csv"}},
    )
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", require_physical_files=True)
    )
    assert assessment.status != ReadinessStatus.BLOCKED


# ---------------------------------------------------------------------------
# ContractCheck / comparison
# ---------------------------------------------------------------------------

def test_comparison_sin_operational_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "operational_csv": {"path": None, "status": "missing", "contract_role": "project"},
    }, contracts={"project": {"artifact": "operational_csv"}})
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="comparison"))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "ARTIFACT_MISSING" and i.artifact_type == "operational_csv" for i in assessment.blockers)


def test_comparison_con_operational_presente_no_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "operational_csv": {
            "path": "Widget.csv", "status": "present",
            "contract_role": "project", "required_for_comparison": True,
        },
    }, contracts={"project": {"artifact": "operational_csv"}})
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="comparison"))
    assert assessment.status != ReadinessStatus.BLOCKED


def test_comparison_sin_contrato_de_proyecto_declarado_bloquea(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={})
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="comparison"))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "PROJECT_CONTRACT_MISSING" for i in assessment.blockers)


def test_sample_no_bloquea_por_template_ni_operational_ausentes(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
        "template_csv": {"path": None, "status": "missing", "contract_role": "platform"},
        "operational_csv": {"path": None, "status": "missing", "contract_role": "project"},
        "etl": {"path": None, "status": "missing"},
    }, contracts={"platform": {"artifact": "template_csv"}, "project": {"artifact": "operational_csv"}})
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status in (ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS)
    assert not any(i.severity == ReadinessSeverity.BLOCKER for i in assessment.issues)


def test_contract_artifact_no_marcado_required_genera_warning(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "operational_csv": {"path": "Widget.csv", "status": "present", "contract_role": "project"},
    }, contracts={"project": {"artifact": "operational_csv"}})
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="comparison"))
    assert any(i.code == "CONTRACT_ARTIFACT_NOT_MARKED_REQUIRED" for i in assessment.warnings)


# ---------------------------------------------------------------------------
# Rutas inseguras
# ---------------------------------------------------------------------------

def test_ruta_con_escape_es_rechazada_al_cargar_el_manifest(tmp_path, monkeypatch):
    """Defensa en profundidad: un `..` en `path` ya es rechazado por el
    propio esquema del manifest (`ManifestSchemaError`), antes de que este
    validador (o `ResourceResolver`) lleguen siquiera a evaluarlo."""
    from src.core.workspace_manifest import ManifestSchemaError

    with pytest.raises(ManifestSchemaError):
        _manifest(tmp_path, monkeypatch, artifacts={
            "template_csv": {"path": "../../escape.csv", "status": "present", "required_for_sample": True},
        })


def test_error_de_resolucion_del_resolver_se_convierte_en_blocker(tmp_path, monkeypatch):
    """Si `ResourceResolver` no puede resolver un recurso declarado (p. ej.
    la categoría del artefacto no está configurada en el DataWorkspace),
    ese fallo se convierte en un `ReadinessIssue` BLOCKER -- nunca se deja
    escapar la excepción del resolver sin traducir."""
    monkeypatch.setenv(ENV_VAR, str(tmp_path))
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    ws_config = _ws_config()
    del ws_config["projects"]["moeve"]["categories"]["csv_enablon_template"]
    resolver = ResourceResolver(manifest, DataWorkspace(ws_config))
    request = ReadinessRequest(
        project_id="moeve", module_id="widget", operation="sample",
        manifest=manifest, registry=registry, resolver=resolver,
    )
    assessment = WorkspaceReadinessValidator().assess(request)
    assert assessment.status == ReadinessStatus.BLOCKED
    assert any(i.code == "RESOURCE_RESOLUTION_ERROR" for i in assessment.blockers)


# ---------------------------------------------------------------------------
# Agregación de estado
# ---------------------------------------------------------------------------

def test_sin_issues_es_ready(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.READY
    assert not assessment.blockers
    assert not assessment.warnings


def test_un_blocker_domina_sobre_warnings(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "missing", "required_for_sample": True},
        "etl": {"path": None, "status": "missing"},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.status == ReadinessStatus.BLOCKED
    assert assessment.blockers and assessment.warnings


def test_strict_escala_warnings_a_blocked(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
        "etl": {"path": None, "status": "missing"},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", strict=True)
    )
    assert assessment.status == ReadinessStatus.BLOCKED
    assert not assessment.blockers  # el bloqueo viene de strict, no de un blocker real
    assert assessment.warnings


def test_orden_de_checks_es_deterministico(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert assessment.checks == (
        "ModuleImplementationCheck",
        "ProjectModuleDeclarationCheck",
        "CapabilityCheck",
        "ArtifactDeclarationCheck",
        "ArtifactStatusCheck",
        "ResourceResolutionCheck",
        "PhysicalExistenceCheck",
        "ContractCheck",
        "SecurityCheck",
    )


def test_issues_deduplicados_por_codigo_y_artefacto(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "missing", "required_for_sample": True},
    })
    registry = _registry(_widget_definition(required_artifact_types=frozenset({"sql"})))
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    codes = [i.code for i in assessment.issues if i.artifact_type == "sql"]
    assert len(codes) == len(set(codes))


# ---------------------------------------------------------------------------
# SecurityCheck / SQL Execution Guard -- nunca cambia de estado
# ---------------------------------------------------------------------------

def test_readiness_no_llama_a_grant_ni_revoke_del_guard():
    """Análisis AST (no de texto -- el docstring del módulo menciona
    'grant()'/'revoke()' en prosa) -- ninguna llamada real a
    `sql_execution_guard.grant`/`revoke`/`get_engine` en todo el fichero."""
    import ast

    tree = ast.parse(inspect.getsource(readiness_validator_module))
    forbidden_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"grant", "revoke", "get_engine"}:
            forbidden_calls.append(func.attr)
        elif isinstance(func, ast.Name) and func.id == "get_engine":
            forbidden_calls.append(func.id)
    assert forbidden_calls == []


def test_readiness_no_cambia_el_estado_del_guard(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assert sql_execution_guard.is_authorized() is False
    WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert sql_execution_guard.is_authorized() is False


def test_security_check_incluye_nota_informativa_de_autorizacion(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "sql": {"path": None, "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    assessment = WorkspaceReadinessValidator().assess(_request(manifest, registry, operation="sample"))
    assert any(i.code == "SQL_AUTHORIZATION_INFO" for i in assessment.informational)


# ---------------------------------------------------------------------------
# No side effects de filesystem
# ---------------------------------------------------------------------------

def test_readiness_no_crea_directorios_ni_archivos(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, monkeypatch, artifacts={
        "template_csv": {"path": "Widget.csv", "status": "present", "required_for_sample": True},
    })
    registry = _registry(_widget_definition())
    WorkspaceReadinessValidator().assess(
        _request(manifest, registry, operation="sample", require_physical_files=True)
    )
    assert list(tmp_path.rglob("*")) == []
