# 02 — Safe Mode Design

Global incident/lockdown switch: `HB_MCP_SAFE_MODE=1` (`profile.safe_mode_enabled`, tri-state
`_env_bool`, default off). Operator/env-only — **no MCP tool toggles it**, so a remote LLM can
neither enable nor disable it.

## Enforcement (`broker.dispatch`)
Ordered BEFORE the profile write-gate so lockdown is unconditional:
`hard-denied verbs → SAFE MODE (deny if write_attempted) → profile blocked_write_tools →
per-token allowed_tools → write-window → concurrency → dispatch`.
`write_attempted` covers all mutations (AI Outputs, scratch writers, the 5 broad vault tools),
so safe mode denies every one with `safe_mode_active:<tool>` + audit.

## Preserved in safe mode
Minimal health, `hb_mcp_status`, `hb_data_freshness`, `hb_queue_status`, `hb_recent_failures`,
`hb_last_successful_runs`, `hb_capability_mode`, and all Tier 0-1 reads. Origin auth stays
required — safe mode creates no unauthenticated path. Visible via `gate_status()` →
`hb_mcp_status` / protected `/health` / `hb_capability_mode` (`safe_mode: true`).

## Not remotely disableable
The only control surface is the env/config the operator sets on the NAS host; there is no
request path to change it.
