# Phase 10A Prompt 07 — Action Intelligence From Raw Content

**Status**: Implemented (additive).  
**Related**: Prompt 05 (raw endpoints), Prompt 06 (raw model context packets), V41 action candidate tables (task_candidates, commitment_candidates, candidate_source_refs), V42 raw content tables.

## Objective
Use local models (OllamaChatClient) to extract actionable candidates (task, commitment, follow-up/relationship/decision etc.) **directly from Phase 10A raw email and calendar content** (the V42 raw tables populated by P03/P04 and surfaced via P05/P06).

Enforce:
- The existing strict `ActionCandidate` Pydantic schema (extra="forbid", field/model validators).
- New business-contract validation that **rejects generic data-cleaning, data-analysis, "normalize the spreadsheet", "perform data analysis", or other hallucinations** not tied to a concrete project deliverable or commitment.
- Retry + self-repair on JSON parse failures or business validation failures (up to 3 attempts; appends a precise repair instruction containing the error).
- Persistence of accepted candidates to the V41 advisory tables, with `candidate_source_refs` carrying a **bounded raw excerpt** (`evidence_redacted`) verbatim from the triggering raw row (subject/body snippet).

All paths are advisory-only (review_status=pending, recommended_next_action=review, external_action_requires_approval=true). No auto-accept, no writeback.

## Inputs
- **Preferred**: P06 raw context packets (`raw_email_packet`, `raw_calendar_packet`) — these already contain the bounded actual `body_text`, subject, participants, etc. from the raw tables when policy + model_context allow.
- **Fallback**: `project_key` → the extractor calls the P05 store list methods (`list_email_message_raw_content`, `list_calendar_event_raw_content`) to obtain recent raw rows for that project.
- The raw content surfaces (P05) and packet builders (P06) already respect the `RawContentPolicy` (`email_calendar` mode, `include_raw_content`, external LLM disabled, local-only).

Raw excerpts shown to the model and persisted in evidence are **bounded** (`_truncate` at ~1200 / ~400 chars). Full bodies live only in the V42 raw tables.

## Schema & Strictness
- Output contract: the Phase 10 `action_candidate_output_schema.json` (already present; registered in contracts).
- Runtime model: `ActionCandidate` (in `local_ai/models.py`) — `model_validate` with `extra="forbid"`.
- The system prompt (`STRICT_ACTION_SYSTEM`) demands **ONLY a JSON array** (or `[]`) matching the schema exactly. No prose, no markdown fences.
- `source_refs` must be stable identifiers present in the provided excerpts (message hashes, event ids, etc.).

## Business-Contract Validation (`_validate_business_contract`)
After strict parse, each candidate is checked:

- If `title` or `reason` contains any of: "clean the data", "normalize the data", "data cleaning", "data analysis", "analyze the data", "perform data analysis", "summarize trends", "clean up the spreadsheet", "process the information", "extract fields for analysis", "data quality", "standardize the data" → rejected with `generic_data_work`.
- For `task`/`commitment` types, title must be non-vague (≥8 chars after strip).
- Only concrete, deliverable-tied actions are accepted (e.g. "Submit revised RFI #42 ... by COB Friday", "Confirm steel vendor commitment for 2026-06-18 or escalate").

Rejected candidates are recorded in the report (`rejections` list) with reason; they are **not** persisted.

## Retry / Repair
`_run_with_retry_repair` + outer loop in the extractor:
- On JSON decode failure or Pydantic `ValidationError` or business rejection in a prior attempt, the prompt for the next attempt is the original + `PREVIOUS OUTPUT FAILED ... Output ONLY a corrected JSON array matching the Phase 10 ActionCandidate schema exactly. No other text.`
- Up to 3 attempts total.
- When using `--mock-output` (tests/CLI), the first call uses the supplied mock; subsequent repair attempts fall through to the same static mock (tests drive "bad first, good later" by calling the function twice or by exercising the append path).
- If all attempts fail, the report contains `rejections` and `note: "exhausted retries"`.

## Persistence
Accepted candidates are written via the new (P07) store helpers added to `ConstructionStore`:
- `upsert_task_candidate(...)` / `upsert_commitment_candidate(...)` (idempotent on `candidate_id`; stable_key derived from source refs + content).
- `upsert_candidate_source_ref(..., evidence_redacted=short_verbatim_excerpt)` — one ref per `source_ref` in the candidate. `source_family` is `email_message_raw_content` or `calendar_event_raw_content`; `evidence_redacted` carries the bounded raw snippet that triggered the candidate.
- Other candidate types (decision, risk_signal, ...) are accepted by schema but the P07 MVP focuses on task/commitment for the V41 tables; they can be extended later.

The 13 `_P10_GUARDS` (no raw bodies, no writeback, etc.) are enforced by the table DDL. The Python layer and bounded excerpts are defense-in-depth.

## CLI
Under `hb-assistant second-brain phase-10`:
- `raw-action-candidates --project PRJ-XYZ --source both|email|calendar --dry-run|--apply --json`
  - `--mock-output '[{"candidate_type":"task", ...}]'` (hidden; for tests/CI).
  - On `--apply` the extractor persists; on default `--dry-run` the report shows `would_persist` and forces `persisted=0` in the CLI envelope.
  - Payload includes `guardrails` block documenting local-only, advisory-only, strict schema, business contract, retry/repair, bounded excerpts only in evidence, no auto-accept.

The CLI is intentionally thin — it delegates to the extractor and surfaces the report + guardrail attestation.

## Module Surface
- New: `src/hb_assistant/construction/second_brain/local_ai/raw_action_intelligence.py`
  - `extract_action_candidates_from_raw(...)`
  - `STRICT_ACTION_SYSTEM`, `_validate_business_contract`, `_run_with_retry_repair`, helpers.
- Wired in `local_ai/__init__.py` (additive export).
- Store upserts + list helpers in `construction/store/repositories.py` (additive, after the P06 packet methods).
- Thin CLI in `cli/second_brain.py`.
- Tests: `tests/test_phase_10a_raw_action_intelligence.py`.
- Proof touch (additive) in `local_ai/proof.py` so the contracts-proof run imports the P07 module.

## Tests (focused, hermetic)
- `test_good_candidates_parsed_persisted_with_excerpts`: seeds realistic raw email with task-like + commitment signals via `upsert_*_raw_content`; calls with good mock JSON; asserts accepted counts, persisted rows in V41 tables, source refs present with bounded `evidence_redacted` excerpts, and that full raw bodies are **not** present in the persisted evidence.
- `test_bad_generic_candidate_is_rejected`: supplies the forbidden pattern mock; asserts rejected with `generic_data_work`, zero persisted.
- `test_retry_repair_path_exercised`: drives a bad-JSON first attempt (triggers repair append), then a good one; verifies the code paths and that good output is still accepted after a parse failure.
- `test_no_full_raw_leakage_in_excerpts_or_report`: asserts that neither the report candidates nor the source-ref evidence contain full raw bodies or the sentinel full-body sentence from the seed; the raw tables themselves still hold the complete content (the designated holder).
- CLI smoke via direct extractor call.

All tests use a fresh temp DB + `store.migrate()`, seed only via the sanctioned raw upsert paths, and run under the default safe pytest markers (no integration/live/manual).

## Invariants / Guardrails (maintained)
- Raw content (full bodies) only ever lives in the V42 raw tables (`email_message_raw_content`, `calendar_event_raw_content`, `email_thread_raw_context`, `raw_content_model_context_packets`).
- This P07 path is the **sanctioned exception** that may carry short bounded excerpts **only inside** `candidate_source_refs.evidence_redacted` for explainability of the advisory candidates.
- Business validation is the primary defense against the model hallucinating generic "data work".
- All model calls (including this one) are mockable; the implementation never requires a live Ollama in CI.
- Idempotency via `candidate_id` / `stable_key`.
- Advisory posture: `review_status=pending`, `recommended_next_action=review`, `external_action_requires_approval=true`.
- No change to deterministic (non-raw) action extraction; this is a parallel raw-content path.
- No new schema migration (V41 tables and V42 raw tables pre-exist).
- No downstream auto-accept or external writeback.
- Policy surface (P01) continues to control whether raw content is even present; if not enabled the extractor will see empty input and return early with a note.

## Acceptance Evidence (in commit)
- Good fixture-style raw email + good mock → produces useful task + commitment + follow-up ActionCandidates with correct fields, source_refs, and persisted excerpts.
- Bad/generic mock ("analyze the data...") → rejected by business contract (not persisted).
- Retry path covered.
- Persisted source refs contain short verbatim excerpts; full raw bodies remain only in the raw tables.
- Strict schema enforced.
- CLI and python -c paths runnable with `--mock-output`.
- Verification: ruff + mypy + focused pytest + manual simulation all pass; only intended files staged.

## Non-Goals (explicit scope)
- Full local model runtime / job queue / scheduler (Phase 10 main prompts).
- Changes to the deterministic (pre-raw) actions extractor.
- Auto-promotion or writeback of candidates.
- New raw content policy knobs (reuses P01/P05).
- Changes to fixtures (tests construct or mock the "raw email" case).

This implementation is deliberately surgical and additive, reusing the strict schema, client, store patterns, dry-run/mocking conventions, and guardrail posture already established for Phase 10.
