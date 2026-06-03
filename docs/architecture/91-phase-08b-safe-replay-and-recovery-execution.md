# Phase 08B Addendum Prompt 05 — Safe Replay and Recovery Execution (Architecture Note)

**Status**: Implemented (additive to P03 executor + P04 resilience). No schema change (V34/151 unchanged). Gate `automation_execution` remains `deferred_not_blocking`.

## Summary of Changes
- **Replay request validation** (contract-driven): `_validate_safe_replay` loads `phase_08b_safe_replay_contract.json` (checks: run_not_in_progress, lock_not_held_or_stale_reclaimable, brief_not_already_delivered..., no_inflight); queries V29 registry steps/status + locks + evaluate_daily_brief_delivery + recent succeeded runs for date. Early block before lock/register with SAFE_REPLAY_BLOCKED_* reasons.
- **ExecutionRequest extensions (additive)**: `original_run_registry_id`, `replay_selector` ("failed-only" | "failed-and-following" | "explicit"), `replay_stages: list[str]`; reuse `force` for delivery re-allow.
- **Selectors**: compute from original `read_run_steps` (failed_names, first_failed_idx); "failed-only" = just the failed; "failed-and-following" = from first failed to end; explicit = provided list intersected with plan. Effective stages filtered for dispatch.
- **New replay run + link (preserve original)**: register_run with reason_code="REPLAY_EXECUTION"; record_run_step("replay_link", reason="REPLAY_LINKED_TO_ORIGINAL", detail= original+selector+force+explicit). Original rows untouched (read-only queries only). New run independent.
- **Lock**: normal acquire_run_lock before register (same no-overlap guarantee).
- **--apply --confirm**: enforced in executor (before validation/lock) + CLI (two-factor; dry otherwise + blocked reason).
- **Block non-replay-safe**: REPLAY_SAFE_STAGES = {preflight_status, source_freshness_check, daily_brief_generate, job_health_update, closeout}; DELIVERY_STAGES = the 3 (local_html, macos_notify, delivery_receipt). Unsafe selected -> skipped_policy "STAGE_BLOCKED_NON_REPLAY_SAFE" (even if force only relaxes delivery).
- **Dedupe delivery unless force**: before delivery stage dispatch in replay: if not force and (registry recent success for brief_date or evaluate_daily_brief_delivery written): skip "SAFE_REPLAY_IDEMPOTENT_SKIP". Force bypasses (per policy "unless explicitly permits").
- **Recovery recommendation update**: suggested_next now includes --mode=replay --replay-of <id> --replay-selector failed-only (and failed-and-following example); keeps run-recovery (lock/orphan) + other.
- **Proof + evidence**: `build_safe_replay_execution_proof` pre-pops failed original (register + mixed steps), runs with fakes + apply+confirm + replay req (various selectors/force); asserts new run + link marker, original steps unchanged, fakes called only for selected (delivery 0 unless force), blocks/dedup, lock released, no raw, schema=34, contract checks, writes the exact `safe-replay-execution-proof.json`.
- **CLI**: automation_execute extended with --replay-of, --replay-selector, --replay-stages (parsed to req); validation error if replay without of (via executor block).
- **Exports/tests**: additive build_safe_replay... + test_p05_... in service test (asserts proof keys + selectors).
- **Arch**: new 91- + 00-README additive.

## Integration & Guardrails
- Reuses P02 planner (mode=replay decision/bypass still fires), P03 lock/register/record/finish/_run_stage/5 injected fakes + recovery, P04 dup checks + clock/sleep/inject + retry classify (orthogonal).
- All replay paths: lock first, new run only, preserve orig, effective dispatch with guards, finally release, receipts via V29 steps + domain emit.
- No external writeback/delivery (fakes in proof; real still gated by confirm + surfaces); dry default; --apply --confirm; local; sanitize; no raw.
- `automation_execution` gate stays deferred (proof covers "safe_replay_contract_satisfied" sub-requirement; full gate per history requires genuine end-to-end real apply success post-addendum; no overstate).

## Verification Performed
Full matrix (compileall, ruff, mypy ~255 0 issues, pytest non-live green, construction validate 4/4 s34, phase-08b-gates ~16/1 with automation deferred, safety/no-raw pass, CLI smokes for execute+replay flags dry+block, P05 proof gen + test asserts, evidence written clean).

No overstatement of readiness. Repository truth authoritative.

See package manifest `HB_Construction_Intelligence_Phase_08B_Automation_Execution_Addendum_Package/00_PACKAGE_MANIFEST.md` (Prompt 05) and the evidence JSON.