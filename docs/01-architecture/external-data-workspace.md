# External Data Workspace — separación entre código y datos

**Status:** Approved Design (diseño conceptual + contrato de configuración
mínimo; implementación del resolvedor en `src/core/data_workspace.py`
descrita en detalle en § 10-11; workspace real todavía no creado en ningún
equipo — ver § 20).

## 1. Propósito

Fijar, de forma permanente, la separación entre **código** (versionado en
Git) y **datos de migración** (ETL reales, CSV de Enablon, BAK, ZIP,
evidencias, exportaciones, documentos de cliente — nunca versionados), y
preparar el Framework para resolver la ubicación de esos datos desde un
**workspace externo** configurable, sin rutas absolutas codificadas en el
Core.

## 2. Problema resuelto

El 2026-07-27, `inputs/_incoming_claude_web/` — una carpeta de datos
reales de cliente incorporada manualmente dentro del repositorio —
entró en el historial de Git (commit `aa1d0e2`, "Initial commit"),
superó el límite de tamaño de GitHub, y una operación de limpieza de
historial (`git filter-repo`) necesaria para poder publicar el
repositorio acabó eliminando esos archivos también del disco local (ver
`docs/07-developer-guide/local-data-recovery-checklist.md` § 0 para el
incidente completo). La causa raíz no fue la herramienta de limpieza en
sí — fue que **nunca debió haber datos reales de cliente dentro del árbol
de un repositorio Git**. Este documento resuelve esa causa raíz, no solo
el síntoma.

## 3. Principio: Code/Data Separation

```
Repositorio Git (versionado)          Workspace externo (NO versionado)
─────────────────────────────         ──────────────────────────────────
código fuente                         ETL reales
configuración sin secretos            CSV reales de Enablon
documentación                         BAK
tests                                 ZIP de cliente
fixtures pequeños/anonimizados        evidencias reales
ejemplos, plantillas vacías           exportaciones completas
catálogos genéricos                   documentos de cliente
schemas, manifests de ejemplo         información confidencial
```

Regla dura: **el repositorio nunca depende de que el workspace externo
exista** para clonarse, instalarse, o pasar su suite de tests — todo lo
que el repositorio necesita para funcionar como código está dentro de
sí mismo. El workspace externo aporta los *datos* sobre los que ese
código opera cuando hay que ejecutar una migración real, nunca al revés.

## 4. Estructura del repositorio

Sin cambios respecto a la ya existente — `src/`, `tests/`, `config/`,
`docs/`, `sql/source_queries/` (SQL como texto, sin datos), `main.py`.
`inputs/` sigue existiendo como carpeta de **fixtures pequeños y
catálogos gitignored por defecto** (ver § 7-8), nunca como el lugar
donde vive un dato de cliente de volumen real.

## 5. Estructura del workspace externo

Ruta de ejemplo para este equipo (configurable, ver § 10):

```
C:\Users\EduardoVelásquez\Desktop\Migracion_Enablon_Data\
    ETL\
    CSV_Enablon\
    Mappings\
    Catalogs\
    Errors\
    Evidence\
    SQL\
    Outputs\
    Archive\
```

Organizada **por finalidad**, no por el nombre histórico de los bloques
de entrega del cliente (`Bloque1`…`Bloque7`) — esos nombres se conservan
solo como referencia de procedencia en el inventario de recuperación
(`local-data-recovery-checklist.md` § 5), nunca como estructura operativa.

### 5.1 Alternativa evaluada: estructura plana vs. por proyecto

Dos alternativas evaluadas para el nivel superior del workspace:

**A. Plana** (categorías directamente bajo la raíz, un único proyecto
implícito):
```
Migracion_Enablon_Data\
    ETL\
    CSV_Enablon\
    ...
```

**B. Por proyecto** (recomendada):
```
Migracion_Enablon_Data\
    projects\
        moeve\
            ETL\
            CSV_Enablon\
            Mappings\
            Catalogs\
            Errors\
            Evidence\
            Outputs\
        example\
            fixtures\
```

**Se recomienda B — por proyecto.** Aunque hoy solo existe un proyecto
(Moeve), el propio Blueprint (§ 1-2) define EMF explícitamente como una
plataforma reutilizable entre clientes — la estructura plana obligaría a
una migración disruptiva de rutas el día que aparezca un segundo
proyecto, mientras que la estructura por proyecto no cuesta nada extra
hoy (es un nivel de anidación) y evita esa migración futura. Mismo
criterio ya aplicado en el resto de la documentación EMF: anticipar la
forma de una extensión conocida (Blueprint § 2) sin construir todavía el
mecanismo completo de gestión de proyectos (principio 8, No Abstraction
Without a Real Consumer — aquí el "consumidor" es el propio Blueprint, no
un mecanismo de código nuevo).

## 6. Categorías de datos

| Categoría | Contenido | Ejemplo |
|---|---|---|
| `etl` | Libros Excel de ETL originales del cliente | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` |
| `csv_enablon` | CSV reales exportados de Enablon (histórico, para comparación) | `Drills-22072026-41.csv` |
| `mappings` | Mapeos SQL↔Enablon, catálogos de entidad reales | `entidades_mapeo_ANTIGUO_referencia_historica.csv` |
| `catalogs` | Catálogos de referencia de gran volumen | `First_Axis_export_bruto.csv` |
| `errors` | Documento de incidencias del cliente (Help Desk) | `helpdesk_export_834_tickets.xlsx` |
| `evidence` | Excel de evidencia generados por una ejecución real | `evidence_client.xlsx` |
| `sql` | Resultados de queries ejecutadas manualmente contra SQL Server real | — |
| `outputs` | Exportaciones completas (`drills.csv` de una corrida real, no de test) | — |
| `archive` | Material histórico sin categoría activa | — |

## 7. Datos versionables

Ver `local-data-recovery-checklist.md` § 2 (idéntico, no se duplica aquí
— un solo documento, una responsabilidad, `documentation-standards.md`
§ 8): código fuente, configuración sin secretos, documentación, tests,
fixtures pequeños y anonimizados, ejemplos, plantillas vacías, catálogos
genéricos sin información de cliente, schemas, manifests de ejemplo.

## 8. Datos no versionables

Ver `local-data-recovery-checklist.md` § 2: ETL reales, CSV reales de
Enablon, BAK, ZIP de cliente, evidencias reales, exportaciones completas,
documentos de cliente, errores con datos reales, información
confidencial, credenciales, archivos generados de gran volumen.

## 9. Seguridad y confidencialidad

- Ningún dato no versionable (§ 8) se commitea, ni siquiera
  temporalmente, ni siquiera en una rama — el incidente de este mismo
  sprint es la prueba de que "estaba ahí solo un tiempo" no es una
  mitigación real una vez que ha entrado en el historial.
- El workspace externo no tiene requisitos de cifrado ni control de
  acceso impuestos por este documento — hereda los que ya apliquen al
  sistema de ficheros/política de la organización; este documento solo
  garantiza que EMF no obliga a que esos datos pasen por Git para poder
  trabajar con ellos.
- Ningún mensaje de error del resolvedor de rutas (§ 11) imprime el
  contenido de ningún fichero, ni credenciales, ni nada más que la ruta
  que se intentó resolver — mismo principio ya vigente en
  `security-standards.md` § 4 para el resto del Framework.

## 10. Resolución de rutas

Variable de entorno única, con el mismo espíritu que las ya usadas para
credenciales (`SQL_PREVENCION_HOST`, etc. — nunca en YAML versionado,
siempre en `.env`/entorno):

```
EMF_DATA_ROOT=C:\Users\EduardoVelásquez\Desktop\Migracion_Enablon_Data
```

**Esta variable nunca se define en `.env` como valor real dentro del
repositorio** (`.env` no se versiona, ver `.gitignore`) — cada
desarrollador la define en su propio entorno. `.env.example` documenta
solo la forma (§ 17), nunca un valor real.

El **Core no contiene esta ruta como literal** en ningún fichero `.py` —
el ejemplo de ruta de este documento (`C:\Users\...\Migracion_Enablon_Data`)
es exactamente eso, un ejemplo de documentación, nunca código.

## 11. Configuración por entorno

`config/data_workspace.yaml` (nuevo, versionado — no contiene ninguna
ruta real, solo la declaración de categorías):

```yaml
root_env: EMF_DATA_ROOT

projects:
  moeve:
    base: projects/moeve
    categories:
      etl: ETL
      csv_enablon: CSV_Enablon
      mappings: Mappings
      catalogs: Catalogs
      errors: Errors
      evidence: Evidence
      sql: SQL
      outputs: Outputs
      archive: Archive
```

`root_env` declara **el nombre** de la variable de entorno a leer
(`EMF_DATA_ROOT`), nunca su valor. `projects.<nombre>.base` es la
subcarpeta del proyecto dentro de la raíz externa (§ 5.1, alternativa B);
`categories` mapea nombre lógico → subcarpeta, igual patrón ya usado en
`config/settings.yaml` → `folders` para las rutas internas del
repositorio, generalizado aquí para la raíz externa.

## 12. Portabilidad

- Ninguna ruta absoluta de ningún sistema operativo concreto vive en
  código — `EMF_DATA_ROOT` puede apuntar a cualquier ruta, Windows,
  macOS o Linux (aunque el equipo de este proyecto trabaja en Windows).
- La resolución usa `pathlib.Path` en todo momento — nunca concatenación
  de cadenas con separadores fijos (`/` o `\`), lo que permite rutas con
  espacios y caracteres Unicode sin tratamiento especial (`pathlib` los
  soporta de forma nativa).
- Dos desarrolladores del mismo proyecto pueden tener `EMF_DATA_ROOT`
  apuntando a ubicaciones completamente distintas sin que ni el código ni
  la configuración versionada necesiten saberlo.

## 13. Integración con Drills

Fase 7 de Sprint 7 (mínima, de bajo riesgo): la única ruta de dato real
que Drills resolvía directamente dentro del repositorio era
`HISTORICAL_CSV_PATH` (`src/export/prototype/drills/pipeline.py`,
apuntaba a `inputs/_incoming_claude_web/Bloque4_CSV_Enablon/
Drills-22072026-41.csv` — la ruta ya eliminada por el incidente). Se
sustituye por una resolución vía `DataWorkspace` (§ 11 de
`framework-core-v1.md` amplía el detalle de implementación):

1. Si `EMF_DATA_ROOT` está declarado y el fichero existe en
   `csv_enablon/Drills-22072026-41.csv` dentro del workspace, se usa para
   `comparison_report.yaml` (comportamiento idéntico al actual: la
   comparación es opcional).
2. Si `EMF_DATA_ROOT` no está declarado, o el fichero no está en el
   workspace, `comparison_report.yaml` simplemente no se genera — **nunca
   cae de vuelta a leer un dato real dentro de `inputs/`** (esa carpeta ya
   no debe contener datos de ese volumen, ver § 8).
3. El catálogo de entidad (`reference_data.entity_catalog_csv` en
   `config/exports/drills.yaml`) **no se toca en esta fase** — sigue
   apuntando a `inputs/entity_catalog/` (ya gitignored, nunca estuvo en el
   historial de Git, no formó parte del incidente) — se documenta como
   candidato a una migración futura al workspace externo, no urgente (ver
   `framework-core-v1.md`-style deuda técnica en el informe de esta
   fase).

## 14. Integración con futuros módulos

Cualquier objeto migrable futuro que necesite un dato real (un segundo
catálogo, un segundo CSV histórico de comparación) resuelve su ruta con
la misma `DataWorkspace`, declarando su propia categoría en
`config/data_workspace.yaml` bajo su proyecto — nunca inventa un segundo
mecanismo de resolución de rutas. `DataWorkspace` no conoce Drills ni
ningún objeto concreto (verificado por inspección de imports, mismo
criterio ya aplicado al Core en `framework-core-v1.md` § 4).

## 15. Campos estándar y campos `CS_`

Ver `local-data-recovery-checklist.md` § 6 (no se duplica aquí): los CSV
de Enablon combinan campos estándar estables con campos personalizados de
cliente (`CS_*`), que deben declararse expresamente en plantillas/mappings/
validaciones — nunca aceptarse automáticamente por prefijo. Los CSV reales
que los contienen residen siempre en el workspace externo, categoría
`csv_enablon`.

## 16. Evidencias y outputs

- `evidence_internal.xlsx`/`evidence_client.xlsx` de una ejecución
  **real** (contra SQL Server real, con datos de cliente reales) son
  datos no versionables (§ 8) — categoría `evidence` del workspace.
- Los artefactos de una ejecución de **test** (con datos fake, bajo
  `tmp_path` de pytest) nunca tocan ni el repositorio ni el workspace
  externo — se descartan al terminar el test, como ya ocurre hoy.
- `outputs/prototype/drills/` dentro del repositorio sigue existiendo
  para ejecuciones locales de desarrollo (ya gitignored salvo
  `.gitkeep`) — no es lo mismo que la categoría `outputs` del workspace
  externo, que es para **archivar** una exportación real que se quiera
  conservar más allá del ciclo de vida de `outputs/` local. Esta
  distinción se deja documentada como decisión pendiente de refinar (ver
  § 20).

## 17. Backups

- El workspace externo **no es, por sí mismo, un sistema de backup** —
  es el lugar de trabajo activo. La copia de seguridad real de los datos
  de cliente es responsabilidad de quien gestiona ese equipo/carpeta
  (OneDrive, backup corporativo, etc.), fuera del alcance de EMF.
- Git tampoco es un backup de datos de migración (`local-data-recovery-
  checklist.md` § 1) — este documento no cambia esa regla, la refuerza.

## 18. Recuperación

Ver `local-data-recovery-checklist.md` completo — este documento no
repite el procedimiento operativo de recuperación, solo fija la
arquitectura de destino hacia la que se recupera.

## 19. Criterios de aceptación

1. Ninguna ruta absoluta de un equipo concreto aparece en `src/core/` ni
   en ningún componente del Core — verificado por inspección.
2. La resolución de rutas depende de una variable de entorno
   (`EMF_DATA_ROOT`), nunca de un valor por defecto que apunte dentro del
   repositorio a un dato real.
3. `DataWorkspace` no conoce Drills ni ningún objeto migrable concreto.
4. Drills sigue funcionando exactamente igual que antes cuando
   `EMF_DATA_ROOT` no está declarado (comparación opcional, sin cambios
   de comportamiento observable, ver § 13).
5. Ninguna carpeta de datos reales vuelve a versionarse — reforzado por
   `.gitignore` (ver informe de esta fase, § "Protección Git").
6. El repositorio se clona, instala y pasa su suite de tests sin que el
   workspace externo exista en absoluto.

## 20. Deuda técnica

- `reference_data.entity_catalog_csv` de Drills no se migra al workspace
  externo en esta fase (§ 13, punto 3) — sigue en `inputs/entity_catalog/`
  local, gitignored. Migrarlo es una extensión directa y de bajo riesgo
  de este mismo diseño, aplazada por no ser urgente (nunca estuvo en el
  historial de Git).
- La relación exacta entre `outputs/` (local, por ejecución, dentro del
  repo) y la categoría `outputs`/`archive` del workspace externo (§ 16)
  no está completamente resuelta — hoy son conceptos paralelos, sin un
  mecanismo automático que archive una ejecución local al workspace
  externo. Decisión de implementación futura, no de este documento.
- `config/data_workspace.yaml` declara categorías fijas
  (`etl`/`csv_enablon`/.../`archive`) — si un futuro proyecto necesita una
  categoría distinta, hoy exige editar este YAML a mano; no hay
  validación automática de que una categoría "tenga sentido" más allá de
  existir en el fichero. Aceptado como suficiente con un único proyecto
  real (principio 8).
- No existe todavía un mecanismo para que `main.py`/la CLI avisen de
  forma proactiva "tu `EMF_DATA_ROOT` no está declarado" al arrancar —
  el error solo aparece en el momento en que algo intenta resolver una
  ruta real (comportamiento perezoso, deliberado — ver
  `framework-core-v1.md`-style justificación en el informe: no fallar
  hasta que haga falta).
