# Prompt 12 Email Obsidian Output Preview (Sanitized)

Date: 2026-05-30

## CLI Dry-Run Envelope

```json
{
  "command": "graph mail obsidian",
  "ok": false,
  "dry_run": true,
  "status": "obsidian_error",
  "error": "Database unavailable at /Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
}
```

The dry-run output remained plaintext-safe and secret-safe. No body content was emitted.

## Note Shapes (from tests)

Planned note families:
- `Work/HB Personal Assistant/06_Email_Intelligence/Mailbox Source Manifest.md`
- `Work/HB Personal Assistant/06_Email_Intelligence/Sync Receipts/Email Sync Receipt.md`
- `Work/HB Personal Assistant/06_Email_Intelligence/Projects/<project>/Correspondence Intelligence.md`
- `Work/HB Personal Assistant/06_Email_Intelligence/Review/<project> Review Required.md`
- `Work/HB Personal Assistant/06_Email_Intelligence/Projects/<project>/Meeting Prep.md`

## Guardrails Confirmed

- Plaintext body in Obsidian: `false`
- Encrypted body refs rendered: `false` (count-only/boolean status only)
- Mailbox mutation path introduced: `false`
- Prompt/body plaintext persisted by projector: `false`
