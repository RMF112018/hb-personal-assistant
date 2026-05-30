# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`hb-personal-assistant` — a Bobby-only, **local-first** MVP that pulls delegated Microsoft 365 (Graph) and Procore data, classifies/enriches it, and writes source-linked notes into an Obsidian vault. Pure Python 3.12+, single package `hb_assistant`, Typer CLI, SQLite for local state. No web service, frontend, or JS workspaces.

Work is organized by **phases** (Construction Intelligence 01/02, Procore 04A live sync / 04B second-brain). The README "Repository Status" block is the authoritative phase ledger; each phase has an evidence bundle under `docs/evidence/`.

## Commands

Run inside the venv (`source .venv/bin/activate`) or prefix with `.venv/bin/`.

```bash
pip install -e ".[dev]"                                    # package + dev tooling
pytest                                                     # full suite
pytest tests/test_procore_cli_validate.py::test_name       # one test (or pass a file)
pytest -m "not integration and not live and not manual"    # default-safe subset
ruff check . && ruff format .                              # lint + format (line-length 100)
mypy src                                                   # type-check
hb-assistant --help                                        # CLI entry point
construction-agent validate --json                         # `construction-agent` is an hb-assistant subgroup
```

- **Lint/type scope is intentionally partial.** `pyproject.toml` (`[tool.ruff] extend-exclude`, `per-file-ignores`, `[[tool.mypy.overrides]]`) lists exactly which modules are held to strict ruff/mypy; new phases opt their modules in. Check whether a module is in-scope before trusting a clean `ruff check .` / `mypy src`.
- **Markers** `integration`/`manual`/`live` are opt-in. `live` hits real Procore HTTP and needs `HB_PROCORE_LIVE=1` — never run without explicit intent.

## Architecture

All source under `src/hb_assistant/`. Layered pipeline: **auth → external read clients → SQLite store + projections → classification/retrieval → Obsidian output**, with `cli/` on top and `automation/` driving scheduled runs.

- **`cli/`** — Typer apps composed in `cli/main.py` (`hb-assistant`). Large nested groups: `construction-agent` (`cli/construction.py`), `procore` (`cli/procore.py`). `vault`/`sync`/`brief` are deliberate "not implemented" stubs. Most commands support `--json` + a dry-run posture.
- **`auth/`** — MSAL delegated (Bobby-user) tokens are the runtime default; cert app-only is proof/admin only. Scopes are minimized in `scope_policy.py` (tenant consented `Mail.ReadWrite.All`, but runtime requests only `Mail.Read`). Token cache lives outside the repo.
- **`graph/`** — read-only Graph clients (mail, calendar, drive) over `http_client.py` + `proof_runner.py`. Delta crawling is folder-scoped, not deep-index.
- **`store/`** — SQLite via `connection.py` + `migrator.py` (**additive, versioned schema V1…V19 — never rewrite existing tables, add migrations**; Procore-specific migrations span V6–V9). `procore_*_projection.py` modules are per-domain read models; `construction/store/repositories.py` is the construction-side schema.
- **`construction/`** — source registry (Pydantic + YAML loaders), Graph resolution/delta, classification, manifests, policy. Config seeds in `resources/config/*.seed.yaml`.
- **`procore/`** — `auth.py` (OAuth), `normalizers/`, `sync.py`, `live_gate.py` (fail-closed live gate), daily-log selection. The Procore HTTP client is intentionally absent for non-live work (a test enforces this).
- **`obsidian/`** — `writer.py` + `brief.py` project store data into vault notes. Hard invariant: every output carries source traceability and never leaks raw delta links, tokens, full bodies, or PEMs (redaction attestations + an output-fence enforce this).
- **`retrieval/` `classification/` `actions/`** — embeddings/context, Ollama-backed classification (`--mock-output` offline mode), action extraction.
- **`automation/`** — `orchestrator.py` (morning "run" pipeline) + `launchd_manager.py` (macOS launchd).
- **`config/`** — `path_policy.py` resolves the macOS Application Support root; **all auth cache, SQLite, and logs live outside the repo** under `~/Library/Application Support/HB Personal Assistant/`.

**Non-negotiable runtime guardrails** (enforced in code/tests): no Microsoft 365 write-back; mailbox read-only at four layers (YAML policy, MSAL scope, Python adapter, SQLite `CHECK`); dry-run before any write; no secrets/tokens/full-bodies/PEMs logged or committed; state stored outside the repo.

`docs/architecture/` holds per-component design records; `docs/evidence/<phase>/` holds authoritative per-phase validation bundles. Repo code/tests/evidence are the source of truth over any planning note.

### Code graph

A pre-built index lives at `.code-graph/graph.bin` (with a daemon), but the wrapper commands (`update-code-graph`, `query-graph`, `graph-blast-radius`) are **not installed on PATH** — they're unfilled placeholders. Use standard Grep/Glob/Read; don't invoke commands that don't resolve. Update this section if a real graph CLI is wired up.

## Working style

- **Think before coding.** State assumptions; if multiple interpretations exist, surface them rather than picking silently. If something is unclear or a simpler approach exists, say so.
- **Simplicity first.** Minimum code that solves the problem — no speculative features, abstractions for single-use code, or error handling for impossible cases.
- **Surgical changes.** Touch only what the request requires; match existing style; don't refactor what isn't broken. Remove orphans *your* change created; flag (don't delete) pre-existing dead code.
- **Goal-driven.** Turn tasks into verifiable goals (e.g. "fix the bug" → "write a failing test, then make it pass") and loop until verified. State a brief step→verify plan for multi-step work.

## Obsidian vault governance

- Vault root: `/Users/bobbyfetting/Documents/Obsidian Vault/Work/HB Personal Assistant/` · Repo root: `/Users/bobbyfetting/hb-personal-assistant`
- **Source of truth:** repo code, tests, runtime behavior, and repo evidence are authoritative over planning notes. If vault instructions conflict with repo truth, stop and report before patching.
- Package lifecycle: `Active`, `Closed`, `Deferred`, `Superseded`. Lifecycle changes must be reflected in `09_Implementation_Packages/Package Registry.md` + related manifests. Any `Closed` package needs `CLOSURE_NOTE.md` (or explicit pending-closeout mark).
- Before modifying/removing package sources, verify migration prerequisites, manifest status, and registry coverage. Migration is valid only when manifest coverage, payload counts, and pre-metadata hash verification pass; declare post-metadata changes.
- `docs/evidence/**` stays in-repo and is referenced — evidence bundles are *not* lifecycle-classified packages. Deferred external blockers may be documented without reclassifying evidence bundles.
- Never copy credentials/tokens/sensitive material into governance notes. Governance must stay usable without Obsidian plugins.
