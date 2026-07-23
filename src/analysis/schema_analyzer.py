"""
Análisis estructural de un ETL Excel original (Función 1 del framework:
Análisis del ETL).

Replica en código lo que hicimos a mano para los 9 módulos: listar hojas,
detectar cuáles son hojas de mapeo (patrón de 5 u 8 columnas conocido),
detectar hojas "huérfanas" (patrón MAP-ITPOLD-* ya confirmado en 7 de 7
libros), y extraer las reglas usadas.

IMPORTANTE: usar siempre read_only=True al abrir libros grandes (varios
ETL de este proyecto superan los 200-300 MB) para no agotar memoria.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from src.analysis._sheet_taxonomy import SheetClassification, classify_sheet

logger = logging.getLogger(__name__)

# Firma de columnas de las hojas de mapeo de campo, tal como aparecen en
# TODOS los ETL auditados (Simulacros, SM, MOC, Bypass, Eventos, OPS,
# Inspecciones, AP).
FIELD_MAPPING_HEADER_HINTS = {"campoorigen", "field destiny xml", "adaptación", "adaptacion"}

# Firma de las hojas de regla pequeñas (DatoOrigen/DatoDestino/...).
RULE_SHEET_HEADER_HINTS = {"datoorigen", "datodestino", "reglaespecial"}

# Nombres de hoja que, en 7 de 7 libros auditados con checklists/eventos,
# resultaron ser copias sin uso de Eventos Antiguos. Si aparecen en un ETL
# de un módulo que NO sea Eventos, márcalas como huérfanas por defecto —
# pero confirma mirando si el Index las referencia antes de descartarlas.
KNOWN_ORPHAN_SHEETS = {
    "map-itpold-evt",
    "map-itpold-imp",
    "map-itpold-med",
    "map-itpold-med-2",
    "map_update_id-imp",
}


@dataclass
class SheetInfo:
    title: str
    max_row: int
    max_col: int
    kind: str  # "field_mapping" | "rule" | "index" | "data" | "unknown"
    is_known_orphan: bool = False


@dataclass
class EtlInventory:
    path: str
    sheets: list[SheetInfo] = field(default_factory=list)

    @property
    def field_mapping_sheets(self) -> list[SheetInfo]:
        return [s for s in self.sheets if s.kind == "field_mapping"]

    @property
    def rule_sheets(self) -> list[SheetInfo]:
        return [s for s in self.sheets if s.kind == "rule"]

    @property
    def orphan_candidates(self) -> list[SheetInfo]:
        return [s for s in self.sheets if s.is_known_orphan]


def _classify_sheet(ws, title_lower: str) -> str:
    if title_lower == "index":
        return "index"

    try:
        first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    except StopIteration:
        return "unknown"

    header_cells = {str(c).strip().lower() for c in first_row if c is not None}

    if FIELD_MAPPING_HEADER_HINTS & header_cells:
        return "field_mapping"
    if RULE_SHEET_HEADER_HINTS & header_cells:
        return "rule"
    if ws.max_row and ws.max_row > 200:
        return "data"
    return "unknown"


def inventory(path: str | Path) -> EtlInventory:
    """Inventaría un ETL Excel: hojas, tipo de cada una, y marca las que
    coinciden con el patrón de hoja huérfana ya confirmado en el proyecto.

    Usa read_only=True siempre — varios ETL de este proyecto pesan
    200-340 MB y un load_workbook normal puede agotar memoria.
    """
    path = Path(path)
    wb = load_workbook(path, read_only=True, data_only=False)
    sheets: list[SheetInfo] = []
    try:
        for ws in wb.worksheets:
            title_lower = ws.title.strip().lower()
            kind = _classify_sheet(ws, title_lower)
            sheets.append(
                SheetInfo(
                    title=ws.title,
                    max_row=ws.max_row or 0,
                    max_col=ws.max_column or 0,
                    kind=kind,
                    is_known_orphan=title_lower in KNOWN_ORPHAN_SHEETS,
                )
            )
    finally:
        wb.close()

    inv = EtlInventory(path=str(path), sheets=sheets)
    if inv.orphan_candidates:
        logger.warning(
            "%s: %d hoja(s) coinciden con el patrón de huérfana conocido (Eventos "
            "copiado sin limpiar): %s. Confirma si el Index las referencia antes "
            "de asumir que no se usan.",
            path.name, len(inv.orphan_candidates),
            [s.title for s in inv.orphan_candidates],
        )
    return inv


def classify_workbook_sections(
    path: str | Path, *, check_no_migrate_marker: bool = False
) -> dict[str, list[SheetClassification]]:
    """Clasifica cada hoja de un ETL Excel según la taxonomía ampliada de 18
    categorías (ver `_sheet_taxonomy.py`, privado -- no importar directamente
    fuera de este módulo). Puede devolver más de una clasificación por hoja
    cuando hay secciones lógicas superpuestas (ver `field_mapping` +
    `enablon_reference_catalog`, confirmado en `src/etl/mapping_resolver.py`).

    `check_no_migrate_marker=True` activa un barrido de todo el contenido de
    cada hoja para detectar el valor literal "No migra" -- más lento en
    libros grandes (varios de este proyecto superan 200-300 MB), por eso no
    está activo por defecto.
    """
    path = Path(path)
    wb = load_workbook(path, read_only=True, data_only=False)
    result: dict[str, list[SheetClassification]] = {}
    try:
        for ws in wb.worksheets:
            try:
                headers = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
            except StopIteration:
                headers = []

            contains_no_migrate = False
            if check_no_migrate_marker:
                for row in ws.iter_rows(values_only=True):
                    if any(isinstance(v, str) and "no migra" in v.lower() for v in row):
                        contains_no_migrate = True
                        break

            result[ws.title] = classify_sheet(
                sheet_title=ws.title,
                headers=headers,
                max_row=ws.max_row or 0,
                source_file=str(path),
                contains_no_migrate_marker=contains_no_migrate,
            )
    finally:
        wb.close()
    return result


def read_index_sheet(path: str | Path) -> list[tuple]:
    """Devuelve las filas no vacías de la hoja 'Index', que en todos los ETL
    del proyecto documenta los flujos SOURCES DATA -> MAPS -> FINAL DATA."""
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Index"]
        return [row for row in ws.iter_rows(values_only=True) if any(v is not None for v in row)]
    finally:
        wb.close()
