# Final Handoff Template

Use this exact structure.

## Summary

- Manifest:
- Branch:
- Commit SHA:
- Base:
- Merge target:
- Merge readiness:

## Changed files

```text
<path list>
```

## Implementation summary

- Lifecycle/read model:
- Schema/migration:
- Disposition operations:
- Promotion/source refs:
- Duplicate/merge/suppression:
- Feedback read model:
- Daily brief integration:
- Usefulness gate/status:
- CLI/operator surface:
- Raw-safety hardening:

## Validation

| Check | Result | Evidence |
|---|---|---|
| Compile |  |  |
| Ruff |  |  |
| Targeted pytest |  |  |
| Existing Phase 10A review regression |  |  |
| DB integrity on `/tmp` copy |  |  |
| Migration check, if applicable |  |  |
| Idempotency replay |  |  |
| No-raw-leak scan |  |  |
| Usefulness gate |  |  |
| Rendered daily brief |  |  |

## DB-copy validation results

- Production DB copied from:
- Copy path:
- Production DB SHA before:
- Production DB SHA after:
- Integrity check:
- Migration result:
- Candidate counts:
- Review queue counts:
- Lifecycle transition counts:
- Accepted task count:
- Accepted commitment count:
- Rejected count:
- Snoozed count:
- Merged count:
- Suppressed count:
- Closed count:
- Reopened count:
- Source-ref coverage:
- Project-key coverage:
- Duplicate/idempotency result:
- Guard-column result:
- Raw access event delta:

## Usefulness / status

- Lifecycle gate result:
- Daily-brief lifecycle status:
- Degraded/withheld reasons:
- Data-gap cards:
- Known lifecycle contradictions:

## Raw-safety statement

State whether any raw body, raw HTML, recipient array, attendee array, private URL, signed URL, token, model prompt/response, or raw Procore detail leaked into outputs/evidence.

## Production safety statement

State whether production DB or external systems were mutated.

## Known failures / limitations

- 
- 
- 

## Merge readiness statement

Use one of:

- `Merge-ready`
- `Not merge-ready`

If not merge-ready, include the exact blockers.

