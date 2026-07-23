"""Carga tipada de `config/exports/drills.yaml`.

No reinterpreta el significado de negocio de cada campo -- solo expone la
definición declarativa ya escrita en el YAML (mismo principio que
`src.config.settings`). La interpretación (cómo se construye `Reference`,
cómo se resuelve la entidad...) vive en `transformations.py` / `mappings.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT, load_yaml

DRILLS_CONFIG_FILE = "config/exports/drills.yaml"


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


@dataclass(frozen=True)
class DrillsExportConfig:
    object_id: str
    module: str
    migration_object: str
    prototype_status: str
    source: SourceSpec
    output: OutputSpec
    invalid_row_policy: str
    reference_data: dict[str, Any]
    fields: tuple[FieldSpec, ...]
    excluded_columns: tuple[dict[str, Any], ...]
    raw: dict[str, Any] = field(repr=False)


def load_drills_config() -> DrillsExportConfig:
    """Lee y valida estructuralmente `config/exports/drills.yaml`.

    No abre ningún Excel ni SQL Server -- solo el propio YAML declarativo.
    """
    raw = load_yaml(DRILLS_CONFIG_FILE)

    missing_top = {
        "object_id", "module", "migration_object", "prototype_status",
        "source", "output", "invalid_row_policy", "reference_data", "fields",
    } - set(raw.keys())
    if missing_top:
        raise ValueError(
            f"{DRILLS_CONFIG_FILE} no declara las claves obligatorias: "
            f"{sorted(missing_top)}"
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
            f"El SQL declarado en {DRILLS_CONFIG_FILE} no existe: {source.sql_path}"
        )

    return DrillsExportConfig(
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
