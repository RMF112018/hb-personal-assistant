# Final Output Manifest — Relationship / Entity Normalization

## Intended operator-facing output

`second-brain relationship-candidates report`: one consolidated, review-safe report of the unified V25
cross-source relationship/entity candidates, grouped by operator action — alias/project matches,
person/company/project relationships, likely-duplicate entities, low-confidence needs-review, and
rejected/not-actionable — each source-linked with confidence + reason signal-types. Read-only;
deterministic grouping; persists/promotes nothing.

## Generated proof artifacts

| Artifact | Path | From | Safe? |
|---|---|---|---|
| Report (MD) | `01-relationship-candidates-final-output.md` | seeded temp DB | yes |
| Report (JSON) | `02-relationship-candidates-final-output.json` | seeded temp DB | yes |
| Dedupe proof | `03-dedupe-proof.json` | same-entity candidates | yes |
| Alias-match proof | `04-alias-match-proof.json` | project candidates | yes |
| Low-confidence proof | `05-low-confidence-proof.md` | weak/model-proposed | yes |
| Daily-brief context | `06-daily-brief-context-proof.json` | promotion-safety | yes |
| Dry-run / read-only | `07-apply-cap-or-dry-run-proof.json` | rows before/after | yes |
| Safety scan | `08-safety-scan-results.txt` | scan | yes (0 findings) |
| Guard-column proof | `09-guard-column-proof.json` | introspection | yes (sum 0) |
| Production DB unchanged | `10-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |

## Manual verification command

```bash
hb-assistant second-brain relationship-candidates report --db /tmp/copy.sqlite --no-json
hb-assistant second-brain relationship-candidates report --project <key> --markdown-out /tmp/rel.md --json
```
