# 10 — Override Expiration & Revocation Proof

`test_expired_and_revoked_override_no_longer_apply`:
- A `rows` override (max_value 999, expires in 1 min) raises the effective rows limit to 999.
- Advancing time +5 min (monkeypatch `overrides._now`) → the override is past `expires_ts`;
  `effective_limit("rows", …)` falls back to the base (100). **Expired overrides never apply.**
- After `store.revoke(override_id)` → `effective_limit` again returns the base. **Revoked
  overrides never apply.**

`_live()` filters out both revoked and expired records before any match, so both the effective
limit and the `hb_capability_mode` status reflect only live overrides. There is no indefinite
override (creation requires a positive `expires_minutes`).
