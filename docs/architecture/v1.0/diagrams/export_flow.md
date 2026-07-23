# Diagrama — Flujo de exportación

> **Todo lo mostrado en este diagrama es `Approved Design`. No existe código
> de ninguno de estos componentes en `src/` a día de esta versión.**

Diagrama ASCII únicamente.

```
┌─────────────────────────┐
│  ProjectAnalysisResult    │  Implemented (ya existe hoy)
│  (incluye action_plan_    │
│   buffers en               │
│   ready_for_final_load,    │
│   blocked o excluded)      │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  ExportPlan                │  Approved Design
│  (qué MigrationObject se   │
│   exporta, en qué orden --  │
│   Action Plans siempre      │
│   al final)                 │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  ExportDefinition           │  Approved Design
│  (columnas del CSV final    │
│   por objeto Enablon,        │
│   formato de fecha/         │
│   separador...)              │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  CSV Generator               │  Approved Design
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  CSV Writer                   │  Approved Design
│  (encoding/separador según    │
│   la plantilla real de        │
│   Enablon de cada objeto)      │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  CSV Validator                 │  Approved Design
│  (contra la plantilla real     │
│   de Enablon -- QA, Fase 4)     │
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  ExportPackage + Manifest       │  Approved Design
└────────────┬─────────────┘
             │
             ▼
┌─────────────────────────┐
│  Entrega a Enablon               │  Fuera de alcance del framework
│  (manual o vía API, decidido      │  (ver ADR-006)
│   por el cliente)                  │
└─────────────────────────┘
```
