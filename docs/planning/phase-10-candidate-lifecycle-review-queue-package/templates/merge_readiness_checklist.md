# Merge Readiness Checklist

- [ ] Branch is based on current `origin/main`.
- [ ] Dirty tree is understood and not accidental.
- [ ] No production DB mutation during validation.
- [ ] No external writeback.
- [ ] Existing Phase 10A review tests pass.
- [ ] New lifecycle tests pass.
- [ ] DB copy integrity is `ok`.
- [ ] Migration, if any, is additive and validated.
- [ ] Guard columns remain zero.
- [ ] Source-ref coverage is 100% for surfaced actionable/executive rows.
- [ ] Accepted actions have source-ref traceability.
- [ ] Rejected/suppressed/merged rows hidden from normal daily brief.
- [ ] Snooze behavior works.
- [ ] Duplicate replay is idempotent.
- [ ] Usefulness gate catches lifecycle contradictions.
- [ ] No raw leak scan passes.
- [ ] Final handoff complete.

