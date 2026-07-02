"""Bounded subroot traversal safety (Phase 10L).

Lets the source indexers/probe walk explicitly-supplied, locally-available descendant folders even when
the SynologyDrive project **root** fails root-level enumeration (EINTR). Cloud-safe: all checks are
lexical or ``lstat``-based — no ``resolve()``/``realpath()``/open, so a dormant/on-demand path is never
dereferenced or hydrated.

Safety model:
- ``validate_subroot`` rejects absolute paths, ``..`` traversal, and source-root escape (lexical). These
  are operator errors → callers raise a refusal (exit 3).
- ``walk_files`` is symlink-safe: it never recurses into symlink directories, and every emitted file is
  re-checked to remain lexically inside ``source_root`` (else counted ``containment_rejected``). A
  subroot that is itself a symlink is the caller's responsibility to reject (``os.path.islink``).
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

_SCANDIR_RETRIES = 3


class SubrootError(Exception):
    """Invalid include-subroot (absolute / '..' / escapes source-root) — a refusal."""


def is_contained(source_root: Path, candidate: Path) -> bool:
    """True iff ``candidate`` is lexically equal to or under ``source_root`` (no realpath)."""
    root_n = os.path.normpath(str(source_root))
    cand_n = os.path.normpath(str(candidate))
    return cand_n == root_n or cand_n.startswith(root_n + os.sep)


def validate_subroot(source_root: Path, rel: str) -> Path:
    """Lexically validate a relative include-subroot; return the (unresolved) joined Path.

    Raises SubrootError for empty, absolute, ``..``-bearing, or escaping values.
    """
    raw = str(rel).strip().replace("\\", "/")
    if not raw:
        raise SubrootError("empty include-subroot")
    p = Path(raw)
    if p.is_absolute():
        raise SubrootError("absolute include-subroot rejected (must be relative to --source-root)")
    parts = [seg for seg in p.parts if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        raise SubrootError("'..' traversal in include-subroot rejected")
    joined = source_root.joinpath(*parts) if parts else source_root
    if not is_contained(source_root, joined):
        raise SubrootError("include-subroot escapes source-root")
    return joined


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
