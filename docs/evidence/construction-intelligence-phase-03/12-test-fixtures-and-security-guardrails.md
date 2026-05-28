# Phase 03 — Prompt 12: Test Fixtures and Security Guardrails

## 1. HEAD before / after

- HEAD before changes: `dcc59f6` (`fix(procore): recover prompt 12 regressions and integrate sync-state summaries`)
- HEAD after changes: pending commit on `main`; this evidence file is part of the same commit.
- Untracked-before set: `docs/evidence/construction-intelligence-phase-03/session-handoff.md` (untouched, carried from Prompt 11 arc).

The previous "recovery" commit (`dcc59f6`) repaired Prompt-11 deferrals
(EndpointAuditor redeclaration, sync default-construction, obsidian fixture
mismatch, stale `procore_app` import) and added
`13-test-fixture-validation-output.txt` documenting that recovery scope. This
commit lands the actual Prompt 12 deliverables on top of that baseline:
synthetic transport fixtures, redaction-boundary tests, repo-wide sensitive
scan with allowlist, AST-level offline-only enforcement, pytest marker
taxonomy, and the test-discipline runbook.

## 2. Files inspected

Read-only:
- `src/hb_assistant/procore/redaction.py`
- `src/hb_assistant/procore/errors.py`
- `src/hb_assistant/procore/pagination.py`
- `src/hb_assistant/procore/http_client.py` (via `test_procore_http_client.py`)
- `src/hb_assistant/procore/__init__.py`, `procore/auth.py`, `procore/loader.py`,
  `procore/config.py`, `procore/obsidian.py`, `procore/validate.py`
- `src/hb_assistant/security/sensitive_scan.py`
- `src/hb_assistant/cli/sensitive_scan.py`, `cli/procore.py`, `cli/main.py`
- `tests/test_procore_http_client.py`, `tests/test_sensitive_scan.py`,
  `tests/test_sensitive_scan_cli.py`, `tests/test_construction_manifests.py:894`
- `tests/conftest.py`
- `pyproject.toml`, `CLAUDE.md`
- `docs/architecture/00-README.md`
- `docs/operations/procore-operator-runbook.md`
- `docs/evidence/construction-intelligence-phase-03/13-test-fixture-validation-output.txt`
- `resources/config/procore_*.yaml` (top-of-file only)

## 3. Files changed

Created:
- `src/hb_assistant/procore/fixtures.py` — five fixture dicts:
  `PROCORE_PAGE_FIXTURES`, `PROCORE_ERROR_FIXTURES`,
  `PROCORE_RATE_LIMIT_HEADERS`, `PROCORE_SENSITIVE_ROUTING_FIXTURES`,
  `PROCORE_MALFORMED_BODY_FIXTURES`; plus `SYNTHETIC_TOKEN_LITERALS` tuple
  used by the redaction tests.
- `tests/test_procore_redaction.py` — 14 boundary tests (5 parametrized over
  the malformed-body fixtures + 9 direct).
- `tests/test_repo_sensitive_scan.py` — runs `SensitiveScanner` over the repo
  with explicit per-rule path allowlist + broad allowlist for keyword-style
  rules (`env_secret_assignment`, `msal_cache_content`).
- `tests/test_procore_offline_enforcement.py` — AST scan asserting no
  `requests` / `httpx` / `urllib.request` / `urllib3` import in any
  `tests/test_procore_*.py` file.
- `docs/operations/test-discipline.md` — marker taxonomy, live-test guard
  pattern, synthetic-fixture rule, offline-enforcement rationale,
  invocations, references.

Modified:
- `pyproject.toml` — added `markers = [...]` under
  `[tool.pytest.ini_options]`: `integration`, `manual`, `live`. No other
  pyproject changes.
- `docs/architecture/00-README.md` — appended one Prompt-12 pointer line
  after the existing Prompt-11 pointer (surgical, matches convention).
- `docs/operations/procore-operator-runbook.md` — appended a "Live-test mode"
  subsection (`HB_PROCORE_LIVE=1`-gated invocation); updated References to
  cite prompts 00–12.

Explicitly not touched:
- `src/hb_assistant/procore/auditor.py`, `procore/sync.py`, `procore/obsidian.py`
  (already repaired in `dcc59f6`).
- `tests/test_procore_obsidian_output.py`, `tests/test_procore_sync.py`
  (already repaired in `dcc59f6`).
- `CLAUDE.md` (test discipline belongs in `docs/operations/`).
- `resources/config/*.yaml` (no seed mutations).
- Existing fixture infrastructure at
  `src/hb_assistant/construction/fixtures/procore.py` (Pydantic-validated
  contract/projects fixtures — orthogonal to transport-shape fixtures added
  in this prompt).

## 4. Commands run

All commands are local, read-only against external systems, and produced no
network traffic. Outputs below are summarised; redacted envelopes never
contained credential values.

```text
$ git rev-parse HEAD
dcc59f6060cae6c59b99bfa42e9b53baf100e899

$ git status --short
 M docs/architecture/00-README.md
 M docs/operations/procore-operator-runbook.md
 M pyproject.toml
?? docs/operations/test-discipline.md
?? src/hb_assistant/procore/fixtures.py
?? tests/test_procore_offline_enforcement.py
?? tests/test_procore_redaction.py
?? tests/test_repo_sensitive_scan.py

$ ruff check src/hb_assistant/procore/fixtures.py \
    tests/test_procore_redaction.py \
    tests/test_repo_sensitive_scan.py \
    tests/test_procore_offline_enforcement.py
All checks passed!

$ python -m pytest tests/test_procore_redaction.py \
    tests/test_repo_sensitive_scan.py \
    tests/test_procore_offline_enforcement.py \
    tests/test_procore_cli_validate.py \
    tests/test_sensitive_scan.py \
    tests/test_sensitive_scan_cli.py -q
30 passed in ~1.5s

$ hb-assistant procore validate --json | head
{
  "command": "hb-assistant procore validate",
  ...
  "ok": false,
  "summary": {"total": 11, "passed": 10, "failed": 1},
  ...
}
(exit 0 from `head`; underlying exit code 1 because of expected
informational mapping_consistent semantics for pending pilots —
unchanged from `dcc59f6`.)

$ hb-assistant diagnostics scan-sensitive --repo src --json | tail
Scanner reports rule-name pattern hits in src/ scope (oauth_access_token_field
in procore/cli surfaces; msal_cache_content / jwt_like in local app-support
cache references). All output redacted to {category, path, line, severity,
rule_id}; no matched secret values emitted.
```

Verified that the pre-existing `tests/test_procore_http_client.py` failures
require `PROCORE_CLIENT_SECRET` to be set in the local environment — not a
Prompt 12 regression. Confirmed by stashing the working tree and re-running
the test on clean `dcc59f6`: same 3 failures, same root cause.

## 5. Outputs summarised

- 30 tests pass across the Prompt-12 slice; zero new failures.
- Lint clean on all four new modules (`ruff check` exit 0).
- `procore validate --json`: 11 checks, 10 pass, 1 informational fail
  (`mapping_consistent` flags pending pilots — same envelope shape as
  Prompt 11; the `dcc59f6` auditor fix prevents the `TypeError` envelope
  that Prompt 11's evidence flagged as a residual risk).
- `diagnostics scan-sensitive --repo src --json`: returns redacted finding
  envelope; no matched secret values present in payload.
- Repo-wide `SensitiveScanner.scan(repo=<root>)` returns
  `findings_by_category` with `bearer_token`, `jwt_like`,
  `client_secret_assignment`, `oauth_access_token_field`,
  `env_secret_assignment`, `msal_cache_content` matches, all in
  allowlisted paths (fixtures, regex source, docs, test files); the test
  asserts no _unallowed_ findings.

## 6. Guardrails preserved

| Guardrail | Coverage |
| --- | --- |
| Local-first only | Every command above ran offline; no Procore/SharePoint/OneDrive/Outlook traffic. |
| Read-only external systems | No live calls; CLI invocations are all `--dry-run` / read-only. |
| No Procore writeback | GET-only contract unchanged; no POST/PUT/PATCH/DELETE introduced. |
| No SharePoint/OneDrive/Outlook writeback | Surfaces untouched. |
| No credential material in repo | Repo-wide `SensitiveScanner` test gates the commit; only synthetic literals (prefixed `synthetic-` / containing `eyJ` garbage payload) appear, all in allowlisted files. |
| Redaction at boundaries | Ten boundary tests in `test_procore_redaction.py` cover `redact_headers`, `redact_request`, `redact_response`, `redact_body`, and `ProcoreAPIError` / `ProcoreRateLimitError` round-trips. |
| Sensitive material routes to review | Routing-rule shape preserved in `PROCORE_SENSITIVE_ROUTING_FIXTURES`; no rule changes. |
| Controller policy validates model recommendations | Untouched. |
| Models never execute file ops | No model integration changed. |
| All live calls have explicit dry-run/apply | Untouched (operator runbook augmented with live-test mode subsection, gated by `HB_PROCORE_LIVE=1`). |
| Unit tests offline unless marked integration/manual/live | AST scan in `test_procore_offline_enforcement.py` codifies this; pytest marker taxonomy registered. |

### 6.1 Amendments

- **Evidence filename deviation.** The Phase 03 package's evidence spec for
  this prompt names the file `13-test-fixture-validation-output.txt`. A file
  by that exact name already exists in `docs/evidence/construction-
  intelligence-phase-03/` — it was created by the recovery commit `dcc59f6`
  to document the Prompt-11 deferral fixes. To avoid overwriting that
  artifact and to match the repo convention (`.md`, prompt-number prefix),
  the actual Prompt 12 deliverable evidence is filed here as
  `12-test-fixtures-and-security-guardrails.md`. The two files are
  complementary: `13-*.txt` is the recovery record; `12-*.md` (this file)
  is the deliverables record.
- **HEAD-before mismatch with prior session handoff.** The session handoff
  prompt that initiated this work referenced HEAD `6b4d215`. The actual
  current HEAD at session start is `dcc59f6`, one commit ahead. All
  Prompt-11 deferrals listed in the handoff (auditor, sync, obsidian
  fixture, stale import) were repaired in `dcc59f6` and are therefore not
  in scope for this prompt.

## 7. Residual risk

- `tests/test_procore_http_client.py` still requires `PROCORE_CLIENT_SECRET`
  to pass (3 failures on a clean checkout without the env var or
  Keychain entry). Pre-existing across the Prompt-11 / `dcc59f6` arc; not
  addressed here.
- `SensitiveScanner` rule `env_secret_assignment` is keyword-based and
  triggers on legitimate variable-name constants (`_CLIENT_SECRET_ENV =
  "..."`). The repo test allowlists this rule tree-wide; its real value is
  for scanning `.env`-style files, which the existing
  `tests/test_sensitive_scan.py` probes directly. If the scanner is later
  hardened (e.g., file-extension-aware matching), the test's broad allowlist
  should narrow accordingly.
- No live Procore tests exist yet. The `live` marker is registered but
  unused. Future prompts that add live tests must apply both the marker and
  the `HB_PROCORE_LIVE` skip guard per `docs/operations/test-discipline.md`.
- `tests/test_repo_sensitive_scan.py` adds ~1s to the offline pytest run
  because it walks the repo tree. Acceptable; the slice still finishes in
  under 2 s.

## 8. Next prompt recommendation

Prompt 13 (or successor): wire `PROCORE_CLIENT_SECRET` test injection into
the `ProcoreHTTPClient` test harness so `tests/test_procore_http_client.py`
becomes self-contained (no env-var dependency) — that closes the 3
pre-existing failures and lets the broad pytest matrix go fully green.

Optional follow-up: add a single `@pytest.mark.live` skipped placeholder test
that calls `procore validate --strict` end-to-end against a real tenant when
`HB_PROCORE_LIVE=1` is set, to exercise the marker plumbing end-to-end.
