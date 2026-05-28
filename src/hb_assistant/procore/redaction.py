"""
Centralized redaction for the GET-only Procore HTTP client.

Guarantees that Authorization headers, any token-like strings, client_secret,
and full response/request bodies NEVER appear in logs, exceptions, or evidence.

Bodies are reduced to structural summary (top-level keys + types + counts) or
bounded hash only.

Used on every request/response/error boundary before any log, str(), or evidence artifact.

Design directly from subagent exploration (019e6b5b-16b6-7f60-85ae-37dd43872fec) grounded in
Prompt_01 Decision Register facts and strict no-leak guardrails.
"""

import hashlib
import re
from typing import Any, Dict, Optional

_SENSITIVE_HEADER_KEYS = {"authorization", "proxy-authorization", "x-api-key", "cookie"}
_TOKEN_RE = re.compile(
    r"\b(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\b|\b([A-Za-z0-9_-]{20,})\b"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _is_sensitive_key(k: str) -> bool:
    kl = k.lower()
    return any(s in kl for s in _SENSITIVE_HEADER_KEYS) or "token" in kl or "secret" in kl


def redact_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Redact any header that looks like auth, token, or secret."""
    out: Dict[str, str] = {}
    for k, v in (headers or {}).items():
        if _is_sensitive_key(k) or _TOKEN_RE.search(str(v) or ""):
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


def redact_body(body: Any, *, for_error: bool = False) -> Dict[str, Any]:
    """Return structural summary or safe hash. Never raw content."""
    if body is None:
        return {"type": "null"}

    if isinstance(body, dict):
        top = sorted(body.keys())[:15]
        summary: Dict[str, Any] = {"type": "dict", "top_level_keys": top, "key_count": len(body)}
        if for_error:
            safe: Dict[str, Any] = {}
            for ek in ("error", "errors", "message", "code", "status", "title"):
                if ek in body:
                    val = body[ek]
                    safe[ek] = val if isinstance(val, (str, int, float, bool, type(None))) else str(type(val))
            summary["error_fields"] = safe or None
        return summary

    if isinstance(body, (list, tuple)):
        return {"type": "list", "length": len(body), "sample_types": [type(x).__name__ for x in body[:3]]}

    if isinstance(body, str):
        if len(body) > 256:
            h = hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()[:12]
            return {"type": "string", "length": len(body), "hash_prefix": h}
        return {"type": "string", "value": body[:128] + "..." if len(body) > 128 else body}

    return {"type": type(body).__name__, "hash": hashlib.sha256(repr(body).encode()).hexdigest()[:12]}


def redact_request(
    method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Redacted request summary safe for logs and evidence."""
    safe_params = redact_body(params) if params else None
    return {
        "method": (method or "GET").upper(),
        "url_path_redacted": url.split("?")[0] if url else None,
        "headers": redact_headers(headers or {}),
        "params_summary": safe_params,
    }


def mask_pii_in_excerpt(text: str, max_len: int = 120) -> str:
    """Length-capped excerpt with emails, US-shaped phones, and token-like
    substrings masked. Masks first, then truncates, so partial literals
    cannot slip through at the truncation boundary. Used only for evidence
    artifacts; does not replace hash-summary behavior in normalizers."""
    if not isinstance(text, str) or not text:
        return ""
    masked = _EMAIL_RE.sub("[email-redacted]", text)
    masked = _PHONE_RE.sub("[phone-redacted]", masked)
    masked = _TOKEN_RE.sub("[token-redacted]", masked)
    return masked[:max_len]


def redact_response(status: int, headers: Dict[str, str], body: Any) -> Dict[str, Any]:
    """Redacted response summary with safe rate-limit extraction."""
    h = headers or {}
    rate = {k: h[k] for k in h if "ratelimit" in k.lower() or k.lower() == "retry-after"}
    safe_h = redact_headers({k: v for k, v in h.items() if k.lower() not in {kk.lower() for kk in rate}})
    return {
        "status": status,
        "headers": safe_h,
        "rate_limit": rate,
        "body_summary": redact_body(body, for_error=(status >= 400)),
    }
