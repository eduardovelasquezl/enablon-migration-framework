# Micro-sprint 9.9.1 — Enablon CSV Output Contract

**Objetivo:** determinar con evidencia el CSV Output Contract real de Enablon
y corregir, una sola vez en el Export Engine, el hallazgo transversal de
mojibake detectado antes del primer sample real de Safety Meetings (Sprint
9.9, todavía sin autorizar). Ningún SQL real ejecutado.

---

## Fase 0 — Preflight

- **HEAD:** `3ddbb0bb96b2f355794c9750a2e38a27bbd86e0f` — confirmado.
- **Suite antes de empezar:** `844 passed, 7 skipped`.
- **Sprint 9.9:** sin cambios funcionales pendientes (solo los 2 informes de
  puerta de seguridad, sin código).
- Sin SQL real, sin `full`, sin push en ningún momento de este micro-sprint.

## Fase 1 — Inspección byte-level de artefactos reales

Inspeccionados, a nivel de bytes (nunca inferido desde cómo Excel los
muestra):

**`CSV_Enablon_Template/` (Platform Contract — 15 ficheros, todos los
módulos con Template disponible):**

| Dialecto | Encoding | BOM | Delimiter | Quoting | Line ending | Ficheros (9) |
|---|---|---|---|---|---|---|
| "Padre" | UTF-16LE | `\xff\xfe` | TAB (`\t`) | Todo entre `"..."`, `""` interno para escapar | CRLF | `Drills-34.csv`, `Change Register-17.csv`, `Group Meetings-40.csv`, `Events-4.csv`, `Impacts-9.csv`, `Inspections-51.csv`, `Investigations-11.csv`, `List of Activities-38.csv`, `Observations-60.csv` |
| "Hijo"/detalle | Latin-1/Windows-1252 (un byte) | Ninguno | `;` | Todo entre `"..."` | CRLF | `Causes Data-64_PSM Cheklist.csv`, `Checklists Data-24_Change Register.csv`, `Impact Injuries-26.csv`, `Inspection Data-58.csv`, `PSM forms-13.csv`, `Update External Meeting Participations-42.csv` |

Ambos dialectos son **auto-descriptivos** (BOM propio, o un solo byte sin
ambigüedad de interpretación) — **ningún artefacto real de Enablon usa UTF-8
sin BOM**. Este hallazgo NO es nuevo: coincide, carácter a carácter en su
clasificación, con uno ya registrado en Sprint 8.2
(`docs/specifications/v1.0/export/evidence_inventory.md` §3, sobre un
conjunto de 17 CSV distinto — mismos 6 ficheros "hijo" identificados de forma
independiente). Ese informe ya advertía: son `validated_output_csv`
(evidencia fiable de forma/encoding), **no** `enablon_template` confirmado
como contrato de importación (`template_status: candidate`, nunca
`validated`) — matiz que se respeta en la Fase 2.

**`CSV_Enablon_Operational/` (Project Contract, 4 ficheros comparados):**

| Fichero | Encoding | BOM | Delimiter |
|---|---|---|---|
| `By pass new .bak.csv` | UTF-8 | No | `;` |
| `Reuniones de grupo import completo.csv` | UTF-8 | **Sí** | `;` |
| `Events-05082026-30.csv` | UTF-8/ASCII | No | `;` |
| `Inspections-04082026-222.csv` | UTF-8 | **Sí** | `;` |

2 de 4 ya usan BOM UTF-8 por su cuenta — UTF-8+BOM SÍ tiene precedente real
en este ecosistema; UTF-8 sin BOM no lo tiene en ningún artefacto inspeccionado.

**EMF (antes de este micro-sprint):** UTF-8, sin BOM, TAB, `quoting=minimal`,
CRLF — coincide con el dialecto "padre" en encoding-family y delimiter, pero
es el ÚNICO perfil de todos los inspeccionados (Enablon real + EMF) que
combina UTF-8 con ausencia de BOM.

### Causa exacta del mojibake

Reportado: `PrevenciÃ³n.ITP_BES` en vez de `Prevención.ITP_BES`
(`CS_HistoricalDataOrigin`, Bypass). Verificado byte a byte, en dos puntos
independientes:

```
config/exports/bypass.yaml (fuente, ya en git):  ...Prevenci\xc3\xb3n.ITP_BES"...
outputs/prototype/bypass/20260814T061625Z/bypass.csv (generado, sample real Sprint 9.5):
                                                  ...Prevenci\xc3\xb3n.ITP_BES\r\n...
```

`\xc3\xb3` es la codificación UTF-8 CORRECTA de "ó". **EMF ya escribía bytes
UTF-8 correctos, en ambos puntos del pipeline.** El mojibake nace al ABRIR ese
fichero (sin BOM, UTF-8) con una herramienta que no autodetecta UTF-8 y cae
por defecto a Windows-1252/Latin-1 — `\xc3`→`Ã`, `\xb3`→`³` es exactamente el
patrón clásico de "UTF-8 leído como Latin-1".

**Clasificación: B — bytes UTF-8 correctos, interpretados con encoding
incorrecto al abrir.** No A (no hay bug de escritura), no C (el valor fuente
en `bypass.yaml` ya es UTF-8 válido, no venía corrupto), no D.

## Fase 2 — Output Contract

```yaml
csv_output:
  encoding: utf-8       # sin cambios
  bom: true              # CORREGIDO (antes: false)
  delimiter: "\t"        # sin cambios
  quoting: minimal       # sin cambios
  line_ending: "\r\n"    # sin cambios
```

**ENABLON/PLATFORM confirmado:** ningún artefacto real de Enablon usa UTF-8
sin BOM; los dos dialectos reales observados son ambos auto-descriptivos.

**MOEVE/project-specific:** 2 de 4 Operational reales ya usan UTF-8+BOM por
iniciativa propia (no impuesto por EMF).

**Todavía desconocido / NO concluyente** (no se implementa sin evidencia
`validated`, mismo estándar que Sprint 8.2): si Enablon EXIGE en importación
el dialecto UTF-16LE+TAB+quoting-total del Template "padre", o si acepta
UTF-8. El propio informe de Sprint 8.2 ya clasificó los CSV de Bloque4 como
`candidate`, nunca `validated`, para ese propósito — este micro-sprint no
tiene evidencia nueva que cambie esa clasificación. Tampoco hay evidencia de
que `quoting=all` sea EXIGIDO (ninguna columna actual de los 3 módulos
contiene el delimitador salvo texto libre, ya fuera de alcance).

**Por qué NO se cambia a UTF-16LE ni a Latin-1:** `NameZH` (Drills, Field
Specifications real, Fase 7) y el fan-out `cloneorigin` a 5 idiomas incluido
ZH (CLAUDE.md) confirman que el fan-out de PSM/otros necesita CJK completo —
Latin-1 (dialecto "hijo") es arquitectónicamente incompatible con eso, sin
posibilidad de reconsiderarlo. UTF-16LE sí soporta CJK, pero cambiarlo sin
evidencia `validated` de que Enablon lo exige sería una migración de mucho
mayor riesgo que la corrección mínima y concluyente (BOM) que sí resuelve el
mojibake demostrado.

## Fase 3 — Revisión del Engine

`src/export/engine/writer.py::write_csv` ya era, desde Sprint 9.6/9.8, el
ÚNICO punto de escritura de CSV para los 3 módulos (confirmado por identidad
de objeto, no solo por comportamiento — test de Sprint 9.8). **No estaba
hardcodeado** — el formato venía siempre de `OutputSpec`, cargado desde
`config/exports/<módulo>.yaml`.

**Hallazgo propio de esta fase, no de Sprint 9.8:** `write_csv` SÍ resolvía
`bom`+`encoding` correctamente (`-sig` inline), pero
`engine/validator.py::validate_csv_structure` (el validador que confirma que
el CSV recién escrito es reabrible y con la cabecera esperada) decodificaba
con `output_spec.encoding` A SECAS, ignorando `output_spec.bom` por
completo. Mientras los 3 módulos declaraban `bom=false` esto no tenía efecto
observable — en cuanto se corrige `bom=true` (Fase 4), `validate_csv_structure`
habría dejado `U+FEFF` colgando del primer valor de cabecera y roto la
comparación `header != expected_columns` en **los 3 módulos**, en cada
ejecución. Verificado empíricamente antes de tocar ningún YAML
(`raw_bytes.decode("utf-8")` sobre un fichero con BOM real deja
`'﻿CS_Typology'`; `decode("utf-8-sig")` deja `'CS_Typology'` limpio).

## Fase 4 — Implementación mínima

Cambio arquitectónico: **una única función compartida**, no una corrección
por módulo.

- `src/export/engine/writer.py`: nueva `resolve_text_encoding(output_spec)`
  -- extrae la lógica que antes vivía solo, inline, dentro de `write_csv`.
  `write_csv` la usa ahora en vez de su `if` local (comportamiento idéntico,
  cero cambio observable en esa función).
- `src/export/engine/validator.py`: `validate_csv_structure` ahora decodifica
  con `resolve_text_encoding(output_spec)` en vez de `output_spec.encoding` a
  secas -- corrige el hallazgo de la Fase 3 ANTES de que `bom=true` pudiera
  activarlo.
- `config/exports/drills.yaml` / `bypass.yaml` / `safety_meetings.yaml`:
  `output.bom: false` → `true`, con el mismo comentario de evidencia
  (drills.yaml lo desarrolla completo; bypass/safety_meetings remiten a él
  para no triplicar el texto) -- una sola decisión, documentada una vez,
  aplicada igual a los 3.

Ninguna sustitución de texto sobre datos ("PrevenciÃ³n"→"Prevención"): la
solución es enteramente de encoding/dialecto (BOM), nunca de contenido.
`delimiter`/`quoting`/`encoding`-family **sin cambios** -- sin evidencia
concluyente que los justifique (Fase 2).

## Fase 5 — Tests

17 tests nuevos en `tests/test_export_engine.py` (sección "Output Contract"):
`resolve_text_encoding` (3: bom+utf8→sig, bom=false→sin cambio, bom+encoding
no-utf8→sin cambio), BOM presente/ausente en bytes reales (2), Unicode
parametrizado -- 5 casos: `"Prevención.ITP_BES"` (el caso real reportado),
`"Servicio Prevención LA RÁBIDA"`, `"año, ñoño, José"`, `"维护会议"` (CJK),
`"Café — SGA/Niño"` -- delimitador dentro de un valor (queda citado),
comillas dentro de un valor (`""` doblado, RFC4180), vacío/null (cadena
vacía, nunca literal `None`/`NULL`), line endings CRLF, `validate_csv_structure`
con BOM sin `U+FEFF` colgando (reproduce y cierra el hallazgo de la Fase 3),
y una confirmación explícita de que los 3 módulos declaran el MISMO Output
Contract (no 3 decisiones divergentes).

## Fase 6 — Regresión

3 tests existentes SÍ fallaron al activar `bom=true` -- exactamente el caso
que el encargo anticipaba ("golden tests congelando el formato antiguo
incorrecto"): `test_bypass_pipeline.py`,
`test_drills_core_pipeline.py`, `test_safety_meetings_pipeline.py` leían el
CSV recién escrito con `read_text(encoding="utf-8")` a secas. **No se revirtió
el fix para mantenerlos verdes** -- se corrigieron para decodificar con
`"utf-8-sig"` (mismo criterio que el propio Output Contract), con comentario
explícito de por qué. Un cuarto call site sin cobertura en la suite por
defecto (`test_drills_export_integration.py`, gateado tras SQL real) se
corrigió igual, por consistencia, aunque no había fallado en este run.

**Impacto por módulo:**
- **Drills:** CSV ahora con BOM UTF-8 -- 1 test de pipeline corregido.
- **Bypass:** CSV ahora con BOM UTF-8 -- 1 test de pipeline corregido; el
  mojibake reportado queda resuelto en la próxima ejecución.
- **Safety Meetings:** CSV ahora con BOM UTF-8 -- 1 test de pipeline
  corregido; afecta directamente al sample real de Sprint 9.9, todavía sin
  autorizar (se generará ya con el contrato corregido).

**Suite final: `860 passed, 7 skipped`** (844 + 16 tests nuevos netos),
**cero regresiones reales** (los 3 fallos transitorios eran el propio
contrato cambiando de forma esperada, ya corregidos).

## Fase 7 — Field Specifications: inventario

**Fichero:** `Catalogs/Enablon_Field_Specifications/Raw/Export_Spec_Stand30.xls.xlsx`
(no modificado, no normalizado -- solo inspeccionado en modo lectura).

- **Formato:** XLSX, 25 hojas.
- **Estructura:** 1 hoja `Page Resume` (matriz de permisos/roles por objeto
  -- no es field-level), 4 hojas `Recuperado_HojaN` (artefactos de
  recuperación de Excel, prácticamente vacías -- solo restos de una hoja de
  filtro/informe distinta, sin datos de campo), y **20 hojas de objeto real**
  (`Drills`, `Group Meetings`, `Meeting External Participations`, `Events`,
  `Impacts`, `Impact Injuries`, `Investigations`, `PSM forms`, 3 variantes de
  `Action Plans` aliadas desde distintos módulos padre (`ims`/`AP`/`zB` --
  `zB` = alias desde By-Passes), `Inspections(acs)`, `Checklists(acs)`,
  `Observations`, `Inspection Data`, `Change Register`, `Checklists(MC)`,
  `Data Answers`, `Teams`).
- **Cada hoja de objeto:** cabecera real en la fila 13 (`Short Name`/
  `Long Name`/`On Line Help`/**`XML Info`** [= código de campo real, p. ej.
  `CS_HistoricalOriginID`]/**`Type`**/**`Size Max`**/`Virtual`/...
  /**`Mandatory`**/`Search`/**`Export`**/**`Import`**/`Sensitivity Level`/
  `Privacy Notice`...), datos desde la fila 14. Las filas 1-2 de cada hoja
  son un resto de una hoja de filtro/informe SIN relación con los datos de
  campo (códigos `F11`...`F503`) -- no forman parte del catálogo real.
- **Número aproximado de registros:** **1238 filas de campo** en total sobre
  las 20 hojas de objeto, de las cuales **372 (30%) son campos `CS_*`**
  (custom fields del cliente). Por objeto (ejemplos): Drills 46 campos/25
  `CS_*`; Group Meetings 64/28; Change Register 166/93; Events 150/57.
- **Metadatos que aporta, confirmados por lectura directa:** `Type` (`Text`,
  `Date`, `Currency`, `Float`, `Text Area`, `MultiLink(<objeto>)`,
  `Link(<catálogo>)`, listas `CCL: valor1/valor2/...`), **`Size Max`**
  (longitud máxima real, entero), **`Mandatory`** (`Never`/`Add`/`Edit/Add`),
  `Input`/`Visible if not editable` (editabilidad), **`Export`**/**`Import`**
  (`Always`/`If Visible`/`If Editable`/`Never` -- indica si un campo participa
  realmente en importación), `Sensitivity Level`/`Privacy Notice`
  (`Confidential (Privacy)` marca campos con datos personales), y
  `Type=MultiLink(...)`/`Link(...)` que apunta al catálogo/objeto referenciado
  (equivalente a una FK declarada).
- **Bypass no tiene hoja propia** -- mismo patrón ya visto en
  `CSV_Enablon_Template/` (sin fichero Template para By_Passes): solo
  aparece indirectamente vía `Action Plans(zB)` (Action Plans aliado desde
  By-Passes), nunca como objeto propio con sus 7+ columnas reales.

**Ejemplo concreto de por qué esto importa (no implementado, solo observado):**
`TitleEN` en la hoja `Group Meetings`: `Type=Text`, **`Size Max=240`**. El
candidato de Sprint 9.8 (`config/exports/safety_meetings.yaml`,
`Parametro=239` de la hoja `Title_map` del ETL, "podría ser un `max_length`,
no confirmado") queda ahora **fuertemente respaldado** por una fuente
independiente y autoritativa (240 vs 239 -- diferencia de 1, consistente con
un margen de seguridad o un índice base distinto en el ETL original). Se
registra como hallazgo, **no se implementa** ningún `constraints.max_length`
a partir de él en este micro-sprint.

**Propuesta de Field Catalog gobernado (diseño, no implementado):** un
fichero derivado versionado (`config/field_catalog/<objeto>.yaml`, generado
por un script de lectura de este XLSX, nunca a mano) con, por campo:
`code` (columna `XML Info`), `type`, `max_length` (columna `Size Max`, 0 =
sin límite declarado), `mandatory`, `exportable`/`importable` (booleanos
derivados de `Export`/`Import`), `reference` (objeto/catálogo si `Type` es
`MultiLink`/`Link`), `sensitivity` (si no es `N/A`). El XLSX `Raw/` queda
como fuente de verdad inmutable; el YAML derivado es lo que
`FieldSpec.constraints` (diseño ya existente desde Sprint 9.6, sin
implementar) consumiría en un sprint futuro.

## Fase 8 — Action Plans: decisión arquitectónica registrada

**Regla de rollout confirmada** (documentada aquí, no implementada):

1. Cargar primero los módulos padre (Drills, Bypass, Safety Meetings, MOC,
   Events...).
2. Enablon asigna IDs definitivos (el `Id` que ve el usuario, distinto del
   `CS_HistoricalOriginID` de origen -- ver
   `docs/01-architecture/action-plans-native-design.md` §"Display/reference
   identifier").
3. Exportar desde Enablon Historical ID + Enablon ID (par de identificadores
   por cada registro ya cargado).
4. Construir un Reference Crosswalk (diseño abajo).
5. Resolver las relaciones de Action Plans contra ese crosswalk.
6. Generar/cargar Action Plans al final -- nunca antes que sus padres.

**Diseño conceptual del crosswalk** (no implementado):

```
source_system        # p. ej. "prevencion" / "gct"
source_object_type    # p. ej. "drills" / "bypass" / "safety_meetings"
historical_id          # CS_HistoricalOriginID de origen
enablon_id              # Id asignado por Enablon tras la carga
reference               # Reference/clave funcional, cuando exista (Drills la tiene, Bypass/SM no)
project                  # p. ej. "moeve" -- nunca cruzar crosswalks entre proyectos
load_execution_id         # qué ejecución de carga produjo esta fila -- trazabilidad
```

No depende únicamente del ID numérico -- `historical_id` por sí solo puede
colisionar entre `source_system`/`source_object_type` distintos (ver
CLAUDE.md: `IDCentro` de ITP y de GCT son numeraciones incompatibles; el
mismo riesgo aplica a IDs de registro, no solo de centro). La clave de
resolución es la tupla completa, nunca `historical_id` aislado.

**Estados mínimos de resolución:**
- `RESOLVED` -- exactamente un `enablon_id` para la tupla
  `(source_system, source_object_type, historical_id, project)`.
- `UNRESOLVED` -- ningún `enablon_id` encontrado todavía (el padre no se ha
  cargado, o la carga no generó una fila de export reconocible).
- `AMBIGUOUS` -- más de un `enablon_id` candidato para la misma tupla (nunca
  se elige uno de forma silenciosa -- mismo principio ya aplicado en
  `EntityCatalog.conflicting_keys`, Sprint 9.8 Fase 4).

No se implementa Action Plans en este micro-sprint. Este diseño quede
registrado para cuando se retome (Sprint 9.8 lo dejó como opción E, no
priorizada frente a A).

---

# PUERTA — 16 PUNTOS

1. **Formato real encontrado en CSV Enablon:** dos dialectos auto-descriptivos
   (UTF-16LE+BOM+TAB+quote-all para objetos "padre"; Latin-1+`;`+quote-all
   para objetos "hijo"/detalle) -- ninguno usa UTF-8 sin BOM.
2. **Formato anterior del EMF:** UTF-8, sin BOM, TAB, quoting minimal, CRLF.
3. **Causa exacta del mojibake:** B -- bytes UTF-8 ya correctos (verificado
   byte a byte en config y en el CSV real generado), mal interpretados al
   abrir sin BOM.
4. **Cambio realizado:** `output.bom: false→true` en los 3 `config/exports/*.yaml`
   (misma decisión, documentada una vez); `resolve_text_encoding` extraída a
   `engine/writer.py` y reutilizada también por `engine/validator.py`
   (hallazgo propio: el validador ignoraba `bom` antes de este fix).
5. **Pruebas Unicode:** 5 casos parametrizados (acentos, ñ, CJK, em-dash) +
   delimitador/comillas embebidas/vacío/CRLF -- 17 tests nuevos.
6. **Impacto en Drills:** CSV con BOM UTF-8 desde la próxima ejecución; 1
   test de pipeline corregido (no relajado).
7. **Impacto en Bypass:** ídem; resuelve directamente el mojibake reportado.
8. **Impacto en Safety Meetings:** ídem; el sample real de Sprint 9.9 (sin
   autorizar todavía) se generará ya con el contrato corregido.
9. **Suite final:** `860 passed, 7 skipped`, cero regresiones reales.
10. **Inventario Field Specifications:** XLSX, 25 hojas, 20 de objeto real +
    1 resumen de permisos + 4 de recuperación casi vacías; ~1238 filas de
    campo, cabecera real en fila 13, datos desde fila 14.
11. **Presencia de `CS_*`:** sí -- 372/1238 (30%) de las filas son campos
    `CS_*`.
12. **Propuesta de Field Catalog:** YAML derivado versionado por objeto
    (`code`/`type`/`max_length`/`mandatory`/`exportable`/`importable`/
    `reference`/`sensitivity`), generado por script desde el XLSX (nunca a
    mano); el XLSX `Raw/` permanece intacto como fuente de verdad. No
    implementado.
13. **Decisión Action Plans registrada:** regla de rollout de 6 pasos +
    diseño conceptual de Reference Crosswalk (7 campos) + 3 estados
    (`RESOLVED`/`UNRESOLVED`/`AMBIGUOUS`). No implementado.
14. **Archivos modificados:** `src/export/engine/writer.py`,
    `src/export/engine/validator.py`, `config/exports/{drills,bypass,safety_meetings}.yaml`,
    `tests/test_export_engine.py`, `tests/test_bypass_pipeline.py`,
    `tests/test_drills_core_pipeline.py`, `tests/test_safety_meetings_pipeline.py`,
    `tests/test_drills_export_integration.py`. `src/core/` sin cambios.
15. **Commit propuesto, SIN ejecutar:**
    `fix(export): correct CSV Output Contract (UTF-8 BOM) across all modules`.
16. **Confirmaciones:**
    - 0 SQL real ejecutado.
    - 0 `full`.
    - 0 push.
    - `Raw/Export_Spec_Stand30.xls.xlsx` intacto -- solo lectura, ni modificado ni normalizado.
    - Ningún dato real (cliente, Operational, ETL, workspace.yaml real)
      versionado -- todos los ejemplos Unicode de los tests son literales
      sintéticos/públicos ("Prevención.ITP_BES" ya vive en
      `config/exports/bypass.yaml`, committeado desde Sprint 9.4).

**DETENIDO. No se reanuda Sprint 9.9 ni se ejecuta su comando SQL sin
autorización explícita adicional.**
