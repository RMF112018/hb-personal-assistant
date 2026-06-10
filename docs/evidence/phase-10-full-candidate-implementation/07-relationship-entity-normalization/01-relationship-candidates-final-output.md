# Relationship / Entity Normalization Report

_Project: (all) · read-only / dry-run / deterministic grouping._

## Summary
- total: 8 · alias/project: 2 · relationships: 2 · duplicates: 2 · needs-review: 1 · rejected: 1
- promotion-safety (unreviewed promoted as fact): 0

## Alias / project matches (2)
- **person:contact** → **project:project** _(email_project_match · strong_heuristic 0.80 · candidate)_
  - id: proj1 · project: PRJ-A · deterministic: True · refs: 2 · signals: [shared_thread, same_project]
- **person:contact** → **project:project** _(calendar_project_alias · strong_heuristic 0.80 · candidate)_
  - id: proj2 · project: PRJ-B · deterministic: True · refs: 2 · signals: [shared_thread, same_project]

## Person / company / project relationships (2)
- **person:contact** → **company:org** _(related_to · strong_heuristic 0.80 · candidate)_
  - id: rel1 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]
- **person:contact** → **person:contact** _(related_to · strong_heuristic 0.80 · candidate)_
  - id: rel2 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]

## Likely duplicate entities (2)
- **person:contact** → **person:contact** _(same_entity · deterministic 0.95 · candidate)_
  - id: dup1 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]
- **company:org** → **company:org** _(alias_of · strong_heuristic 0.90 · candidate)_
  - id: dup2 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]

## Low-confidence / needs review (1)
- **person:contact** → **company:org** _(related_to · weak_heuristic 0.30 · needs_review)_
  - id: nr1 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]

## Rejected / not actionable (1)
- **person:contact** → **company:org** _(related_to · rejected 0.80 · rejected)_
  - id: rej1 · project: (none) · deterministic: True · refs: 2 · signals: [shared_thread, same_project]
