# Validation Matrix — Procore Expansion (Prompt 06)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall procore_monitor.py procore.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_procore_monitor.py` | pass | 4 passed | ✅ |
| Targeted tests | `pytest -k "procore or source_refresh or procore_digest or endpoint or freshness"` | pass (modulo pre-existing) | 1115 passed, 2 pre-existing fails | ✅ |
| Lint (changed module) | `ruff check procore_monitor.py` | pass | All checks passed | ✅ |
| Types | `mypy procore_monitor.py` | pass | no issues | ✅ |
| Monitoring read-model | report on seeded temp DB | verdicts honest | partial_stale / stale / no_data | ✅ |
| Source-refresh status | per-project verdicts | reflect seeded freshness | `03` | ✅ |
| Endpoint contract | registry counts | 59 total / 56 verified / 3 degraded | `04` | ✅ |
| Sync persistence | reads canonical procore_live_* | seeded watermark → current | `05` | ✅ |
| Daily-brief consumption | digest + monitor verdict | complementary, no dup | `06` | ✅ |
| Degraded endpoint | unverified + no_data honesty | reported explicitly | `07` | ✅ |
| No writeback | row counts before/after | unchanged | `08` (read_only=true) | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

## Pre-existing failures / lint (not this candidate)

- `tests/test_fastapi_analytics_source_refresh_surfaces.py::test_live_refresh_fails_closed` and
  `tests/test_launcher_scheduler.py::test_production_default_no_hb_procore_live` fail in this
  environment; confirmed pre-existing (fail with this candidate's `procore.py` change stashed). Those
  subsystems were not touched.
- `ruff check src/hb_assistant/cli/procore.py` reports 3 pre-existing B008 (lines 696/1088/1889) in
  code not added by this candidate; every option added by the `monitor` verb carries `# noqa: B008`.
  Recorded, not fixed (global validation policy).

All monitoring/digest ran on a disposable temp DB; production read once, never written; no live HTTP call.
