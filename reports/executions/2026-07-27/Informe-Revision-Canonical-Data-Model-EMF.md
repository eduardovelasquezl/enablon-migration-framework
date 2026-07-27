# Informe — Revisión Arquitectónica del Canonical Data Model (EMF)

**Proyecto:** Enablon Migration Framework (EMF)
**Fecha:** 2026-07-27
**Tarea:** Aplicar las 10 correcciones exigidas por la Architectural Design
Review sobre `docs/01-architecture/canonical-data-model.md` y
`docs/02-adr/ADR-014-canonical-data-model.md`. Sin implementación de código.

---

## 1. Correcciones realizadas

| # | Problema detectado por la revisión | Corrección aplicada |
|---|---|---|
| 1 | `record_id` colisionaba entre dos filas físicas distintas que compartían `source_record_id`. | Se redefine `record_id` como hash de la **ocurrencia física** (`occurrence_key`), no del `source_record_id` de negocio en solitario. Se añade `duplicate_group_key` para agrupar duplicados sin fusionarlos. Invariante duro añadido: dos ocurrencias físicas distintas nunca comparten `record_id`. |
| 2 | `CanonicalField.original_value` y `Provenance.original_value` duplicaban el mismo valor. | Se elimina `Provenance.original_value`. `CanonicalField.original_value` queda como única fuente de verdad. Se añade `Provenance.evidence_excerpt` (opcional, solo fuentes documentales) para el caso en que hace falta más contexto que el valor del campo. |
| 3 | `CanonicalField` se presentaba como "entidad con identidad propia" y a la vez "sin identidad global" — contradicción sin resolver. `Relationship.relationship_id` sin decidir. | Se introduce una taxonomía explícita de tres niveles de identidad (global con colección propia / local sin colección propia / sin identidad). `CanonicalField` queda en el nivel local (coordenada `record_id`+`field_name`). Se resuelve que `Relationship` sí necesita `relationship_id`, pero de alcance local (nunca una colección global). |
| 4 | Un único `CanonicalRecord.status` mezclaba progreso de pipeline con resultado final. | Se separa en `processing_stage` (`extracted→normalized→mapped→transformed→validated→exported`) y `disposition` (`pending→exportable\|excluded\|failed`). Sin máquina de estados formal. |
| 5 | `Execution` dependía de un único `object_type`, incompatible con ejecuciones multi-objeto. | Se elimina `object_type` de `Execution` (queda solo en `CanonicalRecord`). Se añaden `scope`/`object_types`, ambos opcionales e informativos. |
| 6 | `source_type` presentado de forma ambigua, sin incluir `api`. | Se declara explícitamente como vocabulario controlado pero **abierto** (un Connector nuevo declara su propio valor sin tocar el Core). Se añade `api` con su fila de `locator` propia. |
| 7 | Revisión humana sin trazabilidad de quién/cuándo. | Se añaden `reviewed_by`/`reviewed_at`, opcionales, presentes solo tras una revisión. |
| 8 | Forma de `TransformationTrace` (única vs. secuencia) resuelta implícitamente sin evidencia suficiente. | Se declara explícitamente como decisión diferida a una futura Mapping Specification — no se resuelve en este documento. |
| 9 | Documento y ADR-014 marcados "Approved Design" sin revisión formal previa. | Ambos pasan a **Proposed**. Se añade § 28 "Historial de revisión" al documento de arquitectura, y una sección "Revisión del 2026-07-27" al Context de la ADR. |
| 10 | Recomendación de siguiente paso saltaba directamente a un segundo Connector. | Corregida al orden aprobado: (1) aprobar CDM, (2) Mapping Specification, (3) Enablon Template Contract, (4) implementar Framework Core, (5) validar con consumidores reales, (6) segundo Connector. Documentado en ADR-014 § Consequences. |

---

## 2. Decisiones finales

- **Identidad en 4 conceptos** (no 3): `record_id` (técnica, hash de la ocurrencia física, nunca colisiona entre filas físicas distintas), `source_record_id` (del origen, puede repetirse — es la señal del duplicado), `functional_key` (funcional, opcional), `duplicate_group_key` (agrupación de duplicados, opcional). `Execution.execution_id` sigue siendo un `uuid4` aleatorio, concepto aparte.
- **Estrategia de `record_id`**: `record_id = "record:" + slugify(object_type) + "." + slugify(source_system) + "." + short_hash(occurrence_key)`, donde `occurrence_key` prioriza una clave física nativa (`identity_basis: physical_key`), cae a clave de negocio + ordinal de extracción (`source_key_with_ordinal`) si no existe, y finalmente al `locator` (`locator_derived`) para fuentes sin ninguna clave estable. El algoritmo exacto del ordinal se deja como decisión de implementación — lo que se fija es el invariante de no colisión.
- **Taxonomía de identidad en 3 niveles**: (a) global con colección propia — `Execution`, `CanonicalRecord`, `Issue`; (b) local sin colección propia — `CanonicalField` (coordenada), `Relationship` (`relationship_id` local); (c) sin identidad — `Provenance`, `TransformationTrace`.
- **`Provenance` sin duplicar valor**: localiza y explica (`source_type`, `locator`, `extraction_method`, `confidence`, `captured_at`, `evidence_excerpt?`), nunca vuelve a guardar el valor extraído.
- **`processing_stage` + `disposition`** como dos campos obligatorios independientes en `CanonicalRecord`, sin máquina de estados formal.
- **`Execution.scope`/`object_types`** opcionales, en vez de un `object_type` obligatorio — `object_type` vive exclusivamente en `CanonicalRecord`.
- **`source_type` es vocabulario abierto**, ilustrado con `sql_server`, `excel`, `csv`, `word`, `pdf`, `json`, `api` — nunca una enumeración cerrada del Core.
- **Revisión humana**: 5 atributos embebidos en `CanonicalField` (`review_required`, `review_status`, `review_note`, `reviewed_by?`, `reviewed_at?`). Sigue sin existir una entidad `Review`.
- **`TransformationTrace`**: forma exacta (objeto único vs. secuencia) explícitamente diferida a la futura Mapping Specification.
- **Status**: `canonical-data-model.md` y `ADR-014` quedan en **Proposed** hasta que esta revisión se dé por cerrada y aprobada.

---

## 3. Ejemplo corregido de registro duplicado

Añadido como nueva § 20.2 del documento de arquitectura. Reproducido aquí:

```
CanonicalRecord  (primera ocurrencia física)
  record_id: record:event.prevencion_itp.7f1a2b3c4d      -- DISTINTO del segundo
  object_type: "Event"
  source_record_id: "10532"                                -- IGUAL en ambos -- señal del duplicado
  duplicate_group_key: event.prevencion_itp.10532          -- IGUAL en ambos -- agrupa sin fusionar
  identity_basis: source_key_with_ordinal
  source_reference: { source_system: "prevencion_itp", source_object: "ITP_EVENTOS",
                       extraction_method: "sql_query" }
  processing_stage: extracted
  disposition: pending

CanonicalRecord  (segunda ocurrencia física -- el duplicado)
  record_id: record:event.prevencion_itp.9c8d7e6f5a      -- DISTINTO del primero
  object_type: "Event"
  source_record_id: "10532"                                -- IGUAL que el anterior
  duplicate_group_key: event.prevencion_itp.10532          -- IGUAL que el anterior
  identity_basis: source_key_with_ordinal
  processing_stage: extracted
  disposition: pending
```

`Issue` generada por el Validation Engine al detectar el grupo:

```
Issue
  stage: validation
  severity: warning
  code: DUPLICATE_SOURCE_RECORD_ID
  message: "2 registros comparten duplicate_group_key=event.prevencion_itp.10532
            (source_record_id=10532) -- defecto sistémico ya confirmado en
            Eventos/OPS, ver CLAUDE.md."
  record_id: record:event.prevencion_itp.7f1a2b3c4d
  status: open
  blocks_export: false
```

Ningún `record_id` colisiona; la duplicación queda visible y trazable, no oculta ni fusionada — cumple el invariante exigido por la revisión.

---

## 4. Ejemplo corregido de provenance

Extracto del ejemplo PDF/Word (§ 22 del documento), mostrando `evidence_excerpt` reemplazando la duplicación de `original_value` eliminada:

```
fields.ResponsibleRole:
  original_value: "El Jefe de Turno, o en su ausencia el Responsable de Planta"   -- ÚNICA fuente de verdad
  normalized_value: "Jefe de Turno / Responsable de Planta"
  data_type: string
  provenance:
    source_type: pdf
    locator: { file: "PR-EMG-014.pdf", page: 4, block_or_table: "párrafo 2" }
    extraction_method: native_text
    confidence: 0.55
    evidence_excerpt: "En caso de emergencia, la coordinación inicial corresponde
                        al Jefe de Turno, o en su ausencia el Responsable de Planta,
                        quien activará el protocolo PR-EMG-014 sección 3."
                        -- párrafo completo, más amplio que original_value -- permite
                        -- verificar la interpretación en contexto SIN duplicar el valor
  review_required: true
  review_status: pending
  reviewed_by: null
  reviewed_at: null
```

`Provenance` ya no contiene `original_value` propio: solo localiza (`locator`), explica (`extraction_method`, `confidence`) y, cuando aporta algo real, amplía el contexto (`evidence_excerpt`) — nunca vuelve a guardar el valor del campo.

---

## 5. Modelo conceptual actualizado

```
Execution (execution_id, started_at, mode, status, scope?, object_types?)
  │
  │ produce N -- puede ser de varios object_type distintos en la misma Execution
  ▼
CanonicalRecord (record_id, object_type, source_record_id,
                 functional_key?, duplicate_group_key?, identity_basis,
                 source_reference, processing_stage, disposition, metadata)
  │
  ├── fields: { field_name -> CanonicalField }        -- (record_id, field_name), sin identidad global
  │              ├── original_value / normalized_value / transformed_value
  │              ├── data_type (detectado)
  │              ├── provenance                (embebida, sin identidad)
  │              ├── transformation_trace?      (embebida -- forma exacta diferida)
  │              └── review_required / review_status / review_note / reviewed_by? / reviewed_at?
  │
  ├── relationships: [ Relationship, ... ]   (identidad LOCAL -- relationship_id)
  │
  └── issues: consultables por record_id     (Issue -- issue_id global, colección propia)

Relationship (relationship_id, relationship_type, source_record, target_record?,
              target_reference?, direction, required, resolution_status)

Issue (issue_id, execution_id, stage, severity, code, message,
       record_id, field_name?, relationship_id?, rule_reference?, status,
       resolution?, source_value?, transformed_value?, blocks_export)
```

---

## 6. Cambios en ADR-014

- **Status**: `Approved Design` → **`Proposed`**.
- Nueva subsección de Context: "Revisión del 2026-07-27", listando los 10 problemas encontrados.
- **Decision** reescrita completa: taxonomía de identidad de 3 niveles, identidad en 4 conceptos con invariante de no colisión, `Provenance` sin duplicar valor + `evidence_excerpt`, `processing_stage`/`disposition` separados, `Execution` sin `object_type` único, revisión humana con `reviewed_by`/`reviewed_at`, forma de `TransformationTrace` diferida.
- **Consequences**: añadido el orden aprobado de próximos pasos (6 puntos, corrige la recomendación anterior).
- **Alternatives Rejected**: se añaden explícitamente las decisiones de la v1 de esta misma ADR que la revisión obligó a descartar (record_id por source_record_id solo, duplicación de original_value, status único) — para dejar trazabilidad de que esta ADR se corrigió a sí misma, no que apareció así desde el principio.

Índice (`docs/02-adr/README.md`): estado de ADR-014 actualizado a "Proposed (en revisión arquitectónica)".

---

## 7. Riesgos pendientes

Todos documentados en § 26 del documento de arquitectura (extendida con uno nuevo):

- Diseño no validado empíricamente todavía (sin segundo Connector real).
- Las fusiones de entidad podrían resultar insuficientes en la Fase P6 documental.
- Identidad basada en `locator` para fuentes sin clave estable sigue siendo frágil ante re-paginación (no resuelto, es un límite del propio problema).
- **Nuevo**: `identity_basis: source_key_with_ordinal` depende de que la fuente ofrezca un orden de lectura estable entre ejecuciones — sin `ORDER BY` determinista, el `record_id` de un duplicado podría no ser reproducible entre ejecuciones distintas (aunque sí cumple el invariante de no colisión dentro de una misma ejecución).
- `Provenance` embebido por campo incrementa el tamaño de cada registro serializado.
- Riesgo de confusión entre este CDM y `src/knowledge_base/model.py` por vocabulario similar.

Cuestión que la revisión deja explícitamente para más adelante: el algoritmo exacto del ordinal de extracción y la longitud/función de `short_hash` son decisiones de implementación, no de esta ADR (§ 25 del documento).

---

## 8. Archivos creados y modificados

**Modificados** (ya existían de la tarea anterior, corregidos en esta revisión):
- `docs/01-architecture/canonical-data-model.md`
- `docs/02-adr/ADR-014-canonical-data-model.md`
- `docs/02-adr/README.md` (estado de ADR-014 actualizado)

**Creados** (esta revisión):
- `reports/executions/2026-07-27/Informe-Revision-Canonical-Data-Model-EMF.md` (este informe)
- `reports/executions/2026-07-27/Informe-Revision-Canonical-Data-Model-EMF.txt` (mismo informe, texto plano)

Ningún archivo de `src/`, `tests/`, `config/`, `sql/`, `main.py`, `requirements.txt`, `CLAUDE.md` ni documentación legada fue tocado.

---

## 9. Rutas de los informes

- MD: `reports/executions/2026-07-27/Informe-Revision-Canonical-Data-Model-EMF.md`
- TXT: `reports/executions/2026-07-27/Informe-Revision-Canonical-Data-Model-EMF.txt`

Contenido idéntico entre ambos — la única diferencia es de formato (el `.md` usa tablas y encabezados Markdown; el `.txt` usa el mismo contenido con separadores ASCII en texto plano).

---

## 10. Resultado de validaciones

- [OK] Ausencia de colisiones conceptuales de `record_id`: verificado — el invariante ("nunca compartido entre ocurrencias físicas distintas") está explícito en § 9 y demostrado en el ejemplo § 20.2.
- [OK] Ausencia de `original_value` duplicado: verificado — eliminado de `Provenance`, confirmado en § 12 y en el ejemplo § 22.
- [OK] Coherencia entre entidades con identidad y entidades embebidas: verificado — taxonomía de 3 niveles aplicada de forma consistente en § 6, § 7 y § 9.
- [OK] Separación entre `processing_stage` y `disposition`: verificada en § 17, sin máquina de estados formal.
- [OK] `Execution` compatible con varios `object_type`: verificado en § 9.1, con precedente real citado (`MigrationObject.processing_scope` cross_module).
- [OK] `source_type` extensible e incluyendo `api`: verificado en § 12.
- [OK] Revisión humana trazable: `reviewed_by`/`reviewed_at` añadidos en § 14.
- [OK] ADR-014 en estado `Proposed`: verificado en el encabezado de la ADR y en el índice.
- [OK] Enlaces relativos: revisados uno a uno, todos resuelven a ficheros existentes.
- [OK] `git diff --check`: sin errores de formato (solo aviso de normalización de fin de línea LF→CRLF, no de contenido).
- [OK] `git status --short`: solo los archivos declarados en la sección 8 corresponden a esta revisión.
- [OK] `git diff --stat`: no aplica de forma útil (ficheros no trackeados en git — ver sección 12).

---

## 11. git status --short

```
?? docs/01-architecture/canonical-data-model.md   (modificado en esta revisión)
?? docs/02-adr/ADR-014-canonical-data-model.md      (modificado en esta revisión)
?? docs/02-adr/README.md                             (modificado en esta revisión)
?? reports/executions/2026-07-27/                    (informes de esta y la tarea anterior)
```

(el resto de `docs/00-blueprint`, `01-architecture`, `02-adr`,
`03-engineering-standards`, `04-roadmap`, `05-sprint-reviews`,
`06-releases`, `07-developer-guide`, `08-user-guide` ya figuraban sin
trackear antes de esta tarea — no fueron creados ni modificados por ella)

## 12. git diff --stat

No aplica de forma útil: ninguno de los ficheros de este repositorio está
trackeado todavía en git (no ha habido ningún commit sobre `docs/`), por lo
que `git diff` no tiene una versión previa contra la que comparar.
Verificado en su lugar con `git diff --no-index --check` contra cada
fichero modificado: sin errores de espacio en blanco (único aviso:
normalización de fin de línea LF→CRLF, propia de la configuración de git
en este entorno, no un problema de contenido).

---

## Recomendación del siguiente paso (corregida)

Orden aprobado por esta revisión, registrado en ADR-014 § Consequences:

1. Aprobar este Canonical Data Model (cerrar la revisión actual).
2. Diseñar la Mapping Specification (resuelve, entre otras cosas, la forma
   exacta de `TransformationTrace`).
3. Diseñar el Enablon Template Contract (Enablon Template Registry).
4. Implementar el Framework Core (Sprint 4.1).
5. Validar con consumidores reales.
6. Incorporar un segundo Connector cuando corresponda.

No se realizó commit de ningún cambio.
