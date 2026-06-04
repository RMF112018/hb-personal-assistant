# Phase 09 — Prompt 08: Automation Delivery Receipt Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/08-automation-delivery-receipt.md`
**Machine-readable companion:** `08-automation-delivery-receipt.json`
**Captured outputs:** `validation-outputs-prompt-08/`
**Gap:** G-06 (automation records and delivery receipts not populated)
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Controlled, **no-external** automation/delivery receipt population into a **labeled proof DB outside the repo**, plus a reusable guard-clean **proof helper + tests**. The real Obsidian vault / HTML dir / launchd and the **operator DB stay pristine** (0 receipts). **No new schema, no CLI, no LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-06 resolution: run launchd/status + delivery/notification/HTML/open receipt proofs that persist
**metadata-only** receipts **without external delivery or writeback**. The existing Phase 08B agents are
driven in-process against a **fresh V37 proof DB outside the repo** with **temp vault/HTML dirs**,
**policy-off / explicitly-gated** notification, and **injected fake callables** — so no real macOS
notification fires, no real vault/HTML is written, and `launchctl` is never invoked. Every receipt is
metadata-only, protected by the 9 guard `CHECK(=0)` columns and the channel/mode CHECK constraints.

---

## 2. Controlled population (no external delivery → labeled proof DB)

Recipe (in-process; fresh proof DB; temp dirs; fake notifier; `emit_receipt=True`):
`run_daily_brief` (mock adapter, temp vault) → then the 08B agents:

| Agent | Mode | Reason code | Receipt(s) | External? |
|---|---|---|---|---|
| `run_daily_brief_delivery_agent` | apply → temp vault | `DELIVERY_COMPLETED` | `daily_brief_delivery_receipts` ×1 (channel `obsidian_vault`) | none (temp dir) |
| `run_daily_brief_notification_agent` | apply, `policy_emit=True`, **fake notifier** | `NOTIFY_EMITTED` | `daily_brief_notification_receipts` ×1 (channel `local_macos`, title **hash**) | none (no osascript; fake notifier) |
| `run_daily_brief_html_render_agent` | apply → temp html | `HTML_RENDER_COMPLETED` | `daily_brief_html_render_receipts` ×1 | none (temp dir; external-asset scan) |
| `run_brief_open_agent` | apply, fake opener | `OPEN_DISABLED_BY_POLICY` | — (fail-closed; no receipt) | none (policy off) |
| `run_daily_brief_job_health` | read-only | — | agent-run receipt | none |
| `run_launchd_schedule_agent` | dry-run | — | agent-run receipt | none (no plist / launchctl) |

### Persisted counts (proof DB)

| Table | Rows | Guard `CHECK(=0)` cols | Guard sum | Channel/mode |
|---|---|---|---|---|
| `daily_brief_delivery_receipts` | **1** | 9 | **0** | `obsidian_vault` |
| `daily_brief_notification_receipts` | **1** (gated) | 9 | **0** | `local_macos` |
| `daily_brief_html_render_receipts` | **1** | 9 | **0** | — |
| `daily_brief_open_receipts` | 0 (fail-closed) | 9 | 0 | — |
| `second_brain_agent_run_receipts` | **7** | 9 | **0** | — |
| `second_brain_run_registry` | 0 | 9 | 0 | — |
| `launchd_schedule_previews` | 0 | — | 0 | — |
| **total** | **10** | — | **0** | — |

`build_automation_delivery_proof(proof_db)` → **`proof_passed=true`**, `populated=true`,
`guard_violation=false`, `channel_or_mode_violation=false`, `external_writeback_total=0`,
`no_external_delivery=true`, `schema_version=37`. The notification path is the **"explicitly gated"**
case (policy on + a fake notifier that records the emission but performs no real osascript — the title is
stored only as a SHA-256 hash). The **open** path is **fail-closed disabled** (policy off → no receipt, no
external open).

### Operator DB + real surfaces stay pristine

Operator automation/receipt tables **before == after == 0** (verified). The proof DB was a separate file
outside the repo and was **deleted** after measurement; the real vault, HTML dir, and launchd were never
touched (temp dirs / no plist / no launchctl).

---

## 3. Reusable proof helper + tests (the only committed code)

`src/hb_assistant/construction/second_brain/automation_delivery_proof.py` —
`build_automation_delivery_proof(db_path)` is **read-only** (`mode=ro`): per-table receipt counts,
guard-column sums on every receipt table, channel/mode pinning (delivery `obsidian_vault`, notification
`local_macos`, launchd `dry_run`), and the `external_writeback_performed` total (must be 0). Fully typed;
`ruff` + `mypy src` clean (277 files).

`tests/test_phase_09_automation_delivery_proof.py` (4 tests): controlled no-external population →
`proof_passed` (delivery + gated notification + html + agent-run; channels pinned; `notifier_calls == [True]`
for the gated path, never a real osascript); notification **policy-off fail-closed** (`must_not_call`
notifier never invoked → `NOTIFY_DISABLED_BY_POLICY`); empty DB; stale-schema.

---

## 4. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-08/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **277** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3035 + 4 new = **3039 passed**) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a-gates --json` | 0 | `ok=true` |
| `second-brain data-quality phase-08b-gates --json` | 0 | `ok=true`; **16 pass / 0 fail** |
| `second-brain data-quality phase-08c-gates --json` † | 0 | `ok=true` / `proof_passed=true` |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; `ready_to_serve=true` |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |

† Same CLI-spelling resolutions as Prompts 00–06. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical; `phase-08c-gates` (the Prompt-02 append-only ledger) was run once for the
matrix. The operator DB was opened read-only for verification.

---

## 5. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — every guard sum 0 (DB-enforced `CHECK`); receipts metadata-only (hashes/counts/reason codes) |
| **External writeback / external delivery** | **No — temp vault/HTML dirs, fake notifier (no osascript), launchd dry-run (no plist/launchctl); `external_writeback_performed` total = 0** |
| Missing no-raw / no-writeback proof | No — automation proof + 08B gates + MCP/legacy proofs pass |
| Unresolved high-impact review items entering an approved source manifest | N/A |
| Unapproved Obsidian notes indexed | N/A — vault note went to a temp dir, not the real vault, and is not indexed |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A |

No stop condition triggered.

---

## 6. Verdict

G-06 **resolved (pipeline-proven)**: the Phase 08B automation/delivery agents produce controlled,
metadata-only, guard-clean receipts (10 receipts: delivery 1 / gated notification 1 / html 1 / agent-run 7;
open fail-closed) with channels pinned to local artifacts and **no external delivery** — demonstrated in a
labeled proof DB with the **operator DB and the real vault/HTML/launchd left pristine**. A reusable
read-only proof helper + 4 tests are committed (suite green). No stop condition triggered. **Proceed to
Phase 09 Prompt 07** (memory runtime & review — G-05) or the next preflight gap.
