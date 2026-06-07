# End-User Copy Standard

## Voice

- Professional, plainspoken, construction-management-first.
- Explain outcome and next step, not implementation mechanics.
- Keep advisory posture compact; do not overstate conclusions.

## Preferred labels

- `Data Health` instead of `Data Confidence` where practical.
- `Source Updates` instead of `Source / Sync Health`.
- `Background Tasks` instead of `Workflow / Job Health`.
- `Safety Checks` instead of `Evidence / Guardrail Health`.
- `Answer Quality` instead of `Retrieval / AI Quality`.
- `Access & Permissions` instead of `Permissions / Governance`.
- `Data Coverage` instead of `Data Completeness / Coverage`.
- `Check connection status` instead of `Load Accounts Status`.
- `Review project connections` instead of `Load Projects`.
- `Check for today’s brief` instead of `Test detection`.

## Status copy

- Not connected
- Connected
- Needs sign-in
- Updating connection
- Waiting for admin approval
- Ready to update
- Some information may be out of date
- Nothing needs attention here right now
- The local app service is not running. Restart the app and try again

## Forbidden production UI patterns

- Prompt labels: `Prompt 14B`, `Prompt 20`, etc.
- Internal gap IDs: `FPR-004`, `ADC-001`, etc.
- Raw/debug wording: `raw panels`, `JSON.stringify`, `payload`, `response body`.
- Framework/server wording: `FastAPI`, `uvicorn`, `Vite`, `HMR`.
- Architecture wording: `read model`, `route`, `endpoint`, `guardrail`, `retrieval`.
- Dev auth wording: `local dev role`, `not production auth`, `viewer/operator/admin` in normal chrome.

## Advanced/technical details

Technical details may remain only if:

1. The user is on an admin page.
2. The detail is behind a collapsed `Technical details` disclosure.
3. It contains no tokens, secrets, raw content, signed URLs, download URLs, or cache paths.
