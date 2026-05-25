# Prompt 03 — Delegated Graph Capability Proof Evidence

This directory is populated by `scripts/proofs/delegated_graph_capability_proof.py` (and the CLI wrapper `hb-assistant diagnostics proof --delegated-graph`).

## Files

- `summary.json` — overall proof run metadata + assumption note
- `step-1.json` through `step-10.json` — sanitized per-step results (per 05_Delegated_Graph_Proof_Specification.md redaction rules)
- `phase-3-sensitive-scan.json` — result of step 10 (repo + outputs scan)

## Redaction Rules (strictly followed)

**Allowed in evidence:**
- Endpoint path (with IDs truncated where helpful)
- HTTP status
- Token classification at time of call
- Tenant ID (truncated OK)
- User UPN / display name (for Bobby verification)
- Scope names (not full JWT)
- Hashed/truncated IDs
- File size, MIME type, SHA-256 hash (step 8)
- Cached local path for downloaded file (never the content)

**Forbidden (never present):**
- Access / refresh / id tokens
- Private keys or PEM material
- Full email bodies or calendar bodies
- Full file text contents
- Raw sensitive personal or project data

## Execution Assumption

Per explicit directive for this build:

> Any delegated permissions that are not currently granted will be granted during development, prior to deployment.

Mail-related steps (2, 3, 4, 6) may return 403 during the first proof run(s) until `Mail.Read` (and any other required mail scopes) are added to the app registration. These 403s are documented with the assumption note and are expected to become 200 once the grants are in place.

## How to (Re)Generate

After granting any missing delegated scopes and obtaining a fresh delegated token:

```bash
hb-assistant auth status --json
python -m scripts.proofs.delegated_graph_capability_proof --json
# or
hb-assistant diagnostics proof --delegated-graph --json
```

Then run the sensitive scan as step 10:

```bash
hb-assistant diagnostics scan-sensitive --repo . --json > ../phase-3-sensitive-scan.json
```

All evidence in this directory must remain free of secrets.
