# Workspace Naming Convention — EMF / Moeve

**Status:** Approved Design (Sprint 8.3). Reglas de nomenclatura para los
archivos que el usuario incorpore manualmente al workspace externo
(`EMF_DATA_ROOT`, ver `external-data-workspace.md`). Este documento no
crea, renombra ni mueve ningún archivo — fija la convención que
`workspace-validation-checklist.md` usa para validar lo que ya exista.

## 1. Alcance

Aplica a las categorías del workspace que reciben archivos identificados
por módulo: `ETL/`, `CSV_Enablon_Template/`, `CSV_Enablon_Operational/`.
Las demás categorías (`Mappings/`, `Catalogs/`, `Errors/`, `Evidence/`,
`SQL/`, `Outputs/`, `Archive/`) no tienen todavía una convención de
nombre propia más allá de "nombre descriptivo, sin espacios ambiguos" —
se documentará cuando exista un caso real que la exija (principio 8).

## 2. `ETL/`

**Regla**: `<Modulo>.xlsx`

Un nombre de módulo, capitalizado, sin espacios, extensión `.xlsx`.

| Ejemplo | Módulo correspondiente |
|---|---|
| `Drills.xlsx` | `simulacros` (Drills) |
| `Events.xlsx` | `eventos` |
| `Audits.xlsx` | (nombre de ejemplo dado por el encargo — no existe todavía un módulo `Audits` en `config/modules.yaml`; si se incorpora, este documento no inventa a qué módulo real correspondería) |

**Notas**:

- Un solo archivo por módulo — si existen varias versiones históricas del
  mismo ETL, la versión vigente vive aquí y las anteriores en `Archive/`
  (nunca varias versiones sueltas en `ETL/` sin distinguir cuál es la
  vigente).
- El nombre **no** reproduce el nombre de fichero original del cliente
  (p. ej. `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx`, ver
  `drills-real-data-inventory.md` fila 1) — se renombra a la convención
  `<Modulo>.xlsx` en el momento de incorporarlo. Esta acción de renombrado
  es responsabilidad del usuario al incorporar el archivo, nunca de
  Claude (ver "No mover archivos automáticamente" en el encargo de
  Sprint 8.3) — Claude solo valida que, una vez incorporado, el nombre
  siga la convención.

## 3. `CSV_Enablon_Template/`

**Regla**: mantiene **siempre** el nombre original exportado por
Enablon — **no se renombra nunca**.

| Ejemplo |
|---|
| `Drills-22072026-41.csv` |
| `Events-15092026-18.csv` |

**Notas**:

- **Pueden coexistir varias versiones** del mismo módulo (distintas
  fechas de exportación) — a diferencia de `ETL/` y
  `CSV_Enablon_Operational/`, esta carpeta no exige un único fichero
  vigente por módulo. Cada exportación es, por definición, una foto de un
  momento distinto del Platform Contract.
- El patrón de nombre observado hasta hoy (único caso real conocido,
  `Drills-22072026-41.csv`) es `<Modulo>-<DDMMAAAA>-<n>.csv` — **no se
  fija como regla obligatoria** en este documento (solo un caso
  confirmado no es evidencia suficiente de un patrón universal de
  Enablon, principio de no asumir sin evidencia) — la regla real es "el
  nombre que Enablon le dio, tal cual, sin tocar".

## 4. `CSV_Enablon_Operational/`

**Regla**: `<Modulo>.csv` — **un único archivo vigente por módulo**.

| Ejemplo | Módulo correspondiente |
|---|---|
| `Drills.csv` | `simulacros` (Drills) |
| `Events.csv` | `eventos` |
| `Audits.csv` | (nombre de ejemplo del encargo, ver § 2) |

**Notas**:

- Este archivo representa el **Project Contract** (ver
  `project-contract-model.md` § 2.2) — el contrato funcional real de
  importación de este cliente, no un histórico de versiones.
- Si aparece una versión más reciente, **sustituye** a la anterior — la
  versión sustituida, si se quiere conservar, va a `Archive/` (con un
  nombre que identifique su fecha, p. ej. `Drills_2026-06-01.csv`; este
  documento no fija un patrón exacto de archivo histórico por no tener
  todavía un caso real).
- Dos archivos `<Modulo>.csv` para el mismo módulo en esta carpeta es una
  violación de la convención (ambigüedad sobre cuál es el vigente) — ver
  `workspace-validation-checklist.md` § "Duplicados".

## 5. Vocabulario de nombre de módulo

El `<Modulo>` de las reglas anteriores usa, por consistencia, los mismos
nombres ya usados en el proyecto para identificar objetos migrables — en
inglés, capitalizados, coincidiendo con el nombre del objeto CSV real de
Enablon cuando se conoce (`Drills`, no `Simulacros`; ver
`config/modules.yaml` para la relación módulo↔nombre interno↔objeto real,
p. ej. `simulacros` (módulo) → `Drills` (objeto/CSV real)). Este documento
no inventa nombres de módulo nuevos — usa únicamente los ya confirmados
en `config/modules.yaml`/`CLAUDE.md`.

## 5.1 Validación automática (Sprint 8.4)

Estas reglas ya no son solo prosa: `workspace.naming_convention` en un
Workspace Manifest (ver `docs/01-architecture/workspace-manifest.md`
§ 12) declara los mismos patrones (`"{module}.xlsx"`, `"{module}.csv"`,
`preserve_source_name`...) y `validate_manifest()`
(`src/core/workspace_manifest.py`) los comprueba contra cada `path`
declarado — sin abrir ningún archivo, sin adivinar nombres. El ejemplo
completo vive en `examples/workspace/workspace.example.yaml`.

## 6. Qué NO cubre este documento

- No fija ninguna convención para el contenido interno de los ficheros
  (columnas, encoding, delimitador) — eso es el Template/Project/EMF
  Contract (`project-contract-model.md`), no la nomenclatura de archivo.
- No renombra, mueve ni valida ningún archivo por sí mismo — es la
  referencia que usa `workspace-validation-checklist.md` (Sprint 8.3,
  Fase 7) para comprobar organización.
- No asume que todos los módulos seguirán este patrón sin excepción — si
  aparece un caso real que no encaje (p. ej. un objeto con dos ETL
  distintos), se documenta la excepción cuando ocurra, no se prohíbe de
  antemano.
