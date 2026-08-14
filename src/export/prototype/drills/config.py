"""Carga tipada de `config/exports/drills.yaml`.

`FieldSpec`/`OutputSpec`/`SourceSpec` y el propio bucle de carga/validación
viven en `src.export.engine.config` desde Sprint 9.6 (Export Engine mínimo,
ver `reports/executions/2026-08-14/Informe-Minimal-Export-Engine-Extraction-EMF.md`)
-- este fichero solo declara `DrillsExportConfig` (el contenedor específico
de Drills, mismo campo a campo que antes) y `load_drills_config()`, que
delega en `load_export_config`. Comportamiento IDÉNTICO al de antes de este
refactor (mismas excepciones, mismos mensajes).

No reinterpreta el significado de negocio de cada campo -- solo expone la
definición declarativa ya escrita en el YAML (mismo principio que
`src.config.settings`). La interpretación (cómo se construye `Reference`,
cómo se resuelve la entidad...) vive en `transformations.py` / `mappings.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.export.engine.config import FieldSpec, OutputSpec, SourceSpec, load_export_config

DRILLS_CONFIG_FILE = "config/exports/drills.yaml"

__all__ = [
    "FieldSpec", "OutputSpec", "SourceSpec", "DrillsExportConfig",
    "DRILLS_CONFIG_FILE", "load_drills_config",
]


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
    return load_export_config(DRILLS_CONFIG_FILE, DrillsExportConfig)
