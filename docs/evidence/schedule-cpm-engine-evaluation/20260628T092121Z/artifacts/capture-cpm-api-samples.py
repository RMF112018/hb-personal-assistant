import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

evidence_dir = Path(os.environ["EVIDENCE_DIR"])
svk = "tropical|1071|2026-06-23 08:00"
encoded = quote(svk, safe="")
base_url = "http://127.0.0.1:8000"

out_dir = evidence_dir / "artifacts" / "api-samples"
out_dir.mkdir(parents=True, exist_ok=True)

endpoints = {
    "summary": f"{base_url}/api/schedules/versions/{encoded}/cpm/summary",
    "activities": f"{base_url}/api/schedules/versions/{encoded}/cpm/activities",
    "longest-path": f"{base_url}/api/schedules/versions/{encoded}/cpm/longest-path",
    "diagnostics": f"{base_url}/api/schedules/versions/{encoded}/cpm/diagnostics",
}

standard_names = {
    "summary": "api-cpm-summary-sample.json",
    "activities": "api-cpm-activities-sample.json",
    "longest-path": "api-cpm-longest-path-sample.json",
    "diagnostics": "api-cpm-diagnostics-sample.json",
}

for name, url in endpoints.items():
    with urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))

    specific_path = out_dir / f"tropical-1071-2026-06-23-0800-{name}.json"
    standard_path = evidence_dir / "artifacts" / standard_names[name]

    rendered = json.dumps(payload, indent=2, default=str)
    specific_path.write_text(rendered)
    standard_path.write_text(rendered)

    print(f"Wrote {specific_path}")
    print(f"Wrote {standard_path}")
