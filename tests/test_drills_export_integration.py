"""Test de integración OPT-IN del prototipo de exportación de Drills contra
SQL Server real, en modo `sample`.

Deshabilitado por defecto (mismo patrón que el resto de tests de este
repositorio que requieren red -- ver tests/test_db_connection.py). Activar
con:

    RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1 pytest tests/test_drills_export_integration.py -v

Solo lectura: usa `main.run(mode="sample", limit=...)`, que a su vez usa
`src.db.query_runner.run_query` (validación de solo lectura + límite de
filas). Nunca ejecuta modo `full` automáticamente. Escribe únicamente bajo
un directorio temporal de pytest (`tmp_path`) -- nunca bajo `outputs/` real
-- y no requiere borrado explícito porque pytest limpia `tmp_path` por su
cuenta entre sesiones.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

_INTEGRATION_GATE_OFF = os.environ.get("RUN_DRILLS_EXPORT_INTEGRATION_TESTS") != "1"

pytestmark = pytest.mark.skipif(
    _INTEGRATION_GATE_OFF,
    reason="Test de integración opt-in -- activar con RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1",
)


def test_export_sample_contra_sql_server_real(tmp_path):
    from src.export.prototype.drills.pipeline import run

    result = run(mode="sample", limit=10, output_root=tmp_path)

    assert result.csv_path.is_file()
    assert result.validation_report_path.is_file()
    assert result.manifest_path.is_file()

    assert result.manifest["approved_for_enablon_import"] is False
    assert result.stats.rows_exported <= 10

    # El CSV debe ser reabrible y UTF-8 -- reconfirma lo que ya valida
    # `validator.validate_output_csv`, esta vez sobre datos reales.
    text = result.csv_path.read_text(encoding="utf-8")
    assert text.splitlines()[0].split("\t") == [
        "CS_Typology", "Reference", "StartingDate", "CS_HistoricalOriginID",
        "CS_Letter", "CS_ImpactedEntities", "CS_WorkflowStatus", "CS_HistoricalDataOrigin",
    ]

    # Confirmar por rutas absolutas que todo quedó bajo tmp_path -- nunca
    # bajo outputs/ real ni sobrescribiendo una ejecución anterior.
    assert str(result.output_dir).startswith(str(tmp_path))


def test_export_sample_con_evidencia_contra_sql_server_real(tmp_path):
    """Igual que el test anterior, pero además genera ambas evidencias
    (Fase 12 del incremento de Evidence Engine). Sigue en modo `sample`
    únicamente -- nunca se ejecuta `full` en un test."""
    from src.evidence.collector import load_run
    from src.evidence.workbook import build_workbook, save_workbook
    from src.export.prototype.drills.pipeline import run

    result = run(mode="sample", limit=10, output_root=tmp_path)
    ctx = load_run(result.output_dir)

    for audience in ("internal", "client"):
        wb = build_workbook(ctx, audience)
        path = save_workbook(wb, result.output_dir / f"evidence_{audience}.xlsx")
        assert path.is_file()
        assert str(path).startswith(str(tmp_path))


# --------------------------------------------------------------------------
# Query Engine v0.1 -- filtro real contra SQL Server (opt-in adicional)
#
# Además del gate general de este fichero (RUN_DRILLS_EXPORT_INTEGRATION_TESTS),
# este test concreto exige DRILLS_FILTER_INTEGRATION_TEST_ID: el IDSimulacro
# real de una fila conocida en ITP_SIMULACRO. No se fabrica ni se asume
# ningún ID -- sin conectividad a SQL Server desde este repositorio no hay
# forma honesta de conocer uno, así que quien ejecute el test con acceso
# real debe aportarlo explícitamente:
#
#   RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1 \
#   DRILLS_FILTER_INTEGRATION_TEST_ID=<IDSimulacro real> \
#   pytest tests/test_drills_export_integration.py -v -k query_engine
# --------------------------------------------------------------------------

_FILTER_TEST_ID_RAW = os.environ.get("DRILLS_FILTER_INTEGRATION_TEST_ID")

pytestmark_query_engine = pytest.mark.skipif(
    _INTEGRATION_GATE_OFF or not _FILTER_TEST_ID_RAW,
    reason=(
        "Test de integración opt-in del Query Engine -- activar con "
        "RUN_DRILLS_EXPORT_INTEGRATION_TESTS=1 y "
        "DRILLS_FILTER_INTEGRATION_TEST_ID=<IDSimulacro real conocido>"
    ),
)


@pytestmark_query_engine
def test_query_engine_filtro_historical_origin_id_contra_sql_server_real(tmp_path):
    """Cubre, contra SQL Server real, los 6 puntos exigidos por el
    incremento para el test opt-in del Query Engine v0.1:

    1-2. El resultado filtrado contiene únicamente el ID solicitado.
    3-4. `generated_query.sql` existe, contiene el placeholder y NUNCA el
         valor interpolado como literal SQL.
    5.   El manifiesto registra el filtro aplicado.
    6.   La SQL fuente original (`sql/source_queries/`) no se altera.

    (El punto 7 -- "no se realiza ninguna escritura en SQL Server" -- es una
    garantía estructural de `validate_read_only_sql` + el rol de solo
    lectura del login SQL, no algo que este test pueda verificar por
    introspección sin permisos de administración de base de datos.)
    """
    import csv as csv_module

    import yaml

    from src.export.prototype.drills.pipeline import run
    from src.query.catalog import DRILLS_FILTER_CATALOG
    from src.query.validator import compile_filter_tokens

    known_id = int(_FILTER_TEST_ID_RAW)

    source_sql_path = (
        Path(__file__).resolve().parents[1]
        / "sql" / "source_queries" / "Simulacros" / "SQLQuery - DATASET SIMULACRO.sql"
    )
    source_before = source_sql_path.read_bytes()

    compiled_filters = compile_filter_tokens(
        [f"historical_origin_id:eq:{known_id}"], DRILLS_FILTER_CATALOG
    )

    result = run(mode="sample", limit=10, output_root=tmp_path, compiled_filters=compiled_filters)

    # 1-2. El CSV filtrado contiene únicamente el ID solicitado.
    with result.csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv_module.DictReader(f, delimiter="\t")
        rows = list(reader)
    assert rows, (
        f"No se devolvió ninguna fila para historical_origin_id={known_id} -- "
        "confirma que DRILLS_FILTER_INTEGRATION_TEST_ID corresponde a un "
        "IDSimulacro real existente en ITP_SIMULACRO."
    )
    assert {row["CS_HistoricalOriginID"] for row in rows} == {str(known_id)}

    # 3-4. generated_query.sql existe, tiene placeholder, nunca el valor.
    generated_path = result.output_dir / "generated_query.sql"
    assert generated_path.is_file()
    generated_text = generated_path.read_text(encoding="utf-8")
    assert ":filter_1" in generated_text
    assert f"= {known_id}" not in generated_text
    assert str(known_id) not in generated_text.split("SELECT", 1)[-1].split("WHERE")[0]

    # 5. El manifiesto registra el filtro tal cual se pidió.
    manifest_text = result.manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_text)
    assert manifest["query_filters"]["applied"] is True
    assert manifest["query_filters"]["count"] == 1
    assert manifest["query_filters"]["expressions"] == [
        {"field": "historical_origin_id", "operator": "eq", "value": known_id}
    ]
    assert manifest["query_filters"]["generated_sql_file"] == "generated_query.sql"
    assert str(known_id) not in manifest_text

    # 6. La SQL fuente original no se altera en disco.
    assert source_sql_path.read_bytes() == source_before
