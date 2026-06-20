# Forecast UI — Phase 1 Readiness Evidence

Product Phase A exit gate for the forecasting UI product (plan: `radiant-pebble`).
Read-only capture proving the repo/DB claims Implementation Phase 1 rests on. **No live-DB writes were performed** (all DB reads via `?mode=ro`).

Stamp: `20260620T105106Z` (UTC).

| File | Proves (plan claim) |
|---|---|
| `git_state.txt` | Working tree is on `main`, clean except the 6 untracked `docs/evidence/` dirs (plan §2). |
| `db_schema_version.txt` | Live DB schema version = **60** (plan §3). |
| `forecast_table_rowcounts.txt` | v58 foundation tables empty (0); v59 source-domain = 127 / 6324 / 1081; v60 config registry = 6 / 194 / 1 / 194 (plan §3). |
| `missing_ui_tables.txt` | The 14 UI-support tables are **absent** in the live DB (plan §3, §10). |
| `cfr_test_posture.txt` | CFR suite 565 passed; repo-root phase16–20/lifecycle green per-file; combined-`-k` failure is a pre-existing test-isolation artifact (see isolation note). Backend is green on `main` before building (plan §17, §18 stop condition). |
| `package_output_location.txt` | Generators write `<name>_<key>_<stamp>/` under `out_root or data_root` — the roots the catalog scans (plan §2, §9). |
| `frontend_copycheck_present.txt` | `scripts/proofs/frontend_display_copy_check.py` exists — the copy-redaction proof is real (plan correction #3). |

## Interpretation
- The deterministic backend, source-domain projection, and config registry are all live and populated as the plan describes.
- No table or capability that the plan calls "missing" actually exists yet (re-verified, per stop condition).
- The backend is green; Implementation Phase 1 (read-only package browser) may proceed.

This is an **evidence bundle**, not a lifecycle-classified package.
