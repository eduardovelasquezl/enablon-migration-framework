# Mapping Specification — EMF

**Status:** Proposed. Diseño conceptual completo, sin tipos Python
implementados todavía. Depende conceptualmente de
[`canonical-data-model.md`](canonical-data-model.md) (marcado como
`Proposed` en este repositorio en el momento de escribir este documento —
ver § 0 nota de estado) y resuelve explícitamente la decisión que ADR-014
dejó diferida sobre `TransformationTrace` (§ 20).

## 0. Nota de estado sobre CDM/ADR-014

El encargo que originó este documento afirma que el Canonical Data Model y
[ADR-014](../02-adr/ADR-014-canonical-data-model.md) ya están "diseñados y
aprobados". En los ficheros de este repositorio, en el momento de escribir
este documento, ambos siguen marcados `Status: Proposed` (ver
`canonical-data-model.md` § 28, Historial de revisión). Este documento se
apoya en el contenido técnico de ambos (que no ha cambiado desde esa
revisión) sin asumir ni corregir su estado de aprobación — actualizar ese
estado no está entre los archivos autorizados para esta tarea. Se señala
aquí explícitamente para no dejar una contradicción silenciosa entre lo que
dice el encargo y lo que dice el repositorio.

## 1. Propósito

Definir cómo se representan, versionan, validan y trazan los mapeos entre
un origen extraído (`CanonicalRecord`/`CanonicalField`, ver
[`canonical-data-model.md`](canonical-data-model.md)) y los campos de
destino de Enablon — como **datos configurables, auditables y
versionables** (principio ya fijado en
[ADR-013](../02-adr/ADR-013-mappings-as-data.md)), nunca como ramas
condicionales embebidas en código.

## 2. Alcance

- El modelo conceptual de un conjunto de mapeos (`MappingSet`) y de una
  regla de mapeo individual (`MappingRule`).
- Un vocabulario cerrado de tipos de regla (`rule_type`), suficiente para
  expresar declarativamente el catálogo de reglas ya confirmado en
  `CLAUDE.md`/`config/validation_rules.yaml`, con una vía de escape
  controlada (`registered_transform`) para lo que no se puede expresar de
  forma segura como dato.
- Un modelo mínimo y seguro de condiciones declarativas.
- Una estrategia explícita, auditable, de prioridad y resolución de
  conflictos entre reglas — nunca "la última regla gana" en silencio.
- Un modelo de mapeo de valores (`value_map`) y de lookups contra
  catálogos referenciados, distinguiéndolos de una referencia a otro
  `CanonicalRecord`.
- Una distinción precisa entre valor nulo, cadena vacía, campo ausente,
  valor no mapeado, valor por defecto, campo vacío deliberado y "No
  migra".
- Un modelo de exclusiones explícitas y trazables.
- La resolución de la decisión que ADR-014 dejó diferida sobre la forma de
  `TransformationTrace`.
- Una plantilla Excel conceptual (hojas y columnas), como interfaz de
  edición humana — nunca como modelo de ejecución.
- Las validaciones que una especificación de mapeo debe superar antes de
  poder ejecutarse.

## 3. Fuera de alcance

Explícitamente, la Mapping Specification **no** contiene ni representa:

- El propio Canonical Data Model — no redefine `CanonicalRecord`,
  `CanonicalField`, `Provenance` ni `Relationship`; los referencia y los
  produce/consume, nunca los duplica (ver `canonical-data-model.md` § 3).
- El Enablon Template Contract (Enablon Template Registry, Blueprint §
  11) — no declara qué columnas exige una plantilla de Enablon, su orden,
  encoding ni formato. Referencia una `target_template_version` de forma
  opaca, a falta de que ese componente exista (§ 24).
- La lógica de ejecución del futuro Mapping Engine — el motor que
  interpreta cada `rule_type` sigue siendo código (ver ADR-009,
  Configuration over Code); esta especificación es el dato que ese motor
  consume, nunca el motor en sí.
- Plantillas CSV completas, configuración de conexiones, credenciales,
  SQL, `DataFrame`s — ninguna de estas cosas aparece en un `MappingRule`.
- Valores de registros concretos ni resultados de validación de un
  registro concreto — eso vive en `Issue` (CDM), no aquí. La Mapping
  Specification valida su propia forma (§ 22), nunca los datos de una
  ejecución real.
- Código Python arbitrario, SQL arbitrario, expresiones `eval`, fórmulas
  ejecutables no controladas, scripts incrustados, acceso a red o
  ficheros desde una regla (ver § 9, restricción central de este
  documento).
- Lógica específica de Drills — Drills se usa solo como fuente de
  ejemplos ya confirmados con datos reales, nunca como parte de la forma
  estructural del modelo.

## 4. Principios aplicados

- **Mappings as Data** ([ADR-013](../02-adr/ADR-013-mappings-as-data.md)):
  principio central heredado sin cambios — este documento es su
  desarrollo detallado, no una decisión nueva independiente.
- **Configuration over Code** ([ADR-009](../02-adr/ADR-009-configuration-over-code.md)):
  *qué* regla se aplica a *qué* campo es dato; *cómo* se ejecuta cada
  `rule_type` sigue siendo código.
- **Evidence First** ([ADR-008](../02-adr/ADR-008-evidence-first.md)):
  ninguna regla `approved` sin `justification`; ninguna exclusión sin
  `reason`; el estado `pending`/`unresolved` se conserva, nunca se oculta.
- **No Abstraction Without a Real Consumer** (principio 8): cada
  `rule_type` seleccionado (§ 10) generaliza un comportamiento ya
  confirmado con datos reales en `config/validation_rules.yaml` o
  `CLAUDE.md` — ninguno se inventa especulativamente.
- Restricción de complejidad del encargo: sin lenguaje de expresiones
  propio, sin `eval`, sin fórmulas ejecutables — un vocabulario cerrado de
  tipos de regla y operadores de condición, con una única vía de escape
  controlada (`registered_transform`) hacia código ya revisado.

## 5. Terminología

| Término | Significado |
|---|---|
| **Mapping Specification** | El conjunto de conceptos de este documento — no es una clase, es el nombre del diseño. |
| **`MappingSet`** | Una colección versionada y con alcance propio (proyecto/módulo/`object_type`) de `MappingRule`. Renombrado desde el `MappingSpecification` sugerido en el encargo — ver § 7 para la justificación del renombrado. |
| **`MappingRule`** | Una instrucción declarativa: qué campo(s) origen, qué `rule_type`, qué parámetros, bajo qué condición, producen un campo destino. |
| **Campo origen** | Un `CanonicalField.field_name` de un `CanonicalRecord` ya extraído — nunca una columna SQL o una celda Excel directamente (ver § 13). |
| **Campo destino** | Un nombre de campo del futuro Enablon Template Contract — esta especificación lo referencia por nombre, nunca valida su existencia real hasta que ese componente exista (§ 22/§ 24). |
| **Catálogo referenciado** | Un dataset externo, versionado, identificado por nombre lógico (nunca ruta de fichero ni cadena de conexión) contra el que un `lookup` resuelve (§ 15). |
| **Transformación registrada** | Una función implementada y revisada en código, identificada por nombre, que una regla puede invocar quedando fuera del vocabulario puramente declarativo (§ 19). |

## 6. Modelo conceptual

```
MappingSet
├── mapping_set_id        -- identidad estable (proyecto+módulo+object_type)
├── version                 -- snapshot concreto de `rules` (§ 8)
├── project / module / object_type
├── source_schema_version   -- qué forma de CanonicalRecord asume (opaco, § 24)
├── target_template_version -- qué versión de Template Contract pretende cumplir (opaco, § 24)
├── status                  -- draft | reviewed | approved | deprecated | retired
├── rules: [ MappingRule, ... ]
└── metadata                -- autor, fecha, tickets relacionados (§ 5 plantilla Excel)

MappingRule
├── rule_id                 -- identidad estable de ESTA regla (§ 8)
├── revision                 -- contador de cambios sin cambiar identidad
├── rule_type                -- ver § 10 (vocabulario cerrado)
├── source_fields             -- CanonicalField.field_name(s), § 13
├── target_field               -- nombre del campo destino, § 14 (aún sin validar contra Template Contract)
├── read_from                  -- normalized_value | original_value (§ 13)
├── condition_ref?              -- referencia a una Condition (§ 11), opcional
├── parameters                   -- forma según rule_type (§ 10)
├── priority                      -- entero, orden de evaluación entre reglas del mismo target_field (§ 12)
├── required                       -- bool, § 12/§ 16
├── enabled                         -- bool, independiente de status (§ 8)
├── status                           -- draft | reviewed | approved | deprecated | retired
├── justification                    -- obligatoria si status=approved
├── owner                              -- texto libre, sin sistema de usuarios propio
├── effective_from / effective_to      -- vigencia temporal
└── (solo rule_type=exclusion) exclusion_code, reason, rule_reference,
                                approved_by?, approved_at?, scope (§ 18)

Condition
├── condition_id
├── operator                 -- vocabulario cerrado (§ 11)
├── field_ref?                -- CanonicalField.field_name, si el operador lo requiere
├── literal?                   -- valor tipado, si el operador lo requiere
└── children?                    -- lista de Condition, solo si operator ∈ {and, or}

ValueMapEntry (fila de un value_map con value_map_id compartido)
├── value_map_id
├── source_value / target_value
├── status                  -- active | deprecated
├── justification
├── valid_from / valid_to
├── scope                    -- project | module | object_type
└── normalization             -- none | trim | trim_and_collapse_whitespace | case_insensitive

LookupDefinition
├── lookup_id
├── catalog_ref                -- nombre lógico del catálogo (§ 15), nunca ruta/conexión
├── steps                        -- lista ordenada de (catalog_ref, key_field, value_field) -- longitud ≥ 1
└── on_no_match                   -- fail | default_value | unresolved
```

Ninguna de estas estructuras contiene una fila de dato de una ejecución
real, una credencial, ni una plantilla CSV completa — solo la declaración
de qué regla existe y cómo se comporta.

## 7. `MappingSet` (antes "Mapping Set" en la tabla de entidades a evaluar)

**Renombrado respecto al encargo**: la estructura sugerida se llamaba
`MappingSpecification`, con un campo interno `mapping_set_id`. Se renombra
la entidad a `MappingSet` para que su identificador (`mapping_set_id`) no
quede desalineado con el nombre de la clase — "Mapping Specification" se
reserva para el nombre de este documento/diseño en su conjunto, nunca de
una entidad concreta (mismo criterio de nomenclatura ya aplicado en
`canonical-data-model.md`, que no usa "CDM" como nombre de ninguna clase).

Campos, obligatoriedad y quién los genera:

| Campo | Obligatorio | Quién lo genera | Notas |
|---|---|---|---|
| `mapping_set_id` | Sí | Quien crea el conjunto (determinista: `mapping_set:{project}.{module}.{object_type}`, reutiliza el patrón `slugify`/`make_*_id` ya implementado en `src/knowledge_base/model.py`) | Estable entre versiones — identifica "el mapeo de este objeto", no una versión concreta |
| `version` | Sí | Quien publica una nueva versión | Ver § 8 — eje de versión propio, distinto de `rule.revision` |
| `project` / `module` / `object_type` | Sí | Configuración de proyecto | `object_type` es el mismo valor que `CanonicalRecord.object_type` (CDM) |
| `source_schema_version` | No | Quien publica | Referencia opaca a qué forma de `CanonicalRecord` asume este conjunto — sin Connector formal todavía (ver `extensibility-model.md` § 5), se deja como texto libre versionado manualmente |
| `target_template_version` | No | Quien publica | Referencia opaca a una futura entrada del Enablon Template Registry — no validable hasta que ese componente exista (§ 24) |
| `status` | Sí | Flujo de revisión humano | `draft`\|`reviewed`\|`approved`\|`deprecated`\|`retired` — un conjunto no puede quedar `approved` si alguna de sus reglas no lo está (§ 22) |
| `rules` | Sí (puede ser vacío en `draft`) | Autores de mapeo | Lista de `MappingRule` |
| `metadata` | No | Cualquiera | Información de contexto (autor, tickets, notas) — nunca leída por el Mapping Engine para decidir comportamiento |

## 8. `MappingRule` — identidad y versionado

Cuatro conceptos distintos, que nunca se confunden entre sí (mismo
criterio de separación ya aplicado en `canonical-data-model.md` § 9 para
`record_id`/`source_record_id`/`functional_key`):

| Concepto | Campo | Estable ante... |
|---|---|---|
| Identidad estable del conjunto | `MappingSet.mapping_set_id` | Cualquier cambio de reglas — identifica "el mapeo de este objeto" a través de todas sus versiones |
| Versión concreta del conjunto | `MappingSet.version` | Nada — cada publicación nueva incrementa la versión |
| Identidad estable de una regla | `MappingRule.rule_id` | Cambios de `parameters`, `condition_ref`, `justification`, `priority`, `owner` — la regla sigue "siendo la misma" |
| Revisión de una regla | `MappingRule.revision` | Nada dentro de esa identidad — incrementa en cada cambio de los campos anteriores |
| Estado de aprobación | `MappingRule.status` / `MappingSet.status` | Se mueve explícitamente por un flujo humano, nunca automáticamente por el paso del tiempo (salvo `effective_to` vencido, que solo afecta si `enabled` se evalúa como vigente, no cambia `status`) |

**`rule_id`** es determinista: `rule:{mapping_set_id sin prefijo}.{target_field
slugificado}.{rule_type}.{disambiguador}` — el `disambiguador` es un slug
corto que el autor asigna cuando dos reglas compiten por el mismo
`target_field` (p. ej. `primary`/`fallback`, o un ordinal). Reutiliza el
patrón `slugify`/`short_hash`/`make_*_id` ya implementado y probado en
`src/knowledge_base/model.py` — no se inventa un segundo mecanismo de
identidad en el mismo repositorio (mismo razonamiento ya aplicado en
`canonical-data-model.md` § 9).

**Regla modificada — ¿misma identidad o identidad nueva?** Si cambian
`target_field` o `rule_type` (los dos componentes que forman parte del
propio `rule_id`), es, por definición, una regla distinta: se le asigna un
`rule_id` nuevo y la regla anterior debe marcarse explícitamente
`status=retired` (nunca desaparecer sin dejar rastro — mismo principio
Evidence First que rige todo el CDM). Si cambia cualquier otro campo
(`parameters`, `condition_ref`, `priority`, `justification`, fechas de
vigencia), `rule_id` se mantiene y `revision` incrementa.

**`enabled` es independiente de `status`**: un consultor funcional puede
desactivar temporalmente una regla ya `approved` (p. ej. durante una
investigación de un defecto) con `enabled=false`, sin que eso implique
retroceder su nivel de revisión/aprobación. Son dos ejes distintos a
propósito — mezclarlos obligaría a "reabrir" una aprobación solo para
pausar una regla.

## 9. Cómo se evita convertir Excel en un lenguaje de programación

Principio central de este documento, aplicado en cada sección siguiente:
**toda regla se expresa mediante vocabularios controlados, operadores
permitidos, referencias a campos, referencias a catálogos y parámetros
explícitos — nunca texto libre interpretado como código.**

Mecanismos concretos:

- **`rule_type` es un vocabulario cerrado** (§ 10), nunca una fórmula
  libre. Una celda de Excel para `rule_type` es una lista desplegable
  (hoja `Validation Lists`, § 21), no una casilla de texto libre.
- **`Condition` es una estructura, no una expresión de texto** (§ 11): un
  operador de una lista cerrada, una referencia de campo, un literal
  tipado. No existe una columna "condición" de texto libre que alguien
  pueda rellenar con `df[x] > 5 and y == "a"`.
- **`registered_transform` es la única vía hacia comportamiento no
  declarativo** (§ 19), y exige que el nombre exista ya en un catálogo de
  transformaciones implementadas y revisadas en código — un consultor
  funcional selecciona un nombre de una lista, nunca escribe la lógica.
- **Ningún campo de este modelo admite una ruta de fichero, una cadena de
  conexión, SQL, ni una URL con credenciales** — los catálogos se
  referencian por nombre lógico (`catalog_ref`), nunca por ubicación física
  (§ 15); esa resolución vive en la capa de configuración de proyecto,
  fuera de esta especificación.
- **La validación de la especificación (§ 22) rechaza cualquier valor de
  `rule_type`, `operator` o `transform_name` fuera de su vocabulario
  cerrado** antes de que una ejecución pueda empezar — no es una
  convención de estilo, es una comprobación obligatoria.

## 10. Tipos de regla (`rule_type`)

Doce tipos, evaluados uno a uno contra el catálogo de reglas ya confirmado
en `config/validation_rules.yaml`/`CLAUDE.md` y contra el código real de
`src/etl/transformations.py`/`src/export/prototype/drills/transformations.py`.
Se combinan varios nombres legados en un mismo `rule_type` cuando su
comportamiento observado es el mismo — nunca se generaliza sin evidencia.

| `rule_type` | Qué representa | Generaliza (evidencia real) | Parámetros mínimos |
|---|---|---|---|
| `direct` | Passthrough de un único campo origen a un único campo destino, con normalización trivial opcional (espacio) | `cloneorigin`. El fan-out a varios idiomas (`cloneorigin` 1→5) **no** es un `rule_type` nuevo: se representa como 5 `MappingRule` de tipo `direct`, una por `target_field`, todas con el mismo `source_fields` — más auditable que un concepto "fan-out" implícito, y ya es exactamente como se declara hoy `fields` en `config/exports/drills.yaml` (una fila por columna destino) | `normalization?: none\|trim` |
| `constant` | Ignora el origen, produce un literal fijo | `constant` (ya en `drills.yaml`, `CS_HistoricalDataOrigin`) | `value` |
| `default` | Produce un literal **solo** cuando el origen está ausente/nulo/vacío (según `blank_handling`) | `nullcontrol` | `value`, `blank_handling: null_only\|null_and_empty` |
| `value_map` | Tabla estática pequeña, source_value→target_value, evaluada en memoria sin dependencia de un catálogo externo | `lookup_simple`, `boolorigin` (con `key_normalization: boolean`), `replaceinreference` (sin comportamiento distinguible de un `value_map` con datos reales) | `value_map_id` (referencia a § 16), `on_no_match: fail\|default_value\|unresolved` |
| `lookup` | Resuelve contra un catálogo externo, cargado por separado, potencialmente en varios pasos | `lookup_dinamico_dos_pasos` (Safety Meetings/MOC), resolución de entidad (`EntityCatalog`/`resolve_entity`) | `lookup_id` (referencia a § 15) |
| `conditional` | Elige entre 2+ resultados posibles según una `Condition` | Patrón `EsCondicion` de la hoja de regla `DatoOrigen/DatoDestino/EsCondicion/ReglaEspecial/Parametro` (`src/etl/excel_reader.py::RuleTableEntry`) | `condition_ref`, `when_true` / `when_false` (cada uno: un valor literal o una referencia a otra `MappingRule`) |
| `concatenate` | Concatena 2-4 campos origen, en orden, con separador declarado | `concat`, `barconcat` (`barconcat` = `concatenate` con `separator=" \| "` — no es un tipo distinto) | `source_fields` (ordenada), `separator`, `skip_empty: bool` |
| `type_conversion` | Convierte al tipo canónico declarado (§ 18 de `canonical-data-model.md`) | Conversión implícita ya presente en varias reglas de `drills.yaml` (`data_type`) | `target_type`, `on_error: fail\|null\|default_value` |
| `date_conversion` | Especialización de `type_conversion` para `date`/`datetime`, con formatos de origen/destino declarados | `parse_starting_date`/`format_starting_date`/`format_reference_date` | `source_formats` (lista), `target_format`, `on_error` |
| `reference` | Produce una `Relationship` (CDM) hacia otro `CanonicalRecord`, no un valor plano | Patrón de Action Plans transversal (`config/modules.yaml` → `campos_de_enlace_a_otros_modulos`) | `relationship_type`, `target_reference_from` (qué `source_fields`/regla produce el `target_reference`), `required: bool` |
| `exclusion` | Declara, de forma explícita y trazable, que un registro/campo/relación no se migra | `excluded_columns` de `drills.yaml`, estado `DO_NOT_MIGRATE` de `EntityResolution` | Ver § 18 (campos propios) |
| `registered_transform` | Invoca una función ya implementada y revisada en código, por nombre | `titlefix` (sin motor declarativo posible — confirmado sin fórmula ni VBA visible en 7 libros auditados), y la vía de escape general para cualquier regla futura no declarativa | `transform_name` (del catálogo § 19), `parameters` (según el esquema declarado por esa transformación) |

No se crea un tipo `fan_out` ni un tipo separado para `boolorigin`/
`replaceinreference`/`lookup_simple` — los tres colapsan en `value_map`
porque, con la evidencia disponible, ninguno tiene un comportamiento
observable que `value_map` no cubra ya (crear tres tipos idénticos en
comportamiento solo por conservar tres nombres históricos sería
proliferación de tipos sin justificación).

## 11. Condiciones

Operadores (cerrados, exactamente los evaluados en el encargo, sin
ampliar sin evidencia de necesidad real):

`equals`, `not_equals`, `in`, `not_in`, `is_null`, `is_not_null`,
`contains`, `starts_with`, `greater_than`, `less_than`, `and`, `or`.

No se añade `regex` ni `ends_with`: ninguna regla ya confirmada en
`CLAUDE.md`/`validation_rules.yaml` los necesita como **condición**
declarativa (el único uso de expresión regular confirmado, dentro de
`titlefix`, es lógica interna de una `registered_transform`, no una
condición sobre la que el Mapping Set decide un `rule_type`).

- **Condiciones compuestas**: sí, mediante `and`/`or` con una lista de
  `children` (cada hijo es otra `Condition`, atómica o compuesta).
- **Profundidad máxima conceptual**: recomendada ≤ 3 niveles de anidación.
  No es una restricción técnica de este documento (queda para
  implementación) sino una recomendación de diseño: una condición que
  necesita más de 3 niveles casi siempre debería expresarse como varias
  `MappingRule` con `priority` distinta en vez de una única condición
  ilegible en una celda de Excel.
- **Referencia a un campo**: `field_ref` es siempre un
  `CanonicalField.field_name` del mismo `CanonicalRecord` — nunca un
  campo de otro registro, nunca una expresión (`field_ref: "IDTipo"`, no
  `field_ref: "row['IDTipo'] * 2"`).
- **Literal**: tipado según uno de los tipos canónicos mínimos del CDM
  (`string`\|`integer`\|`decimal`\|`boolean`\|`date`\|`datetime`\|
  `identifier`). `in`/`not_in` exigen una lista de literales del mismo
  tipo; `greater_than`/`less_than` exigen un tipo comparable
  (`integer`\|`decimal`\|`date`\|`datetime`); `is_null`/`is_not_null` no
  admiten literal.
- **Validación de tipo**: la validación de especificación (§ 22)
  comprueba que el literal declarado es convertible al tipo esperado por
  el operador — un literal mal tipado es un error de especificación, no
  un error de ejecución.

## 12. Prioridad y conflictos

**Regla dura**: ningún conflicto se resuelve mediante "la última regla del
fichero gana" de forma implícita. Toda ambigüedad detectable se convierte
en un error de validación de la especificación (§ 22), nunca en un
comportamiento silencioso en tiempo de ejecución.

| Situación | Resolución |
|---|---|
| Dos reglas para el mismo `target_field`, con condiciones mutuamente excluyentes | Válido — `priority` fija el orden de evaluación (menor `priority` se evalúa primero); la primera cuya `condition_ref` sea verdadera (o sin condición) se aplica. |
| Dos reglas para el mismo `target_field`, misma `priority` | **Error de validación** (`OVERLAPPING_RULES`) — nunca se decide por orden de aparición en el fichero. |
| Un `default` y una regla `direct`/`lookup`/... para el mismo campo | Válido, patrón explícitamente soportado — pero el `default` debe declarar la `priority` más alta (se evalúa último); si no, la validación emite una advertencia (`DEFAULT_NOT_LAST`, no bloqueante, indicio de diseño probablemente erróneo). |
| Una `exclusion` de alcance `record` y cualquier regla de campo para ese mismo registro | La `exclusion` de alcance `record` tiene precedencia fija y documentada: ningún campo de ese registro se transforma más allá de lo ya resuelto (mismo comportamiento ya implementado en `EntityResolution.DO_NOT_MIGRATE`, que detiene el resto del procesamiento de la fila). No es "la última regla gana" — es una regla de precedencia explícita y auditable. |
| Un `lookup`/`value_map` con más de un resultado posible para la misma clave | Nunca se elige uno automáticamente — el resultado es `status=conflicting` en el `TransformationTrace` (§ 20), igual que ya hace `EntityCatalog.conflicting_keys`/`duplicate_es_labels` en el código real. |
| Una `reference` no resuelta (`target_record` sin encontrar) | No es un conflicto — es el estado esperado `pending`/`unresolved` de una `Relationship` (CDM). Si `required=true` y sigue sin resolver al validar, se reporta como `Issue`, nunca se inventa un destino. |

## 13. Field mapping — cómo se indica el campo origen y el campo destino

**Campo origen** (`source_fields`): siempre un `CanonicalField.field_name`,
nunca una columna SQL o una celda Excel directamente — la traducción
"columna SQL `IDTipo`" → "campo canónico `IDTipo`" ya ocurrió en la
extracción (Connector), antes de que exista ningún `MappingRule` (ver
`data-processing-lifecycle.md`, orden del pipeline). Este documento **no**
inventa un vocabulario canónico de nombres de campo cruzado entre fuentes
(sería una ontología, explícitamente descartada por el encargo) — el
`field_name` de un `CanonicalRecord` es, en el caso general, el mismo
nombre que ya usaba la fuente (columna SQL, cabecera Excel, etiqueta
asignada por un Connector documental), y la Mapping Specification lo
referencia tal cual.

`read_from: normalized_value | original_value` (por defecto
`normalized_value`) declara explícitamente si la regla lee el valor ya
limpiado por el Connector o el valor exactamente como llegó — necesario
para casos como `titlefix`, que necesita el texto sin limpiar previamente
para decidir su propio comportamiento.

**Campo destino** (`target_field`): un nombre de cadena, sin validación
estructural contra ninguna plantilla real todavía — esta especificación
no conoce el Enablon Template Contract (§ 3/§ 24). Validar que
`target_field` existe de verdad en la plantilla de Enablon queda
explícitamente pendiente hasta que ese componente exista (§ 22).

## 14. (fusionada con § 13 — campo destino)

Ver § 13. No se crea una sección separada para no duplicar contenido —el
encargo pedía "campo destino" como pregunta propia, pero su respuesta es
indisociable de "campo origen" en este modelo (ambos son, estructuralmente,
un nombre de cadena con reglas de validación distintas, documentadas
juntas arriba).

## 15. Lookups

Distinción exigida por el encargo, con su representación exacta:

| Concepto | Representación |
|---|---|
| Value map estático | `rule_type: value_map`, datos en una `ValueMapEntry` (§ 16) |
| Lookup contra un catálogo cargado | `rule_type: lookup`, `LookupDefinition.catalog_ref` — nombre lógico (p. ej. `"entity_catalog"`, `"enablon_organizational_units"`), nunca ruta de fichero ni cadena de conexión. La resolución de ese nombre a un fichero/consulta real es responsabilidad de la configuración de proyecto, fuera de esta especificación (mismo límite ya fijado para `Provenance.locator` en el CDM). |
| Referencia a otro `CanonicalRecord` | `rule_type: reference` (§ 10) — produce una `Relationship`, no un valor plano |
| Referencia a una entidad Enablon (dato maestro, no un registro migrado en esta ejecución) | `rule_type: lookup` cuyo `catalog_ref` apunta a un catálogo cuyos valores ya son identificadores nativos de Enablon (p. ej. el catálogo de entidades `First_Axis`) — no hace falta un `rule_type` distinto: la diferencia está en qué contiene el catálogo, no en cómo se consulta |
| Referencia todavía no resuelta | Estado `pending`/`unresolved` de la `Relationship` producida por una regla `reference` (§ 12), o `on_no_match: unresolved` de un `lookup`/`value_map` |

`LookupDefinition.steps` admite más de un paso para representar
exactamente el patrón ya confirmado "código → descripción, descripción →
Id vigente de Enablon" (Safety Meetings, MOC) — cada paso declara su
propio `catalog_ref`, sin que la Mapping Specification necesite saber cómo
se cargó ese catálogo.

## 16. Referencias — modelo de `value_map` grande

Decisión práctica para tablas de tamaño real (la tabla de tipología tiene
15 filas; el catálogo de entidades, cientos):

- Los `ValueMapEntry` **no se embeben dentro de la fila de `MappingRule`**
  — viven en su propia colección (`value_map_id` compartido), referenciada
  desde la regla vía `parameters.value_map_id`. Generaliza directamente el
  patrón ya implementado en `config/exports/drills.yaml`, donde
  `reference_data.typology_lookup`/`letter_lookup`/`workflow_status_lookup`
  ya viven separados de la lista `fields`, referenciados por clave
  (`mapping: "reference_data.typology_lookup"`).
- Tablas muy pequeñas (`workflow_status_lookup`, 4 filas) pueden declararse
  inline como `parameters.value_map_id` inexistente + un `parameters.inline_entries`
  corto, por legibilidad — el documento no fuerza externalizar tablas
  triviales, pero lo recomienda a partir de un umbral práctico (la propia
  plantilla Excel, § 21, empuja hacia la hoja `Value Maps` en cuanto una
  tabla supera unas pocas filas, por espacio en la fila).
- Campos por entrada: `source_value`, `target_value`, `status`
  (`active`\|`deprecated`), `justification`, `valid_from`/`valid_to`,
  `scope` (`project`\|`module`\|`object_type` — declarado explícitamente,
  nunca asumido global), `normalization` (`none`\|`trim`\|
  `trim_and_collapse_whitespace`\|`case_insensitive` — generaliza
  literalmente `normalize_label()` ya implementado en
  `src/etl/mapping_resolver.py`, que hace strip+colapso de espacio pero
  **nunca** toca mayúsculas/minúsculas por defecto — ese comportamiento
  pasa a ser una opción explícita, no un supuesto oculto).
- **Valores no encontrados**: `on_no_match` (§ 10, `value_map`/`lookup`)
  — `fail` (bloquea el registro), `default_value` (aplica un valor
  documentado, nunca inventado — mismo patrón que `typology_default_no_match:
  "NADA"`), o `unresolved` (se reporta y se conserva, mismo patrón que
  `letter` sin coincidencia).
- **Duplicados**: dos `ValueMapEntry` con el mismo `source_value` y
  `target_value` distintos, dentro del mismo `value_map_id` y `scope`,
  es un **error de validación** (§ 22) — nunca se elige uno
  arbitrariamente (generaliza `EntityCatalog.conflicting_keys` y
  `EnablonReferenceCatalog.duplicate_es_labels`, ambos ya implementados
  con exactamente esta regla).

## 17. Defaults, null y vacío

Siete conceptos distintos, exigidos explícitamente por el encargo, nunca
comprimidos en una única representación:

| Concepto | Cómo se distingue |
|---|---|
| Campo ausente | `field_name` no existe en absoluto en `CanonicalRecord.fields` — ausencia estructural, no un valor. |
| Valor origen nulo | El campo existe; `CanonicalField.original_value is None`. |
| Cadena vacía | El campo existe; el valor no es `None` pero es `""`. Distinta de nulo a propósito — cada regla que le da relevancia a esta distinción declara `blank_handling: null_only \| null_and_empty` (§ 10, `default`) en vez de asumir un comportamiento global. |
| Valor no mapeado | El valor está presente (no nulo/vacío) pero no aparece en el `value_map`/`lookup` — resultado `on_no_match` (§ 16), nunca confundido con "vacío". |
| Valor por defecto | El resultado explícito de un `rule_type: default` — siempre documentado (`value` + `justification`), nunca un valor "de sistema" no declarado. |
| Campo destino vacío deliberadamente | Un `rule_type: exclusion` con `scope: field` (§ 18) — el campo existe en el `target_field` pero se decide, con justificación, no poblarlo. Distinto de "valor por defecto vacío" porque lleva aparejada la trazabilidad de una exclusión (código, motivo, quién). |
| "No migra" | Un valor de negocio (no una ausencia) que, al resolverse mediante `lookup`/`value_map`, coincide con un literal declarado `treat_as_exclusion_when` en la propia definición del lookup/value map — cuando ocurre, escala automáticamente a una `exclusion` de alcance `record`, con `reason` autogenerado que referencia la regla origen (generaliza literalmente `EntityCatalog.do_not_migrate_literal` → `DO_NOT_MIGRATE`, ya implementado). |

**"Sin equivalencia" nunca se convierte automáticamente en "No migra"**:
un valor `unresolved` (no encontrado en un `value_map`/`lookup`) se queda
`unresolved` — solo se convierte en exclusión si el propio catálogo
declara ese valor concreto como `treat_as_exclusion_when`, una decisión
explícita y documentada, nunca una inferencia automática de "no lo
encontré, luego no migra".

## 18. Exclusiones

`rule_type: exclusion` — campos propios, además de los comunes a todo
`MappingRule` (§ 8):

| Campo | Obligatorio | Notas |
|---|---|---|
| `scope` | Sí | `record` \| `field` \| `relationship` — qué exactamente se excluye |
| `exclusion_code` | Sí | Categoría corta, reutilizable (p. ej. `NO_SOURCE_COLUMN_IDENTIFIED`, `OUT_OF_INCREMENT_SCOPE`, `REQUIRES_PII_LOOKUP`, `DO_NOT_MIGRATE_ENTITY`) — nunca solo texto libre |
| `reason` | Sí | Texto humano — generaliza literalmente el campo `reason` ya obligatorio hoy en `excluded_columns` de `drills.yaml` |
| `rule_reference` | No | Puntero a la decisión/spec que la origina (p. ej. un AFD, un ticket) |
| `approved_by` / `approved_at` | Recomendado en `scope=record`, opcional en `scope=field` | Firma explícita para exclusiones de alto impacto — más allá del `status=approved` genérico de la regla |

Cuatro casos distinguidos, tal como exige el encargo:

1. **Registro completo no migrable** → `scope: record`.
2. **Campo omitido** → `scope: field`.
3. **Relación no migrable** → `scope: relationship` — declara que, para
   este `object_type`, un `relationship_type` concreto nunca se intenta
   resolver (distinto de una `Relationship` individual que queda
   `unresolved` en tiempo de ejecución).
4. **Dato pendiente por falta de equivalencia** → **no es una exclusión**
   — es `unresolved` (§ 17), sin `rule_type: exclusion` alguno. Se
   convierte en exclusión solo si alguien la declara explícitamente como
   tal, nunca por defecto.

## 19. Transformaciones registradas

`rule_type: registered_transform` es la única vía hacia comportamiento no
cubierto por los 11 tipos declarativos. Generaliza exactamente el patrón
ya implementado en `src/etl/transformations.py`
(`RULE_REGISTRY`/`resolve_rule`): un nombre resuelto contra un registro de
funciones ya escritas, revisadas y (cuando aplica) confirmadas con datos
reales — nunca código nuevo escrito dentro de una celda de Excel.

- `transform_name`: debe existir en un catálogo de "Registered
  Transforms" (§ 21, hoja de solo lectura para consultores funcionales) —
  poblado únicamente por quien implementa la función en código.
  Referenciar un `transform_name` inexistente es un error de validación
  (§ 22), no un fallo en tiempo de ejecución.
- `parameters`: forma libre pero **declarada** por la propia
  transformación registrada (cada transformación publica qué parámetros
  acepta, p. ej. `titlefix` publica `preserve_inches: bool`) — la Mapping
  Specification no interpreta esos parámetros, solo los transporta.
- Ejemplo real que exige este mecanismo: `titlefix` — confirmado con datos
  reales (76/5207 casos en MOC) pero **sin motor visible** en ningún Excel
  ni macro VBA de los 7 libros auditados (`CLAUDE.md`). No puede
  expresarse de forma segura como dato declarativo porque su
  comportamiento real (más allá del stripping de comillas ya confirmado)
  sigue sin documentarse — es exactamente el caso para el que existe
  `registered_transform`: encapsular en código revisado un comportamiento
  que no se puede auditar como regla declarativa.

## 20. `TransformationTrace` — decisión resuelta

ADR-014 dejó esta decisión explícitamente diferida a este documento
(`canonical-data-model.md` § 11.1/§ 25). Se resuelve aquí:

**Se adopta la opción B, acotada**: `TransformationTrace` es una lista
ordenada y corta de `TraceStep`, cuya longitud **no es arbitraria ni
dinámica** — se deriva directamente de la forma que la propia
`MappingRule` aplicada ya declara (nunca de una ejecución que decide
cuántos pasos registrar sobre la marcha):

```
TransformationTrace
└── steps: [ TraceStep, ... ]   -- longitud = la que declara la regla aplicada
              (p. ej.: direct/constant/default/concatenate/type_conversion/
              date_conversion = 1 paso; lookup con N `steps` = N pasos;
              conditional = 2 pasos: evaluación de condición + regla elegida)

TraceStep
├── engine_stage        -- mapping | transformation
├── rule_id              -- qué MappingRule (o qué paso de un lookup) produjo este paso
├── rule_type
├── status                -- resolved | resolved_with_fallback | default_applied |
│                            unresolved | conflicting (mismo vocabulario ya
│                            confirmado en LookupResult.status)
├── catalog_ref?           -- solo si este paso consultó un catálogo (lookup)
└── note?
```

- **No se rechaza la opción A (solo resultado final)** porque no explica
  el caso pedido explícitamente por el encargo — normalización → lookup →
  fallback → formato final — sin perder la señal de "el lookup falló y
  cayó al fallback", información que un Evidence Engine necesita para
  auditar por qué un valor terminó siendo el que es.
- **No se adopta la opción C (resumen + referencias externas a pasos
  detallados)** porque el número de pasos es siempre pequeño y conocido
  de antemano (nunca más de 2-4, derivado de la propia regla) — una
  indirección hacia un artefacto externo por cada traza sería
  sobreingeniería sin consumidor real que la necesite hoy (principio 8).
- **No se convierte en event sourcing**: los `TraceStep` no repiten el
  valor completo del campo en cada paso (eso ya vive en
  `CanonicalField.original_value`/`normalized_value`/`transformed_value`,
  CDM § 11) — cada paso es una referencia ligera (`rule_id`, `status`,
  `catalog_ref?`), nunca una copia del dato.
- `TransformationTrace` expone además `summary_status` (el `status` del
  último paso) para que un consumidor que solo necesita "¿se resolvió
  bien, al final?" no tenga que recorrer la lista completa.

Ver § 25 para el ejemplo completo del caso "normalización → lookup →
fallback → formato final".

## 21. Interfaz Excel conceptual

Nueve hojas — ninguna se asume necesaria sin justificación:

| Hoja | Contenido | Por qué existe |
|---|---|---|
| **Mapping Set** | Una fila (o pocas, una por versión histórica) con `mapping_set_id`, `project`, `module`, `object_type`, `version`, `status`, `source_schema_version`, `target_template_version`, `owner`, fechas | Cabecera del conjunto — un consultor abre esta hoja primero para saber qué está mirando |
| **Field Rules** | Una fila por `MappingRule`: `rule_id` (columna técnica, autogenerada/no editable), `rule_label` (texto libre legible, p. ej. "CS_Typology desde IDTipo"), `target_field`, `rule_type`, `source_fields`, `condition_ref`, `priority`, `required`, `enabled`, `status`, `justification`, `owner`, vigencia | El núcleo de la especificación — generaliza el patrón de 8 columnas ya confirmado (`CampoOrigen \| ... \| Adaptación \| Transformation From \| ...`) con columnas explícitas de tipo/prioridad/estado en vez de un booleano implícito "Adaptación" |
| **Value Maps** | Una fila por `ValueMapEntry`: `value_map_id`, `source_value`, `target_value`, `status`, `justification`, `valid_from`/`valid_to`, `scope`, `normalization` | Tablas 1:1 potencialmente largas, separadas de `Field Rules` para no romper su legibilidad (§ 16) |
| **Lookups** | Una fila por `LookupDefinition`: `lookup_id`, pasos (`catalog_ref` por paso), `on_no_match` | Declara *cómo* consultar un catálogo externo — nunca contiene los datos del catálogo en sí |
| **Conditions** | Una fila por `Condition` (atómica o el nodo raíz de una compuesta): `condition_id`, `operator`, `field_ref`, `literal`, `parent_condition_id` (para `and`/`or`) | Evita condiciones anidadas ilegibles en una sola celda de `Field Rules` — cada condición es una fila estructurada |
| **Exclusions** | Una fila por regla `exclusion`: `rule_id`, `scope`, `exclusion_code`, `reason`, `rule_reference`, `approved_by`, `approved_at` | Generaliza `excluded_columns` de `drills.yaml`, ya un patrón real y usado |
| **Registered Transforms** | Catálogo de **solo lectura** para consultores funcionales: `transform_name`, `description`, `parameters_schema`, `confirmed_with_real_data` (`true`\|`false`\|`partial`), `added_by`, `added_at` | Población exclusiva de quien implementa la función en código — un consultor solo *selecciona* de aquí (§ 9, § 19), nunca escribe una función nueva |
| **Metadata** | Notas de contexto: autor, fecha de revisión, tickets relacionados, glosario de `exclusion_code` usados en este proyecto | Información de apoyo humano, nunca leída por el Mapping Engine para decidir comportamiento |
| **Validation Lists** | Hoja técnica (recomendada oculta): listas cerradas para las validaciones de datos de Excel (valores válidos de `rule_type`, `operator`, `status`, `scope`, `on_no_match`...) | Mecanismo concreto que convierte cada columna de vocabulario cerrado en una lista desplegable de Excel, no en texto libre (§ 9) |

La plantilla debe ser utilizable por consultores funcionales: `Field
Rules`/`Value Maps`/`Exclusions`/`Conditions` son las hojas de trabajo
habitual; `Registered Transforms`/`Validation Lists` son de solo consulta;
`Mapping Set`/`Metadata` se tocan solo al abrir o cerrar una versión. No se
crea el archivo `.xlsx` real en esta tarea.

## 22. Validación de la especificación

| Validación | Cuándo es posible | Severidad |
|---|---|---|
| `mapping_set_id`/`rule_id` duplicados | Ahora | Error |
| Campos obligatorios ausentes en una regla (según su `rule_type`, § 10) | Ahora | Error |
| `rule_type` desconocido (fuera del vocabulario § 10) | Ahora | Error |
| `target_field` inexistente en el Enablon Template Contract | **Solo cuando el Template Contract exista** (Blueprint § 11, todavía no implementado) | No verificable hoy — se documenta como limitación, nunca se asume que el campo existe |
| Referencia a un catálogo (`catalog_ref`/`value_map_id`) no declarado en absoluto | Ahora (existencia de la *declaración*, no de los datos reales del catálogo) | Error |
| Condición inválida (operador desconocido, literal de tipo incorrecto, profundidad excesiva) | Ahora | Error / advertencia (profundidad) |
| Prioridades conflictivas (§ 12) | Ahora | Error / advertencia según el caso |
| `ValueMapEntry` duplicadas (mismo `source_value`, `target_value` distinto, mismo `value_map_id`+`scope`) | Ahora | Error |
| Ciclos de referencia (`reference`/`lookup` que dependen circularmente entre sí a nivel de definición) | Ahora | Error |
| `registered_transform` con `transform_name` inexistente en el catálogo | Ahora | Error |
| Regla `status=approved` sin `justification` | Ahora | Error |
| Regla `enabled=true` fuera de `effective_from`/`effective_to` | Ahora (si se conoce la fecha de referencia) | Advertencia |
| `MappingSet.status=approved` con alguna regla no `approved` | Ahora | Error |

## 23. Integración con el CDM

- `MappingRule.source_fields`/`read_from` leen `CanonicalField.normalized_value`
  u `original_value` (§ 13).
- El Mapping/Transformation Engine escribe `CanonicalField.transformed_value`
  y construye el `TransformationTrace` (§ 20) según la forma que declara
  la regla aplicada.
- Una regla `exclusion` de `scope: record` mueve `CanonicalRecord.disposition`
  a `excluded` (CDM § 17); de `scope: field` deja ese campo sin
  `transformed_value`, con su `Issue` correspondiente; de `scope:
  relationship` impide que se intente construir esa `Relationship` en
  absoluto para ese `object_type`.
- Una regla `reference` produce una `Relationship` (CDM § 16), con
  `required` heredado directamente del campo homónimo de la regla.
- Cualquier resultado `unresolved`/`conflicting`/`fail` de una regla
  genera un `Issue` (CDM § 15) con `stage: mapping` o `stage:
  transformation` según corresponda — la Mapping Specification nunca
  decide por sí sola si eso bloquea la exportación (`blocks_export`), solo
  documenta el hecho, igual que ya hace `validate_*` (nunca lanza excepción
  por regla de negocio).

## 24. Integración futura con el Enablon Template Contract

No se diseña aquí — es, explícitamente, un componente futuro (Blueprint §
11) que este documento no puede anticipar sin evidencia. Lo que sí se fija:

- `MappingSet.target_template_version` es el único punto de enganche
  declarado — una cadena opaca hoy, que en el futuro se resolverá contra
  una entrada real del Enablon Template Registry.
- La validación de `target_field` (§ 22) queda pendiente hasta que ese
  componente exista — no se simula ni se asume su forma.
- Cuando el Template Contract exista, la reconciliación entre el
  `data_type` **detectado** de un `CanonicalField` (CDM § 18) y el tipo
  **esperado** por la plantilla es responsabilidad del Template Contract,
  no de esta especificación (mismo límite ya fijado en
  `canonical-data-model.md` § 18) — un `type_conversion` mal declarado se
  detectará entonces como discrepancia, pero el criterio de "qué tipo se
  espera" no vive aquí.

## 25. Ejemplos conceptuales

Todos con datos ilustrativos, generalizando patrones reales pero sin
limitarse a Drills.

**1. Mapeo directo** (`direct`) — Safety Meeting, asistente:
```
MappingRule
  rule_id: rule:safety_meeting.gct_asistente.direct.primary
  rule_type: direct
  source_fields: ["NombreUsuario"]
  target_field: "CS_AttendeeName"
  priority: 10
  required: false
  status: approved
  justification: "Passthrough confirmado -- sin transformación de negocio, ver ticket #7359."
```

**2. Value map 1:1** (`value_map`) — Simulacros, tipología (evidencia real):
```
MappingRule
  rule_id: rule:drill.prevencion_itp.value_map.typology
  rule_type: value_map
  source_fields: ["IDTipo"]
  target_field: "CS_Typology"
  parameters: { value_map_id: "vm:drills.typology", on_no_match: default_value }
  justification: "etl_transform:simulacros.mapeotiposim.typology_two_step_lookup"
  status: approved

ValueMapEntry (value_map_id=vm:drills.typology)
  source_value: "365" -> target_value: "PEI"
  source_value: "366" -> target_value: "GEN"
  ... (15 filas confirmadas)
```

**3. Valor por defecto** (`default`) — Simulacros, letra ausente:
```
MappingRule
  rule_id: rule:drill.prevencion_itp.default.letter_null
  rule_type: default
  source_fields: ["IDLetra"]
  target_field: "CS_Letter"
  parameters: { value: "NOLETTER-WRONG", blank_handling: null_only }
  justification: "Literal exacto del nullcontrol de Mapeo_Letra fila 8 -- no inventado."
  status: approved
```

**4. Regla condicional** (`conditional`) — OPS, felicitación condicionada:
```
Condition
  condition_id: cond:ops.unsafe_behavior_is_yes
  operator: equals
  field_ref: "UnsafeBehavior"
  literal: "YES"

MappingRule
  rule_id: rule:ops.prevencion_itp.conditional.congratulated_worker
  rule_type: conditional
  target_field: "CS_CongratulatedWorker"
  condition_ref: cond:ops.unsafe_behavior_is_yes
  parameters: { when_true: "rule:ops...direct.congratulated_worker_value", when_false: null }
  justification: "CS_CongratulatedWorker solo aplica si Unsafe Behavior = YES (config/modules.yaml, ops.reglas_no_estandar)."
```

**5. Lookup** (`lookup`, 2 pasos) — Safety Meetings, nivel (evidencia real):
```
LookupDefinition
  lookup_id: lk:safety_meetings.nivel
  steps:
    - { catalog_ref: "safety_meetings.mapeo_nivel_codigo_a_descripcion", key_field: "IDNivel" }
    - { catalog_ref: "enablon_live.picklist_meeting_level", key_field: "descripcion" }
  on_no_match: unresolved

MappingRule
  rule_id: rule:safety_meeting.prevencion_itp.lookup.level
  rule_type: lookup
  source_fields: ["IDNivel"]
  target_field: "CS_Level"
  parameters: { lookup_id: "lk:safety_meetings.nivel" }
  justification: "Patrón preferente ya confirmado (lookup dinámico 2 pasos, CLAUDE.md)."
```

**6. Exclusión deliberada** (`exclusion`, `scope: field`) — Drills, duración:
```
MappingRule
  rule_id: rule:drill.prevencion_itp.exclusion.duration
  rule_type: exclusion
  target_field: "CS_Duration"
  parameters: { scope: field, exclusion_code: "FORMULA_NOT_LOCATED",
                reason: "OQ-ETL-02 abierta -- no se ha localizado la fórmula que recombina meses/días/horas/minutos." }
  status: approved
```

**7. Equivalencia faltante** (sin `exclusion` — `unresolved`) — MOC, Estado sin tabla:
```
MappingRule
  rule_id: rule:moc.gct.value_map.workflow_status
  rule_type: value_map
  source_fields: ["Estado"]
  target_field: "CS_WorkflowStatus"
  parameters: { value_map_id: "vm:moc.workflow_status", on_no_match: unresolved }
  status: approved
```
Un `Estado` fuera de las 4 filas confirmadas queda `unresolved` — **no**
se convierte en `exclusion`: nadie ha decidido todavía que ese valor no
deba migrar, solo falta su equivalencia (§ 17).

**8. Referencia a otro registro** (`reference`) — ActionPlan → Event:
```
MappingRule
  rule_id: rule:action_plan.gct_acciones.reference.parent_object
  rule_type: reference
  target_field: null   -- una `reference` no produce un valor plano, produce una Relationship
  parameters: { relationship_type: "action_plan_for_object", target_reference_from: "IDEventoOrigen", required: true }
  justification: "Generaliza config/modules.yaml -> ap.campos_de_enlace_a_otros_modulos."
  status: approved
```

**9. Transformación registrada** (`registered_transform`) — MOC, título:
```
MappingRule
  rule_id: rule:moc.gct.registered_transform.title
  rule_type: registered_transform
  source_fields: ["Titulo"]
  target_field: "CS_Title"
  parameters: { transform_name: "titlefix", preserve_inches: false }
  justification: "Confirmado 76/5207 casos (MOC) -- sin motor declarativo visible en 7 libros auditados, ver CLAUDE.md."
  status: approved
```

**10. Conflicto entre reglas** (detectado, no resuelto en silencio) — Inspección, ejemplo deliberadamente inválido:
```
MappingRule A: target_field="CS_Status", priority=10, condition_ref=cond:x_equals_1
MappingRule B: target_field="CS_Status", priority=10, condition_ref=cond:x_equals_1
```
Validación de la especificación (§ 22): `OVERLAPPING_RULES` — misma
`priority`, misma condición, mismo `target_field`. La especificación no
puede aprobarse (`MappingSet.status=approved`) hasta que se resuelva
(distinta `priority`, o consolidar en una sola regla).

**11. Traza de varias operaciones** (`TransformationTrace`, § 20) — caso
"normalización → lookup → fallback → formato final":
```
TransformationTrace (para CS_Level de un Safety Meeting)
  summary_status: default_applied
  steps:
    - { engine_stage: mapping, rule_id: "rule:...lookup.level", rule_type: lookup,
        catalog_ref: "safety_meetings.mapeo_nivel_codigo_a_descripcion", status: unresolved }
    - { engine_stage: mapping, rule_id: "rule:...lookup.level", rule_type: lookup,
        catalog_ref: "enablon_live.picklist_meeting_level", status: unresolved }
    - { engine_stage: transformation, rule_id: "rule:...default.level_fallback",
        rule_type: default, status: default_applied }
```
Tres pasos (los dos del `lookup` declarado + el `default` que lo sigue por
`priority`) — nunca un cuarto paso "por si acaso": la longitud la fija la
propia declaración de las reglas, no la ejecución.

## 26. Riesgos

- **Diseño no validado empíricamente todavía**: sin una implementación
  real del Mapping Engine, este documento es arquitectura, no un hecho
  probado — mismo riesgo ya reconocido en ADR-011/ADR-014 para el CDM.
- **El eje de versión `MappingSet.version` no está incorporado a la tabla
  de cuatro ejes de versión del Blueprint** (§ 16 de `emf-blueprint-v1.0.md`:
  `blueprint_version`/`architecture_version`/`application_version`/
  `template_version`) — es un quinto eje de facto. No se corrige el
  Blueprint en esta tarea (documentación legada, fuera de los archivos
  autorizados) — se señala como inconsistencia a resolver en una futura
  actualización del Blueprint.
- **La imposibilidad de validar `target_field` contra una plantilla real**
  (§ 22) significa que una Mapping Specification puede aprobarse
  internamente coherente y aun así referenciar un campo de Enablon que no
  existe — riesgo aceptado explícitamente hasta que el Template Contract
  exista, no oculto.
- **La detección de solapamiento de condiciones (§ 12) es, en el caso
  general, indecidible sin evaluar todas las combinaciones posibles de
  valores** (dos condiciones sobre campos distintos pueden solaparse de
  formas no triviales) — este documento fija que los casos triviales
  (misma condición exacta, ausencia de condición en ambas) se detectan
  siempre; el caso general se deja como decisión de implementación del
  futuro validador, con el mismo espíritu que "no ocultar en silencio" (si
  el validador no puede decidir, debe señalarlo como advertencia, no
  aprobar silenciosamente).
- **`registered_transform` reintroduce, deliberadamente, una dependencia
  de código** dentro de un modelo por lo demás puramente declarativo — es
  el riesgo aceptado a cambio de no inventar un lenguaje de expresiones
  propio (alternativa rechazada, ver ADR nueva § siguiente).

## 27. Decisiones aplazadas

- **Algoritmo exacto de detección de solapamiento de condiciones** más
  allá de los casos triviales (§ 12/§ 26) — decisión de implementación del
  futuro Mapping Engine/validador.
- **Esquema de parámetros de cada `registered_transform`** (cómo se
  declara formalmente `parameters_schema` en la hoja `Registered
  Transforms`) — se dejará para cuando exista una segunda transformación
  registrada real más allá de `titlefix`, con la que comparar formas
  (principio 8).
- **Quinto eje de versión (`MappingSet.version`)** dentro de la tabla de
  versionado del Blueprint — señalado en § 26, no resuelto aquí.
- **Formato físico definitivo del catálogo "Registered Transforms"** (¿una
  hoja Excel adicional, o un fichero YAML versionado junto al código de la
  transformación, más cercano a `config/validation_rules.yaml`?) — ambos
  son compatibles con este documento; la decisión final es de
  implementación, no de este diseño.
- **Relación exacta entre `MappingSet.source_schema_version` y un futuro
  Connector formal** — aplazada junto con la propia interfaz de Connector
  (`extensibility-model.md` § 5, ya pospuesta hasta el segundo Connector
  real).

## 28. Criterios de aceptación

1. Ninguna regla de este modelo puede representar código Python, SQL
   arbitrario, una expresión `eval` ni una fórmula ejecutable no
   controlada — verificado en § 9: todo campo de vocabulario abierto es,
   o bien una cadena de un vocabulario cerrado, o bien una referencia a un
   catálogo/campo, nunca texto interpretado como código.
2. La Mapping Specification no duplica el CDM (§ 3, § 23) ni el futuro
   Enablon Template Contract (§ 3, § 24) — ningún ejemplo de § 25 declara
   una plantilla CSV completa.
3. `default`, `null`, `vacío`, `ausencia` y `exclusión` están distinguidos
   en cinco (realmente siete, § 17) representaciones distintas, nunca
   comprimidas en una.
4. `value_map`, `lookup` y `reference` están claramente diferenciados
   (§ 15), con criterio explícito para decidir cuál usar en cada caso.
5. Ningún conflicto (misma prioridad, lookup ambiguo, value map duplicado)
   se resuelve en silencio — todos son error o advertencia de validación
   explícita (§ 12, § 22).
6. `TransformationTrace` queda resuelto (§ 20) con una decisión concreta
   (opción B acotada), cerrando la decisión diferida por ADR-014.
7. Excel es una interfaz de edición (§ 21), nunca el modelo de ejecución
   — ninguna hoja propuesta requiere que Excel evalúe una fórmula para que
   la especificación tenga significado.
8. Los tipos de regla seleccionados (§ 10) generalizan evidencia real ya
   confirmada — ninguno se inventó sin un caso ya visto en
   `CLAUDE.md`/`config/validation_rules.yaml`/código real.
