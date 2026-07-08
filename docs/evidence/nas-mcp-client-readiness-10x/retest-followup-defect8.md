# Retest Follow-up — Defect 8 live-read fix (+ archive path_display)

Branch `fix/nas-mcp-source-live-read` off `origin/main` @ `79d281eb`. Follows the deployed 10-defect
remediation. No schema/migration; no tool add/remove/rename; posture unchanged.

## What the retest surfaced

The authenticated connector retest of the live deployment was **6 pass, 1 partial, 1 fail**. The one
hard fail was **Defect 8**: `assistant_source_file_read(prefer_live:true)` on a `syn-work` file still
returned `reason:"root_unavailable"` / `content_source:"indexed_excerpt_fallback"`.

## Root cause

Two config-construction paths exist on the NAS surface. The 10x fix added the `external_sources`
derivation to `obsidian_config_from_nas` (used by the **vault** tools — Defect 7 passed). But the
**source-connector** handler (`nas_mcp/broker.py::_invoke_assistant_source_connector`) builds its
config with `load_config()` — the generic Obsidian loader, which reads a persisted
`obsidian_mcp_config.json` that **does not exist on the NAS** → `ObsidianMcpConfig()` defaults →
`external_sources=[]`. So `SourceContentProvider._root_for("syn-work")` returned `None`.

The existing `test_nas_mcp_source_connector.py::test_tools_return_data` **monkeypatched `load_config`
to include external_sources**, which masked this in the test suite.

Deployed environment was otherwise correct (verified via ssh): compose mounts
`…/Work:/mnt/roots/work:ro`, `…/Home:/mnt/roots/home:ro`; deployed `hb-pa-config.mcp.yml` declares
`roots.work.mount:/mnt/roots/work`, `roots.home.mount:/mnt/roots/home`.

### Path-mapping answer
`syn-work` maps to the **container** path `/mnt/roots/work` (the host `…/Work` tree mounted there),
**not** the host path `/volume1/homes/bfetting/Work`. Index `rel_path`s are relative, so
`Path("/mnt/roots/work")/rel_path` resolves regardless of the absolute path used at index time.

## Fixes

1. **`nas_mcp/broker.py`** — after `config = load_config()`, inject `resolve_external_sources(cfg)`
   when `external_sources` is empty (only fills when empty, so an explicit persisted config still
   wins). `SourceContentProvider` then resolves live files.
2. **`nas_mcp/obsidian_config.py`** — promoted `_resolve_external_sources` → public
   `resolve_external_sources`; `obsidian_config_from_nas` still calls it (no vault-path change).
3. **`nas_mcp/client_output_workspace.py`** — `commit_archive_output` now updates `path_display`
   alongside `relative_path`, so `pa_output_metadata` no longer reports the stale pending path.

Defect 6 needs no code change: the `degraded_last_run_failed` downgrade is unit-proven but not
demonstrable live until a subsystem actually has a failed latest run; the sibling future-timestamp
guard is already visible live (`calendar_sync.status:"anomaly_future_timestamp"`).

## Validation

- New `test_nas_mcp_source_connector.py::test_live_read_resolves_via_nas_root_injection` — with
  `load_config` returning **empty** (real NAS condition) and NAS `roots.work` present, the broker
  injects `syn-work` and `assistant_source_file_read` returns `content_source:"live_extract"`. Passes.
- Extended archive test asserts `path_display` tracks the archive move.
- `test_nas_mcp_client_readiness_10x.py`, `test_nas_mcp_source_connector.py`,
  `test_nas_mcp_decision_memory.py`, `test_n8c24_output_*` — green. `ruff check` clean.
  `scripts/test-schedule.sh` canary — see `schedule-bundle-output-followup.txt`.

## Post-deploy live retest
Via the OAuth connector: `assistant_source_file_read(prefer_live:true)` on a supported `syn-work`
file (`.md`/`.pdf`) → live content, `content_source` NOT `indexed_excerpt_fallback`, no
`root_unavailable`; `assistant_source_roots_list` shows `syn-work`/`syn-home` (`provenance:"config"`);
`pa_output_metadata` on an archived output shows the archive `path_display`.
