"""Catálogo cerrado de campos filtrables por objeto.

Ningún consumidor (CLI, extractor, tests) puede filtrar por una columna que
no esté declarada aquí -- `ObjectFilterCatalog.get_field` rechaza
explícitamente cualquier nombre desconocido, sin fallback a una columna
"libre" aportada por el usuario (requisito de seguridad #3/#4 del
incremento Query Engine v0.1).

Catálogo de Drills aprobado -- ver el informe de diseño previo
(`sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql`, sin
`WHERE`, columnas confirmadas por tipo en
`outputs/inventory/prevencion/20260721_130608/columns.csv`). Los seis
campos son *columnas passthrough* del `SELECT` (el alias es idéntico a la
columna base, sin `FORMAT()` ni ninguna otra transformación) -- por eso son
seguras de filtrar directamente contra `sql_source_expression` sin el
riesgo de fecha-como-texto documentado para `Fecha`/`FechaCreacion`.

`typology_id`, `letter_id` y `workflow_status_source` filtran por el valor
de ORIGEN (`IDTipo`, `IDLetra`, `Estado` tal cual están en
`ITP_SIMULACRO`), nunca por el valor de destino Enablon (`CS_Typology`,
`CS_Letter`, `CS_WorkflowStatus`) -- de ahí el sufijo explícito en el
nombre. Invertir los lookups muchos-a-uno (`typology_lookup`,
`letter_lookup`, `workflow_status_lookup` de
`config/exports/drills.yaml`) queda fuera de alcance de v0.1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.query.models import UnknownFilterFieldError

DATA_TYPE_INTEGER = "integer"
DATA_TYPE_STRING = "string"

_VALID_DATA_TYPES = (DATA_TYPE_INTEGER, DATA_TYPE_STRING)


@dataclass(frozen=True)
class FilterDefinition:
    """Una entrada del catálogo: un campo funcional filtrable, con su
    expresión SQL de columna base y los operadores que admite.

    `sql_source_expression` es texto de confianza fijado por quien
    mantiene el catálogo (nunca construido a partir de una entrada de
    usuario) -- es la única fuente de nombres de columna que el compositor
    SQL usa para construir un `WHERE` (ver `sql_builder.py`).
    """

    field_name: str
    sql_source_expression: str
    data_type: str
    allowed_operators: tuple[str, ...]
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.field_name or not self.field_name.strip():
            raise ValueError("FilterDefinition.field_name no puede estar vacío.")
        if not self.sql_source_expression or not self.sql_source_expression.strip():
            raise ValueError(
                f"FilterDefinition({self.field_name!r}).sql_source_expression no puede estar vacío."
            )
        if self.data_type not in _VALID_DATA_TYPES:
            raise ValueError(
                f"FilterDefinition({self.field_name!r}).data_type debe ser uno de "
                f"{_VALID_DATA_TYPES}, se recibió {self.data_type!r}."
            )
        if not self.allowed_operators:
            raise ValueError(
                f"FilterDefinition({self.field_name!r}).allowed_operators no puede estar vacío."
            )


@dataclass(frozen=True)
class ObjectFilterCatalog:
    """Catálogo cerrado de campos filtrables para un `object_id` concreto
    (p. ej. `"drills"`). No admite ampliarse en tiempo de ejecución ni
    resolver un campo fuera de `fields` -- ese es precisamente el control
    de seguridad #4 del incremento."""

    object_id: str
    fields: Mapping[str, FilterDefinition]

    def get_field(self, field_name: str) -> FilterDefinition:
        """Resuelve `field_name` contra el catálogo cerrado.

        Lanza `UnknownFilterFieldError` si no existe -- nunca hay un
        fallback a una columna libre, ni siquiera validada por regex."""
        try:
            return self.fields[field_name]
        except KeyError:
            allowed = ", ".join(sorted(self.fields))
            raise UnknownFilterFieldError(
                f"Campo de filtro desconocido para el objeto '{self.object_id}': "
                f"{field_name!r}. Campos permitidos: {allowed}."
            ) from None


DRILLS_FILTER_CATALOG = ObjectFilterCatalog(
    object_id="drills",
    fields={
        "historical_origin_id": FilterDefinition(
            field_name="historical_origin_id",
            sql_source_expression="[ITP_SIMULACRO].[IDSimulacro]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Identificador histórico de origen del simulacro (IDSimulacro).",
        ),
        "center_id": FilterDefinition(
            field_name="center_id",
            sql_source_expression="[ITP_SIMULACRO].[IDCentro]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description=(
                "IDCentro tal cual está en el sistema ITP/Prevención "
                "(idcentro_map_itp) -- nunca cruzar contra idcentro_map_gct."
            ),
        ),
        "origin_org_unit_id": FilterDefinition(
            field_name="origin_org_unit_id",
            sql_source_expression="[ITP_SIMULACRO].[IDUnidadOrg]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Unidad organizativa de origen (IDUnidadOrg) -- clave de entrada al catálogo de entidad, no la entidad Enablon ya resuelta.",
        ),
        "typology_id": FilterDefinition(
            field_name="typology_id",
            sql_source_expression="[ITP_SIMULACRO].[IDTipo]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Valor de ORIGEN de tipología (IDTipo) -- no el valor Enablon CS_Typology ya traducido.",
        ),
        "letter_id": FilterDefinition(
            field_name="letter_id",
            sql_source_expression="[ITP_SIMULACRO].[IDLetra]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Valor de ORIGEN de letra (IDLetra) -- no el valor Enablon CS_Letter ya traducido.",
        ),
        "workflow_status_source": FilterDefinition(
            field_name="workflow_status_source",
            sql_source_expression="[ITP_SIMULACRO].[Estado]",
            data_type=DATA_TYPE_STRING,
            allowed_operators=("eq", "in"),
            description="Valor de ORIGEN del estado (Estado, texto) -- no el valor Enablon CS_WorkflowStatus ya traducido.",
        ),
    },
)


# Catálogo de Bypass (Sprint 9.4, segundo módulo real) -- mismo mecanismo
# genérico que DRILLS_FILTER_CATALOG (ObjectFilterCatalog/FilterDefinition,
# REUSED_AS_IS), datos propios de Bypass. Columnas confirmadas por tipo
# en `sql/source_queries/bypass/SQLQuery-dataset_BES.sql` (sin JOINs
# necesarios para estos cuatro campos -- todos vienen directos de
# `ITP_BES`, ver docs/07-developer-guide/bypass-module.md § 2).
BYPASS_FILTER_CATALOG = ObjectFilterCatalog(
    object_id="bypass",
    fields={
        "historical_origin_id": FilterDefinition(
            field_name="historical_origin_id",
            sql_source_expression="[ITP_BES].[IDBES]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Identificador histórico de origen del bypass (IDBES).",
        ),
        "center_id": FilterDefinition(
            field_name="center_id",
            sql_source_expression="[ITP_BES].[IDCentro]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description=(
                "IDCentro tal cual está en el sistema ITP/Prevención "
                "(idcentro_map_itp) -- nunca cruzar contra idcentro_map_gct."
            ),
        ),
        "origin_org_unit_id": FilterDefinition(
            field_name="origin_org_unit_id",
            sql_source_expression="[ITP_BES].[IDUnidadOrg]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description=(
                "Unidad organizativa de origen (IDUnidadOrg) -- clave de entrada al "
                "catálogo de entidad First_Axis vigente; a diferencia de Drills, este "
                "repositorio NO tiene hoy un artefacto local IDUnidadOrg->Code para "
                "ese catálogo (ver excluded_columns de config/exports/bypass.yaml), "
                "así que este filtro no puede acotarse todavía a una entidad conocida."
            ),
        ),
        "bypass_type_id": FilterDefinition(
            field_name="bypass_type_id",
            sql_source_expression="[ITP_BES].[IDTipoBypass]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Valor de ORIGEN de categoría de bypass (IDTipoBypass) -- no el valor Enablon ByPassType ya traducido.",
        ),
    },
)


# Catálogo de Safety Meetings / Group_Meetings (Sprint 9.7, tercer módulo
# real) -- mismo mecanismo genérico que DRILLS_FILTER_CATALOG/
# BYPASS_FILTER_CATALOG (REUSED_AS_IS), datos propios de Safety Meetings.
# Columnas confirmadas leyendo `sql/source_queries/SM/SM2025.sql` (query
# única, sin JOIN -- todos los campos vienen directos de
# `ITP_REUNION_GRUPO`, ver docs/07-developer-guide/safety-meetings-module.md § 2).
SAFETY_MEETINGS_FILTER_CATALOG = ObjectFilterCatalog(
    object_id="safety_meetings",
    fields={
        "historical_origin_id": FilterDefinition(
            field_name="historical_origin_id",
            sql_source_expression="[ITP_REUNION_GRUPO].[IDReunionGrupo]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Identificador histórico de origen de la reunión de grupo (IDReunionGrupo).",
        ),
        "center_id": FilterDefinition(
            field_name="center_id",
            sql_source_expression="[ITP_REUNION_GRUPO].[IDCentro]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description=(
                "IDCentro tal cual está en el sistema ITP/Prevención "
                "(idcentro_map_itp) -- nunca cruzar contra idcentro_map_gct."
            ),
        ),
        "origin_org_unit_id": FilterDefinition(
            field_name="origin_org_unit_id",
            sql_source_expression="[ITP_REUNION_GRUPO].[IDUnidadOrg]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description=(
                "Unidad organizativa de origen (IDUnidadOrg) -- clave de entrada al "
                "catálogo de entidad First_Axis vigente; igual que en Bypass, este "
                "repositorio NO tiene hoy un artefacto local IDUnidadOrg->Code/Ruta1 "
                "para ese catálogo (ver excluded_columns de config/exports/safety_meetings.yaml), "
                "así que este filtro no puede acotarse todavía a una entidad conocida."
            ),
        ),
        "workflow_phase_id": FilterDefinition(
            field_name="workflow_phase_id",
            sql_source_expression="[ITP_REUNION_GRUPO].[FaseActual]",
            data_type=DATA_TYPE_INTEGER,
            allowed_operators=("eq", "in"),
            description="Valor de ORIGEN de fase de flujo (FaseActual) -- no el valor Enablon CS_WorkflowStatus ya traducido.",
        ),
    },
)
