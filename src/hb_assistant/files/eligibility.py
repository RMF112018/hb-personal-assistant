"""EligibilityGate + ApprovalGate for selective file/attachment ingestion (08 spec + Phase 10).

Controls:
- size caps per family (pdf 250, office 100, cad 300, default 100)
- warn 100MB, manual approval >300MB
- supported matrix from 08 (pdf/docx/xlsx/pptx/csv/txt/md + images/zip metadata)
- failure codes: unsupported_type, too_large, manual_approval_required, ...
- ApprovalGate: explicit allow-list for items hitting manual gate (dry-run / CLI --approve for tests)
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


class ApprovalGate:
    """Explicit approval gate for items that hit requires_manual_approval (08 + 20 gates).

    v1.0.0 implementation: caller (service/CLI/tests) passes approved source_record_ids.
    Items still go through relevance + eligibility first. Dry-run friendly; no interactive prompt.
    """

    def __init__(self, approved_source_ids: Optional[set[int]] = None) -> None:
        self.approved = approved_source_ids or set()

    def is_approved(
        self, eligibility: EligibilityResult, *, source_record_id: Optional[int] = None
    ) -> tuple[bool, str]:
        if not eligibility.requires_manual_approval:
            return True, "auto_approved"
        if source_record_id is not None and source_record_id in self.approved:
            return True, "explicitly_approved"
        return False, eligibility.reason or "manual_approval_required"
