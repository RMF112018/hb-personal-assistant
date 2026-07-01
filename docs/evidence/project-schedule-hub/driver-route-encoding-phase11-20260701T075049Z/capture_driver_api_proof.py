#!/usr/bin/env python3
"""Phase 11 real-DB API driver route evidence (full captures written locally)."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PROJECT = "tropical"
EVIDENCE = Path(__file__).resolve().parent
LOCAL_RAW = EVIDENCE / "local-raw"
HEADERS = {"X-HB-UI-Role": "operator"}


def request(method: str, path: str, params: dict | None = None) -> tuple[int, object]:
    url = f"{BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=HEADERS, method=method)
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


def redact_driver_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    body = payload.get("body", payload)
    if not isinstance(body, dict):
        return {"status": payload.get("status"), "available": None}
    activity = body.get("activity") if isinstance(body.get("activity"), dict) else {}
    baseline = body.get("baseline_context") if isinstance(body.get("baseline_context"), dict) else {}
    return {
        "status": payload.get("status"),
        "available": body.get("available"),
        "comparison_basis": body.get("comparison_basis"),
        "activity_id": activity.get("activity_id"),
        "activity_name": activity.get("activity_name"),
        "baseline_context": {
            "slot_key": baseline.get("slot_key"),
            "slot_label": baseline.get("slot_label"),
            "schedule_version_key": baseline.get("schedule_version_key")
            or baseline.get("baseline_schedule_version_key"),
        },
        "sequence_cue_present": bool(body.get("sequence_cue")),
    }


def write_pair(name: str, payload: object) -> None:
    LOCAL_RAW.mkdir(exist_ok=True)
    full_path = LOCAL_RAW / f"{name}.full.json"
    full_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
    redacted = redact_driver_payload(payload)
    (EVIDENCE / f"{name}.json").write_text(json.dumps(redacted, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {name}.json sha256={digest[:16]}...")


def main() -> int:
    as_of = "2026-07-01"
    activity = "FAB/DEL-10"

    st, fab = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/drivers/detail",
        {
            "activity_id": activity,
            "comparison_basis": "current_contract_baseline",
            "as_of": as_of,
        },
    )
    write_pair("api-driver-query-fab-del-10", {"status": st, "body": fab})

    st, legacy = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/drivers/FM-PERMPOWER/detail",
        {"comparison_basis": "current_contract_baseline", "as_of": as_of},
    )
    write_pair("api-driver-legacy-nonslash", {"status": st, "body": legacy})

    st, invalid = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/drivers/detail",
        {"activity_id": activity, "comparison_basis": "mystery_basis", "as_of": as_of},
    )
    write_pair("api-driver-invalid-basis", {"status": st, "body": invalid})

    st, conflict = request(
        "GET",
        f"/api/projects/{PROJECT}/schedule/drivers/detail",
        {
            "activity_id": activity,
            "basis": "prior_update",
            "comparison_basis": "current_contract_baseline",
            "as_of": as_of,
        },
    )
    write_pair("api-driver-conflicting-basis", {"status": st, "body": conflict})

    print(json.dumps({"fab_status": st, "activity": activity}, indent=2))
    return 0 if fab.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
