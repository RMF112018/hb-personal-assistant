"""Phase 06 — attachment metadata analysis (pure, metadata-only).

Classifies an email attachment from its **name and content type only** (never its
content): whether it is a SharePoint/OneDrive link, whether it is a document worth
a source-link candidate, and whether its filename hints at sensitive content that
must route to review. Also detects SharePoint/OneDrive URLs in a bounded bodyPreview.

Pure and deterministic — no I/O, no content download. Attachment content is never
requested ($select excludes contentBytes; the `$value` path is on the blocklist).
Sensitivity categories mirror the package's
`resources/json/email_sensitivity_review_categories.json`.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from hb_assistant.normalize.redaction import hash_value

# Filename extensions that indicate a stored document (a source-link candidate may
# correspond to the same file in SharePoint/OneDrive). Inline images are excluded.
DOCUMENT_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx",
    ".dwg", ".dxf", ".rvt", ".vsdx", ".csv", ".txt", ".rtf", ".msg",
)
# Internet-shortcut style attachments that ARE a link to a drive item.
LINK_EXTENSIONS = (".url", ".website", ".lnk")

# Sensitive-category keyword map (category -> (keywords, level)). Categories match
# email_sensitivity_review_categories.json; route_to_review_by_default is true.
_HIGH = "high"
_MEDIUM = "medium"
SENSITIVITY_KEYWORDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("legal_correspondence", ("legal", "attorney", "counsel", "litigation"), _HIGH),
    ("privileged_or_confidential_markers", ("privileged", "confidential", "do not distribute", "nda"), _HIGH),
    ("claims", ("claim",), _HIGH),
    ("default_or_termination_language", ("termination", "default notice", "cure notice", "notice to cure"), _HIGH),
    ("disputes", ("dispute",), _HIGH),
    ("injuries", ("injury", "injuries", "accident", "osha"), _HIGH),
    ("incidents", ("incident",), _HIGH),
    ("medical_detail", ("medical", "health record"), _HIGH),
    ("personnel_or_hr", ("payroll", "ssn", "w-2", "w2 ", "1099", "offer letter", "personnel"), _HIGH),
    ("liquidated_damages", ("liquidated damages",), _HIGH),
    ("contracts", ("contract", "agreement", "subcontract"), _MEDIUM),
    ("change_orders", ("change order", "changeorder"), _MEDIUM),
    ("notices", ("notice",), _MEDIUM),
    ("insurance_or_bonding", ("insurance", "certificate of insurance", "coi", "bond"), _MEDIUM),
    ("pay_applications", ("pay app", "payapp", "payment application", "g702", "g703"), _MEDIUM),
    ("invoices", ("invoice",), _MEDIUM),
    ("lien_releases", ("lien", "lien release", "lien waiver"), _MEDIUM),
    ("delay_or_time_extension_language", ("delay", "time extension"), _MEDIUM),
    ("additional_compensation_language", ("additional compensation", "extra work"), _MEDIUM),
)

_DRIVE_LINK_HOSTS = ("sharepoint.com", "-my.sharepoint.com", "onedrive.live.com", "1drv.ms")


class AttachmentAnalysis(BaseModel):
    """Deterministic, metadata-only verdict for one attachment."""

    name_redacted: Optional[str] = None
    name_hash: Optional[str] = None
    is_document: bool = False
    link_detected: bool = False
    source_link_candidate: bool = False
    candidate_target_system: Optional[str] = None  # "sharepoint" | "onedrive"
    sensitivity_hint: Optional[str] = None
    sensitivity_level: Optional[str] = None
    review_required: bool = False

    model_config = {"extra": "forbid"}


def _extension(name: Optional[str]) -> str:
    if not name or "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[1].lower()


def _redact_name(name: Optional[str]) -> Optional[str]:
    """Keep only the extension (non-identifying) + a hash of the full name."""
    if not name:
        return None
    ext = _extension(name)
    return f"[redacted:{hash_value(name)}]{ext}"


def _classify_sensitivity(name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not name:
        return None, None
    low = name.lower()
    for category, keywords, level in SENSITIVITY_KEYWORDS:
        if any(kw in low for kw in keywords):
            return category, level
    return None, None


def classify_text_sensitivity(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Classify arbitrary text (e.g. a decrypted-in-memory body) against the
    sensitivity categories. Returns ``(category, level)`` or ``(None, None)``.

    Used in-memory only (the caller discards plaintext after); no text is stored.
    """
    return _classify_sensitivity(text)


def analyze_attachment(
    name: Optional[str], content_type: Optional[str], is_inline: bool
) -> AttachmentAnalysis:
    """Classify an attachment from name + content type only (never content)."""
    ext = _extension(name)
    low_name = (name or "").lower()
    link_detected = ext in LINK_EXTENSIONS or "sharepoint" in low_name or "onedrive" in low_name
    is_document = (not is_inline) and (
        ext in DOCUMENT_EXTENSIONS
        or (content_type is not None and _looks_documentish(content_type))
    )
    source_link_candidate = (is_document or link_detected) and not is_inline
    target_system = "onedrive" if "onedrive" in low_name else "sharepoint"

    sensitivity_hint, sensitivity_level = _classify_sensitivity(name)
    review_required = sensitivity_hint is not None

    return AttachmentAnalysis(
        name_redacted=_redact_name(name),
        name_hash=hash_value(name),
        is_document=is_document,
        link_detected=link_detected,
        source_link_candidate=source_link_candidate,
        candidate_target_system=target_system if source_link_candidate else None,
        sensitivity_hint=sensitivity_hint,
        sensitivity_level=sensitivity_level,
        review_required=review_required,
    )


def _looks_documentish(content_type: str) -> bool:
    ct = content_type.lower()
    return (
        "pdf" in ct
        or "msword" in ct
        or "officedocument" in ct
        or "ms-excel" in ct
        or "ms-powerpoint" in ct
        or "vnd.ms-" in ct
    )


def detect_drive_links(text: Optional[str]) -> Optional[str]:
    """Detect a SharePoint/OneDrive URL host in bounded preview/link text.

    Returns a redacted evidence token (host fragment hash) when found, else None.
    Reads metadata text only; never fetches content.
    """
    if not text:
        return None
    low = text.lower()
    for host in _DRIVE_LINK_HOSTS:
        if host in low:
            # Evidence is the host label, not the full (potentially sensitive) URL.
            return f"{host}:{hash_value(text)}"
    # Generic SharePoint tenant host (e.g. contoso.sharepoint.com) already covered by
    # "sharepoint.com"; also catch a bare onedrive token.
    if re.search(r"\bonedrive\b", low):
        return f"onedrive:{hash_value(text)}"
    return None
