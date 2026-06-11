# Validation Matrix

## Schema / Migration

| Behavior | Required Proof |
|---|---|
| Next migration version is repo-truth `LATEST_SCHEMA_VERSION + 1` | schema audit evidence and migration test |
| New tables exist | `PRAGMA table_info` proof and pytest |
| New indexes exist | `sqlite_master` proof and pytest |
| Guard columns exist with zero CHECK/default | migration test and SQL guard proof |
| Migration is idempotent | apply migrator twice on temp DB |
| No destructive schema change | diff/audit note: no DROP/rename/destructive ALTER |

## Packet Builder

| Behavior | Required Proof |
|---|---|
| Builds packets from ranked/assembled rows | fixture with V51+ ranking/assembly tables |
| Joins source refs by repo-true candidate IDs | source-ref coverage proof |
| Joins lifecycle outcomes without mutating lifecycle | before/after lifecycle row counts |
| Handles no ranked briefs | `no_ranked_briefs` JSON/status |
| Handles no outcomes | `insufficient_outcome_data` JSON/status |
| Rejects planted raw content | scanner test with category-only findings |

## Metrics

| Behavior | Required Proof |
|---|---|
| accepted/rejected/snoozed/ignored rates deterministic | unit tests |
| rank_outcome_score stable | unit tests with fixed expected score |
| brief_usefulness_score stable | unit tests with weighted components |
| procore_noise_score stable | unit tests by source family/section |
| model_degradation_rate stable | model receipt fixture tests |
| duplicate_precision_proxy stable | duplicate cluster fixture tests |
| feedback_calibration_lift marks small sample insufficient | small sample test |

## Evaluators

| Behavior | Required Proof |
|---|---|
| deterministic-only runs evaluate without model telemetry | evaluator test |
| model-assisted runs include model metadata when present | evaluator test |
| invalid/missing receipts degrade honestly | evaluator test |
| no lifecycle/source-ref mutation | before/after row-count tests |
| Procore noise is advisory only | no suppression/state mutation test |

## CLI

| Behavior | Required Proof |
|---|---|
| default dry-run writes zero rows | CLI test and DB count proof |
| apply requires `--max-persist` | CLI exit 2 test |
| invalid date window exits 2 | CLI test |
| fail-closed raw leak exits 3 | CLI test |
| JSON output scanner-clean | scanner test |
| `/tmp` DB redaction follows repo convention | CLI test |

## Report / Dashboard

| Behavior | Required Proof |
|---|---|
| Raw-free Markdown/JSON report renders | report test |
| insufficient data banner appears | report test |
| model degradation summary appears | report test |
| Procore noise summary appears | report test |
| source-ref coverage summary appears | report test |
| no raw/private content appears | no-raw scan |

## Regression

| Behavior | Required Proof |
|---|---|
| Existing V50 lifecycle tests still pass | focused pytest |
| Existing V51+ ranking tests still pass when present | focused pytest |
| Existing no-raw leak tests still pass | focused pytest |
| Existing usefulness gate behavior still catches contradictions | focused pytest |
