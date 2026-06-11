# Merge Readiness Checklist

Do not mark merge-ready unless every item is satisfied.

- [ ] Working branch is not `main`.
- [ ] Repo-truth audit completed and committed as evidence.
- [ ] Ranking/assembly prerequisite exists or implementation stopped honestly.
- [ ] Schema migration is additive only.
- [ ] Guard columns exist and sum to zero.
- [ ] Dry-run writes zero rows.
- [ ] Apply validation used `/tmp` DB copy only.
- [ ] Production DB SHA unchanged.
- [ ] No lifecycle mutation from telemetry.
- [ ] No source-ref mutation from telemetry.
- [ ] Raw leak scan passed.
- [ ] Source-ref coverage reported honestly.
- [ ] Procore noise metrics are advisory only.
- [ ] Model metrics are advisory only.
- [ ] Small samples marked insufficient.
- [ ] Existing V50 lifecycle tests pass.
- [ ] Existing V51+ ranking/assembly tests pass when present.
- [ ] Focused new tests pass.
- [ ] Final handoff uses `FINAL_HANDOFF_TEMPLATE.md`.
