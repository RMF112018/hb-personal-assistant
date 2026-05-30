# 14 — Sensitive File Review Routing Proof (Phase 06A)

**Prompt:** Prompt 12 — Sensitive File Review Routing · **Date:** 2026-05-30
**Posture:** Offline (SQLite + review rules + registry); no Graph; no content read; no writeback. Dry-run default.
Reuses the existing review-queue engine (`construction_review_queue` V3 + idempotent
`enqueue_review_item` + `ReviewPolicyEvaluator`); no new migration (schema stays at version 19).

## What changed

- **`resources/config/review_required_rules.seed.yaml`** — extended from 16 to **25 rules** to cover
  the remaining construction-sensitive categories beyond the protected six (contract, financial,
  legal, incident, injury, personnel): **claim, notice, insurance_bonding, medical, dispute,
  cost_impact, schedule_impact**. Name/folder matching only — no content inspection. Every match
  routes to `controller_review`. The Pydantic validator (`ReviewRules._check_consistency`) still
  passes: the protected six are intact and all rule_ids are unique.
- **`src/hb_assistant/construction/graph/file_review_router.py`** — `FileReviewRouter`, the V5
  `construction_drive_items` counterpart to the V2-inventory `ReviewQueueRouter`. It reuses the same
  deterministic evaluator and the idempotent `enqueue_review_item`, mapping each driveItem to
  `{item_id, name, parent_path}` (no body). It also routes **low-confidence / unmatched** project
  matches (V17 `match_status`) via a synthetic `low-confidence-project-match` rule, and cross-checks
  that every routed item's V18 ingestion decision keeps `extraction_allowed = false`.
- **`hb-assistant graph files review-queue`** — `--source` (optional), `--dry-run/--apply`, `--json`.
  Offline; no Graph client is constructed.

## Category → rule coverage

Every category in the Phase 06 sensitive-file taxonomy is covered by at least one deterministic rule
(or, for the last two, by the router itself):

| Category | Example rule(s) | Kind |
| --- | --- | --- |
| contract | `folder-contracts`, `doc-change-order` | folder_path / document_name |
| financial | `folder-financials`, `doc-invoice`, `doc-purchase-order` | folder_path / document_name |
| claim | `folder-claims`, `term-claim` | folder_path / risk_term |
| notice | `doc-notice` | document_name |
| legal (privileged) | `folder-legal`, `term-confidential` | folder_path / risk_term |
| hr / personnel | `folder-personnel` | folder_path |
| insurance_bonding | `folder-insurance-bonding`, `doc-insurance-bonding` | folder_path / document_name |
| safety / incident | `folder-incidents`, `term-incident`, `term-injury` | folder_path / risk_term |
| medical | `term-medical`, `pii-health-record` | risk_term / document_name |
| dispute | `term-dispute` | risk_term |
| cost_impact | `term-cost-impact` | risk_term |
| schedule_impact | `term-schedule-impact` | risk_term |
| low_confidence_project_match | `low-confidence-project-match` (synthetic, V17 `match_status`) | router |

`construction-agent validate --json` → `review_rules: version=1; 25 rules; threshold=0.7`; all 4
checks pass; `schema_version=19` (unchanged).

## Deterministic routing proof (seeded; offline)

Seed: 10 sensitive files (one per category) + 1 low-confidence item + noise (a folder + a deleted
file, both ignored). `items_seen = 11`; `matches_found = 14` (some items match more than one rule —
e.g. the OSHA report fires `folder-incidents`, `term-incident`, and `term-injury`).

### Dry-run (default) — plans only, writes nothing

```json
{
  "command": "graph files review-queue",
  "mode": "dry_run",
  "results": [
    {
      "source_id": "sp_2023projects_23_435_01_tropical_sl",
      "items_seen": 11,
      "matches_found": 14,
      "enqueued": 0,
      "skipped_already_open": 0,
      "low_confidence_routed": 1,
      "by_category": {
        "contract": 1, "financial": 1, "claim": 2, "notice": 1,
        "insurance_bonding": 1, "incident": 2, "injury": 1, "medical": 1,
        "dispute": 1, "cost_impact": 1, "schedule_impact": 1,
        "low_confidence_project_match": 1
      },
      "extraction_blocked_for_all_routed": true
    }
  ],
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "graph_calls": "none",
    "review_routed_cannot_extract": true,
    "queue_idempotent": true,
    "permission_tightening": "deferred"
  }
}
```

(Queue row count after dry-run = **0** — nothing was written.)

### Apply — enqueues, then idempotent on re-run

```text
apply (1st):  enqueued=14  skipped_already_open=0   → queue rows = 14
apply (2nd):  enqueued=0   skipped_already_open=14  → queue rows = 14   (unchanged)
```

Idempotency is the existing `INSERT OR IGNORE` on `(source_key, item_id, rule_id)`; re-running the
router never duplicates a row.

## No-extraction guarantee for review-routed files

Two layers, both verified here:

1. **Schema CHECK (V18):** `construction_file_ingestion_decisions` enforces
   `CHECK(review_required = 0 OR extraction_allowed = 0)` — a review-required decision can never also
   allow extraction. (Re-confirmed green in `tests/test_graph_files_controlled_extraction.py`.)
2. **Router cross-check:** for every routed driveItem the router reads its V18 decision and reports
   `extraction_blocked_for_all_routed`. With all routed items decisioned `review_required`/
   `extraction_allowed=false`, the flag is `true`. A crafted inconsistency (a routed item whose V18
   decision still allowed extraction) flips the flag to `false`
   (`test_cross_check_detects_extraction_leak`) — the safety net surfaces the leak rather than hiding
   it.

The controlled extractor (Prompt 11) independently skips any item that is not
`extraction_allowed`/is `review_required` (`blocked_review_required`), so a review-routed file is
never downloaded or parsed.

## Guardrails honored

- **No Microsoft 365 writeback / no Graph calls** — the router and CLI touch SQLite + the rule set
  only; no Graph client is constructed.
- **No content inspection** — matching uses driveItem `name` + `parent_path` only; no body, no
  download.
- **No secrets / tokens / signed URLs / full text** persisted — queue rows carry metadata
  (name, parent_path, rule, category, sensitivity) only.
- **Dry-run is the default**; writes require `--apply`.
- **Permission tightening deferred** — no delegated scope or broad Graph file consent was changed.

## Tests

`tests/test_graph_files_review_routing.py` (8 tests): every sensitive category routes; low-confidence
match routes; idempotent re-run; dry-run writes nothing; routed files cannot extract; cross-check
detects an extraction leak; the expanded seed loads and covers the new categories; CLI offline smoke.
Regression: `tests/test_construction_review_policy.py`, `tests/test_construction_store_repositories.py`,
`tests/test_graph_files_ingestion_policy.py`, `tests/test_graph_files_controlled_extraction.py`,
`tests/test_mutation_lockout.py` all green.
