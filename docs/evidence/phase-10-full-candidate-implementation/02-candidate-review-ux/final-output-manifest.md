# Final Output Manifest — Candidate Review UX

## Intended operator-facing output

A single legible **candidate review report** (`second-brain review report`) that Bobby can read
without inspecting DB rows: a lifecycle summary, a dry-run preview of the bounded accepted set, a
"needs Bobby's review" group, and per-group items each source-linked with confidence + safety
reasons. JSON by default; Markdown via `--no-json` / `--markdown-out`. Persists nothing; the bounded
apply remains `review accept … --apply --max-actions`.

## Generated proof artifacts

| Artifact | Path | Generated from | Safe to commit? | Notes |
|---|---|---|---|---|
| Review report (final) | `01-review-list-final-output.md` | temp DB, synthetic | yes | The headline operator surface. |
| Candidate detail | `02-review-detail-final-output.md` | `show_review_candidate` | yes | Single-candidate + source refs. |
| Review export | `03-review-export-final-output.json` | `export_review_queue` | yes | Redacted queue payload. |
| Preview apply | `04-preview-apply-output.md` | report `preview_apply` | yes | Dry-run, bounded; persists nothing. |
| Apply-cap proof | `05-apply-cap-proof.json` | batch accept `--apply --max-actions 2` | yes | 2 applied, 3 over cap. |
| Accept/reject proof | `06-reject-accept-proof.json` | service transitions | yes | Status flips + audit event ids. |
| Safety scan | `07-safety-scan-results.txt` | forbidden-pattern scan | yes | 0 findings. |
| Production DB unchanged | `08-production-db-unchanged-proof.txt` | sha256 before/after | yes | UNCHANGED=True. |

## Output acceptance criteria

- Understandable without internals: ✅ grouped Markdown report.
- Source IDs / citations: ✅ `source: [family:hash]` per item.
- Distinguishes inference from fact: ✅ confidence + "needs Bobby's review"; preview is dry-run.
- Redacted/sanitized: ✅ synthetic fixtures, redacted fields only.
- No forbidden content: ✅ safety scan 0 findings.
- Stable invocation: ✅ `second-brain review report`.

## Manual verification command

```bash
hb-assistant second-brain review report --db /tmp/copy.sqlite --no-json   # prints the Markdown report
hb-assistant second-brain review report --db /tmp/copy.sqlite --markdown-out /tmp/review.md --json
```
