# 05 — Folder Discovery and Sync State (dry-run + persist)

Phase 06 Prompt 05 · read-only / metadata-only · no mailbox mutation · no new scope

Discovers Bobby's live Outlook folders through the guarded read-only client, matches them against the
active policy (include **Inbox / Sent Items / Archive**; exclude **Deleted Items / Junk Email /
Drafts**), and persists the resolved `email_source_locations` + a bounded-lookback `email_sync_state`
cursor per included folder. The mailbox is read-only (GET only, through the endpoint guard); the only
writes are local SQLite rows.

## What landed

- **`src/hb_assistant/construction/email/folder_discovery.py`** (new `construction/email/` package) —
  `EmailFolderDiscovery(mail_client, store)` with `discover(*, policy=None, dry_run=True)`. List-then-
  match: one `get_me` + one `list_mail_folders` GET, the policy-driven mailbox registry
  (`build_mailbox_source_registry`) resolved to live folders by display name, then (unless dry-run)
  `upsert_email_source_location` for every matched folder + `upsert_email_sync_state` for the included
  ones. Returns a metadata-only `FolderDiscoveryResult` (owner hash, per-folder roles/counts, summary).
- **`src/hb_assistant/cli/graph.py`** — `graph mail folders [--json] [--dry-run/--no-dry-run]` (default
  dry-run). Reuses the `status` command's provider/token/`ReadOnlyMailClient` setup; constructs
  `ConstructionStore()` + `EmailFolderDiscovery`.

## Reconciliation

The package "Workflow B" (list → match allowed → reject excluded → persist) is driven by the **active
policy** as the single source of truth: `include_folders`/`exclude_folders` feed
`build_mailbox_source_registry`, which already supplies roles (`inbox`/`sent`/`archive`/`excluded`),
`source_id`s (`outlook:{owner_hash}:{slug}`), and the sha256[:16] owner hash. Discovery resolves each
registry folder to a live Graph folder; it does not re-invent the folder taxonomy. Owner is stored only
as a hash; folder ids are surfaced in JSON as a short `folder_id_fingerprint` (not the raw opaque id).

## Live validation

### `hb-assistant graph mail folders --dry-run --json` (exit 0)

```json
{
  "command": "graph mail folders",
  "ok": true,
  "mailbox_owner_upn": "bfetting@hedrickbrothers.com",
  "mailbox_owner_hash": "69d7743a7435d27c",
  "source_system": "outlook",
  "dry_run": true,
  "persisted": false,
  "default_lookback_days": 30,
  "folders": [
    {"source_id": "outlook:69d7743a7435d27c:inbox",         "folder_role": "inbox",    "folder_display_name": "Inbox",         "include_in_sync": true,  "matched": true, "folder_id_fingerprint": "d77a29483b9c7a25", "total_item_count": 16353, "unread_item_count": 636},
    {"source_id": "outlook:69d7743a7435d27c:sent-items",    "folder_role": "sent",     "folder_display_name": "Sent Items",    "include_in_sync": true,  "matched": true, "folder_id_fingerprint": "0ff7830b5b0923c9", "total_item_count": 4787,  "unread_item_count": 0},
    {"source_id": "outlook:69d7743a7435d27c:archive",       "folder_role": "archive",  "folder_display_name": "Archive",       "include_in_sync": true,  "matched": true, "folder_id_fingerprint": "7d5cf82865db54d9", "total_item_count": 345,   "unread_item_count": 2},
    {"source_id": "outlook:69d7743a7435d27c:deleted-items", "folder_role": "excluded", "folder_display_name": "Deleted Items", "include_in_sync": false, "matched": true, "folder_id_fingerprint": "e5a46c80beb67a62", "total_item_count": 928,   "unread_item_count": 2},
    {"source_id": "outlook:69d7743a7435d27c:junk-email",    "folder_role": "excluded", "folder_display_name": "Junk Email",    "include_in_sync": false, "matched": true, "folder_id_fingerprint": "6418b394aa27e5b4", "total_item_count": 76,    "unread_item_count": 76},
    {"source_id": "outlook:69d7743a7435d27c:drafts",        "folder_role": "excluded", "folder_display_name": "Drafts",        "include_in_sync": false, "matched": true, "folder_id_fingerprint": "ab70312c40963174", "total_item_count": 7,     "unread_item_count": 0}
  ],
  "included_matched": 3,
  "excluded_matched": 3,
  "unmatched_policy_folders": [],
  "other_folders_count": 10
}
```

All 6 policy folders resolved against the live mailbox; 10 other top-level folders were left untouched.
No tokens or raw folder ids in the output (verified by leak scan).

### `hb-assistant graph mail folders --no-dry-run --json` (exit 0) → persisted

`persisted: true`, `included_matched: 3`, `excluded_matched: 3`. Read-only query of the operational DB
afterward:

```
source_location rows: 6
  role=archive   include_in_sync=True  folder_id_present=True  outlook:69d7743a7435d27c:archive
  role=inbox     include_in_sync=True  folder_id_present=True  outlook:69d7743a7435d27c:inbox
  role=sent      include_in_sync=True  folder_id_present=True  outlook:69d7743a7435d27c:sent-items
  role=excluded  include_in_sync=False folder_id_present=True  outlook:69d7743a7435d27c:deleted-items
  role=excluded  include_in_sync=False folder_id_present=True  outlook:69d7743a7435d27c:drafts
  role=excluded  include_in_sync=False folder_id_present=True  outlook:69d7743a7435d27c:junk-email

email_sync_state (included only):
  archive   status=pending mode=bounded_lookback lookback=30
  inbox     status=pending mode=bounded_lookback lookback=30
  sent      status=pending mode=bounded_lookback lookback=30
Excluded folders confirmed to have NO sync_state.
```

Persistence is idempotent (re-running updates rows in place; row count stays 6).

## Guardrails

- **Read-only:** only `GET /me` and `GET /me/mailFolders` were issued, both through
  `assert_mail_request_allowed`. No mutation path exists in the discovery service.
- **No write scope:** runtime still requests `Mail.Read` only.
- **Bounded:** `email_sync_state` initializes to `bounded_lookback` / `default_lookback_days=30` — never
  a full-mailbox backfill. Excluded folders are recorded (`include_in_sync=0`) but get **no** sync cursor.
- **No raw PII:** owner stored as sha256[:16] hash; folder ids surfaced as fingerprints in evidence.

## Verification

- `tests/test_email_folder_discovery.py` (dry-run no-persist, commit persists sources + included sync
  state, Archive-missing unmatched, idempotent recommit) + `tests/test_graph_mail_cli.py` folders case
  → pass. `test_mutation_lockout.py` / guard / client / migration tests → green.
- `ruff check .` clean; `mypy src` no issues (120 files); `compileall` OK.
- Full safe subset green **except 4 pre-existing weekend-driven `test_automation.py` failures** (today,
  2026-05-30, is a Saturday; orchestrator skips weekends) — unrelated.

## Stop conditions — none triggered

No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` request, no destructive migration, no full-body
default persistence, no attachment-content download. The only writes are local SQLite source/sync rows.
