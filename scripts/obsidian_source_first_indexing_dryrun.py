#!/usr/bin/env python3
"""Bounded, single-root first-indexing READINESS dry-run. STRICTLY read-only.

Walks ONE configured source root (bounded by --max-files / --max-seconds), classifies each candidate
by source-value disposition / document_type / domain using the SAME deterministic classifiers as
production, and reports counts. It performs NO DB writes, NO event enqueue, NO queue drain, NO card
generation, NO summaries, NO external mutation, and NEVER starts a backend. Symlinks are recorded but
never followed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


class DryRunError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _size_bucket(n: int | None) -> str:
    if n is None:
        return "unknown"
    for limit, label in ((10_240, "<10KB"), (1_048_576, "<1MB"),
                         (10_485_760, "<10MB"), (104_857_600, "<100MB")):
        if n < limit:
            return label
    return ">=100MB"


def _load_config(config_path: str):
    """Forward-compat load: filter unknown keys against the model (mirrors load_config_with_warnings)."""
    from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
    raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
    known = set(ObsidianMcpConfig.model_fields)
    filtered = {k: v for k, v in raw.items() if k in known}
    return ObsidianMcpConfig.model_validate(filtered)


def scan_root(root_path: Path, root_key: str, config: Any, *, max_files: int, max_seconds: float,
              include_hidden: bool, now_fn: Callable[[], float]) -> dict[str, Any]:
    """Read-only bounded walk + classification. Returns a result dict (safe summary + local detail)."""
    from hb_assistant.obsidian_mcp import source_analyzers
    from hb_assistant.obsidian_mcp.source_notes import _domain_for
    from hb_assistant.obsidian_mcp.source_value import classify_source_value

    by_disposition: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    by_ext: dict[str, int] = {}
    by_skip_reason: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    detail_rows: list[dict[str, Any]] = []
    examined = 0
    symlinks = 0
    cap_reached = False
    start = now_fn()

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        # Record + prune symlinked directories (never descend → never traverse outside the root).
        sdirs = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        symlinks += len(sdirs)
        if sdirs:
            dirnames[:] = [d for d in dirnames if d not in sdirs]
        for fname in sorted(filenames):
            if not include_hidden and fname.startswith("."):
                continue
            if examined >= max_files or (now_fn() - start) >= max_seconds:
                cap_reached = True
                break
            abs_path = Path(dirpath) / fname
            if abs_path.is_symlink():
                symlinks += 1
                continue  # recorded, never followed
            examined += 1
            try:
                rel = str(abs_path.relative_to(root_path))
            except ValueError:
                continue
            ext = abs_path.suffix.lower().lstrip(".")
            size = None
            with contextlib.suppress(OSError):
                size = os.lstat(abs_path).st_size
            detail = {"rel_path": rel, "file_ext": ext, "text_excerpt": "",
                      "source_root_key": root_key}
            sv = classify_source_value(detail, config)
            doc_type = source_analyzers.from_detail(detail).document_type
            domain = _domain_for(detail)
            disp = sv.disposition.value
            by_disposition[disp] = by_disposition.get(disp, 0) + 1
            by_doc_type[doc_type] = by_doc_type.get(doc_type, 0) + 1
            by_ext[ext or "(none)"] = by_ext.get(ext or "(none)", 0) + 1
            by_domain[domain] = by_domain.get(domain, 0) + 1
            if sv.skip_code:
                by_skip_reason[sv.skip_code] = by_skip_reason.get(sv.skip_code, 0) + 1
            detail_rows.append({"rel_path": rel, "ext": ext, "size_bucket": _size_bucket(size),
                                "disposition": disp, "document_type": doc_type, "domain": domain})
        if cap_reached:
            break

    elapsed = round(now_fn() - start, 3)
    summary = {
        "mode": "dry_run", "actions_taken": "none (read-only readiness scan)",
        "root_key": root_key, "files_examined": examined, "symlinks_recorded": symlinks,
        "cap_reached": cap_reached, "max_files": max_files, "max_seconds": max_seconds,
        "elapsed_seconds": elapsed,
        "counts_by_disposition": dict(sorted(by_disposition.items())),
        "counts_by_document_type": dict(sorted(by_doc_type.items())),
        "counts_by_extension": dict(sorted(by_ext.items())),
        "counts_by_domain": dict(sorted(by_domain.items())),
        "skipped_deferred_by_reason": dict(sorted(by_skip_reason.items())),
    }
    return {"summary": summary, "detail_rows": detail_rows}


def _resolve_root(config: Any, root_key: str, vault_path: Path) -> Path:
    roots = {r.source_root_key: r for r in getattr(config, "external_sources", []) or []}
    root = roots.get(root_key)
    if root is None:
        raise DryRunError(f"Root key {root_key!r} is not configured.")
    if not getattr(root, "enabled", False):
        raise DryRunError(f"Root key {root_key!r} is disabled; refusing to scan.")
    root_path = Path(root.path)
    name = root_path.name
    vault_resolved = vault_path.resolve(strict=False)
    rp = root_path.resolve(strict=False)
    if "QUARANTINED" in name or " - QUARANTINED - " in str(root_path):
        raise DryRunError("Root points at a quarantine path; refusing to scan.")
    if rp == vault_resolved or vault_resolved in rp.parents or rp in vault_resolved.parents:
        raise DryRunError("Root overlaps the active vault path; refusing to scan.")
    if not root_path.is_dir():
        raise DryRunError(f"Root path for {root_key!r} does not exist or is unmounted; refusing to scan.")
    return root_path


def _enabled_root_keys(config: Any) -> list[str]:
    return [r.source_root_key for r in getattr(config, "external_sources", []) or []
            if getattr(r, "enabled", False)]


def main(argv: list[str] | None = None, *, now_fn: Callable[[], float] = time.monotonic) -> int:
    p = argparse.ArgumentParser(description="Bounded single-root first-indexing readiness dry-run (read-only).")
    p.add_argument("--db-path", default=None, help="Accepted but never written (dry-run is read-only).")
    p.add_argument("--config-path", required=True)
    p.add_argument("--vault-path", required=True)
    p.add_argument("--root-key", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--max-files", type=int, default=500)
    p.add_argument("--max-seconds", type=float, default=120.0)
    p.add_argument("--include-hidden", action="store_true")
    p.add_argument("--json-output", default=None)
    args = p.parse_args(argv)

    try:
        config = _load_config(args.config_path)
        if not args.root_key:
            # No root selected → list enabled roots and exit WITHOUT scanning. Never auto-pick.
            out = {"mode": "list_roots", "enabled_root_keys": _enabled_root_keys(config),
                   "note": "Pass --root-key to scan exactly one root. No auto-fallback."}
            print(json.dumps(out, indent=2, sort_keys=True))
            return 0
        root_path = _resolve_root(config, args.root_key, Path(args.vault_path))
        result = scan_root(root_path, args.root_key, config, max_files=args.max_files,
                           max_seconds=args.max_seconds, include_hidden=args.include_hidden,
                           now_fn=now_fn)
    except DryRunError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    summary = result["summary"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        # Local-sensitive detail (rel paths) — NOT for commit.
        (ev / f"first-indexing-dryrun-{args.root_key}-detail-local-sensitive.json").write_text(
            json.dumps({"root_key": args.root_key, "rows": result["detail_rows"]}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        # Safe summary (counts only, root key only — no paths).
        (ev / f"first-indexing-dryrun-{args.root_key}-summary-safe.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
