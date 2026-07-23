# Specifications v1.0

## Propósito

`docs/specifications/` es donde vive la especificación **funcional** de lo
que el framework producirá — en contraste con `docs/architecture/`, que
documenta cómo está construido y qué hace hoy. Specifications v1.0 es la
primera versión de esta capa: por ahora contiene una única familia,
[`export/`](export/README.md) (Export Specifications v1.0), centrada en
inventariar la evidencia disponible para una futura generación de CSV de
importación a Enablon.

## Relación con Architecture v1.0

[`docs/architecture/v1.0/`](../../architecture/v1.0/README.md) es la
referencia de lo que **existe** (Implemented), lo que está **aprobado pero
no construido** (Approved Design — el Export Engine completo,
ver [`export_engine.md`](../../architecture/v1.0/export_engine.md)) y lo
que está **planificado** (Planned, ver
[`roadmap.md`](../../architecture/v1.0/roadmap.md)).

Specifications v1.0 no reemplaza ni modifica Architecture v1.0 — se apoya
en ella. Concretamente:

- Toma como dado el modelo de dominio de
  [`domain_model.md`](../../architecture/v1.0/domain_model.md) (no lo
  redefine).
- Respeta la separación de capas de
  [ADR-005](../../architecture/v1.0/decisions/ADR-005-analysis-export-separation.md):
  el Export Engine consume `ProjectAnalysisResult`, nunca al revés.
- Precede al diseño de
  [`export_engine.md`](../../architecture/v1.0/export_engine.md) con el
  trabajo de evidencia que ese documento exige antes de generar cualquier
  CSV ("Generar CSV sin esa plantilla sería inventar un formato").

## Separación entre especificación e implementación

Una especificación en `docs/specifications/` describe **qué** debe
producirse y **con qué evidencia** se justifica cada decisión — nunca
código ejecutable, nunca una clase de dominio nueva, nunca una plantilla de
Enablon inventada. La implementación (código en `src/`) solo ocurre después,
en un incremento separado, y solo sobre una especificación ya aprobada.
Esta separación es deliberada: permite que el cliente valide una decisión
funcional (p. ej. "esta es la plantilla real de importación de Events")
antes de que exista una sola línea de código que dependa de ella.

## Principio basado en evidencias

Toda regla de exportación propuesta en cualquier documento bajo
`docs/specifications/` debe estar respaldada por al menos una de estas
evidencias: template CSV real de Enablon, CSV previamente utilizado y
validado, ETL validado, SQL de extracción utilizado, mapping documentado,
configuración real de Enablon, documentación oficial, decisión funcional
aprobada, o regla documentada del cliente. Donde la evidencia no alcanza,
la regla se marca `evidence_pending` — nunca se completa por inferencia
disfrazada de hecho. Ver la taxonomía completa en
[`export/evidence/evidence_catalog.yaml`](export/evidence/evidence_catalog.yaml).

## Familias futuras de especificaciones

Specifications v1.0 contiene hoy una sola familia
([`export/`](export/README.md)). El mismo patrón (evidencia → inventario →
matriz de preparación → especificación por objeto) podría extenderse en el
futuro a otras familias — por ejemplo, especificaciones de validación de
calidad de dato previas a carga, o de versionado de esquema (Fase 6 del
[roadmap](../../architecture/v1.0/roadmap.md)) — pero ninguna otra familia
existe todavía. No crear carpetas para familias futuras hasta que exista
evidencia concreta que las justifique.

## Índice

- [`export/README.md`](export/README.md) — Export Specifications v1.0.
