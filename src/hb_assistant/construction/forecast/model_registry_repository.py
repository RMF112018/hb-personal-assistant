"""Idempotent writers + per-run provenance persister for the v72 model-registry tables.

P6 / Gap 6. Reads an accuracy package's ``model_methodology.json`` (the deterministic, path-free
methodology descriptor CFR emits) plus its ``audit/calibration_snapshot.json`` and records, into a
NON-LIVE temp DB:

- forecast_model_versions       : one immutable row per methodology (deduped by methodology_sha256).
- forecast_run_model_versions   : the methodology version in effect for this run.
- forecast_calibration_weights  : per-method calibration provenance; ``calibration_source`` marks
                                  which of the 7 estimators the backtest actually weighted.

Writes are UPSERTs on each table's PK so re-running an apply is idempotent (``created_utc`` and
conflict-key columns are never overwritten). Scores/weights are TEXT, never floats. Population is
gated by the caller (the P6 governance flag) and never targets the live DB.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

MODEL_METHODOLOGY_FILE = "model_methodology.json"
CALIBRATION_SNAPSHOT_FILE = "audit/calibration_snapshot.json"

_IMMUTABLE = {"created_utc"}


class ModelMethodologyMissingError(FileNotFoundError):
    """Raised when an accuracy package has no model_methodology.json (fail-closed under the flag)."""


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    values: dict[str, Any],
    conflict_cols: tuple[str, ...],
) -> None:
    cols = list(values)
    placeholders = ", ".join("?" for _ in cols)
    frozen = set(conflict_cols) | _IMMUTABLE
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in frozen)
    conflict = ", ".join(conflict_cols)
    if assignments:
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {assignments}"
        )
    else:
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO NOTHING"
        )
    conn.execute(sql, tuple(values[c] for c in cols))


def upsert_model_version(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_model_versions", row, ("model_version_id",))


def upsert_run_model_version(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_run_model_versions", row, ("run_id",))


def upsert_calibration_weight(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    _upsert(conn, "forecast_calibration_weights", row, ("id",))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp_from_package_name(name: str) -> str | None:
    """Best-effort extraction of the trailing YYYYMMDD_HHMMSS stamp from the package dir name."""
    parts = name.rsplit("_", 2)
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return f"{parts[1]}_{parts[2]}"
    return None


def has_methodology(accuracy_package: Path) -> bool:
    return (Path(accuracy_package) / MODEL_METHODOLOGY_FILE).is_file()


def build_provenance_rows(
    *,
    run_id: str,
    project_key: str,
    accuracy_package: Path,
    now_utc: str,
    stamp: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Pure read: return (model_version_row, run_model_version_row, calibration_rows)."""
    pkg = Path(accuracy_package)
    methodology_path = pkg / MODEL_METHODOLOGY_FILE
    if not methodology_path.is_file():
        raise ModelMethodologyMissingError(str(methodology_path))
    methodology = _read_json(methodology_path)
    sha = methodology["methodology_sha256"]
    label = methodology.get("version_label") or f"methodology-{sha[:12]}"

    model_version = {
        "model_version_id": sha,
        "version_label": label,
        "methodology_sha256": sha,
        "estimator_order_json": json.dumps(methodology.get("estimator_order", []), sort_keys=True),
        "reliability_weights_json": json.dumps(
            methodology.get("reliability_weights", {}), sort_keys=True
        ),
        "thresholds_json": json.dumps(methodology.get("thresholds", {}), sort_keys=True),
        "cohort_json": json.dumps(methodology.get("cohort", {}), sort_keys=True),
        "source": "cfr_accuracy_package",
        "raw_json": json.dumps(methodology, sort_keys=True),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    run_model_version = {
        "run_id": run_id,
        "model_version_id": sha,
        "project_key": project_key,
        "version_label": label,
        "methodology_sha256": sha,
        "accuracy_package_stamp": stamp or _stamp_from_package_name(pkg.name),
        "raw_json": json.dumps(
            {"run_id": run_id, "model_version_id": sha, "version_label": label}, sort_keys=True
        ),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }
    calibration_rows = _calibration_rows(pkg, methodology, run_id, project_key, now_utc)
    return model_version, run_model_version, calibration_rows


def _calibration_rows(
    pkg: Path,
    methodology: dict[str, Any],
    run_id: str,
    project_key: str,
    now_utc: str,
) -> list[dict[str, Any]]:
    estimator_order = methodology.get("estimator_order", [])
    independent = set(methodology.get("independent_methods", []))
    erp = set(methodology.get("erp_methods", []))
    backtest_methods = set(methodology.get("cohort", {}).get("backtest_methods", []))

    summary: dict[str, dict[str, Any]] = {}
    weights: dict[str, Any] = {}
    snap_path = pkg / CALIBRATION_SNAPSHOT_FILE
    if snap_path.is_file():
        snap = _read_json(snap_path)
        for entry in snap.get("summary_by_method", []) or []:
            method = entry.get("method")
            if method is not None:
                summary[method] = entry
        weights = snap.get("calibration_weights", {}) or {}

    rows: list[dict[str, Any]] = []
    for method in estimator_order:
        mape: Any = None
        mean_bias: Any = None
        calibration_weight: Any = None
        if method in backtest_methods:
            source = "backtest"
            s = summary.get(method, {})
            mape = s.get("mape")
            mean_bias = s.get("mean_bias")
            calibration_weight = weights.get(method)
            reason = f"backtest-calibrated (cohort MAPE {mape})"
        elif method in independent:
            source = "not_backtested"
            reason = "independent estimator omitted from the backtest cohort"
        elif method in erp:
            source = "reliability_only"
            reason = "ERP baseline: comparison-only, no calibration multiplier"
        else:
            source = "reliability_only"
            reason = "uncategorized method; no calibration multiplier"
        rows.append(
            {
                "id": f"fcw-{run_id}-{method}",
                "run_id": run_id,
                "project_key": project_key,
                "method": method,
                "calibration_source": source,
                "mape": mape,
                "mean_bias": mean_bias,
                "calibration_weight": calibration_weight,
                "reliability_weight": None,
                "reason": reason,
                "raw_json": json.dumps(
                    {
                        "method": method,
                        "calibration_source": source,
                        "mape": mape,
                        "mean_bias": mean_bias,
                        "calibration_weight": calibration_weight,
                    },
                    sort_keys=True,
                ),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )
    return rows


def persist_run_model_provenance(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    project_key: str,
    accuracy_package: Path,
    now_utc: str,
    stamp: str | None = None,
) -> dict[str, Any]:
    """Upsert the model-version, run-linkage, and calibration rows. Returns a small summary."""
    model_version, run_model_version, calibration_rows = build_provenance_rows(
        run_id=run_id,
        project_key=project_key,
        accuracy_package=accuracy_package,
        now_utc=now_utc,
        stamp=stamp,
    )
    upsert_model_version(conn, model_version)
    upsert_run_model_version(conn, run_model_version)
    for row in calibration_rows:
        upsert_calibration_weight(conn, row)
    return {
        "model_version_id": model_version["model_version_id"],
        "version_label": model_version["version_label"],
        "methodology_sha256": model_version["methodology_sha256"],
        "calibration_methods": len(calibration_rows),
    }


def read_run_model_version(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT raw_json FROM forecast_run_model_versions WHERE run_id = ?", (run_id,)
    ).fetchone()
    return json.loads(row[0]) if row else None
