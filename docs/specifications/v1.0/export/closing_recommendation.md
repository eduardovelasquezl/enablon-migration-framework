# Recomendación de cierre — Export Specifications v1.0

> Documento breve de cierre. No repite el detalle ya documentado en
> `evidence_inventory.md`, `export_readiness_matrix.md`,
> `migration_object_inventory.md`, `action_plans_assessment.md` ni
> `open_questions.md` — solo sintetiza la decisión de cierre y el siguiente
> paso.

## 1. Cierre de la fase documental

La fase **Export Specifications v1.0** (inventario de evidencia, inventario
de `MigrationObject`, matriz de preparación, evaluación de Action Plans,
preguntas abiertas, y los incrementos posteriores de mapping evidence, ETL
profundo, mapeo de entidad y validación cuantitativa de Action Plans) se da
por **cerrada** como fase de análisis documental. No quedan incrementos de
análisis adicionales planificados antes de pasar a implementación.

## 2. Drills es el primer objeto listo para borrador

`simulacros.Drills` es, con evidencia acumulada en `export_readiness_matrix.md`
§7, el único `MigrationObject` de todo el inventario que alcanza
`object_specification_draft_ready`: `Reference` resuelto como decisión
funcional aprobada (`AFD-DRILLS-REFERENCE-001`) y entidad impactada
(`CS_ImpactedEntities`) con mecanismo de resolución localizado y
reproducible. Es el candidato natural para iniciar cualquier implementación.

## 3. Sin template oficial validado

Ningún objeto del inventario tiene `template_status: validated` — los CSV de
`Bloque4_CSV_Enablon`, incluido el de Drills, son exportaciones de datos
reales, no plantillas de importación en blanco confirmadas por Enablon (ver
`evidence_inventory.md` §3). En consecuencia, `approved_specification_readiness`
permanece `blocked` para Drills igual que para el resto — esta condición no
la resuelve ningún volumen de análisis adicional, solo una confirmación del
cliente.

## 4. Preguntas que siguen abiertas

Drills conserva open questions no bloqueantes para un borrador:
`OQ-ETL-05`, `OQ-ETL-06`, `OQ-ENT-04` (ver `open_questions.md`). Ninguna
exige adivinar una regla de negocio no documentada.

## 5. Decisión: iniciar Prototype Export

Se decide iniciar un incremento de **implementación vertical, limitado a
Drills** ("Prototype Export"): SQL de solo lectura → transformación →
mapping → validación → CSV. No es un Export Engine genérico ni cubre otros
`MigrationObject` todavía.

## 6. Carácter provisional del primer CSV

El CSV que produzca este prototipo es un **artefacto de revisión interna**,
no un fichero aprobado para carga en Enablon. Ningún incremento de
implementación puede declararlo `approved_for_enablon_import: true` sin una
confirmación explícita del cliente sobre el template real.
