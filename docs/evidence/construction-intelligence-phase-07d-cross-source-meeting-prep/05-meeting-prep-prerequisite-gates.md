# 07D Prompt 05 — Meeting-Prep Prerequisite Gates (Evidence)

Additive over schema **V25** (no migration). Wires the 07D meeting-prep prerequisite gate set into
`construction-agent data-quality gates`.

## Preflight (repo truth)

- `git rev-parse HEAD` → `2ab2c94c9c8f1e663c6c8c49a8bd283532860e64` (Prompt 04 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`).
- `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652bf55303ceea25b2bbc6b5b1785111a335`,
  07B `748ed7e6519ada0a74d09376f2d2fe353627ac2b`, 07C `733ffedae071ce6a766a33fcd9233205364b8013`.
- Evidence folder `construction-intelligence-phase-07d-cross-source-meeting-prep/` present with
  `00`–`04`; this adds `05`.

## What changed

Five new `GateEvaluator` methods (`future_phase="07D"`) in
`src/hb_assistant/construction/data_quality/gates.py`, evaluating the V25 substrate:
`cross_source_relationship_candidate_coverage`, `deterministic_relationship_quality`,
`evidence_trail_completeness`, `weak_model_sensitive_review_routing_accuracy`,
`meeting_prep_prerequisite_status` (source-scope 3-way: pass / fail_blocking /
deferred_not_blocking). Wired into `run()`; `meeting_prep_readiness` merges the 07B manifest
prerequisites with the new 07D constant and adds a `prerequisite_categories` breakdown
(calendar / email / document / relationship / review / safety / source_scope); a new honest
`needs_07d_data` claim value sits between `needs_07b_07c_data` and `ready`. New test file
`tests/test_data_quality_meeting_prep_gates.py` (15 tests); claim-whitelist widened in two
existing gate tests. Source-scope reuses the existing 07C evaluator; no new store method, no
schema change, no CLI command added.

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **178** source files |
| `pytest -m "not live and not integration and not manual"` | **2165 passed**, 1 deselected (exit 0) |

(Prompt 04 baseline was 2150 passed; +15 new meeting-prep gate tests.)

## CLI validation matrix (all exit 0)

`construction-agent data-quality gates` · `… data-quality no-writeback-proof` ·
`… data-quality table-inventory` · `construction-agent validate` · `procore validate` ·
`graph files status` · `graph files no-writeback-proof` · `graph calendar status` ·
`graph mail status` — captured to `/tmp/p05/*.json` (ephemeral, not committed).

### `data-quality gates` — live 07D meeting-prep gates (populated substrate)

| Gate | Status | Evidence |
|---|---|---|
| `cross_source_relationship_candidate_coverage` | pass | `candidate_count=1880` |
| `deterministic_relationship_quality` | pass | `deterministic_count=1671`, `malformed_count=0` |
| `evidence_trail_completeness` | pass | `candidates=1880`, `evidence_trails=1880` |
| `weak_model_sensitive_review_routing_accuracy` | pass | `weak_model_sensitive_count=158`, `misrouted_count=0` |
| `meeting_prep_prerequisite_status` | pass | `onedrive_source_count=4`, `document_card_count=283`, `blocked_sources=[]`, breakdown `all_folders_explicit_compliant=4 / implicit_root_blocked=0` |

- `meeting_prep_readiness.ready=true`, `blocked_by=[]`, `auto_readiness_allowed=false`;
  all seven `prerequisite_categories` ready. `meeting_prep_readiness_claim="ready"`.
- **Readiness honesty:** `ready=true` is honest here — the live substrate genuinely satisfies all
  21 prerequisites (16 07B/07C + 5 07D): 1,671 deterministic edges with 0 malformed, 1:1 evidence
  trails, all 158 weak/model/sensitive candidates correctly review-routed (0 misrouted, **none
  auto-promoted**), and OneDrive scope is explicit-all-folders compliant. `auto_readiness_allowed`
  stays `false`, so nothing auto-proceeds. On an empty substrate the same five gates report
  `deferred_not_blocking` and readiness stays blocked (verified in tests).

### Safety invariants over the populated substrate

- `data-quality no-writeback-proof` → `proof_passed=true` (fail-closed).
- `graph files no-writeback-proof` → `ok=true`.
- `data-quality table-inventory` → `schema_version=25`, `contract_table_count=120` (no new tables).
- `review_items=[]` on the live run (no misrouting, no scope blocks).

## Test-path coverage (new file)

Presence + 07D phase tagging; empty-substrate ⇒ deferred (never pass); relationship success path;
missing-evidence-trail ⇒ `fail_blocking`; malformed deterministic edge ⇒ `fail_blocking`;
review-routing pass and fail (with `review_items`); source-scope pass (explicit all-folders),
fail_blocking (implicit root), deferred (no OneDrive / no document cards), and policy-disabled
all-folders ⇒ fail_blocking; no-raw-content regex scan of the serialized report; idempotent
persisted runs; prereq-constant ⊆ contract; backward-compatible `meeting_prep_readiness` keys.

## Guardrails honored / stop conditions

- No external writeback, no write scopes, no mutation, no schema change (V25 unchanged).
- No raw email/document/calendar content, signed/download URL, token, secret, prompt, or response
  persisted to SQLite, evidence, logs, or Obsidian (no-raw-content test + both no-writeback proofs).
- Weak / model / sensitive / high-impact relationships stay review-required and are never
  auto-promoted (the routing gate only reports).
- Readiness is not overstated: deferred 07D gates keep readiness blocked;
  `auto_readiness_allowed=false`.
- No stop condition triggered; all validations classified and passing.

## Scope note (validation matrix)

`phase_07d_validation_matrix.json` references `construction-agent data-quality phase-07d-gates`
and `meeting-prep status`. Those commands are intentionally **not** added here — the meeting-prep
prerequisites are validated through the existing `data-quality gates` command; the standalone 07D
gate command and meeting-prep surface land in later 07D prompts. This is a forward-declaration in
the matrix, not an unmet Prompt 05 deliverable.

## Handoff

- **Changed:** `gates.py` (5 gates + constants + readiness/claim), new meeting-prep gate test file,
  two claim-whitelist test edits, `docs/architecture/48-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** on the live DB all five 07D meeting-prep gates **pass**; readiness honest
  (`ready`, `auto_readiness_allowed=false`). On empty DB they correctly **defer**.
- **Next prompt allowed to proceed:** yes. Prompt 06 (meeting-prep brief materialization) may build
  on these prerequisite gates; the substrate, evidence trails, and review routing are gate-verified.
