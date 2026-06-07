# 02 Repo-Truth Audit Baseline

## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Audited HEAD from GitHub connector/static repo inspection: `c52cc757b062fe4baf918bd7227dad5e669e3899`
- App version observed: `1.3.0`
- Frontend package version observed: `0.0.0`
- SQLite schema head observed: `V40`
- Latest merged PR observed: PR #3, `Codex/frontend shell layout p00`
- Local dirty state: not verifiable from this package generation context; local agent must run `git status --short` before editing.
- Local launcher/scheduler runtime state: not verifiable from this package generation context; local agent must run the launcher/scheduler commands listed in Prompt 00.

Repository truth is authoritative. This package is an implementation guide only. Reconfirm every touched path and command before editing.


## Verified static findings

- `pyproject.toml` defines project version `1.3.0`, optional extras for `second-brain`, `mcp`, `retrieval`, `retrieval-local`, and `analytics-ui`.
- `frontend/package.json` defines Vite/React scripts and version `0.0.0`.
- `SQLiteMigrator.LATEST_SCHEMA_VERSION` is `40`.
- Launcher profiles enforce strict Dev/Production path isolation and default Dev source refresh mode to `mock_data`.
- Source refresh orchestrator has preflight, Procore, Graph, rebuild, and finalize stages.
- Rebuild includes approved source manifest, coverage parity, vector index plan/apply, Daily Brief V2, no-raw vector index proof, and MCP no-raw/no-writeback proofs.
- Frontend currently exposes Today, Projects, Project subpages, My Items, Data Health, Settings, and Get Started.
- `vault`, `sync`, and `brief` root CLI command groups are currently stubs and should be converted or replaced only under explicit Phase 10 prompts.

## Local-agent baseline commands

Before editing, run:

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

python - <<'PY'
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION
print(LATEST_SCHEMA_VERSION)
PY

cat frontend/package.json
hb-assistant launcher dev --plan --json
hb-assistant launcher status --environment dev --json
hb-assistant launcher production --plan --json
hb-assistant scheduler status daily-source-refresh --environment production --json
hb-assistant second-brain status --json
hb-assistant second-brain retrieval llamaindex status --json
```

## Stop if

- Current HEAD differs from the expected head and the diff touches any Phase 10 target file family.
- Dev and Production resolve to the same app-support or DB path.
- Validation shows raw-content or writeback guard regressions.
