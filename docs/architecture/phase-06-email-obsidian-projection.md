# Phase 06 Email Obsidian Projection Boundaries (Prompt 12)

## Purpose

Define the local-only projection boundary for operational email intelligence outputs into Obsidian-safe markdown.

## Data Boundary

Inputs:
- local SQLite Phase 06 email intelligence tables (messages, project matches, relationship candidates, review queue, processing receipts, body-vault metadata, model classifications, thread summaries)

Outputs:
- grouped project-level Obsidian notes and manifest/receipt notes

Never output:
- plaintext body
- decrypted full body
- raw encrypted body ref
- raw Graph payload/token/headers

## Security Posture

- Mailbox remains read-only.
- Obsidian is not full-body storage.
- Encrypted full bodies remain in external text-vault storage.
- Obsidian notes may carry encrypted-body availability booleans/counts only.
- Prompt 12 fence rejects forbidden plaintext markers in generated note content.

## CLI Surface

`hb-assistant graph mail obsidian --project <key> --include-encrypted-body-status --dry-run --json`

JSON summary includes:
- notes planned/written
- messages referenced
- encrypted body ref count exposed (default 0)
- encrypted status included flag
- plaintext body written flag (always false)
