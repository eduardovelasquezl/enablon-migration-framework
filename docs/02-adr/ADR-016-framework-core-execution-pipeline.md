# ADR-016 — Framework Core: Execution Pipeline, Stage Registry y propagación de errores

**Status:** Implemented — existe en `src/core/` y
`src/export/prototype/drills/core_adapters.py`, con 47 tests que lo cubren
(`tests/test_core_*.py`, `tests/test_drills_core_pipeline.py`), ver
`docs/01-architecture/framework-core-v1.md`. Primera ADR de producto EMF
(`docs/02-adr/`) en este estado — ADR-007 a ADR-015 siguen en
`Approved Design`/`Proposed`, diseño sin código todavía.

## Context

El Blueprint y `architecture-overview.md` ya describían conceptualmente el
Core y sus Engines, pero sin fijar ningún contrato concreto — `src/core/`
no existía como código. ADR-013/014/015 fijan, respectivamente, que los
mapeos son datos, la forma del Canonical Data Model, y el modelo de la
Mapping Specification — ninguna de las tres fija cómo se **ejecuta**
realmente un pipeline: qué representa una solicitud de ejecución, cómo se
comparte estado entre etapas, cómo se resuelve un nombre lógico de etapa a
una implementación, y cómo se distingue un error técnico de uno funcional
durante la ejecución.

Esta ADR registra esas decisiones, tomadas al implementar el primer
Execution Pipeline real del EMF (`docs/01-architecture/framework-core-v1.md`),
con Drills como primer y único consumidor.

## Decision

1. **Contratos mínimos, no un framework de ejecución general**:
   `ExecutionRequest` (frozen, serializable, sin I/O), `ExecutionContext`
   (con separación explícita entre campos inmutables y mutables),
   `PipelineDefinition` (secuencia de nombres lógicos, nunca instancias),
   `PipelineStage` (un `Protocol`, no una clase base obligatoria),
   `StageResult` (distingue `success`/`warning`/`failure`/`skipped`),
   `PipelineResult`, `ArtifactReference`, `StageMetrics`/
   `ExecutionStatistics`.

2. **`StageRegistry` explícito, sin descubrimiento dinámico**: un nombre
   lógico de etapa se resuelve contra una implementación solo si alguien
   llamó a `.register()` en código auditable — sin `importlib` sobre
   paquetes completos, sin entry points, sin recorrer directorios. Mismo
   principio ya fijado en `extensibility-model.md` § 5 para el futuro
   `ObjectRegistry`, aplicado aquí a etapas de pipeline.

3. **El orquestador no conoce ningún objeto migrable concreto**: verificado
   por inspección de imports (`src/core/*.py` no importa nada de
   `src.export`/`src.etl`/`src.evidence`) — la conexión Core↔Drills vive
   enteramente en `src/export/prototype/drills/core_adapters.py`, fuera
   del Core.

4. **Propagación de errores en tres niveles**: (a) una excepción técnica
   no controlada dentro de `stage.execute()` se propaga sin capturar —
   el orquestador no la intercepta; (b) un error funcional/legado ya
   conocido y documentado (las cuatro excepciones que ya lanzaba
   `pipeline.run()` antes de esta fase) se traduce, en el adaptador
   correspondiente, a `StageResult(status=FAILURE)`; (c) warnings/
   exclusiones/valores no mapeados se representan como `issues` dentro de
   un `StageResult`, nunca como excepciones.

5. **Adaptador temporal permitido y documentado como deuda técnica**:
   cuando separar limpiamente dos responsabilidades ya mezcladas en código
   existente implica reescribir ese código (el caso de
   `pipeline.run()`, que fusiona Mapping+Validation+Export+Manifest+
   Comparison+Issues), se envuelve como una única etapa en vez de forzar
   una separación de alto riesgo — documentado explícitamente, no oculto.

6. **Seam mínimo hacia el CDM (`CanonicalBatch`), no el CDM completo**:
   se introduce un contenedor de nivel de lote, deliberadamente sin
   `CanonicalField`/`Provenance` por fila, para no obligar a reescribir
   las transformaciones de Drills solo para producir una forma canónica
   completa sin un segundo consumidor real que la necesite.

## Consequences

- Un segundo objeto migrable puede registrar sus propias etapas en su
  propio `StageRegistry` sin tocar `src/core/` ni el de Drills — verificado
  por diseño (dos `StageRegistry` no comparten estado, ADR-010).
- El coste de no separar `transform_and_export` en piezas más finas ahora
  es que el Core, hoy, no puede sustituir individualmente "solo la
  validación" o "solo el export" de Drills por una implementación
  genérica — se acepta como deuda técnica explícita, a resolver cuando un
  segundo objeto real fuerce esa separación (principio 8).
- Cualquier etapa nueva que necesite comunicar un resultado ambiguo debe
  usar el vocabulario `StageStatus` ya fijado (`success`/`warning`/
  `failure`/`skipped`) — no se introduce un quinto estado sin revisar esta
  ADR.
- La modificación aditiva de `pipeline.run()` (tres parámetros opcionales
  nuevos) sienta el precedente de cómo integrar código legado con el Core
  sin reescribirlo: parámetros opcionales con default `None` que
  preservan el comportamiento exacto cuando se omiten, verificado con un
  test de regresión byte a byte.

## Alternatives Rejected

- **Reescribir `pipeline.py` para separar limpiamente Mapping/
  Validation/Export/Manifest en etapas independientes ya en esta fase.**
  Rechazado: alto riesgo de romper el comportamiento ya verificado con
  datos reales (`outputs/prototype/drills/20260723T195418Z/`), sin un
  segundo consumidor que justifique el coste de la separación fina ahora
  mismo (principio 8, y prohibición expresa del encargo de "no realizar
  una reescritura completa del prototipo").
- **Un `StageRegistry` global de módulo, con `register()` a nivel de
  paquete.** Rechazado por el mismo motivo que ADR-010 ya rechazó un
  `ObjectRegistry` global: impediría que dos ejecuciones (o dos tests) con
  registros de etapas distintos convivan en el mismo proceso sin
  interferirse.
- **Descubrimiento dinámico de etapas** (escanear `src/export/` buscando
  clases que implementen `PipelineStage`). Rechazado explícitamente por el
  encargo — un registro implícito por convención de nombres/ubicación es
  más difícil de auditar que una llamada expresa a `.register()`.
- **Convertir todo error en `StageResult`, incluidas las excepciones
  técnicas.** Rechazado: ocultaría fallos de programación/infraestructura
  detrás de un resultado aparentemente controlado — el encargo exige
  explícitamente que las excepciones técnicas no controladas detengan la
  ejecución de forma visible.
- **Adoptar ya el Canonical Data Model completo por fila** (`CanonicalField`
  con `Provenance` por columna) para esta primera integración. Rechazado:
  exigiría reescribir `_transform_rows` completo sin que ningún segundo
  Connector real exista todavía para validar que la forma elegida es la
  correcta — mismo criterio ya aplicado en `canonical-data-model.md` y
  `ADR-014` para no generalizar sin evidencia.
