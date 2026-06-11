# Feedback Read Model Contract

## Output

```json
{
  "generated_utc": "string",
  "counts": {
    "total_reviewed": 0,
    "accepted": 0,
    "rejected": 0,
    "snoozed": 0,
    "merged": 0,
    "suppressed": 0,
    "closed": 0,
    "project_review_required": 0,
    "source_missing": 0
  },
  "by_family": {},
  "by_source_family": {},
  "reason_codes": {},
  "confidence_buckets": {},
  "duplicate_groups": {},
  "project_resolution": {},
  "guardrails": {
    "raw_safe": true,
    "deterministic": true,
    "local_only": true
  }
}
```

## Confidence buckets

- `0_25`
- `26_50`
- `51_70`
- `71_85`
- `86_100`
- `unknown`

## Raw safety

No raw text, body, HTML, URL, recipient, attendee, prompt, response, token, or secret.

