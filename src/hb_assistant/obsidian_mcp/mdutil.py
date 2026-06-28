"""Shared Markdown parsing helpers for the Obsidian MCP second-brain tools.

Pure, deterministic text helpers used by curation, summarization, and extraction.
No vault I/O, no config — just text in, structured data out.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\s*\n?", re.DOTALL)
TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9][\w/-]*)")
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter dict or None, body). Malformed YAML yields an empty dict."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        loaded = None
    fm = loaded if isinstance(loaded, dict) else {}
    return fm, text[match.end():]


def frontmatter_tags(fm: dict[str, Any] | None) -> list[str]:
    if not fm:
        return []
    raw = fm.get("tags")
    if isinstance(raw, str):
        raw = [t for t in re.split(r"[,\s]+", raw) if t]
    if not isinstance(raw, list):
        return []
    return [str(t).strip().lstrip("#") for t in raw if str(t).strip()]


def extract_tags(body: str, fm: dict[str, Any] | None) -> list[str]:
    tags = {m.group(1) for m in TAG_RE.finditer(body)}
    tags.update(frontmatter_tags(fm))
    return sorted(tags)


def normalize_tag(tag: str) -> str:
    norm = re.sub(r"[\s_]+", "-", tag.strip().lstrip("#").lower())
    norm = re.sub(r"[^a-z0-9/-]", "", norm)
    return norm.strip("-/")


def normalized_tags(tags: list[str]) -> list[str]:
    return sorted({n for n in (normalize_tag(t) for t in tags) if n})


def link_target(raw: str) -> str:
    return raw.split("|", 1)[0].split("#", 1)[0].strip()


def extract_wikilinks(text: str) -> list[str]:
    seen: list[str] = []
    for raw in WIKILINK_RE.findall(text):
        target = link_target(raw)
        if target and target not in seen:
            seen.append(target)
    return seen


def title_of(rel: str, text: str) -> str:
    match = H1_RE.search(text)
    return match.group(1).strip() if match else Path(rel).stem
