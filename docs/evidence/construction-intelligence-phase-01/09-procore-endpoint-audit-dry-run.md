# Phase 01 — Prompt 09 / Step 10: Procore Foundation & Endpoint Audit (Dry-Run)

Foundation for the Procore integration. Read-only by construction; no live
API call is wired. The endpoint contract enforces every guardrail at the
Pydantic schema level (a writeback endpoint cannot be loaded;
correspondence is forced to `status="excluded"`; schedule + tasks are
forced to `status="deferred"`).

## Implementation summary

- New module `src/hb_assistant/procore/` (5 files): `models.py`,
  `loader.py`, `auth.py` (documented stub — never reads env values,
  never opens the token cache), `auditor.py` (pure projection), and an
  `__init__.py` exporting the public surface.
- Two seeded YAMLs: `resources/config/procore_endpoint_contract.seed.yaml`
  (13 endpoints across 6 validated, 4 sensitive-validated, 1 excluded, 2
  deferred categories) and `resources/config/procore_projects.seed.yaml`
  (tropical = pilot at `23-435-01`, hilltop = pending).
- Pydantic-generated schema artifact
  `resources/schemas/procore_endpoint_contract.schema.json`.
- New top-level CLI sub-app `src/hb_assistant/cli/procore.py` with
  `auth status`, `tools list`, `tools audit --project KEY`, and
  `mapping validate`. Wired into `cli/main.py` alongside the existing
  `construction-agent` sub-app.
- 36-test suite at `tests/test_procore_endpoint_audit.py` including a
  module-level import scan asserting no `requests` / `httpx` / `urllib3`
  / `aiohttp` makes it into the audit path.
- Operator runbook updated at
  `docs/operations/construction-agent-operator-runbook.md` with a Procore
  section covering all four commands and the env-var matrix.

## Changed files

```
A  resources/config/procore_endpoint_contract.seed.yaml
A  resources/config/procore_projects.seed.yaml
A  resources/schemas/procore_endpoint_contract.schema.json
A  src/hb_assistant/procore/__init__.py
A  src/hb_assistant/procore/auditor.py
A  src/hb_assistant/procore/auth.py
A  src/hb_assistant/procore/loader.py
A  src/hb_assistant/procore/models.py
A  src/hb_assistant/cli/procore.py
A  tests/test_procore_endpoint_audit.py
A  docs/evidence/construction-intelligence-phase-01/09-procore-endpoint-audit-dry-run.md
M  src/hb_assistant/cli/main.py
M  docs/operations/construction-agent-operator-runbook.md
```

## Validation

```
$ python -m pytest tests/test_procore_endpoint_audit.py
36 passed in 0.50s

$ python -m pytest tests/test_construction_*.py tests/test_procore_*.py \
                   tests/test_store.py tests/test_store_links.py tests/test_config.py
227 passed in 2.82s

$ python -m pytest tests/ (broader sweep, excluding documented hang-prone files)
259 passed, 11 deselected in 3.14s

$ python -m pytest tests/test_cli_canonical.py -k 'help_parses or _shape' -q
4 passed

$ ruff check src/hb_assistant/procore/ src/hb_assistant/cli/procore.py \
             src/hb_assistant/cli/main.py tests/test_procore_endpoint_audit.py
All checks passed!
```

The audit module passes a module-import scan asserting it never imports
`requests`, `httpx`, `urllib3`, or `aiohttp`
(`test_procore_module_imports_no_http_client`). Live access is structurally
impossible in this prompt's surface — by construction, not by convention.

## CLI smoke (all dry-run; no live call)

### `hb-assistant procore auth status --json`

```json
{
  "command": "hb-assistant procore auth status",
  "report": {
    "status": "env_absent",
    "env_keys_present": [],
    "env_keys_missing": [
      "PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET", "PROCORE_REFRESH_TOKEN"
    ],
    "token_cache_present": false,
    "ready_for_live_calls": false,
    "hint": "No Procore credentials detected. Live access is deferred …"
  }
}
```

`ready_for_live_calls` stays `false` even when every env key is present —
live calls are gated at the module level (no HTTP client is wired), not
just at the credential check.

### `hb-assistant procore tools list --json`

Loaded contract: **13 endpoints**.

| status | count | notes |
| --- | --- | --- |
| validated | 6 | projects, rfis, submittals, drawings, daily-logs, punch-items |
| sensitive_validated | 4 | change-events, commitments, prime-contracts, invoices (all `sensitivity: high`) |
| excluded | 1 | correspondence (hard guardrail) |
| deferred | 2 | schedule, tasks (hard guardrail) |

Every endpoint carries `http_method: GET`. The Pydantic schema rejects
any non-GET method at load time.

### `hb-assistant procore tools audit --project tropical --json`

Access matrix for the pilot project `23-435-01`:

| verdict | count |
| --- | --- |
| would_audit | 6 |
| sensitive_review_required | 4 |
| excluded | 1 |
| deferred | 2 |

Full per-endpoint verdict table is in the captured CLI transcript. Every
sensitive-validated endpoint (financials, contracts) gets
`sensitive_review_required` — a controller would review each before
authorizing live access.

### `hb-assistant procore tools audit --project unknown --json` (error path)

```json
{
  "command": "hb-assistant procore tools audit",
  "status": "not_found",
  "requested": "unknown",
  "available": ["tropical", "hilltop"]
}
```

Exit code: `1`.

### `hb-assistant procore mapping validate --json`

```json
{
  "report": {
    "company_id": "5280",
    "total": 2,
    "by_status": {"pilot": 1, "pending": 1},
    "rows": [
      {"hb_project_key": "tropical", "procore_project_id": "23-435-01",
       "procore_project_name": "Tropical", "status": "pilot", "mapped": true},
      {"hb_project_key": "hilltop", "procore_project_id": "",
       "procore_project_name": "", "status": "pending", "mapped": false}
    ],
    "ok": false
  }
}
```

Exit code: `1` (informational — pilot mapping is incomplete by design;
hilltop has not been mapped yet).

## Guardrails attested

- **Read-only Procore access only.** `ProcoreEndpoint.http_method` is
  `Literal["GET"]`; the schema rejects any other method at load time.
  Tested by `test_endpoint_rejects_non_get_method`.
- **No Procore writeback.** No HTTP client module created. The auditor
  is pure projection over loaded YAML. Asserted at the module-import
  level by `test_procore_module_imports_no_http_client`.
- **Correspondence excluded.** Seed contract carries
  `status="excluded"`; the Pydantic model raises if any future edit
  changes the status. Auditor reports `verdict="excluded"` regardless of
  mapping status. Tested by `test_contract_rejects_correspondence_not_excluded`.
- **Schedule / tasks deferred.** Seed contract carries
  `status="deferred"`; Pydantic model raises if any future edit changes
  the status. Auditor reports `verdict="deferred"`. Tested by
  `test_contract_rejects_schedule_not_deferred`.
- **Financials included but sensitive.** Change-events, commitments,
  prime-contracts, invoices carry `status="sensitive_validated"` +
  `sensitivity="high"`; auditor routes all four to
  `sensitive_review_required`. Verified in the tropical audit transcript
  (4 `sensitive_review_required` rows).
- **No live external call.** Auth status checks env-var/file presence
  only. The auth report never echoes credential values
  (`test_auth_status_never_leaks_env_values`).
- **SQLite untouched.** No schema migration. No new table. No new
  persistence — the audit is computed on demand from configs.

## Known limitations

- Live Procore OAuth flow is intentionally deferred. The auth-status
  command reports presence/absence only and `ready_for_live_calls`
  stays `false` even when all env keys are set.
- Mapping registry ships with one pilot (`tropical → 23-435-01`) and one
  pending (`hilltop`). Operator must populate hilltop and any future
  projects before extending the audit to them.
- Full `python -m pytest` remains out of scope per the hang-prone
  exclusion list documented across prior prompts. The 4 pre-existing
  `test_obsidian_writer` baseline failures remain unrelated.
- The package-referenced
  `09_Procore_Foundation_And_Endpoint_Validation_Plan.md` and
  `resources/schemas/procore_endpoint_contract.schema.json` (external
  package payloads) do not exist in the repo — the repo's authoritative
  artifacts are
  `resources/config/procore_endpoint_contract.seed.yaml` and the
  generated `resources/schemas/procore_endpoint_contract.schema.json`.
