#!/usr/bin/env python3
"""Phase 13B read-only Tropical API evidence — consolidated manifest files, no POST sync."""

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
    "baseline",
    "current_contract_baseline",
    "previous_progress_update_baseline",
    "secondary_progress_update_baseline",
]


def _save(name: str, payload: object) -> None:
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {name}")


def _controls_extract(body: dict, basis: str) -> dict:
    top = body.get("top_controls") or []
    return {
        "available": body.get("available"),
        "reason": body.get("reason"),
        "comparison_basis": body.get("comparison_basis") or basis,
        "baseline_context": body.get("baseline_context"),
        "provenance": body.get("provenance"),
        "movement": (body.get("sections") or {}).get("movement"),
        "top_controls": [
            {
                "title": c.get("title"),
                "review_status": c.get("review_status"),
                "review_item_id": c.get("review_item_id"),
                "source_metric_key": c.get("source_metric_key"),
                "source_signal_type": c.get("source_signal_type"),
                "activity_id": c.get("activity_id"),
                "comparison_basis": c.get("comparison_basis"),
                "evidence": c.get("evidence"),
                "links": c.get("links"),
            }
            for c in top[:8]
        ],
    }


def _workbench_extract(body: dict, basis: str) -> dict:
    wb = body.get("workbench") or body
    items = wb.get("items") or body.get("items") or []
    return {
        "available": body.get("available"),
        "reason": body.get("reason"),
        "comparison_basis": wb.get("comparison_basis") or basis,
        "baseline_context": wb.get("baseline_context"),
        "review_scope": wb.get("review_scope"),
        "count": len(items),
        "items": [
            {
                "title": i.get("item_title"),
                "review_status": i.get("review_status"),
                "review_item_id": i.get("review_item_id"),
                "source_metric_key": i.get("source_metric_key"),
                "evidence_basis": (i.get("evidence") or {}).get("comparison_basis"),
                "evidence": i.get("evidence"),
                "activity_id": i.get("source_activity_id"),
                "cue_summary": i.get("cue_summary"),
            }
            for i in items[:8]
        ],
    }


def _driver_extract(body: dict, basis: str) -> dict:
    return {
        "available": body.get("available"),
        "reason": body.get("reason"),
        "comparison_basis": body.get("comparison_basis") or basis,
        "baseline_context": body.get("baseline_context"),
        "comparison_schedule_version_key": body.get("comparison_schedule_version_key"),
        "activity": body.get("activity"),
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

    baselines = client.get(
        f"/api/projects/{PROJECT}/schedule/baselines",
        headers=VIEWER,
        params={"as_of": AS_OF},
    )
    _save("13b-api-baselines.json", {"status": baselines.status_code, "body": baselines.json()})

    controls_blocks: list[str] = []
    workbench_blocks: list[str] = []
    driver_blocks: list[str] = []
    drilldown_blocks: list[str] = []
    driver_drill_blocks: list[str] = []
    export_blocks: list[str] = []

    for basis in BASIS_LIST:
        label = f"===== {basis} ====="

        c_resp = client.get(
            f"/api/projects/{PROJECT}/schedule/controls",
            headers=VIEWER,
            params={"comparison_basis": basis, "as_of": AS_OF},
        )
        c_body = c_resp.json() if c_resp.status_code == 200 else {"status": c_resp.status_code, "detail": c_resp.text}
        controls_blocks.append(label)
        controls_blocks.append(json.dumps(_controls_extract(c_body, basis) if c_resp.status_code == 200 else c_body, indent=2))

        w_resp = client.get(
            f"/api/projects/{PROJECT}/schedule/review-items",
            headers=VIEWER,
            params={"comparison_basis": basis, "as_of": AS_OF},
        )
        w_body = w_resp.json() if w_resp.status_code == 200 else {"status": w_resp.status_code, "detail": w_resp.text}
        workbench_blocks.append(label)
        workbench_blocks.append(json.dumps(_workbench_extract(w_body, basis) if w_resp.status_code == 200 else w_body, indent=2))

        d_resp = client.get(
            f"/api/projects/{PROJECT}/schedule/drilldowns",
            headers=VIEWER,
            params={"type": "remaining_later", "comparison_basis": basis, "as_of": AS_OF},
        )
        d_body = d_resp.json() if d_resp.status_code == 200 else {"status": d_resp.status_code, "detail": d_resp.text}
        drilldown_blocks.append(label)
        if d_resp.status_code == 200:
            drilldown_blocks.append(
                json.dumps(
                    {
                        "available": d_body.get("available"),
                        "reason": d_body.get("reason"),
                        "comparison_basis": d_body.get("comparison_basis") or basis,
                        "baseline_context": d_body.get("baseline_context"),
                        "comparison_schedule_version_key": d_body.get("comparison_schedule_version_key"),
                        "source_model": d_body.get("source_model"),
                        "keys": list(d_body.keys()),
                    },
                    indent=2,
                )
            )
        else:
            drilldown_blocks.append(json.dumps(d_body, indent=2))

        dd_resp = client.get(
            f"/api/projects/{PROJECT}/schedule/drivers",
            headers=VIEWER,
            params={"type": "finish_moved_later", "comparison_basis": basis, "as_of": AS_OF},
        )
        dd_body = dd_resp.json() if dd_resp.status_code == 200 else {"status": dd_resp.status_code, "detail": dd_resp.text}
        driver_drill_blocks.append(label)
        if dd_resp.status_code == 200:
            driver_drill_blocks.append(
                json.dumps(
                    {
                        "comparison_basis": dd_body.get("comparison_basis") or basis,
                        "baseline_context": dd_body.get("baseline_context"),
                        "keys": list(dd_body.keys()),
                        "row_count": len(dd_body.get("rows") or []),
                    },
                    indent=2,
                )
            )
        else:
            driver_drill_blocks.append(json.dumps(dd_body, indent=2))

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
                        "body_excerpt": text[:1500],
                        "includes_comparison_basis": basis in text,
                        "includes_baseline_context": "baseline" in text.lower(),
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
                        "detail": e_resp.json() if e_resp.headers.get("content-type", "").startswith("application/json") else e_resp.text,
                        "silent_prior_update_fallback": False,
                    },
                    indent=2,
                )
            )

    activity_id = _pick_activity(client)
    # Try FAB/DEL-10 first per spec, else picked activity
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

    _save("13b-driver-activity-selection.json", {"activity_id": activity_id, "as_of": AS_OF})

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

    (EVIDENCE / "06-api-proof-controls.json").write_text("\n".join(controls_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "07-api-proof-workbench.json").write_text("\n".join(workbench_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "08-api-proof-driver-detail.json").write_text("\n".join(driver_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "13b-api-proof-drilldowns.json").write_text("\n".join(drilldown_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "13b-api-proof-driver-drilldowns.json").write_text("\n".join(driver_drill_blocks) + "\n", encoding="utf-8")
    (EVIDENCE / "13b-api-proof-export.json").write_text("\n".join(export_blocks) + "\n", encoding="utf-8")

    print("activity_id:", activity_id)
    print("read-only GET only — no POST sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
