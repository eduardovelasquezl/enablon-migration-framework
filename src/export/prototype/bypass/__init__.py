"""Prototype Export — bypass.By_Passes (Sprint 9.4).

Segundo módulo real del EMF, replicando el patrón vertical ya validado
por `src.export.prototype.drills` (SQL -> transformación -> mapping ->
validación -> CSV). Reutiliza deliberadamente piezas genéricas de
`drills.transformations`/`drills.exporter`/`drills.manifest` que no
tienen ninguna lógica específica de Drills (ver
`docs/07-developer-guide/bypass-module.md` § 6 para la clasificación
completa REUSED_AS_IS / MODULE_SPECIFIC / DUPLICATED_FROM_DRILLS /
CORE_GAP) -- no es un Export Engine genérico todavía, esa generalización
sigue siendo trabajo futuro documentado, no de este incremento.
"""
