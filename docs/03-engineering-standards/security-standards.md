# Security Standards — EMF

**Status:** Approved Design (formaliza controles ya implementados y
verificados en `src/db/` y `src/query/`; extiende su alcance a toda futura
capa de EMF).

Este documento fija los invariantes de seguridad que **ningún** componente
de EMF, presente o futuro, puede violar — Connector, Engine, Plugin o
configuración de proyecto. No sustituye la revisión de seguridad de cada
incremento concreto, es el estándar contra el que esa revisión se compara.

## 1. Solo lectura sobre cualquier fuente viva

Todo Connector que acceda a una fuente con capacidad de escritura
(SQL Server hoy; cualquier base de datos o API futura) debe implementar
doble salvaguarda, sin excepción:

1. Un permiso real de solo lectura a nivel del sistema origen (hoy: rol
   `db_datareader` exclusivamente, ver `src/db/connection.py`).
2. Una validación estructural en código, independiente del permiso real,
   que rechace cualquier operación de escritura antes de ejecutarla (hoy:
   `validate_read_only_sql`, whitelist de `SELECT`/`WITH...SELECT` +
   lista negra de palabras de escritura/DDL/DCL).

Ningún Connector nuevo puede considerarse "de solo lectura" solo porque el
código no incluye una llamada de escritura — debe tener ambas capas, igual
que SQL Server las tiene hoy.

## 2. Nunca concatenar valores de usuario o de fuente externa

Todo valor que provenga de un usuario (CLI, configuración de proyecto) o de
una fuente externa (un registro extraído) debe viajar como parámetro
nombrado hacia cualquier motor de consulta o comando — nunca concatenado en
el texto de una consulta o comando. Patrón de referencia ya implementado:
`src/query/` (Query Engine v0.1), que compone SQL en memoria con
placeholders (`:filter_1`) y nunca interpola un valor directamente. Todo
Connector/Engine futuro que construya una consulta dinámica debe seguir el
mismo patrón, reutilizando `validate_read_only_sql` (o su equivalente para
la fuente correspondiente) para revalidar el texto compuesto.

## 3. Identificadores SQL nunca desde el usuario sin validar

Ningún nombre de tabla/columna/esquema que se vaya a interpolar en texto
(nunca en un valor, solo en una posición de identificador) puede provenir
directamente de una entrada de usuario sin pasar por una validación
estricta de formato (patrón ya implementado:
`src.db.query_runner.validate_identifier`). Todo campo filtrable/ordenable
expuesto a un usuario debe resolverse contra un catálogo cerrado
(`ObjectFilterCatalog` u homólogo), nunca aceptar un nombre de columna
libre.

## 4. Ninguna credencial en código, configuración versionada, log,
manifiesto o mensaje de excepción

- Credenciales solo en `.env` (nunca commiteado — ver `.gitignore`).
- `config/*.yaml` nunca contiene un host, usuario o contraseña real — solo
  el nombre de la variable de entorno que los resuelve (ya vigente,
  `config/databases.yaml`).
- Ningún mensaje de excepción incluye contraseña, cadena de conexión
  completa o el texto íntegro de una consulta — se usa nombre de
  conexión, nombre de fichero de origen y/o un hash corto, nunca el
  contenido (ya vigente, `src/db/exceptions.py`).
- Ningún manifiesto (`export_manifest.yaml` u homólogo futuro) incluye
  secretos ni cadenas de conexión — ya verificado explícitamente por test
  (`test_manifiesto_no_incluye_claves_de_credenciales`).
- Cualquier dato de logging (`get_logger`, Core Sprint 4.1) sigue la misma
  regla: se registran hashes/nombres, nunca valores sensibles ni el
  contenido completo de una consulta.

## 5. Sin scrubbing automático de secretos por regex

Se documenta la decisión explícita, tomada en el diseño de Sprint 4.1, de
**no** implementar un sistema de redacción automática de secretos en logs
mediante expresiones regulares. Da una falsa sensación de seguridad (es
fácil que un patrón nuevo de secreto se escape) y es sobreingeniería frente
a la disciplina ya existente (nunca loggear el dato sensible en primer
lugar). Esta decisión se revisita solo si aparece evidencia real de una
fuga por este camino.

## 6. Fuentes documentales (Word/PDF) — riesgo adicional

Un futuro Connector de Word/PDF puede procesar documentos que contengan,
incidentalmente, información sensible no relacionada con el objeto migrable
(datos personales, información confidencial ajena al alcance de la
migración). El diseño de ese Connector deberá incluir, explícitamente, qué
se extrae y qué se descarta — no se asume que "todo el documento es
seguro de procesar" solo porque el documento en sí no es una credencial.
Esto se revisará con su propia ADR cuando el Connector se diseñe en
detalle (no forma parte del alcance de esta versión).

## 7. Sin carga en Enablon

Ningún componente de EMF, en esta versión del producto, escribe en Enablon
(ni vía API ni vía UI) — invariante ya fijado por
[ADR-006 legado](../architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md)
y reafirmado por
[ADR-012](../02-adr/ADR-012-source-agnostic-enablon-oriented.md).
Cualquier cambio a este invariante requiere su propia ADR y, dado el
impacto, aprobación explícita fuera del ciclo normal de sprint.

## 8. Operaciones destructivas

Ningún componente de EMF ejecuta, ni directa ni indirectamente,
operaciones destructivas sobre ninguna fuente (DROP, TRUNCATE, DELETE,
UPDATE, `git reset --hard`, `rm -rf` sobre datos de proyecto) como parte de
su funcionamiento normal. Las salvaguardas del punto 1 ya bloquean esto
para SQL Server a nivel de motor de consulta; cualquier Connector nuevo
debe implementar el equivalente para su propia fuente antes de
considerarse listo para uso real.
