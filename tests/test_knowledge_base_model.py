"""Tests unitarios del modelo de dominio del Migration Metadata Repository.
Ejecutar con: pytest tests/"""
import sys
from dataclasses import fields
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.knowledge_base.model import (
    ActionPlanProcessingStatus,
    ActionPlanRelationshipType,
    CrossModuleActionPlanBuffer,
    DecisionType,
    DependencySource,
    LoadPhase,
    LoadStatus,
    Mapping,
    MappingDecision,
    MappingScope,
    MappingStatus,
    MigrationObject,
    ProcessingScope,
    Relation,
    ResolutionStatus,
    build_action_plan_dependency_relation,
    looks_like_mojibake,
    make_csv_column_id,
    make_etl_sheet_id,
    make_etl_workbook_id,
    make_cross_module_action_plan_buffer_id,
    make_mapping_decision_id,
    make_module_id,
    make_query_id,
    make_relation_id,
    make_source_field_id,
    make_source_object_id,
    match_filename,
    normalize_nfc,
    short_hash,
    slugify,
    validate_action_plan_buffer_consistency,
    validate_action_plan_dependency_relation,
    validate_mapping_decision_consistency,
)


# ---------------------------------------------------------------------------
# Normalización / slugify / mojibake
# ---------------------------------------------------------------------------

def test_slugify_quita_acentos_y_normaliza_mayusculas():
    assert slugify("Simulacros") == "simulacros"
    assert slugify("Servicio Prevención LA RÁBIDA") == "servicio_prevencion_la_rabida"


def test_slugify_es_determinista():
    assert slugify("ITP_SIMULACRO") == slugify("ITP_SIMULACRO")


def test_slugify_colapsa_separadores_repetidos():
    assert slugify("A   B---C") == "a_b_c"


def test_normalize_nfc_idempotente():
    once = normalize_nfc("LESIÓN")
    assert normalize_nfc(once) == once


def test_looks_like_mojibake_detecta_patron_conocido():
    assert looks_like_mojibake("LESI├ôN") is True
    assert looks_like_mojibake("LESIÓN") is False


def test_match_filename_exacto():
    m = match_filename("SM2025.sql", "SM2025.sql")
    assert m.matched and m.exact
    assert m.warning is None


def test_match_filename_nfc_resuelve_solo_diferencias_de_composicion():
    # NFC arregla dos representaciones DEL MISMO caracter (composicion
    # distinta, mismo caracter abstracto): 'O' precompuesta (chr(0x00D3))
    # frente a 'O' + acento agudo combinante (chr(0x004F) + chr(0x0301)).
    # Construidas con chr() explicito para no depender de como el editor
    # normalice un literal con tilde.
    o_precompuesta = chr(0x00D3)
    o_descompuesta = chr(0x004F) + chr(0x0301)
    assert o_precompuesta != o_descompuesta  # distintos a nivel de code point

    precompuesta = "LESI" + o_precompuesta + "N.sql"
    descompuesta = "LESI" + o_descompuesta + "N.sql"
    m = match_filename(descompuesta, precompuesta)
    assert m.matched is True
    assert m.exact is False
    assert m.required_nfc_normalization is True
    assert m.required_mojibake_repair is False


def test_match_filename_repara_mojibake_como_mecanismo_separado_de_nfc():
    # "LESI├ôN" es la forma corrompida ya vista en el repo (bytes UTF-8 de
    # 'Ó' reinterpretados como CP437); "LESIÓN" la correcta. NFC por sí solo
    # NO empareja esto -- requiere el mecanismo de reparación de mojibake.
    m = match_filename(
        "SQLQuery- LOCALIZACION  DE LESI├ôN ANTIGUOS.sql",
        "SQLQuery- LOCALIZACION  DE LESIÓN ANTIGUOS.sql",
    )
    assert m.matched is True
    assert m.exact is False
    assert m.required_nfc_normalization is False
    assert m.required_mojibake_repair is True
    assert m.mojibake_suspected_in == "candidate"
    assert m.warning is not None and "mojibake" in m.warning.lower()


def test_match_filename_nfc_solo_no_repara_mojibake_real():
    # Confirma explícitamente que NFC por sí solo NO resuelve el caso de
    # mojibake -- son mecanismos distintos, no debe colarse una falsa
    # coincidencia NFC en un caso que en realidad necesita reparación.
    nfc_candidato = normalize_nfc("SQLQuery- LOCALIZACION  DE LESI├ôN ANTIGUOS.sql")
    nfc_referencia = normalize_nfc("SQLQuery- LOCALIZACION  DE LESIÓN ANTIGUOS.sql")
    assert nfc_candidato.lower() != nfc_referencia.lower()


def test_match_filename_no_coincide_si_son_realmente_distintos():
    m = match_filename("Events-20072026-6.csv", "Impacts-20072026-9.csv")
    assert m.matched is False


# ---------------------------------------------------------------------------
# IDs deterministas
# ---------------------------------------------------------------------------

def test_ids_son_deterministas_no_aleatorios():
    assert make_module_id("simulacros") == make_module_id("simulacros")
    assert make_module_id("Simulacros") == make_module_id("simulacros")


def test_ids_distintos_para_entradas_distintas():
    assert make_module_id("simulacros") != make_module_id("safety_meetings")


def test_source_object_y_source_field_id_incluyen_contexto():
    so_id = make_source_object_id("prevencion", "dbo", "ITP_REUNION_GRUPO")
    assert so_id == "source_object:prevencion.dbo.itp_reunion_grupo"
    sf_id = make_source_field_id(so_id, "IDReunionGrupo")
    assert sf_id == "source_field:prevencion.dbo.itp_reunion_grupo.idreuniongrupo"


def test_query_etl_workbook_etl_sheet_ids():
    q_id = make_query_id("safety_meetings", "SM2025")
    assert q_id == "query:safety_meetings.sm2025"

    wb_id = make_etl_workbook_id("ETL- reunionesdegrupo-fixEntities_SITECAN")
    sheet_id = make_etl_sheet_id(wb_id, "ITP_ASISTENTES_RG")
    assert sheet_id.startswith(wb_id.replace("etl_workbook:", "etl_sheet:"))


def test_csv_column_id_usa_posicion_no_solo_nombre():
    schema_id = "csv_schema:group_meetings_20072026_3"
    c1 = make_csv_column_id(schema_id, 9)
    c2 = make_csv_column_id(schema_id, 10)
    assert c1 != c2


def test_relation_id_es_determinista_y_refleja_los_tres_componentes():
    r1 = make_relation_id("module:simulacros", "module_uses_etl_workbook", "etl_workbook:etl_bcm_simulacros")
    r2 = make_relation_id("module:simulacros", "module_uses_etl_workbook", "etl_workbook:etl_bcm_simulacros")
    r3 = make_relation_id("module:simulacros", "module_uses_etl_workbook", "etl_workbook:otro")
    assert r1 == r2
    assert r1 != r3


def test_short_hash_es_determinista():
    assert short_hash("a", "b", "c") == short_hash("a", "b", "c")
    assert short_hash("a", "b", "c") != short_hash("a", "b", "d")


# ---------------------------------------------------------------------------
# make_mapping_decision_id -- debe incluir el contexto completo
# (module, migration_object, mapping_definition, key_fields, key_values)
# ---------------------------------------------------------------------------

def test_mapping_decision_id_incluye_modulo_objeto_y_mapping():
    base = dict(
        module_id="module:simulacros",
        migration_object_id="migration_object:simulacros.drills",
        mapping_definition_id="mapping:etl_bcm_simulacros.mapeosims#row1",
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_normalized="17|EPSR.SYMEC",
    )
    id_a = make_mapping_decision_id(**base)

    distinto_modulo = dict(base, module_id="module:safety_meetings")
    distinto_objeto = dict(base, migration_object_id="migration_object:simulacros.list_of_activities")
    distinto_mapping = dict(base, mapping_definition_id="mapping:etl_bcm_simulacros.mapeosims#row2")
    distinta_clave = dict(base, key_values_normalized="18|EPSR.SYMEC")

    assert id_a != make_mapping_decision_id(**distinto_modulo)
    assert id_a != make_mapping_decision_id(**distinto_objeto)
    assert id_a != make_mapping_decision_id(**distinto_mapping)
    assert id_a != make_mapping_decision_id(**distinta_clave)
    # Determinista: mismos parámetros -> mismo ID
    assert id_a == make_mapping_decision_id(**base)


def test_mapping_decision_id_funciona_sin_objeto_ni_mapping_conocidos():
    # No debe fallar cuando todavía no se conoce el migration_object o el
    # mapping que originó la decisión -- debe quedar explícito en el ID,
    # no inventar un contexto.
    id_ = make_mapping_decision_id(
        module_id="module:simulacros",
        migration_object_id=None,
        mapping_definition_id=None,
        key_fields=["IDCentro"],
        key_values_normalized="17",
    )
    assert "unknown_object" in id_
    assert "unknown_mapping" in id_


# ---------------------------------------------------------------------------
# Separación MappingDecision (sin recuentos) / MappingCoverageFinding
# ---------------------------------------------------------------------------

def test_mapping_decision_no_lleva_recuentos_ni_ejemplos():
    field_names = {f.name for f in fields(MappingDecision)}
    assert "affected_record_count" not in field_names
    assert "example_historical_ids" not in field_names


# ---------------------------------------------------------------------------
# Validación de vocabularios cerrados
# ---------------------------------------------------------------------------

def _valid_mapped_decision(**overrides) -> MappingDecision:
    base = dict(
        id="mapping_decision:simulacros.drills.mapeosims.abc123",
        mapping_scope=MappingScope.ENTITY,
        key_fields=["IDCentro", "IDUnidadOrg"],
        key_values_raw=["17", "EPSR.SYMEC"],
        key_normalized="17|EPSR.SYMEC",
        decision_type=DecisionType.MAPPED,
        mapping_status=MappingStatus.RESOLVED,
        load_status=LoadStatus.ELIGIBLE,
        resolved_value="MOEVE > ENERGY-PARKS > ENERGYP.SR > EPSR > EPSR.SYMEC",
    )
    base.update(overrides)
    return MappingDecision(**base)


def test_mapping_scope_invalido_lanza_error():
    with pytest.raises(ValueError):
        _valid_mapped_decision(mapping_scope="tabla")  # no es un mapping_scope válido


def test_key_fields_y_key_values_deben_tener_igual_longitud():
    with pytest.raises(ValueError):
        _valid_mapped_decision(key_fields=["IDCentro", "IDUnidadOrg"], key_values_raw=["17"])


def test_relation_resolution_status_invalido_lanza_error():
    with pytest.raises(ValueError):
        Relation(
            id="relation:a|b|c",
            subject_id="a",
            relation_type="b",
            object_id="c",
            resolution_status="probablemente",  # inválido
            authoritative_source="user_functional_correspondence",
        )


# ---------------------------------------------------------------------------
# validate_mapping_decision_consistency -- las 4 situaciones + las 7 reglas
# duras (ninguna ausencia puede desaparecer, ser NULL, vacío, No migra o
# default no documentado)
# ---------------------------------------------------------------------------

def test_correspondencia_valida_es_consistente():
    d = _valid_mapped_decision()
    assert validate_mapping_decision_consistency(d) == []


def test_no_migra_consistente_confirmado():
    d = _valid_mapped_decision(
        decision_type=DecisionType.DO_NOT_MIGRATE,
        mapping_status=MappingStatus.NOT_APPLICABLE,
        load_status=LoadStatus.EXCLUDED,
        resolved_value=None,
    )
    assert validate_mapping_decision_consistency(d) == []


def test_no_migra_con_load_status_incorrecto_es_inconsistente():
    d = _valid_mapped_decision(
        decision_type=DecisionType.DO_NOT_MIGRATE,
        mapping_status=MappingStatus.NOT_APPLICABLE,
        load_status=LoadStatus.ELIGIBLE,  # debería ser excluded
        resolved_value=None,
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("do_not_migrate" in v for v in violations)


def test_sin_correspondencia_sin_fallback_es_blocked_y_sin_valor():
    d = _valid_mapped_decision(
        decision_type=DecisionType.PENDING_MAPPING,
        mapping_status=MappingStatus.UNRESOLVED,
        load_status=LoadStatus.BLOCKED,
        resolved_value=None,
    )
    assert validate_mapping_decision_consistency(d) == []


def test_pending_mapping_con_resolved_value_es_inconsistente_ausencia_no_puede_desaparecer():
    d = _valid_mapped_decision(
        decision_type=DecisionType.PENDING_MAPPING,
        mapping_status=MappingStatus.UNRESOLVED,
        load_status=LoadStatus.BLOCKED,
        resolved_value="algo_inventado",
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("pending_mapping no puede tener resolved_value" in v for v in violations)


def test_pending_mapping_con_fallback_value_es_inconsistente():
    d = _valid_mapped_decision(
        decision_type=DecisionType.PENDING_MAPPING,
        mapping_status=MappingStatus.UNRESOLVED,
        load_status=LoadStatus.BLOCKED,
        resolved_value=None,
        fallback_value="UnidadNull",
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("fallback no documentado" in v for v in violations)


def test_fallback_documentado_consistente_eligible_with_warning():
    d = _valid_mapped_decision(
        decision_type=DecisionType.FALLBACK_VALUE,
        mapping_status=MappingStatus.UNRESOLVED_WITH_FALLBACK,
        load_status=LoadStatus.ELIGIBLE_WITH_WARNING,
        resolved_value=None,
        fallback_value="UnidadNull",
        fallback_rule_reference="Regla ETL: si no hay correspondencia IDCentro+IDUnidadOrg -> UnidadNull",
    )
    assert validate_mapping_decision_consistency(d) == []


def test_fallback_bloqueado_sin_autorizacion_requiere_revision_cliente():
    d = _valid_mapped_decision(
        decision_type=DecisionType.FALLBACK_VALUE,
        mapping_status=MappingStatus.UNRESOLVED_WITH_FALLBACK,
        load_status=LoadStatus.BLOCKED,
        resolved_value=None,
        fallback_value="UnidadNull",
        fallback_rule_reference="Regla ETL: UnidadNull",
        requires_client_review=False,  # debería ser True
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("requires_client_review" in v for v in violations)


def test_fallback_nunca_puede_quedar_resolved_aunque_produzca_un_valor():
    d = _valid_mapped_decision(
        decision_type=DecisionType.FALLBACK_VALUE,
        mapping_status=MappingStatus.RESOLVED,  # nunca debe ser resolved
        load_status=LoadStatus.ELIGIBLE_WITH_WARNING,
        resolved_value=None,
        fallback_value="UnidadNull",
        fallback_rule_reference="Regla ETL: UnidadNull",
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("nunca puede quedar mapping_status=resolved" in v for v in violations)


def test_default_value_no_se_usa_para_ausencia_de_equivalencia():
    # El ejemplo del enunciado: ausencia de equivalencia -> debe ser
    # fallback_value, NUNCA default_value (default_value es solo para
    # sustituir un origen vacío/nulo con regla documentada).
    d_incorrecto = _valid_mapped_decision(
        decision_type=DecisionType.DEFAULT_VALUE,
        mapping_status=MappingStatus.UNRESOLVED_WITH_FALLBACK,  # combinación no permitida para default_value
        load_status=LoadStatus.ELIGIBLE,
        resolved_value="UnidadNull",
    )
    violations = validate_mapping_decision_consistency(d_incorrecto)
    assert violations  # debe marcarse como inconsistente, no aceptarse en silencio


def test_default_value_correcto_para_origen_vacio_documentado():
    d = _valid_mapped_decision(
        decision_type=DecisionType.DEFAULT_VALUE,
        mapping_status=MappingStatus.RESOLVED,
        load_status=LoadStatus.ELIGIBLE,
        resolved_value="N/D",
    )
    assert validate_mapping_decision_consistency(d) == []


def test_resolved_value_y_fallback_value_son_mutuamente_excluyentes():
    d = _valid_mapped_decision(
        decision_type=DecisionType.MAPPED,
        resolved_value="algo",
        fallback_value="UnidadNull",
    )
    violations = validate_mapping_decision_consistency(d)
    assert any("mutuamente excluyentes" in v for v in violations)


def test_conflicting_es_consistente_solo_como_blocked():
    d = _valid_mapped_decision(
        decision_type=DecisionType.CONFLICTING,
        mapping_status=MappingStatus.CONFLICTING,
        load_status=LoadStatus.BLOCKED,
        resolved_value=None,
    )
    assert validate_mapping_decision_consistency(d) == []


# ---------------------------------------------------------------------------
# MigrationObject -- processing_scope / load_phase (Action Plans transversal)
# ---------------------------------------------------------------------------

def test_migration_object_por_defecto_es_module_normal():
    obj = MigrationObject(id="migration_object:eventos.events", name="Events")
    assert obj.processing_scope == ProcessingScope.MODULE
    assert obj.load_phase == LoadPhase.NORMAL


def test_migration_object_action_plans_es_cross_module_final():
    obj = MigrationObject(
        id="migration_object:action_plans.action_plans",
        name="Action Plans",
        processing_scope=ProcessingScope.CROSS_MODULE,
        load_phase=LoadPhase.FINAL,
    )
    assert obj.processing_scope == ProcessingScope.CROSS_MODULE
    assert obj.load_phase == LoadPhase.FINAL


def test_migration_object_processing_scope_invalido_lanza_error():
    with pytest.raises(ValueError):
        MigrationObject(id="x", name="x", processing_scope="global")


# ---------------------------------------------------------------------------
# make_cross_module_action_plan_buffer_id -- determinista, incluye las 5 partes
# ---------------------------------------------------------------------------

def test_buffer_id_es_determinista():
    kwargs = dict(
        source_system="prevencion",
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        action_plan_historical_id="AP-100",
        source_historical_id="EVT-500",
    )
    assert make_cross_module_action_plan_buffer_id(**kwargs) == make_cross_module_action_plan_buffer_id(**kwargs)


def test_buffer_id_no_colisiona_entre_fuentes_distintas():
    base = dict(
        source_system="prevencion",
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        action_plan_historical_id="AP-100",
        source_historical_id="EVT-500",
    )
    id_a = make_cross_module_action_plan_buffer_id(**base)

    distinto_sistema = dict(base, source_system="gct")
    distinto_ap_id = dict(base, action_plan_historical_id="AP-101")
    distinto_hist_id = dict(base, source_historical_id="EVT-501")

    assert id_a != make_cross_module_action_plan_buffer_id(**distinto_sistema)
    assert id_a != make_cross_module_action_plan_buffer_id(**distinto_ap_id)
    assert id_a != make_cross_module_action_plan_buffer_id(**distinto_hist_id)


def test_buffer_id_incluye_source_system_en_claro():
    id_prevencion = make_cross_module_action_plan_buffer_id(
        source_system="prevencion", source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        action_plan_historical_id="AP-100", source_historical_id="EVT-500",
    )
    id_gct = make_cross_module_action_plan_buffer_id(
        source_system="gct", source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        action_plan_historical_id="AP-100", source_historical_id="EVT-500",
    )
    assert id_prevencion.split(".")[0] == "cross_module_action_plan_buffer:prevencion"
    assert id_gct.split(".")[0] == "cross_module_action_plan_buffer:gct"


# ---------------------------------------------------------------------------
# CrossModuleActionPlanBuffer -- validación de vocabularios
# ---------------------------------------------------------------------------

def _valid_buffer(**overrides) -> CrossModuleActionPlanBuffer:
    base = dict(
        id="cross_module_action_plan_buffer:prevencion.eventos.events.abc123",
        action_plan_historical_id="AP-100",
        source_system="prevencion",
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        source_historical_id="EVT-500",
        relationship_type=ActionPlanRelationshipType.LINKED,
        target_historical_reference="EVT-500",
        target_enablon_reference=None,
        relationship_status=ResolutionStatus.PENDING,
        processing_status=ActionPlanProcessingStatus.WAITING_FOR_PARENT,
    )
    base.update(overrides)
    return CrossModuleActionPlanBuffer(**base)


def test_buffer_relationship_type_invalido_lanza_error():
    with pytest.raises(ValueError):
        _valid_buffer(relationship_type="huerfana")


# ---------------------------------------------------------------------------
# validate_action_plan_buffer_consistency
# ---------------------------------------------------------------------------

def test_linked_waiting_for_parent_con_pending_es_consistente():
    buf = _valid_buffer()
    assert validate_action_plan_buffer_consistency(buf) == []


def test_standalone_debe_llevar_not_applicable():
    buf = _valid_buffer(
        relationship_type=ActionPlanRelationshipType.STANDALONE,
        relationship_status=ResolutionStatus.NOT_APPLICABLE,
        processing_status=ActionPlanProcessingStatus.VALIDATED,
        target_historical_reference=None,
    )
    assert validate_action_plan_buffer_consistency(buf) == []


def test_standalone_con_relationship_status_distinto_es_inconsistente():
    buf = _valid_buffer(
        relationship_type=ActionPlanRelationshipType.STANDALONE,
        relationship_status=ResolutionStatus.CONFIRMED,  # debería ser not_applicable
        processing_status=ActionPlanProcessingStatus.VALIDATED,
        target_historical_reference=None,
    )
    violations = validate_action_plan_buffer_consistency(buf)
    assert any("standalone_action_plan debe llevar" in v for v in violations)


def test_waiting_for_parent_con_relationship_status_confirmed_es_inconsistente():
    buf = _valid_buffer(relationship_status=ResolutionStatus.CONFIRMED)
    violations = validate_action_plan_buffer_consistency(buf)
    assert any("waiting_for_parent debe llevar relationship_status=pending" in v for v in violations)


def test_waiting_for_parent_en_standalone_es_inconsistente():
    buf = _valid_buffer(
        relationship_type=ActionPlanRelationshipType.STANDALONE,
        relationship_status=ResolutionStatus.PENDING,
    )
    violations = validate_action_plan_buffer_consistency(buf)
    assert any("solo una acción linked_action_plan puede quedar waiting_for_parent" in v for v in violations)


# ---------------------------------------------------------------------------
# Dependencia Action Plans -> módulo origen
# ---------------------------------------------------------------------------

def test_dependencia_desde_config_nunca_puede_ser_confirmed():
    relation = build_action_plan_dependency_relation(
        action_plans_migration_object_id="migration_object:action_plans.action_plans",
        depends_on_migration_object_id="migration_object:eventos.events",
        dependency_source=DependencySource.CONFIGURED_MAPPING,
        resolution_status=ResolutionStatus.CONFIRMED,  # se pasa mal a propósito
        evidence_ids=[],
        source_idorigenac_values=["2", "13"],
    )
    violations = validate_action_plan_dependency_relation(relation)
    assert violations  # debe marcarse como inconsistente, no aceptarse en silencio


def test_dependencia_desde_config_como_inferred_es_valida():
    relation = build_action_plan_dependency_relation(
        action_plans_migration_object_id="migration_object:action_plans.action_plans",
        depends_on_migration_object_id="migration_object:eventos.events",
        dependency_source=DependencySource.CONFIGURED_MAPPING,
        resolution_status=ResolutionStatus.INFERRED,
        evidence_ids=[],
        source_idorigenac_values=["2", "13"],
    )
    assert validate_action_plan_dependency_relation(relation) == []


def test_dependencia_respaldada_por_datos_sql_puede_ser_confirmed():
    relation = build_action_plan_dependency_relation(
        action_plans_migration_object_id="migration_object:action_plans.action_plans",
        depends_on_migration_object_id="migration_object:eventos.events",
        dependency_source=DependencySource.SQL_EVIDENCE,
        resolution_status=ResolutionStatus.CONFIRMED,
        evidence_ids=["evidence:query:ap.acciones_correctoras#1"],
        source_idorigenac_values=["2", "13"],
    )
    assert validate_action_plan_dependency_relation(relation) == []
    assert relation.dependency_scope == "data_driven"
    assert relation.source_idorigenac_values == ["2", "13"]


def test_dependencia_pendiente_de_visitas_seguridad_y_otros_no_bloquea_otras():
    # visitas_seguridad_y_otros permanece pending -- pero eso no debe afectar
    # a la relación (ya confirmada por evidencia) de otro módulo.
    pendiente = build_action_plan_dependency_relation(
        action_plans_migration_object_id="migration_object:action_plans.action_plans",
        depends_on_migration_object_id="migration_object:visitas_seguridad_y_otros.visitas",
        dependency_source=DependencySource.CONFIGURED_MAPPING,
        resolution_status=ResolutionStatus.PENDING,
        evidence_ids=[],
        source_idorigenac_values=["7", "14"],
    )
    confirmada = build_action_plan_dependency_relation(
        action_plans_migration_object_id="migration_object:action_plans.action_plans",
        depends_on_migration_object_id="migration_object:eventos.events",
        dependency_source=DependencySource.SQL_EVIDENCE,
        resolution_status=ResolutionStatus.CONFIRMED,
        evidence_ids=["evidence:x#1"],
        source_idorigenac_values=["2", "13"],
    )
    assert validate_action_plan_dependency_relation(pendiente) == []
    assert pendiente.resolution_status == ResolutionStatus.PENDING
    assert validate_action_plan_dependency_relation(confirmada) == []
    assert confirmada.resolution_status == ResolutionStatus.CONFIRMED
