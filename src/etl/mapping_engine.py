"""
Motor de mapeo: aplica una lista de FieldMapping (ver excel_reader.py) sobre
un DataFrame de origen y produce el DataFrame destino, resolviendo cada
`ReglaEspecial` contra el registro de transformations.py.

Diseño deliberado: esto reemplaza el patrón "XLOOKUP + fórmula encadenada
por columna" del Excel original por un recorrido explícito, fila a fila,
por columna, con logging de qué regla se aplicó — para que cualquier
resultado sea auditable sin tener que abrir un Excel de 300 MB.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src.etl.excel_reader import FieldMapping
from src.etl.transformations import resolve_rule

logger = logging.getLogger(__name__)


@dataclass
class MappingRuleConfig:
    """Configuración adicional que una FieldMapping por sí sola no trae
    (p. ej. la lista de campos para un `concat`, o la tabla para un
    `lookup`). Se construye a mano por módulo a partir de lo ya conocido en
    config/modules.yaml, no se infiere automáticamente del Excel."""

    campo_destino: str
    regla: str | None = None
    kwargs: dict | None = None


def apply_mapping(
    source_df: pd.DataFrame,
    field_mappings: list[FieldMapping],
    rule_configs: dict[str, MappingRuleConfig] | None = None,
) -> pd.DataFrame:
    """Aplica los mapeos de campo sobre source_df y devuelve el DataFrame
    destino.

    - Los campos con `requiere_adaptacion=False` se copian tal cual
      (passthrough), asumiendo que el nombre de columna origen y destino
      coinciden o hay una relación 1:1 directa.
    - Los campos con `requiere_adaptacion=True` requieren un
      `MappingRuleConfig` explícito en `rule_configs` (indexado por
      `campo_destino_xml`) — si falta, se registra un warning y se deja el
      campo vacío en vez de adivinar.
    """
    rule_configs = rule_configs or {}
    result = pd.DataFrame(index=source_df.index)

    for fm in field_mappings:
        destino = fm.campo_destino_xml or fm.campo_destino_es
        if destino is None:
            continue

        if not fm.requiere_adaptacion:
            if fm.campo_origen in source_df.columns:
                result[destino] = source_df[fm.campo_origen]
            else:
                logger.debug(
                    "Campo origen '%s' no encontrado en el DataFrame de origen; "
                    "destino '%s' queda vacío.", fm.campo_origen, destino,
                )
                result[destino] = None
            continue

        cfg = rule_configs.get(destino)
        if cfg is None:
            logger.warning(
                "Campo '%s' -> '%s' requiere adaptación (regla '%s') pero no hay "
                "MappingRuleConfig registrado para él. Se deja vacío en vez de "
                "adivinar el comportamiento.",
                fm.campo_origen, destino, fm.regla,
            )
            result[destino] = None
            continue

        rule_fn = resolve_rule(cfg.regla or fm.regla or "")
        kwargs = cfg.kwargs or {}

        if fm.campo_origen in source_df.columns:
            result[destino] = source_df.apply(
                lambda row, col=fm.campo_origen: rule_fn(row[col], **kwargs)
                if _is_simple_rule(rule_fn)
                else rule_fn(row, **kwargs),
                axis=1,
            )
        else:
            logger.warning(
                "Campo origen '%s' no encontrado para aplicar la regla '%s' "
                "sobre destino '%s'.", fm.campo_origen, fm.regla, destino,
            )
            result[destino] = None

    return result


def _is_simple_rule(rule_fn) -> bool:
    """Distingue reglas que operan sobre un único valor (nullcontrol,
    titlefix, cloneorigin, lookup_simple, boolorigin) de las que necesitan
    la fila completa (concat, barconcat)."""
    return rule_fn.__name__ not in ("concat", "barconcat")


def validate_required_fields(
    result_df: pd.DataFrame, required_fields: list[str]
) -> list[str]:
    """Comprueba qué campos obligatorios del destino (según la plantilla
    oficial de Enablon) faltan por completo en el resultado. Devuelve la
    lista de campos ausentes — no lanza excepción, es responsabilidad de
    quien orquesta decidir si es bloqueante."""
    return [f for f in required_fields if f not in result_df.columns]
