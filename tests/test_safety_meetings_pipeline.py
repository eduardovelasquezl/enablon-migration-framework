"""Tests de integración de safety_meetings.Group_Meetings (Sprint 9.7) --
SIN SQL real, SIN datos de cliente. Cubre el checklist de la Fase 14 del
encargo: ModuleRegistry, PipelineFactory, Engine Query Stage, filtros,
transformación, validación, output contract, SQL Guard fail-closed, sin
regresión en Drills/Bypass (esta última la confirma la suite completa, no
este archivo).

Ejecutar con: pytest tests/test_safety_meetings_pipeline.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

import src.export.prototype.safety_meetings.extractor as extractor_mod
import src.export.prototype.safety_meetings.pipeline as pipeline_mod
from src.bootstrap.module_registry import build_default_module_registry
from src.cli import cli
from src.core.module_registry import ModuleCapability
from src.db import sql_execution_guard
from src.query.catalog import SAFETY_MEETINGS_FILTER_CATALOG
from src.query.validator import compile_filter_tokens


def _fake_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "IDReunionGrupo": [5303, 5305, 5310],
        "IDCentro": [4, 4, 4],
        "IDUnidadOrg": [278, 278, 278],
        "FaseActual": [4, 2, 1],
        "IDNivel": [256, 257, 371],
        "IDLetra": [258, 259, 373],
        "Fecha": ["18/06/2018 09:59:00", "22/06/2018 13:15:00", "27/06/2018 08:14:00"],
        "Lugar": ["Sala San Roque", None, "Sala Algeciras"],
        "Asistentes": ["Juan, Maria", None, "Pedro"],
        "FechaCreacion": ["2018-06-18", "2018-06-22", "2018-06-27"],
    })


# --------------------------------------------------------------------------
# 1. ModuleRegistry reconoce Safety Meetings -- 2. PipelineFactory lo construye
# --------------------------------------------------------------------------

def test_module_registry_reconoce_safety_meetings():
    registry = build_default_module_registry()
    assert registry.contains("safety_meetings")
    definition = registry.get("safety_meetings")
    assert definition.module_id == "safety_meetings"
    assert definition.canonical_name == "Group_Meetings"
    assert registry.supports("safety_meetings", ModuleCapability.SAMPLE)
    assert registry.supports("safety_meetings", ModuleCapability.FULL)
    assert not registry.supports("safety_meetings", ModuleCapability.EVIDENCE)
    assert not registry.supports("safety_meetings", ModuleCapability.COMPARISON)


def test_pipeline_factory_de_safety_meetings_construye_definicion_y_contexto():
    from src.core.contracts import ExecutionRequest
    from src.core.registry import StageRegistry

    registry = build_default_module_registry()
    factory = registry.get_pipeline_factory("safety_meetings")
    request = ExecutionRequest(project="moeve", object_type="safety_meetings", mode="sample", limit=5)
    definition, context = factory(request, StageRegistry())
    assert definition.name == "safety_meetings"
    assert definition.stages == ("query", "transform_and_export")
    assert context.execution_id


# --------------------------------------------------------------------------
# 3. SQL Guard sigue fail-closed
# --------------------------------------------------------------------------

def test_run_safety_meetings_sin_autorizacion_queda_bloqueado(tmp_path):
    result = CliRunner().invoke(cli, [
        "run", "--project", "moeve", "--object", "safety_meetings", "--mode", "sample",
        "--output-dir", str(tmp_path),
    ])
    assert result.exit_code != 0
    assert "SQL Execution Guard" in result.output
    assert sql_execution_guard.is_authorized() is False


def test_run_safety_meetings_con_autorizacion_y_sql_mockeado_permite_continuar(monkeypatch, tmp_path):
    monkeypatch.setattr(extractor_mod, "run_query", lambda *a, **k: _fake_dataframe())
    result = CliRunner().invoke(cli, [
        "run", "--project", "moeve", "--object", "safety_meetings", "--mode", "sample",
        "--limit", "3", "--output-dir", str(tmp_path), "--allow-real-sql",
    ])
    assert result.exit_code == 0, result.output
    assert "Resultado:" in result.output


# --------------------------------------------------------------------------
# 4. Filtros se compilan correctamente (Query Engine reutilizado)
# --------------------------------------------------------------------------

def test_filtro_historical_origin_id_compila():
    compiled = compile_filter_tokens(("historical_origin_id:eq:5303",), SAFETY_MEETINGS_FILTER_CATALOG)
    assert compiled[0].sql_fragment == "[ITP_REUNION_GRUPO].[IDReunionGrupo] = :filter_1"
    assert compiled[0].parameters == {"filter_1": 5303}


def test_filtro_historical_origin_id_in_list_compila():
    ids = "5303,5305,5310"
    compiled = compile_filter_tokens((f"historical_origin_id:in:{ids}",), SAFETY_MEETINGS_FILTER_CATALOG)
    assert "IN" in compiled[0].sql_fragment.upper()


def test_filtro_campo_desconocido_rechazado():
    from src.query.models import UnknownFilterFieldError
    with pytest.raises(UnknownFilterFieldError):
        compile_filter_tokens(("campo_inventado:eq:1",), SAFETY_MEETINGS_FILTER_CATALOG)


# --------------------------------------------------------------------------
# 5-8. Transformación, validación y output contract (pipeline completo, sin SQL)
# --------------------------------------------------------------------------

def test_pipeline_completo_produce_columnas_esperadas(tmp_path):
    from src.export.prototype.safety_meetings.extractor import ExtractionResult

    extraction = ExtractionResult(
        dataframe=_fake_dataframe(), mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_pipeline", timestamp="20260101T000000Z",
    )
    assert result.csv_path.is_file()
    # utf-8-sig: el Output Contract corregido en Micro-sprint 9.9.1 escribe
    # BOM UTF-8 (config/exports/safety_meetings.yaml -> output.bom: true) --
    # leer con "utf-8" a secas dejaría U+FEFF colgando del primer valor de
    # cabecera.
    header = result.csv_path.read_text(encoding="utf-8-sig").splitlines()[0]
    assert header.split("\t") == pipeline_mod.OUTPUT_COLUMNS

    report = yaml.safe_load(result.validation_report_path.read_text(encoding="utf-8"))
    assert report["counts"]["rows_exported"] == 3
    assert report["counts"]["errors"] == 0
    # 3 estados (Fase 10) -- este fixture no tiene warnings, así que SUCCESS limpio.
    assert report["status"]["result"] == "SUCCESS"

    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["module"] == "safety_meetings"
    assert manifest["migration_object"] == "Group_Meetings"
    assert manifest["approved_for_enablon_import"] is False


def test_pipeline_fila_sin_id_se_excluye(tmp_path):
    from src.export.prototype.safety_meetings.extractor import ExtractionResult

    df = _fake_dataframe()
    df.loc[0, "IDReunionGrupo"] = None
    extraction = ExtractionResult(
        dataframe=df, mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_excl", timestamp="20260101T000001Z",
    )
    assert result.stats.rows_exported == 2
    assert result.stats.rows_excluded == 1
    assert result.stats.missing_historical_origin_id == 1


def test_pipeline_status_success_with_warnings_cuando_hay_unresolved(tmp_path):
    """Fase 10: Safety Meetings SÍ distingue SUCCESS_WITH_WARNINGS -- un
    IDNivel/IDLetra/FaseActual sin coincidencia en la tabla debe reflejarse
    en el status, no enmascararse como SUCCESS limpio."""
    from src.export.prototype.safety_meetings.extractor import ExtractionResult

    df = _fake_dataframe()
    df.loc[0, "IDNivel"] = 999999  # sin coincidencia en level_lookup real
    extraction = ExtractionResult(
        dataframe=df, mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_warn", timestamp="20260101T000002Z",
    )
    report = yaml.safe_load(result.validation_report_path.read_text(encoding="utf-8"))
    assert report["status"]["result"] == "SUCCESS_WITH_WARNINGS"
    assert report["lookups"]["unresolved"] >= 1


def test_pipeline_lugar_y_asistentes_vacios_no_bloquean(tmp_path):
    """Fila 2 del fixture tiene Lugar/Asistentes=None -- deben quedar vacíos
    (status='empty'), nunca excluir la fila ni inventar un valor."""
    from src.export.prototype.safety_meetings.extractor import ExtractionResult

    extraction = ExtractionResult(
        dataframe=_fake_dataframe(), mode="sample", limit=3, rows_available_before_truncation=3,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=3, output_root=tmp_path, extraction=extraction,
        run_id="test_empty_fields", timestamp="20260101T000003Z",
    )
    assert result.stats.rows_exported == 3
    rows = result.csv_path.read_text(encoding="utf-8-sig").splitlines()[1:]
    second_row = rows[1].split("\t")
    meeting_place_idx = pipeline_mod.OUTPUT_COLUMNS.index("CS_MeetingPlace")
    atendee_idx = pipeline_mod.OUTPUT_COLUMNS.index("CS_HistoricalAtendee")
    assert second_row[meeting_place_idx] == ""
    assert second_row[atendee_idx] == ""


def _fake_dataframe_con_nulos_para_forzar_float64() -> pd.DataFrame:
    """Reproduce el tipo real que pandas produce para `IDNivel`/`IDLetra` en
    el sample real (`execution_id=f3647fbc455c`, Sprint 9.9): una columna SQL
    nullable con al menos una fila `NULL` fuerza el upcast de TODA la columna
    a `float64` -- incluso los valores "presentes" llegan como `256.0`, no
    `256`. Es exactamente el patrón que exponía el bug de Micro-sprint 9.10
    antes del fix de 9.10.1 (`resolve_workflow_status` sin normalizar la
    clave). Códigos reales del ETL de `config/exports/safety_meetings.yaml`
    (catálogo de mapeo versionado, no dato de cliente) -- mismos códigos que
    `_fake_dataframe()` ya usa en este fichero."""
    return pd.DataFrame({
        "IDReunionGrupo": [5303, 5305, 5310, 5399],
        "IDCentro": [4, 4, 4, 4],
        "IDUnidadOrg": [278, 278, 278, 278],
        "FaseActual": [4, 2, 1, 1],
        "IDNivel": [256, 257, 371, None],   # el None fuerza float64 en toda la columna
        "IDLetra": [258, 259, 373, None],
        "Fecha": ["18/06/2018 09:59:00", "22/06/2018 13:15:00", "27/06/2018 08:14:00", "01/07/2018 10:00:00"],
        "Lugar": ["Sala San Roque", "Sala X", "Sala Algeciras", None],
        "Asistentes": ["Juan, Maria", "Pedro", "Ana", None],
        "FechaCreacion": ["2018-06-18", "2018-06-22", "2018-06-27", "2018-07-01"],
    })


def test_pipeline_level_letter_resuelven_con_columna_float64_micro_sprint_9_10_1(tmp_path):
    """Regresión Micro-sprint 9.10.1: antes del fix, `IDNivel`/`IDLetra`
    llegando como `float64` (por el NULL de una fila `Scheduled`) hacía que
    NINGÚN código resolviera -- 0/12 en el sample real. Verifica que las 3
    filas con código real ahora resuelven, la fila `EXPECTED_NULL` sigue
    vacía sin inventar default, y confirma explícitamente el dtype `float64`
    (para que el test no pase trivialmente con `int64`, que nunca reprodujo
    el bug)."""
    from src.export.prototype.safety_meetings.extractor import ExtractionResult

    df = _fake_dataframe_con_nulos_para_forzar_float64()
    assert df["IDNivel"].dtype == "float64"
    assert df["IDLetra"].dtype == "float64"

    extraction = ExtractionResult(
        dataframe=df, mode="sample", limit=4, rows_available_before_truncation=4,
        sql_text="SELECT 1", sql_sha256="abc123", connection_name="prevencion",
        source_file="fake.sql",
    )
    result = pipeline_mod.run(
        mode="sample", limit=4, output_root=tmp_path, extraction=extraction,
        run_id="test_level_letter_float64", timestamp="20260101T000004Z",
    )
    rows = result.csv_path.read_text(encoding="utf-8-sig").splitlines()[1:]
    parsed = [r.split("\t") for r in rows]
    level_idx = pipeline_mod.OUTPUT_COLUMNS.index("CS_Level")
    letter_idx = pipeline_mod.OUTPUT_COLUMNS.index("CS_Letter")

    # Filas 1-3: código real presente en level_lookup/letter_lookup -> deben
    # resolver (antes del fix, las 3 quedaban vacías igual que la 4a).
    assert parsed[0][level_idx] == "1" and parsed[0][letter_idx] == "1"   # 256->1, 258->1
    assert parsed[1][level_idx] == "2" and parsed[1][letter_idx] == "2"   # 257->2, 259->2
    assert parsed[2][level_idx] == "3" and parsed[2][letter_idx] == "3"   # 371->3, 373->3

    # Fila 4 (EXPECTED_NULL, IDNivel/IDLetra ausentes): sigue vacía -- nunca
    # se inventa un default.
    assert parsed[3][level_idx] == ""
    assert parsed[3][letter_idx] == ""

    report = yaml.safe_load(result.validation_report_path.read_text(encoding="utf-8"))
    # Solo la fila EXPECTED_NULL genera "unresolved" (Level + Letter) -- las
    # otras 3 filas ahora resuelven, a diferencia de antes del fix.
    assert report["lookups"]["unresolved"] == 2
    assert report["status"]["result"] == "SUCCESS_WITH_WARNINGS"


# --------------------------------------------------------------------------
# 9. Readiness funciona (offline, workspace de ejemplo sintético)
# --------------------------------------------------------------------------

def test_readiness_safety_meetings_con_manifest_sintetico_sample_sin_blockers(tmp_path):
    manifest_yaml = tmp_path / "workspace.yaml"
    manifest_yaml.write_text(
        "project:\n  id: acme\n  display_name: Acme\n  status: active\n  version: '1.0'\n"
        "workspace:\n  schema_version: '1.0'\n  project_root: projects/acme\n"
        "modules:\n  safety_meetings:\n    display_name: Safety Meetings\n    enabled: true\n"
        "    status: in_progress\n    canonical_name: Group_Meetings\n    artifacts:\n"
        "      sql:\n        path: null\n        status: present\n        required_for_sample: true\n"
        "      mapping:\n        path: null\n        status: present\n        required_for_sample: true\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, [
        "workspace", "readiness", "--manifest", str(manifest_yaml),
        "--module", "safety_meetings", "--operation", "sample", "--format", "json",
    ])
    assert result.exit_code in (0, 1)  # 0=READY, 1=READY_WITH_WARNINGS -- nunca BLOCKED(2)
    assert '"status": "ready"' in result.output
    assert "0 blocker(s)" in result.output
    assert "MODULE_UNKNOWN" not in result.output
    assert "MODULE_DISABLED" not in result.output
