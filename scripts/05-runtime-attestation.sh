#!/usr/bin/env bash
# P1 §3.1 — runtime tool-surface attestation smoke (post-deploy operator step).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="python3"; fi
export PYTHONPATH="${ROOT}/src:${ROOT}/subrepos/construction-financial-review/src${PYTHONPATH:+:$PYTHONPATH}"

echo "=== runtime attestation smoke ==="
"$PY" - <<'PY'
import json
import sys

from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig

cfg = NasMcpConfig.from_env()
broker = NasMcpBroker(cfg)
report = broker.dispatch("pa_tool_surface_runtime_attestation", {})["result"]
summary = {
    "attestation_ok": report.get("attestation_ok"),
    "runtime_commit": report.get("runtime_commit"),
    "manifest_version": report.get("manifest_version"),
    "tested_tool_count": report.get("tested_tool_count"),
    "passed_count": report.get("passed_count"),
    "failed_count": report.get("failed_count"),
    "skipped_count": report.get("skipped_count"),
    "client_writes_must_be_blocked": report.get("client_writes_must_be_blocked"),
    "elapsed_ms": report.get("elapsed_ms"),
}
print(json.dumps(summary, sort_keys=True))
if not report.get("attestation_ok"):
    failed = [r["tool_name"] for r in report.get("per_tool", []) if r.get("status") == "failed"]
    print("FAILED_TOOLS:", failed[:20], file=sys.stderr)
    sys.exit(1)
PY

echo "=== freshness includes execution attestation ==="
"$PY" - <<'PY'
import json
import sys

from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig

cfg = NasMcpConfig.from_env()
broker = NasMcpBroker(cfg)
fr = broker.dispatch("pa_tool_surface_freshness_check", {})["result"]
summary = {
    "stale": fr.get("stale"),
    "staleness_state": fr.get("staleness_state"),
    "execution_attestation_ok": fr.get("execution_attestation_ok"),
    "execution_attestation_failed_count": fr.get("execution_attestation_failed_count"),
    "client_writes_must_be_blocked": fr.get("client_writes_must_be_blocked"),
}
print(json.dumps(summary, sort_keys=True))
assert fr.get("execution_attestation_ok") is True, fr.get("warnings")
assert fr.get("categories", {}).get("execution_attestation") is False
PY

echo "ok"