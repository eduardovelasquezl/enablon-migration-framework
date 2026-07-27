"""Excepciones del Framework Core -- reservadas para errores de
infraestructura/programación del propio motor de ejecución (registro,
configuración de pipeline, contratos), nunca para errores de negocio de un
módulo concreto (esos se representan como `Issue`/`StageResult`, ver
`contracts.py`). Mismo principio ya vigente en el resto del proyecto para
`validate_*` (ver `docs/03-engineering-standards/engineering-standards.md`
§ 4): una regla de negocio incumplida no lanza excepción.
"""
from __future__ import annotations


class CoreError(Exception):
    """Base común de todas las excepciones del Framework Core -- permite un
    `except CoreError` genérico sin enumerar cada subtipo, mismo patrón que
    `QueryEngineError`/`DatabaseError` ya establecido en `src/query/` y
    `src/db/`."""


class StageNotRegisteredError(CoreError):
    """Una `PipelineDefinition` referencia un nombre de etapa que no está
    registrado en el `StageRegistry` -- error de configuración del
    pipeline, nunca un fallo silencioso ni una etapa que se omite sin
    avisar."""


class DuplicateStageRegistrationError(CoreError):
    """Se intentó registrar dos veces el mismo nombre de etapa sin pedir
    explícitamente sobrescritura -- evita que un registro tardío reemplace
    uno anterior sin que quien orquesta lo note."""


class PipelineConfigurationError(CoreError):
    """La `PipelineDefinition`, el `ExecutionRequest` o la configuración
    resuelta no tienen una forma válida para ejecutar (p. ej. lista de
    etapas vacía, modo de ejecución desconocido)."""
