"""Transformaciones de campo para safety_meetings.Group_Meetings (Sprint 9.7).

Reutiliza deliberadamente, sin copiar, dos funciones de
`src.export.prototype.drills.transformations` que resultaron ser genéricas
pese a su nombre -- mismo criterio ya aplicado por Bypass (Sprint 9.4):

- `to_historical_id`: limpieza de un ID numérico a texto. Cero lógica de
  Drills.
- `resolve_workflow_status`: `IDValor -> lookup`, SIN default para
  ausencia/no-coincidencia (siempre `unresolved`, nunca inventa un valor).
  Es la semántica correcta para los 3 lookups de Safety Meetings
  (`CS_WorkflowStatus`/`CS_Level`/`CS_Letter`) porque ninguna de las hojas
  `Mapeo_Flujos`/`Mapeo_Nivel`/`Mapeo_Letra` del ETL real documenta un
  `nullcontrol` -- a diferencia de `resolve_letter` (que sí exige un
  `null_default` explícito) o `resolve_typology` (que aplica el mismo
  default a ambos casos), aplicar cualquiera de los dos aquí sería inventar
  una regla no evidenciada. El nombre de la función menciona "workflow
  status" pero su cuerpo no tiene ninguna lógica específica de ese campo --
  verificado leyendo su implementación antes de reutilizarla para
  `CS_Level`/`CS_Letter` también.

Esta es la TERCERA vez que un módulo nuevo necesita `to_historical_id`
(Drills, Bypass, ahora Safety Meetings) y ambas funciones de lookup del
mismo fichero (`resolve_letter`/`resolve_workflow_status`, la segunda ahora
reutilizada 3 veces solo en este módulo) -- evidencia relevante para
Sprint 9.8 (ver informe de cierre de Sprint 9.7 § Fase 17): mover
`LookupResult`/`to_historical_id`/`resolve_workflow_status` a
`src.export.engine` ya cruza el umbral de evidencia que Sprint 9.6 fijó
para `_is_missing` ("esperar una 3ª necesidad real antes de mover
código") -- no se mueve en este sprint (fuera de alcance, ver Fase 7).

`passthrough_or_empty` es nueva -- ningún campo de Drills/Bypass usa
exactamente este patrón (sin lookup, sin nullcontrol documentado, solo
"si está vacío, cadena vacía; si no, tal cual")."""
from __future__ import annotations

from src.export.engine.values import is_missing
from src.export.prototype.drills.transformations import (
    LookupResult,
    resolve_workflow_status as resolve_lookup,
    to_historical_id,
)

__all__ = ["LookupResult", "resolve_lookup", "to_historical_id", "passthrough_or_empty"]


def passthrough_or_empty(value) -> LookupResult:
    """Sin tabla de lookup, sin `nullcontrol` documentado: si `value` está
    vacío, se deja explícitamente vacío (`status="empty"`, nunca se inventa
    un literal por defecto); si no, se conserva tal cual (passthrough, sin
    transformación de formato)."""
    if is_missing(value):
        return LookupResult(value="", status="empty", raw_source_value=value)
    text = str(value).strip()
    return LookupResult(value=text, status="resolved", raw_source_value=value)
