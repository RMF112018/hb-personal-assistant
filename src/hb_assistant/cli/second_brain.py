"""``hb-assistant second-brain`` CLI group (Phase 08A).

Prompt 03 ships a single offline-safe command:

- ``hb-assistant second-brain status [--json] [--no-emit-receipt]`` — report the
  resolved second-brain runtime posture (mode, config status, dependency
  availability, schema/contract versions, guardrails) and write a metadata-only
  config receipt to the V26 ``second_brain_runtime_config_receipts`` table.

Runs with no network access. Never emits the Anthropic API key value (presence
only). Remaining ``second-brain`` subcommands (query/chat/brief/index/memory/
launchd) arrive in later 08A prompts.
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(
    name="second-brain",
    help="Local-first second-brain runtime (Phase 08A).",
    no_args_is_help=True,
)

agents_app = typer.Typer(
    name="agents",
    help="Phase 08A internal service-agent registry (read-only).",
    no_args_is_help=True,
)
app.add_typer(agents_app, name="agents")

index_app = typer.Typer(
    name="index",
    help="Approved Obsidian indexing (read-only over the vault).",
    no_args_is_help=True,
)
app.add_typer(index_app, name="index")

query_tools_app = typer.Typer(
    name="query-tools",
    help="Allowlisted read-only SQLite query tools (no arbitrary SQL).",
    no_args_is_help=True,
)
app.add_typer(query_tools_app, name="query-tools")

research_packet_app = typer.Typer(
    name="research-packet",
    help="Pre-synthesis research packet + context-quality gate (read-only).",
    no_args_is_help=True,
)
app.add_typer(research_packet_app, name="research-packet")

memory_app = typer.Typer(
    name="memory",
    help="Long-term memory candidates + review (source-linked, review-controlled).",
    no_args_is_help=True,
)
app.add_typer(memory_app, name="memory")

preference_app = typer.Typer(
    name="preference",
    help="Reviewable operator preferences (presentation-only; never override safety).",
    no_args_is_help=True,
)
app.add_typer(preference_app, name="preference")

daily_brief_app = typer.Typer(
    name="daily-brief",
    help="Daily-brief context builder + review triage (read-only; no HTML/notifications).",
    no_args_is_help=True,
)
app.add_typer(daily_brief_app, name="daily-brief")

data_quality_app = typer.Typer(
    name="data-quality",
    help="Phase 08A second-brain data-quality gates (read-only; no readiness overstatement).",
    no_args_is_help=True,
)
app.add_typer(data_quality_app, name="data-quality")

automation_app = typer.Typer(
    name="automation",
    help="Phase 08B automation health + observability (read-only status surface).",
    no_args_is_help=True,
)
app.add_typer(automation_app, name="automation")

_GUARDRAILS = {
    "local_first": True,
    "model_direct_external_api_access": False,
    "external_writeback": False,
    "raw_content_persisted": False,
    "api_key_value_persisted_or_logged": False,
    "network_required_for_status": False,
}


@app.command("status")
def status(
    json_out: bool = typer.Option(True, "--json"),
    emit_receipt: bool = typer.Option(
        True,
        "--emit-receipt/--no-emit-receipt",
        help="Write a metadata-only config receipt to the local V26 table.",
    ),
) -> None:
    """Report second-brain runtime config posture (offline-safe)."""
    from hb_assistant.construction.second_brain.config import load_second_brain_config
    from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
    from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

    config = load_second_brain_config()
    runtime_contract = load_phase_08a_contract("second_brain_runtime_contract")

    try:
        schema_version = SQLiteMigrator().current_version()
    except Exception:  # pragma: no cover - defensive: status must not crash
        schema_version = 0

    config_receipt_id: str | None = None
    config_receipt_error: str | None = None
    if emit_receipt:
        try:
            from hb_assistant.construction.second_brain.store import write_config_receipt

            config_receipt_id = write_config_receipt(config=config)
            schema_version = SQLiteMigrator().current_version()
        except Exception as exc:  # pragma: no cover - defensive
            config_receipt_error = type(exc).__name__

    payload = {
        "command": "second-brain status",
        "runtime": {
            "mode": config.mode,
            "offline": config.mode == "disabled",
            "enabled": config.enabled,
            "synthesis_enabled": config.synthesis_enabled,
            "config_status": config.config_status,
            "claude_model": config.claude_model,
            "max_input_chars": config.max_input_chars,
            "max_output_tokens": config.max_output_tokens,
            "notes": config.notes,
        },
        "dependencies": config.dependency_status(),
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "runtime_contract_version": runtime_contract.get("version", "unknown"),
        "config_receipt_id": config_receipt_id,
        "config_receipt_error": config_receipt_error,
        "guardrails": _GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_AGENT_GUARDRAILS = {
    "local_first": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "source_refs_required": True,
    "review_tiers_required": True,
    "model_direct_external_api_access": False,
    "mcp_implemented": False,
}


@agents_app.command("registry")
def agents_registry(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List the registered Phase 08A internal service agents (read-only)."""
    from hb_assistant.construction.second_brain.agents import load_agent_registry

    registry = load_agent_registry()
    agents = [
        {
            "agent_id": a.agent_id,
            "phase_owner": a.phase_owner,
            "enabled": a.enabled,
            "purpose": a.purpose,
            "allowed_tool_groups": a.allowed_tool_groups,
            "denied_tool_groups": a.denied_tool_groups,
            "default_model_profile": a.default_model_profile,
            "review_policy": a.review_policy,
            "output_contract": a.output_contract,
            "receipt_required": a.receipt_required,
        }
        for a in registry.agents
    ]
    payload = {
        "command": "second-brain agents registry",
        "registry_version": registry.version,
        "count": len(agents),
        "agents": agents,
        "guardrails": _AGENT_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@agents_app.command("status")
def agents_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report agent registry status + policy validity (offline, fail-closed)."""
    from hb_assistant.construction.second_brain.agents import (
        build_agent_registry_proof,
        build_agent_tool_policy_proof,
    )
    from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
    from hb_assistant.store.migrator import SQLiteMigrator

    registry_proof = build_agent_registry_proof()
    tool_proof = build_agent_tool_policy_proof()

    try:
        schema_version = SQLiteMigrator().current_version()
    except Exception:  # pragma: no cover - defensive: status must not crash
        schema_version = 0

    registry_valid = bool(registry_proof["proof_passed"])
    tool_policy_valid = bool(tool_proof["proof_passed"])
    violations_count = len(registry_proof["violations"]) + len(tool_proof["violations"])

    payload = {
        "command": "second-brain agents status",
        "agent_count": registry_proof["agent_count"],
        "enabled_count": registry_proof["enabled_count"],
        "registry_valid": registry_valid,
        "tool_policy_valid": tool_policy_valid,
        "violations_count": violations_count,
        "required_agents_present": registry_proof["required_agents_present"],
        "tier3_handling_visible": registry_proof["tier3_handling_visible"],
        "contracts": {
            "agent_registry_contract": registry_proof["contract_version"],
            "agent_tool_contract": tool_proof["contract_version"],
            "model_profile_contract": load_phase_08a_contract("model_profile_contract").get(
                "version", "unknown"
            ),
        },
        "schema_version": schema_version,
        "guardrails": _AGENT_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if registry_valid and tool_policy_valid else 3)


_QUERY_TOOL_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_arbitrary_sql": True,
    "no_model_generated_sql": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "source_refs_required": True,
    "review_tier_required": True,
}


@query_tools_app.command("list")
def query_tools_list(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List the allowlisted query tools + their backing read-model availability."""
    from hb_assistant.construction.second_brain.query_tools import (
        list_query_tools,
        validate_query_tool_policy,
    )

    policy = validate_query_tool_policy()
    tools = list_query_tools()
    payload = {
        "command": "second-brain query-tools list",
        "contract_version": policy["contract_version"],
        "seed_version": policy["seed_version"],
        "policy_valid": policy["valid"],
        "count": len(tools),
        "backed_count": sum(1 for t in tools if t["backed"]),
        "tools": tools,
        "guardrails": _QUERY_TOOL_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if policy["valid"] else 3)


@query_tools_app.command("run")
def query_tools_run(
    tool: str = typer.Argument(..., help="Allowlisted query-tool name."),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Write a metadata-only query-tool receipt to the local V26 table.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Run one allowlisted query tool (read-only). Unknown tool names are rejected."""
    from hb_assistant.construction.second_brain.query_tools import (
        QueryToolError,
        run_query_tool,
    )

    try:
        result = run_query_tool(tool, project_key=project_key, emit_receipt=emit_receipt)
    except QueryToolError as exc:
        err_payload: dict[str, object] = {
            "command": "second-brain query-tools run",
            "tool": tool,
            "error": "tool_not_allowlisted",
            "detail": str(exc),
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain query-tools run",
        "tool": result.tool_name,
        "project_key": result.project_key,
        "status": result.status,
        "row_count": result.row_count,
        "char_count": result.char_count,
        "truncated": result.truncated,
        "review_tier_summary": result.review_tier_summary,
        "warnings": result.warnings,
        "source_refs": result.source_refs[:200],
        "guardrails": _QUERY_TOOL_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_RESEARCH_PACKET_GUARDRAILS = {
    "local_first": True,
    "synthesis_requires_packet": True,
    "insufficient_context_degrades_not_overstates": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "source_references_required": True,
    "model_direct_external_api_access": False,
}


@research_packet_app.command("build")
def research_packet_build(
    packet_type: str = typer.Option(
        "interactive_query",
        "--packet-type",
        help="Packet type (e.g. interactive_query, daily_brief).",
    ),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Write a metadata-only research-packet receipt to the local V26 table.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Assess context quality and build a pre-synthesis research packet (read-only)."""
    from hb_assistant.construction.second_brain.research import (
        PACKET_TYPES,
        RetrievalOrchestrator,
    )

    if packet_type not in PACKET_TYPES:
        err_payload: dict[str, object] = {
            "command": "second-brain research-packet build",
            "error": "invalid_packet_type",
            "detail": f"{packet_type!r} not in {list(PACKET_TYPES)}",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    try:
        result = RetrievalOrchestrator().orchestrate(
            packet_type=packet_type, project_key=project_key, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {
            "command": "second-brain research-packet build",
            "packet_type": packet_type,
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    packet = result.packet
    a = result.assessment
    payload = {
        "command": "second-brain research-packet build",
        "packet_type": result.packet_type,
        "project_key": project_key,
        "request_requires_packet": result.request_requires_packet,
        "research_packet_ok": result.research_packet_ok,
        "synthesis_allowed": result.synthesis_allowed,
        "packet": {
            "packet_id": packet.packet_id,
            "topic_hash": packet.topic_hash,
            "source_ref_count": packet.source_ref_count,
            "review_required_count": packet.review_required_count,
            "stale_unknown_count": packet.stale_unknown_count,
            "conflict_count": packet.conflict_count,
            "context_quality_class": packet.context_quality_class,
            "degradation_mode": packet.degradation_mode,
            "confidence_class": packet.confidence_class,
            "review_tier": packet.review_tier,
            "status": packet.status,
        },
        "assessment": {
            "families_present": a.families_present,
            "families_missing": a.families_missing,
            "source_coverage": a.source_coverage,
            "review_tier_distribution": a.review_tier_distribution,
            "accepted_memory_refs_count": len(a.accepted_memory_refs),
            "open_questions": a.open_questions[:50],
            "degradation_recommendation": a.degradation_recommendation,
        },
        "retrieval_receipt_id": result.retrieval_receipt_id,
        "packet_receipt_id": result.packet_receipt_id,
        "warnings": result.warnings,
        "guardrails": _RESEARCH_PACKET_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_QUERY_GUARDRAILS = {
    "local_first": True,
    "mock_first": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "research_packet_required_for_complex": True,
    "advisory_vs_actionable_separation": True,
    "tier_3_never_final_conclusion": True,
    "model_direct_external_api_access": False,
}


@app.command("query")
def query(
    question: str = typer.Argument(..., help="The question to answer (source-linked, advisory)."),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist the research-packet + retrieval receipts (metadata only).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Answer a question from approved, source-linked context (mock-first, advisory)."""
    from hb_assistant.construction.second_brain.synthesis import synthesize_answer

    try:
        result = synthesize_answer(
            question=question, project_key=project_key, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {"command": "second-brain query", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain query",
        **result.model_dump(),
        "guardrails": _QUERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_MEMORY_GUARDRAILS = {
    "local_first": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "sensitive_high_impact_routes_tier_3": True,
    "no_silent_acceptance": True,
    "preferences_never_override_safety": True,
}


@memory_app.command("candidate")
def memory_candidate(
    statement: str = typer.Option(..., "--statement", help="Redacted memory statement."),
    memory_type: str = typer.Option("fact", "--memory-type"),
    origin_id: str = typer.Option(
        ..., "--origin-id", help="Origin (query/packet/brief/feedback) id."
    ),
    confidence: str = typer.Option("medium", "--confidence", help="high|medium|low."),
    sensitivity: str = typer.Option(None, "--sensitivity", help="Sensitive/high-impact category."),
    project_key: str = typer.Option(None, "--project-key"),
    source_refs: str = typer.Option(
        None, "--source-refs", help="Comma-separated 'family:ref' pairs."
    ),
    emit: bool = typer.Option(
        False, "--emit/--no-emit", help="Persist the candidate (dry-run default)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Propose a long-term memory candidate (sensitive/high-impact -> Tier 3; never auto-accepted)."""
    from hb_assistant.construction.second_brain.memory import propose_memory_candidate

    refs: list[dict[str, str]] = []
    for raw in (source_refs or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        family, _, ref = raw.partition(":")
        refs.append({"source_family": family, "source_ref": ref})
    candidate = propose_memory_candidate(
        statement_redacted=statement,
        proposed_memory_type=memory_type,
        origin_id=origin_id,
        source_refs=refs,
        confidence_class=confidence,
        sensitivity_category=sensitivity,
        project_key=project_key,
        emit=emit,
    )
    payload = {
        "command": "second-brain memory candidate",
        "emitted": emit,
        "candidate": candidate.model_dump(),
        "guardrails": _MEMORY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@memory_app.command("review")
def memory_review(
    candidate_id: str = typer.Option(..., "--candidate-id"),
    decision: str = typer.Option(..., "--decision", help="accepted|rejected|superseded|deferred."),
    reason: str = typer.Option(None, "--reason", help="Redacted decision reason."),
    emit: bool = typer.Option(
        False, "--emit/--no-emit", help="Persist the review (dry-run default)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Apply an explicit operator review; 'accepted' promotes the candidate to memory."""
    from hb_assistant.construction.second_brain.memory import (
        MemoryCandidate,
        review_memory_candidate,
    )
    from hb_assistant.construction.second_brain.memory.store import read_memory_candidate

    row = read_memory_candidate(candidate_id)
    if row is None:
        err = {
            "command": "second-brain memory review",
            "error": "candidate_not_found",
            "candidate_id": candidate_id,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3)

    candidate = MemoryCandidate(
        candidate_id=row["candidate_id"],
        proposed_memory_type=row["proposed_memory_type"],
        statement_redacted=row["statement_redacted"],
        project_key=row["project_key"],
        origin_id=row["origin_id"],
        provenance_class=row["provenance_class"],
        confidence_class=row["confidence_class"],
        review_required=bool(row["review_required"]),
        review_tier=row["review_tier"] or 3,
        review_tier_reason_code=row["review_tier_reason_code"] or "T3_MODEL_ONLY",
        sensitivity_class=row["sensitivity_class"],
        source_refs=json.loads(row["source_refs_json"] or "[]"),
        status=row["status"],
    )
    review, item, signals = review_memory_candidate(
        candidate=candidate,
        decision=decision,
        decision_reason_redacted=reason,
        emit=emit,
    )
    payload = {
        "command": "second-brain memory review",
        "emitted": emit,
        "decision": review.decision,
        "accepted_memory_id": item.memory_id if item else None,
        "quality_signal_types": [s.signal_type for s in signals],
        "guardrails": _MEMORY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@preference_app.command("capture")
def preference_capture(
    preference_key: str = typer.Option(..., "--key", help="Preference key (presentation only)."),
    value: str = typer.Option(None, "--value", help="Redacted preference value."),
    scope: str = typer.Option("global", "--scope", help="global|project|entity."),
    scope_key: str = typer.Option(None, "--scope-key"),
    preference_type: str = typer.Option(
        None, "--type", help="Preference type (sensitive -> Tier 3)."
    ),
    sensitive: bool = typer.Option(False, "--sensitive/--not-sensitive"),
    emit: bool = typer.Option(
        False, "--emit/--no-emit", help="Persist the preference (dry-run default)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Capture a reviewable operator preference (never auto-accepted; can't override safety)."""
    from hb_assistant.construction.second_brain.memory import capture_preference

    pref = capture_preference(
        scope=scope,
        preference_key=preference_key,
        preference_value_redacted=value,
        preference_type=preference_type,
        scope_key=scope_key,
        sensitive=sensitive,
        emit=emit,
    )
    payload = {
        "command": "second-brain preference capture",
        "emitted": emit,
        "preference": pref.model_dump(),
        "guardrails": _MEMORY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_DAILY_BRIEF_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "no_html_or_notifications": True,
    "source_references_required": True,
    "synthesis_requires_packet": True,
    "insufficient_context_degrades_not_overstates": True,
    "tier_3_never_final_conclusion": True,
    "model_direct_external_api_access": False,
}


@daily_brief_app.command("build")
def daily_brief_build(
    brief_date: str = typer.Option(..., "--date", help="Brief date (YYYY-MM-DD)."),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    mode: str = typer.Option("dry_run", "--mode", help="dry_run|apply (no external writeback)."),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only daily-brief run to the local V26 table.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a bounded, source-linked daily-brief context package (read-only)."""
    if mode not in ("dry_run", "apply"):
        err_payload: dict[str, object] = {
            "command": "second-brain daily-brief build",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief import build_daily_brief_context

    try:
        context = build_daily_brief_context(
            brief_date=brief_date,
            project_key=project_key,
            mode=mode,
            emit_receipt=emit_receipt,
        )
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {
            "command": "second-brain daily-brief build",
            "brief_date": brief_date,
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    handoff = context.delivery_handoff
    payload = {
        "command": "second-brain daily-brief build",
        "brief_date": context.brief_date,
        "brief_run_id": context.brief_run_id,
        "mode": mode,
        "status": context.status,
        "project_count": context.project_count,
        "source_ref_count": context.source_ref_count,
        "review_required_count": context.review_required_count,
        "stale_unknown_count": context.stale_unknown_count,
        "source_coverage": context.source_coverage,
        "review_tier_counts": context.review_tier_counts,
        "context_quality_class": context.context_quality_class,
        "degradation_mode": context.degradation_mode,
        "review_tier": context.review_tier,
        "review_tier_reason_code": context.review_tier_reason_code,
        "research_packet_id": context.research_packet_id,
        "cards": {
            "attention_item": len(context.attention_cards),
            "meeting": len(context.meeting_cards),
            "project": len(context.project_cards),
            "warning": len(context.warning_cards),
            "review_required": len(context.review_required_cards),
        },
        "review_load": context.review_load.model_dump(),
        "delivery_handoff": {
            "output_format": handoff.output_format,
            "notification_emitted": handoff.notification_emitted,
            "review_tier": handoff.review_tier,
            "degradation_mode": handoff.degradation_mode,
            "section_counts": {k: len(v) for k, v in handoff.sections.items()},
            "source_ref_count": len(handoff.source_refs),
        },
        "warnings": context.warnings[:50],
        "guardrails": _DAILY_BRIEF_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@daily_brief_app.command("triage")
def daily_brief_triage(
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Summarize review load grouped by tier, source, project, and urgency (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief import ReviewTriageAgent

    try:
        status = ReviewTriageAgent().summarize(project_key=project_key)
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {"command": "second-brain daily-brief triage", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain daily-brief triage",
        "project_key": project_key,
        **status.model_dump(),
        "guardrails": _DAILY_BRIEF_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_DAILY_BRIEF_GENERATE_GUARDRAILS = {
    "local_first": True,
    "mock_first": True,
    "research_packet_required": True,
    "evaluation_required_before_apply": True,
    "apply_blocked_when_evaluation_fails": True,
    "no_external_delivery": True,
    "no_macos_notification": True,
    "no_html_rendering": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@daily_brief_app.command("generate")
def daily_brief_generate(
    brief_date: str = typer.Option(
        None, "--date", help="Brief date YYYY-MM-DD (default: today + --day-offset)."
    ),
    day_offset: int = typer.Option(
        0, "--day-offset", help="Days from today when --date is omitted (1 = tomorrow)."
    ),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    mode: str = typer.Option(
        "dry_run", "--mode", help="dry_run|apply (apply writes approved Obsidian output)."
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist metadata-only evaluation + brief-run rows to the local V26 tables.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Generate -> evaluate -> (gated) apply -> hand off the daily brief (mock-first)."""
    if mode not in ("dry_run", "apply"):
        err_payload: dict[str, object] = {
            "command": "second-brain daily-brief generate",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    if brief_date is None:
        from datetime import date, timedelta

        brief_date = (date.today() + timedelta(days=day_offset)).isoformat()

    from hb_assistant.construction.second_brain.daily_brief import run_daily_brief

    try:
        result = run_daily_brief(
            brief_date=brief_date,
            project_key=project_key,
            mode=mode,
            emit_receipt=emit_receipt,
        )
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB/vault unavailable)
        err = {
            "command": "second-brain daily-brief generate",
            "brief_date": brief_date,
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    handoff = result.delivery_handoff
    evaluation = result.evaluation
    payload = {
        "command": "second-brain daily-brief generate",
        "brief_date": result.brief_date,
        "brief_run_id": result.brief_run_id,
        "mode": result.mode,
        "status": result.status,
        "applied": result.applied,
        "apply_blocked_reason": result.apply_blocked_reason,
        "evaluation": {
            "passed": evaluation.get("passed"),
            "score": evaluation.get("score"),
            "checklist_passed": evaluation.get("checklist_passed"),
            "checklist_total": evaluation.get("checklist_total"),
        },
        "evaluation_run_id": result.evaluation_run_id,
        "eligible_for_delivery": result.eligible_for_delivery,
        "output_written": result.output_written,
        "output_path_redacted": result.output_path_redacted,
        "source_ref_count": result.source_ref_count,
        "source_coverage": result.source_coverage,
        "review_tier_counts": result.review_tier_counts,
        "delivery_handoff": {
            "phase": handoff.phase,
            "eligible_for_delivery": handoff.eligible_for_delivery,
            "local_only": handoff.local_only,
            "external_delivery_performed": handoff.external_delivery_performed,
            "section_counts": {k: len(v) for k, v in handoff.sections.items()},
            "source_ref_count": len(handoff.source_refs),
            "notification_summary": handoff.notification_summary.model_dump(),
            "html_rendering": {
                "format": handoff.html_rendering.format,
                "rendered": handoff.html_rendering.rendered,
            },
        },
        "warnings": result.warnings[:50],
        "guardrails": _DAILY_BRIEF_GENERATE_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_RENDER_VIEW_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "deterministic": True,
    "reconstructed_from_persisted_handoff": True,
    "no_html_rendered": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "source_references_required": True,
}


@daily_brief_app.command("render-view")
def daily_brief_render_view(
    brief_date: str = typer.Option(
        None, "--date", help="Reconstruct the most recent persisted brief for this date."
    ),
    run_id: str = typer.Option(None, "--run-id", help="Reconstruct a specific brief_run_id."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Emit the deterministic, no-raw, rendered=False render view for a persisted brief (read-only)."""
    if not run_id and not brief_date:
        err_payload = {
            "command": "second-brain daily-brief render-view",
            "error": "missing_selector",
            "detail": "provide --run-id or --date",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_render_view,
        read_daily_brief_handoff,
        read_latest_daily_brief_runs,
    )

    try:
        resolved_run_id = run_id
        if not resolved_run_id:
            runs = [r for r in read_latest_daily_brief_runs() if r["brief_date"] == brief_date]
            resolved_run_id = runs[0]["brief_run_id"] if runs else None

        handoff = read_daily_brief_handoff(resolved_run_id) if resolved_run_id else None
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {
            "command": "second-brain daily-brief render-view",
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    if handoff is None:
        not_found = {
            "command": "second-brain daily-brief render-view",
            "error": "brief_run_not_found",
            "brief_date": brief_date,
            "run_id": run_id,
            "guardrails": _RENDER_VIEW_GUARDRAILS,
        }
        typer.echo(json.dumps(not_found, indent=2, default=str) if json_out else str(not_found))
        raise typer.Exit(4)

    view = build_daily_brief_render_view(handoff)
    payload = {
        "command": "second-brain daily-brief render-view",
        **view.model_dump(),
        "guardrails": _RENDER_VIEW_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_SCHEDULE_PREVIEW_GUARDRAILS = {
    "local_first": True,
    "dry_run_install_only": True,
    "no_launchctl_invocation": True,
    "no_plist_written": True,
    "logs_outside_repo": True,
    "no_external_writeback": True,
    "no_hidden_background_behavior": True,
    "phase_08b_owns_hardening": True,
}


@daily_brief_app.command("schedule-preview")
def daily_brief_schedule_preview(
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only dry-run preview row to the local V26 table.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Preview the launchd schedule for the daily brief (dry-run install only; no launchctl)."""
    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_schedule_preview,
    )

    try:
        preview = build_daily_brief_schedule_preview(emit=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive (e.g., seed unavailable)
        err = {"command": "second-brain daily-brief schedule-preview", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain daily-brief schedule-preview",
        "preview_id": preview.preview_id,
        "label": preview.label,
        "schedule": {"hour": preview.hour, "minute": preview.minute},
        "day_offset": preview.day_offset,
        "command_mode": preview.command_mode,
        "program_arguments_redacted": preview.program_arguments_redacted,
        "plist": preview.plist,
        "plist_path_redacted": preview.plist_path_redacted,
        "log_out_redacted": preview.log_out_redacted,
        "log_err_redacted": preview.log_err_redacted,
        "logs_outside_repo": preview.logs_outside_repo,
        "manual_install_commands": preview.manual_install_commands,
        "readiness": preview.readiness,
        "dry_run_install_only": preview.dry_run_install_only,
        "phase_08b_handoff": preview.phase_08b_handoff,
        "guardrails": _SCHEDULE_PREVIEW_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@data_quality_app.command("phase-08a-gates")
def data_quality_phase_08a_gates(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Evaluate the Phase 08A second-brain data-quality gate set (read-only)."""
    from hb_assistant.construction.second_brain.data_quality import (
        evaluate_phase_08a_data_quality_gates,
    )

    report = evaluate_phase_08a_data_quality_gates()
    typer.echo(json.dumps(report, indent=2, default=str) if json_out else str(report))
    raise typer.Exit(0 if report["ok"] else 3)


@data_quality_app.command("phase-08b-gates")
def data_quality_phase_08b_gates(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Evaluate the Phase 08B automation/observability substrate gate set (read-only)."""
    from hb_assistant.construction.second_brain.data_quality import (
        evaluate_phase_08b_data_quality_gates,
    )

    report = evaluate_phase_08b_data_quality_gates()
    typer.echo(json.dumps(report, indent=2, default=str) if json_out else str(report))
    raise typer.Exit(0 if report["ok"] else 3)


_AUTOMATION_HEALTH_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_alert_emitted": True,
    "no_raw_content": True,
    "receipt_emit_gated": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("health")
def automation_health(
    json_out: bool = typer.Option(True, "--json"),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this health run (off by default).",
    ),
) -> None:
    """Report second-brain automation health with actionable reason codes (read-only)."""
    from hb_assistant.construction.second_brain.automation_health import run_automation_health

    try:
        status, agent_run_id = run_automation_health(emit_receipt=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive: status must not crash
        err = {"command": "second-brain automation health", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation health",
        "overall_status": status.overall_status,
        "reason_code": status.reason_code,
        "checks": [c.model_dump() for c in status.checks],
        "degraded_checks": status.degraded_checks,
        "policy_version": status.policy_version,
        "schema_version": status.schema_version,
        "schema_expected": status.schema_expected,
        "agent_run_id": agent_run_id,
        "generated_utc": status.generated_utc,
        "guardrails": _AUTOMATION_HEALTH_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_LAUNCHD_SCHEDULER_GUARDRAILS = {
    "local_first": True,
    "read_only_default": True,
    "dry_run_install_only": True,
    "apply_fail_closed_by_policy": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("launchd-status")
def automation_launchd_status(
    json_out: bool = typer.Option(True, "--json"),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this scheduling eval (off by default).",
    ),
) -> None:
    """Report daily-brief LaunchAgent install/schedule + catch-up status (read-only)."""
    from hb_assistant.construction.second_brain.launchd_scheduler import run_launchd_schedule_agent

    try:
        snapshot, agent_run_id = run_launchd_schedule_agent(emit_receipt=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive: status must not crash
        err = {"command": "second-brain automation launchd-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation launchd-status",
        "overall_status": snapshot.overall_status,
        "reason_code": snapshot.reason_code,
        "schedule": snapshot.schedule.model_dump(),
        "catch_up": snapshot.catch_up.model_dump(),
        "policy_version": snapshot.policy_version,
        "schema_version": snapshot.schema_version,
        "schema_expected": snapshot.schema_expected,
        "agent_run_id": agent_run_id,
        "generated_utc": snapshot.generated_utc,
        "guardrails": _LAUNCHD_SCHEDULER_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if snapshot.overall_status == "ok" else 3)


@automation_app.command("catch-up-status")
def automation_catch_up_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report whether a first-run-after-wake catch-up is owed (read-only, advisory)."""
    from hb_assistant.construction.second_brain.launchd_scheduler import (
        evaluate_first_run_after_wake,
    )

    try:
        catch_up = evaluate_first_run_after_wake()
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation catch-up-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation catch-up-status",
        **catch_up.model_dump(),
        "guardrails": _LAUNCHD_SCHEDULER_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("launchd-install")
def automation_launchd_install(
    apply: bool = typer.Option(
        False, "--apply/--no-apply", help="Attempt a real install (fail-closed by policy)."
    ),
    confirm: bool = typer.Option(
        False, "--confirm/--no-confirm", help="Required alongside --apply to attempt an install."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Preview (default) or attempt installing the daily-brief LaunchAgent (dry-run by default)."""
    from hb_assistant.construction.second_brain.launchd_scheduler import (
        apply_launchd_install,
        preview_launchd_install,
    )

    try:
        result = apply_launchd_install(confirm=confirm) if apply else preview_launchd_install()
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation launchd-install", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation launchd-install",
        **result,
        "guardrails": _LAUNCHD_SCHEDULER_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("launchd-uninstall")
def automation_launchd_uninstall(
    apply: bool = typer.Option(
        False, "--apply/--no-apply", help="Attempt a real uninstall (fail-closed by policy)."
    ),
    confirm: bool = typer.Option(
        False, "--confirm/--no-confirm", help="Required alongside --apply to attempt an uninstall."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Preview (default) or attempt uninstalling the daily-brief LaunchAgent (dry-run by default)."""
    from hb_assistant.construction.second_brain.launchd_scheduler import uninstall_launchd

    try:
        if apply:
            result = uninstall_launchd(confirm=confirm)
        else:
            result = {
                "command": "launchd-uninstall",
                "status": "preview",
                "plist_removed": False,
                "launchctl_invoked": False,
                "external_writeback_performed": 0,
                "detail": "pass --apply --confirm to attempt (fail-closed by policy)",
            }
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation launchd-uninstall", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation launchd-uninstall",
        **result,
        "guardrails": _LAUNCHD_SCHEDULER_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_RUN_REGISTRY_GUARDRAILS = {
    "local_first": True,
    "read_only_default": True,
    "atomic_file_lock_outside_repo": True,
    "fail_closed_on_overlap": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("run-registry-status")
def automation_run_registry_status(
    limit: int = typer.Option(10, "--limit", help="Max recent registry rows to report."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report recent run-registry rows + step counts + reason codes (read-only)."""
    from hb_assistant.construction.second_brain.run_registry import read_latest_run_registry

    try:
        rows = read_latest_run_registry(limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        err = {
            "command": "second-brain automation run-registry-status",
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation run-registry-status",
        "count": len(rows),
        "runs": rows,
        "guardrails": _RUN_REGISTRY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("run-lock-status")
def automation_run_lock_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report the current no-overlap lock state (held / stale / absent) with reason codes."""
    from hb_assistant.construction.second_brain.run_registry import read_run_lock

    try:
        lock = read_run_lock()
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation run-lock-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation run-lock-status",
        **lock.model_dump(),
        "guardrails": _RUN_REGISTRY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("run-lock")
def automation_run_lock(
    run_kind: str = typer.Option("morning_automation", "--run-kind", help="Run kind label."),
    mode: str = typer.Option(
        "dry_run", "--mode", help="dry_run|apply (apply performs a real acquire->release cycle)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Preview (dry-run, default) or perform an acquire->release no-overlap lock cycle."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation run-lock",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.run_registry import (
        acquire_run_lock,
        release_run_lock,
    )

    try:
        acquired = acquire_run_lock(run_kind=run_kind, dry_run=(mode == "dry_run"))
        released = None
        if mode == "apply" and acquired.status in ("acquired", "reclaimed") and acquired.token:
            released = release_run_lock(token=acquired.token, lock_name=acquired.lock_name)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation run-lock", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation run-lock",
        "mode": mode,
        "acquire": acquired.model_dump(),
        "release": released.model_dump() if released is not None else None,
        "guardrails": _RUN_REGISTRY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_RETRY_RECOVERY_GUARDRAILS = {
    "local_first": True,
    "read_only_default": True,
    "apply_mutates_local_state_only": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("retry-plan")
def automation_retry_plan(
    run_kind: str = typer.Option("morning_automation", "--run-kind", help="Run kind label."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report the policy-driven retry/backoff schedule for a run kind (read-only)."""
    from hb_assistant.construction.second_brain.retry_recovery import plan_retry_schedule

    try:
        plan = plan_retry_schedule(run_kind=run_kind)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation retry-plan", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation retry-plan",
        **plan,
        "guardrails": _RETRY_RECOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("run-recovery")
def automation_run_recovery(
    mode: str = typer.Option(
        "dry_run",
        "--mode",
        help="dry_run|apply (apply recovers orphaned runs + clears stale locks).",
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this recovery run (off by default).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Detect orphaned runs / stale locks and (apply, dry-run default) recover them."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation run-recovery",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.retry_recovery import run_run_recovery_agent

    try:
        status, agent_run_id = run_run_recovery_agent(mode=mode, emit_receipt=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation run-recovery", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation run-recovery",
        "mode": mode,
        **status.model_dump(),
        "agent_run_id": agent_run_id,
        "guardrails": _RETRY_RECOVERY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_FRESHNESS_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "deterministic": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("source-freshness")
def automation_source_freshness(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report per-domain source freshness (last successful sync vs threshold; read-only)."""
    from hb_assistant.construction.second_brain.freshness import evaluate_source_freshness

    try:
        status = evaluate_source_freshness()
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation source-freshness", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation source-freshness",
        "overall_status": status.overall_status,
        "reason_code": status.reason_code,
        "signals": [s.model_dump() for s in status.signals],
        "stale_count": status.stale_count,
        "unknown_count": status.unknown_count,
        "guardrails": _FRESHNESS_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("retrieval-freshness")
def automation_retrieval_freshness(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report Obsidian index + retrieval freshness (read-only, deterministic)."""
    from hb_assistant.construction.second_brain.freshness import evaluate_retrieval_freshness

    try:
        status = evaluate_retrieval_freshness()
    except Exception as exc:  # pragma: no cover - defensive
        err = {
            "command": "second-brain automation retrieval-freshness",
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation retrieval-freshness",
        "overall_status": status.overall_status,
        "reason_code": status.reason_code,
        "signals": [s.model_dump() for s in status.signals],
        "stale_count": status.stale_count,
        "unknown_count": status.unknown_count,
        "guardrails": _FRESHNESS_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("observability")
def automation_observability(
    json_out: bool = typer.Option(True, "--json"),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this observability run (off by default).",
    ),
) -> None:
    """Combined source / runtime / retrieval freshness observability (read-only)."""
    from hb_assistant.construction.second_brain.freshness import run_observability

    try:
        snapshot, agent_run_id = run_observability(emit_receipt=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation observability", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation observability",
        "overall_status": snapshot.overall_status,
        "reason_code": snapshot.reason_code,
        "source": snapshot.source.model_dump(),
        "runtime": snapshot.runtime.model_dump(),
        "retrieval": snapshot.retrieval.model_dump(),
        "policy_version": snapshot.policy_version,
        "schema_version": snapshot.schema_version,
        "schema_expected": snapshot.schema_expected,
        "agent_run_id": agent_run_id,
        "generated_utc": snapshot.generated_utc,
        "guardrails": _FRESHNESS_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if snapshot.overall_status == "ok" else 3)


@automation_app.command("daily-brief-health")
def automation_daily_brief_health(
    json_out: bool = typer.Option(True, "--json"),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this job-health run (off by default).",
    ),
) -> None:
    """Report daily-brief job health (cadence / success / degradation) with reason codes (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief_health import (
        run_daily_brief_job_health,
    )

    try:
        status, agent_run_id = run_daily_brief_job_health(emit_receipt=emit_receipt)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation daily-brief-health", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation daily-brief-health",
        "overall_status": status.overall_status,
        "reason_code": status.reason_code,
        "last_run_status": status.last_run_status,
        "last_run_utc": status.last_run_utc,
        "last_run_date": status.last_run_date,
        "age_seconds": status.age_seconds,
        "degradation_mode": status.degradation_mode,
        "review_tier": status.review_tier,
        "consecutive_non_healthy": status.consecutive_non_healthy,
        "runs_examined": status.runs_examined,
        "policy_version": status.policy_version,
        "schema_version": status.schema_version,
        "schema_expected": status.schema_expected,
        "agent_run_id": agent_run_id,
        "generated_utc": status.generated_utc,
        "guardrails": _FRESHNESS_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_DELIVERY_GUARDRAILS = {
    "local_first": True,
    "dry_run_default": True,
    "delivery_channel": "obsidian_vault",
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


def _delivery_payload(command: str, status: object, agent_run_id: str | None) -> dict[str, object]:
    return {
        "command": command,
        **status.model_dump(),  # type: ignore[attr-defined]
        "agent_run_id": agent_run_id,
        "guardrails": _DELIVERY_GUARDRAILS,
    }


@automation_app.command("delivery-status")
def automation_delivery_status(
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report local-only daily-brief delivery eligibility with reason codes (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief_delivery import (
        evaluate_daily_brief_delivery,
    )

    try:
        status = evaluate_daily_brief_delivery(brief_date=brief_date)
    except Exception as exc:  # pragma: no cover - defensive: status must not crash
        err = {"command": "second-brain automation delivery-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _delivery_payload("second-brain automation delivery-status", status, None)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("deliver")
def automation_deliver(
    mode: str = typer.Option(
        "dry_run",
        "--mode",
        help="dry_run|apply (apply writes the redacted brief note to the Obsidian vault).",
    ),
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this delivery run (off by default).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Deliver an approved brief locally to the Obsidian vault (apply; dry-run by default)."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation deliver",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief_delivery import (
        run_daily_brief_delivery_agent,
    )

    try:
        status, agent_run_id = run_daily_brief_delivery_agent(
            brief_date=brief_date, mode=mode, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation deliver", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _delivery_payload("second-brain automation deliver", status, agent_run_id)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_HTML_RENDER_GUARDRAILS = {
    "local_first": True,
    "dry_run_default": True,
    "self_contained_no_network": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_html_persisted": True,
    "model_direct_external_api_access": False,
}


def _html_render_payload(
    command: str, status: object, agent_run_id: str | None
) -> dict[str, object]:
    return {
        "command": command,
        **status.model_dump(),  # type: ignore[attr-defined]
        "agent_run_id": agent_run_id,
        "guardrails": _HTML_RENDER_GUARDRAILS,
    }


@automation_app.command("html-status")
def automation_html_status(
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report local HTML-render eligibility for the daily brief with reason codes (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief_html import (
        evaluate_daily_brief_html_render,
    )

    try:
        status = evaluate_daily_brief_html_render(brief_date=brief_date)
    except Exception as exc:  # pragma: no cover - defensive: status must not crash
        err = {"command": "second-brain automation html-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _html_render_payload("second-brain automation html-status", status, None)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("render-html")
def automation_render_html(
    mode: str = typer.Option(
        "dry_run",
        "--mode",
        help="dry_run|apply (apply renders a self-contained HTML brief to <app_support>/html/).",
    ),
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this render run (off by default).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Render a self-contained local HTML daily brief (apply; dry-run by default)."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation render-html",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief_html import (
        run_daily_brief_html_render_agent,
    )

    try:
        status, agent_run_id = run_daily_brief_html_render_agent(
            brief_date=brief_date, mode=mode, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation render-html", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _html_render_payload("second-brain automation render-html", status, agent_run_id)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_NOTIFY_GUARDRAILS = {
    "local_first": True,
    "dry_run_default": True,
    "fail_closed_emission": True,
    "channel": "local_macos",
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


def _notify_payload(command: str, status: object, agent_run_id: str | None) -> dict[str, object]:
    return {
        "command": command,
        **status.model_dump(),  # type: ignore[attr-defined]
        "agent_run_id": agent_run_id,
        "guardrails": _NOTIFY_GUARDRAILS,
    }


@automation_app.command("notify-status")
def automation_notify_status(
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report local macOS notification eligibility for the daily brief with reason codes (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief_notify import (
        evaluate_daily_brief_notification,
    )

    try:
        status = evaluate_daily_brief_notification(brief_date=brief_date)
    except Exception as exc:  # pragma: no cover - defensive: status must not crash
        err = {"command": "second-brain automation notify-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _notify_payload("second-brain automation notify-status", status, None)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("notify")
def automation_notify(
    mode: str = typer.Option(
        "dry_run",
        "--mode",
        help="dry_run|apply (apply emits a local macOS banner — fail-closed behind the emit policy).",
    ),
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this notify run (off by default).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Preview / emit a local macOS notification for the daily brief (apply; dry-run by default)."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation notify",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief_notify import (
        run_daily_brief_notification_agent,
    )

    try:
        status, agent_run_id = run_daily_brief_notification_agent(
            brief_date=brief_date, mode=mode, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation notify", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = _notify_payload("second-brain automation notify", status, agent_run_id)
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


_OPEN_GUARDRAILS = {
    "local_first": True,
    "dry_run_default": True,
    "fail_closed_open": True,
    "no_external_writeback": True,
    "no_external_delivery": True,
    "no_raw_content": True,
    "model_direct_external_api_access": False,
}


@automation_app.command("brief-status")
def automation_brief_status(
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report the consolidated daily-brief delivery lifecycle (delivered/rendered/notified/opened)."""
    from hb_assistant.construction.second_brain.daily_brief_open import (
        evaluate_brief_delivery_status,
    )

    try:
        status = evaluate_brief_delivery_status(brief_date=brief_date)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation brief-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation brief-status",
        **status.model_dump(),
        "guardrails": _OPEN_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@automation_app.command("receipts")
def automation_receipts(
    brief_date: str = typer.Option(
        None, "--brief-date", help="Filter to a specific brief date (YYYY-MM-DD)."
    ),
    limit: int = typer.Option(50, "--limit", help="Max receipts to list."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List recent delivery/render/notify/open receipts across the ledgers (read-only, metadata)."""
    from hb_assistant.construction.second_brain.daily_brief_open import list_brief_receipts

    try:
        receipts = list_brief_receipts(brief_date=brief_date, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation receipts", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation receipts",
        "receipt_count": len(receipts),
        "receipts": receipts,
        "guardrails": _OPEN_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("open-brief")
def automation_open_brief(
    mode: str = typer.Option(
        "dry_run",
        "--mode",
        help="dry_run|apply (apply runs macOS `open` — fail-closed behind the open policy).",
    ),
    target: str = typer.Option(
        "vault", "--target", help="vault|html (which produced local artifact to open)."
    ),
    brief_date: str = typer.Option(
        None, "--brief-date", help="Specific brief date (YYYY-MM-DD); default = latest run."
    ),
    emit_receipt: bool = typer.Option(
        False,
        "--emit-receipt/--no-emit-receipt",
        help="Persist a metadata-only V28 agent-run receipt for this open run (off by default).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Open the produced local brief artifact (vault note / HTML) — apply; dry-run by default."""
    if mode not in ("dry_run", "apply"):
        err = {
            "command": "second-brain automation open-brief",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)
    if target not in ("vault", "html"):
        err = {
            "command": "second-brain automation open-brief",
            "error": "invalid_target",
            "detail": f"{target!r} not in ['vault', 'html']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief_open import run_brief_open_agent

    try:
        status, agent_run_id = run_brief_open_agent(
            brief_date=brief_date, target=target, mode=mode, emit_receipt=emit_receipt
        )
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation open-brief", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation open-brief",
        **status.model_dump(),
        "agent_run_id": agent_run_id,
        "guardrails": _OPEN_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if status.overall_status == "ok" else 3)


@data_quality_app.command("no-writeback-proof")
def data_quality_no_writeback_proof(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Prove the Phase 08A runtime has no writeback / secrets / raw content (read-only)."""
    from hb_assistant.construction.second_brain.safety import (
        build_second_brain_no_writeback_proof,
    )

    report = build_second_brain_no_writeback_proof()
    typer.echo(json.dumps(report, indent=2, default=str) if json_out else str(report))
    raise typer.Exit(0 if report["proof_passed"] else 3)


@index_app.command("obsidian")
def index_obsidian(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview planned notes (no apply)."),
    apply: bool = typer.Option(False, "--apply", help="Persist an apply index manifest."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Index approved/generated marker-bounded Obsidian notes (read-only over vault)."""
    if dry_run and apply:
        typer.echo(
            json.dumps({"error": "mutually_exclusive", "detail": "--dry-run and --apply"}, indent=2)
            if json_out
            else "error: --dry-run and --apply are mutually exclusive"
        )
        raise typer.Exit(2)
    mode = "apply" if apply else "dry_run"

    from hb_assistant.construction.second_brain.obsidian_index import build_index

    try:
        manifest = build_index(mode=mode)
        error = None
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB/vault unavailable)
        manifest = None
        error = type(exc).__name__

    if manifest is None:
        payload: dict[str, object] = {
            "command": "second-brain index obsidian",
            "mode": mode,
            "error": error,
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(3)

    planned = [
        {
            "approved_root_label": e.approved_root_label,
            "note_path_redacted": e.note_path_redacted,
            "note_path_hash": e.note_path_hash,
            "section_marker": e.section_marker,
            "content_hash": e.content_hash,
            "project_key": e.project_key,
            "source_type": e.source_type,
            "confidence_class": e.confidence_class,
            "review_tier": e.review_tier,
            "review_status": e.review_status,
            "source_ref_count": e.source_ref_count,
        }
        for e in manifest.entries[:200]
    ]
    payload = {
        "command": "second-brain index obsidian",
        "mode": manifest.mode,
        "manifest_id": manifest.manifest_id,
        "entry_count": manifest.entry_count,
        "excluded_count": manifest.excluded_count,
        "approved_roots": manifest.approved_roots,
        "policy_version": manifest.policy_version,
        "planned_entries": planned,
        "guardrails": {
            "source_notes_mutated": False,
            "raw_content_persisted": False,
            "raw_vault_browsing": False,
        },
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@automation_app.command("plan-execution")
def automation_plan_execution(
    mode: str = typer.Option("manual", "--mode", help="manual|launchd|catch_up|replay"),
    day_offset: int = typer.Option(0, "--day-offset"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build (dry-run) execution plan for daily brief using P01 substrate + 08B surfaces. Emits plan only (no side effects)."""
    from hb_assistant.construction.second_brain.automation_executor import (
        ExecutionRequest,
        build_execution_plan,
    )

    req = ExecutionRequest(run_kind="daily_brief", mode=mode, day_offset=day_offset)  # type: ignore[arg-type]
    plan = build_execution_plan(request=req, dry_run=True)
    payload = {
        "command": "second-brain automation plan-execution",
        "dry_run": True,
        "plan": plan.model_dump(),
        "guardrails": plan.guardrails,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


_EXEC_GUARDRAILS = {
    "local_first": True,
    "apply_requires_explicit_confirm": True,
    "no_external_delivery": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "lock_guaranteed_release": True,
    "stage_receipts_persisted": "V29_run_steps + emit V28+",
    "fail_closed": True,
    "automation_execution_still_deferred": False,
    "automation_execution_ready_via_proof": True,
}


@automation_app.command("execute")
def automation_execute(
    mode: str = typer.Option("manual", "--mode", help="manual|launchd|catch_up|replay"),
    day_offset: int = typer.Option(0, "--day-offset"),
    apply: bool = typer.Option(
        False,
        "--apply/--no-apply",
        help="Attempt real execution (acquire lock, register run, run 8 stages, persist receipts). Dry-run default.",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm/--no-confirm",
        help="REQUIRED together with --apply to execute (two-factor explicit approval).",
    ),
    json_out: bool = typer.Option(True, "--json"),
    # P05 safe replay flags (additive; only meaningful with --mode=replay)
    replay_of: str | None = typer.Option(
        None, "--replay-of", help="original run_registry_id when --mode=replay"
    ),
    replay_selector: str | None = typer.Option(
        None, "--replay-selector", help="failed-only|failed-and-following|explicit"
    ),
    replay_stages: str | None = typer.Option(
        None, "--replay-stages", help="comma-separated explicit stage names"
    ),
) -> None:
    """Execute (or dry-run) the daily brief automation plan.

    Default is dry-run (plan only). Real apply path requires BOTH --apply and --confirm.
    Uses the executor service: lock before registry before ordered stages, stage receipts via V29+,
    downstream skip on failure, recovery recommendation, guaranteed lock release.
    Injected fakes used in tests; real CLI --apply --confirm is the production gate (still local-only).
    """
    from hb_assistant.construction.second_brain.automation_executor import (
        ExecutionRequest,
        run_automation_execution,
    )

    rsel = replay_selector  # type: ignore[assignment]
    rstages = (
        [s.strip() for s in (replay_stages or "").split(",") if s.strip()] if replay_stages else []
    )
    req = ExecutionRequest(
        run_kind="daily_brief",
        mode=mode,
        day_offset=day_offset,
        original_run_registry_id=replay_of,
        replay_selector=rsel,  # type: ignore[arg-type]
        replay_stages=rstages,
    )  # type: ignore[arg-type]
    result = run_automation_execution(req, apply=apply, confirm=confirm)
    payload = {
        "command": "second-brain automation execute",
        "apply_requested": apply,
        "confirmed": confirm,
        "result": result.model_dump() if hasattr(result, "model_dump") else result,
        "guardrails": _EXEC_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    ok = (
        result.overall_status in ("succeeded", "dry_run")
        if hasattr(result, "overall_status")
        else True
    )
    raise typer.Exit(0 if ok else 3)


@automation_app.command("execution-status")
def automation_execution_status(
    limit: int = typer.Option(
        5, "--limit", help="Max recent daily_brief runs to report with step counts."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report recent daily_brief execution runs + per-stage steps from the run registry (read-only)."""
    from hb_assistant.construction.second_brain.run_registry import read_latest_run_registry

    try:
        rows = read_latest_run_registry(run_kind="daily_brief", limit=limit) or []
    except Exception as exc:  # pragma: no cover - defensive
        err = {"command": "second-brain automation execution-status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation execution-status",
        "count": len(rows),
        "runs": rows,
        "guardrails": _EXEC_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# P06: new operator CLI surface per suggested grammar + required JSON shape
_AUTOMATION_CLI_GUARDRAILS = {
    "local_first": True,
    "dry_run_default": True,
    "apply_requires_explicit_confirm": True,
    "read_only_status_diagnostics": True,
    "replay_idempotent_via_registry": True,
    "recovery_commands_redacted": True,
    "no_external_delivery_or_writeback": True,
    "no_raw_content": True,
    "stage_receipts_persisted": "V29_run_steps",
    "automation_execution_still_deferred": False,
    "automation_execution_ready_via_proof": True,
    # P07
    "last_good_updated_only_on_full_success": True,
    "job_health_after_all_outcomes": True,
}


def _parse_date(d: str | None) -> str | None:
    if not d:
        return None
    d = d.strip().lower()
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    from datetime import timezone as _tz

    if d in ("today", "now"):
        return _dt.now(_tz.utc).date().isoformat()
    if d in ("yesterday",):
        return (_dt.now(_tz.utc).date() - _td(days=1)).isoformat()
    return d  # assume iso


@automation_app.command("run")
def automation_run(
    kind: str = typer.Option("daily-brief", "--kind", help="run kind (daily-brief etc)"),
    date: str | None = typer.Option(None, "--date", help="target date (today|YYYY-MM-DD)"),
    catch_up: bool = typer.Option(False, "--catch-up", help="force catch-up mode"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="dry (default) or real"),
    apply: bool = typer.Option(False, "--apply/--no-apply"),
    confirm: bool = typer.Option(False, "--confirm/--no-confirm"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Run (dry or apply+confirm) the automation for a kind/date (P06 grammar)."""
    from hb_assistant.construction.second_brain.automation_executor import (
        ExecutionRequest,
        run_automation_execution,
    )

    brief_date = _parse_date(date)
    mode = "catch_up" if catch_up else "manual"
    eff_apply = (apply or not dry_run) and not dry_run
    eff_confirm = confirm and eff_apply
    req = ExecutionRequest(run_kind=kind.replace("-", "_"), brief_date=brief_date, mode=mode)
    result = run_automation_execution(req, apply=eff_apply, confirm=eff_confirm)
    # Build required P06 shape (stage/retry/lock/replay-elg/recovery-redacted/guardrails)
    stage_sum = {
        "total": len(getattr(result, "stage_receipts", [])),
        "succeeded": sum(
            1 for r in getattr(result, "stage_receipts", []) if r.status == "succeeded"
        ),
        "failed": sum(1 for r in getattr(result, "stage_receipts", []) if r.status == "failed"),
    }
    payload = {
        "command": "second-brain automation run",
        "mode": "apply" if eff_apply and eff_confirm else "dry_run",
        "status": getattr(result, "overall_status", "dry_run"),
        "run_id": getattr(result, "run_registry_id", None),
        "target_date": brief_date,
        "stage_summary": stage_sum,
        "retry_summary": {"note": "see diagnostics for per-run retry receipts"},
        "lock_status": "acquired_or_released_during_run",
        "replay_eligibility": "see diagnostics --run-id for this run",
        "recovery_command_redacted": "hb-assistant second-brain automation run --kind {} --date {} --apply --confirm --json ; hb-assistant second-brain automation replay --run-id <id> --stage failed-only --apply --confirm --json".format(
            kind, brief_date or "today"
        ),
        "guardrails": _AUTOMATION_CLI_GUARDRAILS,
    }
    if hasattr(result, "recovery_recommendation") and result.recovery_recommendation:
        payload["recovery_command_redacted"] = str(
            result.recovery_recommendation.get("suggested_next", ["<redacted>"])[0]
        )[:200]
    # P07 surfaces from executor result (or defaults)
    payload["last_failed_stage"] = getattr(result, "last_failed_stage", None)
    payload["failure_class"] = getattr(result, "failure_class", None)
    payload["retry_exhausted"] = getattr(result, "retry_exhausted", False)
    payload["catch_up_status"] = "yes" if getattr(result, "catch_up", False) else "no"
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    ok = getattr(result, "overall_status", "dry_run") in ("succeeded", "dry_run")
    raise typer.Exit(0 if ok else 3)


@automation_app.command("replay")
def automation_replay(
    run_id: str = typer.Option(..., "--run-id", help="original failed run_registry_id"),
    stage: str = typer.Option(
        "failed-only", "--stage", help="failed-only|failed-and-following|explicit"
    ),
    apply: bool = typer.Option(False, "--apply/--no-apply"),
    confirm: bool = typer.Option(False, "--confirm/--no-confirm"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Replay a prior failed run (P06 grammar; delegates to P05 replay executor path)."""
    from hb_assistant.construction.second_brain.automation_executor import (
        ExecutionRequest,
        run_automation_execution,
    )

    sel = stage
    req = ExecutionRequest(
        run_kind="daily_brief",
        mode="replay",
        original_run_registry_id=run_id,
        replay_selector=sel,  # type: ignore[arg-type]
    )
    result = run_automation_execution(req, apply=apply, confirm=confirm)
    stage_sum = {
        "total": len(getattr(result, "stage_receipts", [])),
        "succeeded": sum(
            1
            for r in getattr(result, "stage_receipts", [])
            if getattr(r, "status", "") == "succeeded"
        ),
    }
    payload = {
        "command": "second-brain automation replay",
        "mode": "apply" if (apply and confirm) else "dry_run",
        "status": getattr(result, "overall_status", "dry_run"),
        "run_id": getattr(result, "run_registry_id", None),
        "target_date": None,
        "stage_summary": stage_sum,
        "retry_summary": {"note": "replay of prior run"},
        "lock_status": "acquired_for_replay",
        "replay_eligibility": "executed",
        "recovery_command_redacted": "hb-assistant second-brain automation diagnostics --run-id {} --json".format(
            run_id
        ),
        "guardrails": _AUTOMATION_CLI_GUARDRAILS,
        # P07
        "last_failed_stage": getattr(result, "last_failed_stage", None),
        "failure_class": getattr(result, "failure_class", None),
        "retry_exhausted": getattr(result, "retry_exhausted", False),
        "catch_up_status": "yes" if getattr(result, "catch_up", False) else "no",
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    ok = getattr(result, "overall_status", "dry_run") in ("succeeded", "dry_run")
    raise typer.Exit(0 if ok else 3)


@automation_app.command("status")
def automation_status(json_out: bool = typer.Option(True, "--json")) -> None:
    """High-level automation status (P06; aggregates registry/lock/eligibility)."""
    from hb_assistant.construction.second_brain.automation_executor import build_automation_status

    try:
        p = build_automation_status()
    except Exception as exc:
        err = {"command": "second-brain automation status", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc
    typer.echo(json.dumps(p, indent=2, default=str) if json_out else str(p))
    raise typer.Exit(0)


@automation_app.command("diagnostics")
def automation_diagnostics(
    run_id: str = typer.Option(..., "--run-id"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Diagnostics for a specific run (P06; stages + retries + elg + redacted rec)."""
    from hb_assistant.construction.second_brain.automation_executor import (
        build_automation_diagnostics,
    )

    try:
        p = build_automation_diagnostics(run_id)
    except Exception as exc:
        err = {"command": "second-brain automation diagnostics", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc
    typer.echo(json.dumps(p, indent=2, default=str) if json_out else str(p))
    raise typer.Exit(0)


@automation_app.command("last-good-run")
def automation_last_good_run(
    kind: str = typer.Option("daily-brief", "--kind"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Last successful run for kind (P06/P07)."""
    from hb_assistant.construction.second_brain.run_registry import last_good_run

    try:
        good = last_good_run(run_kind=kind.replace("-", "_"))
    except Exception as exc:
        err = {"command": "second-brain automation last-good-run", "error": type(exc).__name__}
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    payload = {
        "command": "second-brain automation last-good-run",
        "mode": "status",
        "status": "found" if good else "none",
        "run_id": good.get("run_registry_id") if good else None,
        "target_date": (good.get("started_utc", "").split("T")[0] if good else None),
        "stage_summary": {"note": "use diagnostics --run-id for details"},
        "retry_summary": {},
        "lock_status": "see status",
        "replay_eligibility": "n/a_for_good_run",
        "recovery_command_redacted": "n/a",
        # P07
        "last_failed_stage": None,
        "failure_class": None,
        "retry_exhausted": False,
        "catch_up_status": "n/a_for_good_run",
        "guardrails": _AUTOMATION_CLI_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)
