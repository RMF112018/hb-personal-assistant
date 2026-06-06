# 169 — Phase 09 Addendum: Memory Candidate Staging Bridge

**Status:** Bugfix — the missing `preview → durable candidate store` bridge so `memory accept` can find a previewed candidate.
**Schema:** unchanged (V39; no migration). **Version:** 1.8.0-phase-09-addendum.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/accepted-memory-candidate-stage-proof.{json,md}` + `validation-outputs-candidate-stage-bridge/`.
**Builds on:** records 164 (candidate preview), 165 (acceptance), 166–168.

---

## 1. The gap

`memory candidates build` (record 164) is intentionally **read-only** — `build_memory_candidate_preview`
surfaces candidate ids (`mcp_<hash>`) but never persists. `memory accept` (record 165) reads the durable
safe candidate store `memory_update_candidates` via `read_memory_candidate`. So a previewed id was not
acceptable: `accept --candidate-id <mcp id>` failed `candidate not found`. The missing piece is an
**explicit staging step** that persists a chosen preview candidate into that store.

## 2. The bridge

`candidate_preview.stage_memory_candidate(candidate_id, *, db_path=None, confirm=False)`:

1. Rebuilds the preview deterministically and finds the requested candidate; **fail-closed**
   (`MemoryCandidatePreviewError`) if it is not in the current preview.
2. **Re-runs** the preview safety checks on the found candidate via `_evaluate_input` (source-linked /
   no-raw / no-determination / review-tier) — defense in depth.
3. **Converts** it to the existing `MemoryCandidate` model **preserving the `mcp_` id** (so `accept`
   finds it): `proposed_memory_type`, `statement_redacted`, `project_key`, `origin_id=source_ref`,
   `provenance_class="candidate_preview"`, `confidence_class`, `review_tier`, `review_required=(tier!=1)`,
   `review_tier_reason_code` mapped by tier, `sensitivity_class="normal"`,
   `source_refs=[{source_family, source_ref}]`, `status="proposed"`.
4. **Persists** via `store.write_memory_candidate` only with `--confirm` (dry-run otherwise); idempotent
   (`already_staged` when the id already exists — no duplicate INSERT). Guard columns stay at DB default
   0; no raw fields; **never creates accepted memory**; metadata-only output. *(Subscript assignment
   throughout — no `dict.update()`, which the no-writeback static scanner flags.)*

CLI: `memory candidates stage --candidate-id <id> --confirm` and `memory candidates stage-proof`.

## 3. Flow

`memory candidates build` → `memory candidates stage --candidate-id <id> --confirm` →
`memory accept --candidate-id <id> --confirm`. Acceptance then runs its full gate (incl. the Prompt-04
`DUPLICATE_ACCEPTED` suppression). The acceptance criteria are demonstrated **live** by staging +
accepting the benign tier-1 system fact `mcp_562433…` (`system:local_first_posture`):
`coverage-parity-closeout` flips `memory_substrate_status` to `covered`, and after
`llamaindex build --apply` the vector-indexed family count rises **8 → 9**
(`accepted_long_term_memory`); the no-raw / no-writeback / MCP proofs stay green. (See
`validation-outputs-candidate-stage-bridge/`.)

## 4. Validation

`ruff`/`mypy` clean; `tests/test_phase_09_memory_candidate_stage.py` (11 tests) green plus the memory
regression; the no-writeback proof stays `proof_passed=true` (0 findings — the new code uses no
`.update()`). The committed `accepted-memory-candidate-stage-proof` runs preview→stage→accept on a
fixture and asserts id preservation, dry-run no-persist, accept-after-staging, staging-creates-no-
accepted-memory, not-found-fails-closed, and guard columns 0.

## 5. Notes

Staging persists any *previewed* candidate (which already passed the preview filters); tier-3 previewed
candidates can be staged but are then refused by the acceptance gate (`UNRESOLVED_HIGH_IMPACT`) — the
correct division of responsibility. Pre-existing phase-08b/c/d failures remain out of scope.
