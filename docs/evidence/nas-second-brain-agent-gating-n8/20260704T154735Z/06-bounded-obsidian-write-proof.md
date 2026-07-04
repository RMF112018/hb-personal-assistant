# 06 — Bounded Obsidian Source-Card Proof — RUNBOOK (PENDING LIVE EXECUTION WITH BOBBY)

Status: **HOLD** — live NAS vault write, per-step approval required. Not executed this session.

## Pre-write guard (STOP conditions)
- Confirm the resolved vault path is **NAS-local** (`/volume2/personal-assistant/…`).
- **Abort** if the vault resolves to the Mac vault `/Users/bobbyfetting/Documents/Obsidian Vault/…`
  (wrong-vault stop condition).
- Confirm `writes_enabled && vault_markdown_write_enabled` are the deliberate, current config.

## Plan (exactly one card)
1. Generate one source card for one ingested `nas_test` source (`source-card/generate` or
   `generate_source_card`).
2. Verify the card wrote atomically (temp+`os.replace`), path derived from the **root-scoped**
   `source_id[:12]`, frontmatter records `source_root_key=nas_test`, SHA optimistic-concurrency intact.

## Acceptance / receipts
- Exactly **1** `source_intelligence_generated_notes` row (`generation_status=generated`); +1 card file
  under the NAS vault's Source Notes folder.
- Card identity includes the fixed `source_id`; no raw body/token/path leak in the card (redaction fence).
