"""Tests de src/analysis/sql_inventory.py.

Unitarias (esta sección): sin red -- run_query_file se sustituye por
DataFrames sintéticos vía monkeypatch. Cubren ensamblado, deduplicación de
FKs simples/compuestas/repetidas, escritura atómica de todos los
artefactos, contenido del manifiesto, orden determinista, y el
comportamiento fail-fast (aborto + limpieza de temporal + ausencia de
carpeta definitiva).

Las pruebas de integración reales (al final) requieren
RUN_SQL_INTEGRATION_TESTS=1 y escriben exclusivamente en tmp_path.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
import yaml

from src.analysis.sql_inventory import (
    CATEGORY_QUERY_FILES,
    InventoryResult,
    _derive_table_relationships,
    run_and_save_inventory,
    run_sql_inventory,
    save_inventory,
)


# --------------------------------------------------------------------------
# Datos sintéticos mínimos y válidos por categoría (columnas reales de cada
# .sql de sql/diagnostics/sql_server_inventory/).
# --------------------------------------------------------------------------

def _empty_category_frames() -> dict[str, pd.DataFrame]:
    return {
        "tables": pd.DataFrame([{"schema_name": "dbo", "table_name": "Foo", "object_id": 1, "create_date": "2020-01-01", "modify_date": "2020-01-01"}]),
        "views": pd.DataFrame([{"schema_name": "dbo", "view_name": "VFoo", "object_id": 2, "create_date": "2020-01-01", "modify_date": "2020-01-01"}]),
        "columns": pd.DataFrame([{"schema_name": "dbo", "table_name": "Foo", "object_type": "U", "column_id": 1, "column_name": "Id", "data_type": "int", "max_length": 4, "precision": 10, "scale": 0, "is_nullable": False, "is_identity": True, "is_computed": False, "default_definition": None}]),
        "primary_keys": pd.DataFrame([{"schema_name": "dbo", "table_name": "Foo", "constraint_name": "PK_Foo", "column_name": "Id", "key_ordinal": 1}]),
        "foreign_keys": pd.DataFrame(columns=[
            "foreign_key_object_id", "foreign_key_name", "source_schema", "source_table",
            "source_column", "target_schema", "target_table", "target_column",
            "column_ordinal", "update_action", "delete_action",
        ]),
        "indexes": pd.DataFrame([{"schema_name": "dbo", "table_name": "Foo", "index_id": 1, "index_name": "PK_Foo", "index_type": "CLUSTERED", "is_unique": True, "is_primary_key": True, "is_unique_constraint": False, "has_filter": False, "filter_definition": None, "index_column_id": 1, "key_ordinal": 1, "is_included_column": False, "sort_direction": "ASC", "column_name": "Id"}]),
        "stored_procedures": pd.DataFrame([{"schema_name": "dbo", "procedure_name": "spFoo", "object_id": 3, "create_date": "2020-01-01", "modify_date": "2020-01-01"}]),
        "functions": pd.DataFrame([{"schema_name": "dbo", "function_name": "fnFoo", "object_id": 4, "function_type": "SQL_SCALAR_FUNCTION", "create_date": "2020-01-01", "modify_date": "2020-01-01"}]),
        "triggers": pd.DataFrame([{"trigger_scope": "TABLE", "schema_name": "dbo", "table_name": "Foo", "trigger_name": "trgFoo", "object_id": 5, "is_disabled": False, "is_instead_of_trigger": False}]),
        "synonyms": pd.DataFrame(columns=["schema_name", "synonym_name", "object_id", "base_object_name"]),
        "approx_row_counts": pd.DataFrame([{"schema_name": "dbo", "table_name": "Foo", "approx_row_count": 100}]),
    }


def _fk_row(fk_object_id, fk_name, src_table, src_col, tgt_table, tgt_col, ordinal=1):
    return {
        "foreign_key_object_id": fk_object_id,
        "foreign_key_name": fk_name,
        "source_schema": "dbo",
        "source_table": src_table,
        "source_column": src_col,
        "target_schema": "dbo",
        "target_table": tgt_table,
        "target_column": tgt_col,
        "column_ordinal": ordinal,
        "update_action": "NO_ACTION",
        "delete_action": "NO_ACTION",
    }


@pytest.fixture
def mock_run_query_file(monkeypatch):
    """Sustituye run_query_file por datos sintéticos indexados por nombre de
    archivo (el último componente de la ruta), y get_connection_spec por una
    especificación falsa (server/database no derivados de URL/engine)."""
    frames = _empty_category_frames()

    def _fake_run_query_file(path, connection=None, params=None):
        filename = Path(path).name
        category = filename[: -len(".sql")]
        return frames[category].copy()

    class _FakeSpec:
        server = r"ALL4-CJJKW74\SQLEXPRESS"
        database = "Prevencion"

    monkeypatch.setattr("src.analysis.sql_inventory.run_query_file", _fake_run_query_file)
    monkeypatch.setattr("src.analysis.sql_inventory.get_connection_spec", lambda name=None: _FakeSpec())
    return frames


# --------------------------------------------------------------------------
# Ensamblado de InventoryResult
# --------------------------------------------------------------------------

def test_run_sql_inventory_ensambla_todas_las_categorias(mock_run_query_file, tmp_path, monkeypatch):
    monkeypatch.setattr("src.analysis.sql_inventory.get_paths", lambda: {
        "logs": tmp_path / "logs", "sql_diagnostics": Path("sql/diagnostics"), "outputs": tmp_path / "outputs",
    })
    result = run_sql_inventory("prevencion")
    assert isinstance(result, InventoryResult)
    assert result.connection == "prevencion"
    assert result.database == "Prevencion"
    assert result.server == r"ALL4-CJJKW74\SQLEXPRESS"
    assert isinstance(result.generated_at, datetime)
    assert result.generated_at.tzinfo is not None

    expected_categories = set(CATEGORY_QUERY_FILES) | {"table_relationships"}
    assert set(result.artifacts) == expected_categories


# --------------------------------------------------------------------------
# Deduplicación de FKs -- simple / compuesta / repetida
# --------------------------------------------------------------------------

def test_fk_simple_una_relacion():
    df = pd.DataFrame([_fk_row(1, "FK_A_B", "A", "b_id", "B", "id")])
    rel = _derive_table_relationships(df)
    assert len(rel) == 1
    assert rel.iloc[0]["foreign_key_count"] == 1
    assert rel.iloc[0]["source_table"] == "A"
    assert rel.iloc[0]["target_table"] == "B"


def test_fk_compuesta_no_se_cuenta_por_columna():
    # Una única FK (mismo foreign_key_object_id) con 2 columnas.
    df = pd.DataFrame([
        _fk_row(1, "FK_A_B", "A", "b_id1", "B", "id1", ordinal=1),
        _fk_row(1, "FK_A_B", "A", "b_id2", "B", "id2", ordinal=2),
    ])
    rel = _derive_table_relationships(df)
    assert len(rel) == 1
    assert rel.iloc[0]["foreign_key_count"] == 1


def test_relaciones_repetidas_entre_las_mismas_tablas():
    # Dos FKs DISTINTAS (distinto foreign_key_object_id) entre A y B.
    df = pd.DataFrame([
        _fk_row(1, "FK_A_B_1", "A", "b_id", "B", "id"),
        _fk_row(2, "FK_A_B_2", "A", "b_id2", "B", "id2"),
    ])
    rel = _derive_table_relationships(df)
    assert len(rel) == 1
    assert rel.iloc[0]["foreign_key_count"] == 2


def test_fk_vacio_devuelve_dataframe_vacio_con_columnas():
    df = pd.DataFrame(columns=[
        "foreign_key_object_id", "foreign_key_name", "source_schema", "source_table",
        "source_column", "target_schema", "target_table", "target_column",
        "column_ordinal", "update_action", "delete_action",
    ])
    rel = _derive_table_relationships(df)
    assert len(rel) == 0
    assert list(rel.columns) == [
        "source_schema", "source_table", "target_schema", "target_table", "foreign_key_count",
    ]


# --------------------------------------------------------------------------
# Escritura de artefactos + manifiesto + orden determinista
# --------------------------------------------------------------------------

def _build_result(generated_at=None) -> InventoryResult:
    frames = _empty_category_frames()
    frames["table_relationships"] = _derive_table_relationships(frames["foreign_keys"])
    return InventoryResult(
        connection="prevencion",
        database="Prevencion",
        server=r"ALL4-CJJKW74\SQLEXPRESS",
        generated_at=generated_at or datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc),
        artifacts=frames,
    )


def test_save_inventory_escribe_todos_los_artefactos(tmp_path):
    result = _build_result()
    final_dir = save_inventory(result, base_output_dir=tmp_path)

    assert final_dir == tmp_path / "prevencion" / "20260721_120000"
    esperado = {f"{c}.csv" for c in CATEGORY_QUERY_FILES} | {"table_relationships.csv", "manifest.yaml"}
    assert {p.name for p in final_dir.iterdir()} == esperado


def test_manifest_contenido(tmp_path):
    result = _build_result()
    final_dir = save_inventory(result, base_output_dir=tmp_path)

    manifest = yaml.safe_load((final_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["inventory_version"] == 1
    assert manifest["connection"] == "prevencion"
    assert manifest["database"] == "Prevencion"
    assert manifest["server"] == r"ALL4-CJJKW74\SQLEXPRESS"
    assert manifest["generated_at"] == "2026-07-21T12:00:00+00:00"
    assert "usuario" not in manifest and "password" not in str(manifest).lower()

    rows_by_name = {a["name"]: a["rows"] for a in manifest["artifacts"]}
    assert rows_by_name["tables.csv"] == 1
    assert rows_by_name["synonyms.csv"] == 0


def test_orden_determinista_no_depende_del_orden_de_entrada(tmp_path):
    frames_a = _empty_category_frames()
    frames_a["tables"] = pd.DataFrame([
        {"schema_name": "dbo", "table_name": "Zeta", "object_id": 1, "create_date": "x", "modify_date": "x"},
        {"schema_name": "dbo", "table_name": "Alfa", "object_id": 2, "create_date": "x", "modify_date": "x"},
    ])
    frames_b = _empty_category_frames()
    frames_b["tables"] = frames_a["tables"].iloc[::-1].reset_index(drop=True)  # mismo contenido, orden invertido

    for frames, out in ((frames_a, "run_a"), (frames_b, "run_b")):
        frames["tables"] = frames["tables"].sort_values(["schema_name", "table_name"]).reset_index(drop=True)
        frames["table_relationships"] = _derive_table_relationships(frames["foreign_keys"])
        result = InventoryResult(
            connection="prevencion", database="Prevencion", server="srv",
            generated_at=datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc), artifacts=frames,
        )
        save_inventory(result, base_output_dir=tmp_path / out)

    csv_a = (tmp_path / "run_a" / "prevencion" / "20260721_120000" / "tables.csv").read_bytes()
    csv_b = (tmp_path / "run_b" / "prevencion" / "20260721_120000" / "tables.csv").read_bytes()
    assert csv_a == csv_b


def test_csv_no_incluye_indice_de_pandas(tmp_path):
    result = _build_result()
    final_dir = save_inventory(result, base_output_dir=tmp_path)
    primer_linea = (final_dir / "tables.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert primer_linea.split(",")[0] == "schema_name"  # no hay columna de índice antes


# --------------------------------------------------------------------------
# Fail-fast: aborto, sin carpeta definitiva, sin temporal residual
# --------------------------------------------------------------------------

def test_run_sql_inventory_aborta_si_falla_una_categoria(monkeypatch, tmp_path):
    monkeypatch.setattr("src.analysis.sql_inventory.get_paths", lambda: {
        "logs": tmp_path / "logs", "sql_diagnostics": Path("sql/diagnostics"), "outputs": tmp_path / "outputs",
    })

    class _FakeSpec:
        server = "srv"
        database = "Prevencion"

    frames = _empty_category_frames()

    def _failing_run_query_file(path, connection=None, params=None):
        filename = Path(path).name
        if filename == "triggers.sql":
            raise RuntimeError("fallo simulado en triggers")
        return frames[filename[: -len(".sql")]].copy()

    monkeypatch.setattr("src.analysis.sql_inventory.run_query_file", _failing_run_query_file)
    monkeypatch.setattr("src.analysis.sql_inventory.get_connection_spec", lambda name=None: _FakeSpec())

    with pytest.raises(RuntimeError, match="fallo simulado en triggers"):
        run_sql_inventory("prevencion")


def test_save_inventory_no_deja_carpeta_definitiva_ni_temporal_si_falla(tmp_path, monkeypatch):
    result = _build_result()

    def _boom(*args, **kwargs):
        raise RuntimeError("fallo simulado escribiendo manifest")

    monkeypatch.setattr("yaml.safe_dump", _boom)

    with pytest.raises(RuntimeError, match="fallo simulado escribiendo manifest"):
        save_inventory(result, base_output_dir=tmp_path)

    connection_dir = tmp_path / "prevencion"
    contenido = list(connection_dir.iterdir()) if connection_dir.exists() else []
    assert (connection_dir / "20260721_120000") not in contenido
    assert not any(p.name.startswith(".tmp_") for p in contenido)


def test_run_and_save_inventory_no_deja_rastro_si_run_falla(monkeypatch, tmp_path):
    def _boom(connection):
        raise RuntimeError("fallo simulado en run_sql_inventory")

    monkeypatch.setattr("src.analysis.sql_inventory.run_sql_inventory", _boom)

    with pytest.raises(RuntimeError):
        run_and_save_inventory("prevencion", base_output_dir=tmp_path)

    assert not (tmp_path / "prevencion").exists()


# --------------------------------------------------------------------------
# Integración real -- SOLO si RUN_SQL_INTEGRATION_TESTS=1. Escriben
# exclusivamente en tmp_path, nunca en outputs/inventory real. Si la
# bandera está activa y algo falla, la prueba FALLA (no se omite).
# --------------------------------------------------------------------------

RUN_INTEGRATION = os.environ.get("RUN_SQL_INTEGRATION_TESTS") == "1"

pytestmark_integration = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="RUN_SQL_INTEGRATION_TESTS no está activo (usar =1 para probar contra SQL Server real).",
)

_EXPECTED_COLUMNS = {
    "tables": {"schema_name", "table_name", "object_id"},
    "views": {"schema_name", "view_name", "object_id"},
    "columns": {"schema_name", "table_name", "column_name", "data_type", "is_nullable"},
    "primary_keys": {"schema_name", "table_name", "constraint_name", "column_name"},
    "foreign_keys": {"foreign_key_object_id", "source_table", "target_table"},
    "indexes": {"schema_name", "table_name", "index_name", "sort_direction"},
    "stored_procedures": {"schema_name", "procedure_name"},
    "functions": {"schema_name", "function_name", "function_type"},
    "triggers": {"trigger_scope", "trigger_name"},
    "synonyms": {"schema_name", "synonym_name", "base_object_name"},
    "approx_row_counts": {"schema_name", "table_name", "approx_row_count"},
    "table_relationships": {"source_table", "target_table", "foreign_key_count"},
}


@pytestmark_integration
@pytest.mark.parametrize("connection_name", ["prevencion", "gct"])
def test_integracion_inventario_real(connection_name, tmp_path):
    result = run_sql_inventory(connection_name)

    for categoria, columnas_esperadas in _EXPECTED_COLUMNS.items():
        df = result.artifacts[categoria]
        assert columnas_esperadas.issubset(set(df.columns)), categoria

    assert (result.artifacts["approx_row_counts"]["approx_row_count"].dropna() >= 0).all()

    final_dir = save_inventory(result, base_output_dir=tmp_path)
    assert final_dir.exists()
    assert (final_dir / "manifest.yaml").exists()
    manifest = yaml.safe_load((final_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["connection"] == connection_name
