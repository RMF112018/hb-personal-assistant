# NAS Source-Structure Layered Index — Implementation Notes

Feature: an additive, deterministic, reviewable layered index of the NAS source folders so connected
LLM clients can navigate roots/folders/projects, know which roots are authoritative vs
backup/noise/generated, and learn where to search first. Built out-of-band; read-only API + MCP
surfaces. No Ollama in this increment (deferred). Branch `feat/nas-source-structure` off
`origin/main` @ 13a4e1a2.

## Scope delivered (operator-approved: "Through MCP tools", no Ollama)

- **Phase 1 — Schema V115 + models.** `store/source_structure_tables.py` (8 tables:
  roots/folders/entities/entity_folders/summaries/hints/findings/runs), wired into `store/migrator.py`
  (`_v115_statements`, guarded block, `LATEST_SCHEMA_VERSION = 115`). Dataclasses + client bounds in
  `obsidian_mcp/source_structure_models.py`.
- **Phase 2 — Tree parser.** `source_structure_tree_parser.py` parses a printed folder-tree artifact
  (absolute-path root headers + tree/indent branches) into structured folders. Purely structural;
  never persists an absolute path (headers only derive a neutral `root_key` + display name).
- **Phase 3 — Deterministic classifier.** `source_structure_classifier.py` — rule-first root/folder/
  doc-family classification, project-number regex (`NN-NNN-NN` high-conf / `NN-NNN` low-conf),
  noise/backup/generated/sensitive flags (safety classes take precedence over doc-family and are the
  ones a future Ollama phase must never override), search-rank. `classify_tree` propagates a project
  number to descendant doc-family folders (marked `classification_source='inherited'`).
- **Phase 4 — Repository + service + quality.** `source_structure_repository.py` (SQLite-only CRUD +
  bounded cursor reads; stable content-hash IDs → idempotent re-ingest), `source_structure_service.py`
  (bounded, curated, whitelisted-field reads — root-relative `rel_path` + opaque `folder_id` only, plus
  search-route ranking, project map, scope explain), `source_structure_quality.py` (deterministic
  findings incl. the hard `forbidden_path_exposed` absolute-path safety check).
- **Phase 5 — CLI + scanner + config.** `cli/source_structure.py` group (`ingest-tree`, `scan-roots`,
  `classify`, `summarize`, `quality`, `inspect-root`, `project-map`, `export-evidence`) with dry-run
  default + explicit `--apply`; `source_structure_scanner.py` (bounded metadata-only live walk →
  ParsedTree, operator-only, never a request path); `config/models.py` `SourceStructureConfig`
  (default all-safe; `extra="forbid"` respected). `source_structure_ingest.py` ties parse→classify→
  persist and generates bounded root/project summaries + prefer/avoid routing hints.
- **Phase 6 — Read-only API.** 7 GET `/api/assistant/source-structure/*` routes added inline to
  `construction/analytics/api.py` (`_source_structure()` helper + `_assistant_env`/`role_dep`),
  matching the existing assistant block. No absolute paths; bounded; cursor paged.
- **Phase 7 — MCP tools (78 → 85, default-off).** 7 read-only `assistant_source_*` tools in a new
  14th group `source_structure`, DEFAULT-OFF behind `HB_MCP_ASSISTANT_SOURCE_STRUCTURE`. Wired through
  `profile.py` (gate), `tool_registration.py` (`@mcp.tool()` wrappers), `broker.py` (tuple +
  ASSISTANT_TOOL_GROUPS + ASSISTANT_GROUP_GATES + dispatch branch + `_invoke_assistant_source_structure`
  reading over immutable RO connections + `hb_mcp_status` fields), `exposure_audit.py` (gate-aware gap
  logic + `installed_but_disabled`), and `tool_family_manifest.py` (maps to the existing
  `assistant_source_connector` family — keeps family_for_tool total at 24). Docs updated (AGENTS.md
  mandate, client-tool-operating-manifest.md, mcp-server-endpoints.md).

## Three-state tool-surface model (verified)

| State | client-exposed assistant tools | installed (canonical) |
|-------|-------------------------------|-----------------------|
| Baseline (before group) | 78 | 78 |
| **Gate OFF (default / live)** | **78** — 7 tools installed-but-disabled, NOT client-invokable (dispatch raises `assistant_source_structure_disabled`) | 85 |
| Gate ON (test harness / operator opt-in) | **85** | 85 |

The exposure audit reports NO code-level gap in the default-off state (a default-off group is not a
gap): `installed_total=85, expected_exposed=78, client_manifest_exposed=78, missing=0,
installed_but_disabled=[7 tools]`. See `mcp_status_gate_off.json` / `mcp_status_gate_on.json`.

## Safety posture (preserved, not weakened)

- No source-file mutation/move/delete; no email/calendar; no request-time recursive scans; no client
  index rebuilds; MCP handlers read precomputed rows only; RO-snapshot reads.
- No absolute-path leakage: rows carry root-relative `rel_path` + opaque `folder_id`; service returns
  only whitelisted keys; a `forbidden_path_exposed` finding + tests assert this.
- New tool names carry no forbidden finality/action substring; denied tools stay denied; new group is
  default-off behind its own kill switch — the live internet-facing surface is unchanged at 78 until an
  operator opts in.

## Validation

- Focused gate: **156 passed** (`test_results.txt`) — source-structure schema/parser/classifier/repo/
  service/CLI/API/MCP + tool-surface guard/invariant (`test_n8c_client_exposure_bridge`,
  `test_n8c_mcp_tool_inventory_final`, `test_n8c23/24`, `test_tool_surface_maintenance_contract`,
  `test_tool_manifest_freshness_guard`, `test_prompt_preflight_family_routing`, `test_n8c_final_validation`)
  + existing schema tests.
- Schedule bundle migrator canary (`store/migrator.py` cross-domain): see `schedule_canary.txt`.
- Ruff: `All checks passed` on every new/touched file (`ruff_results.txt`).

## Deferred (out of this increment)

- Ollama enrichment (`source_structure_ollama.py`, `source_structure_model_outputs` table → V116,
  `--include-ollama`, embeddings) — wraps existing `OllamaChatClient`/`StructuredOutputClient`,
  disabled by default; deterministic safety classes never overridden by a model.
- launchd scheduling automation.

## Pre-existing test correction

`test_n8c_client_exposure_bridge.py::test_catalog_lists_all_groups_and_tools` asserted
`safety_class == "read_only_advisory"`, which is stale on origin/main (`classify_tool` returns
`bounded_read` for all reads; the blanket label was retired when write surfaces joined the gateway).
The count-fix (13→14) newly reached that loop, so the assertion was corrected to `bounded_read` to
match current behavior. No product code changed for it.

## Not committed

All changes are staged-free and uncommitted, awaiting explicit in-run authorization. Pre-existing
untracked `docs/evidence/*` and `project-schedule-hub/*` dirs from prior sessions were left untouched;
staging will use explicit per-path adds only.
