# External Data Workspace — separación entre código y datos

**Status:** Approved Design (diseño conceptual + contrato de configuración
mínimo; implementación del resolvedor en `src/core/data_workspace.py`
descrita en detalle en § 10-11). El workspace real (carpetas vacías) fue
creado en Sprint 8, evolucionado en Sprint 8.2 (§ 5, § 21-23),
normalizado/validado en Sprint 8.3 (§ 24-26) y formalizado como
Workspace Manifest en Sprint 8.4 — sigue sin contener ningún dato real:
la recuperación de ETL/CSV/mappings/evidencias sigue siendo
responsabilidad 100% manual del usuario. Ver
`docs/01-architecture/workspace-naming-convention.md` y
`docs/01-architecture/workspace-validation-checklist.md` (Sprint 8.3)
para las reglas de nomenclatura y el procedimiento de validación de
organización (nunca de contenido), y
`docs/01-architecture/workspace-manifest.md` (Sprint 8.4) para el modelo
declarativo (`WorkspaceManifest`, `src/core/workspace_manifest.py`) que
formaliza en código lo que ambos documentos ya describían en prosa.

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

**Vigente desde Sprint 8.2** (evoluciona la estructura de Sprint 7, ver §
21 para el detalle del cambio). Ruta de ejemplo para este equipo
(configurable, ver § 10):

```
C:\Users\EduardoVelásquez\Desktop\Migracion_Enablon_Data\
    ETL\
    CSV_Enablon_Template\
    CSV_Enablon_Operational\
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

`CSV_Enablon` (singular, sin sufijo) es la categoría de Sprint 7 —
**superada** por la distinción Template/Operational de Sprint 8.2 (§ 21),
pero su carpeta física no se elimina ni se renombra sin verificar primero
que no contiene ningún dato (a la fecha de Sprint 8.2 está vacía en el
único puesto de trabajo real de este proyecto). Ver § 21 para la relación
exacta entre ambos esquemas.

### 5.1 Alternativa evaluada: estructura plana vs. por proyecto

Dos alternativas evaluadas para el nivel superior del workspace:

**A. Plana** (categorías directamente bajo la raíz, un único proyecto
implícito):
```
Migracion_Enablon_Data\
    ETL\
    CSV_Enablon_Template\
    CSV_Enablon_Operational\
    ...
```

**B. Por proyecto** (recomendada):
```
Migracion_Enablon_Data\
    projects\
        moeve\
            ETL\
            CSV_Enablon_Template\
            CSV_Enablon_Operational\
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
| `etl` | Documentación histórica de transformación — libros Excel de ETL originales del cliente | `ETL_BCM_Simulacros_UpdateEje_SITECAN.xlsx` |
| `csv_enablon_template` *(Sprint 8.2, sustituye a `csv_enablon`)* | Exportaciones **completas** obtenidas directamente desde Enablon — pueden incluir campos de sistema, campos calculados por Enablon y columnas nunca utilizadas por el proyecto. Ver `project-contract-model.md` § "Platform Contract". | Un export íntegro de un objeto Enablon con sus ~36 columnas nativas |
| `csv_enablon_operational` *(Sprint 8.2, nueva)* | El CSV **realmente utilizado para importar** — el contrato funcional real del cliente, normalmente sin las columnas vacías/no usadas del template. Es la referencia principal para validar el EMF. Ver `project-contract-model.md` § "Project Contract". | El CSV que el equipo del cliente sube de verdad a Enablon en una carga real |
| `mappings` | Reglas de correspondencia SQL↔Enablon, catálogos de entidad reales | `entidades_mapeo_ANTIGUO_referencia_historica.csv` |
| `catalogs` | Catálogos auxiliares de referencia de gran volumen | `First_Axis_export_bruto.csv` |
| `errors` | Incidencias históricas — documento de Help Desk del cliente | `helpdesk_export_834_tickets.xlsx` |
| `evidence` | Evidencias de migración — Excel de evidencia generados por una ejecución real | `evidence_client.xlsx` |
| `sql` | Consultas versionadas / resultados de queries ejecutadas manualmente contra SQL Server real | — |
| `outputs` | Resultados del EMF — exportaciones completas (`drills.csv` de una corrida real, no de test) | — |
| `archive` | Copias históricas / material sin categoría activa | — |

**Nota de implementación (deliberadamente no resuelta en Sprint 8.2)**:
`config/data_workspace.yaml` sigue declarando, a la fecha de este
documento, la categoría única `csv_enablon` (§ 11) — el código
(`src/core/data_workspace.py`, `pipeline.py::HISTORICAL_CSV_CATEGORY`) no
se ha modificado en este sprint (fuera de alcance: "Claude únicamente
debe preparar la estructura, documentación y reglas de uso", no código).
Adaptar `config/data_workspace.yaml` y `pipeline.py` a las dos categorías
nuevas queda como trabajo pendiente explícito — ver § 22.

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
   comparación es opcional). **Pregunta abierta de Sprint 8.2 (§ 21, no
   resuelta aquí)**: bajo el nuevo esquema Template/Operational, no está
   confirmado si `Drills-22072026-41.csv` corresponde conceptualmente a
   `csv_enablon_template` (export completo de producción, 36 columnas) o
   a `csv_enablon_operational` (el CSV que de verdad se cargó) — no se
   asume ninguna de las dos sin confirmación del cliente/consultor.
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
`csv_enablon_template` o `csv_enablon_operational` según corresponda
(Sprint 8.2, § 21).

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

## 21. Evolución Sprint 8.2 — de `csv_enablon` a Template/Operational

**Motivación**: un único CSV real de Enablon no basta para distinguir dos
preguntas distintas que el proyecto necesita responder por separado:
"¿qué columnas puede llegar a tener un objeto de Enablon en general?"
(pregunta de plataforma) y "¿qué columnas usa realmente este cliente para
importar?" (pregunta de proyecto). La categoría única `csv_enablon` de
Sprint 7 no distinguía entre ambas — se sustituye por dos categorías:

| Categoría anterior (Sprint 7) | Categorías nuevas (Sprint 8.2) |
|---|---|
| `csv_enablon` | `csv_enablon_template` **y** `csv_enablon_operational` (dos carpetas separadas, no una con subcarpetas) |

Ver `docs/01-architecture/project-contract-model.md` (nuevo en este
sprint) para la definición completa de qué representa cada uno
(**Platform Contract** vs. **Project Contract**) y cómo se relacionan con
el **EMF Contract** (el CSV que genera el Framework).

**Qué cambió realmente en Sprint 8.2** (solo estructura y documentación,
nada de código ni datos):

1. Se crearon dos carpetas nuevas, vacías, en el workspace externo real
   de este equipo: `projects/moeve/CSV_Enablon_Template/` y
   `projects/moeve/CSV_Enablon_Operational/`.
2. La carpeta `projects/moeve/CSV_Enablon/` (Sprint 7) **no se movió, no
   se renombró y no se eliminó** — sigue existiendo, vacía, sin ningún
   dato dentro a la fecha de este sprint.
3. Este documento y `drills-real-data-inventory.md` se actualizaron para
   reflejar la nueva estructura y explicar el nuevo modelo de contratos.
4. `config/data_workspace.yaml` y el código de `DataWorkspace`/Drills
   **no se modificaron** — siguen usando la categoría `csv_enablon`
   heredada de Sprint 7 (ver § 22 para el trabajo pendiente).

## 22. Trabajo de código pendiente (explícitamente NO hecho en Sprint 8.2)

Sprint 8.2 fue exclusivamente documental/estructural. Queda pendiente,
como una tarea de código futura y separada (requiere su propia
autorización):

- Añadir `csv_enablon_template`/`csv_enablon_operational` a
  `config/data_workspace.yaml` (sustituyendo o conviviendo con
  `csv_enablon`, decisión pendiente).
- ~~Decidir y actualizar, en `src/export/prototype/drills/pipeline.py`, si
  `HISTORICAL_CSV_CATEGORY` debe apuntar a `csv_enablon_template`, a
  `csv_enablon_operational`, o si Drills necesita seguir usando un
  concepto propio distinto de ambos~~ — resuelto en Sprint 8.5: la
  constante se retiró; la comparación pide `operational_csv` vía
  `ResourceResolver` (ver § 23). La clasificación de
  `Drills-22072026-41.csv` en sí (§ 13) sigue sin confirmar — no es lo
  mismo que decidir qué categoría consulta el código.
- Diseñar (no implementar todavía tampoco, ver
  `project-contract-model.md` § "Futura validación automática") el motor
  de comparación de tres vías Template → Operational → EMF.
- Decidir si la categoría `csv_enablon` (Sprint 7) se retira formalmente
  de `config/data_workspace.yaml` una vez confirmado que ningún dato
  real la usa, o si se mantiene como alias de compatibilidad.

## 23. Criterios de aceptación de Sprint 8.2

1. Las dos carpetas nuevas existen en el workspace externo real y están
   vacías — verificado por listado de directorio en la ejecución de esta
   fase.
2. Ninguna carpeta ni archivo existente se movió, renombró o eliminó.
3. Ningún dato real se copió, descargó ni generó de forma ficticia.
4. `project-contract-model.md` define los tres niveles de contrato
   (Platform/Project/EMF) sin implementar ningún motor de comparación.
5. `config/data_workspace.yaml` y el código de `src/core/`/Drills quedan
   sin modificar — verificado por `git status --short` al cierre de esta
   fase.
6. No se ejecutó SQL, pipeline, ni sample. No se creó ningún commit.

## 24. Normalización del workspace (Sprint 8.3)

**Resultado de la revisión de esta fase**: la estructura física del
workspace externo real de este equipo, verificada por listado de
directorio en el momento de esta revisión, es:

```
projects/moeve/
    Archive/            [conforme]
    Catalogs/            [conforme, vacía]
    CSV_Enablon/          [DEPRECATED -- ver más abajo]
    CSV_Enablon_Operational/ [conforme, vacía]
    CSV_Enablon_Template/     [conforme, vacía]
    Errors/                    [conforme, vacía]
    ETL/                        [conforme, vacía]
    Evidence/                    [conforme, vacía]
    Mappings/                     [conforme, vacía]
    Outputs/                       [conforme, vacía]
    SQL/                             [conforme, vacía]
```

Ninguna carpeta legacy adicional fue detectada más allá de `CSV_Enablon/`
— es la única superada por la evolución de Sprint 8.2. **No se elimina**
(regla dura de este sprint: "no eliminar carpetas legacy") — se marca
formalmente:

> **`projects/moeve/CSV_Enablon/` — Status: Deprecated.**
> Sustituida por `CSV_Enablon_Template/` y `CSV_Enablon_Operational/`
> (Sprint 8.2, § 21). No colocar archivos nuevos aquí. Se conserva vacía
> hasta que se confirme (por quien administra el workspace) que ningún
> proceso ni persona depende todavía de esta ruta, momento en el que
> podría eliminarse manualmente — esa eliminación no es parte de este
> sprint ni de ningún sprint de Claude hasta que se autorice
> explícitamente.

Ningún archivo se movió automáticamente (regla dura de este sprint) — no
había ningún archivo que mover: la carpeta está vacía.

## 25. Workspace Manifest — diseño conceptual (Sprint 8.3, NO implementado)

**Nada de esta sección tiene código ni fichero real.** Es el diseño de un
manifiesto declarativo, versionado, que un incremento futuro podría
generar por proyecto para responder de un vistazo "¿qué tiene este
proyecto y en qué estado está?", sin tener que recorrer el workspace a
mano.

### 25.1 Propuesta de forma (`workspace.yaml`, conceptual)

```yaml
# EJEMPLO CONCEPTUAL -- este fichero NO existe todavía, no se genera en
# este sprint, y esta forma no está implementada por ningún código.
project: moeve
last_reviewed: "2026-07-27"
reviewed_by: "Functional Migration Team"   # texto libre, sin sistema de usuarios propio (mismo
                                            # criterio ya fijado en canonical-data-model.md § 14)

modules:
  drills:
    etl:
      path: "ETL/Drills.xlsx"
      status: pending          # pending | present | validated
    csv_template:
      path: "CSV_Enablon_Template/Drills-22072026-41.csv"
      status: pending
    csv_operational:
      path: "CSV_Enablon_Operational/Drills.csv"
      status: pending
    sql:
      path: "sql/source_queries/Simulacros/SQLQuery - DATASET SIMULACRO.sql"  # ya en Git, no en el workspace externo
      status: present
    mapping:
      path: "inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv"  # ya en el repo, no en el workspace externo (deuda técnica, § 20)
      status: present
    state: draft_partial        # draft_partial | ready_for_sample | sample_executed | full_executed
```

### 25.2 Campos propuestos, uno por artefacto de módulo

- `etl.path` / `etl.status`
- `csv_template.path` / `csv_template.status`
- `csv_operational.path` / `csv_operational.status`
- `sql.path` / `sql.status`
- `mapping.path` / `mapping.status`
- `state` (agregado del módulo completo)

Vocabulario de `status` propuesto (cerrado, mismo espíritu que el resto
de vocabularios ya fijados en este proyecto —
`canonical-data-model.md` § 17, `mapping-specification.md` § 17):
`pending` (no recuperado todavía), `present` (existe en la ruta
declarada, sin validar más allá de organización — ver
`workspace-validation-checklist.md`), `validated` (pasó la validación de
organización de § "Fase 7").

### 25.3 Por qué no se implementa todavía

- **No hay todavía ningún dato real en el workspace** (§ 24) — un
  manifiesto que describa un workspace vacío no aporta valor operativo
  hoy, sería una plantilla sin contenido real que mantener sincronizada.
- **Principio 8 (No Abstraction Without a Real Consumer)**: el consumidor
  real de este manifiesto (una CLI que lo lea antes de un sample, o un
  humano que lo consulte) no existe todavía — se documenta la forma para
  cuando exista ese consumidor, no se construye antes.
- **Quién lo mantendría actualizado** (¿se regenera automáticamente
  escaneando el workspace, o lo edita a mano quien incorpora un archivo?)
  es una decisión de implementación explícitamente diferida — ambas
  opciones son compatibles con la forma propuesta en § 25.1.

### 25.4 Relación con `config/data_workspace.yaml`

`workspace.yaml` (propuesto) y `config/data_workspace.yaml` (ya
implementado) **no son el mismo concepto**: `config/data_workspace.yaml`
vive en el repositorio, declara categorías genéricas por proyecto (mismo
esquema para cualquier módulo), y lo lee `DataWorkspace` en tiempo de
ejecución. `workspace.yaml` (propuesto) viviría **dentro del propio
workspace externo** (nunca en Git — sería, él mismo, un dato operativo
del proyecto, no código), y describiría el estado concreto de CADA
módulo (Drills, Safety Meetings, MOC...) con sus rutas y artefactos
reales. Uno es esquema (código), el otro sería inventario de instancia
(dato) — misma distinción que Mapping Model vs. datos de una ejecución
real, ya aplicada en el resto de la documentación EMF.

## 26. Criterios de aceptación de Sprint 8.3

1. La carpeta legacy `CSV_Enablon/` queda marcada `Status: Deprecated` en
   documentación, sin eliminarse ni renombrarse.
2. No se detectó ninguna otra carpeta obsoleta más allá de esa.
3. Ningún archivo se movió, copió ni se generó de forma ficticia — el
   workspace sigue sin ningún dato real (§ 24).
4. El diseño del Workspace Manifest (§ 25) no tiene ninguna
   implementación de código ni fichero real generado.
5. `workspace-naming-convention.md` y `workspace-validation-checklist.md`
   existen como documentos nuevos, referenciados desde este documento.
6. No se ejecutó SQL, pipeline, ni sample. No se creó ningún commit. No
   se modificó ningún mapping ni código.

## 27. Sprint 8.4 — Workspace Manifest (código)

El diseño conceptual de `workspace.yaml` (§ 25) se implementó en Sprint
8.4 como `WorkspaceManifest`/`WorkspaceManifestLoader`/`validate_manifest`
en `src/core/workspace_manifest.py`, con un ejemplo versionado
(`examples/workspace/workspace.example.yaml`) y un comando CLI
(`python main.py workspace validate --manifest <path>`). Ver
`docs/01-architecture/workspace-manifest.md` para el diseño completo —
no se repite aquí. Como parte de esta implementación,
`config/data_workspace.yaml` ganó dos categorías nuevas, puramente
aditivas: `csv_enablon_template` y `csv_enablon_operational` (§ 21) — la
categoría legacy `csv_enablon` se mantiene sin cambios para no romper el
comportamiento actual de Drills (`pipeline.py::HISTORICAL_CSV_CATEGORY`
sigue sin modificarse, ver § 22, todavía pendiente).

## 23. Sprint 8.5 — Resource Resolver y retiro de `HISTORICAL_CSV_CATEGORY`

El punto pendiente de § 22 ("Decidir y actualizar... si
`HISTORICAL_CSV_CATEGORY` debe apuntar a `csv_enablon_template`, a
`csv_enablon_operational`...") queda resuelto en Sprint 8.5:
`pipeline.py` ya no tiene una constante `HISTORICAL_CSV_CATEGORY` —
resuelve el CSV de comparación pidiendo explícitamente el artefacto
`operational_csv` (Project Contract) a través del `ResourceResolver`
genérico (`src/core/resource_resolver.py`). La categoría legacy
`csv_enablon` deja de consultarse en código (sigue declarada en
`config/data_workspace.yaml` únicamente por si hay que auditar qué había
ahí, no se retira el YAML). Ver `docs/01-architecture/resource-resolver.md`
§ 15 para el detalle completo y la nota abierta sobre la clasificación de
`Drills-22072026-41.csv`.

## 24. Sprint 8.7 — consumido por el Workspace Readiness Validator

`DataWorkspace` sigue sin cambios de comportamiento. El nuevo
`WorkspaceReadinessValidator` (`src/core/readiness_validator.py`, ver
`docs/01-architecture/workspace-readiness-validator.md`) lo usa
transitivamente, a través de `ResourceResolver`, para comprobar existencia
física opcional (`require_physical_files=True`) -- nunca crea directorios ni
archivos, mismas garantías ya vigentes en este documento.

## 25. Sprint 9.0 — primer workspace real activado (Moeve)

`EMF_DATA_ROOT/projects/moeve/workspace.yaml` (fuera de Git) es el primer
`WorkspaceManifest` real cargado contra el workspace físico verdadero, no
un ejemplo versionable. Confirma en la práctica una limitación de
configuración no documentada hasta ahora: los comandos `workspace
validate/resolve/readiness` de la CLI **no** llaman a `load_dotenv()` (solo
`src/db/connection.py` lo hace) -- `EMF_DATA_ROOT` debe estar exportado
como variable de entorno real del shell, no basta con tenerlo en `.env`,
para que estos comandos vean el workspace externo. Ver
`docs/07-developer-guide/moeve-workspace-activation.md` § 7 para el
detalle y la clasificación (`IMPROVEMENT`, no corregido en ese sprint).
