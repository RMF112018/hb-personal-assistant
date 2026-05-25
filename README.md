# HB Personal Assistant + Work Product Intelligence System

Bobby-only local-first MVP for Microsoft 365 delegated access, source-linked retrieval, action intelligence, meeting prep, file review, and Obsidian Daily Brief output.

**The Daily Brief is a module, not the project name.**

## Repository Status

- Latest implemented manifest in this repository: `v1.3.0`
- Remediation status: **Implemented through v1.3.0 but not accepted until remediation validation is green.**
- Closeout status note: Prior Phase 13 closeout evidence is preserved and superseded pending remediation validation.

## Quickstart (after clone)

```bash
# Use the phase-0 venv or create fresh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

hb-assistant --version
hb-assistant --help
hb-assistant diagnostics env --json
```

## Key Paths (macOS)

- Application Support: `~/Library/Application Support/HB Personal Assistant/`
- Obsidian Vault: `/Users/bobbyfetting/Documents/Obsidian Vault/`

See `docs/architecture/` for implementation and remediation records, and `docs/plans/my-pa-phase-0/` for the original implementation package.

## Guardrails (Global)

- Delegated Bobby-user Microsoft Graph auth is the runtime default.
- Certificate-backed app-only is proof/admin only.
- **No** Microsoft 365 write-back.
- **No** tokens/keys/full bodies/PEMs logged or committed.
- Store auth/cache/SQLite/logs **outside** the repo.
- Dry-run before writes.
- Every output carries source traceability.

## Validation & Evidence

Remediation baseline evidence is tracked at:

- `docs/evidence/remediation/remediation-baseline.md`

Historical evidence remains under `docs/evidence/`, including prior Phase 13 closeout artifacts (superseded pending remediation validation).
