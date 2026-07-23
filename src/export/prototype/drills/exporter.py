"""Escritura del CSV de Drills: UTF-8, escritura atómica (temporal +
renombrado), sin índice técnico de DataFrame.

No decide el contenido de las columnas -- solo serializa una lista de
`dict` ya transformados (`rows`) en el orden de columnas ya decidido por el
llamador (`pipeline.py`).
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from .config import OutputSpec

_QUOTING_MAP = {
    "minimal": csv.QUOTE_MINIMAL,
    "all": csv.QUOTE_ALL,
    "nonnumeric": csv.QUOTE_NONNUMERIC,
    "none": csv.QUOTE_NONE,
}


def write_csv(
    rows: list[dict],
    columns: list[str],
    output_path: Path,
    output_spec: OutputSpec,
) -> Path:
    """Escribe `rows` (una lista de dict, cada uno con exactamente las
    claves de `columns`) en `output_path`, de forma atómica: escribe a un
    fichero temporal en el MISMO directorio y solo lo renombra al destino
    final si la escritura completa sin error (`os.replace`, atómico en el
    mismo filesystem). Nunca sobrescribe una ejecución anterior porque el
    directorio de salida ya incluye un timestamp (ver `pipeline.py`).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(
            f"El fichero de salida ya existe y no se sobrescribe: {output_path}"
        )

    quoting = _QUOTING_MAP.get(output_spec.quoting, csv.QUOTE_MINIMAL)

    encoding = output_spec.encoding
    if output_spec.bom and encoding.lower() in ("utf-8", "utf8"):
        encoding = "utf-8-sig"  # único caso en el que Python añade BOM automáticamente en texto UTF-8.

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=str(output_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                delimiter=output_spec.delimiter,
                quoting=quoting,
                lineterminator=output_spec.line_terminator,
            )
            if output_spec.include_header:
                writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in columns})
        os.replace(tmp_path, output_path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return output_path
