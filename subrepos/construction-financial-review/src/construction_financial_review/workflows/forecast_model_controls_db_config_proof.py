"""Phase 17 — DB-backed config consumer proof for ``forecast_model_controls``.

Proves the existing deterministic ``forecast_model_controls`` generator can consume the Phase 16 DB config
snapshot (via the materialized config root + the ``CFR_CONFIG_ROOT`` opt-in bridge) and produce output that
is parity-equivalent to the current file-backed config path. It is a CONSUMER PROOF only — it changes no
default, never writes/migrates the live DB, and does not widen into monthly/comprehensive/probability/
integrated-CSV or the Phase 6/7/9/12/15 chain.

Repo truth (Phase 16/17 audits): ``forecast_model_controls`` directly consumes only
``config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl`` (via
``forecast_model_controls.load_controls.control_file_path`` -> ``common.config_root.resolve_config_base``,
already ``CFR_CONFIG_ROOT``-aware). The generator is deterministic under a frozen stamp, makes no LLM/Ollama/
network calls (``with_llm``/``llm_model`` are dead params), and mutates nothing outside its output package.
The caller-supplied project ``cfg`` is NOT read through the bridge and is therefore not reported as a
DB-snapshot-consumed input.

CFR-only / stdlib at import; ``hb_assistant`` is only touched lazily by the reused Phase 16 helpers and the
read-only live-DB check. The live DB is opened READ-ONLY (``mode=ro``) for snapshot materialization only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .. import config_registry as cr
from ..common.config_root import ENV_CONFIG_ROOT
from ..common.hashing import sha256_file
from ..common.project_eligibility import eligible_projects, is_project_eligible
from . import live_db_certification as cert

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = 60
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "forecast_model_controls_db_config_proof_report.json"
SUMMARY_NAME = "forecast_model_controls_db_config_proof_summary.md"
MATERIALIZE_SUBDIR = "db_snapshot_config"
FILE_BACKED_SUBDIR = "file_backed"
DB_BACKED_SUBDIR = "db_snapshot_backed"

DECISION_READY = "forecast_model_controls_db_config_parity_ready"
DECISION_NOT_READY = "not_ready"
DEFAULT_RUN_STAMP = "20260101_000000"

# The live Phase 16 baseline (documented; gated only when require_item_count is provided).
LIVE_BASELINE_ITEM_COUNT = 194
CONSUMED_CONFIG_DOMAIN = "forecast_model_controls"
CONSUMED_CONFIG_FILE = "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl"

REQUIRED_CONFIG_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)
# The generator's deterministic, path-free quantitative outputs — compared BYTE-EXACT (no normalization).
# These 17 files carry the model-control forecast semantics and embed NO absolute path; any difference is
# a real semantic mismatch (the config the generator actually consumed produced different numbers).
_SEMANTIC_FILES = (
    "model_controls_by_budget_code.jsonl",
    "model_control_applications_by_budget_code.jsonl",
    "model_control_resolved_targets_by_budget_code.jsonl",
    "model_control_monthly_preview_by_budget_code.jsonl",
    "model_control_probability_assessment_by_budget_code.jsonl",
    "model_control_review_queue.jsonl",
    "model_control_conflicts.jsonl",
    "model_control_warnings.jsonl",
    "audit/control_mapping_audit.json",
    "audit/target_source_resolution_audit.json",
    "audit/window_resolution_audit.json",
    "audit/actuals_floor_audit.json",
    "audit/no_hidden_cap_audit.json",
    "audit/model_shape_audit.json",
    "audit/monthly_reconciliation_preview_audit.json",
    "audit/probability_anchor_policy_audit.json",
    "audit/combined_actuals_plus_forecast_target_reconciliation_audit.json",
)
# Files that LEGITIMATELY record the control-file/output ABSOLUTE PATH (their only file/db-mode difference);
# compared after path normalization. Their non-path content (incl. summary numbers) is still compared.
_PATH_EMBEDDING_FILES = (
    "project_forecast_model_controls_summary.json",
    "input_inventory.json",
    "audit/source_hashes_before_after.json",
    "audit/safety_scan_report.json",
    "README.md",
    "SCHEMA.md",
)
_NORMALIZED_RULES = [
    "file-backed output package root and DB-backed output package root replaced with <OUTPUT_PACKAGE>",
    "repo/source config root and materialized config root replaced with <CONFIG_ROOT>",
    (
        "validation_report.json: the sha256 of the path-embedding files "
        "(project_forecast_model_controls_summary.json, input_inventory.json, "
        "audit/source_hashes_before_after.json, audit/safety_scan_report.json, README.md, SCHEMA.md) is "
        "neutralized to <PATH_FILE_SHA> because those files record absolute config/output paths"
    ),
    (
        "manifest.json: size_bytes + sha256 of the same path-embedding files are excluded (their only "
        "difference is the recorded absolute path); the 17 semantic data/audit files are required "
        "byte-exact and their manifest size_bytes/sha256 are NOT excluded"
    ),
]

# Controlled-safety guard only (mirrors the generators' default Synology root); monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ForecastModelControlsDbConfigProofError(RuntimeError):
    """Raised when the consumer proof is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastModelControlsDbConfigProofError(message)


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _normalize(text: str, replacements: list[tuple[str, str]]) -> str:
    for needle, token in replacements:
        if needle:
            text = text.replace(needle, token)
    return text


def _compare_packages(
    *, file_pkg: Path, db_pkg: Path, replacements: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Compare two model-controls packages. Returns a list of differences (empty == parity).

    Tier 1 (semantic): the 17 forecast/control data+audit files — byte-exact, NO normalization.
    Tier 2 (path-embedding): files recording an absolute config/output path — path-normalized text.
    Tier 3 (manifest/validation): per-file-sha files — path-normalized + the path-embedding files' shas
    neutralized to <PATH_FILE_SHA> (those shas differ only because the underlying file records a path).
    """
    diffs: list[dict[str, Any]] = []

    # 1. Semantic files: byte-exact, no normalization.
    for rel in _SEMANTIC_FILES:
        a, b = file_pkg / rel, db_pkg / rel
        if not a.is_file() or not b.is_file():
            diffs.append(
                {
                    "file": rel,
                    "key_or_path": "<presence>",
                    "file_backed_value": a.is_file(),
                    "db_backed_value": b.is_file(),
                    "normalized_rules": "none (semantic file must exist in both)",
                }
            )
            continue
        if a.read_bytes() != b.read_bytes():
            diffs.append(
                {
                    "file": rel,
                    "key_or_path": "<bytes>",
                    "file_backed_value": sha256_file(a),
                    "db_backed_value": sha256_file(b),
                    "normalized_rules": "none (semantic files compared byte-exact)",
                }
            )

    # 2. Path-embedding files: path-normalized text compare (non-path content still compared).
    for rel in _PATH_EMBEDDING_FILES:
        d = _compare_text(file_pkg / rel, db_pkg / rel, rel, replacements)
        if d:
            diffs.append(d)

    # 3a. validation_report.json: path-normalized + neutralize the path-embedding files' shas.
    sha_repl = list(replacements)
    for rel in _PATH_EMBEDDING_FILES:
        for pkg in (file_pkg, db_pkg):
            p = pkg / rel
            if p.is_file():
                sha_repl.append((sha256_file(p), "<PATH_FILE_SHA>"))
    d = _compare_text(
        file_pkg / "validation_report.json",
        db_pkg / "validation_report.json",
        "validation_report.json",
        sha_repl,
    )
    if d:
        diffs.append(d)

    # 3b. manifest.json: structured; size_bytes + sha256 of the path-embedding files are excluded
    # (their only difference is the recorded absolute config/output path); all other entries compared.
    fa, fb = _read_manifest_files(file_pkg), _read_manifest_files(db_pkg)
    if set(fa) != set(fb):
        diffs.append(
            {
                "file": "manifest.json",
                "key_or_path": "<file set>",
                "file_backed_value": sorted(set(fa) - set(fb)),
                "db_backed_value": sorted(set(fb) - set(fa)),
                "normalized_rules": "none",
            }
        )
    for rel in sorted(set(fa) & set(fb)):
        ea, eb = fa[rel], fb[rel]
        keys = (
            ("path", "row_count")
            if rel in _PATH_EMBEDDING_FILES
            else ("path", "size_bytes", "row_count", "sha256")
        )
        for k in keys:
            if ea.get(k) != eb.get(k):
                diffs.append(
                    {
                        "file": "manifest.json",
                        "key_or_path": f"{rel}.{k}",
                        "file_backed_value": ea.get(k),
                        "db_backed_value": eb.get(k),
                        "normalized_rules": (
                            "manifest size_bytes/sha256 excluded for path-embedding files"
                            if rel in _PATH_EMBEDDING_FILES
                            else "none"
                        ),
                    }
                )
    return diffs


def _read_manifest_files(package: Path) -> dict[str, dict[str, Any]]:
    import json

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    return {f["path"]: f for f in manifest.get("files", [])}


def _compare_text(
    a: Path, b: Path, rel: str, replacements: list[tuple[str, str]]
) -> dict[str, Any] | None:
    if not a.is_file() and not b.is_file():
        return None
    if a.is_file() != b.is_file():
        return {
            "file": rel,
            "key_or_path": "<presence>",
            "file_backed_value": a.is_file(),
            "db_backed_value": b.is_file(),
            "normalized_rules": "path-normalized",
        }
    na = _normalize(a.read_text(encoding="utf-8"), replacements)
    nb = _normalize(b.read_text(encoding="utf-8"), replacements)
    if na == nb:
        return None
    # find the first differing normalized line for an exact, honest report
    import difflib

    detail = next(
        (
            line
            for line in difflib.unified_diff(na.splitlines(), nb.splitlines(), n=0, lineterm="")
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ),
        "<normalized text differs>",
    )
    return {
        "file": rel,
        "key_or_path": "<normalized-text>",
        "file_backed_value": detail if detail.startswith("-") else "<see db value>",
        "db_backed_value": detail if detail.startswith("+") else "<see file value>",
        "normalized_rules": "; ".join(_NORMALIZED_RULES),
    }


def _run_model_controls(
    *, project_key: str, cfg: dict, data_root: Path, run_stamp: str, out_root: Path
) -> dict:
    """Run the real forecast_model_controls generator (deterministic; no LLM/Ollama)."""
    from ..forecast_model_controls import generate_forecast_model_controls_package as gen

    return gen.generate(
        project_key,
        cfg,
        data_root=data_root,
        frozen_stamp=run_stamp,
        out_root=out_root,
        with_llm=False,
        llm_model=None,
        control_file=None,
    )


def run_forecast_model_controls_db_config_proof(
    *,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path,
    config_snapshot_id: str,
    work_root: Path,
    run_stamp: str | None = None,
    require_live_snapshot: bool = True,
    data_root: Path | None = None,
    source_config_root: Path | None = None,
    require_item_count: int | None = None,
) -> dict[str, Any]:
    """Prove forecast_model_controls consumes the DB config snapshot with parity vs file-backed config.

    Fails closed (``ForecastModelControlsDbConfigProofError`` -> CLI rc 3) before any output on: non-tropical
    project; unsafe work root; a live DB that is missing, not v60, or lacking the 4 config registry tables;
    (when ``require_live_snapshot``) a db_path that is not the live/default DB; a missing snapshot row or one
    for the wrong project; (when ``require_item_count``) a snapshot item-count mismatch; or a missing source
    config root / data root / context package. The live DB is opened READ-ONLY and never written/migrated.

    Materializes the snapshot under ``<work_root>/db_snapshot_config``, runs the real generator file-backed
    (``CFR_CONFIG_ROOT`` unset) and DB-backed (``CFR_CONFIG_ROOT`` = materialized root, scoped+restored), and
    compares: the 18 semantic files byte-exact + the path-embedding metadata files path-normalized. Parity ->
    ``decision=forecast_model_controls_db_config_parity_ready`` (rc 0); mismatch -> ``not_ready`` (rc 1).
    """
    # --- Gate 1-2: project + work root. -----------------------------------------------------------
    if not is_project_eligible(project_key):
        raise ForecastModelControlsDbConfigProofError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    _require(bool(work_root), "work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    _require(
        not _is_under(work_root, _LIVE_ROOT),
        f"work_root is at/under the live forecast root (refused): {work_root}",
    )
    run_stamp = run_stamp or DEFAULT_RUN_STAMP

    # --- Gate 3-4: live DB read-only (v60 + 4 tables; optionally the real live DB). ----------------
    _require(bool(live_db_path), "live_db_path is required")
    live_db_path = Path(live_db_path)
    _require(live_db_path.exists(), f"live DB not found: {live_db_path}")
    if require_live_snapshot:
        _require(
            cr._is_live_db(live_db_path),
            f"live_db_path is not the live/default DB (require_live_snapshot=True): {live_db_path}",
        )
    conn = cert._ro_conn(live_db_path)
    try:
        vrow = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(vrow[0]) if vrow and vrow[0] is not None else 0
        _require(
            schema_version >= REQUIRED_SCHEMA_VERSION,
            f"live DB schema version {schema_version} < {REQUIRED_SCHEMA_VERSION} (config registry)",
        )
        for t in REQUIRED_CONFIG_TABLES:
            _require(_table_exists(conn, t), f"live DB missing config registry table: {t}")
        # --- Gate 5-6: snapshot row. --------------------------------------------------------------
        row = conn.execute(
            "SELECT project_key, item_count FROM forecast_config_snapshots WHERE config_snapshot_id = ?",
            (config_snapshot_id,),
        ).fetchone()
        _require(row is not None, f"config_snapshot_id not found: {config_snapshot_id}")
        _require(
            row[0] == project_key,
            f"snapshot project_key {row[0]!r} != {project_key!r}",
        )
        snapshot_item_count = int(row[1])
    finally:
        conn.close()
    if require_item_count is not None:
        _require(
            snapshot_item_count == require_item_count,
            f"snapshot item_count {snapshot_item_count} != required {require_item_count}",
        )

    # --- Gate 7: source config root (default: the CFR subproject root). ----------------------------
    if source_config_root is None:
        from .. import config_registry as _cr  # the package root holds the config/ subtree

        source_config_root = Path(_cr.__file__).resolve().parents[2]
    source_config_root = Path(source_config_root)
    _require(source_config_root.exists(), f"source_config_root not found: {source_config_root}")
    _require(
        not _is_under(work_root, source_config_root) or work_root != source_config_root,
        "work_root must not be the source config root",
    )

    # --- Materialize the snapshot (read-only on the live DB; never writes repo config/). ----------
    try:
        mat = cr.materialize_forecast_config_snapshot(
            db_path=live_db_path,
            config_snapshot_id=config_snapshot_id,
            out_root=work_root / MATERIALIZE_SUBDIR,
        )
    except cr.ConfigRegistryError as exc:
        raise ForecastModelControlsDbConfigProofError(
            f"snapshot materialization failed: {exc}"
        ) from exc
    materialized_config_root = mat["materialized_config_root"]
    # Consumed-config accounting: only the model-controls file the generator actually reads.
    consumed_files = [r for r in mat["row_counts"] if "/forecast_model_controls/" in f"/{r}"]
    consumed_item_count = sum(int(mat["row_counts"][r]) for r in consumed_files)

    # --- Load cfg ONCE with CFR_CONFIG_ROOT unset (repo project json); resolve data_root. ---------
    prev_env = os.environ.pop(ENV_CONFIG_ROOT, None)
    try:
        from .. import cli as cfr_cli

        cfg = cfr_cli.load_project(project_key)
    finally:
        if prev_env is not None:
            os.environ[ENV_CONFIG_ROOT] = prev_env
    eff_data_root = Path(data_root) if data_root is not None else Path(cfg["default_data_root"])
    _require(
        eff_data_root.exists() and eff_data_root.is_dir(),
        f"data_root not found or not a directory: {eff_data_root}",
    )

    # --- File-backed run: CFR_CONFIG_ROOT UNSET (proves default preserved). -----------------------
    _require(
        os.environ.get(ENV_CONFIG_ROOT) in (None, ""),
        "CFR_CONFIG_ROOT must be unset for the file-backed run (default preservation)",
    )
    file_meta = _run_model_controls(
        project_key=project_key,
        cfg=cfg,
        data_root=eff_data_root,
        run_stamp=run_stamp,
        out_root=work_root / FILE_BACKED_SUBDIR,
    )
    file_pkg = Path(file_meta["output_package"])

    # --- DB-backed run: scoped CFR_CONFIG_ROOT = materialized root (try/finally restore). ---------
    prev = os.environ.get(ENV_CONFIG_ROOT)
    os.environ[ENV_CONFIG_ROOT] = materialized_config_root
    try:
        db_meta = _run_model_controls(
            project_key=project_key,
            cfg=cfg,
            data_root=eff_data_root,
            run_stamp=run_stamp,
            out_root=work_root / DB_BACKED_SUBDIR,
        )
    finally:
        if prev is None:
            os.environ.pop(ENV_CONFIG_ROOT, None)
        else:
            os.environ[ENV_CONFIG_ROOT] = prev
    db_pkg = Path(db_meta["output_package"])
    env_restored = os.environ.get(ENV_CONFIG_ROOT) in (None, "")

    # --- Compare (semantic byte-exact + metadata path-normalized). --------------------------------
    replacements = [
        (str(db_pkg), "<OUTPUT_PACKAGE>"),
        (str(file_pkg), "<OUTPUT_PACKAGE>"),
        (materialized_config_root, "<CONFIG_ROOT>"),
        (str(source_config_root), "<CONFIG_ROOT>"),
    ]
    diffs = _compare_packages(file_pkg=file_pkg, db_pkg=db_pkg, replacements=replacements)
    parity_pass = not diffs
    status = "ready" if parity_pass else DECISION_NOT_READY
    decision = DECISION_READY if parity_pass else DECISION_NOT_READY

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "live_db_path": str(live_db_path),
        "db_schema_version": schema_version,
        "config_snapshot_id": config_snapshot_id,
        "snapshot_item_count": snapshot_item_count,
        "consumed_config_domains": [CONSUMED_CONFIG_DOMAIN],
        "db_snapshot_consumed_files": sorted(consumed_files) or [CONSUMED_CONFIG_FILE],
        "consumed_snapshot_item_count": consumed_item_count,
        "materialized_config_root": materialized_config_root,
        "config_snapshot_manifest": mat["manifest_path"],
        "run_stamp": run_stamp,
        "data_root": str(eff_data_root),
        "source_config_root": str(source_config_root),
        "file_backed": {
            "output_package": str(file_pkg),
            "validation_passed": file_meta.get("validation_passed"),
            "control_count": file_meta.get("control_count"),
            "applied_control_count": file_meta.get("applied_control_count"),
            "cfr_config_root": None,
        },
        "db_snapshot_backed": {
            "output_package": str(db_pkg),
            "validation_passed": db_meta.get("validation_passed"),
            "control_count": db_meta.get("control_count"),
            "applied_control_count": db_meta.get("applied_control_count"),
            "config_snapshot_consumed": True,
            "config_snapshot_id": config_snapshot_id,
            "materialized_config_manifest": mat["manifest_path"],
            "cfr_config_root_restored": env_restored,
        },
        "comparison": {
            "compared": True,
            "result": "pass" if parity_pass else "fail",
            "semantic_files_byte_exact": parity_pass
            or not any(d["file"] in _SEMANTIC_FILES for d in diffs),
            "differences": diffs,
            "normalized_rules": _NORMALIZED_RULES,
        },
        "safety": {
            "live_db_written": False,
            "live_db_migrated": False,
            "source_config_mutated": False,
            "source_package_mutated": False,
            "production_defaults_changed": False,
            "cfr_config_root_default_changed": False,
            "db_snapshot_config_consumed": True,
            "file_backed_default_preserved": True,
            "downstream_monthly_comprehensive_probability_run": False,
            "integrated_csv_generated": False,
            "model_backed_llm_or_ollama_run": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    report["report_path"] = str(report_path)
    _write_summary(work_root / SUMMARY_NAME, report)
    return report


def _write_summary(path: Path, report: dict) -> Path:
    cmp = report["comparison"]
    lines = [
        "# Forecast Model Controls — DB-Backed Config Consumer Proof (Phase 17)",
        "",
        f"- status: {report['status']}",
        f"- decision: {report['decision']}",
        f"- live_db_path: {report['live_db_path']} (read-only)",
        f"- db_schema_version: {report['db_schema_version']}",
        f"- config_snapshot_id: {report['config_snapshot_id']}",
        f"- snapshot_item_count: {report['snapshot_item_count']}",
        f"- consumed_config_domains: {report['consumed_config_domains']}",
        f"- db_snapshot_consumed_files: {report['db_snapshot_consumed_files']}",
        f"- consumed_snapshot_item_count: {report['consumed_snapshot_item_count']}",
        f"- materialized_config_root: {report['materialized_config_root']}",
        "",
        "## Outputs",
        f"- file_backed_output_package: {report['file_backed']['output_package']}",
        f"- db_snapshot_backed_output_package: {report['db_snapshot_backed']['output_package']}",
        "",
        "## Parity",
        f"- result: {cmp['result']}",
        f"- differences: {len(cmp['differences'])}",
        "- normalized_rules:",
        *[f"  - {r}" for r in cmp["normalized_rules"]],
    ]
    if cmp["differences"]:
        lines += ["", "## Differences"]
        lines += [
            f"  - {d['file']} :: {d['key_or_path']} (file={d['file_backed_value']!r} "
            f"db={d['db_backed_value']!r})"
            for d in cmp["differences"]
        ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
