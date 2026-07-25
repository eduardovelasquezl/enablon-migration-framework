"""Evidence Engine v0.1 -- generación de Excel de evidencia (interno y
cliente) a partir de una ejecución ya completada del Prototype Export de
Drills.

No vuelve a ejecutar SQL ni reinterpreta reglas de negocio -- lee
únicamente los artefactos ya escritos por
`src.export.prototype.drills.pipeline` (`validation_report.yaml`,
`export_manifest.yaml`, `comparison_report.yaml`, `issues.jsonl`, `drills.csv`)
más el catálogo de categorías de este paquete. Limitado a Drills -- no es
un motor genérico para otros objetos (ver
`docs/specifications/v1.0/export/closing_recommendation.md`).
"""
