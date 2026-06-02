# Phase 08B — Prompt 10: Local HTML Brief Renderer

**Status:** Implemented (additive). Schema **V31 → V32** (one new table); package stays `1.3.0`.
**Baseline:** atop `cea914b` (08B Prompt 09; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** A dry-run-by-default renderer producing a polished, fully self-contained interactive HTML
daily brief outside the repo, a V32 render-receipt ledger, and a proof-backed `daily_brief_html_render`
gate. `automation_execution` stays the only deferred 08B gate.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/daily_brief_html.py` (new) —
  `render_daily_brief_html` (self-contained interactive page), `_scan_html_for_external_assets`
  (fail-closed), `evaluate_daily_brief_html_render`, `run_daily_brief_html_render_agent` (apply writes
  the `.html` + V32 receipt; emit-gated V28 receipt), `write_daily_brief_html_render_receipt`,
  `build_daily_brief_html_render_proof`.
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 31 → 32`; V32
  `daily_brief_html_render_receipts` (+ index) with `CHECK(no_external_assets = 1)`, `mode` CHECK,
  `daily_brief_runs` FK, 9 no-raw/no-writeback guard columns.
- `src/hb_assistant/construction/second_brain/safety.py` — `daily_brief_html_render_receipts` added
  to `_PHASE_08A_TABLES`.
- `src/hb_assistant/config/path_policy.py` — lazy `get_html_dir()` → `<app_support>/html`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `daily_brief_html_render` proof-gate
  + `PHASE_08B_GATE_NAMES`.
- `src/hb_assistant/cli/second_brain.py` — `automation html-status` (read-only) + `render-html`
  (apply-capable, dry-run default) commands.
- `resources/config/phase_08b_automation_policy.seed.yaml` — `daily_brief_html_render` section +
  reason codes.
- `src/hb_assistant/resources/json/{phase_08b_automation_policy_contract.json,
  phase_08b_data_quality_gates.json}` — new reason codes; `required_fields` + `daily_brief_html_render`.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 148 → 149` +
  `daily_brief_html_render_receipts` entry (`v: V32`).

Tests (new): `tests/test_phase_08b_schema_v32.py`, `tests/test_daily_brief_html_render_agent.py`,
`tests/test_second_brain_html_render_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (html gate pass),
`test_phase_08b_contracts_and_seed.py` (new reason-code membership in seed + both contracts);
`contract_table_count` 148 → 149 in seven files
(`test_data_quality_table_inventory.py`, `test_phase_08a_schema_v26.py`,
`test_phase_07d_data_quality_gates.py`, `test_phase_08b_schema_v28.py`,
`test_phase_08b_schema_v29.py`, `test_phase_08b_schema_v30.py`, `test_phase_08b_schema_v31.py`).

Docs: `docs/architecture/82-phase-08b-local-html-brief-renderer.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **252** source files |
| targeted suite (schema V32 + html render agent + CLI + gates + contracts + count bumps) | all passed |
| `pytest -m "not integration and not live and not manual"` | **2727 passed, 0 failed, 0 errors** (junit `tests=2727 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=32) |
| `second-brain data-quality no-writeback-proof --json` | proof_passed=true, schema 32 (V32 table covered) |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | **13 pass / 0 warning / 0 fail / 1 deferred**, `daily_brief_html_render=pass`, `automation_execution=deferred_not_blocking`, `required_fields_covered=true` |
| `second-brain automation html-status --json` | reason_code HTML_RENDER_NEVER_GENERATED (fresh DB), read-only |
| `second-brain automation render-html --mode dry_run --json` | render_status=preview, written=false (writes nothing) |

---

## 3. Specific Checks

- **Schema + lifecycle:** schema **V32**; new `daily_brief_html_render_receipts` ships empty,
  classified `operational_empty_expected` at `table_count` **149**; FK to `daily_brief_runs`; added to
  `safety._PHASE_08A_TABLES`.
- **Dry-run default:** `render-html` defaults to `--mode dry_run` (writes nothing); `html-status` is
  read-only.
- **No external writeback / delivery / raw-content / raw-HTML:** the page is inline-only — the
  fail-closed `_scan_html_for_external_assets` proves no `http(s)`/`//`/`<link>`/`<script src>`/`url(//`/
  `fetch(`/`XMLHttpRequest`/`WebSocket` etc. (tested both on the rendered page and on synthetic
  network refs). The V32 receipt stores only redacted path + content/path hashes + reason code (9 guard
  `CHECK(col = 0)` columns + `CHECK(no_external_assets = 1)`); raw HTML is never persisted in SQLite;
  the page renders from the structured, escaped handoff, never a model response.
- **Actionable reason codes:** `HTML_RENDER_NEVER_GENERATED`, `HTML_RENDER_BLOCKED`,
  `HTML_RENDER_STALE`, `HTML_RENDER_ELIGIBLE`, `HTML_RENDER_COMPLETED`, `HTML_RENDER_ALREADY_RENDERED`,
  `HTML_RENDER_EXTERNAL_ASSET_BLOCKED` (fail-closed).
- **Coverage of success / failure / blocked / stale / dry-run:** completed render (success);
  never-generated (failure-to-render); blocked run refused (blocked); brief older than threshold
  (stale); dry-run preview writes nothing (dry-run); plus the idempotent already-rendered no-op and the
  required interactive UI components (filters, collapsible, evidence drawer, warning banner, meeting
  timeline, review panel, print CSS).

---

## 4. Guardrails Verified

- Fully self-contained HTML — inline CSS/JS, zero external assets / network calls (fail-closed scan;
  the agent refuses to write + emits `HTML_RENDER_EXTERNAL_ASSET_BLOCKED` on any hit, and the V32 row
  cannot persist with `no_external_assets = 0`).
- No raw HTML in SQLite; no raw email/document/calendar/prompt/response/URL content persisted; guard
  columns enforced at the DB layer (nonzero insert raises `IntegrityError`).
- Generated `.html` written outside the repo and vault (`<app_support>/html/`); dry-run writes
  nothing; the V28 agent receipt is emit-gated (off by default).
- No external writeback/delivery. Phase 08A guardrails preserved: phase-08a-gates unchanged (8/1/0/3);
  no-writeback proof passes at schema 32 and now covers `daily_brief_html_render_receipts`.
- Tests inject a temp app-support DB + temp html dir + fixed `now`; deterministic; the real
  app-support html dir is never written by the suite.

---

## 5. Known Limitations

1. `automation_execution` stays `deferred_not_blocking` — the final executor + morning-orchestrator
   wiring is unbuilt (the renderer is ready to be wired as an optional render step).
2. The project filter derives projects from `project_signals` titles (handoff lines carry no explicit
   project key); cross-project items bucket to "General". Tier filtering is exact.
3. Apply persists the V32 render receipt unconditionally (the render ledger); the V28 audit receipt is
   emit-gated. Idempotency keys on a prior `rendered` receipt for the brief run/date.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V32 / 149 tables**; full matrix green (ruff, mypy 252, validate 4/4, pytest 2727 passed /
  0 fail, no-writeback proof at schema 32, phase-08a-gates 8/1/0/3, phase-08b-gates 13/0/0/1).
- A dry-run-default, idempotent, **fully self-contained Local HTML Brief Renderer** (V32
  `daily_brief_html_render_receipts`, output to `<app_support>/html/`, fail-closed external-asset scan,
  emit-gated V28 receipt) with a passing `daily_brief_html_render` gate — ready to be wired as an
  optional render step in the morning orchestrator.
- The remaining build target is the **full automation executor** consuming the 08B observability +
  substrate + delivery + render surfaces — flipping the last `deferred_not_blocking` gate.
