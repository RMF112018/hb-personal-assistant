# Prompt 04 — Source-Ref Gate and Model-Facing Contract

## Objective

Ensure model synthesis only sees source-linked, deterministic, useful daily-brief context.

## Problem

The audit found `candidate_source_ref_coverage = 0.0`. The model nevertheless produced source-looking bullets while deterministic sections were empty.

## Required Implementation

1. Identify canonical source-ref tables: `candidate_source_refs`, `daily_brief_source_refs`, source evidence trails, or repo equivalent.
2. Define a model-facing context object with candidate id, safe title, project/category, rank, `why_today`, next action, source refs, coverage, omissions, and gate status.
3. Executive/top-priority model context requires 100% source-ref coverage.
4. Missing source refs withhold rows from synthesis.
5. If all rows are withheld, synthesis is skipped/degraded.
6. Status JSON includes coverage metrics and withhold reasons.
7. Model-enriched intelligence cannot claim meetings, Procore risks, follow-ups, or actions absent from deterministic source-linked context.

## Tests

Source-linked row included, missing-ref row withheld, mixed rows include only linked rows, all rows withheld degrades, unsupported model bullet dropped, coverage metrics, no raw persistence.

## Evidence

Create `docs/evidence/daily-brief-usefulness-repair/04-source-ref-gates/`.

## Suggested Commit

`fix(second-brain): gate model synthesis on source-linked useful context`
