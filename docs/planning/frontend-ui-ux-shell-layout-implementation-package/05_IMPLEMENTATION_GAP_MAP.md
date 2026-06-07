# Implementation Gap Map

The local agent must close all P0 and P1 gaps before the implementation is considered ready for operator validation. P2 items are required when they are regression safeguards or directly adjacent to touched files.

| Gap ID | Severity | Title | Prompt placement | Source |
|---|---:|---|---|---|
| `UIUX-P0-001` | P0 | Shell is not constrained to viewport height; main scroll can expand the full app shell | Prompt A | ui_ux_shell_layout_audit |
| `UIUX-P0-002` | P0 | Sidebar footer lacks a dedicated pinned status/action zone | Prompt A / Prompt F | ui_ux_shell_layout_audit |
| `COPY-P0-001` | P0 | Local dev role selector is visible in normal app chrome | Prompt A / Copy C01 | ui_ux_shell_layout_audit |
| `COPY-P0-002` | P0 | Settings and account connection surfaces still expose prompt IDs and dev guidance | Prompt B / Prompt F / Copy C02-C03 | ui_ux_shell_layout_audit |
| `COPY-P0-003` | P0 | Frontend only partially consumes normalized readiness/account/data-quality routes | Prompt B / Prompt F / Copy C02 | ui_ux_shell_layout_audit |
| `UIUX-P1-001` | P1 | Primary pages use linear stacked layouts instead of reusable dashboard/masonry primitives | Prompt B / Prompt C / Prompt D / Prompt E | ui_ux_shell_layout_audit |
| `UIUX-P1-002` | P1 | Today page hierarchy is diluted by duplicated headings, wide cards, and technical Daily Brief/status copy | Prompt C / Copy C04 | ui_ux_shell_layout_audit |
| `UIUX-P1-003` | P1 | Projects page is sparse and not ready for project-intelligence onboarding | Prompt D / Copy C04 | ui_ux_shell_layout_audit |
| `UIUX-P1-004` | P1 | My Items is a work queue but lacks prioritization and masonry layout | Prompt E / Copy C04 | ui_ux_shell_layout_audit |
| `COPY-P1-001` | P1 | Admin/Data Confidence copy is telemetry-oriented and exposes development access guidance | Prompt F / Copy C05 | ui_ux_shell_layout_audit |
| `COPY-P1-002` | P1 | Disabled Chat is visible in production navigation | Prompt A / Copy C01 | ui_ux_shell_layout_audit |
| `UIUX-P2-001` | P2 | Empty, loading, and error states are visually weak and sometimes expose technical instructions | Prompt B / Prompt H / Copy C06 | ui_ux_shell_layout_audit |
| `UIUX-P2-002` | P2 | Responsive behavior is present but not intentionally specified or regression-tested for shell overflow | Prompt H / Prompt I | ui_ux_shell_layout_audit |
| `COPY-P2-001` | P2 | Daily Brief copy exposes Markdown/MCP/scheduled prompt internals in normal view | Prompt C / Prompt F / Copy C03-C04 | ui_ux_shell_layout_audit |
| `COPY-P2-002` | P2 | No dedicated production display-copy regression harness | Prompt I / Copy C08 | ui_ux_shell_layout_audit |
| `UIUX-P3-001` | P3 | Future onboarding/auth/sync/data-quality surfaces need reserved shell placement now | Prompt F | ui_ux_shell_layout_audit |
| `COPY-P0-001` | P0 | Local dev role selector is visible in normal app chrome | Prompt C01 | end_user_copy_remediation_package |
| `COPY-P1-002` | P1 | Disabled Chat remains visible as a support-nav item | Prompt C01 | end_user_copy_remediation_package |
| `COPY-P0-003` | P0 | Frontend does not consume new normalized auth/readiness contract | Prompt C02 | end_user_copy_remediation_package |
| `COPY-P0-004` | P0 | Settings still exposes prompt IDs, loader actions, raw-panel remnants, and backend workflow labels | Prompt C03 | end_user_copy_remediation_package |
| `COPY-P1-005` | P1 | Keyword management exposes project keys, JSON.stringify output, Explain/List debug surfaces | Prompt C03 | end_user_copy_remediation_package |
| `COPY-P1-006` | P1 | Today still includes backend/startup and read-model copy | Prompt C04 | end_user_copy_remediation_package |
| `COPY-P1-007` | P1 | Admin page still uses engineering telemetry labels | Prompt C05 | end_user_copy_remediation_package |
| `COPY-P1-008` | P1 | Core pages still mention source systems, Admin approvals, domain-nav implementation constraints, and diagnostics | Prompt C04 | end_user_copy_remediation_package |
| `COPY-P2-009` | P2 | ErrorState renders raw backend error messages and HTTP status text | Prompt C06 | end_user_copy_remediation_package |
| `COPY-P2-010` | P2 | Vite starter App.tsx remains in source tree with React/Vite demo copy | Prompt C07 | end_user_copy_remediation_package |
| `COPY-P2-011` | P2 | Daily Brief still exposes external Markdown, MCP, scheduled prompt, 7 states, parse/state language | Prompt C03/C04 | end_user_copy_remediation_package |
| `COPY-P2-012` | P2 | No dedicated frontend display-copy forbidden-term scan is visible in current client code | Prompt C08 | end_user_copy_remediation_package |

## Priority rule

- P0: must be fixed before continuing to dependent prompts.
- P1: must be fixed before final validation.
- P2: fix when adjacent to touched files; otherwise document explicit deferral with reason.
- P3: document as future-ready consideration unless it is cheap and safe to implement with the current prompt.
