# 04 — Graph /me Command (sanitized)

## Container invocation (sanitized)
The inline snippet was staged to a NAS temp path and executed **inside** the container with the backend `CMD`
overridden by `python`. `--network host` was used (bridge DNS instability; see 00/N5C-A). No ports bound (outbound
HTTPS client only).

```
# stage snippet (bfetting-writable temp), then:
sudo /usr/local/bin/docker run --rm --network host --user 1028:100 \
  -e HB_PA_CONFIG=/config/hb-pa-config.yml \
  -e HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1 \
  -v <NAS-CONFIG-YML>:/config/hb-pa-config.yml:ro \
  -v /volume1/personal-assistant/app-support:/volume1/personal-assistant/app-support \
  -v /volume1/personal-assistant/runtime/n5c-b-me.py:/app/n5c-b-me.py:ro \
  hb-personal-assistant:nas \
  python /app/n5c-b-me.py
# then remove the temp snippet from the NAS
```

- `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` — no watchers/scheduler.
- app-support mounted so the cache is readable; **no vault, no source-root, no writable-DB mount for scan/card work.**
- `script_written=yes`, `script_removed=yes` (temp snippet deleted after the run).

## Snippet (repo-truth auth reuse, sanitized output only)
```python
import sys, json, hashlib, urllib.request
sys.path.insert(0, "/app/src")
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.auth.providers import DelegatedAuthProvider
cfg = load_config()
pp = PathPolicy(cfg)
prov = DelegatedAuthProvider(cfg.identity.tenant_id, cfg.identity.client_id,
                             cfg.identity.delegated_scopes, path_policy=pp)
res = prov.get_token(["User.Read"])            # silent — reads existing NAS cache
tok = res["access_token"]                      # never printed
req = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
                             headers={"Authorization": "Bearer " + tok})   # never printed
r = urllib.request.urlopen(req, timeout=15)
body = json.loads(r.read().decode("utf-8"))
upn = body.get("userPrincipalName") or ""
out = {
  "status": "ok", "graph_endpoint": "/v1.0/me", "http_status": r.status,
  "content_type": (r.headers.get("Content-Type") or "").split(";")[0],
  "response_keys": sorted(body.keys()),
  "account_proof": {
    "upn_sha256_12": hashlib.sha256(upn.encode("utf-8")).hexdigest()[:12] if upn else None,
    "id_present": "id" in body, "mail_present": bool(body.get("mail")),
    "displayName_present": "displayName" in body,
  },
  "raw_body_printed": False, "tokens_printed": False,
}
print(json.dumps(out))                          # sanitized metadata only
```

The token, the `Authorization` header, and the raw Graph body are held only in process memory and are **never**
printed. Only key names, presence booleans, and a truncated UPN hash are emitted.
