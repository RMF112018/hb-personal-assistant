# Phase 10A Prompt 09 — MCP and Obsidian Raw Capability

**Objective**: Prepare raw-content downstream capability, config-gated. Raw packets can be built locally. MCP and Obsidian raw exposure must be explicit, default-disabled, and visible (policy + guardrails + behavior tests). No change to defaults; fail-closed; additive.

## Packet Types (first-class)

- Extended `PACKET_TYPES` in `research/policy.py` to include `"raw_email_context"`, `"raw_calendar_context"`, `"raw_daily_brief_context"`.
- `requires_research_packet` returns False for `raw_*` (self-contained).
- `RetrievalOrchestrator.orchestrate` (and `build_research_packet` call sites via CLI) now delegates to the canonical builders in `local_ai/raw_context.py` for raw packet types and returns an `OrchestratorResult` with a thin `ResearchPacket` stand-in adapter (raw posture explicit via `packet_type`, `summary_redacted`, and `source_ref_count`).
- `raw_daily_brief_context` is a composite of email + calendar raw packets.
- CLI `research-packet build --packet-type raw_*` now works (first-class); phase-10 `raw-*-packet` commands remain direct.
- Contracts/proofs updated to recognize raw posture distinction (metadata vs raw) where needed.

## MCP Wiring (default-disabled, explicit enable)

- `mcp/policy.py`: `evaluate_startup_checks` and `build_mcp_status` now load `load_raw_content_policy()`, compute `mcp_raw_allowed` (flag + permissive mode), surface under `raw_content` and effective `no_raw_content` in guardrails/status.
- `mcp/broker.py`: `_compute_mcp_raw_allowed`, early deny with reason `"raw_content_disabled"` for raw packet_type requests when not allowed; `_bound_output(..., allow_raw=True)` skips strict no-raw assert for permitted raw packets (still bounded + tagged `raw_content: true` / `mcp_raw_exposure`); `_allow` augments `policy_posture` and envelope when raw exposed.
- `mcp/wrappers.py`: `mcp_research_packet_wrapper` (and daily via orchestrator path) now surface full raw packet dicts (from canonical builders) when `packet_type` is raw_* (broker already gated).
- `mcp/resources.py`, `prompts.py`: posture dicts now include effective `mcp_raw_allowed` / adjusted `no_raw`; resources/prompts remain no-raw by default (raw lane is via packet tools).
- `mcp/registry.py`: added `get_mcp_raw_content_posture()` helper (consumed by proofs/audit).
- `mcp/proof.py`: `evaluate_no_raw_mcp_access` now loads posture via registry helper, reports `raw_content_posture`, sets guardrail `no_raw_content` = `not allowed`; proofs pass under both default-disabled (no raw) and enabled (permitted raw on approved surfaces) states.
- `mcp/audit.py`: includes `raw_content_posture` in permission audit report; adjusts guardrail when enabled.
- `mcp/__init__.py`: re-exports the posture getter.
- Denied raw actions (`raw_email_body_access` etc.) remain denied; permitted raw is only via `hb_research_packet` / `hb_daily_brief_packet` with `packet_type=raw_*` (still source-linked, bounded, audited, receipts).

All raw MCP surfaces carry explicit `"raw_content": true`, policy version/mode, and guardrails block.

## Obsidian Raw Export (config-gated)

- Wired `load_raw_content_policy` + obsidian flag check into `daily_brief/output.py` (module import + comment) and relevant call sites.
- New CLI surface: `second-brain phase-10 obsidian-raw-export --project P --date YYYY-MM-DD [--apply]`.
  - Loads policy; checks `obsidian_allow_raw_content` + permissive mode.
  - Default (disabled): reports reason, dry-runs with `ok:false` / disabled detail; never writes.
  - Enabled: builds raw packets (via canonical builders), emits bounded note with frontmatter (`raw_content: true`, `policy_mode`, `source_refs`, guardrails), Phase-10-specific markers (`HB_PHASE10_RAW_CONTEXT:BEGIN/END`), provenance, and bounded excerpts (never full unredacted outside V42); uses `MarkerBoundedWriter` for safe marker-bounded apply.
- Fences: `_assert_no_raw` / existing output fences are preserved for non-raw and disabled paths; raw export intentionally includes bounded raw excerpts only under the allowlist markers + explicit policy note when enabled. No PEM/JWT/URL leaks (builders + bounded excerpts + existing redaction).
- No change to standard daily-brief / projectors (remain redacted/metadata); raw export is opt-in Phase 10A lane.

## Config Gating and Invariants

- Policy (P01): `DownstreamToggles.mcp_allow_raw_content` / `obsidian_allow_raw_content` default `false`; validator requires permissive mode to honor `true`.
- Schema (P02): `raw_content_policy_state.{mcp_raw_enabled, obsidian_raw_enabled}` (used for snapshots/audit).
- Fail-closed: any error in policy load → disabled.
- Visibility: every enabled raw surface (MCP envelope, Obsidian frontmatter/markers, packet payloads) includes `raw_content: true` + policy mode/version + source refs.
- Bounded + provenance: excerpts only; no full bodies outside V42 tables; all carries hashes/refs.
- Local-only, advisory, dry-run default, no external writeback.
- No schema migration (columns pre-existed).
- No removal of existing no-raw fences (they become conditional on the allow flag + mode).

## Tests

- New: `tests/test_phase_10a_mcp_obsidian_raw_capability.py`
  - Default-disabled: MCP broker denies raw packet types (explicit reason); no_raw proofs report `no_raw_content=true`; Obsidian CLI reports disabled.
  - Enabled (mocked permissive + flags): MCP dispatch succeeds for raw packet_type and result carries `raw_content` marker; raw packets build; Obsidian CLI dry-run shows would-write + visibility.
  - Local builders succeed regardless of downstream toggles (model_context path).
  - Hermetic temp DB, policy object mocks, safe markers, no live.

## Acceptance

- Raw packets (raw_* context or raw daily-brief variant) first-class and buildable via packet/orchestrator/CLI when policy/model_context allows.
- MCP raw exposure explicit + visible: default → strict no_raw + denials/metadata-only + proofs pass; explicit enable → raw-capable via approved packet tools with markers + guardrails in payloads + receipts.
- Obsidian raw export explicit + visible: default → no raw written; enable → bounded raw sections written to allowlisted markers with provenance/frontmatter; fences preserved when disabled.
- Config behavior tested; all guardrails (local-only, advisory, bounded, source-linked, explicit visibility, no silent enable) preserved.
- Architecture 216 + 00-README line + traditional manifest commit.

## Files Touched (surgical/additive)

- Packet: `research/policy.py`, `research/orchestrator.py`, `cli/second_brain.py` (orchestrate path), `local_ai/raw_context.py` (canonical, no change), `local_ai/__init__.py` (export).
- MCP: `mcp/policy.py`, `broker.py`, `wrappers.py`, `resources.py`, `prompts.py`, `registry.py`, `proof.py`, `audit.py`, `mcp/__init__.py`.
- Obsidian/raw export: `daily_brief/output.py` (wire), `cli/second_brain.py` (new phase-10 command), `obsidian/writer.py` (existing, used), no new exporter needed.
- Tests: `tests/test_phase_10a_mcp_obsidian_raw_capability.py`.
- Docs: `docs/architecture/216-...md`, append to `00-README.md`.

**Risks / non-goals**: No default policy change; no full raw dumps; no web/remote; no auto-inclusion; later prompts may extend lanes.
