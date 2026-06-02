"""Phase 08A Daily Brief Agent (daily_brief_agent) — Synthesized Prompt 12.

Generate -> evaluate -> (gated) apply -> hand off. Assembles the brief context (Prompt 11),
generates mock-first through the Claude adapter's research-packet gate (the adapter result
drives evaluation + an in-memory model-call receipt only — never written), runs the Output
Evaluation Agent (A05), and blocks apply unless evaluation passes and the context is not
blocked. On apply it writes approved local Obsidian output; it always emits a local-only,
source-linked Phase 08B delivery-handoff payload (with an eligibility flag, a data-only
notification summary, and HTML render-data). No macOS notification, no HTML, no external
delivery, no raw content.
"""

from __future__ import annotations

from typing import Any

from ..config import SecondBrainConfig, load_second_brain_config
from ..reasoning import ClaudeAdapter, MockClaudeAdapter, build_claude_adapter
from ..synthesis import build_evaluation_preview, write_evaluation_run
from .context import _assemble_daily_brief
from .models import (
    DailyBriefContext,
    DailyBriefResult,
    DeliveryHandoffPayload,
    HtmlRenderingData,
    NotificationSummary,
)
from .output import render_brief_markdown, write_brief_output
from .store import write_daily_brief_handoff_lines, write_daily_brief_run


def _build_handoff(
    context: DailyBriefContext,
    *,
    brief_run_id: str | None,
    evaluation_run_id: str | None,
    eligible: bool,
) -> DeliveryHandoffPayload:
    """Assemble the local-only, source-linked Phase 08B delivery-handoff payload."""
    sections = context.delivery_handoff.sections
    title = f"Daily Brief {context.brief_date}"
    notification = NotificationSummary(
        title_redacted=title,
        attention_count=len(context.attention_cards),
        review_required_count=len(context.review_required_cards),
        warning_count=len(context.warning_cards),
        project_count=context.project_count,
        eligible=eligible,
    )
    html = HtmlRenderingData(
        title_redacted=title,
        sections=sections,
        source_refs=context.source_refs,
    )
    return DeliveryHandoffPayload(
        brief_run_id=brief_run_id,
        brief_date=context.brief_date,
        evaluation_run_id=evaluation_run_id,
        eligible_for_delivery=eligible,
        review_tier=context.review_tier,
        degradation_mode=context.degradation_mode,
        sections=sections,
        source_refs=context.source_refs,
        notification_summary=notification,
        html_rendering=html,
    )


def run_daily_brief(
    *,
    brief_date: str,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
    db_path: str | None = None,
    mode: str = "dry_run",
    config: SecondBrainConfig | None = None,
    adapter: ClaudeAdapter | None = None,
    emit_receipt: bool = False,
    vault_brief_dir: str | None = None,
) -> DailyBriefResult:
    """Generate, evaluate, gate-apply, and hand off the daily brief.

    Apply (``mode="apply"``) is blocked unless evaluation passes and the context is not
    blocked; the approved Obsidian output is written only when apply is allowed. The brief
    run + evaluation run are persisted (metadata only) when ``emit_receipt`` is True.
    """
    context, packet, assessment, envelope, _packet_receipt_id = _assemble_daily_brief(
        brief_date=brief_date,
        project_key=project_key,
        families=families,
        db_path=db_path,
        emit_receipt=emit_receipt,
    )

    # Generate (mock-first; requires research packet). The adapter result drives evaluation
    # only — it is never written to disk/DB (live-mode raw-response safety).
    research_packet_ok = packet.degradation_mode != "blocked"
    ctx_env = envelope.to_context_envelope(
        question=f"daily brief {brief_date}", research_packet_ok=research_packet_ok
    )
    resolved_adapter = (
        adapter or build_claude_adapter(config or load_second_brain_config()) or MockClaudeAdapter()
    )
    adapter_result = resolved_adapter.synthesize(ctx_env)

    # Output Evaluation Agent (A05).
    evaluation = build_evaluation_preview(
        adapter_result=adapter_result, packet=packet, assessment=assessment, envelope=ctx_env
    )
    evaluation_run_id: str | None = None
    if emit_receipt:
        evaluation_run_id = write_evaluation_run(
            evaluation=evaluation,
            target_kind="daily_brief",
            target_id=packet.packet_id,
            research_packet_id=context.research_packet_id,
            confidence_class=adapter_result.confidence,
            review_tier_reason_code=adapter_result.review_reason_code,
            degradation_mode=adapter_result.degradation_mode,
            mode=adapter_result.mode if mode == "apply" else "dry_run",
            db_path=db_path,
        )

    # Apply gate: evaluation must pass and context must not be blocked.
    apply_requested = mode == "apply"
    apply_blocked_reason: str | None = None
    if apply_requested and not evaluation.passed:
        apply_blocked_reason = "evaluation_failed"
    elif apply_requested and context.status == "blocked":
        apply_blocked_reason = "context_blocked"
    apply_allowed = apply_requested and apply_blocked_reason is None

    # Render (from cards, never the adapter answer) + write approved output (apply only).
    content = render_brief_markdown(context)
    written = write_brief_output(
        brief_date=brief_date,
        content=content,
        vault_brief_dir=vault_brief_dir,
        apply=apply_allowed,
    )

    eligible = evaluation.passed and context.status != "blocked"

    brief_run_id: str | None = None
    if emit_receipt:
        brief_run_id = write_daily_brief_run(
            context,
            mode="apply" if apply_allowed else "dry_run",
            db_path=db_path,
            evaluation_run_id=evaluation_run_id,
            output_path_redacted=written.output_path_redacted,
            output_path_hash=written.output_path_hash,
        )
        context.brief_run_id = brief_run_id
        # Durably persist the structured handoff lines (V27) so the full safe handoff can be
        # reconstructed after process exit (Phase 08B recovery). Metadata-only; guard cols 0.
        write_daily_brief_handoff_lines(
            context.delivery_handoff.sections,
            brief_run_id=brief_run_id,
            db_path=db_path,
        )

    handoff = _build_handoff(
        context,
        brief_run_id=brief_run_id,
        evaluation_run_id=evaluation_run_id,
        eligible=eligible,
    )

    warnings = list(context.warnings)
    if apply_blocked_reason:
        warnings.append(f"apply_blocked:{apply_blocked_reason}")

    return DailyBriefResult(
        brief_date=brief_date,
        brief_run_id=brief_run_id,
        mode=mode,
        status=context.status,
        applied=apply_allowed and written.written,
        apply_blocked_reason=apply_blocked_reason,
        evaluation=evaluation.model_dump(),
        evaluation_run_id=evaluation_run_id,
        eligible_for_delivery=eligible,
        output_written=written.written,
        output_path_redacted=written.output_path_redacted,
        output_path_hash=written.output_path_hash,
        delivery_handoff=handoff,
        source_ref_count=context.source_ref_count,
        source_coverage=context.source_coverage,
        review_tier_counts=context.review_tier_counts,
        review_tier=context.review_tier,
        degradation_mode=context.degradation_mode,
        warnings=sorted(set(warnings)),
    )


def _render_dry_run_for(db_path: str, *, brief_date: str, vault_brief_dir: str) -> str:
    """Return the would-be brief markdown for a seeded DB (used by evidence/proofs)."""
    context, _p, _a, _e, _pid = _assemble_daily_brief(
        brief_date=brief_date, project_key="P1", db_path=db_path, emit_receipt=False
    )
    return render_brief_markdown(context)


def build_daily_brief_agent_proof() -> dict[str, Any]:
    """Deterministic proof for ``daily-brief-agent-proof.md`` (temp DB + temp vault)."""
    import json
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        vault = f"{tmp}/vault_briefs"
        store = ConstructionStore(seeded)
        store.upsert_cross_source_relationship(
            relationship_id="rel-1",
            source_family="email",
            source_record_type="message",
            source_record_ref="m1",
            target_family="procore",
            target_record_type="rfi",
            target_record_ref="rfi1",
            relationship_type="references",
            confidence_class="human_promoted",
            source_reference_json=json.dumps({"project_key": "P1"}),
            project_key="P1",
            promotion_status="promoted",
            promoted_by="human",
            review_required=False,
        )
        store.upsert_project_issue_history_item(
            issue_family_id="iss-1",
            project_key="P1",
            status="open",
            source_families_json=json.dumps(["procore"]),
            confidence_class="medium",
            issue_kind="rfi",
            age_days=30,
            review_required=False,
            stale_unknown_flags_json=json.dumps(["stale_status"]),
        )

        applied = run_daily_brief(
            brief_date="2026-06-02",
            project_key="P1",
            db_path=seeded,
            mode="apply",
            adapter=MockClaudeAdapter(),
            emit_receipt=True,
            vault_brief_dir=vault,
        )

        empty = f"{tmp}/empty.sqlite3"
        empty_vault = f"{tmp}/empty_vault"
        ConstructionStore(empty)
        blocked = run_daily_brief(
            brief_date="2026-06-02",
            project_key="P1",
            db_path=empty,
            mode="apply",
            adapter=MockClaudeAdapter(),
            emit_receipt=True,
            vault_brief_dir=empty_vault,
        )

        from pathlib import Path as _Path

        applied_file_exists = bool(list(_Path(vault).glob("*_daily_brief.md")))
        blocked_file_exists = _Path(empty_vault).exists() and bool(
            list(_Path(empty_vault).glob("*_daily_brief.md"))
        )

        c = sqlite3.connect(seeded)
        c.row_factory = sqlite3.Row
        run_row = dict(c.execute("SELECT * FROM daily_brief_runs").fetchone())
        eval_count = c.execute("SELECT COUNT(*) FROM second_brain_evaluation_runs").fetchone()[0]
        c.close()

    blob = applied.model_dump_json() + blocked.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
        )
    )
    guards_zero = all(
        run_row[col] == 0
        for col in run_row
        if col.endswith("_persisted") or col == "external_writeback_performed"
    )
    handoff_local_only = (
        applied.delivery_handoff.local_only is True
        and applied.delivery_handoff.external_delivery_performed is False
        and applied.delivery_handoff.notification_summary.emitted is False
        and applied.delivery_handoff.html_rendering.rendered is False
    )
    handoff_source_linked = bool(applied.delivery_handoff.source_refs)

    proof_passed = bool(
        applied.applied is True
        and applied.output_written is True
        and applied_file_exists
        and applied.eligible_for_delivery is True
        and applied.evaluation_run_id
        and run_row["evaluation_run_id"] == applied.evaluation_run_id
        and run_row["output_path_redacted"]
        and run_row["mode"] == "apply"
        and blocked.applied is False
        and blocked.output_written is False
        and blocked.apply_blocked_reason == "evaluation_failed"
        and not blocked_file_exists
        and handoff_local_only
        and handoff_source_linked
        and guards_zero
        and no_raw_content
        and eval_count == 1
    )
    return {
        "proof": "phase_08a_daily_brief_agent",
        "proof_passed": proof_passed,
        "applied_run": {
            "applied": applied.applied,
            "output_written": applied.output_written,
            "output_path_redacted": applied.output_path_redacted,
            "evaluation_passed": applied.evaluation["passed"],
            "evaluation_run_id": applied.evaluation_run_id,
            "eligible_for_delivery": applied.eligible_for_delivery,
            "brief_run_id": applied.brief_run_id,
        },
        "apply_blocked_run": {
            "applied": blocked.applied,
            "apply_blocked_reason": blocked.apply_blocked_reason,
            "evaluation_passed": blocked.evaluation["passed"],
            "output_written": blocked.output_written,
            "eligible_for_delivery": blocked.eligible_for_delivery,
        },
        "approved_output_written_on_apply": applied_file_exists,
        "no_output_when_apply_blocked": not blocked_file_exists,
        "delivery_handoff_local_only": handoff_local_only,
        "delivery_handoff_source_linked": handoff_source_linked,
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "mock_first": True,
            "research_packet_required": True,
            "evaluation_required_before_apply": True,
            "apply_blocked_when_evaluation_fails": True,
            "no_external_delivery": True,
            "no_html_or_notifications": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }


def build_daily_brief_delivery_handoff_proof() -> dict[str, Any]:
    """Deterministic proof for ``daily-brief-delivery-handoff-proof.json`` (temp DB)."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        store = ConstructionStore(seeded)
        store.upsert_cross_source_relationship(
            relationship_id="rel-1",
            source_family="email",
            source_record_type="message",
            source_record_ref="m1",
            target_family="procore",
            target_record_type="rfi",
            target_record_ref="rfi1",
            relationship_type="references",
            confidence_class="human_promoted",
            source_reference_json=json.dumps({"project_key": "P1"}),
            project_key="P1",
            promotion_status="promoted",
            promoted_by="human",
            review_required=False,
        )
        result = run_daily_brief(
            brief_date="2026-06-02",
            project_key="P1",
            db_path=seeded,
            mode="dry_run",
            adapter=MockClaudeAdapter(),
            emit_receipt=False,
        )

    handoff = result.delivery_handoff
    blob = handoff.model_dump_json()
    no_raw_content = not any(
        t in blob
        for t in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
        )
    )
    source_linked = bool(handoff.source_refs) and all(
        {"source_family", "source_ref"} <= set(ref) for ref in handoff.source_refs
    )

    proof_passed = bool(
        handoff.phase == "08B"
        and handoff.local_only is True
        and handoff.external_delivery_performed is False
        and handoff.notification_summary.emitted is False
        and handoff.notification_summary.channel == "local_only"
        and handoff.html_rendering.rendered is False
        and handoff.html_rendering.format == "render_data"
        and source_linked
        and no_raw_content
    )
    return {
        "proof": "phase_08a_daily_brief_delivery_handoff",
        "proof_passed": proof_passed,
        "phase": handoff.phase,
        "eligible_for_delivery": handoff.eligible_for_delivery,
        "local_only": handoff.local_only,
        "external_delivery_performed": handoff.external_delivery_performed,
        "notification_summary": {
            "channel": handoff.notification_summary.channel,
            "emitted": handoff.notification_summary.emitted,
            "review_required_count": handoff.notification_summary.review_required_count,
        },
        "html_rendering": {
            "format": handoff.html_rendering.format,
            "rendered": handoff.html_rendering.rendered,
        },
        "section_counts": {k: len(v) for k, v in handoff.sections.items()},
        "source_ref_count": len(handoff.source_refs),
        "handoff_source_linked": source_linked,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "handoff_local_only": True,
            "handoff_source_linked": True,
            "no_external_delivery": True,
            "no_macos_notification": True,
            "no_html_rendering": True,
            "no_raw_content": True,
        },
    }
