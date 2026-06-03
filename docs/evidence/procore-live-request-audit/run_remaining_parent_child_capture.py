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
REQUESTS_PATH = OUT_DIR / f"{STAMP}-remaining-parent-child-requests.jsonl"
RECEIPTS_PATH = OUT_DIR / f"{STAMP}-remaining-parent-child-receipts.json"
SUMMARY_PATH = OUT_DIR / f"{STAMP}-remaining-parent-child-summary.json"

# Activities were tested separately with schedule 9517. Unverified rows are listed in summary only.
DEFAULT_ENDPOINTS = [
    "rfi-responses",
    "submittal-responses",
    "submittal-packages",
    "meeting-detail",
    "prime-contract-line-items",
    "prime-contract-attachments",
    "prime-change-order-line-items",
    "commitment-line-items",
    "commitment-attachments",
    "commitment-compliance",
    "commitment-change-order-line-items",
    "purchase-order-line-items",
    "subcontractor-invoice-contract-items",
    "subcontractor-invoice-contract-detail-items",
    "subcontractor-invoice-change-order-items",
    "rfq-responses",
    "rfq-quotes",
    "change-event-comments",
    "budget-detail-columns",
    "budget-detail-rows",
]
ENDPOINTS = [
    endpoint.strip()
    for endpoint in os.environ.get("HB_PROCORE_CAPTURE_ENDPOINTS", ",".join(DEFAULT_ENDPOINTS)).split(",")
    if endpoint.strip()
]
MAX_CHILD_REQUESTS = int(os.environ.get("HB_PROCORE_CAPTURE_MAX_CHILD_REQUESTS", "100000"))
CHILD_REQUEST_DELAY_SECONDS = float(os.environ.get("HB_PROCORE_CAPTURE_CHILD_DELAY_SECONDS", "0"))
STOP_ON_RATE_LIMIT = os.environ.get("HB_PROCORE_CAPTURE_STOP_ON_RATE_LIMIT", "1") not in {
    "0",
    "false",
    "False",
}
UNVERIFIED_PARENT_CHILD_ENDPOINTS = [
    "purchase-order-detail-line-items",
    "budget-details",
    "budget-change-line-items",
]
SAFE_HEADER_NAMES = {"Accept", "Content-Type", "Procore-Company-Id", "User-Agent", "X-Correlation-ID"}
SAFE_RESPONSE_HEADERS = {"Link", "Retry-After"}
SAFE_RESPONSE_HEADER_PREFIXES = ("X-RateLimit", "X-Request", "X-Correlation")

current_endpoint: Optional[str] = None
request_log: list[dict[str, Any]] = []
live_client = ProcoreHTTPClient(
    environment="production",
    transport=None,
    access_token_provider=default_procore_token_provider(),
    live_enabled=True,
)


def _safe_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        k: v for k, v in headers.items()
        if k in SAFE_RESPONSE_HEADERS or any(k.startswith(p) for p in SAFE_RESPONSE_HEADER_PREFIXES)
    }


def capture_transport(method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Any:
    entry = {
        "seq": len(request_log) + 1,
        "endpoint": current_endpoint,
        "method": method,
        "url": url,
        "params": dict(params or {}),
        "request_headers_redacted": {k: v for k, v in dict(headers or {}).items() if k in SAFE_HEADER_NAMES},
        "auth_header_present": bool((headers or {}).get("Authorization")),
        "authorization_redacted": True,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = live_client._default_live_transport(method, url, headers, params)
        entry["status_code"] = getattr(resp, "status_code", None)
        entry["response_headers_redacted"] = _safe_response_headers(dict(getattr(resp, "headers", {}) or {}))
        request_log.append(entry)
        REQUESTS_PATH.open("a", encoding="utf-8").write(json.dumps(entry, sort_keys=True) + "\n")
        return resp
    except Exception as exc:
        entry["transport_exception"] = type(exc).__name__
        request_log.append(entry)
        REQUESTS_PATH.open("a", encoding="utf-8").write(json.dumps(entry, sort_keys=True) + "\n")
        raise


def run_one(endpoint: str) -> dict[str, Any]:
    global current_endpoint
    current_endpoint = endpoint
    return run_live_sync(
        project_key="tropical",
        endpoint=endpoint,
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=1000,
        max_items=100000,
        max_child_requests=MAX_CHILD_REQUESTS,
        child_request_delay_seconds=CHILD_REQUEST_DELAY_SECONDS,
        mode_hint="live_apply",
        transport=capture_transport,
        evidence_path=str(REQUESTS_PATH),
    )


def main() -> None:
    os.environ["HB_PROCORE_LIVE"] = "1"
    receipts: dict[str, Any] = {}
    for endpoint in ENDPOINTS:
        try:
            receipts[endpoint] = run_one(endpoint)
        except Exception as exc:  # defensive; run_live_sync should normalize most failures
            receipts[endpoint] = {"state": "runner_exception", "error_type": type(exc).__name__}
        reason_codes = receipts.get(endpoint, {}).get("reason_codes") or []
        if STOP_ON_RATE_LIMIT and any("rate_limited" in str(reason) for reason in reason_codes):
            break
    RECEIPTS_PATH.write_text(json.dumps(receipts, indent=2, sort_keys=True), encoding="utf-8")

    request_counts: dict[str, int] = {}
    statuses: dict[str, dict[str, int]] = {}
    for req in request_log:
        endpoint = str(req.get("endpoint"))
        request_counts[endpoint] = request_counts.get(endpoint, 0) + 1
        status = str(req.get("status_code") or req.get("transport_exception") or "unknown")
        statuses.setdefault(endpoint, {})[status] = statuses.setdefault(endpoint, {}).get(status, 0) + 1

    summary = {
        "stamp": STAMP,
        "requests_path": str(REQUESTS_PATH),
        "receipts_path": str(RECEIPTS_PATH),
        "request_count_observed": len(request_log),
        "max_child_requests": MAX_CHILD_REQUESTS,
        "child_request_delay_seconds": CHILD_REQUEST_DELAY_SECONDS,
        "stop_on_rate_limit": STOP_ON_RATE_LIMIT,
        "unverified_not_run": UNVERIFIED_PARENT_CHILD_ENDPOINTS,
        "endpoints": {
            endpoint: {
                "request_count_observed": request_counts.get(endpoint, 0),
                "statuses_observed": statuses.get(endpoint, {}),
                "state": receipts.get(endpoint, {}).get("state"),
                "status": receipts.get(endpoint, {}).get("status"),
                "request_count_receipt": receipts.get(endpoint, {}).get("request_count"),
                "retrieved_count": receipts.get(endpoint, {}).get("retrieved_count"),
                "sqlite_upserted_count": receipts.get(endpoint, {}).get("sqlite_upserted_count"),
                "retry_count": receipts.get(endpoint, {}).get("retry_count"),
                "last_retry_after": receipts.get(endpoint, {}).get("last_retry_after"),
                "reason_codes": receipts.get(endpoint, {}).get("reason_codes"),
                "redacted_errors": receipts.get(endpoint, {}).get("redacted_errors"),
                "n1_fanout": receipts.get(endpoint, {}).get("n1_fanout"),
            }
            for endpoint in ENDPOINTS
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
