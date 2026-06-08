# 211. Phase 10 Local Action Intelligence — Email Task Candidate Extraction

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 07)

## Context

Base-Phase-10 Prompt 07 extracts **reviewable task/commitment candidates from metadata-safe email
thread summaries / read models using deterministic signals plus local-model structured output**. A
sibling **Phase 10A Prompt 07** (`raw_action_intelligence.extract_action_candidates_from_raw`) already
extracts from **raw email bodies** (V42 tables). This prompt adds the **complementary, cheaper, safer
summary path** for broad/background scanning and does **not** duplicate the raw extractor, the
`ActionCandidate` model/schema, `StructuredOutputClient`, `extract-fixture`, or the candidate tables.

The genuine gaps it fills: there was **no deterministic-signal layer**, **no production
`extract_email_tasks` path** (the ai-job only validated fixtures), and **no Prompt 07 evidence**.

## Decision

Add a new production module + CLI that scores deterministic task signals over email thread summaries
and runs the existing schema-enforced client to produce advisory task/commitment candidates, in two
modes, and wire the `extract_email_tasks` ai-job to it. **No new migration, candidate table, seed, or
Ollama-runtime change.** `LATEST_SCHEMA_VERSION` stays at 42.

## Module (`construction/second_brain/local_ai/email_task_extraction.py`)

- **`score_email_task_signals(summary)`** — pure deterministic scorer (code-constant regex/keyword
  sets) over a normalized, metadata-safe summary. Fires seven signal categories mapped to stable
  reason codes: `direct_ask`, `due_date`, `waiting_on_me`, `waiting_on_others`, `unanswered_question`,
  `follow_up_stale`, `project_source_confidence` (plus `low_signal` when none fire). Produces a
  candidate_type / waiting_state hint and a bounded deterministic-confidence contribution.
- **Two modes.** `metadata_safe` (default): redacted summary fields only. `bounded_content` (opt-in,
  policy-gated via `RawContentPolicy` — `enabled` + `model_context.include_raw_content` +
  `starting_sources.email`): augments the window with bounded local thread content read **ephemerally
  in-process** via the existing `build_raw_email_context_packet` (lazy-imported to avoid a package
  init cycle); never persisted beyond a policy-approved bounded excerpt (≤400 chars). When disallowed
  it falls back to `metadata_safe` and records the blocker
  `bounded_content_not_eligible_fell_back_to_metadata_safe`.
- **`extract_email_task_candidates(...)`** — resolves summaries (explicit arg or
  `store.list_email_thread_summaries`), scores signals, builds the window
  (`input_window_hash = hash_summary(...)`), runs `StructuredOutputClient` over `ActionCandidate`,
  reuses `raw_action_intelligence._validate_business_contract` to reject vague titles, and — only
  when `dry_run=False` and a store is given — persists accepted `task`/`commitment` candidates via
  `upsert_task_candidate` / `upsert_commitment_candidate` (clean `email-task:{sha(source_refs)}` /
  `email-commit:` stable key) plus `upsert_candidate_source_ref` linked to the **correct**
  `candidate_id` (avoiding the raw extractor's `source_refs[0]` linkage quirk),
  `source_family="email_thread_summary"`. Returns counts, candidates, rejections, `signals_summary`,
  and `blockers`. Hash-only/redacted; no raw text echoed.

## Contract (`resources/json/phase_10_email_task_signal_contract.json`)

Declarative shape (`signal_categories`, `reason_codes`, `modes`, `candidate_types`, `source_family`,
the 13 `guard_columns`), registered in `PHASE_10_CONTRACT_FILES` as `email_task_signal_contract`. A
parity test asserts the module's closed vocabularies match the contract. No new seed policy —
`bounded_content` eligibility/bounds reuse `RawContentPolicy`. (Registered contract count 12 → 13;
the contracts proof is dynamic, so it stays clean; the two hardcoded count assertions in
`test_phase_10_contracts.py` were updated.)

## CLI + AI-job wiring

- **`action-intel extract-email-tasks`** (`cli/second_brain.py`): `--mode`, `--project`,
  `--summary-source store|fixtures`, `--fixtures-dir`, `--mock-output`, `--dry-run/--apply`,
  `--environment`, `--db`, `--json`. Dry-run default; exit `0` ok / `2` blocked / `1` error.
- **`ai_jobs._run_one_job`**: `job_type == "extract_email_tasks"` now delegates to the real extractor
  (metadata_safe, dry-run-aware, env-isolated, injected backend honored) and maps
  produced/accepted/rejected + backend-unavailable into the existing run-row + retry/backoff
  lifecycle; all other job types keep the fixture-validation harness. The extractor returns
  `produced=0` without touching Ollama when there are no summaries, so the lifecycle tests stay
  deterministic. `test_phase_10_ai_jobs.py` was updated to seed a summary + inject a backend for the
  apply-receipts and retry/backoff cases (coverage preserved).

## Fixtures + tests

Summary fixtures live in `tests/fixtures/local_ai/email_summaries/` — a **subdirectory** so the
non-recursive `ai_jobs` glob and the Prompt 06 glob-safety test (which assert exactly the original 4
flat fixtures) are unaffected; a regression test pins this. `tests/test_phase_10_email_task_extraction.py`
covers the six required scenarios (success, bounded-content-gated/blocked, unavailable dependency,
invalid schema, stale forbidden field, no-raw/no-writeback), deterministic-signal behavior,
contract↔module parity, persistence linkage, and commitment routing.

## Proof / evidence

`email_task_extraction_proof.py::build_email_task_extraction_proof` (run directly, mirroring the
04/05/06 builders) emits
`docs/evidence/construction-intelligence-phase-10-local-action-intelligence/07-email-task-candidate-extraction-proof.{json,md}`
with all gates clean and `guard_sum=0`.

## Guardrails

Local-only; deterministic signals + schema-validated structured output; advisory candidates
(review-only, `external_action_requires_approval` const true); dry-run default; no Graph/Procore/
email/calendar/Obsidian writeback; no raw body/prompt/response/URL/token persistence (`bounded_content`
ephemeral only); env isolation in the ai-job path; every candidate carries source refs, confidence,
model profile, prompt-template version, and review status. Consistent with Prompts 01–06, no README/
ledger bump (deferred to a later closeout).
