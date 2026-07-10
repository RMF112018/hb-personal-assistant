# Post-deploy validation

## Agent read-only checks (no sudo)

From `ssh hb-nas` without docker access:

```text
GET /health -> {"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}
POST /mcp (unauth) -> 401
```

## Deploy-script gates (operator transcript)

| Check | Pass |
| --- | --- |
| Schema head 119 | yes |
| quick_check ok | yes |
| V118 manifest columns | yes (2/2) |
| V119 bootstrap_runs table | yes |
| manifest row count unchanged | yes (0 -> 0) |
| RO snapshot at head 119 | yes |
| MCP restarted on new image | yes |
| Health endpoint | yes |
| Origin auth 401 | yes |
| Runtime commit assert (phase 7) | yes (script would have aborted on mismatch) |

## Non-blocking warnings

1. **`source-watch status` traceback** — `borrow_connection` failure when reading bootstrap state from the RO snapshot DB inside the container. Does not affect core MCP deploy; bootstrap `--dry-run --all-roots` still returned structured JSON.
2. **Bootstrap dry-run `root_found: false` for 4 roots** — dry-run executed inside container but reported no files seen for vault/work/home/macbook_backup. Requires separate operator review of `external_sources` mount mapping before any apply (deferred by policy).
3. **Phase 7/9 docker exec stdout empty** — Synology/docker exec heredoc quirk; phase 7 failure would have aborted the script.

## Live runtime identity (operator probe 2026-07-10)

```text
runtime_identity= RuntimeIdentity(runtime_commit='14dfc3a0e007475543e19f1d8efd999b23f3e28b', ..., runtime_identity_kind=exact_commit)
runtime_commit= 14dfc3a0e007475543e19f1d8efd999b23f3e28b
```

**PASS** — exact commit identity verified in live container.

## Live routing acceptance (Phase 10)

Route plan fields are **not** top-level `workflow_id` / `blocked_reason`. Use:

- `recommended_workflow` (workflow)
- `authorization.execution_blocked_reason`
- `authorization.currently_executable`

An initial probe printed `None` for all routes because of wrong key names; routing engine was still invoked.

**Corrected operator probe:**

```bash
ssh -t hb-nas 'sudo /usr/local/bin/docker exec hb-personal-assistant-mcp python3 -c "
from hb_assistant.nas_mcp.broker import runtime_identity, runtime_commit, NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig
print(\"runtime_commit=\", runtime_commit())
b = NasMcpBroker(NasMcpConfig.from_env())
for p in [\"Do not promote anything.\", \"Stage this for review.\", \"Search my work files.\", \"Search the vault for meeting notes.\", \"Promote the approved artifact.\"]:
    r = b.dispatch(\"pa_prompt_route\", {\"prompt\": p})[\"result\"]
    a = r.get(\"authorization\") or {}
    print(p, \"->\", r.get(\"recommended_workflow\"), a.get(\"execution_blocked_reason\"), a.get(\"currently_executable\"))
"'
```

**Expected (from route-proof-matrix):**

| Prompt | `recommended_workflow` | `execution_blocked_reason` |
| --- | --- | --- |
| Do not promote anything. | not `apply_canonical_promotion` | — |
| Stage this for review. | `stage_artifact_proposals` | `missing_arguments` |
| Search my work files. | `source_file_search` | null or `missing_arguments` |
| Search the vault for meeting notes. | `vault_note_search` | — |
| Promote the approved artifact. | `apply_canonical_promotion` | `approval_required` or `missing_arguments` |

Pre-deploy proxy: matrix 20/20, smoke 21/21, targeted pytest green.

## Live routing probe (operator 2026-07-10) — PASS

See `04-live-routing-probe.md`. Summary:

```text
runtime_commit=14dfc3a0e007475543e19f1d8efd999b23f3e28b
Do not promote -> context_preflight (not apply_canonical_promotion)
Stage -> stage_artifact_proposals / missing_arguments / False
Work files -> source_file_search
Vault notes -> vault_note_search
Promote -> apply_canonical_promotion / missing_arguments / False
```

## Manifest / freshness

```text
active_manifest_revision=none (0 rows in pa_client_tool_manifests)
manifest_schema_version=n/a
freshness_state=n/a (no persisted active manifest)
auto_stage_occurred=false
auto_promote_occurred=false
vault_manifest_files_changed=not verified (no vault writes authorized)
```

Manifest automation flags remain unset in compose (`HB_MCP_MANIFEST_*` not enabled).