# 17 — Audit Attribution Proof

Every dispatch audit event (`broker.dispatch`) now carries, in addition to the origin-auth
attribution (`authenticated`/`client`/`client_label`/`token_id`/`auth_method`/`actor`):
- `safe_mode` (bool),
- `capability_tier` (0/1/3/4/5),
- `rate_limit_result` (e.g. `write_rate_exceeded`, `write_rate_state_unavailable`, `too_many_concurrent_calls` — on limit / fail-closed denials),
- `override_id` (when an operator override affected the decision),
- `slow_tool` (post-hoc timeout flag).

Proven in-suite: `test_safe_mode_denial_is_audited` (safe_mode + reason class),
`test_write_window_blocks_repeated_writes` (rate_limit_result `write_rate_exceeded`),
`test_write_window_fails_closed_on_unreadable_or_corrupt_state` (rate_limit_result
`write_rate_state_unavailable`), `test_freshness_tier0_in_audit` (capability_tier). Override create writes a separate audit receipt (override_id + scope + client
+ reason + expiry).

**Never audited:** raw bearer tokens, Cloudflare tokens/service-token secrets, JWTs, private
keys, Text-Vault keys, MSAL caches, decrypted content, raw confidential payloads. The audit
records reason classes, counts, ids, and redacted labels only.
