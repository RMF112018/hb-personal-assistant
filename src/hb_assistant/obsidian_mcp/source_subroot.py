"""Bounded subroot traversal safety (Phase 10L).

Lets the source indexers/probe walk explicitly-supplied, locally-available descendant folders even when
the SynologyDrive project **root** fails root-level enumeration (EINTR). Cloud-safe: all checks are
lexical or ``lstat``-based — no ``resolve()``/``realpath()``/open, so a dormant/on-demand path is never
dereferenced or hydrated.

Safety model:
- ``validate_subroot`` / ``validate_include_file`` reject absolute paths, ``..`` traversal, and
  source-root escape (lexical). These are operator errors → callers raise a refusal (exit 3).
- ``walk_files`` is symlink-safe: it never recurses into symlink directories, and every emitted file is
  re-checked to remain lexically inside ``source_root`` (else counted ``containment_rejected``). A
  subroot that is itself a symlink is the caller's responsibility to reject (``os.path.islink``).
- ``classify_include_file`` resolves an EXACT file by ``lstat`` only — never ``scandir``/``resolve``/open
  — so a directly-addressable file is processable even when its parent directory fails enumeration
  (EINTR), and a dormant/on-demand placeholder is never dereferenced or hydrated.
"""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

_SCANDIR_RETRIES = 3


class SubrootError(Exception):
    """Invalid include-subroot / include-file (absolute / '..' / escapes source-root) — a refusal."""


def is_contained(source_root: Path, candidate: Path) -> bool:
    """True iff ``candidate`` is lexically equal to or under ``source_root`` (no realpath)."""
    root_n = os.path.normpath(str(source_root))
    cand_n = os.path.normpath(str(candidate))
    return cand_n == root_n or cand_n.startswith(root_n + os.sep)


def validate_relative_under_root(source_root: Path, rel: str, *, kind: str = "path") -> Path:
    """Lexically validate a relative selector; return the (unresolved) joined Path.

    Shared core for both include-subroot and include-file. Raises SubrootError for empty, absolute,
    ``..``-bearing, or escaping values. ``kind`` only shapes the error message.
    """
    raw = str(rel).strip().replace("\\", "/")
    if not raw:
        raise SubrootError(f"empty include-{kind}")
    p = Path(raw)
    if p.is_absolute():
        raise SubrootError(f"absolute include-{kind} rejected (must be relative to --source-root)")
    parts = [seg for seg in p.parts if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise SubrootError(f"'..' traversal in include-{kind} rejected")
    joined = source_root.joinpath(*parts) if parts else source_root
    if not is_contained(source_root, joined):
        raise SubrootError(f"include-{kind} escapes source-root")
    return joined


def validate_subroot(source_root: Path, rel: str) -> Path:
    """Lexically validate a relative include-subroot; return the (unresolved) joined Path."""
    return validate_relative_under_root(source_root, rel, kind="subroot")


def validate_include_file(source_root: Path, rel: str) -> Path:
    """Lexically validate a relative include-file; return the (unresolved) joined Path.

    Same lexical safety as ``validate_subroot`` plus a refusal if the value names the source-root
    itself (an include-file must address a file, not the root directory). File existence / type /
    availability are classified later by :func:`classify_include_file` (lstat only).
    """
    joined = validate_relative_under_root(source_root, rel, kind="file")
    if os.path.normpath(str(joined)) == os.path.normpath(str(source_root)):
        raise SubrootError("include-file must name a file under source-root, not the root itself")
    return joined


def classify_include_file(path: os.PathLike[str] | str) -> str:
    """Classify an EXACT file path by ``lstat`` only (no scandir/resolve/open).

    Returns ``"missing"`` (cannot stat), ``"not_file"`` (directory / symlink / non-regular),
    ``"placeholder"`` (dataless on-demand: ``st_size>0`` and ``st_blocks==0``), or ``"readable"``
    (a genuinely-local regular file). Never opens the file, so nothing is hydrated/downloaded.
    """
    try:
        st = os.lstat(os.fspath(path))
    except OSError:
        return "missing"
    if stat.S_ISLNK(st.st_mode) or stat.S_ISDIR(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return "not_file"
    if st.st_size > 0 and getattr(st, "st_blocks", 1) == 0:
        return "placeholder"
    return "readable"


def load_source_manifest(path: os.PathLike[str] | str) -> list[str]:
    """Read a newline-delimited manifest; strip lines, drop blanks and ``#`` comments.

    Entries are raw relative selectors (validated by the caller against ``--source-root``). The manifest
    path and its entries are operator-local and must never appear in safe evidence.
    """
    text = Path(path).read_text(encoding="utf-8")
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def classify_manifest_entry(entry: str) -> str:
    """``"subroot"`` if the (stripped) entry ends with ``/``, else ``"file"``."""
    return "subroot" if entry.rstrip().endswith("/") else "file"


def _scandir_retry(path: os.PathLike[str] | str) -> tuple[list[os.DirEntry[str]] | None, OSError | None]:
    for attempt in range(_SCANDIR_RETRIES):
        try:
            with os.scandir(os.fspath(path)) as it:
                return list(it), None
        except OSError as exc:  # noqa: PERF203 - bounded retry loop
            if exc.errno == errno.EINTR and attempt < _SCANDIR_RETRIES - 1:
                continue
            return None, exc
    return None, None


def scandir_listable(path: Path) -> bool:
    """True iff ``os.scandir`` enumerates ``path`` without error (EINTR-retried)."""
    entries, err = _scandir_retry(path)
    return err is None and entries is not None


def _bump(stats: dict[str, int], exc: OSError | None) -> None:
    if exc is None:
        return
    if exc.errno == errno.EINTR:
        stats["interrupted_system_call_count"] += 1
    elif exc.errno in (errno.EACCES, errno.EPERM):
        stats["permission_error_count"] += 1
    else:
        stats["other_error_count"] += 1


def new_walk_stats() -> dict[str, int]:
    return {"listable": 0, "containment_rejected": 0, "symlink_dirs_skipped": 0,
            "interrupted_system_call_count": 0, "permission_error_count": 0, "other_error_count": 0}


def walk_files(base: Path, source_root: Path, *, max_files: int) -> tuple[list[Path], dict[str, int]]:
    """Symlink-safe, EINTR-resilient, containment-checked file walk starting at ``base``.

    Never recurses into symlink directories (counts ``symlink_dirs_skipped``). Every returned file is
    lexically inside ``source_root`` (others counted ``containment_rejected``). ``listable`` is 1 iff the
    base directory itself enumerated. Bounded by ``max_files``.
    """
    stats = new_walk_stats()
    files: list[Path] = []
    entries, err = _scandir_retry(base)
    if err is not None or entries is None:
        _bump(stats, err)
        return files, stats
    stats["listable"] = 1
    stack: list[list[os.DirEntry[str]]] = [entries]
    while stack and len(files) < max_files:
        ents = stack.pop()
        for entry in sorted(ents, key=lambda e: e.name):
            if len(files) >= max_files:
                break
            try:
                if entry.is_symlink():
                    # Never follow symlinks (dir or file) — count skipped symlink dirs.
                    try:
                        if entry.is_dir(follow_symlinks=True):
                            stats["symlink_dirs_skipped"] += 1
                    except OSError:
                        pass
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                _bump(stats, exc)
                continue
            if is_dir:
                sub, sub_err = _scandir_retry(entry.path)
                if sub_err is not None:
                    _bump(stats, sub_err)
                    continue
                if sub is not None:
                    stack.append(sub)
                continue
            if not is_contained(source_root, Path(entry.path)):
                stats["containment_rejected"] += 1
                continue
            files.append(Path(entry.path))
    return files, stats
