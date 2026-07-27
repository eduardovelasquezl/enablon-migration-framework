# Release Strategy — EMF

**Status:** Approved Design (estrategia documental; no existe todavía
ningún mecanismo de release/paquete real — no hay `pyproject.toml`,
`setup.py` ni publicación de ningún tipo en el repositorio hoy).

## 1. Cuatro ejes de versión, no confundir

Extensión directa de la tabla ya vigente en
[`docs/architecture/v1.0/README.md`](../architecture/v1.0/README.md#versionado--cuatro-conceptos-distintos-no-confundir),
con un eje nuevo:

| Eje | Qué versiona | Formato | Estado |
|---|---|---|---|
| `blueprint_version` | El conjunto `docs/00-blueprint/` a `docs/08-user-guide/` | `vMAJOR.MINOR` en el nombre de fichero del Blueprint (`emf-blueprint-v1.0.md`) | **Implemented** (este documento) |
| `architecture_version` (legado) | `docs/architecture/v1.0/` | `vMAJOR.MINOR` en la ruta | Implemented, no se toca |
| `application_version` / `FrameworkVersion` | El software del Core | SemVer (`MAJOR.MINOR.PATCH`), fuente única en `src/core/version.py` | Planned (diseñado en Sprint 4.1, no implementado) |
| `template_version` | Cada entrada del Enablon Template Registry | A definir cuando el Registry se diseñe en detalle | Planned |

No existe todavía un `application_version` publicado — cuando `src/core/`
se implemente, `1.0.0` será su primer valor, coherente con este Blueprint
v1.0.

## 2. Qué significa "1.0" en `emf-blueprint-v1.0.md`

Es la primera versión **aprobada** de la visión de producto, no una
afirmación de que el producto está terminado o implementado al 100%. La
mayoría de los componentes descritos en ella son "Approved Design" o
"Planned" — ver el estado explícito de cada uno en
[`architecture-overview.md`](../01-architecture/architecture-overview.md).
Subir a `v1.1`/`v2.0` el Blueprint requiere un cambio de alcance o de
principios, no simplemente que se implemente más código (eso se refleja en
`application_version`, no en `blueprint_version`).

## 3. Cuándo se crea un release

No se define todavía un proceso formal de release/tag/publicación — es
explícitamente prematuro sin un mecanismo de empaquetado (`pyproject.toml`)
ni un segundo consumidor del Core. Este documento fija la **intención**:
cuando exista `application_version`, un release correspondería a un
`FrameworkVersion` estable con su propio changelog, siguiendo SemVer
(cambio de `MAJOR` = rotura de compatibilidad de la API pública del Core/
Engines; `MINOR` = capacidad nueva compatible; `PATCH` = corrección sin
cambio de API).

## 4. Compatibilidad entre versiones del Core y Plugins

Principio, no mecanismo implementado: un Plugin construido contra
`FrameworkVersion 1.x` debe seguir funcionando contra cualquier `1.y` con
`y >= x` (compatibilidad hacia adelante dentro del mismo `MAJOR`). Cómo se
verifica esto en la práctica (¿un campo de compatibilidad declarado en
`ObjectMetadata`? ¿un chequeo en el `ObjectRegistry`?) no está diseñado
todavía — se define cuando exista un segundo Plugin real que permita
validar el mecanismo contra un caso concreto (principio 8).

## 5. Relación con el changelog existente

[`docs/changelog/architecture_changelog.md`](../changelog/architecture_changelog.md)
ya documenta el historial de `docs/architecture/v1.0/` (legado). Este
conjunto documental (`docs/00-blueprint/` a `docs/08-user-guide/`) inicia
su propio historial cuando reciba su primera revisión posterior a esta
versión inicial — no se mezcla con el changelog legado, que tiene un
alcance distinto (el primer proyecto, no la plataforma).

## 6. Sin releases automatizados todavía

No existe CI/CD en este repositorio (no se ha detectado configuración de
integración continua durante la revisión de este sprint). Cualquier
proceso de release, cuando se diseñe, empezaría siendo manual y
documentado, no automatizado — coherente con el principio 8 (no se
construye infraestructura de CI/CD sin un consumidor real que la necesite).
