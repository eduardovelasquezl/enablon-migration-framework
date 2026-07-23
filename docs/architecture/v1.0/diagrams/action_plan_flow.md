# Diagrama — Flujo de Action Plans (objeto transversal)

Diagrama ASCII únicamente. Todo lo mostrado es **Implemented**.

```
 Módulo A          Módulo B          Módulo C         visitas_seguridad_y_otros
(Simulacros)     (Reuniones)       (Eventos)          (idorigenac sin clasificar)
    │                 │                 │                        │
    ▼                 ▼                 ▼                        ▼
module_analysis.py (por módulo, en paralelo conceptualmente)
    │                 │                 │                        │
    │  detect_action_plan_candidates()                            │
    │  validate_action_plan_fields()                              │
    │  resolve_parent_reference() (solo si el padre está           │
    │  en el propio módulo)                                        │
    │                 │                 │                        │
    ▼                 ▼                 ▼                        ▼
CrossModuleActionPlanBuffer  x N  (discovered/validated/
                                   waiting_for_parent/blocked/excluded
                                   -- NUNCA ready_for_final_load aquí)
    │                 │                 │                        │
    └────────┬────────┴────────┬────────┴────────────┬───────────┘
             │                 │                      │
             ▼                 ▼                      ▼
     ┌─────────────────────────────────────────────────────┐
     │            project_analysis.py                        │
     │                                                         │
     │  1. consolidate_action_plan_buffers()                  │
     │     -- dedup por (source_system, source_module,        │
     │        action_plan_historical_id); duplicados exactos   │
     │        se fusionan conservando evidencias; duplicados   │
     │        incompatibles -> blocked/conflicting, nunca se   │
     │        elige uno                                        │
     │                                                         │
     │  2. resolve_action_plan_parents()                       │
     │     -- resuelve linked SOLO con parent_reference_index  │
     │        (evidencia exacta, cruzando módulos); si no hay  │
     │        más módulos por analizar, sin padre -> blocked   │
     │                                                         │
     │  3. finalize_action_plans()  ← ÚNICO punto autorizado   │
     │     a producir ready_for_final_load                     │
     │     -- solo si NINGÚN módulo del alcance quedó sin       │
     │        analizar (visitas_seguridad_y_otros incluido)    │
     └───────────────────────┬───────────────────────────────┘
                             │
                             ▼
              ┌───────────────────────────────┐
              │  ActionPlanGlobalCoverage       │
              │  status: complete | incomplete  │
              │          | conflicting          │
              │  (incomplete mientras            │
              │   visitas_seguridad_y_otros      │
              │   siga pendiente -- esto NO      │
              │   impide que otras acciones      │
              │   ya resueltas lleguen a ready)  │
              └───────────────────────────────┘
```
