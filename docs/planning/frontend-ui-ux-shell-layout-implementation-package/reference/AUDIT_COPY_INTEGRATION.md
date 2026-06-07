# End-User Copy Remediation Integration

This file folds the attached `HB_Frontend_End_User_Copy_Remediation_Implementation_Package` into the shell/layout implementation plan. Treat copy cleanup as a required part of production readiness, not a later polish pass.

## Current copy debt confirmed

### App shell

- Visible local-development role selector.
- Header says `Local dev role — not production auth`.
- Footer says `No determinations... source, sync, evidence, and retrieval details`.
- Sidebar renders disabled Chat.
- Admin/Data Confidence naming should be reconsidered in favor of Data Health/Data Quality.

### Today

- Error state references FastAPI, pip install, and uvicorn.
- Daily Brief explains external Markdown workflow and lists internal status states.
- Section fallbacks use `JSON.stringify` snippets.
- Footer copy references composed read models and source/sync/evidence.

### Projects

- Copy explains navigation architecture instead of project outcomes.
- Empty state sends users to Admin rather than Settings/Data Health.
- Page feels like a route selector, not a project command center.

### My Items

- Copy mentions Outlook + Procore + local review state, Graph, first-sync Admin, and diagnostics.
- Work-queue purpose is good, but copy should be action-oriented and source-agnostic.

### Settings

- Largest copy-debt surface.
- Prompt IDs remain visible.
- Load/Test buttons are implementation-oriented.
- Keyword management shows JSON snippets.
- Daily Brief normal view exposes Markdown/MCP/scheduled prompt internals.

### Admin / Data Health

- Section labels are telemetry-oriented.
- Access-denied state refers to local dev role selector.
- Footer exposes `/api/admin/*`, read models, and ADC metric IDs.

## Copy standard to apply

Voice:
- Professional, plainspoken, construction-management-first.
- Explain outcome and next step, not implementation mechanics.
- Keep advisory posture compact.

Preferred label replacements:

| Current/internal | Preferred user-facing copy |
|---|---|
| Data Confidence | Data Health or Data Quality |
| Source / Sync Health | Source Updates |
| Workflow / Job Health | Background Tasks |
| Evidence / Guardrail Health | Safety Checks |
| Retrieval / AI Quality | Answer Quality |
| Permissions / Governance | Access & Permissions |
| Data Completeness / Coverage | Data Coverage |
| Load Accounts Status | Check connection status |
| Load Projects | Review project connections |
| Test detection | Check for today’s brief |
| Not configured / external AI setup required | Brief not set up / Brief source not connected |
| FastAPI/uvicorn/backend down | The local app service is not running. Restart the app and try again. |
| Admin approval / first sync | Waiting for update approval |

Forbidden production UI patterns:

- Prompt labels: `Prompt 14B`, `Prompt 20`, etc.
- Internal gap IDs: `FPR-004`, `ADC-001`, etc.
- Raw/debug wording: `raw panels`, `JSON.stringify`, `payload`, `response body`.
- Framework/server wording: `FastAPI`, `uvicorn`, `Vite`, `HMR`.
- Architecture wording in normal UI: `read model`, `route`, `endpoint`, `guardrail`, `retrieval`.
- Dev auth wording: `local dev role`, `not production auth`, visible `viewer/operator/admin` selector in normal chrome.

## Integration into implementation sequence

- Copy C01 maps into Prompt A.
- Copy C02 maps into Prompt B/F.
- Copy C03 maps into Prompt F.
- Copy C04 maps into Prompts C/D/E.
- Copy C05 maps into Prompt G.
- Copy C06 maps into Prompt B/H.
- Copy C07 and C08 map into Prompt I.

## Acceptance evidence expected

- Screenshot before/after for AppShell, Today, Projects, My Items, Settings, Admin/Data Health.
- Copy scan output showing no forbidden production strings.
- Manual validation notes confirming normal UI has no prompt IDs, framework/server terms, raw debug text, or local-dev auth copy.
- Confirmation that technical details, where retained, are admin-only and behind disclosure.
