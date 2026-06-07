# Launcher Risk Register

| ID | Severity | Risk | Why It Matters | Mitigation | Validation |
|---|---:|---|---|---|---|
| LR-001 | P0 | Launcher depends on Vite dev server | User still needs two-process development workflow | Serve production `frontend/dist` from backend | Start app without `npm run dev` |
| LR-002 | P0 | API routes broken by static fallback | Dashboard may load shell but fail data calls | Exclude `/api/*` and `/health` from SPA fallback | Curl API routes |
| LR-003 | P1 | Unsafe host binding | Dashboard could be exposed on local network | Default to `127.0.0.1`; reject/warn on `0.0.0.0` | Inspect command defaults |
| LR-004 | P1 | Port conflict creates confusing failure | User cannot launch reliably | Detect port and print clear next step | Duplicate launch test |
| LR-005 | P1 | Shortcut duplicates server logic | Launcher behavior diverges from CLI | Shortcut calls CLI only | Inspect shortcut |
| LR-006 | P1 | Missing build artifacts cause blank page | User sees broken UI | Preflight `frontend/dist/index.html` | Missing-dist test |
| LR-007 | P1 | Terminal closes before showing errors | Shortcut appears to do nothing | Keep prompt open on failure | Manual shortcut failure test |
| LR-008 | P1 | Startup triggers live sync | Launch could mutate systems or consume API | Launcher must be view-only/startup-only | Review code/tests/logs |
| LR-009 | P2 | Logs leak sensitive data | Compliance/security issue | Sanitize logs; avoid raw content | Inspect logs |
| LR-010 | P2 | Browser opens before server ready | User sees connection refused | Health polling before open | `--open` smoke |
| LR-011 | P2 | Stale PID blocks relaunch | User friction | Detect stale PID and recover | Stop/restart test |
| LR-012 | P3 | Desktop shortcut icon is plain | Cosmetic polish issue | Optional Automator app wrapper later | Runbook note |
