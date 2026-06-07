# Phase 10A Prompt 03 — Email Raw Content Ingestion

**Date:** 2026-06-07  
**Status:** Implemented (additive)  
**Related:** Phase 10A 00_PACKAGE_MANIFEST, 04_SCHEMA_PLAN (V42), 06_EMAIL_PLAN, Prompt_03_Email_Raw_Content_Ingestion.md, prior Prompt 01 (raw policy), Prompt 02 (V42 tables + helpers).

## Objective
Extend Graph mail discovery/indexing (the production ReadOnlyMailClient + EmailMessageIndexer path used by `graph mail index`) to fetch full subject/preview/text/HTML body + participants + attachment metadata when raw-content policy enables `email_calendar` mode (or explicit `--include-raw-content` flag). Persist to the V42 `email_message_raw_content` table (plaintext under policy control) and build `email_thread_raw_context` rows (aggregated per thread/conversation). Reuse existing bounded lookback, dry_run, folder scoping, and body-fetch (`get_message_body`). Keep metadata path (`email_messages` etc.) unchanged. Add CLI flag + policy-driven behavior. Produce dry-run/apply evidence in results/JSON.

## Files Touched (surgical)
- `src/hb_assistant/construction/store/repositories.py`: Added `upsert_email_message_raw_content` and `upsert_email_thread_raw_context` (idempotent ON CONFLICT by message_id_hash / thread_ref; no 13-guard CHECKs; match planning columns exactly).
- `src/hb_assistant/construction/email/message_indexer.py`: Extended `IndexResult` + `IndexedFolder` with `include_raw_content`, `raw_content_enabled`, `raw_emails_persisted`, `raw_threads_built`. Added `include_raw_content` param to `index()` / `_index_folder()`. Policy resolution for `email_calendar` + starting_sources.email (fail-closed). Body fetch (reusing `get_message_body`) + normalize to raw payload when effective. Persist via new upserts on apply; thread aggregation at end of folder (messages_json with body_text/html + from/received). Dry-run computes would-persist counts/samples without raw stores. Existing metadata path, dry_run, encrypted-body path untouched. Added `_build_raw_payload` helper.
- `src/hb_assistant/cli/graph.py`: Added `--include-raw-content` Typer option to `mail index_cmd`; pass-through to indexer; updated docstring. Result JSON automatically includes raw_* via model_dump.
- `src/hb_assistant/construction/email/operational_validation.py`: Added `--include-raw-content` to the `mail_index_live` command in dev refresh harness so evidence bundles capture raw stats/receipts.
- `docs/architecture/210-...md` (this) + `docs/architecture/00-README.md` entry.

No changes to: mail_readonly_client (reused), email_messages metadata table or vault path, legacy MailClient, calendar yet, schema, writeback, or any encrypted/raw leakage paths.

## Decision / Rationale
- Policy + flag combo (Prompt 01 surface): explicit opt-in or `email_calendar` mode enables; downstream (MCP/Obsidian) remain false for Prompt 03.
- Reuse body fetch + indexer: minimal new surface; bounded by list scope (max per folder); no new budgets for raw in this prompt.
- Thread context: aggregated `messages_json` per conversationId (or fallback) to support later model-packet builder without re-scanning.
- Dry/apply evidence: raw counts in IndexResult (and thus CLI JSON + processing receipts) mirror the encrypted-body pattern; dry emits would-persist, apply emits actual rows + receipt detail.
- Additive only: V42 tables (Prompt 02) are the designated holders; metadata path + guards unchanged; no plaintext to vault/obsidian/evidence logs.
- Fail-closed, read-only, no external writes (enforced by policy + existing layers).

## Verification Summary (post-impl)
- Dev `hb-assistant graph mail index --no-dry-run --include-raw-content --json` (or equiv via operational_validation "dev email refresh") produces rows in `email_message_raw_content` (subject/body_text/body_html/from/to json/att meta present) and `email_thread_raw_context` (messages_json with body_text usable, model_ready=1).
- `get_raw_content_table_row_counts()` shows counts >0 for raw tables post-apply; re-run is idempotent (no dup growth beyond updates).
- Prior metadata tables (`email_messages`, attachments, vault refs, etc.) unchanged when running with/without flag.
- Dry-run path: returns raw_* would counts >0 when effective, no raw table writes, receipt not inserted.
- Body text present for "model packet" readiness (sample row body_text len >0, redacted in logs).
- Sensitive scan / no-writeback attest: raw only in the two new tables; no leakage to old paths, no tokens/full-delta/raw in outputs.
- Linting/type: ruff clean, mypy (scoped) clean on touched + local_ai.
- Focused tests: `pytest -k "email or mail or graph or indexer or phase_10 or raw"` (safe markers) green for the exercised paths; pre-existing broad suite noise acknowledged.

## Guardrail Attestations
- Raw plaintext only in designated V42 raw tables when policy on + (flag or email_calendar); never in email_messages (still metadata_only), never in vault (encrypted path separate), never in Obsidian (downstream toggles false), never submitted to cloud LLM.
- Mailbox stays read-only at all layers; no mutations, no send, no calendar changes.
- Evidence + receipts only on apply (not dry); dry_run default safe.
- All source traceability preserved; redaction for non-raw paths untouched.
- Additive migration (V42) + no drops/rewrites of prior schema.

## References
- Planning: `docs/planning/HB_Construction_Intelligence_Phase_10A_.../Prompt_03_Email_Raw_Content_Ingestion.md`, `06_EMAIL_PLAN.md`, `04_SCHEMA_PLAN.md`, `02_DECISION_RECORD_RAW_CONTENT.md`.
- Prior: Arch 208 (Prompt 01 policy), 209 (Prompt 02 V42 schema), Phase 06/08A email metadata/encrypted patterns.
- Code: message_indexer.py (reuse get_message_body + normalize), repositories.py (raw upserts), cli/graph.py + operational_validation.py (flag + dev evidence), local_ai (policy load + RawContentPolicy).

Follow-ups (deferred to later prompts): calendar raw (Prompt 04), full model context packet builder using the raw rows, downstream consumption (MCP/Obsidian under future policy), bounded max from model_context policy, raw access events logging.
