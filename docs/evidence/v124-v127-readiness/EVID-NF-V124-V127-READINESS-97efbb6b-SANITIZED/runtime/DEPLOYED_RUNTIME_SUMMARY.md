# runtime/DEPLOYED_RUNTIME_SUMMARY.md — BOUNDED PUBLIC SUMMARY (public tier)

Evidence type: BOUNDED PUBLIC SUMMARY
Summary artifact trust: trusted
Underlying execution evidence trust: partially_trusted
Trust does not transfer: Yes
Raw evidence location: Private tier

Replaces (for the public tier) three deep-disclosure raw runtime captures retained **private-only** (full SHA-256 in
`PRIVATE_EVIDENCE_REFERENCES.md`):
- `PRIV-EVID-V124V127-RUNTIME-INSPECT` — container inspect
- `PRIV-EVID-V124V127-RUNTIME-LOGS` — running-container log tail / auth flow
- `PRIV-EVID-V124V127-RUNTIME-IMGINSPECT` — running-image inspect

## Bounded claims (deployed MCP container)
- The deployed image predates V127 (approximately V124-era) — supports NF-DEP-001.
- The container reads a **READ-ONLY snapshot** database; it does **not** open the live managed production DB.
- There is **no running container writer** against the live managed DB → a V124→V127 migration is a deliberate,
  separately-authorized operator action, not something a running service performs.
- Background workers are **disabled** in the deployed posture.

## Redacted to the private tier (operational topology — AEOS 04 §11)
Runtime duration/age, host/network bindings and endpoint topology, internal container and network identifiers, the
full environment, mount table, snapshot storage-path structure, and authentication request/response logs are
**not** required to support any V124→V127 readiness claim and are retained private (referenced above by SHA-256).

## Observation time: 2026-07-16 UTC
## Independent verification: Required
