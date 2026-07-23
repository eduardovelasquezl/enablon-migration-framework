"""Resolución de entidad (`CS_ImpactedEntities`) para simulacros.Drills.

Mecanismo aceptado para Simulacros (`config/modules.yaml:84`,
`docs/specifications/v1.0/export/object_assessments/drills_entity_resolution_assessment.md`):
`IDUnidadOrg` -> catálogo `Entidades_Enablon_ITP` (681 filas, ya normalizado
en `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv`)
-> columna `Code`.

Este módulo NUNCA abre el workbook Excel original -- el catálogo ya está
normalizado en un CSV versionado del propio repositorio (preferencia 1 de
la Fase 4 del incremento: catálogo normalizado > CSV/YAML > workbook).
"""
from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.config import PROJECT_ROOT

RESOLVED = "resolved"
DO_NOT_MIGRATE = "do_not_migrate"
UNRESOLVED = "unresolved"
CONFLICTING = "conflicting"
EMPTY = "empty"


@dataclass(frozen=True)
class EntityResolution:
    value: str | None
    status: str  # resolved | do_not_migrate | unresolved | conflicting | empty
    raw_source_value: object = None


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _normalize_key(value) -> str | None:
    if _is_missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".")[0]
    if text.upper() == "NULL":
        return None
    return text


@dataclass(frozen=True)
class EntityCatalog:
    """Índice `IDUnidadOrg -> {Code}` construido desde el CSV normalizado.

    `conflicting_keys` conserva, para trazabilidad, qué claves tienen más
    de un `Code` distinto en el catálogo -- nunca se elige uno de forma
    silenciosa (mismo principio que `mapping_resolver.py`)."""
    key_to_codes: dict
    conflicting_keys: dict
    do_not_migrate_literal: str
    source_path: str
    row_count: int


def load_entity_catalog(
    csv_path: str | Path,
    key_column: str = "IDUnidadOrg",
    value_column: str = "Code",
    do_not_migrate_literal: str = "No migra",
) -> EntityCatalog:
    path = Path(csv_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"No existe el catálogo de entidad declarado: {path}")

    key_to_codes: dict[str, set[str]] = {}
    row_count = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if key_column not in (reader.fieldnames or []) or value_column not in (reader.fieldnames or []):
            raise ValueError(
                f"El catálogo {path} no tiene las columnas esperadas "
                f"({key_column!r}, {value_column!r}); columnas reales: {reader.fieldnames}"
            )
        for row in reader:
            row_count += 1
            key = _normalize_key(row.get(key_column))
            if key is None:
                continue
            value = (row.get(value_column) or "").strip()
            if not value:
                continue
            key_to_codes.setdefault(key, set()).add(value)

    conflicting = {k: sorted(v) for k, v in key_to_codes.items() if len(v) > 1}

    return EntityCatalog(
        key_to_codes=key_to_codes,
        conflicting_keys=conflicting,
        do_not_migrate_literal=do_not_migrate_literal,
        source_path=str(path),
        row_count=row_count,
    )


@lru_cache(maxsize=None)
def _load_entity_catalog_cached(csv_path: str, key_column: str, value_column: str, do_not_migrate_literal: str) -> EntityCatalog:
    return load_entity_catalog(csv_path, key_column, value_column, do_not_migrate_literal)


def get_entity_catalog(
    csv_path: str,
    key_column: str = "IDUnidadOrg",
    value_column: str = "Code",
    do_not_migrate_literal: str = "No migra",
) -> EntityCatalog:
    """Punto de entrada cacheado -- una sola lectura de disco por proceso."""
    return _load_entity_catalog_cached(csv_path, key_column, value_column, do_not_migrate_literal)


def resolve_entity(id_unidad_org, catalog: EntityCatalog) -> EntityResolution:
    """Clasifica `IDUnidadOrg` -> `CS_ImpactedEntities` en uno de los 5
    estados documentados en la Fase 4 del incremento. Nunca inventa un
    fallback: `unresolved` y `conflicting` se reportan tal cual."""
    key = _normalize_key(id_unidad_org)
    if key is None:
        return EntityResolution(value=None, status=EMPTY, raw_source_value=id_unidad_org)

    if key in catalog.conflicting_keys:
        return EntityResolution(value=None, status=CONFLICTING, raw_source_value=id_unidad_org)

    codes = catalog.key_to_codes.get(key)
    if not codes:
        return EntityResolution(value=None, status=UNRESOLVED, raw_source_value=id_unidad_org)

    (code,) = tuple(codes)
    if code.strip().lower() == catalog.do_not_migrate_literal.strip().lower():
        return EntityResolution(value=code, status=DO_NOT_MIGRATE, raw_source_value=id_unidad_org)

    return EntityResolution(value=code, status=RESOLVED, raw_source_value=id_unidad_org)
