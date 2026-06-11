# Phase 10 — Email Follow-Up Candidate Projection and Commitment Readiness

## Objective

Implement the next Phase 10 enhancement for `RMF112018/hb-personal-assistant`:

**Convert the V49 structured email/message/thread substrate into safe, source-linked, project-aware, reviewable daily-brief follow-up, task, and commitment candidates.**

The local code agent must execute this package as a one-shot implementation package with:

```bash
Execute the objective defined at docs/planning/phase-10-email-followup-candidate-projection-package/README.md
```

This package is implementation guidance only. It does not authorize external writeback, production DB mutation during validation, email sending, email drafting, calendar mutation, Graph/Procore writes, or raw private-content exposure.

## Background

Repo-truth sampled through the GitHub connector at `main`/commit family `e7c1b511...` indicates the first daily-brief projection slice has landed:

- PR 23 is present as `feat(second-brain): activate source-linked daily brief projection sli…`.
- PR 22 is present as `Fix/email calendar full raw content ingestion`.
- The V49 email/calendar raw-to-structured projection is now a first stage in the local-agent pipeline.
- The first slice deliberately leaves email/follow-up candidate projection unresolved and surfaces an email/follow-up data-gap card when raw or structured email exists but follow-up layers are empty.
- The correct next slice is not new raw ingestion. It is deterministic email/thread candidate projection using the structured read models and idempotent source-ref persistence.

Important repo-truth anchors to verify locally before editing:

- `src/hb_assistant/construction/email_calendar/projection_registry.py`
- `src/hb_assistant/construction/email_calendar/read_models.py`
- `src/hb_assistant/construction/second_brain/local_ai/projection_activation.py`
- `src/hb_assistant/construction/second_brain/local_ai/email_followup_readiness.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_candidate_writer.py`
- `src/hb_assistant/construction/second_brain/local_ai/source_ref_gate.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_run.py`
- `src/hb_assistant/construction/second_brain/local_ai/usefulness_gate.py`
- `tests/test_email_calendar_consumer_read_models.py`
- `tests/test_phase_10_first_slice_projection_activation.py`
- `tests/test_phase_10_email_task_extraction.py`

## Repo State Assumptions

Assume:

- Work starts from `main` after fetching `origin`.
- PR 23 has merged into `main`.
- The local repo may have uncommitted user changes. Do not overwrite them.
- The production SQLite DB exists at:
  `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- All DB validation must use `/tmp` copies.
- The local code agent may inspect the production DB read-only only when necessary to copy it or compute raw-free counts.

The first step is always `prompts/00_repo_truth_audit.md`.

## Implementation Scope

Implement a deterministic, raw-safe email follow-up candidate projection path that:

1. Uses V49 structured email/message/thread tables as the primary substrate.
2. Uses existing `body_ref` / `load_body(...)` raw body access only when strictly necessary and audited.
3. Extracts bounded/redacted candidates for:
   - waiting-on / response-needed items
   - stale-thread nudge candidates
   - Bobby/user commitments
   - third-party commitments
   - project-related action items
   - due/meeting/time-sensitive email follow-ups
4. Persists rows idempotently into applicable domain tables:
   - `follow_up_watch_items`
   - `task_candidates`
   - `commitment_candidates`
   - any existing email follow-up enrichment/review-safe table if repo truth says it is the active contract
5. Persists daily-brief rows through the central writer:
   - `daily_brief_action_candidates`
   - `candidate_source_refs`
6. Reuses existing project identity/project-key resolution.
7. Surfaces unresolved project-like items honestly for review; never invents project keys.
8. Replaces the email/follow-up data-gap card with real follow-up sections when eligible candidates exist.
9. Preserves the data-gap card when email rows exist but no follow-up candidates are produced.
10. Extends usefulness/status gates so silent follow-up projection failure cannot look like success.

## Explicit Out of Scope

- Sending email.
- Creating drafts.
- Replying to or forwarding email.
- Calendar creation/update/delete.
- Graph write APIs.
- Procore write APIs.
- SharePoint/OneDrive/Obsidian mutation.
- Production DB mutation during validation.
- Cloud LLM use on private raw content.
- Model-assisted extraction as a primary requirement.
- Exposing raw email bodies, HTML, private URLs, tokens, secrets, full recipient arrays, or model prompts/responses.
- Large unrelated refactors.
- Schema migration unless the repo-truth audit proves current tables cannot support idempotent candidate persistence.

## Safety Requirements

Follow `SCOPE_LOCKS.md` and `references/raw_safety_policy.md`.

Minimum safety posture:

- Prefer structured read models.
- Treat raw body access as exceptional.
- Audit every raw body read through the existing raw-content access-event mechanism.
- No raw body/HTML in logs, stdout, status JSON, browser output, evidence, markdown, tests, or exceptions.
- Bound and redact titles/summaries.
- Hash source refs.
- No private URLs, signed URLs, tokens, secrets, authorization headers, cookies, or model prompts/responses in evidence.
- Validation artifacts must pass the no-raw-leak scan.

## Expected Final Behavior

After implementation, an apply-mode daily run on a `/tmp` DB copy with structured email rows should show:

- `email_calendar_projection` runs first and succeeds or degrades honestly.
- New email follow-up projection stage or existing follow-up stage reports:
  - raw email available
  - structured email available
  - eligible messages/threads considered
  - candidates generated
  - candidates persisted by family/type
  - daily-brief candidates persisted
  - source-ref coverage
  - project-key coverage
  - unresolved review count
  - data-gap reason codes, if any
- Eligible email-derived follow-ups appear in daily brief sections such as `follow_up`, `waiting`, and/or `actions`.
- `candidate_source_refs` coverage is 100% for every persisted email-derived daily-brief candidate.
- Re-running on the same DB copy does not duplicate domain or daily-brief candidates.
- If email rows exist but no follow-up candidates are produced, the data-gap card remains and the usefulness gate does not allow misleading success.
- If candidates exist without source refs, the run fails/degrades honestly.
- If project-key coverage is unexpectedly low, the run reports a review-required condition rather than inventing project keys.

## Package Structure

```text
docs/planning/phase-10-email-followup-candidate-projection-package/
  README.md
  TRIGGER_PROMPT.md
  SCOPE_LOCKS.md
  VALIDATION_MATRIX.md
  FINAL_HANDOFF_TEMPLATE.md
  prompts/
    00_repo_truth_audit.md
    01_schema_and_read_model_audit.md
    02_email_followup_domain_contract.md
    03_deterministic_candidate_extractor.md
    04_candidate_persistence_and_source_refs.md
    05_project_resolution_and_review_queue.md
    06_daily_brief_integration.md
    07_usefulness_gate_and_status.md
    08_commitment_test_failure_resolution.md
    09_raw_safety_and_no_leak_hardening.md
    10_validation_and_evidence.md
    11_final_handoff.md
  references/
    expected_db_invariants.md
    email_followup_candidate_contract.md
    source_ref_contract.md
    raw_safety_policy.md
    usefulness_scorecard.md
    repo_truth_audit_summary.md
  templates/
    db_copy_validation_commands.md
    raw_safe_sql_checks.sql
    no_raw_leak_scan.md
    evidence_index_template.md
    merge_readiness_checklist.md
```

## Ordered Execution Sequence

Execute the prompt files in numeric order.

```bash
cd /Users/bobbyfetting/hb-personal-assistant

# Never work directly on main.
git fetch origin
git switch main
git pull --ff-only
git switch -c feature/phase-10-email-followup-candidate-projection

# Then execute:
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/00_repo_truth_audit.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/01_schema_and_read_model_audit.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/02_email_followup_domain_contract.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/03_deterministic_candidate_extractor.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/04_candidate_persistence_and_source_refs.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/05_project_resolution_and_review_queue.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/06_daily_brief_integration.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/07_usefulness_gate_and_status.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/08_commitment_test_failure_resolution.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/09_raw_safety_and_no_leak_hardening.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/10_validation_and_evidence.md
cat docs/planning/phase-10-email-followup-candidate-projection-package/prompts/11_final_handoff.md
```

Each prompt must start with:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main`, have unexplained dirty files, or cannot validate on a `/tmp` DB copy.

## Validation Requirements

Validation must cover:

- repo-truth before/after diff
- unit tests for deterministic extractor
- unit tests for idempotent persistence
- source-ref coverage tests
- project-key review behavior tests
- daily-run integration tests
- usefulness-gate contradiction tests
- known-bad commitment regression
- DB copy replay
- idempotency replay
- no-raw-leak scan
- guard-column proof
- final usefulness scorecard

Use `VALIDATION_MATRIX.md` as the acceptance gate.

## Evidence Requirements

Create an evidence directory:

```bash
EVIDENCE_DIR="docs/evidence/phase-10-email-followup-candidate-projection"
mkdir -p "$EVIDENCE_DIR"
```

Minimum required evidence:

```text
00-repo-truth.md
01-schema-and-read-model-audit.md
02-domain-contract.md
03-extractor-results.md
04-persistence-and-source-refs.md
05-project-resolution-review.md
06-daily-brief-integration.md
07-usefulness-gate-status.md
08-commitment-regression.md
09-no-raw-leak.md
10-db-copy-validation.md
11-idempotency-replay.md
12-guard-column-proof.json
13-usefulness-scorecard.md
14-final-handoff.md
```

Evidence must be raw-free. Do not paste private message subjects, body text, HTML, recipient arrays, URLs, tokens, secrets, prompts, or model responses.

## Stop Conditions

Stop and report without further edits if any of the following occur:

- You are on `main`.
- Production DB would be mutated.
- Any validation path would send/draft email or mutate calendar/Graph/Procore/SharePoint/OneDrive/Obsidian.
- A raw body/HTML/private URL/token/secret appears in stdout, evidence, status JSON, browser output, or tests.
- Source-ref coverage for email-derived daily-brief candidates is below 100%.
- Re-run on the same `/tmp` DB copy duplicates candidates.
- The usefulness gate can report success when structured email rows exist but follow-up candidate projection silently fails.
- The pre-existing commitment persistence failure is not explained and either fixed or explicitly quarantined with evidence.
- Schema changes are proposed without proof that current tables cannot support the slice.

## Final Handoff Requirements

Use `FINAL_HANDOFF_TEMPLATE.md`.

The final handoff must include:

- branch
- commit SHA, if Bobby requested commits
- changed files
- tests run
- DB copy validation results
- candidate counts
- source-ref coverage
- project-key coverage
- guard-column result
- no-raw-leak result
- known failures
- production safety statement
- merge readiness statement
