"""Configuración compartida de la suite de tests.

Sprint 8.6.1 (SQL Execution Guard): ningún test debe heredar una
autorización de SQL real concedida por otro test, ni dejarla concedida
para el resto de la sesión -- `sql_execution_guard.revoke()` se llama de
forma autouse antes y después de CADA test, sin excepción. Esto es lo que
garantiza que "tests con mocks/fakes no requieran --allow-real-sql" (no
necesitan autorización porque nunca llegan al `get_engine()` real) y que
un test que sí la concede explícitamente (p. ej. `fake_config` en
`tests/test_db_connection.py`) no la deje filtrada al siguiente test de
la sesión.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.db import sql_execution_guard


@pytest.fixture(autouse=True)
def _reset_sql_execution_guard():
    sql_execution_guard.revoke()
    yield
    sql_execution_guard.revoke()
