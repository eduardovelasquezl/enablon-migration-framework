# Índice de ADR — EMF

**Status:** Approved Design. Índice de referencia rápida — no repite el
contenido de cada ADR, solo su ubicación y estado. La numeración de ADR es
**única en todo el repositorio**: no existen dos ADR con el mismo número en
ninguna carpeta.

## Legado — primer proyecto (Moeve, previo a EMF)

Ubicación: [`docs/architecture/v1.0/decisions/`](../architecture/v1.0/decisions/).
No se renumeran ni se modifican al introducir la secuencia EMF.

| ADR | Título | Status |
|---|---|---|
| [ADR-001](../architecture/v1.0/decisions/ADR-001-migration-object-centric-model.md) | MigrationObject como unidad central del modelo | Implemented |
| [ADR-002](../architecture/v1.0/decisions/ADR-002-mapping-decision-vs-coverage-finding.md) | Separar MappingDecision de MappingCoverageFinding | Implemented |
| [ADR-003](../architecture/v1.0/decisions/ADR-003-action-plans-cross-module.md) | Action Plans como objeto transversal de fase final | Implemented |
| [ADR-004](../architecture/v1.0/decisions/ADR-004-exact-parent-resolution.md) | Resolución exclusivamente exacta de referencias padre | Implemented |
| [ADR-005](../architecture/v1.0/decisions/ADR-005-analysis-export-separation.md) | Separar Analysis Engine de Export Engine | Approved Design |
| [ADR-006](../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md) | Generar CSV en vez de cargar directamente en Enablon | Implemented |

## Producto EMF

Ubicación: [`docs/02-adr/`](.) (este directorio). Continúan el consecutivo
inmediatamente después del número más alto ya usado por la secuencia legada
(`006`) — empiezan en `007`.

| ADR | Título | Status |
|---|---|---|
| [ADR-007](ADR-007-framework-first.md) | Framework First | Approved Design |
| [ADR-008](ADR-008-evidence-first.md) | Evidence First | Approved Design |
| [ADR-009](ADR-009-configuration-over-code.md) | Configuration over Code | Approved Design |
| [ADR-010](ADR-010-no-hidden-state.md) | No Hidden State | Approved Design |
| [ADR-011](ADR-011-extensibility-by-design.md) | Extensibility by Design | Approved Design |
| [ADR-012](ADR-012-source-agnostic-enablon-oriented.md) | Source Agnostic, Enablon Oriented | Approved Design |
| [ADR-013](ADR-013-mappings-as-data.md) | Mappings as Data | Approved Design |
| [ADR-014](ADR-014-canonical-data-model.md) | Canonical Data Model: conjunto de entidades y estrategia de identidad | Proposed (en revisión arquitectónica) |
| [ADR-015](ADR-015-mapping-specification.md) | Mapping Specification: modelo de reglas, conflictos y TransformationTrace | Proposed |
| [ADR-016](ADR-016-framework-core-execution-pipeline.md) | Framework Core: Execution Pipeline, Stage Registry y propagación de errores | Implemented |

## Próximo número disponible

**ADR-017.** Toda ADR nueva, legada o de producto, se numera consecutiva a
partir de aquí — antes de crear una ADR nueva, comprobar este índice para
confirmar el siguiente número libre.

## Relación con el Blueprint

Ver [Blueprint § 5](../00-blueprint/emf-blueprint-v1.0.md#5-principios-de-diseño)
para la tabla de los 14 principios de EMF y cuáles tienen ADR dedicada.
