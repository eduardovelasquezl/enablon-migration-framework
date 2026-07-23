# ADR-003 — Action Plans como objeto transversal de fase final

**Status:** Implemented

## Context

Action Plans no es un módulo con origen SQL propio: se alimenta de una única
tabla (`ITP_Acciones_correctoras`, clasificada por `idorigenac`) que en
realidad reúne acciones originadas en Simulacros, Eventos, Inspecciones, OPS,
Safety Meetings y otros. Tratarlo como un módulo ordinario más —analizado en
paralelo con el resto, con su propio CSV generado de forma independiente—
arriesgaba generar su salida antes de que los módulos de los que depende
(padres de las acciones vinculadas) estuvieran resueltos.

## Decision

Action Plans se modela con `processing_scope=cross_module` y
`load_phase=final` (ver ADR-001). Se introduce
`CrossModuleActionPlanBuffer` como estructura de trabajo transitoria que
consolida candidatos de todos los módulos, y se reserva
`processing_status=ready_for_final_load` exclusivamente a
`project_analysis.py::finalize_action_plans()` — ningún análisis por módulo
(`module_analysis.py`) puede producirlo. Se distingue explícitamente
`linked_action_plan` (depende de un objeto padre) de `standalone_action_plan`
(no depende de nadie, pero espera igualmente a la fase final, para mantener un
único proceso transversal).

## Consequences

- Ninguna acción puede "colarse" como lista para carga antes de que el
  proyecto complete el análisis de todos los módulos de su alcance declarado.
- Se distingue explícitamente *readiness* individual (¿esta acción concreta
  está resuelta?) de *cobertura global* (¿está todo el proyecto analizado?) —
  un módulo pendiente (`visitas_seguridad_y_otros`) dejará la cobertura global
  en `incomplete` sin bloquear acciones ya resueltas de otros módulos.
- Introduce una entidad de trabajo (`CrossModuleActionPlanBuffer`) que no es
  catálogo estable — vive solo durante la orquestación de una ejecución.

## Alternatives Rejected

- **Tratar Action Plans como un módulo más, en paralelo.** Rechazado: rompía
  la garantía de que ninguna acción vinculada se genere sin su padre resuelto.
- **Reclasificar una acción vinculada como independiente si no se encuentra su
  padre.** Rechazado explícitamente — enmascararía un problema real de
  cobertura como si fuera una acción sin dependencias.
