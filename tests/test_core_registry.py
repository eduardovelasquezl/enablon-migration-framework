"""Tests unitarios del StageRegistry (Fase 3) -- registro explícito,
sin descubrimiento dinámico.

Ejecutar con: pytest tests/test_core_registry.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from src.core.exceptions import DuplicateStageRegistrationError, StageNotRegisteredError
from src.core.registry import StageRegistry


class _FakeStage:
    name = "fake"

    def execute(self, context, stage_input):  # pragma: no cover -- no se invoca en estos tests
        raise NotImplementedError


def test_registro_y_resolucion_basicos():
    registry = StageRegistry()
    stage = _FakeStage()
    registry.register("fake", stage)
    assert registry.resolve("fake") is stage


def test_resolver_etapa_no_registrada_lanza_error_explicito():
    registry = StageRegistry()
    with pytest.raises(StageNotRegisteredError):
        registry.resolve("no_existe")


def test_registro_duplicado_sin_overwrite_lanza_error():
    registry = StageRegistry()
    registry.register("fake", _FakeStage())
    with pytest.raises(DuplicateStageRegistrationError):
        registry.register("fake", _FakeStage())


def test_registro_duplicado_con_overwrite_reemplaza():
    registry = StageRegistry()
    first = _FakeStage()
    second = _FakeStage()
    registry.register("fake", first)
    registry.register("fake", second, overwrite=True)
    assert registry.resolve("fake") is second


def test_is_registered():
    registry = StageRegistry()
    assert registry.is_registered("fake") is False
    registry.register("fake", _FakeStage())
    assert registry.is_registered("fake") is True


def test_registered_names_devuelve_tupla_ordenada():
    registry = StageRegistry()
    registry.register("zeta", _FakeStage())
    registry.register("alfa", _FakeStage())
    assert registry.registered_names() == ("alfa", "zeta")


def test_dos_registries_no_comparten_estado():
    """No Hidden State (ADR-010): dos instancias de StageRegistry no deben
    interferirse -- confirma que no hay ningún registro global de módulo."""
    registry_a = StageRegistry()
    registry_b = StageRegistry()
    registry_a.register("fake", _FakeStage())
    assert registry_a.is_registered("fake") is True
    assert registry_b.is_registered("fake") is False
