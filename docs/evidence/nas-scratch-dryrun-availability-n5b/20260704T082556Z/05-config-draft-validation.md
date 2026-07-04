# 05 — Config Draft Validation

Validated the N5A drafts **and** the N5B scratch configs, non-destructively, against repo truth. No config was placed
or activated.

## Method
Parsed each file (YAML/JSON), asserted required keys + expected NAS paths + all activation flags off, then loaded each
Obsidian-MCP config through the **real** `ObsidianMcpConfig` model the way the production loader does (forward-compat
filter to known fields, then `model_validate`). Secret-pattern scan on every file.

## Results
```
n5a_draft_parse=ok  flags_off=ok  synwork_readonly+disabled=ok  no_secrets=ok
n5b_scratch_parse=ok  flags_off=ok  synwork_readonly+disabled=ok  appsupport_is_scratch=ok  no_secrets=ok

n5a: model_validate(after forward-compat filter)=ok  ENABLED_ROOTS=[]  index=False watch=False card_autogen=False summary_autogen=False
n5b: model_validate(after forward-compat filter)=ok  ENABLED_ROOTS=[]  index=False watch=False card_autogen=False summary_autogen=False
```
- Both configs point at the NAS vault `/volume1/personal-assistant/vault/obsidian`.
- N5B `application_support_root` = the `app-support-smoke/n5b-…` **scratch** path (asserted **not** production
  app-support).
- `syn-work` = `/volume1/homes/bfetting/Work`, `enabled=false`.
- **`ENABLED_ROOTS=[]`** for both → if either config were loaded, **no root would register or ingest**.
- No bearer token / secret-looking values in any file.

## SCHEMA FINDING (code-quality / hardening — no longer the active blocker) — `read_only` is not a config field

> **Update (post-ACL, 2026-07-04):** This finding no longer blocks — `syn-work` read-only is now enforced at the
> filesystem/ACL layer (proven in `13`). It is retained below as a code-quality / future-activation hardening item:
> the config schema should eventually offer a real, enforced read-only control so activation does not rely solely on
> per-path ACLs.
`ExternalSourceRoot` fields = `[source_root_key, path, enabled, source_kind, sensitive]`, with `extra=forbid`. There
is **no `read_only` field**. Consequences:
- Strict `model_validate` on the raw draft **rejects** `read_only` (and the `_note` annotation) as `extra_forbidden`.
- The production forward-compat loader (`load_config_with_warnings` / dry-run `_load_config`) **silently drops**
  unknown keys → `read_only=true` is **documentary only** and evaporates at load time:
  ```
  DROPPED-by-loader keys on syn-work = ['read_only', '_note']
  ```
- `sensitive` **does** exist and currently resolves to `False` for `syn-work`.

**Implication:** the N5/N5A plan's reliance on a config-level `read_only=true` control for `syn-work` is **not
schema-enforced**. The read-only control now comes from the **filesystem/ACL** instead (svc `r-x…` ACL + proven
write-denial, `13`), which is authoritative and sufficient for the current bounded posture. The drafts remain safe
because `enabled=false` (nothing registers), and `read_only` in a config must not be treated as an enforced control
until the schema honors it. Adding a schema-honored `read_only` (or wiring the existing `sensitive` field) is retained
as a future-activation hardening item (`11`), not a blocker.
