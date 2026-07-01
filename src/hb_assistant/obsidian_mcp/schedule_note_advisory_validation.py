"""Validation for optional local LLM advisory sections on schedule notes (Phase 19)."""

from __future__ import annotations

import re
from typing import Any

_REQUIRED_HEADINGS = ("### Summary", "### PM Attention", "### Follow-Up Questions", "### Limits / Uncertainty")

_FORBIDDEN_LANGUAGE = re.compile(
    r"\b(claim|liability|responsibility|fault|compensable|entitlement|delay damages|caused|causation|forensic|proved|liable|entitled)\b",
    re.IGNORECASE,
)

_FORBIDDEN_ID = re.compile(
    r"\b([A-Za-z]:\\|/Users/|/Volumes/|schedule_version_key|import_id|package_id|cpm_run_id|procore_project_id)\b",
    re.IGNORECASE,
)


def validate_schedule_advisory(advisory_markdown: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    text = (advisory_markdown or "").strip()
    violations: list[str] = []
    if not text:
        violations.append("empty_advisory")
    for heading in _REQUIRED_HEADINGS:
        if heading not in text:
            violations.append(f"missing_heading:{heading}")
    if _FORBIDDEN_LANGUAGE.search(text):
        violations.append("forbidden_language")
    if _FORBIDDEN_ID.search(text):
        violations.append("forbidden_id_or_path")
    for status_key in (
        "analytics_trust_status",
        "identity_trust_status",
        "cpm_trust_status",
        "quality_trust_status",
    ):
        status = str(payload.get(status_key) or "")
        if status and status not in {"mixed", "unavailable"}:
            contradiction = re.search(
                rf"\b(not\s+{re.escape(status)}|contrary to\s+{re.escape(status)})\b",
                text,
                re.IGNORECASE,
            )
            if contradiction:
                violations.append(f"trust_contradiction:{status_key}")
    return {"passed": not violations, "violations": violations}
