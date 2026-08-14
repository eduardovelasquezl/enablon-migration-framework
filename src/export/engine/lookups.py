"""Resolución de lookups simples `código -> valor destino` (Sprint 9.8).

Extraído de `drills/transformations.py` tras confirmar una TERCERA
necesidad real e idéntica:

- `LookupResult`: usado por Drills (origen), Bypass (Sprint 9.4, vía
  `resolve_letter`) y Safety Meetings (Sprint 9.7, vía
  `resolve_workflow_status`).
- `resolve_letter`: reutilizada tal cual por los 4 lookups de Bypass
  (`ByPassType`/`Cause`/`ElementType`/`RealizationMethods`) -- semántica:
  `null_default` SOLO para el caso vacío; un valor presente pero sin
  coincidencia en la tabla queda `unresolved`, sin aplicarle el default
  (los dos casos nunca se mezclan).
- `resolve_workflow_status`: reutilizada tal cual por los 3 lookups de
  Safety Meetings (`CS_WorkflowStatus`/`CS_Level`/`CS_Letter`) --
  semántica: SIN default en ningún caso (ni vacío ni sin coincidencia),
  correcta porque ninguna hoja `Mapeo_*` de Safety Meetings documenta un
  `nullcontrol`.

Bypass y Safety Meetings solo IMPORTABAN estas funciones de
`drills.transformations` (nunca las copiaron) -- este movimiento corrige
el acoplamiento módulo-a-módulo resultante, no elimina duplicación de
código (no la había). Mismo criterio que `identifiers.py` en este mismo
sprint.

`resolve_typology` (Drills) NO se mueve aquí: solo tiene un uso real
(Drills), sin segunda ni tercera confirmación -- permanece module-specific
en `drills/transformations.py`, que importa `normalize_lookup_key` de
este fichero para no duplicar esa pieza sí ya demostrada genérica (usada
internamente por `resolve_letter`/`resolve_workflow_status`/
`resolve_typology`, sus tres llamadores)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .values import is_missing, to_native


@dataclass(frozen=True)
class LookupResult:
    value: str | None
    status: str  # "resolved" | "default_no_match" | "null_default" | "unresolved"
    raw_source_value: object = field(default=None)


def normalize_lookup_key(value) -> str | None:
    if is_missing(value):
        return None
    value = to_native(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+\.0+", text):
            return text.split(".")[0]
        return text
    return str(value)


def resolve_letter(id_letra, letter_lookup: dict, null_default: str) -> LookupResult:
    """`null_default` se aplica SOLO cuando `id_letra` está vacío. Un
    `id_letra` presente pero sin coincidencia en `letter_lookup` queda
    `unresolved` -- no se le aplica el default (son casos distintos, no
    se mezclan)."""
    if is_missing(id_letra):
        return LookupResult(value=null_default, status="null_default", raw_source_value=id_letra)
    key = normalize_lookup_key(id_letra)
    lookup = {str(k): v for k, v in letter_lookup.items()}
    if key in lookup:
        return LookupResult(value=lookup[key], status="resolved", raw_source_value=id_letra)
    return LookupResult(value=None, status="unresolved", raw_source_value=id_letra)


def resolve_workflow_status(estado, workflow_status_lookup: dict) -> LookupResult:
    """`estado` -> valor destino, SIN default para ausencia/no-coincidencia
    en ningún caso -- nunca se inventa uno: se reporta `unresolved` y se
    conserva el valor origen para auditoría.

    `key` se normaliza con `normalize_lookup_key` (Micro-sprint 9.10.1) --
    antes usaba `str(estado).strip()` a secas, que nunca coincidía cuando
    `estado` llegaba como float íntegro (`256.0`, típico de una columna SQL
    nullable que pandas sube a `float64`): `resolve_letter`, en este mismo
    fichero, ya normalizaba así; esta función no, y era el único de los dos
    lookups reutilizado por los 3 campos numéricos de Safety Meetings
    (`CS_Level`/`CS_Letter`) -- ver Informe-Micro-Sprint-9.10-Level-Letter-
    StartDate-RootCause-EMF.md para la evidencia completa. Los códigos de
    texto de Drills (`"Terminado"`, `"En Curso"`...) no cambian de
    comportamiento: `normalize_lookup_key` los deja pasar tal cual."""
    if is_missing(estado):
        return LookupResult(value=None, status="unresolved", raw_source_value=estado)
    key = normalize_lookup_key(estado)
    if key in workflow_status_lookup:
        return LookupResult(value=workflow_status_lookup[key], status="resolved", raw_source_value=estado)
    return LookupResult(value=None, status="unresolved", raw_source_value=estado)
