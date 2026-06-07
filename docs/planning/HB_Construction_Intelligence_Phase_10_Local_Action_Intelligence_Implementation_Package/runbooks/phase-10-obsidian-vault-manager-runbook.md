# Phase 10 Obsidian Vault Manager Runbook

## Validate vault

```bash
hb-assistant vault status --json
hb-assistant vault index --dry-run --json
```

## Write Daily Brief dry-run

```bash
hb-assistant vault write-daily-brief --date 2026-06-07 --dry-run --json
```

## Safety

- Check the diff before apply.
- Confirm only managed HB markers changed.
- Confirm user text and checkbox state are preserved.
