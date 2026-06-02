# Phase 08B — Prompt 03: Automation Health Agent + status surface

**Status:** Implemented (additive). Schema **V28 reused** (no migration); package stays `1.3.0`.
**Baseline:** atop `d45e0de` (08B Prompt 02; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-02.
**Scope:** a deterministic, offline, read-only Automation Health Agent that runs the seeded health
checks + a `second-brain automation health` status surface, with an emit-gated metadata-only V28
agent-run receipt and a new `automation_health` gate. No external delivery; no alert emitted.

---

## 1. Files Changed

Source:
- `src/hb_assistant/construction/second_brain/automation_health.py` (new) — `HealthCheckResult` +
  `AutomationHealthStatus` models, `evaluate_automation_health`, `run_automation_health`
  (emit-gated receipt), `build_automation_health_proof`.
- `src/hb_assistant/construction/second_brain/data_quality.py` — `automation_health` added to
  `PHASE_08B_GATE_NAMES` + evaluated as a `_proof_gate`.
- `src/hb_assistant/resources/json/phase_08b_data_quality_gates.json` — `automation_health` added to
  `required_fields`.
- `src/hb_assistant/cli/second_brain.py` — new `automation` sub-app + read-only `health` command.
- `src/hb_assistant/construction/second_brain/daily_brief/store.py` — reconstruct determinism fix
  (`read_daily_brief_handoff` source-refs `ORDER BY rowid`).

Tests (new): `test_automation_health_agent.py`, `test_second_brain_automation_health_cli.py`.
Tests (updated): `test_phase_08b_data_quality_gates.py` (+`automation_health` pass assertion).

Docs: `docs/architecture/75-phase-08b-automation-health-agent.md` (new).

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **245** source files |
| targeted suite (health agent + CLI + 08b gates + contracts/seed + no-writeback proof + agent receipts + 08a gates) | **42 passed** |
| `pytest -m "not integration and not live and not manual"` | **2585 passed, 1 deselected** (baseline 2575; +10 new) |
| `construction-agent validate --json` | **4/4**, `ok=true` |
| `second-brain data-quality no-writeback-proof --json` | `proof_passed=true`, schema 28 |
| `second-brain data-quality phase-08a-gates --json` | **unchanged**: 8 pass / 1 warning / 0 fail_blocking / 3 deferred |
| `second-brain data-quality phase-08b-gates --json` | 6 pass / 0 warning / 0 fail_blocking / 2 deferred; `automation_health=pass`; `ok=true` |
| `second-brain automation health --json` | read-only status surface; `RUN_OK` on a healthy runtime; degraded → exit 3 with reason codes |

---

## 3. Specific Checks

- **Schema + lifecycle:** unchanged at V28 / 144 tables (the agent reuses the V28 receipt table; no
  new table, no migration).
- **Dry-run default:** health evaluation is read-only (never migrates/writes); the receipt is
  `--emit-receipt`-gated (off by default; proven by `test_dry_run_default_writes_no_receipt` +
  `test_health_healthy_exit_zero` showing `agent_run_id=None`).
- **No writeback / delivery / raw content:** the agent records health locally and never sends an
  alert; the emit-gated receipt is metadata-only (guard columns zero; no-raw scan); detail strings
  are validator-checked for forbidden tokens; the no-writeback proof still passes.
- **Actionable reason codes:** per-check `HEALTH_CHECK_FAILED`; overall `RUN_OK` / `RUN_DEGRADED`
  (from the seed vocabulary); the CLI payload + receipt + status model all carry them.
- **Coverage of success/failure/blocked/stale/dry-run:** success (migrated DB → `RUN_OK`),
  failure/blocked (unmigrated DB → `RUN_DEGRADED` + `HEALTH_CHECK_FAILED`), stale (absent durable
  handoff table → `table_absent` detail), dry-run (no-emit → no receipt), plus the emit path.

---

## 4. Guardrails Verified

Local-first; read-only health evaluation; no external writeback or delivery
(email/Slack/Teams/SMS/push/webhook/`sendMail` — none); no alert emitted (alerting policy is
local-only, emit false); receipts metadata-only + guard-checked + no raw content; receipt
persistence emit-gated/dry-run default; `automation health` CLI read-only; runtime artifacts outside
the repo; no schema change. **No repo-truth contradiction; no stop condition triggered.**

---

## 5. Known Limitations

1. The agent runs the four seeded health checks; retry/backoff, weekend gating, and real launchd
   install **execution** remain deferred — the `automation_execution` and `launchd_install` 08B
   gates stay `deferred_not_blocking`.
2. `path_readiness` for an explicit db_path uses an inline parent-writable + sqlite-openable probe
   (the full `ensure_db_ready` report targets the default app-support path).
3. A latent non-determinism in the Prompt-01 `read_daily_brief_handoff` (source-refs ordered by a
   random uuid) was surfaced by the full-suite run and fixed here (`ORDER BY rowid`); unrelated to
   the agent but carried in to keep the suite green.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- Schema **V28 / 144 tables**; full matrix green (ruff, mypy 245, validate 4/4, pytest 2585,
  no-writeback-proof, 08A gates unchanged, 08B gates ok with `automation_health=pass`).
- A read-only Automation Health Agent (`evaluate_automation_health` / `run_automation_health`) + the
  `second-brain automation health` status surface + emit-gated V28 receipt exist and are gate-backed.
- The remaining **automation execution** work — retry/backoff orchestration, weekend gating using
  the seeded policy, the run-ledger bridge (`assistant_runs` ↔ second-brain receipts), and real
  launchd install (dry-run-default) — is the next build and should flip the two deferred 08B gates
  as it lands. Further persistence stays additive (V29+).
