# Phase 03 Entry — Graph Delegated Scope Alignment

## Why

Device-code login at `hb-assistant auth login --json` was blocked by an Azure AD
"Need admin approval" page because the runtime requested **`Calendars.Read`**
and **`Files.Read.All`**, neither of which is admin-consented in the
**HB SharePoint Creator** app registration
(`client_id = 08c399eb-a394-4087-b859-659d493f8dc7`,
`tenant_id = 0e834bd7-628b-42c8-b9ec-ecebc9719be4`). The app registration
already holds admin-consented delegated grants for the broader strings
**`Calendars.ReadWrite.Shared`** and **`Files.ReadWrite.All`**, which include
the read capabilities required by the application.

Swapping the runtime scope strings to match the consented strings unblocks
login without changing the Azure app registration and without weakening any
controller-level guardrail.

## Scope changes

| Setting | Before | After |
|---|---|---|
| `IdentityConfig.delegated_scopes` defaults | `["User.Read", "Mail.Read", "Calendars.Read", "Files.Read.All", "offline_access"]` | `["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All", "offline_access"]` |
| `config/config.example.yml` `identity.delegated_scopes` | (mirrored old) | (mirrored new) |
| `cli/diagnostics.py` calendar diagnostic per-call scopes | `["Calendars.Read", "User.Read"]` | `["Calendars.ReadWrite.Shared", "User.Read"]` |
| `construction/graph/resolver.py` `GRAPH_SCOPES` | `["Sites.Read.All", "Files.Read.All", "User.Read"]` | `["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]` |
| `construction/graph/__init__.py` `GRAPH_SCOPES` | same as resolver | same as resolver |
| `graph/proof_runner.py` calendar gap remediation string | "Verify Calendars.Read delegated permission." | "Verify Calendars.ReadWrite.Shared delegated permission." |
| `graph/proof_runner.py` drive gap remediation string | "Verify Files.Read.All delegated permission." | "Verify Files.ReadWrite.All delegated permission." |
| `docs/architecture/03-delegated-graph-capability-proof.md` required-scopes bullet list | (old) | (new) |
| `docs/architecture/04-graph-mail-calendar-read-models.md` scope sentence | (old) | (new) plus the broader-scope/no-mutation clarification |

## Guardrail assertions (verbatim)

- **Device login was blocked because runtime requested `Calendars.Read` and `Files.Read.All`.**
- **Runtime now requests `Calendars.ReadWrite.Shared` and `Files.ReadWrite.All`, which match the already-granted Azure delegated permissions.**
- **Runtime still requests only `Mail.Read` for mail.**
- **Runtime still does not request `Mail.ReadWrite`, `Mail.ReadWrite.All`, `Mail.Send`, or `.default`.**
- **Broader file/calendar permissions are granted but controller guardrails still prohibit MVP source-system mutation.**

Mailbox-read-only and source-system-read-only posture unchanged:

- `mailbox_writeback_allowed = false`
- `persist_full_body = false`
- `review_required_for_sensitive = true`
- No mailbox mutation endpoints exist (covered by the static scans in
  `tests/test_mutation_lockout.py`).
- No email send / delete / move / reply / forward behavior.
- Runtime never requests `Mail.ReadWrite*` or `Mail.Send*`.
- `Sites.ReadWrite.All`, `Sites.FullControl.All`, `Sites.Manage.All` are not
  introduced anywhere.
- `Sites.Read.All` in `GRAPH_SCOPES` was preserved (already required for
  construction-agent SharePoint folder resolution; not new).

## Runtime verification

### Default-scope assertion

```
$ python -c "from hb_assistant.config.models import IdentityConfig; print(IdentityConfig().delegated_scopes)"
['User.Read', 'Mail.Read', 'Calendars.ReadWrite.Shared', 'Files.ReadWrite.All', 'offline_access']
```

### `hb-assistant auth status --json` (post-edit, pre-login)

```json
{
  "mode": "delegated",
  "token_type": "none",
  "message": "No delegated token. Run login.",
  "configured_scopes": ["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All", "offline_access"],
  "effective_msal_scopes": ["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All"],
  "removed_reserved_scopes": ["offline_access"]
}
```

`offline_access` is stripped by `sanitize_delegated_scopes`
(`src/hb_assistant/auth/scope_policy.py`, `RESERVED_SCOPES` includes
`offline_access`, `openid`, `profile`). MSAL receives the four Graph
scopes only.

### `hb-assistant construction-agent graph auth status --json` (post-edit, pre-login)

Same `delegated.configured_scopes` and `delegated.effective_msal_scopes` as
above. `required_scopes` (a separate construction-agent declaration) is
`["Sites.Read.All", "Files.Read.All", "User.Read"]` — note that
`graph auth status`'s `required_scopes` field is independent of
`GRAPH_SCOPES` and will be updated by a later prompt if a parallel
alignment is needed. The actual per-call token requests by
`ConstructionGraphResolver` use the corrected
`GRAPH_SCOPES = ["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]`.

### `python -m pytest tests/test_mutation_lockout.py` (after change)

```
13 passed in 0.05s
```

Includes the new `test_identity_default_scopes_match_granted_app_registration_scopes`
pinning the runtime default to exactly the post-change scope list, asserting
the previously-blocking `Calendars.Read` / `Files.Read.All` are absent, and
asserting no scope contains the `.default` literal.

### `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```
All checks passed!
```

### `hb-assistant construction-agent validate --json`

```
schema           ok=True  schema_version=5
source_registry  ok=True  6 projects, 14 sources
review_rules     ok=True  version=1; 16 rules; threshold=0.7
model_routing    ok=True  version=1; default_model=llama3.2:1b
summary          total=4, passed=4, failed=0, ok=True
```

### Pre-existing test failures (NOT introduced by this change)

`python -m pytest tests/test_mutation_lockout.py tests/test_construction_*.py tests/test_procore_*.py`
reports `401 passed, 18 failed`. The 18 failures are all in
`tests/test_procore_endpoint_audit.py` (4) and
`tests/test_procore_endpoint_reference.py` (5 named + others in the same
file), introduced by the parallel Phase 03 Procore-reference work landed
in commits `ca5ea71 feat(procore): add verified endpoint reference contract foundation`
and `c051523 docs(evidence): add construction-intelligence-phase-03/01-procore-api-research-summary`.
The same 18 failures were present on `c051523` **before** the scope
alignment in this commit. Delta from this commit: **+1 passing test**
(the new `test_identity_default_scopes_match_granted_app_registration_scopes`).
Classification: `pre-existing known limitation` (Phase 03 Procore-reference
workstream).

## Pending: device-login retry

Bobby is expected to run, from his local terminal:

```
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant auth login --json
```

Expected outcome: the device-code flow proceeds past the prior "Need admin
approval" page (the requested scopes now match what's admin-consented). The
post-login `auth status --json` should report `token_type` ≠ `none` and the
same `effective_msal_scopes` list shown above.

If the page still requires admin approval after this change, that indicates
the app registration has additional un-consented permissions configured
(beyond Mail.Read, Calendars.ReadWrite.Shared, Files.ReadWrite.All,
User.Read). The exact requested-scope list in the MSAL response should be
captured verbatim before any further code change.
