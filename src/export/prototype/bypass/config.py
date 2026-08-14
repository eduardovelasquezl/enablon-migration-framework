"""Carga tipada de `config/exports/bypass.yaml`.

`FieldSpec`/`OutputSpec`/`SourceSpec` y el bucle de carga/validación viven en
`src.export.engine.config` desde Sprint 9.6 (antes se importaban/duplicaban
desde `drills.config` -- ver Sprint 9.4/9.5.1 para el historial). Este
fichero solo declara `BypassExportConfig` (el contenedor específico de
Bypass) y `load_bypass_config()`, que delega en `load_export_config`.
Comportamiento IDÉNTICO al de antes de este refactor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.export.engine.config import FieldSpec, OutputSpec, SourceSpec, load_export_config

BYPASS_CONFIG_FILE = "config/exports/bypass.yaml"

__all__ = [
    "FieldSpec", "OutputSpec", "SourceSpec", "BypassExportConfig",
    "BYPASS_CONFIG_FILE", "load_bypass_config",
]


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
    return load_export_config(BYPASS_CONFIG_FILE, BypassExportConfig)
