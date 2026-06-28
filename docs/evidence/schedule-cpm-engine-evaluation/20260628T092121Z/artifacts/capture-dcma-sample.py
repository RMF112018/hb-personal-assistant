import json
import os
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService

evidence_dir = Path(os.environ["EVIDENCE_DIR"])
db_path = os.environ["HB_ASSISTANT_DB_PATH"]
svk = "tropical|1071|2026-06-23 08:00"

service = ScheduleCpmGraphService(db_path=db_path)
result = service.evaluate_dcma_critical_path(svk)

payload = {
    "schedule_version_key": svk,
    "result": result,
}

out = json.dumps(payload, indent=2, default=str)

(evidence_dir / "artifacts" / "dcma-computed-cpm-sample.json").write_text(out)
print(out)
