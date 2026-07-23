# Evaluación de evidencia de mapping — los 9 ZIP de `Bloque2_Mappings_SQL_ENA/`

> Este documento responde a una única pregunta dejada abierta en el incremento
> anterior (`open_questions.md` OQ-GLOBAL-04): ¿qué contienen realmente los 9
> ZIP de `inputs/_incoming_claude_web/Bloque2_Mappings_SQL_ENA/`? Se
> inspeccionaron, extrajeron de forma segura y analizaron los 9 archivos
> completos. El resultado es un hallazgo estructural, no una carencia menor:
> **ninguno de los 9 ZIP contiene evidencia de mapping de campo**. Todo lo que
> contienen son copias — algunas bit a bit idénticas — de las queries SQL de
> extracción ya presentes en `sql/source_queries/`. Este documento no oculta
> ni suaviza ese resultado, tal como exige el principio "nada se especifica
> como definitivo sin evidencia" y su contraparte: tampoco se debe ocultar
> cuando la evidencia esperada resulta no existir.

## 1. Método

Cada ZIP se abrió con `zipfile` de Python (solo lectura), se verificó su
integridad (`ZipFile.testzip()`, sin errores de CRC en ninguno), se listó su
estructura interna completa, y se extrajo a una carpeta de análisis aislada
**fuera del repositorio** (directorio de scratchpad de la sesión, nunca
`inputs/` ni ninguna ruta versionada) preservando los nombres originales.
Antes de extraer, se verificó ausencia de path traversal (ninguna entrada
contiene `..`, ruta absoluta, o letra de unidad) en los 9 ZIP y en el ZIP
anidado. Cada archivo extraído se hasheó (SHA-256) y se comparó
byte a byte contra su posible equivalente en `sql/source_queries/`. Ninguno
de los 9 ZIP originales fue modificado; no se sobrescribió ninguna entrada.

## 2. Inventario de los 9 ZIP

| ZIP | Ruta | Tamaño | Nº archivos | Extensiones | Estado de apertura |
|---|---|---:|---:|---|---|
| `AP.zip` | `inputs/_incoming_claude_web/Bloque2_Mappings_SQL_ENA/AP.zip` | 1794 B | 1 | `.sql` | Abierto, íntegro |
| `bypass.zip` | ídem | 7586 B | 2 | `.sql` | Abierto, íntegro |
| `Eventos.zip` | ídem | 27661 B | 13 | `.sql` | Abierto, íntegro |
| `Inspecciones.zip` | ídem | 6882 B | 6 | `.sql` | Abierto, íntegro |
| `MOC.zip` | ídem | 33656 B | 9 | `.sql` | Abierto, íntegro |
| `OPS.zip` | ídem | 2432 B | 2 | `.sql` | Abierto, íntegro |
| `PSM.zip` | ídem | 1633 B | 2 | `.sql` | Abierto, íntegro |
| `Reunionesdegrupo.zip` | ídem | 2507 B | 3 | `.sql` | Abierto, íntegro |
| `Simulacros.zip` | ídem | 6468 B | 5 `.sql` + 1 ZIP anidado | `.sql`, `.zip` | Abierto, íntegro |

**Total: 43 archivos `.sql` de primer nivel + 1 ZIP anidado (que contiene 3
`.sql` más, ya contados también como `Reunionesdegrupo.zip`) = 46 lecturas de
archivo en total, 34 rutas `.sql` distintas si se cuenta cada ZIP de primer
nivel una vez.** Ninguna extensión distinta a `.sql`/`.zip` — no hay Excel,
CSV, TXT, YAML, JSON, imágenes ni documentos dentro de ninguno de los 9 ZIP.
Ningún archivo vacío (el más pequeño, `SM/Asistentes_SM2025.sql`, tiene
181 bytes de contenido real). Ningún archivo no relacionado con su módulo
aparente.

## 3. El hallazgo central: identidad byte a byte con `sql/source_queries/`

Se comparó el hash SHA-256 de los 34 archivos `.sql` de primer nivel contra
todos los archivos de `sql/source_queries/`. **Los 34 coinciden exactamente**
(mismo tamaño, mismo SHA-256) con un archivo ya existente en
`sql/source_queries/<módulo>/`. Ejemplos verificados:

- `AP.zip:AP/Acciones_correctoras.sql` (1626 B) == `sql/source_queries/AP/Acciones_correctoras.sql`.
- `MOC.zip:MOC/DB_MOC_CT.sql` (14069 B) == `sql/source_queries/MOC/DB_MOC_CT.sql`.
- `Reunionesdegrupo.zip:SM/SM2025.sql` (1463 B) == `sql/source_queries/SM/SM2025.sql` — nótese que la carpeta interna del ZIP se llama `SM/`, no `Reunionesdegrupo/`, ver §6.

**Conclusión directa**: `Bloque2_Mappings_SQL_ENA/` no es, pese a su nombre,
un conjunto de documentos de mapeo SQL→Enablon. Es un empaquetado ZIP
alternativo — probablemente para envío o respaldo — de las mismas 34 queries
de extracción ya analizadas y catalogadas en el incremento anterior como
`source_sql`. **No existe en ningún ZIP columna `DatoOrigen`/`DatoDestino`,
`EsCondicion`/`ReglaEspecial`/`Parametro`, ni ninguna referencia textual a
`Enablon` o a un campo `CS_*`** — se buscó explícitamente (`grep`
case-insensitive) sobre los 46 archivos extraídos y no se encontró ninguna
coincidencia. Este es exactamente el caso que las instrucciones de este
incremento advierten explícitamente: el nombre del ZIP no demuestra su
contenido.

## 4. Excepción real: el ZIP anidado en `Simulacros.zip`

`Simulacros.zip` contiene, además de sus 5 `.sql` esperados, una entrada
`SM.zip` (2507 bytes) — un ZIP completo anidado. Se extrajo de forma aislada
(sin escribirlo directamente al disco del repo) y se comparó byte a byte
contra `Reunionesdegrupo.zip`: **son idénticos, SHA-256 completo
coincidente** (`43e48cd4...d3e248c`), no solo su contenido interno sino el
propio contenedor ZIP completo. Es decir, alguien empaquetó una copia
completa de `Reunionesdegrupo.zip` (el ZIP de Safety Meetings) dentro de
`Simulacros.zip`. Metadato adicional que refuerza que se trata de un
empaquetado accidental y no deliberado: `Simulacros.zip` tiene fecha de
modificación un día posterior (`2026-07-22`) a la de los otros 8 ZIP
(`2026-07-21`), incluido `Reunionesdegrupo.zip` — es decir, `Simulacros.zip`
fue reempaquetado después de los demás, y en ese reempaquetado se incluyó
por error una copia completa de otro ZIP. Esto se documenta como
**conflicto de packaging**, no se corrige ni se elimina la entrada anidada —
ver `open_questions.md`.

## 5. Incidencias de codificación y nombres

Dos entradas de `Eventos.zip` tienen nombre con acento (`Ó`):

- `Eventos/SQLQuery- LOCALIZACION  DE LESIÓN ANTIGUOS.sql`
- `Eventos/SQLQuery- LOCALIZACION + TIPO DE LESIÓN ANTIGUOS.sql`

Dentro del ZIP, el bit de flag EFS (UTF-8) está activado (`flag_bits=2056`,
bit 11 activo) y el nombre decodifica correctamente como UTF-8 a `Ó`
(U+00D3, bytes `\xc3\x93`) — **sin mojibake**. Al comparar contra el archivo
homónimo que ya existe suelto en `sql/source_queries/Eventos/`, ese archivo
en disco tiene el mismo contenido (mismo SHA-256) pero un **nombre
distinto**: contiene los caracteres reales U+251C U+00F4 (`├ô`), es decir,
mojibake genuino ya presente en el nombre de archivo en disco (confirmado
leyendo los bytes del nombre con Python, no es un artefacto de terminal).

**Esto es una distinción importante y nueva**: el mojibake que
`CLAUDE.md` documenta para este archivo (`"LESI├ôN"`) **no está en el ZIP** —
está únicamente en la copia suelta de `sql/source_queries/Eventos/`. El ZIP
conserva el nombre correcto. Esto sugiere que la corrupción del nombre
ocurrió en algún paso posterior a la creación de este ZIP (al copiar,
descomprimir con una herramienta que asumió otra codificación, o al subir el
archivo a este repositorio) — no es un defecto del origen. No se ha
modificado el archivo en `sql/source_queries/` en este incremento; esta
observación queda registrada como hallazgo, no como corrección aplicada.

No se detectó ninguna otra incidencia de normalización NFC (`unicodedata.normalize('NFC', ...)`
no cambió ningún nombre de archivo de los 46 extraídos) ni ningún otro caso
de mojibake dentro de los propios ZIP.

## 6. Inconsistencia de nombres confirmada

`Reunionesdegrupo.zip` empaqueta sus archivos bajo la carpeta interna `SM/`,
no `Reunionesdegrupo/` ni `safety_meetings/` — el mismo slug `SM` que usa
`sql/source_queries/SM/`. Esto es un dato adicional (no resolutivo) para
`open_questions.md` OQ-GLOBAL-03 (naming `safety_meetings` vs
`reuniones_de_grupo`): ni el ZIP ni la carpeta de queries usan
"reuniones_de_grupo" como identificador interno — solo el nombre del propio
archivo ZIP y el ETL Excel lo usan. El identificador técnico interno
consistente en SQL es `SM`.

## 7. Clasificación de mappings encontrados

**Cero.** No se identificó ningún mapping de campo (`mapping_scope: field`),
de entidad (`mapping_scope: entity`) ni de relación
(`mapping_scope: relationship`) en ninguno de los 46 archivos extraídos. Cada
archivo es una query T-SQL de extracción (`SELECT ... FROM ... [JOIN ...]`),
ya catalogada como `source_sql` en el incremento anterior. Ningún archivo
contiene una tabla de traducción `origen → destino`, ni una referencia a un
campo Enablon (`CS_*`, `FirstAxis`, etc.), ni un valor por defecto o
fallback documentado como tal.

Por indicación explícita de la Tarea 4 ("No inventes decisiones que el
documento no contenga"), **no se han creado entradas de mapping ficticias**.
`evidence/mapping_catalog.yaml` (Tarea 8) registra, en su lugar, una entrada
por ZIP que documenta explícitamente esta ausencia, con
`mapping_scope: unknown`, `decision_type: unknown`, `mapping_status: unknown`
y `evidence_status: validated` (validado que el archivo **no** es un
documento de mapping, no que sí lo sea).

## 8. Consecuencia sobre `mapping_status` en la matriz de preparación

En el incremento anterior, `mapping_status: partial` se asignó a la mayoría
de los objetos basándose en que su ZIP correspondiente en Bloque2 **existía
pero no se había abierto** — es decir, se daba el beneficio de la duda. Con
esta apertura, esa duda queda resuelta **en sentido negativo**: los ZIP de
Bloque2 no aportan ninguna evidencia de mapping de campo para ningún módulo.
`export_readiness_matrix.md` se actualiza en consecuencia — ver ese
documento para el detalle objeto por objeto. Esto no cambia
`specification_readiness` de los objetos ya `ready_for_draft` (los cuatro
mínimos de la Tarea 4 original no exigían mapping de campo completo), pero
sí impide que ningún objeto avance a un nivel de preparación mayor
(`ready_for_approved_specification`, introducido en este incremento) sin
nueva evidencia — ver Tarea 11 en `export_readiness_matrix.md`.

## 9. Qué evidencia de mapping de campo sigue realmente pendiente

Descartados los 9 ZIP de Bloque2 como fuente de mapping de campo, la
evidencia de mapping de campo que **sí podría existir** y sigue sin abrir es:

- Los 2 xlsx de `Bloque3_Mappings_Entidades/` (mapeo de **entidad**, no de
  campo funcional — de todos modos no abiertos en este incremento).
- Los 10 workbooks ETL de `Bloque1_ETL/` — son el lugar real donde,
  según `CLAUDE.md` y `outputs/reports/03_Catalogo_Reglas_Cruzado_Modulos.md`,
  viven las hojas `Mapeo_*` con el patrón `CampoOrigen | Field Destiny XML |
  Field Destiny ES | ...` — no se han reabierto en este incremento.

Ninguno de estos dos grupos se abrió en este incremento — el alcance de esta
tarea fue exclusivamente los 9 ZIP de `Bloque2_Mappings_SQL_ENA/`.

## 10. Impacto sobre Action Plans / `CS_HistoricalOriginID`

`AP.zip` contiene únicamente `AP/Acciones_correctoras.sql`, idéntico byte a
byte a `sql/source_queries/AP/Acciones_correctoras.sql` ya analizado en el
incremento anterior. **No aporta ninguna evidencia nueva** sobre por qué el
63% de los registros de Action Plans comparten `CS_HistoricalOriginID`
(`OQ-AP-02`), sobre `parent reference`, `relationship_status`,
`CS_HistoricalOriginID`, deduplicación, ni sobre campos de enlace vacíos.
Ver `action_plans_assessment.md` (sin cambios de fondo) y
`open_questions.md` (OQ-AP-02 permanece `pending_confirmation`, sin
reducirse, sin explicarse — no se asume que la repetición sea un defecto ni
que sea un patrón legítimo, sigue exactamente como estaba).

## 11. Limitaciones de este análisis

- Solo se inspeccionaron los 9 ZIP de `Bloque2_Mappings_SQL_ENA/` — no se
  abrieron los ZIP/xlsx de `Bloque3_Mappings_Entidades/` ni los workbooks de
  `Bloque1_ETL/`.
- La comparación byte a byte se hizo por nombre base
  (`os.path.basename`) contra todo `sql/source_queries/` — si dos módulos
  distintos tuvieran un archivo con el mismo nombre base pero contenido
  distinto, el primer match por hash habría bastado para confirmar
  identidad; no se detectó ningún caso de colisión de nombre con hash
  distinto en esta ejecución.
- Los archivos extraídos se conservan únicamente en la carpeta de
  scratchpad de esta sesión (fuera del repositorio) — no se han añadido al
  repositorio ni se referencian por ruta absoluta de máquina en ningún
  documento versionado, para no filtrar rutas locales del entorno.
