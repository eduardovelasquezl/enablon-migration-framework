"""
Modelo de dominio del Migration Metadata Repository.

Separa deliberadamente tres capas, que no deben mezclarse:

- CATÁLOGO: entidades de existencia pura (dataclasses de este módulo). Ninguna
  entidad de catálogo lleva claves foráneas embebidas hacia otra entidad --
  eso vive exclusivamente en `Relation`.
- RELACIONES: aristas tipadas entre IDs de catálogo (`Relation`).
- EVIDENCIAS: procedencia de cualquier hecho de catálogo o relación (`Evidence`).

Todos los identificadores son deterministas (funciones `make_*_id`) -- nunca
UUID aleatorio. Dos ejecuciones sobre el mismo dato producen siempre el mismo
ID, lo que permite comparar corridas y detectar qué cambió.

Este módulo no lee ficheros, no toca Excel/SQL/CSV y no tiene efectos
secundarios -- es puro modelo de datos + construcción de IDs + validación de
invariantes. La lectura real vive en `src/etl/mapping_resolver.py` y
`src/analysis/mapping_coverage.py`.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Normalización de texto y nombres de fichero
#
# Nunca modifica ni renombra ficheros originales -- solo produce una forma
# normalizada en memoria para poder comparar/emparejar, y señala con un
# warning explícito cuando el emparejamiento solo funciona después de
# normalizar (indicio de que uno de los dos nombres puede estar mal
# codificado). La detección de mojibake es una heurística declarada como tal,
# no una corrección: no intenta adivinar el texto correcto.
# ---------------------------------------------------------------------------

# Caracteres que aparecen típicamente cuando UTF-8 se reinterpreta con una
# página de códigos distinta (CP1252, OEM/CP437...). No es una lista
# exhaustiva ni infalible -- es una señal para revisar, no una prueba.
_MOJIBAKE_MARKERS = frozenset("├┬ÂÃ¤¥§░▒▓") | {"�"}

_SLUG_INVALID = re.compile(r"[^a-z0-9_.]+")
_SLUG_REPEATED_UNDERSCORE = re.compile(r"_+")


def normalize_nfc(text: str) -> str:
    """Normaliza a la forma de composición Unicode NFC. No altera el
    contenido semántico del texto, solo su representación en memoria."""
    return unicodedata.normalize("NFC", text)


def looks_like_mojibake(text: str) -> bool:
    """Heurística de detección de mojibake (p. ej. 'LESI├ôN' en vez de
    'LESIÓN'). Puede dar falsos negativos con corrupciones distintas a las
    ya vistas en este proyecto -- no se usa para decidir nada por sí sola,
    solo para anotar un warning cuando coincide con una discrepancia real de
    emparejamiento (ver `match_filename`)."""
    return any(marker in text for marker in _MOJIBAKE_MARKERS)


# Páginas de código legacy que, reinterpretadas como si los bytes fueran
# UTF-8, explican los mojibakes ya vistos en este proyecto (ej. 'Ó' ->
# 'LESI├ôN' via CP437). Esto es un intento de REPARAR la representación en
# memoria para poder comparar/emparejar -- nunca se escribe de vuelta al
# fichero original.
_MOJIBAKE_SOURCE_ENCODINGS: tuple[str, ...] = ("cp437", "cp1252")


def attempt_mojibake_repair(text: str) -> str | None:
    """Intenta reinterpretar `text` como si sus caracteres fueran en
    realidad bytes de una página de códigos legacy que después se
    decodificaron (incorrectamente) como UTF-8. Devuelve el texto reparado
    si alguna combinación produce una decodificación válida, o `None` si
    ninguna funciona. Es una heurística de recuperación, no una prueba --
    quien la use debe seguir tratando el resultado como no confirmado hasta
    verificarlo contra otra evidencia (ver `match_filename`)."""
    for encoding in _MOJIBAKE_SOURCE_ENCODINGS:
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if candidate != text:
            return candidate
    return None


def slugify(text: str) -> str:
    """Texto -> fragmento de ID determinista: NFC, sin acentos, minúsculas,
    solo [a-z0-9_.]. Dos textos que solo difieren en acentos o mayúsculas
    producen el mismo slug -- por diseño, para que un ID no dependa de cómo
    se capturó el texto. El texto original nunca se descarta: se conserva
    aparte en los campos *_raw de cada entidad."""
    normalized = normalize_nfc(text).strip().lower()
    without_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(c) != "Mn"
    )
    slug = _SLUG_INVALID.sub("_", without_accents)
    slug = _SLUG_REPEATED_UNDERSCORE.sub("_", slug)
    return slug.strip("_")


def short_hash(*parts: str, length: int = 10) -> str:
    """Hash determinista corto para componer IDs cuando el contexto completo
    sería demasiado largo o con caracteres problemáticos. Nunca sustituye al
    contexto legible -- se usa como sufijo, y el valor completo se conserva
    en los campos *_raw de la entidad."""
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


@dataclass
class FilenameMatch:
    matched: bool
    exact: bool
    required_nfc_normalization: bool
    required_mojibake_repair: bool
    mojibake_suspected_in: str | None  # "candidate" | "reference" | None
    warning: str | None


def match_filename(candidate: str, reference: str) -> FilenameMatch:
    """Compara dos nombres de fichero sin modificar ninguno de los dos, en
    tres pasos separados y en este orden:

    1. Coincidencia exacta.
    2. Normalización Unicode NFC (arregla formas de composición distintas
       del MISMO carácter -- nunca arregla mojibake, son problemas
       distintos).
    3. Reparación de mojibake (`attempt_mojibake_repair`) -- un mecanismo
       DELIBERADAMENTE separado del anterior, porque NFC no puede resolver
       una recodificación incorrecta (bytes de un carácter reinterpretados
       como otros), solo diferencias de composición del mismo carácter.

    Si el emparejamiento solo funciona en el paso 2 o 3, se marca el campo
    correspondiente y se genera un warning explícito -- nunca se corrige el
    nombre en disco, solo se documenta que hizo falta una corrección para
    emparejar.
    """
    if candidate == reference:
        return FilenameMatch(True, True, False, False, None, None)

    nfc_candidate = normalize_nfc(candidate)
    nfc_reference = normalize_nfc(reference)
    if nfc_candidate.lower() == nfc_reference.lower():
        mojibake_side = _mojibake_side(candidate, reference)
        warning = f"Emparejado tras normalizar Unicode (NFC): {candidate!r} == {reference!r}."
        if mojibake_side:
            warning += (
                f" Posible mojibake en el lado '{mojibake_side}' -- no se ha "
                "modificado ningún archivo, solo se registra para revisión."
            )
        return FilenameMatch(True, False, True, False, mojibake_side, warning)

    # NFC no resolvió nada -- intentar reparación de mojibake (mecanismo
    # separado, no una segunda pasada de lo mismo).
    for repaired, side in (
        (attempt_mojibake_repair(candidate), "candidate"),
        (attempt_mojibake_repair(reference), "reference"),
    ):
        if repaired is None:
            continue
        other = reference if side == "candidate" else candidate
        if repaired == other or normalize_nfc(repaired).lower() == normalize_nfc(other).lower():
            warning = (
                f"Emparejado tras reparar mojibake en el lado '{side}': "
                f"{candidate!r} <-> {reference!r}. No se ha modificado ningún "
                "archivo -- la reparación es solo para poder relacionar la "
                "evidencia, revisar antes de dar el emparejamiento por definitivo."
            )
            return FilenameMatch(True, False, False, True, side, warning)

    return FilenameMatch(False, False, False, False, None, None)


def _mojibake_side(candidate: str, reference: str) -> str | None:
    candidate_suspect = looks_like_mojibake(candidate)
    reference_suspect = looks_like_mojibake(reference)
    if candidate_suspect and not reference_suspect:
        return "candidate"
    if reference_suspect and not candidate_suspect:
        return "reference"
    return None


# ---------------------------------------------------------------------------
# Vocabularios cerrados (nunca texto libre para estos campos)
# ---------------------------------------------------------------------------

class MappingScope:
    ENTITY = "entity"
    FIELD = "field"
    RELATIONSHIP = "relationship"
    UNKNOWN = "unknown"
    ALL = frozenset({ENTITY, FIELD, RELATIONSHIP, UNKNOWN})


class DecisionType:
    MAPPED = "mapped"
    DO_NOT_MIGRATE = "do_not_migrate"
    FALLBACK_VALUE = "fallback_value"
    PENDING_MAPPING = "pending_mapping"
    DEFAULT_VALUE = "default_value"
    NOT_APPLICABLE = "not_applicable"
    CONFLICTING = "conflicting"
    ALL = frozenset(
        {MAPPED, DO_NOT_MIGRATE, FALLBACK_VALUE, PENDING_MAPPING, DEFAULT_VALUE, NOT_APPLICABLE, CONFLICTING}
    )


class MappingStatus:
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNRESOLVED_WITH_FALLBACK = "unresolved_with_fallback"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"
    ALL = frozenset({RESOLVED, UNRESOLVED, UNRESOLVED_WITH_FALLBACK, CONFLICTING, NOT_APPLICABLE})


class LoadStatus:
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_WARNING = "eligible_with_warning"
    BLOCKED = "blocked"
    EXCLUDED = "excluded"
    ALL = frozenset({ELIGIBLE, ELIGIBLE_WITH_WARNING, BLOCKED, EXCLUDED})


class EvidenceStatus:
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    ALL = frozenset({CONFIRMED, INFERRED, PENDING, NOT_APPLICABLE})


class ResolutionStatus:
    """Estado de una `Relation` -- distinto de `MappingStatus`, que es
    propio de `MappingDecision`."""
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    PENDING = "pending"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"
    ALL = frozenset({CONFIRMED, INFERRED, PENDING, CONFLICTING, NOT_APPLICABLE})


class FallbackLoadPermissionSource:
    ETL_RULE = "etl_rule"
    FUNCTIONAL_DECISION = "functional_decision"
    VALIDATION_RULE = "validation_rule"
    USER_CONFIRMATION = "user_confirmation"
    UNKNOWN = "unknown"
    ALL = frozenset({ETL_RULE, FUNCTIONAL_DECISION, VALIDATION_RULE, USER_CONFIRMATION, UNKNOWN})


class RuleKind:
    TRANSFORMATION = "transformation"
    EXCLUSION = "exclusion"
    FALLBACK = "fallback"
    DEFAULT_VALUE = "default_value"
    VALIDATION = "validation"
    ALL = frozenset({TRANSFORMATION, EXCLUSION, FALLBACK, DEFAULT_VALUE, VALIDATION})


class ProcessingScope:
    """Alcance de procesamiento de un `MigrationObject`: la mayoría se
    procesa dentro de su propio módulo; Action Plans (y cualquier otro
    objeto transversal futuro con evidencia real) se procesa cruzando
    módulos."""
    MODULE = "module"
    CROSS_MODULE = "cross_module"
    ALL = frozenset({MODULE, CROSS_MODULE})


class LoadPhase:
    """Fase de carga de un `MigrationObject`. Action Plans es "final":
    nunca se genera su CSV durante el análisis individual de un módulo."""
    NORMAL = "normal"
    FINAL = "final"
    ALL = frozenset({NORMAL, FINAL})


class ActionPlanRelationshipType:
    LINKED = "linked_action_plan"
    STANDALONE = "standalone_action_plan"
    ALL = frozenset({LINKED, STANDALONE})


class ActionPlanProcessingStatus:
    """Estado OPERATIVO del buffer transversal de Action Plans -- distinto
    de `relationship_status` (que es el estado de la EVIDENCIA de la
    relación con el objeto origen, ver `ResolutionStatus`). No se deriva
    uno del otro automáticamente."""
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    WAITING_FOR_PARENT = "waiting_for_parent"
    PARENT_RESOLVED = "parent_resolved"
    READY_FOR_FINAL_LOAD = "ready_for_final_load"
    BLOCKED = "blocked"
    EXCLUDED = "excluded"
    ALL = frozenset(
        {DISCOVERED, VALIDATED, WAITING_FOR_PARENT, PARENT_RESOLVED, READY_FOR_FINAL_LOAD, BLOCKED, EXCLUDED}
    )


class DependencySource:
    """De dónde sale la evidencia de que un módulo genera Action Plans.
    `CONFIGURED_MAPPING` (solo config/modules.yaml, sin evidencia adicional)
    nunca basta por sí solo para `resolution_status=confirmed` -- ver
    `validate_action_plan_dependency_relation`."""
    FUNCTIONAL_DECISION = "functional_decision"
    ETL_MAPPING = "etl_mapping"
    SOURCE_DATA = "source_data"
    SQL_EVIDENCE = "sql_evidence"
    CONFIGURED_MAPPING = "configured_mapping"
    ALL = frozenset({FUNCTIONAL_DECISION, ETL_MAPPING, SOURCE_DATA, SQL_EVIDENCE, CONFIGURED_MAPPING})


class DependencyScope:
    DATA_DRIVEN = "data_driven"
    ALL = frozenset({DATA_DRIVEN})


ACTION_PLAN_DEPENDS_ON_MIGRATION_OBJECT = "action_plan_object_depends_on_migration_object"


def _check_choice(value: str | None, allowed: frozenset[str], field_name: str) -> None:
    if value is not None and value not in allowed:
        raise ValueError(f"{field_name}={value!r} no es un valor válido de {sorted(allowed)}")


# ---------------------------------------------------------------------------
# Entidades de catálogo -- existencia pura, sin FKs embebidas
# ---------------------------------------------------------------------------

@dataclass
class Module:
    id: str
    name: str
    status: str = ""
    notes: str = ""


@dataclass
class SourceSystem:
    id: str
    name: str


@dataclass
class SourceObject:
    id: str
    schema: str
    table_name: str
    kind: str = "table"  # table | view | synonym


@dataclass
class SourceField:
    id: str
    column_name: str
    data_type: str | None = None


@dataclass
class Query:
    id: str
    file_path: str
    file_hash: str
    has_where: bool = False
    joins_raw: list[str] = field(default_factory=list)
    from_tables_raw: list[str] = field(default_factory=list)


@dataclass
class SelectExpression:
    id: str
    position: int
    raw_expression: str
    output_alias: str | None = None
    is_calculated: bool = False
    functions_used: list[str] = field(default_factory=list)
    is_wildcard: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ETLWorkbook:
    id: str
    file_path: str
    file_hash: str
    size_mb: float
    has_vba: bool = False
    modified_at: str | None = None


@dataclass
class ETLSheet:
    id: str
    title: str
    max_row: int
    max_col: int


@dataclass
class MigrationObject:
    """Objeto funcional granular dentro de un módulo -- p. ej. dentro del
    módulo 'eventos': Events, Impacts, Investigations, PSM Forms son cuatro
    MigrationObject distintos del mismo Module. Existe para poder tratar un
    módulo compuesto como un único módulo funcional sin perder la distinción
    entre sus objetos (ver CLAUDE.md / correspondencia funcional de Eventos).

    `processing_scope`/`load_phase` distinguen objetos transversales de
    fase final (hoy, únicamente Action Plans) del resto -- por defecto
    "module"/"normal", para no romper instancias ya construidas."""
    id: str
    name: str
    functional_order: int | None = None  # orden de carga esperado, si aplica
    processing_scope: str = ProcessingScope.MODULE
    load_phase: str = LoadPhase.NORMAL

    def __post_init__(self) -> None:
        _check_choice(self.processing_scope, ProcessingScope.ALL, "processing_scope")
        _check_choice(self.load_phase, LoadPhase.ALL, "load_phase")


@dataclass
class Mapping:
    """Una fila de una hoja de mapeo de campo (definición estructural
    ES->XML) -- nivel definición, no nivel dato. Ver `MappingDecision` para
    el nivel dato/valor."""
    id: str
    destination_label_es: str | None
    resolution_status: str  # resolved_exact | unresolved | ambiguous | missing_destination | invalid_row
    resolution_method: str
    source_row: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class MigrationRule:
    """Generaliza el concepto de regla documentada -- transformación de
    campo, exclusión ('No migra'), fallback (p. ej. UnidadNull), valor por
    defecto o validación. `rule_kind` discrimina el tipo."""
    id: str
    canonical_name: str
    rule_kind: str  # ver RuleKind
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    confirmed_con_datos_reales: str = "false"  # "true" | "false" | "partial"
    fallback_load_permission: str | None = None  # ver LoadStatus (solo eligible_with_warning|blocked tienen sentido aquí)
    fallback_load_permission_source: str | None = None  # ver FallbackLoadPermissionSource

    def __post_init__(self) -> None:
        _check_choice(self.rule_kind, RuleKind.ALL, "rule_kind")
        _check_choice(
            self.fallback_load_permission,
            frozenset({LoadStatus.ELIGIBLE_WITH_WARNING, LoadStatus.BLOCKED}),
            "fallback_load_permission",
        )
        _check_choice(
            self.fallback_load_permission_source,
            FallbackLoadPermissionSource.ALL,
            "fallback_load_permission_source",
        )


@dataclass
class EntityMapping:
    id: str
    source_entity_code: str
    enablon_entity_path: str


@dataclass
class EnablonObject:
    id: str
    name: str


@dataclass
class EnablonField:
    id: str
    field_name_xml: str


@dataclass
class CSVSchema:
    id: str
    file_path: str
    file_hash: str
    encoding: str
    separator: str
    approx_row_count: int


@dataclass
class CSVColumn:
    id: str
    position: int
    header_name: str


@dataclass
class KnownError:
    id: str
    ticket_id: str
    title: str
    description: str = ""
    status: str = ""


@dataclass
class FunctionalDecision:
    id: str
    description: str


@dataclass
class Validation:
    """Comprobación de calidad de datos documentada (ver
    config/validation_rules.yaml -> data_quality_checks)."""
    id: str
    description: str
    action: str
    threshold: str | None = None


@dataclass
class MappingDecision:
    """Decisión estable sobre una clave (simple o compuesta): NO contiene
    recuentos ni ejemplos de registro -- eso es responsabilidad de
    `MappingCoverageFinding`, precisamente para que una misma decisión pueda
    producir resultados distintos en BAK/freezes distintos sin reescribir la
    decisión en sí."""
    id: str
    mapping_scope: str  # ver MappingScope
    key_fields: list[str]
    key_values_raw: list[str]
    key_normalized: str
    decision_type: str  # ver DecisionType
    mapping_status: str  # ver MappingStatus
    load_status: str  # ver LoadStatus
    resolved_value: str | None = None
    fallback_value: str | None = None
    fallback_rule_reference: str | None = None
    fallback_load_permission: str | None = None
    fallback_load_permission_source: str | None = None
    requires_client_review: bool = False
    # Preparado para el motor de versionado futuro -- no hay lógica de
    # versionado implementada todavía, solo los campos para no tener que
    # cambiar el esquema cuando se implemente.
    valid_from: str | None = None
    valid_to: str | None = None
    supersedes_decision_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_choice(self.mapping_scope, MappingScope.ALL, "mapping_scope")
        _check_choice(self.decision_type, DecisionType.ALL, "decision_type")
        _check_choice(self.mapping_status, MappingStatus.ALL, "mapping_status")
        _check_choice(self.load_status, LoadStatus.ALL, "load_status")
        _check_choice(
            self.fallback_load_permission,
            frozenset({LoadStatus.ELIGIBLE_WITH_WARNING, LoadStatus.BLOCKED}),
            "fallback_load_permission",
        )
        _check_choice(
            self.fallback_load_permission_source,
            FallbackLoadPermissionSource.ALL,
            "fallback_load_permission_source",
        )
        if len(self.key_fields) != len(self.key_values_raw):
            raise ValueError(
                "key_fields y key_values_raw deben tener la misma longitud "
                f"({len(self.key_fields)} != {len(self.key_values_raw)})"
            )


@dataclass
class MappingCoverageFinding:
    """Resultado observado de aplicar una `MappingDecision` en una corrida
    de análisis concreta, sobre un snapshot de datos concreto (BAK/freeze).
    Lleva los recuentos y ejemplos que `MappingDecision` no lleva."""
    id: str
    analysis_run_id: str
    mapping_decision_id: str
    source_snapshot_id: str
    affected_record_count: int
    example_historical_ids: list[str]
    first_detected_at: str
    last_detected_at: str
    finding_status: str = "active"  # active | resolved | superseded
    warnings: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    id: str
    subject_type: str  # "entity" | "relation"
    subject_id: str
    source_path: str
    file_name: str
    file_hash: str
    modified_at: str | None
    evidence_status: str  # ver EvidenceStatus
    workbook_sheet: str | None = None
    row_or_range: str | None = None
    extraction_timestamp: str | None = None
    parser_version: str | None = None
    confidence_score: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        _check_choice(self.subject_type, frozenset({"entity", "relation"}), "subject_type")
        _check_choice(self.evidence_status, EvidenceStatus.ALL, "evidence_status")
        if self.confidence_score is not None and not (0 <= self.confidence_score <= 100):
            raise ValueError(f"confidence_score={self.confidence_score} debe estar entre 0 y 100")


@dataclass
class OpenQuestion:
    id: str
    question_text: str
    status: str = "open"  # open | resolved
    created_at: str | None = None
    resolved_at: str | None = None
    resolution_note: str | None = None
    affected_entity_ids: list[str] = field(default_factory=list)


@dataclass
class Relation:
    """Arista tipada entre dos IDs de catálogo. Nunca se embebe dentro de
    una entidad de catálogo -- vive aparte, precisamente para poder separar
    'qué existe' de 'cómo se relaciona'.

    `order` (solo relation_type=functional_hierarchy) y
    `dependency_scope`/`source_idorigenac_values` (solo relation_type=
    action_plan_object_depends_on_migration_object) son campos específicos
    de un tipo de relación concreto -- quedan `None`/vacíos para el resto,
    en vez de crear una subclase por cada tipo de relación."""
    id: str
    subject_id: str
    relation_type: str
    object_id: str
    resolution_status: str  # ver ResolutionStatus
    authoritative_source: str
    evidence_ids: list[str] = field(default_factory=list)
    confidence_score: int | None = None
    order: int | None = None  # solo relevante para relation_type=functional_hierarchy
    dependency_scope: str | None = None  # ver DependencyScope -- solo action_plan_object_depends_on_migration_object
    source_idorigenac_values: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        _check_choice(self.resolution_status, ResolutionStatus.ALL, "resolution_status")
        _check_choice(self.dependency_scope, DependencyScope.ALL, "dependency_scope")
        if self.confidence_score is not None and not (0 <= self.confidence_score <= 100):
            raise ValueError(f"confidence_score={self.confidence_score} debe estar entre 0 y 100")


@dataclass
class CrossModuleActionPlanBuffer:
    """Estructura de TRABAJO transitoria, no de catálogo -- representa una
    acción candidata a Action Plans mientras se consolida entre módulos.
    Produce entidades de catálogo (Mapping/MappingDecision/Relation) solo
    cuando termina de resolverse; no es en sí misma un hecho estable.

    `relationship_status` (ver ResolutionStatus) es el estado de la
    EVIDENCIA de la relación con el objeto origen. `processing_status` (ver
    ActionPlanProcessingStatus) es el estado del WORKFLOW del buffer. No se
    deriva uno del otro automáticamente -- una acción linked puede tener
    campos `validated` y seguir con el padre `pending`."""
    id: str
    action_plan_historical_id: str
    source_system: str
    source_module: str
    source_migration_object: str
    source_historical_id: str
    relationship_type: str  # ver ActionPlanRelationshipType
    target_historical_reference: str | None
    target_enablon_reference: str | None
    relationship_status: str  # ver ResolutionStatus
    processing_status: str  # ver ActionPlanProcessingStatus
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_choice(self.relationship_type, ActionPlanRelationshipType.ALL, "relationship_type")
        _check_choice(self.relationship_status, ResolutionStatus.ALL, "relationship_status")
        _check_choice(self.processing_status, ActionPlanProcessingStatus.ALL, "processing_status")


# ---------------------------------------------------------------------------
# Constructores de ID deterministas -- nunca UUID aleatorio.
#
# Cada función es pura: mismo input -> mismo ID, siempre. El contexto
# completo (módulo, objeto de migración, definición de mapping...) forma
# parte del ID para que dos decisiones sobre la misma clave pero en
# contextos distintos no colisionen.
# ---------------------------------------------------------------------------

def make_module_id(module_key: str) -> str:
    return f"module:{slugify(module_key)}"


def make_source_system_id(name: str) -> str:
    return f"source_system:{slugify(name)}"


def make_source_object_id(source_system_key: str, schema: str, table_name: str) -> str:
    return f"source_object:{slugify(source_system_key)}.{slugify(schema)}.{slugify(table_name)}"


def make_source_field_id(source_object_id: str, column_name: str) -> str:
    base = source_object_id.split(":", 1)[1]
    return f"source_field:{base}.{slugify(column_name)}"


def make_query_id(module_key: str, file_stem: str) -> str:
    return f"query:{slugify(module_key)}.{slugify(file_stem)}"


def make_select_expression_id(query_id: str, position: int) -> str:
    base = query_id.split(":", 1)[1]
    return f"select_expression:{base}#{position}"


def make_etl_workbook_id(file_stem: str) -> str:
    return f"etl_workbook:{slugify(file_stem)}"


def make_etl_sheet_id(etl_workbook_id: str, sheet_title: str) -> str:
    base = etl_workbook_id.split(":", 1)[1]
    return f"etl_sheet:{base}.{slugify(sheet_title)}"


def make_migration_object_id(module_key: str, name: str) -> str:
    return f"migration_object:{slugify(module_key)}.{slugify(name)}"


def make_mapping_id(etl_sheet_id: str, source_row: int) -> str:
    base = etl_sheet_id.split(":", 1)[1]
    return f"mapping:{base}#row{source_row}"


def make_migration_rule_id(canonical_name: str) -> str:
    return f"migration_rule:{slugify(canonical_name)}"


def make_entity_mapping_id(source_system_key: str, source_entity_code: str) -> str:
    return f"entity_mapping:{slugify(source_system_key)}.{slugify(source_entity_code)}"


def make_enablon_object_id(name: str) -> str:
    return f"enablon_object:{slugify(name)}"


def make_enablon_field_id(enablon_object_id: str, field_name_xml: str) -> str:
    base = enablon_object_id.split(":", 1)[1]
    return f"enablon_field:{base}.{slugify(field_name_xml)}"


def make_csv_schema_id(file_stem: str) -> str:
    return f"csv_schema:{slugify(file_stem)}"


def make_csv_column_id(csv_schema_id: str, position: int) -> str:
    base = csv_schema_id.split(":", 1)[1]
    return f"csv_column:{base}.{position}"


def make_known_error_id(ticket_id: str) -> str:
    return f"known_error:{slugify(str(ticket_id))}"


def make_functional_decision_id(slug_hint: str) -> str:
    return f"functional_decision:{slugify(slug_hint)}"


def make_validation_id(check_id: str) -> str:
    return f"validation:{slugify(check_id)}"


def make_mapping_decision_id(
    module_id: str,
    migration_object_id: str | None,
    mapping_definition_id: str | None,
    key_fields: list[str],
    key_values_normalized: str,
) -> str:
    """Incluye el contexto completo (módulo, objeto de migración, definición
    de mapping, campos de clave y valor normalizado) -- nunca solo módulo +
    clave, para que la misma clave resuelta por mappings distintos no
    colisione en un único ID."""
    module_part = module_id.split(":", 1)[1]
    migration_object_part = (
        migration_object_id.split(":", 1)[1] if migration_object_id else "unknown_object"
    )
    mapping_definition_part = (
        mapping_definition_id.split(":", 1)[1] if mapping_definition_id else "unknown_mapping"
    )
    key_fields_slug = "_".join(slugify(f) for f in key_fields) or "no_key_fields"
    digest = short_hash(module_part, migration_object_part, mapping_definition_part, key_fields_slug, key_values_normalized)
    return f"mapping_decision:{module_part}.{migration_object_part}.{mapping_definition_part}.{digest}"


def make_mapping_coverage_finding_id(mapping_decision_id: str, analysis_run_id: str) -> str:
    base = mapping_decision_id.split(":", 1)[1]
    return f"mapping_coverage_finding:{base}.{slugify(analysis_run_id)}"


def make_evidence_id(subject_id: str, sequence: int) -> str:
    return f"evidence:{subject_id}#{sequence}"


def make_open_question_id(slug_hint: str, sequence: int) -> str:
    return f"open_question:{slugify(slug_hint)}#{sequence}"


def make_relation_id(subject_id: str, relation_type: str, object_id: str) -> str:
    return f"relation:{subject_id}|{relation_type}|{object_id}"


def make_cross_module_action_plan_buffer_id(
    *,
    source_system: str,
    source_module: str,
    source_migration_object: str,
    action_plan_historical_id: str,
    source_historical_id: str,
) -> str:
    """Formato visible: cross_module_action_plan_buffer:<source_system>.
    <source_module>.<source_migration_object>.<short_hash>.

    El hash incorpora TAMBIÉN `action_plan_historical_id` y
    `source_historical_id` (no aparecen en claro en el ID para no hacerlo
    interminable) -- dos acciones del mismo sistema/módulo/objeto pero con
    ID histórico distinto nunca colisionan, aunque el ID visible parezca
    igual a simple vista."""
    system_part = slugify(source_system)
    module_part = source_module.split(":", 1)[1] if ":" in source_module else slugify(source_module)
    object_part = (
        source_migration_object.split(":", 1)[1] if ":" in source_migration_object else slugify(source_migration_object)
    )
    digest = short_hash(system_part, module_part, object_part, str(action_plan_historical_id), str(source_historical_id))
    return f"cross_module_action_plan_buffer:{system_part}.{module_part}.{object_part}.{digest}"


def build_action_plan_dependency_relation(
    *,
    action_plans_migration_object_id: str,
    depends_on_migration_object_id: str,
    dependency_source: str,
    resolution_status: str,
    evidence_ids: list[str],
    source_idorigenac_values: list[str],
    notes: str | None = None,
) -> Relation:
    """Construye la relación `action_plan_object_depends_on_migration_object`.

    No decide por sí sola si la dependencia está confirmada -- eso lo
    determina quien llama, pasando `resolution_status`. Ver
    `validate_action_plan_dependency_relation` para la regla dura: una
    dependencia basada únicamente en `configured_mapping` nunca puede
    quedar `confirmed`.
    """
    relation = Relation(
        id=make_relation_id(
            action_plans_migration_object_id, ACTION_PLAN_DEPENDS_ON_MIGRATION_OBJECT, depends_on_migration_object_id
        ),
        subject_id=action_plans_migration_object_id,
        relation_type=ACTION_PLAN_DEPENDS_ON_MIGRATION_OBJECT,
        object_id=depends_on_migration_object_id,
        resolution_status=resolution_status,
        authoritative_source=dependency_source,
        evidence_ids=list(evidence_ids),
        dependency_scope=DependencyScope.DATA_DRIVEN,
        source_idorigenac_values=list(source_idorigenac_values),
        notes=notes,
    )
    return relation


def validate_action_plan_dependency_relation(relation: Relation) -> list[str]:
    """Regla dura: `config/modules.yaml` (dependency_source=
    configured_mapping) es la configuración consolidada actual, pero NUNCA
    es evidencia suficiente por sí sola para `resolution_status=confirmed`
    -- debe quedar `inferred` o `pending` hasta contrastarla con decisión
    funcional / ETL / datos SQL reales (ver orden de contraste acordado)."""
    violations: list[str] = []
    if relation.relation_type != ACTION_PLAN_DEPENDS_ON_MIGRATION_OBJECT:
        return violations
    if (
        relation.authoritative_source == DependencySource.CONFIGURED_MAPPING
        and relation.resolution_status == ResolutionStatus.CONFIRMED
    ):
        violations.append(
            "Una dependencia respaldada únicamente por 'configured_mapping' "
            "(config/modules.yaml sin evidencia adicional) no puede quedar "
            "resolution_status=confirmed -- usar 'inferred' o 'pending'."
        )
    return violations


def validate_action_plan_buffer_consistency(buffer: CrossModuleActionPlanBuffer) -> list[str]:
    """Invariantes duras del buffer transversal de Action Plans:

    - standalone_action_plan siempre lleva relationship_status=not_applicable.
    - waiting_for_parent solo es válido para acciones linked, y siempre con
      relationship_status=pending (nunca confirmed/conflicting/not_applicable).
    """
    violations: list[str] = []

    if buffer.relationship_type == ActionPlanRelationshipType.STANDALONE:
        if buffer.relationship_status != ResolutionStatus.NOT_APPLICABLE:
            violations.append("standalone_action_plan debe llevar relationship_status=not_applicable")

    if buffer.processing_status == ActionPlanProcessingStatus.WAITING_FOR_PARENT:
        if buffer.relationship_type != ActionPlanRelationshipType.LINKED:
            violations.append("solo una acción linked_action_plan puede quedar waiting_for_parent")
        if buffer.relationship_status != ResolutionStatus.PENDING:
            violations.append("waiting_for_parent debe llevar relationship_status=pending")

    return violations


# ---------------------------------------------------------------------------
# Validación de invariantes de MappingDecision
#
# Encierra en código la regla dura: ninguna ausencia de correspondencia puede
# desaparecer, convertirse en NULL/vacío silencioso, en "No migra" no
# documentado, ni en un default no documentado.
# ---------------------------------------------------------------------------

# Combinaciones (decision_type, mapping_status, load_status) que la regla de
# negocio considera coherentes. Cualquier combinación fuera de esta tabla es
# una inconsistencia a reportar, no un caso silenciosamente aceptado.
_CONSISTENT_STATUS_COMBINATIONS: frozenset[tuple[str, str, str]] = frozenset(
    {
        (DecisionType.MAPPED, MappingStatus.RESOLVED, LoadStatus.ELIGIBLE),
        (DecisionType.DO_NOT_MIGRATE, MappingStatus.NOT_APPLICABLE, LoadStatus.EXCLUDED),
        (DecisionType.PENDING_MAPPING, MappingStatus.UNRESOLVED, LoadStatus.BLOCKED),
        (DecisionType.FALLBACK_VALUE, MappingStatus.UNRESOLVED_WITH_FALLBACK, LoadStatus.ELIGIBLE_WITH_WARNING),
        (DecisionType.FALLBACK_VALUE, MappingStatus.UNRESOLVED_WITH_FALLBACK, LoadStatus.BLOCKED),
        (DecisionType.DEFAULT_VALUE, MappingStatus.RESOLVED, LoadStatus.ELIGIBLE),
        (DecisionType.CONFLICTING, MappingStatus.CONFLICTING, LoadStatus.BLOCKED),
        (DecisionType.NOT_APPLICABLE, MappingStatus.NOT_APPLICABLE, LoadStatus.EXCLUDED),
    }
)


def validate_mapping_decision_consistency(decision: MappingDecision) -> list[str]:
    """Devuelve la lista de inconsistencias encontradas (vacía si no hay
    ninguna). No lanza excepción -- quien orquesta decide qué hacer con una
    decisión inconsistente (normalmente: no persistirla, y registrar un
    OpenQuestion)."""
    violations: list[str] = []

    combo = (decision.decision_type, decision.mapping_status, decision.load_status)
    if combo not in _CONSISTENT_STATUS_COMBINATIONS:
        violations.append(
            f"Combinación no permitida decision_type={decision.decision_type!r}, "
            f"mapping_status={decision.mapping_status!r}, load_status={decision.load_status!r}"
        )

    if decision.decision_type == DecisionType.PENDING_MAPPING:
        if decision.resolved_value is not None:
            violations.append("pending_mapping no puede tener resolved_value (ausencia silenciosamente resuelta)")
        if decision.fallback_value is not None:
            violations.append("pending_mapping no puede tener fallback_value (fallback no documentado aplicado)")

    if decision.decision_type == DecisionType.MAPPED and decision.resolved_value is None:
        violations.append("mapped debe llevar resolved_value")

    if decision.decision_type == DecisionType.FALLBACK_VALUE:
        if decision.fallback_value is None:
            violations.append("fallback_value requiere un valor de fallback_value")
        if decision.fallback_rule_reference is None:
            violations.append("fallback_value requiere fallback_rule_reference (regla que lo documenta)")
        if decision.mapping_status == MappingStatus.RESOLVED:
            violations.append("un fallback nunca puede quedar mapping_status=resolved -- la ausencia de correspondencia sigue siendo real")

    if decision.decision_type == DecisionType.FALLBACK_VALUE and decision.load_status == LoadStatus.BLOCKED:
        if not decision.requires_client_review:
            violations.append("fallback bloqueado sin autorización documentada debe llevar requires_client_review=True")

    if decision.resolved_value is not None and decision.fallback_value is not None:
        violations.append("resolved_value y fallback_value son mutuamente excluyentes")

    if decision.decision_type == DecisionType.DO_NOT_MIGRATE and decision.load_status != LoadStatus.EXCLUDED:
        violations.append("do_not_migrate debe tener load_status=excluded")

    return violations
