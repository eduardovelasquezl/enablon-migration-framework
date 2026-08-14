"""Validación post-escritura del CSV de bypass.By_Passes.

MODULE_SPECIFIC pero deliberadamente más genérico que su equivalente en
Drills (`drills.validator.validate_output_csv`, que recibe el
`DrillsExportConfig` completo) -- esta versión solo pide `OutputSpec`,
que ya es genérico (ver `bypass.config`). No se reutiliza la de Drills
tal cual porque está acoplada a `DrillsExportConfig`, no a
`OutputSpec` -- diferencia pequeña pero real, registrada en
docs/07-developer-guide/bypass-module.md § 6."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.export.prototype.drills.config import OutputSpec


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
    result = PostWriteValidation()

    if not path.is_file():
        result.issues.append(f"El fichero de salida no existe: {path}")
        return result

    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode(output_spec.encoding)
    except UnicodeDecodeError as exc:
        result.issues.append(f"El fichero no es {output_spec.encoding} válido: {exc}")
        return result

    reader = csv.reader(text.splitlines(), delimiter=output_spec.delimiter, quotechar='"')
    rows = list(reader)
    if not rows:
        result.issues.append("El fichero de salida está vacío (sin cabecera).")
        return result

    header, data_rows = rows[0], rows[1:]
    result.columns = header
    result.column_count = len(header)
    result.row_count = len(data_rows)

    if header != expected_columns:
        result.issues.append(
            f"La cabecera no coincide con el orden esperado.\n"
            f"  esperado: {expected_columns}\n  obtenido: {header}"
        )

    return result
