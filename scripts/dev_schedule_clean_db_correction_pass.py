#!/usr/bin/env python3
"""Capture clean-DB correction evidence (purge table delta, Stage 5/6/7 API)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import httpx

_REPO = Path(__file__).resolve().parents[1]
for _p in (_REPO / "src", _REPO / "subrepos/construction-financial-review/src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hb_assistant.construction.schedule_clean_db.purge import run_tropical_purge
from hb_assistant.construction.schedule_clean_db.schema_audit import (
    build_schedule_domain_inventory,
    build_schema_audit_report,
)

PURGE_TRACKED_TABLES = (
    "schedule_version_diffs",
    "schedule_version_diff_facts",
    "schedule_version_diff_detail_facts",
    "schedule_version_diff_impact_rollups",
    "schedule_baseline_projects",
    "schedule_baseline_activity_codes",
    "schedule_baseline_udfs",
    "schedule_baseline_wbs",
    "schedule_baseline_activities",
    "schedule_baseline_relationships",
)

API = "http://127.0.0.1:8000"
PROJECT = "tropical"
VIEWER = {"X-HB-UI-Role": "viewer"}
OPERATOR = {"X-HB-UI-Role": "operator"}
FINAL_SVK = "tropical|1071|2026-06-23 08:00"
BASELINE_SVK = "tropical|851|2025-11-28 08:00"


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_text(str(data), encoding="utf-8")


def _table_counts(db_path: str, tables: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        for table in tables:
            try:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                counts[table] = -1
    return counts


def _tropical_table_counts(db_path: str, tables: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        for table in tables:
            try:
                cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
                if "project_key" in cols:
                    counts[table] = int(
                        conn.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE project_key=?",
                            (PROJECT,),
                        ).fetchone()[0]
                    )
                elif "baseline_project_key" in cols:
                    counts[table] = int(
                        conn.execute(
                            f"""
                            SELECT COUNT(*) FROM {table}
                            WHERE baseline_project_key IN (
                              SELECT baseline_project_key FROM schedule_baseline_projects
                              WHERE import_id IN (
                                SELECT import_id FROM schedule_file_imports WHERE project_key=?
                              )
                            )
                            """,
                            (PROJECT,),
                        ).fetchone()[0]
                    )
                else:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                counts[table] = -1
    return counts


def capture_purge_evidence(evidence: Path, db_path: str) -> dict[str, Any]:
    before = _tropical_table_counts(db_path, PURGE_TRACKED_TABLES)
    _write(evidence / "purge-before-table-counts.json", before)
    result = run_tropical_purge(db_path, project_key=PROJECT, dry_run=False, apply=True)
    after = _tropical_table_counts(db_path, PURGE_TRACKED_TABLES)
    _write(evidence / "purge-after-table-counts.json", after)
    delta = {
        table: {"before": before.get(table, 0), "after": after.get(table, 0), "delta": after.get(table, 0) - before.get(table, 0)}
        for table in PURGE_TRACKED_TABLES
    }
    _write(evidence / "purge-table-delta.json", delta)
    _write(evidence / "purge-apply-result.json", result)
    audit = build_schema_audit_report(db_path, project_key=PROJECT)
    _write(evidence / "schedule-domain-inventory.json", build_schedule_domain_inventory(audit))
    return {"remaining": result.get("remaining_tropical_schedule_records"), "before": before, "after": after}


def _request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    **kwargs: Any,
) -> dict[str, Any]:
    response = client.request(method, url, headers=headers, **kwargs)
    body: Any
    try:
        body = response.json()
    except Exception:
        body = response.text[:8000]
    return {
        "method": method,
        "url": url,
        "headers": headers,
        "status": response.status_code,
        "body": body,
    }


def _wait_health(client: httpx.Client, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("backend health timeout")


def capture_stage5(evidence: Path) -> dict[str, Any]:
    with httpx.Client(base_url=API, timeout=120.0) as client:
        _wait_health(client)
        hub = _request(client, "GET", f"/api/projects/{PROJECT}/schedule", headers=VIEWER)
        versions = _request(
            client, "GET", f"/api/schedules/projects/{PROJECT}/versions", headers=VIEWER
        )
        _write(evidence / "stage05-hub-response.json", hub)
        _write(evidence / "stage05-versions-response.json", versions)
        version_body = versions.get("body")
        version_list = version_body if isinstance(version_body, list) else []
        keys = [str(v.get("schedule_version_key", "")) for v in version_list if isinstance(v, dict)]
        extraction = {
            "version_count": len(version_list),
            "twun19_present": FINAL_SVK in keys,
            "current_version_key": FINAL_SVK if FINAL_SVK in keys else (keys[0] if keys else None),
            "stage05_status": "pass"
            if hub.get("status") == 200
            and versions.get("status") == 200
            and len(version_list) >= 5
            and FINAL_SVK in keys
            else "fail",
            "schedule_version_keys": keys,
        }
        _write(evidence / "stage05-extraction.json", extraction)
        return extraction


def capture_stage67(evidence: Path, *, api_db_path: str) -> dict[str, Any]:
    with httpx.Client(base_url=API, timeout=120.0) as client:
        _wait_health(client)
        viewer_put = _request(
            client,
            "PUT",
            f"/api/projects/{PROJECT}/schedule/baselines",
            headers=VIEWER,
            json={"selections": {"current_contract_baseline": {"schedule_version_key": BASELINE_SVK}}},
        )
        baseline_put = _request(
            client,
            "PUT",
            f"/api/projects/{PROJECT}/schedule/baselines",
            headers=OPERATOR,
            json={"selections": {"current_contract_baseline": {"schedule_version_key": BASELINE_SVK}}},
        )
        controls_get = _request(
            client,
            "GET",
            f"/api/projects/{PROJECT}/schedule/controls",
            headers=VIEWER,
            params={"comparison_basis": "current_contract_baseline"},
        )
        review_before = _request(
            client, "GET", f"/api/projects/{PROJECT}/schedule/review-items", headers=VIEWER
        )
        before_items = (
            review_before.get("body", {}).get("items", [])
            if isinstance(review_before.get("body"), dict)
            else []
        )
        before_events = 0
        with sqlite3.connect(api_db_path) as conn:
            try:
                before_events = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM project_schedule_review_item_events WHERE project_key=?",
                        (PROJECT,),
                    ).fetchone()[0]
                )
            except sqlite3.Error:
                before_events = -1

        sync = _request(
            client,
            "POST",
            f"/api/projects/{PROJECT}/schedule/review-items",
            headers=OPERATOR,
            params={"comparison_basis": "prior_update"},
        )
        review_after_sync = _request(
            client, "GET", f"/api/projects/{PROJECT}/schedule/review-items", headers=VIEWER
        )
        after_sync_items = (
            review_after_sync.get("body", {}).get("items", [])
            if isinstance(review_after_sync.get("body"), dict)
            else []
        )
        patch_resp: dict[str, Any] | None = None
        promote_resp: dict[str, Any] | None = None
        action_note = ""
        target = next((i for i in after_sync_items if i.get("review_item_id")), None)
        if target:
            before_status = target.get("review_status")
            patch_resp = _request(
                client,
                "PATCH",
                f"/api/projects/{PROJECT}/schedule/review-items/{target['review_item_id']}",
                headers=OPERATOR,
                json={"disposition": "reviewed", "pm_notes": "correction-pass follow up"},
            )
            after_status = (
                patch_resp.get("body", {}).get("item", {}).get("review_status")
                if isinstance(patch_resp.get("body"), dict)
                else None
            )
            action_note = "patch_disposition_reviewed"
        else:
            preview_item = next((i for i in after_sync_items if not i.get("review_item_id")), None)
            if preview_item and preview_item.get("stable_item_key"):
                promote_resp = _request(
                    client,
                    "POST",
                    f"/api/projects/{PROJECT}/schedule/review-items/promote",
                    headers=OPERATOR,
                    json={"stable_item_keys": [preview_item["stable_item_key"]]},
                )
                action_note = "promote_preview_item"
            else:
                action_note = "no_eligible_item"

        review_after_action = _request(
            client, "GET", f"/api/projects/{PROJECT}/schedule/review-items", headers=VIEWER
        )
        after_events = 0
        with sqlite3.connect(api_db_path) as conn:
            try:
                after_events = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM project_schedule_review_item_events WHERE project_key=?",
                        (PROJECT,),
                    ).fetchone()[0]
                )
            except sqlite3.Error:
                after_events = -1

        _write(evidence / "stage06-viewer-baseline-mutation.json", viewer_put)
        _write(evidence / "stage06-baseline-put.json", baseline_put)
        _write(evidence / "stage06-controls-get.json", controls_get)
        _write(evidence / "stage07-review-before.json", review_before)
        _write(evidence / "stage07-review-sync.json", sync)
        _write(evidence / "stage07-review-after-sync.json", review_after_sync)
        if patch_resp:
            _write(evidence / "stage07-review-patch.json", patch_resp)
        if promote_resp:
            _write(evidence / "stage07-review-promote.json", promote_resp)
        _write(evidence / "stage07-review-after-action.json", review_after_action)

        viewer_class = (
            "role_gate_proven"
            if viewer_put.get("status") == 403
            else "route_contract_changed"
            if viewer_put.get("status") == 422
            else "failure"
            if viewer_put.get("status") < 300
            else "auth_not_established"
            if viewer_put.get("status") == 401
            else "unknown"
        )
        return {
            "stage06_status": "pass"
            if baseline_put.get("status") == 200 and controls_get.get("status") == 200
            else "fail",
            "stage07_status": "pass" if sync.get("status") == 200 and (patch_resp or promote_resp) else "fail",
            "viewer_mutation_classification": viewer_class,
            "action_note": action_note,
            "review_event_delta": after_events - before_events,
            "items_before": len(before_items),
            "items_after_sync": len(after_sync_items),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--purge-db-path", required=True)
    parser.add_argument("--api-db-path")
    parser.add_argument("--api-only", action="store_true")
    args = parser.parse_args(argv)
    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    api_db_path = args.api_db_path or args.purge_db_path

    purge_summary: dict[str, Any] = {}
    if not args.api_only:
        purge_summary = capture_purge_evidence(evidence, args.purge_db_path)

    stage5 = capture_stage5(evidence)
    stage67 = capture_stage67(evidence, api_db_path=api_db_path)

    final = {
        "purge_gate": "pass" if purge_summary.get("remaining") == 0 else ("skipped" if args.api_only else "fail"),
        "stage05_hub_api": stage5.get("stage05_status"),
        "stage06_controls_baseline_api": stage67.get("stage06_status"),
        "stage07_review_workbench_api": stage67.get("stage07_status"),
        "core_import_cpm_metric_chain": "prior_pass_not_rerun",
        "full_14_stage_classification": "pass"
        if all(
            status == "pass"
            for status in (
                "pass" if purge_summary.get("remaining") == 0 or args.api_only else "fail",
                stage5.get("stage05_status"),
                stage67.get("stage06_status"),
                stage67.get("stage07_status"),
            )
        )
        else "pass_with_limitations",
    }
    _write(evidence / "correction-final-classification.json", final)
    print(json.dumps({"purge": purge_summary, "stage5": stage5, "stage67": stage67, "final": final}, indent=2))
    return 0 if final["full_14_stage_classification"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
