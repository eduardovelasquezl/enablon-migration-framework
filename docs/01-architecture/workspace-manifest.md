# Workspace Manifest — EMF

**Status:** Implemented (Sprint 8.4). Modelo + validador implementados en
`src/core/workspace_manifest.py`, ejemplo versionado en
`examples/workspace/workspace.example.yaml`, comando CLI
`python main.py workspace validate --manifest <path>`. **Ningún
`workspace.yaml` real se ha creado dentro del workspace externo** (fuera
de alcance de este sprint, requiere aprobación separada) — el manifiesto
real seguiría siendo, cuando se cree, un dato del proyecto (no
versionado), nunca un fichero de este repositorio.

## 1. Propósito

Dar al EMF una única fuente declarativa para responder, sin recorrer el
workspace externo a mano: qué proyecto existe, qué módulos lo forman, qué
artefactos corresponde a cada módulo, cuáles son obligatorios/opcionales,
cuáles existen/faltan, qué nivel de contrato (Platform/Project/EMF)
representa cada CSV, y en qué estado operativo está cada módulo.

## 2. Alcance

- Modelo de datos tipado (`dataclasses`) para proyecto, workspace,
  módulo, artefacto y contrato.
- Carga desde YAML (`WorkspaceManifestLoader`), con validación
  estructural estricta (claves obligatorias, vocabularios cerrados, rutas
  relativas y seguras) que falla al cargar si el manifest está mal
  formado.
- Validación de reglas de negocio (`validate_manifest`) sobre un manifest
  ya cargado con éxito — devuelve una lista de violaciones, nunca lanza.
- Integración con `DataWorkspace` (`resolve_artifact_path`) para resolver
  la ruta absoluta de un artefacto declarado, reutilizando toda la
  protección de rutas ya implementada — sin duplicarla.
- Un ejemplo versionable completo para el proyecto Moeve, con sus 8
  módulos conocidos.
- Un comando CLI aditivo de validación (`workspace validate`).

## 3. Fuera de alcance

- **No crea, mueve ni copia ningún archivo real** del workspace externo.
- **No abre ni lee el contenido** de ningún ETL, CSV o mapping
  referenciado por el manifest — solo el propio YAML del manifest.
- **No comprueba, en producción, que los archivos físicos declarados
  existan** — `resolve_artifact_path` acepta `required=False` por
  defecto; solo los tests de integración (con un `DataWorkspace`
  temporal) verifican existencia real, y únicamente porque ellos mismos
  crean el archivo de prueba.
- **No implementa el motor de comparación de tres vías** (Template →
  Operational → EMF) diseñado en `project-contract-model.md` § 5 — este
  manifiesto es un insumo para ese motor futuro, no el motor en sí.
- **No sustituye `config/exports/drills.yaml`** ni ningún fichero de
  configuración de objeto migrable existente — el manifest describe el
  **workspace** (qué hay y dónde), no las reglas de mapeo/transformación
  de un objeto (eso sigue siendo el Mapping Model, ADR-013).
- No se generó ningún `workspace.yaml` real — solo la plantilla de
  ejemplo dentro del repositorio.

## 4. Relación con `DataWorkspace`

`DataWorkspace` (`src/core/data_workspace.py`, Sprint 7) resuelve
"proyecto + categoría + ruta relativa" contra `EMF_DATA_ROOT` — no sabe
qué proyectos, módulos o artefactos existen de antemano, solo resuelve
peticiones puntuales. El Workspace Manifest es la capa que sí sabe eso:
**declara** el catálogo completo de artefactos esperados, y usa
`DataWorkspace.resolve()` internamente (`resolve_artifact_path`) para
convertir "el `operational_csv` del módulo `drills`" en una ruta absoluta
real, sin reimplementar la protección de escape/rutas absolutas que
`DataWorkspace` ya ofrece. `ARTIFACT_KIND_TO_CATEGORY` es el único punto
de correspondencia entre el vocabulario del manifest (`etl`,
`template_csv`, `operational_csv`...) y las categorías de
`config/data_workspace.yaml` (`etl`, `csv_enablon_template`,
`csv_enablon_operational`...) — nunca se duplica en otro sitio.

## 5. Relación con Module Registry

No existe hoy un "Module Registry" formal e independiente en el
repositorio — la información más cercana es `config/modules.yaml`
(análisis manual consolidado) y `StageRegistry`
(`src/core/registry.py`, registro de *etapas* de pipeline, no de
*módulos migrables*). El Workspace Manifest **no sustituye** a
`config/modules.yaml` (que documenta hallazgos de análisis, volumetría,
reglas no estándar) ni a `StageRegistry` (que registra código ejecutable)
— documenta un tercer aspecto, ortogonal a ambos: qué artefactos de datos
tiene cada módulo en el workspace externo, en qué estado. Si en el futuro
se formaliza un Module Registry de código (que sepa, p. ej., qué
`object_type` tiene un pipeline registrado), el Workspace Manifest sería
un consumidor natural de esa información (`ModuleSpec.target_object` ya
apunta en esa dirección), no su reemplazo.

## 6. Relación con Resource Resolver

`DataWorkspace` **es** el Resource Resolver de este proyecto — no existe
un componente separado con ese nombre. El Workspace Manifest no introduce
un segundo mecanismo de resolución: `resolve_artifact_path` es una
función fina que traduce "módulo + tipo de artefacto" a los parámetros
que `DataWorkspace.resolve()` ya entiende (`project`, `category`,
`relative_path`), y delega toda la resolución real en él.

## 7. Estructura del manifest

```yaml
project:
  id: moeve
  display_name: "Moeve"
  status: active
  version: "1.0"
  owner: "Functional Migration Team"       # opcional
  last_reviewed_at: "2026-07-27"           # opcional

workspace:
  schema_version: "1.0"
  project_root: projects/moeve
  naming_convention:
    etl: "{module}.xlsx"
    sql: "{module}.sql"
    mapping: "{module}.xlsx"
    operational_csv: "{module}.csv"
    outputs: "{module}_{execution_id}.csv"
    template_csv: preserve_source_name
  deprecated_paths:
    - CSV_Enablon

modules:
  drills:
    display_name: "Drills (Business Continuity Management / Simulacros)"
    enabled: true
    status: in_progress
    source_system: prevencion
    target_object: Drills
    canonical_name: Drills
    artifacts:
      etl: {status: missing}
      template_csv: {status: missing, contract_role: platform}
      operational_csv: {status: missing, contract_role: project, required_for_comparison: true}
      sql: {status: present, required_for_sample: true, required_for_full: true}
      mapping: {status: present, required_for_sample: true, required_for_full: true}
      # ... catalogs, errors, evidence, outputs
    contracts:
      platform: {artifact: template_csv}
      project: {artifact: operational_csv}
      emf: {generated: true, output_pattern: "Drills_{execution_id}.csv"}
    notes: "..."
```

Ver `examples/workspace/workspace.example.yaml` para el ejemplo completo
de Moeve con sus 8 módulos.

## 8. Project metadata

| Campo | Obligatorio | Descripción |
|---|---|---|
| `id` | Sí | Identificador del proyecto (coincide con `config/data_workspace.yaml` → `projects.<id>`). |
| `display_name` | Sí | Nombre legible. |
| `status` | Sí | Texto libre hoy (p. ej. `active`) — no se define un vocabulario cerrado de estado de *proyecto* en esta fase (solo de *módulo* y *artefacto*, ver § 13) por no tener todavía un segundo proyecto real que justifique fijarlo (principio 8). |
| `version` | Sí | Versión del propio manifest/proyecto — texto libre. |
| `owner` | No | Texto libre, sin sistema de usuarios propio (mismo criterio que `canonical-data-model.md` § 14). |
| `last_reviewed_at` | No | Fecha de la última revisión humana del manifest. |

## 9. Module metadata

| Campo | Obligatorio | Descripción |
|---|---|---|
| `module_id` | Sí (es la propia clave del mapa `modules`) | Debe coincidir exactamente con la clave — verificado al cargar (`WorkspaceManifest.__post_init__`). |
| `display_name` | Sí | Nombre legible completo. |
| `enabled` | Sí | Si este módulo participa activamente hoy. |
| `status` | Sí | Uno de `ModuleStatus.ALL` (§ 13). |
| `source_system` | No | `prevencion` \| `gct` (mismo vocabulario que `config/databases.yaml`) — texto libre, no vocabulario cerrado en este modelo (evita duplicar esa validación aquí). |
| `target_object` | No | Nombre del objeto Enablon destino, si se conoce. |
| `canonical_name` | No | Nombre usado en las convenciones de fichero (`<Modulo>.xlsx`, `<Modulo>.csv`) — **nunca inventado**: solo se declara cuando hay evidencia real inequívoca (ver `examples/workspace/workspace.example.yaml`, que lo omite para 5 de 8 módulos por ambigüedad). |
| `artifacts` | No (vacío por defecto) | Mapa `kind -> ArtifactSpec` (§ 10). |
| `contracts` | No | `ContractsSpec` (§ 11). |
| `validation` | No | Mapa libre, no interpretado por este módulo — reservado para una futura sección de reglas específicas de módulo. |
| `notes` | No | Texto libre. **Obligatorio en la práctica** cuando `status=deprecated` y `enabled=true` (regla dura, § 14). |

## 10. Artifacts

Nueve `kind` cerrados (`ARTIFACT_KINDS`): `etl`, `template_csv`,
`operational_csv`, `sql`, `mapping`, `catalogs`, `errors`, `evidence`,
`outputs` — cada uno resuelto contra una categoría de `DataWorkspace`
(§ 4).

| Campo | Obligatorio | Descripción |
|---|---|---|
| `path` | No | Relativo a la carpeta de categoría (nunca absoluto, nunca con `..` — validado al cargar). `null`/ausente = todavía no se conoce/recuperó. |
| `required_for_sample` | No (default `false`) | Declara el artefacto obligatorio para `sample`. Hasta Sprint 8.7 este flag era puramente declarativo (solo comprobado al cargar el manifest, nunca en runtime) -- desde Sprint 8.7, `WorkspaceReadinessValidator` (ver `docs/01-architecture/workspace-readiness-validator.md`) es quien realmente lo aplica y bloquea si falta. |
| `required_for_full` | No (default `false`) | Igual que arriba, para `full`. |
| `required_for_comparison` | No (default `false`) | Necesario solo para generar un reporte de comparación (nunca bloquea sample/full) -- aplicado por `WorkspaceReadinessValidator` para la operación `comparison`. |
| `status` | No (default `missing`) | Uno de `ArtifactStatus.ALL` (§ 13). |
| `description` | No | Texto libre. |
| `contract_role` | No | `platform` \| `project` \| `emf` — normalmente coincide con lo declarado en `contracts` (§ 11), pero se deja como anotación libre del propio artefacto también. |
| `source` | No | Texto libre — de dónde viene o se espera que venga (p. ej. `"git:sql/source_queries/..."`, `"repo:inputs/entity_catalog/..."`, `"pendiente de recuperación manual"`). |
| `checksum` | No | Reservado para una futura verificación de integridad — no calculado ni verificado por este incremento. |
| `last_reviewed_at` | No | Fecha de última revisión de este artefacto concreto. |

## 11. Contract roles

`ContractsSpec` declara, por módulo, qué artefacto representa cada nivel
de `project-contract-model.md`:

```yaml
contracts:
  platform:
    artifact: template_csv       # nombre de kind, no una ruta
  project:
    artifact: operational_csv
  emf:
    generated: true
    output_pattern: "Drills_{execution_id}.csv"
```

- `platform.artifact` / `project.artifact` deben referenciar un `kind`
  **declarado en `artifacts` de ese mismo módulo** — verificado al
  cargar (`ManifestSchemaError` si no).
- `emf.generated` es informativo (si el EMF ya produce un CSV para este
  módulo); `emf.output_pattern` es el patrón de nombre esperado de la
  salida (consistente con la convención `outputs` de § 12).
- **No se asume que `template_csv` y `operational_csv` tengan el mismo
  número de columnas** (ver `project-contract-model.md` § 3) — este
  modelo no lo valida ni lo necesita validar; son artefactos
  independientes.
- **No se exige que todas las columnas del Platform Contract sean
  generadas por el EMF** — el objetivo declarado es el Project Contract
  (`project-contract-model.md` § 2.4).

## 12. Naming conventions

`workspace.naming_convention` (mapa `kind -> patrón`) declara el patrón
esperado de nombre de archivo por tipo de artefacto, con dos placeholders
reconocidos: `{module}` (sustituido por `ModuleSpec.canonical_name`) y
`{execution_id}` (sustituido por cualquier valor no vacío al validar).
`template_csv: preserve_source_name` es un valor especial que desactiva
la validación de nombre para esa categoría (el nombre original de Enablon
se conserva tal cual, ver `workspace-naming-convention.md` § 3).

**La implementación no usa glob** como mecanismo principal — los
patrones se convierten a una regex exacta (`_pattern_to_regex`) y se
comparan con `re.fullmatch` contra el `path` **efectivo** ya declarado en
el manifest. Las convenciones sirven para **validar** un nombre ya
declarado, nunca para **adivinar** qué archivo corresponde a un módulo
cuando no se ha declarado ningún `path`.

## 13. Status model

**`ModuleStatus`**: `planned` \| `ready` \| `blocked` \| `in_progress` \|
`validated` \| `deprecated`.

**`ArtifactStatus`**: `missing` \| `present` \| `validated` \| `optional`
\| `deprecated` \| `not_applicable`.

Ambos vocabularios se adoptaron tal como los propuso el encargo de
Sprint 8.4 — revisados contra el resto de vocabularios ya usados en el
proyecto (`StageStatus`/`ExecutionStatus` en `contracts.py`,
`RESOLVED`/`UNRESOLVED`/`DO_NOT_MIGRATE`/`CONFLICTING`/`EMPTY` en
`mappings.py`) sin encontrar una superposición directa que obligara a
reutilizar uno de ellos — un módulo/artefacto de workspace es un concepto
distinto de una etapa de pipeline o una resolución de entidad, y mezclar
ambos vocabularios habría sido más confuso que tener dos pequeños y
propios.

## 14. Validation rules

**A nivel de esquema** (`ManifestSchemaError`, lanzada al cargar — un
manifest mal formado no llega a construirse):

1. `project`/`workspace`/`modules` presentes en el nivel superior.
2. `project.id`/`display_name`/`status`/`version` presentes.
3. `workspace.schema_version`/`project_root` presentes.
4. Al menos un módulo declarado.
5. Cada módulo declara `display_name`/`enabled`/`status`.
6. `status` de módulo y de artefacto dentro de sus vocabularios cerrados.
7. `kind` de artefacto dentro de `ARTIFACT_KINDS`.
8. `contract_role` dentro de `CONTRACT_ROLES`.
9. Ningún `path` absoluto ni con `..`.
10. `naming_convention` no declara un `kind` desconocido.
11. Un artefacto obligatorio (`required_for_sample`/`required_for_full`)
    no puede tener `status=not_applicable`.
12. `contracts.platform`/`project` referencian un `kind` declarado en
    `artifacts` de ese módulo.
13. `status=deprecated` + `enabled=true` exige `notes` no vacío.
14. La clave de un módulo coincide con su `module_id` interno.

**A nivel de negocio** (`validate_manifest`, devuelve lista de
violaciones, nunca lanza):

15. Ningún artefacto usa una ruta dentro de `deprecated_paths` desde un
    módulo no deprecated.
16. Ningún nombre declarado de `operational_csv`/`etl`/`mapping`/`sql`/
    `outputs` viola el patrón de `naming_convention` (cuando el módulo
    declara `canonical_name`).
17. `template_csv` con `preserve_source_name` nunca produce violación de
    nombre.
18. Dos módulos no pueden declarar el mismo `canonical_name`
    (colisionarían en el nombre de fichero).
19. Dos módulos no pueden declarar la misma ruta para el mismo `kind` de
    artefacto (ambigüedad de cuál es el vigente).

## 15. Seguridad de rutas

- Toda ruta de artefacto es relativa a su carpeta de categoría — nunca
  absoluta, verificado con una regex específica para unidades de Windows
  (`C:\...`) y rutas UNC (`\\...`) además de la comprobación genérica de
  `pathlib`.
- Ningún componente `..` permitido — verificado a nivel de esquema
  (`_validate_relative_safe_path`) **y**, de forma independiente, por
  `DataWorkspace.resolve()` cuando se resuelve de verdad
  (`PathEscapesWorkspaceError`) — dos capas, la segunda reutilizada, no
  duplicada en su lógica interna.
- Compatible con Unicode y espacios — verificado con un test dedicado
  (`test_unicode_y_espacios_en_nombres_y_rutas`), mismo principio ya
  aplicado en `DataWorkspace`.
- Nunca crea carpetas ni abre archivos — verificado por inspección (sin
  `open()`/`mkdir()` en `workspace_manifest.py`, solo lectura del propio
  YAML del manifest) y por tests (`test_cargar_y_validar_no_crea_ninguna_carpeta`,
  `test_resolve_artifact_path_no_crea_ninguna_carpeta`).
- No se sigue ningún symlink de forma especial — este incremento no
  añade lógica de symlinks; `DataWorkspace.resolve()` ya usa
  `Path.resolve()` (que sí sigue symlinks del sistema operativo de forma
  estándar) sin comportamiento adicional aquí.

## 16. Ejemplo Moeve

`examples/workspace/workspace.example.yaml` — 8 módulos
(`drills`, `safety_meetings`, `moc`, `bypass`, `events`, `ops`,
`inspections`, `corrective_actions`). Solo `drills` tiene artefactos con
`status` distinto de `missing`/`not_applicable` (verificado por test,
`test_ejemplo_moeve_solo_drills_tiene_artefactos_con_status_distinto_de_missing`).
`canonical_name` solo se declara para `drills` (`Drills`), `events`
(`Events`) y `corrective_actions` (`Action_Plans`) — los tres únicos
casos con un objeto real de Enablon inequívoco confirmado en
`config/modules.yaml`; los otros 5 módulos lo omiten explícitamente, con
una nota explicando por qué (cubren varios objetos reales, o el nombre de
módulo no coincide con el nombre real del objeto).

## 17. Evolución futura

- Conectar el motor de comparación de tres vías
  (`project-contract-model.md` § 5) a este manifest, usando
  `contracts.platform`/`project` para saber qué dos artefactos comparar.
- Un comando CLI que **genere** un `workspace.yaml` inicial escaneando el
  workspace real (nunca implementado en Sprint 8.4 — este sprint solo
  valida un manifest ya escrito a mano).
- Extender `ModuleSpec.validation` (hoy un mapa libre no interpretado) si
  aparece una necesidad real de reglas de validación específicas por
  módulo, más allá de las genéricas de § 14.
- Formalizar `project.status` como vocabulario cerrado si aparece un
  segundo proyecto real con estados distintos que lo justifiquen
  (principio 8, igual que se decidió NO fijarlo todavía en § 8).

## 18. Criterios de aceptación

1. Existe un modelo declarativo (`WorkspaceManifest` + dataclasses
   asociadas) — implementado en `src/core/workspace_manifest.py`.
2. El manifest describe proyecto, módulos, artefactos y contratos —
   verificado por el ejemplo de Moeve y los tests.
3. Todas las rutas son relativas y seguras — verificado a nivel de
   esquema y por reutilización de `DataWorkspace`.
4. Integración con `DataWorkspace` — `resolve_artifact_path`, sin
   duplicar su lógica de resolución/seguridad.
5. No existen rutas absolutas en ningún ejemplo ni en el propio código.
6. No existe lógica específica de Drills en `src/core/` — verificado por
   inspección de imports (`test_modulo_no_importa_nada_de_src_db_ni_src_export`).
7. Drills aparece solo en `examples/workspace/workspace.example.yaml`.
8. Naming conventions validadas — `validate_manifest` con 8 tests
   dedicados.
9. Project Contract explícito (`contracts.project`).
10. Platform Contract explícito (`contracts.platform`).
11. EMF Contract explícito (`contracts.emf`).
12. Ejemplo Moeve válido — 0 violaciones (`test_carga_de_ejemplo_moeve_sin_violaciones`).
13. Tests nuevos en verde — 35 (`test_workspace_manifest.py`) + 4
    (`test_cli_workspace_validate.py`) = 39 nuevos, todos `PASSED`.
14. Suite previa continúa pasando — 474 → 513 passed, mismos 7 skipped.
15. No se accede a datos reales — verificado, ningún test toca SQL
    Server ni abre un ETL/CSV real.
16. No se crea el manifest real en el workspace externo — verificado
    (`git status`/listado de directorio del workspace sin cambios).
17. Documentación e informe generados (este documento +
    `reports/executions/2026-07-27/Informe-Workspace-Manifest-EMF.md`).
18. No se hizo commit sin aprobación.

## 19. Deuda técnica

- `ModuleSpec.validation` es un mapa libre sin interpretar — reservado
  para una extensión futura, no urgente (principio 8).
- No hay todavía un mecanismo que genere `workspace.yaml` a partir de un
  escaneo real del workspace (evitaría transcribir a mano lo que ya está
  en disco) — decisión de implementación futura, fuera de alcance de
  este sprint.
- `project.status` no es un vocabulario cerrado (§ 8) — aceptado como
  suficiente con un único proyecto real.
- El motor de comparación de tres vías que este manifest habilita
  (§ 17) sigue sin implementarse — este sprint solo prepara el insumo
  declarativo, no el motor.
- `checksum`/`last_reviewed_at` de artefacto son campos declarados pero
  no calculados ni verificados por ningún código todavía — puramente
  informativos en esta fase.

## 20. Sprint 8.5 — Resource Resolver

`resolve_artifact_path()` (§ 15 arriba) sigue existiendo sin cambios y
sigue siendo la función que hace la resolución de ruta física real. Sobre
ella se construyó, en Sprint 8.5, una capa de más alto nivel
(`ResourceResolver`, `src/core/resource_resolver.py`) que añade petición/
resultado tipados, reglas de estado (`missing`/`optional`/`deprecated`/
`not_applicable`) y soporte de recursos generados — ver
`docs/01-architecture/resource-resolver.md` para el diseño completo. Este
documento no se duplica aquí.
