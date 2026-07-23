"""Validaciones previas y posteriores a la escritura del CSV de Drills.

Separadas en dos momentos, tal como exige la Fase 8 del incremento:
- `validate_pre_write`: sobre el DataFrame extraído/transformado, antes de
  escribir nada en disco.
- `validate_output_csv`: sobre el fichero ya escrito, reabriéndolo de forma
  independiente (no reutiliza el DataFrame en memoria) para detectar
  problemas de la propia escritura (encoding, BOM, columnas, filas).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import DrillsExportConfig
from .transformations import REFERENCE_PATTERN


@dataclass
class PreWriteValidation:
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_pre_write(
    df: pd.DataFrame,
    config: DrillsExportConfig,
) -> PreWriteValidation:
    """Comprobaciones ANTES de escribir: columnas fuente disponibles,
    columnas obligatorias configuradas, número de filas > 0. Los mappings
    (tipología/letra/estado/entidad) se validan por su cuenta al cargarse
    (ver `mappings.load_entity_catalog`, que lanza si el CSV no existe o no
    tiene las columnas esperadas) -- si esta función se llama, ya se
    cargaron sin error."""
    result = PreWriteValidation()

    if df.empty:
        result.issues.append("El DataFrame extraído no contiene ninguna fila.")
        return result

    required_source_columns: set[str] = set()
    for f in config.fields:
        # `f.source` puede ser una lista (varias columnas fuente, p. ej. el
        # campo `Reference`) o una sola columna -- una vez cargado desde
        # YAML congelado (`src/config/loader.py`), una lista llega como
        # `tuple`, no como `list`.
        sources = f.source if isinstance(f.source, (list, tuple)) else [f.source]
        for s in sources:
            if s:
                required_source_columns.add(s)

    missing_columns = required_source_columns - set(df.columns)
    if missing_columns:
        result.issues.append(
            f"Columnas fuente esperadas ausentes en el resultado de la consulta: "
            f"{sorted(missing_columns)}"
        )

    return result


def check_duplicate_references(reference_values: list[str]) -> int:
    """Cuenta valores de `Reference` (ya construidos, no nulos) que se
    repiten más de una vez -- filas afectadas, no valores distintos."""
    seen: dict[str, int] = {}
    for value in reference_values:
        seen[value] = seen.get(value, 0) + 1
    return sum(count for count in seen.values() if count > 1)


# --------------------------------------------------------------------------
# Post-escritura
# --------------------------------------------------------------------------

@dataclass
class PostWriteValidation:
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    columns: list[str] = field(default_factory=list)
    reference_valid: int = 0
    reference_invalid: int = 0

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_output_csv(
    path: Path,
    config: DrillsExportConfig,
    expected_columns: list[str],
    expected_row_count: int,
) -> PostWriteValidation:
    result = PostWriteValidation()

    if not path.is_file():
        result.issues.append(f"El fichero de salida no existe: {path}")
        return result

    raw_bytes = path.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf") and not config.output.bom:
        result.issues.append("El fichero contiene BOM UTF-8 pero la configuración declara bom=false.")
    if not raw_bytes.startswith(b"\xef\xbb\xbf") and config.output.bom:
        result.issues.append("El fichero no contiene BOM UTF-8 pero la configuración declara bom=true.")

    try:
        text = raw_bytes.decode(config.output.encoding)
    except UnicodeDecodeError as exc:
        result.issues.append(f"El fichero no es {config.output.encoding} válido: {exc}")
        return result

    try:
        raw_bytes.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        pass  # esperado -- contenido con acentos/ñ es válido en UTF-8, esto no es un error.

    reader = csv.reader(text.splitlines(), delimiter=config.output.delimiter, quotechar='"')
    rows = list(reader)
    if not rows:
        result.issues.append("El fichero de salida está vacío (sin cabecera).")
        return result

    header = rows[0]
    data_rows = rows[1:]

    result.columns = header
    result.column_count = len(header)
    result.row_count = len(data_rows)

    if header != expected_columns:
        result.issues.append(
            f"La cabecera no coincide con el orden esperado.\n"
            f"  esperado: {expected_columns}\n  obtenido: {header}"
        )

    if len(data_rows) != expected_row_count:
        result.issues.append(
            f"Número de filas exportadas ({len(data_rows)}) distinto del "
            f"esperado ({expected_row_count})."
        )

    bad_column_count_rows = [i for i, r in enumerate(data_rows) if len(r) != len(header)]
    if bad_column_count_rows:
        result.issues.append(
            f"{len(bad_column_count_rows)} fila(s) no tienen el mismo número "
            f"de columnas que la cabecera (primeras: {bad_column_count_rows[:5]})."
        )

    if "Reference" in header:
        ref_idx = header.index("Reference")
        for r in data_rows:
            if len(r) <= ref_idx:
                continue
            value = r[ref_idx]
            if REFERENCE_PATTERN.match(value):
                result.reference_valid += 1
            else:
                result.reference_invalid += 1
        if result.reference_invalid:
            result.warnings.append(
                f"{result.reference_invalid} fila(s) con 'Reference' que no cumple el patrón esperado."
            )

    # Reabrible mediante Python (ya lo hicimos arriba); confirmar además que
    # pandas puede leerlo con la misma configuración declarada.
    try:
        pd.read_csv(
            path,
            sep=config.output.delimiter,
            encoding=config.output.encoding,
            quotechar='"',
            dtype=str,
        )
    except Exception as exc:  # noqa: BLE001 -- se reporta cualquier fallo de lectura, sin filtrar tipo.
        result.issues.append(f"El fichero no es reabrible con pandas: {exc}")

    return result
