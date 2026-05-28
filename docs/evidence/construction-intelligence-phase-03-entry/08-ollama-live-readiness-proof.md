# Phase 03 Entry — Prompt 08: Ollama Live Readiness Proof

**Date:** 2026-05-28
**Operator:** bfetting@hedrickbrothers.com
**Repo:** `/Users/bobbyfetting/hb-personal-assistant`
**HEAD at evidence capture:** `71e758d` (parent of the prompt-08 evidence commit)
**Prompt:** `HB_Construction_Intelligence_Phase_03_Entry_Package/prompts/Prompt_08_*`

## Scope

Evidence-only proof that the existing Ollama readiness surface reports accurately
against the local environment, without coupling validation to a live daemon. No
behavior changes were made to the readiness probe or its CLI handler; one
unrelated single-line typo in `src/hb_assistant/cli/procore.py` (parallel
Prompt_09 workstream) was repaired in a separate commit to unblock CLI import —
see "Incidental unblock" below.

## Commands run

```
hb-assistant construction-agent ollama status --json
ollama list || true
python -m pytest tests/test_construction_ollama_classification.py
grep -n "/api/generate" src/hb_assistant/construction/classification/readiness.py
```

## 1. `hb-assistant construction-agent ollama status --json`

Verbatim stdout (exit 0):

```json
{
  "command": "construction-agent ollama status",
  "report": {
    "endpoint_url": "http://localhost:11434",
    "endpoint_source": "default",
    "daemon_reachable": false,
    "expected_models": [
      "llama3.2:1b"
    ],
    "present_models": [],
    "missing_models": [
      "llama3.2:1b"
    ],
    "suggested_pull_commands": [
      "ollama pull llama3.2:1b"
    ],
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
  "guardrails": {
    "external_systems": "read_only",
    "writeback": "none",
    "live_inference": "false",
    "endpoint_path": "/api/tags"
  }
}
```

**Process exit code:** `0` (offline-safe; callers inspect `report.ok`).

## 2. `ollama list || true`

Verbatim stdout/stderr (`||` clause keeps shell exit 0):

```
Error: could not connect to ollama server, run 'ollama serve' to start it
```

Daemon is not running on this workstation at evidence-capture time. The `|| true`
guard preserves shell exit `0` so the readiness probe never blocks a script
even when the local daemon is offline.

## 3. Model presence / missing / suggested pulls

Read from the JSON in section 1:

| Field | Value |
| --- | --- |
| `expected_models` | `["llama3.2:1b"]` |
| `present_models` | `[]` (daemon unreachable; cannot enumerate) |
| `missing_models` | `["llama3.2:1b"]` (cannot confirm presence; treated as missing) |
| `suggested_pull_commands` | `["ollama pull llama3.2:1b"]` |

**Operator note:** Suggested pull is **not** executed. Prompt 08 explicitly
forbids automatic pulls absent operator authorization in the local notes;
no such authorization was provided. The operator can run
`ollama serve` and `ollama pull llama3.2:1b` at their discretion outside this
prompt's scope.

## 4. Endpoint source classification

From the JSON: `endpoint_source: "default"`. The probe resolves the endpoint in
this precedence — `OLLAMA_HOST` env var (→ `"env"`) → config file
(→ `"config"`) → built-in default `http://localhost:11434` (→ `"default"`).
Neither env var nor config override is set in this environment, so the probe
falls through to the default.

## 5. Offline-safe behavior proofs

**Exit code:** the `hb-assistant construction-agent ollama status --json`
command exited `0` even though `report.ok == false` and
`report.status == "daemon_unreachable"`. This is the contract:
the JSON command never propagates daemon failure as a non-zero shell exit, so
CI and validation never depend on a live daemon.

**Static guardrail attestation:** the readiness module does not reference the
live-inference endpoint at all.

```
$ grep -n "/api/generate" src/hb_assistant/construction/classification/readiness.py
$ echo $?
1
```

Exit `1` = zero matches. The module's `guardrails.endpoint_path` is pinned to
`/api/tags` (read-only model enumeration). The repository also carries the
companion static-scan test
`test_readiness_module_does_not_reference_generate_endpoint` which would
fail-loud on any future regression.

**Separation from `validate --json`:** `ollama status` is registered under a
separate Typer sub-app (`construction-agent ollama status`); the
`construction-agent validate` command path does not import or invoke the
readiness probe. Verified by the existing test suite (section 6).

## 6. Test suite — `tests/test_construction_ollama_classification.py`

Verbatim pytest tail:

```
...........................................................              [100%]
59 passed in 0.32s
```

59 / 59 passing. Coverage includes (per audit):

- `test_readiness_ok_when_daemon_returns_all_expected_models`
- `test_readiness_models_missing_when_some_absent`
- `test_readiness_daemon_unreachable_on_connection_error`
- `test_readiness_daemon_unreachable_on_non_200`
- `test_readiness_daemon_unreachable_on_malformed_response`
- `test_endpoint_source_env_when_ollama_host_set`
- `test_endpoint_source_config_when_seed_overrides_default`
- `test_endpoint_source_default_when_neither_set`
- `test_cli_ollama_status_ready_when_daemon_returns_models`
- `test_cli_ollama_status_daemon_unreachable_still_exits_0`
- `test_cli_ollama_status_respects_ollama_host_env`
- `test_cli_ollama_status_models_missing_shows_pull_commands`
- `test_readiness_module_does_not_reference_generate_endpoint`
- (additional fixtures-and-classification tests, totalling 59)

## Acceptance criteria

| Criterion | Result |
| --- | --- |
| Readiness reports accurately | ✅ `daemon_unreachable` + missing-model list + pull suggestions match observed local state |
| Offline daemon does not block entry acceptance | ✅ CLI exits 0 with `report.ok=false`; 59 tests pass with no live daemon |
| Readiness not folded into `validate --json` | ✅ separate Typer sub-app; verified by existing coverage |
| No `/api/generate` call | ✅ static grep confirms zero references |
| No automatic daemon start, no automatic model pull | ✅ neither attempted |
| `endpoint_source` captured | ✅ JSON field reports `"default"` in this environment |

## Incidental unblock (separate commit)

Initial CLI invocation failed with `NameError: name 'procore_app' is not
defined` at `src/hb_assistant/cli/procore.py:381`. The parallel Prompt_09
Procore commit (`71e758d`) registered a new `sync` sub-app via
`procore_app.add_typer(...)` while every sibling registration in that file
(`auth`, `tools`, `mapping`, `projects`, `companies`, `audit`, lines 41–46)
uses the variable `app`. The mismatch prevented the entire `hb-assistant` CLI
from loading, blocking the Prompt 08 commands.

A single-character variable rename (`procore_app` → `app` on line 381) was
applied as a stand-alone commit before this evidence commit, mirroring the
pattern of every other `app.add_typer(...)` line in the same file. No behavior
change beyond the import path being walkable; no Procore code paths beyond
that one line were touched.
