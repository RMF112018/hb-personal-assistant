# Prompt 03 — Email Raw Content Ingestion

## Objective

Update Graph mail discovery to persist raw email content locally when raw-content mode is enabled.

## Tasks

1. Fetch subject, preview, text body, HTML body, participants, attachment metadata.
2. Persist into `email_message_raw_content`.
3. Build/update `email_thread_raw_context`.
4. Add `--include-raw-content` or config-driven behavior.
5. Add dry-run/apply evidence.

## Acceptance

- Dev email refresh produces raw email rows.
- Raw thread context exists.
- Model packet can be built from actual body text.
