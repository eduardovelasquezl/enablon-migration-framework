# Micro-sprint 9.9.2 — Field Constraints & Text Normalization Design

**Objetivo:** convertir la evidencia real de Micro-sprint 9.9.1 (Field
Specifications + error de carga reportado) en un diseño gobernado,
preparado para implementación futura. **No se implementa el motor de Field
Constraints en este sprint.** Ningún SQL real ejecutado. `Raw/` de Field
Specifications no modificado ni normalizado.

---

## Fase 0 — Cierre de Micro-sprint 9.9.1

- **Commit creado:** `a8ba2aa6dbc4f2971c944ee301f6c78a04df834b` —
  `fix(export): correct CSV Output Contract (UTF-8 BOM) across all modules`.
  12 ficheros, +770/-16. Incluye el matiz explícito pedido: UTF-8+BOM
  corrige el problema práctico de mojibake, pero los CSV "padre" reales de
  Enablon usan nativamente UTF-16LE+BOM+TAB+quote-all -- no se declara
  UTF-8+BOM como formato universal de importación sin evidencia adicional.
- **Suite tras el commit:** `860 passed, 7 skipped`.
- **`Raw/Export_Spec_Stand30.xls.xlsx`:** intacto, solo lectura en todo momento.
- **Sin datos reales ni secretos versionados**, `src/core/` sin cambios
  (confirmado por el propio diff del commit -- ningún fichero de `src/core/`
  en la lista).

## Fase 1 — Inventario real de Field Specifications

Releído `Raw/Export_Spec_Stand30.xls.xlsx` (solo lectura). Cabecera real en
fila 13 de cada hoja de objeto -- columnas confirmadas por letra de Excel
(no inventadas):

| Columna Excel | Nombre real | Alimenta a |
|---|---|---|
| `O` | `XML Info` | **internal field name** (p. ej. `CS_HistoricalOriginID`) |
| `L` / `M` | `Short Name` / `Long Name` | **display label** |
| `C` / `D` (fila 14, por hoja) | `Application Name` / `Name` | **object/module** (nombre real del objeto Enablon) |
| `P` | `Type` | **data type** (`Text`, `Date`, `Currency`, `Float`, `Text Area`, `MultiLink(<objeto>)`, `Link(<catálogo>)`, `CCL: v1/v2/...` = lista fija) |
| `Q` | `Size Max` | **max length** (entero; `0` = sin límite declarado) |
| `AG` | `Mandatory` | **required** (`Never`/`Add`/`Edit`/`Edit/Add` -- contextual, no booleano) |
| `AE` | `Input` | **read-only** (`Never` = nunca editable directamente -- la señal real de solo-lectura, no `Category`) |
| `S` | `Virtual` | **system/automatic** (`Yes` = valor calculado por la plataforma, ver `Expression`/`Format Expression`) |
| `P` (cuando `MultiLink`/`Link`) | `Type` | **reference/list** (apunta al objeto/catálogo referenciado) |
| `Z` | `Default Expression` | **default** (fórmula, no siempre un literal simple) |
| `O` (prefijo) | `XML Info` | **custom CS_\*** (empieza por `CS_`) |
| `AK` / `AL` | `Export` / `Import` | participación real en export/import (`Always`/`If Visible`/`If Editable`/`Never`) |
| `AP` / `AQ` | `Sensitivity Level` / `Privacy Notice` | dato personal (`Confidential (Privacy)` en 50/1238 filas) |

**Corrección respecto a una hipótesis inicial de esta misma fase:** la
columna `Category` (`AO`) NO es una señal de "campo de sistema" -- es
clasificación de dato personal (`N/A` en 1114/1238 filas, `Identity (Name,
Firstname, User ID...)` en 29, `Geolocation` en 7...), del mismo grupo que
`Sensitivity Level`/`Privacy Notice`. La señal real de solo-lectura/sistema
es `Input=Never` (353/1238 filas) combinado con `Virtual=Yes` (205/1238) --
verificado por distribución real, no asumido por el nombre de columna.

No se inventa ninguna propiedad que el XLSX no contenga -- no hay columna de
`overflow_policy`, `forbidden_characters`, ni `replacements`: esas son
decisiones de proyecto (Fase 3/4), no datos de Enablon.

## Fase 2 — `max_length` es field-specific (regla arquitectónica)

**No existe un `max_length` global para campos de texto.** Confirmado con
los propios datos: `Reference` (Drills) = 40, `CS_HistoricalDataOrigin`
(Drills) = 70, `CS_MeetingPlace` (Safety Meetings) = 80,
`CS_HistoricalAtendee` (Safety Meetings) = 4096 -- cuatro campos de tipo
`Text`/`Text Area`, cuatro límites distintos, en dos objetos distintos. El
esquema futuro debe declarar `constraints.max_length` **por campo**, nunca
un valor por defecto aplicado a todo tipo `Text`.

### `TitleEN`: `Size Max=240` (Field Specifications) vs. `Parametro=239` (ETL)

Releída `Title_map` del ETL real de Safety Meetings
(`ETL- Reunionesdegrupo-fixEntities_SITECAN.xlsx`):

```
DatoOrigen | DatoDestino | EsCondicion | ReglaEspecial | Parametro | Topic
(vacío)    | (vacío)     | (vacío)     | titlefix      | 239       | cloneorigin
```

Sin motor visible (ninguna fórmula ni macro asociada -- mismo patrón ya
registrado en CLAUDE.md para `titlefix` en otros módulos: "no tiene motor
visible en ningún Excel ni VBA de los 7 libros auditados"). **No puede
demostrarse matemáticamente la relación 239↔240 desde el ETL** -- se
registran dos hipótesis, ninguna confirmada:

1. **Margen de seguridad de 1 carácter** (`240 - 1 = 239`): el autor del
   ETL pudo reservar un carácter de margen deliberadamente, o usar un
   límite calculado con un índice base distinto (0 vs 1) al truncar.
2. **Valores no relacionados**: `Parametro=239` podría no ser en absoluto
   un `max_length`, sino otro tipo de parámetro del motor no documentado de
   `titlefix` -- la coincidencia numérica cercana (239 vs 240) sería
   entonces casualidad.

**Se deja abierta, no se asume.** Si se implementa en el futuro, la fuente
AUTORITATIVA para `max_length` debe ser **Field Specifications (240)**, por
ser dato de plataforma confirmado -- no el `Parametro` del ETL (239), que
sigue siendo un mecanismo no documentado. Decisión de implementación
(¿240? ¿239? ¿ambos, con `239` como margen de seguridad deliberado?) queda
para revisión humana explícita, no para este diseño.

## Fase 3 — Restricciones de caracteres: tres capas

Evidencia de partida (aportada por el usuario, error real de carga
Enablon, no localizado como fichero en este repositorio -- tratado como
hecho dado, mismo criterio que el documento de incidencias del cliente en
CLAUDE.md):

```
Error row 1: Field "Event Title" cannot contain any of the following
characters: "¤¦|§\r\n
```

**Observación de apoyo, real, encontrada en este micro-sprint:** el
carácter `¤` (U+00A4) NO es ruido -- aparece de forma intencional en un CSV
"hijo" real de Enablon (`Checklists Data-24_Change Register.csv`, Sprint
9.9.1 Fase 1) como **separador interno de Enablon dentro de una misma
celda**: `"20/10/2025 00:00:00¤IMP-000610.P01"`. Esto es evidencia real
(no asumida) de que al menos `¤` está reservado por la propia plataforma
como carácter de control/separador, no solo prohibido por capricho --
consistente con que `|` (también reservado internamente por este mismo
proyecto como separador de `barconcat`, ver CLAUDE.md) y `§`/comillas/CR/LF
sean del mismo tipo: caracteres con significado estructural que colisionan
si aparecen dentro de un valor de dato.

**Diseño de tres capas (conceptual, no implementado):**

### A) PLATFORM/FIELD CONSTRAINT
Qué caracteres están REALMENTE prohibidos por Enablon para un campo
concreto. Evidencia disponible hoy: 6 caracteres confirmados por el error
real (`"`, `¤`, `¦`, `|`, `§`, CR, LF -- 7 si se cuentan CR y LF por
separado). **No universal a todos los campos de texto** -- el error es
específico de `Field "Event Title"`; no hay evidencia de que la misma
lista aplique a todos los `Text`/`Text Area` de todos los objetos. Se
declara por campo (o por `Type`, si evidencia futura lo confirma como
propiedad del tipo, no del campo individual).

### B) PROJECT NORMALIZATION POLICY
Qué debe hacer EMF cuando aparecen. Política, no dato de Enablon --
decisión de proyecto, configurable por campo/contrato.

### C) FIELD-SPECIFIC OVERRIDE
Excepciones/reglas particulares de un campo u objeto concreto que
sobrescriben la política de proyecto por defecto (p. ej. un campo donde
`|` SÍ debe rechazarse en vez de reemplazarse, porque ese campo en
concreto alimenta un proceso interno que usa `|` como separador real).

## Fase 4 — Políticas de normalización

**Confirmado por el error real:** `"`, `¤`, `¦`, `|`, `§`, CR, LF.
**NO confirmado:** que `-` esté prohibido. La práctica histórica aportada
por el usuario (`" -> '`, `\ -> eliminar`, `- -> _`) se registra como
**candidato**, no como regla -- en particular, **`- -> _` NO se aplica
globalmente** sin evidencia adicional, tal como pide explícitamente el
encargo.

Diseño conceptual (`invalid_character_policy`, enum):

```yaml
invalid_character_policy:
  - reject    # la fila se excluye/marca error -- ningún carácter se toca
  - replace   # sustitución declarativa 1:1 por constraints.replacements
  - remove    # el carácter se elimina, sin sustituto
  - warn      # el valor se conserva TAL CUAL, se registra un warning (ver Fase 6) -- nunca "warn y además modificar en silencio"
```

Ejemplo conceptual (NO implementado literalmente, valores ilustrativos que
requerirían confirmación campo a campo antes de usarse):

```yaml
constraints:
  forbidden_characters: ['"', '¤', '¦', '|', '§', '\r', '\n']
  replacements:
    '"': "'"      # candidato histórico -- aplicar solo si se confirma para ESTE campo
    '|': '_'       # candidato -- "|" es separador reservado (Fase 3), reemplazo razonable pero no confirmado por Enablon
    '¤': ''        # sin candidato histórico -- pendiente de decisión humana
    '¦': ''        # ídem
    '§': ''        # ídem
    '\r': ''
    '\n': ' '      # salto de línea -> espacio, evita pegar palabras; candidato, no confirmado
  invalid_character_policy: replace
```

El backslash (`\`) del candidato histórico ("eliminar") **no aparece en el
error real** -- se mantiene como candidato de fuente separada (práctica
histórica del cliente), no se mezcla con la evidencia de la Fase 3 sin
distinguir el origen de cada regla.

## Fase 5 — Orden de transformación

```
source value
  → module mapping/transformation      (reglas ya existentes: resolve_lookup, to_historical_id, etc.)
  → text normalization                 (Unicode/espacios -- ya existe hoy: .strip() en passthrough_or_empty/nullcontrol_passthrough)
  → forbidden-character policy         (Fase 3/4 -- NUEVO, no implementado)
  → max-length policy (truncate/reject/warn)  (Fase 2/4 -- NUEVO, no implementado)
  → final field validation             (ya existe: validate_csv_structure / validate_output_csv)
  → CSV writer                         (ya existe: engine/writer.py)
```

**`truncate` DESPUÉS de `replacements`, nunca antes.** Motivo: un
`replacement` puede CAMBIAR la longitud del valor (p. ej. `\r\n` → `''`
acorta; `¤` → `'/'` no cambia longitud; en general no hay garantía de que
==). Si se truncara ANTES de aplicar replacements, el valor final podría
seguir excediendo `max_length` después de la sustitución (si un
reemplazo alarga) o quedar más corto de lo necesario (si un reemplazo
acorta un valor que ya cumplía el límite sin necesitar truncado). **Solo
truncar el valor YA normalizado garantiza que el resultado final cumple
`max_length`** -- es la única opción compatible con el objetivo explícito
del encargo ("Elegir la opción que garantice que el valor FINAL cumple
max_length").

## Fase 6 — Trazabilidad / Evidence (diseño, no implementado)

```python
@dataclass(frozen=True)
class FieldTransformationIssue:
    module: str                    # p. ej. "safety_meetings"
    object_: str                   # p. ej. "Group_Meetings"
    field: str                     # p. ej. "CS_MeetingPlace"
    historical_id: str | None      # CS_HistoricalOriginID de la fila, cuando exista -- NUNCA el valor completo del campo si es dato personal
    constraint_type: str           # "max_length" | "forbidden_character"
    original_length: int | None
    final_length: int | None
    offending_characters: tuple[str, ...]   # solo los caracteres, NUNCA el valor completo si es sensible (ver nota abajo)
    action: str                    # REPLACED | REMOVED | TRUNCATED | REJECTED | WARNING
    rule: str                      # referencia al contrato/regla que originó la acción (p. ej. "config/exports/safety_meetings.yaml#fields.CS_MeetingPlace.constraints")
```

**Datos personales:** para campos marcados `Sensitivity Level=Confidential
(Privacy)` en Field Specifications (Fase 1 -- 50/1238 campos reales), el
diseño NUNCA registra el valor completo en `offending_characters` ni en
ningún log -- solo los caracteres ofensivos aislados y las longitudes,
igual que ya hace el proyecto con otros datos (p. ej.
`build_connection_section` nunca incluye credenciales). Ningún campo de los
3 módulos actuales está marcado así hoy (verificado en Fase 8), pero el
diseño lo contempla desde el principio, no como parche posterior.

**Dónde aparecería (diseño, no implementado):**
- `validation_report.yaml`: nueva sección `field_transformations` (lista de
  `FieldTransformationIssue` serializados), agregada por `constraint_type`/
  `action` en el resumen (`counts`), igual que ya se hace con
  `lookups`/`entities`/`reference`.
- `issues.jsonl` (solo Drills hoy -- ver Sprint 9.8 Fase 5, `MODULE_SPECIFIC`):
  una entrada por fila afectada, mismo formato que las entradas ya
  existentes (`_issue()` en `drills/pipeline.py`), con
  `issue_type="field_transformation"`.
- `evidence_internal.xlsx` (Drills, `src/evidence/`): nueva fila-resumen en
  la hoja de incidencias -- **no implementado en este sprint** ("no
  implementar Evidence genérico todavía si amplía demasiado el alcance",
  instrucción explícita, y Evidence ya está identificado como
  Drills-only/hardcoded, Sprint 9.8 Fase 8).

## Fase 7 — Field Catalog: diseño

```
Raw XLSX (Enablon_Field_Specifications/Raw/, inmutable, fuera de git)
   ↓  normalizer/importer (script nuevo, léelo, nunca a mano)
config/field_catalog/<objeto>.yaml   (versionado -- ver por qué es seguro, abajo)
   ↓  + overrides de proyecto/módulo
config/exports/<módulo>.yaml         (ya existe -- fields[].constraints, nuevo)
   ↓
Effective Field Contract              (resultado en memoria por ejecución -- no persiste como fichero nuevo)
```

**Por qué el catálogo derivado SÍ puede versionarse (a diferencia de
`Raw/`):** Field Specifications es METADATA de configuración de Enablon
(nombres de campo, tipos, límites de longitud, reglas de obligatoriedad) --
no contiene ningún dato de cliente (sin filas de `ITP_*`, sin nombres de
empleados, sin valores reales migrados). Es estructuralmente equivalente a
`config/modules.yaml`/`config/databases.yaml`, ya versionados. `Raw/`
permanece fuera de git (mismo criterio que todo `inputs/`/`Catalogs/`) por
ser un artefacto externo grande y regenerable desde Enablon, no por
sensibilidad de contenido.

**Schema mínimo, usando SOLO columnas reales confirmadas en Fase 1** (nada
teórico/sobredimensionado):

```yaml
# config/field_catalog/group_meetings.yaml (ejemplo conceptual)
object: Group_Meetings
source: Catalogs/Enablon_Field_Specifications/Raw/Export_Spec_Stand30.xls.xlsx
fields:
  CS_HistoricalOriginID:
    type: Text
    max_length: 40
    mandatory: never          # de "Mandatory" real
    read_only: false          # de "Input" != "Never"
    virtual: false             # de "Virtual"
    exportable: always         # de "Export"
    importable: always         # de "Import"
    reference: null            # solo si Type es MultiLink/Link
    sensitivity: null          # solo si != "N/A"
  CS_Level:
    type: "Link (Meetings Levels)"
    max_length: null           # Size Max=0 -- sin límite declarado por Enablon
    mandatory: edit_add
    read_only: false
    virtual: false
    exportable: if_visible
    importable: if_editable
    reference: "Meetings Levels"
    sensitivity: null
```

**Separación conceptual, tres niveles** (pedida explícitamente):
1. **Enablon standard fields** -- campos de plataforma sin prefijo `CS_`
   (`Reference`, `StartDate`, `Duration`...) -- mismo significado en
   cualquier proyecto Enablon.
2. **Moeve `CS_*` custom fields** -- 372/1238 campos reales (Fase 1,
   Sprint 9.9.1), específicos de la configuración de este cliente.
3. **Project-specific migration policy** -- `constraints.replacements`/
   `invalid_character_policy`/overrides de Fase 3/4 -- NUNCA en el catálogo
   derivado del XLSX (nivel 1/2), siempre en `config/exports/<módulo>.yaml`
   (nivel 3, ya existente) -- evita que una decisión de proyecto contamine
   el catálogo que debería poder regenerarse limpio desde Enablon en
   cualquier momento.

## Fase 8 — Validación contra los 3 módulos (sin cambiar mappings)

Cruzados los `target` reales de `config/exports/{drills,bypass,safety_meetings}.yaml`
contra las hojas `Drills` y `Group Meetings` del XLSX real (Bypass no tiene
hoja propia -- ver Sprint 9.9.1 Fase 7).

### Drills (hoja `Drills`) -- 8/8 ENCONTRADOS

| Campo EMF | Type real | Size Max | Mandatory | Import |
|---|---|---|---|---|
| `CS_Typology` | `Link(Scenario Types)` | 0 (sin límite) | Edit/Add | If Editable |
| `Reference` | `Text` | **40** | Edit/Add | If Editable |
| `StartingDate` | `Date` | 0 | Add | If Editable |
| `CS_HistoricalOriginID` | `Text` | **40** | Never | Always |
| `CS_Letter` | `CCL: A/B/C/D/E/F/J.O.` | 0 | Edit/Add | If Editable |
| `CS_ImpactedEntities` | `MultiLink(First Axis)` | 0 | Edit/Add | If Editable |
| `CS_WorkflowStatus` | `CCL: Draft/Pending validation/Validated` | 0 | Edit/Add | Always |
| `CS_HistoricalDataOrigin` | `Text` | **70** | Never | Always |

`CS_*` encontrados: 6/8 (`CS_Typology`, `CS_HistoricalOriginID`, `CS_Letter`,
`CS_ImpactedEntities`, `CS_WorkflowStatus`, `CS_HistoricalDataOrigin`).
Longitud del literal real `CS_HistoricalDataOrigin`
("Prevención.ITP_SIM+ITP_SIM_ACCIONES_CORRECTORAS") = 47 caracteres, dentro
del límite de 70 -- sin riesgo confirmado.

### Bypass -- 0/7 ENCONTRADOS (sin hoja propia)

Mismo gap ya confirmado en Sprint 9.9.1 Fase 7 (sin Template ni Field Spec
propios) -- ningún campo de Bypass puede cruzarse contra evidencia real de
plataforma. `CS_*` esperados por nombre (`CS_HistoricalOriginID`,
`CS_HistoricalDataOrigin`) sin confirmación de `type`/`max_length` reales.

### Safety Meetings (hoja `Group Meetings`) -- 7/7 ENCONTRADOS

| Campo EMF | Type real | Size Max | Mandatory | Import |
|---|---|---|---|---|
| `CS_HistoricalOriginID` | `Text` | **40** | Never | Always |
| `CS_WorkflowStatus` | `CCL: Scheduled/Initiated/Validation/Completed` | 0 | Edit/Add | Always |
| `CS_Level` | `Link(Meetings Levels)` | 0 | Edit/Add | If Editable |
| `CS_Letter` | `Link(Shifts)` | 0 | Edit/Add | If Editable |
| `StartDate` | `Date` | 0 | Edit/Add | If Editable |
| `CS_MeetingPlace` | `Text` | **80** | Never | If Editable |
| `CS_HistoricalAtendee` | `Text Area` | **4096** | Never | Always |

`CS_*` encontrados: 6/7. **Hallazgo de apoyo independiente:** el `Type`
real de `CS_WorkflowStatus` es literalmente
`CCL: Scheduled/Initiated/Validation/Completed` -- coincide EXACTO con los 4
valores del `workflow_status_lookup` ya declarado en
`config/exports/safety_meetings.yaml` (Sprint 9.7), confirmando
independientemente que esa tabla está completa y correcta.

### Campos que requerirían decisión humana (no se resuelven aquí)

1. **`CS_Level`/`CS_Letter` (Safety Meetings): `Mandatory=Edit/Add`** en el
   spec real, pero el Operational real (Sprint 9.7/9.9) tiene **19/1734
   filas con ambos vacíos** -- tensión entre "declarado obligatorio" y
   "observado vacío en datos ya cargados en producción". Puede que
   `Mandatory` en Enablon se aplique solo a edición manual vía UI, no a
   import por CSV -- **no confirmado, requiere decisión humana** antes de
   convertir esto en un `reject`/`warn` de Field Constraints.
2. **`TitleEN` 240 vs 239** (Fase 2) -- qué valor usar si se implementa.
3. **Caracteres prohibidos por campo vs. por tipo** (Fase 3) -- solo hay
   evidencia real para 1 campo (`Event Title`, de un módulo que ni siquiera
   es uno de los 3 ya implementados) -- decidir si se generaliza por `Type`
   o se exige evidencia campo a campo antes de aplicar a Drills/Bypass/SM.

## Fase 9 — Diseño de tests futuros (no implementados -- el motor no existe todavía)

1. `max_length` específico por campo (p. ej. `Reference`=40 vs
   `CS_MeetingPlace`=80 -- confirmar que NO se comparten).
2. Dos campos con `max_length` diferente en el MISMO módulo no se
   contaminan entre sí.
3. Texto dentro del límite -- passthrough sin cambios.
4. Texto EXACTAMENTE en el límite -- passthrough sin cambios (no
   truncar de más).
5. Texto sobre el límite -- se trunca a `max_length` exacto.
6. `"` → `'` (candidato histórico, solo si el campo lo declara).
7. `\` → eliminar (candidato histórico, solo si el campo lo declara).
8. `|` → replacement configurable (evidencia real de carácter prohibido).
9. CR/LF → tratamiento declarado (evidencia real).
10. Unicode válido NO tocado: `"Prevención"`, `"ñoño"`, `"维护会议"` (CJK) --
    passthrough completo, ninguno de estos aparece en la lista real de
    prohibidos.
11. Carácter prohibido SIN `replacement` declarado → `reject`/`warn` según
    `invalid_character_policy` (nunca eliminado en silencio por defecto).
12. Un `replacement` que ALARGA el valor -- confirmar que el truncado
    posterior (Fase 5) sigue garantizando `max_length` final.
13. `truncate` ocurre DESPUÉS de `replacements`, nunca antes (test de
    orden, no solo de resultado).
14. Reglas de un campo NO se aplican a otro campo del mismo módulo (ni de
    otro módulo) -- aislamiento por `field`+`module`.
15. Un campo `CS_*` con constraint propio (p. ej. `CS_MeetingPlace`
    max_length=80) coexiste con un campo estándar sin prefijo con su
    propio límite (p. ej. `Reference`=40) sin interferencia.

---

# PUERTA — 21 PUNTOS

1. **Commit de 9.9.1:** `a8ba2aa6dbc4f2971c944ee301f6c78a04df834b`.
2. **Suite después del commit:** `860 passed, 7 skipped`.
3. **Schema real en Field Specifications:** XLSX, cabecera en fila 13
   (columnas `O`=XML Info/código real, `P`=Type, `Q`=Size Max, `AG`=Mandatory,
   `AE`=Input, `S`=Virtual, `AK`/`AL`=Export/Import, `AP`/`AQ`=Sensitivity/Privacy),
   datos desde fila 14, 20 hojas de objeto real.
4. **Número de campos:** 1238 filas de campo totales, 372 (30%) `CS_*`.
5. **Evidencia real de `max_length`:** confirmado field-specific --
   `Reference`=40, `CS_HistoricalDataOrigin`=70, `TitleEN`=240,
   `CS_MeetingPlace`=80, `CS_HistoricalAtendee`=4096 -- 5 valores distintos
   en campos de texto reales, ninguno compartido por defecto.
6. **`TitleEN` 240 vs `Parametro` 239:** sin motor visible en el ETL, 2
   hipótesis registradas (margen de seguridad de 1 carácter / parámetros no
   relacionados), **ninguna confirmada** -- decisión de implementación
   pospuesta a revisión humana explícita.
7. **Diseño Field Constraint:** `constraints: {max_length, forbidden_characters,
   replacements, invalid_character_policy}`, declarado por campo, nunca
   global.
8. **Diseño forbidden characters:** 3 capas -- A) Platform/Field Constraint
   (qué prohíbe Enablon de verdad, evidencia real: `"¤¦|§` + CR/LF), B)
   Project Normalization Policy (`reject`/`replace`/`remove`/`warn`), C)
   Field-specific override.
9. **Separación constraint vs policy:** constraint = hecho de Enablon
   (Field Specifications o error real observado); policy = decisión de
   proyecto sobre qué hacer -- nunca mezcladas en el mismo nivel del
   esquema.
10. **Orden final de transformación:** mapping → text normalization →
    forbidden-character policy → max-length policy → final validation →
    CSV writer. `truncate` SIEMPRE después de `replacements`.
11. **Diseño de trazabilidad:** `FieldTransformationIssue`
    (module/object/field/historical_id/constraint_type/original_length/
    final_length/offending_characters/action/rule), sin volcar el valor
    completo de campos `Confidential (Privacy)`. Superficies previstas:
    `validation_report.yaml` (nueva sección), `issues.jsonl` (solo Drills
    hoy), `evidence_internal.xlsx` (NO implementado -- fuera de alcance
    explícito de este sprint).
12. **Diseño del Field Catalog:** `Raw XLSX` (inmutable) → normalizer/importer
    → `config/field_catalog/<objeto>.yaml` (versionable, sin datos de
    cliente) → overrides en `config/exports/<módulo>.yaml` (ya existente) →
    Effective Field Contract en memoria. Separación Enablon standard / `CS_*`
    Moeve / project policy en 3 niveles distintos de fichero.
13. **Cobertura Drills:** 8/8 campos encontrados con evidencia real
    (`type`/`max_length`/`mandatory`/`import`).
14. **Cobertura Bypass:** 0/7 -- sin hoja propia en Field Specifications
    (mismo gap ya confirmado para Templates, Sprint 9.9.1).
15. **Cobertura Safety Meetings:** 7/7 encontrados; `CS_WorkflowStatus`
    confirma independientemente el `workflow_status_lookup` ya declarado
    (Sprint 9.7).
16. **Gaps/unresolved:** Bypass sin evidencia de plataforma alguna;
    `CS_Level`/`CS_Letter` (SM) `Mandatory=Edit/Add` vs. 19 filas reales
    vacías (tensión sin resolver); `TitleEN` 240 vs 239 sin confirmar;
    lista de caracteres prohibidos confirmada solo para 1 campo de 1 módulo
    no implementado (`Event Title`).
17. **Qué implementar ahora / posponer:** **nada de Field Constraints se
    implementa en este sprint** (instrucción explícita) -- todo el
    contenido de este informe es diseño. Lo único "implementado" es el
    propio documento y la evidencia registrada.
18. **Archivos modificados:** ninguno de código -- solo los 2 ficheros de
    este informe (`.md`/`.txt`), nuevos.
19. **Commit adicional propuesto:**
    `docs(field-constraints): register Field Specifications evidence and normalization design`
    (solo estos 2 ficheros -- no hay cambio de código que commitear).
20. **Suite final:** sin cambios -- `860 passed, 7 skipped` (no se tocó
    ningún fichero de `src/`/`tests/`).
21. **Confirmaciones:** 0 SQL real, 0 `full`, 0 push, `Raw/` intacto (solo
    lectura), ningún dato real versionado (los ejemplos del documento son
    literales sintéticos o ya públicos en `config/exports/*.yaml`/CLAUDE.md).

**DETENIDO. No se ejecuta el sample SQL de Safety Meetings sin autorización
explícita adicional.**
