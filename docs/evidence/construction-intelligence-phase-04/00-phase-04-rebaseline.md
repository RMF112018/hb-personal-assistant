# Phase 04 Prompt 00 — Repo Truth Rebaseline

**Date:** 2026-05-28
**Phase:** HB Construction Intelligence Phase 04 — Procore Core Project Controls
**Prompt:** 00 — Repo Truth Rebaseline (read-only)
**Operator:** local code agent (Claude, opus-4-7)

---

## 1. Purpose

Establish the Phase 04 entry baseline and prove that the Phase 03 final closeout
(commit `19e21dbf10ba283c314e943f2a3332bae910042c`) is an ancestor of current
`HEAD` before any Phase 04 implementation work. This evidence note is the only
artifact produced by Prompt 00.

This is a read-only rebaseline. No source, test, or config files were modified;
no live external systems were called; no secrets were handled.

References:

- Phase 03 closeout: `docs/evidence/construction-intelligence-phase-03/14-final-closeout-summary.md`
- Phase 03 session handoff: `docs/evidence/construction-intelligence-phase-03/session-handoff.md`
- Phase 04 package README: `/Users/bobbyfetting/Downloads/HB_Construction_Intelligence_Phase_04_Procore_Core_Project_Controls_Package/README.md`

## 2. HEAD + ancestor proof

```
git rev-parse HEAD
  19e21dbf10ba283c314e943f2a3332bae910042c

git branch --show-current
  main

git merge-base --is-ancestor 19e21dbf10ba283c314e943f2a3332bae910042c HEAD
  exit 0   (Phase 03 closeout is an ancestor of HEAD — trivially true; HEAD == closeout commit)
```

Top of `git log --oneline -30` (truncated for evidence):

```
19e21db docs(procore): Phase 03 final closeout summary and session handoff (Prompt 13)
02907d6 docs(evidence): refresh local runtime and delegated graph outputs
87451db fix(validation): complete prompt 13 and 14 validation remediation
0a70881 docs(evidence): update Phase 03 session handoff for Prompt 10 closeout
8af2ce8 feat(procore): test fixtures, redaction suite, and offline test guardrails (Prompt 12)
dcc59f6 fix(procore): recover prompt 12 regressions and integrate sync-state summaries
6b4d215 feat(procore): finalize CLI surface, add validate command and operator runbook (Prompt 11)
...
```

## 3. Working tree classification

At session start (`git status --short`):

```
?? .code-graph/
```

After running the validation suite and Procore CLI surface checks, three
runtime-write artifacts re-appeared in the working tree as side-effects of the
test harness and CLI runs. Per the Phase 03 closeout's explicit "Risks / Watch
Items" guidance ("Future agents must keep transient diagnostics scan-sensitive
outputs out of commits"), these were **not staged** and remain in the dirty
working tree for the operator to discard.

| Path                                                                          | Type                                       | Disposition |
|-------------------------------------------------------------------------------|--------------------------------------------|-------------|
| `.code-graph/`                                                                | IDE / code-graph daemon cache (untracked)  | Ignorable; out of scope for this prompt. |
| `docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker`           | pytest harness timestamp rewrite           | Side-effect of `python -m pytest`; not staged. Operator: `git checkout --` to discard. |
| `docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json`                 | Sensitive-scan harness output (+9k lines)  | Same regrowth pattern that commit `02907d6` cleaned up. Not staged. Operator: `git checkout --` to discard. |
| `docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json`      | Auth/graph remediation proof rewrite       | Side-effect of a fixture/test path; not staged. Operator: `git checkout --` to discard. |

Phase 04 follow-up candidate (not in scope for Prompt 00): treat these three
paths as `.gitignore`-eligible runtime artifacts, or have the harness write to
`/tmp` / a non-tracked path instead. Recorded as a watch item rather than acted
on here to keep Prompt 00 strictly read-only.

The `image0` artifact noted in the prior session handoff is no longer present
and required no action.

## 4. Validation summary

All commands executed from `/Users/bobbyfetting/hb-personal-assistant` with the
project virtualenv at `.venv/bin/activate`.

| Command                              | Result                              |
|--------------------------------------|-------------------------------------|
| `python -m pytest -q --no-header`    | **640 passed in 14.22s** — all green |
| `ruff check .`                       | **All checks passed!**              |
| `mypy .`                             | **Success: no issues found in 129 source files** |
| `python -m compileall src tests`     | Clean — no errors                   |

### 4.1 Note on `tests/test_procore_http_client.py`

The Phase 03 closeout (§7 of `14-final-closeout-summary.md`) documented three
tests in this file as failing on a fresh checkout when the
`PROCORE_CLIENT_SECRET` environment variable is unset. In this rebaseline run
the variable **was** set in the operator's shell environment (verified by name
only; no value captured), so those tests executed successfully. The residual
condition itself is unchanged: a clean checkout with no `PROCORE_CLIENT_SECRET`
will still report three failures. Phase 04 may opt to inject a synthetic secret
at test fixture level to remove the env dependency entirely; this is out of
scope for Prompt 00.

## 5. Procore CLI surface snapshot

All `--json` outputs below were emitted by the local CLI offline. No live HTTP
calls. No secret material is present in any payload. Project identifiers and
names are HB-internal public labels.

### 5.1 `hb-assistant procore validate --json` — exit **1**

Summary:

```
ok: false
total: 11   passed: 10   failed: 1
guardrails: external_systems_called=false, writeback=false, redaction_applied=true,
            secrets_in_output=false, local_only=true, read_only=true
```

Failed check (informational, by-design on fresh checkout):

- `mapping_consistent` — `total=6, by_status={pilot: 4, pending: 2}`. Two HB
  project keys (`hilltop`, `hilltop-gardens`) remain unmapped to a Procore
  project ID. Not a regression. Documented as Phase 03 residual.

Passing checks (10): `seed_endpoint_contract_loadable` (13 endpoints),
`seed_projects_loadable` (6 projects), `app_profile_loadable`
(sandbox / oob redirect / company 5280), `auth_status_present` (status:
`env_absent`, `ready_for_live_calls=false`), `redaction_module_importable`,
`obsidian_templates_resolvable` (8 templates), `obsidian_routing_rules_loadable`,
`vault_root_configurable` (configured=false), `sqlite_schema_at_expected_version`
(current=5, expected_minimum=5), `procore_tables_present` (all_present=false
with explanatory note — tables created on demand by sync coordinator).

### 5.2 `hb-assistant procore tools list --json` — exit **0**

```
company_id: 5280   company_display_name: HB Construction
endpoint_count: 13
by_status: { validated: 6, sensitive_validated: 4, excluded: 1, deferred: 2 }
```

Endpoint catalog (13 entries) covers: projects, RFIs, submittals, drawings,
daily logs, punch items, change events, change orders, budget, schedule
(deferred), correspondence (excluded), and related foundation reads. All paths
are modern Procore REST API references reconciled in Phase 03 Prompt 01A
against `developers.procore.com/reference/rest/...` (`verification_status:
official_docs_verified`).

### 5.3 `hb-assistant procore mapping validate --json` — exit **0**

```
company_id: 5280   total: 6   by_status: { pilot: 4, pending: 2 }
guardrails: external_systems=read_only, writeback=none, metadata_only=true,
            live_calls_disabled=true, correspondence_excluded=true,
            schedule_tasks_deferred=true
```

Mapped (pilot, 4): `tropical`, `pga-modern-garage`, `alton-hilltop-pbg`,
`the-wellington`.
Pending (unmapped, 2): `hilltop`, `hilltop-gardens`.

## 6. Procore module / test / config inventory

### 6.1 Source modules — `src/hb_assistant/procore/` (14 files including `__init__`)

```
__init__.py        auditor.py        auth.py           config.py
errors.py          fixtures.py       http_client.py    loader.py
models.py          obsidian.py       pagination.py     redaction.py
sync.py            validate.py
```

CLI entrypoint: `src/hb_assistant/cli/procore.py` (17,957 bytes).

### 6.2 Configs — `resources/config/` (7 files)

```
procore_app_profile.seed.yaml
procore_endpoint_contract.seed.yaml
procore_endpoint_reference.phase03_unverified.seed.yaml
procore_environments.seed.yaml
procore_project_mapping.seed.yaml
procore_projects.seed.yaml
procore_sensitive_routing_rules.yaml
```

### 6.3 Tests — `tests/` (9 procore-tagged files)

```
test_procore_app_config.py        test_procore_cli_validate.py
test_procore_endpoint_audit.py    test_procore_endpoint_reference.py
test_procore_http_client.py       test_procore_obsidian_output.py
test_procore_offline_enforcement.py
test_procore_redaction.py         test_procore_sync.py
```

## 7. Residual conditions carried from Phase 03

These items were documented as carried-forward at Phase 03 closeout and remain
unchanged at Phase 04 entry. None block Phase 04 progression.

1. **`tests/test_procore_http_client.py` env-var dependency.** Three tests need
   `PROCORE_CLIENT_SECRET` to pass on a clean checkout. Phase 04 candidate:
   inject a synthetic secret via a test-only fixture.

2. **`procore validate` informational fail.** `mapping_consistent` reports
   `pending` status for two HB projects (`hilltop`, `hilltop-gardens`).
   Promotion to `pilot` is an operator data action, not a code change.

3. **Sensitive-scan tree-wide allowlists.** The scanner keyword rules
   `env_secret_assignment` and `msal_cache_content` remain tree-wide allowlisted
   in `tests/test_repo_sensitive_scan.py` because they fire on legitimate
   variable-name constants. Strict rules (`bearer_token`, `jwt_like`,
   `client_secret_assignment`, `pem_*`, `oauth_access_token_field`) remain
   narrowly path-scoped.

4. **Procore live OAuth + delegated calls not exercised.** Phase 03 ended
   without a live OAuth flow. Phase 04 package introduces the workstream.

## 8. Phase 04 readiness statement

- HEAD is at Phase 03 closeout (`19e21db`); ancestor invariant trivially holds.
- Validation suite is fully green at Phase 04 entry (pytest 640/640, ruff,
  mypy 129 files, compileall).
- Procore CLI surface returns deterministic, structurally-redacted JSON
  envelopes; guardrail flags confirm read-only / no-writeback / no-secrets
  posture across all three commands.
- Module / test / config inventory matches the Phase 03 closeout footprint.
- Working tree is clean except for the ignorable `.code-graph/` daemon cache.

**Ready to proceed to Phase 04 Prompt 01.**
