from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hb_assistant.procore.http_client import ProcoreHTTPClient
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.procore.token_provider import default_procore_token_provider

OUT_DIR = Path("docs/evidence/procore-live-request-audit")
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
REQUESTS_PATH = OUT_DIR / f"{STAMP}-schedule-activity-requests.jsonl"
RECEIPTS_PATH = OUT_DIR / f"{STAMP}-schedule-activity-receipts.json"
SUMMARY_PATH = OUT_DIR / f"{STAMP}-schedule-activity-summary.json"

SAFE_HEADER_NAMES = {
    "Accept",
    "Content-Type",
    "Procore-Company-Id",
    "User-Agent",
    "X-Correlation-ID",
}
SAFE_RESPONSE_HEADER_PREFIXES = ("X-RateLimit", "X-Request", "X-Correlation")
SAFE_RESPONSE_HEADERS = {"Link", "Retry-After"}

request_log: list[dict[str, Any]] = []
live_client = ProcoreHTTPClient(
    environment="production",
    transport=None,
    access_token_provider=default_procore_token_provider(),
    live_enabled=True,
)


def _safe_request_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in headers.items() if k in SAFE_HEADER_NAMES}


def _safe_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        if k in SAFE_RESPONSE_HEADERS or any(
            k.startswith(prefix) for prefix in SAFE_RESPONSE_HEADER_PREFIXES
        ):
            out[k] = v
    return out


def capture_transport(
    method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None
) -> Any:
    entry: dict[str, Any] = {
        "seq": len(request_log) + 1,
        "method": method,
        "url": url,
        "params": dict(params or {}),
        "request_headers_redacted": _safe_request_headers(dict(headers or {})),
        "auth_header_present": bool((headers or {}).get("Authorization")),
        "authorization_redacted": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = live_client._default_live_transport(method, url, headers, params)
        entry["status_code"] = getattr(resp, "status_code", None)
        entry["response_headers_redacted"] = _safe_response_headers(
            dict(getattr(resp, "headers", {}) or {})
        )
        request_log.append(entry)
        with REQUESTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        return resp
    except Exception as exc:
        entry["transport_exception"] = type(exc).__name__
        request_log.append(entry)
        with REQUESTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        raise


def run(endpoint: str) -> dict[str, Any]:
    return run_live_sync(
        project_key="tropical",
        endpoint=endpoint,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1000,
        max_items=100000,
        max_child_requests=100000,
        mode_hint="live_apply",
        transport=capture_transport,
        evidence_path=str(REQUESTS_PATH),
    )


def main() -> None:
    os.environ["HB_PROCORE_LIVE"] = "1"
    receipts = {"schedules": run("schedules"), "activities": run("activities")}
    RECEIPTS_PATH.write_text(json.dumps(receipts, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "stamp": STAMP,
        "requests_path": str(REQUESTS_PATH),
        "receipts_path": str(RECEIPTS_PATH),
        "request_count_observed": len(request_log),
        "requests_by_endpoint_hint": {
            "schedules_urls": [
                r["url"] for r in request_log if r["url"].rstrip("/").endswith("/schedules")
            ],
            "activity_urls": [r["url"] for r in request_log if "/activities" in r["url"]],
        },
        "receipts": {
            k: {
                "state": v.get("state"),
                "status": v.get("status"),
                "request_count": v.get("request_count"),
                "retrieved_count": v.get("retrieved_count"),
                "sqlite_upserted_count": v.get("sqlite_upserted_count"),
                "reason_codes": v.get("reason_codes"),
                "redacted_errors": v.get("redacted_errors"),
                "n1_fanout": v.get("n1_fanout"),
            }
            for k, v in receipts.items()
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
