# DB-Copy Live Proof

Production DB read-only; apply run against a `.backup` copy with `/tmp` output roots.

## Production DB unchanged ✓
```
before: f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
after:  f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
```
`integrity_check` / `quick_check`: `ok` / `ok`.

## Run result (the repair)
```
status: deterministic_success_synthesis_degraded
ok: true | partial: false | partial-contradiction: false
synthesis_degraded: true | synthesis_status: degraded
deterministic_fallback_used: true | operator_usable: true
deterministic_fallback: { used: true, reason: synthesis_degraded:empty_synthesis_low_quality,
                          usefulness_gate_passed: true, published: true,
                          stable_path: daily-brief-latest-deterministic.html,
                          counts: { total_candidates: 18, calendar: 8, procore: 10 } }
model_enriched_intelligence: { available: false, degraded: true,
                               withheld_reason: synthesis_degraded:empty_synthesis_low_quality,
                               label: "Source-Linked Deterministic Brief" }
egress_scan: { clean: true, matched_labels: [] }
```
HTML files: `daily-brief-2026-06-10.html`, `daily-brief-latest-attempted.html`,
`daily-brief-latest-deterministic.html` (no `daily-brief-latest.html` — Option A).

## Stop conditions
None triggered: prod DB unchanged; no writeback; no raw/token leak; egress clean; no
`partial:false` contradiction; MEI not available/degraded=false under degraded synthesis; deterministic
fallback published only because the usefulness gate passed.

Artifacts: `integrity_check.txt`, `quick_check.txt`, `prod-before.sha256`, `prod-after.sha256`,
`latest-status.safe.json` (sanitized), `html-files.txt`. Raw `/tmp` brief content referenced by path
only.
