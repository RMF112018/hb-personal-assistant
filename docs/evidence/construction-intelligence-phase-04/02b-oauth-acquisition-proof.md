# Phase 04 Prompt 02 — OAuth Token Acquisition (Remediation)

**Date:** 2026-05-28
**Phase:** HB Construction Intelligence Phase 04 — Procore Core Project Controls
**Prompt:** 02 (remediation) — OAuth Token Acquisition
**Operator:** local code agent (Claude, opus-4-7)

---

## 1. Purpose

Close the gap left when the original Prompt 02 commit (`681d3c9`) shipped only
the consumer **boundary** — protocol, env/keychain reader, read-only cache
shell — and deferred the actual OAuth code-flow exchange and refresh path.
The package's Prompt 02 is titled "Procore OAuth Token Provider **Foundation**";
a foundation needs an acquisition path, not just a consumer interface.

This remediation lands:

1. A real OAuth client (`ProcoreOAuthClient`) implementing Procore's
   **OOB Installed-Apps flow** with both `authorization_code` exchange and
   `refresh_token` rotation.
2. A token-cache writer (`write_token_cache`) and clearer (`clear_token_cache`)
   that satisfy the existing `0o600` / `0o700` permission posture and write
   atomically via `tempfile + os.replace`.
3. A `RefreshingOAuthTokenProvider` that transparently refreshes near-expiry
   tokens via the OAuth client and writes the rotated tokens back to the cache.
4. CLI commands `procore auth login / refresh / logout` plus an extended
   `procore auth status` envelope surfacing cache state + default-chain order.

No Procore writeback. The OAuth `/oauth/token` POST is the only POST permitted
anywhere in the Procore module; the GET-only data plane (`http_client.py`,
`sync.py`, etc.) is unchanged. Unit tests stay offline via an injected mock
transport; live OAuth tests are gated behind `HB_PROCORE_LIVE=1` **and** an
explicit operator-supplied `PROCORE_TEST_REFRESH_TOKEN`.

## 2. HEAD + ancestor

- HEAD before this commit: `b739607` (Phase 04 Prompt 03 — endpoint catalog).
- Phase 03 closeout `19e21db` remains an ancestor.

## 3. Files added / modified

**Created:**
- `src/hb_assistant/procore/oauth.py` — `TokenSet`, `ProcoreOAuthError`,
  `ProcoreOAuthClient`, OOB authorization-URL helper, `requests`-backed
  default transport (lazy import).
- `tests/test_procore_oauth.py` — 11 tests covering the URL builder,
  exchange + refresh request shapes, error normalization, and `TokenSet`
  redaction.
- `tests/test_procore_token_cache_io.py` — 7 tests covering writer perms,
  atomic replace, clear, permission-unsafe read rejection, explicit-path
  override.
- `tests/test_procore_cli_auth.py` — 8 tests covering `login` / `refresh` /
  `logout` / extended `status` envelopes.
- `tests/test_procore_oauth_live.py` — single live refresh test, **skipped
  by default**; runs only when both `HB_PROCORE_LIVE=1` and
  `PROCORE_TEST_REFRESH_TOKEN` are set.

**Modified:**
- `src/hb_assistant/procore/token_provider.py` — `write_token_cache`,
  `clear_token_cache`, `read_token_cache_payload`, and
  `RefreshingOAuthTokenProvider`; default chain reshuffled to
  `env_or_keychain → oauth_refreshing → missing`.
- `src/hb_assistant/procore/__init__.py` — 6 new exports
  (`ProcoreOAuthClient`, `ProcoreOAuthError`, `TokenSet`,
  `RefreshingOAuthTokenProvider`, `write_token_cache`, `clear_token_cache`).
- `src/hb_assistant/procore/validate.py` — added 19th check
  `oauth_acquisition_path_present`; extended
  `procore_init_exports_complete` (6 new required names) and
  `token_provider_default_chain_shape` (new expected order).
- `src/hb_assistant/cli/procore.py` — `auth login`, `auth refresh`,
  `auth logout` commands; extended `auth status` envelope.
- `tests/test_procore_token_provider.py` — chain-order assertion updated
  + 4 new `RefreshingOAuthTokenProvider` tests.
- `tests/test_procore_client_secret_isolation.py` — allowlist += `oauth.py`
  (the single legitimate consumer of `get_procore_client_secret`).
- `tests/test_procore_endpoint_audit.py` — the
  `test_procore_module_imports_no_http_client` invariant now allowlists
  `hb_assistant.procore.oauth` (the GET-only data plane is still verified
  clean).
- `tests/test_procore_cli_validate.py` — envelope check count 18 → 19.

**Not modified:** `http_client.py` (GET-only data plane unchanged);
`auth.py` (env-status surface unchanged; the new cache/refresh state
surfaces via the extended CLI envelope); `errors.py` (`ProcoreOAuthError`
lives in `oauth.py` since that's the only call site); endpoint seed YAMLs;
`pyproject.toml` (`requests>=2.32.0` was already a dependency, used by
existing graph + classification + retrieval modules).

## 4. Boundary carve-out evidence

`grep -rn "get_procore_client_secret" src/hb_assistant/procore/`:

```
src/hb_assistant/procore/config.py:17           # docstring example
src/hb_assistant/procore/config.py:19           # docstring example
src/hb_assistant/procore/config.py:170          # def get_procore_client_secret(...)
src/hb_assistant/procore/config.py:231          # docstring cross-reference
src/hb_assistant/procore/config.py:287          # __all__
src/hb_assistant/procore/oauth.py:4             # module docstring
src/hb_assistant/procore/oauth.py:36            # `from ... import get_procore_client_secret`
src/hb_assistant/procore/oauth.py:205           # call in exchange_authorization_code
src/hb_assistant/procore/oauth.py:218           # call in refresh_access_token
src/hb_assistant/procore/token_provider.py:30   # docstring invariant statement
src/hb_assistant/procore/http_client.py:38      # explanatory comment
```

`oauth.py` is the **sole** non-`config.py` site that imports or calls the
symbol. The AST isolation test `test_procore_client_secret_isolation.py`
enforces this on every run with the allowlist
`{"config.py", "errors.py", "redaction.py", "oauth.py"}`.

## 5. OOB OAuth flow walkthrough

### First-time login (manual one-time)

1. Operator runs `hb-assistant procore auth login`.
2. The CLI prints the authorization URL:
   `https://login-sandbox.procore.com/oauth/authorize?response_type=code&client_id=<id>&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob`
3. Operator opens the URL, signs in, approves the app, and is shown an
   authorization code on-screen.
4. Operator pastes the code into the CLI prompt.
5. The CLI POSTs to `https://login-sandbox.procore.com/oauth/token` with
   form body `grant_type=authorization_code, code, client_id, client_secret,
   redirect_uri`.
6. On success, the CLI writes the resulting `TokenSet` to
   `~/Library/Application Support/HB Personal Assistant/auth/procore_token.json`
   with `0o600` perms and `0o700` on the parent directory.
7. The CLI emits a redacted envelope: `{ok, kind: "oauth_login",
   access_token_cached: true, refresh_token_cached: <bool>,
   expires_in_seconds: <int>}` — no token value ever leaves the process.

### Ongoing refresh (automatic)

- Any caller that resolves an access token via the default provider chain
  hits `RefreshingOAuthTokenProvider` in the middle slot.
- It reads the cache, sees the access token within ~60s of expiry, calls
  `ProcoreOAuthClient.refresh_access_token(<cached refresh>)`, writes the
  new `TokenSet` back to the cache, and returns the fresh access token.
- Any exception during refresh causes a silent `None` (fail-closed). The
  HTTP client owns the explicit `ProcoreAuthRequired` failure.

### Manual refresh / logout

- `hb-assistant procore auth refresh` forces a refresh round-trip even
  when the token is still fresh; useful for manual rotation.
- `hb-assistant procore auth logout` atomically removes the cache file.

## 6. Validation summary

All offline; no live Procore HTTP.

| Command | Result |
|---------|--------|
| `python -m pytest -q --no-header` | **719 passed, 1 skipped** (+29 over Prompt 03; skipped = live OAuth) |
| `python -m pytest tests/test_procore_*.py -q --no-header` | **189 passed, 1 skipped** |
| `ruff check .` | All checks passed |
| `mypy .` | Success: no issues found in 140 source files |
| `python -m compileall src tests` | Clean |
| `hb-assistant procore validate --json` | **19 checks**, 18 pass, 1 informational (`mapping_consistent`) |
| `tests/test_procore_client_secret_isolation.py` | 2/2 pass with the `oauth.py` allowlist entry |
| `tests/test_procore_oauth.py` | 11/11 pass |
| `tests/test_procore_token_cache_io.py` | 7/7 pass |
| `tests/test_procore_cli_auth.py` | 8/8 pass |
| Sensitive-scan + offline-enforcement gates | All green |

## 7. Live-mode gating

The live refresh test is intentionally skipped by default. Operator
invocation:

```bash
export HB_PROCORE_LIVE=1
export PROCORE_TEST_REFRESH_TOKEN='<a valid refresh token from a sandbox app>'
python -m pytest tests/test_procore_oauth_live.py -q
```

This test:

- Calls `ProcoreOAuthClient.refresh_access_token(...)` against real Procore.
- Asserts only that a non-empty access token is returned.
- **Discards the token immediately** — never asserts on the value, never
  prints it, never writes the cache.

This commit landed without running the live test. Confirmation that the
non-live invocation skips the test correctly:

```
$ python -m pytest tests/test_procore_oauth_live.py -q
.s
1 skipped in 0.0Xs
```

## 8. Phase 04 Prompt 04 readiness

- The data-plane HTTP client can now resolve access tokens through the
  default chain without operator intervention beyond the one-time
  `procore auth login`.
- The refresh path is automatic and bounded to a single
  `RefreshingOAuthTokenProvider` instance per request; failures fail closed
  with `ProcoreAuthRequired` at the HTTP boundary.
- The client secret is reachable from exactly two source modules
  (`config.py` definition; `oauth.py` invocation). The AST boundary test
  enforces this on every run.
- 19 validate checks, 719 pytest pass, ruff/mypy/compileall green, live
  test gated.

**Greenlight for Phase 04 Prompt 04** (RFI sync dry-run + normalization).
