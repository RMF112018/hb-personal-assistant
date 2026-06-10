# 06 — Ranked Signals, Candidates, and Downstream Consumers

## Objective

Update downstream Procore read models so daily brief/local-model consumption uses ranked, source-linked, structured projections rather than aggregate sludge or opaque counts.

This prompt is downstream of the analytics foundation. Do not let it reshape the raw/structured storage layer.

## Required signal ranking changes

Implement a ranked Procore signal projection that scores or tiers records using due date/overdue/due soon, status/actionability, recent change, importance/priority, owner/ball-in-court/assignee coverage, project key coverage, source ref coverage, financial materiality, schedule exposure, safety/quality/compliance exposure, closed/open state, and stale backlog/aggregate group suppression.

## Aggregate sludge suppression

A high-count backlog group cannot be a top priority unless specific records have due/recent/high/owner/materiality/safety/schedule evidence. Closed records cannot generate open action signals unless another field proves unresolved follow-up. Aggregate diagnostics belong in analytics/status appendices, not daily brief top priorities.

## Daily brief candidate projection

Populate `daily_brief_action_candidates` and `candidate_source_refs` from ranked structured projections.

Candidates must include brief date, project key or explicit internal/unassigned classification, section, ranked priority, redacted title, recommended next action, reason redacted, source refs, source table and source primary key hash, confidence/tier, and no raw guard columns set to zero.

## Local model context

Local model context packets may include structured summaries and source refs. They must not include raw Procore payloads unless a separate local-only raw-content access policy explicitly allows it for a bounded, audited context packet. Daily brief/status/evidence must never display raw payloads.

## Required tests

Ranked ordering, aggregate sludge suppression, closed-record suppression, due/recent/high/owner/financial/schedule ranking, candidate projection, candidate source-ref coverage, no raw leak, model-unavailable deterministic fallback, and daily brief success/degraded gate tests.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/06-ranked-signals-candidates-and-downstream-consumers/`.
