#!/usr/bin/env python3
"""Guarded generated-artifact DB reset (Phase 10L-A).

After manual vault deletion, ``source_intelligence_generated_notes`` rows still claim cards that no
longer exist. This tool flips those rows' ``generation_status`` → ``not_generated`` (the existing enum
meaning "no card exists", which is now true). That is the REVERSIBLE reset: ``has_generated_note``
returns False for a ``not_generated`` row, so the source is treated as never-carded and regeneration
recreates the card (``record_generated_note`` upserts it back to ``generated``). It mirrors the existing
``retire_stale_obsidian_generated_notes.py`` transition, generalized to the approved Source-Notes and
Email-Archive prefixes.

It NEVER deletes source rows, source metadata/text/chunks, vault files, runtime JSON, or queue rows.
Advisory summary receipts are left untouched by default; ``--also-reset-orphaned-summaries`` deletes a
receipt ONLY when EVERY generated note for that source is missing (unambiguous) — ambiguous receipts are
always left and reported count-only.

DRY-RUN BY DEFAULT. ``--apply`` requires ALL of: ``--backup-db-path``, ``--confirm-db-path`` (==
``--db-path``), ``--confirm-reset-generated-artifact-rows``; a stopped backend (port 8000); and an empty
queue. Safe output is count-only; row-level detail goes to ``--local-sensitive-dir`` only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from hb_assistant.obsidian_mcp.source_indexer import EMAIL_ARCHIVE_FOLDER  # noqa: E402

BACKEND_PORT = 8000

# note_rel_path prefixes eligible for reset. Source-Notes cards are the real targets; the Email-Archive
# prefixes (incl. the legacy double-domain ``Work/Work``) are defensive — archive NOTES are not DB-tracked
# generated notes, so these normally match nothing, but any stray row under them is in-scope for cleanup.
APPROVED_PREFIXES = (
    "Source Notes/Work/", "Source Notes/Home/", "Source Notes/Shared/",
    f"{EMAIL_ARCHIVE_FOLDER}/Work/Work/", f"{EMAIL_ARCHIVE_FOLDER}/Work/",
    f"{EMAIL_ARCHIVE_FOLDER}/Home/", f"{EMAIL_ARCHIVE_FOLDER}/Shared/",
)


class ResetError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)


def _counts(db: str) -> dict[str, int]:
    c = _ro(db)
    try:
        source = int(c.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0])
        q = c.execute("SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
                      "FROM source_intelligence_events").fetchone()
        summaries = int(c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0])
        gen = {str(s): int(n) for s, n in c.execute(
            "SELECT generation_status, COUNT(*) FROM source_intelligence_generated_notes "
            "GROUP BY generation_status").fetchall()}
    finally:
        c.close()
    return {"source_rows": source, "queue_queued": int(q[0] or 0),
            "queue_processing": int(q[1] or 0), "summary_rows": summaries,
            "generated_generated": gen.get("generated", 0), "generated_stale": gen.get("stale", 0),
            "generated_not_generated": gen.get("not_generated", 0)}


def _norm_rel(rel: str | None) -> str | None:
    if rel is None or str(rel).strip() == "":
        return None
    raw = str(rel).replace("\\", "/")
    if raw.startswith("/"):
        return None
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _under_approved(norm_rel: str) -> bool:
    low = norm_rel.lower()
    return any(low.startswith(p.lower()) for p in APPROVED_PREFIXES)


def select_candidates(db: str, vault_root: Path) -> dict[str, Any]:
    """Read-only selection of missing-file generated-note rows under approved prefixes."""
    c = _ro(db)
    try:
        rows = c.execute(
            "SELECT generated_note_id, note_rel_path, generation_status, source_id "
            "FROM source_intelligence_generated_notes WHERE generation_status IN ('generated','stale')"
        ).fetchall()
    finally:
        c.close()
    candidates: list[dict[str, str]] = []
    skipped_not_approved = 0
    skipped_invalid = 0
    skipped_present = 0
    per_source_total: dict[str, int] = {}
    per_source_missing: dict[str, int] = {}
    for gid, rel, status, source_id in rows:
        per_source_total[source_id] = per_source_total.get(source_id, 0) + 1
        norm = _norm_rel(rel)
        if norm is None:
            skipped_invalid += 1
            continue
        if not _under_approved(norm):
            skipped_not_approved += 1
            continue
        if (vault_root / norm).exists():
            skipped_present += 1
            continue
        per_source_missing[source_id] = per_source_missing.get(source_id, 0) + 1
        candidates.append({"generated_note_id": gid, "note_rel_path": norm,
                           "generation_status": status, "source_id": source_id})
    # A source's summary is unambiguously orphaned only if ALL its generated notes are missing candidates.
    fully_orphaned_sources = sorted(
        sid for sid, miss in per_source_missing.items() if miss == per_source_total.get(sid, 0))
    return {"candidates": candidates, "skipped_not_approved": skipped_not_approved,
            "skipped_invalid": skipped_invalid, "skipped_present": skipped_present,
            "fully_orphaned_sources": fully_orphaned_sources}


def _safe_summary(mode: str, sel: dict[str, Any], before: dict[str, int],
                  after: dict[str, int] | None, reset_rows: int, reset_summaries: int,
                  ambiguous_summaries_left: int) -> dict[str, Any]:
    return {
        "mode": mode,
        "candidate_rows": len(sel["candidates"]),
        "skipped_not_approved": sel["skipped_not_approved"],
        "skipped_invalid_path": sel["skipped_invalid"],
        "skipped_file_present": sel["skipped_present"],
        "fully_orphaned_sources": len(sel["fully_orphaned_sources"]),
        "generated_note_rows_reset": reset_rows,
        "summary_rows_reset": reset_summaries,
        "ambiguous_summaries_left": ambiguous_summaries_left,
        "counts_before": before,
        "counts_after": after,
        "source_rows_unchanged": (after is None or before["source_rows"] == after["source_rows"]),
        "queue_unchanged": (after is None or (before["queue_queued"] == after["queue_queued"]
                                              and before["queue_processing"] == after["queue_processing"])),
        "transition": "generated|stale -> not_generated",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Reset missing-file generated-note rows to not_generated (dry-run default).")
    p.add_argument("--db-path", required=True)
    p.add_argument("--vault-path", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-db-path", default="")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-reset-generated-artifact-rows", action="store_true")
    p.add_argument("--also-reset-orphaned-summaries", action="store_true")
    p.add_argument("--require-empty-queue", dest="require_empty_queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--json-output", default=None)
    p.add_argument("--markdown-report", default=None)
    p.add_argument("--local-sensitive-dir", default=None)
    args = p.parse_args(argv)

    db, vault_root = args.db_path, Path(args.vault_path)
    try:
        if not db or not Path(db).is_file():
            raise ResetError(f"DB path missing or not a file: {db!r}")
        if not vault_root.is_dir():
            raise ResetError(f"vault path missing or not a directory: {args.vault_path!r}")
        sel = select_candidates(db, vault_root)
        before = _counts(db)
        # Ambiguous = a summary receipt exists but the source is NOT fully orphaned; always left.
        fully_orphaned = set(sel["fully_orphaned_sources"])
        candidate_sources = {c["source_id"] for c in sel["candidates"]}
        ambiguous_sources = candidate_sources - fully_orphaned

        reset_rows = reset_summaries = 0
        after: dict[str, int] | None = None
        if args.apply:
            if args.confirm_db_path != args.db_path:
                raise ResetError("--confirm-db-path must exactly match --db-path.")
            if not args.confirm_reset_generated_artifact_rows:
                raise ResetError("--apply requires --confirm-reset-generated-artifact-rows.")
            if not args.backup_db_path:
                raise ResetError("--apply requires --backup-db-path (a DB backup is mandatory).")
            if _backend_listening():
                raise ResetError("Refusing apply while a backend is listening on port 8000.")
            if args.require_empty_queue and (before["queue_queued"] or before["queue_processing"]):
                raise ResetError(
                    f"Refusing apply: queue not empty (queued={before['queue_queued']}, "
                    f"processing={before['queue_processing']}).")
            if len(sel["candidates"]) > args.limit:
                raise ResetError(
                    f"Candidate rows {len(sel['candidates'])} exceed --limit {args.limit}; review first.")

            backup_path = Path(args.backup_db_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db, backup_path)

            from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
            repo = SourceIndexRepository(db)
            for cand in sel["candidates"]:
                repo.set_generated_note_status(cand["generated_note_id"], "not_generated")
                reset_rows += 1
            if args.also_reset_orphaned_summaries:
                # Only unambiguously-orphaned sources; ambiguous receipts are never touched.
                for sid in sel["fully_orphaned_sources"]:
                    if repo.get_summary(sid) is not None:
                        repo.delete_summary(sid)
                        reset_summaries += 1
            after = _counts(db)

        result = _safe_summary("apply" if args.apply else "dry_run", sel, before, after, reset_rows,
                               reset_summaries, len(ambiguous_sources))
    except ResetError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    if args.local_sensitive_dir:
        ev = Path(args.local_sensitive_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"generated-artifact-reset-{result['mode']}-detail-local-sensitive.json").write_text(
            json.dumps({"candidates": sel["candidates"],
                        "fully_orphaned_sources": sel["fully_orphaned_sources"]},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_report:
        lines = [f"# Generated-artifact DB reset ({result['mode']})", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(result.items()) if not isinstance(v, dict)]
        Path(args.markdown_report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
