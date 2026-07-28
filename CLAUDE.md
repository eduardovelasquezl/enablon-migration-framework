# Migración Histórica a Enablon — Contexto del Proyecto

Este documento es la memoria persistente del proyecto. Léelo antes de tocar nada.
Refleja el análisis manual acumulado sobre 9 módulos + 2 ETL de Acciones, hecho
antes de escribir una sola línea de este código. Todo lo de aquí está verificado
contra ETL reales, CSV reales exportados de Enablon, queries SQL reales y el
catálogo real de entidades de Enablon — no es especulación.

## Objetivo

Sustituir el proceso actual de migración histórica (ETL en Excel, pesado y lento,
con dependencias frágiles) por un motor Python repetible, auditable y más rápido.
Este repo NO ejecuta cargas contra Enablon ni escribe en el SQL de origen — es
analítico y de generación de CSV. La carga final a Enablon sigue siendo manual
o vía API, fuera de este repo, al menos por ahora.

## Restricciones (heredadas del proyecto original — no negociables)

- **Nunca** se modifica el BAK ni se ejecuta INSERT/UPDATE/DELETE contra el SQL origen.
- Todo acceso SQL es de solo lectura.
- **El entorno de desarrollo puede disponer de conectividad SQL real** (usuario
  readonly `ClaudeReadOnly`) — **la disponibilidad de credenciales NUNCA implica
  autorización de uso**. Todo acceso SQL real (`python main.py run` / `export
  drills`, en modo `sample` o `full`) requiere autorización técnica explícita
  del usuario para esa ejecución concreta (`--allow-real-sql` /
  `EMF_ALLOW_REAL_SQL=1`, bloqueado por defecto — ver
  `docs/01-architecture/sql-execution-guard.md`). Nunca ejecutar un comando que
  pueda tocar SQL real sin haber confirmado antes con el usuario que esa
  ejecución concreta está autorizada, incluso si la CLI lo permitiría técnicamente.
- Nunca se inventan reglas de negocio no documentadas — si algo no está claro
  (p. ej. qué hace `titlefix` exactamente), se marca como pendiente de confirmar,
  no se asume.
- Toda propuesta de cambio debe ser reversible y trazable.

## Arquitectura de carpetas

- `config/` — definición declarativa de módulos, bases de datos y reglas de validación.
- `src/db/` — conexión SQL de solo lectura y ejecución de queries.
- `src/analysis/` — réplica en código de los análisis que hicimos a mano
  (inventario de ETL, revisión de queries, volumetría, duplicados, calidad de datos).
- `src/etl/` — el motor de transformación real: lee hojas de mapeo (`DatoOrigen /
  DatoDestino / EsCondicion / ReglaEspecial / Parametro`) y aplica las reglas.
- `sql/` — queries de extracción por módulo (`source_queries/`, tal cual las dio
  el cliente), queries de diagnóstico que generemos nosotros (`diagnostics/`), y
  SQL generado por el motor (`generated/`).
- `inputs/` — todo lo que el usuario deposita: ETL Excel, CSV reales de Enablon,
  ficheros de mapeo, el catálogo de entidades, el documento de incidencias.
- `outputs/` — todo lo que genera el motor: inventarios, revisiones de query,
  volumetría, calidad de datos, CSV transformados, informes.

## Catálogo de entidades — YA RESUELTO

**No usar `Entidades_Mapeo` de ningún ETL individual — están todas desactualizadas
y son copias fragmentadas, cada módulo con la suya.**

Fuente de verdad: `inputs/entity_catalog/` debe contener el export real de Enablon
(`First_Axis`, columnas `Parent`/`Code`/nombres/`EntityStatus`). A partir de `Parent`
+ `Code` se reconstruye la ruta completa (`Ruta1`). El "site" (`Centro`) de cada
entidad se resuelve cruzando contra las 162 asociaciones Código→Centro conocidas
de los catálogos antiguos, con fallback de mayoría por prefijo de nivel 3 para las
ramas no cubiertas directamente.

Resultado ya validado: aplicado a Safety Meetings, MOC y Bypass, pasa de 42-59%
de códigos "no catalogados" a 0%. Simulacros no lo necesita (usa el esquema
antiguo de sufijo "-XXH", ya retirado del árbol vigente, pero correcto para su
momento — su migración ya está cerrada).

**IMPORTANTE — dos sistemas de origen usan numeraciones de `IDCentro` DISTINTAS
e incompatibles entre sí:**
- Sistema ITP/Prevención (Simulacros, SM, Eventos, Inspecciones, OPS): `IDCentro`
  propio, ver `config/modules.yaml` → `idcentro_map_itp`.
- Sistema GCT (MOC): `IDCentro` propio y diferente. Ver `config/modules.yaml` →
  `idcentro_map_gct`. Ejemplo: `IDCentro=17` es "Tenerife" en ITP pero "La Rábida"
  en GCT. **Nunca cruzar `IDCentro` de un sistema contra el otro sin traducir
  primero por nombre de site.**

## Hallazgo #1 del proyecto — pendiente de resolver, máxima prioridad

**Servicio Prevención LA RÁBIDA y MC-Palos de la Frontera tienen infra-migración
sistemática**, confirmada de forma independiente en Eventos, Inspecciones y MOC
(dos sistemas de origen distintos, ITP y GCT):

| Site | % típico en origen SQL | % típico en Enablon real |
|---|---:|---:|
| La Rábida | 20-35% | 0,1-3% |
| Palos de la Frontera | 12-45% | ~0-1% |

Mientras que las entidades con rollback conocido (San Roque/Algeciras, Site
Canarias, Puente Mayorga, CCE) están completas o sobre-representadas — el
rollback NO explica el problema, lo enmascaraba.

**No des por buena ninguna cifra de volumetría de un módulo nuevo sin desglosarla
por site** — un total agregado sano puede esconder este patrón exactamente igual
que lo escondió al principio en Simulacros/SM/Bypass.

## Rollbacks de producción conocidos (confirmados por el cliente)

BAK de corte recibido y recargado para: `ENERGYP.SR` (San Roque), `ENERGYP.CAN`
(Site Canarias), `MCHEM.MCPM` (Puente Mayorga), `CCE`, `CCE.05` (Biocombustibles).
Las entidades marcadas `No migra` en los mapeos nunca se cargan (por diseño, no
es un error).

## Catálogo de reglas del motor de transformación

Toda hoja de mapeo del ETL original sigue uno de estos dos patrones:
1. Mapeo de campo: `CampoOrigen | Field Destiny XML | Field Destiny ES | Adaptación
   (Sí/No) | Transformation From | ... | XML | ES`
2. Regla de traducción: `DatoOrigen | DatoDestino | EsCondicion | ReglaEspecial | Parametro`

Reglas confirmadas (normalizar nombre, case-insensitive — aparecen escritas de
formas distintas en cada módulo):

| Regla | Comportamiento | Confirmado con datos reales |
|---|---|---|
| `nullcontrol` | Sustituye NULL por un valor destino por defecto | Sí |
| `concat` / `barconcat` | Concatena 2-4 campos origen en un destino, separador variable (`\|` en `barconcat`) | Sí |
| `titlefix` / `Titlefix` | Al menos hace *stripping* de comillas dobles (`"`) — verificado en MOC, 76/5207 casos, pierde el significado de pulgadas (`8"`→`8`). **No tiene motor visible en ningún Excel ni VBA de los 7 libros auditados** — se aplica por un proceso externo no documentado. Preguntar al cliente quién/qué lo ejecuta. | Parcial |
| `cloneorigin` | Passthrough directo; variante *fan-out* clona a 5 idiomas (`EN/FR/ES/ZH/BR`) simultáneamente | Sí |
| `replaceinreference` | Sustitución vía tabla de referencia cruzada | No verificado con datos reales aún |
| `boolorigin` | Convierte un flag Sí/No de origen en un valor categórico usando una tabla de referencia adicional | No verificado con datos reales aún |
| Lookup simple | Diccionario `DatoOrigen→DatoDestino` 1:1 | Sí |
| Lookup dinámico en 2 pasos contra catálogo "en vivo" | Resuelve código→descripción y descripción→Id vigente de Enablon | Visto en SM/MOC — mejor patrón, preferible al lookup estático |

## Registro de módulos — ver `config/modules.yaml` para el detalle estructurado

Simulacros, Safety Meetings, MOC, Bypass, Eventos (antiguos+nuevos+PSM), OPS,
Inspecciones, Acciones (AP_GCT + AP-Con Ajuste Entidad, transversal — se
alimenta de una única tabla `ITP_Acciones_correctoras` clasificada por
`idorigenac`, uno por módulo origen).

## Defectos sistémicos ya confirmados (no relacionados con el hallazgo #1)

- **Duplicados de registro** (mismo `CS_HistoricalOriginID`, distinto `Id` de
  Enablon, contenido idéntico): confirmado en Eventos (585), OPS (423), y
  reportado por el cliente también en Safety Meetings y Simulacros.
- **Pérdida de precisión en duración** (redondeo a 5 min, mes de 30 días fijos).
- **Fases de flujo incorrectas tras migrar** (MOC — 3 tickets del cliente).
- **Cambios anulados migrados como activos** (MOC).
- **Asistentes incompletos** en reuniones (Safety Meetings — solo se usa 1 de 2
  campos origen posibles).
- **PSM con respuestas en inglés** (fallo del fan-out de `cloneorigin` a 5 idiomas).
- Todos los ETL nuevos se construyen copiando el libro de un módulo anterior sin
  limpiar — las hojas `MAP-ITPOLD-EVT/IMP/MED/MED-2` (de Eventos) aparecen sin
  uso en 7 de 7 libros con checklists/eventos auditados.

## Documento de incidencias del cliente (Help Desk)

834 tickets, 107 categorizados por módulo (el resto sin etiquetar). Cruzado ya
contra los hallazgos técnicos — confirma varios de forma independiente. Ver
`inputs/incidents/` para el export bruto. El ticket más relevante (`#7581`) es
el propio cliente pidiendo la documentación de mapeo que este proyecto produce.

## Estado de los accesos

| Necesidad | Estado |
|---|---|
| Acceso SQL de solo lectura | Concedido — corrección Sprint 8.6.1: este entorno de trabajo **sí puede** disponer de conectividad real a SQL Server (usuario readonly `ClaudeReadOnly`, ver `src/db/connection.py`) — un incidente contenido durante Sprint 8.6 lo confirmó (`python main.py run --object simulacros` abrió una conexión real y leyó 5 filas). **La disponibilidad de credenciales/conectividad NUNCA implica autorización de uso**: todo acceso SQL real requiere autorización técnica explícita, por ejecución, vía `--allow-real-sql` (o `EMF_ALLOW_REAL_SQL=1`) — bloqueado por defecto, para `sample` y `full` por igual, verificado por el SQL Execution Guard (`src/db/sql_execution_guard.py`, ver `docs/01-architecture/sql-execution-guard.md`). Sin esa autorización explícita del usuario para una ejecución concreta, no se ejecuta SQL real — el flujo de trabajo por defecto sigue siendo: alguien ejecuta la query (las de `sql/source_queries/` u otras que propongamos) y sube el resultado. |
| Queries de extracción originales | Recibidas para los 9 módulos, en `sql/source_queries/`. Revisadas en profundidad solo Eventos hasta ahora (hallazgo del `FULL JOIN` que infla el "origen" — ver abajo). |
| CSV reales de Enablon | Recibidos y contrastados para todos los módulos excepto PSM (recibido, no volumetrizado). |
| Catálogo real de entidades | Recibido (`First_Axis`) y aplicado. |
| Acceso a Enablon (API/admin) | No solicitado formalmente aún. |

## Nota técnica: `FULL JOIN` en las queries de Eventos infla el "origen" aparente

La query de Eventos Antiguos hace `ITP_ANALISIS FULL JOIN ITP_INFORME_INVEST_PR227`.
El `FULL JOIN` conserva análisis sin investigación asociada (con nulos). El
recuento ingenuo de filas de esa query (14.169) NO es "eventos que deberían
migrar" — de esas, solo 9.496 tienen investigación real asociada. Antes de tomar
el recuento de cualquier query como "origen" para una comparación de volumetría,
mirar el tipo de JOIN.

## Cómo continuar

1. Terminar de poblar `config/modules.yaml` con el detalle de cada módulo
   (columnas exactas, reglas, claves de correlación create/update) a medida que
   se traslada del análisis manual (ver hilo de conversación previo) a config.
2. Implementar `src/analysis/volumetry.py` contra Simulacros primero (el módulo
   más simple y ya cerrado) como caso de prueba end-to-end.
3. No dar por bueno ningún resultado de volumetría sin desglose por site — ver
   Hallazgo #1.
4. Cuando se automatice un módulo nuevo, comprobar primero si sus hojas
   `Mapeo_*` esconden alguna hoja huérfana de otro módulo (patrón confirmado
   siete veces) antes de asumir que la hoja `Index` lista todo lo real.
