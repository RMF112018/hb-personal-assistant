# Phase 3: Delegated Graph Capability Proof (Prompt 03)

**Status**: Implemented (Prompt 03 executed 2026-05-25)  
**Version**: 0.3.0

## Purpose
This is the **mandatory gate** (per 05_Delegated_Graph_Proof_Specification.md) before any production mail, calendar, or file retrieval workflows may be accepted.

The proof exercises the Phase 2 auth + GraphHttpClient foundation against the 10 required steps using safe, read-only queries only.

## Execution Assumption (User Directive)
> Any delegated permissions that are not currently granted on the app registration (especially `Mail.Read` and related scopes) will be granted during development, prior to deployment.

This means:
- 403 responses on mail-related steps (2, 3, 4, 6) during the initial proof run are expected and are documented as temporary.
- The proof script, CLI, and evidence are structured so that once the scopes are granted and a fresh delegated token is obtained, re-running the proof will produce 200 results for those steps.
- No app registration changes were performed as part of this phase (20_Manual_Approval_Gates.md honored).

## 10-Step Proof Summary

| Step | Target | Expected under full scopes | Evidence location |
|------|--------|----------------------------|-------------------|
| 1 | `/me` (safe select) | 200 + Bobby identity | `step-1.json` |
| 2 | Mail metadata (bounded) | 200 (or 403 until Mail.Read granted) | `step-2.json` |
| 3 | Message body | 200 or redacted access proof | `step-3.json` |
| 4 | Body mention ("Bobby") | Mention demonstrated in preview/body | `step-4.json` |
| 5 | `calendarView` (default window) | 200 + sanitized events | `step-5.json` |
| 6 | Attachment metadata | Metadata or "no sample" evidence | `step-6.json` |
| 7 | driveItem metadata | 200 + file/folder info | `step-7.json` |
| 8 | Controlled download (small eligible file) | Hash + size + MIME only (no content committed) | `step-8.json` |
| 9 | App-only rejection (mail/calendar) | Classification or 403 blocks it | `step-9.json` |
| 10 | Sensitive scan (repo + outputs) | Clean (no tokens/keys/PEMs/caches in artifacts) | `phase-3-sensitive-scan.json` |

## Key Artifacts Delivered

- `scripts/proofs/delegated_graph_capability_proof.py` — canonical, reproducible proof runner
- `hb-assistant diagnostics proof --delegated-graph --json` — CLI convenience entry point
- `tests/test_graph_proof.py` — redaction, classifier, and structure tests
- `docs/evidence/prompt-03-delegated-proof/` — per-step sanitized evidence + summary (produced on each run)
- This document

## Scope Requirements (for full green proof)

The following delegated scopes are required on the app registration for a completely successful proof:

- `User.Read`
- `Mail.Read`
- `Calendars.ReadWrite.Shared`
- `Files.ReadWrite.All`
- `offline_access`

(See `src/hb_assistant/config/models.py` defaults and the proof script's `REQUIRED_DELEGATED_SCOPES`.)

## Architecture Integration

The proof reuses the Phase 2 components without modification:

```
DelegatedAuthProvider.get_token()
        ↓
GraphHttpClient (token injection + 06 retry + paging + sanitize)
        ↓
10 safe Graph calls (exact patterns from 05 spec)
        ↓
_redact_for_evidence() + safe_redact_claims()
        ↓
docs/evidence/prompt-03-delegated-proof/step-N.json
```

App-only path (step 9) is exercised via `AppOnlyAuthProvider` + classifier to demonstrate fail-closed behavior for mail/calendar (per 04_Auth_And_Permissions_Model.md).

## Limitations / Known Gaps at Time of Proof

- Mail-related steps (2–4, 6) will return 403 until `Mail.Read` (and any other required mail scopes) are granted on the registration.
- Step 8 (download) only records hash/size/MIME/path — never full file content in evidence.
- Body mention (step 4) prefers `bodyPreview` when full body retrieval is still scope-limited.
- Step 10 (sensitive scan) is best executed via the CLI after the proof run.

Once the missing delegated scopes are granted, re-running the proof with a fresh token will produce the final "all steps green" evidence bundle.

## References

- [05_Delegated_Graph_Proof_Specification.md](../plans/my-pa-phase-0/05_Delegated_Graph_Proof_Specification.md) (the 10 steps, safe patterns, redaction rules)
- [04_Auth_And_Permissions_Model.md](../plans/my-pa-phase-0/04_Auth_And_Permissions_Model.md) (token classification + app-only rules)
- [06_Graph_Integration_Specification.md](../plans/my-pa-phase-0/06_Graph_Integration_Specification.md) (central client, retry policy)
- [20_Manual_Approval_Gates.md](../plans/my-pa-phase-0/20_Manual_Approval_Gates.md) (no app-reg changes performed)
- Phase 2 auth + Graph foundation (`src/hb_assistant/auth/`, `src/hb_assistant/graph/`)

**This proof is the hard gate. No production retrieval workflows are accepted until it is satisfied.**
