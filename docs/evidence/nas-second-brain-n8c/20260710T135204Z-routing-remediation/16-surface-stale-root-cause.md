# Surface-stale after manifest promote — root cause

**Date:** 2026-07-10  
**Symptom:** `pa_tool_manifest_freshness_check` → fresh; `pa_prompt_route` on `document_session` → `blocked surface_stale`.

## Two different freshness checks

| Check | What it compares | Operator saw |
| --- | --- | --- |
| `pa_tool_manifest_freshness_check` | Live tool **names** vs persisted manifest | `stale False` |
| `pa_tool_surface_freshness_check` / `pa_prompt_route` | Live routing **classification** vs persisted manifest entries | `stale True` → write routes blocked |

Manifest promote succeeded. Name-level manifest is current. Write-route gate still saw classification drift.

## Root causes (code)

### 1. `get_active()` dropped `tool_family` (primary — 145/145 false family drift)

`save_manifest()` writes full semantic payload (including `tool_family`) to `manifest_payload_json`, but `get_active()` rebuilt `entries` from a narrow SQL select (`tool_name`, `tool_class`, `safety_class`, `read_write_class` only). `live_freshness()` then compared live families against `None` → every tool flagged `family_changed`.

### 2. Promote omitted `surface_profile` (profile drift)

`build_manifest()` on stage/promote did not pass `surface_profile_label()` / `gate_state_snapshot()`. Stored profile was `unknown`; live NAS profile is `remote_cloudflare` → `profile_context_changed`.

### 3. `build_tool_entry()` classification parity (43 class drift)

`build_tool_entry()` used family-level defaults for `read_write_class` / `safety_class` while manifest entries use per-tool `classify_tool()`.

## Fixes (repo)

1. `ClientToolManifestRepository.get_active()` hydrates `tool_family` from `manifest_payload_json` (legacy DB rows fall back to `family_for_tool`).
2. Stage/promote/bootstrap `build_manifest()` calls pass `surface_profile`, `gate_state_snapshot`, and `gateway_allowlist`.
3. `build_tool_entry()` uses `classify_tool()` for classification fields.

Regression tests: `test_get_active_hydrates_tool_family_from_manifest_payload`, `test_persisted_manifest_agrees_with_live_surface_freshness`.

## Operator path after fix lands

1. Build + deploy NAS image (new `HB_RUNTIME_COMMIT`).
2. Re-run manifest refresh (stage → promote) so stored `generated_from_runtime_commit` matches live deploy SHA.
3. Run `15-manifest-verify-only.sh` — expect step **4b** `stale false` and step **5** not `surface_stale`.

Transfer on Synology (no `scp` subsystem):

```bash
ssh hb-nas 'cat > /tmp/hb-manifest-verify-only.sh' < docs/evidence/nas-second-brain-n8c/20260710T135204Z-routing-remediation/15-manifest-verify-only.sh
ssh -t hb-nas 'sudo sh /tmp/hb-manifest-verify-only.sh' | tee ~/manifest-verify-only.txt
```