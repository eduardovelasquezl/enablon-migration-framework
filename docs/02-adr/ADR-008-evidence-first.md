# ADR-008 — Evidence First

**Status:** Approved Design (principio ya aplicado en la práctica desde el
inicio del proyecto — ver `CLAUDE.md`; formalizado aquí como decisión de
producto para todo EMF, no solo para el proyecto Moeve).

## Context

`CLAUDE.md` ya documenta, como restricción no negociable del proyecto
Moeve, que "nunca se inventan reglas de negocio no documentadas" y que todo
hallazgo debe marcarse con su estado real (`confirmed` / `inferred` /
`pending` / `conflicting`). El Evidence Engine v0.1 (`src/evidence/`) ya
implementa una parte de esto para Drills: nunca vuelve a consultar SQL
Server, construye el Excel de revisión exclusivamente a partir de los
artefactos ya escritos (`validation_report.yaml`, `export_manifest.yaml`,
`comparison_report.yaml`, `issues.jsonl`). La pregunta de esta ADR es si
este principio se mantiene como una decisión de EMF como producto, más allá
del proyecto Moeve.

## Decision

Evidence First se adopta como principio de producto: **ninguna afirmación
de negocio (un mapeo aplicado, una regla de exclusión, un valor calculado)
se acepta en EMF sin evidencia trazable a su origen**, y esa trazabilidad
se conserva desde la extracción (campo `provenance`, ver
[`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md)
§ 3) hasta el manifiesto final de cada ejecución. El Evidence Engine, al
generalizarse más allá de Drills, conserva su restricción actual más
importante: **nunca vuelve a consultar la fuente original** — construye
evidencia solo a partir de artefactos ya persistidos por el pipeline.

Para fuentes documentales (Word/PDF), Evidence First se extiende
explícitamente a exigir el nivel de confianza y la señal de revisión
humana descritos en
[`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md)
§ 3 — no basta con "de dónde vino el dato", también hace falta "con qué
certeza se extrajo".

## Consequences

- Todo Connector nuevo debe poblar `provenance` de forma honesta desde el
  primer commit — no es un campo que se pueda añadir "después".
- Todo Engine nuevo que module datos de negocio (Mapping, Transformation)
  debe dejar rastro de qué regla aplicó y con qué evidencia — no basta con
  el valor final.
- El Evidence Engine genérico no podrá, por diseño, ser más rápido que "leer
  los artefactos ya escritos" — no se permite un atajo que vuelva a tocar
  la fuente para "completar" evidencia faltante; si falta, se reporta como
  falta.

## Alternatives Rejected

- **Generar evidencia bajo demanda, re-ejecutando parte del pipeline sobre
  la fuente.** Rechazado: reintroduce dependencia de red/credenciales en un
  paso que hoy es, deliberadamente, offline y determinista — y arriesga
  que la evidencia generada no corresponda exactamente a los datos que
  produjeron el CSV real si la fuente cambió entre medias.
