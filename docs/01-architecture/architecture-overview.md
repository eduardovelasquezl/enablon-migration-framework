# Architecture Overview — EMF

**Status:** Approved Design. Ver terminología completa en el
[Blueprint](../00-blueprint/emf-blueprint-v1.0.md#terminología--no-confundir)
antes de leer este documento — evita repetirla aquí.

Este documento detalla la arquitectura conceptual objetivo introducida en el
Blueprint (sección 6). Describe capas y componentes **como diseño**, con su
estado real de implementación marcado en cada uno — no crea código ni
directorios vacíos para representarlos.

## 1. Las cinco capas y su dirección de dependencia

```
┌─────────────────────────────────────────────────────────────┐
│  Project Configuration   (Moeve: config/*.yaml, sql/, .env)  │
└───────────────────────────────┬───────────────────────────────┘
                                 │ depende de
┌───────────────────────────────▼───────────────────────────────┐
│  Modules / Plugins        (ej.: "Drills de Moeve")             │
└───────────────────────────────┬───────────────────────────────┘
                                 │ depende de
┌───────────────────────────────▼───────────────────────────────┐
│  Connectors / Adapters   (SQL Server, Excel, CSV, Word, PDF...)│
└───────────────────────────────┬───────────────────────────────┘
                                 │ depende de
┌───────────────────────────────▼───────────────────────────────┐
│  Engines   (Extraction, Mapping, Transformation, Validation,   │
│             Comparison, Export, Evidence)                      │
└───────────────────────────────┬───────────────────────────────┘
                                 │ depende de
┌───────────────────────────────▼───────────────────────────────┐
│  Core   (excepciones, contexto, registro, versión, logging)    │
└─────────────────────────────────────────────────────────────┘
```

Regla fundamental (principio 9, "No Higher-Layer Dependencies in Core"): la
flecha siempre apunta hacia abajo. Una capa superior puede importar de
cualquier capa inferior; ninguna capa inferior importa nunca de una
superior. El Core, en particular, **no conoce**: módulos concretos,
clientes, proyectos, tablas específicas, bases de datos determinadas,
plantillas específicas de Enablon, Drills, Moeve, ni ningún formato
concreto de entrada.

Esta regla ya se aplicó, de facto, en el diseño de Sprint 4.1 (ver el
informe de diseño del Core, referenciado desde `docs/changelog/` cuando se
incorpore) al auditar el grafo de imports real de `src/`: hoy `src.config`
y `src.db.exceptions` son las únicas "hojas" sin dependencias internas —
el Core, cuando se implemente, se sitúa **por debajo** incluso de ellas
(cero imports de `src.*`), precisamente para no arriesgar un ciclo si en el
futuro `src.config` quisiera depender del Core.

## 2. Componentes de la arquitectura objetivo

Para cada componente: qué hace, de qué depende, y su estado real hoy.

### 2.1 Core
**Estado: Approved Design (Sprint 4.1), no implementado — `src/core/` no existe.**

Primitivas transversales sin conocimiento de negocio: jerarquía de
excepciones común (`FrameworkError`), versión del framework
(`FrameworkVersion`), metadatos de un objeto migrable (`ObjectMetadata`),
contexto de una ejecución (`FrameworkContext`), registro de objetos
(`ObjectRegistry`), logging común (`get_logger`). No depende de ningún otro
paquete `src.*`.

### 2.2 Source Connectors
**Estado: Planned salvo SQL Server (Implemented, no generalizado).**

Cada Connector sabe leer un tipo de fuente y producir Registros
Normalizados en el Modelo de Datos Canónico (ver
[`data-processing-lifecycle.md`](data-processing-lifecycle.md)). No conoce
Enablon, no conoce mappings, no decide qué es "obligatorio" — eso es
responsabilidad de capas superiores.

- **SQL Server**: implementado hoy como `src/db/` (conexión de solo
  lectura, `query_runner`, `metadata`) — pero acoplado directamente al
  Prototype Export de Drills, no expuesto todavía como un Connector
  genérico intercambiable.
- **Excel**: uso parcial hoy (`src/etl/excel_reader.py`,
  `mapping_resolver.py`) — como fuente de **mapeos**, no como fuente de
  **registros migrables**. Un futuro Excel Connector (fuente de datos) es
  un componente distinto, todavía no diseñado en detalle.
- **CSV, JSON, Word, PDF**: sin ninguna implementación. El contrato que
  deberán cumplir (interfaz de Connector + campos de provenance
  documentales) está definido en el Blueprint § 8/12 y en
  [`data-processing-lifecycle.md`](data-processing-lifecycle.md).

### 2.3 Extraction Engine
**Estado: Planned.** Orquesta uno o varios Connectors para una ejecución,
aplica límites de seguridad (máximo de filas, timeout — ya existentes hoy
en `config/databases.yaml` → `safety`, a generalizar), y entrega Registros
Normalizados al resto del pipeline. Hoy esta orquestación vive, sin
generalizar, dentro de `src/export/prototype/drills/extractor.py`.

### 2.4 Canonical Data Model
**Estado: Planned (diseño conceptual en este Blueprint, sin tipos Python
todavía).** La forma común de un registro migrable, independiente de la
fuente. Ver [`data-processing-lifecycle.md`](data-processing-lifecycle.md)
§ 2 para su forma conceptual completa.

### 2.5 Mapping Engine
**Estado: Planned.** Aplica mapeos-como-datos (ver
[ADR-013](../02-adr/ADR-013-mappings-as-data.md)) sobre un Registro
Normalizado para producir un registro mapeado. Generaliza
`src/etl/mapping_resolver.py` y el patrón de `reference_data` de
`config/exports/drills.yaml`.

### 2.6 Transformation Engine
**Estado: Planned.** Aplica las reglas de transformación (concat,
nullcontrol, lookup dinámico, conversión de fecha/tipo...) ya catalogadas
con evidencia real en `CLAUDE.md`. Generaliza `src/etl/transformations.py`
y `src/export/prototype/drills/transformations.py` (hoy dos
implementaciones paralelas, una por generación de incremento — señalado
como riesgo en la sección de Riesgos del informe de Sprint 4.1).

### 2.7 Validation Engine
**Estado: Planned como motor genérico.** Existe hoy, sin generalizar, como
`src/export/prototype/drills/validator.py` (pre-escritura y post-escritura)
y como el patrón `validate_*` documentado en
[`naming_conventions.md`](../architecture/v1.0/naming_conventions.md) legado
(devuelve lista de violaciones, nunca lanza excepción por regla de
negocio — convención que el futuro Validation Engine **hereda tal cual**,
no reemplaza).

### 2.8 Comparison Engine
**Estado: Planned como motor genérico.** Existe hoy, sin generalizar, como
`src/export/prototype/drills/comparison.py` (compara el CSV generado contra
el CSV histórico real de Drills). Un Comparison Engine genérico opera sobre
cualquier par de conjuntos de datos comparables, no solo Drills.

### 2.9 Enablon Template Registry
**Estado: Planned.** Catálogo versionado de plantillas de importación reales
de Enablon — ver Blueprint § 11. No existe hoy ni siquiera como concepto
explícito: cada objeto fija su propia plantilla dentro de su propio YAML de
exportación (`config/exports/drills.yaml`).

### 2.10 Export Engine
**Estado: Planned como motor genérico; Implemented como caso único (Drills).**
`src/export/prototype/drills/` es hoy la única instancia real: SQL →
transformación → mapping → validación → CSV, íntegramente específica de
Drills. El Export Engine genérico consulta el Enablon Template Registry en
vez de tener el contrato hardcodeado por objeto.

### 2.11 Evidence Engine
**Estado: Implemented para Drills (v0.1), Planned como motor genérico.**
`src/evidence/` ya genera Excel interno/cliente a partir de los artefactos
de una ejecución, sin volver a consultar la fuente — ese principio
(Evidence First, [ADR-008](../02-adr/ADR-008-evidence-first.md)) se
mantiene sin cambios al generalizar a otros objetos/proyectos.

### 2.12 Plugin System
**Estado: Planned.** El Core incluye el diseño de un `ObjectRegistry`
(Sprint 4.1) capaz de registrar `ObjectMetadata` — el mecanismo base de un
futuro sistema de plugins. No incluye todavía carga dinámica (entry
points), ni descubrimiento automático — ver
[`extensibility-model.md`](extensibility-model.md) § 3 para qué falta y por
qué se pospone deliberadamente.

### 2.13 AI Assistant
**Estado: Planned, sin diseño detallado.** Se reserva el nombre y la
posición conceptual al final del pipeline (equivalente a la Fase 7 del
[roadmap legado](../architecture/v1.0/roadmap.md)) — no se documenta
ninguna capacidad concreta todavía, para no presentar como diseñado algo
que no lo está.

## 3. Query Engine — dónde encaja

`src/query/` (Query Engine v0.1, Implemented) no aparece en la lista de
Engines "canónicos" de la sección 2 porque no es una etapa del pipeline
Fuente→CSV — es una capacidad transversal de **filtrado de extracción**,
ortogonal al pipeline principal. Hoy depende directamente de
`src.db.query_runner` (ver auditoría de imports en el informe de diseño de
Sprint 4.1) y está acoplado a Drills vía su catálogo cerrado
(`DRILLS_FILTER_CATALOG`). Su generalización futura (un catálogo de filtros
por objeto, no solo Drills) es candidata a integrarse como una capacidad del
Extraction Engine, no como un Engine nuevo — decisión a tomar con ADR propia
cuando haya un segundo consumidor real (principio 8).

## 4. Por qué "Stable Core, Extensible Edges"

El Core cambia poco y despacio porque **no sabe nada que cambie a menudo**
— ni un cliente, ni un objeto, ni un formato. Todo lo que cambia con
frecuencia (un cliente nuevo, un módulo de Enablon nuevo, una fuente nueva)
vive en los bordes (Connectors, Plugins, Project Configuration), que se
añaden sin tocar las capas inferiores. Esta es la consecuencia práctica
directa de los principios 1, 9 y 11 del Blueprint, no un principio
adicional independiente.
