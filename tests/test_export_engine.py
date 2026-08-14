"""Tests del Export Engine mínimo (Sprint 9.6) -- `src/export/engine/`.

Dos frentes:
1. Unit tests de cada pieza extraída, aislados de Drills/Bypass (fixtures
   propias de este fichero, nunca SQL real, nunca `config/exports/*.yaml`
   reales salvo donde se indica explícitamente).
2. Tests arquitectónicos (Fase 14 del encargo de Sprint 9.6): impiden que el
   Engine vuelva a acoplarse a un módulo concreto, o que un módulo concreto
   dependa de otro módulo hermano en vez del Engine.

Ejecutar con: pytest tests/test_export_engine.py -v
"""
from __future__ import annotations

import ast
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest
import yaml

from src.config import PROJECT_ROOT
from src.core.contracts import ExecutionContext, ExecutionRequest, StageStatus
from src.export.engine.config import FieldSpec, OutputSpec, SourceSpec, load_export_config
from src.export.engine.extractor import (
    DEFAULT_SAMPLE_LIMIT,
    MODE_FULL,
    MODE_SAMPLE,
    ExtractionResult,
    extract_via_sql,
)
from src.export.engine.manifest import (
    FAILED_VALIDATION,
    SUCCESS,
    SUCCESS_WITH_WARNINGS,
    BaseRunStats,
    build_connection_section,
    build_counts_section,
    build_output_section,
    build_query_filters_section,
    build_run_section,
    determine_status,
)
from src.export.engine.identifiers import to_historical_id
from src.export.engine.lookups import LookupResult, normalize_lookup_key, resolve_letter, resolve_workflow_status
from src.export.engine.query_stage import GenericQueryStage, QueryStageSpec
from src.export.engine.validator import validate_csv_structure
from src.export.engine.values import is_missing, to_native
from src.export.engine.writer import resolve_text_encoding, write_csv
from src.query.catalog import DRILLS_FILTER_CATALOG


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FakeExportConfig:
    object_id: str
    module: str
    migration_object: str
    prototype_status: str
    source: SourceSpec
    output: OutputSpec
    invalid_row_policy: str
    reference_data: dict[str, Any]
    fields: tuple[FieldSpec, ...]
    excluded_columns: tuple[dict[str, Any], ...]
    raw: dict[str, Any] = field(repr=False)


def _write_minimal_export_yaml(tmp_path: Path, *, sql_relpath: str) -> Path:
    sql_path = PROJECT_ROOT / sql_relpath
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    if not sql_path.is_file():
        sql_path.write_text("SELECT 1 AS Id", encoding="utf-8")
    yaml_path = tmp_path / "fake_export.yaml"
    yaml_path.write_text(textwrap.dedent(f"""\
        object_id: fake
        module: fake_module
        migration_object: Fake
        prototype_status: review_only
        source:
          connection: prevencion
          sql_file: "{sql_relpath}"
          max_rows: 100
        output:
          filename: fake.csv
          encoding: utf-8
          bom: false
          delimiter: "\\t"
          quoting: minimal
          line_terminator: "\\r\\n"
          include_header: true
        invalid_row_policy: report_and_exclude_from_csv
        reference_data: {{}}
        fields:
          - source: "Id"
            target: "Id"
            required: true
            transformation: passthrough
            data_type: string
            date_format: null
            default: null
            mapping: null
            validation: required_non_null
            evidence_id: "test:fake.id"
        """), encoding="utf-8")
    return yaml_path, sql_path


def test_load_export_config_construye_el_contenedor_generico(tmp_path):
    yaml_path, sql_path = _write_minimal_export_yaml(tmp_path, sql_relpath="sql/source_queries/_engine_test_fixture.sql")
    try:
        config = load_export_config(str(yaml_path), _FakeExportConfig)
        assert isinstance(config, _FakeExportConfig)
        assert config.object_id == "fake"
        assert config.source.connection == "prevencion"
        assert config.fields[0].target == "Id"
        assert config.excluded_columns == ()
    finally:
        sql_path.unlink(missing_ok=True)


def test_load_export_config_lanza_si_faltan_claves_obligatorias(tmp_path):
    yaml_path = tmp_path / "incompleto.yaml"
    yaml_path.write_text("object_id: fake\n", encoding="utf-8")
    with pytest.raises(ValueError, match="claves obligatorias"):
        load_export_config(str(yaml_path), _FakeExportConfig)


def test_drills_y_bypass_usan_las_mismas_dataclasses_de_config():
    """No son clases equivalentes por casualidad -- son el MISMO objeto,
    importado del Engine (Sprint 9.6)."""
    from src.export.prototype.bypass.config import FieldSpec as BypassFieldSpec
    from src.export.prototype.bypass.config import OutputSpec as BypassOutputSpec
    from src.export.prototype.drills.config import FieldSpec as DrillsFieldSpec
    from src.export.prototype.drills.config import OutputSpec as DrillsOutputSpec

    assert DrillsFieldSpec is BypassFieldSpec is FieldSpec
    assert DrillsOutputSpec is BypassOutputSpec is OutputSpec


# ---------------------------------------------------------------------------
# extractor.py
# ---------------------------------------------------------------------------

def _fake_source(tmp_path: Path, sql_text: str = "SELECT 1") -> SourceSpec:
    sql_relpath = f"sql/source_queries/_engine_test_extractor_{tmp_path.name}.sql"
    sql_path = PROJECT_ROOT / sql_relpath
    sql_path.parent.mkdir(parents=True, exist_ok=True)
    sql_path.write_text(sql_text, encoding="utf-8")
    return SourceSpec(connection="prevencion", sql_file=sql_relpath, max_rows=1000)


def test_extract_via_sql_sin_sort_column_conserva_el_orden_de_origen(tmp_path):
    source = _fake_source(tmp_path)
    df = pd.DataFrame({"Id": [3, 1, 2]})
    try:
        result = extract_via_sql(source, query_runner=lambda *a, **k: df.copy(), mode=MODE_SAMPLE, limit=10)
        assert list(result.dataframe["Id"]) == [3, 1, 2]  # sin reordenar
        assert result.limit == 10
        assert result.rows_available_before_truncation == 3
    finally:
        source.sql_path.unlink(missing_ok=True)


def test_extract_via_sql_con_sort_column_ordena_antes_de_truncar(tmp_path):
    source = _fake_source(tmp_path)
    df = pd.DataFrame({"Id": [3, 1, 2], "Fecha": ["2020-01-03", "2020-01-01", "2020-01-02"]})
    try:
        result = extract_via_sql(
            source, query_runner=lambda *a, **k: df.copy(), mode=MODE_SAMPLE, limit=2, sort_column="Fecha",
        )
        assert list(result.dataframe["Id"]) == [1, 2]  # ordenado por Fecha asc, truncado a 2
    finally:
        source.sql_path.unlink(missing_ok=True)


def test_extract_via_sql_modo_full_no_trunca_ni_ordena(tmp_path):
    source = _fake_source(tmp_path)
    df = pd.DataFrame({"Id": [3, 1, 2]})
    try:
        result = extract_via_sql(
            source, query_runner=lambda *a, **k: df.copy(), mode=MODE_FULL, sort_column="Id",
        )
        assert result.limit is None
        assert list(result.dataframe["Id"]) == [3, 1, 2]
    finally:
        source.sql_path.unlink(missing_ok=True)


def test_extract_via_sql_rechaza_limit_no_positivo_en_sample(tmp_path):
    source = _fake_source(tmp_path)
    try:
        with pytest.raises(ValueError, match="positivo"):
            extract_via_sql(source, query_runner=lambda *a, **k: pd.DataFrame(), mode=MODE_SAMPLE, limit=0)
    finally:
        source.sql_path.unlink(missing_ok=True)


def test_extract_via_sql_query_runner_recibe_params_none_sin_filtros(tmp_path):
    source = _fake_source(tmp_path)
    captured = {}

    def _runner(sql_text, *, connection, params, source_file):
        captured["params"] = params
        return pd.DataFrame({"Id": [1]})

    try:
        extract_via_sql(source, query_runner=_runner, mode=MODE_SAMPLE, limit=5)
        assert captured["params"] is None
    finally:
        source.sql_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# values.py
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [None, float("nan"), np.float64("nan"), "", "   ", pd.NA])
def test_is_missing_reconoce_todas_las_formas_de_ausencia(value):
    assert is_missing(value) is True


@pytest.mark.parametrize("value", [0, 1, "x", "0", np.int64(42), np.float64(3.14), False])
def test_is_missing_no_confunde_valores_reales_con_ausencia(value):
    assert is_missing(value) is False


def test_to_native_convierte_escalares_numpy():
    assert isinstance(to_native(np.int64(7)), int)
    assert isinstance(to_native(np.float64(1.5)), float)
    assert to_native("x") == "x"  # no numpy -- passthrough


# ---------------------------------------------------------------------------
# manifest.py
# ---------------------------------------------------------------------------

def _stats(**overrides) -> BaseRunStats:
    base = dict(run_id="r1", timestamp="20260101T000000Z", mode="sample", connection_name="prevencion")
    base.update(overrides)
    return BaseRunStats(**base)


def test_determine_status_sin_errores_ni_warnings_es_success():
    result, blocking, warnings = determine_status([], [])
    assert result == SUCCESS
    assert blocking == []
    assert warnings == []


def test_determine_status_con_warnings_sin_errores_es_success_with_warnings():
    result, blocking, warnings = determine_status([], ["algo raro"])
    assert result == SUCCESS_WITH_WARNINGS


def test_determine_status_con_errores_es_failed_validation_aunque_haya_warnings():
    result, blocking, warnings = determine_status(["error bloqueante"], ["warning"])
    assert result == FAILED_VALIDATION
    assert blocking == ["error bloqueante"]


def test_build_run_section_usa_migration_object_del_llamador():
    stats = _stats()
    section = build_run_section(stats, migration_object="Fake")
    assert section["migration_object"] == "Fake"
    assert section["prototype_status"] == "review_only"
    assert section["run_id"] == "r1"


def test_build_counts_y_output_section_reflejan_stats():
    stats = _stats(rows_read=5, rows_exported=4, rows_excluded=1, warnings=["w"], errors=[])
    counts = build_counts_section(stats)
    assert counts == {
        "rows_read": 5, "rows_transformed": 0, "rows_exported": 4,
        "rows_excluded": 1, "warnings": 1, "errors": 0,
    }
    stats.output_columns = ["A", "B"]
    stats.output_column_count = 2
    output = build_output_section(stats)
    assert output["columns"] == ["A", "B"]
    assert output["column_count"] == 2


def test_build_connection_section_nunca_incluye_credenciales():
    section = build_connection_section("prevencion")
    assert section["name"] == "prevencion"
    assert "password" not in section["note"].lower() or "no incluidos" in section["note"].lower()


def test_build_query_filters_section_sin_filtros():
    section = build_query_filters_section(
        compiled_filters=(), source_sql_sha256="abc", generated_sql_file=None, generated_sql_sha256=None,
    )
    assert section["applied"] is False
    assert section["count"] == 0


# ---------------------------------------------------------------------------
# validator.py
# ---------------------------------------------------------------------------

_OUTPUT_SPEC = OutputSpec(
    filename="fake.csv", encoding="utf-8", bom=False, delimiter="\t",
    quoting="minimal", line_terminator="\r\n", include_header=True,
)


def test_validate_csv_structure_fichero_inexistente(tmp_path):
    result = validate_csv_structure(tmp_path / "no_existe.csv", ["A", "B"], _OUTPUT_SPEC)
    assert not result.is_valid
    assert "no existe" in result.issues[0]


def test_validate_csv_structure_fichero_vacio(tmp_path):
    path = tmp_path / "vacio.csv"
    path.write_bytes(b"")
    result = validate_csv_structure(path, ["A", "B"], _OUTPUT_SPEC)
    assert not result.is_valid
    assert "vacío" in result.issues[0]


def test_validate_csv_structure_cabecera_no_coincide(tmp_path):
    path = tmp_path / "bad_header.csv"
    path.write_bytes(b"A\tC\r\n1\t2\r\n")
    result = validate_csv_structure(path, ["A", "B"], _OUTPUT_SPEC)
    assert not result.is_valid
    assert result.columns == ["A", "C"]


def test_validate_csv_structure_exitoso(tmp_path):
    path = tmp_path / "ok.csv"
    path.write_bytes(b"A\tB\r\n1\t2\r\n3\t4\r\n")
    result = validate_csv_structure(path, ["A", "B"], _OUTPUT_SPEC)
    assert result.is_valid
    assert result.row_count == 2
    assert result.data_rows == [["1", "2"], ["3", "4"]]


def test_bypass_validator_delega_en_engine_sin_cambiar_forma(tmp_path):
    from src.export.prototype.bypass.validator import validate_output_csv

    path = tmp_path / "bypass.csv"
    path.write_bytes(b"A\tB\r\n1\t2\r\n")
    result = validate_output_csv(path, ["A", "B"], _OUTPUT_SPEC)
    assert result.is_valid
    assert result.row_count == 1
    assert result.columns == ["A", "B"]


# ---------------------------------------------------------------------------
# query_stage.py
# ---------------------------------------------------------------------------

@dataclass
class _FakeExtraction:
    dataframe: pd.DataFrame
    rows_available_before_truncation: int


def test_generic_query_stage_ejecuta_lifecycle_completo():
    calls = {"config_loader": 0, "extract_fn_args": None}

    def _config_loader():
        calls["config_loader"] += 1
        return {"fake": "config"}

    def _extract_fn(config, *, mode, limit, compiled_filters):
        calls["extract_fn_args"] = (config, mode, limit, tuple(compiled_filters))
        return _FakeExtraction(dataframe=pd.DataFrame({"Id": [1, 2]}), rows_available_before_truncation=2)

    stage = GenericQueryStage(QueryStageSpec(
        name="query", config_loader=_config_loader, state_key="fake_config",
        filter_catalog=DRILLS_FILTER_CATALOG, extract_fn=_extract_fn,
    ))

    request = ExecutionRequest(project="acme", object_type="fake", mode="sample", limit=7)
    context = ExecutionContext(
        execution_id="e1", request=request, started_at=None, working_dir=PROJECT_ROOT,
        output_dir=PROJECT_ROOT, logger=__import__("logging").getLogger("test"),
    )
    result = stage.execute(context, None)

    assert result.status == StageStatus.SUCCESS
    assert context.state["fake_config"] == {"fake": "config"}
    assert calls["config_loader"] == 1
    assert calls["extract_fn_args"][1] == "sample"
    assert calls["extract_fn_args"][2] == 7
    assert result.metrics.output_record_count == 2
    assert result.metrics.input_record_count == 2


def test_generic_query_stage_compila_filtros_del_request():
    captured = {}

    def _extract_fn(config, *, mode, limit, compiled_filters):
        captured["filters"] = compiled_filters
        return _FakeExtraction(dataframe=pd.DataFrame({"Id": [1]}), rows_available_before_truncation=1)

    stage = GenericQueryStage(QueryStageSpec(
        name="query", config_loader=lambda: None, state_key="k",
        filter_catalog=DRILLS_FILTER_CATALOG, extract_fn=_extract_fn,
    ))
    request = ExecutionRequest(
        project="acme", object_type="fake", mode="sample", limit=5,
        filters=("historical_origin_id:eq:100",),
    )
    context = ExecutionContext(
        execution_id="e2", request=request, started_at=None, working_dir=PROJECT_ROOT,
        output_dir=PROJECT_ROOT, logger=__import__("logging").getLogger("test"),
    )
    stage.execute(context, None)
    assert len(captured["filters"]) == 1
    assert captured["filters"][0].field == "historical_origin_id"


# ---------------------------------------------------------------------------
# Tests arquitectónicos (Fase 14)
# ---------------------------------------------------------------------------

_ENGINE_DIR = PROJECT_ROOT / "src" / "export" / "engine"
_ENGINE_FILES = sorted(p for p in _ENGINE_DIR.glob("*.py") if p.name != "__pycache__")


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_engine_no_importa_drills_ni_bypass():
    for path in _ENGINE_FILES:
        imported = _imported_module_names(path)
        offending = {m for m in imported if "export.prototype" in m}
        assert not offending, f"{path.name} importa de src.export.prototype: {offending}"


_MODULE_ID_LITERALS = {"drills", "bypass", "simulacros", "safety_meetings", "moc", "events", "eventos", "inspections", "inspecciones", "ops", "action_plans"}


def _compares_against_module_literal(tree: ast.AST) -> list[str]:
    """Busca comparaciones de CÓDIGO (nunca docstrings/comentarios, ya
    excluidos por ser nodos `ast.Compare`, no texto plano) contra un literal
    de string que sea un nombre de módulo conocido -- la señal concreta de
    un `if module_id == "drills"` o equivalente."""
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for operand in operands:
                if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                    if operand.value in _MODULE_ID_LITERALS:
                        offenders.append(operand.value)
    return offenders


def test_engine_no_tiene_condicionales_por_module_id():
    """Ningún fichero del Engine debe decidir comportamiento comparando
    contra un nombre de módulo concreto -- la diferenciación siempre debe
    llegar por inyección de dependencias (parámetros/funciones). Se analiza
    el AST (no el texto crudo) para no confundir esto con menciones en
    docstrings/comentarios, que sí son legítimas."""
    for path in _ENGINE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders = _compares_against_module_literal(tree)
        assert not offenders, f"{path.name} compara código contra {offenders} -- branching por módulo prohibido en el Engine"


def test_drills_y_bypass_consumen_el_engine():
    drills_files = [
        PROJECT_ROOT / "src/export/prototype/drills/config.py",
        PROJECT_ROOT / "src/export/prototype/drills/extractor.py",
        PROJECT_ROOT / "src/export/prototype/drills/manifest.py",
        PROJECT_ROOT / "src/export/prototype/drills/validator.py",
        PROJECT_ROOT / "src/export/prototype/drills/core_adapters.py",
    ]
    bypass_files = [
        PROJECT_ROOT / "src/export/prototype/bypass/config.py",
        PROJECT_ROOT / "src/export/prototype/bypass/extractor.py",
        PROJECT_ROOT / "src/export/prototype/bypass/manifest.py",
        PROJECT_ROOT / "src/export/prototype/bypass/validator.py",
        PROJECT_ROOT / "src/export/prototype/bypass/core_adapters.py",
    ]
    for path in drills_files + bypass_files:
        imported = _imported_module_names(path)
        assert any(m.startswith("src.export.engine") for m in imported), (
            f"{path.relative_to(PROJECT_ROOT)} no importa nada de src.export.engine tras Sprint 9.6"
        )


def test_bypass_ya_no_importa_directamente_de_drills():
    """Antes de Sprint 9.6, `bypass/manifest.py` y `bypass/pipeline.py`
    importaban `write_yaml_atomic`/`write_text_atomic`/`build_query_filters_section`
    directamente de `drills/manifest.py`. Hasta Sprint 9.8, `bypass/pipeline.py`
    seguía importando `exporter.write_csv` y `bypass/transformations.py`
    importaba `resolve_letter`/`to_historical_id` de
    `drills/transformations.py` -- las dos últimas excepciones documentadas
    de acoplamiento bypass -> drills para utilidades sin ninguna lógica de
    Drills. Sprint 9.8 movió ambas al Engine (`identifiers.py`/`lookups.py`/
    `writer.py`) tras confirmar una tercera reutilización real idéntica
    (Safety Meetings) -- ningún fichero de `bypass/` debe importar de
    `drills/` en absoluto a partir de aquí."""
    for path in (PROJECT_ROOT / "src/export/prototype/bypass").glob("*.py"):
        imported = _imported_module_names(path)
        offending = {m for m in imported if m.startswith("src.export.prototype.drills")}
        assert not offending, f"{path.name} todavía importa de drills: {offending}"


def test_safety_meetings_ya_no_importa_directamente_de_drills():
    """Mismo criterio que Bypass: hasta Sprint 9.8, `safety_meetings/pipeline.py`
    importaba `exporter.write_csv` y `safety_meetings/transformations.py`
    importaba `resolve_workflow_status`/`to_historical_id` de
    `drills/transformations.py` -- movidas al Engine en Sprint 9.8. Ningún
    fichero de `safety_meetings/` debe importar de `drills/`."""
    for path in (PROJECT_ROOT / "src/export/prototype/safety_meetings").glob("*.py"):
        imported = _imported_module_names(path)
        offending = {m for m in imported if m.startswith("src.export.prototype.drills")}
        assert not offending, f"{path.name} todavía importa de drills: {offending}"


# ---------------------------------------------------------------------------
# identifiers.py / lookups.py / writer.py (Sprint 9.8)
# ---------------------------------------------------------------------------

def test_to_historical_id_limpia_decimal_artificial():
    assert to_historical_id(440) == "440"
    assert to_historical_id(440.0) == "440"
    assert to_historical_id(np.int64(440)) == "440"
    assert to_historical_id(None) is None
    assert to_historical_id(440.5) is None


def test_resolve_letter_null_default_solo_para_vacio():
    lookup = {"258": "A"}
    assert resolve_letter(None, lookup, "NOLETTER-WRONG").status == "null_default"
    assert resolve_letter(258, lookup, "NOLETTER-WRONG").status == "resolved"
    assert resolve_letter(9999, lookup, "NOLETTER-WRONG").status == "unresolved"


def test_resolve_workflow_status_sin_default_en_ningun_caso():
    lookup = {"Terminado": "Validated"}
    assert resolve_workflow_status(None, lookup).status == "unresolved"
    assert resolve_workflow_status("Terminado", lookup).status == "resolved"
    assert resolve_workflow_status("Cancelado", lookup).status == "unresolved"


def test_normalize_lookup_key_recorta_decimal_artificial():
    assert normalize_lookup_key(258.0) == "258"
    assert normalize_lookup_key("258.0") == "258"
    assert normalize_lookup_key(None) is None


def test_write_csv_respeta_output_spec(tmp_path):
    spec = OutputSpec(
        filename="out.csv", encoding="utf-8", bom=False, delimiter="\t",
        quoting="minimal", line_terminator="\r\n", include_header=True,
    )
    out = write_csv([{"A": "1", "B": "2"}], ["A", "B"], tmp_path / "out.csv", spec)
    assert out.read_bytes() == b"A\tB\r\n1\t2\r\n"


def test_write_csv_nunca_sobrescribe(tmp_path):
    spec = OutputSpec(
        filename="out.csv", encoding="utf-8", bom=False, delimiter=",",
        quoting="minimal", line_terminator="\n", include_header=True,
    )
    path = tmp_path / "out.csv"
    write_csv([{"A": "1"}], ["A"], path, spec)
    with pytest.raises(FileExistsError):
        write_csv([{"A": "2"}], ["A"], path, spec)


def test_drills_bypass_y_safety_meetings_comparten_la_misma_funcion_no_una_copia():
    """Prueba de identidad (`is`, no solo de comportamiento): confirma que
    los tres módulos apuntan al MISMO objeto función del Engine tras
    Sprint 9.8 -- si algún módulo volviera a copiar en vez de importar,
    esta comparación por identidad lo detectaría aunque el comportamiento
    siguiera pareciendo correcto."""
    from src.export.prototype.bypass import transformations as bypass_tr
    from src.export.prototype.drills import transformations as drills_tr
    from src.export.prototype.safety_meetings import transformations as sm_tr

    assert drills_tr.to_historical_id is to_historical_id
    assert bypass_tr.to_historical_id is to_historical_id
    assert sm_tr.to_historical_id is to_historical_id

    assert drills_tr.resolve_letter is resolve_letter
    assert bypass_tr.resolve_lookup is resolve_letter

    assert drills_tr.resolve_workflow_status is resolve_workflow_status
    assert sm_tr.resolve_lookup is resolve_workflow_status

    assert drills_tr.LookupResult is LookupResult
    assert bypass_tr.LookupResult is LookupResult
    assert sm_tr.LookupResult is LookupResult

    from src.export.prototype.bypass.pipeline import write_csv as bypass_write_csv
    from src.export.prototype.drills.exporter import write_csv as drills_write_csv
    from src.export.prototype.safety_meetings.pipeline import write_csv as sm_write_csv

    assert drills_write_csv is write_csv
    assert bypass_write_csv is write_csv
    assert sm_write_csv is write_csv


# ---------------------------------------------------------------------------
# Output Contract -- encoding/BOM/quoting/delimiter (Micro-sprint 9.9.1)
#
# Datos 100% sintéticos -- ningún valor real de cliente. "Prevención.ITP_BES"
# se usa aquí como caso de prueba porque reproduce EXACTAMENTE el patrón del
# mojibake real reportado (acento propagado a mojibake por falta de BOM), no
# porque sea un valor de cliente -- es un literal ya público en
# config/exports/bypass.yaml (CS_HistoricalDataOrigin, `default`).
# ---------------------------------------------------------------------------

def _contract_output_spec(**overrides) -> OutputSpec:
    base = dict(
        filename="out.csv", encoding="utf-8", bom=True, delimiter="\t",
        quoting="minimal", line_terminator="\r\n", include_header=True,
    )
    base.update(overrides)
    return OutputSpec(**base)


def test_resolve_text_encoding_bom_true_utf8_usa_sig():
    assert resolve_text_encoding(_contract_output_spec(bom=True, encoding="utf-8")) == "utf-8-sig"


def test_resolve_text_encoding_bom_false_usa_encoding_declarado_sin_modificar():
    assert resolve_text_encoding(_contract_output_spec(bom=False, encoding="utf-8")) == "utf-8"


def test_resolve_text_encoding_bom_true_pero_encoding_no_utf8_no_se_toca():
    """`-sig` es un mecanismo específico de la familia UTF-8 -- para
    cualquier otro encoding (p. ej. un futuro módulo con Latin-1),
    `resolve_text_encoding` no debe inventar un comportamiento."""
    assert resolve_text_encoding(_contract_output_spec(bom=True, encoding="latin-1")) == "latin-1"


def test_write_csv_con_bom_true_produce_bytes_bom_utf8(tmp_path):
    spec = _contract_output_spec(bom=True)
    out = write_csv([{"A": "1"}], ["A"], tmp_path / "out.csv", spec)
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")


def test_write_csv_sin_bom_no_produce_bytes_bom(tmp_path):
    spec = _contract_output_spec(bom=False)
    out = write_csv([{"A": "1"}], ["A"], tmp_path / "out.csv", spec)
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("valor", [
    "Prevención.ITP_BES",  # acento -- el caso real reportado
    "Servicio Prevención LA RÁBIDA",  # ñpicos/tildes adicionales, ver CLAUDE.md
    "año, ñoño, José",  # ñ explícita, varias posiciones
    "维护会议",  # CJK -- NameZH del fan-out cloneorigin (CLAUDE.md), imposible en Latin-1
    "Café — SGA/Niño",  # em-dash + ñ combinados
])
def test_write_csv_preserva_unicode_bajo_el_contrato_corregido(tmp_path, valor):
    """Round-trip completo escritura+lectura bajo el Output Contract
    corregido (bom=True) -- ningún carácter se pierde ni se corrompe. La
    causa del mojibake real NO era una escritura incorrecta (ver Fase 1 del
    informe: bytes UTF-8 ya correctos) -- este test demuestra que sigue
    siéndolo, con BOM añadido para que un lector sin autodetección de UTF-8
    (Excel en Windows) no lo confunda con Latin-1/Windows-1252."""
    spec = _contract_output_spec(bom=True)
    out = write_csv([{"Valor": valor}], ["Valor"], tmp_path / "out.csv", spec)
    encoding = resolve_text_encoding(spec)
    text = out.read_text(encoding=encoding)
    row = text.splitlines()[1]
    assert valor in row


def test_write_csv_delimitador_dentro_de_un_valor_queda_citado(tmp_path):
    spec = _contract_output_spec(quoting="minimal")
    out = write_csv([{"Valor": "A\tB"}], ["Valor"], tmp_path / "out.csv", spec)
    text = out.read_text(encoding=resolve_text_encoding(spec))
    assert '"A\tB"' in text


def test_write_csv_comillas_dentro_de_un_valor_se_escapan_doblando(tmp_path):
    spec = _contract_output_spec(quoting="minimal")
    out = write_csv([{"Valor": 'dice "hola"'}], ["Valor"], tmp_path / "out.csv", spec)
    text = out.read_text(encoding=resolve_text_encoding(spec))
    assert '"dice ""hola"""' in text


def test_write_csv_valor_vacio_se_representa_como_cadena_vacia_no_null(tmp_path):
    spec = _contract_output_spec()
    out = write_csv([{"A": "", "B": "x"}], ["A", "B"], tmp_path / "out.csv", spec)
    text = out.read_text(encoding=resolve_text_encoding(spec))
    data_row = text.splitlines()[1]
    assert data_row.startswith("\tx") or data_row.startswith('""\tx')
    assert "None" not in text and "NULL" not in text.upper().replace("NULLCONTROL", "")


def test_write_csv_line_endings_son_crlf(tmp_path):
    spec = _contract_output_spec(line_terminator="\r\n")
    out = write_csv([{"A": "1"}, {"A": "2"}], ["A"], tmp_path / "out.csv", spec)
    raw = out.read_bytes()
    assert b"\r\n" in raw
    assert raw.count(b"\r\n") == 3  # cabecera + 2 filas, cada una con su propio terminador


def test_validate_csv_structure_con_bom_no_deja_ufeff_colgando(tmp_path):
    """Confirma el hallazgo de la Fase 3 del micro-sprint: antes de este
    fix, `validate_csv_structure` decodificaba con `output_spec.encoding` a
    secas -- con bom=True dejaba U+FEFF en el primer valor de cabecera y
    esta comprobación habría fallado."""
    spec = _contract_output_spec(bom=True)
    out = write_csv([{"A": "1", "B": "2"}], ["A", "B"], tmp_path / "out.csv", spec)
    result = validate_csv_structure(out, ["A", "B"], spec)
    assert result.is_valid, result.issues
    assert result.columns == ["A", "B"]
    assert not result.columns[0].startswith("﻿")


def test_los_tres_modulos_declaran_el_mismo_output_contract():
    """Confirma que la corrección del Output Contract se aplicó como UNA
    decisión compartida, no tres correcciones independientes que podrían
    haber divergido -- los 3 YAML declaran exactamente los mismos
    encoding/bom/delimiter/quoting/line_terminator."""
    from src.export.prototype.bypass.config import load_bypass_config
    from src.export.prototype.drills.config import load_drills_config
    from src.export.prototype.safety_meetings.config import load_safety_meetings_config

    drills_out = load_drills_config().output
    bypass_out = load_bypass_config().output
    sm_out = load_safety_meetings_config().output

    for other in (bypass_out, sm_out):
        assert other.encoding == drills_out.encoding
        assert other.bom == drills_out.bom
        assert other.delimiter == drills_out.delimiter
        assert other.quoting == drills_out.quoting
        assert other.line_terminator == drills_out.line_terminator

    assert drills_out.bom is True  # el contrato corregido -- ver Informe-Micro-Sprint-9.9.1
