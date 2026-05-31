# Phase 06B — Prompt 15: No-Writeback / No-Secret / No-Raw-Body Proof

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `cb52666` (`phase-06b prompt-14: procore retrieval readiness`)
**Objective:** Produce an explicit, executable proof that Phase 06B added no Procore writeback, no
Microsoft 365 writeback, no raw-body persistence, and leaked no secrets — surfaced as
`hb-assistant procore live no-writeback-proof --json`. Read-only; local SQLite + repo source/evidence
scans only.

---

## 1. What was built

`store/procore_no_writeback_proof.py::build_no_writeback_proof` upgrades the Prompt 12 placeholder
into a real proof; the `live no-writeback-proof` CLI verb repoints to it and is **fail-closed**
(exit 3 if `proof_passed` is false). No new table or migration (schema stays V19). The prover holds
the secret-detection patterns, so it scans the *other* 8 Phase 06B modules — never itself.

### Checks (`checks_detail`, each `{passed, findings}`)
| Check | Result |
| --- | --- |
| `static_writeback_scan` | PASS — 8 modules, 0 mutating method calls (`.post(`/`.put(`/`.patch(`/`.delete(`/`.send_mail(`/`.create_message(`…) |
| `no_http_client_imports` | PASS — AST: 0 imports of `requests`/`httpx`/`urllib3`/`procore.http_client` |
| `module_secret_scan` | PASS — 0 value-shaped secret matches in the modules |
| `sqlite_raw_body_guardrail` | PASS — 24 `raw_body_persisted` tables, all `CHECK(raw_body_persisted = 0)`, distinct values ⊆ {0} |
| `evidence_output_scan` | PASS — 16 phase evidence `*.json` files, 0 token/secret/signed-URL matches |

**Scanned modules (8):** `procore_project_health`, `procore_freshness`, `procore_action_queue`,
`procore_cost_exposure`, `procore_schedule_exposure`, `procore_relationship_quality`,
`procore_operational`, `procore/obsidian_operational`.

---

## 2. Method / stop-condition reconciliation

- **Call-form writeback scan** — mutating patterns are matched only as method calls (`.verb(`) so
  the read-models' own guardrail prose ("no writeback", "no raw payload values") never
  false-positives.
- **Value-shaped secret regexes** — JWT, PEM header, `Bearer <token>`, SAS `sig=` / `sv=`, AWS key
  id, and `refresh_token`/`client_secret`/`access_token":"…` assignments — never bare keywords,
  because the evidence narratives legitimately mention "Authorization headers" / "tokens" in prose.
  `_scan_text_for_secrets` is unit-tested to **flag planted secrets and ignore prose** (the proof is
  not vacuous).
- **Raw-body guardrail probe** — `raw_body_persisted` tables are discovered dynamically from
  `sqlite_master`; each must carry the `CHECK(raw_body_persisted = 0)` constraint and store only `0`.
  A test confirms the CHECK constraint actively rejects an attempted `raw_body_persisted = 1` insert.
- **Prover self-exclusion** — the prover module is intentionally not in the scanned set (it holds the
  detection pattern table); it performs no writeback and imports no HTTP client by construction.
- **Stop condition honored** — any token / secret / signed URL / Authorization header / raw payload
  body / writeback code path makes a check fail → `proof_passed: false` → CLI exits 3. The current
  run passes all five checks.

---

## 3. Proof (no-writeback-proof.json)

```
proof_passed: true
checks_detail: { static_writeback_scan, no_http_client_imports, module_secret_scan,
                 sqlite_raw_body_guardrail, evidence_output_scan } all passed=true, findings=[]
scanned_modules: 8
raw_body_tables: 24 (each has_check=true, distinct_values ⊆ {0})
evidence files scanned: 16
```

See [`no-writeback-proof.json`](./no-writeback-proof.json). Re-running the command after its own
output exists in the evidence dir still passes (self-consistent).

---

## 4. Validation

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_no_writeback_proof.py` | 0 | 7 passed (proof passes; raw-body distinct {0}; CHECK constraint bites; scanner flags planted secrets; scanner ignores prose; CLI proof) |
| `pytest tests/test_procore_operational_cli.py` | 0 | 13 passed (Prompt 12 no-writeback regression — `_patch_conn` extended with the prover module) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_no_writeback_proof.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 144 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live no-writeback-proof --json` | 0 | `proof_passed: true` (exit 0; would exit 3 on failure) |

---

## 5. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only** (no
  migration, no persistence) — proven by the static + AST + SQLite + evidence scans, not merely
  asserted.
- **No raw bodies / secrets / signed URLs** — module + evidence value-shaped scans returned 0
  findings; the 24 `raw_body_persisted` guardrail columns enforce `= 0`.
- **No determinations** (`determinations_made: false`).
