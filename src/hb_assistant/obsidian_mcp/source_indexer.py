"""Bounded, idempotent source indexing — runs OUTSIDE the MCP request path.

Deterministic extraction (reusing files/parsers/*), bounded excerpt/chunk caps, path→project
matching, and explicit writes via SourceIndexRepository. Never copies files into the vault.
"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import threading
import unicodedata
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE

from . import pathsafe
from .config import ExternalSourceRoot, ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository
from .source_skip_codes import (
    BOUNDED_RESUME,
    DEFERRED_PATH,
    EMAIL_ARCHIVE_SELF_INDEX_GUARD,
    EXCLUDED_PATH,
    SOURCE_NOTES_SELF_INDEX_GUARD,
    UNSUPPORTED_FILE_TYPE,
)
from .source_value import SourceValue, _ext_norm, classify_source_value

_logger = logging.getLogger("hb_assistant.obsidian_mcp.source_index")

_TEXT_EXTS = {"md", "markdown", "txt"}
_PARSER_EXTS = {"pdf", "docx", "xlsx"}
# Synchronous native/ZIP/MIME parsers with NO killable timeout (PR 1). A hung or pathological file of
# these types can stall/OOM the whole scan, so they are indexed metadata-only unless the hardened
# ``source_index_enable_synchronous_parser_extraction`` opt-in is set (permanent fix = PR 4 watchdog).
_SYNC_PARSER_EXTS = _PARSER_EXTS | {"eml"}
_TEMP_SUFFIXES = (".tmp", ".swp", ".swo", ".part", ".crdownload")
_TEMP_NAMES = {".ds_store"}


def should_ignore(rel_path: str, name: str) -> bool:
    """Skip protected/hidden/temp files (shared by scan + watcher)."""
    if pathsafe.path_blocked(rel_path, include_hidden=False):
        return True
    lower = name.lower()
    return lower in _TEMP_NAMES or lower.startswith("~$") or lower.endswith(_TEMP_SUFFIXES)


def is_excluded_source_path(rel_path: str, config: ObsidianMcpConfig) -> bool:
    """True if a source path lies in a low-value dependency/build/cache tree.

    Pure + segment-based: normalizes separators, lowercases, and matches whole path SEGMENTS
    against ``config.source_index_excluded_path_parts`` (so ``node_modules/x`` and ``a/node_modules/x``
    both hit, while a file merely *named* ``build.txt`` does NOT). Applied before indexing AND before
    any card/summary generation so broad roots don't produce low-value cards.
    """
    excluded = getattr(config, "source_index_excluded_path_parts", None)
    if not excluded:
        return False
    excluded_set = {str(p).strip().lower() for p in excluded if str(p).strip()}
    segments = [seg for seg in str(rel_path).replace("\\", "/").lower().split("/") if seg]
    return any(seg in excluded_set for seg in segments)


def effective_max_files(root: ExternalSourceRoot, config: ObsidianMcpConfig) -> int:
    """Per-root ``max_files`` override, else the global ``external_source_scan_max_files`` default.

    Lets a small root (vault) keep the conservative default while a large NAS root (Work/Home/backup)
    raises its own ceiling, without one blunt global number.
    """
    per_root = getattr(root, "max_files", None)
    if per_root is not None:
        return int(per_root)
    return int(getattr(config, "external_source_scan_max_files", 5000))


def _redact_walk_error(root_path: Path, target: Path) -> str:
    """Redaction-safe token (parent-hash + depth, never an absolute host path) for ``error_sink``."""
    from .source_scan_runner import redact_rel_prefix

    try:
        rel = str(target.relative_to(root_path))
    except ValueError:
        rel = ""
    return redact_rel_prefix(rel)


def walk_source_tree(
    root_path: Path,
    config: ObsidianMcpConfig,
    *,
    want_dirs: bool = False,
    error_sink: list[str] | None = None,
) -> Iterator[tuple[str, Path, str]]:
    """Lazily walk ``root_path`` depth-first, yielding ``(kind, abs_path, rel_path)`` where ``kind``
    is ``"file"`` (always) or ``"dir"`` (only when ``want_dirs``).

    Unlike ``sorted(root_path.rglob("*"))``, this NEVER materializes or sorts the whole tree: it uses
    ``os.scandir`` per directory (sorted only within a directory for deterministic order) and — the key
    scale win — **prunes excluded/hidden/ignored directory subtrees**, so a low-value tree
    (``node_modules``, ``.git``, ``Library``, caches, hidden dirs) costs one ``readdir`` instead of a
    full recursive sweep. Symlinked directories are never descended (cycle/escape safety); a symlinked
    file is yielded only if it resolves inside the root. No file content is read.

    Callers apply their own ``max_files`` cap on the yielded ``"file"`` entries.

    ``error_sink`` (opt-in): this walker is intentionally fail-OPEN (it silently skips every unreadable
    directory/entry so a bounded stat-walk never aborts). A caller that uses the walk to drive DELETIONS
    (lightweight reconcile) cannot tolerate that — an unreadable subtree would look empty and mass-delete
    its still-present rows. When ``error_sink`` is provided, an INDETERMINATE OSError (anything but a
    confirmed ``ENOENT``/``ENOTDIR`` — permission / transient I/O / stale-handle / mount-loss) at any of
    the three swallow points appends a redaction-safe token to it, so the caller can fail closed. A
    confirmed missing dir/entry stays a silent skip (a genuine removal). Callers that pass no sink are
    byte-for-byte unchanged.
    """
    root_path = Path(root_path)
    stack: list[Path] = [root_path]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError as exc:
            if error_sink is not None and _is_indeterminate_oserror(exc):
                error_sink.append(_redact_walk_error(root_path, current))
            continue
        subdirs: list[Path] = []
        for entry in entries:
            abs_path = Path(entry.path)
            try:
                rel_path = str(abs_path.relative_to(root_path))
            except ValueError:
                continue
            try:
                is_symlink = entry.is_symlink()
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError as exc:
                if error_sink is not None and _is_indeterminate_oserror(exc):
                    error_sink.append(_redact_walk_error(root_path, abs_path))
                continue
            if should_ignore(rel_path, entry.name) or is_excluded_source_path(rel_path, config):
                # prune: neither descend an excluded dir nor yield an excluded file
                continue
            if is_symlink:
                # never descend a symlink dir; include a symlinked file only if it stays in-root
                try:
                    if abs_path.is_file() and not pathsafe.symlink_escapes(abs_path, root_path):
                        yield ("file", abs_path, rel_path)
                except OSError as exc:
                    if error_sink is not None and _is_indeterminate_oserror(exc):
                        error_sink.append(_redact_walk_error(root_path, abs_path))
                continue
            if is_dir:
                if want_dirs:
                    yield ("dir", abs_path, rel_path)
                subdirs.append(abs_path)
            elif is_file:
                yield ("file", abs_path, rel_path)
        # push in reverse so the sorted children pop in ascending order (stable DFS)
        for d in reversed(subdirs):
            stack.append(d)


class DirectoryFanoutError(Exception):
    """A directory exceeded the configured fanout cap — fail closed rather than unbounded-sort (V122).

    Carries the redaction-safe rel_dir depth (never an absolute host path) for the ``last_error_code``.
    """

    def __init__(self, rel_dir: str, count_over: int) -> None:
        self.rel_dir = rel_dir
        self.count_over = count_over
        super().__init__(
            f"directory_fanout_limit:depth={len([s for s in rel_dir.split('/') if s])}"
        )


class DirectoryReadError(Exception):
    """A directory could not be enumerated for an INDETERMINATE reason (permission / transient I/O /
    stale NAS handle / mount interruption) — NOT a confirmed removal (V122 §7, F-01).

    A confirmed-gone directory (``ENOENT``/``ENOTDIR``) is treated as empty (its files reconcile as
    deleted only when the whole walk completes and each file's own restat confirms absence). An
    indeterminate error MUST fail closed: the walk cannot claim that subtree is empty, so the generation
    is SUSPENDED (partial, resumable) with no reconciliation — an unreadable subtree can never be
    published as a complete scan that then mass-deletes its indexed files. Carries only the redaction-safe
    rel_dir depth, never an absolute host path.
    """

    def __init__(self, rel_dir: str) -> None:
        self.rel_dir = rel_dir
        super().__init__(f"directory_read_error:depth={len([s for s in rel_dir.split('/') if s])}")


# Filesystem-uncertainty taxonomy (V122, round-7 blocker 3). A confirmed ``ENOENT``/``ENOTDIR`` is a
# structural fact (gone / not-a-directory) and is safe to treat as invalid/absent. Every OTHER OSError —
# permission (``EACCES``/``EPERM``), transient I/O (``EIO``), stale handle (``ESTALE``), timeout, mount-loss,
# or even a bare OSError with no errno — is INDETERMINATE: we CANNOT distinguish "truly gone" from
# "momentarily unreachable", so it must fail closed (suspend / preserve), never abandon a cursor or silently
# drop a possibly-present entry. Fail-closed-by-default is deliberately broader than any fixed errno list.
def _is_confirmed_missing(exc: OSError) -> bool:
    """True only for a CONFIRMED ``ENOENT``/``ENOTDIR`` — a structural fact (gone / not-a-directory)."""
    return exc.errno in (errno.ENOENT, errno.ENOTDIR)


def _is_indeterminate_oserror(exc: OSError) -> bool:
    """True when an ``OSError`` cannot be trusted as a confirmed structural fact (anything that is not
    ``ENOENT``/``ENOTDIR``) — permission / transient I/O / stale-handle / mount-loss / unknown errno. Such
    errors must fail closed (suspend), never abandon a cursor or silently skip a possibly-present entry."""
    return not _is_confirmed_missing(exc)


def derive_watcher_ready(
    *,
    gen_row: dict[str, Any] | None,
    current_fp: str | None,
    folder_count: int,
    legacy_ready: bool,
) -> bool:
    """Single authority for "is the file watcher clear to run for this root?" — shared by the health
    projection and ``resolve_run_state`` so the CLI can never launch a watcher the health service reports
    as not-ready (V122 blocker 2).

    For a root the V122 architecture tracks (``gen_row`` present), readiness is FAIL-CLOSED: the current
    policy fingerprint must be KNOWN (``current_fp is not None`` — an unverifiable policy must never launch
    a live watcher), the latest generation must be ``completed`` under THAT fingerprint, and a structure
    folder map must exist. A root with no V122 generation yet falls back to the persisted legacy bit.
    """
    if gen_row is not None:
        return bool(
            current_fp is not None
            and gen_row.get("status") == "completed"
            and gen_row.get("policy_fingerprint") == current_fp
            and folder_count > 0
        )
    return bool(legacy_ready)


# V122 traversal comparator: a COLLISION-SAFE total order used for BOTH sorting a directory listing and
# resuming a cursor. NFC alone can map two distinct filesystem names to one key, so the tie-breaker is the
# original name — two distinct entries never compare equal. Locked by test.
def entry_sort_key(name: str) -> tuple[str, str]:
    return (unicodedata.normalize("NFC", name), name)


def _scandir_sorted(
    abs_dir: Path, root_path: Path, config: ObsidianMcpConfig, fanout_limit: int
) -> list[tuple[tuple[str, str], str, Path, str, bool, bool]]:
    """Bounded, pruned, deterministically-sorted listing of one directory.

    Reads at most ``fanout_limit + 1`` entries; if the directory has more, raises
    :class:`DirectoryFanoutError` (fail closed — never load+sort an unbounded listing). Otherwise returns
    entries sorted by :func:`entry_sort_key`, each as
    ``(sort_key, name, abs_path, rel_path, is_dir, is_symlink)`` with excluded/hidden/ignored entries
    pruned (same policy as :func:`walk_source_tree`). Symlinked dirs are marked so the walker never
    descends them; a symlinked file is included only if it resolves inside the root.
    """
    raw: list[os.DirEntry[str]] = []
    try:
        with os.scandir(abs_dir) as it:
            for entry in it:
                raw.append(entry)
                if len(raw) > fanout_limit:
                    try:
                        rel_dir = str(abs_dir.relative_to(root_path))
                    except ValueError:
                        rel_dir = ""
                    raise DirectoryFanoutError(rel_dir, len(raw))
    except (FileNotFoundError, NotADirectoryError):
        # Confirmed gone (ENOENT/ENOTDIR): the directory legitimately no longer exists. Treat as empty —
        # its indexed files are deleted only if the FULL walk completes and each file's own restat
        # confirms absence (never from this empty listing alone).
        return []
    except OSError as exc:
        # INDETERMINATE (permission / transient I/O / stale handle / mount interruption): we must NOT
        # claim this subtree is empty. Fail closed so the generation is suspended, not falsely completed.
        try:
            rel_dir = str(abs_dir.relative_to(root_path))
        except ValueError:
            rel_dir = ""
        raise DirectoryReadError(rel_dir) from exc
    try:
        rel_dir = str(abs_dir.relative_to(root_path))
    except ValueError:
        rel_dir = ""
    out: list[tuple[tuple[str, str], str, Path, str, bool, bool]] = []
    for entry in raw:
        abs_path = Path(entry.path)
        try:
            rel_path = str(abs_path.relative_to(root_path))
        except ValueError:
            continue
        try:
            is_symlink = entry.is_symlink()
            is_dir = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
        except OSError as exc:
            # A per-entry stat that CONFIRMS the entry vanished (ENOENT/ENOTDIR — a mid-scan removal) is
            # safe to skip: the full walk + each file's own restat reconciles the deletion. Any INDETERMINATE
            # error must NOT silently drop a possibly-present file — fail closed so the walk suspends (F-01,
            # round-7 blocker 3).
            if _is_indeterminate_oserror(exc):
                raise DirectoryReadError(rel_dir) from exc
            continue
        if should_ignore(rel_path, entry.name) or is_excluded_source_path(rel_path, config):
            continue
        if is_symlink:
            try:
                if abs_path.is_file() and not pathsafe.symlink_escapes(abs_path, root_path):
                    out.append(
                        (entry_sort_key(entry.name), entry.name, abs_path, rel_path, False, True)
                    )
            except OSError as exc:
                # A broken symlink (confirmed-missing target) is legitimately skipped; an indeterminate
                # target error (permission / stale mount) must fail closed, never silently drop the entry.
                if _is_indeterminate_oserror(exc):
                    raise DirectoryReadError(rel_dir) from exc
            continue
        if is_dir:
            out.append((entry_sort_key(entry.name), entry.name, abs_path, rel_path, True, False))
        elif is_file:
            out.append((entry_sort_key(entry.name), entry.name, abs_path, rel_path, False, False))
    out.sort(key=lambda e: e[0])
    return out


@dataclass
class _WalkFrame:
    rel_dir: str
    abs_dir: Path
    entries: list[tuple[tuple[str, str], str, Path, str, bool, bool]]
    idx: int
    current: str | None = (
        None  # name of the entry currently in progress at this level (for the cursor)
    )


def _resume_frame(
    rel_dir: str,
    root_path: Path,
    config: ObsidianMcpConfig,
    fanout_limit: int,
    after_name: str | None,
) -> _WalkFrame:
    abs_dir = root_path if rel_dir in ("", ".") else root_path / rel_dir
    entries = _scandir_sorted(abs_dir, root_path, config, fanout_limit)
    idx = 0
    if after_name is not None:
        after_key = entry_sort_key(after_name)
        while idx < len(entries) and entries[idx][0] <= after_key:
            idx += 1
    return _WalkFrame(rel_dir=rel_dir, abs_dir=abs_dir, entries=entries, idx=idx)


def walk_generation(
    root_path: Path,
    config: ObsidianMcpConfig,
    *,
    cursor: dict[str, Any] | None,
    fanout_limit: int,
) -> Iterator[tuple[Path, str, dict[str, Any]]]:
    """Deterministic, RESUMABLE, depth-first file walk yielding ``(abs_path, rel_path, cursor_after)``.

    Unlike :func:`walk_source_tree`, this resumes past a durable ``cursor`` WITHOUT re-listing the
    already-completed sibling directories: the cursor is a versioned frame stack
    ``{"version": tv, "frames": [{"d": rel_dir, "after": name}, ...]}`` where each frame's ``after`` names
    the entry that was in progress at that level (an intermediate frame's ``after`` is the subdir we
    descended into; the deepest frame's ``after`` is the last committed file). On resume each frame is
    re-listed, entries with ``entry_sort_key <= after`` are skipped, and the deeper frames re-enter the
    in-progress subtree — so DFS pre-order is preserved exactly.

    ``cursor_after`` yielded with each file is the resume cursor to persist AFTER committing that file.
    Raises :class:`DirectoryFanoutError` if any directory exceeds ``fanout_limit`` (fail closed).
    """
    frames = (cursor or {}).get("frames") or []
    stack: list[_WalkFrame] = []
    if frames:
        # Rebuild the in-progress path. Intermediate frames' `current` = the descended child (so the
        # cursor we emit re-includes them); the deepest frame resumes at entries > its `after`.
        for i, fr in enumerate(frames):
            rel_dir = str(fr.get("d") or "")
            after = fr.get("after")
            wf = _resume_frame(rel_dir, root_path, config, fanout_limit, after)
            if i < len(frames) - 1:
                # Intermediate frame: `after` IS the in-progress child we descended into. Re-record it
                # so a cursor emitted before this frame advances still includes this level.
                wf.current = after
            stack.append(wf)
    else:
        stack.append(_resume_frame("", root_path, config, fanout_limit, None))

    def _cursor_after() -> dict[str, Any]:
        return {
            "version": int(getattr(config, "source_index_traversal_version", 1)),
            "frames": [
                {"d": f.rel_dir, "after": f.current} for f in stack if f.current is not None
            ],
        }

    while stack:
        frame = stack[-1]
        if frame.idx >= len(frame.entries):
            stack.pop()
            continue
        _key, name, abs_path, rel_path, is_dir, _is_symlink = frame.entries[frame.idx]
        frame.idx += 1
        frame.current = name
        if is_dir:
            child = _resume_frame(rel_path, root_path, config, fanout_limit, None)
            stack.append(child)
            continue
        yield (abs_path, rel_path, _cursor_after())


def is_deferred_source_path(rel_path: str, config: ObsidianMcpConfig) -> bool:
    """True if a source path is in a DEFERRED business class (e.g. 'HB INSURANCE RENEWALS').

    Distinct from exclusion: deferred sources are still indexed/searchable, but auto card/summary
    generation is intentionally skipped (they are valid records that are not PM-card-first). Pure +
    segment-based against ``config.source_index_deferred_path_parts``.
    """
    deferred = getattr(config, "source_index_deferred_path_parts", None)
    if not deferred:
        return False
    deferred_set = {str(p).strip().lower() for p in deferred if str(p).strip()}
    segments = [seg for seg in str(rel_path).replace("\\", "/").lower().split("/") if seg]
    return any(seg in deferred_set for seg in segments)


def is_source_notes_path(rel_path: str, config: ObsidianMcpConfig) -> bool:
    """True if a vault-relative path is a generated source card under ``source_notes_folder``.

    Generated ``Source Notes/<...>.md`` cards must NOT be re-indexed as vault notes (that would feed
    the watcher its own writes). Prefix match on the configured folder (default 'Source Notes'),
    normalized + case-insensitive, honoring a custom/multi-segment folder.
    """
    folder = (
        (getattr(config, "source_notes_folder", None) or "Source Notes")
        .replace("\\", "/")
        .strip("/")
        .lower()
    )
    if not folder:
        return False
    rel = str(rel_path).replace("\\", "/").strip("/").lower()
    return rel == folder or rel.startswith(folder + "/")


# Top-level vault root for Phase-10E full-email archive notes (see Amendment #4). Kept as a module
# constant (not a config field) so it needs no config-schema version bump — the location is fixed.
EMAIL_ARCHIVE_FOLDER = "Email Archive"


def is_email_archive_path(rel_path: str) -> bool:
    """True if a vault-relative path is a Phase-10E full-email archive note.

    Archive notes carry full bodies/addresses/message-ids and must NEVER be self-indexed into the
    note FTS (nor treated as a source card). Unlike ``is_source_notes_path`` they live in a SEPARATE
    top-level root (``Email Archive/Work/...``), so protection is keyed on the archive-root prefix,
    normalized + case-insensitive.
    """
    rel = str(rel_path).replace("\\", "/").strip("/").lower()
    folder = EMAIL_ARCHIVE_FOLDER.lower()
    return rel == folder or rel.startswith(folder + "/")


def match_path_to_project(rel_path: str) -> tuple[str | None, str | None, str]:
    """Deterministic HB project-number extraction from a path. Returns (key, number, confidence).

    Foundation slice: project_number comes from the NN-NNN-NN token; canonical project_key
    resolution against the registry is deferred to a later slice (key left None unless a single
    unambiguous number is present, in which case the number doubles as a filterable key).
    """
    numbers = sorted(set(HB_PROJECT_NUMBER_RE.findall(rel_path)))
    if len(numbers) == 1:
        return (numbers[0], numbers[0], "high")
    if len(numbers) > 1:
        return (None, numbers[0], "low")
    return (None, None, "none")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _read_text_head(path: Path, max_chars: int) -> str:
    """Bounded streaming read: at most ``max_chars`` characters, never the whole file into memory.

    A pathological huge text/log file must not be fully read just to index a bounded excerpt.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return fh.read(max_chars)


def extraction_disposition(ext: str, size: int, config: ObsidianMcpConfig) -> str:
    """Resolve how a file is indexed BEFORE any hashing/parsing (PR 1 safety gate).

    Returns ``content`` | ``metadata_only`` | ``unsupported`` | ``too_large``. The size gate and this
    disposition run BEFORE the full-file SHA-256 and any parser, so metadata-only / oversize / unsupported
    files are never hashed or parsed. Synchronous parser/eml formats are metadata-only unless the hardened
    ``source_index_enable_synchronous_parser_extraction`` opt-in is set.
    """
    max_mb = int(getattr(config, "max_file_mb", 100))
    if size > max_mb * 1024 * 1024:
        return "too_large"
    if ext in _TEXT_EXTS:
        return "content"
    if ext in _SYNC_PARSER_EXTS:
        enabled = bool(getattr(config, "source_index_enable_synchronous_parser_extraction", False))
        return "content" if enabled else "metadata_only"
    metadata_only = getattr(config, "source_index_metadata_only_file_types", None) or ()
    if ext in set(metadata_only):
        return "metadata_only"
    return "unsupported"


def _extract(
    path: Path, ext: str, max_chars: int, *, enable_parsers: bool = False
) -> dict[str, Any]:
    """Deterministic, best-effort extraction. Never raises on bad input.

    Text is read with a bounded streaming read (never the whole file). Synchronous native/ZIP/MIME
    parsers (pdf/docx/xlsx/eml) run ONLY when ``enable_parsers`` is set — the caller gates by
    ``extraction_disposition`` so this is normally unreachable for those types unless the hardened
    opt-in is on; the guard here is defense in depth against an unbounded parser hang/OOM.
    """
    if ext in _TEXT_EXTS:
        try:
            text = _read_text_head(path, max_chars)
            return {"text_excerpt": text, "char_count": len(text), "extraction_status": "ok"}
        except OSError as exc:  # unreadable
            return {
                "text_excerpt": "",
                "char_count": 0,
                "extraction_status": "failed",
                "failure_code": type(exc).__name__,
            }
    if not enable_parsers:
        return {"text_excerpt": None, "char_count": 0, "extraction_status": "metadata_only"}
    if ext == "eml":
        # First-class email (Phase 10E): deterministic MIME body as the indexed excerpt. The full
        # headers/attachments live in the archive note; only the body text is indexed here.
        from .source_email_archive import parse_email_file

        em = parse_email_file(path)
        status = (
            "ok"
            if em.parse_status == "complete"
            else ("failed" if em.parse_status == "failed" else "partial")
        )
        return {
            "text_excerpt": em.canonical_body_markdown[:max_chars],
            "char_count": len(em.canonical_body_markdown[:max_chars]),
            "extraction_status": status,
        }
    try:
        if ext == "pdf":
            from hb_assistant.files.parsers.pdf import PDFParser

            r = PDFParser().parse(path, max_chars)
        elif ext == "docx":
            from hb_assistant.files.parsers.docx import DOCXParser

            r = DOCXParser().parse(path, max_chars)
        elif ext == "xlsx":
            from hb_assistant.files.parsers.xlsx import XLSXParser

            r = XLSXParser().parse(path, max_chars)
        else:
            return {"text_excerpt": None, "char_count": 0, "extraction_status": "unsupported"}
    except Exception as exc:  # parser robustness backstop
        return {
            "text_excerpt": "",
            "char_count": 0,
            "extraction_status": "failed",
            "failure_code": type(exc).__name__,
        }
    status = "failed" if r.get("failure_code") else "ok"
    return {**r, "extraction_status": status}


def _chunks(text: str, max_chunks: int, max_chunk_chars: int) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for i in range(0, len(text), max_chunk_chars):
        out.append(text[i : i + max_chunk_chars])
        if len(out) >= max_chunks:
            break
    return out


_VALID_EXTRACTION_STATUS = {"pending", "ok", "unsupported", "failed", "skipped_too_large"}


def _norm_extraction_status(status: str | None) -> str:
    """Map an extractor's status onto the DB CHECK vocabulary (EXTRACTION_STATUS_VALUES).

    ``metadata_only`` (content deferred) -> ``pending``; ``partial`` (bounded eml body) -> ``ok``. Keeps
    a new value from ever violating the ``source_intelligence_metadata.extraction_status`` CHECK.
    """
    if status in _VALID_EXTRACTION_STATUS:
        return status  # type: ignore[return-value]
    if status == "metadata_only":
        return "pending"
    return "ok"


@dataclass
class IndexOutcome:
    """Structured result of indexing one file — lets the scan aggregate accurate counters without a
    per-file DB reread. ``source_id`` is None only when the file could not be registered at all."""

    source_id: str | None
    disposition: str  # content | metadata_only | unsupported | too_large
    changed: bool
    hashed: bool
    extraction_attempted: bool
    extraction_status: str


def _index_source_file(
    abs_path: Path,
    root: ExternalSourceRoot,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    conn: Any = None,
) -> IndexOutcome:
    """Index one external file (idempotent caller decides skip). Returns a structured IndexOutcome.

    Gate order (PR 1): stat -> size/disposition -> ONLY content-eligible files are SHA-256 hashed and
    parsed. Metadata-only/unsupported/too-large files register identity + metadata with no hash and no
    parser, so a hung/pathological parser or a giant file cannot stall/OOM the scan.
    """
    root_path = Path(root.path)
    try:
        rel_path = str(abs_path.relative_to(root_path))
    except ValueError:
        return IndexOutcome(None, "unsupported", False, False, False, "unsupported")
    ext = abs_path.suffix.lower().lstrip(".")
    try:
        stat = abs_path.stat()
    except OSError:
        return IndexOutcome(None, "unsupported", False, False, False, "unsupported")
    size = stat.st_size
    max_excerpt = int(getattr(config, "source_index_max_excerpt_chars", 8000))
    disposition = extraction_disposition(ext, size, config)

    record: dict[str, Any] = {
        "source_kind": "external_file",
        "source_root_key": root.source_root_key,
        "rel_path": rel_path,
        "abs_path_hash": hashlib.sha256(str(abs_path).encode()).hexdigest()[:32],
        "file_ext": ext,
        "size_bytes": size,
        "mtime_ns": stat.st_mtime_ns,
        # Explicit V122 disposition column (resolves the pending vs metadata-only ambiguity).
        "extraction_disposition": disposition,
        # Stamp the current policy fingerprint so a later scan can fast-skip this targeted-indexed row.
        "last_indexed_fingerprint": _root_fingerprint(root, config),
    }
    key, number, conf = match_path_to_project(rel_path)
    record["project_key"], record["project_number"] = key, number
    if number:
        record["relationships"] = [
            {
                "dst_kind": "project",
                "dst_ref": number,
                "relation": "belongs_to_project",
                "confidence": conf,
            }
        ]

    hashed = False
    extraction_attempted = False
    if disposition == "content":
        # Content-eligible ONLY: now (and only now) do the expensive full-file hash + extraction.
        record["content_sha256"] = _sha256_file(abs_path)
        hashed = True
        extraction_attempted = True
        enable_parsers = bool(
            getattr(config, "source_index_enable_synchronous_parser_extraction", False)
        )
        ex = _extract(abs_path, ext, max_excerpt, enable_parsers=enable_parsers)
        record["extraction_status"] = _norm_extraction_status(ex.get("extraction_status", "ok"))
        record["extraction_failure_code"] = ex.get("failure_code")
        record["page_count"] = ex.get("page_count")
        record["paragraph_count"] = ex.get("paragraph_count")
        record["sheet_count"] = ex.get("sheet_count")
        excerpt = ex.get("text_excerpt")
        if excerpt:
            if root.sensitive:
                # Sensitive root: encrypt the excerpt to the Text Vault; keep only a marker in-DB,
                # and DO NOT index sensitive text into FTS (extracted but not content-searchable).
                from hb_assistant.security.text_vault import encrypt_text

                record["text_vault_ref"] = encrypt_text(excerpt)
                record["text_excerpt"] = None
                record["excerpt_char_count"] = 0
            else:
                record["text_excerpt"] = excerpt[:max_excerpt]
                record["excerpt_char_count"] = len(record["text_excerpt"])
                record["excerpt_truncated"] = len(excerpt) >= max_excerpt
                record["full_text_sha256"] = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
                record["chunks"] = _chunks(
                    excerpt,
                    int(getattr(config, "source_index_max_chunks", 40)),
                    int(getattr(config, "source_index_max_chunk_chars", 1500)),
                )
    else:
        # metadata_only | unsupported | too_large: identity + metadata ONLY. No content_sha256, no
        # parse. content-clearing on a content->metadata transition is handled in upsert_source_file
        # (absent text_excerpt/text_vault_ref => stale text/chunks/FTS are cleared).
        record["content_sha256"] = None
        record["extraction_status"] = {
            "metadata_only": "pending",
            "unsupported": "unsupported",
            "too_large": "skipped_too_large",
        }[disposition]

    source_id = repo.upsert_source_file(record, conn=conn)
    return IndexOutcome(
        source_id=source_id,
        disposition=disposition,
        changed=True,
        hashed=hashed,
        extraction_attempted=extraction_attempted,
        extraction_status=str(record.get("extraction_status", "ok")),
    )


def index_source_file(
    abs_path: Path,
    root: ExternalSourceRoot,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    conn: Any = None,
) -> str | None:
    """TARGETED single-file indexing (metadata + eligible content extraction) — the compatibility entry
    point for watcher events, rebuild drains, tests, and external callers. Unlike a ROOT SCAN (which is
    metadata-only, :func:`_index_source_metadata`), this path DOES hash + extract content for a
    content-eligible file, since a single targeted file cannot stall a whole-root bootstrap. Preserves the
    historical ``source_id | None`` return."""
    return _index_source_file(abs_path, root, repo, config, conn=conn).source_id


class MetadataStatError(Exception):
    """A metadata observation could not stat/resolve the file (transient I/O, permission, disappeared
    between the walk's stat and this one). In a generation context this is INDETERMINATE — the caller
    must SUSPEND without advancing the cursor, never certify the file as processed (finding: second-stat
    race). ``raise_on_error=True`` opts into this typed error instead of the historical ``source_id=None``."""


def _index_source_metadata(
    abs_path: Path,
    root: ExternalSourceRoot,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    generation_id: str | None,
    preserve_content: bool = False,
    policy_fingerprint: str | None = None,
    raise_on_error: bool = False,
    conn: Any = None,
    in_transaction: bool = False,
) -> IndexOutcome:
    """Index ONE external file's METADATA ONLY (V122 metadata-first root scan).

    Stat -> disposition -> identity + metadata + path/project FTS, stamping ``last_seen_generation``.
    NEVER computes a SHA-256, parses, reads a body, or builds chunks — regardless of the parser opt-in
    flag — so a root scan cannot stall/OOM on a pathological file, and no content is read during discovery.
    Content extraction is deferred to the targeted :func:`index_source_file` path (and PR 3's queue). A
    content-eligible file therefore records ``extraction_disposition='content'`` with
    ``extraction_status='pending'`` (eligible, not yet extracted); a metadata-only file records
    ``metadata_only``/``pending``.

    ``preserve_content=True`` marks this a metadata/path-FTS REPAIR of a PHYSICALLY UNCHANGED file (a legacy
    row missing a path-FTS row or disposition): the upsert then keeps any valid extracted text/chunks/digest
    intact rather than clearing them. Otherwise (a genuine change or a disposition/sensitivity transition)
    the record carries no excerpt, so the upsert INVALIDATES stale content while retaining a path FTS row.
    ``in_transaction`` threads the write onto the caller's open txn for atomic batch commit.
    """
    root_path = Path(root.path)
    try:
        rel_path = str(abs_path.relative_to(root_path))
    except ValueError as exc:
        if raise_on_error:
            raise MetadataStatError("path_not_in_root") from exc
        return IndexOutcome(None, "unsupported", False, False, False, "unsupported")
    ext = abs_path.suffix.lower().lstrip(".")
    try:
        stat = abs_path.stat()
    except OSError as exc:
        # A stat failure here (the SECOND stat — the walk stat'd the file earlier) is INDETERMINATE, not a
        # confirmed removal: in a generation context raise so the pass suspends with the cursor HELD rather
        # than certifying the file as processed off a None outcome (finding: second-stat race).
        if raise_on_error:
            raise MetadataStatError("stat_failed") from exc
        return IndexOutcome(None, "unsupported", False, False, False, "unsupported")
    size = stat.st_size
    disposition = extraction_disposition(ext, size, config)
    record: dict[str, Any] = {
        "source_kind": "external_file",
        "source_root_key": root.source_root_key,
        "rel_path": rel_path,
        "abs_path_hash": hashlib.sha256(str(abs_path).encode()).hexdigest()[:32],
        "file_ext": ext,
        "size_bytes": size,
        "mtime_ns": stat.st_mtime_ns,
        "content_sha256": None,
        "extraction_disposition": disposition,
        "last_seen_generation": generation_id,
        "preserve_content": preserve_content,
        "last_indexed_fingerprint": (
            policy_fingerprint
            if policy_fingerprint is not None
            else _root_fingerprint(root, config)
        ),
    }
    key, number, conf = match_path_to_project(rel_path)
    record["project_key"], record["project_number"] = key, number
    if number:
        record["relationships"] = [
            {
                "dst_kind": "project",
                "dst_ref": number,
                "relation": "belongs_to_project",
                "confidence": conf,
            }
        ]
    record["extraction_status"] = {
        "content": "pending",  # eligible, not yet extracted (targeted path / PR 3 queue does that)
        "metadata_only": "pending",
        "unsupported": "unsupported",
        "too_large": "skipped_too_large",
    }[disposition]
    source_id = repo.upsert_source_file(record, conn=conn, in_transaction=in_transaction)
    return IndexOutcome(
        source_id=source_id,
        disposition=disposition,
        changed=not preserve_content,
        hashed=False,
        extraction_attempted=False,
        extraction_status=str(record["extraction_status"]),
    )


_VAULT_ROOT_KEY = "__vault_notes__"
_TAG_RE = __import__("re").compile(r"(?:^|\s)#([A-Za-z0-9_/\-]+)")


def _note_tags(text: str) -> str:
    """Space-joined tag set from inline #tags + a simple frontmatter ``tags:`` line."""
    tags = set(_TAG_RE.findall(text))
    head = text[:2000]
    if head.startswith("---"):
        for line in head.splitlines():
            stripped = line.strip()
            if stripped.startswith("tags:"):
                rest = stripped[len("tags:") :].strip().strip("[]")
                tags.update(
                    t.strip().strip("'\"#") for t in rest.replace(",", " ").split() if t.strip()
                )
    return " ".join(sorted(t for t in tags if t))


def index_obsidian_note(
    abs_path: Path,
    vault_root: Path,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    conn: Any = None,
) -> str | None:
    try:
        rel_path = str(abs_path.relative_to(vault_root))
        stat = abs_path.stat()
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    max_excerpt = int(getattr(config, "source_index_max_excerpt_chars", 8000))
    excerpt = text[:max_excerpt]
    _, number, _conf = match_path_to_project(rel_path)
    record: dict[str, Any] = {
        "source_kind": "obsidian_note",
        "source_root_key": _VAULT_ROOT_KEY,
        "rel_path": rel_path,
        "file_ext": "md",
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "content_sha256": _sha256_file(abs_path),
        "extraction_status": "ok",
        "text_excerpt": excerpt,
        "excerpt_char_count": len(excerpt),
        "excerpt_truncated": len(text) > max_excerpt,
        "full_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "project_number": number,
        "fts_aux": _note_tags(text),
    }
    return repo.upsert_source_file(record, conn=conn)


def scan_vault_notes(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    allow_confirmed_empty_recovery: bool = False,
) -> "ScanReport":
    """Bounded, idempotent index of the Obsidian vault's markdown notes into the note FTS.

    A1 deletion safety: a valid vault-note row is marked deleted ONLY when this scan is a
    certified-complete, untruncated, error-free, uninterrupted traversal of an AVAILABLE vault root
    (confirmed-absence only). A truncated / indeterminate-read / per-file-error / interrupted / empty
    observation preserves every pre-existing active row (source row, its FTS row, and generated-card
    state) and performs NO absence-based deletion — a resume/retry pass reconciles once the scan is
    trustworthy. "Delete" is index-state only; no source FILE is ever removed.

    ``allow_confirmed_empty_recovery`` is the one-shot operator override for the empty-root
    blast-radius guard ONLY: it still requires a certified-complete scan to reach reconciliation, and it
    is never exposed on a remote MCP surface (local operator CLI only).
    """
    report = ScanReport(root_key=_VAULT_ROOT_KEY)
    # Snapshot the active set BEFORE walking, so the empty-root guard and reconciliation compare against a
    # stable baseline and ``active_rows_before_scan`` reflects the pre-scan index.
    active_before = repo.active_rel_paths(_VAULT_ROOT_KEY)
    report.active_rows_before_scan = len(active_before)

    vault_root = Path(config.vault_root)
    if not vault_root.is_dir():
        report.root_available = False
        report.errors += 1
        report.error_codes.append("vault_root_not_found")
        report.completeness = "root_unavailable"
        report.deletion_reconciliation_allowed = False
        return report
    report.root_available = True

    max_files = int(getattr(config, "external_source_scan_max_files", 5000))
    seen: set[str] = set()
    walk_errors: list[str] = []
    walk_completed = False
    # Stream the vault the same way as external roots: walk_source_tree never materializes the whole tree
    # (no `sorted(rglob(...))`) and already applies should_ignore / is_excluded_source_path /
    # symlink-escape pruning, so a large vault cannot exhaust memory. The ``error_sink`` makes the
    # fail-OPEN walker REPORT indeterminate reads so an unreadable subtree can never masquerade as empty
    # and drive a mass-delete (mirrors the external-root apply path in source_bootstrap).
    try:
        for _kind, abs_path, rel_path in walk_source_tree(
            vault_root, config, error_sink=walk_errors
        ):
            if abs_path.suffix.lower() != ".md":
                continue
            # Never re-index our own generated source cards (Source Notes/...) or full-email archive
            # notes (Email Archive/...) as vault notes — that would feed the watcher its own writes and,
            # for archives, leak full email bodies/addresses into the note FTS.
            if is_source_notes_path(rel_path, config) or is_email_archive_path(rel_path):
                continue
            report.scanned += 1
            if report.scanned > max_files:
                report.truncated = True
                break
            seen.add(rel_path)
            try:
                existing = repo.lookup_by_path("obsidian_note", rel_path)
                if (
                    existing
                    and not existing["deleted"]
                    and existing["mtime_ns"] == abs_path.stat().st_mtime_ns
                    and existing["content_sha256"] == _sha256_file(abs_path)
                ):
                    report.skipped += 1
                    continue
                if index_obsidian_note(abs_path, vault_root, repo, config) is not None:
                    report.indexed += 1
            except Exception as exc:  # noqa: BLE001 — per-file observation/index failure (fail closed)
                report.per_file_error_count += 1
                report.errors += 1
                report.error_codes.append(type(exc).__name__)
        else:
            # for-else: reached ONLY when the loop exhausts naturally (no break, no exception).
            walk_completed = True
    except Exception as exc:  # noqa: BLE001 — a traversal-level failure is an INTERRUPTION (fail closed)
        report.interrupted = True
        report.errors += 1
        report.error_codes.append(type(exc).__name__)

    report.walk_error_count = len(walk_errors)
    report.eligible_files_seen = len(seen)

    # ---- Certified-completeness gate (single deterministic reason code) ----------------------------
    if report.interrupted:
        report.completeness = "interrupted"
    elif report.truncated or not walk_completed:
        report.completeness = "truncated"
    elif report.walk_error_count > 0:
        report.completeness = "walk_errors"
    elif report.per_file_error_count > 0:
        report.completeness = "file_errors"
    else:
        report.completeness = "complete"

    if report.completeness != "complete":
        # Uncertified traversal: retain every successful insert/update committed above; delete NOTHING.
        report.deletion_reconciliation_allowed = False
        return report

    # ---- Empty-root blast-radius guard -------------------------------------------------------------
    # A certified-complete scan that observed ZERO eligible notes while the index still holds active rows
    # is almost always a lost/empty mount, not a genuine full emptying. Block by default; the one-shot
    # operator recovery (which STILL required a certified scan to get here) is the only way an established
    # vault that legitimately emptied is reconciled — never a single empty observation on its own.
    if (
        report.eligible_files_seen == 0
        and report.active_rows_before_scan > 0
        and not allow_confirmed_empty_recovery
    ):
        report.completeness = "empty_root_guard"
        report.deletion_reconciliation_allowed = False
        return report

    # ---- Confirmed-absence reconciliation (ONE transaction over the whole confirmed-gone batch) -----
    report.deletion_reconciliation_allowed = True
    gone = sorted(active_before - seen)
    if gone:
        report.deleted += repo.mark_deleted_batch(
            "obsidian_note", gone, source_root_key=_VAULT_ROOT_KEY
        )
    return report


@dataclass
class ScanReport:
    root_key: str
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
    truncated: bool = False
    # A1 vault deletion-safety completeness contract. ``completeness`` is a single deterministic reason
    # code: complete | truncated | walk_errors | file_errors | interrupted | root_unavailable |
    # empty_root_guard. Deletion reconciliation runs ONLY when ``completeness == "complete"`` (and, for a
    # zero-observation scan, only under the operator recovery override) — a truncated/indeterminate/
    # interrupted/empty scan preserves every pre-existing active row (confirmed-absence only).
    completeness: str | None = None
    deletion_reconciliation_allowed: bool = False
    walk_error_count: int = 0
    per_file_error_count: int = 0
    interrupted: bool = False
    root_available: bool = True
    eligible_files_seen: int = 0
    active_rows_before_scan: int = 0
    # bounded_out: a per-pass budget (max_files_per_pass / max_seconds) stopped the walk early, so it
    # is INCOMPLETE and a resume pass is needed. completed: the walk fully finished (delete-reconcile ran).
    bounded_out: bool = False
    completed: bool = False
    error_codes: list[str] = field(default_factory=list)
    # source_ids of files newly indexed/changed this scan (NOT skipped/unchanged) — drives
    # rebuild auto-generation. Unchanged files are absent, so cards aren't needlessly regenerated.
    indexed_source_ids: list[str] = field(default_factory=list)
    # Per-disposition counters (aggregated from IndexOutcome, no per-file DB reread). ``metadata_upserted``
    # counts every changed file written this pass; ``files_unchanged`` == fast-skipped.
    files_walked: int = 0
    metadata_upserted: int = 0
    files_unchanged: int = 0
    content_attempted: int = 0
    content_succeeded: int = 0
    content_failed: int = 0
    metadata_only: int = 0
    unsupported: int = 0
    too_large: int = 0
    # V122 generation linkage (metadata-first scan). ``conflict`` = a live pass already owns the root
    # (retryable). ``generation_status`` mirrors the terminal generation state for the caller.
    run_id: str | None = None
    generation_id: str | None = None
    generation_status: str | None = None
    conflict: bool = False
    bounded_reason: str | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "root_key": self.root_key,
            "scanned": self.scanned,
            "indexed": self.indexed,
            "skipped": self.skipped,
            "deleted": self.deleted,
            "errors": self.errors,
            "truncated": self.truncated,
            "completeness": self.completeness,
            "deletion_reconciliation_allowed": self.deletion_reconciliation_allowed,
            "walk_error_count": self.walk_error_count,
            "per_file_error_count": self.per_file_error_count,
            "interrupted": self.interrupted,
            "root_available": self.root_available,
            "eligible_files_seen": self.eligible_files_seen,
            "active_rows_before_scan": self.active_rows_before_scan,
            "bounded_out": self.bounded_out,
            "completed": self.completed,
            "metadata_upserted": self.metadata_upserted,
            "files_unchanged": self.files_unchanged,
            "content_attempted": self.content_attempted,
            "content_succeeded": self.content_succeeded,
            "content_failed": self.content_failed,
            "metadata_only": self.metadata_only,
            "unsupported": self.unsupported,
            "too_large": self.too_large,
        }


# Bumped when the walker/cursor traversal order or frame format changes (folded into the fingerprint).
_WALKER_VERSION = "gen-walk-v1"


def _classify_observation_error(exc: BaseException) -> str:
    """Map a per-file stat failure to a STRUCTURED quarantine error code (never the raw exception string).

    ``path_unreadable`` — permission denied (EACCES/EPERM); ``path_changed_during_observation`` — the entry
    vanished mid-walk (ENOENT); ``stat_failed`` — any other stat/OS error."""
    e = getattr(exc, "errno", None)
    if e in (errno.EACCES, errno.EPERM):
        return "path_unreadable"
    if e in (errno.ENOENT, errno.ESTALE):
        return "path_changed_during_observation"
    return "stat_failed"


def _policy_fingerprint(
    root: ExternalSourceRoot, config: ObsidianMcpConfig, root_path_hash: str
) -> str:
    """Hash of EVERY metadata/search-affecting policy + code version (V122 §6).

    Any change (walker/cursor version, exclusion policy, disposition inputs, project matching, FTS
    weighting/tokenizer, traversal version, or the root's path) changes the fingerprint, so a resumed
    generation with an incompatible cursor is abandoned + restarted and previously fast-skippable files
    are reclassified. Never includes an absolute path (only ``root_path_hash``)."""
    payload = {
        "walker": _WALKER_VERSION,
        "traversal_version": int(getattr(config, "source_index_traversal_version", 1)),
        "excluded": sorted(getattr(config, "source_index_excluded_path_parts", []) or []),
        "deferred": sorted(getattr(config, "source_index_deferred_path_parts", []) or []),
        "text_exts": sorted(_TEXT_EXTS),
        "parser_exts": sorted(_SYNC_PARSER_EXTS),
        "metadata_only": sorted(getattr(config, "source_index_metadata_only_file_types", []) or []),
        "unsupported": sorted(getattr(config, "source_index_unsupported_file_types", []) or []),
        "max_file_mb": int(getattr(config, "max_file_mb", 100)),
        # The bounds that GOVERN no-forward-progress failures (high-fanout cap, per-generation ceiling) are
        # part of the policy: raising them is the operator's "relevant policy change" that lifts a failed
        # generation's no-auto-retry block (round-6 finding 1) — the changed fingerprint starts a fresh
        # generation instead of re-failing the old one every pass.
        "fanout_limit": int(getattr(config, "source_index_directory_fanout_limit", 20000)),
        "generation_ceiling": (
            int(config.source_index_generation_max_files)
            if getattr(config, "source_index_generation_max_files", None) is not None
            else None
        ),
        # The poison-file retry threshold GOVERNS a no-forward-progress failure (quarantine_unresolved), so it
        # is part of the policy: changing it is a "relevant policy change" that lifts a quarantine block via a
        # changed fingerprint (a fresh generation starts) — the same mechanism as fanout_limit above.
        "quarantine_retry_threshold": int(
            getattr(config, "source_index_quarantine_retry_threshold", 3)
        ),
        "parser_optin": bool(
            getattr(config, "source_index_enable_synchronous_parser_extraction", False)
        ),
        "project_matcher": "hb-num-v1",
        "fts": "bm25:1,8,12|unicode61",
        # A sensitivity flip changes how content is handled (encrypt-to-vault vs plain, FTS eligibility),
        # so it must invalidate the generation → a fresh generation reclassifies + re-secures every row.
        "sensitive": bool(getattr(root, "sensitive", False)),
        "root_key": root.source_root_key,
        "root_path_hash": root_path_hash,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def _root_fingerprint(root: ExternalSourceRoot, config: ObsidianMcpConfig) -> str:
    """Current policy fingerprint for a root, computed the same way :func:`scan_source_root` does (so a row
    stamped by a targeted index and one stamped by a scan agree). Stored per row as ``last_indexed_fingerprint``
    and compared on the next generation: a mismatch means the row is stale for current policy and must be
    reprocessed, not fast-skipped."""
    root_path_hash = hashlib.sha256(str(Path(root.path)).encode("utf-8")).hexdigest()[:32]
    return _policy_fingerprint(root, config, root_path_hash)


def _tally_disposition(report: "ScanReport", disposition: str) -> None:
    if disposition == "content":
        report.content_attempted += 0  # metadata-first: no content attempted during a root scan
    elif disposition == "metadata_only":
        report.metadata_only += 1
    elif disposition == "unsupported":
        report.unsupported += 1
    elif disposition == "too_large":
        report.too_large += 1


def _validate_cursor(
    cursor: dict[str, Any] | None, root_path: Path, config: ObsidianMcpConfig, fanout: int
) -> bool:
    """Structurally + physically + SEMANTICALLY validate a persisted traversal cursor BEFORE resuming.

    A resumed cursor is trusted only when: it is a dict; ``version`` is PRESENT and equals the current
    traversal version (a version-less or non-integer version is rejected — no lenient default); every frame
    is ``{"d": <root-relative dir>, "after": <basename>}``; each frame directory is contained within the root
    (no absolute path, no ``..`` escape, resolves inside root), still exists as a real directory, and is NOT
    a symlink at all; the first frame is the ROOT; each deeper frame's directory is EXACTLY
    ``parent.d / parent.after`` (the child we descended into); and — SEMANTICALLY — each ``after`` is an
    ACTUAL entry in its directory, an intermediate anchor is that directory (the descended child) and the
    deepest anchor is a FILE (a yielded entry). Without the semantic check a forged anchor (``after`` naming
    a non-existent or later entry, or the deepest anchor naming a directory) could make ``_resume_frame``
    skip real entries / an entire subtree and reach ``completed`` with false metadata completeness. Any
    STRUCTURAL/SEMANTIC violation ⇒ returns ``False`` ⇒ the caller ABANDONS the generation (no
    reconciliation) and restarts from the root. The semantic check re-lists each frame's directory, so it
    may raise :class:`DirectoryReadError` (transient I/O — the caller SUSPENDS to ``partial``, cursor
    preserved) or :class:`DirectoryFanoutError` (the caller FAILS the generation); these are NOT cursor
    corruption and must not be flattened into ``False``.
    """
    if cursor is None:
        return True
    if not isinstance(cursor, dict):
        return False
    tv = int(getattr(config, "source_index_traversal_version", 1))
    # A stored cursor MUST declare its version explicitly and numerically — a missing or non-integer
    # version is not a match (guards the int() conversion against arbitrary payloads).
    if "version" not in cursor:
        return False
    try:
        cursor_version = int(cursor["version"])
    except (TypeError, ValueError):
        return False
    if cursor_version != tv:
        return False
    frames = cursor.get("frames")
    if frames is None:
        return True  # a versioned cursor with no frames == start-from-root
    if not isinstance(frames, list):
        return False
    import stat as _sm

    root = Path(root_path)
    try:
        root_resolved = root.resolve()
    except OSError as exc:
        # A CONFIRMED-missing root anchor (ENOENT/ENOTDIR) is genuinely invalid → abandon. An INDETERMINATE
        # error (permission / stale mount) is NOT cursor corruption → suspend, preserve cursor (blocker 3).
        if _is_indeterminate_oserror(exc):
            raise DirectoryReadError("") from exc
        return False

    def _norm(rel: str) -> str:
        return rel.replace("\\", "/").strip("/")

    def _valid_basename(name: str) -> bool:
        # A cursor ``after`` names a single directory entry — never a path. Reject separators, NUL, and the
        # traversal specials so a corrupted ``after`` can't smuggle a path fragment into the resume compare.
        return bool(name) and not (
            "/" in name or "\\" in name or "\0" in name or name in (".", "..")
        )

    prev_norm: str | None = None
    prev_after: str | None = None
    for i, fr in enumerate(frames):
        if not isinstance(fr, dict):
            return False
        d = fr.get("d")
        after = fr.get("after")
        # Every ``after`` must be a single valid basename (no separators / NUL / '.' / '..').
        if not isinstance(d, str) or not isinstance(after, str) or not _valid_basename(after):
            return False
        norm_d = _norm(d)
        # The first frame MUST be the ROOT (d == "" or "."). A cursor that begins at an arbitrary
        # subdirectory could skip discovery of new files elsewhere yet still reach ``completed``.
        if i == 0 and norm_d != "":
            return False
        abs_dir = root if norm_d == "" else root / norm_d
        if d not in ("", "."):
            segments = norm_d.split("/")
            if d.startswith("/") or ".." in segments or "" in segments:
                return False
            try:
                resolved = abs_dir.resolve()
            except OSError as exc:
                if _is_indeterminate_oserror(exc):
                    raise DirectoryReadError(norm_d) from exc
                return False
            if resolved != root_resolved and root_resolved not in resolved.parents:
                return False
            # Reject ANY symlink frame (not merely an escaping one): its target may have changed since the
            # cursor was persisted, so resuming into it is unsafe regardless of where it currently points.
            # An explicit ``os.stat`` (not ``Path.is_dir()``, which swallows the stat errno) lets a transient
            # I/O error be classified: indeterminate → suspend (preserve cursor), confirmed-missing / not-a-
            # directory → abandon (blocker 3).
            try:
                dir_st = os.stat(abs_dir)  # follows symlinks — the frame must be a real directory
                is_symlink_frame = abs_dir.is_symlink()
                escapes = pathsafe.symlink_escapes(abs_dir, root)
            except OSError as exc:
                if _is_indeterminate_oserror(exc):
                    raise DirectoryReadError(norm_d) from exc
                return False
            if not _sm.S_ISDIR(dir_st.st_mode) or is_symlink_frame or escapes:
                return False
        # Parent→child must be EXACT: a deeper frame is the subdirectory named by its parent frame's
        # ``after`` (the entry the walker descended into), so ``child.d == parent.d / parent.after``.
        if prev_norm is not None:
            if prev_after is None:
                return False
            expected = _norm(f"{prev_norm}/{prev_after}" if prev_norm else prev_after)
            if norm_d != expected:
                return False
        # SEMANTIC anchor check: ``after`` must be an ACTUAL entry of this directory (else resuming past it
        # would skip real entries), an intermediate anchor must be a DIRECTORY (the descended child) and the
        # deepest anchor must be a FILE (a yielded entry — a directory here would skip its whole subtree).
        # DirectoryReadError (transient I/O) and DirectoryFanoutError PROPAGATE to the caller: a transient
        # NAS read failure is not cursor corruption (→ suspend, preserve cursor) and a fanout violation has
        # its own terminal classification (→ fail). Only a STRUCTURALLY/SEMANTICALLY invalid cursor returns
        # False here (→ abandon). Conflating the three into "invalid" wrongly abandons on transient I/O.
        entries = _scandir_sorted(abs_dir, root, config, fanout)
        is_dir_by_name = {name: is_dir for (_k, name, _a, _r, is_dir, _s) in entries}
        if after not in is_dir_by_name:
            return False
        is_deepest = i == len(frames) - 1
        if is_deepest and is_dir_by_name[after]:
            return False
        if not is_deepest and not is_dir_by_name[after]:
            return False
        prev_norm = norm_d
        prev_after = after
    return True


def _probe_candidate(abs_c: Path, root_path: Path) -> str:
    """Classify a stale reconcile candidate → ``present`` | ``absent`` | ``indeterminate`` (V122 §7).

    Only a confirmed **regular, in-root** file is ``present`` (a survivor — never deleted, refreshed
    instead). Only a confirmed **ENOENT** is ``absent`` (delete-eligible). A permission error, transient
    I/O error, symlink escape, or a non-regular inode now occupying the path is ``indeterminate`` — the
    candidate is NEVER deleted (that would be the exact false-deletion hazard PR 2 exists to prevent); the
    generation stays ``reconcile_pending`` until the condition clears.
    """
    import stat as _sm

    try:
        st = os.stat(abs_c)  # follows symlinks; a missing/broken target raises ENOENT
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "indeterminate"
    try:
        if not _sm.S_ISREG(st.st_mode):
            return "indeterminate"
        if pathsafe.symlink_escapes(abs_c, root_path):
            return "indeterminate"
    except OSError:
        return "indeterminate"
    return "present"


def _probe_root_dir(root_path: Path) -> str:
    """Classify a scan root → ``usable`` | ``absent`` | ``indeterminate`` (mount-safety, round-7 blocker 3).

    ``usable`` only for a confirmed existing directory. ``absent`` for a confirmed ENOENT/ENOTDIR (the root
    genuinely does not exist / is not a directory) or a non-directory inode now at the path. Any OTHER
    OSError (permission / stale handle / transient I/O — a lost or flaky mount) is ``indeterminate``: the
    scan SUSPENDS rather than failing as if the root were gone, so a previously-completed generation is never
    invalidated by a momentary mount blip. Unlike the old ``Path.is_dir()`` probe this runs AFTER the
    generation is claimed and its verdict is persisted in generation truth, so health closes trust at once."""
    import stat as _sm

    try:
        st = os.stat(root_path)  # follows symlinks (a symlinked root dir is fine)
    except OSError as exc:
        return "absent" if _is_confirmed_missing(exc) else "indeterminate"
    return "usable" if _sm.S_ISDIR(st.st_mode) else "absent"


def normalize_moved_rel_path(rel: str | None) -> str | None:
    """Lexically validate + canonicalize a moved event's relative path WITHOUT touching the filesystem
    (PB-006 / PLAN-C2R2-001). BOTH the old and new paths cross the queue trust boundary and must pass this
    before any lookup, source-id derivation, filesystem probe, or mutation. Returns the canonical posix
    relative path, or ``None`` when it is unsafe: empty, absolute, containing ``..``/``.``/empty segments,
    a backslash/alternate separator or NUL, a non-canonical form (duplicate separators / trailing slash),
    or a protected/hidden segment (``path_blocked``)."""
    if not rel or not isinstance(rel, str):
        return None
    if "\\" in rel or "\x00" in rel:
        return None
    p = PurePosixPath(rel)
    if p.is_absolute():
        return None
    parts = p.parts
    if not parts or any(seg in ("", ".", "..") for seg in parts):
        return None
    canonical = "/".join(parts)
    if canonical != rel:  # duplicate separators, trailing slash, './' etc. → reject rather than coerce
        return None
    if pathsafe.path_blocked(canonical, include_hidden=False):
        return None
    return canonical


@dataclass(frozen=True)
class DestinationResolution:
    """Structured verdict of a moved-event destination check (PB-006). ``identity`` is
    ``(st_dev, st_ino, st_size, st_mtime_ns)`` of the non-following ``lstat``; ``resolved_path`` is the
    symlink-resolved absolute path proven inside the resolved root."""

    state: str  # contained | absent | indeterminate | outside_root | not_regular
    resolved_path: Path | None = None
    identity: tuple[int, int, int, int] | None = None


def resolve_destination(root_path: Path, new_rel: str) -> DestinationResolution:
    """Classify a normalized destination rel-path against the root (PB-006). ``new_rel`` MUST already be
    lexically validated by :func:`normalize_moved_rel_path` (so no absolute/traversal path is ever probed).
    ``os.lstat`` is non-following → a symlink final component is ``not_regular``; ``resolve()`` +
    ``relative_to`` catches a symlinked PARENT escaping the root (``outside_root``); transient I/O →
    ``indeterminate`` (recoverable). A parent-symlink escape may be lstat/resolve-probed here, but the
    caller rejects ``outside_root`` BEFORE any source mutation or content indexing."""
    import stat as _sm

    dest_abs = root_path / new_rel
    try:
        lst = os.lstat(dest_abs)
    except FileNotFoundError:
        return DestinationResolution("absent")
    except OSError:
        return DestinationResolution("indeterminate")
    if not _sm.S_ISREG(lst.st_mode):
        return DestinationResolution("not_regular")
    try:
        resolved_root = root_path.resolve(strict=True)
        resolved_dest = dest_abs.resolve(strict=True)
    except OSError:
        return DestinationResolution("indeterminate")
    try:
        resolved_dest.relative_to(resolved_root)
    except ValueError:
        return DestinationResolution("outside_root")
    return DestinationResolution(
        "contained",
        resolved_path=resolved_dest,
        identity=(lst.st_dev, lst.st_ino, lst.st_size, lst.st_mtime_ns),
    )


def _apply_moved_event(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    event: dict[str, Any],
    root: ExternalSourceRoot,
    *,
    old_rel: str,
    new_rel: str,
    src_key: str,
    expected_attempt: int,
) -> None:
    """Governed same-root rename/move (Phase B / B4 corrective — PB-005/006/007/010), off the observer
    thread. GUARDED EXCEPTION WRAP: any unexpected error completes via the ownership-guarded path, so a
    moved event can NEVER reach the drain's generic unguarded ``complete_event``."""
    event_id = event["event_id"]
    try:
        _apply_moved_event_inner(
            repo, config, root, event_id=event_id, old_rel=old_rel, new_rel=new_rel,
            src_key=src_key, expected_attempt=expected_attempt,
        )
    except Exception as exc:  # noqa: BLE001 - never let a moved event fall through to the generic handler
        repo.complete_owned_event(
            event_id, "error", expected_attempt=expected_attempt, error_code=type(exc).__name__
        )


def _apply_moved_event_inner(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    root: ExternalSourceRoot,
    *,
    event_id: str,
    old_rel: str,
    new_rel: str,
    src_key: str,
    expected_attempt: int,
) -> None:
    """Readiness-gated, resolved/identity-safe, ownership-guarded move + destination re-extraction. Every
    RECOVERABLE condition (lost mount, not-ready root, dest not yet visible, transient I/O, pre/post-mutation
    drift, pending re-extraction) DEFERS under the CLAIM GENERATION (never terminally consumed while it could
    still succeed; old row left current until the move is proven safe). A provably-invalid destination
    (non-regular, escapes-root) is a fail-closed TERMINAL skip that never deletes the old row. Both rel-paths
    are already canonically validated by ``normalize_moved_rel_path`` (caller)."""
    from .source_root_trust import load_root_trust

    def _defer(code: str) -> None:
        if repo.defer_event(event_id, error_code=code, expected_attempt=expected_attempt) == "exhausted":
            # Recoverable condition that never cleared within the retry budget. NEVER delete the old row;
            # a guarded terminal, NON-mutating skip.
            repo.complete_owned_event(
                event_id, "skipped", expected_attempt=expected_attempt, error_code=f"{code}_unresolved"
            )

    def _terminal(status: str, code: str) -> None:
        repo.complete_owned_event(event_id, status, expected_attempt=expected_attempt, error_code=code)

    root_path = Path(root.path)
    # 1. Mount usable? (recoverable — a lost/flaky mount must not consume the move.)
    if _probe_root_dir(root_path) != "usable":
        _defer("root_unavailable")
        return
    # 2. Root readiness — the SAME strict bar the watcher activates on.
    try:
        ready = bool(load_root_trust(repo, config, None, src_key).safe_for_watcher_activation)
    except Exception:  # noqa: BLE001
        _defer("root_trust_unevaluable")
        return
    if not ready:
        _defer("root_not_ready")
        return
    # 3. Structured destination resolution (resolved-path containment catches a symlinked PARENT).
    res = resolve_destination(root_path, new_rel)
    if res.state == "absent":
        _defer("dest_absent")
        return
    if res.state == "indeterminate":
        _defer("dest_indeterminate")
        return
    if res.state == "outside_root":
        _terminal("skipped", "dest_escapes_root")
        return
    if res.state == "not_regular":
        _terminal("skipped", "dest_not_regular")
        return
    resolved0, identity0 = res.resolved_path, res.identity
    # 4. Immediate pre-transaction re-resolution (drift here is PRE-mutation → NO move, old stays current).
    pre = resolve_destination(root_path, new_rel)
    if pre.state != "contained" or pre.resolved_path != resolved0 or pre.identity != identity0:
        _defer("dest_changed_before_move")
        return
    assert identity0 is not None
    dest_metadata = {
        "file_ext": PurePosixPath(new_rel).suffix.lower().lstrip("."),
        "size_bytes": identity0[2],
        "mtime_ns": identity0[3],
    }
    # 5. Ownership-guarded lineage move (ownership SELECT + mutation atomic in one txn). claim_conflict →
    #    a stale worker whose event was reclaimed: NO mutation happened, and we must NOT complete/defer
    #    (the current owner is authoritative).
    move = repo.apply_owned_confirmed_same_root_move(
        event_id=event_id, expected_attempt=expected_attempt, root_key=src_key,
        old_relative_path=old_rel, new_relative_path=new_rel, destination_metadata=dest_metadata,
    )
    result = move.get("result")
    if result == "claim_conflict":
        return
    if result == "conflicting_successor":
        _terminal("skipped", "conflicting_successor")
        return
    # move_applied / move_already_applied / source_missing → (re)index the destination.
    # 6. Post-transaction re-resolution: drift AFTER the move leaves the old row SUPERSEDED (not restored);
    #    dest is content-invalidated + pending, so just defer re-extraction — never advertise complete.
    post = resolve_destination(root_path, new_rel)
    if post.state != "contained" or post.resolved_path != resolved0 or post.identity != identity0:
        _defer("dest_changed_during_move")
        return
    # 7. Re-check ownership before EXPENSIVE indexing. If lost, do not index under a stale claim — leave the
    #    dest pending+invalidated for the current owner to recover.
    if not repo.event_is_owned(event_id, expected_attempt):
        return
    dest_abs = root_path / new_rel
    try:
        sid = index_source_file(dest_abs, root, repo, config)
    except Exception:  # noqa: BLE001
        sid = None
    if sid is None:
        # None (or an exception) is a RETRYABLE indexing failure — never complete on a bare no-throw.
        if repo.defer_event(
            event_id, error_code="dest_reindex_pending", expected_attempt=expected_attempt
        ) == "exhausted":
            # The safe move committed; only the content refresh did not complete. Terminal ERROR (not
            # 'done') — "move committed, content pending", lineage + supersede + invalidation intact.
            _terminal("error", "dest_reindex_exhausted")
        return
    _terminal("done", None)


class _LeaseLost(Exception):
    """Raised inside a batch txn when the generation-cursor advance affects 0 rows — this run lost the
    ownership lease (a stale-lease takeover claimed the generation). The batch rolls back and the pass
    aborts WITHOUT touching the generation (its new owner is authoritative)."""


def scan_source_root(
    root: ExternalSourceRoot,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    *,
    max_files_per_pass: int | None = None,
    max_seconds: float | None = None,
    progress: Any = None,
    genrepo: Any = None,  # SourceIndexScanGenerationsRepository
    bstate: Any = None,  # SourceIndexBootstrapRepository
    run_id: str | None = None,
    mode: str = "bootstrap",
    restart: bool = False,
) -> ScanReport:
    """METADATA-FIRST, generation-driven, resumable walk of one root. NEVER called from a request handler.

    A root scan reads only METADATA — it never hashes, parses, reads a body, or chunks a file (content
    extraction is the targeted :func:`index_source_file` path / PR 3's queue). Discovery runs under a
    durable *scan generation* (V122): each bounded pass resumes past a persisted traversal cursor, commits
    metadata then checkpoints the cursor (a crash re-processes the batch, never skips it), and — only after
    the FULL metadata walk completes — reconciles deletions by generation (source_id keyset, restat before
    delete, never from a partial/failed generation). A per-generation ceiling or a high-fanout directory
    FAILS the generation (no reconciliation), never reopening as partial.
    """
    import time
    import uuid as _uuid

    from hb_assistant.store.connection import open_connection, transaction
    from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    report = ScanReport(root_key=root.source_root_key)
    root_path = Path(root.path)
    # NOTE: the root-availability probe is deliberately deferred until AFTER the generation is claimed (see
    # below) so a missing/stale mount is recorded in generation truth — the pre-claim ``Path.is_dir()`` guard
    # here returned a failure while leaving the prior COMPLETED generation authoritative in health, so a lost
    # mount silently kept advertising trust (round-7 blocker 3). Computing the fingerprint/hash needs only the
    # path string, not an existing directory, so claiming first is safe.
    if genrepo is None:
        genrepo = SourceIndexScanGenerationsRepository(repo.db_path)
    if bstate is None:
        bstate = SourceIndexBootstrapRepository(repo.db_path)
    if run_id is None:
        run_id = _uuid.uuid4().hex
    report.run_id = run_id

    root_path_hash = hashlib.sha256(str(root_path).encode("utf-8")).hexdigest()[:32]
    fingerprint = _policy_fingerprint(root, config, root_path_hash)
    tv = int(getattr(config, "source_index_traversal_version", 1))
    stale = float(getattr(config, "source_index_bootstrap_stale_run_seconds", 120.0))

    gen = genrepo.begin_generation_pass(
        root.source_root_key,
        run_id,
        policy_fingerprint=fingerprint,
        root_path_hash=root_path_hash,
        traversal_version=tv,
        mode=mode,
        stale_lease_seconds=stale,
        restart=restart,
    )
    if gen is None:
        report.conflict = True
        report.generation_status = "conflict"
        report.error_code = "active_run_conflict"
        return report
    if gen.get("blocked"):
        # The latest generation FAILED with a no-forward-progress code (high-fanout / ceiling) under the
        # current policy: no new generation was created. Recovery needs a policy/config change (changes the
        # fingerprint) or an explicit restart — do NOT walk, do NOT reconcile, do NOT open a V119 pass.
        report.generation_id = gen["generation_id"]
        report.generation_status = "failed"
        report.error_code = gen.get("last_error_code") or "restart_required"
        report.error_codes.append(report.error_code)
        report.error_codes.append("restart_required")
        return report
    gid = gen["generation_id"]
    report.generation_id = gid
    gen_started = gen["started_at"]

    # Bounds: observed-file limit (counts EVERY walked entry, changed or fast-skipped), batch commit size,
    # optional per-generation hard ceiling, high-fanout cap.
    observed_limit = int(
        getattr(config, "source_index_scan_observed_files_per_pass", None) or 0
    ) or (int(max_files_per_pass) if max_files_per_pass is not None else None)
    batch_size = max(1, int(getattr(config, "source_index_metadata_batch_size", 500)))
    gen_ceiling = getattr(config, "source_index_generation_max_files", None)
    fanout = int(getattr(config, "source_index_directory_fanout_limit", 20000))
    heartbeat_s = float(getattr(config, "source_index_bootstrap_heartbeat_seconds", 10.0))

    # Running totals across ALL passes of this generation (resumed generation carries prior totals).
    files_observed = int(gen.get("files_observed") or 0)
    metadata_upserted = int(gen.get("metadata_upserted") or 0)
    files_unchanged = int(gen.get("files_unchanged") or 0)
    errors_count = int(gen.get("errors_count") or 0)
    deleted_count = int(gen.get("deleted_count") or 0)

    started = time.monotonic()
    last_progress = started

    def _emit_progress(rel_hint: str) -> None:
        if progress is None:
            return
        with suppress(Exception):
            progress(report, rel_hint, time.monotonic() - started)

    def _finish_v119(status: str) -> None:
        with suppress(Exception):
            bstate.finish_bootstrap_run(
                run_id,
                status=status,
                bounded_reason=report.bounded_reason,
                last_error_code=report.error_code,
                completed_metadata_walk=report.generation_status
                in ("reconcile_pending", "completed"),
                reconciliation_completed=report.generation_status == "completed",
                files_walked=report.files_walked,
                metadata_upserted=report.metadata_upserted,
                files_unchanged=report.files_unchanged,
                errors_count=report.errors,
            )

    def _transition_or_conflict(affected: int, attempted_status: str) -> bool:
        """Single lost-lease exit for the ownership-guarded GIVE-UP transitions (partial / reconcile_pending
        / failed). ``affected == 0`` means a stale-lease takeover already claimed this generation, so this
        run must NOT report ``attempted_status`` as authoritative — record a retryable ``lease_lost`` conflict
        and stop. Returns ``True`` to continue, ``False`` when the caller should ``return report`` at once
        (round-7 blocker 3). Factored from the pre-existing `_LeaseLost` handler so every give-up branch fails
        the same way instead of duplicating the block ~10 times."""
        if affected == 0:
            _logger.warning(
                "source_scan.lease_lost",
                extra={
                    "obsidian_mcp": {
                        "root": root.source_root_key,
                        "attempted_status": attempted_status,
                    }
                },
            )
            report.conflict = True
            report.generation_status = "conflict"
            report.error_code = "lease_lost"
            report.error_codes.append("lease_lost")
            _finish_v119("interrupted")
            return False
        return True

    # Root availability, now UNDER generation truth (blocker 3): a lost/stale mount is persisted as a
    # failed/partial generation so health closes trust immediately, instead of the old pre-claim guard that
    # returned while the prior COMPLETED generation stayed authoritative. Confirmed missing/not-a-directory →
    # FAIL (root_not_found, auto-retries when the root returns); indeterminate (permission / stale mount) →
    # SUSPEND (partial, no reconciliation) rather than falsely declaring the root gone.
    root_probe = _probe_root_dir(root_path)
    if root_probe == "absent":
        report.error_codes.append("root_not_found")
        report.errors += 1
        report.error_code = "root_not_found"
        if not _transition_or_conflict(
            genrepo.fail_generation(gid, run_id, last_error_code="root_not_found"), "failed"
        ):
            return report
        report.generation_status = "failed"
        _finish_v119("failed")
        return report
    if root_probe == "indeterminate":
        report.error_codes.append("root_probe_io_error")
        report.error_code = "root_probe_io_error"
        report.bounded_out = True
        report.bounded_reason = "root_probe_io_error"
        if not _transition_or_conflict(
            genrepo.mark_partial(gid, run_id, last_error_code="root_probe_io_error"), "partial"
        ):
            return report
        report.generation_status = "partial"
        _finish_v119("partial")
        return report

    walk_complete = gen.get("metadata_walk_completed_at") is not None
    # Decode the persisted cursor INSIDE the validation guard: a malformed/non-object JSON payload is
    # itself an invalid cursor (finding 4), so a decode error must ABANDON — never crash the pass or fall
    # through to a walk from root that then reconciles against a tree the cursor never described.
    cursor_raw = gen.get("cursor_json")
    cursor: dict[str, Any] | None = None
    cursor_decode_ok = True
    if cursor_raw:
        try:
            decoded = json.loads(cursor_raw)
        except (ValueError, TypeError):
            cursor_decode_ok = False
        else:
            # A well-formed but non-object payload (list/number/string) is not a valid cursor either.
            if isinstance(decoded, dict):
                cursor = decoded
            else:
                cursor_decode_ok = False

    # Validate a resumed cursor BEFORE walking (V122 §5). Outcomes are distinct (finding 4): a malformed /
    # escaping / renamed cursor is genuine corruption ⇒ ABANDON (no reconciliation, restart from root); a
    # transient directory read error during validation is NOT corruption ⇒ SUSPEND to partial with the
    # cursor PRESERVED (retried next pass); a fanout violation ⇒ FAIL with its own terminal classification.
    # The abandon is lease-fenced: cursor validation touches the filesystem, so a lease could expire + be
    # taken over during it — a 0 rowcount means we lost ownership and must NOT abandon the new owner's
    # generation (close as conflict).
    if not walk_complete:
        cursor_valid = cursor_decode_ok
        if cursor_decode_ok:
            try:
                cursor_valid = _validate_cursor(cursor, root_path, config, fanout)
            except DirectoryFanoutError:
                if not _transition_or_conflict(
                    genrepo.fail_generation(gid, run_id, last_error_code="directory_fanout_limit"),
                    "failed",
                ):
                    return report
                report.error_code = "directory_fanout_limit"
                report.error_codes.append("directory_fanout_limit")
                report.generation_status = "failed"
                _finish_v119("failed")
                return report
            except DirectoryReadError:
                # Transient permission / I/O / stale-NAS-handle error while re-listing to verify an anchor —
                # preserve the SAME cursor and suspend so the next pass retries from the same checkpoint.
                if not _transition_or_conflict(
                    genrepo.mark_partial(
                        gid,
                        run_id,
                        cursor_json=cursor_raw,
                        last_error_code="cursor_validation_io_error",
                    ),
                    "partial",
                ):
                    return report
                report.error_code = "cursor_validation_io_error"
                report.error_codes.append("cursor_validation_io_error")
                report.bounded_out = True
                report.bounded_reason = "cursor_validation_io_error"
                report.generation_status = "partial"
                _finish_v119("partial")
                return report
        if not cursor_valid:
            if genrepo.abandon_generation(gid, run_id, last_error_code="invalid_cursor") == 0:
                report.conflict = True
                report.generation_status = "conflict"
                report.error_code = "lease_lost"
                report.error_codes.append("lease_lost")
                _finish_v119("interrupted")
                return report
            report.error_code = "invalid_cursor"
            report.error_codes.append("invalid_cursor")
            report.generation_status = "abandoned"
            _finish_v119("interrupted")
            return report

    # ---- Phase 1: metadata walk (skipped if the generation already completed its walk) ----
    if not walk_complete:
        batch: list[tuple[Path, str, dict[str, Any]]] = []
        last_cursor = cursor
        # Set when an unresolved per-file stat/upsert error is hit: the pass stops at that file (the cursor
        # is NOT advanced past it) and the generation is suspended (partial) rather than completed with a
        # hole (F-03) — the file is retried next pass.
        pass_error = False
        # A4 poison-file quarantine (durable per-path bounded retry). BELOW the retry threshold a failing file
        # HOLDS the cursor (partial, retried next pass — the F-03 behavior). AT the threshold it is quarantined
        # (a blocking root-level record) and the cursor advances PAST it so later files still index. A walk that
        # exhausts holding a blocking quarantine is NON-authoritative (failed + quarantine_unresolved) and is
        # not auto-restarted until the operator resolves it (or policy changes / explicit restart).
        from hb_assistant.store.source_index_scan_quarantine_repository import (
            SourceIndexScanQuarantineRepository,
        )

        quarantine_repo = SourceIndexScanQuarantineRepository(str(repo.db_path))
        q_threshold = max(1, int(getattr(config, "source_index_quarantine_retry_threshold", 3)))
        # Paths already quarantined (skip immediately) and paths still retrying (resolve on a good observation).
        q_skip = quarantine_repo.blocking_paths(root.source_root_key)
        q_retry_watch = quarantine_repo.troubled_paths(root.source_root_key) - q_skip

        def _flush() -> None:
            """Commit ONE batch ATOMICALLY: all metadata upserts + unchanged last-seen stamps + counters +
            the cursor checkpoint in a SINGLE transaction. A crash rolls the whole batch back (re-processed
            next pass, never skipped). The cursor advances ONLY through a contiguous run of successfully
            persisted/fast-skipped observations — the first unresolved file stops the batch (``pass_error``)
            so completion can never skip it. If the cursor advance affects 0 rows this run LOST the lease →
            raise _LeaseLost and abort."""
            nonlocal files_observed, metadata_upserted, files_unchanged, errors_count
            nonlocal last_cursor, pass_error
            if not batch:
                return
            rels = [rel for _a, rel, _c in batch]
            with open_connection(repo.db_path) as c, transaction(c):
                state = repo.load_metadata_state_batch(root.source_root_key, rels, conn=c)
                unchanged: list[str] = []
                for abs_p, rel, cur in batch:
                    if rel in q_skip:
                        # Already quarantined (blocking): never re-attempt. Advance the cursor PAST it so the
                        # walk can exhaust and later files still index; trust/completion stay blocked by the
                        # durable quarantine record.
                        report.files_walked += 1
                        last_cursor = cur
                        continue
                    try:
                        st = abs_p.stat()
                    except OSError as exc:
                        # A per-file stat failure: record a bounded, durable retry attempt. Below the
                        # threshold HOLD the cursor (retried next pass); at the threshold QUARANTINE and
                        # advance past it (atomic with this batch's cursor checkpoint).
                        ec = _classify_observation_error(exc)
                        res = quarantine_repo.record_failure(
                            root_key=root.source_root_key, rel_path=rel, source_id=None,
                            generation_id=gid, failure_stage="metadata_stat", error_code=ec,
                            threshold=q_threshold, conn=c, in_transaction=True,
                        )
                        errors_count += 1
                        report.errors += 1
                        report.error_codes.append("stat_error")
                        if res["action"] == "quarantine":
                            q_skip.add(rel)
                            q_retry_watch.discard(rel)
                            report.files_walked += 1
                            last_cursor = cur  # advance PAST the quarantined file
                            continue
                        pass_error = True  # below threshold: HOLD the cursor, retry next pass
                        break
                    ext = abs_p.suffix.lower().lstrip(".")
                    recomputed = extraction_disposition(ext, st.st_size, config)
                    cur_pk, cur_num, _cur_conf = match_path_to_project(rel)
                    prev = state.get(rel)
                    stat_match = (
                        prev is not None
                        and prev["mtime"] == st.st_mtime_ns
                        and prev["size"] == st.st_size
                    )
                    disp_match = prev is not None and prev["disposition"] == recomputed
                    # Project routing must match on BOTH key and number: a matcher change that re-routes a
                    # file (even unchanged bytes) forces a replace of the stale project fields/edge (finding).
                    proj_match = (
                        prev is not None
                        and prev.get("project_key") == cur_pk
                        and prev.get("project_number") == cur_num
                    )
                    # Content-storage mode must match current sensitivity in BOTH directions: a sensitive
                    # root must not keep 'plain' (plaintext) and a plain root must not keep 'vault' (an
                    # encrypted ref); either mismatch owes a re-secure and defeats fast-skip AND preserve.
                    mode = prev.get("content_mode") if prev is not None else "none"
                    sensitive = bool(getattr(root, "sensitive", False))
                    sens_ok = not (
                        (sensitive and mode == "plain") or ((not sensitive) and mode == "vault")
                    )
                    # Fingerprint gate: any metadata/search-affecting policy or code change (sensitivity,
                    # project matcher, FTS format, root path, exclusions) changes the fingerprint, so a row
                    # last indexed under a DIFFERENT fingerprint is reprocessed rather than skipped (finding).
                    fp_match = prev is not None and prev.get("fingerprint") == fingerprint
                    content_valid = stat_match and disp_match and sens_ok
                    if content_valid and proj_match and fp_match and prev["has_fts"]:
                        # Fully current for CURRENT policy → fast-skip (stamp last-seen only).
                        unchanged.append(rel)
                        files_unchanged += 1
                        files_observed += 1
                        report.files_unchanged += 1
                        report.files_walked += 1
                        report.scanned += 1
                        report.skipped += 1
                        if rel in q_retry_watch:
                            # A path that was failing (below threshold) now observes cleanly → resolve its
                            # retry record so a transient failure never accumulates toward the threshold.
                            quarantine_repo.resolve_observed(
                                root_key=root.source_root_key, rel_path=rel, conn=c, in_transaction=True
                            )
                            q_retry_watch.discard(rel)
                        last_cursor = cur  # a fast-skip is a resolved, COMMITTED observation
                        continue
                    # preserve = the extracted CONTENT is still valid (stat/disposition/sensitivity ok), but
                    # the row's DERIVED state is stale (fingerprint change, project re-route, missing/legacy
                    # FTS). Preserve keeps content and AUTHORITATIVELY rebuilds the derived state (FTS from
                    # retained text, project/abs_path_hash, fingerprint). Content is cleared ONLY when it is
                    # itself invalid (a genuine change, disposition flip, or owed sensitivity re-secure).
                    preserve = bool(content_valid)
                    try:
                        outcome = _index_source_metadata(
                            abs_p,
                            root,
                            repo,
                            config,
                            generation_id=gid,
                            preserve_content=preserve,
                            policy_fingerprint=fingerprint,
                            raise_on_error=True,
                            conn=c,
                            in_transaction=True,
                        )
                    except Exception as exc:  # an unresolved metadata-upsert error: bounded retry / quarantine
                        res = quarantine_repo.record_failure(
                            root_key=root.source_root_key, rel_path=rel, source_id=None,
                            generation_id=gid, failure_stage="metadata_upsert",
                            error_code="metadata_upsert_failed", threshold=q_threshold,
                            conn=c, in_transaction=True,
                        )
                        errors_count += 1
                        report.errors += 1
                        report.error_codes.append(type(exc).__name__)
                        if res["action"] == "quarantine":
                            q_skip.add(rel)
                            q_retry_watch.discard(rel)
                            report.files_walked += 1
                            last_cursor = cur  # advance PAST the quarantined file
                            continue
                        pass_error = True  # below threshold: HOLD the cursor, retry next pass
                        break
                    if outcome.source_id is None:
                        # A metadata observation that produced no source id (second-stat race) is a path that
                        # changed during observation — bounded retry, then quarantine (never certified).
                        res = quarantine_repo.record_failure(
                            root_key=root.source_root_key, rel_path=rel, source_id=None,
                            generation_id=gid, failure_stage="metadata_observe",
                            error_code="path_changed_during_observation", threshold=q_threshold,
                            conn=c, in_transaction=True,
                        )
                        errors_count += 1
                        report.errors += 1
                        report.error_codes.append("metadata_no_source_id")
                        if res["action"] == "quarantine":
                            q_skip.add(rel)
                            q_retry_watch.discard(rel)
                            report.files_walked += 1
                            last_cursor = cur  # advance PAST the quarantined file
                            continue
                        pass_error = True  # below threshold: HOLD the cursor, retry next pass
                        break
                    metadata_upserted += 1
                    files_observed += 1
                    report.metadata_upserted += 1
                    report.files_walked += 1
                    report.scanned += 1
                    report.indexed += 1
                    report.indexed_source_ids.append(outcome.source_id)
                    _tally_disposition(report, outcome.disposition)
                    # Re-stale generated notes on any MATERIAL derived-state change. Content preservation is
                    # separate from material change: a preserve repair that only rebuilds FTS/fingerprint must
                    # NOT re-stale, but a PROJECT RE-ROUTE is material even under preserve — a source card
                    # persists project_key/number + project/<number> tags, so a re-route leaves the card
                    # showing obsolete project metadata unless it is re-staled (finding 3).
                    if prev is not None and (not preserve or not proj_match):
                        repo._mark_generated_notes_stale(c, outcome.source_id)
                    if rel in q_retry_watch:
                        # A previously-failing path (below threshold) now upserted cleanly → resolve its retry
                        # record so a transient failure never accumulates toward the threshold.
                        quarantine_repo.resolve_observed(
                            root_key=root.source_root_key, rel_path=rel, conn=c, in_transaction=True
                        )
                        q_retry_watch.discard(rel)
                    last_cursor = (
                        cur  # advance ONLY after a fully successful, COMMITTED observation
                    )
                repo.stamp_last_seen(
                    root.source_root_key, unchanged, gid, conn=c, in_transaction=True
                )
                affected = genrepo.advance_cursor(
                    gid,
                    run_id,
                    cursor_json=json.dumps(last_cursor) if last_cursor else None,
                    conn=c,
                    in_transaction=True,
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                )
                if affected == 0:
                    raise _LeaseLost()
            batch.clear()

        try:
            # ``pass_walked`` counts entries WALKED this pass (drives the per-pass observed bound);
            # ``files_observed`` counts only COMMITTED observations (incremented in _flush),
            # so an uncommitted batch suffix retried next pass is never double-counted toward the persisted
            # counters or the generation ceiling (finding: committed-prefix accounting).
            pass_walked = 0
            for abs_path, rel_path, cur in walk_generation(
                root_path, config, cursor=cursor, fanout_limit=fanout
            ):
                pass_walked += 1
                batch.append((abs_path, rel_path, cur))
                hit_observed = observed_limit is not None and pass_walked >= int(observed_limit)
                if len(batch) < batch_size and not hit_observed:
                    continue
                # A flush boundary: commit the batch, then evaluate bounds against COMMITTED counters.
                _flush()
                now_m = time.monotonic()
                if now_m - last_progress >= heartbeat_s:
                    last_progress = now_m
                    _emit_progress(rel_path)
                if pass_error:
                    break  # an unresolved file stopped this batch → suspend below (F-03)
                if hit_observed:  # per-pass OBSERVED bound → partial
                    report.bounded_out = True
                    report.bounded_reason = "observed_files_per_pass"
                    break
                if max_seconds is not None and (time.monotonic() - started) >= float(max_seconds):
                    report.bounded_out = True
                    report.bounded_reason = "max_seconds"
                    break
                # Per-generation hard ceiling (cumulative, COMMITTED) → no forward progress: FAIL.
                if gen_ceiling is not None and files_observed >= int(gen_ceiling):
                    report.error_code = "generation_ceiling"
                    if not _transition_or_conflict(
                        genrepo.fail_generation(
                            gid,
                            run_id,
                            last_error_code="generation_ceiling",
                            files_observed=files_observed,
                            metadata_upserted=metadata_upserted,
                            files_unchanged=files_unchanged,
                            errors_count=errors_count,
                        ),
                        "failed",
                    ):
                        return report
                    report.generation_status = "failed"
                    _finish_v119("failed")
                    return report
            else:
                _flush()  # loop exhausted normally
        except DirectoryFanoutError:
            if not _transition_or_conflict(
                genrepo.fail_generation(
                    gid,
                    run_id,
                    last_error_code="directory_fanout_limit",
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                ),
                "failed",
            ):
                return report
            report.error_code = "directory_fanout_limit"
            report.error_codes.append("directory_fanout_limit")
            report.generation_status = "failed"
            _finish_v119("failed")
            return report
        except DirectoryReadError:
            # A directory could not be enumerated for an INDETERMINATE reason (permission / transient I/O /
            # stale NAS handle / mount interruption). We must not claim that subtree is empty, so commit the
            # progress made so far and SUSPEND the generation (partial, resumable, NO reconciliation) — an
            # unreadable subtree can never be published as a complete scan that then mass-deletes files (F-01).
            with suppress(Exception):
                _flush()
            if not _transition_or_conflict(
                genrepo.mark_partial(
                    gid,
                    run_id,
                    cursor_json=json.dumps(last_cursor) if last_cursor else None,
                    last_error_code="directory_read_error",
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                ),
                "partial",
            ):
                return report
            report.error_code = "directory_read_error"
            report.error_codes.append("directory_read_error")
            report.bounded_out = True
            report.bounded_reason = "directory_read_error"
            report.generation_status = "partial"
            _finish_v119("partial")
            return report
        except _LeaseLost:
            # A stale-lease takeover claimed this generation mid-batch. Do NOT touch the generation (its
            # new owner is authoritative); just close this pass as a retryable conflict.
            report.conflict = True
            report.generation_status = "conflict"
            report.error_code = "lease_lost"
            report.error_codes.append("lease_lost")
            _finish_v119("interrupted")
            return report

        if pass_error:
            # An unresolved per-file stat/upsert error held the cursor: SUSPEND (partial) so the file is
            # retried; the generation is never marked complete with an unresolved observation (F-03).
            if not _transition_or_conflict(
                genrepo.mark_partial(
                    gid,
                    run_id,
                    cursor_json=json.dumps(last_cursor) if last_cursor else None,
                    last_error_code="metadata_walk_error",
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                ),
                "partial",
            ):
                return report
            report.error_code = report.error_code or "metadata_walk_error"
            report.bounded_out = True
            report.generation_status = "partial"
            _emit_progress("")
            _finish_v119("partial")
            return report

        if report.bounded_out:
            if not _transition_or_conflict(
                genrepo.mark_partial(
                    gid,
                    run_id,
                    cursor_json=json.dumps(last_cursor) if last_cursor else None,
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                ),
                "partial",
            ):
                return report
            report.generation_status = "partial"
            _emit_progress("")
            _finish_v119("partial")
            return report

        # A4: the walk exhausted, but this root holds a BLOCKING quarantine (a poison file reached the retry
        # threshold this pass or a prior one). The generation is NON-authoritative: do NOT complete the walk
        # or reconcile. Fail with ``quarantine_unresolved`` (a no-forward-progress code) so automatic workers
        # do not restart it until the operator resolves the quarantine (or policy changes / explicit restart).
        # Resolving the quarantine does NOT itself complete this generation — a fresh pass must verify the
        # walk and reconcile before the root becomes authoritative.
        if quarantine_repo.has_blocking(root.source_root_key):
            if not _transition_or_conflict(
                genrepo.fail_generation(
                    gid,
                    run_id,
                    last_error_code="quarantine_unresolved",
                    files_observed=files_observed,
                    metadata_upserted=metadata_upserted,
                    files_unchanged=files_unchanged,
                    errors_count=errors_count,
                ),
                "failed",
            ):
                return report
            report.error_code = "quarantine_unresolved"
            report.error_codes.append("quarantine_unresolved")
            report.generation_status = "failed"
            _finish_v119("failed")
            return report

        # Full metadata walk complete. Lease-fenced: if this write affects 0 rows we lost ownership after
        # the final batch (stale-lease takeover) — do NOT proceed to reconcile/complete under a lease we no
        # longer hold (finding 6); close the pass as a retryable conflict and let the new owner finish.
        if (
            genrepo.mark_metadata_walk_complete(
                gid,
                run_id,
                files_observed=files_observed,
                metadata_upserted=metadata_upserted,
                files_unchanged=files_unchanged,
                errors_count=errors_count,
            )
            == 0
        ):
            report.conflict = True
            report.generation_status = "conflict"
            report.error_code = "lease_lost"
            report.error_codes.append("lease_lost")
            _finish_v119("interrupted")
            return report

    # Empty-root / lost-mount blast-radius sentinel (F-01): if this generation observed ZERO files yet the
    # index still holds MORE THAN the configured threshold of active rows, the root most likely vanished
    # (share unmounted / empty mountpoint that reads as an accessible-but-empty directory) — reconciling
    # would MASS-delete valid records. Fail closed (no reconciliation) and require operator confirmation. A
    # genuine emptying at/under the threshold still reconciles (bounded, low blast radius). Permission/I/O
    # read errors are handled independently upstream (directory_read_error → suspend).
    empty_guard = int(getattr(config, "source_index_empty_root_delete_threshold", 50))
    if files_observed == 0 and repo.count_source_files(root.source_root_key) > empty_guard:
        if not _transition_or_conflict(
            genrepo.fail_generation(
                gid,
                run_id,
                last_error_code="empty_root_guard",
                files_observed=files_observed,
                metadata_upserted=metadata_upserted,
                files_unchanged=files_unchanged,
                errors_count=errors_count,
            ),
            "failed",
        ):
            return report
        report.error_code = "empty_root_guard"
        report.error_codes.append("empty_root_guard")
        report.generation_status = "failed"
        _finish_v119("failed")
        return report

    # ---- Phase 2: generation-based deletion reconciliation (source_id keyset, 3-outcome probe) ----
    # Each batch: probe every candidate (present survivor / confirmed-absent / indeterminate), then apply the
    # resolvable PREFIX atomically (deletes + survivor refreshes + reconcile-cursor checkpoint in one txn).
    # The FIRST indeterminate (permission/IO/symlink/non-regular) stops the batch and leaves the generation
    # reconcile_pending — only a CONFIRMED absence is ever deleted, and completeness is never falsely certified.
    # Reconciliation ALWAYS restarts its keyset sweep from the beginning (after_sid=None), never trusting a
    # persisted `reconcile_cursor_json`. That checkpoint is not needed for correctness — the stale-candidate
    # query is SELF-LIMITING: a resolved survivor is stamped with this generation and a confirmed-absent row
    # is marked deleted, so both drop OUT of the candidate set immediately; a resume from None re-selects
    # only the still-unresolved rows. Trusting a persisted `after` is exactly what a corrupted/forged value
    # could exploit — a malformed payload could crash the pass, and a forged-high value could skip earlier
    # stale rows yet let finish_completed certify reconciliation. Restarting is safe (idempotent) and cheap
    # (index scan bounded by the shrinking candidate set); the keyset below is a within-phase optimization
    # only. The persisted cursor is still written for diagnostics but never read back as a trust anchor.
    after_sid: str | None = None
    committed_after_sid: str | None = None
    try:
        while True:
            cands = repo.stale_candidates_batch(
                root.source_root_key, gid, gen_started, after_source_id=after_sid, limit=batch_size
            )
            if not cands:
                break
            # (sid, rel, action, preserve, restale_notes)
            resolved: list[tuple[str, str, str, bool, bool]] = []
            blocked = False
            for sid, rel in cands:
                abs_c = root_path / rel
                verdict = _probe_candidate(abs_c, root_path)
                if verdict == "indeterminate":
                    blocked = True
                    break
                if verdict == "absent":
                    resolved.append((sid, rel, "delete", False, False))
                    continue
                # A present file that is now EXCLUDED/ignored by CURRENT policy is a POLICY REMOVAL, not a
                # survivor: a newly-added exclusion prunes it from the walk, so at reconcile it must be
                # DEACTIVATED from the index (the source file itself is never touched) — otherwise its record
                # stays active/searchable forever (finding: exclusion changes).
                if should_ignore(rel, abs_c.name) or is_excluded_source_path(rel, config):
                    resolved.append((sid, rel, "delete", False, False))
                    continue
                # present survivor: preserve valid content when the file is physically unchanged.
                try:
                    st = abs_c.stat()
                except OSError:
                    blocked = True
                    break
                ext = abs_c.suffix.lower().lstrip(".")
                recomputed = extraction_disposition(ext, st.st_size, config)
                p = repo.load_metadata_state_batch(root.source_root_key, [rel]).get(rel)
                stat_match = (
                    p is not None and p["mtime"] == st.st_mtime_ns and p["size"] == st.st_size
                )
                disp_match = p is not None and p["disposition"] == recomputed
                # A project re-route (key/number change) does NOT block preserve — preserve rebuilds the
                # project relationship authoritatively — but it IS a MATERIAL derived-state change, so the
                # generated card must be re-staled even under preserve (finding 3), same as the walk path.
                cur_pk, cur_num, _conf = match_path_to_project(rel)
                proj_match = (
                    p is not None
                    and p.get("project_key") == cur_pk
                    and p.get("project_number") == cur_num
                )
                mode = p.get("content_mode") if p is not None else "none"
                sensitive = bool(getattr(root, "sensitive", False))
                sens_ok = not (
                    (sensitive and mode == "plain") or ((not sensitive) and mode == "vault")
                )
                # A survivor keeps its content when the content is still valid; a project re-route or a
                # fingerprint change is rebuilt authoritatively by preserve, and only an owed sensitivity
                # re-secure or a disposition flip forces a content-clearing replace.
                preserve = bool(stat_match and disp_match and sens_ok)
                restale = (not preserve) or (not proj_match)
                resolved.append((sid, rel, "refresh", preserve, restale))
            if resolved:
                with open_connection(repo.db_path) as c, transaction(c):
                    for sid, rel, action, preserve, restale in resolved:
                        if action == "delete":
                            repo.mark_deleted_by_source_id(sid, conn=c, in_transaction=True)
                            deleted_count += 1
                            report.deleted += 1
                        else:
                            # A survivor refresh that FAILS raises out of this txn → caught below and the
                            # generation is left reconcile_pending (never certified complete with an
                            # unresolved survivor). A bare last-seen stamp is forbidden — a full upsert
                            # (content preserved when unchanged) is the only thing that clears the candidate.
                            # raise_on_error + a None-guard mean a second-stat race here never silently
                            # advances the reconcile cursor past an unresolved survivor.
                            out = _index_source_metadata(
                                root_path / rel,
                                root,
                                repo,
                                config,
                                generation_id=gid,
                                preserve_content=preserve,
                                policy_fingerprint=fingerprint,
                                raise_on_error=True,
                                conn=c,
                                in_transaction=True,
                            )
                            if out.source_id is None:
                                raise RuntimeError("survivor_refresh_no_source_id")
                            # Material derived-state change on a survivor (content replaced, or project
                            # re-routed even under preserve) re-stales its generated card (finding 3).
                            if restale:
                                repo._mark_generated_notes_stale(c, out.source_id)
                    affected = genrepo.advance_reconcile_cursor(
                        gid,
                        run_id,
                        reconcile_cursor_json=json.dumps({"after": resolved[-1][0]}),
                        conn=c,
                        in_transaction=True,
                        deleted_count=deleted_count,
                    )
                    if affected == 0:
                        raise _LeaseLost()
                after_sid = resolved[-1][0]
                committed_after_sid = after_sid
            if blocked:
                if not _transition_or_conflict(
                    genrepo.mark_reconcile_pending(
                        gid,
                        run_id,
                        reconcile_cursor_json=json.dumps({"after": committed_after_sid}),
                        last_error_code="reconcile_indeterminate",
                        deleted_count=deleted_count,
                    ),
                    "reconcile_pending",
                ):
                    return report
                report.error_code = "reconcile_indeterminate"
                report.error_codes.append("reconcile_indeterminate")
                report.generation_status = "reconcile_pending"
                _finish_v119("partial")
                return report
    except _LeaseLost:
        report.conflict = True
        report.generation_status = "conflict"
        report.error_code = "lease_lost"
        report.error_codes.append("lease_lost")
        _finish_v119("interrupted")
        return report
    except (
        Exception
    ) as exc:  # a survivor refresh failed → resolvable later; never a false completion
        report.errors += 1
        report.error_codes.append(type(exc).__name__)
        report.error_code = "survivor_refresh_failed"
        if not _transition_or_conflict(
            genrepo.mark_reconcile_pending(
                gid,
                run_id,
                reconcile_cursor_json=json.dumps({"after": committed_after_sid}),
                last_error_code="survivor_refresh_failed",
                deleted_count=deleted_count,
            ),
            "reconcile_pending",
        ):
            return report
        report.generation_status = "reconcile_pending"
        _finish_v119("partial")
        return report

    # Lease-fenced completion: 0 rows means the lease was lost after the final reconcile batch — the new
    # owner is authoritative, so we must NOT report this pass as the completing one (finding 6).
    if (
        genrepo.finish_completed(
            gid,
            run_id,
            files_observed=files_observed,
            metadata_upserted=metadata_upserted,
            files_unchanged=files_unchanged,
            errors_count=errors_count,
            deleted_count=deleted_count,
        )
        == 0
    ):
        report.conflict = True
        report.generation_status = "conflict"
        report.error_code = "lease_lost"
        report.error_codes.append("lease_lost")
        _finish_v119("interrupted")
        return report
    report.completed = True
    report.generation_status = "completed"
    _emit_progress("")
    _finish_v119("completed")
    return report


def _auto_generate(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    source_id: str,
    root: ExternalSourceRoot,
    *,
    summaries_remaining: int,
    disposition: "SourceValue | None" = None,
) -> tuple[int, int]:
    """Policy-driven card/summary generation after a successful index.

    Returns ``(cards_generated, summaries_generated)`` (each 0 or 1) so the caller can enforce
    per-drain caps. NEVER raises — an auto-gen failure must not fail the index/rebuild event
    (indexing already succeeded); a failure is counted as 0 (a skip). Sensitive roots get a card
    (preview withheld by the renderer) but never an advisory summary. Vault writes go through the
    existing write-policy in ``source_notes``.

    The PM Source Value disposition (A1.11) gates auto-card/auto-summary: only AUTO_CARD_HIGH/NORMAL
    (or METADATA_ONLY when explicitly enabled) auto-card. Deferred/unsupported/metadata are a
    deliberate skip, not an error; manual generation can still override a deferred source.
    """
    from . import source_notes  # lazy import to avoid a module cycle

    detail = repo.get_source_detail(source_id)
    if detail is None or detail.get("deleted") or detail["source_kind"] == "obsidian_note":
        return 0, 0
    if disposition is None:
        disposition = classify_source_value(detail, config)
    if not disposition.allow_auto_card:
        return 0, 0
    kind = detail["source_kind"]

    want_card = (
        getattr(config, "source_card_auto_generate_enabled", False)
        and kind in getattr(config, "source_card_auto_generate_kinds", [])
        and getattr(config, "source_card_generation_enabled", True)
    )
    want_refresh = getattr(config, "source_note_auto_refresh_enabled", True)
    cards = 0
    if want_card or (want_refresh and repo.has_generated_note(source_id)):
        try:
            source_notes.generate_source_card(
                repo, config, source_id=source_id, overwrite=True, principal_kind="local"
            )
            cards = 1
        except Exception:  # noqa: BLE001 - card generation is best-effort; a failure is a skip
            _logger.warning(
                "source_index.auto_card_error",
                extra={"obsidian_mcp": {"root": root.source_root_key}},
            )

    want_summary = (
        summaries_remaining > 0
        and disposition.allow_auto_summary
        and getattr(config, "source_summary_auto_generate_enabled", False)
        and getattr(config, "source_summary_enabled", True)
        and kind in getattr(config, "source_summary_auto_generate_kinds", [])
        and not getattr(root, "sensitive", False)
    )
    if want_summary:
        try:
            out = source_notes.summarize_source(
                repo, config, source_id=source_id, principal_kind="local"
            )
        except Exception:  # noqa: BLE001 - advisory summary is best-effort
            return cards, 0
        if out.get("summarized"):
            return cards, 1
    return cards, 0


def _unsupported_exts(config: ObsidianMcpConfig) -> set[str]:
    return {
        _ext_norm(e) for e in (getattr(config, "source_index_unsupported_file_types", []) or [])
    }


def _order_eligible_sources(
    repo: SourceIndexRepository, config: ObsidianMcpConfig, source_ids: list[str]
) -> list[tuple[str, SourceValue]]:
    """Filter to auto_card-eligible sources and order them by PM value (deterministic).

    HIGH before NORMAL via ``priority_score``; ties broken by ``rel_path`` for stable ordering.
    In-memory over this scan's source list only — NOT a persistent DB queue-priority model.
    """
    eligible: list[tuple[int, str, str, SourceValue]] = []
    for sid in source_ids:
        detail = repo.get_source_detail(sid)
        if not detail:
            continue
        disp = classify_source_value(detail, config)
        if disp.allow_auto_card:
            eligible.append((disp.priority_score, str(detail.get("rel_path") or ""), sid, disp))
    eligible.sort(key=lambda t: (t[0], t[1]))
    return [(sid, disp) for _score, _rel, sid, disp in eligible]


def drain_queue(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, batch: int = 50) -> int:
    """Process queued events (called by the watcher worker / rebuild path). Returns processed count.

    Auto-generation is bounded BOTH by count and time: advisory summaries by
    ``source_summary_auto_max_per_drain`` and deterministic cards by ``source_card_auto_max_per_drain``
    per drain. A rebuild whose changed-file set exceeds the card budget generates up to the cap and
    re-enqueues the remainder as ``reindex_requested`` events, so work resumes on the next drain
    pass instead of blocking on one giant burst.
    """
    from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository

    from .source_scan_runner import run_scan

    roots = {r.source_root_key: r for r in config.external_sources}
    summary_cap = int(getattr(config, "source_summary_auto_max_per_drain", 5))
    card_cap = int(getattr(config, "source_card_auto_max_per_drain", 200))
    bstate = SourceIndexBootstrapRepository(repo.db_path)
    summaries_done = 0
    cards_done = 0
    processed = 0
    for event in repo.claim_queued(batch):
        try:
            if event["event_type"] == "rebuild":
                rebuild_status, rebuild_code = "done", None
                if event["source_root_key"] == _VAULT_ROOT_KEY:
                    scan_vault_notes(repo, config)
                else:
                    root = roots.get(event["source_root_key"])
                    if root and root.enabled:
                        # Rebuild runs through the common bounded/observed wrapper. A live-run conflict is
                        # retryable (re-enqueue, do not discard); a bounded pass indexes what it can then
                        # re-enqueues a COALESCED rebuild so the remainder resumes next drain.
                        run = run_scan(root, repo, config, bstate, mode="rebuild")
                        if run.conflict:
                            repo.enqueue_event(
                                event_type="rebuild", source_root_key=root.source_root_key
                            )
                            rebuild_status, rebuild_code = "skipped", BOUNDED_RESUME
                        else:
                            report = run.report
                            # Auto-generate per changed source AFTER the scan (partial OR complete).
                            # _auto_generate never raises, so a card/summary failure is a skip — it must
                            # not flip this rebuild event to error. PM-value ordering (A1.11): card only
                            # auto_card-eligible sources, HIGH before NORMAL (priority_score then rel_path).
                            src_ids = report.indexed_source_ids if report is not None else []
                            eligible = _order_eligible_sources(repo, config, src_ids)
                            budget = max(0, card_cap - cards_done)
                            for sid, disp in eligible[:budget]:
                                c, s = _auto_generate(
                                    repo,
                                    config,
                                    sid,
                                    root,
                                    summaries_remaining=summary_cap - summaries_done,
                                    disposition=disp,
                                )
                                cards_done += c
                                summaries_done += s
                            for sid, _disp in eligible[budget:]:
                                # Resume the remainder on a later drain (bounded, no giant burst).
                                with suppress(Exception):
                                    detail = repo.get_source_detail(sid)
                                    if detail and detail.get("rel_path"):
                                        repo.enqueue_event(
                                            event_type="reindex_requested",
                                            rel_path=detail["rel_path"],
                                            source_root_key=root.source_root_key,
                                        )
                            if run.status == "partial":
                                # Bounded-out: work remains. Coalesced re-enqueue (dedup keeps at most one
                                # queued rebuild per root) + a clean bounded-resume receipt — NEVER 'done'.
                                repo.enqueue_event(
                                    event_type="rebuild", source_root_key=root.source_root_key
                                )
                                rebuild_status, rebuild_code = "skipped", BOUNDED_RESUME
                            elif run.status == "failed":
                                rebuild_status, rebuild_code = "error", run.error_code
                repo.complete_event(event["event_id"], rebuild_status, error_code=rebuild_code)
            elif event["event_type"] == "deleted":
                rel_path = event["rel_path"]
                src_key = event.get("source_root_key")
                if not rel_path:
                    repo.complete_event(event["event_id"], "done")
                elif src_key == _VAULT_ROOT_KEY:
                    # The vault is always local/mounted: a vault-file deletion is a real user action,
                    # not a mount blip. Preserve existing behavior (no NAS-mount revalidation).
                    repo.mark_deleted("external_file", rel_path, source_root_key=src_key)
                    repo.complete_event(event["event_id"], "done")
                else:
                    # External (NAS) root: NEVER mark_deleted on an enqueued event alone. Between enqueue
                    # and drain the whole mount can drop — every candidate would then probe "absent" and
                    # mass-delete still-present rows. Revalidate: the root must be confirmed USABLE, then
                    # the file itself confirmed ABSENT. Anything else is a distinct, retryable skip.
                    root = roots.get(src_key)
                    if root is None:
                        repo.complete_event(
                            event["event_id"], "skipped", error_code="unconfigured_root"
                        )
                    else:
                        root_path = Path(root.path)
                        root_state = _probe_root_dir(root_path)
                        if root_state != "usable":
                            # absent/indeterminate root → the deletion is unproven (retry next reconcile)
                            repo.complete_event(
                                event["event_id"], "skipped", error_code="root_unavailable"
                            )
                        else:
                            probe = _probe_candidate(root_path / rel_path, root_path)
                            if probe == "absent":
                                repo.mark_deleted(
                                    "external_file", rel_path, source_root_key=src_key
                                )
                                repo.complete_event(event["event_id"], "done")
                            elif probe == "present":
                                repo.complete_event(
                                    event["event_id"], "skipped", error_code="still_present"
                                )
                            else:  # indeterminate → unproven, retry next reconcile
                                repo.complete_event(
                                    event["event_id"], "skipped", error_code="indeterminate"
                                )
            elif event["event_type"] == "moved":
                # Governed same-root rename/move (Phase B / B4 corrective). Placed BEFORE the path-policy
                # branches below (which key on the OLD rel_path) so a move is never mis-routed as an
                # excluded/deferred/unsupported skip. BOTH paths cross the queue trust boundary and are
                # canonically validated (no FS access) before any lookup/probe/mutation; terminal-invalid
                # payloads never mutate. All terminal completions are ownership-guarded (claim generation).
                expected_attempt = int(event.get("attempts") or 1)
                old_norm = normalize_moved_rel_path(event["rel_path"])
                new_norm = normalize_moved_rel_path(event.get("dest_rel_path"))
                src_key = event.get("source_root_key")
                if (old_norm is None or new_norm is None or old_norm == new_norm
                        or src_key == _VAULT_ROOT_KEY):
                    repo.complete_owned_event(
                        event["event_id"], "skipped",
                        expected_attempt=expected_attempt, error_code="moved_invalid",
                    )
                else:
                    root = roots.get(src_key)
                    if root is None or not getattr(root, "enabled", True):
                        repo.complete_owned_event(
                            event["event_id"], "skipped",
                            expected_attempt=expected_attempt, error_code="unconfigured_root",
                        )
                    else:
                        _apply_moved_event(
                            repo, config, event, root,
                            old_rel=old_norm, new_rel=new_norm, src_key=src_key,
                            expected_attempt=expected_attempt,
                        )
            elif (
                event["source_root_key"] == _VAULT_ROOT_KEY
                and event["rel_path"]
                and is_source_notes_path(event["rel_path"], config)
            ):
                # Self-index guard (drain backstop): a generated Source Notes card on the VAULT root
                # must never re-enter source processing. Scoped strictly to the vault root + the
                # configured source_notes_folder — an EXTERNAL root that merely contains a folder
                # named "Source Notes" is NOT caught here and is indexed normally below.
                repo.complete_event(
                    event["event_id"], "skipped", error_code=SOURCE_NOTES_SELF_INDEX_GUARD
                )
            elif (
                event["source_root_key"] == _VAULT_ROOT_KEY
                and event["rel_path"]
                and is_email_archive_path(event["rel_path"])
            ):
                # Self-index guard (drain backstop): a Phase-10E full-email archive note on the VAULT
                # root must never re-enter source processing (it holds full bodies/addresses). Scoped
                # to the vault root + the Email Archive/ prefix, mirroring the Source Notes guard above.
                repo.complete_event(
                    event["event_id"], "skipped", error_code=EMAIL_ARCHIVE_SELF_INDEX_GUARD
                )
            elif event["rel_path"] and is_excluded_source_path(event["rel_path"], config):
                # Excluded dependency/build path: skip cleanly (not an error, not indexed, no card).
                repo.complete_event(event["event_id"], "skipped", error_code=EXCLUDED_PATH)
            elif event["rel_path"] and is_deferred_source_path(event["rel_path"], config):
                # Deferred business record: index for search (no card/summary), mark a clear skip
                # receipt (NOT an error). _auto_generate also no-ops for deferred on the rebuild path.
                root = roots.get(event["source_root_key"])
                if root and event["rel_path"]:
                    with suppress(Exception):
                        index_source_file(Path(root.path) / event["rel_path"], root, repo, config)
                repo.complete_event(event["event_id"], "skipped", error_code=DEFERRED_PATH)
            elif event["rel_path"] and _ext_norm(
                Path(event["rel_path"]).suffix
            ) in _unsupported_exts(config):
                # Unsupported/placeholder type (.url/.aspx/screenshot/etc.): do NOT index (no fragile
                # parsing, no garbage rows). A clean policy skip, NOT an error.
                repo.complete_event(event["event_id"], "skipped", error_code=UNSUPPORTED_FILE_TYPE)
            else:  # created / modified / reindex_requested
                root = roots.get(event["source_root_key"])
                event_status, event_code = "done", None
                if root and event["rel_path"]:
                    source_id = index_source_file(
                        Path(root.path) / event["rel_path"], root, repo, config
                    )
                    if source_id is not None:
                        # PM-value gate (A1.11): card only auto_card-eligible sources. A metadata-only
                        # source that indexed cleanly is a successful policy skip (NOT an error).
                        detail = repo.get_source_detail(source_id)
                        disp = classify_source_value(detail, config) if detail else None
                        if disp is not None and disp.allow_auto_card:
                            # One card per single-file event (naturally bounded by the claim batch);
                            # the card_cap bounds the rebuild scan-burst, not per-file events.
                            c, s = _auto_generate(
                                repo,
                                config,
                                source_id,
                                root,
                                summaries_remaining=summary_cap - summaries_done,
                                disposition=disp,
                            )
                            cards_done += c
                            summaries_done += s
                        elif disp is not None and disp.skip_code:
                            event_status, event_code = "skipped", disp.skip_code
                repo.complete_event(event["event_id"], event_status, error_code=event_code)
            processed += 1
        except Exception as exc:
            repo.complete_event(event["event_id"], "error", error_code=type(exc).__name__)
    if cards_done or summaries_done:
        _logger.info(
            "source_index.drain_generated",
            extra={"obsidian_mcp": {"cards": cards_done, "summaries": summaries_done}},
        )
        with suppress(Exception):
            repo.record_generation_result(cards=cards_done, summaries=summaries_done)
    with suppress(Exception):
        repo.record_drain()
    return processed


def request_rebuild(repo: SourceIndexRepository, config: ObsidianMcpConfig) -> dict[str, Any]:
    """Enqueue a bounded rebuild per enabled root. NEVER scans inside the request."""
    enabled = [r for r in config.external_sources if r.enabled]
    if not getattr(config, "external_source_index_enabled", True):
        return {"accepted": False, "reason": "index_disabled", "roots_queued": 0}
    for root in enabled:
        repo.enqueue_event(event_type="rebuild", source_root_key=root.source_root_key)
    # Always (re)index the curated vault notes so broad search_vault is index-backed.
    repo.enqueue_event(event_type="rebuild", source_root_key=_VAULT_ROOT_KEY)

    # Drain off the request loop in a bounded one-shot thread, so an operator rebuild makes
    # progress even when the real-time watcher is OFF. claim_queued (queued->processing) makes
    # this safe to run alongside a live watcher worker without double-processing.
    def _drain() -> None:
        with suppress(Exception):
            while drain_queue(repo, config, batch=50) > 0:
                pass

    threading.Thread(target=_drain, name="source-rebuild-drain", daemon=True).start()
    return {
        "accepted": True,
        "roots_queued": len(enabled) + 1,
        "mode": "queued",
        "watch_enabled": bool(getattr(config, "external_source_watch_enabled", False)),
    }
