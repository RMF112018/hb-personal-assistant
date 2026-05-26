# Final Acceptance Criteria

The remediation sprint is accepted only when all items below pass.

## Repo Truth

- [ ] Canonical commit ref documented.
- [ ] User-stated missing SHA reconciled.
- [ ] README accurate.
- [ ] Phase 13 prior evidence superseded or corrected.

## CLI

- [ ] `auth status` works as a subcommand.
- [ ] `run morning` works as a subcommand.
- [ ] launchd ProgramArguments use canonical grammar.
- [ ] Typer help output is coherent.

## Automation

- [ ] LaunchAgent dry-run renders valid plist.
- [ ] Executable path exists or readiness blocks installation.
- [ ] Working directory is valid.
- [ ] Logs/evidence dirs writable.

## Validation

- [ ] pytest passes.
- [ ] Ruff passes.
- [ ] mypy passes.
- [ ] No known failures are hidden as “pre-existing.”

## Graph

- [ ] Delegated proof current-state pass.
- [ ] App-only runtime rejection proven.
- [ ] No M365 writeback enabled.

## Mail / Calendar / Files

- [ ] Body mention outside preview detected.
- [ ] Bounded paging implemented.
- [ ] File ingestion requires provenance.

## Obsidian / Brief

- [ ] Marker preservation still works.
- [ ] Daily Brief uses actual current data where available.
- [ ] Empty states are truthful and not stale placeholders.

## Security

- [ ] Sensitive scan reads bounded content.
- [ ] No raw token/private key/full body/full file content in repo/evidence.
- [ ] Token cache remains outside repo.
