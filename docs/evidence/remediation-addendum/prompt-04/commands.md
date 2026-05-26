# Addendum Prompt 04 Command Log

All commands were executed from `/Users/bobbyfetting/hb-personal-assistant`.

## Starting checks

1. `git status --short` -> exit 0  
   output: `command-results/01-git-status-short.txt`
2. `git branch --show-current` -> exit 0  
   output: `command-results/02-git-branch-show-current.txt`
3. `git rev-parse HEAD` -> exit 0  
   output: `command-results/03-git-rev-parse-head.txt`
4. `git log --oneline -5` -> exit 0  
   output: `command-results/04-git-log-oneline-5.txt`
5. `source .venv/bin/activate && python --version` -> exit 0  
   output: `command-results/05-python-version.txt`
6. `source .venv/bin/activate && hb-assistant --version` -> exit 0  
   output: `command-results/06-hb-assistant-version.txt`

## Runtime validation and proof rerun

7. `source .venv/bin/activate && hb-assistant diagnostics paths --json` -> exit 0  
   output: `command-results/07-diagnostics-paths-json.txt`
8. `source .venv/bin/activate && hb-assistant auth status --json` -> exit 1  
   output: `command-results/08-auth-status-json.txt`
9. Conditional login step -> skipped (no `token_type=none`; status path already in network/status-error state)  
   output: `command-results/09-auth-login-json.txt`
10. `source .venv/bin/activate && hb-assistant diagnostics graph --safe --json` -> exit 1  
    output: `command-results/10-diagnostics-graph-safe-json.txt`
11. `source .venv/bin/activate && hb-assistant diagnostics proof delegated-graph --json` -> exit 1  
    output: `command-results/11-diagnostics-proof-delegated-graph-json.txt`
12. `source .venv/bin/activate && hb-assistant diagnostics scan-sensitive --repo . --json` -> exit 0  
    output: `command-results/12-diagnostics-scan-sensitive-json.txt`
13. `source .venv/bin/activate && python -m pytest tests/test_graph_proof.py tests/test_auth.py` -> exit 0  
    output: `command-results/13-pytest-graph-proof-auth.txt`

## Notes

- Commands 8, 10, and 11 returned valid JSON and no traceback.
- Delegated Graph proof did not reach Graph API status responses in this run.
