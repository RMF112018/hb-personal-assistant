#!/usr/bin/env python3
"""Read-only source-root availability probe (Phase 10L Tropical audit).

Diagnoses why the project-corpus / eml selectors see 0 candidates under a SynologyDrive on-demand root.
Unlike ``sorted(root.rglob("*"))`` (which silently swallows a root-level scandir error and yields an
empty result indistinguishable from an empty folder), this walker uses a resilient manual ``os.scandir``
walk that **retries EINTR**, wraps every syscall, and **counts + skips** unreadable dirs/entries instead
of aborting — so it can tell "root not listable / dataless" apart from "reachable local files exist".

Read-only and hydration-safe:
- **stat-only by default** (``--read-probe-limit`` defaults to 0).
- byte-read probing (to prove genuine local availability) is opt-in and requires BOTH a positive
  ``--read-probe-limit`` AND ``--confirm-read-probe-local-files``.
- a byte-read is attempted ONLY on files classified fully-local (``st_blocks>0``, not dataless); a
  placeholder / online-only / dataless file is NEVER opened, so nothing is ever hydrated/downloaded.

Safe (committable) output is count-only. Row/path-level samples and raw errors go to
``--local-sensitive-dir`` only.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from hb_assistant.obsidian_mcp.source_subroot import (  # noqa: E402
    SubrootError,
    classify_include_file,
    classify_manifest_entry,
    is_contained,
    load_source_manifest,
    validate_include_file,
    validate_subroot,
)

# Mirrors scripts/obsidian_source_index_project_corpus.py::_DOC_EXTS and _EML_EXTS (kept in sync).
_DOC_EXTS = frozenset({
    ".pdf", ".doc", ".docx", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".xlsm", ".xlsb", ".csv",
    ".ods", ".ppt", ".pptx", ".eml", ".msg", ".xer", ".mpp", ".mpx", ".mpt", ".dwg", ".dxf",
    ".dwf", ".rvt", ".vsdx",
})
_EML_EXTS = frozenset({".eml"})
_SKIP_SUFFIX = (".tmp", ".lock", ".ds_store", ".ini")
_SCANDIR_RETRIES = 3


class ProbeError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _scandir(path: str) -> tuple[list[os.DirEntry[str]] | None, OSError | None]:
    """Resilient ``os.scandir`` returning (entries, error). Retries EINTR; never raises."""
    for attempt in range(_SCANDIR_RETRIES):
        try:
            with os.scandir(path) as it:
                return list(it), None
        except OSError as exc:  # noqa: PERF203 - bounded retry loop
            if exc.errno == errno.EINTR and attempt < _SCANDIR_RETRIES - 1:
                continue
            return None, exc
    return None, None  # unreachable, keeps type-checkers happy


def _is_temp(name: str) -> bool:
    low = name.lower()
    return name.startswith(("~$", ".")) or low.endswith(_SKIP_SUFFIX) or low == "icon\r"


def classify_readability(abs_path: str) -> str:
    """'readable' | 'placeholder' | 'missing' | 'read_error' (mirrors _select_*._readability)."""
    try:
        st = os.lstat(abs_path)
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "read_error"
    if st.st_size > 0 and getattr(st, "st_blocks", 1) == 0:
        return "placeholder"
    return "readable"


def _bump_error(counts: dict[str, int], exc: OSError) -> None:
    if exc.errno == errno.EINTR:
        counts["interrupted_system_call_count"] += 1
    elif exc.errno in (errno.EACCES, errno.EPERM):
        counts["permission_error_count"] += 1
    else:
        counts["other_error_count"] += 1


def probe(source_root: str, *, max_files: int, max_dirs: int, read_probe_limit: int,
          allow_read_probe: bool, include_subroots: list[Path] | None = None,
          include_files: list[Path] | None = None, include_files_requested_raw: int = 0,
          include_files_containment_rejected: int = 0,
          include_subroots_manifest_rejected: int = 0) -> dict[str, Any]:
    """Resilient read-only walk. Returns {'safe': count-only, 'detail': samples/errors}.

    When ``include_subroots`` is given, the file walk starts AT each bounded subroot (never the failing
    root), so locally-available descendants are seen even when the root won't enumerate. Symlink dirs are
    never followed; every candidate file is re-checked to stay lexically inside ``source_root``.

    When ``include_files`` is given, each EXACT file is classified by ``lstat`` only (no scandir, no
    open) — so a directly-addressable local file is confirmed even when its parent won't enumerate, and
    a placeholder is never opened (no hydration).
    """
    counts: dict[str, int] = {
        "directories_seen": 0, "files_seen": 0, "files_stat_ok": 0, "files_stat_failed": 0,
        "files_read_probe_ok": 0, "files_read_probe_failed": 0, "candidate_doc_ext_count": 0,
        "candidate_eml_count": 0, "unsupported_ext_count": 0, "temp_skipped_count": 0,
        "cloud_placeholder_or_unavailable_count": 0, "interrupted_system_call_count": 0,
        "permission_error_count": 0, "other_error_count": 0,
        "symlink_dirs_skipped": 0, "containment_rejected": 0,
    }
    detail: dict[str, list[str]] = {"error_dirs": [], "placeholder_samples": [],
                                    "candidate_samples": [], "read_probe_failures": []}
    root_path = Path(source_root)

    root_exists = os.path.lexists(source_root)
    try:
        root_is_dir = os.path.isdir(source_root)
    except OSError:
        root_is_dir = False
    root_entries, root_err = _scandir(source_root)
    root_listable = root_err is None and root_entries is not None
    if root_err is not None:
        _bump_error(counts, root_err)
        detail["error_dirs"].append(f"<root>: errno={root_err.errno}")

    subroot_mode = include_subroots is not None
    inc_requested = len(include_subroots) if include_subroots else 0
    inc_listable = inc_failed = 0
    stack: list[tuple[str, list[os.DirEntry[str]]]] = []
    if subroot_mode:
        for base in include_subroots or []:
            if base.is_symlink():  # symlink subroot is unusable/unsafe → report, skip
                inc_failed += 1
                continue
            entries, err = _scandir(os.fspath(base))
            if err is not None or entries is None:
                if err is not None:
                    _bump_error(counts, err)
                inc_failed += 1
                continue
            inc_listable += 1
            stack.append((os.fspath(base), entries))
    elif root_listable and root_entries is not None:
        stack.append((source_root, root_entries))

    while stack and counts["files_seen"] < max_files and counts["directories_seen"] <= max_dirs:
        _dirpath, entries = stack.pop()
        for entry in sorted(entries, key=lambda e: e.name):
            if counts["files_seen"] >= max_files:
                break
            try:
                if entry.is_symlink():  # never follow symlinks (dir or file)
                    try:
                        if entry.is_dir(follow_symlinks=True):
                            counts["symlink_dirs_skipped"] += 1
                    except OSError:
                        pass
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                _bump_error(counts, exc)
                continue
            if is_dir:
                counts["directories_seen"] += 1
                if counts["directories_seen"] > max_dirs:
                    break
                sub, sub_err = _scandir(entry.path)
                if sub_err is not None:
                    _bump_error(counts, sub_err)
                    if len(detail["error_dirs"]) < 50:
                        detail["error_dirs"].append(f"{entry.name}: errno={sub_err.errno}")
                    continue
                if sub is not None:
                    stack.append((entry.path, sub))
                continue

            # regular file
            counts["files_seen"] += 1
            if not is_contained(root_path, Path(entry.path)):
                counts["containment_rejected"] += 1
                continue
            if _is_temp(entry.name):
                counts["temp_skipped_count"] += 1
                continue
            status = classify_readability(entry.path)
            if status in ("missing", "read_error"):
                counts["files_stat_failed"] += 1
                continue
            counts["files_stat_ok"] += 1
            if status == "placeholder":
                counts["cloud_placeholder_or_unavailable_count"] += 1
                if len(detail["placeholder_samples"]) < 50:
                    detail["placeholder_samples"].append(entry.path)
                continue  # NEVER opened → no hydration

            ext = Path(entry.name).suffix.lower()
            supported = ext in _DOC_EXTS
            if ext in _EML_EXTS:
                counts["candidate_eml_count"] += 1
            elif supported:
                counts["candidate_doc_ext_count"] += 1
            else:
                counts["unsupported_ext_count"] += 1
            if supported and len(detail["candidate_samples"]) < 50:
                detail["candidate_samples"].append(entry.path)

            # Hydration-safe byte-read probe: readable (st_blocks>0) supported files ONLY, opt-in.
            if (allow_read_probe and supported
                    and counts["files_read_probe_ok"] + counts["files_read_probe_failed"]
                    < read_probe_limit):
                try:
                    with open(entry.path, "rb") as fh:
                        fh.read(1)
                    counts["files_read_probe_ok"] += 1
                except OSError as exc:
                    counts["files_read_probe_failed"] += 1
                    if len(detail["read_probe_failures"]) < 50:
                        detail["read_probe_failures"].append(f"{entry.name}: errno={exc.errno}")

    # Exact-file classification pass: lstat only — no scandir, no open (never hydrates).
    inc_f_lstat_ok = inc_f_selected = inc_f_missing = inc_f_not_files = inc_f_placeholder = 0
    inc_f_unsupported = 0
    for fp in include_files or []:
        cls = classify_include_file(fp)
        if cls != "missing":
            inc_f_lstat_ok += 1
        if cls == "missing":
            inc_f_missing += 1
            continue
        if cls == "not_file":
            inc_f_not_files += 1
            continue
        if cls == "placeholder":
            inc_f_placeholder += 1
            continue
        if Path(fp).suffix.lower() not in _DOC_EXTS:
            inc_f_unsupported += 1
            continue
        inc_f_selected += 1

    safe = {
        # legacy field names (back-compat) reflect whatever was walked (root OR subroots)
        "root_exists": bool(root_exists), "root_is_dir": bool(root_is_dir),
        "root_listable": bool(root_listable),
        # spec field names (Phase 10L bounded-subroot audit)
        "source_root_exists": bool(root_exists), "source_root_listable": bool(root_listable),
        "include_subroots_requested": inc_requested,
        "include_subroots_listable": inc_listable,
        "include_subroots_failed": inc_failed + include_subroots_manifest_rejected,
        "include_files_requested_raw": include_files_requested_raw,
        "include_files_validated": len(include_files or []),
        "include_files_lstat_ok": inc_f_lstat_ok,
        "include_files_selected_readable": inc_f_selected,
        "include_files_missing": inc_f_missing,
        "include_files_not_files": inc_f_not_files,
        "include_files_unavailable_or_placeholder": inc_f_placeholder,
        "include_files_unsupported_ext": inc_f_unsupported,
        "include_files_containment_rejected": include_files_containment_rejected,
        "files_seen_under_include_subroots": counts["files_seen"] if subroot_mode else 0,
        "candidate_doc_ext_count_under_include_subroots":
            counts["candidate_doc_ext_count"] if subroot_mode else 0,
        "candidate_eml_count_under_include_subroots":
            counts["candidate_eml_count"] if subroot_mode else 0,
        "unavailable_or_placeholder_count": counts["cloud_placeholder_or_unavailable_count"],
        "read_probe_mode": "byte_read" if allow_read_probe else "stat_only",
        **counts,
    }
    return {"safe": safe, "detail": detail}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only source-root availability probe (stat-only default).")
    p.add_argument("--source-root", required=True)
    p.add_argument("--include-subroot", action="append", default=[],
                   help="bounded relative subroot under --source-root (repeatable); walk starts at the "
                        "subroot so locally-available descendants are seen even when the root won't list")
    p.add_argument("--include-file", action="append", default=[],
                   help="exact relative file under --source-root (repeatable); classified by lstat only "
                        "(no parent listing, no open) to confirm a directly-addressable local file even "
                        "when its parent won't enumerate")
    p.add_argument("--source-manifest", default=None,
                   help="path to a newline-delimited manifest of relative selectors under --source-root "
                        "(a line ending in '/' is a subroot, else an exact file; '#' comments and blank "
                        "lines ignored). The manifest path and its entries are operator-local and never "
                        "appear in safe evidence.")
    p.add_argument("--max-files", type=int, default=500)
    p.add_argument("--max-dirs", type=int, default=20000)
    p.add_argument("--read-probe-limit", type=int, default=0)
    p.add_argument("--confirm-read-probe-local-files", action="store_true")
    p.add_argument("--json-output", default=None)
    p.add_argument("--markdown-report", default=None)
    p.add_argument("--local-sensitive-dir", default=None)
    args = p.parse_args(argv)

    try:
        allow_read_probe = args.read_probe_limit > 0 and args.confirm_read_probe_local_files
        if args.read_probe_limit > 0 and not args.confirm_read_probe_local_files:
            raise ProbeError(
                "--read-probe-limit>0 requires --confirm-read-probe-local-files (byte-read is opt-in; "
                "stat-only is the default and only fully-local files are ever opened).")
        src = Path(args.source_root)
        try:
            subroots = [validate_subroot(src, s) for s in (args.include_subroot or [])]
        except SubrootError as exc:
            raise ProbeError(f"invalid --include-subroot: {exc}") from None
        try:
            include_files = [validate_include_file(src, s) for s in (args.include_file or [])]
        except SubrootError as exc:
            raise ProbeError(f"invalid --include-file: {exc}") from None
        inc_files_raw = len(args.include_file or [])
        inc_files_rejected = 0
        subroots_manifest_rejected = 0
        if args.source_manifest:
            try:
                entries = load_source_manifest(args.source_manifest)
            except OSError as exc:
                raise ProbeError(f"cannot read --source-manifest: {exc}") from None
            for entry in entries:
                if classify_manifest_entry(entry) == "subroot":
                    try:
                        subroots.append(validate_subroot(src, entry))
                    except SubrootError:
                        subroots_manifest_rejected += 1
                else:
                    inc_files_raw += 1
                    try:
                        include_files.append(validate_include_file(src, entry))
                    except SubrootError:
                        inc_files_rejected += 1
        # No subroots (empty) → normal root-walk mode + exact-file classification (no dir listing needed).
        out = probe(args.source_root, max_files=args.max_files, max_dirs=args.max_dirs,
                    read_probe_limit=args.read_probe_limit, allow_read_probe=allow_read_probe,
                    include_subroots=subroots or None, include_files=include_files or None,
                    include_files_requested_raw=inc_files_raw,
                    include_files_containment_rejected=inc_files_rejected,
                    include_subroots_manifest_rejected=subroots_manifest_rejected)
    except ProbeError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    safe = out["safe"]
    if args.local_sensitive_dir:
        ev = Path(args.local_sensitive_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "source-root-probe-detail-local-sensitive.json").write_text(
            json.dumps(out["detail"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_report:
        lines = ["# Source-root availability probe (count-only)", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(safe.items())]
        Path(args.markdown_report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
