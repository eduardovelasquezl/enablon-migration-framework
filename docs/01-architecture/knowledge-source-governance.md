# Knowledge Source Governance — EMF

**Status:** Proposed (Sprint 8.8). Formaliza, de forma genérica y
reutilizable para cualquier cliente futuro (no solo Moeve), el flujo que
toda fuente de conocimiento nueva debe atravesar antes de que una regla
que contiene se considere parte del conocimiento auditable del EMF. Es el
proceso; `mapping-governance.md` es el modelo de datos que ese proceso
produce.

## 1. Por qué

`CLAUDE.md` ya documenta un patrón repetido siete veces: "todos los ETL
nuevos se construyen copiando el libro de un módulo anterior sin
limpiar". Sin un registro explícito de qué fuente aportó qué regla y
cuándo, cada copia-sin-limpiar difumina más el origen real del
conocimiento, hasta que — como con `Entidades_Mapeo` — nadie puede decir
con certeza si una hoja sigue vigente o es un resto arrastrado. Este
documento existe para que la próxima fuente (Excel, CSV, SQL, Word, PDF,
API, JSON, SharePoint, mapping manual, documentación funcional) no repita
el patrón.

## 2. El flujo

```
SOURCE REGISTER → CLASSIFICATION → KNOWLEDGE EXTRACTION → CONFLICT DETECTION → MAPPING GOVERNANCE → VALIDATION → APPROVAL
```

Ninguna regla funcional derivada de una fuente nueva se trata como
conocimiento vigente del EMF hasta pasar por las 7 etapas. Una fuente
puede quedar detenida en cualquier etapa (p. ej. `UNRESOLVED_CLASSIFICATION`)
sin bloquear el resto del inventario — el flujo es por fuente, no por lote.

### 2.1 SOURCE REGISTER

Se asigna `source_document_id` (ver `mapping-governance.md` § 3.2) y se
registra metadata física: categoría, extensión, tamaño, fecha de
modificación, ubicación relativa (nunca la ruta absoluta como identidad),
versión identificable si el nombre la trae, duplicado potencial. Nunca se
modifica, mueve ni renombra el archivo original.

Categorías mínimas: `ETL`, `CSV_TEMPLATE`, `CSV_OPERATIONAL`, `MAPPING`,
`CATALOG`, `ERROR`, `ATTACHMENT_REFERENCE`, `SQL`, `EVIDENCE`, `OTHER`,
`UNCLASSIFIED`.

### 2.2 CLASSIFICATION

Se determina, solo cuando hay evidencia real (nunca por inferencia
forzada): `client_id`, `project_id`, `module_id`, `object_type`,
`subobject` (opcional), `source_version`, `source_status`
(`CURRENT_VERIFIED` / `CURRENT_UNVERIFIED` / `HISTORICAL` / `SUPERSEDED`
/ `REFERENCE` / `UNKNOWN`). Si no puede determinarse un campo, ese campo
queda `UNRESOLVED_CLASSIFICATION` — nunca se inventa un módulo u objeto
para "completar" el registro.

### 2.3 KNOWLEDGE EXTRACTION

Extracción **de solo lectura**, sin ejecutar macros, sin recalcular
fórmulas, sin refrescar Power Query ni conexiones. Para Excel: hojas
(visibles y ocultas), nombres definidos, cabeceras, fórmulas tal cual
están escritas (nunca su resultado evaluado), tablas de equivalencia,
condiciones, defaults, tratamiento de null. Para SQL: texto de la query
tal cual, nunca ejecutada. Si una regla no puede interpretarse solo con
esto, se marca `UNRESOLVED_RULE` — no se completa por analogía con otro
módulo sin decirlo explícitamente.

Restricción técnica práctica (usada en este sprint, ver
`moeve-source-inventory.md` § 4): los libros Excel involucrados pueden
superar los 300 MB. La extracción debe limitarse a metadata de hoja +
cabecera + una muestra acotada de filas en hojas identificadas como
mapping-like — nunca cargar el libro completo en memoria para leer cada
celda de cada fila de datos, que no aporta conocimiento de regla
adicional proporcional al coste.

### 2.4 CONFLICT DETECTION

Se compara la regla candidata contra todo lo ya registrado con precedencia
igual o mayor (`mapping-governance.md` § 2). Si coincide, se referencia
como evidencia adicional de la misma regla. Si contradice, se abre un
`KNOWLEDGE_CONFLICT` (§ 4 del documento de gobierno) — nunca se
sobrescribe la regla anterior en silencio, y nunca se asume que la fuente
nueva es automáticamente correcta solo por ser nueva.

### 2.5 MAPPING GOVERNANCE

La regla (o el conflicto) se incorpora al modelo de identidad de
`mapping-governance.md` § 3 — se le asigna `rule_id` (estable, buscando
primero si ya existe una regla equivalente para no duplicar identidad) y
`rule_revision` si sustituye a una anterior.

### 2.6 VALIDATION

Antes de marcarse `CURRENT_VERIFIED`, la regla debe tener al menos una de:
confirmación humana explícita registrada, ejecución real que la
verifique (p. ej. una corrida de exportación con resultado comparado
contra el CSV Operational real), o coincidencia entre dos fuentes
independientes de precedencia ≥ 4. La sola presencia estructural en un
ETL (extracción § 2.3) sin ninguna de las anteriores dejará la regla en
`CURRENT_UNVERIFIED`, no en `CURRENT_VERIFIED` — ver el caso AP en
`mapping-governance.md` § 7 como ejemplo aplicado de este límite.

### 2.7 APPROVAL

Paso humano final, fuera del alcance de este sprint (que es de solo
inspección/documentación). El backlog (`moeve-mapping-backlog.md`) lista
qué reglas están listas para ese paso y cuáles no.

## 3. Qué no hace este flujo

No decide automáticamente qué fuente "gana" — eso es `mapping-governance.md`
§ 2, y explícitamente puede no decidir (§ 4, conflicto abierto). No
ejecuta nada del origen (SQL, macro, Power Query, recálculo) en ninguna
etapa. No autoriza por sí mismo el acceso a SQL real — eso sigue regido
por `docs/01-architecture/sql-execution-guard.md`, independiente de este
flujo.

## 4. Aplicación a este sprint

`moeve-source-inventory.md` es el resultado de aplicar las etapas 2.1–2.3
a las fuentes reales de Moeve. `mapping-governance.md` §§ 7–9 es el
resultado de aplicar 2.4–2.6 a los dos casos que el encargo pedía
explícitamente (Action Plans, MOC). La etapa 2.7 (aprobación humana)
queda pendiente por diseño — este sprint no aprueba nada, prepara lo
necesario para que se pueda aprobar.
