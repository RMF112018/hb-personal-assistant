"""Deterministic text analysis for Obsidian MCP summarization/extraction.

Pure, offline, regex/heuristic analysis of note and email text — the always-available
fallback beneath the optional local-LLM path (see ``llm.py``) and the engine behind the
construction/PM extraction tools. Reuses the project-detection primitives already proven
in the construction email pipeline; entity/project detection is lazy-imported so importing
this module stays cheap.
"""

from __future__ import annotations

import re

from . import mdutil

_CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+(.+?)\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?!\[[ xX]\])(.+?)\s*$", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_ACTION_RE = re.compile(
    r"\b(please|can you|could you|would you|need (?:you|to)|action required|"
    r"action item|to-?do|follow[- ]?up|let me know|send me|provide|confirm|"
    r"by (?:eod|cob|end of day|today|tomorrow)|due|deadline|no later than|asap)\b",
    re.IGNORECASE,
)
_DECISION_RE = re.compile(
    r"\b(decided|decision|approved|agreed|we will|will proceed|going with|"
    r"chosen|selected|resolved to|sign[- ]?off)\b",
    re.IGNORECASE,
)

_MAX_KEY_POINTS = 8
_MAX_ITEMS = 20
_MAX_ENTITIES = 25
_MIN_LINE = 4


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(flat) if len(s.strip()) >= _MIN_LINE]


def _dedup(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen and len(item) >= _MIN_LINE:
            seen.add(key)
            out.append(item)
        if len(out) >= limit:
            break
    return out


def lead_summary(body: str, *, max_chars: int) -> str:
    """Deterministic summary: the first substantive prose, headings stripped."""
    prose = [ln for ln in _lines(body) if not ln.startswith(("#", "-", "*", ">", "|"))]
    summary = " ".join(prose) if prose else " ".join(_lines(body))
    summary = " ".join(summary.split())
    return summary[:max_chars]


def key_points(body: str) -> list[str]:
    points = [m.group(1).strip() for m in _HEADING_RE.finditer(body)]
    points += [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
    return _dedup(points, _MAX_KEY_POINTS)


def action_items(body: str) -> list[str]:
    items = [m.group(1).strip() for m in _CHECKBOX_RE.finditer(body)]
    for line in _lines(body):
        if _ACTION_RE.search(line):
            items.append(line.lstrip("-*> ").strip())
    for sentence in _sentences(body):
        if _ACTION_RE.search(sentence):
            items.append(sentence)
    return _dedup(items, _MAX_ITEMS)


def decisions(body: str) -> list[str]:
    found = [line.lstrip("-*> ").strip() for line in _lines(body) if _DECISION_RE.search(line)]
    found += [s for s in _sentences(body) if _DECISION_RE.search(s)]
    return _dedup(found, _MAX_ITEMS)


def entities(text: str) -> list[str]:
    """Detect project numbers, resolved project aliases, and capitalized name tokens.

    Reuses the construction project-detection primitives when available; any import
    or seed-config failure degrades to a plain capitalized-token heuristic so
    summarization never fails on entity detection.
    """
    fallback = _dedup(re.findall(r"\b[A-Z][A-Za-z]{2,}\b", text), _MAX_ENTITIES)
    try:
        from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE
        from hb_assistant.construction.second_brain.local_ai.project_aliases import (
            candidate_tokens,
            resolve_project,
        )

        found: list[str] = list(HB_PROJECT_NUMBER_RE.findall(text))
        project = resolve_project(text)
        if project:
            found.append(project)
        found += candidate_tokens(text)
    except Exception:  # noqa: BLE001 - construction helpers/seed are optional at runtime
        return fallback
    return _dedup(found, _MAX_ENTITIES)


def analyze(
    rel: str,
    text: str,
    *,
    max_chars: int,
    include_action_items: bool = True,
    include_decisions: bool = True,
    include_entities: bool = True,
) -> dict[str, object]:
    """Full deterministic analysis bundle for one note/email body."""
    fm, body = mdutil.split_frontmatter(text)
    result: dict[str, object] = {
        "title": mdutil.title_of(rel, text),
        "summary": lead_summary(body, max_chars=max_chars),
        "key_points": key_points(body),
        "suggested_tags": mdutil.normalized_tags(mdutil.extract_tags(body, fm)),
        "suggested_links": mdutil.extract_wikilinks(text),
    }
    result["action_items"] = action_items(body) if include_action_items else []
    result["decisions"] = decisions(body) if include_decisions else []
    result["entities"] = entities(text) if include_entities else []
    return result
