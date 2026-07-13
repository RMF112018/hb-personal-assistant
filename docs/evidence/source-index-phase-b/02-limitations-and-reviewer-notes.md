# Phase B — Known Limitations & Reviewer Notes

This is architecture completion, **not** production activation. Phases C–H remain required.

## Production prohibitions still in effect
- No live watcher activation, no production bootstrap, no destructive reconciliation, no generation prune.
- No production DB mutation, no production migration run, no NAS production writes, no deploy.
- No production parser extraction at scale until Phase D validation.
- No production-readiness claim.

## Known limitations remaining
1. **Complete-read output budget is conservative** (`source_complete_read_max_output_bytes`, default 2 MiB).
   A larger supported file returns `too_large`/`parser_output_too_large` (content withheld); the client
   falls back to `mode="excerpt"`. Tunable, not silently truncated.
2. **No XER/P6 or archive interpretation** — explicit `unsupported_format` / `archive_not_expanded` by
   design (no parser exists; no recursive extraction in Phase B).
3. **`RLIMIT_AS` is best-effort on Darwin.** The hard isolation guarantee is timeout → kill →
   process-group reap. On a platform where `RLIMIT_AS` is strongly enforced (Linux), memory bounding is
   additionally hard; the code applies it either way.
4. **Rename lineage is same-root + watcher-confirmed only.** Cross-root moves remain two independent
   events and the source-side deletion still flows through the drain's confirmed-absence rules (no
   immediate delete). No content-hash-based move inference (deliberately out of scope).
5. **Generated-note carry-forward = inherited-but-unverified.** On a confirmed move, old generated notes
   are relinked to the destination with status `stale` (explicit), and destination extraction is reset to
   `pending`; the normal auto-refresh pipeline regenerates them. No prior extraction/parse success is
   advertised as current for the moved file.
6. **Index-divergence guard is strict** (exact `size`/`mtime_ns` vs index, matching the indexer's own
   fast-skip contract). A file changed since indexing returns `stale` on a complete read until the
   watcher re-indexes it — correct fail-closed behavior, but it means complete reads require a current
   index for that file.

## Environment note for the next auditor (IMPORTANT)
- `scripts/ci_source_index_gate.sh` invokes **bare `pytest`/`ruff`**, which assume an activated venv
  (correct in CI). On a shell where the venv is not activated, bare `pytest` may resolve to a *different*
  system Python (here: `/Library/Frameworks/.../3.13/bin/pytest`) whose FastAPI raises
  `Router.__init__() got an unexpected keyword argument 'on_startup'` in the watcher/FastAPI tests. That
  is an **environment artifact, not a Phase B regression.** Validate locally with
  `.venv/bin/python -m pytest` (3.14) — see `final-runs/gate-equivalent-venv-python.txt`, where the full
  gate test list is green. The gate script's interpreter invocation was intentionally left unchanged
  (Phase A owns it; it is correct under an activated venv / CI).
- Pre-existing, unrelated failures on this tree (NOT Phase B): `test_fastapi_analytics_source_connector.py`
  search/cursor tests (reproduce with Phase B stashed); the two count-drift tests in `#306`
  (`test_source_structure_cli::test_export_evidence_emits_gate_off_and_on_snapshots` 78→80 and
  `test_source_index_client_performance_hardening::test_output_aliases_defined` 10→11). Per AEOS these
  were left tracked in #306 rather than blindly re-numbered — they are outside this gate and unrelated to
  Phase B architecture; the real added-inventory that justifies the new counts should be identified before
  changing those assertions.

## Risks / edge cases for the next audit
- Confirm the subprocess isolation model on the deploy target OS (Linux CI) — verify `RLIMIT_AS`/`RLIMIT_CPU`
  actually enforce there, and that spawn works under the CI pytest.
- The moved-lineage `find_successor_source_id` returns the first active successor; a pathological
  multi-rename chain (A→B→C) links each hop but only the latest active row is "current" — verify the chain
  semantics match product expectations before Phase C.
- Complete-read reads the whole text file into memory (bounded by `source_complete_read_max_input_bytes`,
  default 25 MiB). Confirm that ceiling against real NAS file-size distributions in Phase C.
