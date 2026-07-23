"""
Fachada pública del núcleo de configuración del proyecto.

Uso típico desde cualquier otra capa (db/, analysis/, etl/, reporting/):

    from src.config import get_paths, get_database_config, get_mapping_section

Este paquete solo expone datos de configuración tal cual están escritos en
config/*.yaml — no interpreta su significado ni contiene lógica de negocio.
Esa interpretación corresponde a quien lo consume.
"""
from src.config.loader import PROJECT_ROOT, clear_cache, load_yaml
from src.config.settings import (
    get_database_config,
    get_general_settings,
    get_mapping_section,
    get_paths,
    get_rule_section,
    get_safety_settings,
    get_validation_rules,
)

__all__ = [
    "PROJECT_ROOT",
    "clear_cache",
    "load_yaml",
    "get_paths",
    "get_general_settings",
    "get_database_config",
    "get_safety_settings",
    "get_mapping_section",
    "get_rule_section",
    "get_validation_rules",
]
