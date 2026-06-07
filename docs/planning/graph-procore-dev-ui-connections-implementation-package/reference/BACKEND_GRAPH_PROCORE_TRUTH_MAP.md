# Backend Graph and Procore Truth Map

Graph safe state: configured, account label if safe, token present/stale boolean, expiry if safe, granted/missing scopes, last local sync, live-disabled reason.

Procore safe state: configured, token present/stale boolean, company/account label if safe, mapped project count from local mapping/config, mapping warnings, last local sync, live-disabled reason.

Do not expose tokens, secrets, raw payloads, cache paths, raw bodies, or join URLs.
