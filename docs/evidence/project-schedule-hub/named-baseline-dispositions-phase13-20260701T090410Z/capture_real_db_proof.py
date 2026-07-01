#!/usr/bin/env python3
"""Capture Phase 13 real-DB named baseline disposition API proof."""

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
from hb_assistant.store.project_schedule_named_baseline_review_repository import (
    NAMED_REVIEW_ITEM_ID_PREFIX,
)

EVIDENCE = Path(__file__).resolve().parent
AS_OF = "2026-07-03"
PROJECT = "tropical"
HEADERS = {"X-HB-UI-Role": "operator"}
VIEWER = {"X-HB-UI-Role": "viewer"}


def _sanitize(payload: dict) -> dict:
    out = json.loads(json.dumps(payload))
    for item in out.get("items") or out.get("workbench", {}).get("items") or []:
        if isinstance(item, dict) and item.get("item_title"):
            item["item_title"] = "[redacted]"
        ev = item.get("evidence") if isinstance(item, dict) else None
        if isinstance(ev, dict):
            for key in ("activity_name", "wbs_code", "cue_summary"):
                if key in ev:
                    ev[key] = "[redacted]"
    return out


def main() -> None:
    client = TestClient(create_app())
    before = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "current_contract_baseline", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-named-workbench-before-sync.json").write_text(
        json.dumps(_sanitize(before), indent=2)
    )

    sync = client.post(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=HEADERS,
        params={"comparison_basis": "current_contract_baseline", "as_of": AS_OF},
    )
    sync.raise_for_status()
    sync_body = sync.json()
    (EVIDENCE / "api-named-workbench-sync.json").write_text(json.dumps(_sanitize(sync_body), indent=2))

    after = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "current_contract_baseline", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-named-workbench-after-sync.json").write_text(
        json.dumps(_sanitize(after), indent=2)
    )

    items = after.get("items") or []
    named = next(
        (i for i in items if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)),
        None,
    )
    if not named:
        items = sync_body.get("workbench", {}).get("items") or []
        named = next(
            i for i in items if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
        )
    review_item_id = str(named["review_item_id"])
    patch = client.patch(
        f"/api/projects/{PROJECT}/schedule/review-items/{review_item_id}",
        headers=HEADERS,
        json={"review_status": "watching", "pm_notes": "phase13 real db proof"},
    )
    patch.raise_for_status()
    (EVIDENCE / "api-named-workbench-patch.json").write_text(
        json.dumps(_sanitize(patch.json()), indent=2)
    )

    after_patch = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "current_contract_baseline", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-named-workbench-after-patch.json").write_text(
        json.dumps(_sanitize(after_patch), indent=2)
    )

    prior = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "prior_update", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-prior-update-regression.json").write_text(json.dumps(_sanitize(prior), indent=2))

    legacy = client.post(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=HEADERS,
        params={"comparison_basis": "baseline", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-legacy-baseline-regression.json").write_text(json.dumps(_sanitize(legacy), indent=2))

    progress = client.get(
        f"/api/projects/{PROJECT}/schedule/review-items",
        headers=VIEWER,
        params={"comparison_basis": "previous_progress_update_baseline", "as_of": AS_OF},
    ).json()
    (EVIDENCE / "api-cross-slot-isolation.json").write_text(json.dumps(_sanitize(progress), indent=2))

    proof = {
        "review_scope": sync_body.get("workbench", {}).get("review_scope"),
        "synced": sync_body.get("workbench", {}).get("synced"),
        "patched_item_id_prefix": review_item_id[:8],
        "patched_status": patch.json().get("item", {}).get("review_status"),
        "prior_update_count": len(prior.get("items") or []),
        "progress_slot_count": len(progress.get("items") or []),
    }
    (EVIDENCE / "real-db-proof-summary.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
