# Remediation Delegated Graph Proof (Prompt 05)

**Status**: COMPLETE (2026-05-25)

## Summary

Prompt 05 replaces stale proof indirection with an in-package runtime proof runner and canonical CLI grammar:

- canonical: `hb-assistant diagnostics proof delegated-graph --json`
- compatibility alias: `--delegated-graph`

Proof now uses current runtime auth/graph clients and emits explicit status (`pass`, `gap`, `blocked_no_token`, `runtime_error`) with sanitized step data.

## Key Behavior

- Delegated token gate enforced:
  - runtime delegated valid only when `scp` present and `roles` absent.
- If token unavailable or invalid classification, proof exits with blocking status and remediation guidance.
- No claims of delegated proof success are allowed without real runtime delegated capability.
- Prior script-only delegation is superseded by runtime execution path.

## Evidence

- `docs/evidence/remediation/prompt-05-delegated-graph-proof/`
