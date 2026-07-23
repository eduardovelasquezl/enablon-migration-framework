"""Test de humo del motor de volumetría con datos sintéticos que reproducen
el patrón del Hallazgo #1 (un site grande en origen, casi ausente en real)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.analysis.volumetry import EntityCatalog, compare_volumetry


def test_compare_volumetry_detecta_gap_por_site(caplog):
    catalog = EntityCatalog(
        code_to_site={"LR01": "Servicio Prevención LA RABIDA", "ALG01": "Algeciras"},
        ruta_to_site={},
    )
    origen = pd.DataFrame({"entidad": ["LR01"] * 40 + ["ALG01"] * 60})
    enablon_real = pd.DataFrame({"entidad": ["LR01"] * 2 + ["ALG01"] * 58})

    with caplog.at_level("WARNING"):
        comp = compare_volumetry(origen, "entidad", enablon_real, "entidad", catalog)

    assert comp.loc["Servicio Prevención LA RABIDA", "Origen_SQL"] == 40
    assert comp.loc["Servicio Prevención LA RABIDA", "Enablon_real"] == 2
    assert comp.loc["TOTAL", "Origen_SQL"] == 100
    assert any("HALLAZGO #1" in rec.message for rec in caplog.records)
