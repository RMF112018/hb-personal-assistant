# Phase 03 Entry — Prompt 09: Mailbox Read-Only Metadata Proof

**Date:** 2026-05-28
**Operator:** bfetting@hedrickbrothers.com
**Repo:** `/Users/bobbyfetting/hb-personal-assistant`
**HEAD at evidence capture:** `e303716` (parent of the prompt-09 evidence commit)
**Prompt:** `HB_Construction_Intelligence_Phase_03_Entry_Package/prompts/Prompt_09_*`

## Outcome (one-line)

**Mailbox read-only posture: intact and verified.** Live metadata fetch is
**blocked** by a date-format defect in `MailClient.list_inbound`'s `$filter`
clause that is unrelated to scope, consent, or persistence posture. No code
was changed in this commit; the blocker is reported per the prompt's explicit
"blocker if live mailbox access cannot be tested" clause.

## 1. Runtime scopes (verbatim)

`IdentityConfig().delegated_scopes`:

```
['User.Read', 'Mail.Read', 'Calendars.ReadWrite.Shared', 'Files.ReadWrite.All', 'offline_access']
```

`hb-assistant construction-agent graph auth status --json` →
`delegated.effective_msal_scopes` (what MSAL actually requested on the most
recent silent acquisition):

```json
[
  "User.Read",
  "Mail.Read",
  "Calendars.ReadWrite.Shared",
  "Files.ReadWrite.All"
]
```

`offline_access` is removed before MSAL acquisition (reported under
`removed_reserved_scopes` in the same envelope). Neither `Mail.ReadWrite`,
`Mail.ReadWrite.All`, nor `Mail.Send` is requested at runtime by any code
path.

Note on cached-token claims: the same `graph auth status` envelope's
`delegated.scopes` array enumerates **everything admin has consented for the
app registration at the tenant** (including `Mail.ReadWrite`, `Sites.ReadWrite.All`,
etc.) — this is the audit-discovery surface for the Phase 02 grant-but-suppress
posture. Suppression is enforced at the application layer
(`configured_scopes` / `effective_msal_scopes`) which never requests any
write scope, and at the lockout-test layer (see section 4).

## 2. Live diagnostic command output

Command:

```
hb-assistant diagnostics mail --json
```

Result: **failed (live blocker)**. Verbatim Graph error tail (sanitized — only
shape, no message content):

```
GraphHttpError: GET
https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=receivedDateTime ge
2026-05-23T06:29:46.825456+00:00&$select=id,conversationId,internetMessageId,subject,from,
toRecipients,ccRecipients,receivedDateTime,bodyPreview,hasAttachments,webLink&$top=3
-> 400: Invalid filter clause: The DateTimeOffset text
'2026-05-23T06:29:46.825456' should be in format
'yyyy-mm-ddThh:mm:ss('.'s+)?(zzzzzz)?' and each field value is within valid
range.
```

Process exit code: `1`.

**Root cause:** `MailClient._inbound_window` (`src/hb_assistant/graph/mail_client.py`
line 35-37) builds the filter date with Python `datetime.isoformat()`, which
emits 6-digit microseconds (`.825456`). Microsoft Graph's OData filter parser
rejects 6-digit fractional seconds and requires the
`yyyy-mm-ddThh:mm:ss[.fff][zzzzzz]` shape (no microseconds; at most milliseconds).
The fix is a one-line `since = ... .replace(microsecond=0).isoformat()` (or
`...strftime("%Y-%m-%dT%H:%M:%SZ")`) — but is **out of scope** for this prompt,
which is an evidence-only proof and explicitly forbids touching `mail_client.py`.
Recommended follow-up: a separate `fix(graph): drop microseconds from Mail filter
DateTimeOffset` commit.

**Posture impact: none.** The failure happens client-side at HTTP request
formation; no mailbox data was retrieved, no body was touched, no mutation
endpoint was ever invoked.

## 3. Metadata fields allowed (static attestation)

Read of `src/hb_assistant/graph/mail_client.py`, `list_inbound` `$select`:

```
id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,
receivedDateTime,bodyPreview,hasAttachments,webLink
```

Per Prompt 09's allowed-field list:

| Required field          | Project's `$select` field        | Status |
| --- | --- | --- |
| message ID / immutable ID | `id`, `internetMessageId`        | ✅ |
| subject (redact allowed) | `subject`                        | ✅ (raw subject; redaction is a downstream concern) |
| sender domain            | `from` (full address; domain-only redaction in downstream layer) | ✅ (already-accepted shape per architecture doc) |
| received datetime        | `receivedDateTime`               | ✅ |
| has attachments          | `hasAttachments`                 | ✅ |
| web link                 | `webLink`                        | ✅ (already accepted by existing schema) |
| **no body**              | `bodyPreview` only — **no `body`** | ✅ (see section 4) |

## 4. Explicit no-body / no-writeback proof

**Forbidden-symbol grep across `src/hb_assistant/graph/`:**

```
$ grep -rnE "Mail\.ReadWrite\.All|Mail\.Send|/sendMail|/forward|/reply" src/hb_assistant/graph/
OK: no forbidden symbols
```

Zero matches. No mailbox mutation endpoints, no Mail.ReadWrite.All / Mail.Send
references anywhere in the Graph client tree.

**`$select` body-field scan in `mail_client.py`:**

```
$ grep -nE "select.*body[^P]" src/hb_assistant/graph/mail_client.py
72:            select += ",body"
89:        url = f"/me/messages/{message_id}?$select=id,body"
```

Both hits are on the **single-message body retrieval paths** —
`get_message(message_id, include_body=True)` and
`get_message_body_for_inspection(message_id)`:

- `get_message` only appends `,body` when **both** `include_body=True` **and**
  `cfg.mail.persist_full_body` are set; the config defaults to `False` and a
  mutation-lockout test rejects flipping it (see below).
- `get_message_body_for_inspection` retrieves a single message's body
  **in memory only** for classifier inspection; the docstring explicitly states
  "Never writes raw body to DB, logs, evidence, or cache" and the caller is
  responsible for redaction before any persistence.

The `list_inbound` `$select` (the diagnostic's path) does **not** request
`body` — only `bodyPreview` (a Graph-truncated snippet, max 255 chars), which
is the accepted Phase 02 metadata projection.

**Mutation-lockout test suite — verbatim pytest tail:**

```
python -m pytest tests/test_mutation_lockout.py tests/test_construction_*.py
...
......................................................................... [ 18%]
...........................................................................[100%]
399 passed in 4.92s
```

The 399-test pass set includes (audit-confirmed) the five mailbox-relevant
lockout tests:

- `test_no_m365_write_apis_in_graph_clients` — no write methods in Graph clients.
- `test_identity_default_scopes_do_not_request_mailbox_write_scopes` — Mail.Read
  only, no Mail.ReadWrite.All.
- `test_graph_clients_do_not_contain_mailbox_mutation_endpoints` — explicit
  mailbox write-endpoint rejection.
- `test_email_intelligence_deferred_policy_rejects_mailbox_writeback_allowed_true`
  — policy gate locks writeback.
- `test_email_intelligence_deferred_policy_rejects_persist_full_body_true` —
  policy gate locks full-body persistence.

## 5. Blocker (live live mailbox access)

| Field | Value |
| --- | --- |
| Symptom | `400 Invalid filter clause: DateTimeOffset '...' should be in format ...` |
| Layer | Graph OData filter parser (server-side) |
| Triggering call | `GET /me/mailFolders/inbox/messages?$filter=receivedDateTime ge {iso}&...` |
| Cause | `datetime.isoformat()` emits microseconds; Graph caps fractional seconds at milliseconds |
| File | `src/hb_assistant/graph/mail_client.py:35-37` (`_inbound_window`) |
| Posture impact | none — failure precedes any data retrieval; no body / no mutation touched |
| Suggested fix (separate prompt) | `since = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()` |
| Auth / scope / consent issue | none |
| Re-login required | no |

The MSAL token cache is present and valid (`expires_in: 5042`s at capture
time); silent acquisition succeeds; the cached scopes include `Mail.Read`. The
auth path is healthy. Only the OData filter formatting blocks the live call.

## Acceptance-criteria readout

| Criterion | Result |
| --- | --- |
| Mailbox read-only posture remains intact | ✅ scopes pin Mail.Read only; 399/399 lockout-and-construction tests pass; no forbidden symbols in graph tree |
| Metadata proof succeeds or blocker is clear | ✅ blocker captured precisely with file:line, root cause, and one-line fix proposal |
| No runtime scope expansion | ✅ `effective_msal_scopes` unchanged; no Mail.ReadWrite, no Mail.Send |
| No full-message-body retrieval, no body persistence, no Obsidian body projection | ✅ `list_inbound` $select excludes `body`; body paths gated by `cfg.mail.persist_full_body=False` + in-memory-only contract |
| No mailbox mutation endpoints | ✅ grep confirms zero `sendMail` / `forward` / `reply` / `Mail.ReadWrite` references |
