# Phase 08A — Prompt 10: Long-Term Memory, Memory Curator (A07) + Operator Preference (A08) — Run Proof

Source-linked, review-controlled long-term memory + reviewable operator preferences.
Sensitive/high-impact memory routes to Tier 3 (never auto-accepted); promotion happens
only via explicit operator review; accepted preferences can never override safety policy.

## Repo-truth preflight

- Baseline `git rev-parse HEAD`: `c932dac` (Prompt 08 HEAD).
- Package repo-truth baseline cited by the prompt: `c2656e1c9606662d7e6d86ef80f5715540216912`.
- Schema head **V26** (unchanged); contract table count **141** (unchanged).
- No migration — all 7 memory/preference/feedback tables already ship in V26. No contract
  registration change (all 6 contracts registered + tested in Prompt 02).

## Files changed

Created:
- `resources/config/phase_08a_memory_policy.seed.yaml`, `phase_08a_operator_preference_policy.seed.yaml`
- `src/hb_assistant/construction/second_brain/memory/{__init__,models,policy,store,curator,preference}.py`
- `tests/test_memory_policy.py`, `tests/test_memory_curator.py`, `tests/test_operator_preference.py`, `tests/test_second_brain_memory_cli.py`
- `docs/architecture/66-phase-08a-long-term-memory-and-operator-preferences.md`
- `docs/evidence/.../long-term-memory-proof.json`, `.../memory-curator-agent-proof.json`,
  `.../operator-preference-proof.json`, `.../10-long-term-memory-and-operator-preferences-proof.md`

Modified:
- `src/hb_assistant/construction/second_brain/__init__.py` (memory re-exports)
- `src/hb_assistant/cli/second_brain.py` (`memory candidate|review`, `preference capture`)

## Validation commands + results

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src` | 0 | clean |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in 230 source files |
| `pytest tests/test_memory_policy.py tests/test_memory_curator.py tests/test_operator_preference.py tests/test_second_brain_memory_cli.py` | 0 | 27 new tests passed |
| `pytest -m "not live and not integration and not manual"` | 0 | full suite green |
| `construction-agent validate --json` | 0 | summary 4/4 passed, ok=true |
| `construction-agent data-quality table-inventory --json` | 0 | schema_version=26, contract_table_count=141 |
| `construction-agent data-quality no-writeback-proof --json` | 0 | proof_passed=true (unchanged) |
| `second-brain memory candidate --sensitivity financial …` | 0 | review_tier=3, T3_SENSITIVE_HIGH_IMPACT, review_required |
| `second-brain preference capture --type personnel …` | 0 | review_tier=3, pending_review |

## Evidence proofs (all proof_passed: true)

- `memory-curator-agent-proof.json` — normal candidate → Tier 1; sensitive (financial) →
  Tier 3 (`review_required`); explicit accept promotes to `long_term_memory_items` with
  origin + quality signals; guard columns 0; no raw content; no silent acceptance.
- `long-term-memory-proof.json` — accepted memory persists origin_id + source refs +
  origin/quality signals; review_status accepted; guard columns 0.
- `operator-preference-proof.json` — low-risk preference → Tier 2 pending; sensitive →
  Tier 3; accepted preferences applied only for allowlisted presentation keys, all
  safety-affecting / non-accepted preferences dropped (cannot override safety).

## Guardrail proof points

- **Sensitive/high-impact → Tier 3**: `classify_memory_tier` + `classify_preference` route
  legal/contractual/claim/personnel/safety/financial/entitlement/schedule_impact to Tier 3
  with `T3_SENSITIVE_HIGH_IMPACT` (`test_sensitive_memory_routes_tier_3`).
- **No silent acceptance**: `propose_memory_candidate` never writes a memory item; only an
  explicit `review_memory_candidate(decision="accepted")` promotes
  (`test_propose_does_not_create_memory_item_no_silent_acceptance`).
- **Accepted preferences cannot override safety**: `apply_operator_preferences` drops any
  non-accepted or safety-affecting preference (tier/review/safety/suppress/bypass/guardrail
  tokens or non-allowlisted keys) (`test_accepted_preferences_cannot_override_safety`).
- **Origin + source refs required**: candidates/memory carry `origin_id` + source refs;
  quality signals (origin/quality) written on acceptance.
- **No raw content**: model source-ref validators + DB CHECK guard columns (all 0); tests
  scan serialized output.
- **Dry-run default**: `--no-emit` performs no DB writes.

## Reconciliations / known limitations

- Models are compact and 1:1 with the V26 tables (repo-authoritative over the package's
  fuller proposed candidate/memory fields).
- The memory CLI takes source refs as a comma-separated `--source-refs` string (matching
  the file's `str`-default option style; avoids a B008 list-default lint).
- Memory retrieval-priority influence remains gated to accepted memory only (the existing
  `read_accepted_memory` reader); incremental trust calibration is future work.
- Output Evaluation Agent (A05) persistence + daily brief (13) + scheduling/validation
  matrix remain deferred.

## Next prompt readiness

Accepted memory + operator preferences are ready for the **daily brief (Prompt 13)** and
the **answer-synthesis** path (memory already retrievable via `accepted_long_term_memory`).
Schema stays V26 / 141; the 08A no-writeback proof arm remains deferred to its owning
prompt (~15).
