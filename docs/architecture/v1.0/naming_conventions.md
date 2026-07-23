# Convenciones de nombres

Documenta las convenciones **ya en uso** en el código actual. No prescribe
cambios — los cambios previstos se marcan explícitamente como
`Future Improvement` al final y **no se han aplicado**.

## Clases y dataclasses

`PascalCase`, sustantivo singular: `MigrationObject`, `MappingDecision`,
`CrossModuleActionPlanBuffer`, `ProjectAnalysisResult`. Sin sufijos de tipo
(`...Class`, `...Object`) ni prefijos de capa.

## Enums / vocabularios cerrados

No se usa `enum.Enum` de Python — se usan clases simples con constantes de
clase en `snake_case` como valor de cadena, más un `ALL: frozenset` con todos
los valores válidos:

```
class LoadStatus:
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_WARNING = "eligible_with_warning"
    BLOCKED = "blocked"
    EXCLUDED = "excluded"
    ALL = frozenset({ELIGIBLE, ELIGIBLE_WITH_WARNING, BLOCKED, EXCLUDED})
```

El nombre de la clase es `PascalCase` (`LoadStatus`), sus miembros son
`UPPER_SNAKE_CASE` en Python pero su **valor** (lo que se persiste/compara) es
siempre `snake_case`.

## Funciones

`snake_case`, verbo en infinitivo o `make_`/`build_`/`validate_`/`resolve_`
según su rol:

- `make_*_id(...)` — constructor determinista de un identificador (nunca UUID
  aleatorio).
- `build_*(...)` — construye una entidad aplicando su tabla de decisión.
- `validate_*(...)` — devuelve una lista de violaciones (vacía si es
  consistente), nunca lanza excepción por una regla de negocio.
- `resolve_*(...)` — intenta resolver una referencia contra evidencia exacta.
- `detect_*` / `classify_*` / `analyze_*` — extraen o clasifican, sin decidir
  nada definitivo.

## Identificadores (IDs)

Formato `namespace:contexto.slugificado#fragmento`, siempre determinista:

```
module:simulacros
source_object:prevencion.dbo.itp_reunion_grupo
mapping_decision:simulacros.drills.mapeosims.<hash_corto>
cross_module_action_plan_buffer:prevencion.eventos.events.<hash_corto>
relation:<subject_id>|<relation_type>|<object_id>
```

- `:` separa el tipo de entidad del resto.
- `.` separa niveles de contexto (sistema → módulo → objeto...).
- `#` separa un fragmento posicional (fila, posición, secuencia).
- Cuando el contexto completo sería demasiado largo o con caracteres
  problemáticos, se usa un `short_hash` determinista como sufijo — nunca en
  vez del contexto, siempre además de él.

## Módulos privados

Prefijo `_` en el nombre de fichero (`_select_parser.py`, `_sheet_taxonomy.py`):
implementación interna de un único punto público (`query_analyzer.py`,
`schema_analyzer.py` respectivamente). No se importan directamente desde fuera
de su paquete.

## Ficheros de salida

- **CSV**: `snake_case.csv`, encoding `utf-8-sig` (con BOM, para abrir bien en
  Excel) cuando el CSV es una salida de análisis/diagnóstico propia del
  framework. Los CSV **reales de Enablon** ya observados varían (algunos
  UTF-16 con tabulador, otros UTF-8/Latin-1 con `;`) — eso es un hecho del
  origen, no una convención propia.
- **YAML** (`config/*.yaml`, `manifest.yaml`): claves en `snake_case`,
  minúsculas.
- **JSON** (`project_analysis_summary.json`): claves en `snake_case`, igual que
  los campos Python que representan.

## Cambios de nomenclatura previstos — `Status: Future Improvement`

Ninguno de los siguientes cambios se ha aplicado. Se documentan para que
cuando se implementen no sean una sorpresa, no como trabajo en curso.

| Actual | Propuesto | Motivo |
|---|---|---|
| `ready_for_final_load` | `ready_for_csv_generation` | Más preciso una vez exista el Export Engine: "final" hoy significa "listo para que el Export Engine lo tome", no "cargado". |

**No modificar código para aplicar este cambio** — queda registrado como
mejora futura únicamente.
