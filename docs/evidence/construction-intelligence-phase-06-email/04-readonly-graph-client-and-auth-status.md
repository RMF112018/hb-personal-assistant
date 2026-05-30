# 04 — Read-only Graph Mail Client + Endpoint Guard + `graph mail status`

Phase 06 Prompt 04 · read-only / metadata-only · no mailbox mutation · no new scope

This prompt makes the mail read path **real**: a GET-only Graph mail client wired to the existing
`GraphHttpClient`, a runtime **endpoint guard** that refuses every mutation verb/path/keyword *before*
any HTTP call, and the first operational CLI command `hb-assistant graph mail status --json`. The
guard is the **HTTP layer** of Phase 06 defense-in-depth, beneath the Pydantic/adapter/SQLite/scope
layers already in place.

Captured live output: [`graph-mail-auth-status.json`](./graph-mail-auth-status.json).

## What landed

- **`src/hb_assistant/graph/mail_endpoint_guard.py`** — `MailboxMutationBlockedError` (sanitized:
  method + normalized path + reason only); `load_mail_endpoint_contract()` parsing the Prompt 01
  repo YAMLs; `assert_mail_request_allowed(method, path)`. Decision order is **positive-allowlist
  first**: a GET against an allowlisted read template is permitted outright, so a legitimate folder
  read addressed by well-known name (e.g. `drafts`, `deleteditems`) can never false-positive on a
  forbidden operation keyword. Everything else is blocked with the most specific reason (forbidden
  verb → forbidden path → keyword → not-on-allowlist). All forbidden literals come from the YAML, so
  no mutation-endpoint string lives in `graph/` source (keeps the `test_mutation_lockout` static
  scan green).
- **`src/hb_assistant/graph/mail_readonly_client.py`** — `ReadOnlyMailClient`: `get_me`,
  `list_mail_folders`, `get_mail_folder`, `list_messages` (folder-scoped or mailbox-wide, bounded by
  `$top` + optional `receivedDateTime` `$filter`), `get_message_metadata`, `list_attachment_metadata`.
  Every call routes through the guard, then the metadata-only `$select` (full `body` and attachment
  `contentBytes` structurally excluded). The class exposes **no** mutation method and only ever calls
  `GraphHttpClient.get` / `get_all_pages`.
- **`src/hb_assistant/cli/graph.py`** (+ registration in `cli/main.py`) — new top-level `graph` group
  with a `mail` sub-app. `graph mail status` reports auth/scope readiness (via
  `DelegatedAuthProvider.status_info()` — safe, redacted, no tokens), runs an in-process **guard
  self-test** derived from the contract, and (unless `--no-probe`) issues one bounded read-only probe
  (`/me/mailFolders`) through the guarded client. Exit 0 when mail-read scope is present, no write
  scopes are requested, and the guard self-test passes.

## Reconciliation (package ↔ repo truth)

- The package README + validation matrix specify a **top-level `graph` group**
  (`hb-assistant graph mail status …`); the repo previously had graph commands only under
  `construction-agent graph`. A new top-level `graph` Typer app was added — the command family
  Prompts 05–14 extend.
- The guard loads the existing **repo YAML** contract (`resources/config/graph_mail_*`) from Prompt 01,
  not the package's `resources/json/*.json` (already reconciled to YAML in Prompt 01).
- The minimal Phase 02 `MailClient` (`graph/mail_client.py`) was left untouched; the new read-only
  client is a separate module so existing callers don't regress and the guard layers onto the mail
  path only (not the generic `GraphHttpClient`, which also serves drive/calendar).

## Live validation — `hb-assistant graph mail status --json`

Exit 0. Key results (full JSON in the evidence file):

- **Guard self-test:** `passed: true`, `read_paths_allowed: 8`, `mutation_attempts_blocked: 18`,
  `anomalies: []` — every allowlisted GET permitted, every forbidden verb/path refused, in-process,
  no network.
- **Mail probe:** `GET /me/mailFolders` → `status: 200`, `folder_sample_count: 1` (real read-only
  call succeeded through the guarded client).
- **Guardrails:** `mailbox_read_only`, `mutation_endpoints_blocked`, `no_mail_write_scopes_requested`,
  `metadata_only_select`, `attachment_content_excluded` — all `true`.
- **Contract:** `allowed_methods: ["GET"]`, 8 allowed paths, forbidden methods
  `[DELETE, PATCH, POST, PUT]`, 14 forbidden paths.

### Observed auth-cache nuance (honest note)

`auth.token_type` reported `app_only` / `classification: unexpected` (the currently cached token
carries broad tenant grants incl. `roles: [Admin, …]` and `scp_count: 0`). This is a property of the
local MSAL cache state, **not** of this change, and does not affect read-only mail readiness: our
`effective_msal_scopes` request only `User.Read, Mail.Read, Calendars.ReadWrite.Shared,
Files.ReadWrite.All`, `forbidden_mail_scopes_requested` is empty, and the read probe succeeded. This
is the documented **grant-but-suppress** posture — the tenant may grant more than the runtime requests,
and the guard + GET-only client keep the mailbox read-only regardless. No token material appears in the
output (verified by leak scan).

## Verification

- `tests/test_graph_mail_endpoint_guard.py`, `tests/test_graph_mail_readonly_client.py`,
  `tests/test_graph_mail_cli.py` → all pass; `tests/test_graph_mail_endpoint_contract.py` (Prompt 01)
  and `tests/test_mutation_lockout.py` (static write-verb / mailbox-action scan over `graph/`) → green.
- `ruff check .` → All checks passed. `mypy src` → no issues (118 files).
  `python -m compileall -q src tests` → OK.
- Full safe subset (`-m "not integration and not live and not manual"`) → green **except 4
  pre-existing, date-driven `test_automation.py` failures** (today, 2026-05-30, is a Saturday; the
  morning orchestrator skips weekends) — confirmed unrelated to this change (same as Prompt 03).

## Stop conditions — none triggered

No mailbox mutation path (the guard makes one a hard failure), no `Mail.ReadWrite`/`Mail.Send` scope
request, no destructive migration, no full-body default persistence, no attachment-content download.
