# 18 Acceptance Checklist

## Functional

- [ ] `review list` works for pending candidates.
- [ ] `review show` works and includes source refs/evidence redacted only.
- [ ] `review accept` updates local review status and writes event.
- [ ] `review ignore` maps to stored `suppressed` and writes event.
- [ ] `review reject` updates local review status and writes event.
- [ ] `review summary` returns grouped counts.
- [ ] `review snooze` works if V43 migration is implemented.
- [ ] `review edit` works if V43 migration is implemented.
- [ ] `review export` writes redacted JSON.
- [ ] Batch review defaults to dry-run and requires `--apply`.

## Safety

- [ ] No raw prompt/body/response appears in CLI output.
- [ ] No external writeback occurs.
- [ ] Guard columns remain zero.
- [ ] Source refs remain intact.
- [ ] Stable keys remain unchanged.
- [ ] Existing extraction commands still work.
