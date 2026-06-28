"""Capture the DCMA computed-CPM evaluation as STRUCTURED JSON (not a repr string).

The original capture-dcma-sample.py serialized the dataclass with json.dumps(default=str),
which collapsed DcmaCriticalPathEvaluation into a single repr string. This version uses
dataclasses.asdict so the evidence file is machine-readable structured JSON.

Run with EVIDENCE_DIR and HB_ASSISTANT_DB_PATH set (HB_ASSISTANT_DB_PATH must point at the
evidence DB copy; this script reads only).
"""

import dataclasses
import json
import os
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService

evidence_dir = Path(os.environ["EVIDENCE_DIR"])
db_path = os.environ["HB_ASSISTANT_DB_PATH"]
svk = "tropical|1071|2026-06-23 08:00"

service = ScheduleCpmGraphService(db_path=db_path)
result = service.evaluate_dcma_critical_path(svk)

if dataclasses.is_dataclass(result):
    result_payload = dataclasses.asdict(result)
elif hasattr(result, "__dict__"):
    result_payload = dict(result.__dict__)
else:
    result_payload = {"repr": repr(result)}

payload = {
    "schedule_version_key": svk,
    "result": result_payload,
}

out = json.dumps(payload, indent=2, default=str)
(evidence_dir / "artifacts" / "dcma-computed-cpm-sample.json").write_text(out)
print(out)
