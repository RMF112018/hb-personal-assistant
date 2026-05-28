# Prompt 14 — Mypy Remediation and Strict Green

## 1. HEAD before / after
- HEAD before: `0a70881acb126ca7b8c3c57cbea89ee45b9695ba`
- HEAD after: `0a70881acb126ca7b8c3c57cbea89ee45b9695ba` (no commit in this run)

## 2. Working tree before fixes
- git status: dirty at start.
- notes (classification before Prompt 14 edits):
  - Prompt 12/13 active work: existing modified source/tests under `src/hb_assistant/*` and `tests/*`.
  - generated artifacts/local-only noise: `docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker`, `docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json`, untracked `image0`.
  - prior evidence work: `docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json`, untracked `docs/evidence/construction-intelligence-phase-03/13-complete-validation-and-green-suite.md`.
- preservation: no cleanup/reset of unrelated/generated files performed.

## 3. Mypy inventory before fixes
- command: `./.venv/bin/mypy . --show-error-codes --pretty`
- exit code: `1`
- total errors: `42`
- files with errors: `9`
- file-by-file error inventory: `/tmp/hbpa-mypy-error-inventory.md`

Bucketed error groups used for remediation:
- bad Optional narrowing.
- untyped mocks/fakes in tests.
- JSON payload shape typing.
- CLI/Typer callback typing.
- Path/string mismatch.
- repository/store return typing.
- `dict[str, object]` vs `dict[str, Any]`.
- stale imports/name collisions.

Observed dominant buckets in this run:
- repository/store return typing + Optional narrowing: `tests/test_construction_store_repositories.py`, `tests/test_store.py`, `tests/test_construction_graph_delta.py`, `tests/test_construction_manifests.py`.
- untyped fixtures (generator return type): `tests/test_store_links.py`, `tests/test_classification.py`, `tests/test_body_mentions.py`.
- script typing/name collisions: `scripts/proofs/delegated_graph_capability_proof.py`.
- mock/callback typing + module attribute typing in tests: `tests/test_construction_ollama_classification.py`.

## 4. Root causes confirmed
### Group 1 — repository/store Optional return values (tests)
- errors: many `[index]` failures indexing `dict | None`.
- classification: test typing defect.
- root cause: tests indexed optional repository lookups without narrowing.
- fix: add explicit `assert <row> is not None` before indexing.

### Group 2 — generator fixture annotations
- errors: `[misc]` generator fixture return types.
- classification: test typing defect.
- root cause: fixtures using `yield` annotated as `Path` instead of `Iterator[Path]`.
- fix: annotate fixtures as `Iterator[Path]` and import `Iterator`.

### Group 3 — proof script typed-object conflicts
- errors: `[no-redef]`, `[attr-defined]`, `[arg-type]`, `[assignment]` in delegated proof script.
- classification: script typing defect.
- root cause: local variable name collision (`summary`), optional endpoint constants passed where `str` required.
- fix: rename early summary to `early_summary`; define non-optional endpoint constants (`STEP_1_ENDPOINT`, `STEP_2_ENDPOINT`); route all `_record` calls through definite `str` endpoints.

### Group 4 — ollama readiness test typing
- errors: `[arg-type]` callback return type mismatch; `[attr-defined]` on `readiness_mod.requests`.
- classification: test typing defect.
- root cause: mock callback annotated with `None` return; patching module attribute path through imported module object caused mypy export check noise.
- fix: annotate callback as returning `requests.Response` (raises at runtime); patch with explicit string path `hb_assistant.construction.classification.readiness.requests.get`.

### Group 5 — optional drift value in baseline comparison test
- errors: `[arg-type]` passing `float | None` to `abs`.
- classification: test typing defect.
- root cause: optional metric field not narrowed.
- fix: assign to local, assert non-None, then call `abs`.

## 5. Files changed
- `tests/test_construction_store_repositories.py`: added non-None narrowing assertions before optional dict indexing.
- `tests/test_store.py`: added non-None narrowing for readiness report.
- `tests/test_construction_graph_delta.py`: added non-None narrowing for delta token lookups.
- `tests/test_store_links.py`: fixture yield return type fixed to `Iterator[Path]`.
- `tests/test_classification.py`: fixture yield return type fixed to `Iterator[Path]`.
- `tests/test_body_mentions.py`: fixture yield return type fixed to `Iterator[Path]`.
- `scripts/proofs/delegated_graph_capability_proof.py`: resolved mypy name collision and optional endpoint arg typing.
- `tests/test_construction_ollama_classification.py`: callback annotation corrected; patch target changed to explicit module path.
- `tests/test_construction_manifests.py`: optional drift value narrowed before `abs`.

## 6. Type-safety approach
- TypedDicts / Protocols / casts added:
  - none.
- Any type ignores added:
  - none.
- Why each ignore is safe and narrow:
  - not applicable.
- Newly introduced/changed `Any` usage:
  - none introduced for remediation (existing file-level `Any` uses retained where pre-existing).
- Any `cast(...)` introduced:
  - none.
- Any mypy config/override changes:
  - none.
- Config justification:
  - not applicable; no exclusion/override broadening performed.

## 7. Validation after fixes
- mypy:
  - `./.venv/bin/mypy . --show-error-codes --pretty`
  - result: `Success: no issues found in 129 source files` (exit `0`).
- pytest concise:
  - `./.venv/bin/python -m pytest -q --no-header`
  - result: pass (exit `0`).
- ruff:
  - `./.venv/bin/ruff check .`
  - result: `All checks passed!` (exit `0`).
- compileall:
  - `./.venv/bin/python -m compileall src tests`
  - result: pass (exit `0`).
- verbose pytest:
  - not rerun in this prompt (runtime behavior unchanged; test-only/script typing fixes).
- required regression files rerun:
  - `tests/test_cli_canonical.py` pass.
  - `tests/test_procore_endpoint_reference.py` pass.
  - `tests/test_procore_endpoint_audit.py` pass.
  - `tests/test_procore_sync.py` pass.
  - `tests/test_procore_obsidian_output.py` pass.
  - `tests/test_procore_cli_validate.py` pass.
- additional touched-area tests rerun:
  - `tests/test_construction_ollama_classification.py` pass.
  - grouped run for touched store/manifests/classification/body/store-links/delta tests pass.
- safe CLI checks (actual exit codes):
  - `./.venv/bin/hb-assistant --help` -> `0` (expected).
  - `./.venv/bin/hb-assistant auth status --json` -> `1` (expected offline/no-live-auth in this environment).
  - `./.venv/bin/hb-assistant procore validate --json` -> `1` (expected local non-ready checks / pending mapping / sqlite readiness).
  - `./.venv/bin/hb-assistant procore tools list --json` -> `0` (expected).
  - `./.venv/bin/hb-assistant construction-agent sources validate --json` -> `0` (expected).

## 8. Guardrails preserved
Confirmed:
- no live Procore calls.
- no live Microsoft Graph / SharePoint / OneDrive / Outlook calls from unit tests.
- no auth login / browser / device-code invocation in unit tests.
- no external writeback.
- no source document mutation.
- no POST / PUT / PATCH / DELETE Procore calls introduced.
- no secrets/tokens/authorization headers in evidence output.
- no skipped/xfail/deleted tests used to force green.
- no broad mypy suppression or exclusion expansion used to force green.

## 9. Residual risks / next steps
- `mypy .` is green; strict gate achieved for this prompt.
- repo remains dirty from prior Prompt 12/13 and generated artifacts/local noise; commit should be scoped carefully to intended files only.
