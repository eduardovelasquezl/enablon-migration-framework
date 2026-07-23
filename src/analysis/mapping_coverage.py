"""
Motor de clasificación de cobertura de mappings, exclusiones y fallbacks.

Distingue siempre estas situaciones (nunca se confunden entre sí):

1. Correspondencia válida               -> mapped / resolved / eligible
2. Decisión funcional "No migra"        -> do_not_migrate / not_applicable / excluded
3. Sin correspondencia y sin fallback    -> pending_mapping / unresolved / blocked
4. Sin correspondencia con fallback      -> fallback_value / unresolved_with_fallback / *
   documentado en el ETL (p. ej. UnidadNull)

Regla dura: ninguna ausencia de correspondencia puede desaparecer,
convertirse en NULL/vacío silencioso, clasificarse como "No migra" sin
evidencia, ni recibir un valor por defecto no documentado. Ver
`src.knowledge_base.model.validate_mapping_decision_consistency`, que este
módulo invoca sobre cada decisión antes de aceptarla.

Separa `MappingDecision` (decisión estable sobre una clave, sin recuentos) de
`MappingCoverageFinding` (resultado observado en una corrida de análisis
concreta, con recuentos y ejemplos) -- la misma decisión puede producir
findings distintos en BAK/freezes distintos.

Las 7 salidas de diagnóstico se generan siempre desde la UNIÓN
MappingCoverageFinding <-> MappingDecision, nunca desde MappingDecision sola
(una decisión sin ningún finding en la corrida actual no tiene registros
afectados que reportar todavía).

Este módulo no ejecuta SQL, no lee `inputs/` directamente y no genera CSV de
carga -- produce únicamente ficheros de diagnóstico (reportar, no cargar).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook

from src.etl.mapping_resolver import normalize_label
from src.knowledge_base.model import (
    DecisionType,
    LoadStatus,
    MappingCoverageFinding,
    MappingDecision,
    MappingScope,
    MappingStatus,
    make_mapping_coverage_finding_id,
    make_mapping_decision_id,
    validate_mapping_decision_consistency,
)

CSV_ENCODING = "utf-8-sig"  # mismo criterio que los CSV finales del proyecto


# ---------------------------------------------------------------------------
# Determinación de mapping_scope -- NUNCA por lista fija de nombres de campo
# (ni "IDCentro", ni "IDUnidadOrg"...). Se apoya en lo que ya se sabe del
# mapping: si el destino es un campo de entidad conocido, una referencia
# relacional declarada, o ninguna de las dos. Si no hay evidencia suficiente,
# queda "unknown" y se debe generar un OpenQuestion aparte (responsabilidad
# de quien orquesta, no de esta función pura).
# ---------------------------------------------------------------------------

def determine_mapping_scope(
    *,
    destination_is_known_entity_field: bool = False,
    destination_is_known_relationship_field: bool = False,
    destination_field_xml: str | None = None,
) -> tuple[str, str]:
    """Devuelve (mapping_scope, method). Los booleanos de entrada deben venir
    de evidencia ya verificada (p. ej. `destination_field_xml` coincide con
    un `EnablonField` ya catalogado como campo de entidad en `EnablonObject`,
    o con un campo de referencia cruzada ya documentado como
    `CS_ReferenceCrisis`/`MoCChange`/`CS_ByPasses`/etc.) -- esta función no
    inspecciona nombres por sí misma."""
    if destination_is_known_entity_field:
        return MappingScope.ENTITY, "destino_coincide_con_campo_de_entidad_ya_catalogado"
    if destination_is_known_relationship_field:
        return MappingScope.RELATIONSHIP, "destino_es_referencia_cruzada_ya_documentada"
    if destination_field_xml:
        return MappingScope.FIELD, "destino_es_campo_enablon_simple_sin_evidencia_de_entidad_o_relacion"
    return MappingScope.UNKNOWN, "sin_evidencia_suficiente_para_determinar_el_alcance"


# ---------------------------------------------------------------------------
# Clasificación de una clave (simple o compuesta)
# ---------------------------------------------------------------------------

@dataclass
class FallbackRuleInfo:
    """Lo que ya se sabe de la regla de fallback documentada en el ETL (p.
    ej. 'si no hay correspondencia IDCentro+IDUnidadOrg -> UnidadNull')."""
    rule_id: str
    fallback_value: str
    load_permission: str | None = None  # LoadStatus.ELIGIBLE_WITH_WARNING | LoadStatus.BLOCKED | None
    load_permission_source: str | None = None  # ver FallbackLoadPermissionSource


def normalize_key(key_values_raw: list[str]) -> str:
    """Clave compuesta normalizada -- SIEMPRE como unidad completa, nunca
    componente a componente. Dos claves que difieren en cualquier
    componente producen una clave normalizada distinta."""
    return "|".join(normalize_label(str(v)) for v in key_values_raw)


def build_mapping_decision(
    *,
    module_id: str,
    key_fields: list[str],
    key_values_raw: list[str],
    mapping_scope: str,
    migration_object_id: str | None = None,
    mapping_definition_id: str | None = None,
    resolved_value: str | None = None,
    is_marked_do_not_migrate: bool = False,
    do_not_migrate_reference: str | None = None,
    fallback_rule: FallbackRuleInfo | None = None,
    is_default_value: bool = False,
    default_value_applied: str | None = None,
    conflicting_values: list[str] | None = None,
) -> MappingDecision:
    """Aplica la tabla de decisión aprobada sobre UNA clave (posiblemente
    compuesta) y devuelve la `MappingDecision` resultante -- sin recuentos,
    esos van en `MappingCoverageFinding` (ver `build_coverage_finding`).

    Los parámetros de entrada deben reflejar evidencia ya verificada por
    quien orquesta (si hay equivalencia, si está marcado "No migra", si hay
    una regla de fallback aplicable...) -- esta función solo aplica la
    tabla de decisión, no decide por sí sola si algo tiene equivalencia.
    """
    key_normalized = normalize_key(key_values_raw)
    decision_id = make_mapping_decision_id(
        module_id=module_id,
        migration_object_id=migration_object_id,
        mapping_definition_id=mapping_definition_id,
        key_fields=key_fields,
        key_values_normalized=key_normalized,
    )

    extra: dict = {}

    if conflicting_values is not None and len(set(conflicting_values)) > 1:
        decision_type = DecisionType.CONFLICTING
        mapping_status = MappingStatus.CONFLICTING
        load_status = LoadStatus.BLOCKED

    elif is_marked_do_not_migrate:
        decision_type = DecisionType.DO_NOT_MIGRATE
        mapping_status = MappingStatus.NOT_APPLICABLE
        load_status = LoadStatus.EXCLUDED
        extra["fallback_rule_reference"] = do_not_migrate_reference

    elif resolved_value is not None and not is_default_value:
        decision_type = DecisionType.MAPPED
        mapping_status = MappingStatus.RESOLVED
        load_status = LoadStatus.ELIGIBLE
        extra["resolved_value"] = resolved_value

    elif is_default_value:
        # default_value es EXCLUSIVAMENTE para origen vacío/nulo con regla
        # documentada -- nunca para sustituir una ausencia de equivalencia
        # (eso es fallback_value, aunque el valor aplicado se parezca).
        decision_type = DecisionType.DEFAULT_VALUE
        mapping_status = MappingStatus.RESOLVED
        load_status = LoadStatus.ELIGIBLE
        extra["resolved_value"] = default_value_applied

    elif fallback_rule is not None:
        decision_type = DecisionType.FALLBACK_VALUE
        mapping_status = MappingStatus.UNRESOLVED_WITH_FALLBACK
        requires_review = fallback_rule.load_permission is None
        load_status = fallback_rule.load_permission or LoadStatus.BLOCKED
        extra.update(
            fallback_value=fallback_rule.fallback_value,
            fallback_rule_reference=fallback_rule.rule_id,
            fallback_load_permission=fallback_rule.load_permission,
            fallback_load_permission_source=fallback_rule.load_permission_source,
            requires_client_review=requires_review,
        )

    else:
        decision_type = DecisionType.PENDING_MAPPING
        mapping_status = MappingStatus.UNRESOLVED
        load_status = LoadStatus.BLOCKED

    decision = MappingDecision(
        id=decision_id,
        mapping_scope=mapping_scope,
        key_fields=list(key_fields),
        key_values_raw=list(key_values_raw),
        key_normalized=key_normalized,
        decision_type=decision_type,
        mapping_status=mapping_status,
        load_status=load_status,
        **extra,
    )

    violations = validate_mapping_decision_consistency(decision)
    if violations:
        decision.warnings.extend(f"INCONSISTENCIA: {v}" for v in violations)

    return decision


def build_coverage_finding(
    *,
    decision: MappingDecision,
    analysis_run_id: str,
    source_snapshot_id: str,
    affected_record_count: int,
    example_historical_ids: list[str],
    detected_at: str,
    max_examples: int = 10,
) -> MappingCoverageFinding:
    """Construye el `MappingCoverageFinding` de una corrida concreta sobre
    una `MappingDecision` ya construida. `example_historical_ids` se recorta
    a `max_examples` -- es una muestra para trazabilidad, nunca el listado
    completo de registros afectados."""
    return MappingCoverageFinding(
        id=make_mapping_coverage_finding_id(decision.id, analysis_run_id),
        analysis_run_id=analysis_run_id,
        mapping_decision_id=decision.id,
        source_snapshot_id=source_snapshot_id,
        affected_record_count=affected_record_count,
        example_historical_ids=list(example_historical_ids[:max_examples]),
        first_detected_at=detected_at,
        last_detected_at=detected_at,
    )


# ---------------------------------------------------------------------------
# Unión Finding <-> Decision (fuente única de las 7 salidas)
# ---------------------------------------------------------------------------

@dataclass
class CoverageRow:
    module: str
    decision: MappingDecision
    finding: MappingCoverageFinding


def join_findings_with_decisions(
    findings: list[MappingCoverageFinding],
    decisions_by_id: dict[str, MappingDecision],
    module_by_decision_id: dict[str, str],
) -> list[CoverageRow]:
    """Une cada finding con su decisión. Un finding cuya decisión no exista
    en `decisions_by_id` se descarta silenciosamente (violación de
    integridad referencial que no debería ocurrir en un uso normal) -- no se
    inventa una decisión ni se reporta con datos incompletos."""
    rows: list[CoverageRow] = []
    for finding in findings:
        decision = decisions_by_id.get(finding.mapping_decision_id)
        if decision is None:
            continue
        module = module_by_decision_id.get(finding.mapping_decision_id, "desconocido")
        rows.append(CoverageRow(module=module, decision=decision, finding=finding))
    return rows


# ---------------------------------------------------------------------------
# Generación de las 7 salidas
# ---------------------------------------------------------------------------

def _write_csv(path: str | Path, header: list[str], data_rows: list[list]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data_rows)


def rows_unmapped_entities(rows: list[CoverageRow]) -> list[CoverageRow]:
    return [
        r for r in rows
        if r.decision.decision_type == DecisionType.PENDING_MAPPING
        and r.decision.mapping_scope == MappingScope.ENTITY
    ]


def rows_unmapped_field_values(rows: list[CoverageRow]) -> list[CoverageRow]:
    return [
        r for r in rows
        if r.decision.decision_type == DecisionType.PENDING_MAPPING
        and r.decision.mapping_scope != MappingScope.ENTITY
    ]


def rows_marked_no_migrate(rows: list[CoverageRow]) -> list[CoverageRow]:
    return [r for r in rows if r.decision.decision_type == DecisionType.DO_NOT_MIGRATE]


def rows_with_mapping_fallback(rows: list[CoverageRow]) -> list[CoverageRow]:
    return [r for r in rows if r.decision.decision_type == DecisionType.FALLBACK_VALUE]


def rows_blocked_by_mapping(rows: list[CoverageRow]) -> list[CoverageRow]:
    return [r for r in rows if r.decision.load_status == LoadStatus.BLOCKED]


def write_unmapped_entities_csv(rows: list[CoverageRow], path: str | Path) -> int:
    selected = rows_unmapped_entities(rows)
    _write_csv(
        path,
        ["module", "key_fields", "key_values_raw", "key_normalized", "affected_record_count",
         "example_historical_ids", "mapping_status", "load_status"],
        [
            [r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
             r.decision.key_normalized, r.finding.affected_record_count,
             "|".join(r.finding.example_historical_ids), r.decision.mapping_status, r.decision.load_status]
            for r in selected
        ],
    )
    return len(selected)


def write_unmapped_field_values_csv(rows: list[CoverageRow], path: str | Path) -> int:
    selected = rows_unmapped_field_values(rows)
    _write_csv(
        path,
        ["module", "key_fields", "key_values_raw", "affected_record_count",
         "example_historical_ids", "mapping_status", "load_status"],
        [
            [r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
             r.finding.affected_record_count, "|".join(r.finding.example_historical_ids),
             r.decision.mapping_status, r.decision.load_status]
            for r in selected
        ],
    )
    return len(selected)


def write_records_marked_no_migrate_csv(rows: list[CoverageRow], path: str | Path) -> int:
    selected = rows_marked_no_migrate(rows)
    _write_csv(
        path,
        ["module", "key_fields", "key_values_raw", "decision_reference",
         "affected_record_count", "example_historical_ids", "load_status"],
        [
            [r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
             r.decision.fallback_rule_reference or "", r.finding.affected_record_count,
             "|".join(r.finding.example_historical_ids), r.decision.load_status]
            for r in selected
        ],
    )
    return len(selected)


def write_records_with_mapping_fallback_csv(rows: list[CoverageRow], path: str | Path) -> int:
    selected = rows_with_mapping_fallback(rows)
    _write_csv(
        path,
        ["module", "key_fields", "key_values_raw", "fallback_value_applied", "fallback_rule_reference",
         "mapping_status", "load_status", "requires_client_review", "affected_record_count",
         "example_historical_ids"],
        [
            [r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
             r.decision.fallback_value or "", r.decision.fallback_rule_reference or "",
             r.decision.mapping_status, r.decision.load_status, r.decision.requires_client_review,
             r.finding.affected_record_count, "|".join(r.finding.example_historical_ids)]
            for r in selected
        ],
    )
    return len(selected)


def write_records_blocked_by_mapping_csv(rows: list[CoverageRow], path: str | Path) -> int:
    selected = rows_blocked_by_mapping(rows)
    _write_csv(
        path,
        ["module", "decision_type", "mapping_status", "key_fields", "key_values_raw",
         "affected_record_count", "example_historical_ids", "reason"],
        [
            [r.module, r.decision.decision_type, r.decision.mapping_status,
             "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
             r.finding.affected_record_count, "|".join(r.finding.example_historical_ids),
             "; ".join(r.decision.warnings) if r.decision.warnings else ""]
            for r in selected
        ],
    )
    return len(selected)


def write_mapping_summary_csv(rows: list[CoverageRow], path: str | Path) -> int:
    aggregated: dict[tuple[str, str, str, str], dict] = {}
    for r in rows:
        key = (r.module, r.decision.decision_type, r.decision.mapping_status, r.decision.load_status)
        agg = aggregated.setdefault(key, {"total": 0, "keys": set()})
        agg["total"] += r.finding.affected_record_count
        agg["keys"].add(r.decision.key_normalized)

    data_rows = [
        [module, decision_type, mapping_status, load_status, agg["total"], len(agg["keys"])]
        for (module, decision_type, mapping_status, load_status), agg in sorted(aggregated.items())
    ]
    _write_csv(
        path,
        ["module", "decision_type", "mapping_status", "load_status", "total_affected_records", "distinct_keys"],
        data_rows,
    )
    return len(data_rows)


def write_client_mapping_questions_xlsx(rows: list[CoverageRow], path: str | Path) -> dict[str, int]:
    """Genera el .xlsx multi-hoja para el cliente. Devuelve el nº de filas
    escritas por hoja (para poder verificar en tests sin reabrir el fichero)."""
    wb = Workbook()
    wb.remove(wb.active)

    counts: dict[str, int] = {}

    def _sheet(name: str, header: list[str], data: list[list]) -> None:
        ws = wb.create_sheet(name)
        ws.append(header)
        for row in data:
            ws.append(row)
        counts[name] = len(data)

    entidades = rows_unmapped_entities(rows)
    _sheet(
        "Entidades sin equivalencia",
        ["module", "key_fields", "key_values_raw", "affected_record_count", "example_historical_ids"],
        [[r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
          r.finding.affected_record_count, "|".join(r.finding.example_historical_ids)] for r in entidades],
    )

    campos = rows_unmapped_field_values(rows)
    _sheet(
        "Campos sin equivalencia",
        ["module", "key_fields", "key_values_raw", "affected_record_count", "example_historical_ids"],
        [[r.module, "|".join(r.decision.key_fields), "|".join(r.decision.key_values_raw),
          r.finding.affected_record_count, "|".join(r.finding.example_historical_ids)] for r in campos],
    )

    fallbacks = rows_with_mapping_fallback(rows)
    _sheet(
        "Fallbacks sin equivalencia",
        ["module", "key_values_raw", "fallback_value_applied", "fallback_rule_reference",
         "load_status", "requires_client_review", "affected_record_count"],
        [[r.module, "|".join(r.decision.key_values_raw), r.decision.fallback_value,
          r.decision.fallback_rule_reference, r.decision.load_status,
          r.decision.requires_client_review, r.finding.affected_record_count] for r in fallbacks],
    )

    no_migra = rows_marked_no_migrate(rows)
    _sheet(
        "Valores No migra",
        ["module", "key_values_raw", "decision_reference", "affected_record_count"],
        [[r.module, "|".join(r.decision.key_values_raw), r.decision.fallback_rule_reference,
          r.finding.affected_record_count] for r in no_migra],
    )

    conflictos = [r for r in rows if r.decision.decision_type == DecisionType.CONFLICTING]
    _sheet(
        "Conflictos",
        ["module", "key_values_raw", "affected_record_count"],
        [[r.module, "|".join(r.decision.key_values_raw), r.finding.affected_record_count] for r in conflictos],
    )

    aggregated: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.module, r.decision.decision_type)
        aggregated[key] = aggregated.get(key, 0) + r.finding.affected_record_count
    _sheet(
        "Resumen",
        ["module", "decision_type", "total_affected_records"],
        [[module, decision_type, total] for (module, decision_type), total in sorted(aggregated.items())],
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return counts


REQUIRED_CLIENT_XLSX_SHEETS = (
    "Entidades sin equivalencia",
    "Campos sin equivalencia",
    "Fallbacks sin equivalencia",
    "Valores No migra",
    "Conflictos",
    "Resumen",
)


def generate_coverage_reports(rows: list[CoverageRow], output_dir: str | Path) -> dict[str, int]:
    """Genera las 7 salidas en `output_dir`. Devuelve el nº de filas
    escritas por fichero."""
    output_dir = Path(output_dir)
    result = {
        "unmapped_entities.csv": write_unmapped_entities_csv(rows, output_dir / "unmapped_entities.csv"),
        "unmapped_field_values.csv": write_unmapped_field_values_csv(rows, output_dir / "unmapped_field_values.csv"),
        "records_marked_no_migrate.csv": write_records_marked_no_migrate_csv(rows, output_dir / "records_marked_no_migrate.csv"),
        "records_with_mapping_fallback.csv": write_records_with_mapping_fallback_csv(rows, output_dir / "records_with_mapping_fallback.csv"),
        "records_blocked_by_mapping.csv": write_records_blocked_by_mapping_csv(rows, output_dir / "records_blocked_by_mapping.csv"),
        "mapping_summary.csv": write_mapping_summary_csv(rows, output_dir / "mapping_summary.csv"),
    }
    sheet_counts = write_client_mapping_questions_xlsx(rows, output_dir / "client_mapping_questions.xlsx")
    result["client_mapping_questions.xlsx"] = sheet_counts
    return result
