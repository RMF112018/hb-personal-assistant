# Phase 06 Prompt 13 Operational Validation Model

This document defines the Prompt 13 operational validation boundary for the email workflow chain:

- `status`
- `folders`
- `discover`
- `index` (dry + live)
- `classify`
- `review-queue`
- `obsidian`

## Runtime Proof Model

The validation runner records sanitized per-command receipts including exit code, safe JSON payload, and timestamps.
No auth headers, access tokens, plaintext email bodies, or raw payload dumps are persisted.

## Closeout Metrics

Prompt 13 computes and reports:

- folders discovered
- messages discovered/indexed
- encrypted body ref count
- plaintext persistence indicators
- attachment content download indicators
- mailbox mutation attempt indicators
- review queue / relationship candidate counts
- obsidian notes generated
- overall validation status

## Safety Posture

- Microsoft Graph mailbox access remains read-only.
- Full body storage remains external encrypted text vault only.
- Obsidian output remains plaintext-safe and reference-safe.
- Prompt 13 evidence files are bounded and sanitized by design.
