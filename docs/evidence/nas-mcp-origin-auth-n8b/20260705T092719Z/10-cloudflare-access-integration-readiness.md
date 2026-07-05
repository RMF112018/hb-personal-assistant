# 10 — Cloudflare Access Integration Readiness

## Two independent layers (defense-in-depth)
1. **Edge — Cloudflare Access** authenticates the human/agent at `mcp.bobby-fetting.me`
   before traffic reaches cloudflared. (Not live yet; operator sub-phase.)
2. **Origin — this phase** authenticates the MCP *client* at `nas_mcp:8765` with a bearer
   token, independent of any Cloudflare header. If Access is misconfigured, bypassed, or
   disabled, the origin still rejects unauthenticated MCP.

**No insecure bypass.** The origin never trusts `CF-Access-*` headers or "requests from
cloudflared" as authentication. Access is necessary-but-not-sufficient; origin auth is
enforced regardless.

## Client header model
| client | edge (Access) | origin (this phase) |
|---|---|---|
| Claude Desktop / ChatGPT (interactive) | Access login (SSO/OTP) in the MCP OAuth/browser flow | `Authorization: Bearer <origin token>` in MCP config |
| service-token / headless | `CF-Access-Client-Id` + `CF-Access-Client-Secret` | **also** `Authorization: Bearer <origin token>` |

### Dual-header constraint (HOLD → later sub-phase)
A service-token client must send **both** the Access service-token headers **and** the
origin `Authorization` bearer. If a given client cannot attach both header sets, the
acceptable design is a **local bridge** on the NAS/approved host that (a) sits behind
Cloudflare Access, (b) translates the client's auth into the origin bearer, (c) never
exposes raw NAS surfaces, (d) does not broaden MCP capabilities, (e) is audited. This is
the same posture the foundation flagged for Grok (no native MCP → secure bridge). **Not
built this phase.**

## Blockers before full N8B PASS (edge side)
- Operator creates the tunnel + Access self-hosted app; provides the tunnel token out-of-repo.
- Prove Access denies unauthenticated at the edge (foundation `48`/`49`).
- Prove each client path (Claude / ChatGPT / Grok-bridge) end-to-end through Access **and** origin auth.
- Rollback/disable proof.
