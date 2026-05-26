# 11 — Standards and Best Practices

## Local-First Runtime Standards

- Store runtime data under Application Support, not inside the repo.
- Keep token caches outside the repo with strict permissions.
- Use SQLite for local state.
- Keep Obsidian writes explicit, marker-bounded, and idempotent.
- Make all local validation possible without Microsoft delegated consent.

## CLI Standards

- Use canonical Typer subcommand groups.
- All machine-readable commands must support `--json`.
- Error JSON must be structured and bounded.
- Do not print tokens, secrets, full bodies, full file text, or PEMs.
- Exit code `0` means success or intentional no-op; exit code `1` means blocked/error and must include classification.

## Privacy Standards

- Metadata-first retrieval.
- Bounded body retrieval in memory only.
- Redacted excerpts only.
- Parser excerpts only.
- No cloud state.
- No Microsoft writeback.

## Testing Standards

- Unit tests for deterministic action extraction.
- Store tests for idempotency and source links.
- CLI runner tests for JSON shape and exit codes.
- Orchestrator tests for consent-blocked Graph continuation.
- Obsidian tests for marker preservation.
- Sensitive scan tests for no secrets/full bodies/full file contents.

## Evidence Standards

Every prompt should produce a small evidence bundle:

- `summary.md`
- command outputs or summarized exit codes;
- updated validation register row;
- sensitive scan output where applicable;
- final commit SHA.

## Code Quality Standards

- Prefer small additive modules over large rewrites.
- Keep functions deterministic and testable.
- Avoid broad exception swallowing unless failure isolation is explicit and reported.
- Use typed models where the repo already uses Pydantic/dataclasses.
- Keep Ruff/mypy exclusions from expanding.
- Reduce exclusions opportunistically, but do not derail Phase 14.
