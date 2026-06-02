# Phase 08B — Prompt 01: Durable Handoff Recovery + Render-View Contract

**Status:** Implemented (additive). Schema **V26 → V27**; package stays `1.3.0` (repo convention:
the V25 and V26 schema migrations both shipped under `1.3.0` without a bump — followed here).
**Baseline:** built atop Prompt 00 rebaseline `1c1cd37` (08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** resolves the two verified 08A preflight gaps from `00-repo-truth-rebaseline.md`:
durable delivery-handoff recovery and a render-ready handoff contract. No external delivery, no
HTML rendering, no raw-content persistence.

---

## 1. Gap Targets — Outcome

### Gap A — durable handoff recovery: RESOLVED
Before: the structured handoff sections were built in memory only and lost on process exit
(`daily_brief_runs` stored counts; the only reader returned counts). Now a V27
`daily_brief_handoff_lines` table durably persists each handoff line (section, order, redacted
title, review tier, safe source-ref pairs) on `--emit-receipt`, and
`read_daily_brief_handoff(brief_run_id)` reconstructs the full `DeliveryHandoffPayload` from
persisted rows after a fresh connection. **Round-trip proven:** reconstructed `.sections` equal the
in-memory handoff sections exactly (`test_durable_roundtrip_after_fresh_connection`).

### Gap B — render-ready contract: RESOLVED
Added `DailyBriefRenderView` + the pure, deterministic `build_daily_brief_render_view(handoff)`
builder and a read-only `daily-brief render-view` CLI command. The view carries ordered sections
(canonical `HANDOFF_SECTIONS`), per-line redacted title / tier / safe refs, and aggregate counts —
the stable contract a future HTML renderer consumes. `rendered=False` is validator-enforced; no
HTML is produced.

---

## 2. Files Changed

Source:
- `src/hb_assistant/store/migrator.py` — `LATEST_SCHEMA_VERSION 26→27`; `V27_STATEMENTS`
  (`daily_brief_handoff_lines` + index); V27 apply block.
- `src/hb_assistant/resources/json/table_lifecycle_status_contract.json` — `table_count 141→142`;
  `daily_brief_handoff_lines` entry (`phase_owner 08B`, `v V27`, `operational_empty_expected`).
- `src/hb_assistant/construction/second_brain/daily_brief/models.py` — `RenderViewLine`,
  `RenderViewSection`, `DailyBriefRenderView` (`rendered=False` validator).
- `src/hb_assistant/construction/second_brain/daily_brief/store.py` —
  `write_daily_brief_handoff_lines()`, `read_daily_brief_handoff()`.
- `src/hb_assistant/construction/second_brain/daily_brief/generate.py` — persist handoff lines on
  the existing `emit_receipt` path.
- `src/hb_assistant/construction/second_brain/daily_brief/render_view.py` — new builder module.
- `src/hb_assistant/construction/second_brain/daily_brief/__init__.py` — exports.
- `src/hb_assistant/construction/second_brain/safety.py` — add `daily_brief_handoff_lines` to the
  no-writeback guard/leak scan scope (now nineteen tables).
- `src/hb_assistant/cli/second_brain.py` — read-only `daily-brief render-view` command.

Tests:
- `tests/test_daily_brief_handoff_durability.py` (new) — durability + render-view + guard + paths.
- `tests/test_second_brain_daily_brief_render_view_cli.py` (new) — CLI happy path + exit 2/4.
- `tests/test_phase_08a_schema_v26.py` — V26 version pin relaxed to `>= 26` / `== LATEST` (matches
  the 07c/07d forward-compatible pattern); count `141→142`; added `_V27_TABLES` +
  `test_v27_creates_handoff_lines_table_with_guards` + `test_v27_is_idempotent`.
- `tests/test_data_quality_table_inventory.py`, `tests/test_phase_07d_data_quality_gates.py` —
  `contract_table_count 141→142`.

Docs:
- `docs/architecture/73-phase-08b-durable-handoff-recovery-and-render-view-contract.md` (new).

---

## 3. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `ruff format` (touched files) | formatted |
| `mypy src` | Success — no issues in **243** source files |
| targeted suite (durability, render-view CLI, schema V26/V27, table inventory, 07d gates, no-writeback proof, daily-brief agent, generate CLI) | **75 passed** |
| `pytest -m "not integration and not live and not manual"` | **2553 passed, 1 deselected** (was 2539 at baseline; +14 new tests) |
| `second-brain data-quality no-writeback-proof --json` | `proof_passed=true`, schema 27, 52 modules, 19 tables |
| `second-brain data-quality phase-08a-gates --json` | schema 27; **8 pass / 1 warning / 0 fail_blocking / 3 deferred**; `readiness_overstated=false` (unchanged) |
| `construction-agent validate --json` | **4/4** pass, `ok=true` |
| CLI end-to-end (generate `--emit-receipt` → render-view `--date`) | proven by `test_render_view_by_date` (format `render_view`, `rendered=false`, ordered sections, no raw content) |

---

## 4. Specific Checks

- **Schema + lifecycle:** V27; `daily_brief_handoff_lines` registered
  (`operational_empty_expected`, `phase_owner 08B`); migration idempotent; V1–V26 untouched.
- **Dry-run default:** unchanged. Lines persist only on `--emit-receipt`
  (`test_dry_run_persists_no_handoff_lines`); `render-view` is read-only.
- **No writeback / delivery / raw content:** nine `CHECK(=0)` guard columns on the new table
  (`test_handoff_line_guard_columns_zero`); `_reject_forbidden_refs` before serialization;
  no-writeback content-leak scan now covers the table (`proof_passed=true`); no
  email/Slack/Teams/SMS/push/webhook/`sendMail`; `rendered=False` + no HTML.
- **Reason codes:** reconstruction preserves `review_tier` per line and the run-level
  `review_tier_reason_code`/`degradation_mode`; `render-view` carries tier per line.
- **Coverage of success/failure/blocked/stale/dry-run:** success+apply
  (`test_emit_persists_handoff_lines`, round-trip), failure/not-found (CLI exit 2/4), blocked
  (`test_blocked_run_reconstructs_with_empty_sections`), stale
  (`test_no_raw_content_in_persisted_lines_and_render_view` seeds a stale issue), dry-run
  (`test_dry_run_persists_no_handoff_lines`).

---

## 5. Guardrails Verified

Local-first; read-only against external systems (`validate` guardrails); no external writeback or
delivery; no raw-content persistence (DB CHECKs + model validators + leak scan); apply-capable
commands dry-run by default; `render-view` read-only; all runtime artifacts outside the repo
(Application Support root). **No repo-truth contradiction; no stop condition triggered.**

---

## 6. Known Limitations

1. Top-level aggregate `handoff.source_refs` reconstruct to durable `{source_family, source_ref}`
   identity (+ `evidence_trail_id`/`confidence_class` when persisted); `record_type`/`review_tier`
   annotations are not in the V26 `daily_brief_source_refs` schema and are not reconstructed
   (pre-existing V26 limitation). Per-line refs round-trip verbatim; sections round-trip exactly.
2. Notification-summary `attention_count`/`warning_count` are derived from reconstructed section
   membership (the run-level `review_required_count`/`project_count` are exact/durable).
3. HTML rendering and notification delivery remain deferred (`automation_hardening` gate). This
   prompt ships the durable receipt + render contract, not the renderer.

---

## 7. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V27 / 142 tables**; full validation matrix green (ruff, mypy 243, validate 4/4, pytest
  2553, no-writeback-proof, gates unchanged).
- A durable, reconstructable delivery handoff exists (`read_daily_brief_handoff`) and a stable,
  deterministic render-view contract (`build_daily_brief_render_view` / `daily-brief render-view`)
  — an HTML renderer can be built against the view **without** touching internals or persisting raw
  content, flipping `rendered` only when it actually emits HTML.
- The dry-run-default, no-writeback/no-delivery/no-raw-content guardrails and reason-code
  vocabulary are intact and test-backed — extend, not replace.
- Any further persistence (launchd install runs, run-ledger bridge, model/agent receipts) remains
  an additive V28+ migration; the three deferred gates (`automation_hardening`,
  `model_call_receipt_persistence`, `mcp_exposure`) remain the open 08B/08D contracts.
