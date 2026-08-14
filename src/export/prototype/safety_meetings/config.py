"""Carga tipada de `config/exports/safety_meetings.yaml`.

`FieldSpec`/`OutputSpec`/`SourceSpec`/`load_export_config` vienen de
`src.export.engine.config` (Sprint 9.6) -- este fichero solo declara
`SafetyMeetingsExportConfig` (el contenedor específico de este módulo) y
`load_safety_meetings_config()`, que delega en `load_export_config`. Mismo
patrón exacto que `drills.config`/`bypass.config` tras Sprint 9.6 -- REUSED_ENGINE,
sin ninguna lógica propia más allá del nombre del fichero YAML y la clase
contenedora."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.export.engine.config import FieldSpec, OutputSpec, SourceSpec, load_export_config

SAFETY_MEETINGS_CONFIG_FILE = "config/exports/safety_meetings.yaml"

__all__ = [
    "FieldSpec", "OutputSpec", "SourceSpec", "SafetyMeetingsExportConfig",
    "SAFETY_MEETINGS_CONFIG_FILE", "load_safety_meetings_config",
]


@dataclass(frozen=True)
class SafetyMeetingsExportConfig:
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


def load_safety_meetings_config() -> SafetyMeetingsExportConfig:
    """Lee y valida estructuralmente `config/exports/safety_meetings.yaml`.

    No abre ningún Excel ni SQL Server -- solo el propio YAML declarativo
    (mismo contrato que `load_drills_config`/`load_bypass_config`)."""
    return load_export_config(SAFETY_MEETINGS_CONFIG_FILE, SafetyMeetingsExportConfig)
