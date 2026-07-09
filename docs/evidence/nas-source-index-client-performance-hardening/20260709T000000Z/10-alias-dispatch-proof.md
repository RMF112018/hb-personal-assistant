# 10 — assistant_output_* alias dispatch proof

## Gate decision

| Item | Status |
|------|--------|
| Root cause identified | **PASS** |
| Code fix committed (`fa266c52…`) | **PASS** |
| Local regression + inventory tests | **PASS** |
| Live all 10 aliases callable | **PENDING** (redeploy required) |
| Push/PR | **NOT AUTHORIZED** |

## Root cause

`NasMcpBroker.dispatch` evaluated `tool_name.startswith("assistant_")` **before** the
client-output branch (`ALL_PA_OUTPUT_TOOLS | ASSISTANT_OUTPUT_ALIASES`).

All ten `assistant_output_*` names matched the broad catch-all, entered
`_invoke_assistant` (nav path), and raised:

```text
tool_not_registered: assistant_output_stage
```

(and the same for the other nine aliases). FastMCP still listed the tools (registration
in `tool_registration.py` was correct); only broker routing was wrong.

`dispatch_client_output_tool` already remaps:

```python
if tool_name.startswith("assistant_output_"):
    tool_name = "pa_output_" + tool_name[len("assistant_output_"):]
```

so handlers were ready once routing reached them.

## Fix

In `src/hb_assistant/nas_mcp/broker.py`: run the client-output dispatch block **before**
the `startswith("assistant_")` catch-all. Preserve:

- `pa_output_*` compatibility
- gateway allowlist membership for aliases
- write-gate behavior (`CLIENT_OUTPUT_WRITE_TOOLS` includes both `pa_` and `assistant_` write names)

HEAD: `fa266c5293757fdd907eb2e8fba8c0424abe801f`  
Branch: `ops/source-index-client-performance-hardening-20260709`

## Local validation

Artifacts: `10-alias-dispatch-pytest.txt`

Focused suites (all green):

- `tests/test_n8c24_output_mcp_tools.py` (new alias parity + gateway gate tests)
- `tests/test_n8c24_output_safety_negative.py`
- `tests/test_source_index_client_performance_hardening.py`
- `tests/test_n8c_mcp_tool_inventory_final.py`
- `tests/test_n8c_client_exposure_bridge.py`

New regressions prove broker-callable parity for:

`stage`, `commit`, `archive_plan`, `archive_commit`, `metadata`, `list`, `read_excerpt`,
`receipt_get`, `manifest_get`, `zip_inspect` — plus FastMCP fn path + `hb_assistant_tool_query`
gateway path for `assistant_output_stage`.

## Live pre-redeploy (current host image)

Endpoint: `https://nas-mcp.bobby-fetting.me/mcp`  
Artifact: `10-alias-dispatch-live-pre-redeploy.json`

| Check | Result |
|-------|--------|
| All 10 aliases in tools/list | **PASS** (True) |
| All 10 callable (no tool_not_registered) | **FAIL** (False) |

Every alias call returned `tool_not_registered` — expected until the fix image is loaded.

## Staged deploy (operator sudo required)

```
tag=hb-nas-alias-fix-fa266c529375
head=fa266c5293757fdd907eb2e8fba8c0424abe801f
image_id=sha256:533bb295a0d9ec50584ca3ca1c0d2bc62bf43fa5bb86722f9ff5816008438e48
tarball=/tmp/hb-nas-alias-fix-fa266c529375.tar.gz
local_sha256=693924a8b19c2fe477e3df51219acf1c91de440203d0ec7a120a8bb86d25244e
nas_sha256=693924a8b19c2fe477e3df51219acf1c91de440203d0ec7a120a8bb86d25244e
nas_path=/tmp/hb-nas-alias-fix-fa266c529375.tar.gz
operator_script=/tmp/hb-deploy-alias-fix.sh
fix=assistant_output_alias_broker_dispatch
```

Operator resume (interactive sudo on NAS):

```sh
ssh hb-nas
sh /tmp/hb-deploy-alias-fix.sh
```

Then re-run the alias-only live probe (stage/commit/archive via **assistant_output_*** only;
no `pa_output_*` fallback) and attach results as
`10-alias-dispatch-live-post-redeploy.json` / update this note.

## Cleanup ledger

| Artifact | Disposition |
|----------|-------------|
| Live temp outputs this probe | None created (stage failed pre-redeploy) |
| NAS image tarball `/tmp/hb-nas-alias-fix-fa266c529375.tar.gz` | Staged for load; remove after successful deploy |
| Origin bearer token | Not written to evidence |

## Recommendation

1. Operator runs staged deploy script.
2. Agent/operator re-probes all 10 aliases live + output cases 7–9 with **assistant_output_*** only.
3. Only then consider push/PR authorization.

**No push, no PR from this agent.**
