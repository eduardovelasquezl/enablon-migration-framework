# Workspace Validation Checklist — EMF / Moeve

**Status:** Implemented as procedure (Sprint 8.3) — **manual**, no
automatizada en código todavía (ver § 5). Valida exclusivamente
**organización** del workspace externo (ubicación, nombre, carpeta,
extensión, módulo, duplicados, convención) — **nunca abre ni analiza el
contenido** de ningún ETL o CSV (fuera de alcance de Sprint 8.3 por
diseño explícito del encargo).

## 1. Qué valida esta checklist (y qué no)

**Sí valida** (por archivo incorporado al workspace):

| Check | Pregunta |
|---|---|
| ✔ Ubicación | ¿El archivo está bajo `EMF_DATA_ROOT/projects/moeve/<categoría>/`, no suelto en la raíz ni en una categoría ajena? |
| ✔ Nombre | ¿El nombre de archivo cumple `workspace-naming-convention.md` para su categoría? |
| ✔ Carpeta correcta | ¿La categoría física (`ETL/`, `CSV_Enablon_Template/`, `CSV_Enablon_Operational/`, etc.) corresponde al tipo real de archivo (extensión + rol)? |
| ✔ Extensión | ¿La extensión es la esperada para su categoría (`.xlsx` en `ETL/`, `.csv` en las dos categorías `CSV_Enablon_*`)? |
| ✔ Módulo | ¿El `<Modulo>` del nombre coincide con un módulo real ya reconocido en `config/modules.yaml`? |
| ✔ Duplicados | ¿Hay más de un archivo `<Modulo>.csv` en `CSV_Enablon_Operational/` para el mismo módulo (violación) o más de un `<Modulo>.xlsx` en `ETL/`? (`CSV_Enablon_Template/` permite varias versiones por diseño, ver `workspace-naming-convention.md` § 3 — no se reporta como duplicado). |
| ✔ Convención | Resumen: ¿el archivo, en conjunto, es indistinguible de lo que un desarrollador nuevo esperaría encontrar siguiendo `workspace-naming-convention.md` sin explicación adicional? |

**No valida** (fuera de alcance, explícito):

- Contenido de ningún ETL (hojas, fórmulas, macros) — eso es el trabajo
  de una futura Fase 5 de inspección de solo lectura (Sprint 8, no
  repetido aquí).
- Contenido de ningún CSV (columnas reales, filas, encoding) más allá de
  su nombre de archivo.
- Si el CSV Operacional realmente coincide con lo cargado en Enablon —
  eso es una pregunta funcional, no de organización.
- Si el ETL/CSV recuperado es el correcto o el más reciente — solo que
  esté bien ubicado y nombrado.

## 2. Procedimiento (para cuando existan archivos que validar)

1. Listar recursivamente `EMF_DATA_ROOT/projects/moeve/` (solo nombres y
   rutas — nunca abrir ningún archivo).
2. Para cada archivo encontrado, aplicar los 7 checks de § 1.
3. Clasificar cada archivo como `OK`, `ADVERTENCIA` (convención no
   seguida pero sin ambigüedad funcional, p. ej. mayúsculas distintas) o
   `ERROR` (ubicación equivocada, duplicado en `CSV_Enablon_Operational/`,
   extensión inesperada).
4. Reportar un resumen: total de archivos, `OK`/`ADVERTENCIA`/`ERROR` por
   categoría y por módulo.
5. Nunca corregir automáticamente — solo reportar. Cualquier corrección
   (renombrar, mover) es una acción manual del usuario.

## 3. Resultado de esta ejecución (Sprint 8.3, 2026-07-27)

Se aplicó el procedimiento de § 2 contra el workspace externo real de
este equipo (`C:\Users\EduardoVelásquez\Desktop\Migracion_Enablon_Data`).

**Archivos encontrados dentro de `projects/moeve/`: 0.**

Todas las carpetas (`ETL/`, `CSV_Enablon_Template/`,
`CSV_Enablon_Operational/`, `Mappings/`, `Catalogs/`, `Errors/`,
`Evidence/`, `SQL/`, `Outputs/`, `Archive/`, y la carpeta legacy
`CSV_Enablon/` marcada `Deprecated`) están vacías — confirmado por
listado de directorio en esta misma sesión.

El único archivo existente en todo el workspace externo es
`Archive/env-backup-before-sprint8.txt` (nivel raíz, fuera de
`projects/moeve/`), un registro de metadatos de la Fase 4 de Sprint 8 —
no es un artefacto de proyecto sujeto a esta convención.

**Resumen**:

| Categoría | Archivos encontrados | OK | ADVERTENCIA | ERROR |
|---|---:|---:|---:|---:|
| `ETL/` | 0 | — | — | — |
| `CSV_Enablon_Template/` | 0 | — | — | — |
| `CSV_Enablon_Operational/` | 0 | — | — | — |
| `Mappings/` | 0 | — | — | — |
| `Catalogs/` | 0 | — | — | — |
| `Errors/` | 0 | — | — | — |
| `Evidence/` | 0 | — | — | — |
| `SQL/` | 0 | — | — | — |
| `Outputs/` | 0 | — | — | — |
| `Archive/` | 0 (dentro de `projects/moeve/`) | — | — | — |
| `CSV_Enablon/` (Deprecated) | 0 | — | — | — |

**Conclusión de esta validación**: el workspace está estructuralmente
limpio y listo para recibir archivos — no hay ninguna violación de
organización que corregir porque no hay ningún archivo todavía. Esta
checklist debe volver a ejecutarse cada vez que el usuario incorpore
material nuevo.

## 4. Ejemplo de violaciones que este procedimiento detectaría (ilustrativo, no observado)

Para dejar explícito el criterio antes de que ocurra un caso real
(ninguno de estos ejemplos describe un archivo que exista hoy):

- `ETL/ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` → **ADVERTENCIA**
  (ubicación y extensión correctas; nombre no sigue `<Modulo>.xlsx`,
  debería renombrarse a `Drills.xlsx` al incorporarlo).
- `CSV_Enablon_Operational/Drills.csv` **y**
  `CSV_Enablon_Operational/Drills_v2.csv` simultáneamente → **ERROR**
  (duplicado — la convención exige un único vigente por módulo).
- `CSV_Enablon_Template/drills_final.csv` → **ADVERTENCIA** (nombre no
  reconocible como export original de Enablon — la convención de esta
  categoría es "no renombrar", así que un nombre que no parece un export
  nativo sugiere que sí se renombró en algún punto).
- `ETL/Drills.csv` (extensión `.csv` dentro de `ETL/`) → **ERROR**
  (extensión inesperada para esta categoría).
- Un archivo `Auditorias2026.xlsx` en `ETL/` sin que exista un módulo
  `auditorias`/`Audits` en `config/modules.yaml` → **ERROR** de check
  "Módulo" (nombre de módulo no reconocido — no se asume qué módulo real
  representa).

## 5. Automatización futura (no implementada)

Esta checklist es hoy un procedimiento manual, documentado, ejecutable
por Claude o por cualquier persona con acceso al workspace. Convertirla
en un script ejecutable (`python main.py workspace validate`, por
ejemplo) es trabajo de código futuro, explícitamente fuera de alcance de
Sprint 8.3 ("no modificar código"). Reutilizaría, si se implementa,
`src/core/data_workspace.py::DataWorkspace.resolve` para obtener las
rutas de categoría sin inventar un segundo mecanismo de resolución.
