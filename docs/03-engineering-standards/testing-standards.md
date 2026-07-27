# Testing Standards — EMF

**Status:** Approved Design (formaliza la práctica ya seguida por los ~404
tests existentes en `tests/`).

## 1. Todo debe ser probable sin red ni credenciales reales

Regla general, sin excepción salvo el mecanismo de opt-in del punto 4:
cualquier componente de EMF (Core, Engine, Connector, Plugin) debe poder
probarse con datos sintéticos, en memoria, sin abrir una conexión de red ni
requerir un `.env` relleno. Esto ya es cierto para el 98% de la suite
actual (404 de 411 tests no requieren red).

## 2. Un fichero de test por módulo, mismo grano que el código

Convención ya seguida (`src/db/connection.py` → `tests/test_db_connection.py`,
`src/db/metadata.py` → `tests/test_db_metadata.py`...): cada módulo público
nuevo de Core/Engine tiene su propio fichero de test homónimo
(`src/core/registry.py` → `tests/test_core_registry.py`). No se agrupan
varios módulos no relacionados en un único fichero de test grande.

## 3. Boilerplate de import

No existe `conftest.py` ni `pytest.ini` en el repositorio hoy — cada
fichero de test resuelve el import con
`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` al
principio. Todo test nuevo sigue este mismo patrón hasta que se decida
introducir un `conftest.py` (mejora propuesta, no decidida — ver Riesgos y
cuestiones abiertas en la revisión de este sprint).

## 4. Tests de integración opt-in, nunca por defecto

Cualquier test que requiera una fuente real (SQL Server, un fichero externo
no versionado, una API externa) se marca `pytest.mark.skipif` gateado por
una variable de entorno explícita (patrón:
`RUN_<COMPONENTE>_INTEGRATION_TESTS=1`), y **nunca** se ejecuta en la
corrida por defecto de `pytest tests/`. Si el test necesita, además, un
valor real que no se puede fabricar honestamente (p. ej. un ID real
existente en una base de datos), se exige una segunda variable de entorno
específica en vez de inventar el valor — patrón ya usado en el test
opt-in del Query Engine (`DRILLS_FILTER_INTEGRATION_TEST_ID`).

## 5. Tests de fronteras de dependencia

Todo paquete que declare una restricción de capa (en particular, el Core:
"no importa nada de `src.*`") debe tener un test automatizado que la
verifique — no basta con la disciplina de revisión manual. Ver el test
`test_core_dependency_boundaries` propuesto en el diseño de Sprint 4.1
como referencia de este patrón.

## 6. Nunca fabricar datos de negocio en un test

Un test no inventa un valor de negocio que no se pueda justificar (un ID
real, una regla de mapeo no confirmada). Cuando un test necesita datos
"reales" para validar contra el mundo real, se usan fixtures explícitamente
marcadas como sintéticas (`_fake_catalog`, `ObjectMetadata` de prueba con
valores inventados pero declarados como tales) — nunca se presenta un dato
inventado como si fuera un hecho confirmado del proyecto.

## 7. Regresión obligatoria

Ningún incremento se considera terminado si reduce el número de tests que
pasaban antes, o si cualquiera de los tests existentes cambia de
comportamiento sin que el cambio esté explícitamente documentado y
aprobado. La suite completa (`pytest tests/ -q`) se ejecuta antes de cerrar
cualquier incremento.

## 8. Seguridad probada, no solo documentada

Los controles de [`security-standards.md`](security-standards.md) que son
verificables por código (validación de solo lectura, ausencia de
credenciales en manifiestos, parametrización de valores) tienen su propio
test explícito — no basta con que estén documentados como práctica. Ver
`tests/test_db_query_runner.py` (SQL bloqueado/permitido) y
`test_manifiesto_no_incluye_claves_de_credenciales` como referencia de
este patrón para todo componente nuevo.
