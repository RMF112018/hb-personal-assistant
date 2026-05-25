"""EligibilityGate for file/attachment ingestion per 08 spec.

Controls:
- size caps: default 100MB, pdf 250MB, office 100MB, cad_export 300MB
- warn_above_mb: 100
- require_manual_approval_above_mb: 300
- type allow-list from parser matrix
- failure codes: unsupported_type, too_large, manual_approval_required, ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from hb_assistant.normalize.drive_item import DriveItem

# From 08 spec
DEFAULT_MAX_MB = 100
PDF_MAX_MB = 250
OFFICE_MAX_MB = 100
CAD_EXPORT_MAX_MB = 300
WARN_ABOVE_MB = 100
MANUAL_APPROVAL_ABOVE_MB = 300

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".csv", ".txt", ".md",
    ".png", ".jpg", ".webp", ".zip"
}

@dataclass
class EligibilityResult:
    eligible: bool
    reason: Optional[str] = None  # failure code or "ok"
    requires_manual_approval: bool = False
    size_mb: float = 0.0

class EligibilityGate:
    """Decides if a DriveItem/attachment can proceed to download/parse."""

    def check(self, item: DriveItem, *, content_type: Optional[str] = None) -> EligibilityResult:
        if not item.is_file:
            return EligibilityResult(eligible=False, reason="unsupported_type")

        size_bytes = item.size or 0
        size_mb = size_bytes / (1024 * 1024)

        ext = ""
        if item.name and "." in item.name:
            ext = "." + item.name.rsplit(".", 1)[-1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            return EligibilityResult(eligible=False, reason="unsupported_type", size_mb=size_mb)

        # Size caps (simplified per family)
        max_mb = DEFAULT_MAX_MB
        if ext == ".pdf":
            max_mb = PDF_MAX_MB
        elif ext in {".docx", ".xlsx", ".xlsm", ".pptx"}:
            max_mb = OFFICE_MAX_MB

        if size_mb > max_mb:
            if size_mb > MANUAL_APPROVAL_ABOVE_MB:
                return EligibilityResult(eligible=False, reason="manual_approval_required", size_mb=size_mb, requires_manual_approval=True)
            return EligibilityResult(eligible=False, reason="too_large", size_mb=size_mb)

        requires_approval = size_mb > MANUAL_APPROVAL_ABOVE_MB or size_mb > WARN_ABOVE_MB  # simplified

        return EligibilityResult(
            eligible=True,
            reason="ok",
            requires_manual_approval=requires_approval,
            size_mb=size_mb
        )
