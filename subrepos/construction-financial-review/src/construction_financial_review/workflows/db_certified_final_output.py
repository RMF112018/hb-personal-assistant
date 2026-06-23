"""Phase 15 — controlled DB-certified final forecast output generation.

Phase 14 populated and certified the live/default DB's three v59 source-domain tables for
``project_key='tropical'`` (post-write ``certified_match``; a guarded operator proof confirmed the
DB-backed context/analysis chain). Phase 15 turns that certification into an eligibility gate and runs
the existing controlled, deterministic final-output chain under an explicit work root:

    Phase 14 certified evidence (gate) -> rerun Phase 13 read-only certification (require
    ``certified_match``, consistent counts) -> Phase 12 guarded operator run under <work_root>/guarded
    (a fresh NON-LIVE temp v59 DB drives Phase 11->10->9, never the live DB) -> copy the approved
    DB-certified analysis package under <work_root>/final_output/ -> deterministic Phase 15 report.

It is NOT a production cutover. It changes no production default, makes no DB-backed read or package
resolution the default, removes no file-backed path, runs no intelligence/comprehensive/probability/
monthly/model-controls/LLM workflow, adds no schema, and never writes/migrates/projects the live DB
(the live DB is opened read-only only, by certification verification).

The in-scope deterministic generator (Phase 7 analysis package) emits JSONL/JSON/Markdown with
per-file row counts and sha256 — it does NOT emit the true integrated CSV (that is produced by
forecast_comprehensive/monthly/probability, which Phase 15 boundaries defer). Therefore
``generate_final_csv`` is a controlled refusal: it does not synthesize a CSV; it returns ``not_ready``
(CLI rc 1) and records the exact out-of-scope blocker.

CFR-only / stdlib at import time; reuses Phase 13 (``live_db_certification``) and Phase 12
(``guarded_db_operator_run``); ``hb_assistant`` is only ever touched transitively by those reused
workflows (lazily, and only against a fresh non-live temp DB) or by a lazy live-DB safety check.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from ..common.project_eligibility import (
    eligible_projects,
    is_project_eligible,
    source_package_name,
)
from . import guarded_db_operator_run as guarded
from . import live_db_certification as cert
from .db_cutover_readiness import REQUIRED_SOURCE_DOMAIN_TABLES

SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "db_certified_final_output_report.json"
SUMMARY_NAME = "db_certified_final_output_summary.md"
FINAL_OUTPUT_DIRNAME = "final_output"
GUARDED_SUBDIR = "guarded"
CURRENT_CERT_SUBDIR = "current_certification"


DECISION_READY = "db_certified_final_output_ready"
DECISION_NOT_READY = "not_ready"

# The Tropical source-domain baseline certified by Phase 14 (documented; the runtime gate compares the
# rerun certification against the Phase 14 evidence, so the live DB cannot have drifted since Phase 14).
EXPECTED_TROPICAL_COUNTS = {
    "forecast_budget_details": 127,
    "forecast_cost_entries": 6324,
    "forecast_monthly_actuals_by_budget_code": 1081,
}

CSV_OUT_OF_SCOPE_BLOCKER = (
    "true integrated CSV is produced by forecast_comprehensive/monthly/probability, which Phase 15 "
    "boundaries defer"
)

# Phase 14 report invariants this phase gates on (mirrors live_db_source_domain_projection.py).
_PHASE14_REQUIRED_SAFETY = {
    "live_db_written": True,
    "live_db_migrated": False,
    "live_db_projected_directly": False,
    "projected_via_temp_db": True,
    "production_defaults_changed": False,
    "final_integrated_csv_generated": False,
    "true_live_execution_used": False,
}
_PHASE14_DECISION_CERTIFIED = "live_db_source_domain_certified"
_CERT_MATCH = "certified_match"
_GUARDED_DECISION_APPROVED = "approved_for_guarded_db_context_analysis_use"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class DbCertifiedFinalOutputError(RuntimeError):
    """Raised when a DB-certified final-output run is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _same_path(a: Any, b: Any) -> bool:
    return Path(str(a)).expanduser().resolve(strict=False) == Path(str(b)).expanduser().resolve(
        strict=False
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path, *, what: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise DbCertifiedFinalOutputError(f"{what} not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DbCertifiedFinalOutputError(f"{what} is not readable JSON: {p} ({exc})") from exc
    if not isinstance(data, dict):
        raise DbCertifiedFinalOutputError(f"{what} is not a JSON object: {p}")
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DbCertifiedFinalOutputError(message)


def _validate_phase14_report(report: dict) -> None:
    """Gates 4-6: the Phase 14 report's status/decision/safety, post-write cert, guarded proof."""
    _require(report.get("status") == "ready", "Phase 14 report status is not 'ready'")
    _require(
        report.get("decision") == _PHASE14_DECISION_CERTIFIED,
        f"Phase 14 report decision is not {_PHASE14_DECISION_CERTIFIED!r} "
        f"(decision={report.get('decision')!r})",
    )
    safety = report.get("safety") or {}
    for key, want in _PHASE14_REQUIRED_SAFETY.items():
        _require(
            safety.get(key) is want,
            f"Phase 14 safety.{key} != {want!r} (got {safety.get(key)!r})",
        )

    # Gate 5 — post-write certification (embedded + on-disk).
    pwc = report.get("post_write_certification") or {}
    _require(
        pwc.get("decision") == _CERT_MATCH,
        f"Phase 14 post-write certification is not {_CERT_MATCH!r} (got {pwc.get('decision')!r})",
    )
    tables = pwc.get("tables") or {}
    for t in REQUIRED_SOURCE_DOMAIN_TABLES:
        entry = tables.get(t)
        if not (isinstance(entry, dict) and entry.get("match") is True):
            raise DbCertifiedFinalOutputError(
                f"Phase 14 post-write certification table {t!r} is not a confirmed match"
            )
        _require(
            entry.get("live_rows") == entry.get("temp_rows"),
            f"Phase 14 post-write certification table {t!r} live_rows != temp_rows",
        )
    pwc_path = pwc.get("report_path")
    _require(bool(pwc_path), "Phase 14 post-write certification report_path is missing")
    on_disk = _load_json(Path(str(pwc_path)), what="Phase 14 post-write certification report")
    _require(
        on_disk.get("decision") == _CERT_MATCH,
        "Phase 14 post-write certification report on disk is not certified_match",
    )

    # Gate 6 — guarded operator proof.
    gor = report.get("guarded_operator_check") or {}
    _require(gor.get("status") == "ready", "Phase 14 guarded operator check status is not 'ready'")
    _require(
        gor.get("decision") == _GUARDED_DECISION_APPROVED,
        f"Phase 14 guarded operator check decision is not {_GUARDED_DECISION_APPROVED!r}",
    )
    live = gor.get("live_db") or {}
    _require(live.get("certified") is True, "Phase 14 guarded operator check live_db not certified")
    _require(
        live.get("certification_decision") == _CERT_MATCH,
        "Phase 14 guarded operator check live_db certification_decision is not certified_match",
    )
    _require(
        live.get("equivalent_to_temp_db") is True,
        "Phase 14 guarded operator check live_db is not equivalent_to_temp_db",
    )
    _require(
        live.get("used_for_execution") is False,
        "Phase 14 guarded operator check live_db used_for_execution is not False",
    )
    gor_path = gor.get("report_path")
    _require(bool(gor_path), "Phase 14 guarded operator manifest report_path is missing")
    _require(
        Path(str(gor_path)).is_file(),
        f"Phase 14 guarded operator manifest not found: {gor_path}",
    )


def _final_output_evidence(copied_root: Path) -> tuple[dict[str, int], dict[str, str]]:
    """Deterministic row counts (per .jsonl) + sha256 (per file) over the copied analysis package."""
    row_counts: dict[str, int] = {}
    sha256: dict[str, str] = {}
    for p in sorted(copied_root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(copied_root))
        sha256[rel] = _sha256_file(p)
        if p.suffix == ".jsonl":
            with p.open("r", encoding="utf-8") as fh:
                row_counts[rel] = sum(1 for line in fh if line.strip())
    return row_counts, sha256


def _write_summary(path: Path, report: dict) -> Path:
    """Deterministic human-readable summary (no wall-clock)."""
    lines = [
        "# DB-Certified Final Forecast Output (Phase 15)",
        "",
        f"- project_key: {report['project_key']}",
        f"- status: {report['status']}",
        f"- decision: {report['decision']}",
        f"- context_stamp: {report['context_stamp']}",
        f"- work_root: {report['work_root']}",
        f"- source_package: {report['source_package']}",
        "",
        "## Live DB certification (read-only verification)",
        f"- decision: {report['live_db_verification']['certification_decision']}",
        f"- read_only: {report['live_db_verification']['read_only']}",
        f"- table_counts: {report['live_db_verification']['table_counts']}",
        "",
        "## Controlled chain",
    ]
    chain = report.get("controlled_chain") or {}
    lines += [
        f"- guarded operator decision: {chain.get('guarded_decision')}",
        f"- context_package: {chain.get('context_package')}",
        f"- analysis_package: {chain.get('analysis_package')}",
        f"- chain_manifest: {chain.get('chain_manifest')}",
        "",
        "## Final outputs (under work_root only)",
        f"- package_paths: {report['final_outputs']['package_paths']}",
        f"- csv_paths: {report['final_outputs']['csv_paths']}",
        f"- final_integrated_csv_generated: {report['safety']['final_integrated_csv_generated']}",
    ]
    if report["csv_generation"]["requested"]:
        lines += [
            "",
            "## CSV generation (refused — out of scope)",
            f"- decision: {report['csv_generation']['decision']}",
            f"- blocker: {report['csv_generation']['blocker']}",
        ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_db_certified_final_output(
    *,
    phase14_report: Path,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path | None = None,
    require_certified_live_db: bool = True,
    require_guarded_operator_check: bool = True,
    generate_final_csv: bool = False,
    run_id: str | None = None,
    config_snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """Generate DB-certified final forecast outputs under ``work_root`` from Phase 14 certified evidence.

    Fails closed (``DbCertifiedFinalOutputError`` -> CLI rc 3) BEFORE any output on any unsafe/missing
    input or eligibility-gate failure: non-tropical project; unsafe/non-explicit work root (or one under
    the live forecast root, or equal to the source package); missing/malformed Phase 14 report; a Phase
    14 report whose status/decision/safety, post-write certification, or guarded operator proof is not
    the certified shape; a backup that is missing or whose sha256 does not match the report; a source
    package that does not match the report / is missing / has the wrong name; a provided live DB path
    that does not match the report; or a rerun certification that is not ``certified_match`` with counts
    consistent with the Phase 14 evidence.

    On a passing eligibility set: if ``generate_final_csv`` is requested it is a controlled refusal
    (``status='not_ready'`` / CLI rc 1) recording the out-of-scope blocker — no CSV is synthesized.
    Otherwise it runs the Phase 12 guarded operator run under ``<work_root>/guarded`` (a fresh NON-LIVE
    temp DB drives Phase 11->10->9; the live DB is never executed against), copies the approved
    DB-certified analysis package under ``<work_root>/final_output/``, records per-file sha256 and
    per-JSONL row counts, and writes a deterministic report + summary. ``decision`` is
    ``db_certified_final_output_ready`` (rc 0) on success, else ``not_ready`` (rc 1).
    """
    # --- Gate 1-2: project + work root (fail closed before any output). ---------------------------
    if not is_project_eligible(project_key):
        raise DbCertifiedFinalOutputError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not work_root:
        raise DbCertifiedFinalOutputError(
            "work_root is required (explicit; no implicit output root)"
        )
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise DbCertifiedFinalOutputError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise DbCertifiedFinalOutputError("context_stamp is required (explicit; no latest-glob)")

    # --- Gate 8: source package. ------------------------------------------------------------------
    if not source_package:
        raise DbCertifiedFinalOutputError("source_package is required")
    source_package = Path(source_package)
    if _same_path(work_root, source_package):
        raise DbCertifiedFinalOutputError("work_root must not be the source package path")
    if not source_package.exists() or not source_package.is_dir():
        raise DbCertifiedFinalOutputError(
            f"source_package not found or not a directory: {source_package}"
        )
    expected_source = source_package_name(project_key)
    if source_package.name != expected_source:
        raise DbCertifiedFinalOutputError(
            f"source_package is not the expected Tropical package "
            f"{expected_source!r}: {source_package.name}"
        )

    # --- Gate 3-6: Phase 14 report. ---------------------------------------------------------------
    if not phase14_report:
        raise DbCertifiedFinalOutputError("phase14_report is required")
    phase14_report = Path(phase14_report)
    report14 = _load_json(phase14_report, what="Phase 14 report")
    _require(
        report14.get("project_key") == project_key,
        f"Phase 14 report project_key {report14.get('project_key')!r} != {project_key!r}",
    )
    _validate_phase14_report(report14)

    # --- Gate 7: backup exists and sha256 matches the report. -------------------------------------
    backup = report14.get("backup") or {}
    backup_path = backup.get("path")
    _require(bool(backup_path), "Phase 14 report has no backup path")
    backup_path = Path(str(backup_path))
    _require(backup_path.is_file(), f"Phase 14 backup not found: {backup_path}")
    backup_sha = backup.get("sha256")
    _require(bool(backup_sha), "Phase 14 report has no backup sha256")
    backup_sha_ok = _sha256_file(backup_path) == backup_sha
    _require(backup_sha_ok, f"Phase 14 backup sha256 mismatch: {backup_path}")

    # --- Gate 8 (cont.): source package matches the Phase 14 report. ------------------------------
    _require(
        bool(report14.get("source_package"))
        and _same_path(report14["source_package"], source_package),
        "source_package does not match the Phase 14 report",
    )

    # --- Gate 9: resolve / verify the live DB path (read-only verification only). ------------------
    report_live_path = ((report14.get("live_db") or {}).get("path")) or report14.get("live_db")
    if live_db_path is not None:
        live_db_path = Path(live_db_path)
        _require(
            bool(report_live_path) and _same_path(report_live_path, live_db_path),
            "provided live_db_path does not match the Phase 14 report live DB path",
        )
    else:
        live_db_path = (
            Path(str(report_live_path)) if report_live_path else cert._resolve_live_db_path()
        )
    if not cert._is_live_db(live_db_path):
        raise DbCertifiedFinalOutputError(
            f"live DB path does not resolve to the live/default DB: {live_db_path}"
        )

    data_root = source_package.parent

    # --- Gate 10-12: rerun Phase 13 read-only certification (required for a real run). ------------
    rerun = cert.run_live_db_readonly_certification(
        source_package=source_package,
        work_root=work_root / CURRENT_CERT_SUBDIR,
        context_stamp=context_stamp,
        live_db_path=live_db_path,
        project_key=project_key,
    )
    if require_certified_live_db:
        _require(
            rerun.get("decision") == _CERT_MATCH,
            f"rerun live-DB certification is not {_CERT_MATCH!r} (got {rerun.get('decision')!r})",
        )
    rerun_tables = rerun.get("tables") or {}
    phase14_tables = (report14.get("post_write_certification") or {}).get("tables") or {}
    table_counts: dict[str, int] = {}
    digest_matches: dict[str, dict[str, bool]] = {}
    for t in REQUIRED_SOURCE_DOMAIN_TABLES:
        entry = rerun_tables.get(t) or {}
        live_rows = int(entry.get("live_rows", -1))
        table_counts[t] = live_rows
        digest_matches[t] = {
            "raw_json_match": bool(entry.get("raw_json_match")),
            "canonical_match": bool(entry.get("canonical_match")),
        }
        # Gate 12: rerun counts must be consistent with the Phase 14 certified evidence (no drift).
        want = int((phase14_tables.get(t) or {}).get("live_rows", -2))
        _require(
            live_rows == want,
            f"rerun certification count drift for {t}: rerun {live_rows} != Phase 14 {want}",
        )

    live_db_verification = {
        "path": str(live_db_path),
        "certification_decision": rerun.get("decision"),
        "certification_report": rerun.get("report_path"),
        "table_counts": table_counts,
        "digest_matches": digest_matches,
        "read_only": True,
    }
    phase14_evidence = {
        "decision": report14.get("decision"),
        "backup_path": str(backup_path),
        "backup_sha256_verified": backup_sha_ok,
        "post_write_certification_path": (report14.get("post_write_certification") or {}).get(
            "report_path"
        ),
        "guarded_operator_manifest_path": (report14.get("guarded_operator_check") or {}).get(
            "report_path"
        ),
    }
    safety = {
        "live_db_written": False,
        "live_db_migrated": False,
        "live_db_projected": False,
        "live_db_read_only_verification": True,
        "true_live_execution_used": False,
        "production_defaults_changed": False,
        "db_backed_reads_default_changed": False,
        "db_backed_package_resolution_default_changed": False,
        "source_files_mutated": False,
        "source_package_mutated": False,
        "final_integrated_csv_generated": False,
        "output_root_only": True,
    }
    base_report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "phase14_report": str(phase14_report),
        "source_package": str(source_package),
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "run_id": run_id,
        "live_db_verification": live_db_verification,
        "phase14_evidence": phase14_evidence,
        "safety": safety,
    }
    # Phase 16: optional config-snapshot lineage metadata ONLY (the chain does not consume config).
    if config_snapshot_root is not None:
        from ..config_registry import config_snapshot_lineage_block

        base_report["config_snapshot"] = config_snapshot_lineage_block(Path(config_snapshot_root))

    # --- Controlled CSV refusal (out of scope; no synthesis). -------------------------------------
    if generate_final_csv:
        report = {
            **base_report,
            "status": DECISION_NOT_READY,
            "decision": DECISION_NOT_READY,
            "controlled_chain": None,
            "final_outputs": {"package_paths": [], "csv_paths": [], "row_counts": {}, "sha256": {}},
            "comparison": {"compared": False, "result": None, "normalized_rules": None},
            "csv_generation": {
                "requested": True,
                "decision": "out_of_scope",
                "blocker": CSV_OUT_OF_SCOPE_BLOCKER,
            },
        }
        report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
        report["report_path"] = str(report_path)
        _write_summary(work_root / SUMMARY_NAME, report)
        return report

    # --- Controlled chain: reuse the Phase 12 guarded operator run (fresh non-live temp DB). ------
    try:
        manifest = guarded.run_guarded_db_operator_run(
            source_package=source_package,
            work_root=work_root / GUARDED_SUBDIR,
            context_stamp=context_stamp,
            db_path=live_db_path,
            project_key=project_key,
            allow_certified_live_db=True,
            live_db_certification=Path(str(rerun["report_path"])),
        )
    except guarded.GuardedDbOperatorRunError as exc:
        raise DbCertifiedFinalOutputError(f"guarded operator run refused: {exc}") from exc

    guarded_status = manifest.get("status")
    guarded_decision = manifest.get("decision")
    approved = (manifest.get("approved_artifacts") or {}) if guarded_status == "ready" else {}
    context_package = approved.get("context_package")
    analysis_package = approved.get("analysis_package")
    chain_manifest = approved.get("chain_manifest")

    controlled_chain = {
        "guarded_operator_report": manifest.get("report_path"),
        "guarded_status": guarded_status,
        "guarded_decision": guarded_decision,
        "context_package": context_package,
        "analysis_package": analysis_package,
        "chain_manifest": chain_manifest,
        "live_db": manifest.get("live_db"),
    }

    # Not-ready evidence (guarded run did not approve) is an outcome, not a refusal: rc 1.
    if guarded_status != "ready" or guarded_decision != _GUARDED_DECISION_APPROVED:
        report = {
            **base_report,
            "status": DECISION_NOT_READY,
            "decision": DECISION_NOT_READY,
            "controlled_chain": controlled_chain,
            "final_outputs": {"package_paths": [], "csv_paths": [], "row_counts": {}, "sha256": {}},
            "comparison": {"compared": False, "result": None, "normalized_rules": None},
            "csv_generation": {"requested": False, "decision": "not_requested", "blocker": None},
        }
        report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
        report["report_path"] = str(report_path)
        _write_summary(work_root / SUMMARY_NAME, report)
        return report

    if require_guarded_operator_check:
        _require(
            bool(analysis_package) and Path(str(analysis_package)).is_dir(),
            "guarded operator run approved but the analysis package path is missing",
        )

    # --- Assemble the DB-certified final output under <work_root>/final_output/. ------------------
    analysis_src = Path(str(analysis_package))
    final_root = work_root / FINAL_OUTPUT_DIRNAME
    copied_root = final_root / analysis_src.name
    if copied_root.exists():
        raise DbCertifiedFinalOutputError(
            f"final output path already exists (refusing to overwrite): {copied_root}"
        )
    final_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(analysis_src, copied_root)
    row_counts, sha256 = _final_output_evidence(copied_root)

    report = {
        **base_report,
        "status": "ready",
        "decision": DECISION_READY,
        "controlled_chain": controlled_chain,
        "final_outputs": {
            "package_paths": [str(copied_root)],
            "csv_paths": [],
            "row_counts": row_counts,
            "sha256": sha256,
        },
        "comparison": {"compared": False, "result": None, "normalized_rules": None},
        "csv_generation": {"requested": False, "decision": "not_requested", "blocker": None},
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    report["report_path"] = str(report_path)
    _write_summary(work_root / SUMMARY_NAME, report)
    return report
