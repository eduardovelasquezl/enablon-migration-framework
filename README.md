# Migración Histórica a Enablon

## 1. Qué es este proyecto

Plataforma de análisis, exportación, validación y generación de evidencias
para la migración histórica de datos hacia Enablon. Sustituye el ETL en
Excel original por un flujo auditable: análisis del SQL de origen,
documentación de reglas de mapeo, un motor de exportación de solo lectura
por objeto, y generación automática de evidencia en Excel para revisión
funcional.

Este repositorio **no carga nada en Enablon**. Genera CSV y evidencia de
revisión; la carga final sigue siendo manual o vía un proceso fuera de este
repo, al menos por ahora.

Para el análisis histórico completo (9 módulos, hallazgos de volumetría,
reglas de transformación confirmadas) ver [`CLAUDE.md`](CLAUDE.md) y
[`docs/specifications/v1.0/`](docs/specifications/v1.0/). Este README cubre
solo lo **operativo**: cómo instalar, ejecutar y generar evidencia con lo
que ya está implementado hoy.

## 2. Estado actual

| Elemento | Estado |
|---|---|
| Objeto implementado | **Drills** (`simulacros.Drills`) — el único objeto con un flujo de exportación ejecutable hoy |
| Estado del CSV generado | `prototype_status: review_only` — documento de revisión, no un fichero aprobado |
| Carga automática en Enablon | No disponible (y no planificada en este repositorio, ver [ADR-006](docs/architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md)) |
| Exportación filtrada por entidad o centro | Planificada, no disponible todavía |
| Otros objetos de migración (Eventos, MOC, Bypass, OPS, Inspecciones, Safety Meetings, Action Plans...) | Analizados y documentados (`docs/specifications/v1.0/`), **sin flujo de exportación ejecutable todavía** |
| `export all` | No implementado |

`approved_for_enablon_import` es siempre `false` en el manifiesto de cada
ejecución — ningún incremento de este repositorio lo cambia por sí solo.

## 3. Requisitos

- Python -- probado en este entorno con **3.14**; no se ha verificado con
  otras versiones.
- Entorno virtual (`.venv`) con las dependencias de `requirements.txt`
  (`pandas`, `SQLAlchemy`, `pyodbc`, `openpyxl`, `click`, `pytest`...).
- Driver ODBC de SQL Server instalado en el sistema (`ODBC Driver 17 for
  SQL Server`, declarado en `config/databases.yaml`).
- Un fichero `.env` (copiado de `.env.example`, nunca versionado) con las
  credenciales reales de conexión de solo lectura. Este README no muestra
  ni necesita valores reales.
- Acceso de red de solo lectura a la base de datos `Prevencion` (conexión
  lógica `prevencion` en `config/databases.yaml`) para el objeto Drills.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # rellenar con credenciales reales, nunca commitear
```

## 4. Inicio rápido

```bash
# Exportación de revisión, 100 filas más antiguas (modo por defecto: sample)
python main.py export drills --mode sample --limit 100

# Exportación completa -- requiere confirmación explícita, no se ejecuta por accidente
python main.py export drills --mode full --confirm-full-export
```

> El segundo comando exporta el objeto Drills completo (miles de filas
> reales contra SQL Server). No lo ejecutes como prueba ni lo incluyas en
> scripts automatizados sin necesidad real -- por eso exige
> `--confirm-full-export` explícito. Los ejemplos de este README y sus
> tests solo usan `--mode sample`.

## 5. Salidas

Cada ejecución escribe en una carpeta propia con marca de tiempo, nunca
sobrescribe una anterior:

```
outputs/prototype/drills/<timestamp>/
    drills.csv               # CSV generado (UTF-8, revisión -- no aprobado para carga)
    validation_report.yaml   # conteos, estado de Reference/entidades/fechas, resultado
    export_manifest.yaml     # trazabilidad técnica (hashes, reglas aplicadas, approved_for_enablon_import)
    comparison_report.yaml   # comparación contra el CSV histórico real (si está disponible)
    issues.jsonl             # detalle de incidencias por fila (usado por el Evidence Engine)
    evidence_internal.xlsx   # evidencia interna -- solo si se generó (ver sección 6)
    evidence_client.xlsx     # evidencia para el cliente -- solo si se generó (ver sección 6)
```

## 6. Generación de evidencia

El **Evidence Engine** convierte los informes de una ejecución en un Excel
por pestañas, listo para revisión funcional -- sin volver a consultar SQL
Server. Genera dos versiones:

- `evidence_internal.xlsx` -- conserva trazabilidad técnica (hashes, rutas
  relativas de artefactos, reglas aplicadas).
- `evidence_client.xlsx` -- sin hashes, sin rutas locales, sin nombres de
  módulos ni SQL; lenguaje neutral orientado a revisión funcional.

Dos formas de generarla:

```bash
# 1) Integrada -- genera ambas evidencias al terminar la exportación
python main.py export drills --mode sample --limit 100 --generate-evidence

# 2) Independiente -- regenera evidencia desde una ejecución ya existente,
#    sin volver a consultar SQL Server
python main.py evidence drills --run outputs/prototype/drills/<timestamp>

# También admite el run_id (sin ruta) y localizar la última ejecución sin --run:
python main.py evidence drills --run <run_id>
python main.py evidence drills
```

Ambos comandos aceptan `--audience internal|client|both` (por defecto
`both`). El comando `evidence drills` rechaza explícitamente: una carpeta
inexistente, una ejecución de otro objeto, informes YAML inválidos, un
manifiesto sin `approved_for_enablon_import`, o una ruta fuera de
`outputs/`.

## 7. Uso con Claude Code

Claude Code puede recibir la instrucción en lenguaje natural, pero siempre
debe traducirla al comando real del repositorio -- nunca inventar un
resultado ni asumir que una exportación ocurrió sin ejecutarla.

> **Instrucción**: "Genera un sample de 100 Drills y crea las evidencias
> interna y cliente."
>
> **Comando equivalente real**:
> ```bash
> python main.py export drills --mode sample --limit 100 --generate-evidence --audience both
> ```

Cualquier instrucción que implique modo `full`, carga en Enablon, u otro
objeto distinto de Drills, hoy no tiene un comando real equivalente en este
repositorio -- ver sección 9.

## 8. Uso con Codex

Uso recomendado: revisión de código, ejecución de la suite de tests
(`pytest tests/ -v`), revisión de los resultados de una ejecución ya hecha,
y correcciones controladas y acotadas sobre el código existente.

Codex **no sustituye** la validación funcional de una exportación real --
revisar `validation_report.yaml` y la evidencia en Excel sigue siendo un
paso humano, no algo que se pueda dar por bueno solo porque los tests
pasen.

## 9. Funciones futuras -- Planificado / no implementado

Nada de esta sección tiene un comando ejecutable hoy. Se documenta para
dejar clara la dirección, no como uso actual:

- Filtros de exportación por `IDCentro`.
- Filtros de exportación por entidad.
- Filtros de exportación por rango de fechas.
- Un comando `preview` (vista previa sin escribir ficheros).
- Exportación de otros objetos de migración (Eventos, MOC, Bypass, OPS,
  Inspecciones, Safety Meetings, Action Plans...).
- `export all` (orquestación de todos los objetos a la vez).
- Carga directa en Enablon (API o UI) -- fuera de alcance por diseño, ver
  [ADR-006](docs/architecture/v1.0/decisions/ADR-006-csv-generation-not-direct-load.md).

## 10. Seguridad

- **SQL Server siempre en modo solo lectura**: doble salvaguarda --
  `ApplicationIntent=ReadOnly` en la cadena de conexión y un validador
  estructural (`src/db/query_runner.py`) que solo permite `SELECT` (o `WITH`
  que desemboque en `SELECT`); cualquier otra sentencia se rechaza antes de
  tocar el servidor. La garantía real de fondo son los permisos del login
  SQL a nivel de servidor.
- **Sin escritura en Enablon**: ningún comando de este repositorio se
  conecta a Enablon para escribir; no existe ese código todavía.
- **Manifiestos sin secretos**: `export_manifest.yaml` nunca incluye
  contraseñas ni cadenas de conexión completas -- solo el nombre lógico de
  la conexión (`prevencion`).
- **Outputs separados de las fuentes originales**: todo lo generado vive
  bajo `outputs/`; nunca se modifica ningún SQL, Excel de ETL, CSV histórico
  ni mapping de evidencia original.
- **Todo lo generado es `review_only`**: ninguna ejecución de este
  repositorio marca `approved_for_enablon_import: true`.
