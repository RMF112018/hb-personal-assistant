# 208. Phase 10 Local Action Intelligence — Local Model Structured Output Client

Date: 2026-06-07

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 04)

## Decision

Add a reusable, schema-enforced **structured-output client** that turns a free-form local-model call into a validated, auditable run, and wire the Prompt 04 CLI surfaces on top of it. The client is the first runtime consumer of the V41 `local_model_run_receipts` table (Prompt 02 laid it; nothing wrote to it before). It is independent of and does **not** refactor the Phase 10A Prompt 07 extractor (`raw_action_intelligence.py`).

## Client (`construction/second_brain/local_ai/structured_output.py`)

`StructuredOutputClient.run(...)` performs, in order:

1. **Heavy-profile gate** — a `heavy_profile` profile refuses to run unless `heavy_enabled=True` (`status="blocked"`, redacted reason). Profile-shape invariants are already enforced by the Prompt 01 Pydantic models.
2. **Backend resolution** — an injected `GenerationBackend` (a narrow `Protocol`: `generate_json(*, system, prompt) -> str`, satisfied structurally by the existing `OllamaChatClient`), else a real `OllamaChatClient(model=profile.model_name, timeout=float(profile.timeout_seconds))`. Timeout always comes from the resolved profile.
3. **Generate → validate** — output is `json.loads`-parsed and validated with `schema.model_validate(...)` (e.g. `ActionCandidate`) **before** it is trusted. Bad JSON / `ValidationError` never crash the run.
4. **Bounded self-repair** — up to `_MAX_ATTEMPTS` (3) on the primary profile, appending a redacted repair instruction (never the raw output).
5. **Single-hop fallback** — on terminal failure, resolve `LocalModelProfiles.fallbacks[profile_id]` (one hop only, matching the single-hop seed), retry once, set `fallback_used=True`.
6. **Hash-only receipt** — `input_context_hash` / `output_hash` are SHA-256[:12] prefixes via the shared `procore.normalizers.hashing.hash_summary`. In `dry_run` (default) the receipt is **not** written and the would-be fields are surfaced under `would_write_receipt`; otherwise exactly one `local_model_run_receipts` row is written through the store.
7. **Redacted errors** — backend/timeout/validation errors map to a closed status set (`ok | schema_invalid | unavailable | timeout | failed | blocked`) plus a category code; raw exception text stays only in the in-memory `StructuredOutputResult`, never in the row.

`StaticOutputClient` is the in-module offline/test backend (canned JSON, scripted bad-then-good sequences, or simulated unavailability). `action_candidate_dict_from_fixture(...)` deterministically builds a complete `ActionCandidate` from a `tests/fixtures/local_ai/*` fixture's already-redacted fields.

## Store (`construction/store/repositories.py`)

- `insert_local_model_run_receipt(...)` — the only write path to `local_model_run_receipts`. By contract it accepts **hashes + metadata only** (no parameter can carry raw prompt/response/body/URL/token/path); the 13 no-raw / no-writeback guard columns are pinned to literal `0` in the INSERT (mirroring `insert_download_receipt`).
- `ai_job_status_summary(environment=None)` — read-only queue counts by status + recent `ai_job_runs` aggregates, scoped by environment (dev/production isolation via `ix_ai_job_queue_env_status`).

No new migration: V41 (`LATEST_SCHEMA_VERSION = 42`) already provides every table.

## CLI surfaces (`cli/second_brain.py`)

Top-level `second-brain` groups (paths fixed by the Prompt 04 validation contract):

- `second-brain local-model status [--mock] [--heavy-enabled] [--write-evidence] --json` → `build_local_model_status()` (Prompt 03 readiness; exit 0 ready / 3 not-ready). `--write-evidence` finally emits `03-local-model-status-proof.{json,md}`.
- `second-brain ai-jobs status [--environment] [--db] --json` → `ai_job_status_summary()`.
- `second-brain ai-jobs run --dry-run --max-items N [--profile] --json` → dry-run the client over local fixtures; **zero writes** (no receipt, no enqueue, no run row); counts + blockers. `--apply` is intentionally blocked in Prompt 04 (`apply_not_enabled_in_p04`) — the queue/enqueue lifecycle is a later prompt.
- `second-brain action-intel extract-fixture --fixture PATH [--apply] [--db] --json` → run the client over one fixture and emit the validated `ActionCandidate` (advisory; no DB write unless `--apply`, and even then only a hash-only receipt).

## Proof surface

`build_structured_output_client_proof()` (`construction/second_brain/local_ai/structured_output_proof.py`) exercises the client over the bundled fixtures with the offline backend and proves: fixtures schema-valid, heavy-profile blocked, unavailable→redacted+fallback, dry-run zero writes, apply→single hash-only receipt with guard-sum 0. The apply demonstration runs against a throwaway temp DB (the user's app DB is never mutated). Evidence: `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/04-structured-output-client-proof.{json,md}`.

## Guardrails

Local-only; schema-validated before any write; receipts hash-only (no raw persisted); no Graph/Procore/email/calendar writeback; dry-run default; heavy profiles blocked unless explicitly enabled; high-stakes safety categories remain review-only (enforced by `ActionCandidate`); errors redacted to category codes.

## Out of scope (later prompts)

Job-queue enqueue/execution + `ai_job_runs` lifecycle (apply path), candidate-row writing from real raw content at scale, Obsidian writer, MCP packet builder, frontend review queue.
