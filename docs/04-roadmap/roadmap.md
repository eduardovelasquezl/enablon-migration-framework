# Roadmap — EMF

**Status:** Approved Design. Relación explícita con el
[roadmap legado](../architecture/v1.0/roadmap.md) en la sección 2 — léela
antes de asumir que este roadmap sustituye al anterior; lo reencuadra, no lo
invalida.

## 1. Fases del producto EMF

### Fase P1 — Core Foundation
**Status: Approved Design (Sprint 4.1), no implementado**

`src/core/`: excepciones comunes, `FrameworkVersion`, `ObjectMetadata`,
`FrameworkContext`, `ObjectRegistry`, logging común. Sin conocimiento de
ningún cliente, objeto ni fuente. Ver informe de diseño de Sprint 4.1 y
este propio conjunto documental (`docs/00-blueprint/` a `docs/08-user-guide/`)
como los dos entregables de esta fase hasta ahora.

### Fase P2 — Primer Engine generalizado
**Status: Planned**

Extraer un primer Engine genérico (candidato: Validation Engine o Export
Engine, a decidir con su propia ADR) a partir de su implementación actual
acoplada a Drills, demostrando que el Core soporta un segundo consumidor
real sin cambiar. Criterio de entrada: el Core de la Fase P1 debe estar
implementado y probado antes de empezar esta fase.

### Fase P3 — Segundo Connector
**Status: Planned**

Implementar el primer Connector no-SQL (candidato: Excel como fuente de
registros migrables, distinto del uso actual como fuente de mapeos — o
CSV, por ser el más simple estructuralmente). Valida el Modelo de Datos
Canónico con una segunda fuente real.

### Fase P4 — Primer Plugin extraído
**Status: Planned**

Extraer Drills como el primer Plugin real registrado en el `ObjectRegistry`
del Core, con su Connector, sus mapeos como datos (Excel, según
[ADR-013](../02-adr/ADR-013-mappings-as-data.md)) y su entrada en el
Enablon Template Registry. Es el punto en el que Drills deja de ser un caso
especial hardcodeado y pasa a ser una instancia del modelo general.

### Fase P5 — Segundo objeto migrable
**Status: Planned**

Incorporar un segundo objeto de Enablon (candidato: Events/Eventos, ya
analizado en `docs/specifications/v1.0/export/`) como segundo Plugin,
validando que el Fase P4 realmente generaliza sin reescribir Engines.

### Fase P6 — Fuentes documentales
**Status: Planned**

Primer Connector de Word y/o PDF, con el modelo de `provenance` completo
(confianza, revisión humana) descrito en
[`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md)
§ 3. Depende de que el Modelo de Datos Canónico (Fase P3) ya esté validado
con al menos una fuente estructurada no-SQL.

### Fase P7 — AI Assistant
**Status: Planned, sin diseño detallado**

Misma posición y mismo grado de indefinición que la Fase 7 del roadmap
legado — se reserva el nombre y la posición al final del pipeline, sin
comprometer ninguna capacidad concreta todavía.

## 2. Relación con el roadmap legado

El [roadmap legado](../architecture/v1.0/roadmap.md) (Fases 1-7: Knowledge
Engine, Project Analysis, Export Engine, Validation, Repository, Versioning,
AI Assistant) describe el **primer proyecto** (Moeve, previo a EMF como
plataforma) y sigue vigente para ese alcance — no se retira ni se
contradice. Relación conceptual, no de sustitución:

| Fase legada | Aporta a la fase EMF |
|---|---|
| Fase 1 — Knowledge Engine | Base conceptual del futuro Extraction Engine + Canonical Data Model (P3) — el modelo catálogo/relaciones/evidencia ya resuelto para SQL/Excel se generaliza, no se descarta. |
| Fase 2 — Project Analysis | Precedente directo de cómo debe comportarse un futuro Mapping/Validation Engine genérico a nivel de proyecto completo, no solo de un objeto. |
| Fase 3 — Export Engine (Approved Design legado) | Mismo componente conceptual que el Export Engine de EMF (P2/P4) — el diseño legado (`ExportPlan`/`ExportDefinition`/CSV Generator-Writer-Validator) es la base directa a generalizar, no se rediseña desde cero. |
| Fase 4 — Validation | Mismo componente conceptual que el Validation Engine de EMF (P2). |
| Fase 5 — Repository | Persistencia definitiva del Knowledge Repository — sigue siendo Planned en ambos roadmaps, sin fase EMF asignada todavía (candidata a una fase P8 futura). |
| Fase 6 — Versioning | Aporta directamente a `FrameworkVersion`/`application_version` (Fase P1, ya con diseño de Core) y al futuro `template_version` del Enablon Template Registry. |
| Fase 7 — AI Assistant | Misma fase, mismo nombre, misma posición — Fase P7 de este roadmap. |

## 3. Criterio de secuencia

Las fases P1-P7 son una secuencia de **dependencia real**, no solo de
prioridad: P2 no puede empezar sin que P1 esté implementado y probado (el
Core debe existir antes de que un Engine pueda depender de él); P5 no puede
empezar sin P4 (no hay "segundo objeto" sin que el primero ya esté
extraído como Plugin genérico). No se paralelizan fases que dependan
directamente entre sí.

## 4. Fuera de esta secuencia

Multi-tenencia, API, UI: sin fase asignada, igual tratamiento que en el
roadmap legado (mencionados como pendientes, sin comprometerlos a un número
de fase) — se asignarán cuando exista una necesidad real que las priorice,
no antes.
