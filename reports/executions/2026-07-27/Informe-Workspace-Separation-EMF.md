# Informe — Sprint 7: Workspace Separation (Código ↔ Datos)

**Proyecto:** Enablon Migration Framework (EMF)
**Fecha:** 2026-07-27
**Tarea:** Separación permanente entre código (Git) y datos de migración
(workspace externo), tras el incidente de pérdida de datos de Sprint 6.

---

## 1. Resumen ejecutivo

Se versionó y amplió el checklist de recuperación de datos (commit y push
ya realizados, autorizados explícitamente). Se diseñó formalmente la
separación Código↔Datos (`external-data-workspace.md`), se inventariaron
todas las rutas de datos del repositorio, y se implementó un componente
mínimo (`DataWorkspace`, en `src/core/`) que resuelve rutas contra un
workspace externo configurable por variable de entorno
(`EMF_DATA_ROOT`), sin lógica de Drills dentro del Core. Drills se adaptó
mínimamente: solo la ruta del CSV histórico de comparación (la que causó
el incidente) pasa a resolverse contra el workspace externo, con
compatibilidad total cuando no está configurado. 23 tests nuevos, todos en
verde; la suite completa pasa de 451 a **474 passed, 7 skipped** (mismos
skips de siempre). No se creó el workspace real, no se movieron ni
recuperaron datos, no se ejecutó SQL Server. **Solo se hizo el commit
autorizado del checklist** — el resto de esta implementación queda
preparada, probada y documentada, pendiente de tu aprobación para
commitear (ver § 20-diferido y la propuesta de commits al final).

---

## 2. Contexto del incidente

Ver `docs/07-developer-guide/local-data-recovery-checklist.md` § 0: el
26-27/07/2026, una operación de limpieza de historial (`git filter-repo`)
necesaria para publicar el repositorio eliminó, tanto del historial como
del disco local, el contenido de `inputs/_incoming_claude_web/` — ETL,
CSV reales de Enablon, mappings y errores que el usuario había
incorporado manualmente tras el traslado del proyecto desde Claude Web a
Claude Code. La causa raíz: nunca debió haber datos reales de cliente
dentro del árbol de un repositorio Git. Este sprint resuelve esa causa
raíz de forma permanente.

---

## 3. Objetivos

1. Finalizar y versionar el checklist de recuperación — ✅ hecho y
   publicado (commit `f0a4038`).
2. Diseñar formalmente la separación código/datos — ✅
   `external-data-workspace.md`.
3. Preparar el Framework para una raíz de datos externa — ✅
   `DataWorkspace` + `config/data_workspace.yaml`.
4. No depender de rutas absolutas específicas del equipo — ✅ verificado
   por inspección, ninguna ruta de este equipo en `src/core/`.
5. Mantener compatibilidad de Drills — ✅ verificado por suite completa
   en verde.
6. No ejecutar SQL Server ni exportaciones reales — ✅ cumplido.
7. No recuperar ni generar archivos reales automáticamente — ✅ cumplido,
   ningún archivo de datos fue movido, copiado ni descargado.

---

## 4. Estado inicial

```
rama:      feature/drills-filtered-exports
remoto:    https://github.com/eduardovelasquezl/enablon-migration-framework.git
tag:       framework-core-v1 (existente, apunta a d55f4c2)
tests:     451 passed, 7 skipped
pendiente: docs/07-developer-guide/local-data-recovery-checklist.md (único fichero sin trackear)
```

Todo confirmado exactamente como se esperaba antes de modificar nada.

---

## 5. Checklist versionado

`docs/07-developer-guide/local-data-recovery-checklist.md` ampliado con:
ruta recomendada actualizada (`C:\Users\EduardoVelásquez\Desktop\
Migracion_Enablon_Data\`, marcada explícitamente como ejemplo
configurable, no fija); estructura por finalidad (`ETL/CSV_Enablon/
Mappings/Catalogs/Errors/Evidence/SQL/Outputs/Archive`, los `Bloque1..7`
quedan solo como referencia histórica en el inventario); nueva sección
"Datos versionables y no versionables"; nueva sección "Arquitectura
Código↔Datos"; nota sobre campos `CS_`; `Status: Implemented`.
**Commit `f0a4038`, ya publicado** (`git push origin
feature/drills-filtered-exports` exitoso, hash remoto verificado idéntico
al local).

---

## 6. Arquitectura Código ↔ Datos

```
Repositorio Git (versionado)          Workspace externo (NO versionado)
enablon-migration-framework/          Migracion_Enablon_Data/
  src/, tests/, config/, docs/          projects/moeve/
                                           ETL/ CSV_Enablon/ Mappings/
                                           Catalogs/ Errors/ Evidence/
                                           SQL/ Outputs/ Archive/
```

Estructura **por proyecto** recomendada explícitamente (frente a la
alternativa plana) por escalabilidad hacia un segundo cliente futuro —
justificación completa en `external-data-workspace.md` § 5.1. Detalle
completo del diseño en ese mismo documento (20 secciones, ver Fase 3 del
encargo).

---

## 7. Inventario de rutas actuales

| Archivo | Ubicación | Ruta actual | Tipo | Riesgo | Recomendación | Cambio en esta fase |
|---|---|---|---|---|---|---|
| `pipeline.py:68-69` (antes del cambio) | Constante Python | `inputs/_incoming_claude_web/Bloque4_CSV_Enablon/Drills-22072026-41.csv` | Dato real hardcodeado en código | **Alto** — apuntaba a la carpeta ya eliminada; único caso de ruta de dato real en código, no en config | Resolver vía `DataWorkspace` | **Sí** — adaptado (§ 9) |
| `drills.yaml:72` | Config YAML | `entity_catalog_csv: "inputs/entity_catalog/..."` | Dato real, ruta en config | Medio — ya gitignored, nunca estuvo en el historial | Candidato a migrar al workspace externo en una fase futura | No |
| `settings.yaml` → `folders.*` | Config YAML | `inputs/etl`, `inputs/csv_enablon`, `inputs/mappings`, `inputs/entity_catalog`, `inputs/incidents` | Rutas internas del repo, ya gitignored por carpeta | Bajo | Sin cambio necesario ahora | No |
| `settings.yaml` → `folders.outputs` | Config YAML | `outputs` | Artefactos generados (no dato de cliente recibido) | Bajo | Sin cambio | No |
| `core_adapters.py:71`, `pipeline.py:396` | Constante Python | `PROJECT_ROOT / "outputs" / "prototype" / "drills"` | Directorio de salida de ejecuciones locales | Bajo — ya gitignored | Sin cambio | No |
| `validation_rules.yaml:92` | Comentario YAML | Mención textual a `inputs/entity_catalog/` | Documentación, no ejecutable | Nulo | Sin cambio | No |
| `volumetry.py:31`, `mapping_coverage.py:28`, `mappings.py:6` | Docstrings/comentarios | Menciones textuales a `inputs/` | Documentación | Nulo | Sin cambio | No |
| `drills-operational-mvp.md` | Documentación | Menciones a `inputs/_incoming_claude_web/` (Sprint 5, ya desactualizado tras el incidente) | Documentación | Bajo | Actualizar en una fase futura (fuera de alcance aquí) | No |
| `test_evidence_engine.py:138` | Fixture de test | Cadena ilustrativa `"inputs/.../Drills-...csv"` | Dato de prueba, no ruta real de FS | Nulo | Sin cambio | No |
| `.gitignore` | Config | Reglas por carpeta `inputs/*` + `inputs/_incoming_claude_web/` | Protección | Gestionado, reforzado en esta fase | Añadir BAK/ZIP/carpeta workspace accidental | **Sí** — ampliado (§ 11) |

Ninguna ruta absoluta de un equipo concreto (`C:\Users\...`) se encontró
en `src/` ni `config/` — confirmado por búsqueda (`grep -rl "C:\\\\"`
solo encuentra binarios `.pyc`, irrelevantes).

---

## 8. Configuración propuesta

`config/data_workspace.yaml` (nuevo, sin ninguna ruta real):

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

Decisión: YAML mínimo dedicado (no una sección más dentro de
`config/settings.yaml`, que es semánticamente para rutas internas del
repo) — justificado en `external-data-workspace.md` § 11.

---

## 9. Componente de resolución

`src/core/data_workspace.py::DataWorkspace` — vive en `src/core/` (no
conoce Drills, verificado por inspección de imports). API:

```python
resolver = DataWorkspace()  # o get_default_data_workspace()
resolver.resolve(project="moeve", category="csv_enablon",
                  relative_path="Drills.csv", required=True)
```

Garantías implementadas y probadas: raíz vía `EMF_DATA_ROOT` (o
`root_override` para tests); nunca abre/lee archivos; nunca crea
directorios; rechaza rutas que escapan de la categoría vía `..` o rutas
absolutas (`PathEscapesWorkspaceError`); distingue `required=True/False`;
mensajes de error claros, sin datos sensibles; soporta rutas con espacios
y Unicode (via `pathlib.Path`, sin tratamiento especial necesario).
Excepciones: `DataRootNotConfiguredError`, `UnknownProjectError`,
`UnknownCategoryError`, `PathEscapesWorkspaceError`,
`RequiredPathNotFoundError`, todas bajo `DataWorkspaceError`.

---

## 10. Integración mínima con Drills

Único cambio: `HISTORICAL_CSV_PATH` (constante apuntando dentro del repo,
causa directa del riesgo) se sustituye por
`_resolve_historical_csv_path()`, que usa `DataWorkspace` con
`required=False`. Estrategia transitoria implementada exactamente como
pedía el encargo:

1. Si `EMF_DATA_ROOT` está declarado y el fichero existe en el workspace
   → se usa para `comparison_report.yaml`.
2. Si no está declarado, o el fichero no está → `comparison_report.yaml`
   no se genera (idéntico al comportamiento anterior al incidente).
3. **Nunca cae de vuelta a leer un dato real dentro de `inputs/`** —
   verificado por test (`test_nunca_cae_a_inputs_incoming_claude_web`,
   inspecciona el código fuente de la función).

`entity_catalog_csv` de Drills **no se tocó** en esta fase (§ 7,
documentado como deuda técnica, no urgente).

---

## 11. Protección Git

`.gitignore` ampliado: `*.bak`/`*.BAK`, `*.zip`/`*.ZIP`,
`Migracion_Enablon_Data/`/`migracion_enablon_data/` (por si se crea
accidentalmente dentro del repo). **No** se añadió una regla genérica
para todos los `.csv`/`.xlsx` — se preservan fixtures y plantillas
versionables, tal como exigía el encargo. No se creó
`data-safety-rules.md`: su contenido habría duplicado íntegramente
`local-data-recovery-checklist.md` § 1-2 y `external-data-workspace.md`
§ 7-9 — decisión justificada explícitamente (`documentation-standards.md`
§ 8, "un documento, una responsabilidad").

---

## 12. Campos estándar y campos `CS_`

Documentado en `local-data-recovery-checklist.md` § 6 y
`external-data-workspace.md` § 15 (no duplicado dos veces con el mismo
detalle): los campos `CS_*` son personalizados de cliente, deben
declararse expresamente en plantillas/mappings/validaciones (ya así en
`config/exports/drills.yaml`), nunca aceptarse por prefijo sin contrato;
los CSV reales que los contienen viven siempre en el workspace externo.

---

## 13. Tests

23 tests nuevos:

- `tests/test_data_workspace.py` — 17 tests: data root definido/ausente/
  override, ruta relativa válida, ruta con espacios, ruta con Unicode,
  ruta requerida existente/inexistente, ruta opcional inexistente, escape
  con `..`, ruta absoluta rechazada, no crea directorios, proyecto
  desconocido, categoría desconocida, `root_env` configurable/por defecto.
- `tests/test_drills_data_workspace_integration.py` — 6 tests: sin
  `EMF_DATA_ROOT` no falla; con `EMF_DATA_ROOT` pero sin fichero no falla;
  con fichero presente se resuelve; nunca referencia la ruta legada
  (inspección de código fuente); pipeline completo sin workspace (sin
  `comparison_report.yaml`); pipeline completo con workspace fake (con
  `comparison_report.yaml`) — ambos casos ejercitando el pipeline real
  (con `run_query` monkeypatcheado, sin SQL real).

Ninguna dependencia de `C:\Users\EduardoVelásquez`, de SQL Server, ni
escritura fuera de `tmp_path`.

---

## 14. Resultados

```
.venv/Scripts/python.exe -m pytest -q
474 passed, 7 skipped in 9.55s
```

451 (previos) + 23 (nuevos) = 474. Los 7 `skipped` son los mismos de
siempre (integración opt-in contra SQL real). Sin fallos.

---

## 15. Compatibilidad

- `python main.py export drills ...` funciona exactamente igual —
  verificado por la suite completa (incluye los tests de regresión ya
  existentes de Sprint 6 que comparan Core vs. `pipeline.run()` directo).
- Sin `EMF_DATA_ROOT` declarado, el comportamiento es idéntico al de
  antes de este sprint (comparación opcional omitida).
- Ninguna firma pública existente cambió — `pipeline.run()` no ganó
  parámetros nuevos en esta fase (a diferencia de Sprint 6); el único
  cambio es interno a la función.

---

## 16. Archivos creados

- `docs/01-architecture/external-data-workspace.md`
- `config/data_workspace.yaml`
- `src/core/data_workspace.py`
- `tests/test_data_workspace.py`
- `tests/test_drills_data_workspace_integration.py`
- `reports/executions/2026-07-27/Informe-Workspace-Separation-EMF.md` (este informe) y `.txt`

(`docs/07-developer-guide/local-data-recovery-checklist.md` ya se creó y
**commiteó** en la Fase 2, no se repite aquí como "nuevo" de esta lista.)

## 17. Archivos modificados

- `docs/07-developer-guide/local-data-recovery-checklist.md` (Fase 1, ya
  commiteado y publicado)
- `.gitignore` (reglas BAK/ZIP/workspace accidental)
- `.env.example` (`EMF_DATA_ROOT` de ejemplo, sin valor real)
- `README.md` (nota opcional sobre `EMF_DATA_ROOT` en § 3)
- `docs/07-developer-guide/getting-started.md` (enlace a los dos
  documentos nuevos)
- `src/core/__init__.py` (exporta los símbolos de `data_workspace.py`)
- `src/export/prototype/drills/pipeline.py` (adaptación de
  `HISTORICAL_CSV_PATH`, § 10)

**Todos los de esta lista (salvo el checklist, ya commiteado) siguen sin
commitear** — preparados, probados y documentados, a la espera de tu
aprobación (§ 20).

---

## 18. Deuda técnica

1. `entity_catalog_csv` de Drills no se migró al workspace externo (bajo
   riesgo, nunca estuvo en el historial de Git) — candidato futuro.
2. Relación entre `outputs/` local (por ejecución) y la categoría
   `outputs`/`archive` del workspace externo no está automatizada —
   decisión de implementación futura.
3. `config/data_workspace.yaml` con categorías fijas por proyecto — si un
   proyecto futuro necesita una categoría nueva, hoy exige editar el YAML
   a mano; aceptado con un único proyecto real (principio 8).
4. Sin aviso proactivo al arrancar la CLI si `EMF_DATA_ROOT` no está
   declarado — comportamiento perezoso deliberado (solo falla cuando algo
   intenta resolver una ruta real).
5. `docs/01-architecture/drills-operational-mvp.md` (Sprint 5) sigue
   mencionando la ruta legada `inputs/_incoming_claude_web/` como parte de
   un hallazgo histórico — desactualizado tras el incidente, no
   actualizado en esta fase (fuera del alcance estricto del encargo).

---

## 19. Riesgos

- El diseño del workspace externo no se ha probado todavía con un
  workspace real (nunca creado, por instrucción explícita) — validado
  solo con `tmp_path` fake en tests.
- Si en el futuro se declara `EMF_DATA_ROOT` apuntando por error dentro
  del propio repositorio, `DataWorkspace` no lo detecta ni lo impide
  (fuera del alcance de este componente, que solo resuelve rutas) — la
  protección real es la regla de `.gitignore` (§ 11) y la disciplina
  documentada en el checklist.
- La estructura `projects/<project>/` asume, sin haberlo verificado
  todavía con un segundo proyecto real, que el esquema de categorías
  (`etl`/`csv_enablon`/.../`archive`) generaliza bien — riesgo aceptado
  deliberadamente (principio 8).

---

## 20. Acciones manuales pendientes

- El usuario recuperará manualmente los ETL, CSV de Enablon, mappings,
  errores y documentación desde sus fuentes originales (Descargas, Teams,
  SharePoint, OneDrive, correo, carpetas del cliente, sesión original de
  Claude Web) — no se ha intentado ni simulado ninguna recuperación
  automática.
- Cuando se recuperen archivos, se registran en la tabla de
  `local-data-recovery-checklist.md` § 5.
- El workspace real (`C:\Users\EduardoVelásquez\Desktop\
  Migracion_Enablon_Data\` o la ruta que el usuario prefiera) no se ha
  creado — queda pendiente de creación manual antes de que
  `EMF_DATA_ROOT` tenga algún efecto real.
- **Revisar y aprobar los commits propuestos** (§ 21) antes de que se
  ejecuten — ninguno de los cambios de esta fase (salvo el checklist) se
  ha commiteado todavía.

---

## 21. Propuesta de commits (no ejecutados, a la espera de tu aprobación)

Dado que los cambios de esta fase tocan capas distintas (Core, Drills,
documentación, protección Git), se proponen **tres commits separados**,
en este orden:

**Commit A — Core: workspace externo de datos**
```
feat(core): add external data workspace resolver

- add DataWorkspace component (src/core/data_workspace.py)
- add config/data_workspace.yaml (category declarations, no real paths)
- resolve paths via EMF_DATA_ROOT, never hardcoded in the Core
- prevent path escape via '..' or absolute relative_path
- add unit tests (17 new)
```
Archivos: `src/core/data_workspace.py`, `src/core/__init__.py`,
`config/data_workspace.yaml`, `tests/test_data_workspace.py`.

**Commit B — Drills: adaptación al workspace externo**
```
fix(drills): resolve historical CSV from external workspace, not repo

- replace hardcoded HISTORICAL_CSV_PATH with DataWorkspace resolution
- comparison remains optional; no silent fallback to repo-local data
- add integration tests (6 new)
```
Archivos: `src/export/prototype/drills/pipeline.py`,
`tests/test_drills_data_workspace_integration.py`.

**Commit C — Documentación y protección del repositorio**
```
docs(data): document workspace architecture and harden .gitignore

- add external-data-workspace.md (full design)
- update .gitignore (BAK/ZIP/accidental workspace folder)
- update .env.example with EMF_DATA_ROOT example
- add minimal notes in README.md and getting-started.md
```
Archivos: `docs/01-architecture/external-data-workspace.md`,
`.gitignore`, `.env.example`, `README.md`,
`docs/07-developer-guide/getting-started.md`.

Ningún commit incluye push automático — a la espera de tu aprobación
explícita, tanto de los commits como del push.

---

## 22. git diff --check

```
exit=0 (solo avisos de normalización LF→CRLF, sin errores)
```

## 23. git status --short

```
 M .claude/settings.local.json   (auto-gestionado por Claude Code, no se toca)
 M .env.example
 M .gitignore
 M README.md
 M docs/07-developer-guide/getting-started.md
 M src/core/__init__.py
 M src/export/prototype/drills/pipeline.py
?? config/data_workspace.yaml
?? docs/01-architecture/external-data-workspace.md
?? src/core/data_workspace.py
?? tests/test_data_workspace.py
?? tests/test_drills_data_workspace_integration.py
```

## 24. git diff --stat

```
 .claude/settings.local.json                |  5 +++-
 .env.example                               |  9 +++++++
 .gitignore                                 | 15 +++++++++++
 README.md                                  |  7 +++++
 docs/07-developer-guide/getting-started.md |  8 ++++++
 src/core/__init__.py                       | 18 +++++++++++++
 src/export/prototype/drills/pipeline.py    | 43 ++++++++++++++++++++++++++----
 7 files changed, 99 insertions(+), 6 deletions(-)
```

---

## Recomendación del siguiente paso

Revisar y aprobar (o pedir cambios sobre) la propuesta de tres commits de
§ 21. Tras la aprobación: commitear en ese orden, ejecutar la suite
completa una vez más, y hacer push normal (sin force) de
`feature/drills-filtered-exports` — sin crear ni mover el tag
`framework-core-v1` (sigue apuntando correctamente a `d55f4c2`, sin
relación con este sprint). Después de eso, la siguiente prioridad real
del proyecto sigue siendo la recuperación manual de los datos originales
(§ 20), no más trabajo de arquitectura — el Framework ya está preparado
para recibirlos.
