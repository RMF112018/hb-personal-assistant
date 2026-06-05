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
REQUESTS_PATH = OUT_DIR / f"{STAMP}-activity-parent-9517-requests.jsonl"
RECEIPT_PATH = OUT_DIR / f"{STAMP}-activity-parent-9517-receipt.json"
SUMMARY_PATH = OUT_DIR / f"{STAMP}-activity-parent-9517-summary.json"
SAFE_HEADER_NAMES = {
    "Accept",
    "Content-Type",
    "Procore-Company-Id",
    "User-Agent",
    "X-Correlation-ID",
}
SAFE_RESPONSE_HEADERS = {"Link", "Retry-After"}
SAFE_RESPONSE_HEADER_PREFIXES = ("X-RateLimit", "X-Request", "X-Correlation")
request_log: list[dict[str, Any]] = []
live_client = ProcoreHTTPClient(
    environment="production",
    transport=None,
    access_token_provider=default_procore_token_provider(),
    live_enabled=True,
)


def safe_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        k: v
        for k, v in headers.items()
        if k in SAFE_RESPONSE_HEADERS or any(k.startswith(p) for p in SAFE_RESPONSE_HEADER_PREFIXES)
    }


def capture_transport(
    method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None
) -> Any:
    entry = {
        "seq": len(request_log) + 1,
        "method": method,
        "url": url,
        "params": dict(params or {}),
        "request_headers_redacted": {
            k: v for k, v in dict(headers or {}).items() if k in SAFE_HEADER_NAMES
        },
        "auth_header_present": bool((headers or {}).get("Authorization")),
        "authorization_redacted": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = live_client._default_live_transport(method, url, headers, params)
        entry["status_code"] = getattr(resp, "status_code", None)
        entry["response_headers_redacted"] = safe_response_headers(
            dict(getattr(resp, "headers", {}) or {})
        )
        request_log.append(entry)
        REQUESTS_PATH.open("a", encoding="utf-8").write(json.dumps(entry, sort_keys=True) + "\n")
        return resp
    except Exception as exc:
        entry["transport_exception"] = type(exc).__name__
        request_log.append(entry)
        REQUESTS_PATH.open("a", encoding="utf-8").write(json.dumps(entry, sort_keys=True) + "\n")
        raise


def main() -> None:
    os.environ["HB_PROCORE_LIVE"] = "1"
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="activities",
        parent_id="9517",
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
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    summary = {
        "stamp": STAMP,
        "requests_path": str(REQUESTS_PATH),
        "receipt_path": str(RECEIPT_PATH),
        "request_count_observed": len(request_log),
        "request_urls": [r["url"] for r in request_log],
        "receipt": {
            "state": receipt.get("state"),
            "status": receipt.get("status"),
            "request_count": receipt.get("request_count"),
            "retrieved_count": receipt.get("retrieved_count"),
            "sqlite_upserted_count": receipt.get("sqlite_upserted_count"),
            "reason_codes": receipt.get("reason_codes"),
            "redacted_errors": receipt.get("redacted_errors"),
            "retry_count": receipt.get("retry_count"),
            "last_retry_after": receipt.get("last_retry_after"),
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
