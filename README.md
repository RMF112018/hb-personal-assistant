# HB Personal Assistant + Work Product Intelligence System

Bobby-only local-first MVP for Microsoft 365 delegated access, source-linked retrieval, action intelligence, meeting prep, file review, and Obsidian Daily Brief output.

**The Daily Brief is a module, not the project name.**

## Repository Status

- Latest implemented manifest in this repository: `v1.3.0`
- Remediation status: **Addendum (Prompts 01–06) complete.**
- Closeout status (addendum): **CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER** (see `docs/evidence/remediation-addendum/final-closeout/` and `docs/evidence/remediation-addendum/prompt-06/`; DNS language from that era corrected as misattribution in Phase 14 Prompt 01 — see `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-01/`).
- The active external blocker is tenant/admin consent pending for delegated Microsoft Graph permissions (auth flow reaches Microsoft; no current command evidence of DNS failure). Local path + code gates (P01–P05) passed. Prompt 06 matrix executed; truthful evidence bundle regenerated. Blocker taxonomy corrected in Phase 14 Prompt 01.

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
