#!/usr/bin/env python3
"""Phase 13A read-only Tropical API evidence capture (real local DB via TestClient)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "subrepos/construction-financial-review/src"))

os.environ.setdefault(
    "HB_ASSISTANT_DB_PATH",
    str(Path.home() / "Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"),
)

from hb_assistant.construction.analytics import create_app

EVIDENCE = Path(__file__).resolve().parent
PROJECT = "tropical"
VIEWER = {"X-HB-UI-Role": "viewer"}
OPERATOR = {"X-HB-UI-Role": "operator"}
AS_OF = "2026-07-03"

BASIS_CASES = [
    ("api-controls-prior-update.json", "prior_update", "controls"),
    ("api-controls-legacy-baseline.json", "baseline", "controls"),
    ("api-controls-current-contract-baseline.json", "current_contract_baseline", "controls"),
    ("api-controls-previous-progress-update-baseline.json", "previous_progress_update_baseline", "controls"),
    ("api-controls-secondary-progress-update-baseline.json", "secondary_progress_update_baseline", "controls"),
    ("api-workbench-prior-update.json", "prior_update", "workbench_get"),
    ("api-workbench-legacy-baseline.json", "baseline", "workbench_get"),
    ("api-workbench-current-contract-baseline.json", "current_contract_baseline", "workbench_get"),
    ("api-workbench-previous-progress-update-baseline.json", "previous_progress_update_baseline", "workbench_get"),
    ("api-workbench-secondary-progress-update-baseline.json", "secondary_progress_update_baseline", "workbench_get"),
]


def _save(name: str, payload: object) -> None:
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {name}")


def _extract_proof_fields(body: dict, basis: str) -> dict:
    baseline_ctx = body.get("baseline_context") or {}
    comparison_key = baseline_ctx.get("baseline_schedule_version_key")
    movement = (body.get("sections") or {}).get("movement") or {}
    return {
        "comparison_basis": body.get("comparison_basis") or basis,
        "baseline_schedule_version_key": comparison_key,
        "finish_moved_later_count": movement.get("finish_moved_later_count"),
        "available": body.get("available"),
    }


def _workbench_proof(body: dict, basis: str) -> dict:
    wb = body.get("workbench") or body
    items = wb.get("items") or []
    milestone = next((i for i in items if i.get("item_type") == "milestone"), None)
    driver = next((i for i in items if i.get("item_type") == "driver"), None)
    sample = milestone or driver or (items[0] if items else None)
    return {
        "comparison_basis": wb.get("comparison_basis") or basis,
        "review_scope": wb.get("review_scope"),
        "item_count": len(items),
        "sample_cue_summary": (sample or {}).get("cue_summary"),
        "sample_comparison_basis": (sample or {}).get("comparison_basis"),
        "sample_review_status": (sample or {}).get("review_status"),
    }


def main() -> int:
    client = TestClient(create_app())

    baselines = client.get(
        f"/api/projects/{PROJECT}/schedule/baselines",
        headers=VIEWER,
        params={"as_of": AS_OF},
    )
    _save(
        "api-baselines.json",
        {"status": baselines.status_code, "body": baselines.json()},
    )
    if baselines.status_code != 200:
        return 1

    proof_meta: dict[str, object] = {
        "project_key": PROJECT,
        "as_of": AS_OF,
        "basis_proofs": {},
        "activity_id": None,
        "driver_detail_comparison_key": None,
    }

    activity_id = None
    for fname, basis, kind in BASIS_CASES:
        if kind == "controls":
            resp = client.get(
                f"/api/projects/{PROJECT}/schedule/controls",
                headers=VIEWER,
                params={"comparison_basis": basis, "as_of": AS_OF},
            )
            body = resp.json()
            _save(fname, {"status": resp.status_code, "body": body})
            if resp.status_code == 200:
                proof_meta["basis_proofs"][basis] = _extract_proof_fields(body, basis)
                for ctrl in body.get("top_controls") or []:
                    if ctrl.get("activity_id"):
                        activity_id = str(ctrl["activity_id"])
                        break
        else:
            resp = client.get(
                f"/api/projects/{PROJECT}/schedule/review-items",
                headers=VIEWER,
                params={"comparison_basis": basis, "as_of": AS_OF},
            )
            body = resp.json()
            _save(fname, {"status": resp.status_code, "body": body})
            if resp.status_code == 200:
                proof_meta["basis_proofs"][f"workbench:{basis}"] = _workbench_proof(body, basis)
                if activity_id is None:
                    for item in (body.get("workbench") or {}).get("items") or body.get("items") or []:
                        if item.get("source_activity_id"):
                            activity_id = str(item["source_activity_id"])
                            break

    proof_meta["activity_id"] = activity_id

    if activity_id:
        for basis in (
            "current_contract_baseline",
            "previous_progress_update_baseline",
        ):
            resp = client.get(
                f"/api/projects/{PROJECT}/schedule/drivers/{activity_id}/detail",
                headers=VIEWER,
                params={"comparison_basis": basis, "as_of": AS_OF},
            )
            body = resp.json()
            _save(
                f"api-driver-detail-{basis}.json",
                {"status": resp.status_code, "activity_id": activity_id, "body": body},
            )
            if basis == "current_contract_baseline" and resp.status_code == 200:
                proof_meta["driver_detail_comparison_key"] = (
                    body.get("comparison_schedule_version_key")
                    or (body.get("baseline_context") or {}).get("schedule_version_key")
                )

    for basis in (
        "prior_update",
        "current_contract_baseline",
        "previous_progress_update_baseline",
    ):
        resp = client.get(
            f"/api/projects/{PROJECT}/schedule/drilldowns",
            headers=VIEWER,
            params={"type": "remaining_later", "comparison_basis": basis, "as_of": AS_OF},
        )
        _save(
            f"api-drilldown-remaining-later-{basis}.json",
            {"status": resp.status_code, "body": resp.json()},
        )

    for basis in ("prior_update", "current_contract_baseline"):
        resp = client.get(
            f"/api/projects/{PROJECT}/schedule/export",
            headers=VIEWER,
            params={"format": "markdown", "comparison_basis": basis, "as_of": AS_OF},
        )
        excerpt = ""
        if resp.status_code == 200:
            text = resp.text or ""
            excerpt = text[:2500]
        _save(
            f"api-export-markdown-{basis}.json",
            {
                "status": resp.status_code,
                "comparison_basis": basis,
                "content_type": resp.headers.get("content-type"),
                "body_excerpt": excerpt,
                "body_length": len(resp.text or ""),
            },
        )

  # Named workbench with existing disposition (GET only)
    named_wb = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "current_contract_baseline", "as_of": AS_OF},
    ).json()
    disposed = [
        i
        for i in (named_wb.get("workbench") or {}).get("items") or named_wb.get("items") or []
        if str(i.get("review_status")) in {"watching", "reviewed", "dismissed"}
    ]
    disposition_payload = {
        "disposition_count": len(disposed),
        "samples": [
            {
                "review_item_id": i.get("review_item_id"),
                "review_status": i.get("review_status"),
                "comparison_basis": i.get("comparison_basis"),
                "cue_summary": i.get("cue_summary"),
            }
            for i in disposed[:3]
        ],
    }
    _save("api-named-workbench-disposition-sample.json", disposition_payload)

    for basis in (
        "current_contract_baseline",
        "previous_progress_update_baseline",
    ):
        sync = client.post(
            f"/api/projects/{PROJECT}/schedule/review-items",
            headers=OPERATOR,
            params={"comparison_basis": basis, "as_of": AS_OF},
        )
        body = sync.json()
        _save(
            f"api-workbench-sync-{basis}.json",
            {"status": sync.status_code, "body": body},
        )
        if sync.status_code == 200:
            proof_meta["basis_proofs"][f"workbench_sync:{basis}"] = _workbench_proof(body, basis)

    _save("api-proof-meta.json", proof_meta)
    print(json.dumps(proof_meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
