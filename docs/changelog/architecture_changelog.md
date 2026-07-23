# Architecture Changelog

Historial de cambios a la **arquitectura documentada** del framework
(`docs/architecture/`). No es el changelog del código — es el changelog de
`architecture_version`. Ver `docs/architecture/v1.0/README.md` para la
distinción entre `architecture_version`, `application_version`,
`schema_version` y `analysis_run_id`.

## v1.0 — Initial approved architecture

**Fecha:** 2026-07-22

Primera versión oficial y versionada de la arquitectura. Documenta, tal como
existían en el momento de escribirla, sin modificar ningún comportamiento:

- Arquitectura funcional y técnica del framework.
- Flujo de procesamiento completo, marcando qué fases existen (Knowledge
  Engine) y cuáles son diseño aprobado sin implementar (Export Engine).
- Modelo de dominio completo (catálogo / relaciones / evidencia).
- Los seis componentes del Analysis Engine (`query_analyzer`,
  `schema_analyzer`, `mapping_resolver`, `mapping_coverage`,
  `module_analysis`, `project_analysis`).
- Diseño aprobado (no implementado) del Export Engine.
- Convenciones de nombres en uso, y un cambio de nomenclatura previsto
  (`ready_for_final_load` → `ready_for_csv_generation`) marcado como
  `Future Improvement`, sin aplicar.
- Matriz de estado del proyecto (implementado / diseño aprobado / pendiente).
- Roadmap de 7 fases, basado únicamente en lo ya aprobado.
- 6 ADR fundacionales (ADR-001 a ADR-006).
- 4 diagramas ASCII (visión general, ciclo de vida de un registro, flujo de
  Action Plans, flujo de exportación).

Este incremento fue exclusivamente documental: no modificó `src/`, `tests/`,
`config/`, `inputs/`, `outputs/` ni `sql/`.
