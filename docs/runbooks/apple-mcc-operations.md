# Apple Local MCC — Operations Runbook

## Commands
- Probe (dry): `python -m hb_assistant.cli.apple_mcc dry-run --action status`
- Importer dry-run: `python -m hb_assistant.apple_mcc.importer.cli --dry-run`

## Evidence
Detached EV root:
`$HOME/Library/Application Support/HB Personal Assistant/evidence/apple-mcc`

## Not authorized without operator gate
push, PR, merge, NAS production migration, live capture beyond fixtures, launchd enable.
