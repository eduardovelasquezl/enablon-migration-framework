"""Escritura del CSV de Drills.

`write_csv` movida a `src.export.engine.writer` en Sprint 9.8 -- Bypass y
Safety Meetings ya la importaban directamente de aquí sin copiarla (cero
lógica de Drills). Se re-exporta con el mismo nombre para no tocar el
import ya existente en `drills/pipeline.py`
(`from .exporter import write_csv`) ni en
`tests/test_drills_export_prototype.py`
(`from src.export.prototype.drills.exporter import write_csv`).
"""
from __future__ import annotations

from src.export.engine.writer import write_csv

__all__ = ["write_csv"]
