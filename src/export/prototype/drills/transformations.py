"""Transformaciones de campo para simulacros.Drills -- funciones puras,
testeables de forma aislada, cada una con referencia a la evidencia que la
respalda (ver `config/exports/drills.yaml`).

Ninguna función aquí decide si una fila entra o no en el CSV final -- eso es
responsabilidad de `validator.py` (política `invalid_row_policy`).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

# Patrón de validación estructural de Reference -- ver Fase 8 del incremento
# de implementación. Se usa SOLO para validar, nunca para reconstruir o
# corregir una Reference defectuosa.
REFERENCE_PATTERN = re.compile(r"^[^-]+-HIST-[^-]+-\d{2}/\d{2}/\d{4}$")

_DATE_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def _to_native(value):
    """Convierte un escalar numpy (`numpy.int64`, `numpy.float64`...) al
    tipo Python nativo equivalente. pandas devuelve escalares numpy al leer
    columnas SQL bigint/numeric -- sin esto, `isinstance(value, int)`
    devuelve `False` para un `numpy.int64` y las comprobaciones de tipo de
    abajo se saltarían en silencio."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def _is_missing(value) -> bool:
    value = _to_native(value)
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


# --------------------------------------------------------------------------
# StartingDate
# --------------------------------------------------------------------------

def parse_starting_date(value) -> datetime | None:
    """Convierte `Fecha` (origen) a `datetime`, aceptando tanto un
    `datetime`/`Timestamp` ya materializado como una cadena en varios
    formatos observados (con u sin hora, con u sin segundos).

    Devuelve `None` si el valor está vacío o no es interpretable como
    fecha -- nunca inventa una fecha por defecto.
    """
    if _is_missing(value):
        return None
    value = _to_native(value)
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        text = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None
    return None


def format_starting_date(value: datetime, date_format: str = "dd/MM/yyyy HH:mm") -> str:
    """Formatea `StartingDate` para la columna de salida (con hora, a
    diferencia del componente usado dentro de `Reference`, que es solo
    fecha -- ver `format_reference_date`)."""
    py_format = date_format.replace("dd", "%d").replace("MM", "%m").replace("yyyy", "%Y").replace("HH", "%H").replace("mm", "%M")
    return value.strftime(py_format)


def format_reference_date(value: datetime) -> str:
    """Componente de fecha DENTRO de `Reference`: siempre `dd/MM/yyyy`, sin
    hora -- regla funcional aprobada, no reinterpretable."""
    return value.strftime("%d/%m/%Y")


# --------------------------------------------------------------------------
# CS_HistoricalOriginID
# --------------------------------------------------------------------------

def to_historical_id(value) -> str | None:
    """Convierte `IDSimulacro` a texto sin representación decimal
    artificial (p. ej. `440.0` -> `"440"`, no `"440"` con resto de coma
    flotante). Devuelve `None` si el valor está vacío."""
    if _is_missing(value):
        return None
    value = _to_native(value)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return None  # un ID con parte decimal real no es un ID válido -- no se trunca en silencio.
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+", text):
            return text
        if re.fullmatch(r"-?\d+\.0+", text):
            return text.split(".")[0]
        return None
    return None


# --------------------------------------------------------------------------
# CS_Typology / CS_Letter / CS_WorkflowStatus -- lookups documentados
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LookupResult:
    value: str | None
    status: str  # "resolved" | "default_no_match" | "null_default" | "unresolved"
    raw_source_value: object = field(default=None)


def _normalize_lookup_key(value) -> str | None:
    if _is_missing(value):
        return None
    value = _to_native(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+\.0+", text):
            return text.split(".")[0]
        return text
    return str(value)


def resolve_typology(id_tipo, typology_lookup: dict, default_no_match: str) -> LookupResult:
    """IDTipo -> CS_Typology. Confirmado con fórmula real (2-step XLOOKUP,
    ver `etl_transform:simulacros.mapeotiposim.typology_two_step_lookup`);
    el default `default_no_match` ("NADA") está documentado, no inventado
    por este prototipo -- se aplica tanto a IDTipo vacío como a IDTipo sin
    coincidencia, igual que el XLOOKUP original."""
    key = _normalize_lookup_key(id_tipo)
    lookup = {str(k): v for k, v in typology_lookup.items()}
    if key is not None and key in lookup:
        return LookupResult(value=lookup[key], status="resolved", raw_source_value=id_tipo)
    return LookupResult(value=default_no_match, status="default_no_match", raw_source_value=id_tipo)


def resolve_letter(id_letra, letter_lookup: dict, null_default: str) -> LookupResult:
    """IDLetra -> CS_Letter. `null_default` ("NOLETTER-WRONG") es el
    literal EXACTO del `nullcontrol` de la hoja `Mapeo_Letra` -- se aplica
    solo cuando IDLetra está vacío. Un IDLetra presente pero sin
    coincidencia en la tabla queda `unresolved` -- no se le aplica el
    default de NULL (son casos distintos, no se mezclan)."""
    if _is_missing(id_letra):
        return LookupResult(value=null_default, status="null_default", raw_source_value=id_letra)
    key = _normalize_lookup_key(id_letra)
    lookup = {str(k): v for k, v in letter_lookup.items()}
    if key in lookup:
        return LookupResult(value=lookup[key], status="resolved", raw_source_value=id_letra)
    return LookupResult(value=None, status="unresolved", raw_source_value=id_letra)


def resolve_workflow_status(estado, workflow_status_lookup: dict) -> LookupResult:
    """Estado -> CS_WorkflowStatus. Tabla estática confirmada de 4 valores
    (`etl_transform:simulacros.mapeoestado.workflow_status_lookup`). Sin
    default confirmado para un Estado no listado -- no se inventa uno: se
    reporta `unresolved` y se conserva el valor origen para auditoría."""
    if _is_missing(estado):
        return LookupResult(value=None, status="unresolved", raw_source_value=estado)
    key = str(estado).strip()
    if key in workflow_status_lookup:
        return LookupResult(value=workflow_status_lookup[key], status="resolved", raw_source_value=estado)
    return LookupResult(value=None, status="unresolved", raw_source_value=estado)


# --------------------------------------------------------------------------
# Reference -- AFD-DRILLS-REFERENCE-001 (decisión funcional aprobada)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReferenceResult:
    value: str | None
    missing_components: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.value is not None and not self.missing_components


def build_reference(cs_typology, cs_historical_origin_id: str | None, starting_date: datetime | None) -> ReferenceResult:
    """Reference = CS_Typology + "-HIST-" + CS_HistoricalOriginID + "-" +
    StartingDate(dd/MM/yyyy).

    Regla funcional aprobada (`AFD-DRILLS-REFERENCE-001`,
    `docs/specifications/v1.0/export/open_questions.md` OQ-ETL-03,
    resuelta). No se reinterpreta. Sin fallback artificial: si falta
    cualquier componente, no se construye ninguna Reference -- se
    devuelven los componentes ausentes para que `validator.py` los
    contabilice y excluya la fila según `invalid_row_policy`.
    """
    missing: list[str] = []

    typology = None
    if cs_typology is not None and str(cs_typology).strip() != "":
        typology = str(cs_typology).strip()
    else:
        missing.append("missing_typology")

    origin_id = cs_historical_origin_id
    if origin_id is None or str(origin_id).strip() == "":
        missing.append("missing_historical_origin_id")
        origin_id = None

    date_component = None
    if starting_date is not None:
        date_component = format_reference_date(starting_date)
    else:
        missing.append("missing_starting_date")

    if missing:
        return ReferenceResult(value=None, missing_components=tuple(missing))

    value = f"{typology}-HIST-{origin_id}-{date_component}"
    return ReferenceResult(value=value, missing_components=())


def reference_matches_pattern(value: str) -> bool:
    return bool(REFERENCE_PATTERN.match(value))
