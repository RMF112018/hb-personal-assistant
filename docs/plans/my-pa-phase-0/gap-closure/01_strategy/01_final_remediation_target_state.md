# Final Remediation Target State

## Objective

Bring `RMF112018/hb-personal-assistant` from “implemented but not accepted” to a verified MVP that can be trusted for Bobby-only local-first personal assistant use.

This target state does **not** expand the product scope. It closes implementation gaps, corrects command/runtime inconsistencies, and replaces overstated evidence with clean, current, reproducible evidence.

## Canonical Completion Definition

The remediation is complete only when the repo has a new final remediation commit on the correct branch and the following statements are all true:

1. The repo’s current `HEAD` is known and documented.
2. The user-stated missing SHA `63bb05c7163b85ff556f0a599a19cf9bba501280` is reconciled.
3. README and architecture docs accurately describe the actual version and phase state.
4. CLI command grammar matches the package/runbook:
   - `hb-assistant auth status`
   - `hb-assistant auth login`
   - `hb-assistant auth logout`
   - `hb-assistant auth clear-cache`
   - `hb-assistant run morning --dry-run`
   - `hb-assistant diagnostics automation`
   - `hb-assistant diagnostics scan-sensitive --repo .`
5. launchd ProgramArguments invoke the real canonical command.
6. launchd executable path and working directory are valid on Bobby’s machine.
7. `pytest`, `ruff`, and `mypy` pass under the agreed repo scope.
8. delegated Microsoft Graph proof passes using Bobby’s delegated user token from the current codebase.
9. Microsoft 365 writeback remains disabled and no Graph mutation path exists.
10. body mention detection works when Bobby appears outside `bodyPreview`.
11. Graph mail/calendar/drive read clients support bounded paging.
12. file ingestion requires valid source provenance before real download/parse.
13. Daily Brief content uses actual available context instead of stale placeholder language.
14. sensitive scan checks file contents safely and emits only category/path/line metadata.
15. final evidence files are consistent with real command outputs.

## Non-Goals

- Do not add Microsoft 365 writeback.
- Do not add multi-user behavior.
- Do not convert to a server/cloud architecture.
- Do not introduce a UI.
- Do not re-platform away from Typer/Python/SQLite/Obsidian.
- Do not implement broad speculative agent workflows beyond closing the identified MVP gaps.

## Operating Constraints

- Read-only Microsoft 365 access only.
- Local-first storage only.
- No raw tokens, refresh tokens, private keys, PEM contents, full email bodies, or full file contents in logs/evidence.
- Full body retrieval may occur only as bounded in-memory processing for classification; raw body must not be persisted.
- File downloads require provenance and eligibility.
- Dry-run must remain the default for high-impact workflows.
