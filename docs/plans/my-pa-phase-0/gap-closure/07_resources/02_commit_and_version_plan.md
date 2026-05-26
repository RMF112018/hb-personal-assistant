# Commit and Version Plan

## Recommended Branch

```bash
git checkout -b remediation/gap-closure-mvp
```

## Suggested Versioning

Keep current version `1.3.0` during remediation unless project policy requires a bump for each fix. At final closeout, bump to:

```text
1.3.1
```

Rationale: this is corrective remediation/hardening on the v1.3.0 MVP closeout, not a new feature milestone.

## Suggested Commit Sequence

1. `chore(audit): reconcile repo truth and closeout evidence`
2. `fix(cli): align auth and run command groups with canonical grammar`
3. `fix(automation): correct launchd executable and command rendering`
4. `fix(validation): make tests lint and type checks pass`
5. `test(graph): refresh delegated graph proof for current runtime`
6. `feat(mail): add bounded in-memory body mention detection`
7. `feat(graph): add bounded paging to read clients`
8. `fix(files): require source provenance for file ingestion`
9. `feat(brief): wire daily brief to current context sources`
10. `fix(security): implement bounded content sensitive scan`
11. `chore(closeout): regenerate truthful final remediation evidence`

## Final Merge Criteria

Do not merge final remediation branch until Prompt 11 validates successfully.
