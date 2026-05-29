# 00 — Repo-Truth Rebaseline (Phase 06 Operational Email Workflows)

**Prompt:** Phase 06 / Prompt 00 — Repo Truth Rebaseline and Graph Mail Readiness Audit
**Generated:** 2026-05-29 (audit run)
**Posture:** Read-only audit. No source/config/schema modified. Only this evidence
bundle was written. No mailbox mutation path, no `Mail.ReadWrite`/`Mail.Send` runtime
scope request, no destructive migration, no full-body default persistence, and no
attachment-content default download were introduced or required.

---

## 1. Repository identity

| Fact | Value |
| --- | --- |
| Remote | `origin → https://github.com/RMF112018/hb-personal-assistant.git` (fetch + push) |
| Full name | `RMF112018/hb-personal-assistant` |
| Default branch | `main` |
| Current branch | `main` (tracking `origin/main`) |
| HEAD | `634fbb3626663765c07749b2e9a5f3f4294b0f9c` |
| HEAD date | `2026-05-29 19:17:13 -0400` |
| HEAD subject | `docs(procore): Phase 05 Prompt 12 final validation + closeout (CLOSED · 56/59 verified)` |

### Package-baseline reconciliation

The package `02_REPO_TRUTH_AUDIT_SUMMARY.md` recorded `observed_latest_sha:
6d77d3589d2e8bf0a398ed94f0d913e54f60faec`. Repo truth has advanced **one commit
past** that baseline: HEAD is now `634fbb3`, which is the immediate child of `6d77d35`
(Phase 05 Prompt 12 closeout). The package baseline is therefore current-minus-one and
consistent with repo history; no divergence or rebase is detected.

## 2. Working tree status

```text
$ git status --porcelain=v1
?? .code-graph/
```

Only the untracked `.code-graph/` directory is present (a local pre-built code index,
not part of the package). The tree is otherwise clean. No tracked file is modified by
this audit prior to writing this evidence bundle.

## 3. Recent commits (`git log --oneline -15`)

```text
634fbb3 docs(procore): Phase 05 Prompt 12 final validation + closeout (CLOSED · 56/59 verified)
6d77d35 fix(procore): flat payment-applications path + rfq-child contract_id param; promote 3 (56 verified)
d5e3c61 fix(procore): N+1 child GET sends project_id query param; promote 6 v1.0 children (53 verified)
60d05d8 feat(procore): generalized N+1 child orchestration; promote 11 financial children (47 verified)
593071a fix(procore): reconcile change-events + budget-change-history to live shapes, promote (36 verified)
e03da64 feat(procore): live-promote 7 parentless financial endpoints (smoke-verified 2026-05-29)
f7b7d7e feat(procore): Phase 05 Prompt 11 financial query commands & Obsidian register
82d6a67 feat(procore): Phase 05 Prompt 10 live-sync dispatch verification & idempotency sweep
41bfcf9 feat(procore): Phase 05 Prompt 09 budget views, rows, changes & modifications
046e566 feat(procore): Phase 05 Prompt 08 RFQs, quotes/responses, change events & comments
7fe8d90 feat(procore): Phase 05 Prompt 07 billing periods, subcontractor invoices & invoice items
dbd003b feat(procore): Phase 05 Prompt 06 commitment change orders, CO line items & shared change-event linkage
e48640d feat(procore): Phase 05 Prompt 05 commitments, purchase orders, attachments & compliance
e88718b feat(procore): Phase 05 Prompt 04 owner-side contracts, change orders & payment applications
e7223c5 feat(procore): Phase 05 Prompt 03 shared financial normalizers + redaction utilities
```

Phase 05 (Procore Contracts & Financials) is closed at HEAD. Phase 06 builds on top of
this state.

## 4. Component inspection (repo truth vs. package claims)

### 4.1 Auth & scope policy — `src/hb_assistant/auth/`

- `scope_policy.py` is a **sanitizer**, not the scope source: `sanitize_delegated_scopes()`
  strips the three MSAL-reserved scopes (`openid`, `profile`, `offline_access`),
  de-duplicates, and preserves order. `get_scope_diagnostics()` exposes
  `configured_scopes` / `effective_msal_scopes` / `removed_reserved_scopes`.
- The actual requested scopes come from config `identity.delegated_scopes`
  (`src/hb_assistant/config/models.py:22`):
  `["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All", "offline_access"]`.
- **Mail scope reconciliation:** the requested mail scope is `Mail.Read` only. There is
  **no** `Mail.ReadWrite`, `Mail.ReadWrite.All`, or `Mail.Send` in the requested set. This
  matches the Phase 06 hard boundary. (Calendars/Files request write-capable scopes, which
  are out of scope for this mail-only phase and unchanged here.)
- `EXPECTED_GRAPH_SCOPES` in `scope_policy.py` lists `mail.read` (read-only) as the
  canonical mail scope.

### 4.2 Graph clients — `src/hb_assistant/graph/`

- `http_client.py` (`GraphHttpClient`) exposes a **GET-only** HTTP surface: `get()`,
  `get_all_pages()` (bounded by `max_pages`/`max_items`, follows `@odata.nextLink`), and
  `download_to_file()` (a streamed **GET**). A static grep found **no** `post`/`patch`/
  `delete`/`put` methods and no `method="POST|PATCH|DELETE|PUT"` calls. Retry on 429/5xx
  and sanitized errors are present.
- `mail_client.py` (`MailClient`) methods: `list_inbound()`, `list_sent()`,
  `get_message()`, `get_message_body_for_inspection()`. A static grep found **no**
  send/create/draft/update/delete/move/copy/forward/reply/mark/categorize/flag method.
- Body handling is already guarded: `get_message()` only adds `,body` to `$select` when
  `include_body and self.cfg.mail.persist_full_body` — and `persist_full_body` defaults to
  `False`. `get_message_body_for_inspection()` is explicitly in-memory-only, truncated, and
  documents that it never writes raw body to DB/logs/evidence/cache.

### 4.3 Store migrator — `src/hb_assistant/store/migrator.py`

- Versioned, **additive** migrations applied in order: V1→V2→V3→V4→V5→V6→V7→V8→V9.
  `apply()` returns the latest version; max applied version is **9**
  (`v9_procore_billing_and_subcontractor_invoices`). (Note: the README CLAUDE.md text says
  "V1…V7"; repo truth has since extended to V9 via Phase 05. Documentation drift only — no
  conflict for Phase 06.)
- Phase 06-relevant schema floor already present in **V5**:
  `construction_email_intelligence_deferred_state` with hard `CHECK` constraints —
  `mailbox_writeback_allowed = 0` and `persist_full_body = 0` — plus `mail_read_all_granted`
  and `mail_readwrite_all_granted` columns recording tenant consent.
- Legacy V1 `emails` / `attachments` tables exist (minimal normalized model). Per the
  package gap analysis, these are insufficient for operational Phase 06 (no mailbox source
  registry, folder sync state, crawl receipts, message metadata, recipients, attachment
  metadata, project match, relationship candidate, thread summary, or email review-queue
  tables). Any new Phase 06 tables must be **additive (V10+)** and must not touch V1–V9.

### 4.4 Email deferred policy — `src/hb_assistant/construction/policy/email_deferred.py`

- `EmailIntelligenceDeferredPolicy` (Pydantic) locks three fields with `Literal`:
  `mailbox_writeback_allowed: Literal[False]`, `persist_full_body: Literal[False]`,
  `review_required_for_sensitive: Literal[True]`. `extra="forbid"`.
- `mail_read_all_granted` / `mail_readwrite_all_granted` are plain booleans recording
  tenant-level consent with **no runtime side-effect** — the MSAL request still asks only
  for `Mail.Read`.
- Seed exists: `resources/config/email_intelligence_deferred_policy.yaml`.

### 4.5 Review routing — `src/hb_assistant/store/migrator.py` (V3) + repositories

- V3 defines `construction_review_queue`; V5 adds `construction_processing_receipts`,
  `construction_sync_errors`, and project match tables with a `review_required` index.
  Phase 06 sensitive/low-confidence routing should layer onto this existing review-queue
  pattern (additive email-specific queue), not replace it.

### 4.6 Obsidian writers — `src/hb_assistant/obsidian/`

- `writer.py` + `brief.py` are the source-linked vault writers. The hard invariant (source
  traceability; never leak raw delta links/tokens/full bodies/PEMs) governs all Phase 06
  Obsidian output (manifests, receipts, project correspondence summaries, review notes,
  meeting-prep context).

### 4.7 Phase 04B / 05 evidence

- `docs/evidence/` contains: `construction-intelligence-phase-01`, `-02`, `-03`,
  `-03-entry`, `-04`, `-04a`, `-04b`, `-05-financials`. Phase 04B and 05 bundles exist and
  are the link targets for Phase 06 email→Procore/financial relationship candidates.
- No `construction-intelligence-phase-06-email` directory existed prior to this prompt; it
  is created here for the Phase 06 evidence bundle.

### 4.8 CLI surface — operational gap (expected)

- There is **no** top-level `hb-assistant graph mail` command group yet. The repo exposes
  `hb-assistant diagnostics graph --safe --json` and `hb-assistant diagnostics mail --json`
  (a 3-item redacted inbound sample), and a separate `construction-agent graph` group.
- The operational commands required by the package README (`graph mail status / folders /
  discover / index / relationships / review-queue / summarize / meeting-prep / obsidian /
  no-mutation-proof`) are **not yet implemented**. This is the operational build target for
  Phase 06 Prompts 04–14, not a defect at Prompt 00.

## 5. Baseline validations

All run inside `.venv` (`/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python`).

| Check | Command | Result |
| --- | --- | --- |
| Byte-compile | `python -m compileall -q src` | **OK** |
| Lint | `ruff check .` | **All checks passed!** (exit 0) |
| Type-check | `mypy src` | **Success: no issues found in 115 source files** |
| Relevant tests | `pytest tests/test_auth.py tests/test_graph_clients.py tests/test_mutation_lockout.py tests/test_construction_store_repositories.py -m "not integration and not live and not manual"` | **75 passed** in 0.75s |
| Full safe suite | `pytest -m "not integration and not live and not manual"` | **1244 passed, 1 skipped, 1 deselected** in 41.27s |

Notes:
- `ruff`/`mypy` scope is intentionally partial per `pyproject.toml`; the clean result
  reflects in-scope modules. The mail/auth/store modules inspected above are in-scope.
- `integration`/`live`/`manual` markers were excluded; `live` (`HB_PROCORE_LIVE=1`) was
  **not** set — no real Procore HTTP was performed.

### 5.1 Read-only runtime probes (delegated, no mutation)

```text
$ hb-assistant diagnostics graph --safe --json
{ "safe": true, "probes": [ { "path": "/me", "status": 200,
  "sample": { "id_present": true, "upn": "bfetting@hedrickbrothers.com" } } ], ... }
```

`/me` returned 200 under Bobby's delegated context — Graph connectivity is healthy. Auth
scope readiness is detailed in `mail-permission-readiness-proof.md`.

## 6. Rebaseline conclusion

- Repo identity, branch, HEAD, status, and history are verified and consistent with the
  package baseline (current-minus-one).
- The auth/scope, GET-only Graph client, additive migrator, deferred-policy locks, review
  queue, and Obsidian writer guardrails are all present and green.
- The mail scope requested at runtime is `Mail.Read` only — compliant with Phase 06 hard
  boundaries.
- The operational `graph mail` CLI workflows do not yet exist and are the Phase 06 build
  target (Prompts 04–14), to be implemented additively (schema V10+).
- No stop condition was triggered by this audit.
