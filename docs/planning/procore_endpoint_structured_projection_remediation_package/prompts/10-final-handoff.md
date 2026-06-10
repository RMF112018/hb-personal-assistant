# 10 — Final Handoff

## Goal

Commit, push, and report only after all validation gates pass.

## Required final handoff

Include:

- branch,
- base SHA,
- commit SHA,
- schema head before/after,
- migration file(s),
- modified code files,
- new tables,
- endpoints covered,
- endpoints held/no-data,
- unmapped field count by endpoint,
- primary row counts,
- child/detail row counts,
- validation commands and results,
- production DB hash before/after validation,
- no-leak proof,
- post-merge production apply runbook.

## Commit

Use a conventional commit message similar to:

`feat(procore): project full endpoint payloads into endpoint-specific tables`

Do not push if:
- any endpoint with payloads has unmapped business fields,
- tests fail,
- leak scan fails,
- production DB was mutated during validation,
- evidence contains raw payload bodies.
