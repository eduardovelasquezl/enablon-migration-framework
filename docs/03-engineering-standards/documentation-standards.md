# Documentation Standards — EMF

**Status:** Approved Design.

## 1. Todo documento declara su estado

Cada documento de `docs/00-blueprint/` a `docs/08-user-guide/`, y cada
componente descrito dentro de ellos, lleva uno de estos cuatro estados,
igual que ya exige
[`docs/architecture/v1.0/README.md`](../architecture/v1.0/README.md#estado-de-cada-elemento-documentado)
legado:

- **Implemented** — existe en `src/`, con tests que lo cubren.
- **Approved Design** — aprobado explícitamente, no implementado todavía.
- **Planned** — previsto, sin diseño detallado aprobado todavía.
- **Out of Scope** — descartado explícitamente para esta versión.

Nunca se describe una capacidad futura sin marcarla como tal — un lector
nuevo no debe poder confundir "está diseñado" con "está implementado".

## 2. Dos secuencias de documentación arquitectónica, no confundir

- `docs/architecture/v1.0/` (legado): arquitectura de precisión de
  implementación del **primer proyecto** (Moeve, previo a EMF). No se
  reescribe ni se retira al introducir `docs/00-blueprint/`…`08-user-guide/`
  — sigue siendo la referencia correcta para lo que existe hoy en
  producción.
- `docs/00-blueprint/` a `docs/08-user-guide/` (EMF): visión de
  **producto/plataforma**. Sus ADR (`docs/02-adr/`) no son una numeración
  independiente — comparten un único espacio de numeración con
  `docs/architecture/v1.0/decisions/` (legado) en todo el repositorio, y
  continúan el consecutivo justo después del número legado más alto (ver
  [`02-adr/README.md`](../02-adr/README.md) para el índice completo). Los
  documentos en sí (Blueprint, arquitectura, roadmap...) sí son un conjunto
  documental separado del legado — lo que nunca se duplica ni se
  independiza es la numeración de ADR.

Todo documento nuevo que referencie arquitectura debe dejar explícito a
cuál de las dos secuencias documentales pertenece cada afirmación, y
consultar [`02-adr/README.md`](../02-adr/README.md) antes de asignar un
número de ADR nuevo.

## 3. Terminología homogénea

Se usa siempre la tabla de terminología del
[Blueprint](../00-blueprint/emf-blueprint-v1.0.md#terminología--no-confundir):
Core / Engine / Connector / Plugin / módulo de Enablon / Configuración de
proyecto / objeto migrable / plantilla de destino, sin sinónimos
intercambiables no declarados. En particular, fuera del sentido estricto de
Python (un fichero `.py` individual — uso ya establecido en
`naming_conventions.md` legado), "módulo" nunca designa un componente de
software (Connector, Engine, paquete completo) — se reserva para un módulo
de negocio de Enablon (Simulacros, MOC, Bypass...).

## 4. Enlaces relativos, verificados antes de cerrar cualquier cambio

Todo enlace entre documentos de `docs/` es relativo a la ubicación del
fichero que enlaza, nunca una ruta absoluta ni una URL — el conjunto debe
poder clonarse y leerse sin conexión. Antes de cerrar cualquier incremento
que toque documentación, se revisan manualmente los enlaces nuevos o
modificados (no existe todavía una herramienta automatizada de verificación
de enlaces en este repositorio — se propone como mejora futura, ver
Roadmap).

## 5. Sin información sensible

Ningún documento de `docs/` incluye credenciales, cadenas de conexión,
hosts reales, tokens, ni datos personales identificables — ni siquiera como
ejemplo "ilustrativo" con apariencia de real. Los ejemplos de configuración
usan siempre placeholders (`<host>`, `<usuario>`) o, cuando haga falta un
ejemplo concreto, datos ya públicos en este mismo repositorio (nombres de
conexión lógicos como `prevencion`/`gct`, nunca hosts).

## 6. Idioma

La documentación de producto de EMF, igual que el resto del repositorio, se
escribe en español — coherente con `CLAUDE.md`,
`docs/architecture/v1.0/` y `README.md`. Los nombres de componentes de la
arquitectura (Core, Engine, Connector, Plugin) se mantienen en inglés por
ser la convención ya establecida en el propio Blueprint y en el vocabulario
del proyecto (Query Engine, Evidence Engine).

## 7. Formato de ADR

Toda ADR nueva sigue el formato ya establecido por
`docs/architecture/v1.0/decisions/`: título `# ADR-NNN — Título`, línea
`**Status:**`, secciones `## Context`, `## Decision`, `## Consequences`,
`## Alternatives Rejected`. No se introduce un formato distinto sin
justificarlo.

## 8. Un documento, una responsabilidad

Cada fichero de `docs/` tiene una responsabilidad clara y no duplicada —
si dos documentos necesitan explicar lo mismo, uno de los dos enlaza al
otro en vez de repetir el contenido (aplicado en todo este conjunto: el
Blueprint resume y enlaza a `01-architecture/`, `02-adr/`,
`03-engineering-standards/`, nunca repite su contenido íntegro).
