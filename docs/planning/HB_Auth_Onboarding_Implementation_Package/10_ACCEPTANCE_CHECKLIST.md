# Acceptance Checklist

## Functional Acceptance

- [ ] Fully unauthenticated sessions route to `/get-started`.
- [ ] Returning users with stale auth get automated refresh attempt before reauth prompt.
- [ ] Failed refresh results in source-specific reauth prompt.
- [ ] Microsoft 365 connect flow works from frontend.
- [ ] Microsoft 365 device-code flow does not expose tokens.
- [ ] Procore connect flow works from frontend.
- [ ] Procore localhost callback works.
- [ ] Procore manual code fallback exists.
- [ ] Disconnect/reconnect works locally for Graph.
- [ ] Disconnect/reconnect works locally for Procore.
- [ ] Project Connections supports Procore URL preview/save.
- [ ] Project Connections supports SharePoint/OneDrive setup preview/save if existing backend contracts support it.
- [ ] Outlook/Calendar project matching remains optional and false by default.
- [ ] Preview does not start sync.
- [ ] Save does not start sync.
- [ ] First live sync is blocked until admin approval.
- [ ] Admin approval changes sync eligibility through governed path only.
- [ ] Non-admin sidebar footer shows Data Quality indicator.
- [ ] Data Quality hover shows latest update date/time.
- [ ] Admin can see detailed diagnostics in Settings.

## Security Acceptance

- [ ] No tokens are serialized to frontend.
- [ ] No secrets are serialized to frontend.
- [ ] No local token cache paths are serialized to frontend.
- [ ] No raw source payloads are serialized to frontend.
- [ ] No raw email bodies or raw document text are serialized to frontend.
- [ ] No signed URLs or download URLs are serialized to frontend.
- [ ] No setup action starts live sync.
- [ ] No source-system writeback is introduced.
- [ ] Logs redact auth-sensitive values.

## Validation Acceptance

- [ ] Backend auth onboarding tests pass.
- [ ] Existing analytics settings tests pass.
- [ ] Existing connection setup tests pass.
- [ ] Existing app shell tests pass.
- [ ] Ruff passes.
- [ ] Mypy passes.
- [ ] Frontend lint passes.
- [ ] Frontend typecheck passes.
- [ ] Frontend build passes.
- [ ] Manual smoke test completed using mocks or test-only credentials.

## Documentation Acceptance

- [ ] Operator runbook explains first-time setup.
- [ ] Operator runbook explains stale auth refresh and reauth.
- [ ] Operator runbook explains Procore callback and manual fallback.
- [ ] Operator runbook explains Data Quality indicator.
- [ ] Admin docs explain first-sync approval.
