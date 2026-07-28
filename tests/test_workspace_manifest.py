"""Tests unitarios del Workspace Manifest (Sprint 8.4). Sin datos reales,
sin SQL Server, sin dependencia de ninguna ruta específica de un equipo
concreto -- todo sobre `tmp_path` y el ejemplo versionado
`examples/workspace/workspace.example.yaml`.

Ejecutar con: pytest tests/test_workspace_manifest.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.data_workspace import DataWorkspace
from src.core.workspace_manifest import (
    ArtifactStatus,
    ManifestSchemaError,
    ModuleStatus,
    WorkspaceManifestError,
    WorkspaceManifestLoader,
    resolve_artifact_path,
    validate_manifest,
)

EXAMPLE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "examples" / "workspace" / "workspace.example.yaml"


def _minimal_raw(**overrides) -> dict:
    """Manifest mínimo válido -- cada test parte de esto y sobreescribe
    solo lo que necesita probar."""
    raw = {
        "project": {"id": "moeve", "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": "projects/moeve"},
        "modules": {
            "drills": {
                "display_name": "Drills",
                "enabled": True,
                "status": "ready",
            },
        },
    }
    raw.update(overrides)
    return raw


def _ws_config() -> dict:
    return {
        "root_env": "EMF_DATA_ROOT_TEST_ONLY",
        "projects": {
            "moeve": {
                "base": "projects/moeve",
                "categories": {
                    "etl": "ETL",
                    "csv_enablon_template": "CSV_Enablon_Template",
                    "csv_enablon_operational": "CSV_Enablon_Operational",
                    "mappings": "Mappings",
                    "sql": "SQL",
                },
            },
        },
    }


# --------------------------------------------------------------------------
# Carga: manifest válido / claves obligatorias ausentes
# --------------------------------------------------------------------------

def test_manifest_minimo_valido_carga_correctamente():
    manifest = WorkspaceManifestLoader.load_from_dict(_minimal_raw())
    assert manifest.project.id == "moeve"
    assert manifest.module_ids() == ("drills",)
    assert manifest.get_module("drills").status == "ready"


def test_project_id_ausente_lanza_error():
    raw = _minimal_raw()
    del raw["project"]["id"]
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_schema_version_ausente_lanza_error():
    raw = _minimal_raw()
    del raw["workspace"]["schema_version"]
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_sin_modulos_lanza_error():
    raw = _minimal_raw(modules={})
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


# --------------------------------------------------------------------------
# Artefactos: kind desconocido, status inválido, paths inseguros
# --------------------------------------------------------------------------

def test_artefacto_de_kind_desconocido_lanza_error():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"unknown_kind": {"path": "x.csv"}}
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_artefacto_con_status_invalido_lanza_error():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"sql": {"status": "not_a_real_status"}}
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_modulo_con_status_invalido_lanza_error():
    raw = _minimal_raw()
    raw["modules"]["drills"]["status"] = "not_a_real_status"
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


@pytest.mark.parametrize("bad_path", [
    "C:\\Users\\someone\\Drills.csv",
    "/etc/passwd",
    "../../etc/passwd",
    "Mappings/../../../etc/passwd",
])
def test_path_absoluto_o_con_escape_lanza_error(bad_path):
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"sql": {"path": bad_path}}
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_artefacto_obligatorio_no_puede_ser_not_applicable():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {
        "sql": {"required_for_sample": True, "status": ArtifactStatus.NOT_APPLICABLE},
    }
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


# --------------------------------------------------------------------------
# Contratos: referencia a artefacto inexistente
# --------------------------------------------------------------------------

def test_contrato_que_referencia_artefacto_inexistente_lanza_error():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"sql": {"status": "present"}}
    raw["modules"]["drills"]["contracts"] = {"platform": {"artifact": "template_csv"}}
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_contrato_que_referencia_artefacto_existente_carga_bien():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"template_csv": {"status": "missing"}}
    raw["modules"]["drills"]["contracts"] = {"platform": {"artifact": "template_csv"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    assert manifest.get_module("drills").contracts.platform_artifact == "template_csv"


# --------------------------------------------------------------------------
# Módulo deprecated habilitado
# --------------------------------------------------------------------------

def test_modulo_deprecated_habilitado_sin_notas_lanza_error():
    raw = _minimal_raw()
    raw["modules"]["drills"]["status"] = ModuleStatus.DEPRECATED
    raw["modules"]["drills"]["enabled"] = True
    with pytest.raises(ManifestSchemaError):
        WorkspaceManifestLoader.load_from_dict(raw)


def test_modulo_deprecated_habilitado_con_justificacion_explicita_carga_bien():
    raw = _minimal_raw()
    raw["modules"]["drills"]["status"] = ModuleStatus.DEPRECATED
    raw["modules"]["drills"]["enabled"] = True
    raw["modules"]["drills"]["notes"] = "Se mantiene habilitado temporalmente por decisión explícita de X."
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    assert manifest.get_module("drills").status == ModuleStatus.DEPRECATED


def test_modulo_deprecated_deshabilitado_no_requiere_notas():
    raw = _minimal_raw()
    raw["modules"]["drills"]["status"] = ModuleStatus.DEPRECATED
    raw["modules"]["drills"]["enabled"] = False
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    assert manifest.get_module("drills").enabled is False


# --------------------------------------------------------------------------
# Módulo desconocido
# --------------------------------------------------------------------------

def test_get_module_desconocido_lanza_error_explicito():
    manifest = WorkspaceManifestLoader.load_from_dict(_minimal_raw())
    with pytest.raises(WorkspaceManifestError):
        manifest.get_module("no_existe")


# --------------------------------------------------------------------------
# validate_manifest -- reglas de negocio (lista de violaciones, no excepción)
# --------------------------------------------------------------------------

def test_validate_manifest_manifest_limpio_no_produce_violaciones():
    manifest = WorkspaceManifestLoader.load_from_dict(_minimal_raw())
    assert validate_manifest(manifest) == []


def test_operational_csv_con_nombre_incorrecto_produce_violacion():
    raw = _minimal_raw()
    raw["workspace"]["naming_convention"] = {"operational_csv": "{module}.csv"}
    raw["modules"]["drills"]["canonical_name"] = "Drills"
    raw["modules"]["drills"]["artifacts"] = {"operational_csv": {"path": "drills_final_v2.csv"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    violations = validate_manifest(manifest)
    assert len(violations) == 1
    assert "operational_csv" in violations[0]


def test_operational_csv_con_nombre_correcto_no_produce_violacion():
    raw = _minimal_raw()
    raw["workspace"]["naming_convention"] = {"operational_csv": "{module}.csv"}
    raw["modules"]["drills"]["canonical_name"] = "Drills"
    raw["modules"]["drills"]["artifacts"] = {"operational_csv": {"path": "Drills.csv"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    assert validate_manifest(manifest) == []


def test_template_csv_preserva_nombre_fuente_sin_violacion():
    raw = _minimal_raw()
    raw["workspace"]["naming_convention"] = {"template_csv": "preserve_source_name"}
    raw["modules"]["drills"]["canonical_name"] = "Drills"
    raw["modules"]["drills"]["artifacts"] = {
        "template_csv": {"path": "Drills-22072026-41.csv", "contract_role": "platform"},
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    assert validate_manifest(manifest) == []


def test_dos_modulos_con_mismo_canonical_name_produce_violacion():
    raw = _minimal_raw()
    raw["modules"]["drills"]["canonical_name"] = "Shared"
    raw["modules"]["otro"] = {"display_name": "Otro", "enabled": False, "status": "planned", "canonical_name": "Shared"}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    violations = validate_manifest(manifest)
    assert any("canonical_name" in v for v in violations)


def test_ruta_dentro_de_carpeta_deprecated_produce_violacion():
    raw = _minimal_raw()
    raw["workspace"]["deprecated_paths"] = ["CSV_Enablon"]
    raw["modules"]["drills"]["artifacts"] = {
        "operational_csv": {"path": "CSV_Enablon/Drills.csv"},
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    violations = validate_manifest(manifest)
    assert any("deprecated" in v for v in violations)


def test_dos_modulos_con_misma_ruta_de_artefacto_produce_violacion():
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"operational_csv": {"path": "Compartido.csv"}}
    raw["modules"]["otro"] = {
        "display_name": "Otro", "enabled": False, "status": "planned",
        "artifacts": {"operational_csv": {"path": "Compartido.csv"}},
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    violations = validate_manifest(manifest)
    assert any("misma ruta" in v for v in violations)


# --------------------------------------------------------------------------
# Integración con DataWorkspace (Fase 6) -- reutiliza, no duplica
# --------------------------------------------------------------------------

def test_resolve_artifact_path_integra_con_data_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"operational_csv": {"path": "Drills.csv"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    ws = DataWorkspace(_ws_config())

    resolved = resolve_artifact_path(manifest, "drills", "operational_csv", ws, required=False)
    expected = (tmp_path / "projects" / "moeve" / "CSV_Enablon_Operational" / "Drills.csv").resolve()
    assert resolved == expected
    # No se crea nada -- ni la carpeta de categoria ni el archivo.
    assert not (tmp_path / "projects").exists()


def test_resolve_artifact_path_sin_path_declarado_lanza_error(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    manifest = WorkspaceManifestLoader.load_from_dict(_minimal_raw())
    ws = DataWorkspace(_ws_config())
    with pytest.raises(WorkspaceManifestError):
        resolve_artifact_path(manifest, "drills", "etl", ws)


def test_resolve_artifact_path_reutiliza_proteccion_de_escape_de_data_workspace(tmp_path, monkeypatch):
    """El manifest ya rechaza '..' al cargar (ManifestSchemaError) -- este
    test confirma que, además, DataWorkspace.resolve() (reutilizada, no
    duplicada) también protegería un escape si llegara sin pasar por la
    validación de carga."""
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    ws = DataWorkspace(_ws_config())
    from src.core.data_workspace import PathEscapesWorkspaceError
    with pytest.raises(PathEscapesWorkspaceError):
        ws.resolve(project="moeve", category="sql", relative_path="../../etc/passwd", required=False)


def test_resolve_artifact_path_encuentra_archivo_real_en_workspace_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    real_dir = tmp_path / "projects" / "moeve" / "SQL"
    real_dir.mkdir(parents=True)
    (real_dir / "Drills.sql").write_text("SELECT 1", encoding="utf-8")

    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"sql": {"path": "Drills.sql", "status": "present"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    ws = DataWorkspace(_ws_config())

    resolved = resolve_artifact_path(manifest, "drills", "sql", ws, required=True)
    assert resolved.is_file()
    assert resolved.read_text(encoding="utf-8") == "SELECT 1"


# --------------------------------------------------------------------------
# Unicode y espacios
# --------------------------------------------------------------------------

def test_unicode_y_espacios_en_nombres_y_rutas(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    raw = _minimal_raw()
    raw["project"]["display_name"] = "Moeve España — Migración"
    raw["modules"]["drills"]["display_name"] = "Simulacros (Business Continuity Management)"
    raw["modules"]["drills"]["artifacts"] = {
        "template_csv": {"path": "Histórico Drills 2026 (versión final).csv"},
    }
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    ws = DataWorkspace(_ws_config())
    resolved = resolve_artifact_path(manifest, "drills", "template_csv", ws, required=False)
    assert resolved.name == "Histórico Drills 2026 (versión final).csv"


# --------------------------------------------------------------------------
# Ejemplo Moeve
# --------------------------------------------------------------------------

def test_carga_de_ejemplo_moeve_sin_violaciones():
    manifest = WorkspaceManifestLoader.load_from_path(EXAMPLE_MANIFEST_PATH)
    assert manifest.project.id == "moeve"
    expected_modules = {
        "drills", "safety_meetings", "moc", "bypass",
        "events", "ops", "inspections", "corrective_actions",
    }
    assert set(manifest.module_ids()) == expected_modules
    assert validate_manifest(manifest) == []


def test_ejemplo_moeve_solo_drills_tiene_artefactos_con_status_distinto_de_missing():
    manifest = WorkspaceManifestLoader.load_from_path(EXAMPLE_MANIFEST_PATH)
    for module_id in manifest.module_ids():
        module = manifest.get_module(module_id)
        non_missing = [
            kind for kind, artifact in module.artifacts.items()
            if artifact.status not in (ArtifactStatus.MISSING, ArtifactStatus.NOT_APPLICABLE)
        ]
        if module_id == "drills":
            assert non_missing, "Drills deberia tener al menos un artefacto present"
        else:
            assert non_missing == [], f"{module_id} no deberia tener artefactos present/validated todavia"


# --------------------------------------------------------------------------
# Ausencia de acceso a SQL / creación de carpetas (estructural)
# --------------------------------------------------------------------------

def test_modulo_no_importa_nada_de_src_db_ni_src_export():
    """Verificado por inspección de las sentencias `import` reales del
    propio fichero fuente (no de comentarios/docstrings, que sí pueden
    mencionar esos módulos en prosa) -- el Workspace Manifest es
    infraestructura genérica, no debe acoplarse a SQL ni a ningún objeto
    migrable concreto (mismo criterio ya aplicado a DataWorkspace, ver
    framework-core-v1.md § 4)."""
    import ast

    import src.core.workspace_manifest as wm

    tree = ast.parse(Path(wm.__file__).read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_prefixes = ("src.db", "src.export", "src.etl")
    offending = [m for m in imported_modules if m.startswith(forbidden_prefixes)]
    assert offending == []


def test_cargar_y_validar_no_crea_ninguna_carpeta(tmp_path, monkeypatch):
    """Cargar el ejemplo real de Moeve y validarlo no debe tocar el
    filesystem del workspace en absoluto -- todos sus artefactos tienen
    `path: null` (nada recuperado todavía), así que ni siquiera hay una
    ruta que resolver; el propio acto de cargar/validar no crea nada."""
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    manifest = WorkspaceManifestLoader.load_from_path(EXAMPLE_MANIFEST_PATH)
    validate_manifest(manifest)
    assert list(tmp_path.iterdir()) == []


def test_resolve_artifact_path_no_crea_ninguna_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT_TEST_ONLY", str(tmp_path))
    raw = _minimal_raw()
    raw["modules"]["drills"]["artifacts"] = {"sql": {"path": "Drills.sql"}}
    manifest = WorkspaceManifestLoader.load_from_dict(raw)
    ws = DataWorkspace(_ws_config())
    resolve_artifact_path(manifest, "drills", "sql", ws, required=False)
    assert list(tmp_path.iterdir()) == []
