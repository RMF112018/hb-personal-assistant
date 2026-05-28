# Phase 04 Prompt 02 — Procore OAuth Token Provider Foundation

**Date:** 2026-05-28
**Phase:** HB Construction Intelligence Phase 04 — Procore Core Project Controls
**Prompt:** 02 — OAuth Token Provider Foundation (read-only; no OAuth exchange)
**Operator:** local code agent (Claude, opus-4-7)

---

## 1. Purpose

Formalize the bearer / OAuth-secret boundary opened in Prompt 01. Replace the
callable `AccessTokenProvider = Callable[[], Optional[str]]` shim with a real
`ProcoreTokenProvider` `Protocol`, ship a small family of concrete providers
(missing-token, env/keychain, local OAuth cache shell, composed default), and
attest via tests that the OAuth client secret cannot reach the bearer path.

**Out of scope:** OAuth exchange/refresh implementation (deferred); live HTTP
of any kind; writeback; any cache mutation (the cache provider is strictly
read-only).

## 2. HEAD + ancestor

- HEAD before this commit: `fc3343c` (Phase 04 Prompt 01 — entry hardening).
- `git merge-base --is-ancestor 19e21db HEAD` → exit 0 (Phase 03 closeout still ancestor).

## 3. Files added / modified

**Created:**

- `src/hb_assistant/procore/token_provider.py` — Protocol + 5 concrete provider
  classes (`MissingTokenProvider`, `StaticTokenProvider`,
  `EnvOrKeychainTokenProvider`, `LocalOAuthCacheTokenProvider`,
  `_ChainedTokenProvider`) + `default_procore_token_provider()` factory +
  `_CallableTokenProvider` adapter + `adapt_token_source()`.
- `tests/test_procore_token_provider.py` — 20 tests covering each provider,
  the chain, the adapter, and the no-token-in-repr invariant.
- `tests/test_procore_client_secret_isolation.py` — 2 AST-level tests proving
  no Procore source module outside `{config, errors, redaction}.py`
  imports / attributes / calls `get_procore_client_secret`.

**Modified:**

- `src/hb_assistant/procore/http_client.py` — swap callable alias for
  Protocol-typed provider, default lazily via `adapt_token_source(None)` →
  `default_procore_token_provider()`, call `.get_access_token()`.
- `src/hb_assistant/procore/__init__.py` — 5 new exports.
- `src/hb_assistant/procore/validate.py` — added 16th check
  (`token_provider_default_chain_shape`); extended
  `procore_init_exports_complete` to require the 5 new exports.
- `tests/test_procore_http_client.py` — adopt `StaticTokenProvider` and
  `MissingTokenProvider` instead of inline callables.
- `tests/test_procore_cli_validate.py` — envelope check count 15 → 16.

**Not modified:** `config.py` (already had `get_procore_access_token`);
`errors.py` (already had `ProcoreAuthRequired`); `auth.py` (already had
`AUTH_TOKEN_FILE_NAME` + `PathPolicy().get_auth_dir()`); seed YAMLs;
`pyproject.toml`; CLI.

## 4. Boundary proof — `get_procore_client_secret` references

```
$ grep -rn "get_procore_client_secret" src/hb_assistant/procore/
src/hb_assistant/procore/config.py:17           # docstring example
src/hb_assistant/procore/config.py:19           # docstring example
src/hb_assistant/procore/config.py:170          # def get_procore_client_secret(...)
src/hb_assistant/procore/config.py:231          # docstring (cross-reference)
src/hb_assistant/procore/config.py:287          # __all__
src/hb_assistant/procore/http_client.py:38      # explanatory comment ("deliberately does not import")
src/hb_assistant/procore/token_provider.py:30   # docstring invariant statement
```

Every site outside `config.py` is a comment or docstring — no import
statement, attribute access, or call. The AST test
`tests/test_procore_client_secret_isolation.py` enforces this on every run.

## 5. Provider matrix

| Class | Kind | Source | Returns | Failure mode |
|-------|------|--------|---------|--------------|
| `MissingTokenProvider` | `missing` | (none) | `None` | n/a — always None |
| `StaticTokenProvider` (test-only) | `static` | constructor arg | the supplied value | n/a |
| `EnvOrKeychainTokenProvider` | `env_or_keychain` | macOS Keychain account `access-token` under service `hb-assistant-procore` → env `PROCORE_ACCESS_TOKEN` | str token or `None` | both missing → `None` |
| `LocalOAuthCacheTokenProvider` | `oauth_cache` | `~/Library/Application Support/HB Personal Assistant/auth/procore_token.json` | str token or `None` | missing file / unsafe perms (group/other read) / malformed JSON / missing `access_token` field / `expires_at` parseable and ≤ now → `None`. **Never** writes / refreshes / acquires. |
| `_ChainedTokenProvider` | `chained` | ordered providers | first non-`None`, else `None` | all None → `None` |
| `_CallableTokenProvider` | `callable` | wrapped `Callable[[], Optional[str]]` | whatever the callable returns | n/a |

`default_procore_token_provider()` returns a `_ChainedTokenProvider` whose
order is **strictly**: `env_or_keychain → oauth_cache → missing`. Verified at
runtime by the new `token_provider_default_chain_shape` validate check.

## 6. Validation summary

All offline; no live Procore HTTP.

| Command | Result |
|---------|--------|
| `python -m pytest -q --no-header` (full suite) | **671 passed** (+22 over Prompt 01 baseline of 649) |
| `python -m pytest tests/test_procore_*.py -q --no-header` | **141 passed** (+22 over Prompt 01 procore-scope of 119) |
| `ruff check .` | All checks passed |
| `mypy .` | Success: no issues found in 133 source files |
| `python -m compileall src tests` | Clean |
| `hb-assistant procore validate --json` | **16 checks**, 15 pass, 1 informational (`mapping_consistent` — by design) |
| `tests/test_procore_client_secret_isolation.py` | **2 passed** (AST boundary proof) |
| `tests/test_procore_token_provider.py` | **20 passed** |
| `tests/test_repo_sensitive_scan.py` | 2/2 pass (new files contain no credential-shaped strings outside allowlists) |
| `tests/test_procore_offline_enforcement.py` | 2/2 pass (new test modules import only injected-transport / mocking patterns; no real HTTP imports) |

Existing redaction coverage (`tests/test_procore_redaction.py`,
`tests/test_repo_sensitive_scan.py`) continues to attest that no token-shaped
content reaches logs, exceptions, or evidence.

## 7. Residual conditions

1. **OAuth token-acquisition still deferred.** The cache provider is a
   read-only shell. Until a later prompt wires real OAuth exchange, the
   operator must either:
   - export `PROCORE_ACCESS_TOKEN` in the shell, or
   - place a valid token JSON at the canonical cache path (0600 perms,
     `{"access_token": "...", "expires_at": "<ISO 8601>"}`).
2. **`procore validate` `mapping_consistent`** remains informational for the
   2 pending mappings (`hilltop`, `hilltop-gardens`).
3. **`runtime_checkable` Protocol caveat.** `isinstance(x, ProcoreTokenProvider)`
   is method-name-based (Python protocol semantics), so any object with a
   `get_access_token` method satisfies it. This is acceptable for the internal
   `adapt_token_source` shim; production callers always pass concrete
   provider instances or callables.
4. **Pre-existing runtime side-effect rewrites** under
   `docs/evidence/mvp-local-runtime/` and `docs/evidence/remediation/`
   continue to be unstaged per Prompt 00 / Prompt 01 guidance.

## 8. Phase 04 Prompt 03 readiness

- The HTTP client now consumes a typed provider and fails closed
  (`ProcoreAuthRequired`) when none yields a token.
- `default_procore_token_provider()` gives operators a working entry point
  the moment a token is supplied via env, Keychain, or the cache file.
- The OAuth exchange/refresh path can now be added in a single dedicated
  module that writes the cache JSON; no other module needs to change.
- 16 validate checks, ruff/mypy/compileall green, full pytest green.

**Greenlight for Phase 04 Prompt 03** (OAuth code-flow exchange + cache writer).
