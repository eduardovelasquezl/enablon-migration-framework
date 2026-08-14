"""Carga tipada de `config/exports/bypass.yaml`.

`FieldSpec`/`SourceSpec`/`OutputSpec` se REUTILIZAN tal cual desde
`src.export.prototype.drills.config` -- son dataclasses genéricas, sin
ningún campo ni lógica específica de Drills (verificable por
inspección: ninguna referencia a Drills en su definición). Solo
`BypassExportConfig` (el contenedor de nivel superior) y el loader son
nuevos, porque el nombre del fichero YAML y la clase contenedora son,
correctamente, específicos de este módulo -- mismo criterio que ya
separa `DrillsExportConfig` de sus piezas internas reutilizables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import load_yaml
from src.export.prototype.drills.config import FieldSpec, OutputSpec, SourceSpec

BYPASS_CONFIG_FILE = "config/exports/bypass.yaml"


@dataclass(frozen=True)
class BypassExportConfig:
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


def load_bypass_config() -> BypassExportConfig:
    """Lee y valida estructuralmente `config/exports/bypass.yaml`.

    No abre ningún Excel ni SQL Server -- solo el propio YAML
    declarativo (mismo contrato que `load_drills_config`)."""
    raw = load_yaml(BYPASS_CONFIG_FILE)

    missing_top = {
        "object_id", "module", "migration_object", "prototype_status",
        "source", "output", "invalid_row_policy", "reference_data", "fields",
    } - set(raw.keys())
    if missing_top:
        raise ValueError(
            f"{BYPASS_CONFIG_FILE} no declara las claves obligatorias: "
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
            f"El SQL declarado en {BYPASS_CONFIG_FILE} no existe: {source.sql_path}"
        )

    return BypassExportConfig(
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
