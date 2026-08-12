# Mapping Evidence — Action Plans (Moeve)

Narrativa legible para consultor, sin necesidad de leer los YAML de esta
carpeta. Resumen de por qué existe esta carpeta y qué dice cada fichero:
ver `docs/01-architecture/mapping-governance.md` § 7 y § 10 para el
contexto completo (este es el único módulo, de los 9, materializado como
ejemplo concreto del esquema — ver justificación en ese documento).

## Qué se pidió

El encargo de este sprint (8.8) exigía, como caso obligatorio: "el ETL
correspondiente a Action Plans... contiene una modificación posterior del
mapping del eje. Esa versión es la última versión verificada... debe
identificarse exactamente qué mapping cambió... documentarse la
transición origen → nuevo mapping".

## Qué se encontró

Hay **dos** ETL de Action Plans, y no son dos versiones secuenciales del
mismo archivo — cubren ámbitos de origen distintos, ya documentado en
`config/modules.yaml` (`etls: ["AP_GCT (solo MOC)", "AP-Con Ajuste
Entidad (resto de módulos)"]`):

- `ETL- AP_GCT_NEW_SITECAN.xlsx` → AP de origen MOC/GCT.
- `ETL- AP-Con Ajuste Entidad_NEW_SIETCAN (1).xlsx` → AP del resto de
  módulos de origen ITP (Eventos, Simulacros, Inspecciones, OPS, Safety
  Meetings, HAZOPS, Otros).

La modificación del mapping del eje que el encargo pedía registrar es
visible comparando cómo cada uno resuelve la entidad/eje de cada acción:

- El ETL **ITP-genérico** (`AP-Con Ajuste Entidad`) solo tiene la hoja
  `Entidades_Mapeo` — el mecanismo estático que `CLAUDE.md` ya marca como
  desactualizado ("no usar... están todas desactualizadas").
- El ETL **MOC/GCT** (`AP_GCT`) tiene, además, dos hojas que no existen
  en el otro: `Exportación eje` (un export en vivo del catálogo de
  entidades, con la misma forma que `First_Axis`: `ruta / Parent / Code /
  EntityEN / ... / EntityStatus`) y `MapeoEje_uorg` (una regla
  declarativa que resuelve `IDUnidadOrg` contra ese catálogo vivo, con el
  patrón `DatoOrigen / DatoDestino / EsCondicion / ReglaEspecial /
  Parametro` ya conocido de `CLAUDE.md`).

Esto encaja con lo que `CLAUDE.md` ya sabía por otra vía: el patrón de
lookup dinámico en 2 pasos contra un catálogo vivo es "mejor patrón,
preferible al lookup estático — visto en SM/MOC". Este sprint confirma
que también llegó a AP, pero **solo a la mitad de AP** (el ámbito
MOC/GCT).

## Por qué no se cierra como "resuelto"

El encargo afirma como premisa que existe una versión posterior
**verificada**. La evidencia estructural encaja con esa premisa para el
ámbito MOC/GCT — pero no puede confirmarse, solo con lo inspeccionado
este sprint, si el ámbito ITP-genérico de AP **debía** recibir la misma
actualización y se quedó atrás, o si ambos mecanismos son
intencionalmente distintos por sistema de origen (como ya ocurre, por
diseño, con la numeración de `IDCentro` entre ITP y GCT — ver
`CLAUDE.md`). Registrar esto como `CURRENT_VERIFIED` sin esa
confirmación sería inventar una vigencia que la evidencia no sostiene
sola. Por eso queda `CURRENT_UNVERIFIED` con un `KNOWLEDGE_CONFLICT`
abierto (`KC-AP-001`, ver `knowledge-conflicts.yaml`) — la pregunta
concreta que un humano necesita responder está en ese fichero, no
enterrada en prosa.

## Qué mirar primero si se retoma este módulo

1. `knowledge-conflicts.yaml` — la pregunta abierta (`KC-AP-001`).
2. `mapping-set.yaml` — las 4 reglas identificadas con evidencia real
   (incluida la revisión histórica vs. la candidata a vigente).
3. `unresolved-rules.yaml` — 3 candidatos sin evidencia suficiente,
   incluido un segundo posible caso de versionado dentro del mismo ETL
   MOC/GCT (`Mapeo_Sourcesd` vs `Mapeo_Sources_V2` — no investigado en
   profundidad, mismo patrón "_V2" que el caso de eje).
4. `docs/07-developer-guide/moeve-mapping-backlog.md`, ítems P1-01,
   P1-02, P2-06 — las acciones concretas siguientes.
