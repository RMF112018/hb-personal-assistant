# Phase 10 Checkpoint 6 — Daily Local-Agent Run + launchd Scheduler (Operator Runbook)

A weekday (Mon–Fri) 5:00 AM job that generates your daily brief automatically: it runs the proven
local-agent pipeline, applies a bounded set of local candidates, and produces **two private local
consumption surfaces** — a governed Obsidian note and a polished browser HTML file — plus a status
file. The browser is **not** auto-opened (reserved for later). No external/Graph/Procore/calendar
writeback ever occurs.

Branch: `experiment/local-agent-family-proof` (experimental; not merged). Commands run via the
`hb-assistant` CLI (inside the venv or via `.venv/bin/hb-assistant`).

## What you get each weekday morning

- **Obsidian note** (real content): `<vault>/Construction Intelligence/Phase 08A Daily Briefs/<date>_daily_brief.md`
- **Browser brief** (stable path, real content): `~/Library/Application Support/HB Personal Assistant/html/daily-brief-latest.html`
  - dated archive: `daily-brief-<date>.html`; last attempted (may be partial): `daily-brief-latest-attempted.html`
- **Status file** (redacted, safe): `~/Library/Application Support/HB Personal Assistant/daily-run-status/latest-status.json`
  - per-run archive: `status-<timestamp>.json`; last-good pointer: `last-successful.json`

The brief is weekday-aware: **Monday** folds in weekend / prior-week carryover; **Tue–Thu** are
standard adjacent-business-day briefs; **Friday** prepares the following workweek (calendar looks
ahead through next Friday). Weekends don't generate a fresh brief; if the Mac was asleep at 5:00 AM,
launchd runs the missed weekday job on the next wake (a missed Friday caught up on the weekend still
produces the Friday/next-week brief).

## Install the schedule (one time)

Plan first (writes nothing — shows the plist + readiness):

```bash
hb-assistant second-brain daily-run scheduler install --confirm-vault-write
```

Then install for real (writes the LaunchAgent plist + `launchctl load`):

```bash
hb-assistant second-brain daily-run scheduler install --apply --confirm-vault-write \
  --db "<path to your working SQLite DB>"
```

- `--confirm-vault-write` is **required** (the job writes the governed Obsidian note).
- `--db` pins the database the scheduled job reads/persists. If omitted, the default path policy DB
  is used — set it explicitly to the DB you actually work from.
- Defaults are conservative: `--max-persist-per-stage 10 --max-total-persist 30 --limit 50`,
  `--raw`, `--write-obsidian`, `--generate-browser`, `--no-open-browser`, weekday-only, 05:00 local.

## Status / uninstall

```bash
hb-assistant second-brain daily-run scheduler status                 # plist present? schedule? readiness
hb-assistant second-brain daily-run scheduler uninstall              # plan (writes nothing)
hb-assistant second-brain daily-run scheduler uninstall --apply      # unload + remove the plist
```

## Run it manually (test any time)

Dry-run (zero writes — preview the policy + counts):

```bash
hb-assistant second-brain daily-run run --as-of "$(date -u +%Y-%m-%dT05:00:00-04:00)"
```

Full apply to temp locations (safe test — no real vault, no app-support):

```bash
hb-assistant second-brain daily-run run --apply --raw \
  --write-obsidian --confirm-vault-write --vault-brief-dir /tmp/hb_test_vault \
  --browser-output-dir /tmp/hb_test_html --status-dir /tmp/hb_test_status --db "<copy.sqlite>"
```

Real apply (writes the real vault + app-support browser/status):

```bash
hb-assistant second-brain daily-run run --apply --raw \
  --write-obsidian --confirm-vault-write --db "<your working DB>"
```

## Reading the result

- **`status` field** in the JSON / status file:
  - `success` — fresh brief generated; `daily-brief-latest.html` updated.
  - `partial` — some stages failed; a clearly-marked degraded `daily-brief-latest-attempted.html`
    is written, **`daily-brief-latest.html` is NOT touched** (last good preserved).
  - `failure` — nothing safe to render; last good preserved; status file explains (redacted).
  - `skipped_weekend` — a fresh weekend run; nothing generated.
- **`date_policy`** explains exactly which window was used (label + lookback/lookahead/calendar dates
  + a plain-English `explanation`).
- **`egress_scan.clean`** must be `true` (the browser HTML is withheld if any egress pattern slips
  through — last good is preserved).

After a run, check: `status` is `success`; `daily-brief-latest.html` opens and shows today's date;
the Obsidian note exists for the date; `egress_scan.clean` is `true`.

## Rollback / disable

- Disable the schedule: `hb-assistant second-brain daily-run scheduler uninstall --apply`.
- Generated outputs live outside the repo (app-support + vault) and can be deleted freely; the
  `last-successful.json` pointer + `daily-brief-latest.html` are the only "current" state.
- Nothing here mutates Microsoft 365, Procore, the calendar, or the schema; safe to remove without
  side effects.

## Safety notes

- Raw content appears **only** in the Obsidian note and browser HTML (private local surfaces). The
  status file, persisted candidate rows, repo, tests, evidence, and logs stay redacted.
- Output directories inside the repo are refused. The governed vault write is marker-bounded and
  requires explicit `--confirm-vault-write`.
- Guardrail columns stay zero; the run is advisory and read-only against all external systems.
