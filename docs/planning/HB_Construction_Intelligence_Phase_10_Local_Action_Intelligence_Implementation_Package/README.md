# HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package

Generated: 2026-06-07T18:16:29.167838+00:00

This package is an audit-backed implementation guide for `RMF112018/hb-personal-assistant`.

## Phase 10 objective

Move the application from passive data aggregation/reporting into a local, privacy-preserving assistant layer that performs useful background work:

- normalize and relate data across Graph, Procore, SQLite, calendar, Daily Brief, Obsidian, and MCP surfaces;
- extract tasks, commitments, due dates, decisions, follow-up obligations, project references, and risk signals;
- monitor whether follow-ups appear resolved or stale;
- surface reviewable action queues in My Dashboard / Today;
- prepare action-focused Daily Brief candidates;
- manage approved Obsidian vault sections and tags;
- prepare Claude-ready context packets through the local MCP server;
- keep all outputs auditable, source-linked, reviewable, and local-only.

No repository code, branch, ref, commit, or file was modified to create this package. The package is generated as a local artifact only.

## Hardware assumption

Primary target machine: MacBook Pro M4 with 24 GB unified memory.

Phase 10 should use a tiered local model profile:

- `qwen3:14b` as the default extractor/reasoning profile.
- `gpt-oss:20b` or configured equivalent as the quality synthesis/profile option.
- `qwen3:30b` as an explicitly enabled, single-concurrency, manual/on-demand heavy profile.
- `qwen3:8b` only as an optional fast/retry profile.

## Package map

- `00_PACKAGE_MANIFEST.md` — complete package inventory and intended use.
- `01_*` through `28_*` — architecture, schema, UX, safety, evaluation, evidence, and execution plans.
- `prompts/` — ordered local coding-agent prompts.
- `resources/json/` — proposed contracts and output schemas.
- `resources/yaml/` — proposed seed/config policy files.
- `resources/sql/` — proposed additive schema draft.
- `resources/fixtures/` — synthetic model/MCP fixtures for test development.
- `runbooks/` — operator/developer runbooks for local model, jobs, Obsidian, MCP, and validation.

## Core recommendation

Build Phase 10 now as a Level 0–3 assisted local intelligence layer. Do not implement external action/writeback in this phase.
