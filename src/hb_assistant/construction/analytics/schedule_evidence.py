"""Lightweight evidence references for schedule imports (audit trail only)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.config.path_policy import PathPolicy


def write_import_evidence(
    *,
    import_id: str,
    project_key: str,
    summary: dict[str, Any],
) -> str:
    """Persist evidence JSON under app-support; return evidence_package_id."""
    evidence_id = f"sched-ev-{uuid.uuid4().hex[:12]}"
    root = PathPolicy().get_app_support() / "schedule-evidence"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "evidence_package_id": evidence_id,
        "import_id": import_id,
        "project_key": project_key,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    path = root / f"{evidence_id}.json"
    path.write_bytes(body)
    return evidence_id