"""Backlink, unlinked-mention, and local-graph tools for the Obsidian MCP server.

All read-only. Links are parsed as both Obsidian wikilinks (``[[Target]]``) and inline
Markdown links (``[text](Target.md)``); a link resolves to a note when it matches that
note's stem, title, or relative path. Path safety (hidden/protected/traversal) is enforced
exactly as for the other read tools, and results are capped.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import mdutil, pathsafe
from .config import ObsidianMcpConfig
from .tools import (
    ObsidianMcpToolError,
    _extension,
    _hidden_inspection_allowed,
    resolve_safe_path,
)

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_SNIPPET_CHARS = 200
_MAX_RESULTS = 500


def _link_aliases(rel: str, title: str) -> set[str]:
    """The set of lowercased tokens a link may use to reference this note."""
    stem = Path(rel).stem
    no_md = rel[:-3] if rel.lower().endswith(".md") else rel
    return {stem.lower(), title.lower(), rel.lower(), no_md.lower()}


def _normalize_link(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if target.lower().endswith(".md"):
        target = target[:-3]
    return target.lower()


def _outgoing_links(text: str) -> list[str]:
    links = [mdutil.link_target(raw) for raw in mdutil.WIKILINK_RE.findall(text)]
    links += [m.group(1) for m in _MD_LINK_RE.finditer(text)]
    out: list[str] = []
    for link in links:
        norm = _normalize_link(link)
        if norm and not norm.startswith(("http://", "https://")) and norm not in out:
            out.append(norm)
    return out


def _snippet(text: str, needle: str) -> str:
    low = text.lower()
    idx = low.find(needle.lower())
    if idx < 0:
        return " ".join(text.split())[:_SNIPPET_CHARS]
    start = max(0, idx - 60)
    end = min(len(text), idx + len(needle) + 100)
    return " ".join(text[start:end].split())[:_SNIPPET_CHARS]


def _index_notes(config: ObsidianMcpConfig, root_path: str, *, operator_mode: bool) -> list[dict[str, Any]]:
    resolved = resolve_safe_path(config, root_path, must_exist=True)
    if not resolved.path.is_dir():
        raise ObsidianMcpToolError("path_is_not_directory")
    include_hidden = _hidden_inspection_allowed(config, operator_mode)
    if pathsafe.path_blocked(resolved.relative, include_hidden=include_hidden):
        raise ObsidianMcpToolError("protected_path_blocked")
    notes: list[dict[str, Any]] = []
    for item in sorted(resolved.path.rglob("*"), key=lambda p: p.as_posix().lower()):
        if pathsafe.symlink_escapes(item, resolved.root):
            continue
        rel = item.resolve().relative_to(resolved.root).as_posix()
        if pathsafe.path_blocked(rel, include_hidden=include_hidden):
            continue
        if item.is_dir() or (_extension(item) or "") != "md":
            continue
        text = item.read_text(encoding="utf-8", errors="replace")
        title = mdutil.title_of(rel, text)
        notes.append(
            {
                "rel": rel,
                "title": title,
                "text": text,
                "aliases": _link_aliases(rel, title),
                "links": _outgoing_links(text),
            }
        )
    return notes


def get_backlinks(
    config: ObsidianMcpConfig,
    *,
    target_path: str,
    root_path: str = "",
    max_results: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    target = resolve_safe_path(config, target_path, must_exist=True)
    if (_extension(target.path) or "") != "md":
        raise ObsidianMcpToolError("markdown_only")
    target_text = target.path.read_text(encoding="utf-8", errors="replace")
    target_aliases = _link_aliases(target.relative, mdutil.title_of(target.relative, target_text))
    cap = min(max(1, max_results), _MAX_RESULTS)

    results: list[dict[str, Any]] = []
    for note in _index_notes(config, root_path, operator_mode=operator_mode):
        if note["rel"] == target.relative:
            continue
        matched = [link for link in note["links"] if link in target_aliases]
        if matched:
            results.append(
                {"path": note["rel"], "matched_link": matched[0], "snippet": _snippet(note["text"], matched[0])}
            )
        if len(results) >= cap:
            break
    return {"target_path": target.relative, "count": len(results), "backlinks": results}


def get_unlinked_mentions(
    config: ObsidianMcpConfig,
    *,
    target_title: str,
    root_path: str = "",
    max_results: int = 100,
    include_snippets: bool = True,
    operator_mode: bool = False,
) -> dict[str, Any]:
    title = (target_title or "").strip()
    if len(title) < 3:
        raise ObsidianMcpToolError("target_title_too_short")
    cap = min(max(1, max_results), _MAX_RESULTS)
    mention_re = re.compile(rf"\b{re.escape(title)}\b", re.IGNORECASE)
    norm_title = title.lower()

    results: list[dict[str, Any]] = []
    for note in _index_notes(config, root_path, operator_mode=operator_mode):
        if note["title"].lower() == norm_title:
            continue  # the note that *is* the entity
        if norm_title in note["links"]:
            continue  # already links to it
        if mention_re.search(note["text"]):
            entry: dict[str, Any] = {"path": note["rel"]}
            if include_snippets:
                entry["snippet"] = _snippet(note["text"], title)
            results.append(entry)
        if len(results) >= cap:
            break
    return {"target_title": title, "count": len(results), "mentions": results}


def get_note_graph(
    config: ObsidianMcpConfig,
    *,
    root_path: str = "",
    target_path: str | None = None,
    depth: int = 2,
    max_nodes: int = 100,
    operator_mode: bool = False,
) -> dict[str, Any]:
    cap = min(max(1, max_nodes), _MAX_RESULTS)
    notes = _index_notes(config, root_path, operator_mode=operator_mode)
    alias_to_rel: dict[str, str] = {}
    for note in notes:
        for alias in note["aliases"]:
            alias_to_rel.setdefault(alias, note["rel"])

    edges: list[dict[str, str]] = []
    degree: dict[str, int] = {note["rel"]: 0 for note in notes}
    adjacency: dict[str, set[str]] = {note["rel"]: set() for note in notes}
    for note in notes:
        for link in note["links"]:
            dest = alias_to_rel.get(link)
            if dest and dest != note["rel"]:
                edges.append({"source": note["rel"], "target": dest})
                degree[note["rel"]] += 1
                degree[dest] += 1
                adjacency[note["rel"]].add(dest)
                adjacency[dest].add(note["rel"])

    selected = {note["rel"] for note in notes}
    truncated = False
    if target_path is not None:
        target = resolve_safe_path(config, target_path, must_exist=True)
        if target.relative not in adjacency:
            raise ObsidianMcpToolError("target_not_in_scope")
        selected = {target.relative}
        frontier = {target.relative}
        for _ in range(max(0, depth)):
            nxt: set[str] = set()
            for node in frontier:
                nxt |= adjacency.get(node, set())
            new = nxt - selected
            selected |= new
            frontier = new
            if not frontier:
                break
    if len(selected) > cap:
        selected = set(sorted(selected)[:cap])
        truncated = True

    nodes = [{"path": rel, "title": next(n["title"] for n in notes if n["rel"] == rel), "degree": degree[rel]} for rel in sorted(selected)]
    scoped_edges = [e for e in edges if e["source"] in selected and e["target"] in selected]
    orphans = sorted(rel for rel in selected if degree[rel] == 0)
    high_degree = [n["path"] for n in sorted(nodes, key=lambda n: (-n["degree"], n["path"]))[:5] if n["degree"] > 0]
    warnings = ["max_nodes_truncated"] if truncated else []
    return {
        "root_path": root_path.strip("/"),
        "nodes": nodes,
        "edges": scoped_edges,
        "orphans": orphans,
        "high_degree_notes": high_degree,
        "warnings": warnings,
    }
