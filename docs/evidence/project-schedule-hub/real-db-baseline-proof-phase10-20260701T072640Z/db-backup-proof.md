# DB Backup Proof

**STAMP:** 20260701T072640Z  
**Proof type:** real local DB backup  
**Timestamp:** 2026-07-01T07:28:52Z (UTC)

## DB path

`/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`

## Backup files (local only — not committed)

| File | Size |
|------|------|
| `db-backup/hb-personal-assistant.sqlite.pre-phase10` | 3.8G |
| `db-backup/hb-personal-assistant.logical-backup.pre-phase10.sqlite` | 3.8G |

## Integrity check

```
PRAGMA integrity_check; → ok
```

## Rollback

```bash
cp "$EVIDENCE/db-backup/hb-personal-assistant.logical-backup.pre-phase10.sqlite" \
  "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
```
