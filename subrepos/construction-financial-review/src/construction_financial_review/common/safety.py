"""Deterministic safety scan for emitted artifacts.

Scans text for sensitive markers. The phone regex requires separators/word-boundaries so pure-digit
identifiers (cost_code_id, wbs_code_id, vendor_id) and md5-style entity keys do NOT false-positive.
"""
from __future__ import annotations

import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Iterable

SAFETY_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[ .\-])?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?!\d)"),
    "bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    "api_token": re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[_\-][A-Za-z0-9]{16,}\b"),
    "signed_url_sig": re.compile(r"[?&](?:X-Amz-Signature|Signature|sig|X-Goog-Signature|se|sig=)=", re.I),
    "private_blob_url": re.compile(
        r"https?://[^\s\"]*(?:blob\.core\.windows\.net|s3[.\-][^\s\"]*amazonaws\.com|"
        r"sharepoint\.com|1drv\.ms|graph\.microsoft\.com)", re.I),
    "pem": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "raw_body_field": re.compile(
        r"\"(?:description_summary_json|raw_body|payload|response_body|request_body)\"\s*:"),
}

# A finding in any of these categories fails validation.
FAIL_CATEGORIES = {"bearer", "api_token", "signed_url_sig", "private_blob_url", "pem", "raw_body_field"}


def scan_text(text: str) -> dict:
    """Return {category: match_count} for one text blob."""
    return {name: len(pat.findall(text)) for name, pat in SAFETY_PATTERNS.items()}


def safety_scan(files: Iterable[str | Path]) -> "OrderedDict":
    """Scan files; return a report dict with findings + pass/fail."""
    findings = {k: 0 for k in SAFETY_PATTERNS}
    files = list(files)
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        for name, count in scan_text(text).items():
            findings[name] += count
    passed = all(findings[c] == 0 for c in FAIL_CATEGORIES)
    return OrderedDict([
        ("scanned_file_count", len(files)),
        ("findings", OrderedDict((k, findings[k]) for k in sorted(findings))),
        ("fail_categories", sorted(FAIL_CATEGORIES)),
        ("passed", passed),
    ])
