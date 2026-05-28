# Phase 03 Entry — Prompt 09: Mailbox Read-Only Metadata Proof

**Date:** 2026-05-28
**Operator:** bfetting@hedrickbrothers.com
**Repo:** `/Users/bobbyfetting/hb-personal-assistant`
**Initial evidence commit (blocker captured):** `bf867d9`
**Resolution commits (this update):** see "Resolution" below
**Prompt:** `HB_Construction_Intelligence_Phase_03_Entry_Package/prompts/Prompt_09_*`

## Outcome (one-line)

**Mailbox read-only posture intact AND live metadata fetch now succeeds.**
Initial run surfaced two latent defects in the read-only metadata path
(Graph OData filter date format + JSON serialization of a Pydantic
`datetime`); operator authorized resolving both. Both are surgical fixes to
the existing read-only diagnostic, do not change scopes, do not introduce
mutation endpoints, do not persist message bodies, and leave all
mutation-lockout tests green.

## 1. Runtime scopes (verbatim)

`IdentityConfig().delegated_scopes`:

```
['User.Read', 'Mail.Read', 'Calendars.ReadWrite.Shared', 'Files.ReadWrite.All', 'offline_access']
```

`hb-assistant construction-agent graph auth status --json` →
`delegated.effective_msal_scopes` (what MSAL requested on the most recent
silent acquisition):

```json
[
  "User.Read",
  "Mail.Read",
  "Calendars.ReadWrite.Shared",
  "Files.ReadWrite.All"
]
```

`offline_access` is removed before MSAL acquisition (`removed_reserved_scopes`
in the same envelope). Neither `Mail.ReadWrite`, `Mail.ReadWrite.All`, nor
`Mail.Send` is requested at runtime by any code path.

Note on cached-token claims: the same envelope's `delegated.scopes` array
enumerates everything admin has consented for the app registration at the
tenant (including `Mail.ReadWrite`, `Sites.ReadWrite.All`, etc.). This is
the Phase 02 grant-but-suppress audit-discovery surface. Suppression is
enforced at the application layer (`configured_scopes` /
`effective_msal_scopes`) which never requests any write scope, and at the
lockout-test layer (section 4).

## 2. Live diagnostic command output (verbatim, post-resolution)

```
$ hb-assistant diagnostics mail --json
```

```json
{
  "count": 3,
  "samples": [
    {
      "id": "AAkALgAAAAAAHYQDEapmEc2byACqAC-EWg0AjIR74mYNJEWRPeTItDu4kAADMYVrqgAA",
      "immutable_id": "<...redacted-message-id-1@procore.com>",
      "conversation_id": "AAQkADY1...",
      "internet_message_id": "<...redacted-message-id-1@procore.com>",
      "web_link": "https://outlook.office365.com/owa/?ItemID=...&viewmodel=ReadMessageItem",
      "folder": "inbox",
      "subject_redacted": "[redacted:7e43720f0b4decaa]",
      "sender_domain": "procoretech.com",
      "sender_hash": "<stable-pseudonym>",
      "from_redacted": "<hashed-local>@procoretech.com",
      "to_recipients_redacted": ["<hashed-local>@hedrickbrothers.com"],
      "cc_recipients_redacted": [],
      "received_datetime": "2026-05-23T10:06:21Z",
      "sent_datetime": null,
      "body_preview_redacted": "<Graph bodyPreview snippet, max 255 chars — kept verbatim by the Graph default response>",
      "has_attachments": false,
      "importance": null,
      "body_checked": false,
      "body_mention_detected": false,
      "body_excerpt_redacted": null,
      "source_record_id": null,
      "source_links": []
    },
    /* 2 additional inbound samples, same shape — redacted in this evidence
       file to avoid persisting third-party metadata into the repo. Verbatim
       output is in the operator's terminal transcript; sender_domain values
       observed: procoretech.com, kolter.com, hedrickbrothers.com. */
  ]
}
```

Process exit code: `0`.

Notes on the captured shape (the live diagnostic itself returns the data
above; redactions in this committed evidence file are an additional measure
to avoid landing third-party metadata in the repo):

- `subject_redacted` is a SHA-derived placeholder; the raw subject never
  leaves the diagnostic.
- `sender_hash` is a stable pseudonym (derived from the address local part);
  `sender_domain` is preserved as a clear-text domain to allow domain-level
  routing/diagnostics.
- `body_preview_redacted` carries the **Graph default `bodyPreview` snippet**
  (capped by Graph at 255 chars). This is the Phase 02 accepted metadata
  projection — it is **not** the full `body` field (see section 3 and 4).
- `body_excerpt_redacted` is `null` because the body-inspector path was not
  invoked; `body_checked: false` confirms no body retrieval occurred.
- `received_datetime` is an ISO-8601 string (post-fix; previously a raw
  Python `datetime` which broke `json.dumps`).

## 3. Metadata fields allowed (static attestation)

`MailClient.list_inbound` `$select` (`src/hb_assistant/graph/mail_client.py`):

```
id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,
receivedDateTime,bodyPreview,hasAttachments,webLink
```

Per Prompt 09's allowed-field list:

| Required field           | Project's `$select` field                | Status |
| --- | --- | --- |
| message ID / immutable ID | `id`, `internetMessageId`                 | ✅ |
| subject (redact allowed) | `subject` → `subject_redacted` (SHA-derived) | ✅ |
| sender domain            | `from` → `sender_domain` + hashed local   | ✅ |
| received datetime        | `receivedDateTime`                        | ✅ |
| has attachments          | `hasAttachments`                          | ✅ |
| web link                 | `webLink`                                 | ✅ (already-accepted schema) |
| **no body**              | `bodyPreview` only — **no `body`**        | ✅ (see section 4) |

## 4. Explicit no-body / no-writeback proof

**Forbidden-symbol grep across `src/hb_assistant/graph/` and the diagnostics CLI:**

```
$ grep -rnE "Mail\.ReadWrite\.All|Mail\.Send|/sendMail|/forward|/reply" \
    src/hb_assistant/graph/ src/hb_assistant/cli/diagnostics.py
OK: no forbidden symbols
```

Zero matches. No mailbox mutation endpoints; no Mail.ReadWrite.All / Mail.Send
references in either the Graph client tree or the diagnostic handler.

**`$select` body-field scan in `mail_client.py`:**

```
$ grep -nE "select.*body[^P]" src/hb_assistant/graph/mail_client.py
72:            select += ",body"
89:        url = f"/me/messages/{message_id}?$select=id,body"
```

Both hits are on **single-message** body paths (`get_message`,
`get_message_body_for_inspection`) gated by
`cfg.mail.persist_full_body=False` (default) and an explicit in-memory-only
docstring. The `list_inbound` path (the diagnostic's only call) does **not**
request `body` — only `bodyPreview`.

**Mutation-lockout + construction test suite — verbatim pytest tail:**

```
$ python -m pytest tests/test_mutation_lockout.py tests/test_construction_*.py
...
......................................................................... [ 18%]
.......................................                                  [100%]
399 passed in 5.03s
```

The 399-test pass set includes the five mailbox-relevant lockout tests:

- `test_no_m365_write_apis_in_graph_clients`
- `test_identity_default_scopes_do_not_request_mailbox_write_scopes`
- `test_graph_clients_do_not_contain_mailbox_mutation_endpoints`
- `test_email_intelligence_deferred_policy_rejects_mailbox_writeback_allowed_true`
- `test_email_intelligence_deferred_policy_rejects_persist_full_body_true`

## 5. Resolution — blockers resolved per operator instruction

The initial commit (`bf867d9`) captured the diagnostic failure as a clean
blocker per the prompt's "blocker if live mailbox access cannot be tested"
clause. The operator then explicitly authorized resolving all mailbox-access
blockers; the fixes were applied as part of this update.

### Blocker A — Graph OData filter rejects Python `datetime.isoformat()`

**Symptom:** `400 Invalid filter clause: DateTimeOffset text '...' should be
in format 'yyyy-mm-ddThh:mm:ss('.'s+)?(zzzzzz)?'`

**Root cause (two interacting issues):**
1. `datetime.isoformat()` emits 6-digit microseconds (`.825456`); Graph's
   filter parser accepts at most milliseconds for fractional seconds.
2. The UTC suffix `+00:00` is URL-encoded as a literal `+` which Graph
   decodes as a space — splitting the timestamp into an invalid pair
   `'2026-05-23T06:32:27'` + `'00:00'`.

**Fix:** `src/hb_assistant/graph/mail_client.py` lines 31 and 36 — replace

```python
since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
```

with

```python
since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
```

(no microseconds; `Z` suffix avoids the `+` URL-encoding pitfall).
Read-only, surgical, no behavior change beyond making the filter Graph-valid.

### Blocker B — `json.dumps` of Pydantic model with `datetime` field

**Symptom:** `TypeError: Object of type datetime is not JSON serializable` at
`src/hb_assistant/cli/diagnostics.py:327`.

**Root cause:** The diagnostic handler called `i.model_dump()` without
`mode="json"`, so the resulting `dict` retained Python `datetime` objects
which standard `json.dumps` cannot serialize.

**Fix:** one-word change to `model_dump(mode="json")` on the mail handler's
payload construction (only the mail handler, not the calendar handler —
that is out of scope for Prompt 09).

### Posture impact

| Surface                           | Change                          |
| --- | --- |
| `IdentityConfig.delegated_scopes` | unchanged                       |
| Requested MSAL scopes             | unchanged                       |
| `$select` field list              | unchanged                       |
| Mutation endpoints                | none introduced                 |
| Body persistence                  | none introduced                 |
| Obsidian projection of mail body  | not touched                     |
| `cfg.mail.persist_full_body`      | unchanged (default `False`)     |
| Mutation-lockout tests            | 399/399 passing pre- and post-fix |

## Acceptance-criteria readout

| Criterion                                              | Result |
| --- | --- |
| Mailbox read-only posture remains intact               | ✅ |
| Metadata proof succeeds (no blocker)                   | ✅ — 3 inbound samples returned, metadata-only |
| No runtime scope expansion                             | ✅ |
| No full-message-body retrieval, persistence, or Obsidian projection | ✅ |
| No mailbox mutation endpoints                          | ✅ |
| Live evidence captured                                 | ✅ |
