# Obsidian Card Materialization (N8C-23)

Promotion materializes each canonical artifact as an Obsidian card in an **existing** vault folder,
plus a receipt card and a canonical manifest. No new top-level folder is ever created.

## Path resolution (`obsidian_mcp/vault_path_resolver.py`)

`resolve_relative_path(artifact_type, domain, canonical_id, title, operator_override_path=None)` is a
pure function that maps `(artifact_type, domain)` to a destination under an existing top-level folder:

- decisions → `Work/03 Decisions` (or `Home/...` by domain)
- open loops / actions → `Work/04 Actions`
- preferences, architecture notes, knowledge → `Work/07 Knowledge` / `Home/07 Learning`
- answer drafts → `AI Outputs`
- source-card annotations → `Source Notes`
- session notes → `00 Inbox`

Filenames are `{CANONICAL_ID} - {sanitized title}.md`, where the canonical id is
`{PREFIX}-{YYYYMMDD}-{content_hash[:6].upper()}` (e.g. `DEC-20260708-A1B2C3`).

Guards (all raise before any write):

- The destination's first path segment must be in `EXISTING_TOP_LEVEL_FOLDERS`
  (`override_introduces_new_top_level_folder` otherwise).
- Traversal / absolute overrides are rejected (`unsafe_override_path`).
- `resolve_write_path` re-validates against the live vault via `path_blocked` + `resolve_safe_path`
  (hidden `.obsidian`, protected, symlinked paths are blocked).

## Card rendering (`obsidian_mcp/artifact_card_renderer.py`)

`render_artifact_card` builds YAML frontmatter
(`canonical_id, artifact_type, status, title, domain, source_client, source_session_id, proposal_id,
promotion_receipt_id, version, created_at, related_artifacts, tags`) and a body with: summary, body,
source-session backlink (`[[SESSION-...]]`), related-artifact backlinks, review history, future-use
guidance, and a receipt backlink. **Every body passes `redact_text`**; the renderer returns a
`redacted` flag so the promotion receipt records whether redaction fired.

Required tags: `second-brain/canonical`, `artifact/<type>`, `status/<review_state>`,
`source/<client>`, `domain/<domain>`. Tags, folder names, and generated content are
**organization-neutral** — no employer-specific names, abbreviations, or paths
(enforced by `tests/test_n8c23_org_neutral_scan.py`).

## Atomic write engine

Cards are written through the existing `obsidian_mcp` mutation engine (temp `NamedTemporaryFile` →
`fsync` → `os.replace` atomic rename → backup → sha optimistic-concurrency → mutation receipt),
reached via `nas_mcp/obsidian_config.py`. The engine is markdown-only; the canonical and client-tool
manifests need a `.json` sibling, so `artifact_vault_writer._json_manifest_config` narrowly extends
`allowed_write_file_types` to `["md","json"]` **only for the `99 System/Manifests` folder**.

## Outputs of a promotion

- N artifact cards in existing folders.
- One receipt card in `99 System/Receipts/`.
- `99 System/Manifests/canonical-artifact-manifest.{md,json}` (regenerated from canonical rows).

## Partial failure

If a card write fails, the canonical row stays `promotion_partial_failure`, a `pa_artifact_repair_tasks`
row is recorded, and the receipt reports the failure. No half-written file is left behind (atomic
rename), and re-running promotion is idempotent.

## Production note

The production DB is mounted as a read-only snapshot, so promotion (a write) is a local/operator
capability, not a production-runtime one. Tests and the smoke script use a temp DB and a temp vault
mirroring the real structure — never the synced vault.
