# HB Personal Assistant + Work Product Intelligence System

Bobby-only local-first MVP for Microsoft 365 delegated access, source-linked retrieval, action intelligence, meeting prep, file review, and Obsidian Daily Brief output.

**The Daily Brief is a module, not the project name.**

## Current Phase

- **Phase 0**: Environment, Auth, Vault, Evidence Discovery — COMPLETE
- **Phase 1**: Repo Scaffold, Typer CLI foundation, PathPolicy + Pydantic config loader — **COMPLETE** (this README)

## Quickstart (after clone)

```bash
# Use the phase-0 venv or create fresh
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

hb-assistant --version
hb-assistant --help
hb-assistant diagnostics env --json
```

All validation commands (pytest, ruff, mypy, hb-assistant * --json) now execute cleanly (some commands are intentional Phase 2+ stubs that return safe JSON).

## Key Paths (macOS)

- Application Support: `~/Library/Application Support/HB Personal Assistant/`
- Obsidian Vault: `/Users/bobbyfetting/Documents/Obsidian Vault/`

See `docs/architecture/01-scaffold-overview.md` for component diagram and `docs/plans/my-pa-phase-0/` for the full implementation package.

## Guardrails (Global)

- Delegated Bobby-user Microsoft Graph auth is the runtime default.
- Certificate-backed app-only is proof/admin only.
- **No** Microsoft 365 write-back.
- **No** tokens/keys/full bodies/PEMs logged or committed.
- Store auth/cache/SQLite/logs **outside** the repo.
- Dry-run before writes.
- Every output carries source traceability.

## Next

Prompt 02 (Auth Provider + Token Cache) on the solid Phase 1 foundation.

## Validation & Evidence

All commands from the plan executed and captured under `docs/evidence/`.

See `docs/evidence/prompt-execution-log.md` (Prompt 01 section) and the validation result register.

---

Prepared: 2026-05-25 | Phase 1 scaffold complete | v0.1.0
