# Final Output Manifest — Daily Brief Surface Convergence

## Intended operator-facing output

After this candidate, Bobby's daily brief surfaces converge: whenever pending review-safe V45 email
follow-up enrichments exist, a clearly-labeled **"Model-enriched / pending review"** section appears
in (a) the polished browser HTML brief, (b) the governed Obsidian note, and (c) a redacted count in
the status JSON — deterministically, without requiring local-model synthesis, and surviving the
degraded path. Items are source-linked (enrichment/candidate/watch IDs + safe refs) and never present
model inference as accepted fact.

## Generated proof artifacts

| Artifact | Path | Generated from | Safe to commit? | Notes |
|---|---|---|---|---|
| Browser final output | `03-browser-final-output.html` | temp DB, synthetic rows | yes | The real self-contained HTML brief; egress-clean. |
| Obsidian final output | `04-obsidian-final-output.md` | temp vault write | yes | The real marker-bounded governed note. |
| Status final output | `05-status-final-output.json` | temp run | yes | Redacted; carries `pending_followup` counts only. |
| No-row render proof | `01-no-row-render-proof.json` | empty temp DB | yes | Section absent, count 0. |
| Seeded render proof | `02-seeded-v45-render-proof.json` | seeded temp DB | yes | Section present in HTML + Obsidian (3 rows). |
| Degraded proof | `06-degraded-output-proof.md` | direct renderer call | yes | Card present on degraded path. |
| Safety scan | `07-safety-scan-results.txt` | forbidden-pattern scan | yes | 0 findings. |
| Guard-column proof | `08-guard-column-proof.json` | temp DB introspection | yes | 13 guards, nonzero_sum=0. |
| Production DB unchanged | `09-production-db-unchanged-proof.txt` | sha256 before/after | yes | UNCHANGED=True. |

## Output acceptance criteria

- Understandable without inspecting internals: ✅ labeled section + plain bullets.
- Source IDs / citations: ✅ enrichment/candidate/watch IDs + source refs per item.
- Distinguishes inference from fact: ✅ "Model-enriched / pending review … advisory, not accepted fact".
- Redacted/sanitized: ✅ synthetic fixtures, raw-free, egress-clean.
- No forbidden content: ✅ safety scan 0 findings.
- Stable path / invocation: ✅ browser HTML + Obsidian note + status at stable non-repo paths.

## Manual verification command

```bash
# Deterministic, no model, temp DB — regenerates the operator artifacts:
python3.12 /tmp/gen_evidence_01.py
# Or via the CLI against a temp DB (dry-run preview; --apply on a copy writes the surfaces):
hb-assistant second-brain daily-run run --as-of 2026-06-09T05:00:00-04:00 --no-synthesize \
  --with-email-raw-enrichment --json --db /tmp/copy.sqlite
```
