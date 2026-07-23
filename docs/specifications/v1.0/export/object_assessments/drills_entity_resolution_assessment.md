# Evaluación de resolución de entidad — simulacros.Drills

> Responde a la Tarea 7 de este incremento: búsqueda exhaustiva de la
> lógica de entidad de Drills en el ETL de Simulacros, los 2 workbooks de
> mapeo de entidad, SQL, CSV histórico, hojas lookup, hojas ocultas,
> nombres definidos, fórmulas y documentación existente. **Resultado:
> localizada**, con evidencia de fórmula directa — no queda `missing`.

## 1. Campo(s) origen

`IDUnidadOrg` (columna T de `DB_OrigenSim`) — **no** `IDCentro` (columna C,
confirmado sin destino en `MapeoSims`, fila 4: `Field Destiny XML` vacío,
`Adaptación=None`). Clave simple, no compuesta.

## 2. Mecanismo de resolución (confirmado por fórmula)

Dos pasos, ambos dentro de la propia hoja `DB_OrigenSim` (no en `MapeoSims`):

```
RutaEnablon (col U) =
  IF(IDUnidadOrg<>"",
     XLOOKUP(IDUnidadOrg, Entidades_Enablon_ITP[IDUnidadOrg], Entidades_Enablon_ITP[RutaSimple]),
     "")

Nombre Entidad (col V) =
  XLOOKUP(RutaEnablon, Entidades_Enablon_ITP[RutaSimple], Entidades_Enablon_ITP[ENABLON])
```

`Entidades_Enablon_ITP` es una **tabla Excel estructurada** (`xl/tables/table14.xml`,
rango `A1:Q681`) definida sobre la hoja `Entidades_Mapeo` del mismo
workbook — **681 filas, 17 columnas**, coincidiendo exactamente en tamaño
y forma con `inputs/entity_catalog/entidades_mapeo_ANTIGUO_referencia_historica.csv`
(el catálogo antiguo, **deprecado** según CLAUDE.md: "no usar
Entidades_Mapeo de ningún ETL individual — están todas desactualizadas y
son copias fragmentadas").

`MapeoSims` (la hoja de mapeo de CAMPO) recibe `RutaEnablon` ya resuelto y
lo pasa directamente a `CS_ImpactedEntities` (fila 44:
`RutaEnablon → CS_ImpactedEntities`, sin fórmula adicional — mapeo
directo) — es decir, la resolución de entidad ocurre **antes** de llegar a
la hoja de mapeo de campo, dentro de la propia tabla de datos de origen.

## 3. Entidad destino

`CS_ImpactedEntities` — confirmado en la cabecera real de
`Drills-22072026-41.csv` (`evidence:csv_enablon.drills`) y en `MapeoSims`
fila 44.

## 4. Clave simple o compuesta

Simple: `IDUnidadOrg` únicamente. `IDCentro` no participa en la resolución
de entidad para Drills (confirmado, no inferido — `MapeoSims` lo declara
explícitamente sin destino).

## 5. Tratamiento de NULL

Confirmado por fórmula: si `IDUnidadOrg` está vacío (`<>""` falso),
`RutaEnablon` se fija a cadena vacía `""` — no hay valor de reserva de
texto (a diferencia de otros campos del mismo workbook, que sí usan textos
de reserva como "No name defined in historical data"). Consecuencia: un
registro con `IDUnidadOrg` vacío produciría `CS_ImpactedEntities` vacío,
no un error ni un texto de marcador.

**observado en un workbook hermano** (no en Simulacros): `ITP-EVENTOS_OLDv2`
y `ITP-SM-DBC` (Eventos Antiguos y Safety Meetings, mismo mecanismo de
resolución) SÍ tienen un texto de reserva confirmado para `IDUnidadOrg`
nulo: `"Unidad organizativa es Null"` — aparece literalmente en la columna
`RutaEnablon` cacheada de esos workbooks cuando el lookup no puede
resolver. **No se ha confirmado si Simulacros comparte este mismo texto de
reserva** o simplemente deja la cadena vacía — la fórmula de `DB_OrigenSim`
en Simulacros no incluye ese texto explícitamente en la muestra leída.

## 6. "No migra"

No se observó ningún caso de `RutaEnablon` o `CS_ImpactedEntities`
resolviendo a "No migra" en la muestra de `DB_OrigenSim` leída (7 filas) —
a diferencia de `eventos.Events` (nuevos), donde SÍ se observó literalmente
el valor `'No migra'` en la columna `Entity` de una fila real de
`CSV-EVT-2026-FULL` (ver `etl_deep_analysis.md`). No se descarta que
existan filas "No migra" en Simulacros fuera de la muestra de 7 filas
leída (de 12502 totales).

## 7. Fallback / default

Cadena vacía (`""`) para `IDUnidadOrg` nulo — ver §5. No se identificó
ningún otro fallback (p. ej. un valor de entidad por defecto) en la
fórmula confirmada.

## 8. Conflicto

**Conflicto de fondo, no de fórmula**: el mecanismo usa el catálogo
`Entidades_Enablon_ITP` (= `Entidades_Mapeo`, deprecado) en vez del
catálogo real resuelto y validado
(`inputs/entity_catalog/catalogo_resuelto_code_ruta_site.csv`). Para
Simulacros esto está **explícitamente aceptado** en
`config/modules.yaml:84`: *"IDUnidadOrg (resuelto a RutaEnablon/Code vía
catálogo antiguo, esquema histórico -XXH, correcto para su época)"* — es
decir, **no es un hallazgo nuevo de riesgo**, es la confirmación a nivel
de fórmula de una decisión ya documentada y aceptada como correcta para
este módulo específico. Se registra como `evidence_status: confirmed`, no
como conflicto abierto, precisamente porque ya existía una nota
explicativa previa que este incremento corrobora.

## 9. Registros sin mapping

No cuantificado en este incremento — requeriría recorrer las 12502 filas
de `DB_OrigenSim` completas (fuera de alcance de la muestra de 2-8 filas
usada). La cifra de volumetría ya conocida (`config/modules.yaml:89-93`,
gap de -4.6%, "sano") no atribuye el gap a fallos de resolución de
entidad — pero tampoco lo descarta explícitamente por site (recordar
Hallazgo #1: `simulacros` sigue en la lista de `modulos_pendientes_de_
revisar` de `config/modules.yaml:71`).

## 10. Estado final

```
trace_status: fully_traced
mapping_status: mapped
```

Se cumplen los 5 requisitos de `fully_traced` fijados por la Tarea 6/7 de
este incremento: campo SQL/fuente confirmado (`IDUnidadOrg`), transformación
confirmada (2-step XLOOKUP contra `Entidades_Enablon_ITP`), columna de
salida ETL confirmada (`RutaEnablon`), columna CSV confirmada
(`CS_ImpactedEntities`, verificada contra el CSV real), y relación con
evidencia ya documentada confirmada
(`config/modules.yaml:84`, coincide sin contradicción).

**Esto NO implica que Reference y entidad se resuelvan juntas** — son
mecanismos completamente independientes dentro del mismo workbook (ver
`decision_packages/drills_reference_decision_package.md` para Reference).

## 11. Preguntas abiertas

- **`OQ-ENT-04`** (nueva): ¿es igualmente aceptable, para `bypass`,
  `eventos_antiguos`, `ops` y `safety_meetings`, depender del catálogo
  `Entidades_Enablon_ITP` embebido (deprecado) para la resolución de
  entidad, tal como ya está aceptado explícitamente para `simulacros`? No
  hay una nota equivalente a `config/modules.yaml:84` para esos otros
  módulos.
- **Texto de reserva para `IDUnidadOrg` nulo en Simulacros** (§5): no
  confirmado si existe (como en Eventos/Safety Meetings) o si de verdad
  resuelve a cadena vacía — pendiente de leer más filas de `DB_OrigenSim`
  con `IDUnidadOrg` nulo.

## 12. Limitaciones

- Basado en una muestra de 2-10 filas de `DB_OrigenSim`/`MapeoSims`, no en
  las 12502 filas completas.
- No se ha inspeccionado la tabla `Entidades_Enablon_ITP` fila a fila para
  confirmar cuántos códigos `IDUnidadOrg` de Simulacros específicamente
  fallan el primer `XLOOKUP` — solo se confirmó su tamaño (681 filas) y su
  identidad con el catálogo deprecado ya conocido.
- No se ha cruzado esta fórmula contra `inputs/entity_catalog/catalogo_
  resuelto_code_ruta_site.csv` para medir cuántas de las rutas resueltas
  por el mecanismo antiguo coinciden o difieren de las del catálogo
  validado.
