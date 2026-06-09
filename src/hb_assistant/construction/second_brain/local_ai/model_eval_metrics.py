"""Local model evaluation — redaction scanning, usefulness rubric, and metric aggregation.

Pure, dependency-light helpers shared by :mod:`model_eval`. Nothing here makes a network call,
touches the DB, or persists anything. The redaction scanner returns only *category codes* for any
forbidden token it finds — never the matched substring — so eval evidence stays safe to commit.

The usefulness rubric is a deterministic, operator-focused heuristic (not a learned/academic
score): it rewards source-linked, section-covered, non-filler output and penalizes empty or
generic answers. It is intentionally simple — the harness must be *decisive* (recommend a profile),
not produce a research metric.
"""

from __future__ import annotations

import re
from typing import Any

# --- redaction scanner -----------------------------------------------------------------------
# Each rule maps a category code -> compiled pattern. We emit only the category code on a hit, so
# no matched secret/URL/email ever leaves the scanner. Patterns are deliberately broad (fail-loud).
_REDACTION_RULES: dict[str, re.Pattern[str]] = {
    "url": re.compile(r"https?://", re.IGNORECASE),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "join_link": re.compile(
        r"\b(?:teams\.microsoft\.com|zoom\.us|meet\.google\.com)\b", re.IGNORECASE
    ),
    "jwt_like": re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    "access_token": re.compile(r"\b(?:access|refresh|id)_token\b", re.IGNORECASE),
    "bearer": re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    "private_key": re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----"),
}


def scan_text_for_forbidden(text: str | None) -> list[str]:
    """Return the sorted category codes of any forbidden tokens found in ``text`` (never the match).

    An empty list means the text passed the redaction scan. ``None``/empty input passes trivially.
    """
    if not text:
        return []
    found = {category for category, pattern in _REDACTION_RULES.items() if pattern.search(text)}
    return sorted(found)


def redaction_passed(text: str | None) -> bool:
    """True when ``text`` contains none of the forbidden token categories."""
    return not scan_text_for_forbidden(text)


# --- usefulness rubric -----------------------------------------------------------------------
_FILLER_TOKENS: frozenset[str] = frozenset(
    {"tbd", "n/a", "various", "stuff", "things", "etc", "todo", "lorem ipsum", "placeholder"}
)


def _iter_strings(value: Any) -> list[str]:
    """Flatten nested dict/list output into the bag of human-facing strings it contains."""
    out: list[str] = []
    if isinstance(value, str):
        if value.strip():
            out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_iter_strings(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_iter_strings(v))
    return out


def _source_link_coverage(validated: dict[str, Any]) -> float:
    """Fraction of object-bullets that carry a non-empty ``source_id``/``source_refs`` link.

    Returns 1.0 when there are no object-bullets to link (vacuously source-safe).
    """
    linked = 0
    total = 0

    def _walk(node: Any) -> None:
        nonlocal linked, total
        if isinstance(node, dict):
            if "source_id" in node or "source_refs" in node:
                total += 1
                sid = node.get("source_id")
                refs = node.get("source_refs")
                if (isinstance(sid, str) and sid.strip()) or (isinstance(refs, list) and refs):
                    linked += 1
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(validated)
    return 1.0 if total == 0 else linked / total


def compute_usefulness(
    validated: dict[str, Any] | None,
    *,
    expected_sections: list[str] | None = None,
) -> float:
    """Deterministic 0..1 operator-usefulness score for a validated output dict.

    Weighted blend of: section coverage (0.4), source-link coverage (0.4), and non-filler
    content (0.2). An empty/None output scores 0.0.
    """
    if not validated:
        return 0.0
    strings = _iter_strings(validated)
    if not strings:
        return 0.0

    expected = expected_sections or list(validated.keys())
    covered = sum(1 for key in expected if validated.get(key))
    section_coverage = covered / len(expected) if expected else 0.0

    link_coverage = _source_link_coverage(validated)

    filler_hits = sum(
        1 for s in strings if s.strip().lower() in _FILLER_TOKENS or len(s.strip()) < 3
    )
    non_filler = max(0.0, 1.0 - (filler_hits / len(strings)))

    score = 0.4 * section_coverage + 0.4 * link_coverage + 0.2 * non_filler
    return round(min(1.0, max(0.0, score)), 4)


# --- aggregation -----------------------------------------------------------------------------
def aggregate_rate(values: list[bool]) -> float:
    """Fraction of True values (0.0 for an empty list)."""
    return round(sum(1 for v in values if v) / len(values), 4) if values else 0.0


def aggregate_mean(values: list[float]) -> float:
    """Arithmetic mean (0.0 for an empty list)."""
    return round(sum(values) / len(values), 4) if values else 0.0
