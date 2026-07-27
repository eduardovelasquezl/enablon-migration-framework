# EMF Blueprint v1.0 — Enablon Migration Framework

**Blueprint Version: 1.0** — primer documento fundacional del producto EMF.
**Status:** Approved Design (visión de producto aprobada; el Core y los
Engines aquí descritos están en distintos grados de diseño/implementación —
ver el estado explícito de cada componente en la sección 6).

Este documento es la referencia de más alto nivel del producto. No sustituye
a [`docs/architecture/v1.0/`](../architecture/v1.0/README.md) (que documenta,
con precisión de implementación, el primer proyecto construido sobre una
versión temprana y aún no generalizada del pipeline) ni a
[`CLAUDE.md`](../../CLAUDE.md) (memoria operativa del proyecto Moeve). Este
Blueprint documenta hacia dónde evoluciona la **plataforma**, no repite el
detalle ya documentado de lo que existe hoy.

## Terminología — no confundir

| Término | Significado en este documento | No confundir con |
|---|---|---|
| **EMF** (Enablon Migration Framework) | El producto/plataforma en sí — el software reutilizable entre proyectos y clientes. | Un proyecto concreto de migración. |
| **Core** | Paquete de infraestructura transversal (`src/core/`, diseñado en Sprint 4.1, no implementado todavía) sin conocimiento de negocio. | Un "motor" o "engine". |
| **Engine** | Componente que depende del Core y ejecuta una etapa del pipeline (Extraction, Mapping, Transformation, Validation, Comparison, Export, Evidence). Agnóstico de fuente y de cliente. | Un Connector o un Plugin. |
| **Connector / Source Connector** | Componente que sabe leer **un tipo de fuente** (SQL Server, Excel, CSV, Word, PDF, JSON) y producir Registros Normalizados. No conoce Enablon ni mappings. | Un Engine. |
| **Plugin / Module (software)** | Unidad registrable que combina un Connector + mapeos + configuración para un objeto migrable concreto de un proyecto concreto (ej. "Drills de Moeve"). | Un "módulo de Enablon". |
| **Módulo de Enablon (Enablon module)** | Agrupación de negocio dentro de Enablon tal como la organiza el cliente: Simulacros, Safety Meetings, MOC, Bypass... Término heredado de `CLAUDE.md`. | Un Plugin o paquete Python. |
| **Configuración de proyecto (Project Configuration)** | Todo lo específico de un cliente/proyecto: YAML de `config/`, Excel de mapeo, queries SQL, credenciales. La única capa que puede conocer nombres reales (Moeve, Drills, `ITP_SIMULACRO`...). | El Core o cualquier Engine. |
| **Objeto migrable (MigrationObject)** | Unidad de migración tal como ya la define [ADR-001 legado](../architecture/v1.0/decisions/ADR-001-migration-object-centric-model.md) (ej. Drills, Events, MOC). Un Plugin implementa uno o varios. | Un módulo de Enablon (puede haber varios objetos por módulo). |
| **Plantilla de destino (destination template)** | La plantilla real de importación CSV de Enablon para un objeto concreto: columnas, orden, codificación, formatos. | Un mapeo (el mapeo produce datos que **cumplen** la plantilla). |
| **Proyecto de ejemplo: Moeve** | El primer cliente/proyecto sobre el que se construye y valida EMF (ver `CLAUDE.md`). Se usa como ejemplo ilustrativo en este Blueprint — nunca como referencia dentro del Core. | El producto EMF en sí. |

## 1. Propósito

Convertir el motor de migración histórica a Enablon, hoy construido para un
único cliente (Moeve) y una única fuente (SQL Server / BAK), en una
**plataforma reutilizable** capaz de incorporar nuevos clientes, nuevos
módulos de Enablon, nuevas fuentes de datos y nuevos formatos de salida sin
reescribir su núcleo cada vez.

## 2. Visión

Un ingeniero que necesite migrar un módulo de Enablon nuevo, para un cliente
nuevo, con una fuente de datos nueva (una base de datos distinta, un Excel,
un PDF de procedimientos), debería poder hacerlo **configurando y
extendiendo** EMF — escribiendo un Connector, unos mapeos como datos, y una
configuración de proyecto — sin tocar el Core ni ningún Engine existente.
Toda migración, sin importar la fuente, produce el mismo tipo de evidencia
trazable y el mismo tipo de manifiesto auditable.

## 3. Alcance

- Arquitectura de capas (Core → Engines → Connectors → Plugins → Project
  Configuration) y la dirección de dependencia que la gobierna.
- Un modelo de datos canónico único, independiente de la fuente, que
  desacopla la extracción de la generación de salida.
- Un modelo de mapeos como datos versionables (preferentemente en Excel),
  no como lógica embebida en Python.
- Un registro versionado de plantillas de destino de Enablon (Enablon
  Template Registry) como contrato de salida, no como detalle de
  implementación de cada Export.
- Trazabilidad y evidencia de primera clase, incluyendo el caso de fuentes
  documentales (Word/PDF) con menor certeza intrínseca que SQL/Excel.
- Principios de diseño obligatorios (sección 5) y el proceso de decisión
  arquitectónica (ADR) que los hace cumplir en el tiempo.

## 4. Fuera de alcance actual

Explícitamente no cubierto por este Blueprint ni por ningún componente
descrito como "Approved Design" o "Planned" en él:

- Implementación de ningún Connector más allá de SQL Server (Excel/CSV/
  Word/PDF/JSON son diseño de arquitectura, no código, en esta versión).
- Migración del Prototype Export de Drills al nuevo Core/Engines — Drills
  sigue funcionando exactamente igual que hoy (ver
  [`README.md`](../../README.md) raíz del repositorio).
- Carga directa en Enablon (API o UI) — sigue fuera de alcance por diseño,
  ver [ADR-006 legado](../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md).
- Multi-tenencia real (varios proyectos ejecutándose simultáneamente,
  aislamiento de credenciales entre clientes) — se anticipa en el modelo de
  capas pero no se diseña en detalle todavía.
- Interfaz de usuario o API HTTP — sin fase asignada, igual que en el
  roadmap legado.
- El AI Assistant mencionado en la arquitectura objetivo — se reserva el
  nombre y la posición en el pipeline, sin diseño detallado (igual
  tratamiento que la Fase 7 del roadmap legado).

## 5. Principios de diseño

Los 14 principios son obligatorios para todo diseño o implementación futura
de EMF. Los que tienen una decisión arquitectónica formal propia tienen ADR
dedicada; el resto se aplican de forma transversal y se verifican en
[`engineering-standards.md`](../03-engineering-standards/engineering-standards.md).

| # | Principio | ADR dedicada | Resumen |
|---|---|---|---|
| 1 | Framework First | [ADR-007](../02-adr/ADR-007-framework-first.md) | Se construye plataforma, no un script de un solo uso, incluso cuando solo hay un cliente. |
| 2 | Configuration over Code | [ADR-009](../02-adr/ADR-009-configuration-over-code.md) | Lo que cambia entre proyectos/objetos es dato (YAML/Excel), no rama de código. |
| 3 | Evidence First | [ADR-008](../02-adr/ADR-008-evidence-first.md) | Ninguna afirmación de negocio se acepta sin evidencia trazable a su origen. |
| 4 | Security by Design | — (ver [`security-standards.md`](../03-engineering-standards/security-standards.md)) | Solo lectura sobre el origen, credenciales nunca en código/logs/manifiestos, por diseño y no por revisión. |
| 5 | No Hidden State | [ADR-010](../02-adr/ADR-010-no-hidden-state.md) | Sin singletons implícitos, sin estado global mutable oculto. |
| 6 | Backward Compatibility | — (ver [`engineering-standards.md`](../03-engineering-standards/engineering-standards.md)) | Ningún incremento nuevo rompe un comportamiento existente sin una decisión explícita. |
| 7 | Everything Must Be Testable | — (ver [`testing-standards.md`](../03-engineering-standards/testing-standards.md)) | Todo componente se diseña para poder probarse sin red y sin credenciales reales. |
| 8 | No Abstraction Without a Real Consumer | — (aplicado en todo diseño de Core/Engine) | No se generaliza una interfaz hasta que exista un segundo consumidor real que la necesite. |
| 9 | No Higher-Layer Dependencies in Core | [ADR-007](../02-adr/ADR-007-framework-first.md) (extiende la regla de capas) | El Core no importa nada de Engines, Connectors, Plugins ni configuración de proyecto. |
| 10 | Architectural Decisions Require an ADR | — (principio procedimental, se aplica en [`02-adr/`](../02-adr/README.md)) | Ninguna decisión estructural se adopta solo por convención tácita. |
| 11 | Extensibility by Design | [ADR-011](../02-adr/ADR-011-extensibility-by-design.md) | Añadir una fuente, un objeto o un cliente nuevo no debe requerir tocar el Core. |
| 12 | Source Agnostic, Enablon Oriented | [ADR-012](../02-adr/ADR-012-source-agnostic-enablon-oriented.md) | La entrada es plural (cualquier fuente); la salida es siempre un contrato de Enablon versionado. |
| 13 | Mappings as Data | [ADR-013](../02-adr/ADR-013-mappings-as-data.md) | Los mapeos son datos configurables y versionables, no lógica embebida. |
| 14 | Stable Core, Extensible Edges | — (consecuencia directa de 1, 9 y 11, ver [`architecture-overview.md`](../01-architecture/architecture-overview.md)) | El Core cambia poco y despacio; los bordes (Connectors/Plugins) cambian a menudo y libremente. |

No todos los principios tienen ADR propia: los que describen una práctica de
ingeniería continua (Security by Design, Backward Compatibility, Everything
Must Be Testable) se documentan como estándar vivo, no como una decisión de
un momento concreto — cambiarlos SÍ requeriría una ADR nueva, pero su
existencia inicial no es "una decisión", es una condición de entrada al
proyecto.

## 6. Arquitectura conceptual

```
Core
  ↑
Engines            (Extraction, Mapping, Transformation, Validation,
                     Comparison, Export, Evidence)
  ↑
Connectors / Adapters   (SQL Server, Excel, CSV, Word, PDF, JSON...)
  ↑
Modules / Plugins       (una combinación Connector + mapeos + config
                         para UN objeto migrable de UN proyecto)
  ↑
Project Configuration   (Moeve, sus queries, sus Excel de mapeo, su .env)
```

La flecha `↑` significa "depende de", nunca al revés. Detalle completo,
estado de cada capa (implementado / diseño aprobado / planificado) y
justificación en [`architecture-overview.md`](../01-architecture/architecture-overview.md).

Estado actual, resumido:

| Capa | Estado hoy |
|---|---|
| Core | **Approved Design** (Sprint 4.1) — `src/core/` no existe todavía en el repositorio. |
| Engines | Existen versiones **tempranas, acopladas a Drills y a SQL Server**, no generalizadas: Query Engine v0.1 (`src/query/`, Implemented, solo Drills), Evidence Engine v0.1 (`src/evidence/`, Implemented, solo Drills), un Export ad hoc (`src/export/prototype/drills/`, Implemented, solo Drills). El resto de Engines de la arquitectura objetivo (Mapping, Transformation, Validation, Comparison genéricos) son **Planned**. |
| Connectors | Solo existe acceso de solo lectura a SQL Server (`src/db/`, Implemented). Excel/CSV/Word/PDF/JSON son **Planned**, sin implementación. |
| Plugins | No existe el concepto todavía como componente registrable — Drills es, de facto, un Plugin implícito y no extraído. **Planned**. |
| Project Configuration | Implementado para Moeve (`config/*.yaml`, `sql/source_queries/`, `.env`). Es, hoy, la única "configuración de proyecto" que existe. |

## 7. Modelo de extensibilidad

Ver [`extensibility-model.md`](../01-architecture/extensibility-model.md)
para el detalle completo. Resumen: cada capa se extiende **añadiendo**, no
**modificando**. Un nuevo Connector no toca los Engines; un nuevo Engine no
toca el Core; un nuevo Plugin no toca ningún Connector existente; una nueva
Project Configuration no toca ningún Plugin existente. La extensión se
registra (Core Registry, ver diseño de Sprint 4.1), nunca se hardcodea con
un `if`/`elif` creciente.

## 8. Tipos de fuentes

EMF debe estar preparado arquitectónicamente — no implementado hoy salvo el
primero — para:

| Fuente | Estado | Certeza intrínseca de la extracción |
|---|---|---|
| SQL Server (incluye BAK restaurados) | **Implemented** (`src/db/`) | Alta — fila y columna exactas, tipo de dato conocido. |
| Excel | Parcial: se usa hoy solo como fuente de *mapeos* (`src/etl/`), no como fuente de *registros migrables* | Alta si la celda es un valor estructurado; media si depende de formato/fórmula. |
| CSV | **Planned** | Alta si el delimitador/encoding son conocidos y estables. |
| JSON | **Planned** | Alta — estructura autoexplicativa. |
| Word | **Planned** | Media/baja — depende de extracción de texto/tablas, ver sección 12. |
| PDF | **Planned** | Media/baja — igual que Word, con el riesgo añadido de PDFs escaneados/no seleccionables. |

Ningún Connector de fuente documental (Word/PDF) se implementa en esta
versión — solo se documenta el contrato que deberá cumplir (sección 12).

## 9. Modelo intermedio común

Todo Connector, sin importar la fuente, debe producir **Registros
Normalizados** en el **Modelo de Datos Canónico** antes de que cualquier
Engine los toque. Ningún Engine (Mapping, Transformation, Validation...)
conoce SQL, Excel, Word ni PDF — solo conoce la forma canónica. Esto es lo
que permite que "Fuente → CSV Enablon" nunca sea una transformación directa
(ver PRINCIPIO DE PROCESAMIENTO más abajo). Diseño conceptual completo en
[`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md).

Flujo obligatorio:

```
Fuente
  → Extracción                (Connector, produce Registros Normalizados)
  → Registros normalizados    (forma común, con provenance)
  → Modelo intermedio común   (Canonical Data Model)
  → Mapeo                     (Mapping Engine, mapeos como datos)
  → Transformación            (Transformation Engine, reglas del catálogo)
  → Validación                (Validation Engine)
  → CSV Enablon                (Export Engine, contrato de plantilla)
  → Evidencias y manifest      (Evidence Engine)
```

Cada Registro Normalizado conserva **provenance** (de dónde vino y con qué
certeza) desde la extracción hasta el CSV final — nunca se pierde el rastro
al origen, principio ya vigente hoy en Drills (`CS_HistoricalOriginID`,
`CS_HistoricalDataOrigin`) y que el Core generaliza para cualquier fuente.

## 10. Estrategia de mapeos

Los mapeos son **datos**, versionables y auditables, nunca lógica Python
embebida — ver [ADR-013](../02-adr/ADR-013-mappings-as-data.md). Excel es el
formato funcional preferido (es ya el formato con el que trabaja el cliente
y con el que se auditan los ETL actuales, ver `CLAUDE.md`), sin excluir
otros formatos de datos declarativos en el futuro (YAML, por ejemplo, ya se
usa para la configuración estructural de objetos).

Tipos de regla que el Mapping Engine deberá soportar (generalización directa
del catálogo de reglas **ya confirmado con datos reales** en `CLAUDE.md` §
"Catálogo de reglas del motor de transformación" — no es un catálogo
inventado, es la forma general de reglas que ya existen en producción):

1. Mapeo de campo (campo origen → campo Enablon).
2. Mapeo de valor (valor origen → valor Enablon) — generaliza los lookups
   simples y los lookups dinámicos en 2 pasos ya confirmados en SM/MOC.
3. Mapeos 1:1.
4. Constantes y valores por defecto — generaliza `nullcontrol`.
5. Concatenaciones — generaliza `concat`/`barconcat`.
6. Reglas condicionales.
7. Conversión de fecha y tipo.
8. Referencias a tablas maestras — generaliza `replaceinreference`.
9. Relaciones con otros objetos — generaliza el patrón de Action Plans
   transversal ya implementado en el Knowledge Engine legado.
10. Exclusiones justificadas — ya vigente hoy como `excluded_columns` en
    `config/exports/drills.yaml`, con motivo explícito por columna.
11. Transformaciones específicas registrables — generaliza `titlefix` y
    cualquier regla no estándar documentada como "sin motor visible,
    aplicada por proceso externo" (ver `CLAUDE.md`).

Cada entrada de mapeo conserva, como mínimo: proyecto, módulo, objeto,
fuente, campo origen, campo destino, tipo de regla, valor origen, valor
destino, obligatoriedad, prioridad, valor por defecto, observaciones,
versión y estado de validación. Este esquema es una extensión directa,
no una ruptura, del patrón `DatoOrigen / DatoDestino / EsCondicion /
ReglaEspecial / Parametro` ya usado en los ETL Excel originales.

## 11. Contratos de salida Enablon

El CSV de importación de Enablon **no es un formato libre** — es un
contrato de salida versionado, gestionado por el futuro **Enablon Template
Registry**: un catálogo, una entrada por (proyecto, módulo, objeto, versión
de plantilla), que fija columnas esperadas, orden, codificación, formatos de
fecha, valores asociados, campos obligatorios y estructura exacta requerida.
El Export Engine consulta el Registry, nunca decide el formato por su
cuenta ni lo deriva de los datos.

Esto ya es, de facto, el comportamiento de `config/exports/drills.yaml` hoy
(columnas, encoding, delimiter, quoting, orden fijados explícitamente) —
el Registry generaliza ese mismo patrón a "una entrada declarativa por
plantilla", en vez de "un YAML de exportación que mezcla plantilla y reglas
de mapeo en un solo fichero", como ocurre hoy en Drills.

## 12. Trazabilidad y evidencias

Principio: **no toda extracción tiene la misma certeza.** Una fila de SQL
Server es un hecho; un valor leído de un PDF escaneado es una interpretación.
El modelo canónico (sección 9) obliga a que todo Registro Normalizado
proveniente de una fuente documental (Word/PDF) conserve, como mínimo:

- archivo origen;
- página;
- sección;
- tabla o bloque;
- método de extracción;
- valor original (tal cual se leyó);
- valor normalizado (tras limpieza determinista, si aplica);
- nivel de confianza;
- si requiere o recibió revisión humana;
- incidencias detectadas durante la extracción.

Para fuentes estructuradas (SQL, Excel, CSV, JSON) estos mismos campos
existen mecánicamente pero con valores triviales (confianza = 1.0, sin
página/sección) — el modelo es único, no hay dos modelos de evidencia
distintos según la fuente. El Evidence Engine (hoy limitado a Drills, ver
[`evidence-first ADR`](../02-adr/ADR-008-evidence-first.md)) es el
consumidor natural de este `provenance` para producir el Excel de revisión.

## 13. Seguridad

Ver [`security-standards.md`](../03-engineering-standards/security-standards.md)
para el detalle completo. Resumen de los invariantes que EMF hereda,
sin excepción, de las restricciones ya vigentes en `CLAUDE.md` y
`src/db/`:

- Todo acceso a una fuente viva (SQL Server u otra futura) es de solo
  lectura, con doble salvaguarda (permiso real a nivel de servidor +
  validación estructural en código).
- Ninguna credencial vive en código, YAML versionado, log, manifiesto ni
  mensaje de excepción — solo en `.env`, nunca commiteado.
- Ningún valor aportado por un usuario o por una fuente externa se
  concatena en una consulta o comando — siempre parametrizado (patrón ya
  implementado por el Query Engine, ver `src/query/`).
- Ningún componente de EMF escribe en Enablon en esta fase del producto.

## 14. Calidad

Ver [`testing-standards.md`](../03-engineering-standards/testing-standards.md).
Todo componente del Core y de los Engines se diseña para ser probado sin
red, sin credenciales reales y sin depender de un proyecto concreto — los
~400 tests ya existentes en `tests/` (ninguno requiere red salvo los
opt-in explícitamente gateados) son el estándar de referencia a mantener,
no a relajar.

## 15. Ciclo de desarrollo

Ver [`engineering-standards.md`](../03-engineering-standards/engineering-standards.md)
y [`sprint-review-template.md`](../05-sprint-reviews/sprint-review-template.md).
Desarrollo por incrementos pequeños y verificables (mismo patrón ya usado en
los sprints de Query Engine y Evidence Engine v0.1), cada uno con su propia
revisión de sprint documentada, sin mezclar cambios de Core con cambios de
comportamiento funcional de ningún Plugin/proyecto existente.

## 16. Estrategia de versiones

Ver [`release-strategy.md`](../06-releases/release-strategy.md) para el
detalle. Cuatro ejes de versión, **no confundir entre sí** (extensión
directa de la tabla ya vigente en
[`docs/architecture/v1.0/README.md`](../architecture/v1.0/README.md#versionado--cuatro-conceptos-distintos-no-confundir)):

| Eje | Qué versiona | Dónde vive |
|---|---|---|
| `blueprint_version` | Este documento y el conjunto `docs/00-blueprint/`…`08-user-guide/`. | Nombre de fichero (`emf-blueprint-v1.0.md`) + cabecera de cada documento. |
| `architecture_version` (legado) | `docs/architecture/v1.0/` — la arquitectura del primer proyecto, previa a EMF. | Ya vigente, no se toca. |
| `application_version` / `FrameworkVersion` | El software del Core como tal. | Planned — diseñado en Sprint 4.1 (`src/core/version.py`), no implementado todavía. |
| `template_version` (nuevo) | Cada entrada del Enablon Template Registry. | Planned — no existe el Registry todavía. |

## 17. Roadmap

Ver [`roadmap.md`](../04-roadmap/roadmap.md) para el detalle fase a fase y
su relación explícita con las 7 fases ya aprobadas del roadmap legado.

## 18. Criterios de éxito

EMF v1.0 (la plataforma, no este documento) se considera exitosa cuando,
sin modificar el Core:

1. Se puede incorporar un segundo Connector de fuente (más allá de SQL
   Server) implementando únicamente la interfaz de Connector.
2. Se puede incorporar un segundo objeto migrable (más allá de Drills)
   registrándolo como Plugin, sin duplicar lógica de Export/Validation/
   Evidence.
3. Se puede incorporar un segundo proyecto/cliente (más allá de Moeve)
   añadiendo únicamente su Project Configuration.
4. Los mapeos de ese segundo objeto/proyecto se definen enteramente como
   datos (Excel/YAML), sin una sola línea de Python nueva por regla.
5. La evidencia y el manifiesto de cualquier ejecución, de cualquier
   fuente, tienen la misma forma y el mismo nivel de trazabilidad que hoy
   tiene Drills.
6. Ningún cambio de los anteriores rompe el comportamiento de Drills sobre
   Moeve tal como existe hoy.
