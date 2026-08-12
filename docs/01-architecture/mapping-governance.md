# Mapping Governance — EMF

**Status:** Proposed (Sprint 8.8 — Mapping Governance & Knowledge
Consolidation). Framework conceptual y de proceso, construido sobre
evidencia real inspeccionada en solo lectura de `EMF_DATA_ROOT/projects/moeve/`
(ETL, CSV Template, CSV Operational, Errors, Mappings, SQL). No implementa
código nuevo de ejecución — formaliza cómo se registra, prioriza y audita
el conocimiento de mapeo que ya existía disperso en Excel/CSV/SQL/incidencias.
Se apoya en el vocabulario ya aprobado de
[`project-contract-model.md`](project-contract-model.md) (Platform / Project
/ EMF Contract) y en el modelo conceptual de
[`mapping-specification.md`](mapping-specification.md) (`MappingSet` /
`MappingRule` / `rule_type`), sin redefinirlos.

## 0. Por qué existe este documento

El Sprint 8.1 (`knowledge-coverage-matrix.md`, `knowledge-traceability-matrix.md`)
auditó lo que el EMF sabe **sin tocar ningún ETL real**. Este sprint (8.8)
es la primera vez que el repositorio tiene acceso de solo lectura al
workspace real de Moeve — 11 libros ETL (21 MB–361 MB cada uno), 44 CSV
reales (Template + Operational), un export de incidencias y dos paquetes
`.zip` no abiertos (ver § 9). El riesgo que este documento existe para
evitar: que ese conocimiento recién visible quede otra vez disperso en la
cabeza de quien lo miró, en vez de quedar registrado de forma que un
consultor distinto pueda auditarlo sin reabrir los mismos 11 Excel.

## 1. Principio central

Ninguna regla de mapeo funcionalmente relevante debe vivir solo en un
ETL, CSV, Word, PDF, query aislada o memoria de un consultor. Toda regla
relevante se representa, conceptualmente, como la cadena:

```
Cliente → Proyecto → Módulo → Objeto → Campo destino → Regla → Origen → Evidencia → Versión → Estado de validación
```

Este documento define **cómo** se registra esa cadena (identidad de
regla, § 3), **cómo** se decide qué evidencia manda cuando hay más de una
(precedencia, § 2) y **qué se hace cuando dos evidencias de alta prioridad
se contradicen** (conflicto, § 4) — nunca resolviéndolo en silencio.

## 2. Precedencia de evidencias

No se usa "el archivo más reciente gana". El `mtime` del archivo es una
señal débil: en este mismo sprint, el ETL con el mecanismo de mapeo de eje
más antiguo (`Entidades_Mapeo`, estático, ya marcado obsoleto en
`CLAUDE.md`) tiene fecha de modificación **posterior** al ETL con el
mecanismo más nuevo (`MapeoEje_uorg` + `Exportación eje`, catálogo vivo) —
ver caso Action Plans, § 7. Guiarse por `mtime` habría invertido la
precedencia real.

Orden de precedencia (mayor a menor):

1. **Evidencia expresamente validada como vigente** — confirmada por el
   cliente o por un consultor con autoridad sobre el dato, documentada
   como tal (no inferida).
2. **CSV Operational usado realmente en una carga aceptada**
   (`csv_enablon_operational` — Project Contract, ver
   `project-contract-model.md` § 2.2).
3. **Mapping funcional aprobado** (hoja `MAP-*` / `Mapeo_*` de un ETL
   marcado `CURRENT_VERIFIED`, o documento de mapping entregado por el
   cliente).
4. **ETL verificado** (hoja de reglas presente y con datos, aunque no
   esté marcada expresamente como "aprobada").
5. **Configuración ejecutable actual del EMF** (`config/modules.yaml`,
   `config/exports/*.yaml` — lo que el motor realmente hace hoy).
6. **CSV Template de Enablon** (`csv_enablon_template` — Platform
   Contract; nunca decide qué es obligatorio mapear, solo qué existe como
   superficie posible).
7. **Evidencia histórica no validada** (hoja huérfana, ETL antiguo sin
   confirmación de vigencia, `Entidades_Mapeo` de un módulo individual —
   ver `CLAUDE.md`: "están todas desactualizadas").
8. **Inferencia automática** (deducción de este mismo pipeline de
   inspección sin confirmación humana — el nivel más bajo, nunca
   suficiente por sí solo para marcar una regla `CURRENT_VERIFIED`).

La precedencia ayuda a **proponer** una regla candidata vigente. Nunca
borra ni oculta la versión desplazada — ver `mapping_revision`, § 3.3.

## 3. Identidad de una regla de mapeo

### 3.1 Claves de identidad

Cada regla descubierta se representa con:

`mapping_set_id`, `rule_id`, `rule_revision`, `client_id`, `project_id`,
`module_id`, `object_type`, `target_field`, `source_field(s)`,
`rule_type`, `condition`, `transformation`, `lookup_reference`,
`default`, `null_behavior`, `exclusion_behavior`, `evidence_source`,
`evidence_location`, `confidence`, `status`, `functional_description`,
`technical_description`.

`rule_type` reutiliza el vocabulario cerrado ya definido en
`mapping-specification.md`, con tres valores añadidos por este sprint
porque son necesarios para distinguir columnas del Platform Contract que
el EMF **no** debe construir nunca (§ 6 de `project-contract-model.md`):

| `rule_type` | Uso |
|---|---|
| `direct`, `constant`, `default`, `value_map`, `lookup`, `conditional`, `concatenate`, `type_conversion`, `date_conversion`, `reference`, `exclusion`, `registered_transform` | Ya definidos en `mapping-specification.md`. |
| `system_managed` | Campo gestionado por Enablon, no por el cliente (p. ej. `Id`). |
| `enablon_calculated` | Derivado por Enablon en el momento de exportar (p. ej. `GOS` en Bypass — confirmado no importable en `config/modules.yaml`). |
| `non_importable` | Presente en el Platform Contract, sin vía de importación vía CSV/API (p. ej. `FechaEnvioFase1..6`/`MotivoAprobacionFase2/3/5`/`Autorizar` en Bypass). |

### 3.2 `source_document_id` (no la ruta absoluta)

Cada fuente física recibe un identificador estable que **no** es su ruta
absoluta (la ruta cambia con el workspace de cada consultor —
`EMF_DATA_ROOT` es local, ver `external-data-workspace.md`). Esquema
usado en el inventario de este sprint (`moeve-source-inventory.md`):

```
<categoria>:<slug-nombre-archivo-sin-extension>
```

Ejemplo: `etl:ap_gct_new_sitecan`, `csv_operational:action_plans_10082026_163`,
`mapping:attachmentslast`. El slug se deriva del nombre de archivo
normalizado (minúsculas, espacios→`_`, sin sufijos de fecha/contador
cuando hay múltiples exports del mismo objeto — el contador se guarda
aparte como `source_version`).

### 3.3 `mapping_revision`

Cuando dos fuentes representan la **misma** regla en dos momentos
distintos (no dos reglas distintas en paralelo — ver § 7 para la
distinción real encontrada en Action Plans), se registra una entidad
`mapping_revision`:

```
rule_id: <estable, no cambia entre revisiones>
revisions:
  - rule_revision: 1
    status: SUPERSEDED
    evidence_source: <source_document_id>
    summary: <qué hacía>
  - rule_revision: 2
    status: CURRENT_VERIFIED
    evidence_source: <source_document_id>
    summary: <qué hace ahora>
    supersedes: 1
```

La revisión anterior **nunca se borra** — queda con `status: SUPERSEDED`,
consultable para auditoría histórica.

## 4. `KNOWLEDGE_CONFLICT`

Se registra cuando dos fuentes de precedencia igual o ambigua se
contradicen y la contradicción no puede resolverse por la escala de § 2
sin una decisión humana. Esquema:

```yaml
conflict_id: <estable>
module_id: <...>
rule_id_or_field: <...>
source_a: {source_document_id, rule_revision, summary}
source_b: {source_document_id, rule_revision, summary}
impact: <qué se rompe si se elige mal>
recommendation: <propuesta razonada, no una decisión>
human_review_required: true
status: OPEN
```

Un `KNOWLEDGE_CONFLICT` **no bloquea** el resto del inventario — se
registra y se continúa. Ver § 7 (caso AP) y § 8 (caso ITP/MOC) para dos
conflictos reales abiertos por este sprint.

## 5. Estados de clasificación de fuente

`CURRENT_VERIFIED`, `CURRENT_UNVERIFIED`, `HISTORICAL`, `SUPERSEDED`,
`REFERENCE`, `UNKNOWN`. Ninguna fuente se clasifica `CURRENT_VERIFIED`
solo por inferencia automática (nivel 8 de § 2) — requiere confirmación
humana explícita, registrada en `evidence_source`.

## 6. Reglas de mapeo confirmadas por este sprint (evidencia real)

Todas verificadas por lectura directa de hojas `MAP-*`/`Mapeo_*` reales
(no inferidas) — patrón `DatoOrigen | DatoDestino | EsCondicion |
ReglaEspecial | Parametro` (variante 2 de `CLAUDE.md`) o `CampoOrigen |
Field Destiny XML | ... | Transformation From` (variante 1):

| Regla | Confirmado en (evidencia real, Sprint 8.8) | Nota nueva |
|---|---|---|
| `titlefix` | `Mapeo_Titulo` (Simulacros), `Title_map` (AP, Safety Meetings) | Aplicado junto a `cloneorigin` en la misma fila de regla — confirma que el fan-out a 5 idiomas y el stripping de comillas son la **misma** operación configurada, no dos pasos independientes. |
| `cloneorigin` | Mismas hojas que `titlefix`; también `Map_UserEnablon` (AP) | En `Map_UserEnablon`: `DatoOrigen="*"`, `ReglaEspecial=cloneorigin`, con `Parametro` conteniendo una fórmula `BUSCARX(...)` — el clon no es un passthrough puro aquí, pasa por un lookup antes de clonar. Matiz no documentado previamente. |
| `nullcontrol` | `Mapeo_Titulo` (Simulacros): fila con `DatoOrigen=NULL`, `ReglaEspecial=nullcontrol`, `Parametro="No name defined in historical data"` | Confirma el valor de sustitución literal para el caso de título vacío en Simulacros — no documentado antes con este texto exacto. |
| Lookup dinámico 2 pasos contra catálogo "en vivo" | `MapeoEje_uorg` + `Exportación eje` (AP_GCT, Eventos Nuevos), `Niveles` + `Exportación eje` (MOC) | Ver § 7/§ 8 — coexiste con `Entidades_Mapeo` estático en la mayoría de los módulos. |
| `replaceinreference` | No encontrado con este nombre exacto en las hojas inspeccionadas | Sigue **no verificado** — no se inventa su comportamiento. |
| `boolorigin` | No encontrado con este nombre exacto | Sigue **no verificado**. |

`replaceinreference` y `boolorigin` permanecen `UNRESOLVED_RULE` — no se
ha localizado una hoja que los nombre explícitamente en los 11 ETL
inspeccionados a nivel de hoja/cabecera. Esto **no** significa que no
existan (la inspección de este sprint fue de hoja+cabecera+muestra, no
celda-por-celda completa, ver `moeve-mapping-backlog.md` P3-01).

**Actualización Sprint 8.8.1 — motor real encontrado, tabla de reglas
reescrita con comportamiento confirmado por código fuente:**

La inspección autorizada de `Mappings/OneDrive_2_12-8-2026.zip` incluyó
`Documentos de explicación de los transformadores/Script ETL.txt` — el
código fuente completo (TypeScript, Office Scripts / `ExcelScript.Workbook`)
del motor que ejecuta **todas** las hojas `MAP-*`/`Mapeo_*` de los 11
ETL, disparado por un botón en la hoja `Index`, nunca por una macro VBA
(ver `KC-MOC-002`, resuelto arriba). Esto reemplaza la tabla de § 6
original con comportamiento confirmado por código, no solo por muestra
de celdas:

| Regla (`ReglaEspecial`) | Comportamiento confirmado por código | Nota |
|---|---|---|
| `titlefix` | Elimina `#¤¦\|§"'`, elimina saltos de línea, elimina comillas tipográficas (`""''`), trunca a `Parametro` caracteres si es un entero 1–100, si no a 149 por defecto. | Más amplio que "solo stripping de comillas" (CLAUDE.md) — también trunca longitud y elimina más caracteres especiales. |
| `nullcontrol` | Solo escribe `Parametro` como valor si **tanto** el valor previo en destino **como** el valor de origen actual están vacíos/NULL. Si el destino ya tiene algo, no lo pisa. | Confirma comportamiento ya documentado, con la condición exacta (`prev` Y `valor`, no solo uno). |
| `concat` | Acumula: `nuevo = prev + separador + descText + valor` (si `prev` existe) o `descText + valor` (si no). Separador por defecto `\r\n`. | Diseñado para acumular a través de **múltiples filas de origen** que comparten destino (patrón visto en `Asis_concat`, ver § 12.3), no una concatenación de 2-4 campos de una sola fila. |
| `barconcat` | Variante de `concat` activada cuando `Parametro` incluye el sufijo `=barconcat`: separador `" \| "`. | Confirma el separador `\|` ya documentado, ahora con el mecanismo exacto de activación. |
| (variantes de `concat` no documentadas antes) | `Parametro` con sufijo `=onlytext` (separador `"  "`), `=values` (usa el valor ya en destino en vez del de origen), `=separator` (fuerza `" \| "`). | Nuevo — no estaba en el catálogo de `CLAUDE.md`. |
| `replaceinreference` | Divide el valor de origen por comas; resuelve cada elemento contra una hoja de referencia (nombrada en `Parametro`) con el mismo patrón `DatoOrigen/DatoDestino`; concatena los resultados con `" \| "`; si ya había contenido en destino y no lo incluye, lo añade (dedup por `includes`). | Antes "no verificado con datos reales" — ahora confirmado por código. Uso concreto en Moeve no localizado todavía (backlog P3-01). |
| `boolorigin` | Solo actúa si el valor de origen es `true`/`1`/`VERDADERO`. Busca el **nombre del campo origen** (no su valor) en la columna `DatoOrigen` de una hoja de referencia y devuelve el `DatoDestino` correspondiente. | Antes "no verificado" — ahora confirmado. Traduce "el campo X es verdadero" en "escribe el valor Y asociado a X", no un mapeo de valor booleano directo. |
| `cloneto` | **Nueva, no estaba en el catálogo de `CLAUDE.md`.** Si `Parametro` tiene un nombre de campo, escribe el valor tanto en ese campo como en el campo destino original — un fan-out a 2 campos con nombre de destino secundario explícito en `Parametro`, distinto de `cloneorigin` (passthrough, sin `Parametro`). | Verificado por código; sin evidencia de uso confirmada en las hojas de Moeve inspeccionadas todavía. |
| `countIterations` / `countIterationList` | **Nuevas, no estaban en el catálogo.** Cuentan ocurrencias de `Parametro` dentro del valor de origen (`countIterations`), o cuentan elementos de una lista separada por comas/`/` (`countIterationList`, con variante `+1` si `Parametro` contiene `+`). | Verificadas por código; sin evidencia de uso confirmada en Moeve todavía. |
| `cloneorigin` | No es una `ReglaEspecial` procesada por el motor de reglas — es un **literal de texto** encontrado en la celda `DatoDestino` de la fila de referencia coincidente; cuando el motor lo encuentra ahí, escribe el valor de entrada tal cual en esa columna. | Confirma "passthrough directo" (CLAUDE.md) con el mecanismo exacto — y resuelve `P3-08` (AP `Map_UserEnablon`): el `BUSCARX` en `Parametro` es la resolución normal de la fila de match, no un paso especial de `cloneorigin`. |
| Condiciones `igualvalor`, `contains` (columna `EsCondicion`/`ReglaEspecial` de la fila condicional) | `igualvalor`: compara un campo nombrado en `Parametro` (formato `Campo=Valor`) contra un valor esperado. `contains`: normaliza acentos/mayúsculas y comprueba si el valor de origen **o** el valor previo en destino contienen el texto de `Parametro`. | Nuevas — no estaban documentadas como operadores de condición en `CLAUDE.md` (que solo documentaba `*`, implícitamente `=`/`!=`). |

**Dónde vive esta evidencia:** `Script ETL.txt` completo, más
`Guia sobre el proceso general de transformación de datos.docx` (guía
del propio consultor que construyó el motor, explica Index/Maps/
Transformaciones en prosa) y `Script Transformador - Documentacion.docx`
(copia del mismo código con cabecera "DOCUMENTACIÓN ETL OFFICE SCRIPT") —
los tres dentro de `Mappings/OneDrive_2_12-8-2026.zip`, carpeta
`Documentos de explicación de los transformadores/`. Ninguno se copió al
repositorio (son del cliente/consultor anterior, no datos reales de
fila, pero tampoco código propio de este proyecto) — ver
`moeve-mapping-backlog.md` para la recomendación sobre qué hacer con
ellos.

**Hallazgo operativo adicional:** la guía en prosa confirma una
convención no documentada antes: varias fórmulas de las hojas de mapeo
se escriben con un prefijo `$=` (p. ej. `$=BUSCARX(...)`, visto en `Title_map`
y `Map_UserEnablon` de AP) porque el motor no puede calcular ciertos
campos directamente — se guarda la fórmula como texto con `$` delante, y
un script auxiliar separado elimina el `$` para "activar" la fórmula
cuando corresponde. Esto explica por qué varias fórmulas capturadas
durante la Fase 4 de Sprint 8.8 aparecían como texto literal empezando
por `$=` en vez de como fórmulas Excel activas.

## 7. Caso obligatorio — Action Plans, evolución del mapping del eje

Hay dos ETL de Action Plans, y **no son dos versiones secuenciales del
mismo archivo** — son dos ETL paralelos, partición por origen, ya
documentado en `config/modules.yaml`:

| ETL | Alcance (`idorigenac`) | `source_document_id` |
|---|---|---|
| `ETL- AP_GCT_NEW_SITECAN.xlsx` | Solo origen MOC/GCT (hojas `CT_ACCIONES_*`) | `etl:ap_gct_new_sitecan` |
| `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN (1).xlsx` | Resto de módulos origen ITP (hojas `ITP_ACCIONES_EV_new/old/IPS/SIMS/OPS/SM/HAZ/OTROS`) | `etl:ap_con_ajuste_entidad_new_sietcan` |

La **modificación posterior del mapping del eje** que este sprint debía
registrar explícitamente (instrucción del encargo) es visible al comparar
el mecanismo de resolución de entidad (eje) entre ambos:

- **`ETL- AP-Con Ajuste Entidad_NEW_SIETCAN (1).xlsx`** solo tiene la
  hoja `Entidades_Mapeo` — el mecanismo estático por-módulo que
  `CLAUDE.md` ya marca como desactualizado ("no usar... están todas
  desactualizadas y son copias fragmentadas").
- **`ETL- AP_GCT_NEW_SITECAN.xlsx`** tiene, además, dos hojas que
  **no** existen en el anterior: `Exportación eje` (export en vivo del
  catálogo, mismo patrón `ruta/Parent/Code/EntityEN.../EntityStatus` que
  `First_Axis`) y `MapeoEje_uorg` (regla `DatoOrigen/DatoDestino/
  EsCondicion/ReglaEspecial/Parametro` que resuelve `IDUnidadOrg` contra
  ese catálogo vivo). Este es exactamente el patrón que `CLAUDE.md` ya
  identifica como "mejor patrón, preferible al lookup estático" (visto
  antes en SM/MOC).

**Registro `mapping_revision` (candidato, pendiente de confirmación
humana final):**

```yaml
rule_id: ap.entity_axis_resolution
revisions:
  - rule_revision: 1
    status: HISTORICAL
    evidence_source: "etl:ap_con_ajuste_entidad_new_sietcan#Entidades_Mapeo"
    summary: >
      Lookup estático por módulo contra hoja Entidades_Mapeo embebida en
      el propio ETL. Ámbito: AP de origen ITP (EVT/SIMS/IPS/OPS/SM/HAZ/OTROS).
  - rule_revision: 2
    status: CURRENT_UNVERIFIED
    evidence_source: "etl:ap_gct_new_sitecan#MapeoEje_uorg+Exportación eje"
    summary: >
      Resolución en 2 pasos contra catálogo vivo (Exportación eje) vía
      regla declarativa MapeoEje_uorg. Ámbito: AP de origen MOC/GCT.
    supersedes: 1
```

**Por qué queda `CURRENT_UNVERIFIED` y no `CURRENT_VERIFIED`:** el
encargo de este sprint afirma que existe una versión posterior
verificada del mapping del eje para AP, y la evidencia estructural
encontrada encaja con esa afirmación — pero los dos ETL cubren **ámbitos
de origen distintos** (GCT vs. ITP-genérico), no la misma partición de
datos. Que el mecanismo nuevo (`MapeoEje_uorg`/`Exportación eje`) deba
tratarse como el reemplazo general para *todo* AP (incluido el ámbito
ITP-genérico, que hoy solo tiene el mecanismo viejo) o como un mecanismo
propio y exclusivo del ámbito GCT es una pregunta que la inspección
estructural de este sprint no puede cerrar sola.

**Actualización Sprint 8.8.1:** ver § 12.1 — la inspección autorizada del
`.zip` de Mappings encontró el origen documental real de ambos
mecanismos y caracteriza mucho mejor el conflicto, sin cerrarlo.

`KNOWLEDGE_CONFLICT` registrado:

```yaml
conflict_id: KC-AP-001
module_id: ap
rule_id_or_field: ap.entity_axis_resolution
source_a:
  source_document_id: "etl:ap_con_ajuste_entidad_new_sietcan#Entidades_Mapeo"
  summary: "Mecanismo estático, cubre AP de origen ITP-genérico (7 submódulos)."
source_b:
  source_document_id: "etl:ap_gct_new_sitecan#MapeoEje_uorg"
  summary: "Mecanismo dinámico en 2 pasos, cubre solo AP de origen MOC/GCT."
impact: >
  Si el mecanismo nuevo debía reemplazar también al ITP-genérico y no lo
  hizo, el ETL de "AP-Con Ajuste Entidad" (pese a llevar "Ajuste Entidad"
  en el nombre) sigue dependiendo de un catálogo ya confirmado obsoleto
  en otros módulos (CLAUDE.md) — riesgo de repetir el mismo patrón de
  infra-migración de La Rábida/Palos que el Hallazgo #1 ya documentó en
  Eventos/Inspecciones/MOC.
recommendation: >
  Confirmar con el cliente/consultor si "AP-Con Ajuste Entidad" debía
  migrar también al mecanismo MapeoEje_uorg y quedó pendiente, o si el
  ajuste de entidad de ese ETL se hizo por otra vía no capturada en la
  inspección de hoja+cabecera de este sprint (posible fórmula dentro de
  ITP_ACCIONES_* no muestreada en profundidad — ver P1-01 en
  moeve-mapping-backlog.md).
human_review_required: true
status: OPEN
```

**Reformulación tras Checkpoint (post Sprint 8.9):** el estado se
precisa a `OPEN — CURRENT STATIC MECHANISM STRONGLY EVIDENCED`. Tres
fuentes independientes (este ETL, el workbook dedicado "version 4,
final" de Sprint 8.8.1, y C003 en Sprint 8.9) confirman que
`Entidades_Mapeo` es el mecanismo real y actualmente en uso para el
ámbito ITP-genérico — no una copia fragmentada sin relación. No existe,
en ninguna fuente inspeccionada en tres sprints, evidencia observada de
resincronización posterior con el catálogo vivo. Las dos alternativas ya
no se presentan como igual de probables: lo que queda genuinamente
abierto es solo si existe una decisión funcional del cliente no
materializada en ningún artefacto — eso no se puede inferir, solo
confirmar con el cliente. Ver
`config/knowledge/moeve/ap/knowledge-conflicts.yaml`
(`status_note_checkpoint`) para el detalle completo.

Ver `docs/07-developer-guide/moeve-mapping-backlog.md` (P1-01) y
`config/knowledge/moeve/ap/` para el artefacto concreto.

## 8. Segundo caso de versionado — MOC

`ETL_MOC_m_NEW_SITECAN.xlsm` (2026-07-28) y `ETL_MOC_NewColumns.xlsm`
(2026-08-11) tienen **exactamente las mismas 80 hojas, en el mismo
orden** — son la misma estructura de ETL en dos momentos (el nombre del
segundo, "NewColumns", y su fecha más reciente son coherentes con una
revisión que añade columnas sin rehacer la estructura). No se detectó
diferencia de hojas entre ambos con la inspección de este sprint — una
comparación columna-por-columna de las hojas `Mapeo_*`/`CSV_MOC_*`
requiere una pasada dedicada (ver P2-03 en el backlog) para confirmar
exactamente qué columnas se añadieron.

**Hallazgo que reabre una afirmación de `CLAUDE.md`:** ambos ficheros
`.xlsm` de MOC contienen un `vbaProject.bin` real dentro de su contenedor
OOXML (`has_vba_project: true`, verificado por listado de la estructura
zip interna del propio `.xlsm` — sin ejecutar ni decompilar el macro).
`CLAUDE.md` documenta: *"VBA del libro confirmado 100% vacío — titlefix
no tiene motor visible en el Excel"*. La presencia del `vbaProject.bin`
no contradice necesariamente esa afirmación (un proyecto VBA puede
existir vacío o solo con formularios sin código), pero **tampoco la
confirma** — este sprint no decompiló el macro (fuera de alcance,
prohibido ejecutar/recalcular). Se registra como:

```yaml
conflict_id: KC-MOC-002
module_id: moc
rule_id_or_field: titlefix.engine_location
source_a:
  source_document_id: "CLAUDE.md#moc"
  summary: "VBA del libro confirmado 100% vacío (sprint/consultor anterior)."
source_b:
  source_document_id: "etl:moc_m_new_sitecan, etl:moc_newcolumns"
  summary: "vbaProject.bin presente en la estructura interna del .xlsm (solo presencia verificada, contenido no inspeccionado)."
impact: "Bajo — no cambia el comportamiento conocido de titlefix (stripping de comillas), pero la afirmación 'VBA 100% vacío' queda sin reverificar con este hallazgo."
recommendation: "Reverificar con el consultor que dejó esa nota, o inspeccionar el vbaProject.bin (metadata de módulos, sin ejecutar) en un incremento dedicado."
human_review_required: true
status: RESOLVED (Sprint 8.8.1)
resolution: >
  El motor real de titlefix (y de todas las hojas MAP-*/Mapeo_*, de los
  11 ETL, no solo MOC) no es VBA — es un Office Script (TypeScript,
  API ExcelScript.Workbook) documentado y con código fuente completo en
  Documentos de explicación de los transformadores/Script ETL.txt (ver
  § 12.2). Se ejecuta desde un botón en la hoja Index, no desde una
  macro embebida. El `vbaProject.bin` presente en los dos .xlsm de MOC
  no es el motor de transformación — su contenido no se inspeccionó
  (fuera de alcance, no aporta a esta pregunta) y puede corresponder a
  otra utilidad menor sin relación con titlefix. La afirmación de
  CLAUDE.md ("VBA del libro confirmado 100% vacío") queda confirmada en
  espíritu: el motor real nunca estuvo en VBA.
```

## 9. Los dos `.zip` — inspeccionados en Sprint 8.8.1

`Mappings/OneDrive_2_12-8-2026.zip` (2.3 MB) y
`SQL/OneDrive_1_12-8-2026.zip` (88 KB) **no se extrajeron** en Sprint 8.8
— el encargo prohibía extraer ZIP sin autorización explícita, y no se
había pedido. Sprint 8.8.1 recibió esa autorización explícita (solo
lectura, extracción a una carpeta temporal fuera del repositorio y fuera
de las carpetas fuente, sin ejecutar contenido, copia temporal borrada
al finalizar) — ver § 12 para el resultado completo.

## 10. Dónde viven estos artefactos (decisión de ubicación, Fase 15/16)

`config/` ya es, en este repositorio, el lugar de metadata estructurada
por módulo/objeto que se versiona como datos (`modules.yaml`,
`data_workspace.yaml`, `exports/*.yaml`, `validation_rules.yaml` — el
principio de ADR-013, "mappings as data"). Este sprint **no** crea una
raíz nueva `knowledge/` en el repositorio — extiende ese mismo patrón en
`config/knowledge/<client>/<module>/`, con el esquema:

```
config/knowledge/moeve/<module>/
  mapping-set.yaml          # reglas identificadas (§ 3.1), sin datos reales
  mapping-coverage.yaml     # cobertura del Project Contract (ver moeve-mapping-backlog.md § 1)
  unresolved-rules.yaml     # UNRESOLVED_RULE, con evidence_location
  knowledge-conflicts.yaml  # KNOWLEDGE_CONFLICT (§ 4)
  source-inventory.yaml     # source_document_id -> metadata (subset del inventario global)
  mapping-evidence.md       # narrativa legible, para consultor sin leer YAML
```

Este sprint **materializa solo `config/knowledge/moeve/ap/`** (el caso
obligatorio, § 7) como ejemplo concreto y auditable del esquema. Los
otros 8 módulos quedan con la misma plantilla pendiente de rellenar
(backlog P3 — no se genera contenido vacío o inferido solo para
completar la carpeta, ver principio de no inventar en `CLAUDE.md`).

El workbook `Mapping Inventory XLSX` (Fase 16 del encargo) queda
**diseñado, no generado** — las pestañas propuestas (Resumen, Project
Contract, Campos, CS_, Value Maps, Lookups, Conditions, Entity Mapping,
Exclusions, SQL Sources, Conflicts, Unresolved, Evidence, Revisions)
mapean 1:1 contra los ficheros YAML de arriba más las tablas de
`moeve-source-inventory.md`; generarlo hoy no ampliaría el conocimiento
ya capturado, solo lo re-empaquetaría — se deja como tarea de un sprint
posterior una vez exista más de un módulo con `mapping-set.yaml` real que
justifique el volumen de un workbook.

## 12. Sprint 8.8.1 — Knowledge Closure (contenido del ZIP)

### 12.1 Mappings ZIP — un tercer grupo de fuentes de mapeo de eje

`Mappings/OneDrive_2_12-8-2026.zip` (SHA-256
`4e0d5a8e3d1b75be9ce9e7efdf06b3f053fa38f77e79db3322eac3066f12c01c`, 10
entradas) contiene, además de la documentación del motor (§ 6, § 12.2):

| Archivo | `source_document_id` | Contenido |
|---|---|---|
| `Mapeos del Eje-ITP/Mapeo ITP primer eje enablon_revisado _final1 (version 4).xlsx` | `mapping:mapeo_itp_primer_eje_v4` | Workbook dedicado de mapeo de eje ITP-genérico. Hoja `MAPEOFINAL` (681 filas), hoja `Eje final 2` (catálogo estilo First_Axis, 3038 filas), hoja `EJE SITE CANARIAS (V1 oct2025)`, tabs por site (C&CE, Madrid Corporación, MCPF, MCSH, MCPM, M&NC, Site Canarias, PESR, PELR). |
| `Mapeos Eje - GCT/260311 Mapeo gct Enablon-Match UORG ENTIDAD.xlsx` | `mapping:mapeo_gct_match_uorg_entidad` | Hoja `Exportación eje`, contenido **idéntico fila a fila** al de la misma hoja embebida en `ap_gct`/`moc_m_new`/`moc_newcolumns`. |
| `Mapeos Eje - GCT/260311 Mapeo gct Enablon.xlsx`, `Mapeo_Eje_GCT_Enablon.xlsx` | (referencia) | Workbooks de trabajo/borrador relacionados, no inspeccionados en profundidad. |

**Hallazgo central (comparación de contenido de fila, dato real, no
fórmula):** la fila 2 de `MAPEOFINAL` (`IDCentro=7`, `IDDepartamento=77`,
`IDUnidadOrg=278`, "MC-Palos de la Frontera", "CONTRATAS GENERICAS",
"MCPF Histórico") es **idéntica** a la fila 2 de la hoja `Entidades_Mapeo`
embebida en el ETL de Bypass — mismo `IDCentro`/`IDDepartamento`/
`IDUnidadOrg`, mismo texto ENABLON. `Entidades_Mapeo` (presente en 8 de
los 11 ETL) no es un fragmento arbitrario y desconectado — es una
**instantánea de valores** de este workbook dedicado, en su versión
"4, final".

Esto actualiza `KC-AP-001` (ver `config/knowledge/moeve/ap/knowledge-conflicts.yaml`,
`status_note_8_8_1`) sin cerrarlo: confirma que el ámbito ITP-genérico
**sí tuvo** un esfuerzo de mapeo de eje dedicado y versionado, tan real
como el de GCT — la pregunta abierta ahora es más precisa: si los 7 ETL
de ámbito ITP-genérico se resincronizaron desde esta "version 4" en
algún momento posterior, o si quedaron congelados en esa entrega
mientras el eje de Enablon seguía evolucionando (lo que explicaría, sin
contradecir, el hallazgo ya validado empíricamente en `CLAUDE.md` de
42–59% "no catalogado" al usar `Entidades_Mapeo` directamente).

### 12.2 El motor real: Office Script, no VBA — ver § 6 y `KC-MOC-002`

Resuelto arriba (§ 6, § 8). Fuente: `Script ETL.txt` (código completo),
`Guia sobre el proceso general de transformación de datos.docx`
(explicación en prosa del propio consultor autor) y
`Script Transformador - Documentacion.docx` (copia con cabecera
"DOCUMENTACIÓN ETL OFFICE SCRIPT").

La guía en prosa también confirma, en primera persona, la arquitectura
ya inferida estructuralmente en Sprint 8.8: hoja `Index` controla
`Sources Data`/`Destiny Name Headers`/`Maps`/`Final data`; los mapas
tienen `CampoOrigen`/`Field Destiny XML`/`Adaptación`/`Transformation
From`; las hojas de transformación tienen `DatoOrigen`/`DatoDestino`/
`EsCondicion`/`ReglaEspecial`/`Parametro`. Confirma además una regla de
negocio no documentada en `CLAUDE.md`: el split de Eventos Antiguos en
`ITP-EVENTOS_OLD2` (filtrado a `IDTipoAccidente` 408/409, "PERSONAL") y
`ITP-EVENTOS_OLD-in` (407/null, "INDUSTRIAL"/NearMiss/sin definir), y
recomienda no regenerar eventos antiguos ya cargados en UAT — usar el
transformador solo para correcciones puntuales.

Un segundo documento del mismo paquete,
`Información detallada sobre todas las asunciones y procedimientos a
tener en cuenta para la carga de históricos.docx` (25 180 caracteres,
tabla de contenidos con los 9 módulos), es un documento formal de
asunciones y procedimientos de carga — candidato directo a resolver el
ticket de cliente `#7581` ya citado en `CLAUDE.md` ("el propio cliente
pidiendo la documentación de mapeo que este proyecto produce"): **puede
que ya exista**, solo no estaba incorporado al proyecto hasta este
sprint. Ver `moeve-mapping-backlog.md` para la recomendación.

### 12.3 `OQ-ETL-01` y `OQ-ETL-02` (Drills) — RESUELTOS

Con el motor confirmado (§ 12.2) y lectura completa (sin truncar) de las
celdas relevantes del ETL de Simulacros:

**`OQ-ETL-02` (`CS_Duration`) — RESUELTO.** La hoja `MapeoSims`, fila 27
(`CampoOrigen=Duracion`), tiene `Adaptación=No` — es decir, **passthrough
directo**, sin transformación, del valor crudo de `Duracion` (SQL) a
`CS_Duration`. Confirmado resolviendo manualmente la fórmula `XLOOKUP`
de la fila (columna destino real = `CS_Duration`, fila 13 de la propia
hoja). La hoja `CalculoHorasDiasMinutos` (que Sprint 8.8 identificó como
candidata) **no** alimenta `CS_Duration` de Drills — alimenta los 4
campos separados `CS_DurationMonths/Days/Hours/Minutes` de un objeto
distinto (`List of Activities`, BCM), con las fórmulas exactas:
`CS_DurationMonths=INT(NUMBERVALUE(C2)/(24*30))`,
`CS_DurationDays=INT(MOD(NUMBERVALUE(C2),24*30)/24)`,
`CS_DurationHours=INT(MOD(NUMBERVALUE(C2),24))`,
`CS_DurationMinutes=MROUND(INT(MOD(NUMBERVALUE(C2),1)*60),5)` — confirma
exactamente el "mes de 30 días fijo" y el "redondeo a 5 min" ya
documentados en `CLAUDE.md`, pero para `List of Activities`, no para
`CS_Duration` de Drills.

**`OQ-ETL-01` (`CS_HistoricalDrillAttendees`) — RESUELTO.** Dos
mecanismos independientes alimentan el mismo campo destino:
1. `MapeoSims`, fila 35 (`CampoOrigen=Asistentes`, vía resolución de la
   fórmula `XLOOKUP` de la fila 27): `Adaptación=No` — passthrough
   directo del campo de texto libre `Asistentes` de `DB_OrigenSim` (ya
   una lista de nombres separada por comas, tecleada por el
   preventionista original).
2. `Mapeo_asistentes` y `Mapeo_asistentes_EXT` (`CampoOrigen=NombreAsistente`,
   `Adaptación=Sí`, `Transformation From=Asis_concat`): concatenación
   fila a fila (una fila por asistente en `ITP_ASIST_SIMS`/
   `ITP_ASIST_SIMS_EXT`) mediante la regla `concat` (§ 6), que **añade**
   (no sobrescribe) al valor ya presente en destino, separador `\r\n`
   por defecto.

Ambos escriben al mismo campo destino final (`CS_HistoricalDrillAttendees`
via `nuevo-campo-Asistentes_Historicos`) — el resultado esperado es el
texto libre original más, a continuación, los nombres individuales
concatenados desde las tablas de asistentes internos/externos. No se
confirma el orden exacto de ejecución (create vs. update) ni si hay
deduplicación entre ambos — ver `moeve-mapping-backlog.md` para el ítem
residual de menor prioridad.

Actualizado en `docs/01-architecture/knowledge-traceability-matrix.md`
(filas `CS_Duration`, `CS_HistoricalDrillAttendees`).

### 12.4 SQL ZIP — reconciliación completa

`SQL/OneDrive_1_12-8-2026.zip` (SHA-256
`8d8e214f20a8dff3df0c89464b5da6d2e3a879fb53829c0fc5780d6c57b15438`, 43
entradas) — comparado archivo por archivo (nombre + hash SHA-256 de
contenido) contra `sql/source_queries/`:

| Categoría | Resultado |
|---|---:|
| `SQL_DUPLICATE` (mismo nombre, contenido idéntico) | 43 de 43 |
| `SQL_VARIANT` | 0 |
| `SQL_ONLY_IN_ZIP` | 0 |
| `SQL_ONLY_IN_REPOSITORY` | 0 |
| `SQL_CONFLICT` | 0 |

**100% del contenido SQL del zip ya está versionado, byte a byte
idéntico, en el repositorio.** Único hallazgo menor: 2 de los 43 archivos
(`SQLQuery- LOCALIZACION DE LESIÓN ANTIGUOS.sql` y su variante "+TIPO")
tienen, en el repositorio, un nombre de archivo con mojibake
(doble-codificación UTF-8→cp1252→UTF-8 de la "Ó") — el contenido es
idéntico, solo el nombre de archivo en disco está mal codificado desde
que se commiteó. Cosmético, sin impacto funcional — ver
`moeve-mapping-backlog.md` P4.

`SQL_ONLY_IN_REPOSITORY` queda en 0 — cierra la incertidumbre que
Sprint 8.8 había dejado abierta en su § 9.4.

### 12.5 Limpieza

La copia temporal de ambos ZIP extraídos (`scratchpad/zip_extract/`, en
el directorio temporal de la sesión, nunca dentro del repositorio ni de
las carpetas fuente originales) se eliminó al finalizar esta fase. Los
`.zip` originales en `EMF_DATA_ROOT` no se modificaron — verificado por
`testzip()` antes y después de la inspección (sin entradas corruptas).

## 13. Sprint 8.9 — C003 Knowledge Adoption

C003 (`C:\Users\EduardoVelásquez\Desktop\C003-ActionPlans-Tool-v3\`,
herramienta nativa T-SQL/PowerShell/Python que reemplaza al ETL Excel de
Action Plans) se incorporó como fuente de conocimiento — nunca como
runtime ni base tecnológica del EMF (nivel de precedencia 7, "evidencia
histórica no validada", salvo coincidencia con una fuente de precedencia
mayor). Detalle completo en `docs/07-developer-guide/c003-knowledge-adoption.md`
(30 reglas reconstruidas por lectura estática) y
`docs/01-architecture/action-plans-native-design.md` (diseño del futuro
Adaptador AP nativo — identidad, transversalidad, parent policy, Project
Contract, `MappingSet`, `PipelineStages`).

Actualizaciones a `KC-AP-001`: tercera confirmación independiente (tras
el ETL y el workbook dedicado de Sprint 8.8.1) de que `Entidades_Mapeo`
es una fuente real y deliberadamente usada — C003 la extrae
explícitamente por nombre de hoja. No cierra el conflicto — ver
`config/knowledge/moeve/ap/knowledge-conflicts.yaml` (`status_note_8_9`).

`KC-MOC-002` no se reabre — C003 no aporta evidencia sobre MOC.

Ningún dato real de C003 (`runs/`, config CSV) se copió a este
repositorio — solo metadata de regla, nombres de columna/tabla y código
SQL/PowerShell citado como evidencia de mecanismo.

## 14. Historial de revisión

- Sprint 8.8 (2026-08-12): creación. Primer sprint con acceso de solo
  lectura al workspace real de Moeve.
- Sprint 8.8.1 (2026-08-12): Knowledge Closure. Inspección autorizada de
  los 2 `.zip`; `KC-MOC-002` resuelto (motor = Office Script, no VBA);
  `KC-AP-001` mejor caracterizado (no cerrado); catálogo de reglas
  ampliado con comportamiento confirmado por código fuente y 2 reglas +
  2 operadores de condición nuevos; `OQ-ETL-01`/`OQ-ETL-02` de Drills
  resueltos; reconciliación SQL 100% duplicado sin variantes.
- Sprint 8.9 (2026-08-12): C003 Knowledge Adoption & Action Plans Native
  Design. Ver § 13.
