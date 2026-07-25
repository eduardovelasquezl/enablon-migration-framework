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

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DRILLS_EXPORT_INTEGRATION_TESTS") != "1",
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
