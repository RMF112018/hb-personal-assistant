"""Bounded, metadata-only live filesystem scan → ParsedTree.

Operator/CLI-only. NEVER invoked from an MCP request handler. Walks configured local roots with
hard caps (files/folders/depth/timeout), collects only structural metadata (names, counts,
extensions, bounded samples), and emits the same :class:`ParsedTree` the printed-tree parser
produces so the identical classify → persist pipeline runs downstream. It copies nothing, reads no
file contents, and mutates no source folder. Absolute paths are used only to walk; the emitted rows
carry root-relative ``rel_path`` only.
"""

from __future__ import annotations

import os
import time
from collections import Counter
from dataclasses import dataclass

from hb_assistant.obsidian_mcp.source_structure_classifier import is_noise_name
from hb_assistant.obsidian_mcp.source_structure_models import (
    MAX_DOMINANT_EXTENSIONS,
    MAX_SAMPLE_NAMES,
)
from hb_assistant.obsidian_mcp.source_structure_tree_parser import (
    ParsedFolder,
    ParsedRoot,
    ParsedTree,
)


@dataclass(slots=True)
class ScanCaps:
    max_files_per_root: int = 200_000
    max_folders_per_root: int = 50_000
    max_depth: int = 12
    timeout_seconds: int = 300
    high_fanout_threshold: int = 40


class ScanError(RuntimeError):
    pass


def _ext(name: str) -> str | None:
    _, dot, suffix = name.rpartition(".")
    if dot and 1 <= len(suffix) <= 8 and suffix.isalnum():
        return suffix.lower()
    return None


def scan_root(root_key: str, abs_path: str, caps: ScanCaps) -> tuple[ParsedRoot, list[ParsedFolder]]:
    """Walk one local root into a ParsedRoot + folder list, honoring caps. Raises on missing path."""
    if not os.path.isdir(abs_path):
        raise ScanError(f"scan root path is not a directory: {abs_path!r}")
    display = os.path.basename(abs_path.rstrip("/")) or root_key
    root = ParsedRoot(root_key=root_key, display_name=display, source_header=abs_path)
    folders: list[ParsedFolder] = []
    started = time.monotonic()
    folder_count = 0
    file_total = 0
    base_depth = abs_path.rstrip("/").count(os.sep)

    for dirpath, dirnames, filenames in os.walk(abs_path):
        if time.monotonic() - started > caps.timeout_seconds:
            raise ScanError(f"scan timed out after {caps.timeout_seconds}s at {root_key}")
        depth = dirpath.rstrip("/").count(os.sep) - base_depth
        if depth >= caps.max_depth:
            dirnames[:] = []  # stop descending
        # Prune noise dirs from traversal but remember them for counting.
        noise_children = [d for d in dirnames if is_noise_name(d)]
        dirnames[:] = [d for d in dirnames if not is_noise_name(d)]
        dir_children = list(dirnames)

        rel = os.path.relpath(dirpath, abs_path)
        rel_path = "" if rel == "." else rel.replace(os.sep, "/")
        parent_rel = None if rel_path == "" else os.path.dirname(rel_path)
        parent_rel = None if rel_path == "" else (parent_rel or "")

        ext_counter: Counter[str] = Counter()
        for fn in filenames:
            e = _ext(fn)
            if e:
                ext_counter[e] += 1
        dominant = [e for e, _ in ext_counter.most_common(MAX_DOMINANT_EXTENSIONS)]
        sample = (dir_children + filenames)[:MAX_SAMPLE_NAMES]

        folders.append(
            ParsedFolder(
                root_key=root_key,
                rel_path=rel_path,
                name=os.path.basename(dirpath) if rel_path else display,
                depth=depth,
                parent_rel_path=parent_rel,
                child_folder_names=dir_children[:MAX_SAMPLE_NAMES],
                child_folder_count=len(dir_children),
                file_count=len(filenames),
                dominant_extensions=dominant,
                sample_names=sample,
                noise_child_count=len(noise_children),
                is_high_fanout=len(dir_children) >= caps.high_fanout_threshold,
            )
        )
        folder_count += 1  # noqa: SIM113 — os.walk yields dirs, not an enumerable index; caps need both counters
        file_total += len(filenames)
        if folder_count >= caps.max_folders_per_root or file_total >= caps.max_files_per_root:
            break

    return root, folders


def scan_roots(scan_map: dict[str, str], caps: ScanCaps) -> ParsedTree:
    """Scan several configured roots into one ParsedTree. ``scan_map`` = {root_key: abs_path}."""
    if not scan_map:
        raise ScanError("no scan roots configured (source_structure.scan_roots is empty)")
    tree = ParsedTree()
    for root_key, abs_path in scan_map.items():
        root, folders = scan_root(root_key, abs_path, caps)
        tree.roots.append(root)
        tree.folders.extend(folders)
    tree.totals = {
        "root_count": len(tree.roots),
        "folder_count": len(tree.folders),
        "file_count": sum(f.file_count for f in tree.folders),
        "max_depth": max((f.depth for f in tree.folders), default=0),
        "high_fanout_folders": sum(1 for f in tree.folders if f.is_high_fanout),
        "noise_child_total": sum(f.noise_child_count for f in tree.folders),
    }
    return tree
