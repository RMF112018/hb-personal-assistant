# Phase 10A Prompt 01 — Raw Content Config and Policy Surface

**Date:** 2026-06-07  
**Prompt:** 01 (Phase 10A Addendum — Raw Content Enabled Local Intelligence)  
**Status:** Implemented (surgical)

## Objective

Add explicit raw-content policy config per the Phase 10A package:

- Raw content config model fields (Pydantic).
- YAML seed/defaults.
- Diagnostics output showing raw-content mode.
- Support `email_calendar` mode first.
- Keep external writeback disabled (hard invariant).

Acceptance: `hb-assistant diagnostics env --json` (or contracts proof) shows raw mode; config supports raw email and calendar content.

## Changes

- **Models** (`src/hb_assistant/construction/second_brain/local_ai/models.py`): Added `RawContentPolicy`, `RawContentSettings`, and supporting nested models (`DownstreamToggles`, `ModelContextConfig`, `PersistenceConfig`, `EndpointsConfig`, `ProhibitedWithoutApproval`, `StartingSources`, `RawContentMode` Literal). `model_config = {"extra": "forbid"}`. `model_validator` enforces:
  - mode ∈ contract set (disabled | email_calendar | ...)
  - email_calendar requires starting email+calendar sources
  - all `prohibited_without_future_approval.*` (external_writeback, automatic_email_send, automatic_calendar_mutation, cloud_llm_submission) == true
  - downstream allowances (mcp/obsidian) == false under email_calendar for Prompt 01 scope.

- **Resources**:
  - Packaged contract: `src/hb_assistant/resources/json/phase_10a_raw_content_policy_contract.json` (modes, default_recommended_mode, starting_sources, future_sources, raw_content_allowed).
  - Seed: `resources/config/phase_10a_raw_content_policy.seed.yaml` (version 1.0.0, mode: email_calendar, include_raw for model_context, limited persistence, all prohibitions true, downstream off).

- **Registry + loaders** (`local_ai/contracts.py`): Registered contract key + seed key + env override var. Added `load_raw_content_policy() -> RawContentPolicy` (fail-closed via existing `_load_seed_dict` + Pydantic). Updated imports.

- **Exports** (`local_ai/__init__.py`): Re-exported `load_raw_content_policy` and `RawContentPolicy`; the `PHASE_10_*_FILES` dicts now surface the new entries.

- **Proof** (`local_ai/proof.py`): Added loader to contracts import and to the seeds loaders dict (so seed_versions and count cover 5 seeds). Added explicit attestation block after seeds load (mode check, prohibition flags, downstream conservative check). On failure appends to errors (makes proof_passed=false). Added `"raw_content_policy"` snapshot to result payload (mode/enabled/writeback_prohibited/sources/note).

- **Diagnostics** (`cli/diagnostics.py`): `env_cmd` now (lazy import) loads the policy and populates `data["raw_content"]` with mode, enabled, writeback_prohibited, sources, note. Wrapped in try/except for graceful unavailable. Satisfies acceptance: `hb-assistant diagnostics env --json` reports the raw mode.

- No changes to `AppConfig` / `SecurityConfig` (writeback remains false at the master switch). No schema, no email/calendar ingestion, no endpoint behavior, no MCP/Obsidian raw toggles, no model context builder yet — strictly Prompt 01 surface.

## Rationale / Trade-offs

- Reused the established Phase 10 local_ai substrate (contracts + seeds + Pydantic + proof + lazy) for consistency and to keep the surface inside the "local AI policy" family rather than polluting core `AppConfig`.
- Fail-closed invariants at model load time (similar to AiJobPolicy guardrails) ensure the prohibition cannot be silently bypassed by a bad seed/override.
- Diagnostics enrichment is read-only/safe and matches the pattern used by other surfaces (automation, auth, etc.).
- Downstream allowances forced false for email_calendar in this prompt; later prompts (09+) will relax under additional gates.

## Verification notes (see follow-up run)

- ruff + mypy (scoped) clean on touched modules.
- Safe pytest subset + targeted (local_ai, phase_10, diagnostics, config) green.
- Manual: `hb-assistant diagnostics env --json` contains `raw_content.mode == "email_calendar"` and `writeback_prohibited: true`.
- `python -c 'from hb_assistant.construction.second_brain.local_ai import load_raw_content_policy as L; p=L(); print(p.raw_content.mode, p.raw_content.prohibited_without_future_approval.external_writeback)'` succeeds.
- Contracts proof loads the new policy and includes the snapshot; no forbidden raw keys.
- Sensitive scan on new/changed files: clean.
- Stop conditions (no external writes, no raw leakage) preserved.

## Follow-ups (per package manifest)

Prompt 02 (schema additive), 03 (email raw ingestion), 04 (calendar), 05 (endpoints), ... will consume `load_raw_content_policy()` and the persisted raw tables (future).

## References

- Phase 10A package: `00_PACKAGE_MANIFEST.md`, `Prompt_01_Config_And_Policy_Surface.md`, `02_DECISION_RECORD_RAW_CONTENT.md`, `03_ARCHITECTURE.md`, `resources/yaml/phase_10a_raw_content_policy.seed.yaml`, `resources/json/raw_content_policy_contract.json`.
- Phase 10 substrate: `local_ai/models.py`, `contracts.py`, `proof.py`.
- Diagnostics: `cli/diagnostics.py` (env).
- Guardrail philosophy: `CLAUDE.md` (no writeback, local-first, additive only).

This record is intentionally short (surgical per Prompt 01 scope). Later prompts will extend the arch surface.
