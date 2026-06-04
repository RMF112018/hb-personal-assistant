"""Phase 09 Prompt 09 — approved Obsidian linkage proof (read-only, gap G-07).

Verifies that the approved Obsidian index (the V26 ``obsidian_index_*`` tables) carries
**canonical source references** and resolvable note-to-note **linkage** without ever
persisting raw content. Concretely, the proof checks that, for the latest index manifest:

* every no-raw / no-writeback ``CHECK(... = 0)`` guard column on
  ``obsidian_index_manifests`` sums to zero (no raw bodies / prompts / URLs / writeback);
* every indexed entry preserves its canonical refs — ``content_hash``, ``section_marker``,
  and a parseable ``source_refs_json`` carrying ``review_tier`` + ``confidence_class`` +
  ``review_status`` (review tier / confidence class / freshness metadata preserved);
* every entry's ``approved_root_label`` is inside the policy's approved roots — an
  out-of-policy / unapproved note appearing in the index is a hard failure (stop
  condition); and
* each ``[[wikilink]]`` (stored only as a redacted target hash) is classified as
  **resolved** (target note name is indexed in the same manifest), **broken** (no such
  target), or **stale_unknown** (unresolved on an entry already flagged stale). Broken /
  stale links are surfaced as advisory **source-coverage warnings**, never a final
  determination, so they do not by themselves fail the proof.

The verifier is **read-only** — it opens the database read-only and never writes. It is
database-path agnostic so it can run over the operator DB (empty G-07 substrate → an
honest ``populated = False`` posture), a controlled proof DB, or a temporary test DB. A
companion :func:`write_linkage_fixture_vault` writes a throwaway fixture vault (approved +
unapproved notes, resolved + broken wikilinks) into a caller-supplied temp directory so
tests and the evidence driver can populate a proof DB via the existing approved indexer
without ever touching the operator DB or the real vault.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .obsidian_index.policy import (
    ObsidianIndexPolicyError,
    load_obsidian_index_policy,
)

_MANIFEST_TABLE = "obsidian_index_manifests"
_ENTRY_TABLE = "obsidian_index_entries"

# Safe (redacted / structured) columns scanned for forbidden raw-content shapes.
_SCAN_COLUMNS: tuple[str, ...] = ("note_path_redacted", "heading_redacted", "source_refs_json")

# Canonical-source-ref columns that must be present (non-empty) on every indexed entry.
_REQUIRED_REF_COLUMNS: tuple[str, ...] = (
    "content_hash",
    "section_marker",
    "confidence_class",
    "review_status",
)
# Canonical refs that live inside the source_refs_json blob.
_REQUIRED_META_KEYS: tuple[str, ...] = ("review_tier", "approved_root_label")

# Forbidden raw-content value shapes (never echo a match — only the table.column).
_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token|sig=)=[A-Za-z0-9%._-]{16,}"
    r"|https?://[^\s\"']*[?&](sig|token)=",
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    return [
        c
        for c in cols
        if c.endswith("_persisted") or c.endswith("_performed") or c.endswith("_allowed")
    ]


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _latest_manifest_id(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute(
        f"SELECT manifest_id FROM {_MANIFEST_TABLE} "
        "ORDER BY (mode = 'apply') DESC, generated_utc DESC, manifest_id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return str(row[0]) if row is not None else None


def build_obsidian_linkage_proof(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only approved-Obsidian linkage proof.

    Returns a structured dict with the latest manifest's entry count, guard-column sum
    (must be 0), canonical-ref preservation, approved-only verdict, the resolved / broken /
    stale-unknown link classification, advisory source-coverage warnings, a forbidden-raw
    scan, and the overall ``proof_passed`` / ``populated`` verdicts. Never writes.
    """
    resolved = db_path or str(PathPolicy().get_db_path())

    # Approved-roots policy (fail-closed: a missing/unloadable policy cannot validate
    # approved-only indexing, so the proof must not pass).
    policy_loaded = True
    policy_error: str | None = None
    approved_roots: set[str] = set()
    policy_version: str | None = None
    try:
        policy = load_obsidian_index_policy()
        approved_roots = set(policy.approved_roots)
        policy_version = policy.version
    except ObsidianIndexPolicyError as exc:
        policy_loaded = False
        policy_error = type(exc).__name__

    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        manifest_present = _table_exists(conn, _MANIFEST_TABLE)
        entry_present = _table_exists(conn, _ENTRY_TABLE)

        # Guard-column sum across every manifest row (no raw body / URL / writeback).
        guard_cols = _guard_columns(conn, _MANIFEST_TABLE) if manifest_present else []
        manifest_count = (
            int(conn.execute(f"SELECT COUNT(*) FROM {_MANIFEST_TABLE}").fetchone()[0])
            if manifest_present
            else 0
        )
        guard_sum = 0
        if guard_cols and manifest_count:
            expr = "+".join(f"COALESCE(SUM({c}),0)" for c in guard_cols)
            guard_sum = int(conn.execute(f"SELECT {expr} FROM {_MANIFEST_TABLE}").fetchone()[0])

        manifest_id = _latest_manifest_id(conn) if manifest_present else None

        entries: list[dict[str, Any]] = []
        if entry_present and manifest_id is not None:
            entry_cols = _columns(conn, _ENTRY_TABLE)
            wanted = [
                c
                for c in (
                    "note_path_redacted",
                    "heading_redacted",
                    "section_marker",
                    "content_hash",
                    "confidence_class",
                    "review_status",
                    "source_refs_json",
                )
                if c in entry_cols
            ]
            cur = conn.execute(
                f"SELECT {', '.join(wanted)} FROM {_ENTRY_TABLE} WHERE manifest_id = ?",
                (manifest_id,),
            )
            for row in cur.fetchall():
                entries.append(dict(zip(wanted, row, strict=True)))

        # --- Canonical-ref preservation, approved-only, and link metadata extraction ---
        entry_count = len(entries)
        refs_preserved_rows = 0
        unapproved_indexed = 0
        resolvable: set[str] = set()
        per_entry_links: list[tuple[list[str], bool]] = []  # (target_hashes, is_stale)
        raw_findings: list[str] = []

        for entry in entries:
            # Parse the canonical source_refs_json blob.
            try:
                meta = json.loads(entry.get("source_refs_json") or "{}")
            except (TypeError, ValueError):
                meta = {}
            meta = meta if isinstance(meta, dict) else {}

            # Canonical refs present? (columns non-empty AND required meta keys present)
            cols_ok = all(str(entry.get(c) or "").strip() != "" for c in _REQUIRED_REF_COLUMNS)
            meta_ok = all(meta.get(k) not in (None, "") for k in _REQUIRED_META_KEYS)
            if cols_ok and meta_ok:
                refs_preserved_rows += 1

            # Approved-only: the entry's approved root must be inside the policy roots.
            root_label = str(meta.get("approved_root_label") or "")
            if policy_loaded and root_label not in approved_roots:
                unapproved_indexed += 1

            # Linkage metadata (redacted hashes only).
            name_hash = str(meta.get("note_name_hash") or "")
            if name_hash:
                resolvable.add(name_hash)
            targets = meta.get("link_target_hashes") or []
            targets = [str(t) for t in targets] if isinstance(targets, list) else []
            is_stale = bool(meta.get("stale_unknown_flags"))
            per_entry_links.append((targets, is_stale))

        # --- Broken-link classification against the manifest's resolvable note set ---
        total_links = resolved_links = broken_links = stale_unknown_links = 0
        for targets, is_stale in per_entry_links:
            for target in targets:
                total_links += 1
                if target in resolvable:
                    resolved_links += 1
                elif is_stale:
                    stale_unknown_links += 1
                else:
                    broken_links += 1

        # --- Forbidden raw-content scan over safe columns (never echo a match value) ---
        if entry_present and manifest_id is not None:
            entry_cols = _columns(conn, _ENTRY_TABLE)
            for col in _SCAN_COLUMNS:
                if col not in entry_cols:
                    continue
                cur = conn.execute(
                    f"SELECT {col} FROM {_ENTRY_TABLE} WHERE manifest_id = ? AND {col} IS NOT NULL",
                    (manifest_id,),
                )
                for (val,) in cur.fetchall():
                    if isinstance(val, str) and _FORBIDDEN.search(val):
                        raw_findings.append(f"{_ENTRY_TABLE}.{col}")
                        break

        warnings: list[str] = []
        if broken_links:
            warnings.append(f"broken_links={broken_links} (advisory source-coverage warning)")
        if stale_unknown_links:
            warnings.append(f"stale_unknown_links={stale_unknown_links} (advisory freshness)")

        populated = entry_count > 0
        refs_preserved = (not populated) or refs_preserved_rows == entry_count
        guard_clean = guard_sum == 0
        no_raw = not raw_findings
        approved_only = unapproved_indexed == 0
        schema_ok = schema_version == LATEST_SCHEMA_VERSION

        proof_passed = bool(
            manifest_present
            and entry_present
            and policy_loaded
            and schema_ok
            and guard_clean
            and no_raw
            and approved_only
            and refs_preserved
        )

        return {
            "proof": "phase_09_obsidian_linkage",
            "schema_version": schema_version,
            "schema_version_expected": LATEST_SCHEMA_VERSION,
            "schema_ok": schema_ok,
            "populated": populated,
            "proof_passed": proof_passed,
            "policy_loaded": policy_loaded,
            "policy_error": policy_error,
            "policy_version": policy_version,
            "manifest_present": manifest_present,
            "entry_table_present": entry_present,
            "latest_manifest_id": manifest_id,
            "manifest_count": manifest_count,
            "entry_count": entry_count,
            "guard_columns": len(guard_cols),
            "guard_sum": guard_sum,
            "guard_clean": guard_clean,
            "canonical_refs_preserved_rows": refs_preserved_rows,
            "canonical_refs_preserved": refs_preserved,
            "unapproved_indexed": unapproved_indexed,
            "approved_only": approved_only,
            "link_summary": {
                "total_links": total_links,
                "resolved_links": resolved_links,
                "broken_links": broken_links,
                "stale_unknown_links": stale_unknown_links,
                "resolvable_notes": len(resolvable),
            },
            "raw_content_findings": raw_findings,
            "warnings": warnings,
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "no_raw_content": no_raw,
                "no_external_writeback": True,
                "approved_only": approved_only,
                "advisory_only_no_determination": True,
            },
        }
    finally:
        conn.close()


# --- Controlled-population fixture (writes only to a caller-supplied temp directory) ---

_FIXTURE_ROOT = "Construction Intelligence/Phase 07A Data Quality"
# Wikilinks resolve by note filename (stem), so each approved fixture file is named by its
# title and links its sibling by that same title (resolved) — plus one dangling target.
_NOTE_A = "Project Alpha Data Quality Summary"
_NOTE_B = "Project Beta Data Quality Summary"

_APPROVED_A = (
    f"# {_NOTE_A}\n"
    "project_key: ALPHA\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:START -->\n"
    f"bounded safe summary linking [[{_NOTE_B}]] and [[Missing Note]]\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:END -->\n"
)
_APPROVED_B = (
    f"# {_NOTE_B}\n"
    "project_key: BETA\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:START -->\n"
    f"bounded safe summary linking [[{_NOTE_A}]]\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:END -->\n"
)
_UNMANAGED = "# Private note\nno HB markers here — must not be indexed\n"


def write_linkage_fixture_vault(vault_root: Path) -> dict[str, Any]:
    """Write a throwaway approved-index fixture vault under ``vault_root``.

    Creates two approved, marker-bounded notes that wikilink each other by filename
    (resolved) plus a dangling ``[[Missing Note]]`` (broken), and one unmanaged note
    (excluded). Returns the expected shape so callers can assert against it. Writes only
    inside ``vault_root`` — never the operator DB or the real vault.
    """
    root = vault_root / _FIXTURE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{_NOTE_A}.md").write_text(_APPROVED_A, encoding="utf-8")
    (root / f"{_NOTE_B}.md").write_text(_APPROVED_B, encoding="utf-8")
    (root / "Private Note.md").write_text(_UNMANAGED, encoding="utf-8")
    return {
        "approved_root_label": _FIXTURE_ROOT,
        "expected_entries": 2,
        "expected_excluded": 1,
        "expected_resolved_links": 2,
        "expected_broken_links": 1,
    }
