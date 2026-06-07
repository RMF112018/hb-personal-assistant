# Phase 10A Prompt 08 — Frontend Raw Content Review (Local CLI)

**Status**: Implemented (additive).  
**Related**: Prompt 05 (raw endpoints + direct accessors), Prompt 06 (raw packets), Prompt 07 (raw action candidates + V41 task/comm + candidate_source_refs), V42 raw tables, memory review pattern (canonical operator loop).

## Objective
Expose the actual raw source content (full plaintext bodies from the Phase 10A V42 tables) in the local review/inspect experience so an operator can see the real email or calendar content behind a raw-derived action candidate (or any raw row) before making a review decision.

"Frontend" here means the local operator surfaces (Typer CLI), per the pure-Python + local-first nature of the project. No web UI or JS.

## Inputs from prior prompts
- P05: Policy-gated email/calendar endpoints (`list_*`, `get_*`, direct `*_raw_content` getters) that attach `raw_content` + `_raw_content_included` when `RawContentPolicy` + `EndpointsConfig` + `include_raw`/`raw_mode` allow. CLI `graph mail threads` / `calendar events` already existed as list surfaces.
- P06: `build_raw_*_context_packet` + `raw_content_model_context_packets` (bounded packets for models).
- P07: `extract_action_candidates_from_raw` → `task_candidates` / `commitment_candidates` (default `review_status='pending'`) + `candidate_source_refs` (with `source_family`, `source_ref_hash`, `evidence_redacted` = bounded verbatim excerpt). Store `list_*_candidates(review_status=...)` + `list_candidate_source_refs` already present. `candidate_review_events` table existed in V41 schema (unused until now).

## Changes (additive only)
1. **Raw detail surfaces** (inspect full raw by key):
   - `src/hb_assistant/cli/graph.py`:
     - `graph mail message --message-id <id> [--include-raw] [--raw-mode] [--json]` (enriched get via `construction.email.get_email_message`).
     - `graph mail raw-message --message-id <id> | --message-id-hash <hash> [--json]` (direct via `get_email_message_raw_content`).
     - `graph mail raw-thread --thread-ref <ref> [--json]`.
     - `graph calendar event --event-index-id <id> [--include-raw] [--raw-mode] [--json]`.
     - `graph calendar raw-event --event-index-id <id> | --graph-event-id-hash <hash> [--json]`.
   - All reuse the P05 getters (policy-respecting). Payloads carry `raw_content`, `_raw_content_included`, and a `guardrails` block with `review_inspect_only`, `full_raw_bodies_only_in_sanctioned_review_detail`, etc.
   - Human note when not `--json`: "Raw content (actual body from local V42; policy email_calendar) — review/inspect use only."

2. **Link candidates to source content** (the core acceptance requirement):
   - `src/hb_assistant/cli/second_brain.py` (under `phase-10`):
     - `phase-10 list-candidates --project --type task|commitment|both --review-status pending --json`: lists V41 candidates + their `source_refs` (with `evidence_redacted` excerpts) so operators can see provenance at a glance and drive follow-up commands.
     - `phase-10 candidate-source --candidate-id <id> --candidate-type task|commitment [--include-full-raw] [--json]`: loads the candidate (incl. current `review_status`, `title_redacted`, `reason_redacted`, confidence, etc.) + resolves its `candidate_source_refs` to attach the **full** raw content rows (`raw_content` sub-dicts with actual `body_text` etc.) when `--include-full-raw` (default). This is how a user "inspects the actual email/calendar content behind candidates."
     - A small inline resolver `_resolve_raw_for_source_ref` (no new public module required) maps `source_family` + hash → the appropriate `store.get_*_raw_content` call.

3. **Make raw mode visible**:
   - Every new payload includes explicit markers (`_raw_content_included`, `raw_content` when present) + a `guardrails` object documenting:
     - `local_only`, `advisory_only`, `no_auto_accept`, `review_inspect_only`, `full_raw_bodies_only_in_sanctioned_review_detail`, `bounded_excerpts_in_candidate_source_refs`, `raw_content: policy_and_param_controlled | direct_V42_access_policy_controlled`.
   - Human-facing notes reiterate that full bodies live only in the local V42 tables and these surfaces are for review/inspect.

4. **Preserve (and enable) review actions**:
   - `phase-10 review-candidate --candidate-id <id> --candidate-type task|commitment --decision pending|accepted|ignored|snoozed|rejected --reason "..." --emit/--no-emit --json`.
     - Exact mirror of the memory review pattern (`memory review --candidate-id ... --decision ... --emit`): dry-run by default, explicit `--emit` to persist, redacted reason, guardrails block, non-zero exit on not-found/invalid.
     - Uses new minimal store helpers (below) to set `review_status` on the V41 row and (best-effort) insert a `candidate_review_event`.
     - `list-candidates` already supports `--review-status` filter (wired to the existing store `list_*_candidates(review_status=...)`).
   - No changes to candidate upsert logic, defaults, columns, or indexes. Existing `review_status` mechanics are untouched outside these new sanctioned paths.
   - Raw inspect (candidate-source / graph raw-*) informs the human but never auto-accepts.

5. **Store helpers (additive, minimal)** in `src/hb_assistant/construction/store/repositories.py` (inside the Phase 10 V41 block):
   - `set_candidate_review_status(*, candidate_type, candidate_id, review_status) -> bool`
   - `insert_candidate_review_event(*, candidate_type, candidate_id, decision, reason_redacted, reviewer_ref) -> Optional[event_id]`
   - Best-effort for the event (table may be absent or constraints may apply in some DBs); non-fatal.

6. **No new wiring needed for exports**:
   - The P05 getters (`get_email_message*`, `get_calendar_event*`, direct raw getters, list raw) were already exported from `construction.email` and `construction.calendar` `__init__.py`.
   - No new `local_ai/raw_review.py` module was required (resolver + review path kept thin/inside the CLI module that already imports the store and local_ai pieces). P07 persisted data is reused as-is.

7. **Tests**: `tests/test_phase_10a_raw_content_review.py` (new, hermetic).
   - Temp migrated DB.
   - Seed realistic raw email + calendar rows via the sanctioned `upsert_*_raw_content`.
   - Seed V41 task + commitment candidates + `candidate_source_refs` (with excerpts) pointing at the raw rows.
   - Assert: raw detail getters return full bodies; candidate lists + refs work; resolution from ref → full raw succeeds (the "actual content behind" path); review_status filter + `set_candidate_review_status` + `insert_candidate_review_event` transition status as expected; shapes contain the markers; full raw lives in V42 while only excerpts are in the ref rows.
   - Focused, safe markers (no integration/live/manual).

8. **Architecture + index**:
   - New `docs/architecture/215-phase-10a-prompt-08-frontend-raw-content-review.md`.
   - One-line append under the Phase 10A section of `docs/architecture/00-README.md` (following the 210–214 pattern).

## Data flow (review of a raw-backed candidate)
```
# Produce candidates (P07)
hb-assistant second-brain phase-10 raw-action-candidates --project P --apply --mock-output '...'

# See candidates + provenance excerpts (new P08)
hb-assistant second-brain phase-10 list-candidates --project P --review-status pending --json

# Inspect the *actual* full raw content behind a candidate's source ref (new P08)
hb-assistant second-brain phase-10 candidate-source --candidate-id C1 --candidate-type task --json
# → candidate row + source_refs + raw_content: {subject, body_text (full), ...}, _raw_content_included, guardrails, note

# (Alternative direct detail, also new P08)
hb-assistant graph mail raw-message --message-id-hash <hash-from-ref> --json
hb-assistant graph calendar raw-event --event-index-id <eid-from-ref> --json

# Decide (preserve/enable review actions, new P08, memory pattern)
hb-assistant second-brain phase-10 review-candidate --candidate-id C1 --candidate-type task \
    --decision accepted --reason "Reviewed raw thread; action is valid." --emit --json
# → review_status updated on V41 row; optional candidate_review_event; guardrails; dry-run by default
```

## Acceptance
- An operator with a seeded (or P07-produced) raw-backed candidate can run `candidate-source` (or the graph raw-detail commands) and see the **actual full subject + body_text (or calendar equivalent)** from the V42 row, with clear raw-mode markers and provenance.
- Review actions (`review-candidate`, status filter on list) are present and functional; they are the preserved path for changing `review_status`. Raw content informs but does not auto-accept.
- All prior no-raw, policy, dry-run, advisory, and guard-column invariants continue to hold outside these explicitly sanctioned review/inspect surfaces.
- Verification (ruff/mypy/pytest/manual) + architecture doc + manifest-titled commit performed; only intended files staged; final output is only the traditional commit summary + description.

## Invariants / guardrails (maintained + extended)
- Full raw bodies live **only** in the V42 tables (`email_message_raw_content`, `calendar_event_raw_content`, `email_thread_raw_context`).
- These P08 surfaces are the **sanctioned exception** for a human to see the full raw during review/inspect.
- All other paths (daily brief, MCP, Obsidian, retrieval Phase 09 packets, most review-burden/cluster outputs, etc.) remain metadata-only / no-raw.
- `RawContentPolicy` + endpoint `EndpointsConfig` + explicit flags still gate access; the CLI surfaces pass the same `include_raw`/`raw_mode` through.
- Advisory posture everywhere: `review_status` starts pending; decisions are explicit; `recommended_next_action=review`; no auto-promotion or writeback.
- Dry-run by default for any mutating review action (`--emit` to persist).
- Bounded excerpts remain in `candidate_source_refs.evidence_redacted`; full raw is only fetched on-demand in the inspect paths.
- Local-only: zero Graph calls on the review/inspect paths; all reads are SQLite via `ConstructionStore`.
- Guardrails blocks + human notes make the posture (review_inspect_only, full_raw only in sanctioned detail, etc.) visible in every payload.
- Idempotent, mockable where relevant (P07 extraction side), additive schema only.

## Non-goals (exact scope)
- No web UI / JS (Prompt 08 "Frontend" is the local CLI per repo constraints).
- No MCP raw surfaces (that's Prompt 09).
- No Obsidian inlining of raw (policy + separate planning).
- No change to deterministic (non-raw) action extraction or other review queues (construction, email, financial, etc.).
- No new schema (V41 candidates + refs + review_events + V42 raw pre-exist).
- No auto-promotion or downstream writeback from review decisions in this prompt.
- Full promotion lanes / `accepted_tasks` etc. left for later (the frontend contract in resources may define them).

## Verification evidence (in commit)
- Ruff + format clean (scoped).
- Mypy clean (scoped to touched modules).
- Focused safe pytest (`-k "phase_10 or raw or review or candidate or endpoint"`) passes, including the new `test_phase_10a_raw_content_review.py` (5+ scenarios: raw detail, candidate-source linking + full raw resolution, review status transitions + filter, guardrail shapes, no-leakage of full bodies into ref rows).
- Manual simulation (temp DB + seeds):
  - `phase-10 list-candidates` shows candidates + excerpts + source refs.
  - `phase-10 candidate-source` (and the graph `raw-message` / `raw-event`) emit full `body_text` etc. from V42 for the candidate's refs (beyond the stored excerpt).
  - `phase-10 review-candidate --emit` changes `review_status` (dry first shows no change); re-list confirms.
  - Payloads contain the documented guardrails + raw mode notes; exit codes correct (0/3).
- Architecture 215 + 00-README index line added.
- Only the 9 intended files (per plan) staged and committed under the manifest-titled message. No pre-existing evidence or unrelated changes included.

This prompt completes the local "see the actual content behind the candidate → decide" loop for Phase 10A raw action intelligence while preserving every prior guardrail and the advisory posture.
