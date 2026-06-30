#!/usr/bin/env python3
"""Retire stale/pre-reset generated-note DB rows via a narrow status transition.

After the vault reset, `source_intelligence_generated_notes` rows still point at card files the
reset removed. This tool flips those rows' `generation_status` from `generated`/`stale` →
`not_generated` (the existing enum value meaning "no card exists"), which is now true. It is the
ONLY production-DB mutation this performs.

DRY-RUN BY DEFAULT. It never deletes rows/files/sources/events, never touches the quarantine or
external roots, and only reads the active vault (existence checks). Apply requires exact
path confirmations, a stopped backend, an empty queue, and a narrow candidate count.
"""

from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

BACKEND_PORT = 8000


class RetireError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _norm_folder(folder: str) -> str:
    return (folder or "Source Notes").replace("\\", "/").strip("/").lower()


def _normalize_rel(note_rel_path: str | None) -> tuple[str | None, str | None]:
    """Return (normalized_rel, reject_reason). reject_reason set → row must NOT be selected."""
    if note_rel_path is None or str(note_rel_path).strip() == "":
        return None, "empty"
    raw = str(note_rel_path).replace("\\", "/")
    if raw.startswith("/"):
        return None, "absolute_path"
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None, "parent_traversal"
    return "/".join(parts), None


def _under_source_notes(norm_rel: str, folder_norm: str) -> bool:
    rel = norm_rel.lower()
    return rel == folder_norm or rel.startswith(folder_norm + "/")


def _queue_counts(db: str) -> tuple[int, int]:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        row = c.execute(
            "SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
            "FROM source_intelligence_events"
        ).fetchone()
    finally:
        c.close()
    return int(row[0] or 0), int(row[1] or 0)


def _status_counts(db: str) -> dict[str, int]:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        rows = c.execute(
            "SELECT generation_status, COUNT(*) FROM source_intelligence_generated_notes "
            "GROUP BY generation_status"
        ).fetchall()
    finally:
        c.close()
    return {str(s): int(n) for s, n in rows}


def _has_columns(db: str) -> bool:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in c.execute(
            "PRAGMA table_info(source_intelligence_generated_notes)").fetchall()}
    finally:
        c.close()
    return {"generated_note_id", "note_rel_path", "generation_status"} <= cols


def select_candidates(db: str, active_vault: Path, source_notes_folder: str) -> dict[str, list]:
    """Read-only candidate selection. Returns dict with candidates + skipped buckets (no writes)."""
    folder_norm = _norm_folder(source_notes_folder)
    out: dict[str, list] = {
        "candidates": [],          # {generated_note_id, note_rel_path, generation_status}
        "skipped_invalid_path": [],
        "skipped_not_under_folder": [],
        "skipped_file_exists": [],
    }
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        rows = c.execute(
            "SELECT generated_note_id, note_rel_path, generation_status "
            "FROM source_intelligence_generated_notes "
            "WHERE generation_status IN ('generated','stale')"
        ).fetchall()
    finally:
        c.close()
    for gid, rel, status in rows:
        norm, reject = _normalize_rel(rel)
        if reject is not None:
            out["skipped_invalid_path"].append({"generated_note_id": gid, "reason": reject})
            continue
        if not _under_source_notes(norm, folder_norm):
            out["skipped_not_under_folder"].append({"generated_note_id": gid})
            continue
        # Active clean-vault card still on disk → NEVER retire it.
        if (active_vault / norm).exists():
            out["skipped_file_exists"].append({"generated_note_id": gid})
            continue
        out["candidates"].append(
            {"generated_note_id": gid, "note_rel_path": norm, "generation_status": status})
    return out


def _summary(mode: str, sel: dict[str, list], before: dict[str, int],
             after: dict[str, int] | None, retired: int) -> dict[str, Any]:
    """Path-free, count-only summary safe to commit."""
    return {
        "mode": mode,
        "candidate_count": len(sel["candidates"]),
        "skipped_invalid_path_count": len(sel["skipped_invalid_path"]),
        "skipped_not_under_folder_count": len(sel["skipped_not_under_folder"]),
        "skipped_file_exists_count": len(sel["skipped_file_exists"]),
        "retired_count": retired,
        "generation_status_before": before,
        "generation_status_after": after,
        "transition": "generated|stale -> not_generated",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Retire stale generated-note rows (status->not_generated; dry-run default).")
    p.add_argument("--db-path", required=True)
    p.add_argument("--active-vault-path", required=True)
    p.add_argument("--source-notes-folder", default="Source Notes")
    p.add_argument("--quarantine-path", default="")
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-active-vault-path", default="")
    p.add_argument("--confirm-quarantine-path", default="")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--json-output", default=None)
    args = p.parse_args(argv)

    db = args.db_path
    active_vault = Path(args.active_vault_path)
    try:
        if not db or not Path(db).is_file():
            raise RetireError(f"DB path missing or not a file: {db!r}")
        if not _has_columns(db):
            raise RetireError(
                "source_intelligence_generated_notes lacks required columns "
                "(generated_note_id/note_rel_path/generation_status) — stopping (diagnostic only).")

        sel = select_candidates(db, active_vault, args.source_notes_folder)
        before = _status_counts(db)

        if args.apply:
            # Exact-confirmation gates.
            if args.confirm_db_path != args.db_path:
                raise RetireError("--confirm-db-path must exactly match --db-path.")
            if args.confirm_active_vault_path != args.active_vault_path:
                raise RetireError("--confirm-active-vault-path must exactly match --active-vault-path.")
            if args.confirm_quarantine_path != args.quarantine_path:
                raise RetireError("--confirm-quarantine-path must exactly match --quarantine-path.")
            if _backend_listening():
                raise RetireError("Refusing apply while a backend is listening on port 8000.")
            q, pr = _queue_counts(db)
            if q != 0 or pr != 0:
                raise RetireError(f"Refusing apply: queue not empty (queued={q}, processing={pr}).")
            n = len(sel["candidates"])
            if n > args.limit:
                raise RetireError(f"Candidate count {n} exceeds --limit {args.limit}; review before apply.")
            # Narrow transition via the existing repository method (no new write path).
            from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
            repo = SourceIndexRepository(db)
            retired = 0
            for cand in sel["candidates"]:
                repo.set_generated_note_status(cand["generated_note_id"], "not_generated")
                retired += 1
            after = _status_counts(db)
            result = _summary("apply", sel, before, after, retired)
        else:
            result = _summary("dry_run", sel, before, None, 0)
    except RetireError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    # Local-sensitive candidate report (rel_paths) — evidence dir only, NOT for commit.
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"generated-note-retirement-{result['mode']}-candidates-local-sensitive.json").write_text(
            json.dumps({"candidates": sel["candidates"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (ev / f"generated-note-retirement-{result['mode']}-summary-safe.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
