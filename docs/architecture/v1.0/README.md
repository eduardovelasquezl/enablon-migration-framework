# Arquitectura del framework de Migración a Enablon — v1.0

**Architecture Version: 1.0** — primera versión oficial y versionada de la arquitectura.

Este directorio es la referencia oficial del proyecto. Un desarrollador nuevo debería
poder entender el framework completo leyendo únicamente estos documentos, sin
necesidad de revisar el histórico de conversaciones o incrementos que los produjeron.

## Propósito del framework

Sustituir el proceso actual de migración histórica a Enablon (ETL en Excel, pesado,
lento y con dependencias frágiles) por un motor Python repetible, auditable y más
rápido. El framework es **analítico y de generación de conocimiento/CSV** — no
ejecuta cargas contra Enablon ni escribe en el SQL de origen. Ver
[`functional_architecture.md`](functional_architecture.md) para el detalle de
comportamiento.

## Alcance de esta versión (1.0)

Cubre lo que existe **realmente implementado** a fecha de este incremento:

- Inventario y análisis de SQL de origen (estructura, relaciones, queries).
- Análisis estructural y taxonomía de hojas de ETL Excel.
- Resolución correcta de mappings de campo (ES → XML) y de cobertura/fallbacks.
- Modelo de dominio (catálogo / relaciones / evidencia) del Knowledge Engine.
- Análisis por módulo y orquestación global de proyecto, incluyendo Action Plans
  como objeto transversal de fase final.

**No** cubre generación de CSV de carga definitivo, persistencia del repositorio,
versionado, ni ningún tipo de interfaz — eso está documentado como diseño aprobado
o como planificado, nunca como implementado. Ver
[`project_status.md`](project_status.md).

## Principios

1. **Solo lectura sobre el origen.** Nunca se modifica el BAK ni se ejecuta
   INSERT/UPDATE/DELETE contra el SQL de origen.
2. **Nunca inventar.** Ninguna regla de negocio, mapping o relación se asume por
   similitud de nombre, coincidencia parcial o conveniencia — toda afirmación debe
   indicar su origen (evidencia) y su estado (`confirmed` / `inferred` / `pending` /
   `conflicting` / `not_applicable`).
3. **Separar catálogo, relaciones y evidencia.** Qué existe, cómo se relaciona y
   por qué lo sabemos son tres capas distintas que nunca se mezclan en una misma
   estructura.
4. **Readiness individual ≠ cobertura global.** Un registro puede estar listo para
   carga aunque el proyecto, en conjunto, siga incompleto.
5. **Trazabilidad completa.** Todo dato transportado por el framework conserva su
   origen (sistema, módulo, objeto, identificador histórico) hasta la salida final.
6. **Nada se sobrescribe silenciosamente.** Ejecuciones, corridas de análisis y
   evidencias se versionan/identifican explícitamente (`analysis_run_id`), nunca se
   pisan.

## Capas de la arquitectura

```
Input Layer  →  Knowledge Engine  →  Export Engine (diseño aprobado, no implementado)  →  Deliverables
```

Ver el detalle completo en [`technical_architecture.md`](technical_architecture.md).

## Versionado — cuatro conceptos distintos, no confundir

| Concepto | Qué es | Estado |
|---|---|---|
| `architecture_version` | Versión de este conjunto de documentos (`docs/architecture/vX.Y/`). Esta es la 1.0. | Implemented (como convención documental) |
| `application_version` | Versión semántica del framework como software. | Planned — no existe todavía como constante en el código |
| `schema_version` | Versión del esquema del modelo de dominio (`src/knowledge_base/model.py`). | Planned — se introducirá junto con el motor de versionado (Fase 6, ver `roadmap.md`) |
| `analysis_run_id` | Identificador de UNA ejecución concreta de `project_analysis.py` (campo real de `ProjectAnalysisRequest`/`ProjectAnalysisResult`). Determina la carpeta de salida y evita sobrescrituras. | **Implemented** |

## Índice de documentos

- [`functional_architecture.md`](functional_architecture.md) — qué hace el framework, para quién, con qué entradas/salidas.
- [`technical_architecture.md`](technical_architecture.md) — capas técnicas, responsabilidades, dependencias.
- [`processing_flow.md`](processing_flow.md) — flujo de procesamiento completo, fase por fase.
- [`domain_model.md`](domain_model.md) — entidades del modelo de dominio.
- [`analysis_engine.md`](analysis_engine.md) — los seis módulos de análisis existentes.
- [`export_engine.md`](export_engine.md) — diseño aprobado (no implementado) de la generación de CSV.
- [`knowledge_repository.md`](knowledge_repository.md) — qué se almacena, cómo se relaciona, cómo se traza.
- [`naming_conventions.md`](naming_conventions.md) — convenciones de nombres y cambios previstos.
- [`project_status.md`](project_status.md) — matriz implementado/pendiente.
- [`roadmap.md`](roadmap.md) — fases del proyecto.
- [`decisions/`](decisions/) — ADR (decisiones de arquitectura).
- [`diagrams/`](diagrams/) — diagramas ASCII en Markdown.
- [`../../changelog/architecture_changelog.md`](../../changelog/architecture_changelog.md) — historial de esta arquitectura.

## Estado de cada elemento documentado

Todo elemento de estos documentos lleva uno de estos cuatro estados:

- **Implemented** — existe en `src/`, con tests que lo cubren.
- **Approved Design** — aprobado explícitamente en el proceso del proyecto, no implementado todavía.
- **Planned** — previsto en el roadmap, sin diseño detallado aprobado todavía.
- **Out of Scope** — explícitamente descartado para esta versión del framework.
