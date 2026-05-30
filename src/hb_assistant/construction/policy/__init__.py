"""Construction-agent review-queue policy (deterministic, rules-driven).

Controller policy (``resources/config/review_required_rules.seed.yaml``) is the
authority. No model decisioning is permitted for contract / financial / legal /
incident / injury / personnel material — every routing decision traces back to
a ``rule_id`` in the YAML rule file.

Phase 02 additions: :class:`InventoryFirstPolicy` exposes the per-source
operational policy for OneDrive sources running in inventory-first mode.
"""

from .email_active import (
    EmailIntelligenceActivePolicy,
    EmailIntelligenceActivePolicyError,
    load_email_intelligence_active_policy,
)
from .email_deferred import (
    EmailIntelligenceDeferredPolicy,
    EmailIntelligenceDeferredPolicyError,
    load_email_intelligence_deferred_policy,
)
from .evaluator import ReviewPolicyEvaluator
from .inventory_first import (
    ONEDRIVE_INVENTORY_FIRST_SCOPES,
    InventoryFirstPolicy,
    InventoryFirstViolation,
    applies_to,
    assert_no_bulk_document_cards,
    assert_no_full_text_extraction,
    build_policy,
)
from .loader import ReviewRulesError, load_review_rules
from .mailbox_registry import (
    MailboxFolderSource,
    MailboxSourceRegistry,
    build_mailbox_source_registry,
)
from .models import ReviewRule, ReviewRules, RuleKind, RuleMatch, Sensitivity
from .router import ReviewQueueRouter, RouterResult

__all__ = [
    "ReviewPolicyEvaluator",
    "ReviewQueueRouter",
    "ReviewRule",
    "ReviewRules",
    "ReviewRulesError",
    "RouterResult",
    "RuleKind",
    "RuleMatch",
    "Sensitivity",
    "load_review_rules",
    # Phase 02 inventory-first policy
    "InventoryFirstPolicy",
    "InventoryFirstViolation",
    "ONEDRIVE_INVENTORY_FIRST_SCOPES",
    "applies_to",
    "assert_no_bulk_document_cards",
    "assert_no_full_text_extraction",
    "build_policy",
    # Phase 02 email-intelligence deferred policy
    "EmailIntelligenceDeferredPolicy",
    "EmailIntelligenceDeferredPolicyError",
    "load_email_intelligence_deferred_policy",
    # Phase 06 active email-intelligence policy + mailbox source registry
    "EmailIntelligenceActivePolicy",
    "EmailIntelligenceActivePolicyError",
    "load_email_intelligence_active_policy",
    "MailboxFolderSource",
    "MailboxSourceRegistry",
    "build_mailbox_source_registry",
]
