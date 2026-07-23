"""
Taxonomía ampliada de hojas y secciones de un ETL Excel.

PRIVADO -- nadie fuera de `src/analysis/schema_analyzer.py` debe importar
este módulo directamente. `schema_analyzer.py` sigue siendo el único punto
público de análisis estructural de ETL.

Amplía las 5 categorías originales (index/field_mapping/rule/data/unknown)
a las 18 categorías pedidas. Puede devolver MÁS DE UNA clasificación para
una misma hoja física cuando hay secciones lógicas distintas superpuestas
-- confirmado con datos reales: las hojas de mapeo de campo tienen la tabla
de mapeo real en columnas A-E y el catálogo de referencia de Enablon
(independiente, sin relación de fila) en columnas G-H (ver
`src/etl/mapping_resolver.py`).

No convierte automáticamente una hoja sin señal reconocible en ninguna
categoría sustantiva -- el resultado por defecto es `pending_classification`,
nunca una adivinanza.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES = frozenset(
    {
        "index",
        "field_mapping",
        "entity_mapping",
        "equivalence_table",
        "transformation_rule",
        "default_values",
        "validations",
        "required_fields",
        "exclusions_no_migrate",
        "sql_query",
        "quality_control",
        "known_errors",
        "functional_decisions",
        "enablon_reference_catalog",
        "csv_preview",
        "source_data",
        "auxiliary",
        "pending_classification",
    }
)

EVIDENCE_STATUSES = frozenset({"confirmed", "inferred", "pending", "not_applicable"})


@dataclass
class SheetClassification:
    category: str
    evidence_status: str
    confidence_score: int
    evidence: list[str] = field(default_factory=list)
    source_file: str = ""
    sheet: str = ""
    approximate_range: str = ""
    headers_detected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"category={self.category!r} no es una categoría reconocida")
        if self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError(f"evidence_status={self.evidence_status!r} no es válido")
        if not (0 <= self.confidence_score <= 100):
            raise ValueError(f"confidence_score={self.confidence_score} debe estar entre 0 y 100")


# Firmas de cabecera ya confirmadas con datos reales en este proyecto.
FIELD_MAPPING_HEADER_HINTS = {"campoorigen", "field destiny xml", "adaptación", "adaptacion"}
RULE_SHEET_HEADER_HINTS = {"datoorigen", "datodestino", "reglaespecial"}
KNOWN_ERROR_HEADER_HINTS = {"id", "module", "description", "responsible"}

# Alias de regla ya catalogados en config/validation_rules.yaml -- si el
# NOMBRE de hoja coincide, hay buena confianza de qué tipo de regla es sin
# necesidad de leer su contenido.
KNOWN_TRANSFORMATION_RULE_ALIASES = {
    "nullcontrol", "nullcontrolexception", "concat", "barconcat", "titlefix",
    "ap_title_std_fix", "characterfix", "cloneorigin", "replaceinreference", "boolorigin",
}

CSV_PREVIEW_NAME_HINTS = ("csv_", "import csv", "xml_")
FUNCTIONAL_DECISION_NAME_HINTS = ("nota", "decision", "decisión", "criterio")


def classify_header_row(headers: list) -> tuple[str, int, list[str]]:
    """Clasifica según la cabecera (fila 0) de una hoja. Devuelve
    (category, confidence, evidence); category == "" si no hay señal."""
    normalized = {str(h).strip().lower() for h in headers if h is not None}
    if FIELD_MAPPING_HEADER_HINTS & normalized:
        matched = sorted(FIELD_MAPPING_HEADER_HINTS & normalized)
        return "field_mapping", 100, [f"cabecera contiene {matched}"]
    if RULE_SHEET_HEADER_HINTS & normalized:
        matched = sorted(RULE_SHEET_HEADER_HINTS & normalized)
        return "equivalence_table", 85, [f"cabecera contiene {matched}"]
    if KNOWN_ERROR_HEADER_HINTS <= normalized:
        return "known_errors", 90, [f"cabecera compatible con export de incidencias: {sorted(KNOWN_ERROR_HEADER_HINTS)}"]
    return "", 0, []


def classify_sheet_name(sheet_title: str) -> tuple[str, int, list[str]]:
    """Clasifica según el NOMBRE de la hoja -- confianza siempre menor que
    por cabecera/contenido, nunca 'confirmed' salvo el caso 'Index'."""
    title_lower = sheet_title.strip().lower()
    if title_lower == "index":
        return "index", 100, ["nombre de hoja == 'Index'"]
    if title_lower in KNOWN_TRANSFORMATION_RULE_ALIASES:
        return "transformation_rule", 90, [
            f"nombre de hoja coincide con alias ya catalogado en config/validation_rules.yaml: {title_lower!r}"
        ]
    if any(hint in title_lower for hint in CSV_PREVIEW_NAME_HINTS):
        return "csv_preview", 40, [f"nombre de hoja sugiere vista previa de CSV ({title_lower!r})"]
    if any(hint in title_lower for hint in FUNCTIONAL_DECISION_NAME_HINTS):
        return "functional_decisions", 40, [f"nombre de hoja sugiere notas/decisiones ({title_lower!r})"]
    return "", 0, []


def classify_reference_catalog_section(headers: list) -> tuple[bool, list[str]]:
    """Detecta si las columnas G/H (índices 6,7) de la cabecera son
    'XML'/'ES' -- el catálogo de referencia de Enablon confirmado en
    `src/etl/mapping_resolver.py` (no alineado por fila con A-E)."""
    if len(headers) > 7 and headers[6] is not None and headers[7] is not None:
        g = str(headers[6]).strip().lower()
        h = str(headers[7]).strip().lower()
        if g == "xml" and h == "es":
            return True, [
                "columnas G/H tituladas 'XML'/'ES' -- patrón de catálogo de "
                "referencia ya confirmado con datos reales (ver mapping_resolver.py)"
            ]
    return False, []


def classify_sheet(
    *,
    sheet_title: str,
    headers: list,
    max_row: int,
    source_file: str,
    contains_no_migrate_marker: bool = False,
) -> list[SheetClassification]:
    """Clasifica una hoja. Puede devolver más de una `SheetClassification`
    cuando hay secciones lógicas superpuestas (field_mapping +
    enablon_reference_catalog en la misma hoja).

    Orden de prioridad: cabecera reconocida > marcador 'No migra' en
    contenido > nombre de hoja > volumen (heurística "source_data" para
    hojas grandes sin ninguna señal anterior) > `pending_classification`.
    """
    def header_range(cols: str) -> str:
        return f"filas 1-{max_row}, cols {cols}"

    full_range = f"filas 1-{max_row}"
    detected_headers = [str(h) for h in headers if h is not None]

    header_category, header_confidence, header_evidence = classify_header_row(headers)
    if header_category:
        results = [
            SheetClassification(
                category=header_category,
                evidence_status="confirmed" if header_confidence >= 90 else "inferred",
                confidence_score=header_confidence,
                evidence=header_evidence,
                source_file=source_file,
                sheet=sheet_title,
                approximate_range=header_range("A-E") if header_category == "field_mapping" else full_range,
                headers_detected=detected_headers,
            )
        ]
        has_catalog, catalog_evidence = classify_reference_catalog_section(headers)
        if has_catalog:
            results.append(
                SheetClassification(
                    category="enablon_reference_catalog",
                    evidence_status="confirmed",
                    confidence_score=90,
                    evidence=catalog_evidence,
                    source_file=source_file,
                    sheet=sheet_title,
                    approximate_range=header_range("G-H"),
                    headers_detected=detected_headers,
                )
            )
        return results

    if contains_no_migrate_marker:
        return [
            SheetClassification(
                category="exclusions_no_migrate",
                evidence_status="inferred",
                confidence_score=60,
                evidence=["se detectó el valor literal 'No migra' en el contenido de la hoja"],
                source_file=source_file,
                sheet=sheet_title,
                approximate_range=full_range,
                headers_detected=detected_headers,
                warnings=["confirmar manualmente el alcance exacto antes de tratar la exclusión como definitiva"],
            )
        ]

    name_category, name_confidence, name_evidence = classify_sheet_name(sheet_title)
    if name_category:
        return [
            SheetClassification(
                category=name_category,
                evidence_status="confirmed" if name_category == "index" else "inferred",
                confidence_score=name_confidence,
                evidence=name_evidence,
                source_file=source_file,
                sheet=sheet_title,
                approximate_range=full_range,
                headers_detected=detected_headers,
            )
        ]

    if max_row > 200:
        return [
            SheetClassification(
                category="source_data",
                evidence_status="inferred",
                confidence_score=70,
                evidence=[f"{max_row} filas, sin cabecera de mapeo/regla reconocida -- probable extracto de datos origen"],
                source_file=source_file,
                sheet=sheet_title,
                approximate_range=full_range,
                headers_detected=detected_headers,
            )
        ]

    return [
        SheetClassification(
            category="pending_classification",
            evidence_status="pending",
            confidence_score=0,
            evidence=[],
            source_file=source_file,
            sheet=sheet_title,
            approximate_range=full_range,
            headers_detected=detected_headers,
            warnings=["sin señal suficiente para clasificar -- no se fuerza a ninguna categoría sustantiva"],
        )
    ]
