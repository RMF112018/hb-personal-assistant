# 10 — assistant_output_* alias dispatch proof

## Gate decision

| Item | Status |
|------|--------|
| Root cause identified | **PASS** |
| Code fix committed (`fa266c52`) | **PASS** |
| Local regression + inventory tests | **PASS** |
| Live all 10 aliases listed | **PASS** |
| Live all 10 aliases callable | **PASS** |
| Live cases 7–9 via `assistant_output_*` only | **PASS** |
| Push/PR | **NOT AUTHORIZED** (explicit operator authorize still required) |

## Root cause

`NasMcpBroker.dispatch` evaluated `tool_name.startswith("assistant_")` **before** the
client-output branch (`ALL_PA_OUTPUT_TOOLS | ASSISTANT_OUTPUT_ALIASES`).

Aliases entered `_invoke_assistant` and raised `tool_not_registered`. FastMCP listing was
correct; broker routing was wrong. `dispatch_client_output_tool` already remaps aliases to
`pa_output_*` handlers.

## Fix

`src/hb_assistant/nas_mcp/broker.py`: client-output dispatch **before** the `assistant_*`
catch-all. Preserves `pa_output_*`, gateway allowlist, and write gates.

| Field | Value |
|-------|-------|
| Fix commit | `fa266c52` |
| Branch | `ops/source-index-client-performance-hardening-20260709` |
| Evidence tip (this update) | `8095d170f04885d65a39cb9ea0d18bdd7e950199` |

## Local validation

Artifact: `10-alias-dispatch-pytest.txt` (**EXIT:0**)

- `tests/test_n8c24_output_mcp_tools.py` — full 10-alias broker/FastMCP/gateway parity
- inventory / exposure / source-index alias asserts

## Live pre-redeploy

Artifact: `10-alias-dispatch-live-pre-redeploy.json`

- 10/10 listed, **0/10 callable** (`tool_not_registered`) — expected on pre-fix image

## Operator deploy

```
sh /tmp/hb-deploy-alias-fix.sh
# load image → runner stop/start → health_ok
```

Build meta: `10-alias-dispatch-build-meta.txt`

## Live post-redeploy (alias-only)

Artifact: `10-alias-dispatch-live-post-redeploy.json`  
Endpoint: `https://nas-mcp.bobby-fetting.me/mcp`  
Auth: origin bearer from App Support (not stored)  
**No `pa_output_*` fallback** — all calls used `assistant_output_*`.

| Check | Result |
|-------|--------|
| tools/list aliases | **10/10** |
| exposed assistant tools | **87** |
| structure default-ON | **true** |
| client_output_write_enabled | **true** |
| All 10 aliases callable | **PASS** |
| Case 7 stage→commit md | **PASS** (`OUTPUT-20260709-006`) |
| Case 8 stage→zip_inspect→commit | **PASS** (`OUTPUT-20260709-007`) |
| Case 9 archive_plan→archive_commit | **PASS** (both archived) |

### Alias callable score

| Alias | OK |
|-------|----|
| `assistant_output_stage` | **PASS** |
| `assistant_output_commit` | **PASS** |
| `assistant_output_archive_plan` | **PASS** |
| `assistant_output_archive_commit` | **PASS** |
| `assistant_output_metadata` | **PASS** |
| `assistant_output_list` | **PASS** |
| `assistant_output_read_excerpt` | **PASS** |
| `assistant_output_receipt_get` | **PASS** |
| `assistant_output_manifest_get` | **PASS** |
| `assistant_output_zip_inspect` | **PASS** |

### Cases 7–9

| # | Result | Tools |
|---|--------|-------|
| 7 | **PASS** | `assistant_output_stage, assistant_output_commit` |
| 8 | **PASS** | `assistant_output_stage, assistant_output_zip_inspect, assistant_output_commit` |
| 9 | **PASS** | `assistant_output_archive_plan, assistant_output_archive_commit, assistant_output_list` |

## Cleanup ledger

| Artifact | output_id | Disposition |
|----------|-----------|-------------|
| alias-postdeploy-temp-md | `OUTPUT-20260709-006` | archived |
| alias-postdeploy-temp-zip | `OUTPUT-20260709-007` | archived |
| Origin bearer token | — | Not written to evidence |
| NAS image tarball | `/tmp/hb-nas-alias-fix-fa266c529375.tar.gz` | May remove after successful deploy |

## Recommendation

Live alias dispatch residual is **closed**. Functional path and client-facing alias path both work.

**No push/PR from this agent** until you explicitly authorize.
