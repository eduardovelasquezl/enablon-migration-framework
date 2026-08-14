"""Prototype Export — bypass.By_Passes (Sprint 9.4).

Segundo módulo real del EMF, replicando el patrón vertical ya validado
por `src.export.prototype.drills` (SQL -> transformación -> mapping ->
validación -> CSV). Construido originalmente reutilizando piezas
genéricas de `drills.transformations`/`drills.exporter`/`drills.manifest`
sin lógica específica de Drills (ver
`docs/07-developer-guide/bypass-module.md` § 6 para la clasificación
completa REUSED_AS_IS / MODULE_SPECIFIC / DUPLICATED_FROM_DRILLS /
CORE_GAP). Esas piezas viven ahora en `src.export.engine` (manifest/config/
extractor/validator/query_stage desde Sprint 9.6; identifiers/lookups/
writer desde Sprint 9.8) -- Bypass ya no importa nada de `drills` para
utilidades genéricas.
"""
