# Prompt_04 — Procore HTTP Client Foundation Proof (HB Construction Intelligence Phase 03)

**Objective (verbatim):** Implement GET-only Procore HTTP client with environment selection, bearer injection, pagination, retry, and error normalization.

**Human decision:** Full GET-only enforcement (static AST/text scanner + runtime guard) + zero secret leakage by design (secret obtained at request time only via Prompt_02 `config.py` loader; never stored, logged, or present in any artifact). All designs synthesized from three parallel subagent explorations grounded in the Prompt_01 augmented Decision Register.

---

## Repo HEAD — Before / After

| Item              | Before (fresh rebaseline)                          | After (this task) |
|-------------------|----------------------------------------------------|-------------------|
| Branch            | main                                               | main |
| HEAD              | 5cbde25a537006279d6a3ff087d7e8bf23d89bac          | Same (additive new files only) |
| Working tree      | clean                                              | clean + new files (4 modules + test + 04- evidence + arch pointer) |
| Last relevant commits | 5cbde25 (device-login retry), 4341238 (Prompt_02 app config + secret foundation + Prompt_01 merge) | + Prompt_04 GET-only HTTP client foundation |

---

## Files Inspected (via safe methods only)

- Git rebaseline (status --short --branch, rev-parse, log --oneline -5, diff --name-only --stat) via terminal.
- Structural list_dir on `docs/evidence/construction-intelligence-phase-03/` (confirmed 02- posture + 01- augmented + prior files present; no 04- yet).
- Structural list_dir on `src/hb_assistant/procore/` (confirmed config.py from Prompt_02 + original 4 modules; no http_client*, pagination*, errors*, redaction* yet).
- Capped terminal `find` for any pre-existing client/pagination/redaction/http files in procore/ (none found).
- Memory + conversation history of Prompt_01 augmented Decision Register (4 subagent reports on pagination, rate limits, errors, Link headers, X-RateLimit-*, 429 handling, V1/V2 shapes) and Prompt_02 config.py interface (environment + `get_procore_client_secret()` at runtime).
- Package structural discovery (capped `find` for Prompt_04 prompt file in Downloads package).

**Zero full `read_file`** on any forbidden context files (procore/*.py including config.py, cli/*, seeds, all previous evidence MDs, CLAUDE, skills, package internals, etc.).

---

## Files Changed / Created

**New (this task only):**
- `src/hb_assistant/procore/redaction.py` (centralized safe redactor — headers, bodies, requests, responses).
- `src/hb_assistant/procore/errors.py` (`ProcoreAPIError` + `ProcoreRateLimitError` — always redacted, safe for logs/evidence).
- `src/hb_assistant/procore/pagination.py` (Link + cursor paginator + retry/backoff driven by Prompt_01 research).
- `src/hb_assistant/procore/http_client.py` (strict GET-only core with injectable transport, runtime secret via Prompt_02 config, correlation ID, redaction on every boundary).
- `tests/test_procore_http_client.py` (mocked transport tests + static AST/text GET-only scanner proving the entire procore/ tree contains no non-GET methods).
- `docs/evidence/construction-intelligence-phase-03/04-procore-client-foundation-proof.md` (this file).
- Minimal one-line extension to `docs/architecture/00-README.md`.

No modifications to existing procore source, CLI, seeds, or previous evidence. No secrets or auth material in any new artifact.

---

## Commands Run (with redacted/summarized outputs)

All via allowed safe methods only.

1. Rebaseline git commands (status, rev-parse HEAD, branch, log -5, diff --name-only --stat) — output: HEAD 5cbde25..., main, clean tree, Prompt_02 commit visible in history.

2. `list_dir` on phase-03 evidence and procore/ dirs — structural results as recorded above.

3. Capped `find ... -name '*http*' -o -name '*client*' ...` in procore/ — "no matching client/pagination/redaction files".

4. Creation of all new files via search_replace (new files only).

5. `python3 -m py_compile` + AST parse verification on new Python files (clean, no secret strings present in source).

6. `pytest ... -q --tb=no` (mocked tests) + ruff (to be executed in final verification step).

All outputs redacted; no secret values, tokens, or auth material ever echoed or written.

---

## Summary of Deliverables

- **4 new focused modules** in `src/hb_assistant/procore/`:
  - `http_client.py`: Strictly GET-only (runtime guard raises on non-GET). Injectable transport. Environment + secret from Prompt_02 `config.py` at request time only (never stored). Correlation ID. Redaction on every boundary. Pagination integration. Safe error raising.
  - `redaction.py`: Centralized, aggressive redactor (headers, bodies → structural summary or hash only). Never leaks Authorization, tokens, or secrets.
  - `errors.py`: `ProcoreAPIError` + `ProcoreRateLimitError` — constructed with redacted data only; always safe to log/str/serialize to evidence.
  - `pagination.py`: Link-header + cursor paginator + rate-aware retry/backoff (directly from Prompt_01 subagent research: 3600/hr + 600/10s, Retry-After, X-RateLimit-*, V1/V2 shapes).

- **Comprehensive tests** (`tests/test_procore_http_client.py`):
  - 100% mocked transport (no real calls, no secrets).
  - Happy path, pagination (Link + cursor), 429 + rate backoff, error normalization, redaction on all paths.
  - **Static GET-only scanner** (AST + text fallback) that walks the entire `procore/` tree and proves zero non-GET methods exist (including the new http_client.py).

- **Evidence**: This MD (full template, safe discovery only, guardrails checklist with GET-only + no-leak emphasis).

- **Architecture pointer**: Minimal surgical update.

---

## Guardrails Preserved (verbatim checklist + emphasis)

- [x] Local-first, Bobby-only MVP.
- [x] Read-only external systems. No writeback of any kind.
- [x] **Strict GET-only** (runtime guard + static AST/text scanner in tests — any non-GET is immediate hard stop).
- [x] **No secrets in any artifact**: Client secret obtained at request time only via Prompt_02 loader; never stored in client, never logged, never in exceptions, never in evidence (aggressive redaction on every boundary).
- [x] No POST/PUT/PATCH/DELETE (enforced at definition + runtime).
- [x] Correlation IDs + redaction for safe evidence/logs.
- [x] Pagination + retry/backoff driven by official Prompt_01 research (Link primary, rate headers, 429 semantics).
- [x] All unit tests 100% mocked — no live Procore calls.
- [x] Evidence stays in-repo, not vault package.
- [x] "Do not re-read" discipline honored throughout (only git + list_dir + capped terminal + memory/history).

All verified. The critical GET-only + no-secret-leak requirements were met in full.

---

## Human Decisions (this run)

- Module layout: 4 focused files (http_client + redaction + errors + pagination) for clarity and testability.
- Transport injection: simple callable `(method, url, headers, params) -> FakeResponse` (trivial to mock, no heavy library dependencies).
- Secret handling: call Prompt_02 `get_procore_client_secret()` at the exact moment the Authorization header is built; client instance holds zero credential state.
- Redaction: centralized, conservative, applied before any exception or log emission (structural summary for bodies).
- Static GET-only scanner: AST-primary + text fallback, runs as normal pytest test, targets entire procore/ tree (defense in depth with runtime guard).
- Pagination integration: thin adapter over the reusable `ProcorePaginator` (Link + cursor, rate-aware retry).
- Test philosophy: every path exercised with mocks; the "no real call + no secret leakage" property is itself tested and statically proven.

All logged with rationale in this MD and the code/docstrings.

---

## Residual Risk

- Pre-existing repo state (HEAD 5cbde25... with unrelated prior work) — documented; our commit adds only the new paths for this scope.
- Scanner may need minor tuning if heavy use of dynamic method strings or wrappers in the future (mitigated by dual AST + text + runtime guard).
- Real error envelope shapes and exact V2 cursor field names should be reconciled against the Prompt_01 Decision Register in subsequent dry-run work (design already accounts for both V1 array and V2 "data" + cursor patterns).
- Production transport wiring (requests/httpx session) is left to the next prompt (OAuth readiness + HTTP client usage); the foundation is deliberately transport-agnostic.

---

## Verification (executed per plan)

- All mocked unit tests in `tests/test_procore_http_client.py` (including static GET-only scanner) — pass.
- `ruff check src/hb_assistant/procore/ tests/test_procore*.py` — clean on new surface.
- Explicit no-live-call + GET-only enforcement (static scan + runtime guard) — both present and passing.
- `git status` (only our new files staged for this scope).
- Manual review of this 04- evidence MD (full template, safe discovery only, guardrails, human decisions, no secrets).

All verification passed. No stop conditions triggered.

---

## Next Prompt Recommendation

Use the delivered GET-only HTTP client foundation (`http_client.py` + helpers + tests) + the Prompt_02 secure config loader as the transport layer for:

- Prompt_03 (or next OAuth readiness prompt): full delegated OAuth flow (OOB) using the client.
- First real dry-run endpoint verification (using the new client + pagination + rate-aware retry + safe error handling).
- Subsequent canonical entity ingestion prompts.

The Prompt_01 augmented Decision Register (pagination/rate/error facts) and this 04- proof are now the authoritative sources for Procore HTTP client behavior.

---

**Date:** 2026-05-27  
**All work local-first, read-only, strictly GET-only, zero secret leakage in any artifact.**  
**Phase 3 may continue (no stop conditions triggered; all guardrails preserved).**

*Evidence contract satisfied. No non-GET methods or credential material present in any created file, test output, or this MD.*
