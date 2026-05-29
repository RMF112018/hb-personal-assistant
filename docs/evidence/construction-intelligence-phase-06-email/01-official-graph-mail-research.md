# 01 — Official Microsoft Graph Mail Research & Endpoint Contract (Phase 06)

**Prompt:** Phase 06 / Prompt 01 — Official Graph Mail Research and Endpoint Contract
**Generated:** 2026-05-29 (audit run); Graph docs fetched 2026-05.
**Posture:** Research + **static** contract resources + this evidence doc. No runtime code,
loader, CLI command, schema migration, or auth-scope change was made. The Pydantic loader and
HTTP-guard enforcement that consume these resources land in Phase 06 Prompt 04.

> No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` runtime scope request, no destructive
> migration, no full-body default persistence, and no attachment-content default download was
> introduced or required. **No stop condition triggered.**

---

## 1. Sources of truth (official Microsoft Learn, v1.0)

| Topic | URL | Doc `ms.date` / `updated_at` |
| --- | --- | --- |
| List messages | https://learn.microsoft.com/en-us/graph/api/user-list-messages | updated 2025-07-23 |
| Immutable IDs for Outlook | https://learn.microsoft.com/en-us/graph/outlook-immutable-id | updated 2025-08-06 |
| List attachments | https://learn.microsoft.com/en-us/graph/api/message-list-attachments | updated 2026-05-19 |
| Throttling limits | https://learn.microsoft.com/en-us/graph/throttling-limits (+ /graph/throttling) | — |

Per the package's own guidance, docs are re-checked at implementation time.

## 2. Read endpoints (allowlist)

GET-only. Folder-scoped listing is the preferred entry point.

| Method | Path | Use |
| --- | --- | --- |
| GET | `/me` | mailbox-owner / identity probe |
| GET | `/me/mailFolders` | folder discovery |
| GET | `/me/mailFolders/{id}` | single folder metadata |
| GET | `/me/mailFolders/{id}/messages` | **preferred** folder-scoped listing |
| GET | `/me/messages` | mailbox-wide listing (bounded) |
| GET | `/me/messages/{id}` | single message metadata |
| GET | `/me/messages/{id}/attachments` | attachment **metadata only** (see §6) |
| GET | `/me/mailFolders/{id}/messages/delta` | future incremental sync (see §5) |

Confirmed verbatim from *List messages*:
> `GET /me/messages` … `GET /me/mailFolders/{id}/messages`

Recorded in repo at `resources/config/graph_mail_read_endpoint_allowlist.yaml`.

## 3. `$select` — metadata-first, body-free

To improve response time and avoid the HTTP 504 gateway-timeout risk on large pages, the docs
advise requesting only needed properties. The message metadata `$select` (19 fields) is:

```
id, internetMessageId, conversationId, parentFolderId, subject, from, sender,
toRecipients, ccRecipients, bccRecipients, replyTo, receivedDateTime, sentDateTime,
hasAttachments, importance, categories, sensitivity, webLink, bodyPreview, lastModifiedDateTime
```

`body` is **intentionally absent** — full body is never requested by default.

## 4. `$filter` and `$orderby`

- Bounded lookback uses `receivedDateTime ge {iso}` (inbound) / `sentDateTime ge {iso}` (sent) —
  matching the existing `MailClient._inbound_window()` / `_sent_window()`.
- **Filter/orderby ordering rule** (verbatim risk from docs): when using `$filter` and `$orderby`
  together, every `$orderby` property must also appear in `$filter`, in the same order, before any
  filter-only properties — otherwise Graph returns error code `InefficientFilter`
  ("The restriction or sort order is too complex for this operation.").

## 5. Paging and delta

- **Paging:** apply the entire `@odata.nextLink` URL verbatim to the next request. Default page
  size is **10**; `$top` valid range is **1–1000**. Do **not** extract/manipulate the `$skip`
  value from `nextLink` — Graph uses it as an internal cursor (it can exceed the page size even on
  the first response). The repo's `GraphHttpClient.get_all_pages()` already follows `nextLink`
  and bounds by `max_pages`/`max_items`.
- **Delta:** `GET /me/mailFolders/{id}/messages/delta` supports future incremental sync. Phase 06
  uses bounded lookback first and only adopts delta once read-only proof + tests are in place.
  Delta query supports immutable IDs via the `Prefer` header; its `@odata.nextLink` /
  `@odata.deltaLink` are compatible with both ID formats, so no re-sync is required to opt in.

## 6. Immutable IDs

Opt-in per request via the header (verbatim from docs):

```
Prefer: IdType="ImmutableId"
```

- The header applies only to the request it accompanies — it must be sent on **every** request to
  use immutable IDs consistently. The repo's `GraphHttpClient` already sends this header.
- Lifetime caveats: the immutable ID is stable when an item moves **between folders** in the same
  mailbox, but **changes** if the user moves it to a **separate archive mailbox** or exports and
  re-imports it (PST/MSG). Supported by `message` and `attachment` resource types (container types
  like `mailFolder` already have constant IDs).

## 7. Attachment metadata vs. content — **critical correction**

The *List attachments* endpoint `GET /me/messages/{id}/attachments` returns `Attachment` objects
that include **`contentBytes`** (the full file content) **by default** — the documented example
response contains a populated `contentBytes` field. Therefore "metadata only" is **not** automatic:
the allowlist pins an attachment `$select` that **excludes `contentBytes`**:

```
id, name, contentType, size, isInline, lastModifiedDateTime
```

The raw-content path `/me/messages/{id}/attachments/{attachment_id}/$value` is placed on the
**mutation/forbidden** blocklist. Delegated scope for listing attachments is `Mail.Read` (confirmed).

## 8. `bodyPreview` vs `body`

- `bodyPreview` is a short text preview (included in the metadata `$select`).
- `body` is full content, returned in **HTML** by default; format is controlled by the
  `Prefer: outlook.body-content-type` header (`text`/`html`). Phase 06 does **not** request `body`
  by default. The existing `MailClient.get_message_body_for_inspection()` fetches bounded body
  **in memory only** (truncated, never persisted to DB/logs/evidence/cache) for classification; any
  persistence of `body` remains gated behind `cfg.mail.persist_full_body` (default `False`).

## 9. Permissions / scopes

- *List messages* least-privileged delegated permission is **`Mail.ReadBasic`**; higher are
  `Mail.Read` / `Mail.ReadWrite`. `Mail.ReadBasic` **omits** `body` and `bodyPreview`, which the
  metadata-first workflow needs — so the runtime requests **`Mail.Read`** (already configured in
  `identity.delegated_scopes`).
- `Mail.ReadWrite` / `Mail.ReadWrite.All` / `Mail.Send` may be tenant-consented but are **never**
  requested or used by Phase 06 runtime (grant-but-suppress; see
  `mail-permission-readiness-proof.md`).

## 10. Throttling

- Throttled requests return **HTTP 429** with a **`Retry-After`** header indicating the wait; the
  caller must respect it. Diagnostic headers `x-ms-throttle-scope` / `x-ms-throttle-information`
  may accompany the response. A global ceiling of 130,000 requests / 10 s per app applies across
  tenants.
- Outlook/Exchange mailbox-specific limits (per app, per mailbox) are commonly **~10,000 requests
  per 10 minutes** with **~4 concurrent requests** — **re-verify at implementation** as Microsoft
  updates these. Phase 06 mitigations: per-command page/item caps, bounded lookback, no polling
  loops, and **no full-mailbox backfill**. The repo's `GraphHttpClient` already retries on 429/5xx.

## 11. Mutation blocklist (rejected before HTTP)

Forbidden verbs: `POST`, `PATCH`, `DELETE`, `PUT`. Forbidden paths include `sendMail`, message
create/update/delete, `move`, `copy`, `forward`, `reply`, `replyAll`, `createForward`/`createReply`/
`createReplyAll`, `send`, attachment POST, and the raw-content `…/attachments/{id}/$value`.
`on_match`: raise `MailboxMutationBlockedError` before the HTTP request, write a blocked processing
receipt, and stop the workflow. Recorded at
`resources/config/graph_mail_mutation_endpoint_blocklist.yaml`.

**Method/path interaction:** paths such as `/me/messages` and `/me/messages/{id}` appear in **both**
the read allowlist and the mutation blocklist. The HTTP **verb** decides — `GET` reads metadata; the
forbidden verbs are blocked on the same path. Prompt 04 enforcement keys on the `(method, path)` pair.

## 12. Repo reconciliation

- **Format/location divergence (resolved in favor of repo truth):** the package proposed these as
  JSON under `resources/json/`. The repo has no `resources/json/` directory; the convention
  (CLAUDE.md + every existing policy seed, e.g. `email_intelligence_deferred_policy.yaml`,
  `procore_sensitive_routing_rules.yaml`) is **YAML under `resources/config/`**. The contract is
  therefore authored as two repo-native YAML files. Content is equivalent to the package allowlist/
  blocklist plus the doc-grounded corrections above (attachment `$select`, `$value` block, scope
  rationale, paging discipline, immutable-ID caveats).
- **Existing stack already conformant:** `GraphHttpClient` is GET-only and already sets
  `Prefer: IdType="ImmutableId"`; `MailClient` uses bounded lookback windows + a minimal `$select`
  and gates body behind `persist_full_body=False`. This contract documents and pins that behavior;
  it does not change it.
- **Deferred (stated for the record):** Pydantic loader/model + HTTP-guard wiring → Prompt 04;
  folder include/exclude + discovery defaults + email-intelligence policy seed → Prompts 02/05;
  schema migration (V10+) → Prompt 03; `graph mail …` CLI → Prompts 04–14.

## 13. Resource files created + validation

| Artifact | Path |
| --- | --- |
| Read allowlist | `resources/config/graph_mail_read_endpoint_allowlist.yaml` |
| Mutation blocklist | `resources/config/graph_mail_mutation_endpoint_blocklist.yaml` |
| Contract validation test | `tests/test_graph_mail_endpoint_contract.py` |

Validation (run in `.venv`):

```text
$ python -c "import yaml; yaml.safe_load(open('…read_endpoint_allowlist.yaml')); yaml.safe_load(open('…mutation_endpoint_blocklist.yaml'))"
both parse OK

$ pytest tests/test_graph_mail_endpoint_contract.py tests/test_mutation_lockout.py
21 passed in 0.07s

$ ruff check .         → All checks passed!
$ mypy src             → Success: no issues found in 115 source files
$ compileall src tests → OK
```

The contract test asserts: read allowlist is GET-only; message `$select` excludes `body`;
attachment `$select` excludes `contentBytes`; the ImmutableId Prefer header is declared; paging
does not parse the skip token; blocklist forbids all write verbs and the `sendMail` / `$value`
paths and covers the mutation keywords.

## 14. Conclusion

The official Graph mail contract is researched and pinned into repo-native YAML resources, grounded
in current Microsoft Learn docs and reconciled against the existing GET-only stack. The most
material finding — attachments returning `contentBytes` by default — is mitigated by a metadata-only
attachment `$select` plus a `$value` block. All validations are green. No runtime behavior, scope,
or schema changed, and no stop condition was triggered.
