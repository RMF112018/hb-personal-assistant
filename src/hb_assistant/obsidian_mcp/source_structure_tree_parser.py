"""Parse a printed folder-tree artifact into structured, root-relative folder rows.

The NAS roots are not reliably mounted on the machine running the indexer, so the primary ingest
path is a static printed tree (e.g. ``nas-folder-tree.txt`` produced by ``tree`` or an indented
dump). This module is purely *structural*: it recovers the folder hierarchy, per-folder counts,
dominant extensions, and bounded sample names. Classification (root/folder/doc-family, project
numbers, noise/backup/generated flags) is the classifier's job (Phase 3), not the parser's.

Absolute-path root headers are used only to derive a neutral ``root_key`` + display name at ingest
time; the absolute path itself is never carried into the folder rows.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from hb_assistant.obsidian_mcp.source_structure_models import (
    MAX_DOMINANT_EXTENSIONS,
    MAX_SAMPLE_NAMES,
)

# Tree connectors that precede an entry name (order matters — longest/space-suffixed first).
_CONNECTORS = ("├── ", "└── ", "|-- ", "`-- ", "+-- ", "├──", "└──", "|--", "`--", "+--")
# One indentation "unit" is 4 columns in `tree`/typical indented output.
_INDENT_UNIT = 4
# A leaf whose name matches this is treated as a file, not a folder.
_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")
# Extension pull for dominant-extension stats.
_EXT_RE = re.compile(r"\.([A-Za-z0-9]{1,8})$")

IsNoiseName = Callable[[str], bool]


@dataclass(slots=True)
class ParsedRoot:
    root_key: str
    display_name: str
    source_header: str  # original header text — NOT persisted to client-facing rows


@dataclass(slots=True)
class ParsedFolder:
    root_key: str
    rel_path: str  # "" for the root folder itself, else "a/b/c"
    name: str
    depth: int
    parent_rel_path: str | None
    child_folder_names: list[str] = field(default_factory=list)
    child_folder_count: int = 0
    file_count: int = 0
    dominant_extensions: list[str] = field(default_factory=list)
    sample_names: list[str] = field(default_factory=list)
    noise_child_count: int = 0
    is_high_fanout: bool = False


@dataclass(slots=True)
class ParsedTree:
    roots: list[ParsedRoot] = field(default_factory=list)
    folders: list[ParsedFolder] = field(default_factory=list)
    totals: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Node:
    name: str
    depth: int
    is_dir: bool
    children: list["_Node"] = field(default_factory=list)


def _slugify_root_key(header: str) -> str:
    """Derive a neutral, stable root_key from a header line (basename, lowercased, hyphenated)."""
    base = header.strip().rstrip("/:").split("/")[-1] or header.strip().strip("/:")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
    return slug or "root"


def _display_name(header: str) -> str:
    return header.strip().rstrip("/:").split("/")[-1] or header.strip().strip("/:")


def _is_root_header(line: str) -> bool:
    """A root header is a non-indented absolute path or a bare dir header ending in ':'."""
    stripped = line.rstrip("\n")
    if not stripped or stripped[0].isspace():
        return False
    if any(c in stripped for c in _CONNECTORS_CHARS):
        return False
    return stripped.startswith("/") or stripped.rstrip().endswith(":")


_CONNECTORS_CHARS = {"├", "└", "│", "`"}


def _split_indent(line: str) -> tuple[int, str]:
    """Return (depth, name) for a tree/indent line. depth is 1-based under the current root."""
    raw = line.expandtabs(_INDENT_UNIT).rstrip("\n")
    # Locate the connector that immediately precedes the name.
    for conn in _CONNECTORS:
        idx = raw.rfind(conn)
        if idx != -1:
            prefix = raw[:idx]
            name = raw[idx + len(conn) :].strip()
            # prefix is made of "│   " / "    " indentation units.
            units = len(prefix) // _INDENT_UNIT
            return units + 1, name
    # No connector: pure-space indentation.
    stripped = raw.lstrip(" ")
    lead = len(raw) - len(stripped)
    units = lead // _INDENT_UNIT
    return units + 1, stripped.strip()


def _infer_is_dir(name: str, has_children: bool) -> bool:
    if name.endswith("/"):
        return True
    if has_children:
        return True
    # A leaf with a file-like extension is a file; otherwise assume a (possibly empty) folder.
    return not bool(_FILE_EXT_RE.search(name))


def _build_forest(lines: list[str]) -> list[tuple[ParsedRoot, _Node]]:
    """Group lines into (root, root-node) pairs; nesting resolved by depth."""
    forest: list[tuple[ParsedRoot, _Node]] = []
    current_root: ParsedRoot | None = None
    root_node: _Node | None = None
    # Stack of (depth, node) for the active branch.
    stack: list[tuple[int, _Node]] = []

    for line in lines:
        if not line.strip():
            continue
        if _is_root_header(line):
            header = line.rstrip("\n").rstrip(":")
            current_root = ParsedRoot(
                root_key=_slugify_root_key(header),
                display_name=_display_name(header),
                source_header=header,
            )
            root_node = _Node(name=current_root.display_name, depth=0, is_dir=True)
            forest.append((current_root, root_node))
            stack = [(0, root_node)]
            continue
        if current_root is None:
            # A tree with no explicit root header: synthesize one from the first entry's context.
            current_root = ParsedRoot(root_key="root", display_name="root", source_header="root")
            root_node = _Node(name="root", depth=0, is_dir=True)
            forest.append((current_root, root_node))
            stack = [(0, root_node)]

        depth, name = _split_indent(line)
        if not name:
            continue
        name = name.rstrip("/")
        node = _Node(name=name, depth=depth, is_dir=False)
        # Pop to the parent (a node with depth < this depth).
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            stack = [(0, root_node)]  # defensive: reattach to root
        stack[-1][1].children.append(node)
        stack.append((depth, node))

    return forest


def _finalize_dirs(node: _Node) -> None:
    """Second pass: set is_dir now that children are known."""
    for child in node.children:
        _finalize_dirs(child)
    node.is_dir = _infer_is_dir(node.name, bool(node.children))


def _flatten(
    root: ParsedRoot,
    node: _Node,
    rel_path: str,
    parent_rel: str | None,
    out: list[ParsedFolder],
    is_noise_name: IsNoiseName | None,
    high_fanout_threshold: int,
) -> None:
    if not node.is_dir:
        return
    file_children = [c for c in node.children if not c.is_dir]
    dir_children = [c for c in node.children if c.is_dir]
    ext_counter: Counter[str] = Counter()
    for f in file_children:
        m = _EXT_RE.search(f.name)
        if m:
            ext_counter[m.group(1).lower()] += 1
    dominant = [ext for ext, _ in ext_counter.most_common(MAX_DOMINANT_EXTENSIONS)]
    sample = [c.name for c in node.children][:MAX_SAMPLE_NAMES]
    noise_children = 0
    if is_noise_name is not None:
        noise_children = sum(1 for c in dir_children if is_noise_name(c.name))
    out.append(
        ParsedFolder(
            root_key=root.root_key,
            rel_path=rel_path,
            name=node.name,
            depth=node.depth,
            parent_rel_path=parent_rel,
            child_folder_names=[c.name for c in dir_children][:MAX_SAMPLE_NAMES],
            child_folder_count=len(dir_children),
            file_count=len(file_children),
            dominant_extensions=dominant,
            sample_names=sample,
            noise_child_count=noise_children,
            is_high_fanout=len(dir_children) >= high_fanout_threshold,
        )
    )
    for c in dir_children:
        child_rel = posixpath.join(rel_path, c.name) if rel_path else c.name
        _flatten(root, c, child_rel, rel_path, out, is_noise_name, high_fanout_threshold)


def parse_tree_text(
    text: str,
    *,
    root_key_map: dict[str, str] | None = None,
    is_noise_name: IsNoiseName | None = None,
    high_fanout_threshold: int = 40,
    max_nodes: int | None = None,
) -> ParsedTree:
    """Parse printed-tree ``text`` into a :class:`ParsedTree`.

    ``root_key_map`` maps a header substring → an explicit root_key (overrides the derived slug).
    ``is_noise_name`` (from the classifier) enables per-folder noise-child counting.
    ``max_nodes`` caps the number of parsed lines (bounded ingest).
    """
    lines = text.splitlines()
    if max_nodes is not None:
        lines = lines[:max_nodes]
    forest = _build_forest(lines)

    tree = ParsedTree()
    for root, root_node in forest:
        if root_key_map:
            for needle, key in root_key_map.items():
                if needle in root.source_header:
                    root.root_key = key
                    break
        _finalize_dirs(root_node)
        tree.roots.append(root)
        _flatten(root, root_node, "", None, tree.folders, is_noise_name, high_fanout_threshold)

    tree.totals = {
        "root_count": len(tree.roots),
        "folder_count": len(tree.folders),
        "file_count": sum(f.file_count for f in tree.folders),
        "max_depth": max((f.depth for f in tree.folders), default=0),
        "high_fanout_folders": sum(1 for f in tree.folders if f.is_high_fanout),
        "noise_child_total": sum(f.noise_child_count for f in tree.folders),
    }
    return tree
