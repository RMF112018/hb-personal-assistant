# Graph and Procore Dev UI Connections Implementation Package

Repository: `RMF112018/hb-personal-assistant`  
Expected local path: `/Users/bobbyfetting/hb-personal-assistant`  
Package date: `2026-06-07`  
Package type: implementation package for a local coding agent

## Purpose

This package converts the Graph/Procore Dev UI connection audit objective into an executable remediation plan. It mirrors the structure of the provided example package: numbered guidance files, ordered implementation prompts, structured JSON data, reference notes, and a validation manifest.

## Required outcome

After implementation, the Dev UI must:

- show that the app is running in `Dev` and local/mock-data mode;
- render Microsoft 365 / Graph connection status from a safe backend contract;
- render Procore connection status from a safe backend contract;
- expose backend-controlled auth start/status/refresh actions where supported;
- separate `status`, `local/mock refresh`, `dry-run`, and `gated live refresh`;
- keep Dev live reads OFF by default;
- keep Production live reads config-gated and default OFF;
- show clear user-facing next actions for stale auth, missing config, missing mapping, and disabled live refresh;
- keep technical diagnostics admin-only;
- prove with tests that status page load does not call live Graph or Procore APIs.

## How to use

1. Read `00_PACKAGE_MANIFEST.md` and `01_EXECUTION_GUIDE.md`.
2. Run `prompts/00_MASTER_IMPLEMENTATION_PROMPT.md` in the local agent session.
3. Execute prompts `P00` through `P09` in order.
4. Record changed files, validation output, and residual risks after each prompt.
5. Use `09_CLOSEOUT_REPORT_TEMPLATE.md` for the final closeout.

## Hard constraints

- No Microsoft Graph writeback.
- No Procore writeback.
- No raw email/calendar/Procore payload exposure.
- No tokens, client secrets, or token-cache paths in browser responses.
- No live external reads from status endpoints.
- No Dev live reads by default.
- No live refresh unless backend config and explicit confirmation both permit it.
