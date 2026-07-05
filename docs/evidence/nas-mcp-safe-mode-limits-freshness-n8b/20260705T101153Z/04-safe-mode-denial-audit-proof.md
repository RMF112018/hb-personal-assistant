# 04 — Safe Mode Denial Audit Proof

`test_safe_mode_denial_is_audited` — a safe-mode-denied AI Outputs write produces a 0600 audit
event with:
```json
{ "decision": "deny", "deny_reason": "safe_mode_active:ai_outputs_card_upsert",
  "safe_mode": true, "capability_tier": 3, "write_attempted": true }
```
The audit carries the authenticated actor/client context (from origin auth) and the
`capability_tier`; it never contains a token, body, or path payload. Every safe-mode denial
follows this shape (reason class `safe_mode_active:<tool>`).
