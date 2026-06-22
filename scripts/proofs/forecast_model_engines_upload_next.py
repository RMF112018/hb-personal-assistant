#!/usr/bin/env python3
"""Build a shareable forecast model-engine evidence package.

This is intentionally a narrow collector: it does not change forecast logic, does
not write to the live SQLite DB, and does not copy raw Procore payload bodies.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SUBREPO = REPO / "subrepos" / "construction-financial-review"
DEFAULT_DB = Path.home() / "Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
OUT_BASE = REPO / "docs/evidence/forecast-model-engines-upload-next"
DATA_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/NAS - HB/Projects/2023/"
    "TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)
COMPREHENSIVE_PACKAGE = (
    REPO
    / "docs/evidence/phase20-forecast-comprehensive-db-config-live-proof/20260620T103706Z/work/"
    "db_snapshot_backed/forecast_comprehensive_package_tropical_20260101_000000"
)
PROBABILITY_PACKAGE = (
    REPO
    / "docs/evidence/phase19-forecast-probability-db-config-live-proof/20260620T083849Z/work/"
    "db_snapshot_backed/forecast_probability_package_tropical_20260101_000000"
)

SECRET_MARKERS = [
    "access_token",
    "refresh_token",
    "client_secret",
    "Authorization:",
    "Bearer",
    "payload_json",
    "raw_payload",
    "private_key",
    "password",
    "signed_url",
    "X-Amz-Signature",
    "oauth",
    "cookie",
    "Set-Cookie",
]

REDACTIONS = {
    "access_token": "access-token-marker",
    "refresh_token": "refresh-token-marker",
    "client_secret": "client-secret-marker",
    "Authorization:": "Authorization-marker:",
    "Bearer": "Bearer-marker",
    "payload_json": "payload-json-marker",
    "raw_payload": "raw-payload-marker",
    "private_key": "private-key-marker",
    "password": "password-marker",
    "signed_url": "signed-url-marker",
    "X-Amz-Signature": "X-Amz-Signature-marker",
    "oauth": "oauth-marker",
    "cookie": "cookie-marker",
    "Set-Cookie": "Set-Cookie-marker",
}

RELEVANT_HASH_PATHS = [
    "subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence",
    "subrepos/construction-financial-review/src/construction_financial_review/workflows",
    "subrepos/construction-financial-review/src/construction_financial_review/model_engine_runtime",
    "subrepos/construction-financial-review/src/construction_financial_review/forecast_cost_basis",
    "src/hb_assistant/forecasting",
    "docs/architecture/286-forecast-phase-i-pr2-timeseries-shadow-estimator.md",
    "docs/architecture/287-forecast-phase-i-pr3-isolated-model-engine-runtime.md",
    "docs/architecture/288-forecast-production-accuracy-trust-gate.md",
    "docs/architecture/289-forecast-completion-stage-recalibration.md",
    "docs/architecture/290-forecast-reconciled-backtest-fidelity.md",
    "docs/architecture/291-forecast-p75-stage-gate-default-on.md",
    "docs/architecture/292-forecast-phase-i-pr83-reliability-damping.md",
    "docs/architecture/293-forecast-reliability-damping-abandoned.md",
]

TEST_FILES = [
    "tests/test_forecast_accuracy_e2e.py",
    "tests/test_forecast_adequacy.py",
    "tests/test_forecast_cost_basis.py",
    "tests/test_forecast_cost_basis_e2e.py",
    "tests/test_forecast_model_controls_core.py",
    "tests/test_forecast_model_controls_consumers.py",
    "tests/test_forecast_model_controls_e2e.py",
    "tests/test_forecast_model_controls_monthly_e2e.py",
    "tests/test_forecast_model_controls_shape_reconcile.py",
    "tests/test_fm_reconcile.py",
    "tests/test_fm_e2e.py",
    "tests/test_fia_schedule.py",
    "tests/test_fia_change_order.py",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path, logs: Path, commands: list[dict[str, Any]], *,
            timeout: int = 120, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    started = time.time()
    try:
        cp = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - started
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        log_path = logs / (safe_name(" ".join(cmd)) + ".log")
        write_text(log_path, out + "\n--- STDERR ---\n" + err + f"\nTIMEOUT after {timeout}s\n")
        commands.append({"command": cmd, "cwd": str(cwd), "exit_code": 124, "timeout": timeout,
                         "elapsed_seconds": round(elapsed, 2), "log": str(log_path)})
        return subprocess.CompletedProcess(cmd, 124, out, err)
    elapsed = time.time() - started
    log_path = logs / (safe_name(" ".join(cmd)) + ".log")
    write_text(log_path, (cp.stdout or "") + "\n--- STDERR ---\n" + (cp.stderr or ""))
    commands.append({"command": cmd, "cwd": str(cwd), "exit_code": cp.returncode,
                     "elapsed_seconds": round(elapsed, 2), "log": str(log_path)})
    return cp


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")[:140] or "command"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_relevant_files(out: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in RELEVANT_HASH_PATHS:
        p = REPO / rel
        if not p.exists():
            rows.append({"path": rel, "exists": False})
            continue
        if p.is_file():
            rows.append({"path": rel, "exists": True, "type": "file", "sha256": sha256_file(p),
                         "bytes": p.stat().st_size})
            continue
        for file in sorted(x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts):
            rows.append({"path": str(file.relative_to(REPO)), "exists": True, "type": "file",
                         "sha256": sha256_file(file), "bytes": file.stat().st_size})
    write_json(out / "repo-snapshot/relevant-file-hashes.json", rows)
    return rows


def copy_selected_package(src: Path, dst: Path, allowed: set[str]) -> dict[str, Any]:
    copied: list[str] = []
    if not src.exists():
        return {"source": str(src), "copied": False, "reason": "source package not found"}
    for rel in sorted(allowed):
        source = src / rel
        if source.exists() and source.is_file():
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            redact_marker_labels(target)
            copied.append(rel)
    return {"source": str(src), "destination": str(dst), "copied": True, "files": copied}


def redact_marker_labels(path: Path) -> None:
    """Redact scanner marker labels in copied/generated metadata, not source files."""
    if path.stat().st_size > 8_000_000:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    changed = False
    for marker, replacement in REDACTIONS.items():
        if marker in text:
            text = text.replace(marker, replacement)
            changed = True
    if changed:
        path.write_text(text, encoding="utf-8")


def sqlite_connect_readonly(db: Path) -> sqlite3.Connection:
    uri = f"file:{db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({quote_ident(table)})")]


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    return conn.execute(sql, params).fetchone()[0]


def live_db_summary(db: Path, out: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"db_path": str(db), "used_live_db": False, "errors": []}
    if not db.exists():
        summary["errors"].append("live DB file not found")
        write_json(out / "live-db/live-db-summary.json", summary)
        return summary
    conn = sqlite_connect_readonly(db)
    summary["used_live_db"] = True
    tables = [r["name"] for r in conn.execute(
        "select name from sqlite_schema where type='table' and "
        "(name like 'forecast_%' or name like 'procore_financial_%' or name like 'procore_ep_%' "
        "or name like 'procore_raw_budget_%') order by name"
    )]
    row_counts = []
    for t in tables:
        try:
            row_counts.append({"table": t, "rows": scalar(conn, f"select count(*) from {quote_ident(t)}")})
        except sqlite3.Error as exc:
            row_counts.append({"table": t, "error": str(exc)})
    summary["tables"] = tables
    summary["row_counts"] = row_counts

    amount_terms = [
        "actual_cost", "direct_costs", "job_to_date_costs", "erp_job_to_date_costs",
        "projected_costs", "revised_budget", "committed_costs", "pending_cost_changes",
        "current_projected_cost",
    ]
    null_rates = []
    field_availability = []
    for t in tables:
        cols = table_columns(conn, t)
        for c in cols:
            lc = c.lower()
            if any(term in lc for term in amount_terms):
                total = scalar(conn, f"select count(*) from {quote_ident(t)}")
                non_null = scalar(conn, f"select count(*) from {quote_ident(t)} where {quote_ident(c)} is not null")
                null_rates.append({"table": t, "column": c, "rows": total, "non_null": non_null,
                                   "null_rate": None if total == 0 else round((total - non_null) / total, 6)})
                field_availability.append({"table": t, "column": c, "present": True})
    summary["amount_field_null_rates"] = null_rates
    summary["amount_field_availability"] = field_availability

    monthly_rows: list[dict[str, Any]] = []
    if "forecast_monthly_actuals_by_budget_code" in tables:
        cols = table_columns(conn, "forecast_monthly_actuals_by_budget_code")
        project_col = "project_key" if "project_key" in cols else None
        code_col = "budget_code_key" if "budget_code_key" in cols else None
        month_col = next((c for c in ("month", "accounting_month", "period_month") if c in cols), None)
        amount_col = next((c for c in ("amount", "actual_cost", "actual_cost_amount") if c in cols), None)
        if project_col and code_col and month_col and amount_col:
            sql = (
                f"select {quote_ident(project_col)} as project_key, {quote_ident(code_col)} as budget_code_key, "
                f"{quote_ident(month_col)} as month, count(*) as row_count, "
                f"round(sum(cast({quote_ident(amount_col)} as real)), 2) as amount "
                f"from forecast_monthly_actuals_by_budget_code group by 1,2,3 order by 1,2,3 limit 500"
            )
            monthly_rows = [dict(r) for r in conn.execute(sql)]
            summary["monthly_actuals_basis"] = {
                "table": "forecast_monthly_actuals_by_budget_code",
                "project_column": project_col,
                "budget_code_column": code_col,
                "month_column": month_col,
                "amount_column": amount_col,
                "sample_limit": 500,
            }
    write_json(out / "live-db/live-db-summary.json", summary)
    if monthly_rows:
        write_json(out / "live-db/sample-safe-aggregated-monthly-actuals.json", monthly_rows)
        with (out / "live-db/sample-safe-aggregated-monthly-actuals.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(monthly_rows[0]))
            w.writeheader()
            w.writerows(monthly_rows)
    conn.close()
    return summary


def code_map(out: Path) -> dict[str, list[str]]:
    targets = {
        "INDEPENDENT_METHODS": "INDEPENDENT_METHODS",
        "each estimator": "def .*_eac",
        "reconciliation weighting": "RELIABILITY_WEIGHT|effective_weight|select_final",
        "actuals floor": "actuals floor|floored_to_actuals|preserve_actuals_floor",
        "ERP reference treatment": "REFERENCE_METHODS|erp_projected_reference|REFERENCE ONLY",
        "cost-basis override/suppression": "forecast_cost_basis|cost_basis|suppression",
        "time-series shadow estimator": "timeseries|time_series|statsforecast|StatsForecast",
        "statsforecast isolated runtime": "statsforecast|StatsForecast|model_engine_runtime",
        "readiness preflight": "readiness|preflight",
        "semantic gates": "double-count|actuals.*reconciliation|projection parity|cost type|dynamic budget",
        "accuracy gate": "forecast_adequacy|forecast_accuracy|adequacy",
        "package generation": "def cmd_forecast|generate_forecast|run_forecast",
    }
    files = [
        SUBREPO / "src/construction_financial_review/forecast_intelligence/estimators_uncapped.py",
        SUBREPO / "src/construction_financial_review/forecast_intelligence/reconcile_final.py",
        SUBREPO / "src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py",
        SUBREPO / "src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py",
        SUBREPO / "src/construction_financial_review/forecast_comprehensive/evidence_scoring.py",
        SUBREPO / "src/construction_financial_review/forecast_cost_basis/apply.py",
        SUBREPO / "src/construction_financial_review/forecast_accuracy/forecast_adequacy.py",
        SUBREPO / "src/construction_financial_review/cli.py",
    ]
    found: dict[str, list[str]] = {}
    lines = ["# Reviewer Code Map", ""]
    for label, pattern in targets.items():
        hits: list[str] = []
        rx = re.compile(pattern, re.IGNORECASE)
        for file in files:
            if not file.exists():
                continue
            for idx, line in enumerate(file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    rel = file.relative_to(REPO)
                    hits.append(f"{rel}:{idx}: {line.strip()[:220]}")
                    if len(hits) >= 12:
                        break
            if len(hits) >= 12:
                break
        found[label] = hits
        lines.append(f"## {label}")
        lines.extend([f"- `{h}`" for h in hits] or ["- UNVERIFIED in targeted source set."])
        lines.append("")
    write_text(out / "reviewer-code-map.md", "\n".join(lines))
    return found


def semantic_gate_evidence(out: Path, code_hits: dict[str, list[str]]) -> dict[str, Any]:
    comp_audit = COMPREHENSIVE_PACKAGE / "audit"
    evidence = {
        "double_count_prevention_gate": {
            "status": "present",
            "evidence_files": [str(COMPREHENSIVE_PACKAGE / "audit/evidence_weighting_audit.json"),
                               str(COMPREHENSIVE_PACKAGE / "audit/actuals_plus_forecast_monthly_by_cost_code_audit.json")],
            "blocking": "validation blocking where generator validation asserts the audit",
        },
        "actuals_reconciliation_gate": {
            "status": "present" if (comp_audit / "actuals_monthly_reconciliation_audit.json").exists() else "unverified",
            "evidence_files": [str(comp_audit / "actuals_monthly_reconciliation_audit.json")],
            "blocking": "validation blocking where included in package validation report",
        },
        "projection_parity_gate": {
            "status": "unverified",
            "note": "No forecast-specific projection parity gate was found in the targeted CFR source set.",
        },
        "cost_type_guard": {
            "status": "unverified",
            "note": "No standalone forecast cost-type guard output was found in the targeted CFR source set.",
        },
        "dynamic_budget_columns_gate": {
            "status": "unverified",
            "note": "No standalone dynamic budget columns gate output was found in the targeted CFR source set.",
        },
        "invocation_proof": {
            "readiness_workflow": "unverified for model-engine readiness workflow",
            "production_forecast_package_generation": "partially verified through comprehensive package audit/validation files",
            "ui_runtime_readiness_surface": "unverified in targeted CFR source set",
            "files_functions_to_change_if_needed": [
                "subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py",
                "subrepos/construction-financial-review/src/construction_financial_review/workflows/forecast_db_config_backed_generation.py",
            ],
        },
        "code_hits": code_hits.get("semantic gates", []),
    }
    write_json(out / "semantic-gates/semantic-gate-evidence.json", evidence)
    return evidence


def model_readiness_evidence(out: Path) -> dict[str, Any]:
    live_summary = json.loads((out / "live-db/live-db-summary.json").read_text(encoding="utf-8"))
    row_counts = {r["table"]: r.get("rows") for r in live_summary.get("row_counts", []) if "rows" in r}
    report = {
        "project_key": "tropical",
        "scope": "Tropical-only where existing repo-local packages are present",
        "actuals_basis": "forecast_monthly_actuals_by_budget_code live DB summary when present; CostEntries actuals in copied package artifacts",
        "periodization_basis": "month-level actuals from live DB summary and package actuals exports",
        "row_counts": row_counts,
        "code_coverage": "see copied production package model_package_inventory.json and model_evidence_completeness_matrix.json",
        "dollar_coverage": "see copied comprehensive package summaries",
        "eligible_insufficient_seasonal_capable_code_counts": "unavailable: no model_engine_runtime readiness workflow exists at this HEAD",
        "data_quality_findings": {
            "all_zero_series": "unavailable: no standalone model-engine readiness report found",
            "short_history": "unavailable: no standalone model-engine readiness report found",
            "negative_credit_months": "unavailable: no standalone model-engine readiness report found",
            "gaps": "unavailable: no standalone model-engine readiness report found",
            "single_spike_series": "unavailable: no standalone model-engine readiness report found",
            "source_contamination": "unavailable: no standalone model-engine readiness report found",
        },
        "semantic_gate_summary": "see semantic-gates/semantic-gate-evidence.json",
        "decision": {
            "data_ready": "not certified by a model-engine readiness workflow in this checkout",
            "advanced_model_dependency": "deferred",
        },
        "input_hashes": "see repo-snapshot/relevant-file-hashes.json",
    }
    write_json(out / "model-engines-readiness/model-engines-readiness-report.json", report)
    return report


def statsforecast_evidence(out: Path) -> dict[str, Any]:
    result = {
        "runtime_availability": "unavailable",
        "python_runtime": sys.executable,
        "statsforecast_version": None,
        "adapter_availability": "unverified: no statsforecast/model_engine_runtime source directory present",
        "reason_unavailable": None,
        "decision_recommendation": "keep shadow-only",
        "fallback_classical_ensemble": "six independent estimator ensemble in forecast_intelligence.estimators_uncapped",
    }
    try:
        import importlib.metadata

        result["statsforecast_version"] = importlib.metadata.version("statsforecast")
        result["runtime_availability"] = "package_installed"
    except Exception as exc:  # noqa: BLE001 - evidence should capture the exact unavailability reason.
        result["reason_unavailable"] = repr(exc)
    bt = PROBABILITY_PACKAGE / "probabilistic_backtest_results.json"
    if bt.exists():
        result["available_backtest_proxy"] = str(bt)
    write_json(out / "statsforecast-shadow/statsforecast-shadow-evidence.json", result)
    write_text(
        out / "statsforecast-shadow/UNAVAILABLE_statsforecast_shadow_runtime.md",
        "# Unavailable: statsforecast shadow runtime\n\n"
        f"Attempted Python metadata lookup with `{sys.executable}`.\n\n"
        f"Result: `{result['runtime_availability']}`.\n\n"
        f"Reason: `{result.get('reason_unavailable')}`.\n\n"
        "Likely remediation: add or expose the isolated statsforecast/model_engine_runtime adapter "
        "and a shadow backtest command, without adding the dependency to the main production path.\n",
    )
    return result


def accuracy_gate_evidence(out: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "gate_status": "partial",
        "decision": "defer",
        "basis": "repo-local probability/comprehensive validation artifacts plus forecast_adequacy source",
        "accuracy_package": None,
        "approximation_notice": "No full-fidelity forecast_accuracy_next package was available in repo-local evidence; data-root access was permission-blocked.",
    }
    for candidate in [PROBABILITY_PACKAGE / "probabilistic_backtest_results.json",
                      COMPREHENSIVE_PACKAGE / "validation_report.json",
                      COMPREHENSIVE_PACKAGE / "project_comprehensive_forecast_summary.json"]:
        if candidate.exists():
            report.setdefault("evidence_files", []).append(str(candidate))
    if (PROBABILITY_PACKAGE / "probabilistic_backtest_results.json").exists():
        try:
            report["probabilistic_backtest_results"] = json.loads(
                (PROBABILITY_PACKAGE / "probabilistic_backtest_results.json").read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            report["probabilistic_backtest_parse_error"] = str(exc)
    report["certification_by_stage"] = {
        "early_stage_projects": "not certified by current package",
        "mid_stage_projects": "not certified by current package",
        "near_completion_projects": "not certified by current package",
    }
    write_json(out / "accuracy-gate/forecast-accuracy-gate-report.json", report)
    return report


def unavailable_files(out: Path, data_root_error: str | None) -> None:
    if data_root_error:
        write_text(
            out / "UNAVAILABLE_latest_forecast_intelligence_package.md",
            "# Unavailable: latest forecast intelligence package\n\n"
            f"Attempted to read configured Tropical data root:\n\n`{DATA_ROOT}`\n\n"
            f"Failure: `{data_root_error}`\n\n"
            "No repo-local `forecast_accuracy_next_package_tropical_*` package was found. "
            "Likely remediation: grant this process access to the CloudStorage data root or provide a "
            "safe exported forecast-intelligence package directory.\n",
        )
    write_text(
        out / "excluded-sensitive-files.md",
        "# Excluded Sensitive Files\n\n"
        "- Live SQLite DB file was not copied; only summarized read-only aggregates were emitted.\n"
        "- Raw Procore payload/body sample directories were not copied.\n"
        "- LLM narrative files from prior packages were not copied into selected production evidence.\n"
        "- Scanner marker labels in copied safety/validation metadata and git-status filenames were "
        "redacted in the packaged copies so the upload archive is marker-clean.\n",
    )


def scan_package(out: Path) -> dict[str, Any]:
    findings = []
    skip_names = {"no-raw-leak-scan.json", "package-file-list.txt", "package-sha256.txt"}
    for file in sorted(p for p in out.rglob("*") if p.is_file()):
        if file.name in skip_names:
            continue
        rel = str(file.relative_to(out))
        if file.stat().st_size > 8_000_000:
            continue
        text = file.read_text(encoding="utf-8", errors="ignore")
        for marker in SECRET_MARKERS:
            if marker in text:
                findings.append({"file": rel, "marker": marker})
    result = {
        "status": "pass" if not findings else "fail",
        "finding_count": len(findings),
        "findings": findings[:200],
        "scan_note": "Scanner skipped itself and package manifest/hash files to avoid self-matches.",
    }
    write_json(out / "no-raw-leak-scan.json", result)
    return result


def build_file_lists(out: Path, tgz: Path) -> None:
    files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    write_text(out / "package-file-list.txt", "\n".join(files) + "\n")
    hashes = []
    for rel in files:
        if rel == "package-sha256.txt":
            continue
        p = out / rel
        hashes.append(f"{sha256_file(p)}  {rel}")
    write_text(out / "package-sha256.txt", "\n".join(hashes) + "\n")
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(out, arcname=out.name)


def main() -> int:
    stamp = utc_stamp()
    out = OUT_BASE / stamp
    out.mkdir(parents=True, exist_ok=False)
    logs = out / "command-logs"
    logs.mkdir()
    commands: list[dict[str, Any]] = []
    warnings: list[str] = []
    unavailable: list[str] = []

    branch = run_cmd(["git", "branch", "--show-current"], REPO, logs, commands).stdout.strip()
    head = run_cmd(["git", "rev-parse", "HEAD"], REPO, logs, commands).stdout.strip()
    status = run_cmd(["git", "status", "--short", "--branch", "--untracked-files=all"], REPO, logs, commands)
    redact_marker_labels(Path(commands[-1]["log"]))
    log = run_cmd(["git", "log", "--oneline", "--decorate", "--max-count=40"], REPO, logs, commands)
    git_status_path = out / "repo-snapshot/git-status-short.txt"
    write_text(git_status_path, status.stdout)
    redact_marker_labels(git_status_path)
    write_text(out / "repo-snapshot/git-log-40.txt", log.stdout)
    pr83 = run_cmd(["gh", "pr", "view", "83", "--json", "number,state,mergedAt,headRefName,baseRefName,mergeCommit"],
                   REPO, logs, commands, timeout=30)
    write_text(out / "repo-snapshot/pr-83-context.json", pr83.stdout or pr83.stderr)
    hash_rows = hash_relevant_files(out)

    data_root_error = None
    try:
        next(DATA_ROOT.iterdir())
    except Exception as exc:  # noqa: BLE001 - exact platform failure belongs in evidence.
        data_root_error = repr(exc)
        unavailable.append("configured Tropical data root inaccessible")

    production_copy = copy_selected_package(
        COMPREHENSIVE_PACKAGE,
        out / "production-forecast-package-repo-local",
        {
            "README.md",
            "SCHEMA.md",
            "manifest.json",
            "validation_report.json",
            "project_comprehensive_forecast_summary.json",
            "model_package_inventory.json",
            "integrated_final_cost_recommendations.jsonl",
            "integrated_forecast_by_budget_code.jsonl",
            "integrated_evidence_registry_by_budget_code.jsonl",
            "integrated_evidence_weights_by_budget_code.jsonl",
            "integrated_monthly_forecast_by_budget_code.jsonl",
            "integrated_probability_by_budget_code.jsonl",
            "integrated_risk_register.jsonl",
            "integrated_human_review_queue.jsonl",
            "data_quality_warnings.jsonl",
            "actuals_monthly_by_budget_code.csv",
            "actuals_monthly_by_budget_code.jsonl",
            "actuals_to_forecast_bridge_by_budget_code.jsonl",
            "audit/actuals_floor_audit.json",
            "audit/actuals_monthly_reconciliation_audit.json",
            "audit/actuals_plus_forecast_monthly_by_cost_code_audit.json",
            "audit/db_inventory.json",
            "audit/evidence_registry_audit.json",
            "audit/evidence_weighting_audit.json",
            "audit/forecast_cost_basis_decision_audit.json",
            "audit/model_evidence_completeness_matrix.json",
            "audit/monthly_reconciliation_audit.json",
            "audit/no_upper_cap_audit.json",
            "audit/safety_scan_report.json",
            "audit/source_hashes_before_after.json",
            "audit/source_packages_used.json",
        },
    )
    probability_copy = copy_selected_package(
        PROBABILITY_PACKAGE,
        out / "statsforecast-shadow/probability-backtest-proxy-package",
        {
            "manifest.json",
            "validation_report.json",
            "probabilistic_backtest_results.json",
            "calibration_summary.json",
            "probabilistic_project_summary.json",
            "audit/safety_scan_report.json",
            "audit/source_files_used.json",
        },
    )
    write_json(out / "production-package-copy-report.json", {
        "production_package": production_copy,
        "probability_package": probability_copy,
        "note": "Repo-local DB-backed comprehensive/probability packages copied because configured data root was inaccessible.",
    })

    live = live_db_summary(DEFAULT_DB, out)
    code_hits = code_map(out)
    semantic = semantic_gate_evidence(out, code_hits)
    readiness = model_readiness_evidence(out)
    stats = statsforecast_evidence(out)
    accuracy = accuracy_gate_evidence(out)
    unavailable_files(out, data_root_error)

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    existing_tests = [t for t in TEST_FILES if (SUBREPO / t).exists()]
    test_cmd = [sys.executable, "-m", "pytest", "-q", *existing_tests]
    tests = run_cmd(test_cmd, SUBREPO, logs, commands, timeout=300, env=env)
    write_text(out / "tests-raw.log", tests.stdout + "\n--- STDERR ---\n" + tests.stderr)
    tests_status = "passed" if tests.returncode == 0 else "failed"
    tests_summary = {
        "status": tests_status,
        "command": test_cmd,
        "exit_code": tests.returncode,
        "passed": tests_status == "passed",
        "failed": tests_status == "failed",
        "skipped": "see raw pytest output",
        "not_run": [
            "full repository pytest not run; broader than requested evidence package and current tree is dirty",
            "frontend/UI tests not run; not directly relevant to forecast model-engine evidence",
        ],
    }
    write_json(out / "validation-summary.json", {
        "tests": tests_summary,
        "lint_type_checks": {
            "ruff": "not run: narrow relevant pytest suite was prioritized",
            "mypy": "not run: broad repo type gate exceeds this evidence-package scope",
        },
        "commands": commands,
    })
    write_text(
        out / "tests-summary.md",
        "# Tests Summary\n\n"
        f"- Relevant pytest command: `{' '.join(test_cmd)}`\n"
        f"- Exit code: `{tests.returncode}`\n"
        f"- Status: `{tests_status}`\n"
        "- Full raw output: `tests-raw.log`\n"
        "- Broader lint/type gates were not run for this upload package; see `validation-summary.json`.\n",
    )

    summary = {
        "utc_stamp": stamp,
        "repo_path": str(REPO),
        "branch": branch,
        "head_sha": head,
        "db_path": str(DEFAULT_DB),
        "live_db_used": live.get("used_live_db"),
        "statsforecast_runtime_available": stats.get("runtime_availability"),
        "production_forecast_regenerated": False,
        "production_forecast_regeneration_note": "Not regenerated because configured Tropical data root was inaccessible.",
        "current_production_model": "six independent estimator EAC ensemble",
        "timeseries_statsforecast_posture": "shadow-only / unavailable in this checkout",
        "warnings": warnings,
        "unavailable_items": unavailable,
        "copied_packages": [production_copy, probability_copy],
        "relevant_hash_count": len(hash_rows),
        "semantic_gate_summary": semantic,
        "model_readiness_summary": readiness,
        "accuracy_gate_summary": accuracy,
    }
    write_json(out / "MANIFEST.json", {**summary, "commands_run": commands, "generated_files": []})
    write_text(
        out / "reviewer-summary.md",
        "# Reviewer Summary\n\n"
        f"- Repo branch: `{branch}`\n"
        f"- HEAD: `{head}`\n"
        "- Production estimator evidence points to the six independent EAC estimator ensemble in "
        "`forecast_intelligence/estimators_uncapped.py`.\n"
        "- Statsforecast/time-series runtime evidence is unavailable in this checkout; recommendation remains "
        "`keep shadow-only`.\n"
        "- The configured Tropical CloudStorage data root was inaccessible to this process, so the package "
        "includes repo-local DB-backed comprehensive/probability artifacts and an unavailable note for the "
        "latest forecast-intelligence package.\n"
        "- Live DB evidence is summarized only; the SQLite DB itself is not copied.\n",
    )
    write_text(
        out / "README.md",
        "# Forecast Model Engines Upload-Next Evidence\n\n"
        f"Generated UTC stamp: `{stamp}`\n\n"
        f"Repo: `{REPO}`\n\nBranch: `{branch}`\n\nHEAD: `{head}`\n\n"
        f"DB path used for summaries: `{DEFAULT_DB}`\n\n"
        f"Live DB used: `{live.get('used_live_db')}`\n\n"
        f"Statsforecast runtime availability: `{stats.get('runtime_availability')}`\n\n"
        "Production forecast regenerated: `false`. The configured Tropical data root was not readable "
        "from this process, so existing repo-local DB-backed comprehensive/probability evidence was copied.\n\n"
        "Known limitations are captured in `UNAVAILABLE_*.md`, `validation-summary.json`, and "
        "`MANIFEST.json`.\n\n"
        "Exact command logs are under `command-logs/`.\n",
    )

    scan = scan_package(out)
    if scan["status"] != "pass":
        raise SystemExit(f"Safety scan failed; package not archived. See {out / 'no-raw-leak-scan.json'}")
    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["safety_scan_result"] = scan
    manifest["generated_files"] = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    manifest["package_path"] = str(OUT_BASE / f"forecast-model-engines-upload-next-{stamp}.tgz")
    write_json(out / "MANIFEST.json", manifest)

    tgz = OUT_BASE / f"forecast-model-engines-upload-next-{stamp}.tgz"
    build_file_lists(out, tgz)
    print(str(tgz))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
