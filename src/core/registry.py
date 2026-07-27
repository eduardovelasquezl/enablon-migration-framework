"""Registro explícito de etapas del Framework Core (Fase 3).

Deliberadamente NO implementa descubrimiento dinámico de plugins, ni
recorre directorios buscando clases, ni usa importaciones mágicas
(`importlib` sobre un paquete completo, entry points, etc.) -- exactamente
lo que el encargo prohíbe. Un nombre lógico de etapa se resuelve contra una
implementación solo si alguien llamó explícitamente a `register()` antes,
en código auditable (ver `src/export/prototype/drills/core_adapters.py`
para el único registro real que existe hoy).

Mismo criterio que `extensibility-model.md` § 5 ya fija para el futuro
`ObjectRegistry` del Core: "sin carga dinámica de plugins... hasta que
exista un segundo consumidor real" -- este `StageRegistry` es la instancia
concreta de ese mismo principio para etapas de pipeline.
"""
from __future__ import annotations

from src.core.contracts import PipelineStage
from src.core.exceptions import DuplicateStageRegistrationError, StageNotRegisteredError


class StageRegistry:
    """Instancia explícita, nunca un registro global de módulo (ADR-010,
    No Hidden State) -- quien orquesta una ejecución crea su propio
    `StageRegistry` y decide qué registrar en él, para que dos ejecuciones
    (o dos tests) no compartan registro sin saberlo."""

    def __init__(self) -> None:
        self._stages: dict[str, PipelineStage] = {}

    def register(self, name: str, stage: PipelineStage, *, overwrite: bool = False) -> None:
        if not name:
            raise DuplicateStageRegistrationError("El nombre de etapa no puede estar vacío.")
        if name in self._stages and not overwrite:
            raise DuplicateStageRegistrationError(
                f"La etapa {name!r} ya está registrada -- usa overwrite=True si el "
                "reemplazo es intencional (p. ej. en un test)."
            )
        self._stages[name] = stage

    def resolve(self, name: str) -> PipelineStage:
        try:
            return self._stages[name]
        except KeyError:
            raise StageNotRegisteredError(
                f"No hay ninguna etapa registrada con el nombre {name!r}. "
                f"Etapas disponibles: {sorted(self._stages)}"
            ) from None

    def is_registered(self, name: str) -> bool:
        return name in self._stages

    def registered_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._stages))
