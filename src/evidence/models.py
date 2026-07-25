"""Modelos de datos del Evidence Engine -- ninguno ejecuta I/O por sí
mismo; `collector.py` los construye a partir de los artefactos ya escritos
por el pipeline de exportación."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class EvidenceSourceError(Exception):
    """Los artefactos de una ejecución no existen, no son de Drills, o no
    tienen la forma esperada -- se lanza ANTES de intentar construir ningún
    Excel, con un mensaje claro (nunca se rellena con datos inventados)."""


@dataclass(frozen=True)
class RunEvidenceContext:
    """Todo lo que `workbook.py` necesita para construir ambos Excel,
    reunido una sola vez por `collector.py`. Inmutable: ni `workbook.py` ni
    `sanitization.py` deben mutar estos datos -- solo leerlos."""

    run_dir: Path
    run_id: str
    timestamp: str
    mode: str
    connection_name: str
    migration_object: str
    prototype_status: str
    approved_for_enablon_import: bool

    validation_report: dict[str, Any]
    export_manifest: dict[str, Any]
    comparison_report: dict[str, Any] | None

    issues: tuple[dict[str, Any], ...]
    open_questions: dict[str, dict[str, str] | None]

    csv_path: Path
    csv_columns: tuple[str, ...] = field(default_factory=tuple)
