# N8C — Source / Card Identity Contract

> Status: **contract / normative** for N8C-2 (Source/Card Identity Hardening). Companion to
> [`n8c-personal-intelligence-operating-layer.md`](./n8c-personal-intelligence-operating-layer.md),
> [`n8c-memory-classes-and-boundaries.md`](./n8c-memory-classes-and-boundaries.md), and
> [`n8c-neutral-naming-policy.md`](./n8c-neutral-naming-policy.md). Repo code/tests are authoritative.

## 1. Purpose

Make source↔card identity **durable, traceable, stale-aware, and duplicate-resistant** so later
slices (claims, Qwen enrichment, navigation tools, frontend) can answer, for any indexed source:
*which card represents it? which source does a card represent? is the card current, stale, missing,
duplicated, or unsafe?* N8C-2 delivers this as a **read-only** service — no DB mutation, no card
write, no retire/delete, **no schema migration**, and **no change to card rendering**.

## 2. Source identity

`source_id = sha256(key)[:32]` (`obsidian_mcp/source_index_repository.py::source_id_for`):
- file sources: `key = f"{source_kind}|file|{source_root_key or ''}|{rel_path}"` (root folded in since V99);
- domain-link sources: `key = f"{source_kind}|link|{domain_ref_table}|{domain_ref_id}"`.

`source_kind ∈ {external_file, obsidian_note, email, procore, schedule}` (`store/source_intelligence_tables.py`).
The source row (`source_intelligence_sources` + `_metadata`) carries `source_root_key`, `deleted`,
`active`, and the content digest `content_sha256` + `mtime_ns`. Email `.eml` files are indexed as
`external_file`; `email`/`procore`/`schedule` are DB-backed link sources.

## 3. Card identity (separate from source identity)

A source card already carries in frontmatter (`obsidian_mcp/source_notes.py::_frontmatter`, unchanged
by N8C-2): `note_type: source_card`, `source_id`, `source_kind`, `source_root_key` (file) /
`source_ref_table`+`source_ref_id` (link), **`source_sha256`** (= source `content_sha256` at
generation), `source_mtime_ns`, `domain`, `card_version`, `template_version`. Card path is
`<source_notes_folder>/<Domain>/<basename>__<source_id12>.md`.

**`card_id` is computed, not stored:** `card_id = sha256(f"{source_id}|{note_rel_path}")[:16]`
(`source_card_identity.compute_card_id`). It is deterministic, storage-free, and provably distinct
from `source_id` (16-hex over a different key space vs 32-hex). The same source rendered at a
different path is a different card. Computing (not persisting) `card_id` avoids a card-rendering byte
change and a schema migration.

## 4. Linkage

- **source → card:** `get_card_for_source(repo, source_id)` (DB `generated_notes` row, prefers
  `generated` over `stale`); `list_cards_for_source` (all rows).
- **card → source:** `get_source_for_card(repo, note_rel_path)` via the read-only repo method
  `get_sources_for_note`. **Ambiguity-aware:** `note_rel_path` is not unique on its own, so the
  result is `none | unique | ambiguous`; an ambiguous path returns `source_id=None` and the full list
  — it never picks a source arbitrarily.

## 5. Stale rules (`detect_stale_card`, read-only, ordered)

1. `source_deleted` — source row absent or `deleted=1`.
2. `card_file_missing` — DB row says generated but the `.md` is gone.
3. `source_id_mismatch` — the card at that path is not a source card, or its frontmatter `source_id`
   ≠ the source it's checked against.
4. `card_version_obsolete` — card `card_version` present but ≠ `source_notes.CARD_VERSION`
   (the named constant; not a magic literal).
5. `source_digest_drift` — card frontmatter `source_sha256` ≠ current `_metadata.content_sha256`
   (mirrors the existing summary-drift pattern; needs no stored per-card digest).

**Legacy is distinct from corruption:** a card missing `card_version` or `source_sha256` is flagged
`legacy_no_card_version` / `legacy_no_source_digest` (advisory `legacy_flags`) and is **not** declared
stale on that basis alone.

## 6. Duplicate rules (`detect_duplicate_cards`, read-only)

The DB `UNIQUE(source_id, note_rel_path)` already blocks exact `(source, path)` duplicates. N8C-2
detects the two vectors it does not cover:
- **one source, multiple active card paths** → `is_duplicate = True`;
- **one card path claimed by multiple sources** → `cross_source_conflicts`.

`classify_card_state(repo, vault_root, source_id)` rolls a source up to one of
`current | stale | missing | duplicate | source_deleted | no_card`. **`source_deleted` is a
classification only** — N8C-2 does not retire, delete, or rewrite the card.

## 7. Note-type classification (`classify_note`) — no misclassification

Decisive frontmatter wins; path is a fallback. A note resolves to exactly one of:
`source_card | ai_output | email_archive | email_attachment | user_authored | unknown`.
- **AI-Outputs** — `note_type: ai_output` or `managed_by: personal_assistant` (folder `AI Outputs/`).
- **Email Archive** — `note_type: email_archive` or `source_type: eml` (folder `Email Archive/`).
- **Source card** — `note_type: source_card`.
- **User-authored** — no decisive frontmatter and outside the generated folders (indexed as
  `obsidian_note`; `generate_source_card` already refuses `obsidian_note` with
  `source_card_not_applicable`).

`validate_card_frontmatter` fails a note that is not a source card, or a source card missing
`source_id`; legacy-missing `card_version`/`source_sha256` are reported but do not fail.

## 8. `.eml` three-surface model (all preserved, not blocked)

1. **Raw `.eml`** — immutable, indexed as `external_file` (`eml_file_source_id`).
2. **Readable Email Archive note** — `note_type: email_archive` + `source_type: eml` under
   `Email Archive/` (`source_email_archive.py`); full body/addresses/message-ids live only here.
3. **Source/summary card** — a `note_type: source_card` note with the graph-safe managed `hb-email`
   block (hashed message-id, participant domains/counts) so connected agents navigate email without
   reading raw bodies. Attachments: cards under `Email Archive/…/Attachments/`.

`classify_note` keeps these three distinct; N8C-2 adds no `.eml` parser and blocks no future one.

## 9. User-authored Obsidian note policy

User notes are **raw/user-authored by default** (`source_kind="obsidian_note"`): indexed, and may be
summarized / linked / linted / used for future Qwen jobs, but **never freely rewritten** and **never
carded** as a generated source card. Any future update goes through a controlled block / companion
card / review-apply workflow. `classify_note` returns `user_authored` (never `source_card`) for them.

## 10. Boundaries

Read-only service only; no MCP tool, no new remote write, no broad DB/filesystem exposure, no schema
migration (`LATEST_SCHEMA_VERSION` stays 99), no raw/import DB mutation, no card-rendering change, no
mass card rewrite. Frontmatter neutrality additions (`managed_by`/`card_id`/`card_status` on cards)
are deferred — source-card frontmatter is already neutral and adding fields is a byte-locked
~40-test change with no debranding benefit (see the neutral-naming policy doc and the risk list).
