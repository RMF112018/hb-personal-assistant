# P00 — 05 Gated Live Reads (GET-only)

Captured: 2026-06-07

The operator approved running GET-only live reads **in addition to** the safe checks, contingent on the
gates already being enabled. This run **does not enable any disabled gate**. Every live read below is
recorded with its gate state; where the gate is OFF, the read is **skipped** (the safe, fail-closed
outcome). No writeback, no `--apply`, no `--confirm-live-get`, no payload dumps.

## Gate-state inventory (read-only)

| Gate | Source of truth | State | Live read decision |
|---|---|---|---|
| `HB_PROCORE_LIVE` | env var (`procore/live_gate.py`: must equal `"1"`) | **unset** | **skipped — gate OFF** |
| `HB_GRAPH_LIVE` | env var | **unset** | **skipped — gate OFF** |
| Scheduler `live_reads_enabled` | `scheduler status daily-source-refresh` | **false** | **skipped — gate OFF** |
| Dev source mode | launcher profile `source_refresh_mode` | **`mock_data`** | live source-refresh not applicable |

**Result: no gate is currently enabled, so all live external reads are correctly skipped.** This is the
package's intended default posture ("keep Dev live reads OFF by default").

## Auth posture observed (from safe status checks, no live calls)

- **Graph (mail)**: token `token_type: app_only`, `classification: unexpected` (delegated is the runtime
  default; an app-only token is flagged as unexpected by the status surface). `Mail.Read` scope present.
  UPN `bfetting@hedrickbrothers.com`, tenant `0e834bd7-…`.
- **Graph (files)**: `delegated_auth.available: true`, `classification: delegated`, on-demand token
  acquisition (no token acquired during status).
- **Procore**: `status: env_present`; OAuth cache present (`access_token_present: true`,
  `refresh_token_present: true`); **access token expired** (`expires_in_seconds_if_known: -25573`,
  ≈ 7h past expiry); keychain secret present; `ready_for_live_calls: true` but operator-gated. Even if
  the gate were enabled, a live GET would first require a token refresh.

## Conclusion

No live Graph or Procore API calls were made. The precheck honored the fail-closed gates and the
no-writeback / read-only runtime guardrails. The expired Procore token + app-only Graph mail token are
recorded as **auth-readiness findings** for later prompts (re-auth / refresh next-actions), not failures
of this precheck.
