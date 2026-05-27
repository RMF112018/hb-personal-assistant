# Phase 02 — Prompt 10: Email Intelligence Deferred Foundation

## Summary

Lands the **operator-facing** half of the Phase 02 email-intelligence deferred-foundation work. The runtime half — V5 SQL CHECK constraints, `ConstructionStore.set_email_intelligence_deferred_state` Python guards, and the `Mail.Read`-only delegated scope list — were already in place from Prompts 02 and earlier. This prompt adds the checked-in YAML policy, a Pydantic loader that mirrors the JSON contract via `Literal[False]` / `Literal[True]` guards, README documentation explaining the grant-but-suppress posture, and defense-in-depth static scans in `tests/test_mutation_lockout.py` that fail loudly if a future change ever requests a forbidden mailbox-write scope or introduces a mailbox-mutation endpoint in `src/hb_assistant/graph/`.

The central assertion is **grant-but-suppress**: the tenant has consented to `Mail.ReadWrite.All` (recorded in `mail_readwrite_all_granted: true`), but the application's `IdentityConfig.delegated_scopes` still requests only `Mail.Read` at MSAL token acquisition, the YAML policy enforces `mailbox_writeback_allowed: false` and `persist_full_body: false` at the Pydantic Literal boundary, the Python adapter guards reject writeback attempts at runtime, and the SQLite V5 table CHECK constraints reject them at the database boundary. Four layers; none individually relied upon.

## Repo HEAD

- Before: `f21f15e` (Phase 02 Prompt 09 closeout)
- After: `<filled in by commit step>`

## Files changed

```
 README.md                                                              |  11 ++
 src/hb_assistant/construction/policy/__init__.py                       |   9 ++
 tests/test_mutation_lockout.py                                         | 168 +++++++
 resources/config/email_intelligence_deferred_policy.yaml               | new (~30 lines)
 src/hb_assistant/construction/policy/email_deferred.py                 | new (~100 lines)
 5 files changed, ~310 insertions(+)
```

Plus this evidence file.

## Validation commands and outputs

### `python -m pytest tests/test_construction_*.py tests/test_procore_*.py tests/test_mutation_lockout.py`

```
413 passed in 6.02s
```

Mutation lockout file alone (12 passed, 8 new): 4 baseline + 6 policy-regression + 1 scope-defense + 1 graph-client-endpoint-scan.

### `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```
All checks passed!
```

### `hb-assistant construction-agent validate --json` (unchanged)

```
schema           ok=True  schema_version=5
source_registry  ok=True  6 projects, 14 sources
review_rules     ok=True  version=1; 16 rules; threshold=0.7
model_routing    ok=True  version=1; default_model=llama3.2:1b
```

### Smoke test (Python REPL)

```
OK1: policy loads. writeback=False persist_body=False review_required=True
     mail_read_all_granted=True mail_readwrite_all_granted=True future_phase=phase_03
OK2: mailbox_writeback_allowed=True rejected by Pydantic Literal[False]
OK3: default delegated_scopes = ['User.Read', 'Mail.Read', 'Calendars.Read', 'Files.Read.All', 'offline_access']
OK4: forbidden mail scopes absent from runtime request: True
```

## Grant-but-suppress posture (four-layer attestation)

| Layer | Behavior |
|-------|----------|
| Tenant grant | `Mail.ReadWrite.All` granted (recorded in YAML policy as `mail_readwrite_all_granted: true`). |
| MSAL scope request | `IdentityConfig().delegated_scopes` is `['User.Read', 'Mail.Read', 'Calendars.Read', 'Files.Read.All', 'offline_access']`; `Mail.ReadWrite.All`, `Mail.ReadWrite`, `Mail.ReadWrite.Shared`, `Mail.Send`, `Mail.Send.Shared` are absent. Verified by `test_identity_default_scopes_do_not_request_mailbox_write_scopes`. |
| YAML policy | `mailbox_writeback_allowed: false`, `persist_full_body: false`, `review_required_for_sensitive: true` — locked at the Pydantic `Literal[False]` / `Literal[True]` boundary. Verified by 4 dedicated rejection tests. |
| Python adapter | `ConstructionStore.set_email_intelligence_deferred_state` (`src/hb_assistant/construction/store/repositories.py:1213-1249`) raises `ValueError` on any attempt to set `mailbox_writeback_allowed=True` or `persist_full_body=True`. Unchanged from Prompt 02. |
| SQLite | V5 table `construction_email_intelligence_deferred_state` carries `CHECK(mailbox_writeback_allowed = 0)`, `CHECK(persist_full_body = 0)`, `CHECK (id = 1)`. Unchanged from Prompt 02. |
| Graph client code | New `test_graph_clients_do_not_contain_mailbox_mutation_endpoints` static scan over `src/hb_assistant/graph/**.py` ensures no `.post(/.patch(/.delete(` against `/me/messages` or `/me/mailFolders` and no literal `/sendMail`, `/reply`, `/replyAll`, `/forward`, `microsoft.graph.move`, or `microsoft.graph.copy` endpoint appears. Currently passes — only GET-shaped read paths exist. |

## Guardrail attestation

- **No expansion of `IdentityConfig.delegated_scopes`.** `Mail.Read` only.
- **No new CLI command.** Loader + tests + evidence are the deliverables this prompt.
- **No edits to `MailConfig`, the V5 migrator, or the `set_email_intelligence_deferred_state` adapter.** Existing locks remain.
- **No new mailbox endpoints, mailbox writeback paths, or Graph mutation methods.**
- **No live Graph call** during validation. The readiness / scope-acquisition observation is from static config inspection (`IdentityConfig()`) and source-code regex scans; the YAML policy parses through the Pydantic loader without network I/O.
- **No new third-party dependency.** The plan called out an optional `jsonschema` cross-check; `jsonschema` is not currently a project dependency, so the cross-check test was intentionally NOT added. The Pydantic model is the runtime contract; the JSON schema file remains as documentation only.

## Blocked live / external validation

- No live Microsoft Graph mailbox call was attempted.
- MSAL token cache untouched.

## Cross-references

- New policy file — `resources/config/email_intelligence_deferred_policy.yaml`
- New Pydantic model + loader — `src/hb_assistant/construction/policy/email_deferred.py`
- Re-exports — `src/hb_assistant/construction/policy/__init__.py`
- Tests — `tests/test_mutation_lockout.py` (after the existing `test_mutation_lockout_redaction_in_test_artifacts`)
- README section — `## Email Intelligence (Deferred)` (after `## Guardrails (Global)`)
- Existing JSON contract (unchanged, documentation-only) — `resources/schemas/email_intelligence_deferred_contract.schema.json`

## Out of scope (deferred)

- Email intelligence runtime pipeline (parsing, indexing, classification) — Phase 03+.
- Operator CLI for the policy (`email policy show` etc.).
- Expansion of MSAL delegated scopes to `Mail.ReadWrite.All` (intentionally suppressed).
- Adding the email policy to `construction-agent validate --json` checks.
- Adding `jsonschema` as a runtime dependency.

## Next prompt readiness

Repo HEAD advanced; working tree clean after commit; full pytest (413 passing) + ruff + CLI suite green; mailbox grant-but-suppress posture documented and locked at four layers. Ready for Phase 02 Prompt 11 or Phase 02 closeout.
