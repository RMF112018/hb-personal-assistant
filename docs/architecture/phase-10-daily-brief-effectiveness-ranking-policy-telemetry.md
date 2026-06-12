# Phase 10 V52 — Daily-Brief Effectiveness / Ranking-Policy Telemetry

**Status:** implemented (additive, observational-only). Schema **V52** (+ **V53** reconcile). Branch
`feature/phase-10-ollama-candidate-ranking-brief-assembly`.

## Purpose

A deterministic, raw-safe, **observational** evaluation layer that measures whether ranked and
assembled daily briefs are becoming more useful over time. It reads the V51 ranking/assembly overlay
and the V50 lifecycle read model and persists only raw-free counts, rates, scores, hashes, ids, and
reason codes. It changes no V50/V51 behavior, calls no model, and writes back to nothing.

This layer does **not** make the model more authoritative — it measures outcomes.

## Position in the pipeline

```
V41 candidate projection ─┐
V50 lifecycle overlay ─────┼─▶ V51 ranking + assembly overlay ──▶ V52 effectiveness telemetry (read-only)
candidate_source_refs ─────┘                                        │
local_model_run_receipts ───────────────────────────────────────────┘
```

V52 sits at the top of the stack as a pure consumer. The only thing it writes is its own six
telemetry tables, and only in apply mode.

## Schema (V52, additive)

`src/hb_assistant/store/migrator.py` → `V52_STATEMENTS` (registered after V51; `LATEST_SCHEMA_VERSION
= 52`). Every table carries the shared 13-column `_P10_GUARDS` `CHECK(=0)` set.

| Table | Purpose |
|---|---|
| `daily_brief_exposure_events` | Surfaced-item exposure **proxies** (one per ranked candidate/section/brief), derived from persisted V51 rows. `artifact_hash` only; never an artifact body/path. |
| `daily_brief_item_outcome_events` | Post-brief lifecycle outcomes mapped back to exposed items (derived; never creates a lifecycle event). Carries `outcome_lag_hours` + `ignored_lag_hours`. |
| `ranking_policy_eval_runs` | Per-window policy evaluation summary (mode, coverage, usefulness, rank-outcome, degradation, noise). |
| `ranking_policy_eval_items` | Per-(ranking-run, candidate) eval facts (scores, outcome, weight, lag, source-ref count, raw-free `eval_notes_json`). PK `(eval_run_id, ranking_run_id, daily_brief_action_candidate_id)` so a candidate surfaced in two ranking runs keeps a distinct fact per run. |
| `model_profile_eval_results` | Aggregate local-model reliability from receipt metadata only (attempts/success/timeout/fallback/latency/degradation). |
| `brief_effectiveness_rollups` | Daily/window/project/family/source/model-profile trend rollups. |

Deterministic prefixed-sha ids (`dbe:`/`doe:`/`rpe:`/`mpe:`/`ber:`) keep inserts idempotent. Store
accessors live on `ConstructionStore`; guard columns are omitted on INSERT (DEFAULT 0 / CHECK(=0)).

**V53 reconcile.** V52 originally created `ranking_policy_eval_items` with PK `(eval_run_id,
candidate_id)`. Because an editable-install runner (the live scheduler) could migrate a DB to that
original V52 shape before this change merged, the composite-PK fix ships as a separate **V53**
migration (`_reconcile_v53_eval_items`): a guarded, idempotent, **non-destructive** table rebuild that
adds `ranking_run_id` and the 3-column PK, copying any existing rows (legacy rows — none in prod —
backfilled `ranking_run_id='unknown'`). A no-op once the column exists, so fresh DBs and any
prematurely-migrated DB converge to the same shape through the same path.

## Modules (`construction/second_brain/local_ai/`)

- **`daily_brief_effectiveness_packets`** — the read-only join layer. Rebuilds
  `build_review_queue(include_hidden=True)`, joins ranked candidates → review-queue subject (via the
  shared `_candidate_id`) → source-ref count + lifecycle outcome, model receipts, and similarity
  edges. Derives exposure proxies and outcome events. Statuses: `no_ranked_briefs`,
  `insufficient_outcome_data`, `degraded` (assembly/source-ref/model-when-expected), `ok`.
- **`daily_brief_effectiveness_metrics`** — pure deterministic metric functions (accepted/rejected/
  snoozed/ignored rates, rank-outcome, source-family usefulness, Procore noise, model validity/
  degradation, duplicate-precision proxy, source-ref coverage, brief usefulness, det-vs-model delta,
  calibration lift) with named outcome weights and small-sample flags.
- **`ranking_policy_evaluator`** — modes `observed | deterministic-replay | model-assisted-observed |
  ablation`; deterministic-only works without model telemetry; no model call; sample-size caveats.
- **`model_profile_evaluator`** — receipt-metadata-only aggregation (no raw prompt/response; nearest-
  rank p95 latency); emits a `model_telemetry_missing` row for deterministic-only windows.
- **`procore_noise_evaluator`** — Procore noise score + top noisy groups + **advisory** tuning
  recommendations + per-source-family usefulness; never suppresses or re-thresholds.
- **`effectiveness_rollups`** — daily/window/project/family/source/model-profile rollups; missing
  dimensions normalize to `unknown`.
- **`daily_brief_effectiveness_report`** — raw-free Markdown + JSON report and the top-level
  orchestrator `run_daily_brief_effectiveness_evaluation` (build → evaluate → report → projected-
  persist).

## Outcome derivation

Attribution is strictly **post-exposure**: an exposed item's outcome is the latest lifecycle
disposition event at/after the brief-date exposure-proxy time (disposition states map directly;
`reopen` → `reopened`). `outcome_lag_hours` is therefore measured forward and **never negative**
(clamped to ≥ 0 as a safety net). A disposition that **predates** the exposure is *not* attributed to
it and is *not* converted into ignored/stale — the item is excluded with `outcome_type = None` and a
raw-free `status_reason = pre_existing_disposition_not_attributed` (counted in the packet summary).
`ignored` (or `stale_no_action`) is assigned **only** to a genuinely open, actionable item that has
aged past the lag window (default 72h) with no attributable disposition. Absent feedback is never
treated as acceptance. Each item carries a raw-free `status_reason`
(`attributed_post_exposure` / `pre_existing_disposition_not_attributed` / `no_action_after_lag` /
`pending_within_lag_window` / `open_not_actionable`).

## CLI

```
hb-assistant second-brain daily-brief evaluate-effectiveness \
  --db <PATH> --window-start YYYY-MM-DD --window-end YYYY-MM-DD \
  [--brief-date D] [--policy-version V] [--model-profile-id P] \
  [--eval-mode observed|deterministic-replay|model-assisted-observed|ablation] \
  [--ignored-lag-hours 72] [--(no-)procore-noise] [--(no-)model-profile] [--(no-)rollups] \
  [--apply --max-persist N [--allow-non-tmp-db]] [--json/--no-json]
```

Exit 0 ok/dry-run; 2 invalid usage (bad window/date/mode, apply without `--max-persist`, apply without
`--db`, or apply with a non-temp `--db` and no override); 3 fail-closed (raw leak, or projected inserts
exceed `--max-persist`); 1 unexpected.

## Safety invariants

- **Observational only:** no lifecycle/source-ref/ranking/assembly mutation; no auto disposition; no
  threshold auto-tuning; no external/model writeback. Proven by a before/after content-fingerprint
  test over the V50/V51 source tables.
- **`--max-persist` is a total-projected cap:** the sum of projected inserts across all six tables;
  exceeding it fails closed before any write (no partial state).
- **Dry-run writes zero rows.** `--apply` is gated **before the store is opened**: it requires an
  explicit `--db`, and that `--db` must resolve under an OS temp root (`/tmp` or `$TMPDIR`/`tmp_path`)
  unless the explicit `--allow-non-tmp-db` override is passed (surfaced in the result). This makes it
  impossible to persist against the production app DB by accident (opening a `ConstructionStore`
  migrates the configured DB). Production DB SHA-256 was identical before and after all validation.
- **Raw-free:** all output/persisted text is scanned with `scan_text_for_forbidden`; the report/CLI
  fail closed on any category hit. Guard columns sum to 0.

## Known limitation

Table-lifecycle governance classification of the V49/V50/V51/V52 tables in
`table_lifecycle_status_contract.json` remains **deferred pre-existing governance debt** — the
`*_tables_classified_in_lifecycle_contract` / `no_writeback_proof` reconciliation tests were already
red at the V51 HEAD (`6938380b`) before this slice and are addressed in a separate governance PR.
