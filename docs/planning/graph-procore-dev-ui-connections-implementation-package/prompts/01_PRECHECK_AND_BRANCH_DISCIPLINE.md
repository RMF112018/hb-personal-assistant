# P00 — Precheck and Branch Discipline

# Repo-Truth Preflight

Run these before source changes and include outputs in the P00 closeout.

## Baseline

```bash
git status --short
git status -sb
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30
git remote -v
python - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f).get("project", {}).get("version"))
PY
cat frontend/package.json
```

## Launcher

```bash
hb-assistant launcher close --environment dev --action quit --json || true
hb-assistant launcher dev --plan --json
hb-assistant launcher dev --open --open-timeout-seconds 45 --json
hb-assistant launcher status --environment dev --json
```

Record Dev app-support root, Dev DB path, frontend port, backend port, environment mode, source mode, process health, and browser-open result.

## Source inventory

```bash
find src -maxdepth 6 -type f | sort
find frontend/src -maxdepth 6 -type f | sort
find tests -maxdepth 4 -type f | sort
```

## Search targets

```bash
rg -n "Graph|graph|Microsoft|M365|365|mail|calendar|files|OneDrive|SharePoint" src frontend tests
rg -n "Procore|procore|HB_PROCORE_LIVE|OAuth|oauth|token|keychain|mapping|projects|sync" src frontend tests
rg -n "source-refresh|refresh-sources|daily-source-refresh|scheduler|daily brief|data quality|freshness|confidence" src frontend tests
rg -n "fetch\(|axios|apiClient|VITE_|127.0.0.1|localhost|/api/" frontend/src frontend
```

## Safe CLI status checks

```bash
hb-assistant graph mail status --json || true
hb-assistant graph calendar status --json || true
hb-assistant graph files status --json || true
hb-assistant procore auth status --json || true
hb-assistant procore mapping validate --json || true
hb-assistant scheduler status daily-source-refresh --environment dev --json || true
```

Do not run live Graph indexing/discovery, Procore projects list, Procore sync, or live source refresh unless the operator explicitly approves and gates are enabled.

## Browser failure capture

Open `http://127.0.0.1:5173`, navigate to current Settings/Connections/Source Status UI, and capture:

- visible failure;
- console errors;
- network request URLs and status codes;
- backend logs;
- response bodies;
- whether the failure is missing endpoint, wrong endpoint, response-shape mismatch, CORS/base-url issue, unimplemented auth flow, or local/mock mode confusion.


## Acceptance criteria

No source edits except optional evidence notes. Current UI failure path is captured and classified.
