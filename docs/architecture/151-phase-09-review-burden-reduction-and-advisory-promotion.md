# Phase 09: Review Burden Reduction and Advisory Promotion Policy

## Why the old blanket was too strict

The prior `review_not_performed_blocks_all` + `review_not_performed=true` (no human decisions recorded anywhere) caused every distinct review item (including low-risk metadata-only source-linked signals) to be blocked from promotion *and* from safe advisory use in retrieval/daily brief. With thousands of items (financial ledger alone contributing ~128k raw append-only rows), the operator was faced with an unusable "review everything before the assistant is useful" posture. This is incompatible with a personal/executive assistant workflow that must reduce workload.

## The new exception-based model (two-step)

Classification is **two-step**:

1. Source family eligibility is **necessary** (must be in the policy's allowed_families for auto-advisory consideration).
2. Item-level impact/risk classification is **decisive**. 

High-impact item (financial, cost_impact, contractual, claim, entitlement, schedule_impact, safety, legal, payment) from *any* family — including families that look "low-risk" on average such as `cross_source_relationships`, `aging_exposure_report_items`, `project_risk_digest_items` — forces **Tier C** (mandatory review before promotion to accepted fact/memory). High-impact beats low-risk family.

- **Tier A — Auto-Allow Advisory Use** (after two-step + source-linked + metadata-only + no-raw/no-writeback guards): safe for semantic retrieval and daily brief context with the label "Advisory · Source-linked · Not a determination · Review not required". Does not block promotion of other things; is itself not promoted to accepted fact.
- **Tier B — Batch Review / Advisory-Only**: grouped by (source_family, project_key, impact_category, confidence_class, review_reason); weak suppressed by default; top N hash-only examples shown; default action keep advisory, not promoted. Does not block retrieval as unpromoted advisory signals.
- **Tier C — Mandatory Review Before Promotion**: high-impact per the contract list. May appear as advisory *warnings* (e.g. in daily brief or financial exposure), but blocked from accepted promotion, memory acceptance, or high-confidence deterministic answers.
- **Tier D — Hard Prohibited**: raw indexing, external writeback, final financial/payment/claim/entitlement/legal/safety determinations, Graph/Procore calls via MCP, etc. Never allowed.

## Financial review rows are separate

The append-only `second_brain_financial_review_required_items` ledger can have very high raw row counts (one run can add many). These are always `advisory_only=1`, promotion-blocked, and tracked in `financial_review_burden` (raw + distinct). They do **not** inflate the assistant's daily operator review queue cap, and do **not** prevent low-risk non-financial metadata from being used as advisory. Financial *conclusions* remain blocked from final determinations (existing 08C/08D gates).

## Operator review budget + high-impact always visible (clustered)

Policy: `daily_max_items: 10`, `weekly_max_items: 50`, `high_impact_always_visible: true`.

- High-impact *categories and totals* are **always** present in summaries and never silently hidden.
- Only the **top N clusters** (within the daily budget) are "visible" for operator action.
- Item-level spam for high-impact is suppressed; the operator sees counts + representative hash-only clusters.
- `operator_visible_count` and `suppressed_noise_count` are reported everywhere.

## Hash-only top examples (never raw/PII)

`top_examples_json` (and any surfaced examples) may contain only:

- source_family, project_key, item_hash, source_ref_hash, confidence_class, review_reason_code, impact_category, freshness_bucket, count.

Prohibited (enforced in builder + proof + tests): subject/body/title/email/organizer/attendee/location/URL/raw identifiers/document titles if sensitive, any raw content, tokens, secrets, PII.

## Daily brief is exceptions summary, not a review dashboard

Daily brief now emits (capped):

```
Review exceptions:
- 4 contractual correspondence clusters require review.
- 3 financial exposure clusters remain advisory only.
- 2 source-conflict clusters need confirmation.

Batched/suppressed:
- 761 calendar/email candidates retained as advisory signals.
- 384 weak candidates suppressed from standard answers.

Recommended: run `hb-assistant second-brain review burden --json` (and queue) for operator action.
```

Internal Tier-C cards may still flow to handoff for mandatory items, but the operator-facing rendered brief is summary-first and budget-capped. The full clustered view lives in the `review` CLI commands.

## Retrieval integration

- Deterministic (source of truth) unchanged.
- Semantic advisory path (hybrid) consults the burden gate: Tier A (after two-step + guards) is eligible for advisory context even if `review_not_performed`. Tier B usable as unpromoted advisory. Tier C/D excluded or warning-only.
- Approved source manifest / memory loader / embedding candidate validate continue to require `review_status='accepted'` (or equivalent) + tier <= max_auto for promotion into vectors; high-impact/C items stay excluded until human accepted.
- No change to min_tier=2 for semantic, no-raw re-validation, context budget, or source-linked requirements.

## Schema V39 (additive)

Three new tables (with the full 23 Phase 09 guard columns CHECK=0):

- second_brain_review_burden_runs
- second_brain_review_burden_clusters
- second_brain_review_burden_policy_evals

LATEST_SCHEMA_VERSION=39. All prior Phase 09 surfaces use `>= 38` (or `< 38` for "not yet V38") checks; V39 is additive and does not regress them. 08D/MCP surfaces must pass after the bump (explicit validation required).

## Package data

Seed (yaml) and contract (json) live under `src/hb_assistant/resources/config/...` and `.../json/...` so they are included by package-data globs. Loader for seed supports importlib.resources (installed/editable) + PathPolicy fallback (source dev) + ENV override. Validation requires `python -m pip install -e .` followed by `hb-assistant second-brain review policy-status --json` succeeds using the packaged artifacts.

## Validation commands (must pass)

See the runbook and the CI-like sequence in the implementation plan (includes the original 09 commands + the 5 08D-compat commands + pip -e + review policy-status/burden/queue/clusters).

## Acceptance (summary)

- Blanket `review_not_performed_blocks_all` limited to promotion; low-risk advisory flows after two-step.
- No family is auto-advisory by family name alone.
- High-impact always summarized (clustered + totals); not itemized beyond budget.
- Financial separate; does not permanently block low-risk non-financial advisory.
- Unreviewed high-impact blocked from accepted-fact promotion.
- Phase 08D/MCP gates pass after V39 (no regression).
- New seed/contract load from installed package context.
- Daily brief is summary-first capped exceptions (target text shape).
- top_examples_json hash-only (prohibited fields absent in proof/tests).
- Within each cluster, top examples are deduplicated by safe key (item_hash > source_ref_hash > composite of family+project+impact+conf+reason+freshness) so the operator sees unique hash-only examples; each cluster carries `unique_example_count` (distinct) alongside full `item_count`.
- All no-raw/no-writeback/no-determination/source-linked guardrails and existing proofs pass.
- Tests + full validation command matrix pass.

Example cluster snippet (post-dedup):
```json
{ "cluster_id": "...", "item_count": 42, "unique_example_count": 3, "top_examples": [ {"item_hash":"h1", "source_family":"...", ...}, ... ] }
```

## Stop conditions (observed)

Any of the original + the refinement stops (auto-allow by family alone, itemizing high-impact beyond cap, letting 128k financial block low-risk advisory, regressing 08D, emitting prohibited fields in examples, making daily brief a full review queue, etc.).

## Deferred / known

- Full apply of burden clusters into the V39 tables from the review CLI (current is compute + proof; persist optional in the mart).
- Wiring the burden clusters as an additional source family for corpus balance / eval (future prompt).
- UI surfaces or Obsidian commands to act on the top clusters (operator still uses the Typer review commands).

## Review cluster usefulness improvements (Prompt 34 follow-up) — truthful extraction and advisory assertion (modeled on 121)

Follow-up to this record after Prompt 34 objective: "Improve Phase 09 review cluster usefulness without increasing operator burden."

Requirements implemented (per plan; all surgical, no behavior change to caps or blocking):
- Replace weak/unknown review_reason defaults where source tables expose better reason/category/status fields: in `_collect_review_candidates`, the non-dedup SELECT now projects the key + project_*/reason/category/trigger/review_tier_reason_code/review_reason/classification_label/status/promotion_status/preview_kind/relationship_type/review_tier/confidence*/sensitivity/sensitive_high_impact/utc cols (instead of only key_col/rowid); extraction for pk/conf/reason extended with table-native preference order + normalization (int/float/str/real from queues) before falling to None.
- Improve project_key extraction and confidence normalization: pk now also tries "project_id"; conf handles REAL confidence, str labels, numeric tiers with maps for high/medium/low/weak.
- Split over-broad clusters such as email/unclassified/unknown and construction/unclassified/unknown: with real review_reason_code from e.g. email's category+reason+status or construction's reason+classification_label+status, _cluster_key and cluster "review_reason" now vary (e.g. "newsletter or marketing", "routine follow-up item", "low_risk_correspondence") producing distinct clusters; family still B for non-allowed like email/construction queues.
- Keep operator_visible capped: unchanged (daily_max from seed, visible_high cap, operator_visible_count = min(daily, ...)).
- Keep high-impact category totals always visible: unchanged (high_impact_summary, always_visible note, visible_high separate from suppressed).
- Preserve top_examples hash-only and deduped: no changes to _safe_top_example (9 allowed fields), _example_dedup_key (item_hash > source_ref > composite incl. now-richer reason), max_examples, unique_example_count, prohibited strip.
- Fix review_burden_proof so advisory_retrieval_allowed is actually asserted via explicit true/false fixture cases: removed `and (gate.get("advisory_retrieval_allowed") or True)` from proof_passed (now only raw_findings==0 and blanket is False); advisory value in gate is computed from (auto+batch>0) and may legitimately be false; updated docstring. Added explicit fixtures in tests (see below) that INSERT low-risk open queue rows (advisory=True, proof=True) vs only-high (advisory=False, proof=True).
- Do not loosen high-impact promotion blocking: unchanged (Tier C for high_impact_impact_categories or sensitive or outside-family high; financial separate always promotion_blocked; two-step still "high beats family"; evaluate gate still sets promotion_blocked_for_high_impact).

Files changed (this run):
- `src/hb_assistant/construction/second_brain/review_burden_mart.py` (SELECT projection + pk/conf/reason extraction/normalization in _collect ~305-380; proof_passed + docstring in build_review_burden_proof ~647).
- `tests/test_phase_09_advisory_retrieval_gate.py` (added `test_advisory_retrieval_allowed_true_for_low_risk_queue_item` and `_false_for_only_high_impact` using direct INSERTs to construction_review_queue + asserts on gate flag + proof_passed + native reason in clusters).
- `tests/test_phase_09_review_burden_policy.py` (added sqlite3 import; tightened empty-db test to assert advisory=False + proof=True; appended `test_review_burden_proof_asserts_advisory_retrieval_allowed_true_false_explicitly` with construction inserts + native reason checks).
- `docs/architecture/151-phase-09-review-burden-reduction-and-advisory-promotion.md` (this subsection).
- `docs/architecture/00-README.md` (added Prompt 34 ledger line under Phase 09).

Validation (executed post-edit):
- `python -m pip install -e .`
- ruff check . && ruff format . ; mypy src ; .venv/bin/python -m compileall -q src/hb_assistant/construction/second_brain/review_burden_mart.py
- `hb-assistant second-brain review policy-status --json`
- `hb-assistant second-brain review burden --json` (and --project P)
- `hb-assistant second-brain review queue --top 5 --json`
- `hb-assistant second-brain review clusters --json`
- `hb-assistant second-brain data-quality review-load --json`
- `hb-assistant second-brain daily-brief render-view --date 2026-06-05 --json` (and triage/generate paths)
- Targeted: pytest tests/test_phase_09_review_burden_policy.py tests/test_phase_09_advisory_retrieval_gate.py tests/test_phase_09_review_burden_cli.py tests/test_phase_09_review_load_mart.py tests/test_daily_brief_review_burden_summary.py tests/test_daily_brief_output.py tests/test_second_brain_daily_brief_render_view_cli.py -q --tb=line
- `construction-agent validate --json`
- Confirmed via runs: clusters now split with real review_reason (e.g. "routine..." vs unknown bucket); advisory T/F explicitly asserted True/False in fixtures and empty case; proof_passed True; high-impact still promotes block; caps/visible/top_examples guards preserved (no raw in examples, deduped hashes, unique counts).

Guardrails preserved (no regressions):
- operator_visible capped at daily budget; high_impact always summarized via high_impact_summary + always_visible.
- top_examples: only the 9 hash-safe fields, prohibited stripped, deduped by stable key, unique_example_count + item_count.
- High-impact promotion still blocked (C + financial + hard; two-step).
- financial separate (advisory_only + promotion_blocked, does not block non-fin low-risk advisory).
- no-raw/no-writeback asserted in proof + structures (23 guard cols).
- read-only, metadata-only, source-linked hashes/refs only.
- base install unaffected; no new deps; schema additive (no bump).
- proof_passed now truthful (advisory not forced).

This follows the "truthful value reporting without overstatement" discipline from the MCP precedent (sibling record 121 §3, and its appended subsections in 120/121/131/132/137/138/139/00-README): the advisory_retrieval_allowed and review_reason values now reflect actual table state / two-step outcome in status, proofs, and tests (explicit fixtures for T and F paths), just as readiness probes were split to report core vs local accurately. See 121's "LlamaIndex readiness truthful..." append for the pattern.

No other architecture docs required updates (150 etc had no direct overlap with review_burden_mart or the proof expression).

## References

- review_burden_mart.py (two-step, clustering, hash-only, financial separate, gate)
- review_load_mart.py (augmented proof + legacy gate kept for compat)
- cli/second_brain.py (review_app + commands + updated review-load)
- daily_brief/output.py (exceptions summary rendering)
- migrator.py V39 + phase_09_schema.py (additive tables)
- pyproject.toml + packaged resources under src/hb_assistant/resources/...
- tests/test_phase_09_review_burden_policy.py , tests/test_phase_09_advisory_retrieval_gate.py (explicit true/false advisory fixtures asserting the flag)
- Architecture 125 (original review-load) and 120 (repo-truth rebaseline) for history.
