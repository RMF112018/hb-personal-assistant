# 88 — Phase 08B: Automation Execution Planner (Addendum Prompt 02)

**Phase:** 08B Automation Execution Completion Addendum — Prompt 02
**Status:** Planner (build plan + dry-run emit only). No full stage apply/runner, no gate flip. `automation_execution` remains `deferred_not_blocking`. Schema V34 unchanged.

**Baseline:** Post-P01 at `f8998a3` (P01 delivered executor policy/stage registry/safe-replay/weekend-catchup seeds + 5 contracts + 4 load fns + reason codes; 15/1 gates).

## Problem
P01 gave declarative substrate (policy + stage registry + replay + weekend/catchup contracts/seeds + loads + reason codes). The *execution planner* (deterministic request -> plan with stages + decisions for dup prevention / weekend / catch-up / replay safety, using the required default stages, supporting modes, dry-run emit-plan-only) was missing. Without it the surfaces (registry/locks/retry/health/freshness/08B delivery) remain un-orchestrated for the daily brief workflow.

## Design
New `automation_executor.py` (additive; reuses run_registry, retry_recovery, launchd_scheduler, automation_health, freshness, P01 loads/contracts, 08B delivery evaluate/run surfaces for core stages).

**Models** (Pydantic v2, extra=forbid, sanitizers):
- `ExecutionRequest` (run_kind, mode: manual|launchd|catch_up|replay, day_offset, force).
- `ExecutorStage` (name from the 8 required defaults, order, enabled, depends_on, mapped_to).
- `ExecutionDecision` (kind: duplicate_prevention|weekend_gate|catch_up|replay_safety|..., decision: proceed|skip|block, reason_code, detail).
- `ExecutionPlan` (request, stages, decisions, overall_status, dry_run, policy/stage versions, reason_codes_used, guardrails).

**Planner**:
- `_load_policy_and_registry()`: P01 loads (executor + stage + retry + weekend + main) + contract cross-check + validate.
- `_weekend_catchup_decisions()`: reuses `evaluate_first_run_after_wake` + P01 weekend seed/policy.
- `_duplicate_prevention_decision()`: read-only view via `read_run_lock` + registry (block with `RUN_OVERLAP_BLOCKED` etc.; force/replay bypass).
- `_build_stages_from_registry()`: required defaults (preflight_status -> health+freshness; source_freshness_check -> evaluate_source_freshness; daily_brief_generate -> 08A core; local_html_deliver / macos_notification_emit / delivery_receipt_record / job_health_update / closeout mapped to 08B surfaces) + registry order/depends.
- `build_execution_plan(...) -> ExecutionPlan`: always builds full plan; `dry_run=True` (default) emits plan only (no side effects, no 08A apply, no locks/register/deliver/notify/receipts). Returns model (CLI/evidence use `.model_dump()`).
- `run_execution_planner(...)`: thin wrapper (dry always plans; non-dry stub for P02).
- `build_automation_executor_dry_run_plan_proof()`: temp paths, call in dry_run, assert exact 8 stages, decisions, no-raw, proof_passed, guardrails.

**Modes**: manual (normal), launchd (scheduled), catch_up (force first-run-after-wake), replay (idempotent via P01 safe_replay_contract + registry/lock/receipts).

**CLI (minimal additive in second_brain automation_app)**: `plan-execution --json --dry-run --mode catch_up` (emits plan + guardrails; follows existing automation status/reason patterns).

**Tests** (`test_automation_executor_planner.py`): ordering/defaults, invalid kinds, weekend/catch-up, dup prevention (force bypass), replay, dry-run no-side-effects + plan emit, proof, P01 substrate versions/codes.

**Evidence**: exactly `automation-executor-dry-run-plan.json` (live plan with 8 stages + sample decisions for catch_up mode).

No schema (V34/151), no gate change (still 1 deferred), no overstatement (plan shows decisions + blocked reasons; dry-run never applies).

## Guardrails
local-first; dry-run default + "emit plan only"; no external delivery/writeback/raw (sanitizers + 9 guards via reused surfaces); artifacts outside repo; fail-closed (notification emit etc. still policy-gated); reason codes from P01 shared vocab; additive; automation_execution deferred.

## Known limitations / next
- Planner only (build + dry-run emit); full apply (lock/register/invoke stages + surfaces/release + receipts) + wiring to legacy orchestrator deferred to later addendum prompt(s).
- "daily_brief_generate" stage maps to 08A core (no new code here).
- No change to PHASE_08B_GATE_NAMES / data_quality / safety (gate stays deferred until real executor + proof).
- CLI surface is preview (plan-execution); full `execute` with --apply later.

## Validation outputs (Prompt 02)
| Command | Result |
|---|---|
| `python -m compileall src tests` | 0 |
| `ruff check .` | clean |
| `mypy src` | 254 files, success |
| `pytest -m "not live..." -k "executor or planner"` | 0 fail (new tests pass) |
| `hb-assistant construction-agent validate --json` | 4/4, schema=34 |
| `hb-assistant second-brain data-quality phase-08b-gates --json` | 15 pass / 0 / 0 / 1 deferred (unchanged; automation_execution still deferred) |
| `hb-assistant second-brain data-quality no-writeback-proof --json` | proof_passed=true, no_raw_html_persisted=true, schema=34 |
| python planner smoke (dry_run plan + proof) | exact 8 stages, decisions, dry_run, no side effects, codes/versions from P01 |

See `docs/evidence/.../automation-executor-dry-run-plan.json` + arch 88-.

**Next:** later addendum prompts implement apply/runner (using this planner's output), update gate proof, closeout (P15 plan).

No executor behavior, no schema, no readiness overstatement.
