"""Catálogo de categorías de incidencia para Drills (Fase 5 del incremento
de Evidence Engine).

Solo incluye categorías demostradas por la implementación real y sus
informes -- ninguna se ha añadido especulativamente. Cada categoría trae ya
resuelto qué explicación mostrar en cada audiencia (`description_internal`
vs `description_client`) y si debe aparecer en cada versión del Excel
(`include_in_internal` / `include_in_client`), para que `workbook.py` no
tenga que decidir nada de negocio -- solo renderizar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.config import PROJECT_ROOT

OPEN_QUESTIONS_DOC = "docs/specifications/v1.0/export/open_questions.md"

# Vocabulario de severidad -- ver Fase 10: "no depender únicamente del
# color; escribir siempre la severidad en texto". Las claves son las que
# usa el código (`pipeline.py`, este catálogo); los valores son el texto
# que ve cualquier persona, técnica o no.
SEVERITY_LABELS: dict[str, str] = {
    "info": "Información",
    "review_required": "Revisión requerida",
    "blocking_for_approval": "Bloqueante",
    "not_migrated_by_design": "No migra",
}

# Colores de relleno (ARGB) por severidad -- consistentes en todo el libro,
# tanto interno como cliente (Fase 10).
SEVERITY_COLORS: dict[str, str] = {
    "info": "FFDCE6F1",              # azul claro
    "review_required": "FFFFF2CC",   # amarillo claro
    "blocking_for_approval": "FFF8CBAD",  # rojo/naranja claro
    "not_migrated_by_design": "FFE2E2E2",  # gris claro
}


@dataclass(frozen=True)
class CategoryDefinition:
    code: str
    title: str
    short_title: str  # <=31 caracteres, para nombre de pestaña de Excel.
    description_internal: str
    description_client: str
    severity: str  # clave de SEVERITY_LABELS
    migration_impact: str
    responsible_party: str
    requested_action: str
    include_in_internal: bool
    include_in_client: bool


CATEGORY_CATALOG: dict[str, CategoryDefinition] = {
    "EXPORT_SUMMARY": CategoryDefinition(
        code="EXPORT_SUMMARY",
        title="Resumen de la ejecución",
        short_title="Resumen",
        description_internal="Resumen técnico de la ejecución del Prototype Export de Drills.",
        description_client="Resumen general de esta revisión de datos de Drills.",
        severity="info",
        migration_impact="No aplica -- es informativo.",
        responsible_party="Equipo de análisis",
        requested_action="Ninguna -- contexto de lectura.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "EXPORTED_ROWS": CategoryDefinition(
        code="EXPORTED_ROWS",
        title="Registros exportados",
        short_title="Exportados",
        description_internal="Registros incluidos en drills.csv en esta ejecución.",
        description_client="Registros incluidos en el archivo generado en esta revisión.",
        severity="info",
        migration_impact="No aplica -- son los registros ya incluidos correctamente.",
        responsible_party="Equipo de análisis",
        requested_action="Ninguna -- disponibles para revisión en el CSV generado.",
        include_in_internal=True,
        include_in_client=False,
    ),
    "EXCLUDED_ROWS": CategoryDefinition(
        code="EXCLUDED_ROWS",
        title="Registros excluidos",
        short_title="Excluidos",
        description_internal="Registros excluidos del CSV por fallo de validación de 'Reference'.",
        description_client=(
            "Registros que no se han incluido en el archivo generado porque falta "
            "información obligatoria para construir su referencia histórica."
        ),
        severity="review_required",
        migration_impact="No se incluyen en la carga hasta completar la información requerida.",
        responsible_party="Cliente + equipo de análisis",
        requested_action="Completar o confirmar los datos de origen ausentes.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "INVALID_REFERENCE": CategoryDefinition(
        code="INVALID_REFERENCE",
        title="Referencia histórica no construible",
        short_title="Ref_Invalida",
        description_internal=(
            "Filas donde build_reference() no pudo construir 'Reference' por "
            "ausencia de CS_Typology, CS_HistoricalOriginID o StartingDate."
        ),
        description_client=(
            "Registros para los que no ha sido posible construir la referencia "
            "histórica con todos los componentes obligatorios. Estos registros no "
            "se incluyen en el CSV hasta completar o corregir la información "
            "requerida."
        ),
        severity="review_required",
        migration_impact="Bloquea la inclusión del registro en el CSV hasta resolverse.",
        responsible_party="Cliente + equipo de análisis",
        requested_action="Revisar el/los componente(s) ausente(s) señalado(s) por fila.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "ENTITY_UNRESOLVED": CategoryDefinition(
        code="ENTITY_UNRESOLVED",
        title="Entidad no resuelta",
        short_title="Entidad_NoResuelta",
        description_internal="IDUnidadOrg sin coincidencia en el catálogo de entidad normalizado.",
        description_client=(
            "Registros cuya entidad de destino no ha podido resolverse con el "
            "mapping disponible. Es necesario revisar o completar la equivalencia "
            "antes de incorporarlos a la carga."
        ),
        severity="review_required",
        migration_impact="El campo de entidad queda vacío hasta confirmar la equivalencia.",
        responsible_party="Equipo de análisis + cliente",
        requested_action="Confirmar la equivalencia de entidad correcta para este origen.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "ENTITY_CONFLICTING": CategoryDefinition(
        code="ENTITY_CONFLICTING",
        title="Entidad con más de una correspondencia",
        short_title="Entidad_Conflicto",
        description_internal="IDUnidadOrg con más de un 'Code' distinto en el catálogo de entidad.",
        description_client=(
            "Registros para los que el mapping devuelve más de una entidad "
            "posible. Se requiere una decisión funcional para seleccionar la "
            "correspondencia correcta."
        ),
        severity="blocking_for_approval",
        migration_impact="No se elige automáticamente ninguna opción -- bloquea la aprobación.",
        responsible_party="Cliente",
        requested_action="Decidir cuál de las entidades candidatas es la correcta.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "ENTITY_EMPTY": CategoryDefinition(
        code="ENTITY_EMPTY",
        title="Entidad sin información de origen",
        short_title="Entidad_Vacia",
        description_internal="IDUnidadOrg ausente/nulo en el origen -- sin clave para resolver entidad.",
        description_client="Registros sin información suficiente de entidad en el origen.",
        severity="review_required",
        migration_impact="El campo de entidad queda vacío -- no se ha inventado un valor.",
        responsible_party="Cliente",
        requested_action="Confirmar si el origen debería tener esta información y completarla.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "ENTITY_DO_NOT_MIGRATE": CategoryDefinition(
        code="ENTITY_DO_NOT_MIGRATE",
        title="Entidad marcada 'No migra'",
        short_title="No_Migra",
        description_internal="IDUnidadOrg resuelve a una entidad marcada 'No migra' en el catálogo.",
        description_client=(
            "Registros asociados a valores que han sido clasificados expresamente "
            "como “No migra”. No se consideran un error técnico, pero quedan "
            "fuera de la carga conforme a las reglas acordadas."
        ),
        severity="not_migrated_by_design",
        migration_impact="Exclusión esperada y por diseño -- no requiere corrección.",
        responsible_party="No aplica (regla ya acordada)",
        requested_action="Ninguna, salvo que el cliente quiera reconfirmar la regla.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "INVALID_DATE": CategoryDefinition(
        code="INVALID_DATE",
        title="Fecha ausente o inválida",
        short_title="Fecha_Invalida",
        description_internal="StartingDate no interpretable (vacío o formato no soportado).",
        description_client="Registros con una fecha ausente o inválida para el formato requerido.",
        severity="review_required",
        migration_impact="Bloquea la construcción de 'Reference' para ese registro.",
        responsible_party="Cliente + equipo de análisis",
        requested_action="Confirmar o corregir la fecha de origen.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "DUPLICATE_REFERENCE": CategoryDefinition(
        code="DUPLICATE_REFERENCE",
        title="Referencia histórica duplicada",
        short_title="Ref_Duplicada",
        description_internal="Más de una fila incluida en el CSV comparte el mismo valor de Reference.",
        description_client=(
            "Registros que producen una referencia histórica duplicada y "
            "requieren revisión antes de la carga."
        ),
        severity="review_required",
        migration_impact="Riesgo de ambigüedad de identidad si se cargan ambos registros tal cual.",
        responsible_party="Equipo de análisis + cliente",
        requested_action="Confirmar si la duplicidad es esperada o requiere corrección.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "HISTORICAL_DIFFERENCES": CategoryDefinition(
        code="HISTORICAL_DIFFERENCES",
        title="Diferencias frente al histórico",
        short_title="Dif_Historico",
        description_internal=(
            "Resumen por columna de coincidencias/diferencias entre el CSV "
            "generado y el CSV histórico real usado como evidencia de comparación."
        ),
        description_client=(
            "Diferencias detectadas entre el resultado generado y el CSV histórico "
            "utilizado como evidencia de comparación. El histórico no se considera "
            "un template oficial de importación."
        ),
        severity="review_required",
        migration_impact="Ver detalle por columna -- no implica por sí solo un error.",
        responsible_party="Equipo de análisis + cliente",
        requested_action="Revisar las columnas con mayor proporción de diferencias.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "STARTING_DATE_TIME_GAP": CategoryDefinition(
        code="STARTING_DATE_TIME_GAP",
        title="StartingDate sin combinar con la hora de origen",
        short_title="Hallazgo_Fecha",
        description_internal=(
            "'Fecha' llega con la hora truncada a 00:00 en buena parte de los "
            "registros; la hora real vive en la columna separada 'Hora' "
            "(seleccionada por la SQL de origen pero no combinada). La propia "
            "consulta reserva una columna vacía 'FechaHoraCombinado' nunca "
            "implementada. No afecta a 'Reference' (usa solo la fecha)."
        ),
        description_client=(
            "La fecha y la hora se encuentran separadas en el origen. El "
            "prototipo actual conserva la fecha en StartingDate, pero no combina "
            "todavía la columna de hora. Esta situación no afecta a la "
            "construcción de Reference, pero debe validarse funcionalmente antes "
            "de ampliar el alcance."
        ),
        severity="review_required",
        migration_impact="StartingDate puede no reflejar la hora real del simulacro.",
        responsible_party="Equipo de análisis + cliente",
        requested_action="Confirmar la regla de combinación Fecha + Hora antes de ampliar el alcance.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "ENTITY_CATALOG_FIDELITY": CategoryDefinition(
        code="ENTITY_CATALOG_FIDELITY",
        title="Fidelidad del catálogo de entidad",
        short_title="Hallazgo_Entidad",
        description_internal=(
            "La entidad se resuelve mediante el catálogo histórico deprecado "
            "Entidades_Enablon_ITP (681 filas), aceptado para Simulacros. En parte "
            "de los registros comparables contra el histórico, el código obtenido "
            "corresponde a una entidad relacionada de la misma rama, no al valor "
            "histórico exacto -- ver comparison_report.yaml de esta ejecución."
        ),
        description_client=(
            "La entidad se resuelve mediante un catálogo histórico deprecado. En "
            "parte de los registros comparables, el código obtenido corresponde a "
            "una entidad relacionada de la misma rama, pero no coincide "
            "exactamente con el resultado histórico. Se requiere confirmar el "
            "mapping vigente."
        ),
        severity="blocking_for_approval",
        migration_impact="Riesgo de que la entidad cargada no sea la exacta esperada por el cliente.",
        responsible_party="Cliente + equipo de análisis",
        requested_action="Confirmar si el catálogo deprecado sigue siendo válido para Drills.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "OPEN_QUESTIONS": CategoryDefinition(
        code="OPEN_QUESTIONS",
        title="Preguntas abiertas",
        short_title="Preguntas_Abiertas",
        description_internal=(
            "Preguntas abiertas de docs/specifications/v1.0/export/open_questions.md "
            "aplicables a simulacros.Drills, sin cerrar en este incremento."
        ),
        description_client=(
            "Puntos pendientes de confirmación funcional antes de considerar "
            "Drills listo para una carga aprobada."
        ),
        severity="review_required",
        migration_impact="Cada pregunta abierta puede condicionar el alcance final del objeto.",
        responsible_party="Cliente + equipo de análisis",
        requested_action="Revisar y responder cada pregunta listada.",
        include_in_internal=True,
        include_in_client=True,
    ),
    "PROTOTYPE_LIMITATIONS": CategoryDefinition(
        code="PROTOTYPE_LIMITATIONS",
        title="Limitaciones del prototipo",
        short_title="Limitaciones",
        description_internal="Limitaciones conocidas y deliberadas del alcance de este incremento.",
        description_client="Limitaciones conocidas de esta versión de revisión.",
        severity="info",
        migration_impact="Ninguna todavía -- alcance reducido a propósito, no un defecto.",
        responsible_party="Equipo de análisis",
        requested_action="Ninguna -- contexto de alcance.",
        include_in_internal=True,
        include_in_client=True,
    ),
}

PROTOTYPE_LIMITATIONS_TEXT: tuple[str, ...] = (
    "8 de 36 columnas del objeto Drills implementadas -- ver excluded_columns en config/exports/drills.yaml.",
    "Codificación UTF-8 sin BOM -- decisión provisional, no confirmada por Enablon.",
    "El CSV generado NO está aprobado para importación (approved_for_enablon_import: false).",
    "Alcance limitado al objeto Drills -- ningún otro objeto de migración se procesa todavía.",
    "Sin filtros por centro (IDCentro) ni por entidad todavía -- se exporta la muestra/lote completo según el modo.",
)


def _parse_markdown_table_row(markdown_text: str, question_id: str) -> dict[str, str] | None:
    """Extrae, sin interpretarla, la fila de la tabla de
    `open_questions.md` correspondiente a `question_id`. Nunca genera texto
    -- si la fila no existe, devuelve `None` y quien llame decide cómo
    reportarlo (nunca inventar la descripción, ver Fase 5)."""
    pattern = re.compile(
        r"^\|\s*" + re.escape(question_id) + r"\s*\|(.+)\|\s*$", re.MULTILINE
    )
    match = pattern.search(markdown_text)
    if not match:
        return None
    cells = [c.strip() for c in match.group(1).split("|")]
    # Columnas de la tabla (ver open_questions.md): Prioridad | Objeto
    # relacionado | Evidencia faltante | Impacto | Responsable sugerido | Estado
    labels = ["priority", "related_object", "evidence_gap", "impact", "responsible", "status"]
    return dict(zip(labels, cells + [""] * (len(labels) - len(cells))))


def load_open_questions(question_ids: list[str], project_root: Path | None = None) -> dict[str, dict[str, str] | None]:
    """Carga, verbatim, las filas de `open_questions.md` para los IDs
    pedidos. Un valor `None` significa que el ID no se encontró en el
    documento -- se reporta como tal, nunca se sustituye por texto
    inventado."""
    root = project_root or PROJECT_ROOT
    doc_path = root / OPEN_QUESTIONS_DOC
    if not doc_path.is_file():
        return {qid: None for qid in question_ids}
    text = doc_path.read_text(encoding="utf-8")
    return {qid: _parse_markdown_table_row(text, qid) for qid in question_ids}
