# D-CLI-001: Typer as Primary CLI Framework

**Date**: 2026-05-25  
**Phase**: 1 (Prompt 01)  
**Status**: Accepted

## Decision
The HB Personal Assistant MVP will use **Typer** (built on Click) as the primary CLI framework.

## Rationale
- Type-driven command definitions with excellent editor support and autocompletion.
- Clean nested subcommand support (via underlying Click) with lower boilerplate than raw argparse for a multi-group CLI (auth, diagnostics, run, brief, etc.).
- Aligns with modern Python 3.12+ local tooling (many projects in the ecosystem have migrated).
- Preserves the ability to drop to raw Click only for exotic behaviors if ever needed (per clarification constraints).
- Rich help and JSON-friendly output patterns fit the `--json` contract required by the validation suite and automation.

## Alternatives Considered
- Click (more verbose for typed params)
- stdlib argparse (excessive boilerplate for 10+ subcommand groups + options)
- Fire / others (less control, weaker typing)

## Consequences
- `typer[all]` added to runtime dependencies.
- All command functions remain thin routers; real work lives in service modules (future phases).
- `--json` output is the contract for all diagnostics and automation commands.

## References
- Prompt 01 clarification (user decision)
- 11_CLI_Agent_And_Automation_Specification.md (command namespace)
- Phase 1 implementation (src/hb_assistant/cli/)
