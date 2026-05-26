# 09 — File Impact Matrix

## Objective

Define the expected file impact for the local agent. Repo truth may change this matrix, but deviations must be documented.

| Area | Files / Directories | Expected Change |
|---|---|---|
| Blocker taxonomy docs | `README.md`, `docs/architecture/00-README.md`, `docs/evidence/**`, possibly `docs/decisions/` | Correct stale DNS wording; add admin-consent taxonomy and current evidence note. |
| CLI root | `src/hb_assistant/cli/main.py` | Replace `actions` stub with real Typer group; optionally wire real `brief` group if implemented. |
| Actions CLI | `src/hb_assistant/cli/actions.py` | New command group. |
| Actions package | `src/hb_assistant/actions/` | New extractor, models, reconciler, service. |
| Store | `src/hb_assistant/store/repositories.py`, `src/hb_assistant/store/migrator.py` | Add idempotent action helpers and migrations only if needed. |
| Source links | `src/hb_assistant/links/registry.py` | Add helper(s) for action/source and note provenance links. |
| Classification integration | `src/hb_assistant/classification/` | Use existing signals; avoid broad rewrites. |
| Retrieval/context | `src/hb_assistant/retrieval/` | Expand workstream context assembly. |
| Obsidian | `src/hb_assistant/obsidian/writer.py`, `src/hb_assistant/obsidian/brief.py` | Implement source map, action IDs, `written_to_note` links. |
| Automation | `src/hb_assistant/automation/orchestrator.py`, `src/hb_assistant/cli/run.py` | Upgrade morning run stage model and local-only continuation. |
| Files | `src/hb_assistant/files/` | Only adjust if needed for action/file-review integration. No synthetic fallback in real ingest. |
| Tests | `tests/` | Add action, store, context, Obsidian, orchestrator, CLI tests. |
| CI | `.github/workflows/` | Add safe local validation workflow. |
| Resources | `docs/evidence/`, `docs/architecture/`, `docs/decisions/` | Add phase evidence, decisions, and validation outputs. |

## Files That Should Usually Not Need Major Changes

- Core MSAL provider implementation unless scope sanitizer regression appears.
- Graph HTTP client unless proof reveals a specific defect.
- Token cache manager unless path diagnostics fail.
- Parser implementations unless tests reveal unsafe output.

## Required Local Agent Discipline

For every prompt, report:

- files inspected;
- files changed;
- tests run;
- evidence paths created;
- remaining blockers;
- exact commit SHA after commit.
