"""
Inventario técnico automatizado de SQL Server (Prevencion / GCT).

Genera una fotografía reproducible del esquema de una conexión: tablas,
vistas, columnas, claves primarias/foráneas, índices, procedimientos,
funciones, triggers, sinónimos, filas aproximadas y relaciones entre
tablas -- puro metadato de catálogo, nunca datos ni definiciones de código
(sin `sys.sql_modules`, sin `OBJECT_DEFINITION()`, sin `EXEC`).

Deliberadamente NO contiene todavía ninguna lógica de módulos Enablon
(Simulacros, mapeos, CSV de carga, staging) -- es un inventario técnico
puro, pensado para ser reutilizado como base de análisis futuros.

Comportamiento fail-fast: si falla la extracción de cualquier categoría,
se aborta toda la ejecución -- nunca se genera un inventario parcial. La
escritura a disco (`save_inventory`) es atómica: se escribe primero en una
carpeta temporal hermana y solo se renombra a la carpeta definitiva
(`outputs/inventory/<conexion>/<YYYYMMDD_HHMMSS>/`) si todo terminó bien;
si algo falla, la carpeta temporal se borra y la definitiva nunca llega a
existir.
"""
from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.config import get_general_settings, get_paths
from src.db.connection import get_connection_spec
from src.db.query_runner import run_query_file

logger = logging.getLogger(__name__)

# Orden fijo de extracción -- también determina el orden en el manifiesto.
CATEGORY_QUERY_FILES: dict[str, str] = {
    "tables": "tables.sql",
    "views": "views.sql",
    "columns": "columns.sql",
    "primary_keys": "primary_keys.sql",
    "foreign_keys": "foreign_keys.sql",
    "indexes": "indexes.sql",
    "stored_procedures": "stored_procedures.sql",
    "functions": "functions.sql",
    "triggers": "triggers.sql",
    "synonyms": "synonyms.sql",
    "approx_row_counts": "approx_row_counts.sql",
}

# Claves de orden determinista por artefacto -- se aplican en Python además
# del ORDER BY de cada .sql, para que el fichero final no dependa de que
# SQL Server preserve el orden físico de ejecución.
SORT_KEYS: dict[str, list[str]] = {
    "tables": ["schema_name", "table_name"],
    "views": ["schema_name", "view_name"],
    "columns": ["schema_name", "table_name", "column_id"],
    "primary_keys": ["schema_name", "table_name", "key_ordinal"],
    "foreign_keys": ["source_schema", "source_table", "foreign_key_name", "column_ordinal"],
    "indexes": ["schema_name", "table_name", "index_name", "key_ordinal", "index_column_id"],
    "stored_procedures": ["schema_name", "procedure_name"],
    "functions": ["schema_name", "function_name"],
    "triggers": ["trigger_scope", "schema_name", "table_name", "trigger_name"],
    "synonyms": ["schema_name", "synonym_name"],
    "approx_row_counts": ["schema_name", "table_name"],
    "table_relationships": ["source_schema", "source_table", "target_schema", "target_table"],
}

_RELATIONSHIP_COLUMNS = [
    "source_schema", "source_table", "target_schema", "target_table", "foreign_key_count",
]


@dataclass
class InventoryResult:
    """Resultado en memoria de un inventario ya ensamblado (sin persistir)."""

    connection: str
    database: str
    server: str
    generated_at: datetime
    artifacts: dict[str, pd.DataFrame] = field(default_factory=dict)


def _derive_table_relationships(foreign_keys_df: pd.DataFrame) -> pd.DataFrame:
    """Deriva relaciones a nivel de tabla a partir de foreign_keys, SIN
    consultar SQL Server de nuevo.

    Una FK compuesta (varias columnas, mismo foreign_key_object_id) cuenta
    UNA sola vez. Dos FKs distintas entre el mismo par de tablas cuentan
    como foreign_key_count = 2 (no se colapsan entre sí).
    """
    if foreign_keys_df.empty:
        return pd.DataFrame(columns=_RELATIONSHIP_COLUMNS)

    per_fk = (
        foreign_keys_df.groupby("foreign_key_object_id")
        .agg(
            source_schema=("source_schema", "first"),
            source_table=("source_table", "first"),
            target_schema=("target_schema", "first"),
            target_table=("target_table", "first"),
        )
        .reset_index(drop=True)
    )
    relationships = (
        per_fk.groupby(["source_schema", "source_table", "target_schema", "target_table"])
        .size()
        .reset_index(name="foreign_key_count")
    )
    return relationships[_RELATIONSHIP_COLUMNS]


def _sorted(category: str, df: pd.DataFrame) -> pd.DataFrame:
    keys = SORT_KEYS[category]
    if df.empty:
        return df.reset_index(drop=True)
    return df.sort_values(keys, kind="stable").reset_index(drop=True)


def _attach_file_log_handler(connection: str) -> tuple[logging.Handler, Path]:
    """Añade un FileHandler al logger raíz para que toda la ejecución quede
    registrada bajo logs/, además de lo que ya se emita por consola."""
    logs_dir = get_paths()["logs"]
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"sql_inventory_{connection}_{timestamp}.log"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    return handler, log_path


def run_sql_inventory(connection: str) -> InventoryResult:
    """Ejecuta las 11 consultas de catálogo para `connection` y ensambla el
    resultado en memoria (no escribe nada a disco -- ver `save_inventory`).

    Fail-fast: si falla cualquier categoría, se propaga la excepción de
    inmediato y no se devuelve ningún resultado parcial.

    El servidor y la base se toman de `ConnectionSpec` (src/db/connection.py)
    -- nunca se serializa una URL, cadena ODBC ni objeto Engine para
    obtenerlos.
    """
    handler, log_path = _attach_file_log_handler(connection)
    try:
        logger.info("Iniciando inventario SQL Server (conexión=%s)", connection)
        spec = get_connection_spec(connection)
        query_dir = get_paths()["sql_diagnostics"] / "sql_server_inventory"

        artifacts: dict[str, pd.DataFrame] = {}
        for category, filename in CATEGORY_QUERY_FILES.items():
            df = run_query_file(query_dir / filename, connection=connection)
            artifacts[category] = _sorted(category, df)
            logger.info("Categoría '%s': %d filas", category, len(artifacts[category]))

        artifacts["table_relationships"] = _sorted(
            "table_relationships", _derive_table_relationships(artifacts["foreign_keys"])
        )
        logger.info(
            "Categoría 'table_relationships': %d filas (derivada, sin query adicional)",
            len(artifacts["table_relationships"]),
        )

        result = InventoryResult(
            connection=connection,
            database=spec.database,
            server=spec.server,
            generated_at=datetime.now(timezone.utc),
            artifacts=artifacts,
        )
        logger.info("Inventario ensamblado correctamente (conexión=%s)", connection)
        return result
    except Exception:
        logger.exception(
            "Fallo generando el inventario (conexión=%s) -- abortando sin generar salida parcial.",
            connection,
        )
        raise
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def save_inventory(result: InventoryResult, base_output_dir: Path | str | None = None) -> Path:
    """Persiste un InventoryResult ya ensamblado bajo
    `<base_output_dir>/<conexión>/<YYYYMMDD_HHMMSS>/` de forma atómica.

    Escribe primero en una carpeta temporal hermana (`.tmp_<uuid>`, mismo
    padre que la carpeta definitiva, para que el rename final sea atómico
    dentro del mismo volumen). Si algo falla durante la escritura, la
    carpeta temporal se borra y se relanza la excepción -- la carpeta
    definitiva nunca llega a existir a medias.
    """
    base_dir = Path(base_output_dir) if base_output_dir is not None else get_paths()["outputs"] / "inventory"
    connection_dir = base_dir / result.connection
    connection_dir.mkdir(parents=True, exist_ok=True)

    timestamp = result.generated_at.strftime("%Y%m%d_%H%M%S")
    final_dir = connection_dir / timestamp
    tmp_dir = connection_dir / f".tmp_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=False)

    csv_encoding = get_general_settings().get("default_encoding", "utf-8-sig")

    try:
        artifact_manifest = []
        for name, df in result.artifacts.items():
            filename = f"{name}.csv"
            df.to_csv(tmp_dir / filename, index=False, encoding=csv_encoding)
            artifact_manifest.append({"name": filename, "rows": int(len(df))})

        manifest = {
            "status": "complete",
            "inventory_version": 1,
            "connection": result.connection,
            "database": result.database,
            "server": result.server,
            "generated_at": result.generated_at.isoformat(),
            "artifacts": artifact_manifest,
        }
        # manifest.yaml en utf-8 plano (sin BOM) -- el BOM configurado como
        # encoding general es para los CSV, no para YAML.
        with open(tmp_dir / "manifest.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest, f, sort_keys=False, allow_unicode=True)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    tmp_dir.rename(final_dir)
    logger.info("Inventario guardado en %s", final_dir)
    return final_dir


def run_and_save_inventory(connection: str, base_output_dir: Path | str | None = None) -> Path:
    """Atajo: ejecuta `run_sql_inventory` y `save_inventory` encadenados."""
    result = run_sql_inventory(connection)
    return save_inventory(result, base_output_dir=base_output_dir)
