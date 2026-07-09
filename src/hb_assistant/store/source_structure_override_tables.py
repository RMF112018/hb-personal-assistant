"""V116 — NAS Source-Structure operator classification overrides.

A single additive table letting an operator override the deterministic classification of a root or a
folder when a rule misfires (e.g. a "NAS - HB Backup" root that the rules read as construction work).
Overrides are HUMAN-authored and explicitly allowed to override safety classes — unlike a model, which
must never override them. Every override requires a ``reason`` + ``created_by`` (enforced at the CLI),
and any override that turns a safety flag (``is_backup_mirror`` / ``is_generated_output`` /
``is_sensitive``) from true→false is surfaced as a quality finding for review.

Overrides are applied OUTSIDE the request path — a distinct final pass during ingest, AFTER rule
classification and project-number inheritance and immediately before persistence — so inherited project
mappings stay consistent. MCP/API handlers never read this table directly; overridden rows simply flow
through the existing reads carrying ``classification_source='manual_override'``.

Root targets store ``rel_path=''`` (empty, not NULL) so ``UNIQUE(target_type, root_key, rel_path)``
enforces one active override per target and ON CONFLICT upserts cleanly. Additive only; ships EMPTY.
"""

from __future__ import annotations

from hb_assistant.store.source_structure_tables import (
    DOC_FAMILY_VALUES,
    FOLDER_CLASS_VALUES,
    ROOT_CLASS_VALUES,
    TRUST_TIER_VALUES,
    _csv,
)

OVERRIDE_TARGET_TYPE_VALUES: tuple[str, ...] = ("root", "folder")

V116_TABLES: tuple[str, ...] = ("source_structure_overrides",)


V116_SOURCE_STRUCTURE_OVERRIDE_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS source_structure_overrides (
      override_id TEXT PRIMARY KEY,
      target_type TEXT NOT NULL CHECK(target_type IN ({_csv(OVERRIDE_TARGET_TYPE_VALUES)})),
      root_key TEXT NOT NULL,
      rel_path TEXT NOT NULL DEFAULT '',
      root_class TEXT CHECK(root_class IS NULL OR root_class IN ({_csv(ROOT_CLASS_VALUES)})),
      folder_class TEXT CHECK(folder_class IS NULL OR folder_class IN ({_csv(FOLDER_CLASS_VALUES)})),
      doc_family TEXT CHECK(doc_family IS NULL OR doc_family IN ({_csv(DOC_FAMILY_VALUES)})),
      trust_tier TEXT CHECK(trust_tier IS NULL OR trust_tier IN ({_csv(TRUST_TIER_VALUES)})),
      search_rank INTEGER,
      is_backup_mirror INTEGER CHECK(is_backup_mirror IS NULL OR is_backup_mirror IN (0,1)),
      is_generated_output INTEGER CHECK(is_generated_output IS NULL OR is_generated_output IN (0,1)),
      is_sensitive INTEGER CHECK(is_sensitive IS NULL OR is_sensitive IN (0,1)),
      reason TEXT NOT NULL,
      created_by TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(target_type, root_key, rel_path)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_source_structure_overrides_active "
    "ON source_structure_overrides(active, target_type, root_key)",
]
