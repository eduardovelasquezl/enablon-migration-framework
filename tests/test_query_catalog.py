"""Tests unitarios del catálogo cerrado de filtros del Query Engine v0.1
(sin red). Ejecutar con: pytest tests/test_query_catalog.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.query.catalog import (
    DATA_TYPE_INTEGER,
    DATA_TYPE_STRING,
    DRILLS_FILTER_CATALOG,
    FilterDefinition,
    ObjectFilterCatalog,
)
from src.query.models import UnknownFilterFieldError

APPROVED_DRILLS_FIELDS = {
    "historical_origin_id",
    "center_id",
    "origin_org_unit_id",
    "typology_id",
    "letter_id",
    "workflow_status_source",
}


# --------------------------------------------------------------------------
# Catálogo cerrado -- comportamiento genérico
# --------------------------------------------------------------------------

def test_catalogo_cerrado_resuelve_campo_conocido():
    catalog = ObjectFilterCatalog(
        object_id="drills",
        fields={
            "center_id": FilterDefinition(
                field_name="center_id",
                sql_source_expression="[ITP_SIMULACRO].[IDCentro]",
                data_type=DATA_TYPE_INTEGER,
                allowed_operators=("eq", "in"),
            )
        },
    )
    field_def = catalog.get_field("center_id")
    assert field_def.field_name == "center_id"
    assert field_def.sql_source_expression == "[ITP_SIMULACRO].[IDCentro]"


def test_catalogo_cerrado_rechaza_campo_desconocido_sin_fallback():
    catalog = ObjectFilterCatalog(object_id="drills", fields={})
    with pytest.raises(UnknownFilterFieldError, match="desconocido"):
        catalog.get_field("cualquier_columna_libre")


def test_catalogo_cerrado_no_acepta_columna_sql_directa_como_campo():
    """El catálogo nunca debe aceptar un nombre que sea directamente una
    columna/expresión SQL en vez de un nombre funcional -- confirma que no
    hay ningún mecanismo de fallback que trate un campo desconocido como
    una columna literal."""
    catalog = ObjectFilterCatalog(
        object_id="drills",
        fields={
            "center_id": FilterDefinition(
                field_name="center_id",
                sql_source_expression="[ITP_SIMULACRO].[IDCentro]",
                data_type=DATA_TYPE_INTEGER,
                allowed_operators=("eq",),
            )
        },
    )
    with pytest.raises(UnknownFilterFieldError):
        catalog.get_field("[ITP_SIMULACRO].[IDCentro]")


def test_filter_definition_rechaza_data_type_no_soportado():
    with pytest.raises(ValueError):
        FilterDefinition(
            field_name="x", sql_source_expression="[T].[X]",
            data_type="date", allowed_operators=("eq",),
        )


def test_filter_definition_rechaza_sin_operadores():
    with pytest.raises(ValueError):
        FilterDefinition(
            field_name="x", sql_source_expression="[T].[X]",
            data_type=DATA_TYPE_INTEGER, allowed_operators=(),
        )


# --------------------------------------------------------------------------
# Catálogo aprobado de Drills -- contenido exacto
# --------------------------------------------------------------------------

def test_catalogo_drills_contiene_exactamente_los_seis_campos_aprobados():
    assert set(DRILLS_FILTER_CATALOG.fields) == APPROVED_DRILLS_FIELDS


def test_catalogo_drills_object_id():
    assert DRILLS_FILTER_CATALOG.object_id == "drills"


@pytest.mark.parametrize(
    "field_name,expected_expression,expected_type",
    [
        ("historical_origin_id", "[ITP_SIMULACRO].[IDSimulacro]", DATA_TYPE_INTEGER),
        ("center_id", "[ITP_SIMULACRO].[IDCentro]", DATA_TYPE_INTEGER),
        ("origin_org_unit_id", "[ITP_SIMULACRO].[IDUnidadOrg]", DATA_TYPE_INTEGER),
        ("typology_id", "[ITP_SIMULACRO].[IDTipo]", DATA_TYPE_INTEGER),
        ("letter_id", "[ITP_SIMULACRO].[IDLetra]", DATA_TYPE_INTEGER),
        ("workflow_status_source", "[ITP_SIMULACRO].[Estado]", DATA_TYPE_STRING),
    ],
)
def test_catalogo_drills_expresion_sql_y_tipo_confirmados(field_name, expected_expression, expected_type):
    field_def = DRILLS_FILTER_CATALOG.get_field(field_name)
    assert field_def.sql_source_expression == expected_expression
    assert field_def.data_type == expected_type


def test_catalogo_drills_todos_los_campos_admiten_solo_eq_e_in():
    for field_def in DRILLS_FILTER_CATALOG.fields.values():
        assert set(field_def.allowed_operators) == {"eq", "in"}


def test_catalogo_drills_no_usa_nombres_ambiguos_de_valor_destino():
    """Los nombres deben dejar explícito que filtran por valor de ORIGEN --
    'typology', 'letter', 'workflow_status', 'entity', 'date' y 'reference'
    a secas están explícitamente prohibidos por el incremento aprobado."""
    ambiguous_names = {"typology", "letter", "workflow_status", "entity", "date", "reference"}
    assert not (set(DRILLS_FILTER_CATALOG.fields) & ambiguous_names)


def test_catalogo_drills_rechaza_campos_fuera_de_alcance():
    for out_of_scope in ("date", "reference", "entity", "impacted_entity", "typology", "letter"):
        with pytest.raises(UnknownFilterFieldError):
            DRILLS_FILTER_CATALOG.get_field(out_of_scope)
