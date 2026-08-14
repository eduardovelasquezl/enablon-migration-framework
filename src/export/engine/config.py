"""Carga tipada de un YAML de exportación (`config/exports/<módulo>.yaml`).

`FieldSpec`/`OutputSpec`/`SourceSpec` (movidas aquí sin cambios desde
`drills/config.py`, Sprint 9.6) ya eran, desde Sprint 9.4, dataclasses sin
ningún campo ni lógica específica de Drills -- Bypass ya las importaba tal
cual. `load_export_config` extrae el cuerpo de `load_drills_config`/
`load_bypass_config` que era carácter-a-carácter idéntico salvo el nombre
del fichero YAML y la clase contenedora -- confirmado leyendo ambos antes de
mover una sola línea (Sprint 9.5.1 § Fase 2).

No reinterpreta el significado de negocio de ningún campo -- solo expone la
definición declarativa ya escrita en el YAML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from src.config import PROJECT_ROOT, load_yaml

REQUIRED_TOP_LEVEL_KEYS = frozenset({
    "object_id", "module", "migration_object", "prototype_status",
    "source", "output", "invalid_row_policy", "reference_data", "fields",
})


@dataclass(frozen=True)
class FieldSpec:
    source: Any  # str | list[str] | None
    target: str
    required: bool
    transformation: str
    data_type: str
    date_format: str | None
    default: Any
    mapping: str | None
    validation: str
    evidence_id: str


@dataclass(frozen=True)
class OutputSpec:
    filename: str
    encoding: str
    bom: bool
    delimiter: str
    quoting: str
    line_terminator: str
    include_header: bool


@dataclass(frozen=True)
class SourceSpec:
    connection: str
    sql_file: str
    max_rows: int

    @property
    def sql_path(self) -> Path:
        return PROJECT_ROOT / self.sql_file


T = TypeVar("T")


def load_export_config(config_file: str, container_cls: type[T]) -> T:
    """Lee y valida estructuralmente un YAML de exportación, y construye
    `container_cls(...)` con él -- `container_cls` debe ser un dataclass
    con exactamente los campos `object_id/module/migration_object/
    prototype_status/source/output/invalid_row_policy/reference_data/
    fields/excluded_columns/raw` (mismo contrato que `DrillsExportConfig`/
    `BypassExportConfig`, sin cambios de forma en este refactor).

    No abre ningún Excel ni SQL Server -- solo el propio YAML declarativo.
    Comportamiento IDÉNTICO al de `load_drills_config`/`load_bypass_config`
    antes de Sprint 9.6 (refactor behavior-preserving) -- mismas
    excepciones, mismos mensajes, mismo orden de validación.
    """
    raw = load_yaml(config_file)

    missing_top = REQUIRED_TOP_LEVEL_KEYS - set(raw.keys())
    if missing_top:
        raise ValueError(
            f"{config_file} no declara las claves obligatorias: {sorted(missing_top)}"
        )

    source = SourceSpec(
        connection=raw["source"]["connection"],
        sql_file=raw["source"]["sql_file"],
        max_rows=int(raw["source"]["max_rows"]),
    )
    output = OutputSpec(
        filename=raw["output"]["filename"],
        encoding=raw["output"]["encoding"],
        bom=bool(raw["output"]["bom"]),
        delimiter=raw["output"]["delimiter"],
        quoting=raw["output"]["quoting"],
        line_terminator=raw["output"]["line_terminator"],
        include_header=bool(raw["output"]["include_header"]),
    )

    fields = tuple(
        FieldSpec(
            source=f["source"],
            target=f["target"],
            required=bool(f["required"]),
            transformation=f["transformation"],
            data_type=f["data_type"],
            date_format=f.get("date_format"),
            default=f.get("default"),
            mapping=f.get("mapping"),
            validation=f["validation"],
            evidence_id=f["evidence_id"],
        )
        for f in raw["fields"]
    )

    excluded = tuple(dict(e) for e in raw.get("excluded_columns", []))

    if not source.sql_path.is_file():
        raise FileNotFoundError(
            f"El SQL declarado en {config_file} no existe: {source.sql_path}"
        )

    return container_cls(
        object_id=raw["object_id"],
        module=raw["module"],
        migration_object=raw["migration_object"],
        prototype_status=raw["prototype_status"],
        source=source,
        output=output,
        invalid_row_policy=raw["invalid_row_policy"],
        reference_data=dict(raw["reference_data"]),
        fields=fields,
        excluded_columns=excluded,
        raw=dict(raw),
    )
