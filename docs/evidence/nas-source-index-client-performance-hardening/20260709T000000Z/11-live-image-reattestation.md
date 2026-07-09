# 11 — Live image re-attestation (no redeploy)

## Purpose

Reconcile **PR #288 head** with the **currently serving** NAS MCP image after the
FIX_BEFORE_MERGE audit finding that the live image is an undocumented rebuild relative
to a pure PR-tip stamp, while remaining code-equivalent by introspection.

**No redeploy** was performed for this note. Live state was re-probed only.

## Identities

| Item | Value |
|------|-------|
| PR | #288 |
| PR head (validated tip at open) | `77bd67d565c0dbeaf94b8e280bb9632c868ec0f0` |
| Alias-dispatch fix commit | `fa266c5293757fdd907eb2e8fba8c0424abe801f` |
| Live image digest/config | `sha256:c8a04da8…` (`sha256:c8a04da81bd235b688bca8664cd6d4e685534c0051c790627ff219bf49114341`) |
| Redeploy this session | **No** |

## Finding

The live image is an **undocumented rebuild** (image config/digest not equal to a git-SHA
image tag of `77bd67d565c0dbeaf94b8e280bb9632c868ec0f0`), but is **code-equivalent to PR head** by introspection:

- `fa266c52..77bd67d5` is **docs-only** (evidence commits).
- Alias-before-catchall dispatch from `fa266c52` is present live.
- Surface counts match PR expectations (87 / 14 / structure ON).

### Commits `fa266c52..77bd67d5` (docs-only)

```
77bd67d5 docs(evidence): live post-redeploy 10/10 assistant_output alias dispatch PASS
8095d170 docs(evidence): assistant_output alias dispatch fix proof (local green, live pending redeploy)
```

## Distinguish historical matrix evidence

| Evidence | When / tip context | What it proves |
|----------|--------------------|----------------|
| `09-postdeploy-live-matrix.*` | Post operator source-index deploy; branch tip chain around `974becc2` / later evidence commits | **13/13** functional connected-client matrix on the then-serving image |
| `10-alias-dispatch-live-post-redeploy.json` | After `hb-deploy-alias-fix.sh` load of alias-fix image | **10/10** `assistant_output_*` callable + cases 7–9 |
| **This file (`11-…`)** | Current serving image re-probe, no redeploy | Re-attests live image identity + surface/dispatch proof points |

Do **not** use `09` alone as proof of the current image digest; use `10` + `11` for the
alias-fix image generation.

## Live proof points (re-probe)

| Proof | Observed |
|-------|----------|
| installed tools (canonical assistant) | **87** |
| groups | **14** |
| `has_index_health` | **true** |
| `has_query_plan` | **true** |
| `structure_default_on` | **true** |
| structure tools present | **7** |
| `alias_before_catchall` | **true** (assistant_output_stage dispatches; no tool_not_registered) |
| `assistant_output_stage` callable live | **true** → commit → archive (`OUTPUT-20260709-008`) |

Endpoint: `https://nas-mcp.bobby-fetting.me/mcp` (origin bearer; token not stored).

## Cleanup

| Artifact | Disposition |
|----------|-------------|
| `OUTPUT-20260709-008` (reattest-probe) | archived after stage/commit |
| Bearer token | not written to evidence |

## Constraints honored

- No merge of PR #288
- No deploy / image load
- No source-structure live scan
- No launchd install/load
- No gate/credential/tunnel/firewall/runner/Cloudflare changes
