"""PM-safe artifact scanner for schedule evidence directories."""

from __future__ import annotations

import json
import re
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

CAUSATION_PHRASES = (
    "caused by",
    "delay caused",
    "responsible for",
    "liable",
    "entitlement",
)

STALE_MARKERS = ("available:false", "no_schedule", "blocked", "degraded")
READINESS_CLAIMS = ("ready", "production-ready", "fully operational", "all clear")

KEY_PATTERNS = (
    re.compile(r"schedule_version_key[\"']?\s*[:=]\s*[\"'][^\"']+"),
    re.compile(r"schedule_identity_key[\"']?\s*[:=]\s*[\"'][^\"']+"),
)
DB_PATH_PATTERN = re.compile(r"/[^\s\"']+\.sqlite\b")
TRACEBACK_PATTERN = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)
ABS_PATH_PATTERN = re.compile(r"/(?:Users|home|var)/[^\s\"']+")


def _default_allowlist() -> dict[str, Any]:
    try:
        if hasattr(importlib_resources, "files"):
            text = (
                importlib_resources.files("hb_assistant.construction.schedule_clean_db")
                / "artifact_scan_allowlist.json"
            ).read_text(encoding="utf-8")
        else:
            text = importlib_resources.read_text(
                "hb_assistant.construction.schedule_clean_db",
                "artifact_scan_allowlist.json",
                encoding="utf-8",
            )
        return json.loads(text)
    except Exception:
        return {"technical_allowlist": [], "allow_raw_db_paths": [], "allow_raw_schedule_keys": []}


def _load_allowlist(path: str | Path | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return _default_allowlist()


def _is_technical(name: str, allowlist: dict[str, Any]) -> bool:
    return name in set(allowlist.get("technical_allowlist", []))


def _scan_text(
    text: str,
    *,
    filename: str,
    allowlist: dict[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    technical = _is_technical(filename, allowlist)

    if not technical and not allowlist.get("allow_raw_schedule_keys"):
        for pattern in KEY_PATTERNS:
            if pattern.search(text):
                findings.append({"rule": "raw_schedule_key", "file": filename})

    if not technical and not allowlist.get("allow_raw_db_paths"):
        if DB_PATH_PATTERN.search(text):
            findings.append({"rule": "raw_db_path", "file": filename})

    if TRACEBACK_PATTERN.search(text):
        findings.append({"rule": "traceback", "file": filename})

    if not technical and ABS_PATH_PATTERN.search(text):
        findings.append({"rule": "absolute_source_path", "file": filename})

    lower = text.lower()
    for phrase in CAUSATION_PHRASES:
        if phrase in lower:
            findings.append({"rule": "causation_language", "file": filename, "detail": phrase})

    if any(marker in lower for marker in STALE_MARKERS) and any(
        claim in lower for claim in READINESS_CLAIMS
    ):
        findings.append({"rule": "stale_readiness_claim", "file": filename})

    return findings


def scan_evidence_dir(
    evidence_dir: str | Path,
    *,
    allowlist_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(evidence_dir).resolve()
    allowlist = _load_allowlist(allowlist_path)
    findings: list[dict[str, str]] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".md", ".txt"}:
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        name = path.name
        findings.extend(_scan_text(text, filename=name, allowlist=allowlist))
        for item in findings:
            if "path" not in item:
                item["path"] = rel

    return {
        "mode": "schedule_evidence_artifact_scan",
        "evidence_dir": str(root),
        "files_scanned": scanned,
        "finding_count": len(findings),
        "passed": len(findings) == 0,
        "findings": findings,
        "allowlist": allowlist,
    }


def render_scan_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Artifact scan",
        "",
        f"- passed: `{report.get('passed')}`",
        f"- files_scanned: `{report.get('files_scanned')}`",
        f"- findings: `{report.get('finding_count')}`",
        "",
    ]
    for item in report.get("findings", []):
        lines.append(f"- `{item.get('path')}` — {item.get('rule')} {item.get('detail', '')}".rstrip())
    lines.append("")
    return "\n".join(lines)
