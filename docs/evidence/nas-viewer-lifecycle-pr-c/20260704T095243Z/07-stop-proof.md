# 07 — Stop proof

## Command

```sh
sudo sh scripts/stop.sh --down
```

## Result: PASS

- Container `hb-personal-assistant-backend` stopped and removed
- Network `nas_default` removed
- Only HB compose project affected

Captured: `captured/evidence/stop.txt`

Post-stop `status.sh`: container absent, no port binding.

Post-stop LISTEN: **port 8000 not listening**
