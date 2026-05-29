# Phase 04B Prompt 05 — Meeting Detail Enrichment

**Date:** 2026-05-29 · **Modules:** `src/hb_assistant/store/procore_meeting_projection.py`,
`src/hb_assistant/security/text_vault.py` · **Wiring:** `src/hb_assistant/procore/live_sync.py`.

## Summary

Turns `meeting-detail` (and the grouped `meetings` list) into a high-value second-brain source:
extracts attendees, categories, topics, minutes/descriptions, attachments, the meeting-series chain,
mentioned records, and action/risk signals into the cross-cutting enrichment tables (meetings have no
dedicated V7 tables). Wired into the live-sync meeting flow (after the latest-state upsert + history,
guarded). Adds a real **encryption-at-rest mechanism** so full meeting text is retained encrypted
rather than dropped.

## Encryption-at-rest vault (`security/text_vault.py`)

File-based Fernet vault mirroring the OAuth token-cache `0o600` pattern (no SQLite/migration):
- Key from `HB_TEXT_VAULT_KEY` env or a generated `0o600` key file at
  `<AppSupport>/security/text-vault.key`; ciphertext blobs at
  `<AppSupport>/security/text-vault/<sha256[:32]>.enc` (`0o600`) — **outside the repo**, never plaintext.
- `encrypt_text(plaintext) -> ref` (deterministic ref → idempotent) / `decrypt_text(ref) -> str`.
- `cryptography>=42.0` now declared in `pyproject.toml` (previously only an indirect dependency).

## Text-intelligence policy (`emit_text_intelligence` extended)

Each free-text field (meeting `description`/`conclusion`, topic `description`/`minutes`) now stores:
`text_hash`, `text_length`, detected topic keywords, **mentioned-record tokens** (RFI/PCO/submittal
numbers + permit/closeout/utilities), action-candidate keywords, risk-term keywords, a **short
PII-masked redacted excerpt** (emails/phones/URLs masked, truncated to 160), and an
**`encrypted_full_text_ref`** into the vault. Raw prose is never stored unencrypted; `raw_body_persisted=0`.

## Extraction + edges + signals

- **Attendees** (`attendees[].login_information`) and `created_by_id`/`distributed_by` →
  `extract_people_refs` (login/name hashed) + `meeting -> attendee/created_by/distributed_by` edges.
- **Categories** → `meeting -> category` edges (synthetic category entity key).
- **Topics** (`meeting_categories[].meeting_topic[]`) → `meeting -> has_topic` edges (topic record key);
  topic `attachments` → attachment refs + `topic -> has_attachment` edges; topic text → text
  intelligence; mentioned tokens → `topic -> mentioned_rfi/pco/submittal/permit/closeout/utilities`
  edges; open + high-priority topic → `meeting_topic_open_high_priority` action signal.
- **Attachments** (meeting + topic) → `extract_attachment_refs` (filename hashed, URL path-only — no
  query strings).
- **Meeting series** → `meeting -> previous_meeting` edge from `parent_id` (grouped `meetings` list).

`_scan_text` returns tokens/keywords only (regex for `RFI/PCO/SUB \d+`; keyword sets for permit/
closeout/utilities, action language, and risk terms) — never prose.

## Tests

- `tests/test_text_vault.py`: encrypt→decrypt round-trip; deterministic ref; ciphertext ≠ plaintext;
  key + blob `0o600`; empty → None.
- `tests/test_procore_meeting_projection.py`: attendee/category/topic extraction + edges (people
  hashed, raw login absent); attachment refs path-only (no `?`/token/company_id); text intelligence
  with `encrypted_full_text_ref` decrypting to the original + `rfi:123` token + email masked in
  excerpt; `meeting_topic_open_high_priority` signal; meeting-series edge; idempotency; and a
  `run_live_sync` grouped-meetings test asserting flattening (2 rows) + the `previous_meeting` edge.

## Guardrails / validation

People hashed; attachment/text URLs path-only; free text → hash + tokens + redacted excerpt +
encrypted full text (Fernet, key `0o600`, blobs outside repo); deterministic keys/refs +
conflict-upsert / INSERT OR IGNORE keep enrichment idempotent; guarded so it never breaks
latest-state/history; meeting normalizer unchanged; no store→procore import; no schema change.

```
python -m pytest -q --no-header   # full suite green (1 pre-existing skip)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 195 source files
python -m compileall src tests    # OK
```
