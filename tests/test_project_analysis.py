"""Tests de src/analysis/project_analysis.py. Ejecutar con: pytest tests/"""
import inspect
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook  # noqa: F401  (no se usa aquí, evita import perezoso en otros entornos)
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import module_analysis, project_analysis
from src.analysis.module_analysis import ActionPlanCandidate, FieldValidationResult
from src.analysis.project_analysis import (
    ModuleAnalysisResult,
    ModuleExecutionSpec,
    ModuleRequest,
    ParentResolutionInput,
    ProjectAnalysisRequest,
    compute_global_coverage,
    consolidate_action_plan_buffers,
    finalize_action_plans,
    generate_project_outputs,
    make_parent_index_key,
    resolve_action_plan_parents,
    run_project_analysis,
)
from src.knowledge_base.model import (
    ActionPlanProcessingStatus,
    ActionPlanRelationshipType,
    MigrationObject,
    ResolutionStatus,
)


# ---------------------------------------------------------------------------
# Helpers de construcción
# ---------------------------------------------------------------------------

def _candidate(**overrides) -> ActionPlanCandidate:
    base = dict(
        source_system="prevencion",
        source_module="module:eventos",
        source_migration_object="migration_object:eventos.events",
        source_historical_id="EVT-1",
        action_plan_historical_id="AP-1",
        relationship_type=ActionPlanRelationshipType.LINKED,
        target_historical_reference="EVT-1",
    )
    base.update(overrides)
    return ActionPlanCandidate(**base)


def _module_request_single(candidate: ActionPlanCandidate, *, valid=True, parent: ParentResolutionInput | None = None) -> ModuleRequest:
    spec = ModuleExecutionSpec(
        candidates=[candidate],
        field_validation_by_source_historical_id={
            candidate.source_historical_id: FieldValidationResult(is_valid=valid, blocking_reasons=[] if valid else ["campo inválido"])
        },
        parent_resolution_by_source_historical_id=(
            {candidate.source_historical_id: parent} if parent is not None else {}
        ),
    )
    return ModuleRequest(module_id=candidate.source_module, source_system=candidate.source_system, execution_spec=spec)


def _simple_request(candidates_and_requests, **overrides) -> ProjectAnalysisRequest:
    base = dict(
        project_id="proyecto_test",
        analysis_run_id="run_1",
        module_requests=candidates_and_requests,
        module_execution_order=[r.module_id for r in candidates_and_requests],
        generate_outputs=False,
    )
    base.update(overrides)
    return ProjectAnalysisRequest(**base)


# ---------------------------------------------------------------------------
# 1. AP se finaliza después de todos los módulos
# ---------------------------------------------------------------------------

def test_ap_no_se_finaliza_si_falta_un_modulo_del_alcance():
    req = _simple_request(
        [_module_request_single(_candidate())],
        module_execution_order=["module:eventos", "module:moc"],  # "module:moc" nunca se aporta
    )
    result = run_project_analysis(req)
    assert "module:moc" in result.global_coverage.unresolved_modules
    assert not any(b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD for b in result.action_plan_buffers)


def test_ap_se_finaliza_cuando_todos_los_modulos_del_alcance_estan():
    candidate = _candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)
    req = _simple_request([_module_request_single(candidate)])
    result = run_project_analysis(req)
    assert result.global_coverage.unresolved_modules == []
    ready = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD]
    assert len(ready) == 1


# ---------------------------------------------------------------------------
# 2. module_analysis nunca sustituido por lógica duplicada
# ---------------------------------------------------------------------------

def test_no_duplica_logica_de_module_analysis(monkeypatch):
    calls = []
    original = module_analysis.detect_action_plan_candidates

    def _spy(candidates):
        calls.append(len(candidates))
        return original(candidates)

    monkeypatch.setattr(module_analysis, "detect_action_plan_candidates", _spy)
    req = _simple_request([_module_request_single(_candidate())])
    run_project_analysis(req)
    assert calls == [1]  # se llamó de verdad a module_analysis, no a una copia


def test_project_analysis_no_reimplementa_deteccion_de_candidatos():
    source = inspect.getsource(project_analysis)
    # module_analysis se importa y se usa vía su namespace, nunca se copia
    # su cuerpo -- comprobamos que la lógica de resolución de mappings
    # (mapping_resolver/mapping_coverage) no aparece reimplementada aquí.
    assert "from src.analysis import module_analysis" in source
    assert "EnablonReferenceCatalog" not in source  # eso es de mapping_resolver.py, no se duplica aquí


# ---------------------------------------------------------------------------
# 3-5. Resolución del padre
# ---------------------------------------------------------------------------

def test_linked_con_padre_exacto_pasa_a_parent_resolved():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    resolved = resolve_action_plan_parents(
        [buf],
        parent_reference_index={make_parent_index_key("prevencion", "EVT-1"): ["MOEVE > ... > EPSR"]},
        all_modules_analyzed=False,
    )[0]
    assert resolved.processing_status == ActionPlanProcessingStatus.PARENT_RESOLVED
    assert resolved.relationship_status == ResolutionStatus.CONFIRMED
    assert resolved.target_enablon_reference == "MOEVE > ... > EPSR"


def test_linked_sin_padre_queda_blocked_al_cerrar_proyecto():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    resolved = resolve_action_plan_parents([buf], parent_reference_index={}, all_modules_analyzed=True)[0]
    assert resolved.processing_status == ActionPlanProcessingStatus.BLOCKED
    assert resolved.blocking_reasons


def test_linked_sin_padre_sigue_waiting_si_el_proyecto_no_ha_cerrado():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    resolved = resolve_action_plan_parents([buf], parent_reference_index={}, all_modules_analyzed=False)[0]
    assert resolved.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT


def test_varios_padres_incompatibles_generan_conflicting_blocked():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    resolved = resolve_action_plan_parents(
        [buf],
        parent_reference_index={make_parent_index_key("prevencion", "EVT-1"): ["Ruta A", "Ruta B"]},
        all_modules_analyzed=False,
    )[0]
    assert resolved.relationship_status == ResolutionStatus.CONFLICTING
    assert resolved.processing_status == ActionPlanProcessingStatus.BLOCKED


# ---------------------------------------------------------------------------
# 6-7. standalone / linked -- nunca se convierten entre sí
# ---------------------------------------------------------------------------

def test_standalone_validada_pasa_a_ready_solo_en_finalize():
    buf = module_analysis.detect_action_plan_candidates(
        [_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)]
    )[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    assert buf.processing_status == ActionPlanProcessingStatus.VALIDATED  # module_analysis.py no la finaliza
    finalized = finalize_action_plans([buf])[0]
    assert finalized.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD


def test_linked_nunca_se_convierte_en_standalone_en_todo_el_pipeline():
    req = _simple_request([_module_request_single(_candidate())])  # sin padre en el índice
    result = run_project_analysis(req)
    buf = result.action_plan_buffers[0]
    assert buf.relationship_type == ActionPlanRelationshipType.LINKED


# ---------------------------------------------------------------------------
# 8. No migra queda excluded
# ---------------------------------------------------------------------------

def test_no_migra_queda_excluded_tras_todo_el_pipeline():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.mark_excluded(buf, reason="No migra: código en rollback Site Canarias", evidence_ids=["evidence:x#1"])
    consolidation = consolidate_action_plan_buffers([buf])
    resolved = resolve_action_plan_parents(consolidation.consolidated_buffers, parent_reference_index={}, all_modules_analyzed=True)
    finalized = finalize_action_plans(resolved)[0]
    assert finalized.processing_status == ActionPlanProcessingStatus.EXCLUDED


# ---------------------------------------------------------------------------
# 9-12. Deduplicación
# ---------------------------------------------------------------------------

def test_acciones_de_fuentes_distintas_no_colisionan():
    a = module_analysis.detect_action_plan_candidates([_candidate(source_system="prevencion")])[0]
    b = module_analysis.detect_action_plan_candidates([_candidate(source_system="gct")])[0]
    consolidation = consolidate_action_plan_buffers([a, b])
    assert len(consolidation.consolidated_buffers) == 2
    assert consolidation.duplicate_groups == []


def test_duplicados_exactos_se_consolidan_sin_perder_evidencias():
    c = _candidate()
    a = module_analysis.detect_action_plan_candidates([c])[0]
    b = module_analysis.detect_action_plan_candidates([c])[0]  # mismo candidato -- mismo id determinista
    a = module_analysis.validate_action_plan_fields(a, FieldValidationResult(is_valid=True, evidence_ids=["evidence:a#1"]))
    b = module_analysis.validate_action_plan_fields(b, FieldValidationResult(is_valid=True, evidence_ids=["evidence:b#1"]))

    consolidation = consolidate_action_plan_buffers([a, b])
    assert len(consolidation.consolidated_buffers) == 1
    assert consolidation.duplicate_groups == [[a.id, b.id]]
    merged = consolidation.consolidated_buffers[0]
    assert "evidence:a#1" in merged.evidence_ids
    assert "evidence:b#1" in merged.evidence_ids


def test_duplicados_incompatibles_se_bloquean_sin_elegir_uno():
    c1 = _candidate(source_historical_id="EVT-1", target_historical_reference="EVT-1")
    c2 = _candidate(source_historical_id="EVT-2", target_historical_reference="EVT-2")  # mismo AP id, origen distinto
    a = module_analysis.detect_action_plan_candidates([c1])[0]
    b = module_analysis.detect_action_plan_candidates([c2])[0]

    consolidation = consolidate_action_plan_buffers([a, b])
    assert len(consolidation.consolidated_buffers) == 1
    merged = consolidation.consolidated_buffers[0]
    assert merged.processing_status == ActionPlanProcessingStatus.BLOCKED
    assert merged.relationship_status == ResolutionStatus.CONFLICTING
    assert consolidation.conflicting_groups == [[a.id, b.id]]


def test_no_se_deduplica_por_titulo_fecha_o_descripcion():
    # CrossModuleActionPlanBuffer no tiene ningún campo de título/fecha/
    # descripción -- estructuralmente no puede usarse como clave. Lo
    # confirmamos inspeccionando los campos disponibles.
    from dataclasses import fields
    from src.knowledge_base.model import CrossModuleActionPlanBuffer

    field_names = {f.name for f in fields(CrossModuleActionPlanBuffer)}
    assert not field_names & {"title", "description", "date", "name"}


# ---------------------------------------------------------------------------
# 13-14. visitas_seguridad_y_otros pendiente
# ---------------------------------------------------------------------------

def test_visitas_seguridad_y_otros_mantiene_cobertura_incomplete():
    confirmado = _module_request_single(
        _candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)
    )
    visitas = ModuleRequest(
        module_id="module:visitas_seguridad_y_otros",
        source_system="prevencion",
        already_resolved=ModuleAnalysisResult(
            module_id="module:visitas_seguridad_y_otros",
            source_system="prevencion",
            unresolved_idorigenac_values=["7", "14"],
        ),
    )
    req = _simple_request([confirmado, visitas])
    result = run_project_analysis(req)
    assert result.global_coverage.status == "incomplete"
    assert "7" in result.global_coverage.unresolved_idorigenac_values


def test_visitas_pendiente_no_bloquea_acciones_confirmadas_de_otros_modulos():
    confirmado = _module_request_single(
        _candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)
    )
    visitas = ModuleRequest(
        module_id="module:visitas_seguridad_y_otros",
        source_system="prevencion",
        already_resolved=ModuleAnalysisResult(
            module_id="module:visitas_seguridad_y_otros",
            source_system="prevencion",
            unresolved_idorigenac_values=["7", "14"],
        ),
    )
    req = _simple_request([confirmado, visitas])
    result = run_project_analysis(req)
    assert result.global_coverage.status == "incomplete"
    ready = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD]
    assert len(ready) == 1  # la acción standalone SÍ llega a ready pese a la cobertura incompleta


# ---------------------------------------------------------------------------
# 15-16. Invariantes de ready_for_final_load
# ---------------------------------------------------------------------------

def test_ningun_ready_contiene_referencia_padre_pendiente():
    req = _simple_request(
        [_module_request_single(_candidate(), parent=ParentResolutionInput(
            target_enablon_reference="MOEVE > ... > EPSR", resolution_status=ResolutionStatus.CONFIRMED, evidence_ids=["evidence:x#1"],
        ))]
    )
    result = run_project_analysis(req)
    ready = [b for b in result.action_plan_buffers if b.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD]
    assert len(ready) == 1
    assert ready[0].target_enablon_reference is not None
    assert ready[0].relationship_status == ResolutionStatus.CONFIRMED


def test_ready_for_final_load_nunca_aparece_antes_de_finalize():
    buf = module_analysis.detect_action_plan_candidates([_candidate()])[0]
    buf = module_analysis.validate_action_plan_fields(buf, FieldValidationResult(is_valid=True))
    resolved = resolve_action_plan_parents(
        [buf], parent_reference_index={make_parent_index_key("prevencion", "EVT-1"): ["Ruta"]}, all_modules_analyzed=False,
    )[0]
    # tras resolve_action_plan_parents, ANTES de finalize_action_plans
    assert resolved.processing_status != ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD
    finalized = finalize_action_plans([resolved])[0]
    assert finalized.processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD


# ---------------------------------------------------------------------------
# 17-18, 22. Salidas
# ---------------------------------------------------------------------------

def test_salidas_csv_usan_utf8_sig(tmp_path):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=True,
    )
    result = run_project_analysis(req)
    for name, path in result.output_paths.items():
        if name.endswith(".csv"):
            raw = Path(path).read_bytes()
            assert raw.startswith(b"\xef\xbb\xbf"), f"{name} no tiene BOM utf-8-sig"


def test_action_plans_es_la_ultima_salida_funcional(tmp_path):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=True,
    )
    result = run_project_analysis(req)
    manifest_path = Path(result.output_paths["manifest.yaml"])
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    files = manifest["output_files"]
    ap_related = [f for f in files if f.startswith("action_plan")]
    non_ap = [f for f in files if not f.startswith("action_plan")]
    # todos los índices de ficheros "action_plan*" deben ser mayores que
    # todos los de ficheros no relacionados con Action Plans.
    assert max(files.index(f) for f in ap_related) > max(files.index(f) for f in non_ap)


def test_manifest_contiene_hashes_y_recuentos_correctos(tmp_path):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=True,
    )
    result = run_project_analysis(req)
    manifest_path = Path(result.output_paths["manifest.yaml"])
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert manifest["encoding"] == "utf-8-sig"
    assert manifest["ready_action_count"] == 1
    for fname, expected_hash in manifest["file_hashes"].items():
        actual = Path(result.output_paths[fname]).read_bytes()
        import hashlib
        assert hashlib.sha256(actual).hexdigest() == expected_hash
    assert "password" not in str(manifest).lower()
    assert "connection" not in str(manifest).lower()


# ---------------------------------------------------------------------------
# 19. No se modifica ningún input
# ---------------------------------------------------------------------------

def test_no_se_referencia_inputs_ni_config_en_el_codigo():
    source = inspect.getsource(project_analysis)
    assert "inputs/" not in source
    assert "config/modules.yaml" not in source
    assert "open(" in source  # sí escribe (outputs), pero nunca sobre inputs/config


# ---------------------------------------------------------------------------
# 20-21, 23-24. Determinismo, no sobrescritura, generate_outputs=False, limpieza ante error
# ---------------------------------------------------------------------------

def test_ejecucion_repetida_con_mismo_contenido_es_determinista():
    def _build_request():
        return _simple_request(
            [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))]
        )

    r1 = run_project_analysis(_build_request())
    r2 = run_project_analysis(_build_request())
    assert [b.id for b in r1.action_plan_buffers] == [b.id for b in r2.action_plan_buffers]
    assert [b.processing_status for b in r1.action_plan_buffers] == [b.processing_status for b in r2.action_plan_buffers]
    assert r1.global_coverage.status == r2.global_coverage.status


def test_no_sobrescribe_ejecucion_anterior(tmp_path):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=True,
    )
    run_project_analysis(req)  # primera vez, ok
    with pytest.raises(FileExistsError):
        run_project_analysis(req)  # mismo project_id + analysis_run_id -- debe rechazarse


def test_generate_outputs_false_no_escribe_nada(tmp_path):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=False,
    )
    result = run_project_analysis(req)
    assert result.output_paths == {}
    assert not any(tmp_path.iterdir())


def test_error_durante_escritura_no_publica_carpeta_parcial(tmp_path, monkeypatch):
    req = _simple_request(
        [_module_request_single(_candidate(relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None))],
        output_directory=str(tmp_path), generate_outputs=True,
    )

    # Forzamos un fallo a mitad de la escritura de salidas.
    def _boom(*args, **kwargs):
        raise RuntimeError("fallo simulado durante la escritura")

    monkeypatch.setattr(project_analysis.yaml, "safe_dump", _boom)

    with pytest.raises(RuntimeError):
        run_project_analysis(req)

    final_dir = tmp_path / "proyecto_test" / "run_1"
    assert not final_dir.exists()  # nunca se publicó nada parcial
    # tampoco debe quedar ningún directorio temporal huérfano
    leftovers = [p for p in tmp_path.glob("**/*") if "project_analysis_" in str(p)]
    assert leftovers == []


# ---------------------------------------------------------------------------
# 13. Prueba integral
# ---------------------------------------------------------------------------

def test_prueba_integral_seis_modulos_y_escenarios_especiales(tmp_path):
    parent_index = {
        make_parent_index_key("prevencion", "EVT-100"): ["MOEVE > EVENTOS > EVT100"],
    }

    # 1) Simulacros -- standalone válida
    simulacros = _module_request_single(
        _candidate(
            source_system="prevencion", source_module="module:simulacros",
            source_migration_object="migration_object:simulacros.drills",
            source_historical_id="SIM-1", action_plan_historical_id="AP-SIM-1",
            relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None,
        )
    )

    # 2) Reuniones de Grupo -- linked con padre resuelto
    reuniones = _module_request_single(
        _candidate(
            source_system="prevencion", source_module="module:reuniones_de_grupo",
            source_migration_object="migration_object:reuniones_de_grupo.group_meetings",
            source_historical_id="RG-1", action_plan_historical_id="AP-RG-1",
            relationship_type=ActionPlanRelationshipType.LINKED, target_historical_reference="RG-1",
        ),
        parent=ParentResolutionInput(target_enablon_reference="MOEVE > REUNIONES > RG1", resolution_status=ResolutionStatus.CONFIRMED, evidence_ids=["evidence:rg#1"]),
    )

    # 3) Inspecciones -- linked SIN padre (nunca se encuentra)
    inspecciones = _module_request_single(
        _candidate(
            source_system="prevencion", source_module="module:inspecciones",
            source_migration_object="migration_object:inspecciones.inspections",
            source_historical_id="INSP-1", action_plan_historical_id="AP-INSP-1",
            relationship_type=ActionPlanRelationshipType.LINKED, target_historical_reference="INSP-SIN-PADRE",
        )
    )

    # 4) OPS -- No migra
    ops_buf = module_analysis.detect_action_plan_candidates([
        _candidate(
            source_system="prevencion", source_module="module:ops",
            source_migration_object="migration_object:ops.jso",
            source_historical_id="OPS-1", action_plan_historical_id="AP-OPS-1",
            relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None,
        )
    ])[0]
    ops_buf = module_analysis.mark_excluded(ops_buf, reason="No migra: Site Canarias en rollback", evidence_ids=["evidence:ops#1"])
    ops = ModuleRequest(
        module_id="module:ops", source_system="prevencion",
        already_resolved=ModuleAnalysisResult(module_id="module:ops", source_system="prevencion", action_plan_buffers=[ops_buf]),
    )

    # 5) Eventos -- linked con padre resuelto vía parent_reference_index global
    eventos = _module_request_single(
        _candidate(
            source_system="prevencion", source_module="module:eventos",
            source_migration_object="migration_object:eventos.events",
            source_historical_id="EVT-100", action_plan_historical_id="AP-EVT-100",
            relationship_type=ActionPlanRelationshipType.LINKED, target_historical_reference="EVT-100",
        )
    )  # sin parent_resolution local -- se resuelve vía parent_reference_index del proyecto

    # visitas_seguridad_y_otros -- pendiente
    visitas = ModuleRequest(
        module_id="module:visitas_seguridad_y_otros", source_system="prevencion",
        already_resolved=ModuleAnalysisResult(
            module_id="module:visitas_seguridad_y_otros", source_system="prevencion",
            unresolved_idorigenac_values=["7", "14"],
        ),
    )

    # Colisión entre dos fuentes: mismo action_plan_historical_id, sistemas distintos
    colision_a = module_analysis.detect_action_plan_candidates([
        _candidate(source_system="prevencion", source_module="module:bypass",
                   source_migration_object="migration_object:bypass.bypass",
                   source_historical_id="BES-1", action_plan_historical_id="AP-COLISION",
                   relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)
    ])[0]
    colision_b = module_analysis.detect_action_plan_candidates([
        _candidate(source_system="gct", source_module="module:bypass",
                   source_migration_object="migration_object:bypass.bypass",
                   source_historical_id="BES-1-GCT", action_plan_historical_id="AP-COLISION",
                   relationship_type=ActionPlanRelationshipType.STANDALONE, target_historical_reference=None)
    ])[0]
    colision_a = module_analysis.validate_action_plan_fields(colision_a, FieldValidationResult(is_valid=True))
    colision_b = module_analysis.validate_action_plan_fields(colision_b, FieldValidationResult(is_valid=True))
    bypass = ModuleRequest(
        module_id="module:bypass", source_system="prevencion",
        already_resolved=ModuleAnalysisResult(module_id="module:bypass", source_system="prevencion", action_plan_buffers=[colision_a, colision_b]),
    )

    req = ProjectAnalysisRequest(
        project_id="prueba_integral",
        analysis_run_id="run_integral_1",
        module_requests=[simulacros, reuniones, inspecciones, ops, eventos, visitas, bypass],
        module_execution_order=[
            "module:simulacros", "module:reuniones_de_grupo", "module:inspecciones",
            "module:ops", "module:eventos", "module:visitas_seguridad_y_otros", "module:bypass",
        ],
        parent_reference_index=parent_index,
        output_directory=str(tmp_path),
        generate_outputs=True,
        source_snapshot_ids=["bak_prevencion_test"],
    )

    result = run_project_analysis(req)

    # -- consolidación transversal: acción de colisión con misma clave de
    # dedup (source_system distinto -> NO colisiona, se mantienen separadas)
    assert result.action_plan_consolidation_result.duplicate_groups == []
    assert result.action_plan_consolidation_result.conflicting_groups == []

    by_module = {
        "module:simulacros": [], "module:reuniones_de_grupo": [], "module:inspecciones": [],
        "module:ops": [], "module:eventos": [], "module:bypass": [],
    }
    for b in result.action_plan_buffers:
        if b.source_module in by_module:
            by_module[b.source_module].append(b)

    # Simulacros: standalone -> ready
    assert by_module["module:simulacros"][0].processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD
    # Reuniones de Grupo: linked con padre ya resuelto localmente -> ready
    assert by_module["module:reuniones_de_grupo"][0].processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD
    # Inspecciones: linked sin padre, proyecto cerrado -> blocked
    assert by_module["module:inspecciones"][0].processing_status == ActionPlanProcessingStatus.BLOCKED
    # OPS: excluded (No migra), se conserva
    assert by_module["module:ops"][0].processing_status == ActionPlanProcessingStatus.EXCLUDED
    # Eventos: linked resuelto vía índice global del proyecto -> ready
    assert by_module["module:eventos"][0].processing_status == ActionPlanProcessingStatus.READY_FOR_FINAL_LOAD
    assert by_module["module:eventos"][0].target_enablon_reference == "MOEVE > EVENTOS > EVT100"
    # Bypass (colisión entre fuentes): ambas se conservan, ninguna se fusiona
    assert len(by_module["module:bypass"]) == 2
    assert {b.source_system for b in by_module["module:bypass"]} == {"prevencion", "gct"}

    # -- cobertura global: incomplete por visitas_seguridad_y_otros, aunque
    # haya acciones ready de otros módulos
    assert result.global_coverage.status == "incomplete"
    assert "7" in result.global_coverage.unresolved_idorigenac_values
    assert result.global_coverage.ready_action_count >= 4  # simulacros, reuniones, eventos, y las 2 de bypass

    # -- AP como fase final: la carpeta de salidas existe y contiene los
    # ficheros de Action Plans generados en último lugar
    assert result.output_paths
    manifest_path = Path(result.output_paths["manifest.yaml"])
    assert manifest_path.exists()
