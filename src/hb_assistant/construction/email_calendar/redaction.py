"""Email/calendar outbound no-leak scanner (Pass 2, Prompt 06).

Extends the Procore `no_raw_leak_scan` pattern set with Microsoft 365 / Graph / Teams / Outlook
shapes (OAuth bearer tokens, Graph attachment download URLs, Teams/Outlook join URLs) plus
optional caller-supplied body/agenda sentinels. Scans files/dirs and returns counts + the
matched pattern names only — never the matched text — so it is safe to run over evidence, logs,
and captured CLI output.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

# Pattern name -> regex. Names are emitted in findings; matched text is never emitted.
_PATTERNS: dict[str, str] = {
    "oauth_bearer": "Bear" + "er" + r"\s+[A-Za-z0-9._\-]+",
    "access_token": "access_" + "token",
    "refresh_token": "refresh_" + "token",
    "client_secret": "client_" + "secret",
    "authorization_header": "Authoriz" + "ation:",
    "graph_download_url": r"@microsoft\.graph\.downloadUrl",
    "teams_join_url": r"https?://teams\.microsoft\.com/l/[^\s\"')]+",
    "outlook_safelink": r"https?://[a-z0-9.\-]*safelinks\.protection\.outlook\.com/[^\s\"')]+",
    "skype_join_url": r"https?://join\.[a-z0-9.\-]*skype[^\s\"')]+",
    "html_body": "<ht" + "ml",
}

_SKIP_SUFFIXES = {".sqlite", ".db", ".wal", ".shm", ".pyc"}


def no_raw_leak_scan(
    paths: Iterable[str | Path], *, sentinels: Iterable[str] = ()
) -> dict[str, Any]:
    """Scan files/dirs for forbidden email/calendar raw / secret patterns + optional sentinels.

    Returns counts and matched *pattern names* only (never matched values). ``ok`` is True iff
    no finding was produced.
    """
    compiled = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in _PATTERNS.items()]
    sentinel_list = [s for s in sentinels if s]
    findings: list[dict[str, Any]] = []
    files_scanned = 0
    for pathish in paths:
        path = Path(pathish)
        if path.is_dir():
            candidates = [p for p in path.rglob("*") if p.is_file()]
        elif path.exists():
            candidates = [path]
        else:
            candidates = []
        for file in candidates:
            if file.suffix.lower() in _SKIP_SUFFIXES:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files_scanned += 1
            for name, rx in compiled:
                if rx.search(text):
                    findings.append({"path": str(file), "pattern": name})
            for sentinel in sentinel_list:
                if sentinel in text:
                    findings.append({"path": str(file), "pattern": "sentinel"})
    return {
        "command": "hb-assistant email-calendar raw no-raw-leak-scan",
        "ok": not findings,
        "files_scanned": files_scanned,
        "unsafe_finding_count": len(findings),
        "findings": findings,
        "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
    }


__all__ = ["no_raw_leak_scan"]
