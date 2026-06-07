# 209. Phase 10 Local Action Intelligence — AI Job Queue and Run Receipts

Date: 2026-06-07

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 05)

## Decision

Implement the AI-job lifecycle Prompt 04 deferred — **enqueue → claim → run → receipt** over the V41
`ai_job_queue` / `ai_job_runs` tables — with **no-overlap** (single-flight) execution, **retry/backoff**,
**dry-run default**, and **environment isolation**. Prompt 04 left `ai-jobs run --apply` hard-blocked
(`apply_not_enabled_in_p04`) and shipped no `enqueue`; Prompt 05 replaces that with the real lifecycle.

**No new migration, no new contract/seed.** V41 `ai_job_queue` (`status`, `priority`,
`idempotency_key`, `retry_count`, `max_retries`, `last_error_redacted`, `started_utc`, `finished_utc`,
`environment`, `UNIQUE(environment, job_type, idempotency_key)`) and `ai_job_runs` (`run_kind`,
`status`, `dry_run`, counts, `blockers_json`) already carry everything. `phase_10_ai_job_contract.json`
already lists job_types, statuses, `required_receipt_fields`, and guard_columns; the
`phase_10_ai_job_policy` seed already defines `max_concurrent_jobs`, `max_retries`,
`retry_backoff_seconds`. `LATEST_SCHEMA_VERSION` stays at 42.

## Store (`construction/store/repositories.py`)

Additive methods mirroring the existing run-row and idempotent-enqueue patterns; the 13 no-raw /
no-writeback guard columns are pinned to literal `0` on every insert:

- `enqueue_ai_job(...) -> bool` — `INSERT OR IGNORE` keyed by the UNIQUE constraint (True if new).
- `claim_eligible_ai_jobs(*, environment, limit, backoff_seconds, now=None)` — `status='queued'`,
  `retry_count < max_retries`, and (per `ai_job_runs` history) the latest run finished ≥
  `backoff_seconds` ago; ordered `priority ASC, queued_utc ASC`.
- `mark_ai_job_running` / `complete_ai_job(..., increment_retry=...)` — queue status transitions.
- `insert_ai_job_run` / `complete_ai_job_run(...counts...)` — the `ai_job_runs` receipt lifecycle.
- `list_ai_jobs` / `latest_ai_job_run` — reads for `status --list` and backoff.

**Retry-backoff eligibility is computed from `ai_job_runs.finished_utc` history** (helper
`_utc_older_than`), so no `next_eligible_utc` column was added.

## Orchestration (`construction/second_brain/local_ai/ai_jobs.py`)

- `enqueue_ai_job_request(...)` — validates `job_type` against `phase_10_ai_job_contract.json`,
  defaults `idempotency_key` to a deterministic daily hash of `(job_type, source_watermark, date)`,
  dry-run previews the would-be row (no write).
- `run_ai_jobs(...)` — the lifecycle:
  1. **No-overlap lock** — reuse `run_registry.acquire_run_lock(run_kind="ai_jobs_run",
     lock_name=f"ai_jobs_{environment}", locks_dir=..., dry_run=...)`; a live lock ⇒
     `{status:"blocked", blockers:["run_overlap_blocked"]}`; `release_run_lock` in a `finally`.
  2. **Claim** up to `max_items` eligible jobs (`max_concurrent_jobs=1` ⇒ sequential).
  3. Per job: `mark_ai_job_running` + open an `ai_job_runs` row → run the handler (drives the Prompt 04
     `StructuredOutputClient` over the bundled `tests/fixtures/local_ai/*`, validating each against
     `ActionCandidate` and writing a hash-only `local_model_run_receipts` row) → finalize counts +
     queue `status='succeeded'`.
  4. **On failure** (unavailable backend or zero valid candidates): `increment_retry`; back to
     `queued` until `retry_count` reaches `max_retries`, then `failed`; record a redacted category
     code in `last_error_redacted` (never raw error text).
  5. **Dry-run default**: claim + simulate, **zero writes**; report would-be transitions.

Run-row timestamps accept an injected `now` so retry/backoff is deterministic under test.

## CLI (`cli/second_brain.py`)

- `second-brain ai-jobs enqueue --job-type <t> [--environment dev] [--idempotency-key] [--priority] [--source-watermark] [--db] [--dry-run/--apply]` — idempotent; exit 0 enqueued/preview/exists, 2 invalid job_type.
- `second-brain ai-jobs status [--environment] [--list] [--db]` — adds `--list` (metadata-only queued/running rows).
- `second-brain ai-jobs run [--environment dev] [--max-items N] [--db] [--dry-run/--apply]` — replaces the P04 apply-block with `run_ai_jobs(...)`; exit 0 ok, 2 blocked (no-overlap). Now **queue-driven** (an empty queue is a clean no-op), so the standalone `run --dry-run` shows `claimed: 0` until jobs are enqueued.

Exports `enqueue_ai_job_request` / `run_ai_jobs` from `local_ai/__init__.py`.

## Environment isolation

`--environment` (default `dev`) is written into `ai_job_queue.environment`; `--db` selects the SQLite
path. Row-level isolation is enforced by the `environment` column + `UNIQUE(environment, job_type,
idempotency_key)`, and the no-overlap lock is named per-environment (`ai_jobs_<env>`). Full
profile-resolved dev/prod DB separation via `launcher/profiles.resolve_profile` remains available but
the CLI keeps the lighter env-label + `--db` model the existing `ai-jobs` commands use.

## Proof surface

`build_ai_jobs_proof()` (`local_ai/ai_jobs_proof.py`) drives enqueue → run → receipts → no-overlap →
retry/backoff → env-isolation on a throwaway temp DB (the app DB is never touched) and asserts both
V41 receipt tables' guard columns sum to 0. Evidence:
`docs/evidence/construction-intelligence-phase-10-local-action-intelligence/05-ai-job-queue-and-receipts-proof.{json,md}`.

## Guardrails

Local-only; idempotent; no-overlap single-flight; retry with backoff; dry-run default; jobs advisory;
high-stakes items review-only (via `ActionCandidate`); receipts hash-only; no Graph/Procore/email/
calendar writeback; dev/production isolated; structured output validated before any write.

## Out of scope (later prompts)

Real raw-content extraction at scale and richer job-type handlers (Prompt 06+), scheduled/launchd
invocation of `ai-jobs run`, and the frontend review queue.
