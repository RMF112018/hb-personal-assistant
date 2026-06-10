# 22 — CLI Help Snapshots

Captured with COLUMNS=200. Raw-free; flags only.

## second-brain daily-run run (options excerpt)
```
│ --synthesize --no-synthesize Local-model executive synthesis of the brief (apply only; fail-closed → degraded brief on model │
│ [default: synthesize] │
│ --model-enriched-intelligence --no-model-enriched-intelligence DEFAULT-ON: render the single converged 'Model Enriched Intelligence' section (source-linked advisory bullets + │
│ never accepted fact; fails closed to the deterministic brief. Use --no-model-enriched-intelligence to disable. │
│ [default: model-enriched-intelligence] │
│ --with-intelligence --no-intelligence Back-compat alias: additionally attach the standalone advisory intelligence object to the --json payload. The │
│ brief's 'Model Enriched Intelligence' section is now default-on (see --model-enriched-intelligence); this flag │
│ --email-raw-enrichment --no-email-raw-enrichment DEFAULT-ON (apply only): run the bounded, capped, idempotent, source-linked V45 email raw enrichment stage so │
│ and writes nothing; apply is capped by --email-raw-enrichment-max-persist (else --max-persist-per-stage). │
│ [default: email-raw-enrichment] │
│ --email-raw-enrichment-max-persist INTEGER Cap on ACTUAL V45 enrichment writes in apply mode (default: --max-persist-per-stage). │
│ --with-email-raw-enrichment --no-email-raw-enrichment Back-compat alias: also attach the structured PENDING V45 email follow-up section as a machine-readable twin to │
│ [default: no-email-raw-enrichment] │
│ --open-browser --no-open-browser Reserved — auto-open is NOT enabled yet; the browser is never opened. │
│ [default: no-open-browser] │
```

## second-brain daily-run scheduler install (options excerpt)
```
│ --model-enriched-intelligence --no-model-enriched-intelligence Install with the default-on Model Enriched Intelligence section (surfaced in status). │
│ [default: model-enriched-intelligence] │
│ --email-raw-enrichment --no-email-raw-enrichment Install with the default-on bounded, capped V45 email raw enrichment apply stage. │
│ [default: email-raw-enrichment] │
│ --email-raw-enrichment-max-persist INTEGER Scheduled cap on V45 enrichment writes (default: --max-persist-per-stage). │
```

## second-brain follow-up-watch enrich-readiness
```
 
 Usage: python -m hb_assistant.cli.main second-brain follow-up-watch enrich-readiness 
 [OPTIONS] 
 
 Read-only V45 email raw enrichment readiness/eligibility report (raw-free). 
 
 Walks the accepted task/commitment funnel and reports, by reason code, what can safely enrich and why no-op conditions occur (no source refs, no email refs, no raw content, already enriched, local 
 model unavailable, …). Existence of raw email content is determined ONLY from safe source refs / hashes / window-builder availability metadata — raw email body text is never loaded or printed. 
 DB-copy validation is recommended for live proof; this command performs no model run, no persistence, and no writeback. 
 
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --candidate-id TEXT Report readiness for a single accepted candidate id. │
│ --include-closed Also include closed/completed items in the funnel. │
│ --limit INTEGER Max accepted items per type to scan. │
│ [default: 200] │
│ --db TEXT Explicit SQLite path (tests/isolation). │
│ --json Emit JSON (default). │
│ [default: True] │
│ --help Show this message and exit. │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## second-brain follow-up-watch (subcommands)
```
│ scan Scan accepted tasks/commitments → advisory follow-up watch items/status events. │
│ report Review-safe follow-up watch report grouped by operator action (deterministic / read-only). │
│ enrich Enrich source-linked follow-up items from bounded LOCAL raw email context (dry-run default). │
│ enrich-readiness Read-only V45 email raw enrichment readiness/eligibility report (raw-free). │
```
