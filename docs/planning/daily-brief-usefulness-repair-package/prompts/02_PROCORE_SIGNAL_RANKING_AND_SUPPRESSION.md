# Prompt 02 — Procore Signal Ranking and Aggregate Suppression

## Objective

Prevent giant unranked Procore backlog aggregates from dominating executive daily-brief output.

## Problem

The audit found 5,866 open Procore signals, 0 due soon, 1,888 recent, and 3,592 aggregate-sludge rows.

## Required Implementation

1. Locate current Procore digest/read-model code.
2. Implement a daily-brief Procore ranking function that computes:
   - `rank_score`
   - `rank_reasons`
   - `why_today`
   - `suppression_reason`
   - `is_aggregate_sludge`
   - `is_semantically_actionable`
   - `source_change_linked`
   - `recent`
   - `due_soon`
   - `owner_linked`
   - `financial_materiality`, where available.
3. Promote due-soon, new/changed, high-critical and recent, owner-linked, source-change-linked, financial-material, and active workflow blockers.
4. Suppress/demote high-count stale aggregate backlog, semantically closed/resolved signals, duplicates, and rows with no `why_today`.
5. `observation_closed` must not appear as an open action unless repo truth proves an unresolved downstream implication.

## Tests

Cover due-soon, recent high-critical, stale aggregate, closed observation, financial materiality, source-change linkage, cap enforcement, and `why_today` requirement.

## Evidence

Create `docs/evidence/daily-brief-usefulness-repair/02-procore-ranking/`.

## Suggested Commit

`fix(second-brain): rank Procore signals for daily brief usefulness`
