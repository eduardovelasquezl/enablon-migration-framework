"""DataWorkspace — resuelve rutas dentro del workspace externo de datos
(Sprint 7, Workspace Separation). Ver
`docs/01-architecture/external-data-workspace.md` para el diseño completo.

No conoce Drills ni ningún objeto migrable concreto: solo sabe resolver
"proyecto + categoría + ruta relativa" contra una raíz externa
configurable (`EMF_DATA_ROOT` por defecto, nunca codificada aquí). Vive en
`src/core/` porque es infraestructura genérica reutilizable por cualquier
módulo futuro, en el mismo sentido que `contracts.py`/`registry.py`
(ninguno de los dos conoce Drills tampoco).

Garantías deliberadas de esta implementación:
- Nunca abre ni lee el contenido de ningún archivo.
- Nunca crea directorios automáticamente.
- Nunca imprime ni incluye en un mensaje de error nada más que la propia
  ruta que se intentó resolver (sin credenciales, sin contenido).
- Usa `pathlib.Path` en todo momento -- nunca concatenación de cadenas
  con separadores fijos, lo que permite rutas con espacios y caracteres
  Unicode sin tratamiento especial.
- Un intento de escapar de la carpeta de categoría mediante `..` se
  rechaza explícitamente, nunca se resuelve en silencio.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.config import load_yaml

DATA_WORKSPACE_CONFIG_FILE = "config/data_workspace.yaml"
DEFAULT_ROOT_ENV = "EMF_DATA_ROOT"


class DataWorkspaceError(Exception):
    """Base común de todas las excepciones de resolución del workspace
    externo -- permite un `except DataWorkspaceError` genérico, mismo
    patrón que `QueryEngineError`/`CoreError` ya establecido en el resto
    del repositorio."""


class DataRootNotConfiguredError(DataWorkspaceError):
    """La variable de entorno que declara la raíz del workspace externo
    (`root_env`, por defecto `EMF_DATA_ROOT`) no está definida en este
    entorno."""


class UnknownProjectError(DataWorkspaceError):
    """El proyecto solicitado no está declarado en
    `config/data_workspace.yaml` -> `projects`."""


class UnknownCategoryError(DataWorkspaceError):
    """La categoría solicitada no está declarada para ese proyecto en
    `config/data_workspace.yaml` -> `projects.<proyecto>.categories`."""


class PathEscapesWorkspaceError(DataWorkspaceError):
    """`relative_path` intenta salir de la carpeta de la categoría
    resuelta (típicamente mediante `..`) -- nunca se permite, ni siquiera
    si el resultado final seguiría estando dentro de `EMF_DATA_ROOT`: el
    contrato es no escapar de la categoría solicitada."""


class RequiredPathNotFoundError(DataWorkspaceError):
    """Se pidió una ruta con `required=True` y no existe en disco."""


class DataWorkspace:
    """Resuelve rutas de datos reales contra un workspace externo,
    configurado por variable de entorno.

    No valida credenciales, no abre conexiones, no conoce SQL Server ni
    ningún objeto migrable -- exclusivamente resolución de rutas.
    """

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        root_override: str | Path | None = None,
    ) -> None:
        """`config` permite inyectar una configuración distinta de
        `config/data_workspace.yaml` (usado en tests, para no depender del
        fichero real del repositorio). `root_override` permite fijar la
        raíz del workspace sin pasar por la variable de entorno (usado en
        tests con `tmp_path`) -- en producción, ningún llamador real debe
        pasar `root_override`."""
        self._config: Mapping[str, Any] = (
            config if config is not None else load_yaml(DATA_WORKSPACE_CONFIG_FILE)
        )
        self._root_override = Path(root_override) if root_override is not None else None

    @property
    def root_env(self) -> str:
        return self._config.get("root_env", DEFAULT_ROOT_ENV)

    def data_root(self) -> Path:
        """Raíz del workspace externo -- lee la variable de entorno en
        cada llamada (nunca cacheada), para que un cambio de entorno entre
        dos ejecuciones/tests se refleje sin reiniciar el proceso."""
        if self._root_override is not None:
            return self._root_override
        env_name = self.root_env
        raw = os.environ.get(env_name)
        if not raw:
            raise DataRootNotConfiguredError(
                f"La variable de entorno {env_name!r} no está definida -- el "
                "workspace externo de datos no está configurado en este "
                "entorno. Ver docs/01-architecture/external-data-workspace.md."
            )
        return Path(raw)

    def _category_dir(self, project: str, category: str) -> Path:
        projects = self._config.get("projects", {})
        if project not in projects:
            raise UnknownProjectError(
                f"Proyecto no declarado en {DATA_WORKSPACE_CONFIG_FILE!r}: "
                f"{project!r}. Disponibles: {sorted(projects)}"
            )
        project_cfg = projects[project]
        categories = project_cfg.get("categories", {})
        if category not in categories:
            raise UnknownCategoryError(
                f"Categoría no declarada para el proyecto {project!r}: "
                f"{category!r}. Disponibles: {sorted(categories)}"
            )
        base = project_cfg.get("base", f"projects/{project}")
        return self.data_root() / base / categories[category]

    def resolve(
        self,
        *,
        project: str,
        category: str,
        relative_path: str | Path = "",
        required: bool = True,
    ) -> Path:
        """Resuelve `project`/`category`/`relative_path` contra la raíz
        del workspace externo.

        - Nunca crea directorios ni abre/lee el archivo resuelto.
        - Rechaza cualquier `relative_path` que escape de la carpeta de la
          categoría (`PathEscapesWorkspaceError`), típicamente vía `..`.
        - Si `required=True` y la ruta resultante no existe en disco,
          lanza `RequiredPathNotFoundError` con un mensaje claro. Si
          `required=False`, devuelve la ruta exista o no -- quien llama
          decide qué hacer (mismo patrón ya usado hoy por Drills para el
          CSV histórico de comparación, opcional).
        """
        if relative_path and Path(relative_path).is_absolute():
            raise PathEscapesWorkspaceError(
                f"relative_path debe ser relativo, se recibió una ruta absoluta: "
                f"{str(relative_path)!r}."
            )

        category_dir = self._category_dir(project, category)
        category_dir_resolved = category_dir.resolve()
        candidate = (
            (category_dir / relative_path).resolve() if str(relative_path) else category_dir_resolved
        )
        try:
            candidate.relative_to(category_dir_resolved)
        except ValueError:
            raise PathEscapesWorkspaceError(
                f"La ruta relativa {str(relative_path)!r} sale de la carpeta "
                f"de la categoría {category!r} del proyecto {project!r} -- "
                "no se permite escapar de la categoría solicitada."
            ) from None

        if required and not candidate.exists():
            raise RequiredPathNotFoundError(
                f"Ruta requerida no encontrada en el workspace externo: {candidate}"
            )
        return candidate


def get_default_data_workspace() -> DataWorkspace:
    """Punto de entrada por defecto: `DataWorkspace` construido a partir
    de `config/data_workspace.yaml` real del repositorio, resolviendo la
    raíz desde la variable de entorno declarada en él. No cachea la
    instancia (es barata de construir; la propia carga de YAML ya está
    cacheada por `src.config.loader`)."""
    return DataWorkspace()
