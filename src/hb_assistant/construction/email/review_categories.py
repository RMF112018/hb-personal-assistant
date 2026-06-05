"""Phase 06 Prompt 10 — sensitive review-category registry (pure, in-module authority).

Authoritative catalog of the construction-sensitive email categories that route a
message to review and gate encrypted-body capture. This is the **single source of
truth** for review routing; it deliberately *reproduces* (does not import) the 19
legacy attachment categories from
:mod:`hb_assistant.construction.email.attachment_analyzer` so that module's stable
behavior and tests stay untouched, and it adds the 4 additional categories the
Phase 06 package requires (`confidential_bid_or_estimate`, `owner_directive`,
`subcontractor_default`, `schedule_recovery_or_acceleration`).

Pure and deterministic — no I/O. The 19 legacy ids/levels/keywords are held
identical to ``attachment_analyzer.SENSITIVITY_KEYWORDS``; a drift-guard test plus
``resources/config/email_sensitivity_review_categories.json`` keep them in sync.

Every category is treated as sensitive: encrypted-body capture is *permitted* but
*requires review first* (mirrors the policy lock
``encrypted_body_requires_review_for_sensitive``). No category ever permits
plaintext-body persistence — that stays forbidden at the policy/schema layer.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

_HIGH = "high"
_MEDIUM = "medium"


class ReviewCategory(BaseModel):
    """One sensitive review category (metadata only; never message content)."""

    id: str
    label: str
    trigger_terms: tuple[str, ...]
    sensitivity_level: str  # "high" | "medium"
    recommended_review_action: str
    encrypted_body_capture_allowed: bool
    encrypted_body_capture_requires_review_first: bool
    evidence_safe_explanation: str

    model_config = {"extra": "forbid", "frozen": True}


def _cat(
    cid: str,
    label: str,
    terms: tuple[str, ...],
    level: str,
    action: str,
    explanation: str,
) -> ReviewCategory:
    # Every category is sensitive: encryption is allowed but review precedes any
    # body-derived conclusion (policy: encrypted_body_requires_review_for_sensitive).
    return ReviewCategory(
        id=cid,
        label=label,
        trigger_terms=terms,
        sensitivity_level=level,
        recommended_review_action=action,
        encrypted_body_capture_allowed=True,
        encrypted_body_capture_requires_review_first=True,
        evidence_safe_explanation=explanation,
    )


# The 23-category registry. The first 19 mirror attachment_analyzer.SENSITIVITY_KEYWORDS
# (same ids, keywords, levels); the last 4 are Phase 06 Prompt 10 additions.
REVIEW_CATEGORIES: tuple[ReviewCategory, ...] = (
    # --- 19 legacy categories (identical ids/keywords/levels) -------------------
    _cat(
        "legal_correspondence",
        "Legal correspondence",
        ("legal", "attorney", "counsel", "litigation"),
        _HIGH,
        "route_to_legal_review",
        "possible legal correspondence; review before relying on content",
    ),
    _cat(
        "privileged_or_confidential_markers",
        "Privileged / confidential markers",
        ("privileged", "confidential", "do not distribute", "nda"),
        _HIGH,
        "treat_as_privileged_route_to_review",
        "possible privileged/confidential marking; restrict and review",
    ),
    _cat(
        "claims",
        "Claims",
        ("claim",),
        _HIGH,
        "route_to_review_no_determination",
        "possible claim language; not a determination, review required",
    ),
    _cat(
        "default_or_termination_language",
        "Default / termination language",
        ("termination", "default notice", "cure notice", "notice to cure"),
        _HIGH,
        "escalate_to_review",
        "possible default/termination language; review before acting",
    ),
    _cat(
        "disputes",
        "Disputes",
        ("dispute",),
        _HIGH,
        "route_to_review_no_determination",
        "possible dispute language; review required",
    ),
    _cat(
        "injuries",
        "Injuries",
        ("injury", "injuries", "accident", "osha"),
        _HIGH,
        "route_to_safety_review",
        "possible injury/safety content; route to safety review",
    ),
    _cat(
        "incidents",
        "Incidents",
        ("incident",),
        _HIGH,
        "route_to_safety_review",
        "possible incident content; route to review",
    ),
    _cat(
        "medical_detail",
        "Medical detail",
        ("medical", "health record"),
        _HIGH,
        "restrict_and_route_to_review",
        "possible medical detail; restrict and review",
    ),
    _cat(
        "personnel_or_hr",
        "Personnel / HR",
        ("payroll", "ssn", "w-2", "w2 ", "1099", "offer letter", "personnel"),
        _HIGH,
        "restrict_and_route_to_hr_review",
        "possible personnel/HR detail; restrict and review",
    ),
    _cat(
        "liquidated_damages",
        "Liquidated damages",
        ("liquidated damages",),
        _HIGH,
        "escalate_to_review",
        "possible liquidated-damages language; review before acting",
    ),
    _cat(
        "contracts",
        "Contracts",
        ("contract", "agreement", "subcontract"),
        _MEDIUM,
        "route_to_review",
        "possible contract-related content; review required",
    ),
    _cat(
        "change_orders",
        "Change orders",
        ("change order", "changeorder"),
        _MEDIUM,
        "route_to_review",
        "possible change-order content; review required",
    ),
    _cat(
        "notices",
        "Notices",
        ("notice",),
        _MEDIUM,
        "route_to_review",
        "possible formal notice; review required",
    ),
    _cat(
        "insurance_or_bonding",
        "Insurance / bonding",
        ("insurance", "certificate of insurance", "coi", "bond"),
        _MEDIUM,
        "route_to_review",
        "possible insurance/bonding content; review required",
    ),
    _cat(
        "pay_applications",
        "Pay applications",
        ("pay app", "payapp", "payment application", "g702", "g703"),
        _MEDIUM,
        "route_to_financial_review",
        "possible pay-application content; route to financial review",
    ),
    _cat(
        "invoices",
        "Invoices",
        ("invoice",),
        _MEDIUM,
        "route_to_financial_review",
        "possible invoice content; route to financial review",
    ),
    _cat(
        "lien_releases",
        "Lien releases",
        ("lien", "lien release", "lien waiver"),
        _MEDIUM,
        "route_to_financial_review",
        "possible lien/release content; review required",
    ),
    _cat(
        "delay_or_time_extension_language",
        "Delay / time extension",
        ("delay", "time extension"),
        _MEDIUM,
        "route_to_review",
        "possible delay/time-extension language; review required",
    ),
    _cat(
        "additional_compensation_language",
        "Additional compensation",
        ("additional compensation", "extra work"),
        _MEDIUM,
        "route_to_review",
        "possible additional-compensation language; review required",
    ),
    # --- 4 Prompt 10 additions --------------------------------------------------
    _cat(
        "confidential_bid_or_estimate",
        "Confidential bid / estimate",
        ("confidential bid", "bid tab", "estimate", "estimating", "proposal pricing"),
        _HIGH,
        "restrict_and_route_to_review",
        "possible confidential bid/estimate content; restrict and review",
    ),
    _cat(
        "owner_directive",
        "Owner directive",
        ("owner directive", "owner direction", "construction directive", "owner instruction"),
        _MEDIUM,
        "route_to_review",
        "possible owner directive; review before acting",
    ),
    _cat(
        "subcontractor_default",
        "Subcontractor default",
        ("subcontractor default", "default of subcontractor", "sub default", "failure to perform"),
        _HIGH,
        "escalate_to_review",
        "possible subcontractor-default language; not a determination, review required",
    ),
    _cat(
        "schedule_recovery_or_acceleration",
        "Schedule recovery / acceleration",
        ("recovery schedule", "schedule recovery", "acceleration", "accelerate the work"),
        _MEDIUM,
        "route_to_review",
        "possible schedule-recovery/acceleration language; review required",
    ),
)

# Convenience lookup by id.
REVIEW_CATEGORIES_BY_ID: dict[str, ReviewCategory] = {c.id: c for c in REVIEW_CATEGORIES}


def get_review_category(category_id: str) -> Optional[ReviewCategory]:
    """Return the :class:`ReviewCategory` for ``category_id`` (or None)."""
    return REVIEW_CATEGORIES_BY_ID.get(category_id)


def classify_review_categories(text: Optional[str]) -> list[str]:
    """Return every review-category id whose trigger terms appear in ``text``.

    Substring match against the lowercased text (same style as
    ``attachment_analyzer``). Returns ids in registry order. Used on bounded,
    in-memory redacted previews only — no text is stored.
    """
    if not text:
        return []
    low = text.lower()
    hits: list[str] = []
    for category in REVIEW_CATEGORIES:
        if any(term in low for term in category.trigger_terms):
            hits.append(category.id)
    return hits
