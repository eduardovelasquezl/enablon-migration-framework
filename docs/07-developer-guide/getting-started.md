# Developer Guide — Getting Started con EMF

**Status:** Approved Design (guía de orientación; los pasos operativos de
instalación/ejecución concretos siguen viviendo en
[`README.md`](../../README.md) raíz — no se duplican aquí).

Esta guía es para quien va a **extender** EMF (añadir un Connector, un
Engine, un Plugin) — no para quien solo necesita ejecutar una exportación
ya existente (eso es [`08-user-guide/README.md`](../08-user-guide/README.md)).

## 1. Antes de escribir código

Lee, en este orden:

1. [Blueprint](../00-blueprint/emf-blueprint-v1.0.md) — visión y
   principios.
2. [`architecture-overview.md`](../01-architecture/architecture-overview.md)
   — capas y componentes.
3. [`extensibility-model.md`](../01-architecture/extensibility-model.md) —
   qué se añade y qué no se toca para tu caso concreto.
4. [`engineering-standards.md`](../03-engineering-standards/engineering-standards.md)
   y [`security-standards.md`](../03-engineering-standards/security-standards.md).
5. [`CLAUDE.md`](../../CLAUDE.md) — memoria operativa del proyecto Moeve, si
   tu trabajo toca algo relacionado con ese proyecto concreto.

## 2. Entorno local

Ver [`README.md`](../../README.md) § 3 para requisitos e instalación
(Python, `.venv`, `requirements.txt`, `.env`). No se repite aquí para no
duplicar y arriesgar que ambos documentos diverjan.

Si tu componente necesita datos reales de migración (ETL, CSV de Enablon,
mappings, catálogos), esos datos **nunca viven dentro del repositorio** —
ver
[`external-data-workspace.md`](../01-architecture/external-data-workspace.md)
para el workspace externo (`EMF_DATA_ROOT`) y
[`local-data-recovery-checklist.md`](local-data-recovery-checklist.md)
para el procedimiento de recuperación tras el incidente de Sprint 6.

## 3. Antes de escribir un componente nuevo, responde

- **¿En qué capa vive?** (Core / Engine / Connector / Plugin / Project
  Configuration) — ver
  [`architecture-overview.md`](../01-architecture/architecture-overview.md).
  Si no lo tienes claro, probablemente sea Project Configuration (lo
  específico de un proyecto) o un Plugin (lo específico de un objeto).
- **¿Existe ya un segundo consumidor real, o solo lo necesita Drills/Moeve
  hoy?** Si es lo segundo, probablemente no debas generalizarlo todavía
  (principio 8, "No Abstraction Without a Real Consumer") — constrúyelo
  donde ya vive el primer consumidor (hoy, dentro de
  `src/export/prototype/drills/`), no en una capa nueva especulativa.
- **¿Toca al Core?** Si tu cambio necesita que el Core conozca un cliente,
  un objeto o un formato concreto, no es un cambio del Core — es un cambio
  de una capa superior. Revisa
  [ADR-007](../02-adr/ADR-007-framework-first.md).
- **¿Cómo se prueba sin red?** Ver
  [`testing-standards.md`](../03-engineering-standards/testing-standards.md)
  antes de escribir el primer test.

## 4. Estado real del código hoy (no confundir con la arquitectura objetivo)

| Lo que existe hoy | Dónde | Generalizado? |
|---|---|---|
| Conexión SQL de solo lectura | `src/db/` | No — es el único Connector, sin interfaz formal |
| Query Runner | `src/db/query_runner.py` | Parcial — reutilizable, sin abstracción de "Connector" todavía |
| Query Engine v0.1 | `src/query/` | No — catálogo cerrado específico de Drills |
| Prototype Export de Drills | `src/export/prototype/drills/` | No — SQL→CSV íntegramente específico de Drills |
| Evidence Engine v0.1 | `src/evidence/` | No — limitado a Drills |
| Core | `src/core/` | **No existe todavía** — Approved Design (Sprint 4.1) |

Si tu tarea es "añadir algo nuevo al framework", parte de este estado real,
no de la arquitectura objetivo del Blueprint — la arquitectura objetivo
describe hacia dónde se evoluciona, no un punto de partida ya disponible.

## 5. Flujo de trabajo recomendado por incremento

1. Confirmar alcance y capa afectada antes de escribir código (ver § 3).
2. Si el incremento introduce una decisión estructural nueva, escribir su
   ADR en [`02-adr/`](../02-adr/) **antes** de implementar (principio 10).
3. Implementar en pasos pequeños, cada uno con su propia verificación de
   suite completa (ver [`testing-standards.md`](../03-engineering-standards/testing-standards.md)).
4. Cerrar el incremento con una revisión de sprint (copiar
   [`sprint-review-template.md`](../05-sprint-reviews/sprint-review-template.md)).
5. No hacer commit sin aprobación explícita del resultado.

## 6. Dudas de terminología

Antes de nombrar algo nuevo, consulta la tabla de
[terminología del Blueprint](../00-blueprint/emf-blueprint-v1.0.md#terminología--no-confundir)
— evita en particular el error más común: llamar "módulo" a un componente
de software (fuera del sentido estricto de Python de "fichero `.py`") cuando
el proyecto ya usa "módulo" para el sentido de negocio de Enablon
(Simulacros, MOC...).
