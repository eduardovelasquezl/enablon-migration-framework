"""Comparación del CSV generado por el prototipo contra el CSV histórico
real de Drills (`Bloque4_CSV_Enablon/Drills-*.csv`).

El histórico es evidencia de exportación real -- NUNCA se trata como
plantilla oficial de Enablon (ver `evidence_inventory.md` §3 y
`closing_recommendation.md`). Esta comparación es de solo lectura sobre
ambos ficheros; no modifica ninguno de los dos.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

from .transformations import REFERENCE_PATTERN

NOT_AN_OFFICIAL_TEMPLATE = True
ROLE = "historical_output_evidence"

# Sprint 9.2: `_resolve_comparison_csv_path` ahora puede recibir el path
# declarado en un workspace.yaml REAL, cuya extensión no está garantizada
# que sea .csv (el Project Contract real de Drills en Moeve es un .xlsx,
# ver workspace.yaml). Este comparador solo sabe leer CSV -- soportar
# .xlsx es trabajo futuro (backlog), no de este incremento. Se detecta
# explícitamente para devolver un resultado claro ("no soportado"), nunca
# para intentar parsear un binario .xlsx como si fuera texto CSV.
SUPPORTED_EXTENSIONS = frozenset({".csv"})


@dataclass
class HistoricalCsvInfo:
    path: str
    encoding: str
    has_bom: bool
    delimiter: str
    columns: list[str]
    row_count: int


def _decode_and_strip_bom(raw: bytes, encoding: str) -> str:
    """Decodifica y retira un BOM residual (U+FEFF) que algunos codecs
    (`utf-16-le`/`utf-16-be` explícitos, a diferencia del genérico
    `utf-16`) NO retiran automáticamente -- sin esto, la primera columna de
    la cabecera queda contaminada (p. ej. `'\\ufeff"CS_WorkflowStatus"'` en
    vez de `'CS_WorkflowStatus'`), lo que rompe la comparación de esquema."""
    text = raw.decode(encoding)
    if text and text[0] == "﻿":
        text = text[1:]
    return text


def detect_historical_csv(path: Path) -> HistoricalCsvInfo:
    """Detecta encoding/BOM/delimitador/columnas/filas del CSV histórico sin
    asumir nada -- UTF-16LE con BOM y tabulador son lo observado en Drills,
    pero esta función no lo da por hecho para otros ficheros que se le
    pasen.

    El parseo usa `csv.reader` sobre un `io.StringIO` (no
    `text.splitlines()`): los CSV reales de Enablon tienen campos
    entrecomillados con saltos de línea internos (ver CLAUDE.md, nota sobre
    el recuento naive de Action Plans) -- partir por líneas ANTES de que el
    propio `csv` module entienda el quoting corrompería esas filas.
    """
    raw = path.read_bytes()
    if raw[:2] == b"\xff\xfe":
        encoding, has_bom = "utf-16-le", True
    elif raw[:2] == b"\xfe\xff":
        encoding, has_bom = "utf-16-be", True
    elif raw[:3] == b"\xef\xbb\xbf":
        encoding, has_bom = "utf-8-sig", True
    else:
        encoding, has_bom = "utf-8", False

    text = _decode_and_strip_bom(raw, encoding)
    first_line = text.splitlines()[0] if text else ""
    delimiter = "\t" if "\t" in first_line else ("," if "," in first_line else ";")

    reader = csv.reader(io.StringIO(text), delimiter=delimiter, quotechar='"')
    rows = list(reader)
    columns = rows[0] if rows else []
    row_count = max(len(rows) - 1, 0)

    return HistoricalCsvInfo(
        path=str(path), encoding=encoding, has_bom=has_bom,
        delimiter=delimiter, columns=columns, row_count=row_count,
    )


def _read_all_rows(path: Path, info: HistoricalCsvInfo) -> list[dict]:
    raw = path.read_bytes()
    text = _decode_and_strip_bom(raw, info.encoding)
    reader = csv.DictReader(io.StringIO(text), delimiter=info.delimiter, quotechar='"')
    return list(reader)


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def build_comparison_report(
    *,
    historical_path: Path,
    generated_rows: list[dict],
    generated_columns: list[str],
    key_column: str = "CS_HistoricalOriginID",
) -> dict:
    if not historical_path.is_file():
        return {
            "baseline": {"path": str(historical_path), "role": ROLE, "not_an_official_template": NOT_AN_OFFICIAL_TEMPLATE},
            "limitations": ["El CSV histórico declarado no existe -- no se generó comparación."],
        }

    if historical_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {
            "baseline": {"path": str(historical_path), "role": ROLE, "not_an_official_template": NOT_AN_OFFICIAL_TEMPLATE},
            "limitations": [
                f"Extensión {historical_path.suffix!r} no soportada por este comparador "
                f"(solo {sorted(SUPPORTED_EXTENSIONS)}) -- no se intentó leer el fichero, "
                "no se generó comparación de contenido."
            ],
        }

    info = detect_historical_csv(historical_path)
    historical_rows = _read_all_rows(historical_path, info)

    matching_columns = sorted(set(info.columns) & set(generated_columns))
    missing_in_generated = sorted(set(info.columns) - set(generated_columns))
    additional_in_generated = sorted(set(generated_columns) - set(info.columns))
    order_matches = info.columns == generated_columns

    limitations: list[str] = []

    if key_column not in info.columns or key_column not in generated_columns:
        limitations.append(
            f"'{key_column}' no está presente en ambos ficheros -- no se "
            "intenta una unión aproximada; sin comparación fila a fila."
        )
        return {
            "baseline": {"path": str(historical_path), "role": ROLE, "not_an_official_template": NOT_AN_OFFICIAL_TEMPLATE},
            "schema": {
                "matching_columns": matching_columns,
                "missing_in_generated": missing_in_generated,
                "additional_in_generated": additional_in_generated,
                "order_matches": order_matches,
            },
            "rows": {
                "historical": info.row_count,
                "generated": len(generated_rows),
                "matched_by_key": 0,
                "only_historical": info.row_count,
                "only_generated": len(generated_rows),
            },
            "differences": {
                "total_cells_compared": 0,
                "matching_cells": 0,
                "differing_cells": 0,
                "by_column": {},
            },
            "reference": {"matching": 0, "differing": 0, "historical_invalid": 0, "generated_invalid": 0},
            "limitations": limitations,
        }

    historical_by_key = {
        r[key_column].strip(): r for r in historical_rows if (r.get(key_column) or "").strip()
    }
    generated_by_key = {
        r[key_column].strip(): r for r in generated_rows if (r.get(key_column) or "").strip()
    }

    common_keys = set(historical_by_key) & set(generated_by_key)
    only_historical = set(historical_by_key) - set(generated_by_key)
    only_generated = set(generated_by_key) - set(historical_by_key)

    total_compared = 0
    matching_cells = 0
    by_column: dict[str, dict[str, int]] = {c: {"matching": 0, "differing": 0} for c in matching_columns}

    ref_matching = ref_differing = 0
    ref_hist_invalid = ref_gen_invalid = 0

    for key in common_keys:
        h_row = historical_by_key[key]
        g_row = generated_by_key[key]
        for col in matching_columns:
            h_val = (h_row.get(col) or "").strip()
            g_val = (g_row.get(col) or "").strip()
            total_compared += 1
            if h_val == g_val:
                matching_cells += 1
                by_column[col]["matching"] += 1
            else:
                by_column[col]["differing"] += 1

        if "Reference" in matching_columns:
            h_ref = (h_row.get("Reference") or "").strip()
            g_ref = (g_row.get("Reference") or "").strip()
            h_valid = bool(REFERENCE_PATTERN.match(h_ref)) if h_ref else False
            g_valid = bool(REFERENCE_PATTERN.match(g_ref)) if g_ref else False
            if not h_valid:
                ref_hist_invalid += 1
            if not g_valid:
                ref_gen_invalid += 1
            if h_valid and g_valid:
                if h_ref == g_ref:
                    ref_matching += 1
                else:
                    ref_differing += 1

    limitations.append(
        "Comparación limitada a las claves presentes en ambos ficheros en el "
        "momento de esta ejecución -- el histórico es una foto de una carga "
        "pasada, el generado depende del modo (sample/full) y del estado "
        "actual de la base de datos origen."
    )
    if not order_matches:
        limitations.append(
            "El orden y número de columnas difiere por diseño: el prototipo "
            "solo genera las columnas con evidencia suficiente (ver "
            "config/exports/drills.yaml -> excluded_columns)."
        )

    return {
        "baseline": {"path": str(historical_path), "role": ROLE, "not_an_official_template": NOT_AN_OFFICIAL_TEMPLATE},
        "schema": {
            "matching_columns": matching_columns,
            "missing_in_generated": missing_in_generated,
            "additional_in_generated": additional_in_generated,
            "order_matches": order_matches,
        },
        "rows": {
            "historical": info.row_count,
            "generated": len(generated_rows),
            "matched_by_key": len(common_keys),
            "only_historical": len(only_historical),
            "only_generated": len(only_generated),
        },
        "differences": {
            "total_cells_compared": total_compared,
            "matching_cells": matching_cells,
            "differing_cells": total_compared - matching_cells,
            "by_column": by_column,
        },
        "reference": {
            "matching": ref_matching,
            "differing": ref_differing,
            "historical_invalid": ref_hist_invalid,
            "generated_invalid": ref_gen_invalid,
        },
        "limitations": limitations,
        "sample_keys_hashed": [_short_hash(k) for k in sorted(common_keys)[:5]],
    }
