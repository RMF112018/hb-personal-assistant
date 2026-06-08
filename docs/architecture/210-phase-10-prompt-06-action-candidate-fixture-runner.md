# 210. Phase 10 Local Action Intelligence — Action Candidate Fixture Runner and Validation-Failure Harness

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 06)

## Context

Prompt 06 ("Action Candidate Output Contracts and Fixture Runner") was authored against a stale repo
baseline (package cites `HEAD c52cc757`, schema `V40`; the repo is now well past that at `V42`). Its
nominal deliverables — the `ActionCandidate` Pydantic model, the published JSON schema, a fixture
runner, and schema-validation-failure handling — **already landed** in earlier prompts:

- `ActionCandidate` model (`extra="forbid"`, closed enums, high-stakes routing validators) —
  `construction/second_brain/local_ai/models.py` (Prompt 01).
- Published schema — `resources/json/phase_10_action_candidate_output_schema.json` (Prompt 01).
- Single-fixture runner — `action-intel extract-fixture` + `action_candidate_dict_from_fixture()`
  (Prompts 04/05).
- Validation-failure handling — `StructuredOutputClient` (`schema_invalid` status, bounded
  self-repair, `extra="forbid"` rejection, redacted errors, single-hop fallback) (Prompt 04).

Per the explicit scope decision for this prompt, Prompt 06 does **not** recreate any of the above. It
fills the genuine gap: a **batch fixture validation / regression harness** covering positive,
negative, stale, malformed, low-confidence, high-risk, and unavailable scenarios, plus a
schema ↔ model parity guard and the Prompt 06 evidence artifact.

## Decision

Add a thin orchestration layer over the existing client + model that runs a directory of declarative
scenario fixtures, classifies each run's outcome, and asserts it against the fixture's declared
`expected_outcome`. **No new migration, contract, seed, model, or schema.** `LATEST_SCHEMA_VERSION`
stays at 42.

## Critical constraint — fixture isolation

`ai_jobs.py` enumerates fixtures with a **non-recursive** `Path("tests/fixtures/local_ai").glob("*.json")`.
Intentionally-invalid harness fixtures placed in that directory would break `ai-jobs run` and its
tests. All Prompt 06 suite fixtures therefore live in the subdirectory
`tests/fixtures/local_ai/fixture_suite/`, which the parent's non-recursive glob never sees. A
regression test (`test_suite_fixtures_excluded_from_ai_jobs_glob`) pins this.

## Runner (`construction/second_brain/local_ai/fixture_runner.py`)

`run_fixture_suite(*, fixtures_dir=DEFAULT_SUITE_DIR, profile_id="default_extract", store=None,
dry_run=True, low_confidence_threshold=0.4) -> dict`

- For each `*.json` in the suite dir, builds the deterministic offline backend the fixture's scenario
  calls for (checked in order): `malformed_payload` (raw non-JSON string) → `raw_candidate` (object
  fed directly to the validator) → `unavailable: true` → otherwise a positive fixture built with the
  shared `action_candidate_dict_from_fixture()` helper.
- Runs the existing `StructuredOutputClient` over `ActionCandidate` (dry-run), maps the closed run
  `status` (`ok | schema_invalid | unavailable | timeout | blocked`) to an `expected_outcome`
  category, and records `matched`.
- Surfaces advisory flags: `low_confidence` (validated `confidence` below threshold) and
  `high_risk_review` (validated `safety_category` in `HIGH_STAKES_CATEGORIES`), asserting high-risk
  candidates route to `review` (`high_risk_routing_ok`).
- Hash-only: only SHA-256[:12] `input_context_hash` / `output_hash` flow into rows — never raw
  payloads. Always dry-run; the optional `store` exists only so the evidence proof can assert a
  dry-run pass writes zero receipts.

Reuses (does not reimplement): `StructuredOutputClient`, `StaticOutputClient`,
`action_candidate_dict_from_fixture` (Prompt 04); `ActionCandidate`, `HIGH_STAKES_CATEGORIES`
(Prompt 01); `load_local_model_profiles` (Prompt 01); `PHASE_10_GUARD_COLUMNS` (Prompt 02).

## Suite fixtures (`tests/fixtures/local_ai/fixture_suite/`)

| Fixture | Scenario | Expected | Mechanism |
| --- | --- | --- | --- |
| `valid_task_candidate.json` | valid | valid | positive (`ok`) |
| `low_confidence_candidate.json` | low_confidence | valid | confidence 0.3 < threshold |
| `high_risk_review_candidate.json` | high_risk_review | valid | `safety_category=financial`, routes to review |
| `high_risk_preaccepted_invalid.json` | high_risk_preaccepted | schema_invalid | high-stakes + `review_status=accepted` rejected by model validator |
| `missing_required_field.json` | missing_required_field | schema_invalid | `raw_candidate` missing `title`/`source_refs` |
| `empty_source_refs.json` | empty_source_refs | schema_invalid | `source_refs: []` |
| `stale_forbidden_field.json` | stale_forbidden_field | schema_invalid | extra forbidden key → `extra="forbid"` |
| `malformed_json.json` | malformed_json | schema_invalid | non-JSON payload, rejected after bounded repair |
| `unavailable_backend.json` | unavailable_backend | unavailable | simulated unreachable backend |

The forbidden-field fixture carries a placeholder value (never a real body) precisely to prove it is
rejected and never persisted.

## CLI (`cli/second_brain.py`)

`hb-assistant second-brain action-intel run-fixtures [--fixtures-dir ...] [--profile ...] [--json]` —
registered in the existing `action_intel_app`. Advisory and dry-run only (no `--apply`; this is a
validation harness, not a write path). Exits `0` when every fixture matched, else `3`.

## Proof (`construction/second_brain/local_ai/fixture_runner_proof.py`)

`build_action_candidate_fixture_runner_proof(*, evidence_dir=None, write_evidence=False) -> dict`,
mirroring the Prompt 04 proof (not CLI-surfaced, not exported — invoked directly to emit evidence).
Gates: full matrix matched; the six required validation-failure behaviours (invalid JSON, missing
field, stale/forbidden field, high-risk→review with pre-accept rejected, no-accept-without-source-refs,
no raw persistence); and a dry-run pass with a throwaway store writes **zero** receipts with the 13
guard columns summing to 0. Emits
`docs/evidence/construction-intelligence-phase-10-local-action-intelligence/06-action-candidate-fixture-runner-proof.{json,md}`.

## Tests (`tests/test_phase_10_fixture_runner.py`)

- **Schema ↔ model parity** — `ActionCandidate.model_json_schema()` vs the published JSON schema:
  property-name sets agree, required sets agree (modulo the defaulted const
  `external_action_requires_approval`), and every enum field's member set agrees. Catches drift that
  the existing `test_phase_10_contracts.py` (which only checks `{"source_refs","confidence"} <= required`)
  does not.
- **Six-scenario matrix** via `run_fixture_suite`: success, high-risk→review (with pre-accept
  rejected), unavailable dependency, invalid (missing field) schema, stale (forbidden field) schema,
  no-raw/no-writeback (temp store → 0 receipts, raw absent). Plus malformed-JSON, empty-source-refs,
  and low-confidence assertions.
- **Glob-safety regression** — `ai_jobs._load_fixtures` over the parent still returns only the
  original four flat fixtures.
- **Proof** — `proof_passed`, `guard_sum == 0`, `dry_run_receipt_rows == 0`.

## Guardrails

Local-only; no Graph/Procore/email/calendar writeback; advisory and dry-run (no DB write); structured
output validated against `ActionCandidate` before any (here: zero) write; high-stakes items stay
review-only; only hashes surfaced (no raw prompt/response/body/URL/token/path); suite fixtures
isolated from the `ai_jobs` glob. Consistent with Prompts 01–05, this prompt does **not** bump the
phase README or root README "Repository Status" ledger; ledger normalization is deferred to a later
dedicated closeout.
