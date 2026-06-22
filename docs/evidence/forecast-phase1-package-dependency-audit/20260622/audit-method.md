# Audit Method & Hygiene — Phase 1 Package-Dependency Audit

**Date:** 2026-06-22
**Type:** read-only audit. No source, config, or DB files were written. The only writes are
the three markdown deliverables in this directory.

## Provenance (pinned)

| Repo | Branch | Commit |
| --- | --- | --- |
| `hb-personal-assistant` | `feature/forecast-ui-live-config-promotion-orphan-fix` | `33fd116ca9438eb84437686b84494c1f8ade83db` |
| CFR (`subrepos/construction-financial-review`) | (same repo) | `33fd116…` |

The hb_assistant SHA was read from `.git/HEAD` → `.git/refs/heads/…` and confirmed by
`git rev-parse HEAD`. **CFR is vendored in-tree, not a submodule** — there is no `.gitmodules`
and no nested `.git`; `git ls-files` lists `subrepos/construction-financial-review/.../cli.py`
as tracked by the hb_assistant repo. So the CFR source commit is the hb_assistant commit.

The empty standalone clone `/Users/bobbyfetting/construction-financial-review` (whose
`origin/main` is `644a25d16eeb8bddd4fdd63a14a05af8dc16af4d`) is **NOT** the audited checkout
and was excluded.

## Tooling note (disclosed)

For part of this session the `Bash` and sub-agent tools were intermittently
classifier-unavailable; the inventory was built from a systematic module-level exploration of
CFR plus direct Read verification, and the mechanical `grep` sweep + `git` verification were
**completed once tooling recovered** (counts in `package-dependency-map.md`). The inventory was
grounded by:

1. **Systematic module-level exploration** of CFR (package layout, the 14 `workflows/` modules
   + `__init__`, the 15 `forecast_*` domain packages, reader/writer call sites, writer output
   classifications, env toggles, file-handoff chain).
2. **Direct source verification** (via Read) of the four load-bearing files:

| File | Verified facts |
| --- | --- |
| `context/db_source_adapter.py` | `db_backed_reads_active`/`load_forecast_source_rows`/`_read_from_db`/`_READERS`; default file-backed; DB branch lazy-imports hb_assistant; fail-closed on live DB / unset path / empty rows |
| `common/run_lineage.py` | `.cfr_run_state/full_fresh_<p>_<run_id>.json`; `resolve_upstream` 3-tier precedence; `record_latest`/`_latest_of` latest-glob; `validation_report.json` + stamp gating |
| `common/package_resolution.py` | explicit-only resolution (no latest-glob); required members per kind; chain-manifest read/write; live-root refusal |
| (context generator load path) | source rows loaded through the adapter; sorts applied by caller |

## Completeness checklist

| Check | Status |
| --- | --- |
| Both repo SHAs pinned | ✅ hb = CFR = `33fd116…` (vendored in-tree) |
| External input sources enumerated | ✅ (TWN / owner pay-app / Procore export) |
| Source-row adapter + env toggles classified | ✅ verified |
| Lineage/discovery (`run_lineage`, `package_resolution`, `config_root`, `io`) classified | ✅ verified |
| Context generator writers (`emit_*`, `build_context_package`) classified | ✅ — all 13 `emit_` are in `generate_forecast_context_package.py` |
| Analysis generator readers + writers classified | ✅ |
| Mapping workpaper / crosswalk_v2 classified | ✅ (both call `resolve_upstream`) |
| Config registry (Phase 16) classified | ✅ |
| `workflows/` modules assigned a role | ✅ 14 modules + `__init__` (15 files) |
| `forecast_*` domain packages assigned a role | ✅ 15 packages enumerated; each reads upstream via own `package_discovery.py`/`*_io.py` glob |
| Surface B (hb_assistant read-model + API) classified | ✅ |
| File-handoff chain reproduced | ✅ |
| Dual-role artifacts identified | ✅ |
| Mechanical `grep` census of `open(`/`json.load`/`read_jsonl`/`read_json`/`.glob(`/`.rglob(`/`.iterdir(`/`write_jsonl`/`write_json`/`write_text`/`shutil.copy2`/`emit_`/`resolve_inputs`/`resolve_upstream` | ✅ **completed** (counts in the map) |

## Residual follow-ups (refinement, not blockers)

1. Per-line role tagging of every individual `read_json`/`write_json` site (230/310 sites) — the
   census confirms volume and the module-level roles are assigned; a line-by-line tag is optional.
2. Confirm exactly which downstream `forecast_*` generators consume the mapping-workpaper
   crosswalks (backlog item #9 dual-role question).
3. Optional independent re-grep sample to confirm no `runtime-input` reader was misclassified.

## Hygiene assertion

- **Read-only:** no edits to any source, config, or DB file; no migration run; no toggle
  flipped; no forecast run executed; no network access.
- **Writes limited to:** this directory
  (`docs/evidence/forecast-phase1-package-dependency-audit/20260622/`).
- **Read-only proof (verified):** `git status --porcelain` for this audit's path shows exactly
  one addition — `?? docs/evidence/forecast-phase1-package-dependency-audit/` (untracked). No
  tracked source/config/DB file was modified by this audit. (The repo's working tree contains
  unrelated pre-existing modifications — `docs/evidence/construction-intelligence-phase-08*`,
  `frontend/src/**` — that are prior WIP on this branch and were **not** touched by the audit.)
- **Uncommitted by standing rule:** these artifacts are left uncommitted for review.
