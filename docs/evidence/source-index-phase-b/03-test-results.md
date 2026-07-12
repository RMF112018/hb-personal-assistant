# Phase B — Test Results

All runs: `PYTHONPATH="src:subrepos/construction-financial-review/src"` with the documented
`.venv/bin/python -m pytest` (CPython 3.14.5). Raw captures in `final-runs/`.

## New Phase B test files (all green)

| File | Tests | Covers |
|---|---|---|
| `test_source_file_complete_read.py` | 13 | complete txt/csv/json (whole), too_large (output+input), deleted→unavailable, untrusted→stale, file_absent, index-divergence→stale, change-during-read→stale, provenance, search→ref→complete roundtrip, invalid-mode→invalid_request, excerpt still partial |
| `test_source_file_parser_isolation.py` | 18 | real PDF/DOCX/XLSX/EML parse (direct + via provider), corrupt PDF/XLSX, output-budget, input-gate (no spawn), timeout, segfault, nonzero-exit, malformed-payload, **process-group grandchild kill**, unsupported |
| `test_source_file_retrieval_semantics.py` | 10 | xer→unsupported_format, zip→archive_not_expanded, unknown-binary→unsupported, sensitive→denied, path-escape→denied, symlink-escape→denied, path-free ref, unconfigured-root→unavailable, forged ref rejected, no abs paths |
| `test_source_index_rename_lineage.py` | 15 | transactional move links+invalidates, rollback keeps old current + no partial row, plain-create-no-lineage, old-ref→moved+successor, successor-outside-auth not disclosed, non-current-successor not fabricated, plain-deleted→unavailable, watcher helper confirmed/unconfirmed/vault |
| `test_migrator_v126_rename_lineage.py` | 6 | latest==126, column+index added & nullable, V122–V125 preserved, idempotent re-apply, parity on partially-migrated DB |

## Key regression + gate runs

- **Phase-A contract regression** (Step 0): `217 passed` — `test_source_index_generation_hardening`, `_vault_deletion_safety`, `test_source_root_trust`, `_root_mapping`, `_watcher_automated_refresh`.
- **Full gate-equivalent list under venv 3.14** (`final-runs/gate-equivalent-venv-python.txt`): **443 passed, 0 failed, exit 0** — the entire `scripts/ci_source_index_gate.sh` pytest set (original 22 files, disambiguation now ENFORCED — deselect removed) + the 5 Phase B files + the V124 latency test. FastAPI loaded from `.venv/lib/python3.14` (correct interpreter).
- **Original gate list + Phase B src, no Phase B test files, venv** (`scratchpad`): exit 0 — proves no runtime regression from the src changes alone.
- **ruff** (`final-runs/ruff-gate-modules-venv.txt`): `All checks passed!` on the gate lint set + `isolated.py`.
- **Round-trip proof** (`final-runs/roundtrip-proof.txt`): search → path-free `source_ref` → complete txt (whole) + complete docx (isolated `extracted_content`) + xer (`unsupported_format` w/ next-step); provenance present; **no absolute path** in any response.

## Environment caveat (see 02-limitations)

`scripts/ci_source_index_gate.sh` calls bare `pytest`, which on this non-venv-activated shell resolves to
system Python 3.13 with an incompatible FastAPI (`Router 'on_startup' TypeError`) — an environment
artifact that fails the watcher/FastAPI tests. Under the correct venv interpreter the same list is fully
green (above). The gate script's invocation was left unchanged (correct in CI). Captured raw:
`final-runs/ci-source-index-gate.txt` (bare-pytest, shows the 3.13 artifact) vs
`final-runs/gate-equivalent-venv-python.txt` (venv 3.14, green).

## Pre-existing failures (NOT Phase B — tracked, out of scope)

- `test_fastapi_analytics_source_connector.py` search/cursor tests — reproduce with Phase B stashed.
- `#306` count-drift: `test_source_structure_cli::test_export_evidence_emits_gate_off_and_on_snapshots`
  (78→80), `test_source_index_client_performance_hardening::test_output_aliases_defined` (10→11) — left
  tracked, not blindly re-numbered (AEOS #12). Proven pre-existing at the starting SHA in `00-preflight.md`.
