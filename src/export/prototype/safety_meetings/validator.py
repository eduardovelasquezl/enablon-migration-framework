"""Validación post-escritura del CSV de safety_meetings.Group_Meetings.

Wrapper directo de `src.export.engine.validator.validate_csv_structure`
(Sprint 9.6) -- este módulo no tiene ninguna validación de negocio propia
todavía (sin patrón `Reference`, sin `expected_row_count` estricto), así
que no envuelve el núcleo con nada adicional -- a diferencia de Drills, es
igual de simple que `bypass/validator.py`."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.export.engine.config import OutputSpec
from src.export.engine.validator import validate_csv_structure


@dataclass
class PostWriteValidation:
    issues: list[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_output_csv(
    path: Path, expected_columns: list[str], output_spec: OutputSpec,
) -> PostWriteValidation:
    core = validate_csv_structure(path, expected_columns, output_spec)
    return PostWriteValidation(
        issues=list(core.issues), row_count=core.row_count,
        column_count=core.column_count, columns=list(core.columns),
    )
