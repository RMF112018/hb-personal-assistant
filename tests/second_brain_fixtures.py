"""Deterministic second-brain family fixtures (not a test module).

The connector re-test could only validate the *list* tools of many assistant families because
their exact-ID getters and child-resource readers had no seeded data. This module centralises
one deterministic record per family so getter/child-resource tests are possible, consolidating
the per-file ``_seed_*`` blueprints scattered across ``tests/test_fastapi_analytics_*.py``.

Self-contained families (no upstream chain) are implemented here. Chain-dependent families
(context_pack -> memory/review/intelligence -> research_packet -> answer_draft; action_stage)
plug into the same module via the builder entry points named in each ``seed_*`` docstring — add
them incrementally as coverage is extended.
"""

from __future__ import annotations

from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.quality_evaluator import QualityProviders, build_quality
from hb_assistant.obsidian_mcp.quality_repository import QualityRepository


def seed_feedback(db: str, *, feedback_type: str = "wrong_source") -> str:
    """Seed one feedback record (+targets) via feedback_service.capture_feedback. Returns feedback_id."""
    out = fs.capture_feedback(
        FeedbackRepository(db),
        feedback_type=feedback_type,
        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
        note="deterministic fixture", created_by="fixtures", apply=True,
    )
    return out["feedback"]["feedback_id"]


def seed_quality(db: str) -> str:
    """Seed one quality run over a seeded feedback record via build_quality. Returns quality_run_id."""
    seed_feedback(db, feedback_type="needs_review")
    res = build_quality(
        QualityProviders(feedback_repo=FeedbackRepository(db)),
        QualityRepository(db),
        target_kind="feedback", target_id="OL1", apply=True,
    )
    return res["quality_run_id"]


def seed_self_contained_families(db: str) -> dict[str, str]:
    """Seed every currently-supported self-contained family. Returns {family: primary_id}."""
    return {"feedback": seed_feedback(db), "quality": seed_quality(db)}
