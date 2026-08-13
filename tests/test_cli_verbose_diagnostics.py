"""Tests CLI del flag `--verbose` como mecanismo de diagnóstico (Sprint 9.1).

Contexto: el primer intento real de ejecutar `run ... --verbose` falló con
`Error: No such option '--verbose'` porque `--verbose` es una opción del
GRUPO `cli` (`main.py [OPTIONS] COMMAND ...`), no de cada subcomando --
en Click, las opciones de grupo deben preceder al nombre del subcomando
(`main.py --verbose run ...`), nunca ir después. Este archivo fija ese
comportamiento con tests, para que no vuelva a asumirse mal.

Ninguno de estos tests abre SQL real -- se sustituye
`src.db.query_runner.get_engine` por un engine falso cuyo `.connect()` /
`.execute()` lanza una excepción de SQLAlchemy sintética, ejercitando el
mismo camino de código (`run_query` -> `except SQLAlchemyError` ->
`logger.debug(...)` -> `raise QueryExecutionError(...) from exc`) que
tomaría un fallo real, sin tocar la red.

Ejecutar con: pytest tests/test_cli_verbose_diagnostics.py -v
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from click.testing import CliRunner
from sqlalchemy.exc import OperationalError

import src.db.query_runner as qr_mod
from src.cli import cli


def _clear_root_handlers() -> None:
    """`logging.basicConfig()` (llamada por `_configure_logging` en cada
    invocación de `cli()`) es un no-op si el root logger YA tiene handlers.

    Se limpia justo antes de cada `invoke()`, dentro del cuerpo del test
    -- NO en un fixture `autouse` de "setup": el plugin de logging de
    pytest reenvuelve cada fase (setup/call/teardown) con su propio
    contexto de captura, reinstalando sus handlers en el root logger entre
    fases. Un fixture que limpia durante "setup" no sobrevive a la fase
    "call", donde ocurre la invocación real -- confirmado empíricamente
    (un `autouse` con `yield` no bastaba; limpiar en el punto exacto de
    invocación sí). Así se reproduce, dentro del test, el mismo estado
    "sin handlers todavía" de un proceso `python main.py ...` real
    (siempre nuevo)."""
    logging.getLogger().handlers.clear()


class _FailingConn:
    def __init__(self, exc: Exception):
        self._exc = exc

    def execute(self, *args, **kwargs):
        raise self._exc

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FailingEngine:
    def __init__(self, exc: Exception):
        self._exc = exc

    def connect(self):
        return _FailingConn(self._exc)


def _fake_operational_error(detail: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(detail))


@pytest.fixture
def failing_get_engine(monkeypatch):
    """Sustituye `src.db.query_runner.get_engine` por un engine que siempre
    falla con un `OperationalError` sintético -- nunca llega a
    `src.db.connection.get_engine()`, así que tampoco al SQL Execution
    Guard real ni a ninguna credencial."""
    fake_exc = _fake_operational_error("Login failed for user 'ClaudeReadOnly'. (18456)")
    monkeypatch.setattr(qr_mod, "get_engine", lambda name=None: _FailingEngine(fake_exc))
    return fake_exc


def _run(*args):
    _clear_root_handlers()
    return CliRunner().invoke(cli, list(args))


# --------------------------------------------------------------------------
# Sintaxis: dónde vive realmente --verbose
# --------------------------------------------------------------------------

def test_verbose_documentado_en_ayuda_del_grupo():
    result = _run("--help")
    assert result.exit_code == 0
    assert "--verbose" in result.output


def test_verbose_no_documentado_en_ayuda_de_run():
    """`run --help` no lista `--verbose` -- confirma que no es una opción
    de ese subcomando (ver docstring del módulo)."""
    result = _run("run", "--help")
    assert result.exit_code == 0
    assert "--verbose" not in result.output


def test_verbose_despues_de_run_falla_no_such_option():
    """Reproduce EXACTAMENTE el error que devolvió el primer intento real:
    `python main.py run ... --verbose` -> `Error: No such option '--verbose'`."""
    result = _run(
        "run", "--project", "moeve", "--object", "drills",
        "--mode", "sample", "--limit", "1", "--allow-real-sql", "--verbose",
    )
    assert result.exit_code != 0
    assert "No such option" in result.output
    assert "--verbose" in result.output


def test_verbose_antes_de_run_es_aceptado_por_el_parser():
    """Sintaxis correcta: `--verbose` es una opción del grupo `cli`, debe
    preceder al nombre del subcomando."""
    result = _run("--verbose", "run", "--help")
    assert result.exit_code == 0
    assert "No such option" not in result.output


# --------------------------------------------------------------------------
# Comportamiento end-to-end (engine falso, sin SQL real)
# --------------------------------------------------------------------------

def test_modo_normal_no_muestra_causa_tecnica(failing_get_engine, tmp_path):
    result = _run(
        "run", "--project", "moeve", "--object", "drills", "--mode", "sample",
        "--limit", "1", "--output-dir", str(tmp_path), "--allow-real-sql",
    )
    assert result.exit_code != 0
    assert "ERROR de base de datos" in result.output
    # El mensaje amigable no cambia; la causa técnica NO debe aparecer.
    assert "OperationalError" not in result.output
    assert "Login failed" not in result.output


def test_verbose_muestra_causa_tecnica_saneada(failing_get_engine, tmp_path):
    result = _run(
        "--verbose", "run", "--project", "moeve", "--object", "drills",
        "--mode", "sample", "--limit", "1", "--output-dir", str(tmp_path),
        "--allow-real-sql",
    )
    assert result.exit_code != 0
    assert "ERROR de base de datos" in result.output
    assert "OperationalError" in result.output
    assert "Login failed for user 'ClaudeReadOnly'" in result.output


def test_verbose_no_expone_credenciales_incrustadas_por_el_driver(monkeypatch, tmp_path):
    """Si el propio driver/mensaje de error incrusta algo con pinta de
    credencial, ni siquiera --verbose debe mostrarlo -- ver
    `_sanitize_error_detail` en `src/db/query_runner.py`."""
    fake_exc = _fake_operational_error(
        "Login failed. Retry with Password=SuperSecret123 against the server."
    )
    monkeypatch.setattr(qr_mod, "get_engine", lambda name=None: _FailingEngine(fake_exc))

    result = _run(
        "--verbose", "run", "--project", "moeve", "--object", "drills",
        "--mode", "sample", "--limit", "1", "--output-dir", str(tmp_path),
        "--allow-real-sql",
    )
    assert result.exit_code != 0
    assert "SuperSecret123" not in result.output
    assert "REDACTED" in result.output


def test_ningun_test_de_este_archivo_requiere_sql_real(failing_get_engine):
    """Confirma el patrón general: engine sustituido, sin credenciales ni
    autorización real de `sql_execution_guard` (el mock nunca llega a
    `src.db.connection.get_engine`, que es donde vive el chokepoint real)."""
    from src.db import sql_execution_guard
    assert sql_execution_guard.is_authorized() is False
