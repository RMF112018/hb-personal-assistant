"""Phase 9 — controlled DB-backed context->analysis workflow (orchestration only).

One explicit, auditable, operator-safe operation that runs the proven controlled chain end to end:

    context generation (Phase 6) -> analysis generation (Phase 7) -> explicit package resolution
    (Phase 8) -> deterministic chain manifest (Phase 8) -> operator workflow report.

It is purely an orchestration layer over the existing Phase 6/7/8 building blocks; it adds no
schema, no DB resolver, no LLM/model-backed step, and changes NO production default. It does NOT run
intelligence, comprehensive, probability, monthly, model-controls, final-integrated forecast, or any
CSV generation. DB-backed reads stay default-off: the ``db`` mode is an explicit operator choice,
gated by the Phase 6 runner's own fail-closed DB-path/live-DB validation.

Everything is written under an explicit ``work_root`` (``<work_root>/file`` or ``<work_root>/db``);
nothing is ever written under the live Synology forecast root, and no recency-based (latest-glob)
discovery is used anywhere.

CFR-only / stdlib: this module imports the Phase 6 runner, the Phase 7 runner, and the Phase 8
resolver — never ``hb_assistant`` directly. The only DB touchpoint is the Phase 6 runner's lazy,
fail-closed DB branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..analysis.final_forecast_runner import run_final_forecast_generation
from ..common.package_resolution import (
    build_package_chain,
    resolve_explicit_package,
    write_package_chain_manifest,
)
from ..context.context_generation_runner import run_context_generation

# Phase 9 is Tropical-only, exactly like the underlying Phase 6/7/8 runners.
SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1
PARITY_REPORT_SCHEMA_VERSION = 1

_MODES = ("file", "db")
_CONTEXT_PREFIX = "forecast_context_package_tropical_"
_ANALYSIS_PREFIX = "forecast_analysis_package_tropical_"
_ANALYSIS_GLOB = "forecast_analysis_package_tropical_*"
DEFAULT_CHAIN_MANIFEST_NAME = "forecast_package_chain_manifest.json"
WORKFLOW_REPORT_NAME = "controlled_workflow_report.json"
PARITY_REPORT_NAME = "controlled_workflow_parity_report.json"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an
# authoritative environment resolver. Monkeypatched in tests. The Phase 6/7 runners enforce their
# own (identical) live-root guards; this one fails Phase 9's preflight early, before any output.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)

# Approved volatile metadata for parity normalization (mirrors Phase 5/7): the only fields allowed
# to differ between a file-backed and a DB-backed run. Financial/domain values are NEVER normalized.
_VOLATILE_KEYS = {"generated_stamp", "generated_timestamp_local", "package_name", "input_root"}
# Verbatim script copy the context generator drops in the package; identical across runs, skipped to
# mirror the Phase 5 parity loader.
_SKIP_BASENAMES = {"generate_forecast_context_package.py"}


class ControlledWorkflowError(RuntimeError):
    """Raised when Phase 9's own preflight rejects a controlled workflow run (fail closed)."""


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def run_controlled_context_analysis_workflow(
    *,
    data_root: Path,
    work_root: Path,
    context_stamp: str,
    mode: str,
    db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
    run_id: str | None = None,
    chain_manifest_name: str = DEFAULT_CHAIN_MANIFEST_NAME,
) -> dict[str, Any]:
    """Run the controlled context->analysis chain once, in ``file`` or ``db`` mode.

    Writes the context package, the analysis package, a deterministic chain manifest, and an operator
    report under ``<work_root>/<mode>/``. Returns the operator report dict (plus ``report_path``).

    Fails closed via ``ControlledWorkflowError`` — BEFORE Phase 9 creates its mode directory or
    invokes any downstream runner — on: non-tropical project; missing/non-dir data root; missing
    work root or a work root under the live forecast root; empty context stamp; invalid mode; ``db``
    mode without ``db_path``; ``file`` mode WITH a ``db_path`` (ambiguous intent); or a mode subdir
    that already holds the context/analysis package for this stamp. The Phase 6/7 runners' own
    fail-closed errors (unsafe DB path, live root, missing v59 rows, etc.) propagate unchanged.
    """
    # --- Phase 9 preflight: fail closed before creating <work_root>/<mode> or calling a runner. ---
    if project_key != SUPPORTED_PROJECT_KEY:
        raise ControlledWorkflowError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported "
            "in Phase 9 (multi-project generalization is deferred)"
        )
    if not data_root:
        raise ControlledWorkflowError("data_root is required for a controlled workflow")
    data_root = Path(data_root)
    if not data_root.exists() or not data_root.is_dir():
        raise ControlledWorkflowError(f"data_root not found or not a directory: {data_root}")
    if not work_root:
        raise ControlledWorkflowError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise ControlledWorkflowError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise ControlledWorkflowError("context_stamp is required (explicit; no latest-glob)")
    if mode not in _MODES:
        raise ControlledWorkflowError(f"unsupported mode {mode!r}; expected one of {list(_MODES)}")
    if mode == "db" and not db_path:
        raise ControlledWorkflowError("mode='db' requires an explicit db_path (fail closed)")
    if mode == "file" and db_path is not None:
        raise ControlledWorkflowError(
            "mode='file' must not be given a db_path (ambiguous operator intent; fail closed)"
        )

    mode_dir = work_root / mode
    context_out_dir = mode_dir / f"{_CONTEXT_PREFIX}{context_stamp}"
    if context_out_dir.exists():
        raise ControlledWorkflowError(
            f"context package for this stamp already exists (refusing to reuse): {context_out_dir}"
        )
    if mode_dir.exists():
        existing_analysis = [
            p.name
            for p in mode_dir.glob(_ANALYSIS_GLOB)
            if p.is_dir() and "_crosswalk_v2_" not in p.name
        ]
        if existing_analysis:
            raise ControlledWorkflowError(
                f"an analysis package already exists in {mode_dir} (refused): {existing_analysis}"
            )

    db_backed = mode == "db"

    # --- 1. Controlled context generation (Phase 6 runner; explicit out_dir, file or DB backed). --
    context_meta = run_context_generation(
        data_root=data_root,
        out_dir=context_out_dir,
        stamp=context_stamp,
        db_backed=db_backed,
        db_path=Path(db_path) if db_path else None,
        project_key=project_key,
    )
    context_package = Path(context_meta["output_package"])

    # --- 2. Controlled analysis generation (Phase 7 runner; hard-pinned to this context package). -
    analysis_meta = run_final_forecast_generation(
        context_package=context_package,
        project_key=project_key,
        run_id=run_id,
    )
    analysis_package = Path(analysis_meta["output_package"])

    # --- 3. Explicit package resolution + deterministic chain manifest (Phase 8 helpers). ---------
    context_ref = resolve_explicit_package(
        package_kind="context", package_path=context_package, project_key=project_key
    )
    analysis_ref = resolve_explicit_package(
        package_kind="analysis", package_path=analysis_package, project_key=project_key
    )
    chain = build_package_chain(
        project_key=project_key, data_root=mode_dir, refs=[context_ref, analysis_ref]
    )
    chain_manifest_path = write_package_chain_manifest(
        chain=chain, out_path=mode_dir / chain_manifest_name
    )

    # --- 4. Deterministic operator report (no wall-clock added by Phase 9). -----------------------
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "mode": mode,
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "db_backed": db_backed,
        "db_path": str(db_path) if db_backed else None,
        "context_package": str(context_package),
        "context_package_stamp": context_ref.stamp,
        "analysis_package": str(analysis_package),
        "analysis_package_stamp": analysis_ref.stamp,
        "chain_manifest": str(chain_manifest_path),
        "safety_checks": {
            "project_key_supported": True,
            "data_root_is_dir": True,
            "work_root_outside_live_root": True,
            "explicit_context_stamp": True,
            "explicit_paths_only": True,
            "no_latest_glob": True,
            "db_path_required_for_db_mode": True,
            "db_path_rejected_in_file_mode": True,
        },
        "status": "ok",
    }
    report_path = mode_dir / WORKFLOW_REPORT_NAME
    _write_json_deterministic(report_path, report)
    return {**report, "report_path": str(report_path)}


def run_controlled_context_analysis_parity(
    *,
    data_root: Path,
    work_root: Path,
    context_stamp: str,
    db_path: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Run the controlled chain BOTH file-backed and DB-backed under one work root and compare.

    Runs ``file`` under ``<work_root>/file`` and ``db`` under ``<work_root>/db`` (separate roots, so
    Phase 7's "analysis already exists" guard never trips across modes), then compares ONLY:
      - context package outputs (normalized: volatile keys, sha/size, package root path + name);
      - analysis package outputs (same normalization);
      - the two chain manifests (after root-path + analysis-stamp normalization).
    Downstream comprehensive/final/integrated outputs are never compared (none are produced).

    Returns a deterministic parity report dict (plus ``parity_report_path``) with ``status`` in
    {"pass", "fail"}. Fails closed (``ControlledWorkflowError``) on unsafe inputs via the per-mode
    workflow preflight.
    """
    if project_key != SUPPORTED_PROJECT_KEY:
        raise ControlledWorkflowError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported"
        )
    if not db_path:
        raise ControlledWorkflowError("parity mode requires an explicit db_path (fail closed)")
    work_root = Path(work_root)

    file_report = run_controlled_context_analysis_workflow(
        data_root=data_root,
        work_root=work_root,
        context_stamp=context_stamp,
        mode="file",
        project_key=project_key,
    )
    db_report = run_controlled_context_analysis_workflow(
        data_root=data_root,
        work_root=work_root,
        context_stamp=context_stamp,
        mode="db",
        db_path=Path(db_path),
        project_key=project_key,
    )

    context_cmp = _compare_packages(
        Path(file_report["context_package"]), Path(db_report["context_package"])
    )
    analysis_cmp = _compare_packages(
        Path(file_report["analysis_package"]), Path(db_report["analysis_package"])
    )
    chain_cmp = _compare_chain_manifests(file_report, db_report)

    status = (
        "pass"
        if (context_cmp["match"] and analysis_cmp["match"] and chain_cmp["match"])
        else "fail"
    )
    parity_report = {
        "schema_version": PARITY_REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "data_root": str(Path(data_root)),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "file_report": file_report["report_path"],
        "db_report": db_report["report_path"],
        "context_comparison": context_cmp,
        "analysis_comparison": analysis_cmp,
        "chain_comparison": chain_cmp,
        "normalized_fields": sorted(_VOLATILE_KEYS)
        + ["sha256", "size_bytes", "<package_root_path>", "<package_dir_name>", "<analysis_stamp>"],
        "status": status,
    }
    parity_report_path = work_root / PARITY_REPORT_NAME
    _write_json_deterministic(parity_report_path, parity_report)
    return {**parity_report, "parity_report_path": str(parity_report_path)}


# --- internal helpers -------------------------------------------------------------------


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _normalize(obj):
    """Neutralize approved volatile metadata only (mirrors Phase 5/7); never domain/financial data."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _VOLATILE_KEYS:
                out[k] = "<volatile>"
            elif k == "sha256":
                out[k] = "<sha>"
            elif k == "size_bytes":
                out[k] = "<size>"
            else:
                out[k] = _normalize(v)
        return out
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


def _load_package_outputs(package_dir: Path) -> dict:
    """Parse + normalize one package's files; neutralize run-location paths/name/stamps only.

    Replaces the package's parent (mode) root — which contains both the package path and, for an
    analysis package, the consumed context-package path — and the package's own dir name (which
    carries the analysis stamp), then normalizes the approved volatile keys.
    """
    package_dir = Path(package_dir)
    mode_root = package_dir.parent
    data: dict = {}
    for p in sorted(package_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(package_dir))
        if Path(rel).name in _SKIP_BASENAMES:
            continue
        raw = (
            p.read_text(encoding="utf-8")
            .replace(str(mode_root), "<ROOT>")
            .replace(package_dir.name, "<PKG_NAME>")
        )
        if rel.endswith(".jsonl"):
            data[rel] = [_normalize(json.loads(ln)) for ln in raw.splitlines() if ln.strip()]
        elif rel.endswith(".json"):
            data[rel] = _normalize(json.loads(raw))
        else:
            data[rel] = raw
    return data


def _compare_packages(package_a: Path, package_b: Path) -> dict:
    """Compare two packages after normalization; return match + file count + mismatching rel paths."""
    a = _load_package_outputs(package_a)
    b = _load_package_outputs(package_b)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    mismatches = sorted(f for f in a if f in b and a[f] != b[f])
    return {
        "match": not (only_a or only_b or mismatches),
        "files_compared": len(set(a) | set(b)),
        "files_only_in_file_mode": only_a,
        "files_only_in_db_mode": only_b,
        "content_mismatches": mismatches,
    }


def _analysis_stamp(report: dict) -> str:
    return Path(report["analysis_package"]).name[len(_ANALYSIS_PREFIX) :]


def _compare_chain_manifests(file_report: dict, db_report: dict) -> dict:
    """Compare the two chain manifests after normalizing each run's mode root + analysis stamp."""
    file_norm = _normalize_chain_manifest(
        Path(file_report["chain_manifest"]),
        mode_root=Path(file_report["work_root"]) / "file",
        analysis_stamp=_analysis_stamp(file_report),
    )
    db_norm = _normalize_chain_manifest(
        Path(db_report["chain_manifest"]),
        mode_root=Path(db_report["work_root"]) / "db",
        analysis_stamp=_analysis_stamp(db_report),
    )
    return {"match": file_norm == db_norm}


def _normalize_chain_manifest(path: Path, *, mode_root: Path, analysis_stamp: str) -> dict:
    """Neutralize the per-run mode root and the generator-assigned analysis stamp, then parse."""
    text = (
        Path(path)
        .read_text(encoding="utf-8")
        .replace(str(mode_root), "<ROOT>")
        .replace(analysis_stamp, "<ASTAMP>")
    )
    return json.loads(text)
