"""Phase 08A Operator Preference Agent (A08) — Synthesized Prompt 10.

Captures operator preferences as reviewable, presentation-only memory-like records and
records operator feedback. Preferences are never auto-accepted (start pending_review),
sensitive preferences route to Tier 3, and — critically — accepted preferences can never
override safety policy / review-tier routing / guardrails (enforced by
`apply_operator_preferences`). Metadata-only; no raw content.
"""

from __future__ import annotations

import uuid
from typing import Any

from .models import OperatorFeedback, OperatorPreference
from .policy import apply_operator_preferences, classify_preference
from .store import upsert_operator_preference, write_operator_feedback


def capture_preference(
    *,
    scope: str,
    preference_key: str,
    preference_value_redacted: str | None = None,
    preference_type: str | None = None,
    confidence_class: str = "medium",
    scope_key: str | None = None,
    source_feedback_refs: list[dict[str, str]] | None = None,
    sensitive: bool = False,
    db_path: str | None = None,
    emit: bool = False,
) -> OperatorPreference:
    """Capture a reviewable operator preference (never auto-accepted; sensitive -> Tier 3)."""
    tier, reason, review_status = classify_preference(
        preference_type=preference_type or preference_key, sensitive=sensitive
    )
    pref = OperatorPreference(
        preference_id=uuid.uuid4().hex,
        scope=scope,  # type: ignore[arg-type]
        scope_key=scope_key,
        preference_key=preference_key,
        preference_value_redacted=preference_value_redacted,
        confidence_class=confidence_class,
        signal_count=1,
        source_feedback_refs=source_feedback_refs or [],
        review_status=review_status,
        review_tier=tier,
        review_tier_reason_code=reason,
    )
    if emit:
        upsert_operator_preference(pref, db_path=db_path)
    return pref


def record_operator_feedback(
    *,
    target_kind: str,
    target_id: str,
    feedback_class: str = "accept",
    origin_id: str | None = None,
    rating: int | None = None,
    reason_redacted: str | None = None,
    db_path: str | None = None,
    emit: bool = False,
) -> OperatorFeedback:
    """Record auditable operator feedback (metadata only)."""
    feedback = OperatorFeedback(
        feedback_id=uuid.uuid4().hex,
        target_kind=target_kind,
        target_id=target_id,
        origin_id=origin_id,
        feedback_class=feedback_class,  # type: ignore[arg-type]
        rating=rating,
        reason_redacted=reason_redacted,
    )
    if emit:
        write_operator_feedback(feedback, db_path=db_path)
    return feedback


def build_operator_preference_proof() -> dict[str, Any]:
    """Deterministic proof for ``operator-preference-proof.json`` (temp DB)."""
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/pref.sqlite3"
        ConstructionStore(db)

        low_risk = capture_preference(
            scope="global",
            preference_key="detail_level",
            preference_value_redacted="concise",
            preference_type="detail_level",
            db_path=db,
            emit=True,
        )
        sensitive = capture_preference(
            scope="project",
            scope_key="P1",
            preference_key="personnel_emphasis",
            preference_value_redacted="[redacted]",
            preference_type="personnel",
            db_path=db,
            emit=True,
        )

        # Accepted preferences can NEVER override safety / review-tier routing.
        candidate_prefs = [
            {
                "preference_key": "detail_level",
                "preference_value_redacted": "concise",
                "review_status": "accepted",
            },
            {
                "preference_key": "review_tier_override",
                "preference_value_redacted": "tier_1",
                "review_status": "accepted",
            },
            {
                "preference_key": "suppress_warnings",
                "preference_value_redacted": "true",
                "review_status": "accepted",
            },
            {
                "preference_key": "terminology",
                "preference_value_redacted": "RFI",
                "review_status": "pending_review",
            },
        ]
        applied, dropped = apply_operator_preferences(candidate_prefs)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM second_brain_operator_preference_profiles"
            ).fetchall()
        ]
        conn.close()

    guard_cols = [c for c in (rows[0] if rows else {}) if c.endswith("_persisted")]
    guards_zero = all(all(r[c] == 0 for c in guard_cols) for r in rows)
    blob = low_risk.model_dump_json() + sensitive.model_dump_json()
    no_raw = not any(
        t in blob
        for t in ("raw_body", "raw_prompt", "raw_response", "signed_url", "download_url", "secret")
    )

    safety_not_overridable = (
        applied == {"detail_level": "concise"}
        and any("review_tier_override" in d for d in dropped)
        and any("suppress_warnings" in d for d in dropped)
        and any("terminology" in d for d in dropped)  # not accepted -> dropped
    )

    proof_passed = bool(
        low_risk.review_tier == 2
        and low_risk.review_status == "pending_review"
        and sensitive.review_tier == 3
        and sensitive.review_tier_reason_code == "T3_SENSITIVE_HIGH_IMPACT"
        and sensitive.review_status == "pending_review"
        and safety_not_overridable
        and len(rows) == 2
        and guards_zero
        and no_raw
    )
    return {
        "proof": "phase_08a_operator_preference",
        "proof_passed": proof_passed,
        "low_risk_preference": {
            "review_tier": low_risk.review_tier,
            "review_status": low_risk.review_status,
        },
        "sensitive_preference_routed_tier_3": {
            "review_tier": sensitive.review_tier,
            "reason": sensitive.review_tier_reason_code,
            "review_status": sensitive.review_status,
        },
        "accepted_preferences_cannot_override_safety": {
            "applied": applied,
            "dropped": dropped,
            "enforced": safety_not_overridable,
        },
        "preference_rows": len(rows),
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "preferences_never_override_safety": True,
            "sensitive_preferences_default_tier_3": True,
            "preferences_never_auto_accepted": True,
        },
    }
