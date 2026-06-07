# Validation and Evidence Plan

## Required automated validation

Run after each meaningful prompt and again at closeout:

```bash
cd /Users/bobbyfetting/hb-personal-assistant/frontend
npm run lint
npm run typecheck
npm run build
npm run test
```

If `npm run test` is not configured or fails because of pre-existing test harness limitations, document the exact result and run the closest available targeted tests.

## Required backend contract validation

Run when touching frontend clients/hooks for onboarding, settings, connections, or app shell data:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
```

## Required copy regression validation

Add and run a copycheck command. Recommended target:

```bash
cd /Users/bobbyfetting/hb-personal-assistant/frontend
npm run copycheck
```

The copycheck must scan production-rendered frontend source and fail on forbidden terms unless allowlisted.

## Required manual browser smoke tests

Start the local backend/frontend per repo runbook, then validate:

### Desktop

- Open Today at top of page.
- Scroll Today to middle and bottom.
- Confirm sidebar footer remains pinned and visible.
- Confirm main content scrolls independently from sidebar.
- Confirm no horizontal overflow.
- Confirm no visible local-dev role selector, disabled Chat, prompt IDs, or framework/backend terms.

### Projects

- Open Projects.
- Confirm grid layout, clear setup/empty state, and stable sidebar footer.
- Confirm all project navigation remains reachable.

### My Items

- Open My Items.
- Confirm prioritized work-queue grid.
- Confirm empty/loading/error states are business-readable.

### Settings

- Confirm Account Connections, Project Connections, Daily Brief, and Preferences are user-facing.
- Confirm no Prompt 14B/Prompt 20/FPR/raw-panel/JSON snippets in normal UI.
- Confirm advanced Daily Brief technical instructions are collapsed.

### Admin/Data Health

- Confirm non-admin users see Data Quality footer indicator, not admin diagnostics.
- Confirm admins can access Data Health detail.
- Confirm technical diagnostics are behind disclosure.

### Responsive and accessibility

- Test desktop, tablet, and narrow/mobile widths.
- Keyboard-tab through sidebar, footer, page header actions, and cards.
- Confirm visible focus states and logical order.
- Check heading order and landmark coherence.

## Evidence to capture

- command outputs;
- before/after screenshots for Today, Projects, My Items, Settings, Admin/Data Health;
- copycheck output;
- changed file list;
- manual smoke matrix results;
- unresolved known risks.
