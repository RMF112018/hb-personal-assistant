import json
import os
from pathlib import Path
from datetime import datetime, timezone

from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService

evidence_dir = Path(os.environ["EVIDENCE_DIR"])
keys_path = evidence_dir / "imported-schedule-version-keys.txt"
out_path = evidence_dir / "artifacts" / "cpm-chain-run-output.json"

schedule_version_keys = []
for raw in keys_path.read_text().splitlines():
    line = raw.strip()
    if line and not line.startswith("#"):
        schedule_version_keys.append(line)

if not schedule_version_keys:
    raise SystemExit(f"No schedule version keys found in {keys_path}")

db_path = os.environ["HB_ASSISTANT_DB_PATH"]
service = ScheduleCpmGraphService(db_path=db_path)

method_names = [
    "run_graph_diagnostics",
    "run_forward_pass",
    "run_backward_pass",
    "run_float_calculation",
    "run_longest_path",
    "run_criticality_classification",
]

results = {
    "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "db_path": db_path,
    "schedule_version_keys": schedule_version_keys,
    "method_names": method_names,
    "runs": [],
}

for svk in schedule_version_keys:
    svk_result = {"schedule_version_key": svk, "steps": []}

    for method_name in method_names:
        fn = getattr(service, method_name)

        try:
            result = fn(svk)
            svk_result["steps"].append({
                "method": method_name,
                "ok": True,
                "result": result,
            })
        except Exception as exc:
            svk_result["steps"].append({
                "method": method_name,
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            break

    results["runs"].append(svk_result)

out_path.write_text(json.dumps(results, indent=2, default=str))
print(json.dumps(results, indent=2, default=str))
