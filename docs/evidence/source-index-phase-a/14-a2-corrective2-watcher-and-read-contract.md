# A2 corrective #2 — watcher trust enforcement + client-visible read contract

Narrow corrective on the HOLD-A4 disposition, addressing the two implementation-contract gaps the reviewer
identified in the A2 evidence-only corrective #1. Branch stays GREEN; no push/PR/merge/force; no production
mutation; no new tool/write surface; tool NAMES preserved.

## Issue 1 — watcher startup now enforces the authorized trust boundary
**Gap:** corrective #1 relocated the required fail-closed behavior to client serving and let
`SourceWatcher.start()` drain an enabled-but-uncertified root.
**Fix (shared authority, no ad-hoc policy):**
- New `RootTrustDecision.safe_for_watcher_activation` = `trust_state=="safe"` AND `reconciliation_complete`
  AND `structure_ready`, plus `watcher_activation_block_reason` mapping each not-ready state to one sanitized
  code (`source_root_trust.py`).
- `SourceWatcher.start() → _enforce_watch_trust()` now requires every configured+enabled root to be
  `safe_for_watcher_activation`, degrading (no drain) with the block reason otherwise. The watcher takes an
  injected `app_config` for deterministic, health-identical trust evaluation (`source_watch.py`).
- Non-circular: bootstrap is a separate, watcher-independent operation that writes a completed generation +
  structure data; blocking the watcher pre-bootstrap cannot deadlock. Details + call flow in
  `13-watcher-bootstrap-noncircular.md`.
- Tests (`test_source_root_trust.py`): the six named lifecycle tests
  (`watcher_start_before_bootstrap_fails_closed`, `bootstrap_succeeds_without_watcher`,
  `watcher_start_after_bootstrap_succeeds`, `watcher_start_blocks_policy_stale`,
  `watcher_start_blocks_reconciliation_incomplete`, `watcher_start_blocks_structure_data_unready`). The former
  `test_watcher_allows_uncertified_root_to_bootstrap` was reframed into `test_bootstrap_succeeds_without_watcher`
  (proves bootstrap is allowed, not that the watcher starts early); the former non-circular test was replaced by
  the six above. Four existing drain-mechanics tests were aligned to seed real readiness (see doc 13).

## Issue 2 — client-visible `assistant_source_file_read` contract corrected
**Gap:** only the `assistant_get_source` docstring was changed in corrective #1; the canonical manifest
`purpose` for the actual read tool still read the generic family fallback `"Indexed NAS source-file
discovery."`, disclosing none of the read contract.
**Fix:** added a proper `assistant_source_file_read` entry in `tool_entry_manifest.py` (purpose + use_when +
do_not_use_when + examples + common_failure_modes) stating: bounded excerpt, no complete-file retrieval, safe
root required, truncation / indexed fallback. Regenerated `semantic_surface_checksum` moves
`sha256:3eb81b4d…c4bf09fc` → `sha256:16af53d3…a53b72` (expected; confined to the one corrected purpose). Full
semantic diff, parity, and official-regeneration evidence in `11-manifest-semantic-diff.md`. The runtime
docstring was already accurate; `assistant_get_source` is confirmed a separate navigation-family tool.

## Files changed
| File | Change |
|---|---|
| `obsidian_mcp/source_root_trust.py` | +`safe_for_watcher_activation`, +`watcher_activation_block_reason`, watcher reason-code constants; field surfaced in health + readiness envelope |
| `obsidian_mcp/source_watch.py` | `SourceWatcher(app_config=…)` injection; `_enforce_watch_trust` requires `safe_for_watcher_activation` per enabled root |
| `obsidian_mcp/tool_entry_manifest.py` | new `assistant_source_file_read` canonical entry (purpose/use_when/do_not_use_when/examples/failure_modes) |
| `tests/test_source_root_trust.py` | −2 superseded watcher tests, +6 named lifecycle tests (trust suite 36→40) |
| `tests/test_obsidian_source_watch.py`, `tests/test_obsidian_source_watch_ownership.py` | 4 drain-mechanics tests seed real readiness (`_ready` helper) + inject `app_config` |
| `docs/evidence/source-index-phase-a/` | `04`, `09`, `11`, `13`, `14` updated/added; new probe output `manifest-checksum-a2corrective2.txt` |

## Static checks
`ruff check` clean on all changed src + tests; `ruff format --check` clean on the formatted
`source_root_trust.py`; `mypy` — Success on `source_root_trust.py` + `source_watch.py`. The pre-existing
`tool_entry_manifest.py` F841 (`fam`) is unrelated (reproduces on origin/main; not touched by this change).

## Validation
See `12-phase-a-regression-evidence.md` (refreshed counts) and the run artifacts. All Phase A tests introduced
through A2 pass; the only failures anywhere in the radius remain the 6 disclosed pre-existing baseline defects.
