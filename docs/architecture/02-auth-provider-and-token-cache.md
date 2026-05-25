# Phase 2: Auth Provider and Token Cache

**Status**: Complete (Prompt 02 executed 2026-05-25)  
**Version**: 0.2.0

## Scope
Implemented the full auth foundation required by the MVP:
- MSAL-based delegated (runtime default) and app-only (proof only) providers.
- TokenCacheManager with exact two-file layout and 700/600 permission enforcement (via PathPolicy).
- TokenClassifier (pure, strict fail-closed per 04 spec).
- Base GraphHttpClient (centralized, token-injected, paged, retried per 06 policy, sanitized errors — zero tokens/headers/full bodies ever logged or evidenced).

No mail/calendar/file read models yet (Phase 3/4). No M365 mutation. No Keychain (deferred).

## Architecture

```mermaid
flowchart TD
  CLI[CLI: hb-assistant auth login/status/logout/clear-cache<br/>diagnostics auth/graph --safe] --> Prov[Auth Providers<br/>DelegatedAuthProvider + AppOnlyAuthProvider]
  Prov --> TCM[TokenCacheManager<br/>MSAL SerializableTokenCache<br/>+ 2x .bin files @ 600]
  Prov --> TC[TokenClassifier<br/>scp/roles rules + require_delegated fail-closed]
  TCM <--> MSAL[MSAL Python<br/>PublicClient / ConfidentialClient]
  MSAL <--> DISK[Protected bins<br/>~/Library/Application Support/HB Personal Assistant/auth/<br/>msal-token-cache.bin<br/>msal-token-cache-app.bin<br/>(700 dir via PathPolicy)]
  Prov --> GHC[GraphHttpClient<br/>(token injection, @odata.nextLink paging,<br/>06 retry policy 429/5xx, sanitize)]
  GHC --> GRAPH[Microsoft Graph<br/>(safe probes only in Phase 2; /me etc.)]
  TC -.->|enforced by| DIAGS[diagnostics + future clients]
```

## Key Components

- `src/hb_assistant/auth/classifier.py`: `classify_token_claims`, `require_delegated`, `safe_redact_claims`.
- `src/hb_assistant/auth/token_cache_manager.py`: load/save/clear with exact filenames + chmod 600.
- `src/hb_assistant/auth/providers.py`: login (device_code preferred), get_token, status_info (always safe), logout.
- `src/hb_assistant/graph/http_client.py`: retry loop, paging iterator, GraphHttpError (sanitized).
- CLI updates in `cli/main.py` and `diagnostics.py` (real commands, --json always safe).

## Configuration & Paths
Reuses `AppConfig.identity` (tenant, client, scopes) and `PathPolicy` for auth dir + 700 enforcement (Phase 1).

Certificate for app-only: graceful fallback if `~/.secrets/hb-sharepoint-creator/hb-sharepoint-creator.bundle.pem` absent (Phase 0 location).

## CLI Surface (11 spec)
- `hb-assistant auth login [--app-only] [--no-device-code]`
- `hb-assistant auth status [--json] [--app-only]`
- `hb-assistant auth logout [--app-only]`
- `hb-assistant auth clear-cache [--app-only]`
- `hb-assistant diagnostics auth --json`
- `hb-assistant diagnostics graph --safe --json` (now uses real GraphHttpClient + delegated token attempt)

## Evidence & Validation
See `docs/evidence/phase-2-*` (facts, safe status schema, clean sensitive scan, full validation outputs).

All 8+ validation commands now produce real or graceful-safe JSON. `auth status --json` is fully functional and redacted.

## Decisions Recorded
- D-CLI-001 (Typer) carried forward.
- No new D- records; followed 04 model, 06 retry policy, 20 gates (no app-reg/Keychain changes), 19 privacy (zero secret material in evidence).

## Next
Prompt 03 (Delegated Graph Capability Proof) — first production-grade use of the new auth + GraphHttpClient primitives (must pass all 10 proof steps before any real mail/calendar retrieval).

## References
- `docs/plans/my-pa-phase-0/04_Auth_And_Permissions_Model.md`
- `docs/plans/my-pa-phase-0/02_Final_Implementation_Plan.md` (Phase 2)
- `docs/plans/my-pa-phase-0/11_CLI_Agent_And_Automation_Specification.md`
- `docs/plans/my-pa-phase-0/06_Graph_Integration_Specification.md`
- `docs/plans/my-pa-phase-0/baseline_inputs/token-cache-location-and-encryption(1).md`
- `docs/evidence/prompt-execution-log.md` (Prompt 02 section)
