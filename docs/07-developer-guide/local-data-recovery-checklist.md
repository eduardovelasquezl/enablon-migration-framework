# Local Data Recovery Checklist — datos de migración eliminados accidentalmente

**Status:** Implemented — este documento existe y se utiliza como
procedimiento operativo vigente (checklist a rellenar durante la
recuperación real de archivos), aunque la recuperación de los archivos en
sí siga pendiente (acción manual del usuario, fuera del repositorio).

## 0. Contexto

El 2026-07-27, una operación de limpieza del historial de git
(`git filter-repo --path inputs/_incoming_claude_web --invert-paths`)
eliminó accidentalmente, tanto del historial como del árbol de trabajo
local, el contenido de `inputs/_incoming_claude_web/` — los ETL, CSV
reales de Enablon, mappings, errores y documentación que el usuario había
incorporado manualmente después de que el ZIP inicial de Claude Web
(que no los incluía, por tamaño) se trasladara a este repositorio en
Claude Code/VS Code. El código, la documentación EMF, los tests y la
configuración del repositorio no se vieron afectados.

Este documento es la plantilla para reconstruir, de forma auditable, qué
se ha recuperado, desde dónde, y dónde vive ahora (fuera del
repositorio) — y fija, a partir de Sprint 7, el principio permanente de
separación entre código y datos que evita que este incidente vuelva a
ser posible de la misma forma (ver
[`external-data-workspace.md`](../01-architecture/external-data-workspace.md)
para el diseño completo).

## 1. Principios no negociables

- **Nunca se almacenan datos reales del cliente en Git** — ni ETL, ni CSV,
  ni ZIP, ni BAK, bajo ninguna circunstancia, versionados ni sin
  versionar.
- **Git no es un sistema de backup para datos de migración.** La única
  copia de seguridad válida de estos ficheros es una copia externa
  (Descargas, Teams, SharePoint, OneDrive, correo, carpetas originales del
  cliente, u otra ubicación fuera del repositorio) — nunca el propio
  repositorio ni su historial.
- **Antes de cualquier operación destructiva o que reescriba el
  historial** (`filter-repo`, `reset --hard`, `clean -fdx`, etc.) se debe
  validar primero que existe una copia externa completa y verificada de
  cualquier dato local que deba conservarse — confirmar que el dato
  "existe en el repo" no es suficiente, porque el propio repo puede ser
  la superficie que la operación destruye.

## 2. Datos versionables y no versionables

**Versionables** (viven en Git, dentro del repositorio):

- código fuente;
- configuración sin secretos;
- documentación;
- tests;
- fixtures pequeños y anonimizados;
- ejemplos;
- plantillas vacías;
- catálogos genéricos sin información de cliente;
- schemas;
- manifests de ejemplo.

**No versionables** (viven exclusivamente en el workspace externo, ver
§ 3-4):

- ETL reales;
- CSV reales de Enablon;
- BAK;
- ZIP de cliente;
- evidencias reales;
- exportaciones completas;
- documentos del cliente;
- errores que contengan datos reales;
- información confidencial;
- credenciales;
- archivos generados de gran volumen.

## 3. Arquitectura Código ↔ Datos

```
Repositorio Git:
    enablon-migration-framework/        -- código, configuración, docs,
                                            tests, fixtures pequeños

Workspace externo:
    Migracion_Enablon_Data/             -- ETL, CSV reales, BAK, ZIP,
                                            evidencias, exportaciones,
                                            documentos de cliente
```

Ambos forman el entorno de trabajo completo — pero **únicamente el
primero está versionado**. El repositorio nunca depende de que el
workspace externo exista para poder clonarse, instalarse o pasar su
suite de tests; el workspace externo nunca se sube a ningún control de
versiones. Ver
[`external-data-workspace.md`](../01-architecture/external-data-workspace.md)
para el diseño completo de esta separación y cómo el Framework resuelve
la ubicación del workspace en tiempo de ejecución.

## 4. Ubicación del workspace externo

Los datos recuperados **no vuelven a `inputs/_incoming_claude_web/`
dentro del repositorio**. Ruta recomendada para este equipo (fuera del
árbol de git):

```
C:\Users\EduardoVelásquez\Desktop\Migracion_Enablon_Data\
```

**Esta ruta concreta es un ejemplo para este puesto de trabajo, no un
valor fijo del Framework** — es configurable mediante la variable de
entorno `EMF_DATA_ROOT` (ver
[`external-data-workspace.md`](../01-architecture/external-data-workspace.md)
§ 10-11) y **nunca se codifica directamente en el Core**. Cada
desarrollador puede usar una ubicación distinta en su propio equipo.

Estructura interna propuesta, organizada por **finalidad**, no por el
nombre histórico de los bloques de entrega del cliente:

```
Migracion_Enablon_Data\
    ETL\
    CSV_Enablon\
    Mappings\
    Catalogs\
    Errors\
    Evidence\
    SQL\
    Outputs\
    Archive\
```

Los nombres `Bloque1`…`Bloque7` de la entrega original del cliente **no
se conservan como estructura operativa definitiva** — se registran en el
inventario (§ 5) como referencia de origen histórico de cada archivo,
para trazabilidad, pero cada archivo recuperado se coloca en la carpeta
de la estructura anterior que corresponda a su finalidad (un CSV real de
Enablon va a `CSV_Enablon\` independientemente de si originalmente
llegó en "Bloque4").

Esta estructura es una propuesta pendiente de validación — no se ha
creado todavía, no se ha modificado `config/settings.yaml` ni `.env` para
apuntar a ella, y no se crean enlaces simbólicos ni copias hasta que se
apruebe explícitamente (ver Fase 11 del Sprint 7 — no se crea el
workspace real en esta tarea).

## 5. Inventario de recuperación

| Bloque (origen histórico) | Categoría | Nombre del archivo | Origen probable | Recuperado | Ubicación nueva | Tamaño | Fecha | Observaciones |
|---|---|---|---|---|---|---|---|---|
| | | | | ☐ Sí ☐ No ☐ Parcial | | | | |
| | | | | ☐ Sí ☐ No ☐ Parcial | | | | |
| | | | | ☐ Sí ☐ No ☐ Parcial | | | | |

*(Tabla vacía — una fila por archivo recuperado o pendiente de recuperar,
añadida a medida que el usuario reincorpore documentos desde sus fuentes
originales. La columna "Bloque" conserva el nombre histórico
[`Bloque1_ETL`…`Bloque7_Otros`] solo como referencia de procedencia; la
columna "Ubicación nueva" usa siempre la estructura por finalidad de § 4.)*

### Orígenes probables a revisar

- Descargas (carpeta local del equipo)
- Teams
- SharePoint
- OneDrive
- Correo electrónico
- Carpetas originales del cliente (red interna / entrega física)
- Archivos descargados desde Claude Web (sesión original que generó el ZIP)
- Copias locales previas (otros equipos, discos externos, versiones anteriores del proyecto)

## 6. Campos estándar y campos `CS_`

- Los CSV de Enablon suelen mantener **campos estándar estables** (los ya
  provistos por el propio producto Enablon, comunes a cualquier cliente).
- Los **campos personalizados de cliente comienzan con `CS_`** (ya
  confirmado con datos reales en Drills: `CS_Typology`, `CS_Letter`,
  `CS_ImpactedEntities`, `CS_WorkflowStatus`, `CS_HistoricalDataOrigin`,
  `CS_HistoricalOriginID`...).
- Las plantillas, mappings y validaciones deben **declarar expresamente**
  qué campos `CS_` esperan — nunca aceptar automáticamente cualquier
  columna que empiece por `CS_` sin que exista un contrato que la declare
  (mismo principio ya aplicado en `config/exports/drills.yaml`, donde
  cada campo `CS_*` tiene su propia entrada en `fields` con `evidence_id`
  propio, y en `mapping-specification.md`, que exige `target_field`
  declarado por cada `MappingRule`).
- Los CSV reales que contienen estos campos **residen fuera de Git**, en
  el workspace externo (§ 3-4) — nunca se versiona un CSV real solo
  porque contenga campos `CS_` ya "conocidos".

## 7. Antes de cualquier operación destructiva futura

Checklist a repetir cada vez que se plantee una operación irreversible
sobre el repositorio o sus datos locales asociados:

- [ ] ¿Existe una copia externa (fuera del repositorio) de todo dato local que deba sobrevivir a la operación?
- [ ] ¿Se ha verificado esa copia externa (no solo su existencia, sino que es legible y completa)?
- [ ] ¿La operación puede modificar o eliminar archivos del árbol de trabajo, además del historial de git?
- [ ] ¿Se ha comunicado explícitamente al usuario qué se va a eliminar y desde dónde, antes de ejecutar?
- [ ] ¿Existe una vía de cancelar o revertir la operación si algo sale mal?

Si la respuesta a cualquiera de los puntos anteriores es "no" o "no se
sabe", la operación no se ejecuta hasta resolverlo.
