"""Tests unitarios del resolver de mapeos (src/etl/mapping_resolver.py).
Ejecutar con: pytest tests/

Todos los Excel de prueba se generan dinámicamente en tmp_path -- ningún
fixture binario permanente."""
import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.excel_reader import read_field_mapping_sheet
from src.etl.mapping_resolver import (
    AMBIGUOUS,
    INVALID_ROW,
    MISSING_DESTINATION,
    RESOLVED_EXACT,
    UNRESOLVED,
    build_reference_catalog,
    normalize_label,
    resolve_field_mapping_sheet,
)

HEADER = ["CampoOrigen", "Field Destiny XML", "Field Destiny ES", "Adaptación", "Transformation From", None, "XML", "ES"]


def _make_workbook(tmp_path: Path, sheet_name: str, rows: list[list], filename: str = "etl_test.xlsx") -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    path = tmp_path / filename
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Lookup exacto ES -> XML
# ---------------------------------------------------------------------------

def test_lookup_exacto_es_a_xml(tmp_path):
    rows = [
        ["IDBES", None, "Historical Origin ID", "Si", "map_BES_Fix", None, "LevelNo", "Approval"],
        [None, None, None, None, None, None, "CS_HistoricalOriginID", "Historical Origin ID"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert len(resolved) == 1
    r = resolved[0]
    assert r.source_field == "IDBES"
    assert r.destination_label_es == "Historical Origin ID"
    assert r.destination_field_xml == "CS_HistoricalOriginID"
    assert r.resolution_status == RESOLVED_EXACT
    assert r.resolution_method == "exact_lookup_es_to_xml"
    assert r.adaptation is True
    assert r.transformation_rule == "map_BES_Fix"


# ---------------------------------------------------------------------------
# Destino no localizado
# ---------------------------------------------------------------------------

def test_destino_no_localizado_es_unresolved(tmp_path):
    rows = [
        ["IDAlgo", None, "Etiqueta Que No Existe En El Catalogo", "No", None, None, "Entity", "Entity"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert len(resolved) == 1
    assert resolved[0].resolution_status == UNRESOLVED
    assert resolved[0].destination_field_xml is None
    assert resolved[0].warnings


# ---------------------------------------------------------------------------
# Catálogo con etiquetas duplicadas -- nunca se elige una silenciosamente
# ---------------------------------------------------------------------------

def test_catalogo_con_etiqueta_duplicada_es_ambiguous(tmp_path):
    rows = [
        ["IDCampo", None, "Approval", "No", None, None, "LevelNo", "Approval"],
        [None, None, None, None, None, None, "CS_ApprovalStatus", "Approval"],  # misma ES, XML distinto
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert len(resolved) == 1
    r = resolved[0]
    assert r.resolution_status == AMBIGUOUS
    assert r.destination_field_xml is None
    assert "LevelNo" in r.warnings[0] and "CS_ApprovalStatus" in r.warnings[0]


def test_etiqueta_duplicada_con_mismo_xml_no_es_ambigua(tmp_path):
    rows = [
        ["IDCampo", None, "Entity", "No", None, None, "Entity", "Entity"],
        [None, None, None, None, None, None, "Entity", "Entity"],  # repetido, mismo XML -- inofensivo
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert resolved[0].resolution_status == RESOLVED_EXACT
    assert resolved[0].destination_field_xml == "Entity"


# ---------------------------------------------------------------------------
# Normalización de espacios segura -- nunca fusiona etiquetas realmente distintas
# ---------------------------------------------------------------------------

def test_normalizacion_de_espacios_resuelve_diferencia_accidental(tmp_path):
    rows = [
        ["IDCampo", None, "  Historical   Origin ID ", "No", None, None, "CS_HistoricalOriginID", "Historical Origin ID"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert resolved[0].resolution_status == RESOLVED_EXACT
    assert resolved[0].destination_field_xml == "CS_HistoricalOriginID"


def test_normalizacion_no_fusiona_etiquetas_realmente_distintas(tmp_path):
    rows = [
        ["IDCampo", None, "Historical Origin ID Extra", "No", None, None, "CS_HistoricalOriginID", "Historical Origin ID"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    # "Historical Origin ID Extra" no es igual a "Historical Origin ID" tras
    # normalizar solo espacios -- debe quedar sin resolver, no fusionado.
    assert resolved[0].resolution_status == UNRESOLVED


def test_normalize_label_no_toca_mayusculas():
    assert normalize_label("  Historical   Origin ID  ") == "Historical Origin ID"
    assert normalize_label("HISTORICAL ORIGIN ID") == "HISTORICAL ORIGIN ID"


# ---------------------------------------------------------------------------
# Fórmula en columna B sin valor cacheado -- se ignora por completo
# ---------------------------------------------------------------------------

def test_formula_en_columna_b_se_ignora_por_completo(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "MapeoTest"
    ws.append(HEADER)
    ws.append(["IDBES", "=_xlfn.XLOOKUP(C2,H:H,G:G,\" \",0,1)", "Historical Origin ID", "Si", "map_BES_Fix", None, "LevelNo", "Approval"])
    ws.append([None, None, None, None, None, None, "CS_HistoricalOriginID", "Historical Origin ID"])
    path = tmp_path / "etl_formula.xlsx"
    wb.save(path)

    # data_only=False (como en el resolver) -- la celda B2 devuelve el TEXTO
    # de la fórmula, nunca un valor calculado (openpyxl no ejecuta Excel).
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")
    assert resolved[0].resolution_status == RESOLVED_EXACT
    assert resolved[0].destination_field_xml == "CS_HistoricalOriginID"  # no "LevelNo" (columna G de esa fila)


# ---------------------------------------------------------------------------
# Múltiples hojas -- catálogos independientes, sin fuga entre ellas
# ---------------------------------------------------------------------------

def test_multiples_hojas_catalogos_independientes(tmp_path):
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "HojaA"
    ws1.append(HEADER)
    ws1.append(["Campo1", None, "Etiqueta Solo En A", "No", None, None, "DestinoA", "Etiqueta Solo En A"])

    ws2 = wb.create_sheet("HojaB")
    ws2.append(HEADER)
    ws2.append(["Campo2", None, "Etiqueta Solo En A", "No", None, None, "OTRO_DESTINO", "Otra Etiqueta"])
    # En HojaB, "Etiqueta Solo En A" NO está en el catálogo de HojaB.

    path = tmp_path / "etl_multi.xlsx"
    wb.save(path)

    resolved_a = resolve_field_mapping_sheet(path, "HojaA")
    resolved_b = resolve_field_mapping_sheet(path, "HojaB")

    assert resolved_a[0].resolution_status == RESOLVED_EXACT
    assert resolved_a[0].destination_field_xml == "DestinoA"
    # El catálogo de HojaA no debe filtrarse a HojaB.
    assert resolved_b[0].resolution_status == UNRESOLVED


# ---------------------------------------------------------------------------
# Filas vacías -- se saltan sin generar invalid_row espurio
# ---------------------------------------------------------------------------

def test_fila_totalmente_vacia_se_salta_sin_reportar(tmp_path):
    rows = [
        ["IDCampo", None, "Entity", "No", None, None, "Entity", "Entity"],
        [None, None, None, None, None, None, None, None],  # fila totalmente vacía
        ["IDOtro", None, "Entity", "No", None, None, None, None],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    # Solo 2 resultados (las dos filas con contenido), la vacía no aparece.
    assert len(resolved) == 2
    assert all(r.resolution_status != INVALID_ROW for r in resolved)


def test_fila_con_contenido_pero_sin_campo_origen_es_invalid_row(tmp_path):
    rows = [
        [None, None, "Alguna Etiqueta", "No", None, None, "Destino", "Alguna Etiqueta"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert len(resolved) == 1
    assert resolved[0].resolution_status == INVALID_ROW


def test_fila_solo_catalogo_sin_pareja_en_mapeo_no_es_invalid_row(tmp_path):
    # Caso real confirmado en MAP-AP: el catálogo de referencia (G/H) suele
    # tener más filas que la tabla de mapeo (73 entradas de catálogo frente a
    # 36 filas de mapeo) -- una fila con contenido SOLO en G/H no es una fila
    # de mapeo inválida, es una entrada de catálogo sin pareja en A-E.
    rows = [
        ["IDCampo", None, "Entity", "No", None, None, "Entity", "Entity"],
        [None, None, None, None, None, None, "CS_HistoricalOriginID", "Historical Origin ID"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert len(resolved) == 1  # la fila "solo catálogo" no se reporta
    assert resolved[0].resolution_status == RESOLVED_EXACT


def test_campo_origen_sin_etiqueta_destino_es_missing_destination(tmp_path):
    rows = [
        ["IDCampo", None, None, "No", None, None, None, None],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)
    resolved = resolve_field_mapping_sheet(path, "MapeoTest")

    assert resolved[0].resolution_status == MISSING_DESTINATION
    assert resolved[0].destination_field_xml is None


# ---------------------------------------------------------------------------
# build_reference_catalog -- unidad aislada
# ---------------------------------------------------------------------------

def test_build_reference_catalog_detecta_duplicados():
    rows = [
        (None, None, None, None, None, None, "X1", "Etiqueta"),
        (None, None, None, None, None, None, "X2", "Etiqueta"),
        (None, None, None, None, None, None, "X3", "Otra"),
    ]
    catalog = build_reference_catalog(rows)
    assert "Etiqueta" in catalog.duplicate_es_labels
    assert set(catalog.duplicate_es_labels["Etiqueta"]) == {"X1", "X2"}
    assert catalog.es_to_xml["Otra"] == "X3"


# ---------------------------------------------------------------------------
# Compatibilidad -- read_field_mapping_sheet() no cambia de comportamiento
# ---------------------------------------------------------------------------

def test_read_field_mapping_sheet_mantiene_su_comportamiento_previo(tmp_path):
    # Mismo fixture que test_lookup_exacto_es_a_xml: la función VIEJA sigue
    # leyendo row[6] posicionalmente (el defecto ya documentado), y debe
    # seguir haciéndolo -- esta prueba falla si alguien toca excel_reader.py
    # sin querer al implementar el resolver nuevo.
    rows = [
        ["IDBES", None, "Historical Origin ID", "Si", "map_BES_Fix", None, "LevelNo", "Approval"],
    ]
    path = _make_workbook(tmp_path, "MapeoTest", rows)

    old_result = read_field_mapping_sheet(str(path), "MapeoTest")
    assert len(old_result) == 1
    assert old_result[0].campo_origen == "IDBES"
    # Comportamiento histórico (defectuoso, sin tocar): lee columna G (índice
    # 6) de la MISMA fila, no el resultado de la búsqueda -- por eso da
    # "LevelNo" en vez de "CS_HistoricalOriginID".
    assert old_result[0].campo_destino_xml == "LevelNo"

    new_result = resolve_field_mapping_sheet(path, "MapeoTest")
    # El resolver nuevo, sobre el mismo fixture, no puede resolverlo porque
    # "Historical Origin ID" no está en las columnas G/H de este fixture
    # reducido (solo tiene una fila) -- confirma que ambas funciones son
    # independientes y una no delega en la otra.
    assert new_result[0].resolution_status == UNRESOLVED
