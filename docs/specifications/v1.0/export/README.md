# Export Specifications v1.0

> Ver también [`../README.md`](../README.md) (Specifications v1.0 en
> general) y [`../../../architecture/v1.0/export_engine.md`](../../../architecture/v1.0/export_engine.md)
> (el diseño aprobado que este incremento precede, no implementa).

## Objetivo de este incremento

Antes de diseñar el Export Engine (ExportPlan, ExportDefinition, CSV
Generator/Writer/Validator — hoy solo Approved Design, ver
[`export_engine.md`](../../../architecture/v1.0/export_engine.md)), este
incremento responde una pregunta previa y más básica: **¿qué evidencia real
existe hoy en el repositorio que respalde, objeto por objeto, la futura
generación de un CSV de importación a Enablon?**

Principio obligatorio heredado de las instrucciones de este incremento:
nada se implementa si antes no está especificado, y nada se especifica
como definitivo si no existe evidencia. Donde la evidencia no alcanza, el
elemento se marca `evidence_pending` — nunca se completa por inferencia
disfrazada de hecho.

## Alcance de este primer incremento

**Incluye:**

- Inventario técnico y funcional de toda evidencia relacionada con
  exportación (`evidence_inventory.md` + `evidence/evidence_catalog.yaml`).
- Inventario de `MigrationObject` reconocidos por el repositorio
  (`migration_object_inventory.md`).
- Matriz de preparación para especificación, no para carga
  (`export_readiness_matrix.md`).
- Evaluación separada de Action Plans como objeto transversal
  (`action_plans_assessment.md`).
- Preguntas abiertas agrupadas por alcance (`open_questions.md`).
- Diagrama del flujo evidencia → especificación
  (`diagrams/evidence_to_specification_flow.mmd`).

**NO incluye** (explícitamente fuera de alcance de este incremento):

- Export Engine, `ExportPlan`, `ExportDefinition` ejecutable.
- Generador o validador de CSV.
- Persistencia de ningún catálogo.
- Interfaces de usuario.
- Carga directa en Enablon (API o UI) — restricción heredada de
  [ADR-006](../../../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md),
  vigente para todo el proyecto, no solo para este incremento.
- Especificaciones definitivas por objeto (`Event.yaml`, `ActionPlan.yaml`
  o equivalentes) — vendrán en un incremento posterior, una vez cerradas
  las preguntas abiertas de mayor prioridad.
- Templates de Enablon inventados — donde no existe una plantilla de
  importación confirmada, se documenta como tal (ver
  `evidence_inventory.md` §3), nunca se sustituye por una suposición.

## Elementos implementados y planificados

| Elemento | Estado en este incremento |
|---|---|
| Inventario de evidencia | Implementado (documental) |
| Inventario de MigrationObject | Implementado (documental) |
| Matriz de preparación | Implementado (documental) |
| Evaluación de Action Plans | Implementado (documental) |
| Preguntas abiertas | Implementado (documental) |
| `ExportPlan` / `ExportDefinition` ejecutables | Planned — depende de cerrar las preguntas de prioridad Alta de `open_questions.md`, especialmente las de grupo "Templates Enablon" |
| Especificación definitiva por objeto (`Event.yaml` etc.) | Planned — siguiente incremento sugerido, ver [`closing_recommendation.md`](closing_recommendation.md) |

## Criterio para pasar de inventario a especificación

Un `MigrationObject` puede pasar de este inventario a una especificación
definitiva por objeto solo cuando:

1. Su `specification_readiness` en `export_readiness_matrix.md` sea
   `ready_for_draft` (nunca desde `partially_ready`, `evidence_pending` o
   `blocked` sin antes resolver la brecha documentada).
2. Exista al menos un template o export real confirmado
   (`template_status` ≥ `candidate`, idealmente `validated` una vez el
   cliente confirme un template de importación real — ver `open_questions.md`
   grupo "Templates Enablon").
3. Las preguntas abiertas de prioridad **Alta** asociadas a ese objeto
   específico en `open_questions.md` estén resueltas o explícitamente
   aceptadas como riesgo por el cliente.

Ningún objeto de este inventario cumple hoy la condición 2 en su forma más
estricta (`validated`) — ver `evidence_inventory.md` §3. Los candidatos más
cercanos a poder iniciar un borrador son `simulacros.Drills`,
`moc.Change_Register`, `bypass.By_Passes` e `inspecciones.Observations`,
por ser los de mayor cobertura de evidencia y menor número de preguntas
abiertas de prioridad Alta asociadas.
