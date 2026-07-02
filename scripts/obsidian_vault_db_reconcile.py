#!/usr/bin/env python3
"""Read-only DB/vault reconciliation reporter (Phase 10L-A).

After manually deleting generated cards/archive notes from the vault, the
``source_intelligence_generated_notes`` rows still point at files that no longer exist. This tool reports
that drift — COUNT-ONLY and safe to commit — so an operator can decide whether to run the guarded
generated-artifact DB reset. It NEVER writes: the DB is opened read-only (``mode=ro``) and the vault is
only stat/globbed.

Safe (committable) output contains counts/enums only. Row-level detail (paths, source_ids) is written
ONLY to ``--local-sensitive-dir`` (git-ignored). A runtime-state fingerprint is captured before and after
the scan to prove the read-only guarantee.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from hb_assistant.obsidian_mcp import source_archive_paths as sap  # noqa: E402
from hb_assistant.obsidian_mcp.source_indexer import EMAIL_ARCHIVE_FOLDER  # noqa: E402

# Generated source cards always end with ``__<source_id12>.md`` (12 hex chars).
_CARD_SUFFIX_RE = re.compile(r"__[0-9a-f]{12}\.md$")
_SOURCE_NOTES_FOLDER_DEFAULT = "Source Notes"
_README_FOLDERS = tuple(f"{_SOURCE_NOTES_FOLDER_DEFAULT}/{d}" for d in sap.ARCHIVE_DOMAIN_FOLDERS) + tuple(
    f"{EMAIL_ARCHIVE_FOLDER}/{d}" for d in sap.ARCHIVE_DOMAIN_FOLDERS)


class ReconcileError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)


def _state_fingerprint(db: str) -> str:
    c = _ro(db)
    try:
        rows = c.execute(
            "SELECT state_key, state_value FROM source_intelligence_state ORDER BY state_key"
        ).fetchall()
    except sqlite3.OperationalError:
        return "no_state_table"
    finally:
        c.close()
    blob = "\n".join(f"{k}={v}" for k, v in rows)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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


def _readme_variants(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    out: list[str] = []
    for child in sorted(folder.iterdir()):
        if not child.is_file():
            continue
        low = child.name.lower()
        if low == "readme.md":
            continue
        stem = child.name[:-3] if low.endswith(".md") else child.name
        if low.startswith("readme") and stem.lower() != "readme":
            out.append(str(child.name))
    return out


def reconcile(db: str, vault_root: Path, source_notes_folder: str) -> dict[str, Any]:
    """Read-only scan. Returns {'safe': count-only dict, 'detail': row-level dict}."""
    folder = (source_notes_folder or _SOURCE_NOTES_FOLDER_DEFAULT).replace("\\", "/").strip("/")
    c = _ro(db)
    try:
        gen_rows = c.execute(
            "SELECT g.note_rel_path, g.generation_status, g.source_id "
            "FROM source_intelligence_generated_notes g "
            "WHERE g.generation_status IN ('generated','stale')"
        ).fetchall()
        source_count = int(c.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0])
        q_row = c.execute(
            "SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
            "FROM source_intelligence_events"
        ).fetchone()
        queue_queued, queue_processing = int(q_row[0] or 0), int(q_row[1] or 0)
        summary_source_ids = {r[0] for r in c.execute(
            "SELECT source_id FROM source_intelligence_summaries").fetchall()}
        dup_groups = c.execute(
            "SELECT m.content_sha256, COUNT(DISTINCT g.note_rel_path) AS n "
            "FROM source_intelligence_generated_notes g "
            "JOIN source_intelligence_metadata m ON m.source_id = g.source_id "
            "WHERE g.generation_status IN ('generated','stale') AND m.content_sha256 IS NOT NULL "
            "GROUP BY m.content_sha256 HAVING n > 1"
        ).fetchall()
    finally:
        c.close()

    tracked_paths: set[str] = set()
    missing_generated: list[dict[str, str]] = []
    missing_source_ids: set[str] = set()
    present_source_ids: set[str] = set()
    for rel, status, source_id in gen_rows:
        norm = _norm_rel(rel)
        if norm is None:
            continue
        tracked_paths.add(norm)
        if (vault_root / norm).exists():
            present_source_ids.add(source_id)
        else:
            missing_generated.append({"note_rel_path": norm, "generation_status": status,
                                      "source_id": source_id})
            missing_source_ids.add(source_id)

    # Vault source cards with no generated-note row (orphan cards on disk).
    orphan_cards: list[str] = []
    sn_dir = vault_root / folder
    if sn_dir.is_dir():
        for f in sorted(sn_dir.rglob("*.md")):
            rel = str(f.relative_to(vault_root)).replace("\\", "/")
            if _CARD_SUFFIX_RE.search(rel) and rel not in tracked_paths:
                orphan_cards.append(rel)

    # Stale summary rows tied to a source whose generated card(s) are ALL missing (unambiguous).
    stale_summaries = sorted(sid for sid in summary_source_ids
                             if sid in missing_source_ids and sid not in present_source_ids)

    # Archive notes: legacy (double-domain) vs corrected roots.
    legacy_archive: list[str] = []
    corrected_archive: list[str] = []
    ea_dir = vault_root / EMAIL_ARCHIVE_FOLDER
    if ea_dir.is_dir():
        for f in sorted(ea_dir.rglob("*.md")):
            rel = str(f.relative_to(vault_root)).replace("\\", "/")
            if sap.is_legacy_archive_path(rel):
                legacy_archive.append(rel)
            elif any(rel.startswith(f"{EMAIL_ARCHIVE_FOLDER}/{d}/") for d in sap.ARCHIVE_DOMAIN_FOLDERS):
                corrected_archive.append(rel)

    # Duplicate README variants across the six singleton folders.
    readme_variants: list[dict[str, Any]] = []
    for rel_folder in _README_FOLDERS:
        variants = _readme_variants(vault_root / rel_folder)
        if variants:
            readme_variants.append({"folder_rel": rel_folder, "variants": variants})

    safe = {
        "missing_generated_note_rows": len(missing_generated),
        "orphan_vault_cards": len(orphan_cards),
        "stale_summary_rows_tied_to_missing_cards": len(stale_summaries),
        "legacy_archive_notes": len(legacy_archive),
        "corrected_archive_notes": len(corrected_archive),
        "duplicate_readme_folders": len(readme_variants),
        "duplicate_readme_total": sum(len(r["variants"]) for r in readme_variants),
        "duplicate_source_card_groups": len(dup_groups),
        "duplicate_source_card_extra": sum(int(n) - 1 for _sha, n in dup_groups),
        "source_row_count": source_count,
        "queue_queued": queue_queued,
        "queue_processing": queue_processing,
    }
    detail = {
        "missing_generated": missing_generated,
        "orphan_vault_cards": orphan_cards,
        "stale_summary_source_ids": stale_summaries,
        "legacy_archive_notes": legacy_archive,
        "corrected_archive_notes": corrected_archive,
        "duplicate_readme_variants": readme_variants,
    }
    return {"safe": safe, "detail": detail}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only DB/vault reconciliation reporter (count-only safe).")
    p.add_argument("--db-path", required=True)
    p.add_argument("--vault-path", required=True)
    p.add_argument("--source-notes-folder", default=_SOURCE_NOTES_FOLDER_DEFAULT)
    p.add_argument("--json-output", default=None)
    p.add_argument("--markdown-report", default=None)
    p.add_argument("--local-sensitive-dir", default=None)
    args = p.parse_args(argv)

    db, vault_root = args.db_path, Path(args.vault_path)
    try:
        if not db or not Path(db).is_file():
            raise ReconcileError(f"DB path missing or not a file: {db!r}")
        if not vault_root.is_dir():
            raise ReconcileError(f"vault path missing or not a directory: {args.vault_path!r}")
        fp_before = _state_fingerprint(db)
        out = reconcile(db, vault_root, args.source_notes_folder)
        fp_after = _state_fingerprint(db)
    except ReconcileError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    safe = dict(out["safe"])
    safe["runtime_state_unchanged"] = (fp_before == fp_after)
    safe["mode"] = "read_only"

    if args.local_sensitive_dir:
        ev = Path(args.local_sensitive_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "vault-db-reconcile-detail-local-sensitive.json").write_text(
            json.dumps(out["detail"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_report:
        lines = ["# Vault/DB Reconcile (count-only)", ""]
        lines += [f"- {k}: {v}" for k, v in sorted(safe.items())]
        Path(args.markdown_report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
