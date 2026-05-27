# Phase 02 — Prompt 00 — Preflight and Phase 01 Acceptance Rebaseline

## 1. Summary

This is the kickoff evidence for HB Construction Intelligence **Phase 02**. The prompt is documentation-only: it rebaselines the working tree against the user-reported Phase 01 closeout commit, attests vault-package governance, enumerates the acceptance gaps inherited from Phase 01 (so Phase 02 can address them deliberately), and creates the Phase 02 evidence root by landing this file.

No source modules, tests, schemas, or resource configs were modified. No SQLite migrations applied. No external system was contacted. The only artifact produced by this prompt is this evidence file.

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before | `34728c11cc4058fb7f86558e8e85b3789ae50962` ("chore(construction-agent): close phase 01 implementation evidence") |
| HEAD after  | `34728c11cc4058fb7f86558e8e85b3789ae50962` (no commits land until validation + this evidence file are both ready; the post-commit hash will be recorded once committed) |
| Working tree before | clean (`git status --short` empty) |
| Working tree after (pre-commit) | one new untracked file — `docs/evidence/construction-intelligence-phase-02/00-phase-02-preflight-and-phase-01-acceptance-rebaseline.md` |

Last five commits at start of this prompt:

```text
34728c1 chore(construction-agent): close phase 01 implementation evidence
2d43fd3 test(construction-agent): add validation fixtures and harness
8dd32e1 feat(construction-agent): add procore endpoint audit foundation
d55ba07 feat(construction-agent): add cli surface
aea535b feat(construction-agent): add ollama structured classification
```

## 3. Files Changed

**Created (1):**

- `docs/evidence/construction-intelligence-phase-02/00-phase-02-preflight-and-phase-01-acceptance-rebaseline.md` — this file. Establishes the Phase 02 evidence root.

**Modified:** none.
**Deleted:** none.
**Migrations applied:** none.

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 — "Obsidian Vault Planning and Implementation Package Governance" (lines 67–82) | Read and honored |
| `.grok/skills/vault-package-governance/SKILL.md` | Read and honored |
| `docs/evidence/construction-intelligence-phase-01/session-handoff.md` | Carried forward as context from prior session (still authoritative) |
| `docs/evidence/construction-intelligence-phase-01/11-final-closeout-summary.md` | Carried forward as context from prior session |
| Phase 02 implementation package README | Read |

Vault-package governance posture for Phase 02:

- Implementation-package payloads will not be copied into `docs/plans/**`. The package at `/Users/bobbyfetting/Downloads/HB_Construction_Intelligence_Phase_02_Implementation_Package/` is consumed as guidance only; repo truth wins on every conflict.
- `docs/evidence/**` remains evidence-only; no normative architecture content will be written there.
- Existing Phase 01 evidence files are immutable from this prompt forward.
- All surgical patches will preserve existing files; no rewrites without an explicit prompt.

## 5. Validation Commands and Outputs

All commands executed from `/Users/bobbyfetting/hb-personal-assistant`. Date: 2026-05-27.

### 5.1 `git status --short`

```text
(empty)
```

### 5.2 `git diff --stat`

```text
(empty)
```

### 5.3 `git rev-parse HEAD`

```text
34728c11cc4058fb7f86558e8e85b3789ae50962
```

### 5.4 `git log --oneline -5`

```text
34728c1 chore(construction-agent): close phase 01 implementation evidence
2d43fd3 test(construction-agent): add validation fixtures and harness
8dd32e1 feat(construction-agent): add procore endpoint audit foundation
d55ba07 feat(construction-agent): add cli surface
aea535b feat(construction-agent): add ollama structured classification
```

### 5.5 `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```text
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 90%]
........................                                                 [100%]
240 passed in 2.83s
```

### 5.6 `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```text
All checks passed!
```

### 5.7 `hb-assistant construction-agent validate --json`

```json
{
  "command": "construction-agent validate",
  "checks": [
    {"name": "schema",           "ok": true, "detail": "schema_version=4", "error": null},
    {"name": "source_registry",  "ok": true, "detail": "2 projects, 3 sources", "error": null},
    {"name": "review_rules",     "ok": true, "detail": "version=1; 12 rules; threshold=0.7", "error": null},
    {"name": "model_routing",    "ok": true, "detail": "version=1; default_model=llama3.2:1b; tasks=['classification', 'review_reason']", "error": null}
  ],
  "summary": {"total": 4, "passed": 4, "failed": 0, "ok": true},
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": true,
    "command_role": "read_only_dashboard"
  }
}
```

### 5.8 `hb-assistant construction-agent sources validate --json`

```json
{
  "implemented": true,
  "phase": 1,
  "step": "2-source-registry",
  "summary": {
    "project_count": 2,
    "source_count": 3,
    "resolved_count": 0,
    "pending_count": 3,
    "deprecated_count": 0,
    "ok": true,
    "blocking": false
  },
  "warnings": ["3 sources pending live resolution"],
  "guardrails": {
    "all_read_only": true,
    "no_writeback_paths": true,
    "no_live_external_calls": true
  },
  "note": "Read-only validation. No SharePoint/OneDrive/Graph calls were made."
}
```

(Per-project and per-source rows omitted here for brevity — full JSON captured during run; matches the `seed.yaml` registry with `resolution_status: pending` on all three sources.)

### 5.9 `hb-assistant construction-agent index status --json`

```json
{
  "command": "construction-agent index status",
  "schema_version": 4,
  "summary": {"project_count": 2, "source_count": 3, "sources_in_view": 3},
  "review_queue": {"open": 0, "resolved": 0, "deferred": 0},
  "model_decisions": {"accepted": 1, "review": 2},
  "policies": {
    "review_rules":   {"version": 1, "rule_count": 12, "low_confidence_threshold": 0.7},
    "model_routing":  {"version": 1, "default_model": "llama3.2:1b", "low_confidence_threshold": 0.7, "tasks": ["classification", "review_reason"]}
  },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": true,
    "command_role": "read_only_dashboard"
  }
}
```

`model_decisions` shows the residual `{accepted: 1, review: 2}` from the prompt-07 evidence run captured into the real DB — expected and documented in the prior handoff. No fresh decisions written by this prompt.

### 5.10 `hb-assistant procore mapping validate --json` (exit=1 by design)

```json
{
  "command": "hb-assistant procore mapping validate",
  "report": {
    "company_id": "5280",
    "total": 2,
    "by_status": {"pilot": 1, "pending": 1},
    "rows": [
      {"hb_project_key": "tropical", "procore_project_id": "23-435-01", "procore_project_name": "Tropical", "status": "pilot",   "mapped": true},
      {"hb_project_key": "hilltop",  "procore_project_id": "",          "procore_project_name": "",         "status": "pending", "mapped": false}
    ],
    "ok": false
  },
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": true,
    "live_calls_disabled": true,
    "correspondence_excluded": true,
    "schedule_tasks_deferred": true
  }
}
```

Exit code 1 is expected and informational — `hilltop` remains `pending` until the Procore project ID is supplied. The Phase 01 handoff explicitly carries this forward.

### 5.11 `hb-assistant procore tools list --json` (summary)

```json
{
  "command": "hb-assistant procore tools list",
  "company_id": "5280",
  "company_display_name": "HB Construction",
  "version": 1,
  "endpoint_count": 13,
  "by_status": {"validated": 6, "sensitive_validated": 4, "excluded": 1, "deferred": 2}
}
```

Endpoint roster matches the Phase 01 contract: 6 validated (low/medium sensitivity, ready for live audit when OAuth lands), 4 sensitive_validated (high — controller-routed to review), 1 excluded (`list-correspondence`, hard guardrail), 2 deferred (`list-schedule`, `list-tasks`). Per-endpoint JSON omitted here for brevity.

### 5.12 `hb-assistant construction-agent graph auth status --json`

```json
{
  "command": "construction-agent graph auth status",
  "required_scopes": ["Sites.Read.All", "Files.Read.All", "User.Read"],
  "delegated": {
    "token_type": "none",
    "message": "No delegated token. Run login.",
    "cache": {
      "msal-token-cache.bin":      {"exists": false, "perms_ok": false, "path": "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache.bin"},
      "msal-token-cache-app.bin":  {"exists": false, "perms_ok": false, "path": "~/Library/Application Support/HB Personal Assistant/auth/msal-token-cache-app.bin"}
    },
    "configured_scopes":      ["User.Read", "Mail.Read", "Calendars.Read", "Files.Read.All", "offline_access"],
    "effective_msal_scopes":  ["User.Read", "Mail.Read", "Calendars.Read", "Files.Read.All"],
    "removed_reserved_scopes":["offline_access"]
  },
  "note": "No live Graph call is made; report is from local MSAL cache only."
}
```

`ensure_report` (omitted above for brevity) confirms all 11 app-support paths exist and are writable with expected modes (auth_dir = `0o700`).

### 5.13 `hb-assistant construction-agent graph sources resolve --json`

```json
{
  "command": "construction-agent graph sources resolve",
  "mode": "dry_run",
  "targets": ["tropical-sharepoint", "hilltop-sharepoint", "bobby-onedrive"],
  "status": "auth_required",
  "scopes": ["Sites.Read.All", "Files.Read.All", "User.Read"],
  "detail": "No delegated account in cache. Run `hb-assistant auth login` first.",
  "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token."
}
```

Exit code 0 — the command terminates cleanly with a structured `auth_required` payload (no MSAL hang). Live resolution intentionally deferred.

## 6. Phase 01 Acceptance Gaps (Carried Into Phase 02)

Distilled from the prior session-handoff §8 (Unresolved Issues) and §9 (Risks). Each item is a candidate target for later Phase 02 prompts; none are addressed here.

1. **Live MS Graph round-trip never exercised.** MSAL delegated auth hangs in non-interactive sandboxes. Needs an interactive `hb-assistant auth login` followed by re-runs of `graph auth status`, `graph sources resolve --apply`, `graph delta --apply`.
2. **All SharePoint/OneDrive seed sources are `resolution_status: pending`.** `site_url`, `site_id`, `drive_id` remain `null` in `resources/config/sharepoint_onedrive_sources.seed.yaml`. Resolution requires either the SharePoint developer brief or live Graph resolution (see #1).
3. **Live Ollama call CLI-gated.** `OllamaChatClient` is tested with mocked requests, but `cli/construction.py::classify_run` returns `status: "live_call_disabled"`. Removing the guard is a deliberate later step contingent on a local `ollama serve` being available.
4. **Live Procore OAuth not wired.** `procore auth status` is a documented stub; `ready_for_live_calls` stays `false`. No `client.py`, no `procore tools fetch`. Endpoint contract + auditor + (planned) audit table model are forward-compatible.
5. **Procore project mapping incomplete.** Only `tropical → 23-435-01` is pilot; `hilltop` is `pending`. `procore mapping validate` returns exit 1 (informational) until populated.
6. **Construction vault config-field fallback unset.** `paths.construction_vault_root` not present in `config/config.yml`. `HB_CONSTRUCTION_VAULT_ROOT` env var remains the only path; acceptable operationally, but a config fallback would harden persistence.
7. **Pre-existing `test_obsidian_writer.py` failures (4).** `action_item_ids` keyword drift between `MarkerBoundedWriter.write_bounded_section` and the tests. Predates this work and is out of Phase 02 scope unless explicitly authorized.
8. **Hang-prone test files.** `test_cli_canonical.py` (non-help subset), `test_auth.py`, `test_automation.py`, `test_actions_cli.py`, `test_files_cli.py`, `test_graph_*`, `test_mutation_lockout.py`, `test_sensitive_scan_cli.py`, `test_mvp_local_runtime_evidence.py` hang in non-interactive shells (real MSAL / network / subprocess paths). Excluded from regression sweeps by convention; not investigated this prompt.

## 7. Blocked Live / External Validation

- **Graph** — `graph auth status` and `graph sources resolve --json` return structured non-zero/`auth_required` payloads without contacting Microsoft. No interactive shell was provided this turn, so live login was not attempted.
- **Procore** — no HTTP client exists; only audit + mapping commands run. No live Procore call attempted (none possible).
- **Ollama** — `classify run` live path is CLI-gated to `live_call_disabled`; no `ollama serve` was contacted.
- All three deferred surfaces remain consistent with Phase 01 acceptance posture.

## 8. Phase 02 Guardrail Attestation

All Phase 02 non-negotiable guardrails are honored by this prompt (which makes no functional changes) and will be honored by every subsequent Phase 02 prompt:

- External systems (SharePoint, OneDrive, Outlook, Procore) remain **read-only**. No writeback.
- No source-document copies into Obsidian by default.
- No full-document text in vault notes by default.
- No deletion, movement, overwrite, or rename of source files.
- No production webhooks.
- No company-wide rollout.
- Sensitive records always route to manual review.
- Models never execute file operations and never override controller validation.
- `Mail.ReadWrite.All` (where granted) still enforces mailbox **read-only** behavior in Phase 02.
- `docs/evidence/**` stays evidence-only; `docs/plans/**` is not used as a payload mirror.

## 9. Next Prompt Readiness

- Repo HEAD matches the user-reported Phase 01 baseline.
- Working tree is clean (single untracked evidence file pending commit).
- Construction-agent + Procore validation gates all green; ruff clean; 240/240 scoped tests pass.
- Phase 02 evidence root is created.
- Phase 01 acceptance gaps catalogued for future-prompt routing.
- Governance + guardrails attested.

**Status: ready for Phase 02 — Prompt 01.**
