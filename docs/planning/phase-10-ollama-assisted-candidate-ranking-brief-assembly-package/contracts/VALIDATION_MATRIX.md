# Validation Matrix

| Area | Required Proof |
| --- | --- |
| Schema | additive migration, idempotent, guard columns zero |
| Dry-run | zero writes |
| Apply | requires max persist cap |
| Source refs | 100% coverage for surfaced actionable candidates |
| Lifecycle | excluded states hidden; accepted/stale/review-required honest |
| Packet safety | no raw/leak scanner passes |
| Model safety | unknown aliases dropped; unsafe output withheld |
| Fallback | unavailable/timeout/schema-invalid output preserves deterministic ranking |
| Feedback | aggregate, sample-thresholded, clamped |
| Similarity | advisory only, no auto-merge/suppress |
| Rendering | degraded banner when model withheld |
| Static | compile, ruff, mypy clean |
| Tests | focused pytest suite passes |
