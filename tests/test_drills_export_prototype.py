"""Tests unitarios del prototipo de exportación de Drills (sin red, sin
tocar SQL Server real -- ver test_drills_export_integration.py para el test
opt-in contra la base de datos real).

Ejecutar con: pytest tests/test_drills_export_prototype.py -v
"""
import csv as csv_module
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.db.exceptions import ReadOnlyViolationError
from src.db.query_runner import validate_read_only_sql
from src.export.prototype.drills import mappings as m
from src.export.prototype.drills import transformations as tr
from src.export.prototype.drills.config import load_drills_config
from src.export.prototype.drills.exporter import write_csv
from src.export.prototype.drills.extractor import MODE_SAMPLE, extract_drills
from src.export.prototype.drills.manifest import build_export_manifest


# --------------------------------------------------------------------------
# 1. Reference válida
# --------------------------------------------------------------------------

def test_reference_valida_caso_exacto_del_incremento():
    starting_date = tr.parse_starting_date("2010-03-08 12:30:45")
    result = tr.build_reference("PEI1", tr.to_historical_id(440), starting_date)
    assert result.value == "PEI1-HIST-440-08/03/2010"
    assert result.is_valid


# --------------------------------------------------------------------------
# 2. StartingDate con hora
# --------------------------------------------------------------------------

def test_starting_date_con_hora():
    parsed = tr.parse_starting_date("08/03/2010 12:30:45")
    assert parsed == datetime(2010, 3, 8, 12, 30, 45)


# --------------------------------------------------------------------------
# 3. StartingDate como datetime
# --------------------------------------------------------------------------

def test_starting_date_como_datetime_ya_materializado():
    value = datetime(2010, 3, 8, 12, 30, 45)
    assert tr.parse_starting_date(value) == value


# --------------------------------------------------------------------------
# 2b. StartingDate = Fecha + Hora (Sprint 9.3 -- regla reconstruida, ver
# docs/07-developer-guide/drills-startingdate-rule.md). Datos sintéticos,
# ninguno real.
# --------------------------------------------------------------------------

def test_fecha_mas_hora_normal():
    """1. Fecha + Hora normal -- caso central de la regla verificada."""
    parsed = tr.parse_starting_date("08/03/2010", "16:10")
    assert parsed == datetime(2010, 3, 8, 16, 10)


def test_fecha_mas_hora_00_00():
    """2. Hora '00:00' explícita -- se aplica igual que cualquier otra
    hora válida (no es un caso especial de 'vacío')."""
    parsed = tr.parse_starting_date("08/03/2010", "00:00")
    assert parsed == datetime(2010, 3, 8, 0, 0)


@pytest.mark.parametrize("hora_nula", [None, "", "   "])
def test_hora_null_o_vacia_degrada_a_solo_fecha(hora_nula):
    """3. Hora NULL/vacía -- StartingDate usa solo la fecha, comportamiento
    IDÉNTICO al de antes de este incremento. Nunca inventa una hora."""
    parsed = tr.parse_starting_date("08/03/2010", hora_nula)
    assert parsed == datetime(2010, 3, 8)


def test_fecha_null_devuelve_none_independientemente_de_hora():
    """4. Fecha NULL -- sigue devolviendo None aunque Hora sea válida (Hora
    nunca sustituye a una Fecha ausente)."""
    assert tr.parse_starting_date(None, "16:10") is None
    assert tr.parse_starting_date("", "16:10") is None


def test_hora_un_solo_digito_formato_realmente_observado():
    """5. Formato de hora realmente observado en el histórico (ver
    drills-startingdate-rule.md): 'H:MM', un solo dígito de hora, sin cero
    a la izquierda -- confirmado como válido en el 99,97% de las filas
    cruzadas."""
    parsed = tr.parse_starting_date("08/03/2010", "9:05")
    assert parsed == datetime(2010, 3, 8, 9, 5)


def test_hora_nunca_tiene_segundos():
    """6. Segundos -- 'Hora' (varchar(5)) no tiene componente de segundos;
    si 'Fecha' llegara con segundos propios, el segundo de Hora (siempre
    0) reemplaza igualmente el tiempo completo -- no se conservan segundos
    residuales de Fecha una vez Hora es válida."""
    parsed = tr.parse_starting_date("08/03/2010 12:30:45", "16:10")
    assert parsed == datetime(2010, 3, 8, 16, 10)
    assert parsed.second == 0


@pytest.mark.parametrize("hora_invalida", ["11:", "1:", "2:.30", "25:00", "12:60", "mediodia"])
def test_hora_invalida_degrada_a_solo_fecha_sin_crashear(hora_invalida):
    """7. Input inválido -- formatos corruptos realmente observados en el
    histórico (ver drills-startingdate-rule.md, 4/12091 filas) degradan a
    solo fecha, nunca lanzan excepción ni inventan una hora."""
    parsed = tr.parse_starting_date("08/03/2010", hora_invalida)
    assert parsed == datetime(2010, 3, 8)
    assert tr.parse_hora(hora_invalida) is None


def test_formato_final_starting_date_sin_regresion():
    """8. No regresión del formato final esperado por el Project Contract
    ('dd/MM/yyyy HH:mm') -- ver config/exports/drills.yaml."""
    parsed = tr.parse_starting_date("08/03/2010", "16:10")
    assert tr.format_starting_date(parsed) == "08/03/2010 16:10"


# --------------------------------------------------------------------------
# 4. CS_HistoricalOriginID numérico entero
# --------------------------------------------------------------------------

def test_historical_origin_id_entero():
    assert tr.to_historical_id(440) == "440"


# --------------------------------------------------------------------------
# 5. CS_HistoricalOriginID leído como 440.0
# --------------------------------------------------------------------------

def test_historical_origin_id_leido_como_float_sin_decimales():
    assert tr.to_historical_id(440.0) == "440"


def test_historical_origin_id_numpy_int64_no_se_pierde():
    np = pytest.importorskip("numpy")
    assert tr.to_historical_id(np.int64(440)) == "440"


# --------------------------------------------------------------------------
# 6. Typology con espacios laterales
# --------------------------------------------------------------------------

def test_typology_con_espacios_laterales_se_recorta():
    starting_date = tr.parse_starting_date("08/03/2010")
    result = tr.build_reference("  PEI1  ", "440", starting_date)
    assert result.value == "PEI1-HIST-440-08/03/2010"


# --------------------------------------------------------------------------
# 7. Campo obligatorio vacío
# --------------------------------------------------------------------------

def test_campo_obligatorio_vacio_no_construye_reference_artificial():
    starting_date = tr.parse_starting_date("08/03/2010")
    result = tr.build_reference(None, "440", starting_date)
    assert result.value is None
    assert "missing_typology" in result.missing_components
    assert not result.is_valid


def test_los_tres_componentes_ausentes_se_reportan_todos():
    result = tr.build_reference(None, None, None)
    assert set(result.missing_components) == {
        "missing_typology", "missing_historical_origin_id", "missing_starting_date",
    }


# --------------------------------------------------------------------------
# 8. Fecha inválida
# --------------------------------------------------------------------------

def test_fecha_invalida_devuelve_none():
    assert tr.parse_starting_date("no-es-una-fecha") is None


def test_fecha_vacia_devuelve_none():
    assert tr.parse_starting_date(None) is None
    assert tr.parse_starting_date("") is None


# --------------------------------------------------------------------------
# 9-12. Mapping de entidad
# --------------------------------------------------------------------------

def _fake_catalog(key_to_codes, do_not_migrate_literal="No migra"):
    conflicting = {k: sorted(v) for k, v in key_to_codes.items() if len(v) > 1}
    return m.EntityCatalog(
        key_to_codes=key_to_codes,
        conflicting_keys=conflicting,
        do_not_migrate_literal=do_not_migrate_literal,
        source_path="<test>",
        row_count=sum(len(v) for v in key_to_codes.values()),
    )


def test_mapping_de_entidad_resuelto():
    catalog = _fake_catalog({"278": {"MCPF.HIS"}})
    result = m.resolve_entity(278, catalog)
    assert result.status == m.RESOLVED
    assert result.value == "MCPF.HIS"


def test_mapping_de_entidad_no_migra():
    catalog = _fake_catalog({"521": {"No migra"}})
    result = m.resolve_entity(521, catalog)
    assert result.status == m.DO_NOT_MIGRATE
    assert result.value == "No migra"


def test_mapping_de_entidad_unresolved():
    catalog = _fake_catalog({"278": {"MCPF.HIS"}})
    result = m.resolve_entity(999999, catalog)
    assert result.status == m.UNRESOLVED
    assert result.value is None


def test_mapping_de_entidad_conflicting():
    catalog = _fake_catalog({"278": {"MCPF.HIS", "MCPF.OTRO"}})
    result = m.resolve_entity(278, catalog)
    assert result.status == m.CONFLICTING
    assert result.value is None


def test_mapping_de_entidad_empty():
    catalog = _fake_catalog({"278": {"MCPF.HIS"}})
    result = m.resolve_entity(None, catalog)
    assert result.status == m.EMPTY


def test_catalogo_real_del_repositorio_carga_sin_conflictos_conocidos():
    """Confirma contra el CSV normalizado real (no un fixture) que la
    resolución de simulacros.Drills sigue siendo la esperada -- 655 claves
    distintas, 0 conflictos, ver auditoría del incremento de especificación."""
    cfg = load_drills_config()
    rd = cfg.reference_data
    catalog = m.get_entity_catalog(
        rd["entity_catalog_csv"],
        key_column=rd["entity_catalog_key_column"],
        value_column=rd["entity_catalog_value_column"],
        do_not_migrate_literal=rd["entity_catalog_do_not_migrate_literal"],
    )
    assert catalog.row_count == 680
    assert len(catalog.conflicting_keys) == 0
    resolved = m.resolve_entity(278, catalog)
    assert resolved.status == m.RESOLVED
    assert resolved.value == "MCPF.HIS"


# --------------------------------------------------------------------------
# Lookups documentados: tipología / letra / estado
# --------------------------------------------------------------------------

def test_typology_lookup_resuelto():
    result = tr.resolve_typology(379, {379: "PEI1"}, "NADA")
    assert result.value == "PEI1"
    assert result.status == "resolved"


def test_typology_lookup_default_documentado_no_inventado():
    result = tr.resolve_typology(999999, {379: "PEI1"}, "NADA")
    assert result.value == "NADA"
    assert result.status == "default_no_match"


def test_letter_lookup_null_default_literal_exacto():
    result = tr.resolve_letter(None, {258: "A"}, "NOLETTER-WRONG")
    assert result.value == "NOLETTER-WRONG"
    assert result.status == "null_default"


def test_letter_lookup_valor_no_listado_queda_unresolved_no_inventa():
    result = tr.resolve_letter(9999, {258: "A"}, "NOLETTER-WRONG")
    assert result.value is None
    assert result.status == "unresolved"


def test_workflow_status_colapsa_terminado_y_aprobado_a_validated():
    lookup = {"Terminado": "Validated", "Aprobado": "Validated", "En Curso": "Pending validation", "Iniciado": "Draft"}
    assert tr.resolve_workflow_status("Terminado", lookup).value == "Validated"
    assert tr.resolve_workflow_status("Aprobado", lookup).value == "Validated"


def test_workflow_status_no_listado_no_inventa_default():
    lookup = {"Terminado": "Validated"}
    result = tr.resolve_workflow_status("Cancelado", lookup)
    assert result.value is None
    assert result.status == "unresolved"


# --------------------------------------------------------------------------
# 13-16. CSV: UTF-8, sin índice, orden de columnas, escritura atómica
# --------------------------------------------------------------------------

from src.export.prototype.drills.config import OutputSpec  # noqa: E402


def _output_spec(**overrides):
    base = dict(
        filename="drills.csv", encoding="utf-8", bom=False, delimiter="\t",
        quoting="minimal", line_terminator="\r\n", include_header=True,
    )
    base.update(overrides)
    return OutputSpec(**base)


def test_csv_generado_es_utf8_sin_bom(tmp_path):
    rows = [{"A": "áéí", "B": "1"}]
    out = write_csv(rows, ["A", "B"], tmp_path / "out" / "drills.csv", _output_spec())
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    assert "áéí" in text


def test_csv_no_tiene_indice_tecnico_de_dataframe(tmp_path):
    rows = [{"A": "x", "B": "y"}]
    out = write_csv(rows, ["A", "B"], tmp_path / "drills.csv", _output_spec())
    with open(out, encoding="utf-8", newline="") as f:
        reader = csv_module.reader(f, delimiter="\t")
        header = next(reader)
    assert header == ["A", "B"]  # ninguna columna "Unnamed: 0" ni índice numérico.


def test_orden_de_columnas_respetado(tmp_path):
    rows = [{"A": "1", "B": "2", "C": "3"}]
    out = write_csv(rows, ["C", "A", "B"], tmp_path / "drills.csv", _output_spec())
    with open(out, encoding="utf-8", newline="") as f:
        reader = csv_module.reader(f, delimiter="\t")
        header = next(reader)
    assert header == ["C", "A", "B"]


def test_escritura_atomica_no_sobrescribe_existente(tmp_path):
    path = tmp_path / "drills.csv"
    write_csv([{"A": "1"}], ["A"], path, _output_spec())
    with pytest.raises(FileExistsError):
        write_csv([{"A": "2"}], ["A"], path, _output_spec())


def test_escritura_atomica_no_deja_temporales_tras_exito(tmp_path):
    out_dir = tmp_path / "out"
    write_csv([{"A": "1"}], ["A"], out_dir / "drills.csv", _output_spec())
    leftovers = [p for p in out_dir.iterdir() if p.name != "drills.csv"]
    assert leftovers == []


# --------------------------------------------------------------------------
# 17. Manifiesto sin secretos
# --------------------------------------------------------------------------

def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def test_manifiesto_no_incluye_claves_de_credenciales(tmp_path):
    csv_path = tmp_path / "drills.csv"
    csv_path.write_text("A\tB\n1\t2\n", encoding="utf-8")
    manifest = build_export_manifest(
        run_id="abc123", timestamp="20260101T000000Z",
        config_raw={"output": {"encoding": "utf-8", "delimiter": "\t", "bom": False, "line_terminator": "\r\n"}, "reference_data": {}},
        sql_text="SELECT 1", csv_path=csv_path, row_count=1, columns=["A", "B"],
        connection_name="prevencion", mode="sample", evidence_ids=["x"],
        limitations=[], open_questions=[], sql_source_evidence_id="evidence:x",
    )
    keys = set(_walk_keys(manifest))
    forbidden = {"password", "pwd", "secret", "connection_string"}
    assert not (keys & forbidden)
    assert manifest["approved_for_enablon_import"] is False


# --------------------------------------------------------------------------
# 18. Hashes deterministas
# --------------------------------------------------------------------------

def test_hashes_deterministas_misma_entrada_mismo_hash(tmp_path):
    csv_path = tmp_path / "drills.csv"
    csv_path.write_text("A\tB\n1\t2\n", encoding="utf-8")
    kwargs = dict(
        run_id="abc123", timestamp="20260101T000000Z",
        config_raw={"output": {"encoding": "utf-8", "delimiter": "\t", "bom": False, "line_terminator": "\r\n"}, "reference_data": {}},
        sql_text="SELECT 1", csv_path=csv_path, row_count=1, columns=["A", "B"],
        connection_name="prevencion", mode="sample", evidence_ids=["x"],
        limitations=[], open_questions=[], sql_source_evidence_id="evidence:x",
    )
    m1 = build_export_manifest(**kwargs)
    m2 = build_export_manifest(**kwargs)
    assert m1["hashes"] == m2["hashes"]


# --------------------------------------------------------------------------
# 19. Modo sample respeta el límite
# --------------------------------------------------------------------------

def test_modo_sample_respeta_el_limite(monkeypatch):
    import pandas as pd

    fake_df = pd.DataFrame({"IDSimulacro": range(500)})

    def _fake_run_query(sql, connection=None, source_file=None, **kwargs):
        return fake_df

    import src.export.prototype.drills.extractor as extractor_mod
    monkeypatch.setattr(extractor_mod, "run_query", _fake_run_query)

    config = load_drills_config()
    result = extract_drills(config, mode=MODE_SAMPLE, limit=100)
    assert len(result.dataframe) == 100
    assert result.rows_available_before_truncation == 500


def test_modo_sample_rechaza_limite_negativo():
    config = load_drills_config()
    with pytest.raises(ValueError):
        extract_drills(config, mode=MODE_SAMPLE, limit=-1)


# --------------------------------------------------------------------------
# 20. Consulta no permitida sigue bloqueada
# --------------------------------------------------------------------------

def test_consulta_no_permitida_sigue_bloqueada_por_query_runner():
    """El prototipo no introduce ningún atajo alrededor de
    `validate_read_only_sql` -- se reconfirma aquí que sigue rechazando
    sentencias de escritura, exactamente igual que antes de este
    incremento (ver tests/test_db_query_runner.py)."""
    with pytest.raises(ReadOnlyViolationError):
        validate_read_only_sql("DROP TABLE ITP_SIMULACRO")
    with pytest.raises(ReadOnlyViolationError):
        validate_read_only_sql("INSERT INTO ITP_SIMULACRO (IDSimulacro) VALUES (1)")


def test_extractor_usa_la_sql_de_evidencia_sin_modificarla():
    config = load_drills_config()
    sql_text = config.source.sql_path.read_text(encoding="utf-8-sig")
    # No debe lanzar -- confirma que la SQL de Drills sigue siendo un SELECT
    # de solo lectura válido tal cual está en el repositorio.
    validate_read_only_sql(sql_text)
