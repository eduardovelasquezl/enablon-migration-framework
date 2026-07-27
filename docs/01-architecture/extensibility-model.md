# Extensibility Model — EMF

**Status:** Approved Design. Complementa
[`architecture-overview.md`](architecture-overview.md) — léelo primero para
el mapa de capas.

Este documento responde a una pregunta concreta por cada tipo de extensión:
**¿qué hay que añadir, y qué está explícitamente prohibido tocar, para
incorporar X?**

## 1. Añadir una fuente nueva (Connector)

**Qué se añade**: un nuevo Connector que sabe leer esa fuente
(Word, PDF, un ERP distinto, otra base de datos) y producir Registros
Normalizados en el Modelo de Datos Canónico
(ver [`data-processing-lifecycle.md`](data-processing-lifecycle.md)).

**Qué NO se toca**: el Core, ningún Engine (Mapping, Transformation,
Validation, Export, Evidence...), ningún Connector existente, ningún
Plugin existente. Los Engines consumen Registros Normalizados — nunca
consultan "de dónde vinieron" para decidir su comportamiento (más allá de
leer el campo `provenance`, que es parte del propio modelo canónico, no un
`if source == "sql"`).

**Riesgo si se viola**: si un Engine necesita un `if isinstance(source,
SqlSource)` para funcionar, esa fuente no está realmente desacoplada —
señal de que el Connector no está devolviendo una forma canónica completa.

## 2. Añadir un objeto migrable nuevo (Plugin)

**Qué se añade**: una `ObjectMetadata` registrada en el `ObjectRegistry`
del Core (diseño de Sprint 4.1) + su configuración (mapeos como datos,
plantilla de destino en el Enablon Template Registry) + el Connector que ya
exista para su fuente (o uno nuevo, ver punto 1 si hace falta).

**Qué NO se toca**: el Core no cambia (el Registry ya admite cualquier
`object_id` sin código nuevo), ningún otro Plugin, ningún Engine genérico.

**Ejemplo con datos reales**: incorporar Events (Eventos) como segundo
objeto no debería requerir ninguna línea nueva en `src/core/` ni en un
futuro `src/engines/export/`. Solo: su `ObjectMetadata`, sus mapeos (Excel,
según [ADR-013](../02-adr/ADR-013-mappings-as-data.md)), y su entrada en el
Enablon Template Registry.

## 3. Añadir un cliente/proyecto nuevo (Project Configuration)

**Qué se añade**: una nueva raíz de configuración (equivalente a
`config/*.yaml` + `sql/source_queries/` + `.env` de Moeve, pero para el
cliente nuevo), sus propios mapeos, sus propias credenciales.

**Qué NO se toca**: nada de las capas inferiores. Ni el Core, ni los
Engines, ni los Connectors, ni siquiera los Plugins si el cliente nuevo usa
los mismos objetos migrables que uno existente (dos clientes pueden
compartir el Plugin "Drills" con mapeos distintos).

**Multi-tenencia**: fuera de alcance de diseño detallado en esta versión
(ver Blueprint § 4) — el modelo de capas lo anticipa (Project Configuration
es explícitamente la capa más externa y aislable), pero el aislamiento real
de credenciales/ejecución entre proyectos concurrentes no está diseñado
todavía.

## 4. Añadir un formato de salida nuevo

Hoy el único contrato de salida es "CSV de importación de Enablon" (Blueprint
§ 11/12 principio "Source Agnostic, Enablon Oriented",
[ADR-012](../02-adr/ADR-012-source-agnostic-enablon-oriented.md)). Un
formato de salida adicional (por ejemplo, un reporte de auditoría en otro
formato, no un CSV de carga) se trataría como un Engine de salida
alternativo, consumidor del mismo registro mapeado/transformado/validado —
no está diseñado en detalle en esta versión por no tener consumidor real
todavía (principio 8).

## 5. Qué NO se generaliza todavía, y por qué (principio 8)

Explícitamente pospuesto, con su justificación:

| No se implementa todavía | Por qué |
|---|---|
| Carga dinámica de plugins (entry points de Python, descubrimiento automático) | Solo hay un Plugin de facto (Drills, sin extraer) — generalizar el mecanismo de carga sin un segundo Plugin real sería adivinar la interfaz. |
| Registro de objetos desde YAML (`config/objects.yaml` poblando el `ObjectRegistry` automáticamente) | Requiere primero que el Registry tenga un consumidor real (ver informe de Sprint 4.1, § "Recomendación sobre registrar Drills"); no se diseña la carga declarativa antes de la programática. |
| Interfaz formal de Connector (clase base / Protocol) | Con un único Connector real (SQL Server, acoplado a Drills) no hay todavía dos implementaciones que permitan extraer la interfaz común sin adivinar sus métodos. |
| Enablon Template Registry como componente de código | Existe conceptualmente (Blueprint § 11) pero con una sola plantilla real gestionada (Drills, dentro de `config/exports/drills.yaml`) no hay evidencia suficiente de qué variará entre plantillas para diseñar el esquema del Registry con confianza. |
| Aislamiento multi-cliente en tiempo de ejecución | Sin un segundo proyecto real, cualquier diseño de aislamiento sería especulativo. |

La regla general: **una capa se generaliza cuando existe un segundo caso
real que la necesita**, nunca antes. Esto es consistente con cómo se
construyó todo lo que existe hoy (Query Engine y Evidence Engine v0.1 se
diseñaron para Drills primero, sin fingir generalidad prematura).

## 6. Relación con el Core (Sprint 4.1)

El `ObjectRegistry` diseñado en Sprint 4.1 es la única pieza de este modelo
de extensibilidad con diseño de código ya aprobado (no implementado). Todo
lo demás en este documento es arquitectura conceptual, a diseñar con su
propia ADR cuando corresponda (principio 10).
