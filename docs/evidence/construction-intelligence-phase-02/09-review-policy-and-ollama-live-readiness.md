# Phase 02 — Prompt 09: Review Policy and Ollama Live Readiness

## Summary

Two distinct surfaces touched, no overlap:

**Review-policy verification.** The 4 PII rules (`pii-tax-document`, `pii-government-id`, `pii-health-record`, `pii-personal-financial`) and the OneDrive inventory-first scope recognition were already landed in Phase 02 Prompt 06 and Prompt 06 already shipped tests that exercise them (`test_inventory_first_applies_to_onedrive_business_root` / `_personal_root` / `_shared_library`; `test_new_pii_rules_route_personal_onedrive_files_to_review`; `test_seed_rule_count_includes_pii_additions`). What was *not* locked in was the **declaration-order determinism** that the controller policy depends on for provenance ordering. This prompt adds two regression guards: (1) `test_loader_preserves_yaml_declaration_order` proves the loader does not alphabetise, hash, or dict-reorder the rule list; (2) `test_evaluator_emits_matches_in_declared_rule_order` proves the evaluator yields multi-match results in the same order the YAML declares. No rule changes; the 16-rule seed is locked in shape.

**Ollama live readiness.** New code path. Adds a non-mutating `GET /api/tags` probe surfaced via a new `hb-assistant construction-agent ollama status [--json]` CLI command. The command always exits 0 — the JSON `report.ok` and `report.status` fields communicate readiness — so offline CI never fails on this check. `construction-agent validate --json` is intentionally unchanged (deferred per user direction). The new layer comprises: (a) two new fields on `ModelRoutingConfig` — `endpoint_url: str = "http://localhost:11434"` with `http://`/`https://`-scheme + no-trailing-slash validation, and `expected_models: list[str]` with explicit-overrides-must-cover-default-and-task-models validation; (b) a `resolved_expected_models()` helper that derives the effective list from `default_model` + task models when `expected_models` is omitted; (c) a new `classification/readiness.py` module with a Pydantic `ReadinessReport`, an `_resolve_endpoint()` precedence resolver (env var > config > hardcoded default), and `check_readiness()` that takes an injectable `requests_get` for clean testability; (d) the new CLI command with structured JSON envelope and a guardrails block declaring `endpoint_path=/api/tags`, `live_inference=false`.

The readiness module is statically guarded: a parametrized scan asserts the source contains no literal `/api/generate` reference, so a future edit cannot silently widen the probe into the inference path.

## Repo HEAD

- Before: `6bf4bc5` (Phase 02 Prompt 08 closeout)
- After: `a72a728197d95971d4a1027160381491cbc9c738`

## Files changed

```
 resources/config/ollama_model_routing.seed.yaml    |   6 +
 src/hb_assistant/cli/construction.py               |  57 ++++
 .../construction/classification/__init__.py        |  10 +
 .../construction/classification/models.py          |  55 ++++
 tests/test_construction_ollama_classification.py   | 307 +++++++++++++++++++++
 tests/test_construction_review_policy.py           |  52 ++++
 src/hb_assistant/construction/classification/readiness.py  | new file (~150 lines)
 7 files changed, ~640 insertions(+)
```

Plus this evidence file.

## Validation commands and outputs

### `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```
401 passed in 5.49s
```

(379 → 401; +22 net: 2 review-policy declaration-order tests, 7 schema tests, 3 endpoint-resolution tests, 5 readiness probe tests, 1 static-scan, 4 CLI tests = 22.)

### `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```
All checks passed!
```

### `hb-assistant construction-agent validate --json`

(Unchanged from Prompt 08 — readiness intentionally not folded into validate.)

```
checks:
  schema           ok=True   schema_version=5
  source_registry  ok=True   6 projects, 14 sources
  review_rules     ok=True   version=1; 16 rules; threshold=0.7
  model_routing    ok=True   version=1; default_model=llama3.2:1b; tasks=['classification', 'review_reason']
```

### `hb-assistant construction-agent ollama status --json` (NEW)

Live invocation in this non-interactive shell (no Ollama daemon running):

```json
{
  "command": "construction-agent ollama status",
  "report": {
    "endpoint_url": "http://localhost:11434",
    "endpoint_source": "default",
    "daemon_reachable": false,
    "expected_models": ["llama3.2:1b"],
    "present_models": [],
    "missing_models": ["llama3.2:1b"],
    "suggested_pull_commands": ["ollama pull llama3.2:1b"],
    "status": "daemon_unreachable",
    "ok": false,
    "error_redacted": "ollama_request_failed",
    "guardrails": {
      "external_systems": "read_only",
      "writeback": "none",
      "live_inference": "false",
      "endpoint_path": "/api/tags"
    }
  },
  "guardrails": { ... }
}
```

Exit code: `0` (offline-CI-safe by design).

### `hb-assistant procore mapping validate --json` + `procore tools list --json`

Unchanged from Prompt 07 baseline (Procore subsystem untouched this prompt).

## Four mocked readiness scenarios

All exercised via `tests/test_construction_ollama_classification.py` with `requests.get` mocked (no live daemon):

1. **Ready** — mocked `/api/tags` returns `{"models": [{"name": "llama3.2:1b"}]}`. Report: `ok=true`, `status="ready"`, `daemon_reachable=true`, `missing_models=[]`, `suggested_pull_commands=[]`, `error_redacted=null`.
2. **Daemon unreachable (network error)** — mocked `requests.ConnectionError`. Report: `ok=false`, `status="daemon_unreachable"`, `daemon_reachable=false`, `error_redacted="ollama_request_failed"`. Error contains no URL, hostname, port, or exception detail (verified via JSON-blob string assertion).
3. **Daemon unreachable (non-200)** — mocked HTTP 503. Report: `ok=false`, `status="daemon_unreachable"`, `error_redacted="ollama_status_503"`.
4. **Models missing** — mocked `/api/tags` returns `{"models": [{"name": "some-other-model:latest"}]}`. Report: `ok=false`, `status="models_missing"`, `daemon_reachable=true`, `missing_models` contains every expected model, `suggested_pull_commands` populated with `"ollama pull <model>"` strings.

Endpoint-override scenario (also mocked):
- `OLLAMA_HOST=http://probe.local:9999` set in env. Report: `endpoint_source="env"`, `endpoint_url="http://probe.local:9999"` (trailing slash stripped if supplied).

## Guardrail attestation

| Guardrail                                                                  | Status   | Where enforced |
|----------------------------------------------------------------------------|----------|----------------|
| Readiness never calls `/api/generate`                                      | Enforced | `readiness.py` only references `/api/tags` + static-scan test `test_readiness_module_does_not_reference_generate_endpoint` |
| Readiness never raises a network exception to its caller                   | Enforced | All `requests.RequestException` / status / json / shape failures are mapped to `ReadinessReport(daemon_reachable=False, status="daemon_unreachable")` |
| Readiness never leaks URL / hostname / secret in errors                    | Enforced | `error_redacted` is a fixed-set category code (`ollama_request_failed`, `ollama_status_{code}`, `ollama_invalid_envelope`, `ollama_missing_models_field`); test asserts hostname/port absent from the rendered report |
| `validate --json` unchanged                                                | Enforced | No edit to `_validate_model_routing()` or `validate_all()` |
| No model pulls, daemon launches, or live inference                         | Enforced | `readiness.py` only issues `requests.get(/api/tags)`; CLI command never invokes `OllamaChatClient.generate_json` |
| `OLLAMA_HOST` env overrides config; config overrides hardcoded default     | Enforced | `_resolve_endpoint()` precedence + 3 dedicated tests |
| Explicit `expected_models` must cover default_model + every task model     | Enforced | `ModelRoutingConfig._check_consistency` + 2 rejection tests |
| Review-rule loader preserves YAML declaration order                        | Enforced (new) | `test_loader_preserves_yaml_declaration_order` |
| Evaluator emits matches in declaration order                               | Enforced (new) | `test_evaluator_emits_matches_in_declared_rule_order` |
| 16-rule review seed shape is locked                                        | Enforced (unchanged) | `test_seed_rule_count_includes_pii_additions` |

## Blocked live / external validation

- Actual live `/api/tags` probe against an Ollama daemon was NOT performed in this prompt; the readiness path is exercised exclusively via mocked `requests.get` plus a real CLI invocation against the (offline) default endpoint, which correctly reports `daemon_unreachable`.
- Microsoft Graph token cache empty in this shell; no live Graph call attempted.
- Procore OAuth stubbed; no live Procore call attempted.

## Cross-references

- `ModelRoutingConfig` (extended) — `src/hb_assistant/construction/classification/models.py:92-180`
- `ReadinessReport`, `_resolve_endpoint`, `check_readiness` — `src/hb_assistant/construction/classification/readiness.py`
- `ollama status` CLI command — `src/hb_assistant/cli/construction.py` (after `classify decisions`, before `index status`)
- Review-policy declaration-order regression — `tests/test_construction_review_policy.py` (after `test_seed_rule_count_includes_pii_additions`)

## Notes on plan vs. delivery

The plan called for 3 review-policy verification tests. On reading the existing `tests/test_construction_review_policy.py`, two of those three were already covered by Prompt 06's test additions (OneDrive scope recognition at lines 704-722; PII routing at line 896-916). Per CLAUDE.md §3 (Surgical Changes), I added only the genuinely new declaration-order coverage — 2 tests, not 3. The third was intentionally not duplicated.

## Out of scope (deferred)

- Folding Ollama readiness into `construction-agent validate --json`.
- Live `/api/generate` calls or model pulls.
- Embedding-model routes (the `resolved_expected_models()` derivation accommodates them when introduced, but no embedding tasks exist today).
- Streaming or batched inference paths.
- Adding `pii_*` labels to `protected_categories` in `ollama_model_routing.seed.yaml` — PII routing is policy-only.

## Next prompt readiness

Repo HEAD advanced; working tree clean after commit; full pytest (401 passing) + ruff + CLI suite green; new `ollama status` CLI exercised both offline (this shell) and via 4 mocked scenarios in tests. Ready for Phase 02 Prompt 10.
