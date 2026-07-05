# 09 — cloudflared Restart Proof — HOLD

**Status: HOLD** — deferred to the live-activation sub-phase. A full N8B PASS requires proving the connector **restarts after failure** and **starts after NAS reboot**. That requires promoting `restart: "no"` → `restart: unless-stopped` + a DSM boot task (`11`), which is a deliberate authorized step, not part of this foundation.

When executed: kill the connector container → observe auto-restart; reboot the NAS → observe the connector (and MCP) come back without an SSH session. Redacted evidence captured here.
