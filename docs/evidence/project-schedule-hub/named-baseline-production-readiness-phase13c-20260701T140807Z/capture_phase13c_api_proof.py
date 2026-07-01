#!/usr/bin/env python3
"""Phase 13C read-only Tropical API evidence — export + driver disposition."""

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
AS_OF = "2026-07-03"

BASIS_LIST = [
    "prior_update",
    "current_contract_baseline",
    "previous_progress_update_baseline",
    "secondary_progress_update_baseline",
]


def _save(name: str, payload: object) -> None:
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {name}")


def _driver_extract(body: dict, basis: str) -> dict:
    return {
        "available": body.get("available"),
        "reason": body.get("reason"),
        "comparison_basis": body.get("comparison_basis") or basis,
        "baseline_context": body.get("baseline_context"),
        "comparison_schedule_version_key": body.get("comparison_schedule_version_key"),
        "activity": body.get("activity"),
        "review_status": body.get("review_status"),
        "review_scope": body.get("review_scope"),
        "disposition_source": body.get("disposition_source"),
        "disposition_basis": body.get("disposition_basis"),
        "disposition_schedule_version_key": body.get("disposition_schedule_version_key"),
        "review_item_id": body.get("review_item_id"),
    }


def _pick_activity(client: TestClient) -> str | None:
    for basis in BASIS_LIST:
        resp = client.get(
            f"/api/projects/{PROJECT}/schedule/controls",
            headers=VIEWER,
            params={"comparison_basis": basis, "as_of": AS_OF},
        )
        if resp.status_code != 200:
            continue
        for ctrl in resp.json().get("top_controls") or []:
            if ctrl.get("activity_id"):
                return str(ctrl["activity_id"])
    return None


def main() -> int:
    client = TestClient(create_app())

    export_blocks: list[str] = []
    driver_blocks: list[str] = []

    for basis in BASIS_LIST:
        label = f"===== {basis} ====="
        e_resp = client.get(
            f"/api/projects/{PROJECT}/schedule/export",
            headers=VIEWER,
            params={"format": "markdown", "comparison_basis": basis, "as_of": AS_OF},
        )
        export_blocks.append(label)
        if e_resp.status_code == 200:
            text = e_resp.text or ""
            export_blocks.append(
                json.dumps(
                    {
                        "http_status": 200,
                        "comparison_basis": basis,
                        "content_type": e_resp.headers.get("content-type"),
                        "body_length": len(text),
                        "body_excerpt": text[:2000],
                        "includes_slot_label": basis.replace("_", " ") in text.lower() or basis in text,
                        "includes_comparison_context": "Comparison Context" in text,
                        "includes_named_version_key": "tropical|" in text,
                        "silent_prior_update_fallback": (
                            basis != "prior_update" and "compared against prior update" in text.lower()
                        ),
                    },
                    indent=2,
                )
            )
        else:
            export_blocks.append(
                json.dumps(
                    {
                        "http_status": e_resp.status_code,
                        "comparison_basis": basis,
                        "detail": e_resp.json()
                        if e_resp.headers.get("content-type", "").startswith("application/json")
                        else e_resp.text,
                        "silent_prior_update_fallback": False,
                    },
                    indent=2,
                )
            )

    activity_id = _pick_activity(client)
    for candidate in ("FILTER-OUT-50", "FAB/DEL-10", activity_id):
        if not candidate:
            continue
        trial = client.get(
            f"/api/projects/{PROJECT}/schedule/drivers/detail",
            headers=VIEWER,
            params={"activity_id": candidate, "comparison_basis": "current_contract_baseline", "as_of": AS_OF},
        )
        if trial.status_code == 200 and trial.json().get("available") is not False:
            activity_id = candidate
            break
    if not activity_id:
        activity_id = "FILTER-OUT-50"

    _save("13c-driver-activity-selection.json", {"activity_id": activity_id, "as_of": AS_OF})

    for basis in BASIS_LIST:
        label = f"===== {basis} ====="
        resp = client.get(
            f"/api/projects/{PROJECT}/schedule/drivers/detail",
            headers=VIEWER,
            params={"activity_id": activity_id, "comparison_basis": basis, "as_of": AS_OF},
        )
        body = resp.json() if resp.status_code == 200 else {"status": resp.status_code, "detail": resp.text}
        driver_blocks.append(label)
        driver_blocks.append(json.dumps(_driver_extract(body, basis) if resp.status_code == 200 else body, indent=2))

    (EVIDENCE / "13c-api-proof-export.json").write_text("\n".join(export_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "13c-api-proof-driver-detail.json").write_text("\n".join(driver_blocks) + "\n", encoding="utf-8")
    print("activity_id:", activity_id)
    print("read-only GET only — no POST sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
