"""Tests de integración LOCAL (sin SQL Server real, sin datos reales) de
la resolución del CSV histórico de Drills contra el workspace externo de
datos (Sprint 7 -- Workspace Separation, Fase 9).

Ninguna dependencia de `C:\\Users\\EduardoVelásquez`, de SQL Server, ni
escritura sobre datos reales -- todo bajo `tmp_path` de pytest.

Ejecutar con: pytest tests/test_drills_data_workspace_integration.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

import src.export.prototype.drills.extractor as extractor_mod
import src.export.prototype.drills.pipeline as pipeline_mod
from src.export.prototype.drills.pipeline import (
    HISTORICAL_CSV_CATEGORY,
    HISTORICAL_CSV_PROJECT,
    HISTORICAL_CSV_RELATIVE_PATH,
    _resolve_historical_csv_path,
)


def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDSimulacro": [440],
        "IDTipo": [365],
        "Fecha": ["08/03/2010"],
        "IDLetra": [258],
        "IDUnidadOrg": [278],
        "Estado": ["Terminado"],
    })


# --------------------------------------------------------------------------
# _resolve_historical_csv_path -- sin romper compatibilidad
# --------------------------------------------------------------------------

def test_sin_emf_data_root_no_falla_devuelve_none(monkeypatch):
    """Comportamiento sin cambios respecto a antes de Sprint 7: sin
    EMF_DATA_ROOT declarado, la comparación es simplemente omitida --
    nunca un error, nunca un fallback a datos dentro del repositorio."""
    monkeypatch.delenv("EMF_DATA_ROOT", raising=False)
    assert _resolve_historical_csv_path() is None


def test_con_emf_data_root_pero_sin_el_fichero_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))
    assert _resolve_historical_csv_path() is None


def test_con_emf_data_root_y_el_fichero_presente_se_resuelve(tmp_path, monkeypatch):
    category_dir = tmp_path / "projects" / HISTORICAL_CSV_PROJECT / "CSV_Enablon"
    category_dir.mkdir(parents=True)
    historical_file = category_dir / HISTORICAL_CSV_RELATIVE_PATH
    historical_file.write_text(
        "CS_Typology\tReference\tStartingDate\tCS_HistoricalOriginID\tCS_Letter\t"
        "CS_ImpactedEntities\tCS_WorkflowStatus\tCS_HistoricalDataOrigin\r\n",
        encoding="utf-16-le",
    )
    monkeypatch.setenv("EMF_DATA_ROOT", str(tmp_path))

    resolved = _resolve_historical_csv_path()
    assert resolved == historical_file.resolve()
    assert resolved.is_file()


def test_nunca_cae_a_inputs_incoming_claude_web(monkeypatch):
    """La ruta legada (inputs/_incoming_claude_web/...) ya no existe en el
    repositorio -- confirma que _resolve_historical_csv_path no la
    referencia en absoluto (ver el propio código: solo usa DataWorkspace)."""
    monkeypatch.delenv("EMF_DATA_ROOT", raising=False)
    import inspect

    source = inspect.getsource(_resolve_historical_csv_path)
    assert "_incoming_claude_web" not in source


# --------------------------------------------------------------------------
# Pipeline completo: con y sin comparison_report, sin SQL real
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_run_query(monkeypatch):
    fake_df = _fake_dataframe()
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: fake_df.copy())
    yield


def test_pipeline_sin_workspace_externo_no_genera_comparison_report(tmp_path, monkeypatch):
    monkeypatch.delenv("EMF_DATA_ROOT", raising=False)
    result = pipeline_mod.run(mode="sample", limit=10, output_root=tmp_path)
    assert result.comparison_report_path is None
    assert result.csv_path.is_file()  # el resto del pipeline no se ve afectado


def test_pipeline_con_workspace_externo_genera_comparison_report(tmp_path, monkeypatch):
    data_root = tmp_path / "data_root"
    category_dir = data_root / "projects" / HISTORICAL_CSV_PROJECT / "CSV_Enablon"
    category_dir.mkdir(parents=True)
    historical_file = category_dir / HISTORICAL_CSV_RELATIVE_PATH
    # CSV histórico mínimo, con la clave de correlación esperada por
    # comparison.py (CS_HistoricalOriginID) -- basta con la cabecera para
    # que se genere el informe (0 filas coincidentes es un resultado válido).
    # UTF-16LE CON BOM + tabulador: mismo formato que el CSV real de
    # Drills ya documentado en comparison.py (detect_historical_csv lo
    # detecta por los dos primeros bytes -- sin BOM se leería como UTF-8
    # y rompería el parseo).
    historical_file.write_bytes(
        b"\xff\xfe" + (
            "CS_Typology\tReference\tStartingDate\tCS_HistoricalOriginID\tCS_Letter\t"
            "CS_ImpactedEntities\tCS_WorkflowStatus\tCS_HistoricalDataOrigin\r\n"
        ).encode("utf-16-le")
    )
    monkeypatch.setenv("EMF_DATA_ROOT", str(data_root))

    output_root = tmp_path / "output"
    result = pipeline_mod.run(mode="sample", limit=10, output_root=output_root)

    assert result.comparison_report_path is not None
    assert result.comparison_report_path.is_file()
