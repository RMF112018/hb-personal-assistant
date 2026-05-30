# 02 — Graph Auth & Permission Posture (Deferred) + No-Writeback Proof

**Prompt:** Prompt 02 — Permission Posture Deferred and No-Writeback Guardrails
**Phase:** HB Construction Intelligence Phase 06 — SharePoint / OneDrive File Intelligence
**Date:** 2026-05-30
**Posture:** Behavior-level no-writeback guardrail + proof added. **No scopes changed.** Permission
tightening remains **deferred** (see `22-deferred-permission-tightening-record.md`).

---

## 1. Current Effective Permission Posture (documented, not changed)

### Configured runtime delegated scopes — `config/models.py` `IdentityConfig.delegated_scopes`

```
User.Read, Mail.Read, Calendars.ReadWrite.Shared, Files.ReadWrite.All, offline_access
```

`Files.ReadWrite.All` is **write-capable** and broader than the read-only file work this phase
performs. The construction resolver (`construction/graph/resolver.py:40,43`) also requests
`["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]`.

### Tenant-consented app-registration scopes (observed in Prompt 00, `00-repo-truth-baseline.md` §4)

The consented set additionally includes write/management-capable file & site permissions:

```
AllSites.FullControl, Files.ReadWrite.All, Group.ReadWrite.All,
Sites.FullControl.All, Sites.Manage.All, Sites.ReadWrite.All, Sites.Selected
```

### Live auth snapshot at this prompt (redacted — scope NAMES only, no tokens)

- `hb-assistant auth status --json` → `mode=delegated`, `token_type=delegated`,
  `classification=delegated`, UPN domain `@hedrickbrothers.com`. (The currently cached delegated
  token did not surface a scope list; the authoritative over-broad signal is the configured +
  tenant-consented scopes above.)
- `hb-assistant diagnostics graph --safe --json` → `GET /me` returned `200` (delegated read works).

No tokens, Authorization headers, signed URLs, or raw delta links are recorded here.

---

## 2. Behavior-Level No-Writeback Proof (added this prompt)

Even with broad write-capable scopes granted, the implementation is **behaviorally read-only**. This
is enforced and proven independently of the granted scopes.

### New runtime guard — `src/hb_assistant/graph/files_endpoint_guard.py`

Mirrors `graph/mail_endpoint_guard.py`. Loads the Prompt 01 YAML contract
(`resources/config/graph_files_*.yaml`) into a frozen `FilesEndpointContract` and exposes
`assert_files_request_allowed(method, path)` — positive-allowlist-first: a GET against an
allowlisted read template is permitted; any non-GET verb, forbidden path, or forbidden operation
keyword raises `FileMutationBlockedError` **before** any HTTP request. The module holds **no literal
mutation-endpoint strings** (loaded from YAML), keeping `test_mutation_lockout`'s static scan of
`graph/**.py` clean.

> Enforcement wiring into a live files read client lands with the discovery client (Prompt 04); the
> guard + self-test + proof command are delivered now. This is the same author-then-wire sequencing
> the mail track used.

### New proof command — `hb-assistant graph files no-writeback-proof --json`

Offline, deterministic. Output captured this prompt (`ok: true`):

```json
{
  "command": "graph files no-writeback-proof",
  "ok": true,
  "permission_tightening": "deferred",
  "auth": {
    "available": true,
    "token_type": "delegated",
    "classification": "delegated",
    "configured_delegated_scopes": ["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared",
                                    "Files.ReadWrite.All", "offline_access"],
    "broad_file_write_scopes_present": ["Files.ReadWrite.All"],
    "permission_tightening": "deferred"
  },
  "guard_self_test": { "passed": true, "read_paths_allowed": 22, "mutation_attempts_blocked": 19,
                       "anomalies": [] },
  "static_scan": { "dirs_scanned": ["src/hb_assistant/graph", "src/hb_assistant/construction/graph",
                                    "src/hb_assistant/files"],
                   "files_scanned": 28, "mutation_method_calls_found": 0, "violations": [] },
  "contract": { "allowed_methods": ["GET"], "allowed_paths_count": 22,
                "forbidden_methods": ["DELETE", "PATCH", "POST", "PUT"], "forbidden_paths_count": 15,
                "forbidden_keywords_count": 15, "never_persist_count": 7 },
  "guardrails": { "microsoft_365_writeback": "none", "file_mutation_endpoints_blocked": true,
                  "no_mutation_method_calls_in_file_services": true, "metadata_only_select": true,
                  "download_url_never_persisted": true, "permission_tightening": "deferred" }
}
```

The proof asserts three independent facts:

1. **Guard self-test** — all 22 allowlisted GET templates permitted; all 19 mutation attempts
   (forbidden paths + forbidden verbs) blocked; zero anomalies.
2. **Source static scan** — 28 files across `graph/`, `construction/graph/`, `files/` contain **zero**
   mutating HTTP verb calls (`.post/.put/.patch/.delete`).
3. **Contract** — GET-only allowlist; `POST/PUT/PATCH/DELETE` blocklist; `@microsoft.graph.downloadUrl`
   + tokens + raw delta/next links in `never_persist`.

---

## 3. Four-Layer Read-Only Defense-in-Depth (independent of granted scopes)

| Layer | Mechanism |
| --- | --- |
| Source policy | `SourceLocation.read_only: Literal[True]`; `DefaultPolicies` pin `copy_originals_to_vault=False`, `store_full_text_in_vault_notes=False`. |
| SQLite | `CHECK(read_only = 1)` on `construction_source_locations`; deferred-state `CHECK(mailbox_writeback_allowed = 0)`. |
| Endpoint guard | `files_endpoint_guard.assert_files_request_allowed` refuses non-GET / mutation paths before HTTP (new this prompt). |
| Static tests | `tests/test_mutation_lockout.py` now scans `graph/` + `construction/graph/` + `files/` for write verbs; `tests/test_graph_files_endpoint_contract.py` + `test_graph_files_endpoint_guard.py` lock the contract + guard. |
| Config default | `AppConfig.security.microsoft_365_writeback_enabled == False`. |

---

## 4. Validation Recorded

- `ruff check .` PASS; `ruff format` applied to `cli/graph.py`; `mypy src` PASS (130 files);
  `compileall` PASS.
- `pytest tests/test_graph_files_endpoint_contract.py tests/test_graph_files_endpoint_guard.py
  tests/test_mutation_lockout.py tests/test_graph_mail_endpoint_contract.py
  tests/test_graph_mail_endpoint_guard.py` → all green.
- Full default-safe suite: **1569 tests, 12 failures, 0 errors, 1 skipped** — the 12 failures are the
  pre-existing email-track `upsert_email_model_classification` regression documented in
  `00-repo-truth-baseline.md`; **no new failures** introduced by this prompt.

---

## 5. Stop-Condition Check

No stop condition triggered. No Microsoft 365 writeback was introduced (the opposite — a guard that
refuses it), **no permission tightening was attempted**, no source files were copied into Obsidian,
no full source text was persisted, no raw delta links were exposed, and no sensitive-file review
routing was bypassed. The over-broad-permission risk is documented and deferred.
