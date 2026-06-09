# Preview apply (dry-run)

The consolidated report's preview-apply section shows the accepted set an operator apply would act on, bounded by `--apply-cap`. It persists nothing.

```json
{
  "dry_run": true,
  "cap": 10,
  "accepted_total": 1,
  "would_persist_count": 1,
  "would_persist_candidate_ids": [
    "t3"
  ],
  "note": "Dry-run preview: accepted candidates ready to act on. Apply review decisions in bounded batches via `second-brain review accept --candidate-id-file <f> --apply --max-actions <cap>`; this report never persists."
}
```
