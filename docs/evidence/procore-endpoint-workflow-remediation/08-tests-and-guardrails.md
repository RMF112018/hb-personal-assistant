# 08 — Tests & Guardrails

Prompt: `08_TESTS_AND_GUARDRAILS.md`.

## New / updated tests

### `tests/test_procore_daily_refresh_plan.py` (new — pure unit, no I/O)
- **Plan structure**: legacy→canonical alias mapping (`list-projects`→`projects`, `list-invoices`→`subcontractor-invoices`, …); only `projects` is company-level; daily-log family is date-windowed and present; `list-drawings` is unsupported (not in plan); bounded `daily_log_window`.
- **Status taxonomy**: HTTP **400**→`contract_bug_missing_required_param`, **403**→`skipped_permission_limited`, **404**→`skipped_tool_not_enabled`, **429**→`transport_rate_limited`, **5xx**→`transport_error_retryable`, no-status→`transport_error_non_retryable`; `success`/`partial_success`(+projection_error); `gate_blocked`→auth/mapping; `not_live_verified`→`skipped_not_live_eligible`; `normalizer_missing`.
- **Degradation semantics**: contract/transport/projection are degradation; `skipped_*`/`success` are not.

### `tests/test_sources_refresh.py` (updated for canonical routing)
- Dry-run performs **no** live read (`run_live_sync` never called) and reports `status="planned"`, `persistence_path="procore_live"`.
- Auth-not-ready → no live read.
- Apply+live: `inserted == 5 × calls`, company-level `projects` called **once**, daily-log calls carry bounded `start_date`/`end_date`.
- **Contract-bug endpoint (400) degrades the run** → exit 1, `contract_bug_failures ≥ 1`, Procore `next_operator_action` mentions "contract regression".
- **`list-drawings` classified `skipped_tool_not_enabled`** and does **not** degrade the Procore stage.
- Apply receipt carries `tables_written = procore_live_*` and contains **no** token-shaped values (`FORBIDDEN_RAW` scan).

### `tests/test_construction_manifests.py` (updated)
- Project-card Procore totals now seed + read the canonical `procore_live_records` / `procore_live_sync_watermarks` (full V6 rows, `raw_body_persisted=0`).

### Existing coverage relied upon
- `tests/test_scheduler_degraded_surfacing.py` — manual degraded → exit **2**; token-shaped values scrubbed from the receipt; honest status.
- `tests/test_procore_live_apply_fix.py`, `tests/test_procore_live_sync_*`, `tests/test_procore_repositories_v6.py` — canonical write path, GET-only, idempotency, `raw_body_persisted=0`, fail-closed.

## Guardrails verified

- **GET-only / no Procore writeback**: the daily refresh calls `run_live_sync`, which uses the GET-only `ProcoreHTTPClient` (`_require_get`); `procore live no-writeback-proof` remains green (Phase G).
- **No M365 writeback**: unchanged; orchestrator `_GUARDRAILS_BASE` asserts `no_m365_writeback`.
- **`raw_body_persisted=0`**: enforced by the canonical repository + V6 CHECK constraint; manifests-test seed honors it.
- **No token/payload/signed-URL leakage**: orchestrator endpoint rows carry only status/counts; `_REDACT_TOKENS` write-fence + scheduler receipt redactor; `FORBIDDEN_RAW` scan in tests.
- **`HB_PROCORE_LIVE` scoped to the run**: armed only inside `_maybe_live_env` in `scheduler/daily_source_refresh.py` (unchanged).
- **Local config/DB uncommitted**: `config/config.yml`, `*.sqlite` never staged (verified each commit).

## Validation results

| Check | Result |
| --- | --- |
| `python -m compileall src tests` | **OK** |
| `ruff check` (changed src/test files) | **clean** (0 new errors) |
| `ruff format --check` (changed files) | **clean** |
| `mypy src` (changed modules: orchestrator, daily_refresh_plan, manifests/service) | **clean** |
| `pytest tests -k "procore and (endpoint or sync or live or source_refresh or scheduler)"` (deselecting the one env-config test below) | **exit 0 — all passed** |
| `pytest tests -k "no_writeback or secret or redaction or guardrail"` | **exit 0 — all passed** |
| `pytest tests/test_scheduler_degraded_surfacing.py tests/test_procore_live_apply_fix.py` | **passed** |
| `pytest tests/test_procore_daily_refresh_plan.py tests/test_sources_refresh.py` | **43 passed** |
| live-sync suite (`-k "procore_live_sync or procore_repositories or procore_live_apply"`) | **92 passed** |

## Pre-existing / environmental failures (NOT introduced by this work)

All verified to fail identically on clean `main` (changes stashed) and/or to be
driven purely by the local, gitignored `config/config.yml`:

- **8 tests** (`tests/test_launcher_scheduler.py` production-default + snapshot/run-date tests; `tests/test_fastapi_analytics_source_refresh_surfaces.py::test_live_refresh_fails_closed`) fail **only** because the local `config/config.yml` sets `enable_procore_live_reads: true`; these tests resolve the production profile without the `isolated_hb_pa_config` fixture. With the shipped default (live reads off) all 8 pass (verified by temporarily flipping the flag). They pass in CI.
- **3 ruff `B008`** in `cli/procore.py` (pre-existing `typer.Option(Path …)` defaults at lines ~696/1088/1831) + **≥1** in `mcp/wrappers.py`: identical count with my `procore.py` change stashed → my additions introduce **0** new ruff errors.
- **`ruff format --check .`**: ~71 pre-existing unformatted files repo-wide (untouched by this work). All files I changed are format-clean.
- **2 mypy errors** in `construction/second_brain/review_burden_mart.py` (not touched by this work).
