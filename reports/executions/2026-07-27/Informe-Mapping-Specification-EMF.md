# Informe — Mapping Specification (EMF)

**Proyecto:** Enablon Migration Framework (EMF)
**Fecha:** 2026-07-27
**Tarea:** Diseño arquitectónico de la Mapping Specification (sin implementación de código).

---

## 1. Hallazgos del repositorio

- **No existe hoy un modelo formal de "regla de mapeo"** — lo que existe
  son tres capas parciales y no unificadas: `config/exports/drills.yaml`
  (`FieldSpec`, mapeo concreto de un objeto), `config/validation_rules.yaml`
  (catálogo de nombres de regla confirmados con datos reales, sin modelo
  de identidad/versión/condición), y `src/etl/` (`excel_reader.py`,
  `mapping_resolver.py`, `mapping_engine.py`, `transformations.py` —
  lectura/aplicación de hojas Excel legadas). Este documento es la primera
  vez que se unifican en un modelo declarativo único.
- **`src/etl/transformations.py` (`RULE_REGISTRY`/`resolve_rule`) es el
  precedente exacto de `registered_transform`**: un nombre de regla
  resuelto contra un registro de funciones ya implementadas — nunca un
  `if`/`elif` disperso ni código nuevo por regla.
- **Dos patrones de hoja Excel ya confirmados con ETL reales**:
  `read_field_mapping_sheet` (8 columnas: `CampoOrigen | Field Destiny XML
  | Field Destiny ES | Adaptación | Transformation From | (vacía) | XML |
  ES`) y `read_rule_table_sheet` (5 columnas: `DatoOrigen | DatoDestino |
  EsCondicion | ReglaEspecial | Parametro`). Ambos informan directamente
  la plantilla Excel propuesta (§ 21 del documento) y el modelo de
  `Condition` (la columna `EsCondicion` es el precedente literal de
  `rule_type: conditional`).
- **`mapping_resolver.py` ya implementa, con datos reales, exactamente el
  comportamiento de "nunca elegir un lookup ambiguo en silencio"**
  (`AMBIGUOUS`/`duplicate_es_labels`) y "normalización de espacio sin
  tocar mayúsculas" (`normalize_label`) — ambos generalizados literalmente
  en el modelo de `value_map` (§ 16).
- **`config/exports/drills.yaml` ya separa `reference_data` (tablas
  grandes) de `fields` (mapeo por columna)** — precedente directo de
  separar `ValueMapEntry` de `MappingRule` en hojas distintas.
- **`config/validation_rules.yaml` confirma qué reglas están realmente
  probadas con datos reales y cuáles no** (`confirmado_con_datos_reales:
  true|false|partial`) — usado para decidir qué `rule_type` se generaliza
  con confianza (`nullcontrol`, `concat`, `cloneorigin`, `lookup_simple`,
  `lookup_dinámico_dos_pasos`) y cuál exige la vía de escape
  `registered_transform` por no tener motor declarativo confirmado
  (`titlefix`, sin fórmula ni VBA visible en 7 libros auditados).
- **`config/modules.yaml` (`ap.campos_de_enlace_a_otros_modulos`)** es el
  precedente real del `rule_type: reference` (Action Plans enlazando a
  Events/Bypass/MOC/Simulacros/OPS/Inspecciones/Safety Meetings).

---

## 2. Modelo propuesto

```
MappingSet (mapping_set_id, version, project, module, object_type,
            source_schema_version?, target_template_version?, status, rules, metadata)
  └── rules: [ MappingRule, ... ]

MappingRule (rule_id, revision, rule_type, source_fields, target_field,
             read_from, condition_ref?, parameters, priority, required,
             enabled, status, justification, owner, effective_from/to,
             [solo exclusion] exclusion_code/reason/rule_reference/approved_by/at/scope)

Condition (condition_id, operator, field_ref?, literal?, children?)
ValueMapEntry (value_map_id, source_value, target_value, status, justification,
               valid_from/to, scope, normalization)
LookupDefinition (lookup_id, catalog_ref, steps[], on_no_match)
```

`MappingSpecification` (nombre sugerido en el encargo) se renombra a
`MappingSet` para que su identificador (`mapping_set_id`) no quede
desalineado con el nombre de la entidad — "Mapping Specification" queda
reservado para el nombre del documento/diseño en conjunto.

---

## 3. Entidades y estructuras seleccionadas

| Entidad | Decisión |
|---|---|
| `MappingSet` | Mantenida (renombrada), entidad de nivel superior con identidad global (`mapping_set_id`) y versión propia (`version`). |
| `MappingRule` | Mantenida, identidad estable (`rule_id`) + revisión (`revision`), independiente de la versión del conjunto. |
| `Condition` | Mantenida como entidad propia (no un campo de texto) — evita condiciones ilegibles anidadas en una celda. |
| `ValueMapEntry` | Mantenida, externalizada de `MappingRule` para tablas grandes (generaliza `reference_data` ya separado en `drills.yaml`). |
| `LookupDefinition` | Nueva respecto al esbozo del encargo — necesaria para declarar lookups multi-paso (2-step ya confirmado) sin mezclarlos con `value_map`. |
| `Review`/`ValidationResult` como entidades propias | No creadas — el resultado de aplicar una regla vive en `TransformationTrace` (CDM) e `Issue` (CDM), nunca duplicado aquí. |

---

## 4. Tipos de regla

Doce `rule_type`, cada uno con evidencia real que lo respalda (tabla completa en el documento § 10):

`direct`, `constant`, `default`, `value_map`, `lookup`, `conditional`,
`concatenate`, `type_conversion`, `date_conversion`, `reference`,
`exclusion`, `registered_transform`.

Fusiones decididas: `boolorigin`/`replaceinreference`/`lookup_simple` →
`value_map` (sin comportamiento distinguible con la evidencia
disponible); el fan-out de `cloneorigin` (1→5 idiomas) → varias reglas
`direct`, nunca un tipo nuevo. `barconcat` → `concatenate` con
`separator=" | "`, no un tipo aparte.

---

## 5. Modelo de condiciones

Operadores cerrados: `equals`, `not_equals`, `in`, `not_in`, `is_null`,
`is_not_null`, `contains`, `starts_with`, `greater_than`, `less_than`,
`and`, `or` — exactamente los evaluados en el encargo, sin ampliar (no se
añade `regex` ni `ends_with`, sin evidencia real que los necesite como
condición declarativa).

- Condiciones compuestas: sí, vía `and`/`or` con lista de `children`.
- Profundidad recomendada: ≤ 3 niveles (recomendación de diseño, no
  restricción técnica).
- `field_ref`: siempre un `CanonicalField.field_name` del mismo registro.
- `literal`: tipado según los tipos canónicos mínimos del CDM; `in`/`not_in`
  exigen lista; `is_null`/`is_not_null` no admiten literal.

---

## 6. Estrategia de prioridad y conflictos

Regla dura: **ningún conflicto se resuelve por orden de aparición en el
fichero**. Resumen (tabla completa en el documento § 12):

- Misma `priority`, condiciones potencialmente simultáneas → error de
  validación (`OVERLAPPING_RULES`).
- `default` junto a otra regla → válido si `default` tiene la `priority`
  más baja (se evalúa último); si no, advertencia (`DEFAULT_NOT_LAST`).
- Exclusión de alcance `record` → precedencia fija y documentada sobre
  cualquier transformación de campo de ese registro (generaliza
  `EntityResolution.DO_NOT_MIGRATE`, ya implementado).
- Lookup/value map con más de un resultado posible → nunca se elige uno;
  resultado `status=conflicting` (generaliza `EntityCatalog.conflicting_keys`).
- Referencia no resuelta → no es un conflicto, es el estado esperado
  `pending`/`unresolved` de una `Relationship` (CDM).

---

## 7. Modelo de value maps

`ValueMapEntry` vive en su propia colección (`value_map_id`), nunca
embebida en la fila de `MappingRule` — generaliza `reference_data` de
`drills.yaml`. Campos: `source_value`, `target_value`, `status`,
`justification`, `valid_from`/`valid_to`, `scope`, `normalization`
(`none`\|`trim`\|`trim_and_collapse_whitespace`\|`case_insensitive`,
generaliza literalmente `normalize_label()`). Valores no encontrados:
`on_no_match: fail|default_value|unresolved`. Duplicados (mismo
`source_value`, `target_value` distinto) → error de validación, nunca
elegido en silencio (generaliza `conflicting_keys`/`duplicate_es_labels`).

---

## 8. Modelo de lookups y referencias

| Concepto | Representación |
|---|---|
| Value map estático | `rule_type: value_map` |
| Lookup contra catálogo cargado (incl. 2 pasos) | `rule_type: lookup` + `LookupDefinition.steps` |
| Referencia a otro `CanonicalRecord` | `rule_type: reference` → produce una `Relationship` (CDM), no un valor plano |
| Referencia a entidad Enablon (dato maestro) | `rule_type: lookup` cuyo catálogo ya contiene identificadores nativos de Enablon — no es un tipo distinto |
| Referencia no resuelta | Estado `pending`/`unresolved` de la `Relationship`, o `on_no_match: unresolved` |

Catálogos siempre referenciados por **nombre lógico** (`catalog_ref`),
nunca ruta de fichero ni cadena de conexión — esa resolución es
responsabilidad de la configuración de proyecto, fuera de esta
especificación.

---

## 9. Decisión sobre null/default/vacío/exclusión

Siete conceptos distinguidos explícitamente (tabla completa § 17):
campo ausente, valor origen nulo, cadena vacía, valor no mapeado, valor
por defecto, campo destino vacío deliberadamente (`exclusion` con
`scope: field`), y "No migra" (un valor de negocio que, vía `lookup`/
`value_map`, coincide con un literal declarado `treat_as_exclusion_when`
— escala automáticamente a exclusión de alcance `record`, generalizando
`EntityCatalog.do_not_migrate_literal`). Regla explícita: **"sin
equivalencia" nunca se convierte automáticamente en "No migra"** — un
valor `unresolved` se queda `unresolved` hasta que alguien declare
explícitamente lo contrario.

Exclusiones (`rule_type: exclusion`): `scope` (`record`\|`field`\|
`relationship`), `exclusion_code`, `reason` (obligatorio, generaliza
`excluded_columns` de `drills.yaml`), `rule_reference`, `approved_by`/
`approved_at` (recomendado en `scope=record`).

---

## 10. Decisión sobre TransformationTrace

**Resuelve la decisión que ADR-014 dejó explícitamente diferida.** Se
adopta una lista ordenada y **acotada** de `TraceStep`, cuya longitud se
deriva de la forma que la propia `MappingRule` aplicada ya declara (1 paso
para `direct`/`constant`/`default`/`concatenate`/`type_conversion`/
`date_conversion`; N pasos para un `lookup` con N `steps` declarados; 2
pasos para `conditional`) — nunca un objeto único (perdería la señal de
pasos intermedios fallidos) ni una secuencia genérica sin límite conocido
de antemano (sería event sourcing). Cada `TraceStep` es una referencia
ligera (`rule_id`, `status`, `catalog_ref?`), nunca una copia del valor
(que ya vive en `CanonicalField`). Se expone `summary_status` = estado del
último paso.

---

## 11. Diseño conceptual del Excel

Nueve hojas (tabla completa § 21): **Mapping Set**, **Field Rules**,
**Value Maps**, **Lookups**, **Conditions**, **Exclusions**,
**Registered Transforms** (solo lectura, poblada solo por quien
implementa código), **Metadata**, **Validation Lists** (listas cerradas
que alimentan los desplegables de Excel de todas las demás hojas — el
mecanismo concreto que impide texto libre en columnas de vocabulario
cerrado). `Field Rules` generaliza directamente el patrón de 8 columnas
ya confirmado; `Registered Transforms` es la única puerta hacia
comportamiento no declarativo, y un consultor funcional solo *selecciona*
de esa lista, nunca escribe código.

---

## 12. Validaciones

Doce validaciones (tabla completa § 22), todas ejecutables **hoy** salvo
una explícitamente marcada como pendiente: la existencia de `target_field`
en una plantilla real de Enablon **no es verificable hasta que exista el
Enablon Template Contract** — se documenta como limitación, nunca se
asume. El resto (IDs duplicados, campos obligatorios, `rule_type`/
`operator`/`transform_name` desconocidos, catálogos no declarados,
condiciones inválidas, prioridades conflictivas, value maps duplicados,
ciclos de referencia, reglas aprobadas sin justificación, conjunto
`approved` con reglas no aprobadas) son verificables sin ese componente.

---

## 13. ADR creada o justificación

Se creó **ADR-015** — "Mapping Specification: modelo de reglas,
conflictos y TransformationTrace"
(`docs/02-adr/ADR-015-mapping-specification.md`), **Status: Proposed**.

**Justificación**: ADR-013 fija el principio general ("mappings as
data") pero no el modelo exacto de reglas, la estrategia de conflictos, la
frontera declarativo/`registered_transform`, el modelo de identidad/
versión de una regla individual, ni — la pregunta explícitamente diferida
por ADR-014 — la forma de `TransformationTrace`. Son decisiones
estructurales nuevas, cumpliendo el criterio explícito del encargo para
justificar una ADR nueva.

Índice actualizado (`docs/02-adr/README.md`): fila nueva para ADR-015,
próximo número libre actualizado a **ADR-016**.

---

## 14. Riesgos

- Diseño no validado empíricamente todavía (sin Mapping Engine
  implementado) — mismo riesgo ya reconocido para el CDM en ADR-011/014.
- `MappingSet.version` es, de facto, un quinto eje de versión no
  incorporado a la tabla de cuatro ejes del Blueprint (§ 16) — señalado,
  no corregido (Blueprint es documentación legada, fuera de los archivos
  autorizados de esta tarea).
- La imposibilidad de validar `target_field` contra una plantilla real
  significa que una especificación puede aprobarse internamente coherente
  y aun así referenciar un campo de Enablon inexistente — riesgo aceptado
  explícitamente hasta que el Template Contract exista.
- La detección de solapamiento de condiciones es, en el caso general,
  indecidible sin evaluar combinaciones de valores — solo los casos
  triviales (misma condición exacta, ausencia de condición) se garantizan
  detectados; el caso general queda para el futuro validador.
- `registered_transform` reintroduce, deliberadamente, una dependencia de
  código dentro de un modelo por lo demás declarativo — riesgo aceptado a
  cambio de no inventar un lenguaje de expresiones propio.

---

## 15. Archivos creados y modificados

**Creados:**
- `docs/01-architecture/mapping-specification.md`
- `docs/02-adr/ADR-015-mapping-specification.md`
- `reports/executions/2026-07-27/Informe-Mapping-Specification-EMF.md` (este informe)
- `reports/executions/2026-07-27/Informe-Mapping-Specification-EMF.txt` (mismo informe, texto plano)

**Modificados:**
- `docs/02-adr/README.md` (fila nueva ADR-015, número libre actualizado a ADR-016)

Ningún archivo de `src/`, `tests/`, `config/`, `sql/`, ni documentación
legada fue tocado. No se creó el archivo `.xlsx` real.

---

## 16. Rutas de los informes MD y TXT

- MD: `reports/executions/2026-07-27/Informe-Mapping-Specification-EMF.md`
- TXT: `reports/executions/2026-07-27/Informe-Mapping-Specification-EMF.txt`

Contenido idéntico entre ambos — la única diferencia es de formato (el
`.md` usa tablas/encabezados Markdown; el `.txt` usa el mismo contenido
con separadores ASCII en texto plano).

---

## 17. Resultado de validaciones

- [OK] No hay código arbitrario representable en las reglas — verificado
  en § 9 del documento: todo campo de vocabulario abierto es una cadena
  cerrada o una referencia, nunca texto interpretado como código.
- [OK] La Mapping Specification no duplica el CDM (§ 3/§ 23) ni el futuro
  Template Contract (§ 3/§ 24).
- [OK] No contiene plantillas CSV completas — ningún ejemplo (§ 25) las
  incluye.
- [OK] Distingue `default`, `null`, vacío, ausencia y exclusión en 7
  representaciones distintas (§ 17).
- [OK] Distingue `value_map`, `lookup` y `reference` con criterio
  explícito (§ 15).
- [OK] Los conflictos no se resuelven silenciosamente — todos son error o
  advertencia de validación explícita (§ 12/§ 22).
- [OK] `TransformationTrace` queda resuelto (§ 20), cerrando la decisión
  diferida de ADR-014.
- [OK] Excel es interfaz de edición, nunca modelo de ejecución (§ 21) —
  no se crea el `.xlsx` real.
- [OK] Enlaces relativos revisados uno a uno — todos resuelven a ficheros
  existentes.
- [OK] `git diff --check`: sin errores de formato.
- [OK] `git status --short`: solo los archivos declarados en la sección 15.

---

## 18. git status --short

```
?? docs/01-architecture/mapping-specification.md   (nuevo)
?? docs/02-adr/ADR-015-mapping-specification.md      (nuevo)
   docs/02-adr/README.md                              (modificado)
?? reports/executions/2026-07-27/                      (informes de esta y tareas anteriores)
```

(el resto de `docs/*` ya figuraba sin trackear antes de esta tarea — no
fue creado ni modificado por ella)

## 19. git diff --stat

No aplica de forma útil: ningún fichero de este repositorio está
trackeado todavía en git (no ha habido ningún commit sobre `docs/`), por
lo que `git diff` no tiene una versión previa contra la que comparar.
Verificado en su lugar con `git diff --no-index --check` contra cada
fichero nuevo: sin errores de espacio en blanco (único aviso:
normalización de fin de línea LF→CRLF, propia de la configuración de git
en este entorno, no un problema de contenido).

---

## 20. Recomendación del siguiente paso

Según el orden ya aprobado en ADR-014 (§ Consequences): con el Canonical
Data Model y esta Mapping Specification diseñados, el siguiente paso es
**diseñar el Enablon Template Contract** (Enablon Template Registry,
Blueprint § 11) — el tercer contrato de datos que debe existir antes de
implementar el Framework Core. Recién después de los tres contratos
(CDM, Mapping Specification, Template Contract) tiene sentido implementar
el Core y validar con consumidores reales; un segundo Connector sigue
siendo el último paso de esta secuencia, no el siguiente.

No se realizó commit de ningún cambio.
