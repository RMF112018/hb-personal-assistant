# Mail Permission Readiness Proof (Phase 06)

**Prompt:** Phase 06 / Prompt 00 — Repo Truth Rebaseline and Graph Mail Readiness Audit
**Generated:** 2026-05-29 (audit run)
**Scope:** Prove that delegated Microsoft Graph mail access is **ready and read-only**
under Bobby's context, and that no `Mail.ReadWrite`/`Mail.Send` runtime scope is requested.

> Read-only proof. No mailbox state was read beyond a `/me` identity probe; no message
> list/index was executed by this prompt; no token was logged; no mutation was performed.

---

## 1. Requested vs. effective scopes (delegated)

Source of requested scopes: config `identity.delegated_scopes`
(`src/hb_assistant/config/models.py:22`). Sanitization: `auth/scope_policy.py`.

```text
$ hb-assistant auth status --json   # scope diagnostics (delegated token)
{
  "mode": "delegated",
  "token_type": "delegated",
  "classification": "delegated",
  "configured_scopes": [
    "User.Read",
    "Mail.Read",
    "Calendars.ReadWrite.Shared",
    "Files.ReadWrite.All",
    "offline_access"
  ],
  "effective_msal_scopes": [
    "User.Read",
    "Mail.Read",
    "Calendars.ReadWrite.Shared",
    "Files.ReadWrite.All"
  ],
  "removed_reserved_scopes": [
    "offline_access"
  ]
}
```

**Mail readiness verdict:**

| Check | Result |
| --- | --- |
| Mail scope requested | `Mail.Read` only ✅ |
| `Mail.ReadWrite` requested at runtime | **No** ✅ |
| `Mail.ReadWrite.All` requested at runtime | **No** ✅ |
| `Mail.Send` requested at runtime | **No** ✅ |
| Reserved scopes stripped before MSAL | `offline_access` removed ✅ |

The write-capable `Calendars.ReadWrite.Shared` / `Files.ReadWrite.All` scopes are
out of scope for this mail-only phase and are left unchanged; they do not grant any mail
mutation capability.

## 2. Tenant consent vs. runtime request (grant-but-suppress)

The cached token's **granted** scope set (tenant-consented) is broader than what the app
requests. A separately observed cached token entry reported scopes including
`Mail.Read` **and** `Mail.ReadWrite` (alongside `Sites.*`, `Files.ReadWrite.All`, etc.),
classified `unexpected` (an app-only/broad-consent token present in the cache).

This is the documented **grant-but-suppress** posture and is **not** a violation:

- Tenant consent may include `Mail.ReadWrite.All` (recorded as
  `mail_readwrite_all_granted = true` in the deferred policy and the V5
  `construction_email_intelligence_deferred_state` row).
- The application's **delegated runtime request** still asks only for `Mail.Read`
  (Section 1).
- Phase 06 runtime remains strictly read-only even when consent is broader — enforced in
  code/tests (Section 3), not by relying on the consent surface.

Proven by `tests/test_mutation_lockout.py::
test_email_intelligence_deferred_policy_allows_mail_readwrite_all_granted_true_without_loosening_lockout`
("tenant may grant Mail.ReadWrite.All, but the three locked guardrails stay locked").

## 3. Read-only enforcement layers (verified present)

| Layer | Repo truth | Status |
| --- | --- | --- |
| Config policy | `MailConfig.persist_full_body = False`; `security.microsoft_365_writeback_enabled = False` | ✅ |
| Scope policy | runtime requests `Mail.Read`; no mail write scope (Section 1) | ✅ |
| HTTP client | `GraphHttpClient` is GET-only (`get`/`get_all_pages`/streamed `download_to_file`); no `post`/`patch`/`delete`/`put` | ✅ |
| Mail client | `MailClient` exposes only list/get/metadata + bounded in-memory body inspection; no send/draft/forward/reply/delete/move/copy/mark/categorize/flag | ✅ |
| SQLite CHECK | V5 `construction_email_intelligence_deferred_state` — `CHECK(mailbox_writeback_allowed = 0)`, `CHECK(persist_full_body = 0)` | ✅ |
| Pydantic locks | `EmailIntelligenceDeferredPolicy` — `mailbox_writeback_allowed: Literal[False]`, `persist_full_body: Literal[False]`, `review_required_for_sensitive: Literal[True]`, `extra="forbid"` | ✅ |
| Static scan test | `tests/test_mutation_lockout.py::test_no_m365_write_apis_in_graph_clients` asserts zero Graph write calls | ✅ |

## 4. Delegated connectivity proof

```text
$ hb-assistant diagnostics graph --safe --json
{
  "safe": true,
  "probes": [
    { "path": "/me", "status": 200, "sample": { "id_present": true, "upn": "bfetting@hedrickbrothers.com" } }
  ],
  ...
}
```

- Delegated token acquisition and a read-only `/me` probe succeed (HTTP 200).
- Auth cache paths under `~/Library/Application Support/HB Personal Assistant/` exist and
  are writable with correct modes (`auth` dir `0o700`); the token cache lives **outside**
  the repo. No token material is included in this evidence.

## 5. Supporting test evidence

```text
$ pytest tests/test_auth.py tests/test_graph_clients.py tests/test_mutation_lockout.py \
         tests/test_construction_store_repositories.py \
         -m "not integration and not live and not manual"
75 passed in 0.75s
```

Relevant guardrail tests covered: scope sanitization, GET-only Graph client surface,
mutation lockout (no write APIs, writeback disabled by default), and the
email-intelligence deferred-policy locks (rejects `mailbox_writeback_allowed=true`,
`persist_full_body=true`, `review_required_for_sensitive=false`, and unknown fields).

## 6. Readiness verdict

**READY (read-only).** Delegated Graph mail access is functional under Bobby's context,
the runtime requests `Mail.Read` only, write-capable mail scopes are neither requested nor
reachable through the client surface, and the no-mutation / no-full-body guardrails are
enforced at config, scope, HTTP, client, schema, policy, and test layers. Phase 06
operational email workflows can proceed to build on this baseline without requesting any
mail mutation scope.

**No stop condition triggered** — no mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send`
runtime scope request, no destructive migration, no full-body default persistence, and no
attachment-content default download was required or introduced.
