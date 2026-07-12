# Phase B — Step 0 Preflight & Phase-A Verification

Non-production evidence. No secrets, tokens, or production absolute paths.

## Repository state at start

| Item | Value |
|---|---|
| Branch | `phase-b-source-index-architecture-completion` |
| Cut from | `origin/main` |
| Starting SHA | `77cf87da392268f42470e5b8aec814815e7c4af1` |
| Base `origin/main` SHA | `77cf87da392268f42470e5b8aec814815e7c4af1` |
| Untracked (foreign churn, left untouched) | `frontend/src/lib/copyHelpers.test.ts`, `docs/implementation/project-schedule-controls/*.md` |

`git status --short` at start showed only the untracked foreign-churn files above (the known
concurrent-mutation hazard); no tracked working-tree modifications.

## Environment / dependency preflight (STOP-gate: all must pass)

```
$ .venv/bin/python --version
Python 3.14.5

$ .venv/bin/python -c "import pypdf, docx, openpyxl, pdfplumber; import email; print('ok')"
runtime parser deps OK: pypdf  docx=1.2.0  openpyxl=3.1.5  pdfplumber=0.11.9  email(stdlib)

platform: darwin  macOS-27.0-arm64-arm-64bit-Mach-O
os.setsid available: True
resource.RLIMIT_AS: True   resource.RLIMIT_CPU: True
```

**Result: PASS** — every runtime parser dependency imports under Python 3.14.5. No dependency
substitution required. Platform supports `os.setsid` (process-group containment) and the
`RLIMIT_AS`/`RLIMIT_CPU` API.

> Platform note: on Darwin, `RLIMIT_AS` enforcement is weak/inconsistent. Phase B therefore treats
> **subprocess timeout → terminate → kill → process-group reap** as the hard crash/hang-isolation
> guarantee, with `setrlimit` as best-effort defense-in-depth. The implementation report will state
> the OS actually tested and whether the rlimits were observed to enforce.

## Phase-A dependency proof (claim → evidence)

Phase-A trust/readiness/deletion contracts that Phase B builds on were **run**, not assumed:

```
$ PYTHONPATH="src:subrepos/construction-financial-review/src" .venv/bin/python -m pytest \
    tests/test_source_index_generation_hardening.py \
    tests/test_source_index_vault_deletion_safety.py \
    tests/test_source_root_trust.py \
    tests/test_source_root_mapping.py \
    tests/test_source_index_watcher_automated_refresh.py -q
217 passed
```

Invariants confirmed present and tested (file:line leads):
- Root-scoped source identity — `obsidian_mcp/source_index_repository.py:85` (`source_id_for`), unique `idx_si_sources_root_relpath`.
- Fuzzy substring root-matching removed — `obsidian_mcp/source_root_mapping.py:11`.
- `safe_for_client_answering` / `safe_for_content_answering` / `safe_for_path_lookup` — `obsidian_mcp/source_root_trust.py`.
- `derive_watcher_ready` fail-closed — `obsidian_mcp/source_indexer.py:221`.
- Confirmed-absence vs indeterminate deletion — `obsidian_mcp/source_indexer.py:203` (`_is_confirmed_missing`/`_is_indeterminate_oserror`), event-drain re-probe `~:2460`.
- Generation authority + policy-fingerprint currency — V122 (`store/source_index_scan_generations_tables.py`).

**Result: PASS** — Phase A is testable and green. Not a blocker. Proceeding.

## Baseline-debt proof (pre-existing failures, NOT introduced by Phase B)

The three drifted assertions tracked in issue #306 were run at the starting SHA **before any edit**:

```
$ ... pytest \
   tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions \
   tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots \
   tests/test_source_index_client_performance_hardening.py::test_output_aliases_defined -q
FFF  (3 failed)
```

| Test | Failure at starting SHA |
|---|---|
| `test_all_source_tools_have_disambiguating_descriptions` | `assistant_source_index_health` description lacks a "vault"/"card" contrast word (`test_source_connector_eval.py:99`). Currently deselected in `scripts/ci_source_index_gate.sh`. |
| `test_export_evidence_emits_gate_off_and_on_snapshots` | `assert 80 == 78` — `expected_exposed` count drift (`test_source_structure_cli.py:106`). |
| `test_output_aliases_defined` | `assert 11 == 10` — `ASSISTANT_OUTPUT_ALIASES`/`ALL_PA_OUTPUT_TOOLS` now 11 `pa_output_*` tools (`test_source_index_client_performance_hardening.py:235`). |

These are **pre-existing** and independent of Phase B architecture. Per the AEOS-revised plan they are
handled in an **isolated commit** in Step 6, and the two count assertions are only re-numbered after the
actual added tool/alias inventory is identified (not blindly matched to the current count).

## Disposition

Step 0 **PASS**. No stop condition triggered. Proceeding to Step 1 (isolated parser supervisor).
