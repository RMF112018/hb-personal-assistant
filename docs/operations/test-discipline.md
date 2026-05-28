# Test Discipline

Authoritative operator + contributor surface for how this repo runs tests.
Sibling to `procore-operator-runbook.md` and `construction-agent-operator-runbook.md`.

## Scope

Unit tests in this repo are **fully offline**. They never touch Procore,
SharePoint, OneDrive, Outlook, or any real network endpoint. Live calls are
opt-in, marker-gated, and operator-driven.

This document records the marker taxonomy, the synthetic-fixture rule, the
redaction expectation at error boundaries, and the exact invocations for the
default offline slice vs. the opt-in live slice.

## Marker taxonomy

Registered in `pyproject.toml` under `[tool.pytest.ini_options]`:

| Marker | Purpose | Default behavior |
| --- | --- | --- |
| `integration` | Tests that touch external systems (e.g. real SQLite migrations across versions, real disk I/O at scale). | Opt-in. Use `-m integration`. |
| `manual` | Tests intended to be run by an operator by hand for proof or smoke. | Opt-in. Use `-m manual`. |
| `live` | Tests that perform real Procore HTTP calls. | Skipped unless `HB_PROCORE_LIVE=1` is set. |

The default invocation `python -m pytest -q` runs only unmarked tests — the
offline suite.

## Live-test guard pattern

Any future test that requires a real Procore tenant must carry both the marker
and the env guard:

```python
import os
import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("HB_PROCORE_LIVE"),
        reason="set HB_PROCORE_LIVE=1 to enable live Procore tests",
    ),
]
```

No live tests ship in Prompt 12. The marker + convention are registered now so
future prompts have a documented slot.

## Synthetic-fixture rule

Real Procore (or SharePoint/OneDrive/Outlook) payloads are never copied into
the repo. Every fixture in `src/hb_assistant/procore/fixtures.py` and
`src/hb_assistant/construction/fixtures/` is synthetic:

- Tokens use the well-known `eyJ`-prefixed header followed by deterministic
  garbage with the literal substring `synthetic` in the payload.
- Client secrets and bearer values contain the literal substring `synthetic`
  so the repo sensitive-scan allowlist can identify the file by path.
- IDs, names, and titles are sequential or descriptive placeholders.

The repo sensitive-scan test (`tests/test_repo_sensitive_scan.py`) fails on
any unallowed credential-shaped string anywhere in the tree.

## Redaction expectation at boundaries

Every Procore error boundary returns a redacted envelope:

- HTTP request / response: `redact_request`, `redact_response`, `redact_headers`,
  `redact_body` (see `src/hb_assistant/procore/redaction.py`).
- Exception types: `ProcoreAPIError`, `ProcoreRateLimitError` (see
  `src/hb_assistant/procore/errors.py`) — `str()` and `repr()` are safe.
- CLI validator: `procore validate --json` reduces uncaught exceptions to
  `{"error": "<ClassName>"}` via `redact_body(..., for_error=True)`.

Boundary coverage is enforced by `tests/test_procore_redaction.py` — ten
tests across header/request/response/body/error types.

## Offline enforcement

`tests/test_procore_offline_enforcement.py` AST-walks every
`tests/test_procore_*.py` file and fails on any direct import of `requests`,
`httpx`, `urllib.request`, or `urllib3`. The only allowed Procore transport
in tests is the injectable `FakeResponse` + `make_recording_transport`
pattern defined in `tests/test_procore_http_client.py`.

## Invocations

Default offline suite:

```bash
python -m pytest -q
```

Procore-specific offline slice (recommended for fast pre-commit feedback):

```bash
python -m pytest tests/test_procore_redaction.py \
  tests/test_repo_sensitive_scan.py \
  tests/test_procore_offline_enforcement.py \
  tests/test_procore_cli_validate.py \
  tests/test_procore_http_client.py \
  tests/test_sensitive_scan.py \
  tests/test_sensitive_scan_cli.py -q
```

Opt-in integration tests:

```bash
python -m pytest -m integration -q
```

Opt-in live Procore tests (requires explicit env var; never run in CI):

```bash
HB_PROCORE_LIVE=1 python -m pytest -m live -q
```

## References

- Procore operator runbook: `docs/operations/procore-operator-runbook.md`.
- Sensitive scanner module: `src/hb_assistant/security/sensitive_scan.py`.
- Procore redaction module: `src/hb_assistant/procore/redaction.py`.
- Synthetic fixtures: `src/hb_assistant/procore/fixtures.py`,
  `src/hb_assistant/construction/fixtures/procore.py`.
- Architecture index: `docs/architecture/00-README.md`.
