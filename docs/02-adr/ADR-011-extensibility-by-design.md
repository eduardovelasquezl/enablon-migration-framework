# ADR-011 — Extensibility by Design

**Status:** Approved Design

## Context

El proyecto ha vivido hasta ahora con un único cliente, un único conector de
fuente (SQL Server) y un único objeto con flujo ejecutable (Drills). El
Blueprint exige que EMF pueda incorporar módulos de Enablon, bases de datos,
clientes, mapeos, reglas, formatos de entrada/salida y conectores nuevos sin
modificar el Core. Esta ADR fija cómo se garantiza eso sin caer en
sobrediseño (principio 8, con el que esta ADR mantiene tensión directa y
deliberada).

## Decision

La extensibilidad de EMF se logra por **capas con dirección de dependencia
fija** (ver
[`architecture-overview.md`](../01-architecture/architecture-overview.md)),
no por un mecanismo de plugins genérico construido de antemano. Añadir
capacidad significa añadir un componente en la capa correspondiente
(Connector, Engine, Plugin, Project Configuration), nunca modificar una
capa inferior a la que se está extendiendo.

El mecanismo concreto de registro (hoy: `ObjectRegistry` del Core, Sprint
4.1) se mantiene deliberadamente mínimo hasta que exista un segundo
consumidor real: sin carga dinámica de plugins, sin registro automático
desde YAML, sin interfaz formal de Connector todavía (ver
[`extensibility-model.md`](../01-architecture/extensibility-model.md) § 5
para el detalle completo de qué se pospone y por qué).

## Consequences

- Cada extensión real (un Connector nuevo, un objeto nuevo, un cliente
  nuevo) es la oportunidad de validar si el mecanismo de extensión diseñado
  hasta ese momento realmente generaliza, o si hacía falta ajustarlo — y
  eso se documenta como una ADR nueva si cambia algo estructural (principio
  10), no como una modificación silenciosa.
- El coste de este enfoque es que, en este sprint, EMF **no tiene todavía**
  un segundo Connector, un segundo Plugin ni un segundo Project
  Configuration reales — la extensibilidad está probada arquitectónicamente
  (por diseño y por la disciplina de capas) pero no demostrada
  empíricamente todavía. Eso se marca honestamente en cada documento como
  "Approved Design", no como "Implemented".

## Alternatives Rejected

- **Diseñar y construir ahora un sistema de plugins completo (entry points,
  descubrimiento automático, carga dinámica) anticipando necesidades
  futuras.** Rechazado por el principio 8 — sin un segundo Plugin real
  hoy, cualquier interfaz de plugin se diseñaría a ciegas y con alta
  probabilidad de tener que rehacerse en cuanto aparezca el primer caso
  real.
