# User Guide — EMF

**Status:** Approved Design (guía de orientación). Para instrucciones
operativas reales (instalación, comandos exactos, opciones de la CLI), usa
siempre [`README.md`](../../README.md) raíz — es la referencia operativa
viva y la única que se actualiza cuando cambia el comportamiento real de la
CLI. Este documento explica **qué es EMF** para alguien que solo necesita
usarlo, no extenderlo.

## 1. Qué puedes hacer con EMF hoy

Hoy, EMF ofrece un único flujo ejecutable de extremo a extremo: exportar el
objeto **Drills** del proyecto **Moeve** desde SQL Server, con evidencia y
manifiesto de trazabilidad, opcionalmente filtrado. Todo lo demás descrito
en el [Blueprint](../00-blueprint/emf-blueprint-v1.0.md) (otros objetos,
otras fuentes, otros clientes) es la dirección hacia la que evoluciona el
producto, no algo disponible todavía — ver
[`architecture-overview.md`](../01-architecture/architecture-overview.md)
para el estado real de cada componente.

```bash
python main.py export drills --mode sample --limit 100
```

Ver [`README.md`](../../README.md) § 4 en adelante para el resto de
comandos (filtros, generación de evidencia, modo completo).

## 2. Qué produce cada ejecución

Cada ejecución de `export drills` escribe, en una carpeta propia con marca
de tiempo (nunca sobrescribe una ejecución anterior):

- `drills.csv` — el CSV de revisión (no aprobado para carga en Enablon).
- `validation_report.yaml` — resultado de la validación.
- `export_manifest.yaml` — trazabilidad técnica completa de la ejecución.
- `comparison_report.yaml` — comparación contra el histórico real, si
  existe.
- `issues.jsonl` — incidencias fila a fila.
- `generated_query.sql` — si se usaron filtros, la SQL compuesta (sin
  valores reales, solo placeholders).

Ver [`README.md`](../../README.md) § 5 para el detalle exacto.

## 3. Qué significa "review_only"

Todo CSV que produce EMF hoy es un **artefacto de revisión**, nunca un
fichero aprobado para carga directa en Enablon —
`approved_for_enablon_import` es siempre `false`. EMF, como producto, no
carga nada en Enablon en esta versión (ver
[ADR-006 legado](../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md)).
La carga final sigue siendo manual o vía un proceso fuera de este
framework.

## 4. Evidencia — para quién y para qué

El Evidence Engine genera dos versiones del mismo Excel de revisión:

- **Interna** — conserva trazabilidad técnica completa (hashes, rutas,
  reglas aplicadas) para quien construye/audita el pipeline.
- **Cliente** — lenguaje neutral, sin hashes ni rutas locales, orientada a
  revisión funcional por el equipo de negocio.

Ver [`README.md`](../../README.md) § 6.

## 5. Si necesitas un objeto, cliente o fuente que no existe todavía

No está disponible hoy — está descrito como diseño futuro en el
[Blueprint](../00-blueprint/emf-blueprint-v1.0.md) y en el
[roadmap](../04-roadmap/roadmap.md). Si tu necesidad concreta no aparece en
el roadmap, es una señal para priorizarla explícitamente, no para asumir
que EMF ya lo soporta de alguna forma no documentada.

## 6. Seguridad — lo que debes saber como usuario

- EMF nunca escribe en la base de datos de origen — todo acceso es de solo
  lectura, con doble salvaguarda (ver
  [`security-standards.md`](../03-engineering-standards/security-standards.md)).
- EMF nunca escribe en Enablon.
- Ningún fichero que EMF genera (CSV, manifiesto, evidencia) contiene
  credenciales.

## 7. Uso con asistentes de IA (Claude Code, Codex...)

Ver [`README.md`](../../README.md) § 7-8 — un asistente de IA debe traducir
siempre la instrucción en lenguaje natural al comando real de la CLI, nunca
asumir ni inventar que una exportación ocurrió sin ejecutarla realmente.
