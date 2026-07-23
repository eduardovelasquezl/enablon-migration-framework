# ADR-005 — Separar Analysis Engine de Export Engine

**Status:** Approved Design (la separación en sí es un principio arquitectónico
ya aplicado en el código existente; el Export Engine todavía no existe)

## Context

El Knowledge Engine (schema/query analysis, mapping resolution, coverage,
module/project analysis) ya determina con certeza qué está listo para carga y
por qué. Añadir generación de CSV de importación dentro de esos mismos
componentes acoplaría dos responsabilidades muy distintas: **decidir** (basado
en evidencia, iterativo, sin plantilla externa) y **dar forma de salida**
(basado en una plantilla real de Enablon, que puede cambiar sin que cambie
ninguna decisión de negocio).

## Decision

El Export Engine (`ExportPlan`, `ExportDefinition`, CSV Generator/Writer/
Validator, `ExportPackage`) se diseña como una capa consumidora de
`ProjectAnalysisResult`, nunca al revés. El Knowledge Engine no conoce el
formato de ningún CSV de importación real; el Export Engine no vuelve a
decidir si un registro está listo, ni recalcula mappings o cobertura.

## Consequences

- Un cambio de plantilla de Enablon (nueva columna, nuevo formato de fecha) no
  requiere tocar ningún componente del Knowledge Engine.
- El Export Engine puede posponerse indefinidamente sin bloquear el resto del
  framework — de hecho, así ha sido durante todo este proyecto hasta ahora.
- Obliga a que `ProjectAnalysisResult` contenga toda la información que el
  Export Engine necesitará, sin que este tenga que volver a consultar Excel/SQL.

## Alternatives Rejected

- **Generar el CSV directamente desde `project_analysis.py`.** Rechazado:
  mezclaría la orquestación de análisis con el formato de salida, y
  obligaría a tener una plantilla validada antes de poder avanzar en el
  análisis — exactamente la dependencia que se quiere evitar.
