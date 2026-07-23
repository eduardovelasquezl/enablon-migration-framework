"""
Carga genérica de archivos YAML de configuración, con caché interna y
exposición segura hacia los consumidores.

Este módulo no interpreta el contenido de ningún YAML — solo lo lee, lo
cachea por ruta absoluta, y lo congela recursivamente antes de devolverlo,
para que ningún consumidor pueda mutar por accidente el objeto compartido
en caché (un `dict` devuelto por `lru_cache` sin congelar sería mutable y
compartido entre todas las llamadas).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _freeze(value: Any) -> Any:
    """Convierte dict -> MappingProxyType y list -> tuple de forma
    recursiva, dejando el resto de tipos (str, int, float, bool, None) tal
    cual, ya que son inmutables por naturaleza."""
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@lru_cache(maxsize=None)
def _load_yaml_cached(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _freeze(data)


def load_yaml(relative_path: str | Path) -> Any:
    """Lee un YAML relativo a la raíz del proyecto y devuelve su contenido
    ya congelado (`MappingProxyType` / `tuple` de forma recursiva).

    Cacheado internamente por ruta absoluta: leer el mismo archivo varias
    veces no repite E/S de disco. Como el resultado ya es inmutable, se
    devuelve directamente sin necesidad de copiarlo en cada llamada.
    """
    path = (PROJECT_ROOT / relative_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo de configuración: {path}")
    return _load_yaml_cached(path)


def clear_cache() -> None:
    """Limpia la caché de YAML cargados. Pensado para tests, no para uso en
    producción (dentro de un mismo proceso, el contenido de config/*.yaml no
    cambia en caliente)."""
    _load_yaml_cached.cache_clear()
