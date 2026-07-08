# NAS MCP Client-Readiness Remediation — 10 Defects to Operational 10/10

Branch: `fix/nas-mcp-client-readiness-10x` (off `origin/main` @ `d8205699`). No schema/migration
(the workspace tables already exist from WS1); no tools added/removed/renamed. Security posture
unchanged: live prod DB never mounted, authoritative data read-only, writes brokered/idempotent/
path-safe/bounded, server-minted approvals only, archive is soft/reversible.

Follows the two prior workstreams (WS1 writable workspace DB `d1faa00c`, WS2 read-surface/routing
`d8205699`), both deployed.

## Defects, root causes, fixes

| # | Defect | Root cause | Fix |
|---|--------|-----------|-----|
| 1 | Persisted tool manifest missing + thin metadata | promote path correct but never run; `_build_tool_index` returned only `{group}` | Startup **auto-bootstrap** (`bootstrap_persisted_manifest`, gated to RO NAS, idempotent on checksum, server-minted approval); `_build_tool_index` enriched from the live schema index captured at registration; `build_manifest` now carries `purpose` |
| 2 | JSON output staging broken | `_render_json` ran `json.loads` on a base64 payload | `_render_json(content, content_mode)` decodes base64 when `base64_binary`, else validates text |
| 3 | ZIP `content_mode` inconsistent | bare `"base64"` failed the allow-set check | `_CONTENT_MODE_ALIASES` folds `base64→base64_binary` (and `json→json_text`, `zip→zip_base64`) before validation |
| 4 / 10 | Output archive not completable; safe cleanup | `plan_archive_output` omitted the (already-minted, reusable) approval id | Echo `operator_approval_id`; archive stays a soft move (`os.replace`, `deletes:false`), never a delete |
| 5 | Canonical artifacts absent from decision/pref/open-loop reads | promotion writes `pa_canonical_artifacts`; read tools read only `assistant_*_records` (different tables + DBs) | **Read-time union** (`canonical_decision_projection`): project `pa_canonical_artifacts` onto the record shape from the correct DB (workspace under RO, else managed), merged into the 6 read handlers. No writes → repo stays sole writer |
| 6 | Freshness telemetry unreliable | headline `status` from timestamp age alone | `_apply_last_status` downgrades ok/stale → `degraded_last_run_failed` when the latest run status is error/failed (WS2 future-anomaly kept) |
| 7 | Vault tooling ignores limits / leaks path | `list_directory` had no `max_files` cap and returned absolute `/mnt/vault`; scoped-search scope invisible | `list_directory` gains `max_files` (default 100, hard cap 500) + `truncated`; drops `root`, returns `path_display`; `search_by_properties`/`dataview_query` expose `scope`/`scoped`/`truncated` and document `root_path` as the sole scope |
| 8 | Source live-reads fall back to indexed excerpts | `obsidian_config_from_nas` never set `external_sources` → `_root_for` empty → `root_unavailable` | Config-driven `external_sources` (parsed from `obsidian.external_sources`) with a `syn-<roots-key>` default for home/work; `sensitive:false` enables live `:ro` reads; `hb-onedrive` stays indexed-only |
| 9 | Tool help/catalog wrong safety labels | `_assistant_tool_meta` hardcoded `read_only_advisory` for every tool | Uses `classify_tool` (single source of truth) → real `safety_class`/`tool_class`/`read_write_class` |

## Notable correctness find (beyond the audit)

The canonical projection initially opened the workspace DB with the shared `_ro_uri` helper, which
forces `immutable=1`. That is correct for the **static snapshot** but wrong for the **live workspace
DB**: an immutable open ignores the WAL, so a *just-promoted* canonical artifact still in the WAL
would be invisible. Fixed by opening plain `mode=ro` (the workspace/managed DB dirs are writable, so
no immutable needed) — see `canonical_decision_projection.project_canonical_records`.

## Deviation from the approved plan (surfaced, not silently changed)

Defect 7 plan text said "reject empty `root_path` for scope-required tools." Rejecting empty would
remove a legitimate whole-vault structured search. Instead the fix makes the effective **scope and
truncation explicit and honest** (`scope`, `scoped`, `truncated`) — the actual cause of the
"looks like root-level notes" confusion — without deleting a capability.

## Files changed

- Output: `nas_mcp/client_output_writers.py`, `nas_mcp/client_output_workspace.py`
- Manifest/metadata: `nas_mcp/tool_registration.py`, `nas_mcp/artifact_tools.py`, `obsidian_mcp/client_tool_manifest.py`
- Projection: `nas_mcp/canonical_decision_projection.py` (new), `nas_mcp/broker.py`
- Vault: `obsidian_mcp/tools.py`, `obsidian_mcp/frontmatter.py`, `nas_mcp/obsidian_adapter.py`
- Live-read: `nas_mcp/obsidian_config.py`, `nas_mcp/config.py`, `deploy/nas/mcp/hb-pa-config.mcp.example.yml`
- Freshness: `nas_mcp/freshness.py`
- Tests: `tests/test_nas_mcp_client_readiness_10x.py` (new, 21 cases)

## Validation

- New targeted suite: `tests/test_nas_mcp_client_readiness_10x.py` — **21 passed** (see
  `new-tests-output.txt`). Covers every defect group incl. an end-to-end broker union proof
  (a promoted canonical decision appears via `assistant_list_decisions`/`assistant_get_decision`)
  and the full startup manifest bootstrap (persisted + idempotent).
- Regression (all green): `test_n8c23_client_tool_manifest`, `test_n8c23_artifact_workspace`,
  `test_n8c23_canonical_promotion`, `test_n8c23_mcp_surface_safety`, `test_n8c24_output_*`,
  `test_nas_mcp_decision_memory`, `test_decision_memory_repository`, `test_obsidian_mcp_read_hardening`,
  `test_obsidian_mcp_frontmatter`, `test_nas_mcp_source_connector`, `test_nas_mcp_ws2_client_usability`,
  `test_nas_mcp_pa_readonly_db`, `test_nas_mcp_tool_annotations`, `test_nas_mcp_safe_mode_limits_freshness`.
- `ruff check` clean on all touched files. `scripts/test-schedule.sh` (migrator/schema canary): see
  `schedule-bundle-output.txt`.

## Post-deploy live connector retest (to run after authorized deploy)

Through the OAuth connector: stage→review→promote→read-back a decision artifact and confirm it shows
in `assistant_list_decisions`; stage a JSON output via base64 and a ZIP via `content_mode:base64`,
commit, then plan+commit archive; `pa_tool_manifest_get` returns `persisted:true` with real
per-tool metadata and correct `safety_class`; `list_directory` honors `max_files` and shows no
absolute root; a `prefer_live` source read returns live content; `hb_data_freshness` marks a
failed-latest subsystem as degraded, not ok.
