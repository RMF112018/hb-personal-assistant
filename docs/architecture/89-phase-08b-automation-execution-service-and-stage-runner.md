# Phase 08B Prompt 03 — Automation Execution Service and Stage Runner

**Status**: Active (Prompt 03 of Automation Execution Completion Addendum).  
**Baseline**: Post-P02 (HEAD after planner + dry-run-plan evidence + arch 88; V34/151 tables; automation_execution gate still deferred_not_blocking).  
**Package**: HB_Construction_Intelligence_Phase_08B_Automation_Execution_Addendum_Package/00_PACKAGE_MANIFEST.md (Prompt 03).

## Objective (verbatim)
Implement the executor service and stage runner per the 10 required work items + stage integration using existing internal services for daily brief generation, local HTML delivery, macOS notification, delivery receipt, and job health (no real external calls). Produce exactly the two named evidence files. After changes: update architecture, run verification suite, commit with manifest title+version, output ONLY the commit summary+description.

## Context & Scope
- P00: repo-truth audit + baseline (no executor impl; substrate sufficient; no schema gap).
- P01: policy/contracts/seeds + reason codes + no-schema rebaseline (automation_execution remains sole deferred).
- P02: deterministic planner (Execution* models, DEFAULT_STAGES 8, build_execution_plan dry-emit-only + decisions for dup/weekend/catchup/replay, proof, CLI plan-execution, dry-run-plan.json evidence, arch 88).
- P03 (this): turns planner into controlled `AutomationExecutor` service (dry vs apply, --apply --confirm two-factor, lock before registry before ordered stages, per-stage dispatch + receipts, fail+downstream skip, guaranteed release, recovery rec, injected fakes for tests). CLI execute + execution-status. New test + 2 evidence + arch 89.

Non-goals (per addendum guardrails + explicit): no legacy MorningRunOrchestrator bridge, no gate flip, no external delivery/writeback, no raw persistence, no schema, no MCP/LlamaIndex.

## Design
### Models (additive to P02)
- `StageReceipt` (stage, order, status in {succeeded,failed,skipped_downstream}, timestamps, duration_ms, reason_code, detail (bounded/redacted), receipt_ids).
- `ExecutionResult` (request, plan, run_registry_id, stage_receipts list, overall_status, recovery_recommendation dict|None, guardrails, lock_released, schema_version=34).

All Pydantic v2, `extra="forbid"`, pass through `_sanitize`.

### AutomationExecutor
- `__init__` accepts `dry_run=True`, `confirm:bool|None=None`, `db_path`, `locks_dir`, `now`, and 5 injectable callables (brief_gen, html_render, macos_notify, deliver, job_health). Defaults delegate to the real internal run_/evaluate_ surfaces (imports inside methods for hygiene).
- `execute(req)`: always builds plan via P02 `build_execution_plan` (dry). If dry or not `_confirmed()`: return dry/blocked result (no lock/registry). Else:
  1. `acquire_run_lock(run_kind, locks_dir, dry_run=False)`.
  2. If not acquired/reclaimed: return blocked (no register).
  3. `register_run(..., status="started", reason_code="EXECUTOR_STARTED", lock_token, emit=True, db_path)`.
  4. For each of 8 `DEFAULT_STAGES` in order:
     - if prior failed: `record_run_step(..., "skipped_downstream", "STAGE_DOWNSTREAM_SKIPPED")`, append StageReceipt, continue.
     - else: timed `_run_stage(stage, run_id, req)` (dispatch), `record_run_step(..., "succeeded", ...)` or on exc "failed" + "EXECUTOR_FAILED", set failed flag.
  5. `finish_run(..., status=succeeded|failed, reason=EXECUTOR_SUCCEEDED|FAILED)`.
  6. If failed: `_generate_recovery_recommendation(...)`.
  7. `finally: release_run_lock(token)`.
- `_run_stage`: maps name → call to existing internal with `mode="apply"`, `emit_receipt=True`, `db_path`, `brief_date`, isolation dirs, injected notifier=None etc. Returns dict with status/reason/receipt_id. Handles tuple returns from some run_*_agent.
- `_generate_recovery...`: returns human dict with "recommendation", "failed_stage", "run_registry_id", "suggested_next" (safe CLI strings using --apply --confirm + run-recovery first), guardrails. No tokens/secrets/URLs/raw.
- `run_automation_execution(req, apply=False, confirm=False, **ctor)`: thin wrapper used by CLI/tests (sets dry_run=not (apply and confirm)).

### Stage Integration (reuse, not reimplement)
- preflight_status → `run_automation_health` + `evaluate_source_freshness` (or runtime).
- source_freshness_check → `evaluate_source_freshness`.
- daily_brief_generate → `run_daily_brief(..., mode="apply", emit_receipt=True, vault_brief_dir=...)`.
- local_html_deliver → `run_daily_brief_html_render_agent(..., mode="apply", html_dir=..., emit_receipt=True)`.
- macos_notification_emit → `run_daily_brief_notification_agent(..., mode="apply", emit_receipt=True, notifier=..., policy_emit=...)` (fakes ensure 0 osascript).
- delivery_receipt_record → `run_daily_brief_delivery_agent(..., mode="apply", vault_brief_dir=..., emit_receipt=True)`.
- job_health_update → `run_daily_brief_job_health(..., emit_receipt=True)`.
- closeout → final health snapshot + finish_run (registry already closed outside dispatch).

All calls pass isolation (db_path, temp dirs in tests) + emit_receipt=True so surfaces write their V28 agent receipts + domain receipts (V31 delivery, V32 html, V33 notify) using existing writers.

### Receipt Persistence (no schema)
- Per-stage ledger: `record_run_step(run_registry_id, step_name, step_order, status, reason_code, detail, db_path)` → V29 `second_brain_run_steps`.
- Domain side-effects: the run_*_agent(emit_receipt=True) paths inside surfaces emit V28 `second_brain_agent_run_receipts` + V31+ specific (delivery/HTML/notify) — metadata+hashes+counts+fixed channels only (existing CHECKs + redaction).
- run_id links the execution; closeout uses `finish_run`.
- This satisfies "persist stage receipts" using pre-existing V29 + V28+ (P00/P01 confirmed at V34/151).

### Lock & Registry Orchestration
- Manual acquire (before any register) + register + per-stage record + finish + finally release. Matches "acquire no-overlap lock before execution / open run registry record / release on controlled completion".
- coordinate_no_overlap_run left as-is (useful for simple cases; executor interleaves real stage work between lock and release).

### Failure Handling
- First failure: record "failed" + EXECUTOR_FAILED + detail (bounded), set flag.
- Subsequent stages: record "skipped_downstream" + STAGE_DOWNSTREAM_SKIPPED + detail="after X", append receipts.
- Still finish_run(failed), release in finally, produce recovery rec.
- Exception in any stage or closeout: finally still releases.

### Guardrails & Safety (enforced)
- dry-run default; apply only with explicit confirm (CLI + inside executor).
- All results sanitized (no raw_body/prompt/response/token/secret/signed_url/download_url).
- Local-only artifacts (locks under app_support/locks, html under app_support/html; vault writes only via approved surfaces on eligibility).
- No external delivery/writeback (policy + fail-closed in surfaces).
- Proofs/tests use fakes + temp paths only; never touch real vault or fire real osascript.
- schema_version=34 asserted; no new mig.
- automation_execution gate remains deferred (P03 does not flip).

### CLI
- `second-brain automation execute --mode=... --day-offset=... [--apply] [--confirm] [--json]`: dry by default; real apply requires both flags (two-factor). Payload includes apply_requested/confirmed + result + guardrails. Exit 0 on dry/succeeded, 3 otherwise.
- `second-brain automation execution-status [--limit] [--json]`: thin read over latest daily_brief registry rows + steps (reuses existing run-registry surfaces). Guardrails payload.
- plan-execution remains unchanged (pure planner dry).

### Tests
- New `tests/test_automation_executor_service.py` (marker-safe).
- Uses `_FakeSuccess` / `_FakeFail` (record .calls, return success or raise; never real).
- Covers every required item + lock release on error, no side effects (temp dirs), proof builder, reason codes from P01 substrate.
- Evidence capture via the proof builder.

### Evidence (exactly as specified)
- `automation-executor-apply-simulated-run.json`: full ExecutionResult (or simulated_apply_result) from a proof run with fakes (plan + 8 receipts with mixed statuses, recovery on fail case, lock_released, guardrails, no raw).
- `automation-execution-proof.json`: return of `build_automation_execution_proof()` (proof_passed, counts, fakes_used, lock_guaranteed_release, confirm_enforced, schema 34, both success/fail/dry results, no raw).

### Architecture Cross-Refs
- Builds directly on P02 planner (same file, same DEFAULT_STAGES + plan emission).
- Reuses P09–P14 surfaces (delivery P09, HTML P10, notify P11, receipts P12, job-health P08) + run-registry/locks P05 + health/freshness P03/P07.
- Receipt model consistent with V28 agent receipts (reasoning) + domain V31–V34.
- No change to data_quality gates (automation_execution stays deferred), safety (no-writeback + no-raw), or schema (V34).

## Verification Performed (post-changes)
- compileall / ruff / mypy (255 files).
- pytest -m "not live..." (0 fails; new service tests + existing planner).
- hb construction-agent validate (4/4, schema 34).
- phase-08b-gates (15 pass / 0 fail / 0 warn / 1 deferred_not_blocking for automation_execution; covered).
- no-writeback / no-raw-html proof (passed + no_raw_html_persisted true, 34).
- Custom: proof builder + CLI plan-execution/execute (dry + --apply without confirm blocks) + execution-status smokes.
- Evidence files written from proof; no raw tokens in any committed json.
- git status clean after restores of churn; only intended files.

## Limitations & Next
- automation_execution gate remains deferred (flip only after >=1 real successful --apply --confirm run with receipts + recovery exercised).
- No bridge to legacy morning orchestrator (lock + registry already provide mutual exclusion).
- Real --apply --confirm in CLI will invoke real internals (generation may use local model; delivery writes approved note to vault; html to app_support/html; notify uses osascript only if policy allows and eligible). Tests always use fakes.
- Recovery is advisory (human follows with explicit confirm steps).

## Guardrails Attestation
All P03 changes preserve: local-first, dry default, --apply --confirm only, no external writeback/delivery, no raw persistence (sanitizers + surface guards + DB CHECKs), artifacts outside repo, fail-closed, no schema, gate deferred, source traceability via receipts, no MCP/LlamaIndex.

Evidence bundles + this doc + repo code/tests are authoritative.

(End of 89-.)
