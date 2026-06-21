# Forecast UI — Launch Bootstrap (run the forecast surfaces locally)

**Audience:** Operator (Bobby).
**Posture:** Local-first, read-only surfaces; the only writes are to isolated forecast work-roots
under app-support. No live source writeback; no path strings in any status payload.

This runbook covers the launch bootstrap added in ADR 278: when the app is launched, the forecast
**write-roots** are ensured and a redaction-safe readiness report is surfaced, so the write-backed
forecast surfaces serve real data out of the box. See ADR
`docs/architecture/278-forecast-ui-launch-bootstrap.md`.

## What gets auto-provisioned

On `hb-assistant launcher dev`/`production`, the launcher defaults 3 forecast **write-roots** under
the environment's app-support and the backend creates them at startup:

| Root key           | Default location                                          | Purpose                       |
|--------------------|----------------------------------------------------------|-------------------------------|
| `runs_root`        | `<app-support>/analytics/forecast/runs`                  | Run Center execution artifacts |
| `eval_root`        | `<app-support>/analytics/forecast/eval`                  | External-eval results          |
| `config_edit_root` | `<app-support>/analytics/forecast/config-edit`           | Isolated config-edit proposals |

A default is injected **only when unset** — an operator value in the env or the settings file always
wins. Dev uses the `…HB Personal Assistant (Dev)` app-support root; production uses the configured
root.

## What you must still configure (fail-closed read-roots)

The **read-roots** point at the live Tropical inputs and are NEVER auto-invented. Until they are set
(Settings page or env), the surfaces that depend on them report `not_configured` and stay not-ready:

- `package_roots` → forecast package dirs (catalog, external-eval)
- `data_root` → live forecast data root (run-center)
- `db_path` → source-domain / config DB (config viewer, config-edit, external-eval)
- `cfr_src` → optional; defaults to the bundled subrepo

## Launch

```bash
hb-assistant launcher dev --open --json        # Dev: starts backend+frontend, opens the browser
hb-assistant launcher production --open --json  # Production
```

The `start`/`open` JSON now includes a non-fatal `forecast_readiness` block (the same redaction-safe
shape as `GET /api/forecast/runtime/status`, plus a coded `created` list of write-root keys created
this launch). A bootstrap failure degrades to a coded `unavailable` status and never blocks the
launch. `--plan` is side-effect-free (no dirs created, no readiness block).

## Verify

```bash
# Authoritative readiness once the backend is up (path-free payload):
curl -s -H 'X-HB-UI-Role: viewer' http://127.0.0.1:8000/api/forecast/runtime/status | python -m json.tool
```

Expect `roots.runs_root.valid == true` (and eval/config-edit) with the dirs now present under
`<app-support>/analytics/forecast/`, and read-roots reporting their blocker until configured. The
payload must contain no path strings.

## Manual `uvicorn` (no launcher)

The startup bootstrap also runs under a direct factory launch, so the same ensure-dirs behavior
applies — but write-roots are **not** auto-defaulted (that happens only in the launcher path):

```bash
uvicorn hb_assistant.construction.analytics.api:create_app --factory --port 8000
```

With nothing configured this is a strict no-op (fail-closed): no directories are created. Set
`HB_FORECAST_RUNS_ROOT` / `HB_FORECAST_EVAL_ROOT` / `HB_FORECAST_CONFIG_EDIT_ROOT` (and the
read-roots) explicitly, or configure them via the Settings page.
