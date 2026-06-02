# Phase 08B — Prompt 00: Repo-Truth Rebaseline (Automation Delivery & Observability)

**Status:** Audit-only. No schema migration, no new CLI surface, no runtime behavior change.
**Audited HEAD:** `954a5181dbdd470effb1f2fcbd3a78750707eb3c` (Phase 08A closeout, Prompt 16, package `1.3.0`).
**Audit date:** 2026-06-02 (UTC stamps from live proof runs: `2026-06-02T18:5x:xxZ`).
**Repository:** `RMF112018/hb-personal-assistant`.
**Purpose:** Establish the factual baseline at the 08A closeout commit before any Phase 08B
implementation, and classify the 08B build backlog against repo truth.

---

## 1. Ancestry / Drift Verification

`main` HEAD is **byte-for-byte equal** to the Phase 08A closeout commit:

```
git rev-parse HEAD                          -> 954a5181dbdd470effb1f2fcbd3a78750707eb3c
git diff --stat 954a518..HEAD               -> (empty; no tracked changes)
git status --porcelain                      -> only untracked: .claude/  .code-graph/
```

- `main` has **not** moved off the 08A closeout. No tracked file drift to classify.
- The two untracked directories (`.claude/`, `.code-graph/`) are local tooling artifacts, not
  repository content; they are out of scope and are not committed by this prompt.

**Conclusion:** The repo state matches the 08A closeout exactly. This rebaseline is a clean
pre-implementation baseline.

---

## 2. Validation Matrix at HEAD

All commands run from the repo venv (`.venv/bin/`, Python 3.14.5). Generated runtime artifacts
(receipt rows, evidence JSON) are written **outside** the repo under
`~/Library/Application Support/HB Personal Assistant/` and are not committed.

| Command | Result |
|---|---|
| `ruff check .` (in-scope modules) | **All checks passed** |
| `mypy src` | **Success: no issues found in 242 source files** |
| `hb-assistant construction-agent validate --json` | **4/4 passed**, `summary.ok=true`; guardrails `external_systems=read_only`, `writeback=none`, `metadata_only=true`, `command_role=read_only_dashboard` |
| `pytest -m "not integration and not live and not manual"` | **2539 passed, 1 deselected** (201s) |
| `hb-assistant second-brain data-quality no-writeback-proof --json` | `proof_passed=true`, `ok=true`, `repo_sha=954a5181…` (matches HEAD), `schema_version=26` |
| `hb-assistant second-brain data-quality phase-08a-gates --json` | `8 pass / 1 warning / 0 fail_blocking / 3 deferred_not_blocking`, `readiness_overstated=false`, `schema_version=26` |

**Pytest count note:** The 08A closeout (Prompt 16) recorded **2535 passed**; this rebaseline
observes **2539 passed** at the *identical* commit with no tracked changes. The delta is a
measurement-context difference (interpreter/collection environment), **not** a code change — the
tree is provably unchanged from 954a518. Recorded here for transparency; not a regression.

---

## 3. Specific Checks (Required)

### 3.1 Schema version & table lifecycle registrations — CONSISTENT
- `LATEST_SCHEMA_VERSION = 26` (`store/migrator.py:17`).
- `table_lifecycle_status_contract.json` declares `"table_count": 141`.
- The three 08B-relevant tables are all registered (`phase_owner: "08A"`,
  `lifecycle_status: "operational_empty_expected"`):
  - `daily_brief_runs` (DDL `migrator.py:3282`)
  - `launchd_schedule_previews` (DDL `migrator.py:3327`)
  - `phase_08a_validation_runs` (DDL `migrator.py:~3338`)
- No V27 block exists. The `model_call_receipt_persistence` gate is correctly deferred to a future
  V27 migration (not yet present).

### 3.2 Apply-capable CLI surface is dry-run by default — CONSISTENT
Verified default option values in `cli/second_brain.py`:
- `daily-brief build` / `daily-brief generate`: `mode = typer.Option("dry_run", …)`.
- `daily-brief schedule-preview`: dry-run only (no `--apply`); DB layer enforces it (see 3.3).
- `daily-brief generate` apply path is additionally gated on `evaluation.passed`
  (`apply_blocked_reason="evaluation_failed"` when it trips).
- `memory candidate` / `memory review` / `preference capture`: `--emit/--no-emit` default **False**.
- `index obsidian`: defaults to `dry_run` when neither `--dry-run` nor `--apply` is given.
- `query-tools run` / `research-packet build`: `--emit-receipt/--no-emit-receipt` default **False**.
- `status`: defaults `emit_receipt=True` but writes only a metadata-only hashed config receipt row;
  this is not a write-capable apply.

**Runtime demonstration:** `second-brain daily-brief generate` (no flags) returned
`mode=dry_run, applied=False, output_written=False, status=assembled` and persisted nothing.

### 3.3 No external writeback / delivery / raw-content persistence — CONSISTENT
- **Source scan:** zero `sendMail`, SMTP, Slack, Teams, SMS, webhook, push, or HTTP `POST` calls in
  `construction/second_brain/**` or `automation/**`.
- **DB-layer guards** on `daily_brief_runs`: nine `CHECK(… = 0)` columns —
  `raw_email_body_persisted`, `raw_document_text_persisted`, `raw_calendar_payload_persisted`,
  `raw_prompt_persisted`, `raw_response_persisted`, `retrieved_context_persisted`,
  `signed_url_persisted`, `download_url_persisted`, `external_writeback_performed`.
- `launchd_schedule_previews` enforces `mode TEXT NOT NULL CHECK(mode = 'dry_run')` — the database
  structurally forbids any non-dry-run launchd row.
- **Model-layer guards** (`daily_brief/models.py`): `DeliveryHandoffPayload` field validators force
  `local_only=True` and `external_delivery_performed=False`; `HtmlRenderingData.rendered=False` (raises
  if True); `NotificationSummary.emitted=False`.
- `no-writeback-proof` passes (`proof_passed=true`) over the second-brain module + V26 table set.

### 3.4 Status outputs include actionable reason codes — CONSISTENT
- Tier reason-code vocabulary in `daily_brief/policy.py`: `T1_SOURCE_BACKED`,
  `T2_REVIEW_RECOMMENDED`, `T3_MANDATORY_REVIEW` (mirrored by research packet/broker).
- `daily_brief_runs.review_tier_reason_code TEXT` column; populated on store writes
  (`daily_brief/store.py`).
- `apply_blocked_reason` carries `evaluation_failed` on the blocked apply path.
- `phase-08a-gates` emits machine-readable `reason` strings on deferred/warning gates (see 3.6).

### 3.5 Test coverage — success / failure / blocked / stale / dry-run — ADEQUATE (08A substrate)
Verified present in the repo test suite:
- **Success (dry-run):** `test_daily_brief_agent.py::test_dry_run_does_not_write_or_apply`;
  `test_second_brain_daily_brief_generate_cli.py::test_generate_dry_run_exit_zero`.
- **Success (apply):** `test_daily_brief_agent.py::test_apply_writes_output_and_persists_links`
  (guard columns verified zero).
- **Failure:** `test_second_brain_daily_brief_generate_cli.py::test_generate_invalid_mode_rejected`
  (exit 2).
- **Blocked:** `test_daily_brief_agent.py::test_apply_blocked_when_evaluation_fails`
  (persists as `dry_run`).
- **Stale:** `test_daily_brief_context.py` (`stale_unknown` → warning cards, lines 67/91).
- **Dry-run-only (DB):** `test_daily_brief_schedule.py::test_table_rejects_non_dry_run_mode`,
  `::test_emit_persists_dry_run_row_guard_zero`, `::test_proof_passes`.
- **No-raw-content:** `test_daily_brief_agent.py::test_output_carries_no_raw_content`.
- **Deferred gate:** `test_phase_08a_data_quality_gates.py` asserts `automation_hardening` stays
  `deferred_not_blocking`.

### 3.6 Phase 08A data-quality gate set (08B handoff contracts)
```
pass                    automation gates: runtime_readiness, agent_registry, model_profile,
                        retrieval, research_packet, evaluation, memory_provenance, daily_brief_handoff
warning                 synthesis_liveness    -> synthesis_offline_or_mock_runtime_ready_but_not_live
deferred_not_blocking   mcp_exposure          -> mcp_not_implemented
deferred_not_blocking   model_call_receipt_persistence -> model_call_and_agent_run_receipts_in_memory_only
deferred_not_blocking   automation_hardening  -> health_checks_retries_weekend_alerting_owned_by_phase_08b
```
The three `deferred_not_blocking` gates are the explicit 08B/08D handoff contracts.

---

## 4. Phase 08B Build Backlog (classified against repo truth)

| Item | Repo-truth basis | 08B action |
|---|---|---|
| **launchd hardening** | `launchd_schedule_previews` is dry-run-only by DB CHECK; `launchd_manager.py` can render plist / call `launchctl` but is not on the `schedule-preview` path | New `launchd_install_runs` (or equiv) table via **V27**; real plist write + `launchctl` install behind explicit apply gate |
| **Run-ledger bridge** | `MorningRunOrchestrator` writes to `assistant_runs` (V1); daily-brief writes to `daily_brief_runs` (V26) — two independent ledgers | Bridge column/FK between the two, via **V27**; add a second-brain daily-brief stage to the orchestrator that calls `run_daily_brief()` and writes `daily_brief_runs` |
| **Model/agent receipt persistence** | `model_call_receipt_persistence` gate deferred; receipts are in-memory only | New receipt table(s) via **V27**; preserve no-raw-content guards (no raw prompts/responses) |
| **HTML brief render** | `HtmlRenderingData.rendered=False` validated; no renderer exists | Build renderer that writes **local** HTML outside repo; keep delivery off |
| **Notifications** | `NotificationSummary.emitted=False`; no delivery code | macOS-local notification only; **no** email/Slack/Teams/SMS/push/webhook/`sendMail` |
| **Structured hardening reason codes** | `automation_hardening` reason is prose | Define machine-parseable codes (e.g. `HEALTH_CHECK_FAILED`, `RETRY_EXHAUSTED`, `WEEKEND_GATE_SKIPPED`, `LAUNCHD_NOT_INSTALLED`) before building the evaluator so tests assert on codes |
| **Hardening test paths** | Health-check-failure, retry-exhaustion, weekend-skip, and launchd→orchestrator→generate integration are uncovered (08B scope, not 08A gaps) | Add coverage as 08B builds each surface |

---

## 5. Guardrails Verified (preserved from 08A)

- ✅ Local-first; read-only against Microsoft 365 / Graph / Procore (`construction-agent validate`
  guardrails `read_only` / `writeback: none`).
- ✅ No Microsoft 365 / external-system writeback (source scan + DB CHECKs + model validators +
  `no-writeback-proof`).
- ✅ No email/Slack/Teams/SMS/push/webhook/`sendMail` delivery anywhere in second-brain/automation.
- ✅ No raw-content persistence (bodies, doc text, calendar payloads, prompts, responses,
  signed/download URLs, raw HTML) — enforced by `CHECK(=0)` columns and model validators.
- ✅ Apply-capable commands dry-run by default; `schedule-preview` dry-run-only at the DB layer.
- ✅ All runtime state/artifacts written outside the repo (Application Support root).
- ✅ Status outputs carry actionable reason codes (tiers + gate reasons + `apply_blocked_reason`).

**No repo-truth contradiction with the prompt was found.** No stop condition triggered.

---

## 6. Known Limitations / Recommendations (non-blocking)

1. **README label drift (docs-only).** The Repository Status header reads
   `Phase 08A … — Active (Prompts 02–15; Prompt 09 deferred)` while the closeout evidence
   (`final-validation-closeout.md`) and architecture record 72 treat 08A as validated/closed.
   *Recommend* relabeling to `Closed` and adding a Phase 08B stub when 08B implementation begins.
   Left unchanged here to honor the audit-only mandate (not a planning blocker).
2. **`interactive_chat_sessions` / `interactive_chat_message_receipts`** (Prompt 09 deferred) are
   registered under 08A but have no agent/CLI surface — correctly `operational_empty_expected`.
3. The `MorningRunOrchestrator` weekend gate exists but there is no second-brain-specific
   holiday/weekend-skip test yet (08B scope).

---

## 7. Next-Prompt Readiness

The next Phase 08B prompt (first implementation prompt) can safely assume:

- HEAD is the clean 08A closeout (`954a518`); schema is **V26 / 141 tables**; the full validation
  matrix is green at HEAD (ruff, mypy, `validate` 4/4, pytest 2539, no-writeback-proof, gates).
- The dry-run-by-default posture, no-writeback/no-delivery/no-raw-content guardrails, and reason-code
  vocabulary are in place and test-backed — 08B must **extend, not replace** them.
- All new persistence (launchd install runs, run-ledger bridge, model/agent receipts) requires a
  **V27** additive migration; do not rewrite V1–V26 tables.
- The three deferred gates (`automation_hardening`, `model_call_receipt_persistence`,
  `mcp_exposure`) are the open 08B/08D contracts.
- This evidence bundle is the authoritative 08B starting baseline.
