# Data Processing Lifecycle — EMF

**Status:** Approved Design (flujo conceptual y forma del modelo canónico;
sin tipos Python implementados todavía).

## 1. El flujo obligatorio

EMF nunca se diseña como una transformación directa `Fuente → CSV Enablon`.
Toda migración, sin importar la fuente, atraviesa las mismas ocho etapas:

```
1. Fuente                    (SQL Server, Excel, CSV, Word, PDF, JSON...)
        │  Connector específico de la fuente
        ▼
2. Extracción                 (Extraction Engine + un Connector)
        │
        ▼
3. Registros normalizados     (forma común, con provenance -- ver § 2)
        │
        ▼
4. Modelo intermedio común    (Canonical Data Model -- mismo tipo que el paso 3,
        │                      nombrado aparte porque es el punto de
        │                      integración: todos los Connectors convergen aquí)
        ▼
5. Mapeo                      (Mapping Engine, mapeos como datos -- ADR-013)
        │
        ▼
6. Transformación              (Transformation Engine, catálogo de reglas)
        │
        ▼
7. Validación                  (Validation Engine -- devuelve issues, no lanza
        │                       excepción por regla de negocio, ver § 4)
        ▼
8. CSV Enablon                 (Export Engine, contrato del Enablon Template
        │                       Registry)
        ▼
9. Evidencias y manifest       (Evidence Engine -- nunca vuelve a consultar
                                la fuente, lee solo los artefactos ya escritos)
```

Por qué importa el desacople 3↔4 frente a "SQL directo a CSV": cualquier
Engine desde el paso 5 en adelante trabaja **exclusivamente** sobre la forma
canónica del paso 3/4. Ni el Mapping Engine ni el Transformation Engine
saben nunca que un registro vino de SQL Server o de un PDF — eso es
exactamente lo que permite añadir una fuente nueva sin tocar ningún Engine
(ver [`extensibility-model.md`](extensibility-model.md) § 1).

## 2. Forma conceptual del Registro Normalizado

Sin comprometer todavía un tipo Python concreto (eso es implementación, no
arquitectura), todo Registro Normalizado debe poder representar:

```
RegistroNormalizado
├── source_system        -- de qué sistema/proyecto viene (ej.: "prevencion", "moeve.word.procedimientos")
├── source_object         -- objeto/tabla/documento de origen
├── source_record_id      -- identificador dentro de la fuente (fila, id de documento...)
├── extracted_at           -- momento de extracción (UTC)
├── fields                 -- {nombre_campo: ValorDeCampo}
└── provenance              -- ver § 3, siempre presente, nunca opcional
```

Cada `ValorDeCampo` conserva, como mínimo, su valor y su origen dentro del
registro (para que un mapeo pueda referenciar "el campo X tal como llegó",
no solo "el campo X tal como quedó tras normalizar").

## 3. `provenance` — el campo que nunca se omite

Todo Registro Normalizado, sea cual sea su fuente, lleva un bloque
`provenance`. Para fuentes estructuradas la mayoría de campos son triviales;
para fuentes documentales son esenciales y a menudo determinan si el
registro requiere revisión humana antes de continuar el pipeline.

| Campo de `provenance` | SQL Server / CSV / JSON | Excel | Word / PDF |
|---|---|---|---|
| `source_file` | nombre de la conexión/fichero de query | ruta del `.xlsx` | ruta del `.docx`/`.pdf` |
| `page` | N/A | N/A (u hoja, si aplica) | número de página |
| `section` | N/A | nombre de hoja | encabezado/sección detectada |
| `table_or_block` | N/A | rango de celdas | tabla o bloque de texto identificado |
| `extraction_method` | `sql_query` (hash de la query, no el texto — ver [`security-standards.md`](../03-engineering-standards/security-standards.md)) | `openpyxl` / lectura de celda | OCR, extracción de texto nativo, extracción de tabla... (a especificar por Connector) |
| `original_value` | el valor tal cual lo devuelve el driver | el valor de celda tal cual | el texto/tabla tal cual se extrajo, sin limpiar |
| `normalized_value` | normalmente igual a `original_value` | normalmente igual | tras limpieza determinista (espacios, saltos de línea...), si aplica |
| `confidence` | `1.0` (un valor SQL no es una interpretación) | `1.0` si la celda es un valor simple; menor si depende de fórmula | `< 1.0` casi siempre — depende del método de extracción |
| `human_review` | `false` por defecto | `false` por defecto | `true` si `confidence` cae bajo un umbral a definir por el Connector, o si el propio método de extracción no puede autoevaluarse |
| `issues` | vacío salvo error de tipo/formato | vacío salvo error de tipo/formato | frecuente: tabla mal delimitada, texto no reconocido, página no legible... |

**No se asume que la extracción documental tiene la misma certeza que una
fila de SQL o una celda de Excel.** Un futuro Word/PDF Connector que no
pueda poblar `confidence`/`human_review` de forma honesta no cumple el
contrato del modelo canónico — no se acepta un `confidence` fijo a `1.0`
"porque sí" para una fuente documental.

## 4. Relación con el patrón `validate_*` ya existente

El Validation Engine (paso 7) hereda, sin cambiarlo, el patrón ya
documentado en
[`naming_conventions.md`](../architecture/v1.0/naming_conventions.md)
legado: una validación de regla de negocio **devuelve una lista de
violaciones**, nunca lanza una excepción. Esto ya está confirmado en código
real (`PreWriteValidation`/`PostWriteValidation` en
`src/export/prototype/drills/validator.py`). El futuro `ValidationError` del
Core (Sprint 4.1) está reservado para errores de infraestructura del propio
motor de validación (p. ej. "no hay validador registrado para este tipo de
campo"), no para sustituir este patrón.

## 5. Relación con Evidence First

El paso 9 (Evidencias y manifest) nunca vuelve a consultar la fuente
original — lee exclusivamente los artefactos ya escritos por los pasos
anteriores (mismo principio que `src/evidence/collector.py` aplica hoy para
Drills, ver [ADR-008](../02-adr/ADR-008-evidence-first.md)). El `provenance`
de cada registro (§ 3) es precisamente lo que permite construir evidencia
completa sin volver a tocar SQL Server, un Excel o un PDF.

## 6. Qué de esto existe hoy, en código real

| Etapa | Implementación real hoy (acoplada a Drills, no generalizada) |
|---|---|
| Extracción | `src/export/prototype/drills/extractor.py` (+ Query Engine para filtros, `src/query/`) |
| Registros normalizados / modelo intermedio | No existe como tipo separado — hoy es directamente un `pandas.DataFrame` con las columnas crudas de la query SQL de Drills. |
| Mapeo | `reference_data` en `config/exports/drills.yaml` + `src/export/prototype/drills/mappings.py` |
| Transformación | `src/export/prototype/drills/transformations.py` |
| Validación | `src/export/prototype/drills/validator.py` |
| CSV Enablon | `src/export/prototype/drills/exporter.py` + `pipeline.py` |
| Evidencias y manifest | `src/evidence/` + `export_manifest.yaml`/`validation_report.yaml` |

La ausencia de un tipo de "Registro Normalizado" real hoy (se usa
directamente el DataFrame de la query SQL) es la brecha más importante entre
el estado actual y este documento — es, precisamente, lo que impide hoy
añadir una fuente no-SQL sin reescribir el pipeline de Drills desde cero.
Cerrar esa brecha es el objetivo del futuro Canonical Data Model.
