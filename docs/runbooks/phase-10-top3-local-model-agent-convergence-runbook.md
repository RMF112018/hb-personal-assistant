# Runbook — Phase 10 Top 3 Local-Model Agent Convergence

All commands run inside the venv (`source .venv/bin/activate` or prefix `.venv/bin/`). Defaults are
safe (dry-run, no writeback, browser never auto-opened). Use a DB copy for any apply validation.

## Daily brief — manual dry-run (no writes)

```bash
hb-assistant second-brain daily-run run --dry-run --json
```
- Model Enriched Intelligence is **default-on**; JSON `model_enriched_intelligence.enabled=true`.
- Dry-run persists nothing; the email raw enrichment stage reports `skipped`/`would_persist` only.

## Daily brief — manual apply on a DB copy (never production)

```bash
SRC="$(hb-assistant ... )"   # resolve via PathPolicy.get_db_path(); or copy the file directly:
cp "$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" /tmp/hb-copy.sqlite
hb-assistant second-brain daily-run run --apply --db /tmp/hb-copy.sqlite \
  --max-persist-per-stage 10 --max-total-persist 30 \
  --browser-output-dir /tmp/hb-html --status-dir /tmp/hb-status --json
```
- Apply runs the bounded V45 email raw enrichment stage (capped); MEI consumes pending rows.
- Browser HTML + status are written under the non-repo dirs above; the browser is **not** opened.

## Disable Model Enriched Intelligence / email raw enrichment

```bash
hb-assistant second-brain daily-run run --no-model-enriched-intelligence --json
hb-assistant second-brain daily-run run --no-email-raw-enrichment --json
```

## Email raw enrichment — readiness (read-only, raw-free)

```bash
hb-assistant second-brain follow-up-watch enrich-readiness --json
```
- Reports accepted/eligible counts and per-reason skip counts; loads no raw body. If `eligible=0`,
  read `skipped_by_reason` (e.g. `no_email_source_ref`, `no_raw_email_content`, `local_model_unavailable`).

## Email raw enrichment — standalone enrich (dry-run / capped apply on a copy)

```bash
hb-assistant second-brain follow-up-watch enrich --dry-run --json --db /tmp/hb-copy.sqlite
hb-assistant second-brain follow-up-watch enrich --apply --max-persist 10 --json --db /tmp/hb-copy.sqlite
# Terminal-only redacted raw preview (never JSON/apply/evidence):
hb-assistant second-brain follow-up-watch enrich --show-raw-local --dry-run --no-json --db /tmp/hb-copy.sqlite
```

## Scheduler — preview, status, install, uninstall

```bash
hb-assistant second-brain daily-run scheduler install --dry-run --confirm-vault-write --json   # plan only
hb-assistant second-brain daily-run scheduler status --json                                    # readiness + posture
hb-assistant second-brain daily-run scheduler install --apply --confirm-vault-write --json      # real install (operator choice)
hb-assistant second-brain daily-run scheduler uninstall --apply --json                          # rollback / uninstall
```
- Preview/status show `effective_config` (MEI on, email-raw on, `browser_auto_open: false`),
  `readiness` (executable/workdir/log + redacted paths, `blocking_diagnostics`), weekday intervals,
  catch-up-on-wake, and `last_run`. Install is blocked if readiness is blocking.

## Reading status / latest brief

```bash
cat "$HOME/Library/Application Support/HB Personal Assistant/daily-run-status/latest-status.json"
ls "$HOME/Library/Application Support/HB Personal Assistant/html/"   # daily-brief-latest.html (last good)
```
- `model_enriched_intelligence` block: `enabled/available/degraded/withheld_reason`, source-linked
  bullet counts, `pending_followup_count`.
- `run_summary.result`: `success` / `partial` / `degraded` / `failure`; `browser_auto_opened: false`.

## Interpreting degraded / withheld

- **MEI withheld/degraded** (model unavailable, no source-linked bullets): the deterministic brief is
  authoritative; pending rows still render; run can still be `success` (MEI is advisory).
- **Synthesis degraded**: narrative body falls back to deterministic candidates; run downgraded to
  `partial`; last-successful pointer preserved.

## Emergency disable / rollback

```bash
# Stop the scheduled job:
hb-assistant second-brain daily-run scheduler uninstall --apply --json
# Or run with everything advisory disabled:
hb-assistant second-brain daily-run run --no-model-enriched-intelligence --no-email-raw-enrichment --no-synthesize --dry-run --json
```
- Nothing writes back to Microsoft 365 / Procore / Graph / calendar / email under any flag. The only
  writes are local SQLite (review-safe, capped, guarded) and local browser/Obsidian output files.
