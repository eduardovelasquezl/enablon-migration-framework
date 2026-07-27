# Engineering Standards — EMF

**Status:** Approved Design (formaliza convenciones ya en uso — ver
[`naming_conventions.md`](../architecture/v1.0/naming_conventions.md)
legado, que sigue siendo la referencia de detalle de nomenclatura y no se
duplica aquí).

Este documento cubre las prácticas de ingeniería que aplican a **todo**
componente de EMF, en cualquier capa. Para seguridad y pruebas, ver los
documentos dedicados
([`security-standards.md`](security-standards.md),
[`testing-standards.md`](testing-standards.md)).

## 1. Backward Compatibility

Ningún incremento nuevo cambia el comportamiento observable de un
componente existente sin una decisión explícita (ADR si es estructural,
mención expresa en la revisión de sprint si es puntual). En concreto:

- Un cambio en el Core no puede alterar el comportamiento de Drills tal
  como existe hoy, salvo que Drills se migre deliberadamente al Core en un
  sprint dedicado a ello — nunca como efecto colateral.
- Añadir un campo a un manifiesto (`export_manifest.yaml`) es compatible;
  eliminar o renombrar un campo existente no lo es sin una migración
  explícita.
- La suite de tests existente es la definición operativa de "compatible":
  si los tests actuales siguen pasando sin modificarse, el cambio es
  compatible por definición mínima (necesaria, no suficiente).

## 2. Estructura de paquete y dirección de dependencia

Se aplica sin excepción la dirección de capas del Blueprint (Core → Engines
→ Connectors → Plugins → Project Configuration). Antes de añadir un import
`from src.X import Y`, quien escribe el código verifica que `X` está en una
capa igual o inferior a la suya. El Core, en particular, no importa nada de
`src.*` fuera de sí mismo — no solo "de las capas de negocio", ninguna
excepción, ni siquiera `src.config` (ver justificación en el informe de
diseño de Sprint 4.1).

## 3. Nomenclatura

Se hereda íntegramente
[`naming_conventions.md`](../architecture/v1.0/naming_conventions.md)
legado: clases en `PascalCase` sustantivo singular sin sufijos de tipo;
vocabularios cerrados como clases con constantes `UPPER_SNAKE_CASE` de
valor `snake_case` + `ALL: frozenset` (nunca `enum.Enum`); funciones
`snake_case` con prefijo semántico (`make_*_id`, `build_*`, `validate_*`,
`resolve_*`, `detect_*`/`classify_*`/`analyze_*`); módulos privados con
prefijo `_` (aquí "módulo" en el sentido estricto de Python — un fichero
`.py` individual, ej. `_select_parser.py` — mismo uso que ya hace
`naming_conventions.md` legado). Se añade una precisión de terminología EMF
(ver [Blueprint § Terminología](../00-blueprint/emf-blueprint-v1.0.md#terminología--no-confundir)):
fuera de ese sentido estricto de "fichero Python", nunca usar "módulo" para
referirse a un componente de software (un Connector, un Engine, un
paquete completo) — reservado para "módulo de Enablon" (Simulacros,
MOC...). Un componente de software se llama Core, Engine, Connector o
Plugin según su capa.

## 4. `validate_*` nunca lanza por regla de negocio

Convención ya vigente y que EMF hereda sin cambios: una función
`validate_*` devuelve una lista de violaciones (vacía si es válido), nunca
lanza una excepción para señalar una regla de negocio incumplida. Las
excepciones (`FrameworkError` y su jerarquía, Core Sprint 4.1) se reservan
para errores de infraestructura/programación, no de datos de negocio. Ver
[`data-processing-lifecycle.md`](../01-architecture/data-processing-lifecycle.md)
§ 4.

## 5. Identificadores

- `run_id`: identificador único de ejecución, generado aleatoriamente
  (`uuid4`), nunca determinista — no es del mismo tipo que un
  `mapping_decision:...` (esos sí son deterministas, por diseño, según
  `naming_conventions.md` legado). Ambos conceptos coexisten sin
  contradicción: un ID de contenido es determinista porque representa "el
  mismo dato produce el mismo ID"; un `run_id` representa una ejecución
  única en el tiempo, para la que la aleatoriedad es la propiedad
  correcta.
- Timestamps: siempre UTC, siempre tz-aware (`datetime.now(timezone.utc)`)
  — ya universal en el código existente, sin excepciones encontradas en la
  auditoría de Sprint 4.1.

## 6. Escritura de artefactos

Todo artefacto persistido (CSV, YAML, JSONL, SQL generada) se escribe de
forma atómica (fichero temporal + `os.replace`), nunca se sobrescribe una
ejecución anterior en silencio — patrón ya implementado
(`write_yaml_atomic`, `write_text_atomic`, `write_csv`) y obligatorio para
todo Engine nuevo.

## 7. Revisión de código y ADR

Toda decisión que cambie una regla de este documento, o que introduzca una
excepción a la dirección de dependencias de capas, requiere una ADR nueva
en [`02-adr/`](../02-adr/) antes de implementarse (principio 10) — no basta
con un comentario en el código ni con la aprobación verbal de un sprint.

## 8. Ciclo de desarrollo

Incrementos pequeños, cada uno con su propia revisión documentada (ver
[`sprint-review-template.md`](../05-sprint-reviews/sprint-review-template.md)),
suite completa en verde antes de pasar al siguiente paso, ningún cambio
fuera del alcance declarado del incremento sin aprobación explícita —
mismo patrón ya seguido en los incrementos de Query Engine v0.1 y Evidence
Engine v0.1.
