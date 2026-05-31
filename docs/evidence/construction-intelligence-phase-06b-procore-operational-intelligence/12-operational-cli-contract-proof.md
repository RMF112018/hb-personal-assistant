# Phase 06B — Prompt 12: Operational CLI Contract Proof

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `ee4550a` (`phase-06b prompt-11: responsible party & relationship quality diagnostics`)
**Objective:** Wire the Phase 06B read models into a stable operator CLI surface under
`hb-assistant procore live` — every query command local SQLite only, read-only, no live call, no
writeback, no raw values, no determinations.

---

## 1. Final command map (stop-condition reconciliation)

The operator surface is the existing `procore live` group. Of the 11 required commands, **7 already
existed** (Prompts 06–11) and **4 are new** (`store/procore_operational.py`). **No name conflicts** —
`risks` is a new top-level verb, distinct from the existing `live financial risk` sub-verb; `digest`,
`retrieval-ready`, `no-writeback-proof` were unused under `live`.

| Required command | Final command | Read model | Local/Live | New? |
| --- | --- | --- | --- | --- |
| `project-health` | `procore live project-health` | `build_project_health` | local | — |
| `stale` | `procore live stale` | `build_freshness` | local | — |
| `overdue` | `procore live overdue` | `build_overdue_queue` | local | — |
| `risks` | `procore live risks` | `build_risks` | local | **new** |
| `digest` | `procore live digest` | `build_operational_digest` | local | **new** |
| `responsible-party-gaps` | `procore live responsible-party-gaps` | `build_responsible_party_gaps` | local | — |
| `relationship-quality` | `procore live relationship-quality` | `build_relationship_quality` | local | — |
| `financial exposure` | `procore live financial exposure` | `build_cost_exposure` | local | — |
| `schedule exposure` | `procore live schedule exposure` | `build_schedule_exposure` | local | — |
| `retrieval-ready` | `procore live retrieval-ready` | `build_retrieval_readiness` | local | **new (minimal)** |
| `no-writeback-proof` | `procore live no-writeback-proof` | `build_no_writeback_proof` | local | **new (minimal)** |

---

## 2. What was built

- `src/hb_assistant/store/procore_operational.py` — four deterministic, read-only read models:
  - `build_risks` — open action signals that are high-importance OR carry a
    cost/schedule/safety-quality/overdue dimension; reuses `get_procore_action_signals` +
    `procore_project_health._dimensions_for`. Ordered high-importance-first; `by_dimension` summary.
  - `build_operational_digest` — composes `build_project_health` / `build_overdue_queue` /
    `build_cost_exposure` / `build_schedule_exposure` / `build_responsible_party_gaps` /
    `build_relationship_quality` and extracts headline numbers only (no new logic).
  - `build_retrieval_readiness` — preliminary read-only corpus probe over
    `procore_text_intelligence`, `procore_live_records`, open `procore_action_signals`;
    `retrieval_ready` flag + `reasons`.
  - `build_no_writeback_proof` — preliminary posture attestation (`checks` + the local-only query
    command list + the four mailbox read-only layers).
- 4 new `@live_app.command(...)` verbs in `cli/procore.py`, each with docstrings stating
  **local SQLite only / read-only / no live call / no determinations**.

**Deferral (documented decision):** `retrieval-ready` and `no-writeback-proof` are real-but-minimal
here so the surface is contract-stable and JSON-testable; the package's dedicated Prompt 14
(retrieval readiness) and Prompt 15 (no-writeback proof) deepen them. Each carries a `note` field
stating this. No new table or migration (schema stays V19, consistent with Prompts 06–11).

---

## 3. Validation

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_operational_cli.py` | 0 | 13 passed (help local/read-only ×4, JSON shape ×4, missing-project failure ×3, empty-project ok, no-HTTP-client AST proof) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+13) |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_operational_cli.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live {digest,risks,retrieval-ready,no-writeback-proof}` | 0 | ok envelopes, phase "Phase 06B Prompt 12" |

**No-HTTP-client proof** — `test_query_models_do_not_import_http_client` AST-scans the seven Phase
06B query read-model modules and asserts none import `requests` / `httpx` / `urllib3` /
`hb_assistant.procore.http_client` (extends `tests/test_procore_offline_enforcement.py` from test
files to the query *source* modules).

Sample outputs (digest / risks / retrieval-ready / no-writeback-proof + project-health / overdue for
context) generated over an isolated temp DB — see
[`operational-cli-sample-outputs.json`](./operational-cli-sample-outputs.json); secret/raw-value +
banned-determination-word scanned (0 findings).

---

## 4. Guardrail attestations

- **Local SQLite only** for every operator query command; **no live Procore call**
  (`no_live_call_performed: true`); **no writeback**; **read-only** (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only counts, labels, redacted titles, and refs.
  Sample-output JSON secret/raw-value scanned (0 findings).
- **No legal/claims/financial/safety/entitlement/schedule determination** (`determinations_made:
  false`) across all commands — banned-determination-word scan (0 findings).
