"""Etapa `query` genérica del Framework Core v1 (Sprint 9.6).

Extrae el lifecycle común ya demostrado, casi línea a línea, por
`DrillsQueryStage`/`BypassQueryStage` (Sprint 9.5.1 § Fase 1/2): cargar la
configuración del módulo, dejarla en `context.state` para etapas
posteriores, compilar los filtros del `ExecutionRequest` contra el catálogo
de filtros del módulo, extraer, y construir `StageResult`/`StageMetrics`.

Cada módulo aporta sus propios componentes vía `QueryStageSpec` -- este
fichero no importa nada de `src.export.prototype.*` ni conoce ningún
`module_id` concreto. `ModuleAdapter` ya existe como concepto
(`ModuleDefinition.pipeline_factory`, `src/core/module_registry.py`,
confirmado en Sprint 9.5.1) -- esto NO es una segunda abstracción de
plugins, es un bloque reutilizable que un `pipeline_factory` ya existente
compone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from src.core.contracts import ExecutionContext, StageMetrics, StageResult, StageStatus
from src.query.catalog import ObjectFilterCatalog
from src.query.validator import compile_filter_tokens


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QueryStageSpec:
    """Todo lo que un módulo debe aportar para reutilizar
    `GenericQueryStage` -- ningún campo tiene un valor por defecto que
    asuma un módulo concreto.

    `extract_fn` debe aceptar `(config, mode=, limit=, compiled_filters=)` y
    devolver algo con `.rows_available_before_truncation`/`.dataframe`
    (mismo contrato que `ExtractionResult`, ver `engine/extractor.py`) --
    no se tipa aquí de forma estricta para no forzar un import de
    `engine.extractor` en módulos que pudieran tener su propia forma de
    extracción compatible.
    """

    name: str
    config_loader: Callable[[], Any]
    state_key: str
    filter_catalog: ObjectFilterCatalog
    extract_fn: Callable[..., Any]


class GenericQueryStage:
    """Etapa `query` reutilizable -- comportamiento observable idéntico al
    de `DrillsQueryStage`/`BypassQueryStage` antes de Sprint 9.6 (refactor
    behavior-preserving): mismo orden de operaciones, mismas métricas,
    mismo `StageResult`."""

    def __init__(self, spec: QueryStageSpec) -> None:
        self._spec = spec

    @property
    def name(self) -> str:
        return self._spec.name

    def execute(self, context: ExecutionContext, stage_input: Any) -> StageResult:
        start = _now()
        request = context.request

        config = self._spec.config_loader()
        context.state[self._spec.state_key] = config

        compiled_filters: tuple = ()
        if request.filters:
            compiled_filters = compile_filter_tokens(request.filters, self._spec.filter_catalog)

        extraction = self._spec.extract_fn(
            config, mode=request.mode, limit=request.limit, compiled_filters=compiled_filters,
        )

        metrics = StageMetrics(
            stage=self.name, start_time=start,
            input_record_count=extraction.rows_available_before_truncation,
            output_record_count=len(extraction.dataframe),
        )
        return StageResult(stage=self.name, status=StageStatus.SUCCESS, output=extraction, metrics=metrics)
