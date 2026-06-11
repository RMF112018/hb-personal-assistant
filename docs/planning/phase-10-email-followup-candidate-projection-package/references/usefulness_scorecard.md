# Usefulness Scorecard Template

Use this after validation.

| Metric | Result | Merge Gate |
|---|---:|---|
| Raw email rows available |  | Informational |
| Structured email rows available |  | Must be nonzero if raw rows exist after projection |
| Raw thread rows available |  | Informational |
| Structured thread rows available |  | Must be nonzero if raw thread rows exist after projection |
| Eligible messages considered |  | Informational |
| Eligible threads considered |  | Informational |
| Follow-up candidates generated |  | Must match expectations for seeded fixtures |
| Domain candidates persisted |  | Must be idempotent |
| Daily-brief candidates persisted |  | Must be idempotent |
| Source-ref coverage |  | Must be 100% |
| Executive source-ref coverage |  | Must be 100% |
| Project-key coverage |  | Must be reported; unresolved items need review status |
| Review-required count |  | Informational unless hidden |
| Data-gap card when no candidates |  | Required |
| Data-gap card replaced when candidates exist |  | Required |
| Usefulness gate verdict |  | Must not be false success |
| No-raw-leak scan |  | Must be clean |
| Guard columns |  | Must remain zero |
| Production DB mutation |  | Must be zero |
| External writeback |  | Must be zero |
