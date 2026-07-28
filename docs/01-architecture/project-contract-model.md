# Project Contract Model — Platform, Project y EMF Contract

**Status:** Approved Design (Sprint 8.2). Diseño conceptual y de
documentación únicamente — **ninguna lógica de comparación de este
documento está implementada todavía** (ver § 5, "Futura validación
automática": deliberadamente sin código). No modifica
`config/exports/drills.yaml`, `src/export/prototype/drills/*.py` ni
ningún otro fichero de `src/`.

## 1. Propósito

Fijar un vocabulario preciso para distinguir **tres niveles de contrato**
sobre las columnas de un objeto Enablon, y dejar explícito cuál de ellos
es el objetivo real del EMF — evitando el malentendido de que el
Framework debe reproducir todas las columnas que Enablon es capaz de
exponer.

**El objetivo del proyecto NO es reproducir todas las columnas del
template de Enablon. El objetivo es generar exactamente el contrato
operativo del proyecto** (el subconjunto de columnas que el cliente usa
de verdad para importar).

## 2. Los tres niveles de contrato

```
Platform Contract  (Enablon, todas las columnas posibles de un objeto)
        │
        │  el cliente usa un subconjunto
        ▼
Project Contract    (lo que este cliente realmente importa)
        │
        │  el EMF intenta reproducir ESTE nivel, no el anterior
        ▼
EMF Contract         (lo que el Framework genera hoy)
```

### 2.1 Platform Contract

**Representado por:** la categoría de workspace `csv_enablon_template`
(ver `external-data-workspace.md` § 6, § 21).

Es la superficie completa que Enablon **puede** exponer para un objeto:
exportaciones completas obtenidas directamente desde Enablon. Puede
contener:

- campos de sistema (gestionados por la propia plataforma, no por el
  cliente);
- campos calculados por Enablon (derivados en el momento de la
  exportación, no importables tal cual);
- columnas nunca utilizadas por este cliente en concreto (presentes en
  la plantilla de la plataforma, irrelevantes para este proyecto).

El Platform Contract es una propiedad de **Enablon como producto**, no de
este cliente — es el mismo, en esencia, para cualquier proyecto que use
el mismo objeto (Drills, Events, etc.), con variaciones menores según la
configuración de la instancia de Enablon del cliente.

### 2.2 Project Contract

**Representado por:** la categoría de workspace `csv_enablon_operational`.

Es el CSV **realmente utilizado para importar** en este proyecto
concreto — el contrato funcional del cliente. Normalmente:

- elimina columnas vacías o no utilizadas del Platform Contract;
- refleja las decisiones reales de qué campos `CS_*` se poblaron y
  cuáles no;
- es la fuente de verdad de "qué se cargó de verdad", no de "qué se
  podría haber cargado".

**El Project Contract es la referencia principal para validar el EMF** —
no el Platform Contract. Un CSV generado por el EMF que reproduce
perfectamente el Project Contract, aunque le falten columnas del Platform
Contract, es un éxito funcional; un CSV que reproduce el Platform
Contract pero no coincide con el Project Contract no lo es.

### 2.3 EMF Contract

**Representado por:** el CSV generado por el Framework en una ejecución
real (`drills.csv` u homólogo de un futuro objeto).

Es lo que el EMF produce hoy, con el nivel de completitud que su
implementación actual alcanza — para Drills, 8 de las 36 columnas reales
del objeto (ver `drills-csv-contract.md`). El EMF Contract se compara
contra el Project Contract, nunca contra el Platform Contract, para medir
si el Framework está cumpliendo su objetivo real.

### 2.4 Declaración formal (Sprint 8.3)

> **Platform Contract != EMF Contract.**
> **Project Contract == Objetivo del EMF.**

El Framework nunca se mide contra el Platform Contract — medirlo así
penalizaría al EMF por no reproducir columnas de sistema, calculadas por
Enablon, o simplemente no usadas por este proyecto (ver § 3). La única
vara de medir correcta para "¿está completo el EMF Contract?" es el
Project Contract.

## 3. Por qué esta distinción importa

Sin ella, cualquier comparación cuantitativa entre el CSV generado y un
CSV real de Enablon corre el riesgo de dos errores simétricos:

- **Sobreestimar la brecha**: comparar el EMF Contract (8 columnas)
  contra un Platform Contract de 36 columnas hace parecer que faltan 28
  columnas "importantes", cuando puede que 20+ de ellas nunca se hayan
  usado para importar nada en este proyecto.
- **Subestimar la brecha**: si el Project Contract real usa, por ejemplo,
  15 columnas y el EMF solo genera 8, la comparación correcta (EMF vs.
  Project) revela una brecha real de 7 columnas operativas — una
  comparación contra el Platform Contract oscurecería esa cifra dentro de
  las 28 "columnas de plataforma no usadas por nadie".

La distinción convierte "¿está completo el EMF?" de una pregunta vaga en
una pregunta verificable: **completo respecto a qué contrato**.

## 4. Relación con la auditoría de Sprint 8.1

`docs/01-architecture/drills-csv-contract.md` (Sprint 8.1) documenta el
EMF Contract de Drills contra las 36 columnas del CSV histórico real
disponible (`Drills-22072026-41.csv`) — en ese momento, sin el vocabulario
de este documento, ese CSV se trató implícitamente como una única
referencia. **Pregunta abierta, no resuelta aquí** (ver
`external-data-workspace.md` § 13, § 21): no está confirmado si
`Drills-22072026-41.csv` es, en los términos de este documento, un
Platform Contract (export completo de producción) o ya un Project
Contract (lo realmente cargado) — ambos son plausibles y no se asume
ninguno sin confirmación. Cuando se recupere documentación adicional
(ver `drills-real-data-inventory.md` § "Ubicaciones Sprint 8.2"), esta
pregunta debería poder resolverse comparando ese fichero contra un
Platform Contract real (una exportación íntegra sin filtrar) si ambos
llegan a estar disponibles.

## 5. Futura validación automática (diseño, NO implementado)

**Nada de esta sección tiene código.** Es el diseño de una comparación de
tres vías que un incremento futuro podría implementar, análoga a
`comparison.py::build_comparison_report` (ya implementado, pero hoy solo
compara EMF Contract vs. un único CSV histórico, sin distinguir
Template/Operational).

```
CSV Template (Platform Contract)
        │
        ▼
CSV Operacional (Project Contract)
        │
        ▼
CSV generado por EMF (EMF Contract)
```

### 5.1 Clasificación de columnas propuesta

La comparación de tres vías debería poder etiquetar cada columna del
Platform Contract con exactamente una de estas categorías (vocabulario
cerrado, sin ambigüedad — nombres oficiales fijados en Sprint 8.3):

| Categoría | Significado |
|---|---|
| **Importable** | Presente en el Project Contract y con datos reales — candidata legítima a implementar en el EMF Contract. |
| **Sistema** | Gestionada por Enablon (p. ej. `Id`, asignado tras la carga) — nunca producible por el EMF, por diseño, no por carencia. |
| **Calculada** | Derivada por la propia plataforma Enablon en el momento de la exportación (no en el momento de la carga) — no es un dato de origen que el EMF deba generar. |
| **Opcional** | Presente en el Project Contract pero vacía o poco poblada en la práctica — candidata de baja prioridad. |
| **No utilizada** | Presente en el Platform Contract, ausente o siempre vacía en el Project Contract — fuera del objetivo real del proyecto (ver § 1). |
| **CS_** | Campo personalizado (`CS_*`) del cliente — requiere su propio contrato declarado explícitamente (nunca aceptado por prefijo, ver `local-data-recovery-checklist.md` § 6), independientemente de si cae en alguna de las categorías anteriores además. |

Estas seis categorías **no son mutuamente excluyentes en un sentido
estricto** (una columna puede ser simultáneamente `Personalizada (CS_)` y
`Importable`, por ejemplo) — el diseño de implementación futuro deberá
decidir si se modela como una única etiqueta primaria o como un conjunto
de banderas independientes; esta decisión se deja explícitamente abierta,
no resuelta por este documento.

### 5.2 Qué necesitaría el motor futuro (no construido aquí)

- Leer las cabeceras (y, opcionalmente, un muestreo de valores para
  detectar "siempre vacía") de los tres CSV — reutilizando
  `comparison.py::detect_historical_csv` como base de detección de
  encoding/delimitador, ya implementado y probado.
- Producir un reporte estructurado (análogo a `comparison_report.yaml`)
  con la clasificación de cada columna del Platform Contract.
- Decidir, con datos reales de al menos un Project Contract disponible,
  el umbral exacto de "poco poblada" para la categoría `Opcional` — no se
  fija un umbral en este documento por no tener todavía un caso real que
  lo justifique (principio "No Abstraction Without a Real Consumer").

### 5.3 Qué NO hace este diseño

- No decide todavía qué hacer con una columna clasificada
  `Importable` (¿implementarla automáticamente? ¿solo reportarla como
  pendiente?) — es una decisión de producto, no de este documento de
  arquitectura.
- No sustituye la comparación ya implementada
  (`comparison.py::build_comparison_report`) — la complementa. La
  comparación actual (EMF vs. un único CSV histórico) sigue siendo válida
  y sigue funcionando sin cambios mientras este diseño no se implemente.
- No requiere que existan los tres ficheros a la vez para tener valor —
  una comparación de dos vías (Template vs. Operational, o Operational
  vs. EMF) ya sería útil por sí sola y podría implementarse antes que la
  de tres vías completa.

## 6. Ubicación en el workspace

| Contrato | Categoría de `DataWorkspace` | Carpeta física (Sprint 8.2) |
|---|---|---|
| Platform Contract | `csv_enablon_template` | `EMF_DATA_ROOT/projects/moeve/CSV_Enablon_Template/` |
| Project Contract | `csv_enablon_operational` | `EMF_DATA_ROOT/projects/moeve/CSV_Enablon_Operational/` |
| EMF Contract | No aplica — es la salida del propio EMF | `outputs/prototype/drills/<timestamp>/drills.csv` (local) o categoría `outputs` del workspace externo si se archiva |

Ambas carpetas del workspace existen ya, vacías, en el puesto de trabajo
real de este proyecto (ver `external-data-workspace.md` § 21) — ningún
archivo se ha colocado en ellas todavía.

## 6.0 Resolución en código (Sprint 8.5)

`ResourceResolver` (`src/core/resource_resolver.py`,
`docs/01-architecture/resource-resolver.md`) es, desde Sprint 8.5, el
único punto de código que resuelve estos artefactos por su rol de
contrato. `src/export/prototype/drills/pipeline.py` pide explícitamente
`operational_csv` (Project Contract) para su comparación opcional,
alineado con § 2.4 ("Project Contract == Objetivo del EMF") — nunca pide
`template_csv` para ese propósito. La pregunta abierta de § 4 (si
`Drills-22072026-41.csv` es Platform u Project Contract) sigue sin
resolverse por este cambio de código: el resolver apunta al rol correcto
por diseño, independientemente de qué archivo físico exista hoy en cada
carpeta (ninguno existe todavía, ver § 6).

## 6.1 Representación en el Workspace Manifest (Sprint 8.4)

`ContractsSpec` (`src/core/workspace_manifest.py`) formaliza en código
esta sección: cada módulo declara `contracts.platform.artifact` /
`contracts.project.artifact` (apuntando a un `kind` de artefacto ya
declarado, nunca a una ruta directamente) y `contracts.emf.generated` /
`emf.output_pattern`. Ver `docs/01-architecture/workspace-manifest.md`
§ 11 para el detalle completo — no se duplica aquí.

## 7. Criterios de aceptación

1. Los tres niveles de contrato (Platform/Project/EMF) están definidos
   sin ambigüedad y sin superponerse conceptualmente.
2. Se declara explícitamente que el objetivo del EMF es el Project
   Contract, no el Platform Contract.
3. La clasificación de columnas de § 5.1 cubre los seis casos pedidos
   (Importable, Sistema, Calculada por Enablon, Opcional, No utilizada,
   Personalizada `CS_`) sin inventar un séptimo caso sin evidencia.
4. Ninguna lógica de comparación de tres vías está implementada en código
   — verificado por inspección: este documento no toca `src/`.
5. La pregunta sobre la clasificación de `Drills-22072026-41.csv` queda
   explícitamente abierta, no resuelta por inferencia (§ 4).
