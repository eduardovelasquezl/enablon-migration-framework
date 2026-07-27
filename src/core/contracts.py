"""Contratos mínimos del Framework Core v1.

Ninguna clase de este módulo conoce un proyecto, módulo, objeto migrable
ni columna concreta -- son formas genéricas que cualquier Connector/Stage
de cualquier objeto puede producir o consumir. Ver
`docs/01-architecture/framework-core-v1.md` para la justificación de cada
decisión (por qué estos nombres, por qué estos campos, qué se descartó).

Terminología reutilizada del resto del repositorio, no reinventada:
- Vocabularios cerrados como clase + `frozenset` (`StageStatus`,
  `ExecutionStatus`), mismo patrón que `src/knowledge_base/model.py`.
- `run_id`/`execution_id` aleatorio (`uuid4`), nunca determinista -- mismo
  principio ya fijado en `engineering-standards.md` § 5.
- Timestamps siempre UTC, tz-aware.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.core.exceptions import PipelineConfigurationError

_VALID_MODES = frozenset({"sample", "full"})
_VALID_AUDIENCES = frozenset({"internal", "client", "both"})


class StageStatus:
    """Resultado de UNA etapa. `SKIPPED` se reserva para una etapa que
    deliberadamente no hizo nada (p. ej. generación de evidencia
    deshabilitada por el `ExecutionRequest`) -- nunca para una etapa que
    falló en silencio."""
    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"
    SKIPPED = "skipped"
    ALL = frozenset({SUCCESS, WARNING, FAILURE, SKIPPED})


class ExecutionStatus:
    """Resultado de la ejecución COMPLETA -- se deriva de los `StageResult`
    acumulados, nunca se fija a mano por una etapa individual."""
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"
    ALL = frozenset({SUCCESS, SUCCESS_WITH_WARNINGS, FAILED})


def _check_choice(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        raise PipelineConfigurationError(
            f"{field_name}={value!r} no es un valor válido de {sorted(allowed)}"
        )


# ---------------------------------------------------------------------------
# ExecutionRequest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionRequest:
    """Solicitud de ejecución -- serializable, sin estado de I/O.

    NUNCA contiene: conexiones abiertas, DataFrames, credenciales, ni
    reglas funcionales (qué campo mapea a qué columna). Eso vive en la
    configuración de proyecto que el propio pipeline resuelve a partir de
    `project`/`object_type`/`module`, nunca en la petición.
    """

    project: str
    object_type: str
    module: str | None = None
    mode: str = "sample"
    limit: int = 100
    source_override: str | None = None
    output_dir: str | None = None
    confirm_full_export: bool = False
    generate_evidence: bool = False
    evidence_audience: str = "both"
    filters: tuple[str, ...] = field(default_factory=tuple)
    execution_id: str | None = None

    def __post_init__(self) -> None:
        if not self.project:
            raise PipelineConfigurationError("ExecutionRequest.project no puede estar vacío.")
        if not self.object_type:
            raise PipelineConfigurationError("ExecutionRequest.object_type no puede estar vacío.")
        _check_choice(self.mode, _VALID_MODES, "ExecutionRequest.mode")
        _check_choice(self.evidence_audience, _VALID_AUDIENCES, "ExecutionRequest.evidence_audience")
        if self.mode == "sample" and self.limit <= 0:
            raise PipelineConfigurationError("ExecutionRequest.limit debe ser positivo en modo 'sample'.")
        if self.mode == "full" and not self.confirm_full_export:
            raise PipelineConfigurationError(
                "ExecutionRequest.mode='full' exige confirm_full_export=True explícito "
                "(evita exportar todo el histórico por accidente, mismo criterio que la CLI actual)."
            )


# ---------------------------------------------------------------------------
# CanonicalBatch -- seam mínimo hacia el futuro CDM (Fase 6, Opción C)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalBatch:
    """Contenedor MÍNIMO y PROVISIONAL -- NO es el Canonical Data Model
    completo descrito en `docs/01-architecture/canonical-data-model.md`
    (no hay `CanonicalField`/`Provenance`/`Relationship` por fila aquí).

    Es el "intermediate record compatible con el futuro CDM" de la Opción
    C de la Fase 6 de Framework Core v1: envuelve el resultado ya extraído
    con la forma mínima que un futuro `CanonicalRecord` por fila
    necesitará (identidad de objeto/fuente, recuento, momento de
    extracción), sin reescribir las transformaciones de Drills para
    producir campos canónicos completos -- eso es trabajo futuro,
    explícitamente fuera de alcance de esta fase (ver framework-core-v1.md
    § 15, Deuda técnica).
    """

    object_type: str
    source_system: str
    rows: Any  # hoy: pandas.DataFrame -- el mismo tipo que ya produce extract_drills()
    row_count: int
    extracted_at: datetime


# ---------------------------------------------------------------------------
# Artefactos y métricas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactReference:
    """Referencia a un fichero ya escrito por una etapa -- nunca el
    contenido en sí (evita duplicar en memoria lo que ya está en disco)."""

    name: str
    path: Path
    kind: str
    stage: str
    required: bool = True


@dataclass
class StageMetrics:
    """Métricas de una etapa (Fase 9). Un campo ausente (`None`) significa
    "no aplica a esta etapa" -- nunca se inventa un `0` para una métrica
    que la etapa no mide (p. ej. `excluded_record_count` no aplica a la
    etapa de evidencia)."""

    stage: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    input_record_count: int | None = None
    output_record_count: int | None = None
    excluded_record_count: int | None = None
    warning_count: int | None = None
    error_count: int | None = None
    artifacts_generated: int | None = None


@dataclass
class ExecutionStatistics:
    """Resumen acumulado de toda la ejecución. `per_stage` conserva las
    `StageMetrics` de cada etapa sin fundirlas -- una agregación con
    pérdida de detalle (p. ej. sumar `warning_count` de todas las etapas)
    es responsabilidad de quien consuma este objeto, no de este contrato."""

    per_stage: dict[str, StageMetrics] = field(default_factory=dict)

    @property
    def total_warning_count(self) -> int:
        return sum(m.warning_count or 0 for m in self.per_stage.values())

    @property
    def total_error_count(self) -> int:
        return sum(m.error_count or 0 for m in self.per_stage.values())


# ---------------------------------------------------------------------------
# StageResult
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Resultado de ejecutar UNA etapa. Distingue `success`/`warning`/
    `failure`/`skipped` -- nunca usa una excepción como único canal para
    comunicar un error funcional (Fase 8): un `lookup` sin coincidencia,
    una entidad `do_not_migrate`, una fila excluida, son `issues` dentro
    de un `StageResult`, no excepciones. Las excepciones técnicas no
    controladas (fallo de conexión, error de programación) SÍ deben
    propagarse y detener la ejecución -- este contrato no las intercepta."""

    stage: str
    status: str
    output: Any = None
    issues: list[dict] = field(default_factory=list)
    metrics: StageMetrics | None = None
    artifacts: list[ArtifactReference] = field(default_factory=list)
    duration_seconds: float | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        _check_choice(self.status, StageStatus.ALL, "StageResult.status")

    @property
    def is_blocking(self) -> bool:
        return self.status == StageStatus.FAILURE


# ---------------------------------------------------------------------------
# PipelineStage -- contrato uniforme (Protocol, no ABC: cualquier objeto
# con esta forma sirve, sin obligar a heredar de una clase base del Core)
# ---------------------------------------------------------------------------

@runtime_checkable
class PipelineStage(Protocol):
    """Contrato mínimo de una etapa. `name` identifica la etapa en los
    `StageResult`/métricas; `execute` recibe el contexto compartido y la
    salida de la etapa anterior (`None` para la primera etapa) y devuelve
    un `StageResult` -- nunca lanza una excepción para comunicar un
    resultado funcional (ver `StageResult`)."""

    name: str

    def execute(self, context: "ExecutionContext", stage_input: Any) -> StageResult: ...


# ---------------------------------------------------------------------------
# PipelineDefinition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipelineDefinition:
    """Secuencia declarada de nombres lógicos de etapa -- se resuelve
    contra un `StageRegistry` en tiempo de ejecución, nunca contiene
    instancias de etapa directamente (eso acoplaría la definición a una
    implementación concreta)."""

    name: str
    stages: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.stages:
            raise PipelineConfigurationError(
                f"PipelineDefinition {self.name!r} no declara ninguna etapa."
            )


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Contexto compartido durante una ejecución.

    Distinción explícita entre configuración inmutable y estado mutable
    (pedida por el encargo, para no convertir esto en "un contenedor
    global sin control"):

    - INMUTABLE, fijado una vez al construir el contexto: `execution_id`,
      `request`, `started_at`, `working_dir`, `output_dir`,
      `resolved_config`, `logger`.
    - MUTABLE, se acumula a medida que las etapas se ejecutan:
      `statistics`, `artifacts`, `issues`, `state`.

    `state` es el ÚNICO lugar donde una etapa puede dejar información para
    una etapa posterior que no pase por el propio `stage_input`/`output`
    encadenado (p. ej. la configuración ya cargada del objeto, para no
    volver a leer el YAML en cada etapa). Se documenta como excepción
    deliberada y acotada -- no como un cajón de sastre sin control: cada
    clave que una etapa escriba en `state` debe documentarse en el
    adaptador que la escribe.
    """

    execution_id: str
    request: ExecutionRequest
    started_at: datetime
    working_dir: Path
    output_dir: Path
    logger: Logger
    resolved_config: dict[str, Any] = field(default_factory=dict)
    statistics: ExecutionStatistics = field(default_factory=ExecutionStatistics)
    artifacts: list[ArtifactReference] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PipelineResult
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Resumen de la ejecución completa -- lo que devuelve
    `PipelineOrchestrator.run()`."""

    execution_id: str
    status: str
    stage_results: tuple[StageResult, ...]
    statistics: ExecutionStatistics
    artifacts: tuple[ArtifactReference, ...]
    issues: tuple[dict, ...]
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    output_dir: Path

    def __post_init__(self) -> None:
        _check_choice(self.status, ExecutionStatus.ALL, "PipelineResult.status")
