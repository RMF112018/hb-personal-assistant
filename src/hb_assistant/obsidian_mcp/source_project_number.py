"""Project-number extraction and normalization for source index + structure map.

Deterministic, pure functions. Compact 7-digit forms are only promoted when
construction-project-like context is present (path segment, filename token, or
explicit project mapping) — never from bare invoice totals / phone fragments alone.
"""

from __future__ import annotations

import re
from typing import Any

# Full hyphenated: NN-NNN-NN
_FULL_HYPHEN = re.compile(r"\b(\d{2})-(\d{3})-(\d{2})\b")
# Partial: NN-NNN
_PARTIAL_HYPHEN = re.compile(r"\b(\d{2})-(\d{3})\b")
# Spaced / underscored / dotted full forms
_FULL_SEP = re.compile(r"\b(\d{2})[\s_.](\d{3})[\s_.](\d{2})\b")
_PARTIAL_SEP = re.compile(r"\b(\d{2})[\s_.](\d{3})\b")
# Compact 7 digits (candidate only)
_COMPACT7 = re.compile(r"(?<!\d)(\d{7})(?!\d)")


def canonical_full(yy: str, mid: str, suffix: str) -> str:
    return f"{yy}-{mid}-{suffix}"


def compact_digits(number: str | None) -> str | None:
    if not number:
        return None
    digits = re.sub(r"\D", "", number)
    return digits or None


def format_from_digits(digits: str) -> str | None:
    """Format 7 digits as NN-NNN-NN; 5 digits as NN-NNN (partial)."""
    d = re.sub(r"\D", "", digits or "")
    if len(d) == 7:
        return canonical_full(d[0:2], d[2:5], d[5:7])
    if len(d) == 5:
        return f"{d[0:2]}-{d[2:5]}"
    return None


def is_partial_project_number(number: str | None) -> bool:
    if not number:
        return False
    return bool(_PARTIAL_HYPHEN.fullmatch(number.strip())) and not bool(
        _FULL_HYPHEN.fullmatch(number.strip())
    )


def normalize_project_number(
    text: str,
    *,
    allow_compact: bool = False,
    context: str | None = None,
) -> tuple[str | None, float, str]:
    """Return (canonical_number, confidence, match_form).

    ``allow_compact`` / path-like ``context`` gates compact 7-digit promotion so bare
    numeric bodies (invoices, phones) do not become project numbers.
    """
    raw = str(text or "")
    if not raw.strip():
        return None, 0.0, "none"

    m = _FULL_HYPHEN.search(raw)
    if m:
        return canonical_full(m.group(1), m.group(2), m.group(3)), 0.95, "hyphen_full"

    m = _FULL_SEP.search(raw)
    if m:
        return canonical_full(m.group(1), m.group(2), m.group(3)), 0.9, "sep_full"

    m = _PARTIAL_HYPHEN.search(raw)
    if m and not _FULL_HYPHEN.search(raw):
        # Partial is weak evidence (below 0.5 supporting threshold when inherited).
        return f"{m.group(1)}-{m.group(2)}", 0.35, "hyphen_partial"

    m = _PARTIAL_SEP.search(raw)
    if m and not _FULL_SEP.search(raw):
        return f"{m.group(1)}-{m.group(2)}", 0.35, "sep_partial"

    # Compact only with explicit permission or path/filename-like context.
    ctx = (context or "").lower()
    path_like = any(tok in ctx for tok in ("/", "\\", "project", "rel_path", "filename", "folder"))
    if allow_compact or path_like:
        m = _COMPACT7.search(raw)
        if m:
            formatted = format_from_digits(m.group(1))
            if formatted and len(formatted) == 9:  # NN-NNN-NN
                return formatted, 0.85, "compact7"

    return None, 0.0, "none"


def extract_project_numbers_from_path(rel_path: str) -> list[str]:
    """All project numbers found in a root-relative path (full preferred)."""
    found: list[str] = []
    for part in str(rel_path or "").replace("\\", "/").split("/"):
        num, conf, _ = normalize_project_number(part, allow_compact=True, context="path/" + part)
        if num and conf >= 0.35 and num not in found:
            found.append(num)
    return found


def query_project_candidates(query: str) -> list[str]:
    """Project numbers to try for a user query (full forms first).

    Compact digits in a short query (e.g. just ``2343501``) are allowed because the
    entire query is the search term, not free body text.
    """
    q = str(query or "").strip()
    if not q:
        return []
    allow_compact = bool(re.fullmatch(r"[\d\s_.\-]{5,12}", q))
    num, conf, _ = normalize_project_number(q, allow_compact=allow_compact, context="query")
    out: list[str] = []
    if num and conf >= 0.35:
        out.append(num)
    # Also try full-hyphen extraction without compact
    num2, conf2, _ = normalize_project_number(q, allow_compact=False)
    if num2 and conf2 >= 0.35 and num2 not in out:
        out.append(num2)
    return out


def path_has_project(rel_path: str, project_number: str) -> bool:
    """True when the path contains the project number in any equivalent form."""
    digits = compact_digits(project_number)
    if not digits:
        return False
    path = str(rel_path or "")
    path_digits = re.sub(r"\D", "", path)
    if digits in path_digits:
        # Prefer path segment style matches over accidental digit runs in long names
        for form in (
            project_number,
            project_number.replace("-", " "),
            project_number.replace("-", "_"),
            project_number.replace("-", "."),
            digits,
        ):
            if form and form.lower() in path.lower():
                return True
        # Digits contiguous in a path segment
        for part in path.replace("\\", "/").split("/"):
            if compact_digits(part) == digits:
                return True
    return False


def filename_has_project(rel_path: str, project_number: str) -> bool:
    name = str(rel_path or "").replace("\\", "/").rsplit("/", 1)[-1]
    return path_has_project(name, project_number)


def false_positive_compact_body_ok(text: str) -> bool:
    """Return True when compact digits in body text must NOT be treated as project numbers."""
    # Used by tests / callers: invoice-like free text without path context.
    num, conf, form = normalize_project_number(text, allow_compact=False, context="body")
    return num is None or form != "compact7"


def match_explanation_for_row(
    row: dict[str, Any],
    *,
    query: str,
    project_numbers: list[str],
) -> dict[str, Any]:
    """Build a compact, path-safe match explanation for one search hit."""
    rel = str(row.get("rel_path") or "")
    snippet = str(row.get("snippet") or "")
    ext = str(row.get("file_ext") or row.get("extension") or "").lower().lstrip(".")
    factors: list[str] = []
    matched: list[str] = []
    primary = "fts_content_match"
    read_status = "live_readable"
    if ext in {"xer", "mpp", "pln"} or str(row.get("extraction_status") or "") == "unsupported":
        read_status = "unsupported_metadata_only"

    for pn in project_numbers:
        if path_has_project(rel, pn):
            if filename_has_project(rel, pn):
                factors.append("project_number_filename")
                primary = "exact_project_number_filename_match"
            else:
                factors.append("project_number_path")
                primary = "exact_project_number_path_match"
            matched.append(pn)
            break
        if pn and pn in snippet:
            factors.append("project_number_content")
            if primary == "fts_content_match":
                primary = "exact_project_number_content_match"
            matched.append(pn)

    # Generic query tokens in path/filename
    tokens = [t for t in re.split(r"\s+", query.strip().lower()) if len(t) >= 3]
    for tok in tokens[:6]:
        if tok in rel.lower():
            factors.append("path")
            if "filename" not in factors and tok in rel.replace("\\", "/").rsplit("/", 1)[-1].lower():
                factors.append("filename")
                if primary == "fts_content_match":
                    primary = "filename_match"
            matched.append(tok)
            break

    if not factors:
        factors.append("content")
    # Bound
    matched = matched[:8]
    factors = factors[:8]
    return {
        "primary_reason": primary,
        "matched_terms": matched,
        "rank_factors": factors,
        "read_status": read_status,
    }


def rank_boost(row: dict[str, Any], *, query: str, project_numbers: list[str]) -> float:
    """Higher is better. Added to inverted BM25 (lower BM25 is better) via composite sort."""
    boost = 0.0
    rel = str(row.get("rel_path") or "")
    expl = match_explanation_for_row(row, query=query, project_numbers=project_numbers)
    reason = expl["primary_reason"]
    if reason == "exact_project_number_path_match":
        boost += 1000.0
    elif reason == "exact_project_number_filename_match":
        boost += 900.0
    elif reason == "exact_project_number_content_match":
        boost += 400.0
    elif reason == "filename_match":
        boost += 200.0
    if "path" in expl["rank_factors"]:
        boost += 50.0
    # Prefer schedules/pdf slightly when query mentions schedule/billing
    q = query.lower()
    ext = str(row.get("file_ext") or "").lower()
    if "schedule" in q and ext in {"pdf", "xer", "xlsx", "mpp"}:
        boost += 30.0
    if any(w in q for w in ("billing", "invoice", "pay app", "financial")) and ext == "pdf":
        boost += 25.0
    # Unsupported but path-relevant still ranks high via project boosts
    if expl["read_status"] == "unsupported_metadata_only" and boost >= 400:
        boost += 10.0
    # Slight recency would need mtime; leave 0 when absent
    return boost
