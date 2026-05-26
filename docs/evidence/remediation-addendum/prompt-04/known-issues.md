# Addendum Prompt 04 Known Issues

## Open blockers from this proof rerun

1. Local path permission/writability is still not healthy:
   - `hb-assistant diagnostics paths --json` shows app support/auth/db/cache/log/evidence paths as non-writable.
2. Delegated auth cannot complete in this environment due DNS/network resolution to Microsoft login endpoint.
3. Graph diagnostics and delegated proof cannot reach Graph status responses; proof remains `blocked_no_token`.

## Next action guidance

1. Repair local path permissions first using `diagnostics paths` recommendations.
2. Re-check delegated login reachability (DNS/network) and retry `auth status`/`auth login`.
3. Re-run graph diagnostics and delegated proof only after both local readiness and auth reachability are healthy.
