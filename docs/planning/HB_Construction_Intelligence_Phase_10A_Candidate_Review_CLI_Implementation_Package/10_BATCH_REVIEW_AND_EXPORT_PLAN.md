# 10 Batch Review and Export Plan

## Batch input

Support one candidate ID per line:

```text
abc123
candidate_456
# comments ignored if implemented deliberately
```

Recommended flags:

- `--candidate-id-file /tmp/ids.txt`
- `--max-actions 25`
- `--dry-run`
- `--apply`
- `--reason "..."` for ignore/reject

## Batch safety

- Dry-run default.
- Apply requires explicit `--apply`.
- Reject file with duplicate IDs unless deduplication is explicitly reported.
- Fail if `--max-actions` is exceeded.
- Stop or skip unknown IDs according to a clear policy. Recommended: default fail-fast; optional `--skip-missing` can be future scope.

## Export

`review export` should write a redacted JSON file containing export metadata, filters used, candidate rows, safe source refs/evidence if requested, and guardrail summary.

Never export raw bodies, prompts, responses, signed URLs, download URLs, tokens, secrets, raw Graph payloads, or raw Procore payloads.
