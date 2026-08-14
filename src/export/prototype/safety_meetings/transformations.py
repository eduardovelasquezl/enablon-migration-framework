"""Transformaciones de campo para safety_meetings.Group_Meetings (Sprint 9.7).

Reutiliza deliberadamente dos funciones genéricas del Export Engine:

- `to_historical_id`: limpieza de un ID numérico a texto. Cero lógica de
  ningún módulo concreto.
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

Hasta Sprint 9.8, ambas funciones se importaban de
`src.export.prototype.drills.transformations` -- esta fue la TERCERA vez
que un módulo nuevo las necesitaba (Drills, Bypass, ahora Safety
Meetings), lo que cruzó el umbral de evidencia que Sprint 9.6 fijó para
`_is_missing` ("esperar una 3ª necesidad real antes de mover código").
Sprint 9.8 movió `LookupResult`/`to_historical_id`/
`resolve_workflow_status`/`resolve_letter` a
`src.export.engine.identifiers`/`src.export.engine.lookups`; Safety
Meetings ya no importa nada de `drills` para utilidades genéricas.

`passthrough_or_empty` es nueva -- ningún campo de Drills/Bypass usa
exactamente este patrón (sin lookup, sin nullcontrol documentado, solo
"si está vacío, cadena vacía; si no, tal cual")."""
from __future__ import annotations

from src.export.engine.identifiers import to_historical_id
from src.export.engine.lookups import LookupResult, resolve_workflow_status as resolve_lookup
from src.export.engine.values import is_missing

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
