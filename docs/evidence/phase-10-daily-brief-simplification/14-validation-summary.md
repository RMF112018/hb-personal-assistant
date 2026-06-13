# 14 — Validation summary

## Acceptance artifact

The generated **browser HTML from the scheduled `daily-run run`** (apply mode, on a `/tmp` copy of the
production DB), brief date 2026-06-12, `--as-of 2026-06-12T05:00:00-04:00`.

The visible product is, in order: `Today's Daily Brief` → subhead → `New Today` → `Needs your
attention` / `Team follow-up / monitor` / `Awareness only` → collapsed `Run details / diagnostics`.
No status/success banner, `friday_next_week`, project keys, or candidate/synthesis metrics above New
Today. New Today produced **42 source-linked business events** (email 4, calendar 16, Procore 22).

## Production-DB safety

- Source DB resolved from `PathPolicy.get_db_path()` (plain Application Support root).
- `lsof` confirmed no active writer on the plain prod DB before copy (the running
  `daily-source-refresh --environment dev` scheduler targets the `(Dev)` root).
- Apply ran on the `/tmp` copy only. **SHA-256 unchanged before/after** —
  `b0216f0f…65a1bc` (see `11-prod-db-sha-unchanged.txt`).

## Result matrix

| Gate | Result |
|---|---|
| Browser HTML leads with New Today, diagnostics collapsed | PASS (`07`, live section scan) |
| Subhead `Summary of the top items for {date} and prep through {lookahead}` | PASS (`2026-06-12` → `2026-06-19`) |
| No forbidden tokens / banners / date-policy above the fold | PASS (NONE) |
| HTML egress scan (`scan_daily_run_html`) | PASS (`[]`) |
| Real run JSON + status forbidden-token scan | PASS (NONE) — `09`, `10` |
| `daily_brief` block present (run payload + `latest-status.json`) | PASS |
| Product status driven by New Today, legacy synthesis demoted to diagnostics | PASS (`03`) |
| Legacy top-level `status` preserved | PASS (`deterministic_success_synthesis_degraded` still emitted) |
| Guard columns zero on the copy | PASS (`12`) |
| Prod DB SHA unchanged | PASS (`11`) |
| `compileall` / `ruff` (changed) / `mypy` (changed) | PASS (`05`) |
| `pytest` (focused simplified + New Today + daily-run + usefulness suites) | PASS (`05`) |

## Secondary artifacts

- `06-daily-run-json-sample.json` — raw-safe counts/status excerpt of the real run.
- `07-browser-html-sample.html` / `08-markdown-sample.md` — synthetic, commit-safe renders.
- `09-copy-quality-scan.json` / `10-raw-safety-scan.json` — scan verdicts (all clean).
- `11-prod-db-sha-unchanged.txt` / `12-guard-columns-zero.json` — safety proofs.

See `13-known-limitations.md` for caveats.
