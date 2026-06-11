# 09 — Raw-Safety & No-Leak

## Synthetic markers proven absent

The test suite seeds raw bodies / HTML / join URLs / signed URLs / auth-token strings / recipient
arrays carrying obvious synthetic `EMAIL_FOLLOWUP_*` markers (defined only in the test module) and
asserts that none of them appear in: extractor output, persisted domain rows,
`daily_brief_action_candidates`, `candidate_source_refs`, the stage receipt, or status JSON. A subject
that itself embeds a URL / auth-token / recipient marker is scrubbed by `_scrub` before it becomes a
title, so even subject-embedded markers cannot leak.

Relevant tests: `test_no_raw_sentinels_in_extractor_output`,
`test_builder_receipt_is_raw_free_and_reports_coverage`, `test_raw_access_not_used_by_default`.

## Repo scan

`hb-assistant email-calendar raw no-raw-leak-scan --path <evidence-dir> --json` →
**`unsafe_finding_count == 0`** (machine output in `09-no-raw-leak-scan.json`). The scan was also run
over the `/tmp` audit artifacts with the custom synthetic markers added via `--sentinel`, also clean.

## Raw access

No `load_body` call occurs in this pass. `raw_content_access_events` is unchanged by extraction
(metadata-only path); `raw_access_count == 0` in every stage receipt.

## Statement

No raw body text, raw HTML, full recipient arrays, private URLs, join URLs, signed URLs, tokens,
secrets, model prompts, or model responses were found in any evidence / status / output surface. Raw
access count: 0. All raw access events audited: yes — not applicable, none occurred.
