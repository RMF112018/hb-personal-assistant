# 206. Phase 10 Local Action Intelligence — Contracts, Seeds & Policy

Date: 2026-06-07

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 01)

## Decision

Phase 10's declarative substrate ships first: ten JSON contracts, four YAML seed policies, five synthetic fixtures, Pydantic enforcement models, a fail-closed loader/registry, and a read-only `contracts-proof` command. This prompt introduces **no runtime** — no Ollama call, no AI job queue, no DB schema (the V41 migration is Prompt 02), no scheduler hook, and no writeback.

## Placement

- Contract JSON → `src/hb_assistant/resources/json/phase_10_*.json` (the packaged 97-file dir; already covered by the `package-data` glob `resources/json/*.json`, so no `pyproject.toml` change).
- Seed YAML → `resources/config/phase_10_*.seed.yaml` (repo-root, loaded via `PathPolicy().resolve_repo_root()`, mirroring every second_brain seed loader). `HB_PHASE_10_*` env vars override each seed path.
- Code → `src/hb_assistant/construction/second_brain/local_ai/` (`models.py`, `contracts.py`, `proof.py`, `__init__.py`). Nesting under `second_brain` inherits the strict `second_brain.*` mypy scope and sits beside the `daily_brief`, `mcp`, `obsidian_index`, and `memory` surfaces Phase 10 builds on. The broader top-level `construction/local_ai/` namespace is deferred until the runtime/job prompts prove the final boundaries.
- CLI → `second-brain phase-10 contracts-proof` (new `phase-10` Typer subgroup in `cli/second_brain.py`).

## Enforcement: Pydantic, not jsonschema

The repo has no `jsonschema` dependency (only `pydantic>=2.7` + `pyyaml`). The published `phase_10_action_candidate_output_schema.json` (JSON Schema draft 2020-12) is therefore the **contract artifact**, while enforcement happens in code via the `ActionCandidate` Pydantic model. All models use `model_config = {"extra": "forbid"}` and closed `Literal` enums, so forbidden raw fields (`raw_email_body`, `raw_response`, `signed_url`, `token`, …) and unsupported enum values are rejected at parse time.

## Safety invariants encoded now

- **Every candidate carries ≥1 source ref** — `ActionCandidate.source_refs` has `min_length=1` and rejects blank entries. A task/commitment cannot exist without provenance.
- **Advisory provenance** — `model_profile_id`, `prompt_template_version`, `input_window_hash`, `confidence`, and `review_status` (default `pending`) travel on every candidate.
- **High-stakes are signals, never determinations** — for the eight high-stakes `safety_category` values (contract, legal, financial, payment, claim, entitlement, schedule, safety) the model must route to `review` and may not pre-accept.
- **External actions always need approval** — `external_action_requires_approval` is `Literal[True]`.
- **Seed guardrails** — `default_extract` is the only enabled profile; heavy profiles require explicit enable + single concurrency; AI jobs are `dry_run` by default; MCP policy is read-only/metadata-only and forbids arbitrary SQL + all source-system writeback; Obsidian writes are marker-bounded with a frontmatter allowlist and preserve the user body.
- **Environment isolation intent** — dev/production outputs, queues, receipts, vector stores, and Obsidian writes remain isolated by environment profile (carried forward into the V41 schema in Prompt 02).

## Proof surface

`build_phase_10_contracts_proof()` (CLI `second-brain phase-10 contracts-proof --json [--write-evidence]`) loads all ten contracts, validates the four seeds against their Pydantic models, structurally validates the five fixtures against contract enums, and scans every artifact for secrets/tokens/signed-URLs/raw keys. It is read-only and metadata-only — no DB, no Ollama, no network — and exits non-zero on any fail-closed failure or finding. Evidence: `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/01-contracts-seeds-proof.{json,md}`.

## Out of scope (later prompts)

V41 additive schema (Prompt 02); local model runtime/status (Prompt 03); structured-output client (Prompt 04); AI job queue + run receipts (Prompt 05); extraction/classification (Prompt 06+); Obsidian writer, MCP packet builder, and frontend review queue UI.
