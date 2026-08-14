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
"si está vacío, cadena vacía; si no, tal cual").

`resolve_start_date` (Micro-sprint 9.10.3) reutiliza `parse_hora`/
`parse_starting_date` de `drills.transformations` -- TRANSITIONAL_CROSS_
MODULE_DEPENDENCY, deliberada y documentada, NO el patrón `_is_missing`
de arriba. La regla `StartDate = Fecha (fecha) + Hora (hora:minuto)` se
verificó para Safety Meetings de forma INDEPENDIENTE (`ITP-SM-DBC`,
10.782 filas reales, `FechaHora` ya materializado en el propio ETL,
10778/10778 exacto -- ver Informe-Micro-Sprint-9.10.2-StartDate-
RootCause-EMF.md) -- no es una copia por analogía, se comprobó que
`parse_hora`/`parse_starting_date` reproducen exactamente ese mismo
resultado (10782/10782, incluidas las 4 filas de `Hora` corrupta que el
propio ETL también rechaza). Es solo la 2ª confirmación real de estas
funciones (Drills, ahora Safety Meetings) -- todavía NO cruza el umbral
de "3ª necesidad real" que Sprint 9.8 exigió para mover código al Engine
compartido, así que se importan tal cual de `drills.transformations` en
vez de moverse. Deuda registrada explícitamente: promover
`parse_hora`/`parse_starting_date` a `src.export.engine` cuando un tercer
módulo real las necesite.

`format_starting_date` (también en `drills.transformations`) NO se
reutiliza aquí -- no soporta el token de segundos (`ss`), solo
`dd/MM/yyyy HH:mm`, y el Output Contract de Safety Meetings exige
`dd/MM/yyyy HH:mm:ss` (verificado con una llamada real: deja el literal
`"ss"` sin sustituir). Formatear con segundos vía `format_starting_date`
sería forzar una función que no lo soporta -- en vez de modificar su
semántica (prohibido explícitamente en este sprint), `resolve_start_date`
formatea el `datetime` ya combinado con `strftime` directamente."""
from __future__ import annotations

from src.export.engine.identifiers import to_historical_id
from src.export.engine.lookups import LookupResult, resolve_workflow_status as resolve_lookup
from src.export.engine.values import is_missing
from src.export.prototype.drills.transformations import parse_hora, parse_starting_date

__all__ = [
    "LookupResult", "resolve_lookup", "to_historical_id", "passthrough_or_empty",
    "resolve_start_date", "parse_hora", "parse_starting_date",
]


def passthrough_or_empty(value) -> LookupResult:
    """Sin tabla de lookup, sin `nullcontrol` documentado: si `value` está
    vacío, se deja explícitamente vacío (`status="empty"`, nunca se inventa
    un literal por defecto); si no, se conserva tal cual (passthrough, sin
    transformación de formato)."""
    if is_missing(value):
        return LookupResult(value="", status="empty", raw_source_value=value)
    text = str(value).strip()
    return LookupResult(value=text, status="resolved", raw_source_value=value)


def resolve_start_date(fecha, hora) -> LookupResult:
    """`StartDate` = `Fecha` (fecha) + `Hora` (hora:minuto) -- Micro-sprint
    9.10.3, regla VERIFIED (ver docstring de módulo). Delega la combinación
    en `parse_starting_date`/`parse_hora` de `drills.transformations`, SIN
    reimplementar su lógica: `Hora` ausente o no interpretable (formato
    corrupto, p. ej. `'10:'`/`'7:000'`) deja el resultado con solo la fecha
    (`00:00:00`) -- nunca se inventa una hora. `Fecha` ausente o no
    interpretable devuelve vacío -- nunca se inventa una fecha."""
    combined = parse_starting_date(fecha, hora)
    if combined is None:
        return LookupResult(value="", status="empty", raw_source_value=fecha)
    formatted = combined.strftime("%d/%m/%Y %H:%M:%S")
    return LookupResult(value=formatted, status="resolved", raw_source_value=fecha)
