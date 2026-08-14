"""Export Engine (Sprint 9.6) -- capa reutilizable entre el Core
(`src/core/`, agnóstico de todo objeto migrable) y cada módulo concreto
(`src/export/prototype/<módulo>/`).

Extracción MÍNIMA, aprobada en Sprint 9.5.1 (Export Engine Generalization
Assessment) tras comparar en profundidad las dos únicas implementaciones
reales existentes (Drills, Bypass): solo las piezas con evidencia de
duplicación genuina en AMBAS se movieron aquí -- ver
`reports/executions/2026-08-14/Informe-Minimal-Export-Engine-Extraction-EMF.md`
para el inventario completo, pieza a pieza, de qué se extrajo y por qué.

Regla dura de este paquete, verificable por inspección: ningún fichero de
`src/export/engine/` importa nada de `src/export/prototype/` (ni `drills`,
ni `bypass`, ni ningún módulo futuro), ni contiene un `if module_id == ...`
o equivalente. La diferenciación entre módulos se resuelve siempre por
inyección de dependencias (un módulo pasa sus propias funciones/config al
Engine), nunca por condicionales dentro del Engine.
"""
