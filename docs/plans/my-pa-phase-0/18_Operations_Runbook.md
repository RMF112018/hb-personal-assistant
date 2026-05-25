# Operations Runbook

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
hb-assistant diagnostics env --json
```

## Auth

```bash
hb-assistant auth login
hb-assistant auth status --json
hb-assistant diagnostics auth --json
```

## Daily Brief

```bash
hb-assistant run morning --dry-run --json
hb-assistant brief generate --date today --dry-run
hb-assistant run morning --force
```

## launchd

```bash
hb-assistant automation install-launchd --dry-run
hb-assistant automation install-launchd
hb-assistant automation kickstart
hb-assistant automation uninstall-launchd
```

## Troubleshooting

- Auth failure: clear cache, re-login, verify delegated `scp`.
- 403 mail/calendar: inspect scopes/tenant/user context; do not switch to app-only.
- Missing item: inspect source_records, body mention detector, extraction confidence, source links.
- Obsidian issue: run dry-run, check markers and vault permissions.
- launchd issue: check stdout/stderr logs and run ledger.
