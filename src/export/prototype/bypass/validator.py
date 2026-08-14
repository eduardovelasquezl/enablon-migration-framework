"""Validación post-escritura del CSV de bypass.By_Passes.

Desde Sprint 9.6 (Export Engine mínimo), el núcleo (fichero existe,
decodifica, cabecera coincide) vive en
`src.export.engine.validator.validate_csv_structure` -- esta función ya era,
de las dos implementaciones existentes (Drills/Bypass), la forma correcta
de un validador genérico (recibe `OutputSpec`, no el config completo del
módulo, ver Sprint 9.4). Este fichero es ahora un wrapper delgado que
adapta el resultado genérico a la forma `PostWriteValidation` que
`bypass/pipeline.py` ya consumía, sin cambiar ningún campo."""
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
