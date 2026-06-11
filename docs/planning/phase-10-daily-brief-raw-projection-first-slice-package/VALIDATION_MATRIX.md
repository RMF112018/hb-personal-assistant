# Validation Matrix

| Gate | Command / method | Evidence file | Pass condition |
|---|---|---|---|
| Repo truth | `git status`, `git log`, `git branch`, target commit inspection | `00-repo-state.md`, `01-branch-state.txt`, `02-target-commit-basis.md` | clean controlled branch, no accidental main work |
| DB copy baseline | safe SQL against `/tmp` copy | `03-db-copy-baseline.json`, `04-schema-and-migrations.json`, `05-table-counts-baseline.json` | schema and row counts captured raw-free |
| V49 projection dry run | `email-calendar raw projection-reprocess --dry-run --db COPY` | `06-v49-projection-dry-run.json` | no writes, no raw values, ok/degraded honest |
| V49 projection apply copy | `email-calendar raw projection-reprocess --apply --no-dry-run --db COPY` | `07-v49-projection-apply-copy.json` | structured rows written on copy when raw rows exist |
| Projection coverage | `email-calendar raw projection-coverage --db COPY` | `08-v49-projection-coverage-after.json` | zero unmapped business fields |
| Calendar candidates | new/updated calendar projection command or daily-run stage on copy | `09`, `10` | candidates written when useful events exist; refs written |
| Procore candidates | new/updated Procore digest command or daily-run stage on copy | `11`, `12` | promoted rows persisted; aggregate backlog suppressed |
| Project identity | resolver/promotion proof | `13-project-identity-resolution-proof.json` | deterministic mappings persisted or marked review |
| Source-ref coverage | source-ref gate report | `14-candidate-source-ref-coverage.json` | 100% for executive sections |
| Usefulness gate | known-good/known-bad test | `15`, `16` | clean success impossible when source rows exist but candidates empty |
| Integrated daily run | dry-run/apply against copy only | `17-daily-run-integrated-copy-proof.json` | projection + candidates + gates visible in receipt |
| Status JSON | status/diagnostics command | `18-status-json-proof.json` | counts and verdicts surfaced raw-free |
| CLI help | `--help` snapshots | `19-cli-help-snapshots.md` | operator can run stages explicitly |
| Raw leak scan | repo evidence/status scan | `20-no-raw-leak-scan.txt` | no forbidden strings/classes |
| Guard columns | SQL checks | `21-guard-column-proof.json` | guard columns all zero |
| No writeback | command receipt + code scan | `22-no-writeback-proof.md` | no external mutation path used |
| Production unchanged | hash/size/mtime | `23-production-db-unchanged-proof.txt` | before == after |
| Tests/static | pytest/ruff/mypy/compile | `24-validation-results.md` | all targeted checks pass |
| Scorecard | computed summary | `25-usefulness-scorecard.md` | operator-usefulness conditions satisfied |
| Final audit | manual/code review | `28-residual-work-audit.md` | no unowned residual work inside first slice |
