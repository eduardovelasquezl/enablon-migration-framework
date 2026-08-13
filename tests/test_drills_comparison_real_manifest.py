"""Tests del comparison de Drills conectado a un `WorkspaceManifest` REAL
(Sprint 9.2) -- en vez del manifest sintético mínimo hardcodeado
(`_build_drills_comparison_manifest`, que sigue existiendo como FALLBACK
para cuando no se pasa ninguno, ver su docstring).

Ninguno de estos tests usa SQL real ni el `workspace.yaml` real de Moeve --
todo manifest aquí es sintético, construido con
`WorkspaceManifestLoader.load_from_dict`, bajo `tmp_path`.

Nota sobre `project.id`: se usa "moeve" en todos los manifests sintéticos
de este archivo -- NO porque el comportamiento sea específico de Moeve,
sino porque `DataWorkspace` (capa por debajo de `ResourceResolver`, sin
cambios en este incremento) exige que el proyecto esté declarado en
`config/data_workspace.yaml` -> `projects` (hoy solo declara "moeve";
restricción preexistente de Sprint 7, no de este incremento). La prueba de
que la resolución no depende de ningún NOMBRE DE FICHERO concreto de
Moeve se hace con nombres de fichero arbitrarios, distintos de
"Drills.csv" -- ver `_synthetic_manifest`.

Ejecutar con: pytest tests/test_drills_comparison_real_manifest.py -v
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

import src.export.prototype.drills.extractor as extractor_mod
import src.export.prototype.drills.pipeline as pipeline_mod
from src.cli import cli
from src.core.workspace_manifest import ManifestSchemaError, WorkspaceManifestLoader
from src.export.prototype.drills.pipeline import _resolve_comparison_csv_path

_PROJECT_ID = "moeve"  # único proyecto declarado en config/data_workspace.yaml -- ver nota de módulo


def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDSimulacro": [440], "IDTipo": [365], "Fecha": ["08/03/2010"], "Hora": ["12:30"],
        "IDLetra": [258], "IDUnidadOrg": [278], "Estado": ["Terminado"],
    })


def _synthetic_manifest(*, artifact_path: str | None, status: str = "present"):
    """Manifest mínimo con un nombre de fichero ARBITRARIO -- deliberadamente
    distinto de "Drills.csv" (el que fabrica `_build_drills_comparison_manifest`)
    para demostrar que la resolución ya no depende de ese nombre."""
    return WorkspaceManifestLoader.load_from_dict({
        "project": {"id": _PROJECT_ID, "display_name": "Moeve", "status": "active", "version": "1.0"},
        "workspace": {"schema_version": "1.0", "project_root": f"projects/{_PROJECT_ID}"},
        "modules": {
            "drills": {
                "display_name": "Drills", "enabled": True, "status": "in_progress",
                "canonical_name": "Drills",
                "artifacts": {
                    "operational_csv": {
                        "path": artifact_path,
                        "status": status,
                        "contract_role": "project",
                        "required_for_comparison": True,
                        "description": "test",
                    },
                },
            },
        },
    })


# --------------------------------------------------------------------------
# 1-2-4: resuelve desde WorkspaceManifest real, con nombre distinto de Drills.csv
# --------------------------------------------------------------------------

def test_resuelve_operational_csv_declarado_por_manifest_real(tmp_path, monkeypatch):
    category_dir = tmp_path / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    real_file = category_dir / "Nombre Totalmente Distinto De Drills.csv"
    real_file.write_text("x", encoding="utf-8")
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))

    manifest = _synthetic_manifest(artifact_path="Nombre Totalmente Distinto De Drills.csv")
    resolved = _resolve_comparison_csv_path(manifest)

    assert resolved == real_file.resolve()


def test_sin_manifest_real_no_recoge_un_fichero_de_nombre_distinto(tmp_path, monkeypatch):
    """`workspace_manifest=None` sigue usando el manifest sintético de
    siempre, que solo declara "Drills.csv" -- la presencia física de OTRO
    fichero con un nombre distinto no lo hace elegible. Confirma que ambas
    rutas de resolución (con/sin manifest real) son independientes, sin
    mezcla ni fallback cruzado."""
    category_dir = tmp_path / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    (category_dir / "Nombre Totalmente Distinto De Drills.csv").write_text("x", encoding="utf-8")
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))

    assert _resolve_comparison_csv_path(None) is None  # el sintético solo conoce "Drills.csv"


def test_regresion_simulacros_cce_xlsx_se_resuelve_sin_que_python_conozca_el_nombre(tmp_path, monkeypatch):
    """Regresión explícita pedida en Sprint 9.2: un manifest que declare
    `operational_csv.path = "Simulacros CCE.xlsx"` debe hacer que la
    resolución encuentre ESE recurso -- y el propio código de resolución
    (`pipeline.py`) no debe mencionar ese nombre de fichero en absoluto."""
    category_dir = tmp_path / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    real_file = category_dir / "Simulacros CCE.xlsx"
    real_file.write_bytes(b"PK\x03\x04")  # cabecera zip minima -- no se lee, solo se resuelve la ruta
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))

    manifest = _synthetic_manifest(artifact_path="Simulacros CCE.xlsx")
    resolved = _resolve_comparison_csv_path(manifest)

    assert resolved == real_file.resolve()

    source = inspect.getsource(pipeline_mod)
    assert "Simulacros CCE" not in source


# --------------------------------------------------------------------------
# 6-7-8: missing / ambiguous / path traversal
# --------------------------------------------------------------------------

def test_artifact_missing_en_manifest_real_devuelve_none_explicito(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    manifest = _synthetic_manifest(artifact_path=None, status="missing")
    assert _resolve_comparison_csv_path(manifest) is None


def test_multiples_candidatos_fisicos_sin_path_declarado_no_selecciona_ninguno(tmp_path, monkeypatch):
    """Con `path=None` (el módulo no elige un candidato -- mismo patrón que
    `safety_meetings`/`moc` en el workspace.yaml real de Moeve, que dejan
    varios candidatos sin resolver en vez de adivinar uno), la presencia de
    VARIOS ficheros físicos en la carpeta no hace que se seleccione ninguno
    -- nunca hay glob/listado de directorio en el camino de resolución."""
    category_dir = tmp_path / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    (category_dir / "Candidato1.csv").write_text("x", encoding="utf-8")
    (category_dir / "Candidato2.csv").write_text("x", encoding="utf-8")
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))

    manifest = _synthetic_manifest(artifact_path=None, status="missing")
    assert _resolve_comparison_csv_path(manifest) is None

    source = inspect.getsource(pipeline_mod)
    assert "glob" not in source.lower()


def test_path_traversal_rechazado_al_cargar_el_manifest():
    """El path traversal se bloquea INCLUSO ANTES de intentar resolver --
    `ArtifactSpec.__post_init__` (`src/core/workspace_manifest.py`) valida
    la forma de cada `path` a nivel de esquema (`_validate_relative_safe_path`)
    y rechaza cualquier componente '..' al cargar el manifest, no solo al
    resolverlo contra el workspace externo (defensa en profundidad: el
    mismo caso también está cubierto, por separado, en `DataWorkspace.resolve`,
    ver `PathEscapesWorkspaceError` en `src/core/data_workspace.py`)."""
    with pytest.raises(ManifestSchemaError, match=r"\.\."):
        _synthetic_manifest(artifact_path="../../etc/passwd")


def test_nunca_cae_a_inputs_con_manifest_real(monkeypatch):
    monkeypatch.delenv("EMF_DATA_ROOT", raising=False)
    source = inspect.getsource(pipeline_mod._resolve_comparison_csv_path)
    assert "_incoming_claude_web" not in source
    assert "inputs/" not in source


# --------------------------------------------------------------------------
# 3: extensión .csv soportada end-to-end; .xlsx -> resultado explícito, no crash
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_run_query(monkeypatch):
    fake_df = _fake_dataframe()
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: fake_df.copy())
    yield


def test_pipeline_run_con_manifest_real_y_csv_genera_comparison_report(tmp_path, monkeypatch):
    data_root = tmp_path / "data_root"
    category_dir = data_root / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    historical_file = category_dir / "Nombre Distinto.csv"
    historical_file.write_bytes(
        b"\xff\xfe" + (
            "CS_Typology\tReference\tStartingDate\tCS_HistoricalOriginID\tCS_Letter\t"
            "CS_ImpactedEntities\tCS_WorkflowStatus\tCS_HistoricalDataOrigin\r\n"
        ).encode("utf-16-le")
    )
    monkeypatch.setenv("EMF_DATA_ROOT", str(data_root))

    manifest = _synthetic_manifest(artifact_path="Nombre Distinto.csv")
    output_root = tmp_path / "output"
    result = pipeline_mod.run(mode="sample", limit=10, output_root=output_root, workspace_manifest=manifest)

    assert result.comparison_report_path is not None
    assert result.comparison_report_path.is_file()
    report = yaml.safe_load(result.comparison_report_path.read_text(encoding="utf-8"))
    assert "schema" in report  # sí se leyó contenido -- comparación real


def test_pipeline_run_con_manifest_real_y_xlsx_no_crashea_da_resultado_explicito(tmp_path, monkeypatch):
    """Extensión .xlsx: el comparador actual solo sabe leer CSV (Sprint
    9.2, hallazgo documentado) -- debe dar un resultado EXPLÍCITO de
    "no soportado", nunca intentar parsear el binario como texto CSV ni
    lanzar una excepción sin capturar."""
    data_root = tmp_path / "data_root"
    category_dir = data_root / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    historical_file = category_dir / "Operational.xlsx"
    historical_file.write_bytes(b"PK\x03\x04fake-not-a-real-xlsx-payload")
    monkeypatch.setenv("EMF_DATA_ROOT", str(data_root))

    manifest = _synthetic_manifest(artifact_path="Operational.xlsx")
    output_root = tmp_path / "output"
    result = pipeline_mod.run(mode="sample", limit=10, output_root=output_root, workspace_manifest=manifest)

    assert result.comparison_report_path is not None  # se genera igualmente (no se aborta el pipeline)
    report = yaml.safe_load(result.comparison_report_path.read_text(encoding="utf-8"))
    assert "schema" not in report  # nunca se intentó leer el contenido
    assert any("no soportada" in msg.lower() for msg in report["limitations"])


# --------------------------------------------------------------------------
# CLI end-to-end: --manifest realmente llega hasta el pipeline
# --------------------------------------------------------------------------

def test_cli_run_con_manifest_genera_comparison_report(tmp_path, monkeypatch):
    data_root = tmp_path / "data_root"
    category_dir = data_root / "projects" / _PROJECT_ID / "CSV_Enablon_Operational"
    category_dir.mkdir(parents=True)
    (category_dir / "Nombre Distinto.csv").write_bytes(
        b"\xff\xfe" + (
            "CS_Typology\tReference\tStartingDate\tCS_HistoricalOriginID\tCS_Letter\t"
            "CS_ImpactedEntities\tCS_WorkflowStatus\tCS_HistoricalDataOrigin\r\n"
        ).encode("utf-16-le")
    )
    monkeypatch.setenv("EMF_DATA_ROOT", str(data_root))

    manifest_yaml = tmp_path / "workspace.yaml"
    manifest_yaml.write_text(
        f"project:\n  id: {_PROJECT_ID}\n  display_name: Moeve\n  status: active\n  version: '1.0'\n"
        f"workspace:\n  schema_version: '1.0'\n  project_root: projects/{_PROJECT_ID}\n"
        "modules:\n  drills:\n    display_name: Drills\n    enabled: true\n"
        "    status: in_progress\n    canonical_name: Drills\n    artifacts:\n"
        "      operational_csv:\n        path: \"Nombre Distinto.csv\"\n"
        "        status: present\n        contract_role: project\n"
        "        required_for_comparison: true\n"
        "        description: test\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "cli_output"
    result = CliRunner().invoke(cli, [
        "run", "--project", _PROJECT_ID, "--object", "drills", "--mode", "sample",
        "--limit", "5", "--output-dir", str(output_dir), "--allow-real-sql",
        "--manifest", str(manifest_yaml),
    ])

    assert result.exit_code == 0, result.output
    generated_dirs = list(output_dir.iterdir())
    assert len(generated_dirs) == 1
    assert (generated_dirs[0] / "comparison_report.yaml").is_file()
