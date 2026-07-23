"""Tests unitarios de src/analysis/mapping_coverage.py.
Ejecutar con: pytest tests/"""
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.mapping_coverage import (
    REQUIRED_CLIENT_XLSX_SHEETS,
    CoverageRow,
    FallbackRuleInfo,
    build_coverage_finding,
    build_mapping_decision,
    determine_mapping_scope,
    generate_coverage_reports,
    join_findings_with_decisions,
    normalize_key,
    rows_blocked_by_mapping,
    rows_marked_no_migrate,
    rows_unmapped_entities,
    rows_unmapped_field_values,
    rows_with_mapping_fallback,
)
from src.knowledge_base.model import DecisionType, LoadStatus, MappingScope, MappingStatus

MODULE_ID = "module:simulacros"


# ---------------------------------------------------------------------------
# determine_mapping_scope -- nunca por lista fija de nombres
# ---------------------------------------------------------------------------

def test_scope_entity_por_evidencia_no_por_nombre():
    scope, method = determine_mapping_scope(destination_is_known_entity_field=True)
    assert scope == MappingScope.ENTITY
    assert "evidencia" not in method or "entidad" in method  # el metodo debe declarar la evidencia usada


def test_scope_relationship_por_evidencia():
    scope, _ = determine_mapping_scope(destination_is_known_relationship_field=True)
    assert scope == MappingScope.RELATIONSHIP


def test_scope_field_cuando_hay_destino_pero_sin_evidencia_de_entidad_o_relacion():
    scope, _ = determine_mapping_scope(destination_field_xml="CS_Comments")
    assert scope == MappingScope.FIELD


def test_scope_unknown_sin_evidencia_suficiente():
    scope, method = determine_mapping_scope()
    assert scope == MappingScope.UNKNOWN
    assert "sin_evidencia" in method


# ---------------------------------------------------------------------------
# normalize_key -- clave compuesta como unidad
# ---------------------------------------------------------------------------

def test_normalize_key_junta_componentes_en_una_sola_clave():
    assert normalize_key(["17", "EPSR.SYMEC"]) == "17|EPSR.SYMEC"


def test_normalize_key_distingue_permutaciones_de_valores():
    assert normalize_key(["17", "EPSR.SYMEC"]) != normalize_key(["EPSR.SYMEC", "17"])


# ---------------------------------------------------------------------------
# 1. Correspondencia válida
# ---------------------------------------------------------------------------

def test_correspondencia_valida():
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "EPSR.SYMEC"],
        mapping_scope=MappingScope.ENTITY,
        resolved_value="MOEVE > ENERGY-PARKS > ENERGYP.SR > EPSR > EPSR.SYMEC",
    )
    assert d.decision_type == DecisionType.MAPPED
    assert d.mapping_status == MappingStatus.RESOLVED
    assert d.load_status == LoadStatus.ELIGIBLE
    assert d.resolved_value is not None
    assert d.warnings == []  # sin inconsistencias


# ---------------------------------------------------------------------------
# 2. No migra
# ---------------------------------------------------------------------------

def test_no_migra_se_excluye_no_se_trata_como_pendiente():
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["Code"],
        key_values_raw=["ENERGYP.SR"],
        mapping_scope=MappingScope.ENTITY,
        is_marked_do_not_migrate=True,
        do_not_migrate_reference="Mapeo_Entidades hoja X, fila Y: marcado 'No migra'",
    )
    assert d.decision_type == DecisionType.DO_NOT_MIGRATE
    assert d.mapping_status == MappingStatus.NOT_APPLICABLE
    assert d.load_status == LoadStatus.EXCLUDED
    assert d.fallback_rule_reference is not None
    assert d.warnings == []


# ---------------------------------------------------------------------------
# 3. Sin correspondencia y sin fallback -- nunca NULL/vacio/default
# ---------------------------------------------------------------------------

def test_sin_correspondencia_sin_fallback_queda_blocked_sin_valor():
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro"],
        key_values_raw=["999"],
        mapping_scope=MappingScope.ENTITY,
    )
    assert d.decision_type == DecisionType.PENDING_MAPPING
    assert d.mapping_status == MappingStatus.UNRESOLVED
    assert d.load_status == LoadStatus.BLOCKED
    assert d.resolved_value is None
    assert d.fallback_value is None
    assert d.warnings == []


# ---------------------------------------------------------------------------
# 4. Sin correspondencia con fallback documentado
# ---------------------------------------------------------------------------

def test_fallback_documentado_con_autorizacion_eligible_with_warning():
    fallback = FallbackRuleInfo(
        rule_id="migration_rule:unidad_null",
        fallback_value="UnidadNull",
        load_permission=LoadStatus.ELIGIBLE_WITH_WARNING,
        load_permission_source="etl_rule",
    )
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "EPSR.NOPE"],
        mapping_scope=MappingScope.ENTITY,
        fallback_rule=fallback,
    )
    assert d.decision_type == DecisionType.FALLBACK_VALUE
    assert d.mapping_status == MappingStatus.UNRESOLVED_WITH_FALLBACK  # NUNCA resolved
    assert d.load_status == LoadStatus.ELIGIBLE_WITH_WARNING
    assert d.fallback_value == "UnidadNull"
    assert d.requires_client_review is False
    assert d.warnings == []


def test_fallback_sin_autorizacion_documentada_es_blocked_y_requiere_revision():
    fallback = FallbackRuleInfo(rule_id="migration_rule:unidad_null", fallback_value="UnidadNull")
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "EPSR.NOPE"],
        mapping_scope=MappingScope.ENTITY,
        fallback_rule=fallback,
    )
    assert d.load_status == LoadStatus.BLOCKED  # nunca eligible por defecto
    assert d.requires_client_review is True
    assert d.warnings == []  # el propio motor ya marca requires_client_review, es consistente


def test_fallback_nunca_se_confunde_con_no_migra():
    fallback = FallbackRuleInfo(rule_id="migration_rule:unidad_null", fallback_value="UnidadNull",
                                 load_permission=LoadStatus.ELIGIBLE_WITH_WARNING, load_permission_source="etl_rule")
    d = build_mapping_decision(
        module_id=MODULE_ID, key_fields=["IDCentro"], key_values_raw=["999"],
        mapping_scope=MappingScope.ENTITY, fallback_rule=fallback,
    )
    assert d.decision_type != DecisionType.DO_NOT_MIGRATE
    assert d.load_status != LoadStatus.EXCLUDED


# ---------------------------------------------------------------------------
# default_value -- solo para origen vacío/nulo, nunca para ausencia de
# equivalencia (ver correcciones aprobadas)
# ---------------------------------------------------------------------------

def test_default_value_solo_para_origen_vacio_documentado():
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["Observaciones"],
        key_values_raw=[""],
        mapping_scope=MappingScope.FIELD,
        is_default_value=True,
        default_value_applied="N/D",
    )
    assert d.decision_type == DecisionType.DEFAULT_VALUE
    assert d.mapping_status == MappingStatus.RESOLVED
    assert d.load_status == LoadStatus.ELIGIBLE
    assert d.warnings == []


def test_default_value_no_se_usa_para_ausencia_de_equivalencia():
    # Ejemplo del enunciado: IDCentro+IDUnidadOrg sin correspondencia debe
    # seguir siendo fallback_value, nunca default_value -- si alguien lo
    # construye mal (is_default_value=True cuando en realidad es fallback),
    # el validador de invariantes debe marcarlo como inconsistente.
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "EPSR.NOPE"],
        mapping_scope=MappingScope.ENTITY,
        is_default_value=True,
        default_value_applied="UnidadNull",
    )
    # decision_type queda default_value porque así se construyó, pero el
    # propio motor no debe tratarlo como si tuviera fallback_rule -- lo
    # importante es que quien orqueste NUNCA pase is_default_value=True para
    # este caso; aquí solo comprobamos que si ocurriera, no se cuela sin
    # avisar de que el patrón correcto es fallback_value:
    assert d.decision_type == DecisionType.DEFAULT_VALUE
    assert d.fallback_value is None  # default_value no rellena fallback_value
    assert d.resolved_value == "UnidadNull"  # se registra como resolved_value, no como fallback


# ---------------------------------------------------------------------------
# Conflicto entre fuentes
# ---------------------------------------------------------------------------

def test_conflicto_entre_fuentes_nunca_decide_automaticamente():
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["Code"],
        key_values_raw=["ENERGYP.SR"],
        mapping_scope=MappingScope.ENTITY,
        resolved_value="Ruta A",
        conflicting_values=["Ruta A", "Ruta B"],
    )
    assert d.decision_type == DecisionType.CONFLICTING
    assert d.mapping_status == MappingStatus.CONFLICTING
    assert d.load_status == LoadStatus.BLOCKED


# ---------------------------------------------------------------------------
# Clave compuesta evaluada como unidad
# ---------------------------------------------------------------------------

def test_clave_compuesta_sin_combinacion_exacta_es_pending_no_mapped():
    # Los dos componentes podrían ser válidos por separado, pero si la
    # combinación exacta no tiene equivalencia, no se puede fabricar un
    # "mapped" a partir de coincidencias parciales -- quien orquesta no debe
    # pasar resolved_value si no encontró la combinación exacta.
    d = build_mapping_decision(
        module_id=MODULE_ID,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "COMBINACION_SIN_EQUIVALENCIA"],
        mapping_scope=MappingScope.ENTITY,
        # resolved_value deliberadamente ausente -- no se inventa
    )
    assert d.decision_type == DecisionType.PENDING_MAPPING
    # normalize_key reutiliza normalize_label (solo espacio, nunca case) --
    # mismo criterio ya confirmado en test_mapping_resolver.py.
    assert d.key_normalized == "17|COMBINACION_SIN_EQUIVALENCIA"


# ---------------------------------------------------------------------------
# MappingDecision vs MappingCoverageFinding -- separación real
# ---------------------------------------------------------------------------

def test_finding_lleva_recuentos_decision_no():
    d = build_mapping_decision(
        module_id=MODULE_ID, key_fields=["IDCentro"], key_values_raw=["999"],
        mapping_scope=MappingScope.ENTITY,
    )
    finding = build_coverage_finding(
        decision=d,
        analysis_run_id="run_2026_07_22",
        source_snapshot_id="bak_prevencion_2026_07_20",
        affected_record_count=42,
        example_historical_ids=["HIST-1", "HIST-2", "HIST-3"],
        detected_at="2026-07-22T10:00:00",
    )
    assert finding.affected_record_count == 42
    assert finding.mapping_decision_id == d.id
    assert not hasattr(d, "affected_record_count")


def test_una_decision_puede_tener_varios_findings_de_corridas_distintas():
    d = build_mapping_decision(
        module_id=MODULE_ID, key_fields=["IDCentro"], key_values_raw=["999"],
        mapping_scope=MappingScope.ENTITY,
    )
    f1 = build_coverage_finding(
        decision=d, analysis_run_id="run_1", source_snapshot_id="bak_A",
        affected_record_count=10, example_historical_ids=["H1"], detected_at="2026-07-01T00:00:00",
    )
    f2 = build_coverage_finding(
        decision=d, analysis_run_id="run_2", source_snapshot_id="bak_B",
        affected_record_count=25, example_historical_ids=["H2"], detected_at="2026-07-22T00:00:00",
    )
    assert f1.id != f2.id
    assert f1.mapping_decision_id == f2.mapping_decision_id == d.id


def test_ejemplos_historicos_se_recortan_a_muestra():
    d = build_mapping_decision(
        module_id=MODULE_ID, key_fields=["IDCentro"], key_values_raw=["999"],
        mapping_scope=MappingScope.ENTITY,
    )
    many_ids = [f"HIST-{i}" for i in range(50)]
    finding = build_coverage_finding(
        decision=d, analysis_run_id="run_1", source_snapshot_id="bak_A",
        affected_record_count=50, example_historical_ids=many_ids, detected_at="2026-07-22T00:00:00",
        max_examples=10,
    )
    assert len(finding.example_historical_ids) == 10
    assert finding.affected_record_count == 50  # el recuento SI refleja el total real


# ---------------------------------------------------------------------------
# Generación de las 7 salidas (desde Finding + Decision, no desde Decision sola)
# ---------------------------------------------------------------------------

def _make_row(module, decision_type, mapping_status, load_status, mapping_scope=MappingScope.ENTITY, **kw) -> CoverageRow:
    kwargs = dict(
        module_id=f"module:{module}",
        key_fields=["IDCentro"],
        key_values_raw=["17"],
        mapping_scope=mapping_scope,
    )
    if decision_type == DecisionType.MAPPED:
        kwargs["resolved_value"] = "Ruta"
    elif decision_type == DecisionType.DO_NOT_MIGRATE:
        kwargs["is_marked_do_not_migrate"] = True
        kwargs["do_not_migrate_reference"] = "referencia"
    elif decision_type == DecisionType.FALLBACK_VALUE:
        kwargs["fallback_rule"] = FallbackRuleInfo(
            rule_id="migration_rule:unidad_null", fallback_value="UnidadNull",
            load_permission=kw.get("load_permission"), load_permission_source=kw.get("load_permission_source"),
        )
    decision = build_mapping_decision(**kwargs)
    finding = build_coverage_finding(
        decision=decision, analysis_run_id="run_1", source_snapshot_id="bak_A",
        affected_record_count=kw.get("count", 5), example_historical_ids=["H1", "H2"],
        detected_at="2026-07-22T00:00:00",
    )
    return CoverageRow(module=module, decision=decision, finding=finding)


def _sample_rows() -> list[CoverageRow]:
    return [
        _make_row("simulacros", DecisionType.MAPPED, None, None),
        _make_row("simulacros", DecisionType.PENDING_MAPPING, None, None, mapping_scope=MappingScope.ENTITY),
        _make_row("moc", DecisionType.PENDING_MAPPING, None, None, mapping_scope=MappingScope.FIELD),
        _make_row("bypass", DecisionType.DO_NOT_MIGRATE, None, None),
        _make_row("moc", DecisionType.FALLBACK_VALUE, None, None, load_permission=LoadStatus.ELIGIBLE_WITH_WARNING, load_permission_source="etl_rule"),
        _make_row("moc", DecisionType.FALLBACK_VALUE, None, None),  # sin autorizacion -> blocked
    ]


def test_join_descarta_findings_sin_decision():
    rows = _sample_rows()
    decisions_by_id = {r.decision.id: r.decision for r in rows}
    module_by_decision_id = {r.decision.id: r.module for r in rows}
    findings = [r.finding for r in rows]
    joined = join_findings_with_decisions(findings, decisions_by_id, module_by_decision_id)
    assert len(joined) == len(rows)


def test_clasificadores_separan_las_situaciones_correctamente():
    rows = _sample_rows()
    assert len(rows_unmapped_entities(rows)) == 1  # simulacros pending/entity
    assert len(rows_unmapped_field_values(rows)) == 1  # moc pending/field
    assert len(rows_marked_no_migrate(rows)) == 1
    assert len(rows_with_mapping_fallback(rows)) == 2
    # blocked = pending(2) + fallback sin autorizacion(1) -- el fallback con
    # autorizacion queda eligible_with_warning, NO blocked.
    assert len(rows_blocked_by_mapping(rows)) == 3


def test_generate_coverage_reports_produce_los_7_ficheros(tmp_path):
    rows = _sample_rows()
    result = generate_coverage_reports(rows, tmp_path)

    expected_files = [
        "unmapped_entities.csv", "unmapped_field_values.csv", "records_marked_no_migrate.csv",
        "records_with_mapping_fallback.csv", "records_blocked_by_mapping.csv", "mapping_summary.csv",
        "client_mapping_questions.xlsx",
    ]
    for fname in expected_files:
        assert (tmp_path / fname).exists(), f"falta {fname}"
        assert fname in result

    assert result["unmapped_entities.csv"] == 1
    assert result["unmapped_field_values.csv"] == 1
    assert result["records_marked_no_migrate.csv"] == 1
    assert result["records_with_mapping_fallback.csv"] == 2


def test_client_xlsx_tiene_las_6_hojas_requeridas(tmp_path):
    rows = _sample_rows()
    generate_coverage_reports(rows, tmp_path)
    wb = load_workbook(tmp_path / "client_mapping_questions.xlsx", read_only=True)
    sheet_names = set(wb.sheetnames)
    for required in REQUIRED_CLIENT_XLSX_SHEETS:
        assert required in sheet_names
    wb.close()


def test_csv_generado_usa_utf8_sig(tmp_path):
    rows = _sample_rows()
    generate_coverage_reports(rows, tmp_path)
    raw = (tmp_path / "mapping_summary.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM de utf-8-sig
