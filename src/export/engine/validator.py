"""Validación estructural genérica de un CSV ya escrito (Sprint 9.6).

Núcleo extraído de `bypass/validator.py::validate_output_csv` -- ya era,
de las dos implementaciones existentes, la forma correcta de un validador
genérico (recibe `OutputSpec`, no el config completo del módulo -- ver su
propio docstring de Sprint 9.4). `drills/validator.py::validate_output_csv`
ENVUELVE esta función con sus propias comprobaciones adicionales
(`Reference` regex, `expected_row_count`) -- nunca las duplica.

Decodifica con `writer.resolve_text_encoding` (Micro-sprint 9.9.1), no con
`output_spec.encoding` a secas -- hallazgo propio de ese micro-sprint:
decodificar sin tener en cuenta `output_spec.bom` deja `U+FEFF` colgando
del primer valor de cabecera en cuanto un módulo declara `bom=true`,
rompiendo la comparación de cabecera más abajo. Sin efecto observable
mientras todos los módulos declaraban `bom=false`.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from src.export.engine.config import OutputSpec
from src.export.engine.writer import resolve_text_encoding


@dataclass
class CsvStructureResult:
    issues: list[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)
    data_rows: list[list[str]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_csv_structure(
    path: Path, expected_columns: list[str], output_spec: OutputSpec,
) -> CsvStructureResult:
    """Comprobaciones estructurales puras: el fichero existe, decodifica con
    el encoding declarado, tiene cabecera, y la cabecera coincide con
    `expected_columns`. Deja `data_rows` disponible para que el llamador
    (p. ej. `drills/validator.py`) añada comprobaciones de negocio sobre las
    filas sin volver a leer ni parsear el fichero."""
    result = CsvStructureResult()

    if not path.is_file():
        result.issues.append(f"El fichero de salida no existe: {path}")
        return result

    raw_bytes = path.read_bytes()
    decode_encoding = resolve_text_encoding(output_spec)
    try:
        text = raw_bytes.decode(decode_encoding)
    except UnicodeDecodeError as exc:
        result.issues.append(f"El fichero no es {decode_encoding} válido: {exc}")
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
    result.data_rows = data_rows

    if header != expected_columns:
        result.issues.append(
            f"La cabecera no coincide con el orden esperado.\n"
            f"  esperado: {expected_columns}\n  obtenido: {header}"
        )

    return result
