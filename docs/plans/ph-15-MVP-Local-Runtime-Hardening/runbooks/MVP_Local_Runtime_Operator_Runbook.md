# MVP Local Runtime Operator Runbook

## Activate Environment

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate
```

## Basic Diagnostics

```bash
hb-assistant --version
hb-assistant diagnostics env --json
hb-assistant diagnostics paths --json
hb-assistant diagnostics automation --json
```

## Safe Daily Dry-Run

```bash
hb-assistant run morning --dry-run --json
```

## Action Intelligence

```bash
hb-assistant actions extract --dry-run --json
hb-assistant actions list --json
```

## Sensitive Scan

```bash
hb-assistant diagnostics scan-sensitive --repo . --json
```

## What Is Allowed Locally

- SQLite local state.
- Run ledger.
- Redacted evidence.
- Marker-bounded Obsidian note writes only in apply/write mode.
- Source links for generated local outputs.

## What Is Not Allowed

- Microsoft 365 writeback.
- App-only runtime mail/calendar.
- Full email body persistence.
- Full file content persistence.
- Token/PEM/cache evidence.
