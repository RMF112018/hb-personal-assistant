#!/usr/bin/env python3
"""Phase 10 real-DB API evidence capture against live uvicorn on :8000."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PROJECT = "tropical"
EVIDENCE = Path(__file__).resolve().parent
HEADERS = {"X-HB-UI-Role": "operator", "Content-Type": "application/json"}


def request(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers=HEADERS,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def save(name: str, payload: object) -> None:
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.name}")


def main() -> int:
    status, before = request("GET", f"/api/projects/{PROJECT}/schedule/baselines")
    if status != 200:
        print("baselines before failed", status, before, file=sys.stderr)
        return 1
    save("api-real-baselines-before.json", before)

    as_of = before.get("as_of_date", "2026-07-01")
    eligible = [
        v["schedule_version_key"]
        for v in before.get("available_versions", [])
        if v.get("eligible_baseline")
    ]
    if len(eligible) < 3:
        print("insufficient eligible baselines", eligible, file=sys.stderr)
        return 1

  # earliest, mid, immediately prior (by data date desc among eligible)
    by_date = sorted(
        [v for v in before["available_versions"] if v.get("eligible_baseline")],
        key=lambda v: v.get("schedule_data_date", ""),
    )
    current_contract = by_date[0]["schedule_version_key"]
    secondary = by_date[1]["schedule_version_key"] if len(by_date) > 2 else by_date[0]["schedule_version_key"]
    previous = by_date[-1]["schedule_version_key"]

    selections = {
        "current_contract_baseline": {"schedule_version_key": current_contract},
        "previous_progress_update_baseline": {"schedule_version_key": previous},
        "secondary_progress_update_baseline": {"schedule_version_key": secondary},
    }
    put_body = {"selections": selections, "as_of": as_of, "selected_by": "phase10-proof"}
    status, put_resp = request(
        "PUT",
        f"/api/projects/{PROJECT}/schedule/baselines",
        put_body,
    )
    save("api-real-baselines-put.json", {"request": put_body, "response_status": status, "response": put_resp})
    if status != 200:
        print("PUT baselines failed", status, put_resp, file=sys.stderr)
        return 1

    status, after = request("GET", f"/api/projects/{PROJECT}/schedule/baselines?as_of={as_of}")
    save("api-real-baselines-after.json", after)

    basis_cases = [
        ("api-real-controls-current-contract-baseline.json", "current_contract_baseline"),
        ("api-real-controls-previous-progress-update-baseline.json", "previous_progress_update_baseline"),
        ("api-real-controls-secondary-progress-update-baseline.json", "secondary_progress_update_baseline"),
    ]
    activity_id = None
    for fname, basis in basis_cases:
        st, payload = request(
            "GET",
            f"/api/projects/{PROJECT}/schedule/controls?comparison_basis={basis}&as_of={as_of}",
        )
        save(fname, {"status": st, "body": payload})
        if st == 200 and activity_id is None:
            for ctrl in payload.get("top_signals") or payload.get("controls") or []:
                activity_id = ctrl.get("activity_id")
                if activity_id:
                    break
                link = (ctrl.get("links") or {}).get("driver_detail")
                if link and "/drivers/" in link:
                    activity_id = link.split("/drivers/")[-1].split("?")[0]
                    break

    st, wb = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/review-items?comparison_basis=current_contract_baseline&as_of={as_of}",
    )
    save("api-real-workbench-current-contract-baseline.json", {"status": st, "body": wb})
    if activity_id is None and st == 200:
        for item in wb.get("items") or []:
            aid = item.get("activity_id")
            if aid:
                activity_id = aid
                break

    if activity_id:
        st, drv = request(
            "GET",
            f"/api/projects/{PROJECT}/schedule/drivers/{activity_id}/detail?comparison_basis=current_contract_baseline&as_of={as_of}",
        )
        save("api-real-driver-current-contract-baseline.json", {"status": st, "body": drv, "activity_id": activity_id})
    else:
        save(
            "api-real-driver-current-contract-baseline.json",
            {"status": None, "note": "no driver activity_id found in controls/workbench", "activity_id": None},
        )

    st, sync_rej = request(
        "POST",
        f"/api/projects/{PROJECT}/schedule/review-items?comparison_basis=current_contract_baseline&as_of={as_of}",
        {},
    )
    save("api-real-named-sync-rejected.json", {"status": st, "body": sync_rej})

    st, invalid = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/controls?comparison_basis=mystery_basis&as_of={as_of}",
    )
    save("api-real-invalid-controls-basis.json", {"status": st, "body": invalid})

    meta = {
        "project_key": PROJECT,
        "as_of": as_of,
        "selections": selections,
        "eligible_baseline_keys": eligible,
        "activity_id": activity_id,
    }
    save("api-real-proof-meta.json", meta)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
