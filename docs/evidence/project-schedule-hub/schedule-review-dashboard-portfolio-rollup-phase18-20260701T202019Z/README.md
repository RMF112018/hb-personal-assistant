# Phase 18 — Schedule Review Dashboard + Portfolio Rollup

Evidence stamp: `20260701T202019Z`

## Artifacts

| File | Description |
|------|-------------|
| `00-repo-state.txt` | Branch, HEAD, status |
| `01-repo-truth-audit.md` | Pre-implementation audit |
| `02-portfolio-rollup-read-model.md` | Thin read model design |
| `03-dashboard-api-proof.json` | Fixture dashboard overview |
| `04-dashboard-filter-proof.json` | Blocked filter proof |
| `05-next-action-proof.json` | Next-action samples |
| `06-redaction-proof.json` | `find_redaction_leaks` on API payload |
| `07-language-qa-proof.txt` | Export language QA |
| `08-portfolio-export.md` | Markdown export sample |
| `09`–`14` | **Fixture** browser screenshots (seeded `fixture-phase18-portfolio.db`; not live DB proof) |
| `15-test-results.txt` | Phase 18 test output |
| `16-known-limitations.md` | Limits and pre-existing failures |
| `17-rollout-checklist.md` | Rollout steps |
| `18`–`23` | **Live DB** GET-only API/export captures |
| `24-live-redaction-proof.txt` | Redaction + language QA on live artifacts |
| `25-live-browser-dashboard-overview.png` | **Live DB** browser overview (DOM count matched `18-live-dashboard-api.json`) |
| `26-live-smoke-notes.md` | Live smoke attestation (DB file/WAL/SHM metadata, row counts, mutation check) |

## Fixture capture (03–14)

```bash
python docs/evidence/project-schedule-hub/schedule-review-dashboard-portfolio-rollup-phase18-20260701T202019Z/capture_phase18_browser_proof.py
```

Uses seeded fixture DB on port 8001 and Vite on 5173 (`frontend/vite.phase18.config.ts`). Screenshots `09`–`14` prove UI wiring only.

## Live DB GET-only smoke (18–26)

```bash
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"
export HB_ASSISTANT_DB_PATH="${HB_ASSISTANT_DB_PATH:-$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite}"
python docs/evidence/project-schedule-hub/schedule-review-dashboard-portfolio-rollup-phase18-20260701T202019Z/capture_phase18_live_smoke.py
```

- Resolves DB from `HB_ASSISTANT_DB_PATH` or `PathPolicy().get_db_path()`
- **GET-only**: script fails on any non-GET HTTP attempt
- Before/after proof: DB + WAL/SHM file metadata (size, mtime) and watch-table row counts (not size alone)
- Live API on port 8002; Vite on 5174 (`frontend/vite.phase18-live.config.ts`)
- Browser screenshot asserts DOM “Total projects” matches `portfolio_summary.project_count` in `18-live-dashboard-api.json`
- PM-safe exports; `find_redaction_leaks` + `validate_rendered_text` on all live artifacts → `24-live-redaction-proof.txt`

**Do not commit:** `fixture-phase18-portfolio.db`, `node_modules/`, transient logs, or other local capture byproducts (see `.gitignore`).
