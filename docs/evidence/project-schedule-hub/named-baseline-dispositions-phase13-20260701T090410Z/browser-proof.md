# Phase 13 Browser Proof

**Proof type:** live browser (screenshots local-only; manifest committed)

## Capture

Script: `capture_browser_proof.py`  
Screenshots: `screenshots/` (gitignored — redacted schedule content)

## Manifest (`screenshot-proof.json`)

| Shot | Proof |
|------|-------|
| `01-named-workbench-loaded.png` | Named baseline review banner; sync enabled |
| `02-prior-update-unaffected.png` | Prior Update workbench |
| `03-progress-slot-separate.png` | Previous Progress Update Baseline workbench |

## Loaded-state gate

Each shot waits for surface text (`Named baseline review` or `Schedule Workbench`) before capture.

## Note

Full PNG files remain local under evidence `screenshots/` per redaction policy. Re-capture with `capture_browser_proof.py` after starting backend (`uvicorn ... --factory`) and `npm run dev`.
