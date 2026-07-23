"""
Accesores genéricos sobre los YAML de configuración del proyecto
(config/settings.yaml, config/databases.yaml, config/modules.yaml,
config/validation_rules.yaml).

Este módulo no interpreta el significado de ninguna sección: expone datos
tal cual están escritos en el YAML correspondiente. La interpretación de
negocio (qué es un rollback, qué es el Hallazgo #1, qué IDCentro corresponde
a qué site, qué hacer con una regla de transformación...) es responsabilidad
de los componentes de análisis/validación/ETL que consuman estos
accesores — no de este núcleo de configuración.

No contiene ni resuelve credenciales: `get_database_config` devuelve los
metadatos de conexión tal cual están en databases.yaml (driver, nombres de
variable de entorno, flags de solo lectura), nunca valores de .env ni
cadenas de conexión.
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from src.config.loader import PROJECT_ROOT, load_yaml

SETTINGS_FILE = "config/settings.yaml"
DATABASES_FILE = "config/databases.yaml"
MODULES_FILE = "config/modules.yaml"
VALIDATION_RULES_FILE = "config/validation_rules.yaml"


@lru_cache(maxsize=None)
def get_paths() -> Mapping[str, Path]:
    """Devuelve, para cada carpeta declarada en config/settings.yaml ->
    folders, su ruta absoluta como Path.

    No interpreta qué contiene cada carpeta ni exige que exista en disco —
    solo resuelve rutas relativas contra la raíz del proyecto.
    """
    folders = load_yaml(SETTINGS_FILE).get("folders", {})
    return MappingProxyType({name: PROJECT_ROOT / rel for name, rel in folders.items()})


def get_general_settings() -> Mapping[str, Any]:
    """Sección `general` de config/settings.yaml (parámetros no sensibles,
    no específicos de módulo ni de conexión)."""
    return load_yaml(SETTINGS_FILE).get("general", {})


def get_database_config(name: str | None = None) -> Mapping[str, Any]:
    """Metadatos crudos de una conexión declarada en config/databases.yaml
    -> connections. Si `name` es None, usa la conexión `default` del propio
    archivo.

    Devuelve driver, nombres de variable de entorno y flags — nunca
    resuelve el valor de esas variables ni construye una cadena de
    conexión; eso es responsabilidad de src/db/connection.py.
    """
    data = load_yaml(DATABASES_FILE)
    connections = data.get("connections", {})
    name = name or data.get("default")
    if name not in connections:
        raise KeyError(
            f"No existe la conexión '{name}' en {DATABASES_FILE}. "
            f"Disponibles: {sorted(connections.keys())}"
        )
    return connections[name]


def get_safety_settings() -> Mapping[str, Any]:
    """Sección `safety` de config/databases.yaml (palabras clave prohibidas,
    límites de filas/timeout). Solo datos — no aplica ninguna salvaguarda
    por sí mismo."""
    return load_yaml(DATABASES_FILE).get("safety", {})


def get_mapping_section(name: str) -> Any:
    """Sección de nivel superior de config/modules.yaml, tal cual (p. ej.
    `modules`, `idcentro_map_itp`, `idcentro_map_gct`, `rollback_entities`,
    `hallazgo_1_infra_migracion`).

    Genérico a propósito: este núcleo no sabe ni le importa qué significa
    cada sección, solo la devuelve para que la capa de análisis decida.
    """
    data = load_yaml(MODULES_FILE)
    if name not in data:
        raise KeyError(
            f"La sección '{name}' no existe en {MODULES_FILE}. "
            f"Disponibles: {sorted(data.keys())}"
        )
    return data[name]


def get_rule_section(name: str) -> Any:
    """Sección de nivel superior de config/validation_rules.yaml, tal cual
    (p. ej. `transformation_rules`, `data_quality_checks`)."""
    data = load_yaml(VALIDATION_RULES_FILE)
    if name not in data:
        raise KeyError(
            f"La sección '{name}' no existe en {VALIDATION_RULES_FILE}. "
            f"Disponibles: {sorted(data.keys())}"
        )
    return data[name]


def get_validation_rules() -> Mapping[str, Any]:
    """Contenido completo de config/validation_rules.yaml (ambas secciones,
    `transformation_rules` y `data_quality_checks`)."""
    return load_yaml(VALIDATION_RULES_FILE)
