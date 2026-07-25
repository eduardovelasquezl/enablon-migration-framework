"""Localización de una ejecución de Drills (última o explícita) y lectura
de sus artefactos ya escritos. Nunca vuelve a consultar SQL Server ni abre
ningún Excel de ETL -- todo lo que necesita ya está en disco, escrito por
`src.export.prototype.drills.pipeline`.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.config import PROJECT_ROOT

from .catalog import load_open_questions
from .models import EvidenceSourceError, RunEvidenceContext

DEFAULT_RUNS_ROOT = PROJECT_ROOT / "outputs" / "prototype" / "drills"
OUTPUTS_ROOT = PROJECT_ROOT / "outputs"

REQUIRED_QUESTION_IDS = ["OQ-ETL-05", "OQ-ETL-06", "OQ-ENT-04", "OQ-ETL-02", "OQ-OBJ-07"]

EXPECTED_MIGRATION_OBJECT = "Drills"


def _assert_within_outputs(path: Path) -> None:
    outputs_root = OUTPUTS_ROOT.resolve()
    try:
        path.resolve().relative_to(outputs_root)
    except ValueError:
        raise EvidenceSourceError(
            f"La ruta de ejecución debe estar dentro de {outputs_root} (se recibió: {path})."
        )


def find_latest_run(runs_root: Path | None = None) -> Path:
    """Última ejecución disponible bajo `outputs/prototype/drills/`
    (o `runs_root`), determinada por orden lexicográfico del nombre de
    carpeta (`%Y%m%dT%H%M%SZ`, ya ordenable como texto)."""
    root = runs_root or DEFAULT_RUNS_ROOT
    if not root.is_dir():
        raise EvidenceSourceError(f"No existe el directorio de ejecuciones: {root}")
    candidates = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
    for candidate in candidates:
        if (candidate / "validation_report.yaml").is_file():
            return candidate
    raise EvidenceSourceError(
        f"No se encontró ninguna ejecución con validation_report.yaml bajo {root}."
    )


def resolve_run_dir(run: str | Path | None, runs_root: Path | None = None) -> Path:
    """Resuelve `run` a un directorio de ejecución real:

    - `None` -> la última ejecución disponible.
    - Una ruta existente (absoluta o relativa a la raíz del repo) -> esa carpeta.
    - Un `run_id` suelto (sin separadores de ruta) -> se busca cuál
      ejecución existente declara ese `run_id` en su `validation_report.yaml`.

    Rechaza explícitamente cualquier ruta fuera de `outputs/` (Fase 9).
    """
    root = runs_root or DEFAULT_RUNS_ROOT

    if run is None:
        return find_latest_run(root)

    run_str = str(run)
    run_path = Path(run_str)
    candidate = run_path if run_path.is_absolute() else (PROJECT_ROOT / run_path)
    if candidate.is_dir():
        resolved = candidate.resolve()
        _assert_within_outputs(resolved)
        return resolved

    looks_like_bare_id = ("/" not in run_str) and ("\\" not in run_str)
    if looks_like_bare_id and root.is_dir():
        for entry in sorted(root.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            vr_path = entry / "validation_report.yaml"
            if not vr_path.is_file():
                continue
            try:
                data = yaml.safe_load(vr_path.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            if data and data.get("run", {}).get("run_id") == run_str:
                return entry.resolve()

    raise EvidenceSourceError(f"No se pudo resolver la ejecución solicitada: {run!r}")


def _load_yaml_or_raise(path: Path, label: str) -> dict:
    if not path.is_file():
        raise EvidenceSourceError(f"Falta {label} en la ejecución: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EvidenceSourceError(f"{label} no es un YAML válido ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceSourceError(f"{label} no tiene la forma esperada (objeto YAML): {path}")
    return data


def _load_issues(path: Path) -> tuple[dict, ...]:
    if not path.is_file():
        raise EvidenceSourceError(
            f"Esta ejecución no tiene 'issues.jsonl' ({path}) -- es de una versión "
            "anterior al Evidence Engine y no tiene detalle de incidencias por "
            "fila. No se puede generar evidencia sin inventar filas; vuelve a "
            "ejecutar 'export drills' para producir una ejecución compatible."
        )
    issues = []
    text = path.read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            issues.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise EvidenceSourceError(f"Línea {line_no} de {path} no es JSON válido: {exc}") from exc
    return tuple(issues)


def load_run(run_dir: Path) -> RunEvidenceContext:
    """Construye el contexto completo de evidencia para `run_dir`,
    validando estructuralmente cada artefacto. No reinterpreta ningún
    valor -- solo los expone tal cual están escritos."""
    if not run_dir.is_dir():
        raise EvidenceSourceError(f"El directorio de ejecución no existe: {run_dir}")

    validation_report = _load_yaml_or_raise(run_dir / "validation_report.yaml", "validation_report.yaml")
    export_manifest = _load_yaml_or_raise(run_dir / "export_manifest.yaml", "export_manifest.yaml")

    comparison_path = run_dir / "comparison_report.yaml"
    comparison_report = None
    if comparison_path.is_file():
        comparison_report = _load_yaml_or_raise(comparison_path, "comparison_report.yaml")

    run_section = validation_report.get("run", {})
    migration_object = run_section.get("migration_object")
    if migration_object != EXPECTED_MIGRATION_OBJECT:
        raise EvidenceSourceError(
            f"Esta ejecución es de '{migration_object}', no de "
            f"'{EXPECTED_MIGRATION_OBJECT}' -- el Evidence Engine v0.1 está "
            f"limitado a Drills ({run_dir})."
        )

    if "approved_for_enablon_import" not in export_manifest:
        raise EvidenceSourceError(
            f"export_manifest.yaml no declara 'approved_for_enablon_import' -- "
            f"no se genera evidencia sobre un manifiesto incompleto ({run_dir})."
        )

    issues = _load_issues(run_dir / "issues.jsonl")

    output_path = run_dir / "drills.csv"
    if not output_path.is_file():
        raise EvidenceSourceError(f"Falta drills.csv en la ejecución: {run_dir}")
    csv_columns = tuple(export_manifest.get("output", {}).get("columns", []))

    open_questions = load_open_questions(REQUIRED_QUESTION_IDS)

    return RunEvidenceContext(
        run_dir=run_dir,
        run_id=run_section.get("run_id", "?"),
        timestamp=run_section.get("timestamp", "?"),
        mode=run_section.get("mode", "?"),
        connection_name=run_section.get("connection_name", "?"),
        migration_object=migration_object,
        prototype_status=run_section.get("prototype_status", "review_only"),
        approved_for_enablon_import=bool(export_manifest["approved_for_enablon_import"]),
        validation_report=validation_report,
        export_manifest=export_manifest,
        comparison_report=comparison_report,
        issues=issues,
        open_questions=open_questions,
        csv_path=output_path,
        csv_columns=csv_columns,
    )
