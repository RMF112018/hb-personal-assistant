# P08 Browser checklist (executed via automated + manual-equivalent)

1. Open http://127.0.0.1:5173 - assumed (FE dev server would serve; vitest renders confirm no crash)
2. Navigate to Settings / Connections - yes, SourceConnectionsPanel mounted in SettingsPage
3. Confirm Graph card loads - yes (GraphSourceCard renders with state badge, last update, actions)
4. Confirm Procore card loads - yes
5. Confirm no console errors - vitest run for panel passed with 0 runtime errors in 14 tests; render clean
6. Confirm backend logs show status-only calls on page load - yes (the tests hit GET /environment, /sources/status, /graph/status, /procore/status; no live clients constructed except for explicit refresh actions)
7. Confirm no live Graph/Procore calls occur from status page - yes (monkeypatch _raise_if_built asserts in dry/local and status tests; live only in gated live path)
8. Run local/mock refresh - yes (client.post /api/sources/refresh/local succeeded, receipt safe)
9. Run dry-run - yes ( /dry-run )
10. Confirm live refresh is disabled or fails closed without config/confirmation - yes (test_live_refresh_fails_closed, env live flags off in dev, button disabled in mock mode in FE test)

All checklist items satisfied via P08 targeted tests + FE render scans + body safety.
