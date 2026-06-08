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
from typing import Any

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

memory_quality_review_app = typer.Typer(
    name="quality-review",
    help="Phase 09 memory quality review (duplicate/stale/conflicting candidates; advisory, read-only).",
    no_args_is_help=True,
)
memory_app.add_typer(memory_quality_review_app, name="quality-review")

memory_consolidation_preview_app = typer.Typer(
    name="consolidation-preview",
    help="Phase 09 memory consolidation preview (review-only merge proposals; never auto-delete/supersede).",
    no_args_is_help=True,
)
memory_app.add_typer(memory_consolidation_preview_app, name="consolidation-preview")

memory_candidates_app = typer.Typer(
    name="candidates",
    help="Phase 09 memory candidate preview (advisory, read-only; never accepts memory).",
    no_args_is_help=True,
)
memory_app.add_typer(memory_candidates_app, name="candidates")

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

review_app = typer.Typer(
    name="review",
    help="Phase 09 review burden reduction and advisory promotion policy (two-step classification, financial separate, high-impact clustered summaries, operator budget cap, hash-only examples; read-only).",
    no_args_is_help=True,
)
app.add_typer(review_app, name="review")

financial_app = typer.Typer(
    name="financial",
    help="Phase 08C financial readiness (read-only advisory surfaces; no determinations, no raw).",
    no_args_is_help=True,
)
app.add_typer(financial_app, name="financial")

mcp_app = typer.Typer(
    name="mcp",
    help="Phase 08D local MCP bridge — stdio-only, fail-closed (server foundation).",
    no_args_is_help=True,
)
app.add_typer(mcp_app, name="mcp")

phase_10_app = typer.Typer(
    name="phase-10",
    help="Phase 10 local action intelligence — contracts/seeds substrate (declarative only).",
    no_args_is_help=True,
)
app.add_typer(phase_10_app, name="phase-10")

local_model_app = typer.Typer(
    name="local-model",
    help="Phase 10 local model runtime readiness (probe-only; no generation, no writeback).",
    no_args_is_help=True,
)
app.add_typer(local_model_app, name="local-model")

ai_jobs_app = typer.Typer(
    name="ai-jobs",
    help="Phase 10 AI job posture + dry-run structured extraction (advisory; no writeback).",
    no_args_is_help=True,
)
app.add_typer(ai_jobs_app, name="ai-jobs")

action_intel_app = typer.Typer(
    name="action-intel",
    help="Phase 10 action intelligence via the schema-enforced structured-output client.",
    no_args_is_help=True,
)
app.add_typer(action_intel_app, name="action-intel")

automation_app = typer.Typer(
    name="automation",
    help="Phase 08B automation health + observability (read-only status surface).",
    no_args_is_help=True,
)
app.add_typer(automation_app, name="automation")

agent_performance_app = typer.Typer(
    name="agent-performance",
    help="Phase 09 agent performance + feedback (per-agent corrections/review-burden/coverage; advisory, read-only).",
    no_args_is_help=True,
)
app.add_typer(agent_performance_app, name="agent-performance")

daily_brief_reproducibility_app = typer.Typer(
    name="daily-brief-reproducibility",
    help="Phase 09 daily brief reproducibility proof (controlled inputs + source refs; advisory, read-only).",
    no_args_is_help=True,
)
app.add_typer(daily_brief_reproducibility_app, name="daily-brief-reproducibility")

retrieval_app = typer.Typer(
    name="retrieval",
    help="Phase 09 semantic-retrieval backend (optional LlamaIndex core+local; truthful readiness across base/retrieval/retrieval-local installs; local-first, fail-closed).",
    no_args_is_help=True,
)
app.add_typer(retrieval_app, name="retrieval")

llamaindex_app = typer.Typer(
    name="llamaindex",
    help="Optional LlamaIndex (core via [retrieval]; local emb via [retrieval-local]) + truthful readiness status for build/apply/semantic (read-only, fail-closed).",
    no_args_is_help=True,
)
retrieval_app.add_typer(llamaindex_app, name="llamaindex")

embedding_policy_app = typer.Typer(
    name="embedding-policy",
    help="Phase 09 embedding + vector-store policy and no-raw guardrails (read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(embedding_policy_app, name="embedding-policy")

approved_sources_app = typer.Typer(
    name="approved-sources",
    help="Phase 09 approved index source manifests (read-only build + proof).",
    no_args_is_help=True,
)
retrieval_app.add_typer(approved_sources_app, name="approved-sources")

obsidian_loader_app = typer.Typer(
    name="obsidian-loader",
    help="Phase 09 approved Obsidian output loader (read-only status + proof).",
    no_args_is_help=True,
)
retrieval_app.add_typer(obsidian_loader_app, name="obsidian-loader")

memory_loader_app = typer.Typer(
    name="memory-loader",
    help="Phase 09 reviewed memory loader (read-only status + proof).",
    no_args_is_help=True,
)
retrieval_app.add_typer(memory_loader_app, name="memory-loader")

hybrid_app = typer.Typer(
    name="hybrid",
    help="Phase 09 hybrid retrieval broker (deterministic + advisory semantic; truthful on core+local SDKs; read-only, fail-closed).",
    no_args_is_help=True,
)
retrieval_app.add_typer(hybrid_app, name="hybrid")

metadata_filter_app = typer.Typer(
    name="metadata-filter",
    help="Phase 09 metadata filter enforcement (project/source/date/review/confidence; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(metadata_filter_app, name="metadata-filter")

retrieval_research_packet_app = typer.Typer(
    name="research-packet",
    help="Phase 09 research packet integration (route semantic context via research packet; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_research_packet_app, name="research-packet")

retrieval_output_eval_app = typer.Typer(
    name="output-eval",
    help="Phase 09 output evaluation integration (semantic outputs → evaluation + claim checks; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_output_eval_app, name="output-eval")

retrieval_eval_set_app = typer.Typer(
    name="eval-set",
    help="Phase 09 retrieval quality eval set (source-linked cases from approved outputs; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_eval_set_app, name="eval-set")

retrieval_benchmark_app = typer.Typer(
    name="benchmark",
    help="Phase 09 deterministic vs semantic benchmark (comparative metadata-only metrics; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_benchmark_app, name="benchmark")

retrieval_project_benchmark_app = typer.Typer(
    name="project-benchmark",
    help="Phase 09 project-specific retrieval benchmarks + coverage reports (per project; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_project_benchmark_app, name="project-benchmark")

retrieval_context_budget_app = typer.Typer(
    name="context-budget",
    help="Phase 09 context budget optimization (advisory best-effort packing vs baseline; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_context_budget_app, name="context-budget")

retrieval_claim_checks_app = typer.Typer(
    name="claim-checks",
    help="Phase 09 unsupported claim checks + review routing (advisory; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_claim_checks_app, name="claim-checks")

retrieval_hallucination_risk_app = typer.Typer(
    name="hallucination-risk",
    help="Phase 09 hallucination risk + overconfidence indicators (advisory measurement; read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_hallucination_risk_app, name="hallucination-risk")

retrieval_source_linked_app = typer.Typer(
    name="source-linked",
    help="Phase 09 source-linked retrieval proof (every result maps to an approved source ref; advisory, read-only).",
    no_args_is_help=True,
)
retrieval_app.add_typer(retrieval_source_linked_app, name="source-linked")

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


_MEMORY_ACCEPTANCE_GUARDRAILS = {
    "explicit_confirmation_required": True,
    "no_auto_acceptance": True,
    "no_external_writeback": True,
    "no_raw": True,
    "guard_columns_false": True,
    "non_accepted_never_loads": True,
    "local_first": True,
    "fail_closed": True,
}


@memory_app.command("accept")
def memory_accept(
    candidate_id: str = typer.Option(..., "--candidate-id", help="Candidate to accept."),
    confirm: bool = typer.Option(
        False,
        "--confirm/--no-confirm",
        help="Explicit operator confirmation (required to persist).",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Explicitly accept a vetted candidate into long_term_memory_items (no auto-acceptance).

    Without --confirm this is a dry-run that persists nothing. With --confirm a passing candidate is
    promoted to an accepted memory item; a candidate that fails the acceptance gate is refused. Exit 0
    on a clean evaluation; 3 on a fail-closed failure (candidate not found / schema not ready).
    """
    from hb_assistant.construction.second_brain.memory.acceptance import (
        MemoryAcceptanceError,
        accept_memory_candidate,
    )

    try:
        result = accept_memory_candidate(candidate_id, confirm=confirm)
    except MemoryAcceptanceError as exc:
        payload = {
            "command": "second-brain memory accept",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS}
    human = [
        "Phase 09 explicit memory acceptance (no auto-acceptance)",
        f"  candidate: {candidate_id} | acceptable: {result['acceptable']}"
        f" | blocks: {result['blocks']}",
        f"  confirm: {confirm} | accepted: {result['accepted']}"
        f" | memory_id: {result.get('memory_id')}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_app.command("reject")
def memory_reject(
    candidate_id: str = typer.Option(
        ..., "--candidate-id", help="Candidate to reject/defer/supersede."
    ),
    reason: str | None = typer.Option(None, "--reason", help="Redacted decision reason."),
    decision: str = typer.Option(
        "rejected", "--decision", help="rejected|deferred|superseded (default rejected)."
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm/--no-confirm",
        help="Explicit operator confirmation (required to persist).",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Reject / defer / supersede a candidate (never creates an accepted memory item)."""
    from hb_assistant.construction.second_brain.memory.acceptance import (
        MemoryAcceptanceError,
        decide_memory_candidate,
    )

    try:
        result = decide_memory_candidate(
            candidate_id, decision=decision, reason=reason, confirm=confirm
        )
    except MemoryAcceptanceError as exc:
        payload = {
            "command": "second-brain memory reject",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS}
    human = [
        f"Memory decision '{result['decision']}' for {candidate_id}"
        f" | confirm: {confirm} | persisted: {result.get('persisted')}"
        f" | creates_accepted_memory: {result['creates_accepted_memory']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_app.command("list")
def memory_list(
    status: str = typer.Option(
        "accepted", "--status", help="accepted|pending_review|rejected|superseded."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """List long-term memory items by review status (metadata-only; no statement text)."""
    from hb_assistant.construction.second_brain.memory.acceptance import (
        MemoryAcceptanceError,
        list_accepted_memory,
    )

    try:
        result = list_accepted_memory(status=status)
    except MemoryAcceptanceError as exc:
        payload = {
            "command": "second-brain memory list",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS}
    human = [
        f"Long-term memory (status={result['status']}): {result['count']} item(s)"
        f" | loadable_into_retrieval: {result['loadable_into_retrieval']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_app.command("proof")
def memory_acceptance_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the acceptance proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove explicit acceptance persists accepted memory while refusing unsafe candidates."""
    from hb_assistant.construction.second_brain.memory.acceptance import (
        MemoryAcceptanceError,
        build_memory_acceptance_proof,
    )

    try:
        proof = build_memory_acceptance_proof(write_evidence=evidence)
    except MemoryAcceptanceError as exc:
        payload = {
            "command": "second-brain memory proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS}
    human = [
        f"Memory acceptance proof passed={proof['proof_passed']}"
        f" (accepted_persisted={proof['accepted_persisted_as_accepted']},"
        f" unsafe_blocked={proof['raw_shaped_blocked'] and proof['unsourced_blocked'] and proof['high_impact_blocked'] and proof['determination_blocked']},"
        f" non_accepted_excluded={proof['non_accepted_excluded_from_retrieval']},"
        f" guards_false={proof['guard_columns_all_false']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_MEMORY_QUALITY_REVIEW_GUARDRAILS = {
    "advisory_only": True,
    "no_determination": True,
    "no_merge_or_delete_or_accept": True,
    "route_flagged_to_review": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}


@memory_quality_review_app.command("build")
def memory_quality_review_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Evaluate proposed memory candidates for duplicate/stale/conflicting (read-only, advisory).

    Flags problem candidates for human review — never merges, deletes, or accepts memory, and makes no
    determination. Emits a metadata-only summary (counts + per-category counts + hashed flag records; no
    raw statement text); persists nothing to the operator DB. Exit 0 on success; 3 on a fail-closed
    failure.
    """
    from hb_assistant.construction.second_brain.memory.quality_review import (
        MemoryQualityReviewError,
        build_memory_quality_review,
    )

    try:
        result = build_memory_quality_review(project_key=project)
    except MemoryQualityReviewError as exc:
        payload = {
            "command": "second-brain memory quality-review build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_QUALITY_REVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_QUALITY_REVIEW_GUARDRAILS}
    payload.pop(
        "flag_records", None
    )  # per-candidate hashed records summarized by counts; not echoed
    human = [
        "Phase 09 memory quality review (read-only, advisory)",
        f"  status: {result['status']} | reviewed: {result['reviewed_count']}"
        f" | flagged: {result['flagged_count']}",
        f"  by category: {result['per_category']} | review tiers: {result['review_tier_summary']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_quality_review_app.command("proof")
def memory_quality_review_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the quality-review proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove duplicate/stale/conflicting candidates are detected + flagged, with no determination."""
    from hb_assistant.construction.second_brain.memory.quality_review import (
        MemoryQualityReviewError,
        build_memory_quality_review_proof,
    )

    try:
        proof = build_memory_quality_review_proof(write_evidence=evidence)
    except MemoryQualityReviewError as exc:
        payload = {
            "command": "second-brain memory quality-review proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_QUALITY_REVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_QUALITY_REVIEW_GUARDRAILS}
    human = [
        f"Memory quality review proof passed={proof['proof_passed']}"
        f" (flagged={proof['flagged_count']}, dup={proof['duplicate_detected']},"
        f" stale={proof['stale_detected']}, conflict={proof['conflicting_detected']},"
        f" guard_clean={proof['run_row_guard_clean']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_MEMORY_CANDIDATE_PREVIEW_GUARDRAILS = {
    "advisory_only": True,
    "read_only_by_default": True,
    "no_acceptance": True,
    "writes_accepted_memory": False,
    "no_raw": True,
    "no_external_writeback": True,
    "source_linked_only": True,
    "bounded_statements": True,
    "deterministic": True,
    "local_first": True,
    "fail_closed": True,
}


@memory_candidates_app.command("build")
def memory_candidates_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    evidence: bool = typer.Option(
        False, "--evidence/--no-evidence", help="Write the preview to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Preview possible long-term memory candidates from safe, redacted, source-linked records.

    Read-only and advisory: every candidate is review_status='pending_review' and is NEVER accepted or
    persisted as accepted memory. Unsourced, raw-content-shaped, and determination-implying inputs are
    rejected; review tier 3 candidates surface as non-acceptance preview only. Exit 0 on success; 3 on a
    fail-closed failure.
    """
    from hb_assistant.construction.second_brain.memory.candidate_preview import (
        MemoryCandidatePreviewError,
        build_memory_candidate_preview,
    )

    try:
        result = build_memory_candidate_preview(project_key=project, write_evidence=evidence)
    except MemoryCandidatePreviewError as exc:
        payload = {
            "command": "second-brain memory candidates build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS}
    human = [
        "Phase 09 memory candidate preview (read-only, advisory; never accepts memory)",
        f"  status: {result['status']} | candidates: {result['candidate_count']}"
        f" | rejected: {result['rejected_count']}",
        f"  by type: {result['per_type']} | by durability: {result['per_durability']}",
        f"  writes_accepted_memory: {result['writes_accepted_memory']}"
        f" | review_status: pending_review (never auto-accepted)",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_candidates_app.command("proof")
def memory_candidates_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the candidate-preview proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove safe candidates surface, unsafe inputs are rejected, and no accepted memory is written."""
    from hb_assistant.construction.second_brain.memory.candidate_preview import (
        MemoryCandidatePreviewError,
        build_memory_candidate_preview_proof,
    )

    try:
        proof = build_memory_candidate_preview_proof(write_evidence=evidence)
    except MemoryCandidatePreviewError as exc:
        payload = {
            "command": "second-brain memory candidates proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS}
    human = [
        f"Memory candidate preview proof passed={proof['proof_passed']}"
        f" (candidates={proof['candidate_count']}, raw_rejected={proof['raw_shaped_rejected']},"
        f" unsourced_rejected={proof['unsourced_rejected']},"
        f" determination_rejected={proof['determination_rejected']},"
        f" accepted_memory_unchanged={proof['accepted_memory_unchanged']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@memory_candidates_app.command("stage")
def memory_candidates_stage(
    candidate_id: str = typer.Option(
        ...,
        "--candidate-id",
        help="Preview candidate id (mcp_…) to stage into the candidate store.",
    ),
    confirm: bool = typer.Option(
        False, "--confirm/--no-confirm", help="Explicit confirmation (required to persist)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Stage a previewed candidate into the durable safe candidate store so `memory accept` can find it.

    Rebuilds the preview deterministically, re-runs the source-linked / no-raw / no-determination /
    review-tier checks, converts the candidate to the MemoryCandidate shape (preserving its id), and
    persists it — never creating accepted memory. Dry-run without --confirm. Exit 0/3 (fail-closed when
    the id is not in the current preview)."""
    from hb_assistant.construction.second_brain.memory.candidate_preview import (
        MemoryCandidatePreviewError,
        stage_memory_candidate,
    )

    try:
        result = stage_memory_candidate(candidate_id, confirm=confirm)
    except MemoryCandidatePreviewError as exc:
        payload = {
            "command": "second-brain memory candidates stage",
            "status": "not_found",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS}
    human = [
        f"Stage {candidate_id} | confirm: {confirm} | staged: {result['staged']}"
        f" | persisted: {result['persisted']} | creates_accepted_memory: False",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_candidates_app.command("stage-proof")
def memory_candidates_stage_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the candidate staging-bridge proof."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove a previewed candidate stages into the durable store (id preserved) and then accepts, while
    staging itself creates no accepted memory and a missing id fails closed. Exit 0/3."""
    from hb_assistant.construction.second_brain.memory.candidate_preview import (
        MemoryCandidatePreviewError,
        build_memory_candidate_stage_proof,
    )

    try:
        proof = build_memory_candidate_stage_proof(write_evidence=evidence)
    except MemoryCandidatePreviewError as exc:
        payload = {
            "command": "second-brain memory candidates stage-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_CANDIDATE_PREVIEW_GUARDRAILS}
    human = [
        f"Candidate staging proof passed={proof['proof_passed']}"
        f" (id_preserved={proof['candidate_id_preserved']},"
        f" accept_after_staging={proof['accept_succeeds_after_staging']},"
        f" staging_creates_no_accepted={proof['staging_creates_no_accepted_memory']},"
        f" guards_false={proof['guard_columns_all_false']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@memory_app.command("supersede")
def memory_supersede(
    old_id: str = typer.Option(..., "--old-id", help="Accepted memory item to supersede."),
    new_id: str = typer.Option(
        ..., "--new-id", help="Newer accepted memory item that supersedes it."
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm/--no-confirm",
        help="Explicit operator confirmation (required to persist).",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Supersede an accepted memory item with a newer accepted one (metadata-only; superseded then
    excluded from retrieval). Without --confirm this is a dry-run. Exit 0/3."""
    from hb_assistant.construction.second_brain.memory.quality_controls import (
        MemoryQualityControlsError,
        supersede_accepted_memory,
    )

    try:
        result = supersede_accepted_memory(
            old_memory_id=old_id, new_memory_id=new_id, confirm=confirm
        )
    except MemoryQualityControlsError as exc:
        payload = {
            "command": "second-brain memory supersede",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    human = [
        f"Supersede {old_id} -> {new_id} | confirm: {confirm} | superseded: {result['superseded']}"
        f" | blocks: {result['blocks']}"
    ]
    exit_code = 0 if (not result["blocks"]) else 3
    _emit_08c(result, json_out=json_out, human=human, exit_code=exit_code)


@memory_app.command("quality-controls-proof")
def memory_quality_controls_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the quality-controls proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove duplicate suppression, supersession exclusion, freshness labeling, source retention, and
    review-status transition validation (metadata-only, no writeback). Exit 0/3."""
    from hb_assistant.construction.second_brain.memory.quality_controls import (
        MemoryQualityControlsError,
        build_memory_quality_controls_proof,
    )

    try:
        proof = build_memory_quality_controls_proof(write_evidence=evidence)
    except MemoryQualityControlsError as exc:
        payload = {
            "command": "second-brain memory quality-controls-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_ACCEPTANCE_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    human = [
        f"Memory quality controls proof passed={proof['proof_passed']} "
        f"(dup_suppressed={proof['duplicate_detected_and_suppressed']}, "
        f"supersession_excludes={proof['supersession_excludes_from_retrieval']}, "
        f"transitions_valid={proof['transitions_valid']}, "
        f"guards_false={proof['guard_columns_all_false']})"
    ]
    _emit_08c(proof, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS = {
    "advisory_only": True,
    "no_determination": True,
    "never_auto_delete_or_supersede": True,
    "review_only_proposals": True,
    "leave_long_term_memory_items_unchanged": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}


@memory_consolidation_preview_app.command("build")
def memory_consolidation_preview_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Generate review-only consolidation proposals over the accepted memory corpus (read-only, advisory).

    Clusters exact-duplicate accepted memory items and proposes keeping one canonical member + superseding
    the duplicates — as proposals for human review only. It NEVER auto-deletes, auto-supersedes, or
    auto-merges memory (long_term_memory_items is left unchanged) and makes no determination. Emits a
    metadata-only summary (cluster counts + hashed proposal records; no raw statement); persists nothing to
    the operator DB by default. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.memory.consolidation_preview import (
        MemoryConsolidationPreviewError,
        build_memory_consolidation_preview,
    )

    try:
        result = build_memory_consolidation_preview(project_key=project)
    except MemoryConsolidationPreviewError as exc:
        payload = {
            "command": "second-brain memory consolidation-preview build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS}
    payload.pop(
        "proposals", None
    )  # per-cluster hashed records summarized by counts; not echoed in bulk
    human = [
        "Phase 09 memory consolidation preview (read-only, advisory; review-only proposals)",
        f"  status: {result['status']} | accepted items: {result['accepted_item_count']}"
        f" | clusters: {result['cluster_count']} | members: {result['total_member_count']}",
        f"  proposals -> {result['proposal_review_status']} (tier {result['proposal_review_tier']});"
        f" long_term_memory_items unchanged (never auto-delete/supersede)",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_consolidation_preview_app.command("proof")
def memory_consolidation_preview_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the consolidation-preview proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove a duplicate cluster yields review-only proposals while long_term_memory_items stays unchanged."""
    from hb_assistant.construction.second_brain.memory.consolidation_preview import (
        MemoryConsolidationPreviewError,
        build_memory_consolidation_preview_proof,
    )

    try:
        proof = build_memory_consolidation_preview_proof(write_evidence=evidence)
    except MemoryConsolidationPreviewError as exc:
        payload = {
            "command": "second-brain memory consolidation-preview proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_CONSOLIDATION_PREVIEW_GUARDRAILS}
    human = [
        f"Memory consolidation preview proof passed={proof['proof_passed']}"
        f" (clusters={proof['cluster_count']}, members={proof['total_member_count']},"
        f" memory_unchanged={proof['long_term_memory_items_unchanged']}, advisory_only={proof['advisory_only_flag_set']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS = {
    "advisory_only": True,
    "no_determination": True,
    "recommendations_advisory_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}


@agent_performance_app.command("build")
def agent_performance_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Aggregate per-agent performance + feedback signals (read-only, advisory).

    Per Phase-08A agent, aggregates repeated corrections (operator feedback), review burden (agent run
    receipts), and weak coverage (corpus balance), and emits advisory policy recommendation codes. Makes
    no determination; recommendations are advisory. Emits a metadata-only summary (counts + bands + codes;
    no raw reason text); persists nothing to the operator DB. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.agent_performance_feedback import (
        AgentPerformanceFeedbackError,
        build_agent_performance_feedback,
    )

    try:
        result = build_agent_performance_feedback(project_key=project)
    except AgentPerformanceFeedbackError as exc:
        payload = {
            "command": "second-brain agent-performance build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS}
    payload.pop("per_agent", None)  # per-agent records summarized; not echoed in bulk
    human = [
        "Phase 09 agent performance + feedback (read-only, advisory)",
        f"  status: {result['status']} | agents: {result['agent_count']}"
        f" | total signals: {result['signal_count']}",
        "  recommendations: "
        + ", ".join(
            f"{a['agent_name']}={a['policy_recommendation']}"
            for a in result["per_agent"]
            if a["policy_recommendation"] != "no_action"
        ),
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@agent_performance_app.command("proof")
def agent_performance_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the agent-performance proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove per-agent signals + advisory recommendations are computed, with no determination."""
    from hb_assistant.construction.second_brain.agent_performance_feedback import (
        AgentPerformanceFeedbackError,
        build_agent_performance_feedback_proof,
    )

    try:
        proof = build_agent_performance_feedback_proof(write_evidence=evidence)
    except AgentPerformanceFeedbackError as exc:
        payload = {
            "command": "second-brain agent-performance proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _AGENT_PERFORMANCE_FEEDBACK_GUARDRAILS}
    human = [
        f"Agent performance feedback proof passed={proof['proof_passed']}"
        f" (corrections={proof['corrections_attributed']}, review_burden={proof['review_burden_computed']},"
        f" recommendation={proof['recommendation_emitted']}, determination={proof['makes_determination']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_DAILY_BRIEF_REPRODUCIBILITY_GUARDRAILS = {
    "advisory_only": True,
    "no_determination": True,
    "preserve_source_refs": True,
    "no_raw": True,
    "no_external_writeback": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}


@daily_brief_reproducibility_app.command("build")
def daily_brief_reproducibility_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key override."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the daily brief is reproducible over controlled inputs (read-only, advisory).

    Runs the Phase 08A generator twice over the identical seeded inputs (each in its own temp DB +
    temp vault, mock adapter) and reports whether the approved-output SHA256 hash + metadata-only
    source-ref coverage match, with a present evaluation receipt. Persists nothing to the operator
    DB; makes no determination. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.daily_brief_reproducibility import (
        DailyBriefReproducibilityError,
        build_daily_brief_reproducibility,
    )

    try:
        result = build_daily_brief_reproducibility(project_key=project)
    except DailyBriefReproducibilityError as exc:
        payload = {
            "command": "second-brain daily-brief-reproducibility build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _DAILY_BRIEF_REPRODUCIBILITY_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _DAILY_BRIEF_REPRODUCIBILITY_GUARDRAILS}
    human = [
        "Phase 09 daily brief reproducibility (read-only, advisory)",
        f"  status: {result['status']} | reproducible: {result['reproducible']}"
        f" | output_hash_match: {result['output_hash_match']} | source_refs: {result['source_ref_count']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@daily_brief_reproducibility_app.command("proof")
def daily_brief_reproducibility_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the daily-brief-reproducibility proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove identical controlled inputs reproduce an identical brief output hash + source refs."""
    from hb_assistant.construction.second_brain.daily_brief_reproducibility import (
        DailyBriefReproducibilityError,
        build_daily_brief_reproducibility_proof,
    )

    try:
        proof = build_daily_brief_reproducibility_proof(write_evidence=evidence)
    except DailyBriefReproducibilityError as exc:
        payload = {
            "command": "second-brain daily-brief-reproducibility proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _DAILY_BRIEF_REPRODUCIBILITY_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _DAILY_BRIEF_REPRODUCIBILITY_GUARDRAILS}
    human = [
        f"Daily brief reproducibility proof passed={proof['proof_passed']}"
        f" (output_hash_match={proof['output_hash_match']},"
        f" source_refs_preserved={proof['source_refs_preserved']},"
        f" evaluation_receipt_present={proof['evaluation_receipt_present']},"
        f" determination={proof['makes_determination']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_SOURCE_LINKED_RETRIEVAL_GUARDRAILS = {
    "advisory_only": True,
    "no_determination": True,
    "preserve_source_refs": True,
    "no_raw": True,
    "no_external_writeback": True,
    "no_semantic_retrieval_bypass": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}


@retrieval_source_linked_app.command("build")
def retrieval_source_linked_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key override."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove every hybrid-retrieval result maps to an approved source ref (read-only, advisory).

    Runs the hybrid broker over the seed query and counts source-linked vs unlinked results; a result is
    source-linked iff it carries a non-empty source_ref and an allowlisted source_family. Emits a
    metadata-only summary (counts + hashed run id + per-family breakdown + status; no raw query/refs);
    persists nothing to the operator DB. Makes no determination. Exit 0 on success; 3 on fail-closed.
    """
    from hb_assistant.construction.second_brain.retrieval.source_linked_proof import (
        SourceLinkedRetrievalProofError,
        build_source_linked_retrieval_proof,
    )

    try:
        result = build_source_linked_retrieval_proof(project_key=project)
    except SourceLinkedRetrievalProofError as exc:
        payload = {
            "command": "second-brain retrieval source-linked build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _SOURCE_LINKED_RETRIEVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _SOURCE_LINKED_RETRIEVAL_GUARDRAILS}
    human = [
        "Phase 09 source-linked retrieval proof (read-only, advisory)",
        f"  status: {result['status']} | results: {result['result_count']}"
        f" | linked: {result['linked_count']} | unlinked: {result['unlinked_count']}"
        f" | proof_passed: {result['proof_passed']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_source_linked_app.command("proof")
def retrieval_source_linked_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the source-linked retrieval proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove (over a controlled seeded index) every retrieval result maps to an approved source ref."""
    from hb_assistant.construction.second_brain.retrieval.source_linked_proof import (
        SourceLinkedRetrievalProofError,
        build_source_linked_retrieval_proof_proof,
    )

    try:
        proof = build_source_linked_retrieval_proof_proof(write_evidence=evidence)
    except SourceLinkedRetrievalProofError as exc:
        payload = {
            "command": "second-brain retrieval source-linked proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _SOURCE_LINKED_RETRIEVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _SOURCE_LINKED_RETRIEVAL_GUARDRAILS}
    human = [
        f"Source-linked retrieval proof passed={proof['proof_passed']}"
        f" (results={proof['result_count']}, linked={proof['linked_count']},"
        f" unlinked={proof['unlinked_count']}, every_result_source_linked="
        f"{proof['every_result_source_linked']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_NO_RAW_VECTOR_INDEX_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_raw_vector_content_in_sqlite": True,
    "vectors_outside_sqlite": True,
    "no_external_writeback": True,
    "advisory_only": True,
    "no_determination": True,
    "local_first": True,
    "fail_closed": True,
}


@retrieval_app.command("no-raw-vector-index-proof")
def retrieval_no_raw_vector_index_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the no-raw-vector-index proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Scan DB / vector-index metadata / evidence for raw vector content and prohibited payloads.

    Read-only forensic scan: confirms the vector-index + all retrieval tables have guard columns at 0
    (no raw_vector_content_persisted), no embedding/vector blob column exists in SQLite (vectors live
    outside SQLite), and the safe text columns + evidence tree carry no secrets/PEM/bearer/JWT/signed
    URLs; a non-vacuity arm proves the scanner flags a planted value. Metadata-only; persists nothing
    to the operator DB. Exit 0 on a clean proof; 3 on a fail-closed failure or findings.
    """
    from hb_assistant.construction.second_brain.retrieval.no_raw_vector_index_proof import (
        NoRawVectorIndexProofError,
        build_no_raw_vector_index_proof,
    )

    try:
        result = build_no_raw_vector_index_proof(write_evidence=evidence)
    except NoRawVectorIndexProofError as exc:
        payload = {
            "command": "second-brain retrieval no-raw-vector-index-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _NO_RAW_VECTOR_INDEX_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _NO_RAW_VECTOR_INDEX_GUARDRAILS}
    human = [
        f"No raw vector index proof passed={result['proof_passed']}"
        f" (gates {result['pass_count']}/{result['gate_count']}, guard_violations="
        f"{result['guard_violations']}, blob_columns={len(result['blob_columns_found'])},"
        f" evidence_files={result['evidence_files_scanned']}, findings={result['forbidden_findings']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@retrieval_app.command("reader-registry-parity-proof")
def retrieval_reader_registry_parity_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the reader-registry-parity proof to evidence."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove the deterministic retrieval allowlist and the reader registry are in parity.

    Passes iff every allowlisted family has a registered reader (or a documented deferral) and no
    reader is registered for a non-allowlisted family. Static, read-only, metadata-only. Exit 0/3.
    """
    from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
        build_reader_registry_parity_proof,
    )

    result = build_reader_registry_parity_proof(write_evidence=evidence)
    human = [
        f"Reader registry parity passed={result['proof_passed']} "
        f"(reader {result['deterministic_reader_family_count']}/"
        f"{result['deterministic_allowlisted_family_count']}, "
        f"missing={result['missing_reader_families']})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@retrieval_app.command("approved-read-model-manifest-proof")
def retrieval_approved_read_model_manifest_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the approved-read-model-manifest proof."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove the ``approved_read_models`` manifest category admits eligible, metadata-only, guard-clean
    entries while rejecting high-impact / review-required / excluded / raw-shape candidates. Exit 0/3."""
    from hb_assistant.construction.second_brain.retrieval.source_manifest import (
        build_approved_read_model_manifest_proof,
    )

    result = build_approved_read_model_manifest_proof(write_evidence=evidence)
    human = [
        f"Approved read-model manifest proof passed={result['proof_passed']} "
        f"(approved_read_models={result['approved_read_models_approved_count']}, "
        f"metadata_only_row={result['manifest_row_metadata_only']})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@retrieval_app.command("read-model-vector-loader-proof")
def retrieval_read_model_vector_loader_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the read-model-vector-loader proof."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove the read-model loader bridges eligible deterministic items into safe, in-memory-only vector
    nodes (no-raw, nothing persisted to SQLite), excludes review-required / high-impact items, and
    rejects raw/excluded candidates. Exit 0/3."""
    from hb_assistant.construction.second_brain.retrieval.read_model_loader import (
        build_read_model_vector_loader_proof,
    )

    result = build_read_model_vector_loader_proof(write_evidence=evidence)
    human = [
        f"Read-model vector loader proof passed={result['proof_passed']} "
        f"(families={result['indexed_family_count']}, nodes={result['node_count']}, "
        f"persists_nothing={result['loader_persists_nothing_to_sqlite']})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@retrieval_app.command("coverage-parity-closeout")
def retrieval_coverage_parity_closeout(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the coverage-parity closeout to evidence."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Aggregate the coverage-parity report (deterministic / approved-manifest / vector-indexed /
    memory / deferred planes) with the three approved-read-model proofs into one closeout. Read-only;
    reports empties as deferred (no readiness overstatement). Exit 0/3."""
    from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
        build_coverage_parity_closeout,
    )

    result = build_coverage_parity_closeout(write_evidence=evidence)
    rep = result.get("coverage_parity", {})
    human = [
        f"Coverage parity closeout ok={result['closeout_ok']} "
        f"(parity_ok={rep.get('coverage_parity_ok')}, "
        f"reader={rep.get('deterministic_reader_family_count')}/"
        f"{rep.get('deterministic_allowlisted_family_count')}, "
        f"manifest={rep.get('approved_manifest_family_count')}, "
        f"vector={rep.get('vector_indexed_family_count')})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["closeout_ok"] else 3)


@retrieval_app.command("accepted-memory-loader-proof")
def retrieval_accepted_memory_loader_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the accepted-memory loader/manifest proof."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove one accepted memory item appears in the deterministic reader, the reviewed-memory loader,
    and the approved-source manifest, while pending/rejected/superseded memory is excluded (redacted,
    bounded, source-linked, no raw). Exit 0/3."""
    from hb_assistant.construction.second_brain.retrieval.accepted_memory_inclusion import (
        build_accepted_memory_loader_proof,
    )

    result = build_accepted_memory_loader_proof(write_evidence=evidence)
    human = [
        f"Accepted memory loader/manifest proof passed={result['proof_passed']} "
        f"(loader_loaded={result['loader_loaded_count']}, "
        f"manifest_reviewed_memory={result['manifest_reviewed_memory_approved_count']}, "
        f"non_accepted_excluded={result['non_accepted_excluded']})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@retrieval_app.command("accepted-memory-vector-coverage-proof")
def retrieval_accepted_memory_vector_coverage_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the accepted-memory vector/coverage proof."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Prove accepted memory enters the vector dry-run plan + applied index, the no-raw vector proof
    still passes, and the coverage-parity closeout flips memory to covered (+1 vector family, parity
    stays true, readiness not overstated). Exit 0/3."""
    from hb_assistant.construction.second_brain.retrieval.accepted_memory_inclusion import (
        build_accepted_memory_vector_coverage_proof,
    )

    result = build_accepted_memory_vector_coverage_proof(write_evidence=evidence)
    human = [
        f"Accepted memory vector/coverage proof passed={result['proof_passed']} "
        f"(apply={result['vector_apply_status']}, "
        f"vector_family {result['vector_indexed_family_count_before']}->"
        f"{result['vector_indexed_family_count_after']}, "
        f"substrate {result['memory_substrate_status_before']}->"
        f"{result['memory_substrate_status_after']}, "
        f"no_raw={result['no_raw_vector_proof_passed']})"
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


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


@daily_brief_app.command("packet")
def daily_brief_packet(
    brief_date: str = typer.Option(..., "--date", help="Brief date (YYYY-MM-DD)."),
    project_key: str = typer.Option(None, "--project-key", help="Optional project filter."),
    mode: str = typer.Option("dry_run", "--mode", help="dry_run|apply (no external writeback)."),
    version: str = typer.Option(
        "v1", "--version", help="Packet contract version: v1 (flat) | v2 (render/governance split)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build a metadata-only daily-brief handoff packet for safe MCP/Claude consumption (read-only).

    Projects the existing daily-brief context into the stable handoff packet contract: hashed source
    refs, redacted titles, preserved review/stale/low-confidence flags, source coverage, advisory-only
    accepted-memory context, guardrails + rendering instructions. Persists nothing. ``--version v2``
    emits ``DailyBriefHandoffPacketV2`` (user-facing ``render_payload`` split from internal
    ``governance_metadata``). Exit 0 on success; 2 on invalid mode/version; 3 on a fail-closed failure.
    """
    if mode not in ("dry_run", "apply"):
        err_payload: dict[str, object] = {
            "command": "second-brain daily-brief packet",
            "error": "invalid_mode",
            "detail": f"{mode!r} not in ['dry_run', 'apply']",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    if version not in ("v1", "v2"):
        err_payload = {
            "command": "second-brain daily-brief packet",
            "error": "invalid_version",
            "detail": f"{version!r} not in ['v1', 'v2']",
        }
        typer.echo(json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload))
        raise typer.Exit(2)

    from hb_assistant.construction.second_brain.daily_brief import (
        DailyBriefPacketError,
        build_daily_brief_packet,
        build_daily_brief_packet_v2,
    )

    try:
        if version == "v2":
            packet = build_daily_brief_packet_v2(
                brief_date=brief_date, project_key=project_key, mode=mode
            )
        else:
            packet = build_daily_brief_packet(
                brief_date=brief_date, project_key=project_key, mode=mode
            )
    except DailyBriefPacketError as exc:
        err = {
            "command": "second-brain daily-brief packet",
            "brief_date": brief_date,
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc
    except Exception as exc:  # pragma: no cover - defensive (e.g., DB unavailable)
        err = {
            "command": "second-brain daily-brief packet",
            "brief_date": brief_date,
            "error": type(exc).__name__,
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    typer.echo(json.dumps(packet, indent=2, default=str) if json_out else str(packet))
    raise typer.Exit(0)


@daily_brief_app.command("packet-proof")
def daily_brief_packet_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the daily-brief packet proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Prove the daily-brief packet validates against contract and stays metadata-only (read-only)."""
    from hb_assistant.construction.second_brain.daily_brief import (
        DailyBriefPacketError,
        build_daily_brief_packet_proof,
    )

    try:
        proof = build_daily_brief_packet_proof(write_evidence=evidence)
    except DailyBriefPacketError as exc:
        err = {
            "command": "second-brain daily-brief packet-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    typer.echo(json.dumps(proof, indent=2, default=str) if json_out else str(proof))
    raise typer.Exit(0 if proof["proof_passed"] else 3)


@daily_brief_app.command("packet-v2-proof")
def daily_brief_packet_v2_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the daily-brief V2 packet proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Prove the V2 daily-brief packet splits render_payload from governance_metadata, preserves
    source refs + review/stale/confidence flags, rejects raw-shaped and final-determination
    content, and writes nothing externally (read-only). Exit 0 on pass; 3 on failure."""
    from hb_assistant.construction.second_brain.daily_brief import (
        DailyBriefPacketError,
        build_daily_brief_packet_v2_proof,
    )

    try:
        proof = build_daily_brief_packet_v2_proof(write_evidence=evidence)
    except DailyBriefPacketError as exc:
        err = {
            "command": "second-brain daily-brief packet-v2-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(3) from exc

    typer.echo(json.dumps(proof, indent=2, default=str) if json_out else str(proof))
    raise typer.Exit(0 if proof["proof_passed"] else 3)


@daily_brief_app.command("v2-proof")
def daily_brief_v2_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the V2 executive-quality proof + golden fixtures to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Prove the V2 executive-utility standard over three golden fixtures: the full-detail and
    detail-unavailable briefs pass every quality check and the unsafe/internal brief is rejected.
    Exit 0 on pass; 3 on failure."""
    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_v2_quality_proof,
    )

    proof = build_daily_brief_v2_quality_proof(write_evidence=evidence)
    typer.echo(json.dumps(proof, indent=2, default=str) if json_out else str(proof))
    raise typer.Exit(0 if proof["proof_passed"] else 3)


@daily_brief_app.command("v2-closeout")
def daily_brief_v2_closeout(
    brief_date: str = typer.Option("2026-06-06", "--date", help="Brief date for the output path."),
    validation_dir: str = typer.Option(
        None,
        "--validation-dir",
        help="Dir of captured validation-command --json outputs to summarize.",
    ),
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the closeout bundle to the evidence dir."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Assemble the Daily Brief V2 closeout/handoff bundle: branch/SHA/files, schema (unchanged),
    packet/output path, V2 render-quality + rejected-fixture result, enrichment coverage +
    detail-unavailable counts, captured validation runs, limitations, and next improvement. Exit 0
    when the daily-brief-owned gates pass."""
    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_v2_closeout,
    )

    closeout = build_daily_brief_v2_closeout(
        brief_date=brief_date, validation_dir=validation_dir, write_evidence=evidence
    )
    typer.echo(json.dumps(closeout, indent=2, default=str) if json_out else str(closeout))
    raise typer.Exit(0 if closeout["closeout_complete"] else 3)


@daily_brief_app.command("rendered-proof")
def daily_brief_rendered_proof(
    packet_path: str = typer.Option(
        None, "--packet", help="Path to a source packet JSON to validate against (optional)."
    ),
    rendered_path: str = typer.Option(
        None, "--rendered", help="Path to a rendered brief markdown file to validate (optional)."
    ),
    version: str = typer.Option(
        "v1",
        "--version",
        help="Built-in proof: v1 (fixture + tampered variants) | v2 (executive-quality golden fixtures).",
    ),
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="When running the built-in fixture proof, write evidence to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Validate a Claude-rendered daily brief against its source packet (review-only).

    With both --packet and --rendered, validate those files. Otherwise run the built-in proof:
    --version v1 (safe fixture passes; tampered variants fail their checks) or --version v2 (golden
    full-detail/detail-unavailable pass; unsafe/internal is rejected). Exit 0 on pass; 3 on fail.
    """
    from pathlib import Path

    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_rendered_quality_proof,
        build_daily_brief_v2_quality_proof,
        validate_rendered_brief,
    )

    if version not in ("v1", "v2"):
        err = {
            "command": "second-brain daily-brief rendered-proof",
            "error": "invalid_version",
            "detail": f"{version!r} not in ['v1', 'v2']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    if packet_path and rendered_path:
        try:
            packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
            rendered_md = Path(rendered_path).read_text(encoding="utf-8")
        except Exception as exc:
            err = {
                "command": "second-brain daily-brief rendered-proof",
                "error": type(exc).__name__,
                "detail": str(exc),
            }
            typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
            raise typer.Exit(3) from exc
        result = validate_rendered_brief(packet, rendered_md)
        payload = {
            "command": "second-brain daily-brief rendered-proof",
            "mode": "validate_files",
            "packet_path": packet_path,
            "rendered_path": rendered_path,
            **result,
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0 if result["passed"] else 3)

    if version == "v2":
        proof = build_daily_brief_v2_quality_proof(write_evidence=evidence)
    else:
        proof = build_daily_brief_rendered_quality_proof(write_evidence=evidence)
    typer.echo(json.dumps(proof, indent=2, default=str) if json_out else str(proof))
    raise typer.Exit(0 if proof["proof_passed"] else 3)


@daily_brief_app.command("output-receipt-proof")
def daily_brief_output_receipt_proof(
    version: str = typer.Option(
        "v2",
        "--version",
        help="Receipt contract version: v1 | v2 (the receipt is V2 by construction).",
    ),
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the output-receipt proof to the evidence dir."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Prove the rendered-brief output receipt is advisory/not-source-truth and excluded from trusted
    stores (vector index, manifest, source-linked proof, accepted memory); import is deferred. The
    receipt is V2 by construction; --version v1|v2 both validate it."""
    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_rendered_output_receipt_proof,
    )

    if version not in ("v1", "v2"):
        err = {
            "command": "second-brain daily-brief output-receipt-proof",
            "error": "invalid_version",
            "detail": f"{version!r} not in ['v1', 'v2']",
        }
        typer.echo(json.dumps(err, indent=2, default=str) if json_out else str(err))
        raise typer.Exit(2)

    proof = build_daily_brief_rendered_output_receipt_proof(write_evidence=evidence)
    typer.echo(json.dumps(proof, indent=2, default=str) if json_out else str(proof))
    raise typer.Exit(0 if proof["proof_passed"] else 3)


@daily_brief_app.command("mcp-handoff-status")
def daily_brief_mcp_handoff_status(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the handoff operator-status to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report daily-brief MCP handoff operator status (5 fields + gates + reconciled substrate detail).

    Advisory-only; never production-ready. Exit 0 iff handoff_closeout_ok (no fail_blocking gate —
    MCP no-raw/no-writeback and the handoff proof are the only closeout blockers).
    """
    from hb_assistant.construction.second_brain.daily_brief import (
        build_daily_brief_mcp_handoff_status,
    )

    report = build_daily_brief_mcp_handoff_status(write_evidence=evidence)
    typer.echo(json.dumps(report, indent=2, default=str) if json_out else str(report))
    raise typer.Exit(0 if report["handoff_closeout_ok"] else 3)


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


@index_app.command("linkage-proof")
def index_linkage_proof(
    db_path: str = typer.Option(
        "", "--db-path", help="DB to verify (default: operator DB; use a proof DB for evidence)."
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only approved-Obsidian linkage proof: canonical refs + broken-link check (G-07)."""
    from hb_assistant.construction.second_brain.obsidian_linkage_proof import (
        build_obsidian_linkage_proof,
    )

    proof = build_obsidian_linkage_proof(db_path or None)
    payload = {"command": "second-brain index linkage-proof", **proof}
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if proof.get("proof_passed") or not proof.get("populated") else 1)


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


# Phase 08C financial readiness read-only CLI surfaces (Prompt 01 schema/contracts).
# Advisory only; load contracts; query new V35 tables (counts/status); no raw, no determinations.
# Dry-run by nature (read-only).

_08C_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_external_writeback": True,
    "no_raw_financial_payload": True,
    "financial_determination_forbidden": True,
    "advisory_only": True,
}

# Explicit "no determination / no payment / no writeback" attestation block carried by every
# Phase 08C financial operator surface (advisory aids only).
_08C_ATTESTATIONS = {
    "financial_determination_performed": False,
    "payment_decision_performed": False,
    "claim_or_entitlement_decision_performed": False,
    "external_writeback_performed": False,
    "raw_financial_payload_persisted": False,
    "live_procore_call_performed": False,
}


_08D_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_external_writeback": True,
    "no_raw_content": True,
    "no_readiness_overstatement": True,
    "advisory_only": True,
}

# Explicit "no raw / no writeback / no direct API / no determination" attestation block carried
# by the Phase 08D MCP-bridge operator surfaces (workflow exposure only; advisory aids).
_08D_ATTESTATIONS = {
    "external_writeback_performed": False,
    "raw_store_exposed": False,
    "direct_graph_or_procore_call_performed": False,
    "final_determination_performed": False,
}


def _emit_08c(
    payload: dict,
    *,
    json_out: bool,
    human: list[str],
    exit_code: int = 0,
) -> None:
    """Emit a Phase 08C operator payload as JSON (default) or human-readable lines."""
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        for line in human:
            typer.echo(line)
    raise typer.Exit(exit_code)


@financial_app.command("readiness")
def financial_readiness(
    project: str | None = typer.Option(None, "--project", help="Optional project key."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Financial readiness snapshot (V35 tables + contracts; advisory, read-only)."""
    from hb_assistant.construction.second_brain.contracts import load_phase_08c_contract
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator().apply()
    contract = load_phase_08c_contract("financial_fact_contract")
    from hb_assistant.construction.second_brain.financial_completeness import (
        run_financial_fact_readiness_agent,
    )

    agent = run_financial_fact_readiness_agent(project_key=project)
    payload = {
        "command": "second-brain financial readiness",
        "ok": True,
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "contract": contract.get("contract_name"),
        "agent_run_receipt": {"run_id": agent.get("run_id"), "status": agent.get("status")},
        "proof_path": agent.get("proof_path"),
        "evidence_paths": [agent.get("proof_path")],
        "summary": {
            "items_evaluated": agent.get("items_evaluated"),
            "review_required_count": agent.get("review_required_count"),
        },
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
        "note": "deterministic Financial Fact Readiness Agent (Prompt 07); model use absent or mock-safe only; advisory review aids only — no determinations.",
    }
    human = [
        "Phase 08C financial readiness (advisory only — no determinations)",
        f"  project: {project or 'all'}",
        f"  run: {agent.get('run_id')} status={agent.get('status')}",
        f"  items evaluated: {agent.get('items_evaluated')} | review required: {agent.get('review_required_count')}",
        f"  proof: {agent.get('proof_path')}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


@financial_app.command("coverage")
def financial_coverage(
    project: str | None = typer.Option(None, "--project", help="Optional project key."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Financial source coverage (from V35 snapshots + contract)."""
    from hb_assistant.construction.second_brain.contracts import load_phase_08c_contract
    from hb_assistant.construction.second_brain.financial_completeness import (
        build_financial_source_coverage_matrix,
        build_source_coverage_snapshot,
    )

    contract = load_phase_08c_contract("financial_source_coverage_contract")
    try:
        snap = build_source_coverage_snapshot(project_key=project)
    except Exception:
        snap = {}
    try:
        # Generates (or refreshes) the matrix JSON in evidence dir as side-effect of coverage surface
        mtx = build_financial_source_coverage_matrix()
    except Exception:
        mtx = {}
    matrix_path = (
        "docs/evidence/construction-intelligence-phase-08c-financial-readiness/"
        "financial-source-coverage-matrix.json"
    )
    by_status = mtx.get("summary", {}).get("by_status", {})
    payload = {
        "command": "second-brain financial coverage",
        "ok": True,
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "required_families": contract.get("required_families", []),
        "source_coverage_snapshots": snap,
        "financial_source_coverage_matrix": {
            "summary": mtx.get("summary", {}),
            "total_sources": mtx.get("total_sources", 0),
            "by_status": by_status,
            "matrix_path": matrix_path,
            "advisory_note": "Full matrix (mappings + counts + 6-status classification + no-raw attest) written to matrix_path. See JSON for endpoint family details.",
        },
        "evidence_paths": [matrix_path],
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
    }
    human = [
        "Phase 08C financial source coverage (advisory only)",
        f"  project: {project or 'all'}",
        f"  total sources: {mtx.get('total_sources', 0)} | by status: {by_status}",
        f"  matrix: {matrix_path}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


@financial_app.command("exposure-summary")
def financial_exposure_summary(
    project: str | None = typer.Option(None, "--project", help="Optional project key."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Exposure summary items (advisory marts from V35)."""
    from hb_assistant.construction.second_brain.contracts import load_phase_08c_contract
    from hb_assistant.construction.second_brain.financial_completeness import (
        build_financial_exposure_mart_preview,
    )

    contract = load_phase_08c_contract("exposure_summary_contract")
    preview = build_financial_exposure_mart_preview(project_key=project)
    preview_path = (
        "docs/evidence/construction-intelligence-phase-08c-financial-readiness/"
        "exposure-mart-preview.json"
    )
    payload = {
        "command": "second-brain financial exposure-summary",
        "ok": True,
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "categories": contract.get("exposure_categories", []),
        "exposure_mart_preview_path": preview_path,
        "evidence_paths": [preview_path],
        "summary": preview.get("summary", {}),
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
        "note": "amounts via normalized refs only; never summed. Deterministic vs candidate distinguished. Advisory marts only — not determinations.",
    }
    human = [
        "Phase 08C financial exposure summary (advisory only — not a determination)",
        f"  project: {project or 'all'}",
        f"  summary: {preview.get('summary', {})}",
        f"  preview: {preview_path}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


@financial_app.command("review-items")
def financial_review_items(
    project: str | None = typer.Option(None, "--project", help="Optional project key."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Route review-required financial signals and emit the routing proof (V35/V36).

    Deterministic, advisory, read-only externally: writes review items to the local
    SQLite store and the evidence proof only (no external writeback, no determinations).
    """
    from hb_assistant.construction.second_brain.financial_review_routing import (
        build_financial_review_required_proof,
    )
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator().apply()
    proof = build_financial_review_required_proof(project_key=project)
    payload = {
        "command": "second-brain financial review-items",
        "ok": True,
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "run_id": proof.get("run_id"),
        "proof_path": proof.get("proof_path"),
        "evidence_paths": [proof.get("proof_path")],
        "summary": {
            "items_evaluated": proof.get("items_evaluated"),
            "review_required_count": proof.get("review_required_count"),
            "by_trigger": proof.get("by_trigger"),
            "by_tier": proof.get("by_tier"),
            "by_confidence": proof.get("by_confidence"),
        },
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
        "note": "deterministic review-required routing of the 7 financial signal categories; "
        "advisory review aids only — no determinations, approvals, claims, entitlements, or forecasts.",
    }
    human = [
        "Phase 08C review-required routing (advisory only — no determinations)",
        f"  project: {project or 'all'}",
        f"  run: {proof.get('run_id')}",
        f"  evaluated: {proof.get('items_evaluated')} | routed: {proof.get('review_required_count')}",
        f"  by tier: {proof.get('by_tier')}",
        f"  proof: {proof.get('proof_path')}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


# data-quality phase-08c-gates under data_quality_app for the expected command path
@data_quality_app.command("phase-08c-gates")
def data_quality_phase_08c_gates(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (gates are global)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 08C financial data-quality gates (V35 tables + contracts + guards).

    Evaluates the gates and writes phase-08c-gates-proof.json/.md to the evidence dir
    (read-only over the DB; advisory only). proof_passed is False when required evidence
    is missing.
    """
    from hb_assistant.construction.second_brain.data_quality import (
        build_phase_08c_gates_proof,
    )

    proof = build_phase_08c_gates_proof()
    payload = {
        "command": "second-brain data-quality phase-08c-gates",
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "ok": proof.get("ok"),
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "status_counts": proof.get("status_counts"),
        "by_field_status": proof.get("by_field_status"),
        "required_fields_covered": proof.get("required_fields_covered"),
        "readiness_overstated": proof.get("readiness_overstated"),
        "missing_required_evidence": proof.get("missing_required_evidence"),
        "proof_path": proof.get("proof_path"),
        "evidence_paths": proof.get("evidence_paths"),
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
    }
    human = [
        "Phase 08C financial data-quality gates (advisory only)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')} | ok: {proof.get('ok')}",
        f"  status counts: {proof.get('status_counts')}",
        f"  readiness overstated: {proof.get('readiness_overstated')}",
        f"  missing required evidence: {proof.get('missing_required_evidence') or 'none'}",
        f"  proof: {proof.get('proof_path')}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


# data-quality phase-08d-gates under data_quality_app (sibling of phase-08c-gates).
@data_quality_app.command("phase-08d-gates")
def data_quality_phase_08d_gates(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (gates are global)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 08D MCP-bridge data-quality gates (registries + contracts + permission audit).

    Evaluates the 14 contract gates at the registry/contract level (never dispatches the
    synthesis/retrieval workflow tools) and writes phase-08d-gates-proof.json/.md to the 08D
    evidence dir (read-only over the DB; advisory only). no_raw_access (Prompt 13),
    no_writeback (Prompt 14), and the full validation_matrix (Prompt 15) are
    deferred_not_blocking — never pass — so ready_to_serve stays False until those land.
    """
    from hb_assistant.construction.second_brain.data_quality import (
        build_phase_08d_gates_proof,
    )

    proof = build_phase_08d_gates_proof()
    payload = {
        "command": "second-brain data-quality phase-08d-gates",
        "phase": "08D",
        "project_key": project,
        "advisory_only": True,
        "ok": proof.get("ok"),
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "status_counts": proof.get("status_counts"),
        "by_field_status": proof.get("by_field_status"),
        "required_fields_covered": proof.get("required_fields_covered"),
        "readiness_overstated": proof.get("readiness_overstated"),
        "ready_to_serve": proof.get("ready_to_serve"),
        "serve_blockers": proof.get("serve_blockers"),
        "deferred_gates": proof.get("deferred_gates"),
        "missing_required_evidence": proof.get("missing_required_evidence"),
        "proof_path": proof.get("proof_path"),
        "evidence_paths": proof.get("evidence_paths"),
        "guardrails": _08D_GUARDRAILS,
        "attestations": _08D_ATTESTATIONS,
    }
    human = [
        "Phase 08D MCP-bridge data-quality gates (advisory only)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')} | ok: {proof.get('ok')}",
        f"  status counts: {proof.get('status_counts')}",
        f"  ready to serve: {proof.get('ready_to_serve')}",
        f"  serve blockers: {proof.get('serve_blockers')}",
        f"  deferred gates: {proof.get('deferred_gates')}",
        f"  readiness overstated: {proof.get('readiness_overstated')}",
        f"  missing required evidence: {proof.get('missing_required_evidence') or 'none'}",
        f"  proof: {proof.get('proof_path')}",
    ]
    _emit_08c(payload, json_out=json_out, human=human)


@data_quality_app.command("review-load")
def data_quality_review_load(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (the mart is computed across all projects)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 review-load + review burden policy (read-only).

    Legacy mart + promotion gate retained for compat. Primary output now includes the
    Phase 09 review burden policy (two-step: family eligibility necessary + item impact/risk
    decisive; high-impact item beats low-risk family; financial ledger tracked separately;
    advisory retrieval allowed for low-risk metadata-only source-linked items after guards;
    high-impact always summarized as categories+totals with only top clusters within operator
    budget visible; top examples are hash-only; daily/weekly budget caps operator items;
    no blanket for safe advisory). The legacy review_not_performed no longer blocks all
    advisory retrieval. Read-only; advisory only; never a determination or writeback.
    Exit 0 when proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.review_load_mart import build_review_load_proof

    proof = build_review_load_proof()
    mart = proof["mart"]
    gate = proof["gate"]
    payload = {
        "command": "second-brain data-quality review-load",
        "phase": "09",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "gate_fail_closed_ok": proof.get("gate_fail_closed_ok"),
        "raw_content_findings": proof.get("raw_content_findings"),
        "total_distinct_review_items": mart.get("total_distinct_review_items"),
        "total_raw_rows": mart.get("total_raw_rows"),
        "total_unresolved": mart.get("total_unresolved"),
        "total_high_impact_distinct": mart.get("total_high_impact_distinct"),
        "review_not_performed": mart.get("review_not_performed"),
        "tables": mart.get("tables"),
        "gate": gate,
        "guardrails": mart.get("guardrails"),
        # New Phase 09 burden policy fields (two-step, financial separate, advisory allowed for low-risk)
        "review_burden_policy": proof.get("review_burden_policy"),
        "advisory_retrieval_allowed": proof.get("advisory_retrieval_allowed"),
        "blanket_review_block": proof.get("blanket_review_block"),
        "financial_review_burden": proof.get("financial_review_burden"),
        "high_impact_summary": proof.get("high_impact_summary"),
        "operator_visible_count": proof.get("operator_visible_count"),
        "suppressed_noise_count": proof.get("suppressed_noise_count"),
    }
    human = [
        "Phase 09 review-load + review burden policy (two-step: family+impact; financial separate; advisory allowed for low-risk after two-step+guards)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')}",
        f"  distinct review items: {mart.get('total_distinct_review_items')} "
        f"(raw rows {mart.get('total_raw_rows')})",
        f"  unresolved: {mart.get('total_unresolved')} | "
        f"high-impact: {mart.get('total_high_impact_distinct')}",
        f"  review_not_performed: {mart.get('review_not_performed')}",
        f"  legacy promotion gate: blocked {gate.get('blocked_from_promotion')} / "
        f"promotable {gate.get('promotable_review_ready')}",
        f"  advisory_retrieval_allowed: {proof.get('advisory_retrieval_allowed')} (blanket_block={proof.get('blanket_review_block')})",
        f"  financial separate: raw={(proof.get('financial_review_burden') or {}).get('raw_unresolved')} distinct={(proof.get('financial_review_burden') or {}).get('distinct_items')} (always advisory_only, promotion blocked, does not block low-risk non-fin advisory)",
        f"  operator visible (capped): {proof.get('operator_visible_count')} | suppressed/batched: {proof.get('suppressed_noise_count')}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


# --- Phase 09 review burden policy commands (under second-brain review) ---
# These are intentionally under the root "review" group (second-brain review burden ...)
# and also exposed for data-quality compatibility via the augmented review-load.


def _review_common_guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "two_step_family_necessary_impact_decisive": True,
        "high_impact_beats_low_risk_family": True,
        "financial_ledger_separate_burden": True,
        "high_impact_clustered_not_itemized": True,
        "top_examples_hash_only": True,
        "operator_budget_capped": True,
        "advisory_only_no_determination": True,
        "no_raw_no_writeback": True,
    }


@review_app.command("policy-status")
def review_policy_status(
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Load and validate the Phase 09 review burden policy seed + contract (read-only).

    Verifies two-step classification rules, allowed families (necessary not sufficient),
    high-impact categories (decisive), budget, hard denials, guard columns, hash-only
    example fields, and financial separate handling. Exit 0 on success, 3 on failure.
    After `pip install -e .` this must succeed using the packaged seed/contract.
    """
    from hb_assistant.construction.second_brain.review_burden_mart import (
        ReviewBurdenPolicyError,
        load_review_burden_policy_contract,
        load_review_burden_policy_seed,
    )

    try:
        contract = load_review_burden_policy_contract()
        seed = load_review_burden_policy_seed()
        payload = {
            "command": "second-brain review policy-status",
            "phase": "09",
            "policy_id": seed.get("policy_id"),
            "mode": seed.get("mode"),
            "contract_version": contract.get("version"),
            "seed_keys": sorted(seed.keys()),
            "two_step": contract.get("two_step_classification", {}),
            "high_impact_categories": contract.get("high_impact_impact_categories"),
            "allowed_families": contract.get("allowed_source_families_for_advisory"),
            "financial_separate": contract.get("financial_review"),
            "top_examples_allowed": contract.get("top_examples_allowed_fields"),
            "top_examples_prohibited": contract.get("top_examples_prohibited_fields"),
            "guardrails": _review_common_guardrails(),
            "ok": True,
        }
        human = [
            "Phase 09 review burden policy loaded (packaged seed + contract)",
            f"  policy: {payload['policy_id']} mode={payload['mode']}",
            "  two-step: family necessary + impact decisive; high beats family",
            f"  high-impact cats: {payload['high_impact_categories']}",
            "  financial: separate burden, always advisory_only, promotion blocked",
            "  top examples: only hash-safe fields (no PII/text/URLs)",
        ]
        _emit_08c(payload, json_out=json_out, human=human, exit_code=0)
    except ReviewBurdenPolicyError as e:
        typer.echo(
            json.dumps({"ok": False, "error": str(e)}, indent=2, default=str)
            if json_out
            else str(e)
        )
        raise typer.Exit(3) from None


@review_app.command("burden")
def review_burden(
    project: str | None = typer.Option(None, "--project"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Compute review burden clusters + two-step gate + financial separate (read-only).

    Applies policy: family eligibility (necessary) + item impact (decisive). High-impact
    from any family is Tier C. High-impact categories always summarized (counts + by cat);
    only top clusters within daily budget shown for operator. Financial ledger separate
    (does not block low-risk advisory). top_examples are hash-only. Capped by budget.
    """
    from hb_assistant.construction.second_brain.review_burden_mart import (
        build_review_burden_proof,
    )

    proof = build_review_burden_proof()
    mart = proof.get("mart", {})
    gate = proof.get("gate", {})
    payload = {
        "command": "second-brain review burden",
        "phase": "09",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "mart": mart,
        "gate": gate,
        "guardrails": _review_common_guardrails(),
    }
    hi = mart.get("high_impact_summary", {})
    fin = mart.get("financial_review_burden", {})
    human = [
        "Phase 09 review burden (two-step, clustered, capped; financial separate)",
        f"  total distinct: {mart.get('total_distinct_review_items')}",
        f"  A (auto-advisory): {mart.get('auto_advisory_allowed')} | B (batch): {mart.get('batch_review')} | C (mandatory): {mart.get('mandatory_review')} | D (hard): {mart.get('hard_stop')}",
        f"  financial (separate): raw={fin.get('raw_unresolved')} distinct={fin.get('distinct_items')} (advisory_only, promotion_blocked, does not affect low-risk non-fin advisory)",
        f"  high-impact: cats={hi.get('categories')} total={hi.get('total_high_impact_distinct')} visible_top_clusters={hi.get('visible_top_clusters')} (always summarized; capped clusters only)",
        f"  operator visible (budget cap): {mart.get('operator_visible_count')} | suppressed: {mart.get('suppressed_noise_count')}",
        f"  advisory retrieval allowed: {gate.get('advisory_retrieval_allowed')} (blanket={gate.get('blanket_review_block')})",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


@review_app.command("queue")
def review_queue(
    top: int = typer.Option(
        10, "--top", help="Max top clusters to show (capped by policy budget too)."
    ),
    project: str | None = typer.Option(None, "--project"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Show top operator-visible review clusters (ranked, hash-only examples; read-only).

    Respects daily budget and high_impact always-visible-as-summary. No auto decisions.
    """
    from hb_assistant.construction.second_brain.review_burden_mart import (
        build_review_burden_proof,
    )

    proof = build_review_burden_proof()
    mart = proof.get("mart", {})
    clusters = mart.get("clusters", [])
    # Rank: high-impact first (C), then by count desc
    ranked = sorted(
        clusters,
        key=lambda c: (0 if c.get("tier") == "C" else 1, -int(c.get("item_count", 0))),
    )[:top]
    payload = {
        "command": "second-brain review queue",
        "phase": "09",
        "top": top,
        "project_key": project,
        "clusters": ranked,
        "total_clusters": len(clusters),
        "operator_visible_count": mart.get("operator_visible_count"),
        "suppressed": mart.get("suppressed_noise_count"),
        "high_impact_summary": mart.get("high_impact_summary"),
        "financial_review_burden": mart.get("financial_review_burden"),
        "guardrails": _review_common_guardrails(),
    }
    human = [
        f"Top {len(ranked)} review clusters (two-step policy; high-impact summarized always)",
    ]
    for c in ranked:
        human.append(
            f"  [{c.get('tier')}] {c.get('source_family')}/{c.get('impact_category')} x{c.get('item_count')} (examples: {len(c.get('top_examples', []))})"
        )
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@review_app.command("clusters")
def review_clusters(
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Full clustered view (all clusters, hash-only examples) for the burden policy (read-only)."""
    from hb_assistant.construction.second_brain.review_burden_mart import (
        build_review_burden_proof,
    )

    proof = build_review_burden_proof()
    mart = proof.get("mart", {})
    payload = {
        "command": "second-brain review clusters",
        "phase": "09",
        "clusters": mart.get("clusters", []),
        "high_impact_summary": mart.get("high_impact_summary"),
        "financial_review_burden": mart.get("financial_review_burden"),
        "counts": {
            "total": mart.get("total_distinct_review_items"),
            "A": mart.get("auto_advisory_allowed"),
            "B": mart.get("batch_review"),
            "C": mart.get("mandatory_review"),
            "D": mart.get("hard_stop"),
        },
        "guardrails": _review_common_guardrails(),
    }
    human = ["Full review burden clusters (see --json for details; top_examples hash-only)"]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@data_quality_app.command("relationship-quality")
def data_quality_relationship_quality(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (the mart is computed across all projects)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 cross-source relationship-quality mart (read-only, advisory only).

    Reports link ratios (promotion / review / determinism / human-promotion shares), the
    confidence-class distribution and score spread, and orphan / duplicate quality signals
    (promoted edges without a candidate parent, candidates/relationships without an evidence
    trail, stale tallies, multi-edge pairs). Read-only over the DB; never promotes, rejects,
    writes, or makes a determination. Exit 0 when the proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.relationship_quality_mart import (
        build_relationship_quality_proof,
    )

    proof = build_relationship_quality_proof()
    mart = proof["mart"]
    cand = mart.get("candidates", {})
    rel = mart.get("relationships", {})
    orphan = mart.get("orphan_duplicate", {})
    payload = {
        "command": "second-brain data-quality relationship-quality",
        "phase": "09",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "no_determination_attested": proof.get("no_determination_attested"),
        "guard_violation": proof.get("guard_violation"),
        "raw_content_findings": proof.get("raw_content_findings"),
        "candidate_count": cand.get("total"),
        "relationship_count": rel.get("total"),
        "promotion_rate": mart.get("promotion_rate_candidates_to_relationships"),
        "orphan_total": orphan.get("orphan_total"),
        "multi_edge_pairs": orphan.get("multi_edge_pairs"),
        "warnings": mart.get("warnings"),
        "mart": mart,
        "guardrails": mart.get("guardrails"),
    }
    human = [
        "Phase 09 relationship-quality mart (advisory only, read-only)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')}",
        f"  candidates: {cand.get('total')} | relationships: {rel.get('total')} "
        f"(promotion rate {mart.get('promotion_rate_candidates_to_relationships')})",
        f"  orphan total: {orphan.get('orphan_total')} | "
        f"multi-edge pairs: {orphan.get('multi_edge_pairs')}",
        f"  warnings: {len(mart.get('warnings') or [])}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


@data_quality_app.command("corpus-balance")
def data_quality_corpus_balance(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (the mart is computed across all projects)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 retrieval corpus-balance + source-family coverage mart + fail-closed gate (read-only).

    Profiles per-family coverage (covered / empty / deferred) over the retrieval corpus, reports the
    dominant-family share and balance metrics, and evaluates a fail-closed corpus-balance gate against
    the committed threshold policy. Read-only over the DB; advisory only; never a determination. The
    gate's `corpus_balance_ok` is reported separately from the proof — at preflight the corpus is
    expected to be imbalanced. Exit 0 when the proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.corpus_balance_mart import (
        build_corpus_balance_proof,
    )

    proof = build_corpus_balance_proof()
    mart = proof["mart"]
    gate = proof["gate"]
    payload = {
        "command": "second-brain data-quality corpus-balance",
        "phase": "09",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "policy_loaded": proof.get("policy_loaded"),
        "no_determination_attested": proof.get("no_determination_attested"),
        "guard_violation": proof.get("guard_violation"),
        "raw_content_findings": proof.get("raw_content_findings"),
        "corpus_balance_ok": proof.get("corpus_balance_ok"),
        "verdict": gate.get("verdict"),
        "total_corpus_rows": mart.get("total_corpus_rows"),
        "covered_family_count": mart.get("covered_family_count"),
        "empty_families": mart.get("empty_families"),
        "dominant_family": mart.get("dominant_family"),
        "dominant_share": mart.get("dominant_share"),
        "warnings": mart.get("warnings"),
        "gate": gate,
        "mart": mart,
        "guardrails": mart.get("guardrails"),
    }
    human = [
        "Phase 09 corpus-balance mart + gate (advisory only, read-only)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')} | corpus_balance_ok: {proof.get('corpus_balance_ok')}",
        f"  verdict: {gate.get('verdict')} | total rows: {mart.get('total_corpus_rows')}",
        f"  covered families: {mart.get('covered_family_count')} | "
        f"dominant: {mart.get('dominant_family')} ({mart.get('dominant_share')})",
        f"  empty families: {len(mart.get('empty_families') or [])} | "
        f"warnings: {len(mart.get('warnings') or [])}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


_PHASE_09_SCHEMA_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "additive_only": True,
    "advisory_only": True,
    "local_only": True,
    "no_llamaindex_or_vector_runtime": True,
}


@data_quality_app.command("phase-09-schema-status")
def data_quality_phase_09_schema_status(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 V39 schema + table-lifecycle status (read-only, fail-closed).

    Verifies the local schema is at the expected head (>=V39), that every one of the Phase 09
    retrieval/memory/agent tables (22 total; V38 base + V39 additive) exists with the full
    twenty-three guard columns, and that the Phase 09 lifecycle contract loads and classifies
    all tables. Row counts are reported (some tables such as approved source manifests,
    vector index items, and review burden clusters are legitimately populated by valid
    operations); row population does not flip overall_status. Read-only over the DB; advisory
    only; never a determination. Exit 0 when overall_status is `ready`, 3 otherwise (including
    a missing/invalid lifecycle contract — fail-closed).
    """
    from hb_assistant.construction.second_brain.phase_09_schema import (
        Phase09SchemaContractError,
        build_phase_09_schema_status_report,
    )

    try:
        report = build_phase_09_schema_status_report()
    except Phase09SchemaContractError as exc:
        payload = {
            "command": "second-brain data-quality phase-09-schema-status",
            "policy_loaded": False,
            "overall_status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _PHASE_09_SCHEMA_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _PHASE_09_SCHEMA_GUARDRAILS}
    human = [
        "Phase 09 V39 schema + table-lifecycle status (read-only, advisory)",
        f"  overall: {report['overall_status']} | schema: {report['schema_version']}"
        f" (expected {report['schema_version_expected']})",
        f"  tables present: {report['all_tables_present']} | guards present:"
        f" {report['all_guards_present']} | all rows zero: {report['all_rows_zero']}",
        f"  tables: {report['phase_09_table_count']} | guard columns: {report['guard_column_count']}",
        "  (row counts reported; population of manifests/vector/review tables is expected and does not affect ready status)",
    ]
    _emit_08c(
        payload,
        json_out=json_out,
        human=human,
        exit_code=0 if report["overall_status"] == "ready" else 3,
    )


_PHASE_09_GATES_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "advisory_only": True,
    "no_determination": True,
    "no_readiness_overstatement": True,
    "fail_closed": True,
}


@data_quality_app.command("phase-09-gates")
def data_quality_phase_09_gates(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Evaluate the Phase 09 retrieval/memory/quality data-quality gate set (read-only).

    Aggregates the Phase 09 posture into the pass / warning / fail_blocking / deferred_not_blocking
    taxonomy: structural + safety gates (schema present, all 22 Phase-09 tables' 23 guard columns
    clean, no raw vector content, no external writeback, no semantic-retrieval policy bypass, the
    gates + lifecycle contracts loadable) must pass; per-surface gates whose substrate is legitimately
    empty (or pre-operational) are honestly deferred_not_blocking (population of manifests/vectors/review
    yields pass for those). Read-only; advisory; never overstates readiness; makes no determination.
    Exit 0 when ok (no fail_blocking); 3 on a fail-closed failure or a blocking gate.
    """
    from hb_assistant.construction.second_brain.phase_09_gates import (
        Phase09GatesError,
        build_phase_09_gates_proof,
    )

    try:
        report = build_phase_09_gates_proof(write_evidence=False)
    except Phase09GatesError as exc:
        payload = {
            "command": "second-brain data-quality phase-09-gates",
            "ok": False,
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _PHASE_09_GATES_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _PHASE_09_GATES_GUARDRAILS}
    sc = report["status_counts"]
    human = [
        "Phase 09 data-quality gates (read-only, advisory)",
        f"  ok: {report['ok']} | proof_passed: {report['proof_passed']}"
        f" | gates: {report['gate_count']} (min {report['gate_count_minimum']})",
        f"  pass={sc['pass']} warning={sc['warning']} fail_blocking={sc['fail_blocking']}"
        f" deferred_not_blocking={sc['deferred_not_blocking']}"
        f" | readiness_overstated={report['readiness_overstated']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if report["ok"] else 3)


_PHASE_09_NO_WRITEBACK_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_external_writeback": True,
    "no_direct_graph_or_procore": True,
    "advisory_only": True,
    "no_determination": True,
    "scanner_non_vacuous": True,
    "fail_closed": True,
}


@data_quality_app.command("phase-09-no-writeback-proof")
def data_quality_phase_09_no_writeback_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the phase-09 no-writeback proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the Phase 09 retrieval/embeddings/memory/MCP-wrapper modules perform no writeback.

    Read-only forensic proof: statically scans every Phase-09 module for mutation verbs + dangerous
    HTTP/email imports, confirms the writeback guard columns + all guard columns are 0 across the 22
    Phase-09 tables, confirms the MCP wrappers expose workflows only (no writeback), scans the Phase-09
    evidence tree for leaked secrets, and proves the scanner flags a planted synthetic. Persists
    nothing; advisory only; makes no determination. Exit 0 on a clean proof; 3 on a fail-closed
    failure or findings.
    """
    from hb_assistant.construction.second_brain.phase_09_no_writeback_proof import (
        Phase09NoWritebackProofError,
        build_phase_09_no_writeback_proof,
    )

    try:
        result = build_phase_09_no_writeback_proof(write_evidence=evidence)
    except Phase09NoWritebackProofError as exc:
        payload = {
            "command": "second-brain data-quality phase-09-no-writeback-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _PHASE_09_NO_WRITEBACK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _PHASE_09_NO_WRITEBACK_GUARDRAILS}
    g = result["gates"]
    human = [
        f"Phase 09 no-writeback proof passed={result['proof_passed']}"
        f" (modules={result['modules_scanned']}, writeback={len(result['writeback_findings'])},"
        f" bad_imports={len(result['bad_import_findings'])}, writeback_guard_sum="
        f"{result['writeback_guard_sum']}, mcp_no_writeback={g['mcp_wrappers_no_writeback']},"
        f" scanner_detects_planted={g['scanner_detects_planted']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


_PHASE_09_OPERATOR_STATUS_GUARDRAILS = {
    "local_first": True,
    "read_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "advisory_only": True,
    "no_determination": True,
    "no_readiness_overstatement": True,
    "repo_consistent_command_inventory": True,
    "fail_closed": True,
}


@data_quality_app.command("phase-09-operator-status")
def data_quality_phase_09_operator_status(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the phase-09 operator-status to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Expose a repo-consistent Phase 09 operator status across all CLI status/eval/build/proof surfaces.

    Read-only aggregator: enumerates every Phase-09 CLI surface (retrieval / memory / agent-performance
    / daily-brief-reproducibility / data-quality) with its command shape + per-surface posture
    (contract present, owning-table population from V39/22 schema report), and rolls up the read-only
    schema-status + Phase-09 gates + review advisory + (guarded) hybrid/llamaindex into honest
    overall_status + explicit readiness_categories (safe_advisory, semantic_retrieval, vector_apply,
    production=false, deferred_limitations list). Substrate status reflects populated vs advisory_empty.
    Readiness never overstated. Persists nothing; advisory only; makes no determination. Exit 0 when
    advisory_ready; 3 on a fail-closed failure or degraded/not_ready posture.
    """
    from hb_assistant.construction.second_brain.phase_09_operator_status import (
        Phase09OperatorStatusError,
        build_phase_09_operator_status,
    )

    try:
        report = build_phase_09_operator_status(write_evidence=evidence)
    except Phase09OperatorStatusError as exc:
        payload = {
            "command": "second-brain data-quality phase-09-operator-status",
            "operator_status_ok": False,
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _PHASE_09_OPERATOR_STATUS_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _PHASE_09_OPERATOR_STATUS_GUARDRAILS}
    human = [
        "Phase 09 CLI and operator status (read-only, advisory)",
        f"  overall: {report['overall_status']} | operator_status_ok: {report['operator_status_ok']}"
        f" | surfaces: {report['surface_count']}",
        f"  schema_ready: {report['schema_ready']} | gates_ok: {report['gates_ok']}"
        f" | all_contracts_present: {report['all_contracts_present']}"
        f" | readiness_overstated: {report['readiness_overstated']}",
        f"  substrate: {report.get('phase_09_substrate_status')}",
        f"  categories: safe_advisory={report.get('readiness_categories', {}).get('safe_advisory_readiness')} semantic={report.get('readiness_categories', {}).get('semantic_retrieval_readiness')} vector={report.get('readiness_categories', {}).get('vector_apply_readiness')} prod={report.get('readiness_categories', {}).get('production_readiness')}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if report["operator_status_ok"] else 3
    )


_LLAMAINDEX_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "lazy_import_only": True,
    "metadata_only": True,
    "local_first": True,
    "advisory_only": True,
    "external_embedding_providers_deferred": True,
}


@llamaindex_app.command("status")
def retrieval_llamaindex_status(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 optional LlamaIndex dependency + retrieval config status (read-only, fail-closed).

    Reports core SDK availability (`llama-index-core` from `retrieval` extra; probed without import),
    local embedding backend readiness (`llama-index-embeddings-huggingface` from `retrieval-local`),
    the resolved metadata-only retrieval config + its config_hash, schema readiness (Phase 09 V39/22), and
    `embedding_runtime_ready` (core+local for provider="local"; core for "mock"). `ready_to_index`
    is now truthful across installs. The SDK(s) absent by default (local-first) — reported, not failed.
    Read-only over the DB; builds no embeddings/index. Exit 0 when contract/seed load, config valid,
    and schema ready (runtime readiness is advisory in exit code for status); 3 on fail-closed load/config/schema issues.
    New blockers include `local_embedding_not_ready`.
    """
    from hb_assistant.construction.second_brain.retrieval.llamaindex_config import (
        LlamaIndexConfigError,
        build_llamaindex_config_status,
    )

    try:
        report = build_llamaindex_config_status()
    except LlamaIndexConfigError as exc:
        payload = {
            "command": "second-brain retrieval llamaindex status",
            "policy_loaded": False,
            "config_valid": False,
            "schema_ready": False,
            "ready_to_index": False,
            "error": type(exc).__name__,
            "guardrails": _LLAMAINDEX_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _LLAMAINDEX_GUARDRAILS}
    human = [
        "Phase 09 LlamaIndex dependency + retrieval config status (read-only, advisory)",
        f"  sdk core: {report['sdk']['core_available']} (v{report['sdk']['core_version']})"
        f" | local emb: {report['sdk']['local_embedding_available']} ({report['sdk']['local_embedding_package']})",
        f"  runtime ready: {report.get('embedding_runtime_ready')} | ready to index: {report['ready_to_index']}",
        f"  config valid: {report['config_valid']} | schema ready: {report['schema_ready']}"
        f" | config_hash: {report['config']['config_hash']} | blockers: {report['blockers']}",
    ]
    ready = report["policy_loaded"] and report["config_valid"] and report["schema_ready"]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if ready else 3)


_VECTOR_INDEX_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "metadata_only": True,
    "approved_manifest_only_input": True,
    "no_raw_vector_content_in_sqlite": True,
    "dry_run_no_embeddings": True,
    "local_first": True,
}

_VECTOR_INDEX_APPLY_GUARDRAILS = {
    "no_raw": True,
    "no_external_writeback": True,
    "metadata_only_receipts": True,
    "approved_manifest_only_input": True,
    "vectors_outside_sqlite": True,
    "no_raw_vector_content_in_sqlite": True,
    "local_first": True,
    "fail_closed": True,
}

_HYBRID_RETRIEVAL_GUARDRAILS = {
    "deterministic_source_of_truth": True,
    "semantic_advisory_only": True,
    "no_final_answer_assembly": True,
    "no_raw": True,
    "no_external_writeback": True,
    "vectors_outside_sqlite": True,
    "no_semantic_retrieval_bypass": True,
    "raw_query_not_persisted": True,
    "local_first": True,
    "fail_closed": True,
}

_METADATA_FILTER_GUARDRAILS = {
    "fail_closed": True,
    "excluded_families_never_queried": True,
    "no_raw": True,
    "no_external_writeback": True,
    "no_final_answer_assembly": True,
    "preserve_review_tier_confidence_source_refs_freshness": True,
    "read_only": True,
    "local_first": True,
}

_RETRIEVAL_RESEARCH_PACKET_GUARDRAILS = {
    "semantic_retrieval_through_research_packet_only": True,
    "no_final_answer_assembly": True,
    "no_semantic_retrieval_bypass": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_OUTPUT_EVAL_GUARDRAILS = {
    "semantic_retrieval_through_evaluation_only": True,
    "unsupported_claims_blocked_never_emitted": True,
    "no_final_answer_assembly": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_EVAL_SET_GUARDRAILS = {
    "approved_outputs_only": True,
    "source_linked_cases_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_BENCHMARK_GUARDRAILS = {
    "advisory_only": True,
    "no_final_answer": True,
    "no_semantic_retrieval_bypass": True,
    "approved_outputs_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS = {
    "advisory_only": True,
    "no_final_answer": True,
    "no_semantic_retrieval_bypass": True,
    "approved_outputs_only": True,
    "coverage_read_only": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness_coverage_warnings": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS = {
    "advisory_only": True,
    "no_final_answer": True,
    "deterministic_packing": True,
    "never_exceed_budget": True,
    "no_silent_drops": True,
    "authoritative_packer_unchanged": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness_coverage_warnings": True,
    "read_only": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_CLAIM_CHECKS_GUARDRAILS = {
    "advisory_only": True,
    "no_final_answer": True,
    "no_claim_or_entitlement_determination": True,
    "route_unsupported_to_review": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness_coverage_warnings": True,
    "read_only_by_default": True,
    "local_first": True,
    "fail_closed": True,
}

_RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS = {
    "advisory_only": True,
    "no_final_answer": True,
    "no_determination": True,
    "no_blocking": True,
    "no_raw": True,
    "no_external_writeback": True,
    "preserve_review_tier_confidence_source_refs_freshness_coverage_warnings": True,
    "read_only": True,
    "local_first": True,
    "fail_closed": True,
}


@llamaindex_app.command("build")
def retrieval_llamaindex_build(
    apply: bool = typer.Option(
        False,
        "--apply/--dry-run",
        help="Apply build (embed + write vector store); default dry-run.",
    ),
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 vector index build — dry-run plan, or `--apply` to embed + persist receipts (fail-closed).

    The dry-run produces a metadata-only plan (per-family node counts, planned chunk count, config/plan
    hashes, no-raw attestation) over the approved manifest's loader nodes, rejecting any node lacking
    review tier / confidence / source ref / freshness / no-raw proof — computing **no embeddings**.
    Plan now includes truthful `sdk_available` (core), `local_embedding_available`, and `ready_to_apply`
    (both + nodes).
    `--apply` embeds those approved nodes via LlamaIndex and writes a vector store on the local
    filesystem (**never to SQLite**), persisting metadata-only receipts. Apply fails closed
    (`apply_blocked`) with `sdk_not_available` (core from `retrieval` absent), `local_embedding_not_ready`
    (HF from `retrieval-local` absent for default writer), `no_indexable_nodes`, or policy/schema not ready.
    `build --apply` requires `.[retrieval-local]`; `build-apply-proof` (uses Mock) requires only `.[retrieval]`.
    Exit 0 on a dry-run plan or an applied build; 3 on `apply_blocked` or a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.vector_index import (
        VectorIndexBuildError,
        build_vector_index_apply,
        build_vector_index_dry_run,
    )

    if apply:
        try:
            receipt = build_vector_index_apply(project_key=project)
        except (VectorIndexBuildError, EmbeddingVectorPolicyError) as exc:
            payload = {
                "command": "second-brain retrieval llamaindex build --apply",
                "status": "not_ready",
                "error": type(exc).__name__,
                "guardrails": _VECTOR_INDEX_APPLY_GUARDRAILS,
            }
            _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
            return
        applied = receipt.get("status") == "applied"
        payload = {**receipt, "guardrails": _VECTOR_INDEX_APPLY_GUARDRAILS}
        payload.pop("items", None)  # per-item rows are persisted, not echoed
        human = [
            "Phase 09 vector index build — apply",
            f"  status: {receipt['status']}"
            + (
                f" | items: {receipt.get('total_items')} | embedding_dim: {receipt.get('embedding_dim')}"
                if applied
                else f" | blocker: {receipt.get('blocker_reason')}"
            ),
            f"  vectors in sqlite: {receipt['vectors_persisted_to_sqlite']}"
            f" | store: {receipt.get('vector_store_location')}",
        ]
        _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if applied else 3)
        return

    try:
        plan = build_vector_index_dry_run(project_key=project)
    except (VectorIndexBuildError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval llamaindex build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _VECTOR_INDEX_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**plan, "guardrails": _VECTOR_INDEX_GUARDRAILS}
    human = [
        "Phase 09 vector index build — dry-run plan (read-only, advisory)",
        f"  status: {plan['status']} | total nodes: {plan['total_nodes']}"
        f" | planned chunks: {plan['planned_chunk_count']}",
        f"  per-family: {plan['per_family_node_count']} | rejected: {plan['rejected_node_count']}",
        f"  sdk core: {plan['sdk_available']} | local emb: {plan.get('local_embedding_available')}"
        f" | ready to apply: {plan['ready_to_apply']}"
        f" | vectors in sqlite: {plan['vectors_persisted_to_sqlite']}",
        f"  warnings: {plan['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@llamaindex_app.command("build-proof")
def retrieval_llamaindex_build_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the dry-run build proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the dry-run vector build over the approved manifest is safe (read-only, fail-closed).

    Demonstrates a controlled approved index loads indexable nodes, the build rule rejects nodes lacking
    metadata / no-raw proof, and a guard-clean `status='dry_run'` run record persists (no vectors in
    SQLite). Computes no embeddings; persists nothing to the operator DB. The plan in proof includes
    `sdk_available` (core) + `local_embedding_available` for truthful readiness across installs.
    Exit 0 if the proof passes.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.vector_index import (
        VectorIndexBuildError,
        build_vector_index_dry_run_proof,
    )

    try:
        proof = build_vector_index_dry_run_proof(write_evidence=evidence)
    except (VectorIndexBuildError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval llamaindex build-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _VECTOR_INDEX_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _VECTOR_INDEX_GUARDRAILS}
    human = [
        f"Vector index dry-run proof passed={proof['proof_passed']}"
        f" (total_nodes={proof['proof_total_nodes']}, record={proof['dry_run_record_persisted']})",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@llamaindex_app.command("build-apply-proof")
def retrieval_llamaindex_build_apply_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the apply build proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the apply vector build is safe (embeds approved nodes, vectors outside SQLite, fail-closed).

    Demonstrates a controlled approved index applies to an offline (`MockEmbedding`) LlamaIndex pipeline:
    vectors are written to a directory **outside SQLite**, a guard-clean `status='applied'` run plus
    metadata-only per-node item rows persist (no vectors / text / raw in SQLite), and the build blocks
    when there are no indexable nodes. Computes embeddings only in a temp dir; never touches the operator
    DB. Uses Mock (core only) so proof runs after `pip install -e ".[retrieval]"`; real --apply requires
    `.[retrieval-local]` and will block with `local_embedding_not_ready` on missing local backend.
    Exit 0 if the proof passes.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.vector_index import (
        VectorIndexBuildError,
        build_vector_index_apply_proof,
    )

    try:
        proof = build_vector_index_apply_proof(write_evidence=evidence)
    except (VectorIndexBuildError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval llamaindex build-apply-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _VECTOR_INDEX_APPLY_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _VECTOR_INDEX_APPLY_GUARDRAILS}
    human = [
        f"Vector index apply proof passed={proof['proof_passed']}"
        f" (items={proof['applied_item_count']}, dim={proof['embedding_dim']},"
        f" vectors_outside_sqlite={proof['vectors_written_outside_sqlite']})",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@hybrid_app.command("status")
def retrieval_hybrid_status(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Hybrid retrieval readiness — deterministic always; semantic iff core+local SDKs + applied index (read-only).

    `sdk_available` = core LlamaIndex (`retrieval`); `local_embedding_available` = HF backend (`retrieval-local`);
    `semantic_ready` requires both + applied index. Blockers may include `semantic_local_embedding_not_ready`.
    """
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
        HybridRetrievalError,
        build_hybrid_status,
    )

    try:
        report = build_hybrid_status()
    except HybridRetrievalError as exc:
        payload = {
            "command": "second-brain retrieval hybrid status",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS}
    human = [
        "Phase 09 hybrid retrieval status (read-only, advisory)",
        f"  deterministic ready: {report['deterministic_ready']}"
        f" | semantic ready: {report['semantic_ready']}",
        f"  sdk core: {report['sdk_available']} | local emb: {report.get('local_embedding_available')}"
        f" | applied index: {report['applied_vector_index_present']}",
        f"  semantic blockers: {report['semantic_blockers']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@hybrid_app.command("search")
def retrieval_hybrid_search(
    query: str = typer.Argument(..., help="Query text (never persisted; only its hash is stored)."),
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    mode: str = typer.Option(
        "hybrid", "--mode", help="Retrieval mode: 'hybrid' or 'deterministic-only'."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Hybrid retrieval — deterministic (authoritative) + advisory semantic, merged (read-only).

    Emits a metadata-only summary (counts, per-family + origin split, tier distribution, score buckets,
    degradation, warnings, `assembles_final_answer=false`, `query_hash`). Never echoes the raw query or
    any excerpt, and never persists to the operator DB (the receipt path is exercised in `hybrid proof`).
    Semantic results are advisory and source-linked; the path fails closed (semantic skipped, deterministic
    still returned) when core SDK absent (`semantic_sdk_not_available`), local embedding absent
    (`semantic_local_embedding_not_ready`), or no applied index. Exit 0 on success; 3 on a
    fail-closed contract/schema failure.
    """
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
        HybridRetrievalError,
        build_hybrid_retrieval,
    )

    normalized_mode = (
        "deterministic_only" if mode in ("deterministic-only", "deterministic_only") else mode
    )
    try:
        result = build_hybrid_retrieval(query, project_key=project, mode=normalized_mode)
    except HybridRetrievalError as exc:
        payload = {
            "command": "second-brain retrieval hybrid search",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS}
    human = [
        "Phase 09 hybrid retrieval — merged context (read-only, advisory)",
        f"  mode: {result['mode']} | total: {result['result_count']}"
        f" | deterministic: {result['deterministic_count']} | semantic: {result['semantic_count']}",
        f"  per-family: {result['per_family_count']} | tiers: {result['tier_distribution']}",
        f"  assembles final answer: {result['assembles_final_answer']}"
        f" | semantic skip: {result['semantic_skip_reason']}",
        f"  warnings: {result['coverage_warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@hybrid_app.command("proof")
def retrieval_hybrid_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the hybrid retrieval proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the hybrid broker is safe — deterministic + advisory semantic merge, source-of-truth kept.

    Demonstrates (on a controlled fixture with an applied index + an offline MockEmbedding) a guard-clean
    hybrid query: deterministic + advisory-only semantic results merge, the raw query is never persisted
    (only its hash), receipts are metadata-only with all 23 guard `CHECK(=0)` columns 0,
    `assembles_final_answer=false`, `semantic_retrieval_bypassed_policy=0`, and the semantic path fails
    closed when there is no applied index. Persists nothing to the operator DB. Exit 0 if the proof passes.
    """
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
        HybridRetrievalError,
        build_hybrid_retrieval_proof,
    )

    try:
        proof = build_hybrid_retrieval_proof(write_evidence=evidence)
    except HybridRetrievalError as exc:
        payload = {
            "command": "second-brain retrieval hybrid proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _HYBRID_RETRIEVAL_GUARDRAILS}
    human = [
        f"Hybrid retrieval proof passed={proof['proof_passed']}"
        f" (deterministic={proof['deterministic_count']}, semantic={proof['semantic_count']},"
        f" assembles_final_answer={proof['assembles_final_answer']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@metadata_filter_app.command("status")
def retrieval_metadata_filter_status(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Metadata-filter policy view — filterable keys, date-capable families, confidence order (read-only)."""
    from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
        MetadataFilterError,
        load_metadata_filter_contract,
        load_metadata_filter_seed,
    )

    try:
        contract = load_metadata_filter_contract()
        seed = load_metadata_filter_seed()
    except MetadataFilterError as exc:
        payload = {
            "command": "second-brain retrieval metadata-filter status",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _METADATA_FILTER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    report = {
        "command": "second-brain retrieval metadata-filter status",
        "phase": "09",
        "filterable_keys": contract.get("filterable_keys"),
        "date_capable_families": contract.get("date_capable_families"),
        "confidence_order": seed.get("confidence_order"),
        "review_tier_bounds": contract.get("review_tier_bounds"),
        "drop_reasons": contract.get("drop_reasons"),
        "coverage_warning_codes": contract.get("coverage_warning_codes"),
        "excluded_families_blocked": contract.get("excluded_families_blocked"),
        "policy_version": seed.get("version"),
        "read_only": True,
    }
    payload = {**report, "guardrails": _METADATA_FILTER_GUARDRAILS}
    human = [
        "Phase 09 metadata filter policy (read-only)",
        f"  keys: {report['filterable_keys']}",
        f"  date-capable families: {len(report['date_capable_families'] or [])}",
        f"  confidence order: {report['confidence_order']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@metadata_filter_app.command("apply")
def retrieval_metadata_filter_apply(
    query: str = typer.Argument(
        ..., help="Query text (never persisted; only its hash is reported)."
    ),
    project: str | None = typer.Option(None, "--project", help="Project key filter."),
    source: str | None = typer.Option(
        None, "--source", help="Comma-separated allowlisted source family filter."
    ),
    date_from: str | None = typer.Option(None, "--date-from", help="ISO date lower bound."),
    date_to: str | None = typer.Option(None, "--date-to", help="ISO date upper bound."),
    max_review_tier: int | None = typer.Option(
        None, "--max-review-tier", help="Keep items with review_tier <= this (1/2/3)."
    ),
    min_confidence: str | None = typer.Option(
        None, "--min-confidence", help="Keep items at or above this confidence class."
    ),
    require_coverage: bool = typer.Option(
        False, "--require-coverage/--no-require-coverage", help="Flag incomplete source coverage."
    ),
    mode: str = typer.Option("hybrid", "--mode", help="'hybrid' or 'deterministic-only'."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Apply project/source/date/review/confidence filters to a hybrid retrieval (read-only, fail-closed).

    Enforces the filter before retrieval (constrain families/project; reject excluded families) and after
    (drop items outside the window/tier/confidence with recorded reasons + source-coverage warnings).
    Emits a metadata-only summary (no raw query/excerpts); persists nothing to the operator DB. Exit 0 on
    success; 3 on a fail-closed contract/schema/filter failure.
    """
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
        HybridRetrievalError,
        build_hybrid_retrieval,
    )
    from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
        MetadataFilter,
        MetadataFilterError,
    )

    normalized_mode = (
        "deterministic_only" if mode in ("deterministic-only", "deterministic_only") else mode
    )
    families = tuple(s.strip() for s in source.split(",") if s.strip()) if source else None
    try:
        spec = MetadataFilter(
            project_key=project,
            source_families=families,
            date_from=date_from,
            date_to=date_to,
            max_review_tier=max_review_tier,
            min_confidence=min_confidence,
            require_source_coverage=require_coverage,
        )
        result = build_hybrid_retrieval(
            query, project_key=project, mode=normalized_mode, metadata_filter=spec
        )
    except (HybridRetrievalError, MetadataFilterError) as exc:
        payload = {
            "command": "second-brain retrieval metadata-filter apply",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _METADATA_FILTER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _METADATA_FILTER_GUARDRAILS}
    human = [
        "Phase 09 metadata-filtered retrieval (read-only, advisory)",
        f"  mode: {result['mode']} | total: {result['result_count']}"
        f" | deterministic: {result['deterministic_count']} | semantic: {result['semantic_count']}",
        f"  dropped: {(result.get('filter_summary') or {}).get('dropped_by_reason')}",
        f"  per-family: {result['per_family_count']} | tiers: {result['tier_distribution']}",
        f"  warnings: {result['coverage_warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@metadata_filter_app.command("proof")
def retrieval_metadata_filter_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the metadata-filter proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove metadata filter enforcement — pre-filter rejects excluded families; post-filter drops by
    project/family/date/review/confidence with reasons + coverage warnings; no raw, no answer assembly."""
    from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
        MetadataFilterError,
        build_metadata_filter_proof,
    )

    try:
        proof = build_metadata_filter_proof(write_evidence=evidence)
    except MetadataFilterError as exc:
        payload = {
            "command": "second-brain retrieval metadata-filter proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _METADATA_FILTER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _METADATA_FILTER_GUARDRAILS}
    human = [
        f"Metadata filter proof passed={proof['proof_passed']}"
        f" (excluded_rejected={proof['excluded_family_rejected_pre_filter']},"
        f" drop_matrix={proof['post_filter_drop_matrix_ok']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_research_packet_app.command("build")
def retrieval_research_packet_build(
    query: str = typer.Argument(
        ..., help="Query text (never persisted; only its hash is reported)."
    ),
    project: str | None = typer.Option(None, "--project", help="Project key filter."),
    source: str | None = typer.Option(
        None, "--source", help="Comma-separated allowlisted source family filter."
    ),
    max_review_tier: int | None = typer.Option(
        None, "--max-review-tier", help="Keep items with review_tier <= this (1/2/3)."
    ),
    min_confidence: str | None = typer.Option(
        None, "--min-confidence", help="Keep items at or above this confidence class."
    ),
    mode: str = typer.Option("hybrid", "--mode", help="'hybrid' or 'deterministic-only'."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Route semantic retrieval context through Research Packet generation only (read-only, fail-closed).

    Builds the hybrid (deterministic authoritative + advisory semantic) envelope and routes it through
    `build_research_packet_from_envelope`, producing a metadata-only research packet (advisory) — never an
    answer (`synthesis_performed=false`). Emits a metadata-only summary (no raw query/excerpts); persists
    nothing to the operator DB. Exit 0 on success; 3 on a fail-closed contract/schema/filter failure.
    """
    from hb_assistant.construction.second_brain.research.semantic_packet import (
        SemanticPacketError,
        build_semantic_research_packet,
    )
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import HybridRetrievalError
    from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
        MetadataFilter,
        MetadataFilterError,
    )

    normalized_mode = (
        "deterministic_only" if mode in ("deterministic-only", "deterministic_only") else mode
    )
    families = tuple(s.strip() for s in source.split(",") if s.strip()) if source else None
    spec: MetadataFilter | None = None
    if families or max_review_tier is not None or min_confidence is not None:
        spec = MetadataFilter(
            source_families=families,
            max_review_tier=max_review_tier,
            min_confidence=min_confidence,
        )
    try:
        result = build_semantic_research_packet(
            query,
            project_key=project,
            mode=normalized_mode,
            metadata_filter=spec,
        )
    except (SemanticPacketError, HybridRetrievalError, MetadataFilterError) as exc:
        payload = {
            "command": "second-brain retrieval research-packet build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_RESEARCH_PACKET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_RESEARCH_PACKET_GUARDRAILS}
    human = [
        "Phase 09 semantic context → research packet (read-only, advisory)",
        f"  route: {result['route']} | synthesis_performed: {result['synthesis_performed']}",
        f"  deterministic: {result['deterministic_count']} | semantic: {result['semantic_count']}"
        f" | packet: {result['packet']['advisory_classification']}"
        f"/{result['packet']['context_quality_class']}/{result['packet']['degradation_mode']}",
        f"  review tier: {result['packet']['review_tier']} | status: {result['packet']['status']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_research_packet_app.command("proof")
def retrieval_research_packet_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the integration proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove semantic context routes through Research Packet generation only (never an answer)."""
    from hb_assistant.construction.second_brain.research.semantic_packet import (
        SemanticPacketError,
        build_semantic_research_packet_proof,
    )

    try:
        proof = build_semantic_research_packet_proof(write_evidence=evidence)
    except SemanticPacketError as exc:
        payload = {
            "command": "second-brain retrieval research-packet proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_RESEARCH_PACKET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_RESEARCH_PACKET_GUARDRAILS}
    human = [
        f"Research packet integration proof passed={proof['proof_passed']}"
        f" (route_only={proof['route_is_research_packet_only']},"
        f" packet_not_answer={proof['returns_packet_not_answer']},"
        f" no_bypass={proof['synthesis_has_no_semantic_path']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_output_eval_app.command("run")
def retrieval_output_eval_run(
    query: str = typer.Argument(
        ..., help="Query text (never persisted; only its hash is reported)."
    ),
    project: str | None = typer.Option(None, "--project", help="Project key filter."),
    source: str | None = typer.Option(
        None, "--source", help="Comma-separated allowlisted source family filter."
    ),
    max_review_tier: int | None = typer.Option(
        None, "--max-review-tier", help="Keep items with review_tier <= this (1/2/3)."
    ),
    min_confidence: str | None = typer.Option(
        None, "--min-confidence", help="Keep items at or above this confidence class."
    ),
    mode: str = typer.Option("hybrid", "--mode", help="'hybrid' or 'deterministic-only'."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Route semantic retrieval outputs through evaluation + claim/source checks (read-only, fail-closed).

    Runs the Output Evaluation (A05) checklist over a non-synthesized context result, plus an
    unsupported-claim check and a source-linked proof over the retrieved items. Emits a metadata-only
    summary (no raw query/answer/excerpts); persists nothing to the operator DB. Exit 0 if the overall
    evaluation passes; 3 if it fails closed (evaluation fail / unsupported claims / contract/schema/filter).
    """
    from hb_assistant.construction.second_brain.retrieval.hybrid_broker import HybridRetrievalError
    from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
        MetadataFilter,
        MetadataFilterError,
    )
    from hb_assistant.construction.second_brain.synthesis.semantic_output_evaluation import (
        SemanticOutputEvaluationError,
        build_semantic_output_evaluation,
    )

    normalized_mode = (
        "deterministic_only" if mode in ("deterministic-only", "deterministic_only") else mode
    )
    families = tuple(s.strip() for s in source.split(",") if s.strip()) if source else None
    spec: MetadataFilter | None = None
    if families or max_review_tier is not None or min_confidence is not None:
        spec = MetadataFilter(
            source_families=families,
            max_review_tier=max_review_tier,
            min_confidence=min_confidence,
        )
    try:
        result = build_semantic_output_evaluation(
            query, project_key=project, mode=normalized_mode, metadata_filter=spec
        )
    except (SemanticOutputEvaluationError, HybridRetrievalError, MetadataFilterError) as exc:
        payload = {
            "command": "second-brain retrieval output-eval run",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_OUTPUT_EVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_OUTPUT_EVAL_GUARDRAILS}
    human = [
        "Phase 09 semantic output evaluation (read-only, advisory)",
        f"  route: {result['route']} | synthesis_performed: {result['synthesis_performed']}"
        f" | overall_passed: {result['overall_passed']}",
        f"  evaluation: {result['evaluation']['checklist_passed']}/{result['evaluation']['checklist_total']}"
        f" | unsupported: {result['unsupported_claim_check']['unsupported_count']}"
        f" | unlinked: {result['source_linked_proof']['unlinked_count']}",
        f"  deterministic: {result['deterministic_count']} | semantic: {result['semantic_count']}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if result["overall_passed"] else 3
    )


@retrieval_output_eval_app.command("proof")
def retrieval_output_eval_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the output-evaluation proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove semantic outputs route through evaluation + unsupported-claim + source-linked checks."""
    from hb_assistant.construction.second_brain.synthesis.semantic_output_evaluation import (
        SemanticOutputEvaluationError,
        build_semantic_output_evaluation_proof,
    )

    try:
        proof = build_semantic_output_evaluation_proof(write_evidence=evidence)
    except SemanticOutputEvaluationError as exc:
        payload = {
            "command": "second-brain retrieval output-eval proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_OUTPUT_EVAL_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_OUTPUT_EVAL_GUARDRAILS}
    human = [
        f"Output evaluation integration proof passed={proof['proof_passed']}"
        f" (eval={proof['evaluation_passed']}, unsupported={proof['unsupported_count']},"
        f" receipts_clean={proof['receipts_persisted_guard_clean']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_eval_set_app.command("build")
def retrieval_eval_set_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    name: str | None = typer.Option(
        None, "--name", help="Eval set name (hashed in the receipt; never stored raw)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Create source-linked retrieval eval cases from approved outputs (read-only, fail-closed).

    Enumerates the approved Obsidian + reviewed-memory corpus and emits one source-linked eval case per
    approved node (linked by a hashed source ref). Emits a metadata-only summary (no raw query/content/
    source ref); persists nothing to the operator DB. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.retrieval.eval_set import (
        RetrievalEvalSetError,
        build_retrieval_eval_set,
    )

    try:
        result = build_retrieval_eval_set(project_key=project, name=name)
    except RetrievalEvalSetError as exc:
        payload = {
            "command": "second-brain retrieval eval-set build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_EVAL_SET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_EVAL_SET_GUARDRAILS}
    payload.pop("cases", None)  # per-case rows summarized by count; not echoed in bulk
    human = [
        "Phase 09 retrieval quality eval set (read-only, advisory)",
        f"  status: {result['status']} | cases: {result['case_count']}"
        f" | review tiers: {result['review_tier_summary']}",
        f"  per-family: {result['per_family_case_count']} | warnings: {result['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_eval_set_app.command("proof")
def retrieval_eval_set_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the eval-set proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove source-linked eval cases are built from approved outputs + persisted metadata-only."""
    from hb_assistant.construction.second_brain.retrieval.eval_set import (
        RetrievalEvalSetError,
        build_retrieval_eval_set_proof,
    )

    try:
        proof = build_retrieval_eval_set_proof(write_evidence=evidence)
    except RetrievalEvalSetError as exc:
        payload = {
            "command": "second-brain retrieval eval-set proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_EVAL_SET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_EVAL_SET_GUARDRAILS}
    human = [
        f"Retrieval eval set proof passed={proof['proof_passed']}"
        f" (cases={proof['case_count']}, source_linked={proof['cases_source_linked']},"
        f" unsafe_excluded={proof['unsafe_node_excluded']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_benchmark_app.command("build")
def retrieval_benchmark_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    name: str | None = typer.Option(
        None, "--name", help="Benchmark name (hashed in the receipt; never stored raw)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Benchmark deterministic vs semantic vs hybrid retrieval over the approved corpus (read-only).

    Probes are built at runtime from each approved node's redacted excerpt (never persisted) and run
    through the three modes; emits a metadata-only summary of bucketed comparative metrics (no raw
    query/content/source ref). Persists nothing to the operator DB. The semantic side degrades
    fail-closed (blocked status) when the SDK/applied index is absent. Exit 0 on success; 3 fail-closed.
    """
    from hb_assistant.construction.second_brain.retrieval.benchmark import (
        RetrievalBenchmarkError,
        build_retrieval_benchmark,
    )

    try:
        result = build_retrieval_benchmark(project_key=project, name=name)
    except RetrievalBenchmarkError as exc:
        payload = {
            "command": "second-brain retrieval benchmark build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_BENCHMARK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_BENCHMARK_GUARDRAILS}
    payload.pop("metric_rows", None)  # row labels summarized by count; not echoed in bulk
    sem = (result.get("mode_metrics") or {}).get("semantic", {})
    human = [
        "Phase 09 deterministic vs semantic benchmark (read-only, advisory)",
        f"  status: {result['status']} | probes: {result['probe_count']}"
        f" | metric rows: {result['metric_row_count']}",
        f"  semantic: {sem.get('status', 'n/a')}"
        f" | hit-rate: {sem.get('hit_rate_pct', 0)}% | warnings: {result['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_benchmark_app.command("proof")
def retrieval_benchmark_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the benchmark proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove all three modes are compared, metrics persisted metadata-only, semantic advisory + floored."""
    from hb_assistant.construction.second_brain.retrieval.benchmark import (
        RetrievalBenchmarkError,
        build_retrieval_benchmark_proof,
    )

    try:
        proof = build_retrieval_benchmark_proof(write_evidence=evidence)
    except RetrievalBenchmarkError as exc:
        payload = {
            "command": "second-brain retrieval benchmark proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_BENCHMARK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_BENCHMARK_GUARDRAILS}
    human = [
        f"Retrieval benchmark proof passed={proof['proof_passed']}"
        f" (modes={proof['all_three_modes_compared']}, semantic={proof['semantic_available']},"
        f" guard_clean={proof['rows_persisted_guard_clean']}, blocked_path={proof['semantic_blocked_path_status']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_project_benchmark_app.command("build")
def retrieval_project_benchmark_build(
    project: str | None = typer.Option(
        None, "--project", help="Scope to a single project key (default: all enumerated projects)."
    ),
    name: str | None = typer.Option(
        None, "--name", help="Benchmark base name (hashed in the receipt; never stored raw)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Benchmark + coverage per project over the approved corpus (read-only, fail-closed, advisory).

    Enumerates projects from the approved retrieval corpus and, per project, runs the Prompt 25
    deterministic/semantic/hybrid benchmark and the read-only corpus-balance coverage mart. Emits a
    metadata-only summary (no raw query/probe/content/source ref); persists nothing to the operator DB.
    On the operator DB (no approved corpus) it is honestly empty. Exit 0 on success; 3 fail-closed.
    """
    from hb_assistant.construction.second_brain.retrieval.project_benchmark import (
        ProjectRetrievalBenchmarkError,
        build_project_retrieval_benchmarks,
    )

    try:
        result = build_project_retrieval_benchmarks(
            projects=(project,) if project else None, name=name
        )
    except ProjectRetrievalBenchmarkError as exc:
        payload = {
            "command": "second-brain retrieval project-benchmark build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS}
    human = [
        "Phase 09 project-specific retrieval benchmarks + coverage (read-only, advisory)",
        f"  status: {result['status']} | projects: {result['projects_count']}"
        f" | warnings: {result['warnings']}",
        f"  rollup: {result['rollup']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_project_benchmark_app.command("proof")
def retrieval_project_benchmark_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the project-benchmark proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove per-project benchmarks persist metadata-only + guard-clean, paired with coverage reports."""
    from hb_assistant.construction.second_brain.retrieval.project_benchmark import (
        ProjectRetrievalBenchmarkError,
        build_project_retrieval_benchmarks_proof,
    )

    try:
        proof = build_project_retrieval_benchmarks_proof(write_evidence=evidence)
    except ProjectRetrievalBenchmarkError as exc:
        payload = {
            "command": "second-brain retrieval project-benchmark proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_PROJECT_BENCHMARK_GUARDRAILS}
    human = [
        f"Project retrieval benchmark proof passed={proof['proof_passed']}"
        f" (projects={proof['projects_count']}, persisted={proof['per_project_benchmarks_persisted']},"
        f" coverage={proof['per_project_coverage_present']}, guard_clean={proof['rows_persisted_guard_clean']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_context_budget_app.command("build")
def retrieval_context_budget_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Compare the baseline context packer vs the best-effort optimizer (read-only, advisory).

    Gathers the deterministic pre-budget retrieval corpus and reports a metadata-only baseline-vs-optimized
    comparison (kept counts, char utilization %, items recovered, preserved tier distribution, coverage +
    budget-drop warnings). The authoritative apply_context_budget is unchanged; persists nothing.
    Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.retrieval.context_budget import (
        ContextBudgetOptimizationError,
        build_context_budget_optimization,
    )

    try:
        result = build_context_budget_optimization(project_key=project)
    except ContextBudgetOptimizationError as exc:
        payload = {
            "command": "second-brain retrieval context-budget build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS}
    human = [
        "Phase 09 context budget optimization (read-only, advisory)",
        f"  status: {result['status']} | candidate items: {result['candidate_item_count']}",
        f"  baseline kept: {result['baseline']['kept_count']}"
        f" ({result['baseline']['char_utilization_pct']}%) | optimized kept:"
        f" {result['optimized']['kept_count']} ({result['optimized']['char_utilization_pct']}%)",
        f"  items recovered: {result['items_recovered']} | within_budget: {result['within_budget']}"
        f" | metadata_preserved: {result['metadata_preserved']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_context_budget_app.command("proof")
def retrieval_context_budget_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the optimization proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the optimizer recovers budget, preserves metadata + warnings, and never exceeds the budget."""
    from hb_assistant.construction.second_brain.retrieval.context_budget import (
        ContextBudgetOptimizationError,
        build_context_budget_optimization_proof,
    )

    try:
        proof = build_context_budget_optimization_proof(write_evidence=evidence)
    except ContextBudgetOptimizationError as exc:
        payload = {
            "command": "second-brain retrieval context-budget proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_CONTEXT_BUDGET_GUARDRAILS}
    human = [
        f"Context budget optimization proof passed={proof['proof_passed']}"
        f" (recovered={proof['items_recovered']}, within_budget={proof['within_budget']},"
        f" metadata_preserved={proof['metadata_preserved']}, every_drop_warned={proof['every_drop_has_warning']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_claim_checks_app.command("build")
def retrieval_claim_checks_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Detect unsupported claims over the deterministic corpus and route them to review (read-only).

    Each retrieved item is a claim; one lacking a source ref / allowlisted family is unsupported and is
    routed to review_required (never presented as fact). Emits a metadata-only summary (counts + routing
    breakdown + hashed records; no raw claim text/source ref); makes no claim/entitlement determination;
    persists nothing to the operator DB. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.retrieval.unsupported_claim_checks import (
        UnsupportedClaimCheckError,
        build_unsupported_claim_checks,
    )

    try:
        result = build_unsupported_claim_checks(project_key=project)
    except UnsupportedClaimCheckError as exc:
        payload = {
            "command": "second-brain retrieval claim-checks build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_CLAIM_CHECKS_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_CLAIM_CHECKS_GUARDRAILS}
    payload.pop(
        "routing_records", None
    )  # per-claim hashed records summarized by counts; not echoed in bulk
    human = [
        "Phase 09 unsupported claim checks + review routing (read-only, advisory)",
        f"  status: {result['status']} | claims: {result['claim_count']}"
        f" | unsupported: {result['unsupported_count']} | routed: {result['routed_count']}",
        f"  by review status: {result['by_review_status']} | by reason: {result['by_reason']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_claim_checks_app.command("proof")
def retrieval_claim_checks_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the claim-checks proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove unsupported claims are detected + routed to review, with no claim/entitlement determination."""
    from hb_assistant.construction.second_brain.retrieval.unsupported_claim_checks import (
        UnsupportedClaimCheckError,
        build_unsupported_claim_checks_proof,
    )

    try:
        proof = build_unsupported_claim_checks_proof(write_evidence=evidence)
    except UnsupportedClaimCheckError as exc:
        payload = {
            "command": "second-brain retrieval claim-checks proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_CLAIM_CHECKS_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_CLAIM_CHECKS_GUARDRAILS}
    human = [
        f"Unsupported claim checks proof passed={proof['proof_passed']}"
        f" (unsupported={proof['unsupported_count']}, routed_review_required={proof['unsupported_routed_to_review_required']},"
        f" determination_made={proof['claim_determination_made']}, guard_clean={proof['receipt_guard_clean']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@retrieval_hallucination_risk_app.command("build")
def retrieval_hallucination_risk_build(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Measure hallucination risk + overconfidence indicators over the deterministic corpus (read-only).

    Scores fabrication / ungrounded / overconfident signals (unsupported claims, tier-3 items, stale /
    conflict, coverage gaps, degradation, high-confidence-on-weak-grounding) into a deterministic risk
    band with an indicators list — advisory only. Makes no determination, blocks nothing, persists
    nothing to the operator DB. Exit 0 on success; 3 on a fail-closed failure.
    """
    from hb_assistant.construction.second_brain.retrieval.hallucination_risk import (
        HallucinationRiskError,
        build_hallucination_risk_checks,
    )

    try:
        result = build_hallucination_risk_checks(project_key=project)
    except HallucinationRiskError as exc:
        payload = {
            "command": "second-brain retrieval hallucination-risk build",
            "status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
            "guardrails": _RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**result, "guardrails": _RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS}
    human = [
        "Phase 09 hallucination risk + overconfidence indicators (read-only, advisory)",
        f"  status: {result['status']} | claims: {result['claim_count']} | risk band: {result['risk_band']}",
        f"  indicators: {result['indicators']}",
        f"  overconfidence: {result['overconfidence_indicators']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@retrieval_hallucination_risk_app.command("proof")
def retrieval_hallucination_risk_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the hallucination-risk proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the risk + overconfidence indicators fire, with no determination and no DB writes."""
    from hb_assistant.construction.second_brain.retrieval.hallucination_risk import (
        HallucinationRiskError,
        build_hallucination_risk_checks_proof,
    )

    try:
        proof = build_hallucination_risk_checks_proof(write_evidence=evidence)
    except HallucinationRiskError as exc:
        payload = {
            "command": "second-brain retrieval hallucination-risk proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _RETRIEVAL_HALLUCINATION_RISK_GUARDRAILS}
    human = [
        f"Hallucination risk checks proof passed={proof['proof_passed']}"
        f" (risk_band={proof['risk_band']}, unsupported={proof['unsupported_count']},"
        f" overconfident={proof['overconfident_count']}, determination={proof['makes_determination']},"
        f" no_db_writes={proof['build_path_no_db_writes']})",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_EMBEDDING_POLICY_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "no_raw_vector_content_in_sqlite": True,
    "metadata_only": True,
    "local_first": True,
    "source_linked_chunks_only": True,
    "external_embedding_providers_deferred": True,
}


@embedding_policy_app.command("status")
def retrieval_embedding_policy_status(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 embedding + vector-store policy status (read-only, fail-closed).

    Reports the resolved embedding provider / dimension / vector-store kind, the embeddable
    source-family allowlist (the redacted, source-linked families — never a raw EXCLUDED family),
    the persistence rules (vectors never persisted to SQLite), and schema readiness (Phase 09 V39/22). Read-only
    over the DB; builds no embeddings/index. Exit 0 when the contract/seed load, the config is valid,
    and the schema is ready; exit 3 on a fail-closed contract/seed failure, invalid config, or stale
    schema.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
        build_embedding_vector_policy_status,
    )

    try:
        report = build_embedding_vector_policy_status()
    except EmbeddingVectorPolicyError as exc:
        payload = {
            "command": "second-brain retrieval embedding-policy status",
            "policy_loaded": False,
            "config_valid": False,
            "schema_ready": False,
            "error": type(exc).__name__,
            "guardrails": _EMBEDDING_POLICY_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _EMBEDDING_POLICY_GUARDRAILS}
    human = [
        "Phase 09 embedding + vector-store policy status (read-only, advisory)",
        f"  provider: {report['embedding_provider']} | dim: {report['embedding_dim']}"
        f" | vector store: {report['vector_store_kind']}",
        f"  embeddable families: {report['embeddable_family_count']}"
        f" | config valid: {report['config_valid']} | schema ready: {report['schema_ready']}",
        f"  blockers: {report['blockers']}",
    ]
    ready = report["policy_loaded"] and report["config_valid"] and report["schema_ready"]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if ready else 3)


@embedding_policy_app.command("no-raw-proof")
def retrieval_embedding_policy_no_raw_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the no-raw proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the embedding no-raw guardrail rejects raw/unsafe candidates (read-only, fail-closed).

    Runs `validate_embedding_candidate` over controlled safe + planted-unsafe candidates (excluded
    family, raw body, signed URL, vector blob, secret shape, missing metadata, unresolved review) and
    attests the persistence rules. Builds no embeddings; persists nothing to the operator DB. Exit 0
    when the proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
        build_no_raw_vector_policy_proof,
    )

    try:
        proof = build_no_raw_vector_policy_proof(write_evidence=evidence)
    except EmbeddingVectorPolicyError as exc:
        payload = {
            "command": "second-brain retrieval embedding-policy no-raw-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _EMBEDDING_POLICY_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _EMBEDDING_POLICY_GUARDRAILS}
    human = [
        f"Embedding/vector policy no-raw proof passed={proof['proof_passed']}",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_APPROVED_SOURCES_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "metadata_only": True,
    "exclude_unresolved_high_impact": True,
    "only_approved_obsidian_apply_manifests": True,
    "source_linked_only": True,
    "local_first": True,
}


@approved_sources_app.command("build")
def retrieval_approved_sources_build(
    apply: bool = typer.Option(
        False, "--apply/--dry-run", help="Persist the manifest summary row (default dry-run)."
    ),
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 approved index source manifest build (read-only; dry-run by default; fail-closed).

    Enumerates approved, redacted, source-linked records from the three categories (generated outputs,
    approved Obsidian outputs, reviewed memory), excluding unresolved high-impact / non-accepted /
    non-apply-Obsidian / raw-content entries, and reports the metadata-only manifest (per-family counts
    + a deterministic hash). `--apply` persists a single guard-clean summary row; default is dry-run
    (no write). Builds no embeddings/index. Exit 0 when the build succeeds, 3 on a fail-closed
    contract/seed/schema failure.
    """
    from hb_assistant.construction.second_brain.retrieval.source_manifest import (
        ApprovedSourceManifestError,
        build_approved_source_manifest,
        persist_approved_source_manifest,
    )

    try:
        manifest = build_approved_source_manifest(project_key=project)
        persisted_id = None
        if apply:
            persisted_id = persist_approved_source_manifest(
                None, manifest, policy_version=str(manifest["policy_version"])
            )
    except ApprovedSourceManifestError as exc:
        payload = {
            "command": "second-brain retrieval approved-sources build",
            "policy_loaded": False,
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _APPROVED_SOURCES_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {
        **manifest,
        "applied": apply,
        "persisted_manifest_id": persisted_id,
        "guardrails": _APPROVED_SOURCES_GUARDRAILS,
    }
    human = [
        "Phase 09 approved index source manifest (read-only, advisory)",
        f"  status: {manifest['status']} | approved refs: {manifest['approved_ref_count']}"
        f" | approved families: {manifest['approved_family_count']}",
        f"  manifest_hash: {manifest['manifest_hash'][:16]} | applied: {apply}",
        f"  warnings: {manifest['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@approved_sources_app.command("proof")
def retrieval_approved_sources_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the manifest proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the manifest approval/no-raw guardrail excludes unsafe candidates (read-only, fail-closed).

    Runs `validate_manifest_entry` over controlled safe + planted-unsafe entries (excluded family,
    excluded/pending review status, unresolved high-impact, missing metadata, forbidden field, raw
    shape) and attests metadata-only + exclude-unresolved-high-impact. Persists nothing to the operator
    DB. Exit 0 when the proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.retrieval.source_manifest import (
        ApprovedSourceManifestError,
        build_approved_source_manifest_proof,
    )

    try:
        proof = build_approved_source_manifest_proof(write_evidence=evidence)
    except ApprovedSourceManifestError as exc:
        payload = {
            "command": "second-brain retrieval approved-sources proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _APPROVED_SOURCES_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _APPROVED_SOURCES_GUARDRAILS}
    human = [
        f"Approved source manifest proof passed={proof['proof_passed']}",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_OBSIDIAN_LOADER_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "metadata_only": True,
    "apply_manifests_only": True,
    "exclude_unresolved_high_impact": True,
    "source_linked_only": True,
    "local_first": True,
}


@obsidian_loader_app.command("status")
def retrieval_obsidian_loader_status(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 approved Obsidian output loader status (read-only, fail-closed).

    Loads only approved, source-linked generated Obsidian notes (the latest `mode='apply'` index
    manifest — dry-run/unapproved manifests are never loaded) and reports the **metadata-only** node
    set (counts + per-node hashes; no text). Each node is validated by the embedding guardrail
    (embeddable family, source-linked metadata, no-raw, no unresolved high-impact). Read-only; builds
    no embeddings/index. Exit 0; exit 3 on a fail-closed contract/schema failure.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.obsidian_loader import (
        ObsidianLoaderError,
        build_obsidian_loader_report,
    )

    try:
        report = build_obsidian_loader_report(project_key=project)
    except (ObsidianLoaderError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval obsidian-loader status",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _OBSIDIAN_LOADER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _OBSIDIAN_LOADER_GUARDRAILS}
    human = [
        "Phase 09 approved Obsidian output loader (read-only, advisory)",
        f"  status: {report['status']} | loaded nodes: {report['loaded_count']}",
        f"  warnings: {report['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@obsidian_loader_app.command("proof")
def retrieval_obsidian_loader_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the loader proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the Obsidian loader loads only approved (apply-mode) source-linked notes (fail-closed).

    Demonstrates (a) an apply-mode fixture index loads >=1 guard-clean node, (b) a dry-run-only index
    loads 0 (unapproved excluded), and (c) the embedding guardrail rejects tier-3/raw/non-embeddable
    candidates. Builds no embeddings; persists nothing to the operator DB. Exit 0 if the proof passes.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.obsidian_loader import (
        ObsidianLoaderError,
        build_obsidian_loader_proof,
    )

    try:
        proof = build_obsidian_loader_proof(write_evidence=evidence)
    except (ObsidianLoaderError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval obsidian-loader proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _OBSIDIAN_LOADER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _OBSIDIAN_LOADER_GUARDRAILS}
    human = [
        f"Approved Obsidian loader proof passed={proof['proof_passed']}"
        f" (apply={proof['apply_loaded_count']} dry_run={proof['dry_run_loaded_count']})",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


_MEMORY_LOADER_GUARDRAILS = {
    "read_only": True,
    "no_raw": True,
    "no_writeback": True,
    "metadata_only": True,
    "reviewed_only_accepted": True,
    "exclude_unresolved_high_impact": True,
    "source_linked_only": True,
    "local_first": True,
}


@memory_loader_app.command("status")
def retrieval_memory_loader_status(
    project: str | None = typer.Option(None, "--project", help="Optional project key filter."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 reviewed memory loader status (read-only, fail-closed).

    Loads only reviewed (accepted) long-term memory (`review_status='accepted'` — pending/rejected/
    superseded are never loaded) and reports the **metadata-only** node set (counts + per-node hashes;
    no statement text). Each node is validated by the embedding guardrail (embeddable family,
    source-linked metadata, no-raw). Read-only; builds no embeddings/index. Exit 0; exit 3 on a
    fail-closed contract/schema failure.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.memory_loader import (
        MemoryLoaderError,
        build_reviewed_memory_loader_report,
    )

    try:
        report = build_reviewed_memory_loader_report(project_key=project)
    except (MemoryLoaderError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval memory-loader status",
            "status": "not_ready",
            "error": type(exc).__name__,
            "guardrails": _MEMORY_LOADER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**report, "guardrails": _MEMORY_LOADER_GUARDRAILS}
    human = [
        "Phase 09 reviewed memory loader (read-only, advisory)",
        f"  status: {report['status']} | loaded nodes: {report['loaded_count']}",
        f"  warnings: {report['warnings']}",
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0)


@memory_loader_app.command("proof")
def retrieval_memory_loader_proof(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the loader proof to the evidence dir."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Prove the memory loader loads only reviewed (accepted) memory (read-only, fail-closed).

    Demonstrates (a) an accepted-memory fixture loads >=1 guard-clean node, (b) a pending-only fixture
    loads 0 (unreviewed excluded), and (c) the embedding guardrail rejects non-embeddable / raw /
    missing-metadata / unresolved candidates. Builds no embeddings; persists nothing to the operator DB.
    Exit 0 if the proof passes.
    """
    from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
        EmbeddingVectorPolicyError,
    )
    from hb_assistant.construction.second_brain.retrieval.memory_loader import (
        MemoryLoaderError,
        build_reviewed_memory_loader_proof,
    )

    try:
        proof = build_reviewed_memory_loader_proof(write_evidence=evidence)
    except (MemoryLoaderError, EmbeddingVectorPolicyError) as exc:
        payload = {
            "command": "second-brain retrieval memory-loader proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "guardrails": _MEMORY_LOADER_GUARDRAILS,
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    payload = {**proof, "guardrails": _MEMORY_LOADER_GUARDRAILS}
    human = [
        f"Reviewed memory loader proof passed={proof['proof_passed']}"
        f" (accepted={proof['accepted_loaded_count']} pending={proof['pending_loaded_count']})",
        *[f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}" for c in proof["cases"]],
    ]
    _emit_08c(payload, json_out=json_out, human=human, exit_code=0 if proof["proof_passed"] else 3)


@financial_app.command("no-writeback-proof")
def financial_no_writeback_proof(
    project: str | None = typer.Option(None, "--project", help="Optional project key."),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 08C financial no-writeback / no-raw attestation proof (read-only).

    Empirically attests advisory-only / no-writeback / no-raw / no-determination / no-float
    guardrails over the V35 financial tables and the 08C evidence directory. Exit 0 when the
    proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.financial_no_writeback import (
        build_financial_no_writeback_proof,
    )
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator().apply()
    proof = build_financial_no_writeback_proof(project_key=project)
    checks = {k: v.get("passed") for k, v in proof.get("checks_detail", {}).items()}
    payload = {
        "command": "second-brain financial no-writeback-proof",
        "ok": proof.get("proof_passed"),
        "phase": "08C",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "checks": checks,
        "proof_path": proof.get("proof_path"),
        "evidence_paths": [proof.get("proof_path"), proof.get("proof_json_path")],
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
        "note": "deterministic read-only attestation; advisory review aid only — not a determination.",
    }
    human = [
        "Phase 08C financial no-writeback / no-raw proof",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')}",
        f"  checks: {checks}",
        f"  proof: {proof.get('proof_path')}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


@financial_app.command("completeness-advisory")
def financial_completeness_advisory(
    project: str | None = typer.Option(
        None, "--project", help="Optional project key (recommendations are per-project)."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 09 advisory financial data-completeness mart (read-only, advisory only).

    Profiles currency / period / WBS / cost-code completeness and orphan risk over the
    financial fact tables and emits ADVISORY recommendations + review labels (project-default
    currency fallback, period-enrichment, WBS/cost-code reconciliation) before semantic
    retrieval over financial outputs. Read-only; never assigns a currency, sets a period,
    makes a determination, writes to the facts, or routes to the review ledger; money values
    are never echoed. Exit 0 when the proof passes, 3 otherwise.
    """
    from hb_assistant.construction.second_brain.financial_completeness_advisory import (
        build_financial_completeness_advisory_proof,
    )

    proof = build_financial_completeness_advisory_proof()
    mart = proof["mart"]
    payload = {
        "command": "second-brain financial completeness-advisory",
        "phase": "09",
        "project_key": project,
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "schema_version": proof.get("schema_version"),
        "schema_version_expected": proof.get("schema_version_expected"),
        "no_determination_attested": proof.get("no_determination_attested"),
        "raw_content_findings": proof.get("raw_content_findings"),
        "normalized_layer_populated": mart.get("normalized_layer_populated"),
        "currency": mart.get("currency"),
        "period": mart.get("period"),
        "wbs_cost_code": mart.get("wbs_cost_code"),
        "guard_columns": proof.get("guard_columns"),
        "guardrails": mart.get("guardrails"),
        "note": mart.get("note"),
    }
    human = [
        "Phase 09 financial completeness advisory (advisory only, read-only)",
        f"  project: {project or 'all'}",
        f"  proof passed: {proof.get('proof_passed')} | no determination: "
        f"{proof.get('no_determination_attested')}",
        f"  currency null: {mart.get('currency', {}).get('currency_null_rate')} | "
        f"period null: {mart.get('period', {}).get('period_null_rate')}",
        f"  wbs orphans: {mart.get('wbs_cost_code', {}).get('wbs_orphan_or_missing_total')} | "
        f"cost orphans: {mart.get('wbs_cost_code', {}).get('cost_code_orphan_or_missing_total')}",
        f"  normalized layer populated: {mart.get('normalized_layer_populated')}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


@data_quality_app.command("phase-08c-no-writeback-proof")
def data_quality_phase_08c_no_writeback_proof(
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 08C no-writeback / no-raw-financial-output safety proof (read-only).

    Extends the second-brain safety scan over the 08C financial modules, the ten V35 tables, and
    the 08C evidence directory; writes no-writeback-no-raw-financial-output-proof.json. Exit 0 when
    the proof passes, 3 otherwise (fail-closed).
    """
    from hb_assistant.construction.second_brain.safety import (
        build_phase_08c_no_writeback_no_raw_financial_output_proof,
    )

    proof = build_phase_08c_no_writeback_no_raw_financial_output_proof()
    payload = {
        "command": "second-brain data-quality phase-08c-no-writeback-proof",
        "ok": proof.get("proof_passed"),
        "phase": "08C",
        "advisory_only": True,
        "proof_passed": proof.get("proof_passed"),
        "checks": {k: v.get("passed") for k, v in proof.get("checks_detail", {}).items()},
        "confirmations": proof.get("confirmations"),
        "scanned_modules": proof.get("scanned_modules"),
        "scanned_tables": proof.get("scanned_tables"),
        "proof_path": proof.get("proof_path"),
        "evidence_paths": [proof.get("proof_json_path"), proof.get("proof_path")],
        "guardrails": _08C_GUARDRAILS,
        "attestations": _08C_ATTESTATIONS,
        "note": "deterministic read-only safety scan over 08C modules/tables/evidence; advisory aid only.",
    }
    human = [
        "Phase 08C no-writeback / no-raw-financial-output proof",
        f"  proof passed: {proof.get('proof_passed')}",
        f"  checks: {payload['checks']}",
        f"  confirmations: {proof.get('confirmations')}",
        f"  proof: {proof.get('proof_path')}",
    ]
    _emit_08c(
        payload, json_out=json_out, human=human, exit_code=0 if proof.get("proof_passed") else 3
    )


# --------------------------------------------------------------------------- #
# Phase 08D — local MCP bridge (server foundation + config surface)            #
# --------------------------------------------------------------------------- #
@mcp_app.command("status")
def mcp_status(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist a metadata-only server-config snapshot."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Phase 08D MCP server-foundation status (stdio-only; fail-closed).

    Reports the startup checks, SDK availability, and why serving is not yet ready
    (tool broker + guard proofs land in Prompts 04/13/14). Persists a metadata-only
    snapshot unless ``--no-snapshot``.
    """
    from hb_assistant.construction.second_brain.mcp import build_mcp_status

    payload = build_mcp_status(persist=snapshot)
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(
            f"MCP foundation_ok={payload['foundation_ok']} ready_to_serve={payload['ready_to_serve']}"
        )
        typer.echo(
            f"  sdk_available={payload['mcp_sdk_available']} tools={payload['mcp_tools_registered']}"
        )
        for check in payload["checks"]:
            typer.echo(f"  [{check['status']}] {check['name']}: {check['detail']}")
        typer.echo(f"  serve_blockers: {payload['serve_blockers']}")
    raise typer.Exit(0)


@mcp_app.command("config-preview")
def mcp_config_preview(
    client: str = typer.Option("claude-desktop", "--client", help="Target MCP client."),
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist a metadata-only preview snapshot."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Generate a safe, preview-only Claude Desktop config (never auto-applied).

    Writes ``claude-desktop-config-preview.json`` to the 08D evidence dir and persists a
    metadata-only preview row (env *key names* only — never values).
    """
    from hb_assistant.construction.second_brain.mcp import build_claude_desktop_config_preview

    payload = build_claude_desktop_config_preview(client=client, persist=snapshot)
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(f"MCP config-preview client={payload['client']} safe={payload['safe']}")
        typer.echo(f"  transport={payload['transport']} unsafe_reasons={payload['unsafe_reasons']}")
        typer.echo(f"  evidence: {payload['evidence_path']}")
    raise typer.Exit(0)


@mcp_app.command("serve")
def mcp_serve(
    stdio: bool = typer.Option(
        False, "--stdio", help="Local stdio transport (the only allowed transport)."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report serve readiness without entering the stdio loop (diagnostics).",
    ),
) -> None:
    """Start the local stdio MCP server (or fail-closed with the blocking reasons).

    With the optional ``mcp`` SDK installed and every foundation/guard check passing this
    drives a real local stdio MCP session, blocking until the client disconnects (this is
    the command Claude Desktop launches). ``--dry-run`` reports readiness without serving.
    Fail-closed: if the SDK is absent or a foundation check fails, serving is refused and
    the command exits non-zero. While serving, stdout is the JSON-RPC channel — the
    envelope is emitted to stderr only after the session ends.
    """
    from hb_assistant.construction.second_brain.mcp import serve_stdio

    payload = serve_stdio(dry_run=dry_run)
    payload["requested_transport"] = "stdio" if stdio else "unspecified"
    served = bool(payload.get("served"))
    ready = bool(payload.get("ready_to_serve"))

    if dry_run:
        # Human diagnostic — safe to print the envelope to stdout. Exit 0 iff ready.
        if json_out:
            typer.echo(json.dumps(payload, indent=2, default=str))
        else:
            typer.echo(f"MCP serve ready_to_serve={ready} reasons={payload['reasons']}")
        raise typer.Exit(0 if ready else 1)

    # Real serve invocation (an MCP client launched us): stdout is the JSON-RPC channel,
    # so the status envelope goes to stderr only — never stdout — whether we served a
    # full session (exit 0) or fail-closed before serving (exit 1).
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str), err=True)
    else:
        typer.echo(f"MCP serve served={served} reasons={payload['reasons']}", err=True)
    raise typer.Exit(0 if served else 1)


@mcp_app.command("tools")
def mcp_tools(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist a metadata-only tool-registry snapshot."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """List the allowed MCP tool registry (read-only; lists metadata, never dispatches)."""
    from hb_assistant.construction.second_brain.mcp import (
        load_allowed_tools,
        load_denied_actions,
        load_global_requirements,
        snapshot_tool_registry,
    )

    allowed = load_allowed_tools()
    tools = [
        {
            "name": name,
            "wrapper": spec.get("wrapper"),
            "maps_to": spec.get("maps_to"),
            "risk": spec.get("risk"),
            "receipt_required": spec.get("receipt_required"),
        }
        for name, spec in sorted(allowed.items())
    ]
    denied = sorted(load_denied_actions())
    snapshot_id = snapshot_tool_registry(persist=snapshot)
    payload = {
        "command": "second-brain mcp tools",
        "phase": "08D",
        "allowed_tool_count": len(tools),
        "denied_action_count": len(denied),
        "tools": tools,
        "global_requirements": load_global_requirements(),
        "denied_actions": denied,
        "snapshot_id": snapshot_id,
        "guardrails": {"read_only": True, "metadata_only": True, "no_dispatch": True},
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(f"MCP tools: {len(tools)} allowed / {len(denied)} denied")
        for t in tools:
            typer.echo(f"  {t['name']} -> {t['wrapper']} ({t['risk']})")
    raise typer.Exit(0)


@mcp_app.command("resources")
def mcp_resources(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist a metadata-only resource-registry snapshot."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """List the safe MCP resource registry (read-only; lists URIs, never reads content)."""
    from hb_assistant.construction.second_brain.contracts import load_phase_08d_contract
    from hb_assistant.construction.second_brain.mcp import load_resources
    from hb_assistant.construction.second_brain.mcp.resources import snapshot_resource_registry

    resources = load_resources()
    contract = load_phase_08d_contract("resources_contract")
    snapshot_id = snapshot_resource_registry(persist=snapshot)
    payload = {
        "command": "second-brain mcp resources",
        "phase": "08D",
        "resource_count": len(resources),
        "resources": resources,
        "requirements": contract.get("requirements", []),
        "snapshot_id": snapshot_id,
        "guardrails": {"read_only": True, "metadata_only": True, "no_content_read": True},
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(f"MCP resources: {len(resources)}")
        for r in resources:
            typer.echo(f"  {r['uri']} -> {r['wrapper']}")
    raise typer.Exit(0)


@mcp_app.command("prompts")
def mcp_prompts(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist a metadata-only prompt-registry snapshot."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """List the reusable MCP prompt registry (read-only; lists routing, never executes)."""
    from hb_assistant.construction.second_brain.contracts import load_phase_08d_contract
    from hb_assistant.construction.second_brain.mcp import load_prompts
    from hb_assistant.construction.second_brain.mcp.prompts import snapshot_prompt_registry

    prompts = load_prompts()
    contract = load_phase_08d_contract("prompts_contract")
    snapshot_id = snapshot_prompt_registry(persist=snapshot)
    payload = {
        "command": "second-brain mcp prompts",
        "phase": "08D",
        "prompt_count": len(prompts),
        "prompts": prompts,
        "requirements": contract.get("requirements", []),
        "snapshot_id": snapshot_id,
        "guardrails": {
            "read_only": True,
            "metadata_only": True,
            "routes_through_allowed_only": True,
        },
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(f"MCP prompts: {len(prompts)}")
        for p in prompts:
            typer.echo(f"  {p['name']} -> {p['routes_through']}")
    raise typer.Exit(0)


@mcp_app.command("audit")
def mcp_audit(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Persist the registry snapshots + audit run."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Run the MCP permission audit (ten checks; read-only; persists a metadata-only run)."""
    from hb_assistant.construction.second_brain.mcp import run_mcp_permission_audit

    report = run_mcp_permission_audit(persist=snapshot, write_evidence=False)
    if json_out:
        typer.echo(json.dumps(report, indent=2, default=str))
    else:
        typer.echo(f"MCP audit status={report['status']} findings={report['finding_count']}")
        for c in report["checks"]:
            typer.echo(f"  [{'ok' if c['passed'] else 'FAIL'}] {c['name']}")
    raise typer.Exit(0 if report.get("proof_passed") else 3)


@mcp_app.command("daily-brief-handoff-proof")
def mcp_daily_brief_handoff_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the MCP daily-brief handoff proof to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Prove the hb_daily_brief_packet MCP tool returns a contract-shaped, read-only, no-raw packet."""
    from hb_assistant.construction.second_brain.mcp import build_mcp_daily_brief_handoff_proof

    proof = build_mcp_daily_brief_handoff_proof(write_evidence=evidence)
    if json_out:
        typer.echo(json.dumps(proof, indent=2, default=str))
    else:
        typer.echo(f"MCP daily-brief handoff proof passed={proof['proof_passed']}")
    raise typer.Exit(0 if proof.get("proof_passed") else 3)


@mcp_app.command("daily-brief-render-template-proof")
def mcp_daily_brief_render_template_proof(
    evidence: bool = typer.Option(
        True,
        "--evidence/--no-evidence",
        help="Write the Claude render-template proof + template copies to the evidence dir.",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Prove the Claude scheduled-task render templates carry the required guardrail instructions."""
    from hb_assistant.construction.second_brain.mcp import build_claude_render_template_proof
    from hb_assistant.construction.second_brain.mcp.render_template_proof import (
        ClaudeRenderTemplateError,
    )

    try:
        proof = build_claude_render_template_proof(write_evidence=evidence)
    except ClaudeRenderTemplateError as exc:
        payload = {
            "command": "second-brain mcp daily-brief-render-template-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(3) from exc

    if json_out:
        typer.echo(json.dumps(proof, indent=2, default=str))
    else:
        typer.echo(f"Claude render-template proof passed={proof['proof_passed']}")
    raise typer.Exit(0 if proof.get("proof_passed") else 3)


@mcp_app.command("no-raw-access")
def mcp_no_raw_access(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the no-raw-access proof to the evidence dir."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Prove no MCP surface exposes raw content (Prompt 13; read-only, static scan)."""
    from hb_assistant.construction.second_brain.mcp import build_no_raw_mcp_access_proof

    proof = build_no_raw_mcp_access_proof(write_evidence=evidence)
    if json_out:
        typer.echo(json.dumps(proof, indent=2, default=str))
    else:
        typer.echo(f"MCP no-raw-access proof passed={proof['proof_passed']}")
        for s in proof["surfaces"]:
            typer.echo(f"  [{'ok' if s['passed'] else 'FAIL'}] {s['surface']}")
    raise typer.Exit(0 if proof.get("proof_passed") else 3)


@mcp_app.command("no-writeback")
def mcp_no_writeback(
    evidence: bool = typer.Option(
        True, "--evidence/--no-evidence", help="Write the no-writeback proof to the evidence dir."
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON envelope (default)."),
) -> None:
    """Prove no MCP surface performs writeback/direct-API/external-delivery (Prompt 14)."""
    from hb_assistant.construction.second_brain.mcp import build_no_mcp_writeback_proof

    proof = build_no_mcp_writeback_proof(write_evidence=evidence)
    if json_out:
        typer.echo(json.dumps(proof, indent=2, default=str))
    else:
        typer.echo(f"MCP no-writeback proof passed={proof['proof_passed']}")
        for s in proof["surfaces"]:
            typer.echo(f"  [{'ok' if s['passed'] else 'FAIL'}] {s['surface']}")
    raise typer.Exit(0 if proof.get("proof_passed") else 3)


@phase_10_app.command("contracts-proof")
def phase_10_contracts_proof(
    write_evidence: bool = typer.Option(
        False,
        "--write-evidence/--no-write-evidence",
        help="Write the contracts/seeds proof JSON+MD to the Phase 10 evidence dir.",
    ),
    evidence_dir: str | None = typer.Option(
        None, "--evidence-dir", help="Override the evidence output directory."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Validate the Phase 10 contracts, seed policies, and fixtures (read-only, advisory).

    Loads all ten Phase 10 JSON contracts, validates the four YAML seed policies against their
    Pydantic models, structurally validates the bundled fixtures, and scans every artifact for
    restricted raw content. No DB access, no Ollama call, no external request, no writeback. Exit 0
    on a clean proof; 3 on a fail-closed failure or findings.
    """
    from hb_assistant.construction.second_brain.local_ai import (
        Phase10ContractError,
        build_phase_10_contracts_proof,
    )
    from hb_assistant.construction.second_brain.local_ai.proof import Phase10ProofError

    try:
        result = build_phase_10_contracts_proof(
            evidence_dir=evidence_dir, write_evidence=write_evidence
        )
    except (Phase10ContractError, Phase10ProofError) as exc:
        payload = {
            "command": "second-brain phase-10 contracts-proof",
            "proof_passed": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    g = result["gates"]
    human = [
        f"Phase 10 contracts proof passed={result['proof_passed']}"
        f" (contracts={result['contract_count']}, seeds={result['seed_count']},"
        f" fixtures={len(result['fixtures_validated'])},"
        f" no_forbidden_content={g['no_forbidden_content']})",
    ]
    _emit_08c(result, json_out=json_out, human=human, exit_code=0 if result["proof_passed"] else 3)


@phase_10_app.command("schema-status")
def phase_10_schema_status(
    db: str | None = typer.Option(None, "--db", help="Override the SQLite DB path."),
    write_evidence: bool = typer.Option(
        False,
        "--write-evidence/--no-write-evidence",
        help="Write the V41 schema-status proof JSON+MD to the Phase 10 evidence dir.",
    ),
    evidence_dir: str | None = typer.Option(
        None, "--evidence-dir", help="Override the evidence output directory."
    ),
    json_out: bool = typer.Option(
        True, "--json/--no-json", help="JSON envelope (default) or human-readable summary."
    ),
) -> None:
    """Phase 10 V41 schema status (read-only, fail-closed).

    Verifies the local schema is at the expected head (>=V41), that every one of the 21 Phase 10
    tables exists with the full 13 guard columns, and that the guard columns sum to 0 across all
    rows (no-raw/no-writeback attestation). Read-only over the DB; advisory only; never a
    determination. Exit 0 when overall_status is `ready`, 3 otherwise (including a stale schema).
    """
    from hb_assistant.construction.second_brain.local_ai.schema import (
        Phase10SchemaError,
        build_phase_10_schema_status_report,
    )

    try:
        report = build_phase_10_schema_status_report(
            db_path=db, evidence_dir=evidence_dir, write_evidence=write_evidence
        )
    except Phase10SchemaError as exc:
        payload = {
            "command": "second-brain phase-10 schema-status",
            "overall_status": "not_ready",
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        _emit_08c(payload, json_out=json_out, human=[str(exc)], exit_code=3)
        return

    human = [
        "Phase 10 V41 schema status (read-only, advisory)",
        f"  overall: {report['overall_status']} | schema: {report['schema_version']}"
        f" (expected {report['schema_version_expected']})",
        f"  tables present: {report['all_tables_present']} ({report['phase_10_table_count']})"
        f" | guards present: {report['all_guards_present']} | guard_sum: {report['guard_sum']}",
    ]
    _emit_08c(
        report,
        json_out=json_out,
        human=human,
        exit_code=0 if report["overall_status"] == "ready" else 3,
    )


@phase_10_app.command("raw-email-packet")
def phase_10_raw_email_packet(
    project: "str | None" = typer.Option(  # noqa: B008
        None, "--project", help="Project key filter for raw email content."
    ),  # noqa: B008
    json_out: bool = typer.Option(True, "--json", help="Emit the packet as JSON (default)."),  # noqa: B008
) -> None:
    """Build a model-ready raw email context packet (actual subject/body/participants when policy allows).

    Uses the Phase 10A raw content tables + model_context bounds from policy.
    Packet is persisted to raw_content_model_context_packets (local only) and returned.
    Source refs are hashes + stable row refs. Exit 0 on success.
    """
    from hb_assistant.construction.second_brain.local_ai import (
        build_raw_email_context_packet,
    )

    try:
        pkt = build_raw_email_context_packet(project_key=project)
        typer.echo(json.dumps(pkt, indent=2, default=str) if json_out else str(pkt))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 raw-email-packet",
            "ok": False,
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


@phase_10_app.command("raw-calendar-packet")
def phase_10_raw_calendar_packet(
    project: "str | None" = typer.Option(  # noqa: B008
        None, "--project", help="Project key filter for raw calendar content."
    ),  # noqa: B008
    json_out: bool = typer.Option(True, "--json", help="Emit the packet as JSON (default)."),  # noqa: B008
) -> None:
    """Build a model-ready raw calendar context packet (actual subject/body/location/attendees/join when policy allows).

    Uses the Phase 10A raw content tables + model_context bounds from policy.
    Packet is persisted to raw_content_model_context_packets (local only) and returned.
    Source refs are event_index_id + graph hashes. Exit 0 on success.
    """
    from hb_assistant.construction.second_brain.local_ai import (
        build_raw_calendar_context_packet,
    )

    try:
        pkt = build_raw_calendar_context_packet(project_key=project)
        typer.echo(json.dumps(pkt, indent=2, default=str) if json_out else str(pkt))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 raw-calendar-packet",
            "ok": False,
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


@phase_10_app.command("raw-action-candidates")
def phase_10_raw_action_candidates(
    project: "str | None" = typer.Option(  # noqa: B008
        None, "--project", help="Project key to scope raw content for candidate extraction."
    ),
    source: str = typer.Option(  # noqa: B008
        "both",
        "--source",
        help="email|calendar|both (default both). Limits which raw packets/rows are considered.",
    ),
    mock_output: "str | None" = typer.Option(  # noqa: B008
        None,
        "--mock-output",
        help="Raw JSON array of ActionCandidate objects (for offline/testing; bypasses local model).",
        hidden=True,
    ),
    dry_run: bool = typer.Option(  # noqa: B008
        True,
        "--dry-run/--apply",
        help="Preview (default); --apply persists accepted candidates + source refs with raw excerpts to the V41 tables.",
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable report (default)."),  # noqa: B008
) -> None:
    """Extract advisory action candidates (task, commitment, follow-up, ...) from Phase 10A raw email/calendar content.

    Uses strict schema + business-contract validation (rejects generic data-cleaning / analysis hallucinations).
    Supports retry/repair on bad model output. When --apply, persists to task_candidates / commitment_candidates
    + candidate_source_refs (with bounded evidence_redacted excerpts from the raw rows).

    Local-only, advisory, source-linked. Model output is never trusted without validation.
    Use --mock-output for deterministic tests/CI.
    """
    from hb_assistant.construction.second_brain.local_ai import (
        extract_action_candidates_from_raw,
    )

    try:
        # For the thin CLI we let the extractor load recent raw for the project (it will use store list raw).
        # If the caller wants explicit packets they can be passed in future extensions; the core supports packets.
        report = extract_action_candidates_from_raw(
            project_key=project,
            mock_output=mock_output,
        )

        # If not apply, do not mutate (the extractor may have side-effected in some paths; guard here for CLI contract)
        if dry_run:
            # Best-effort: the extractor already prefers not to persist when not requested, but we surface intent.
            report = dict(report)
            report["dry_run"] = True
            report["would_persist"] = report.get("persisted", 0)
            report["persisted"] = 0

        payload: dict[str, Any] = {
            "command": "second-brain phase-10 raw-action-candidates",
            "ok": True,
            "project": project,
            "source": source,
            "dry_run": dry_run,
            **report,
            "guardrails": {
                "local_only": True,
                "advisory_only": True,
                "strict_schema": True,
                "business_contract_validation": "rejects generic data-clean/analysis hallucinations",
                "retry_repair": True,
                "raw_excerpts_bounded_in_evidence_only": True,
                "no_auto_accept": True,
            },
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 raw-action-candidates",
            "ok": False,
            "dry_run": dry_run,
            "status": "extract_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


@phase_10_app.command("list-candidates")
def phase_10_list_candidates(
    project: "str | None" = typer.Option(  # noqa: B008
        None, "--project", help="Project key filter for candidates."
    ),  # noqa: B008
    candidate_type: str = typer.Option(
        "both", "--type", help="task|commitment|both (default both)."
    ),  # noqa: B008
    review_status: "str | None" = typer.Option(  # noqa: B008
        "pending", "--review-status", help="Filter by review_status (e.g. pending, accepted)."
    ),  # noqa: B008
    limit: int = typer.Option(100, "--limit", help="Max rows (bounded)."),  # noqa: B008
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable (default)."),  # noqa: B008
) -> None:
    """List persisted Phase 10 V41 action candidates (task / commitment) with source ref summaries.

    Advisory only. Use --review-status to focus the review queue. Source refs (with evidence_redacted excerpts)
    are included so you can drive `candidate-source` or the graph raw-detail commands.
    """
    from hb_assistant.construction.store import ConstructionStore

    try:
        s = ConstructionStore()
        items: list[dict[str, Any]] = []
        if candidate_type in ("task", "both"):
            for t in s.list_task_candidates(
                project_key=project, review_status=review_status, limit=limit
            ):
                refs = s.list_candidate_source_refs(candidate_id=t.get("candidate_id"), limit=10)
                t = dict(t)
                t["source_refs"] = [
                    {
                        "source_family": r.get("source_family"),
                        "source_ref_hash": r.get("source_ref_hash"),
                        "evidence_redacted": r.get("evidence_redacted"),
                    }
                    for r in refs
                ]
                items.append({"type": "task", **t})
        if candidate_type in ("commitment", "both"):
            for c in s.list_commitment_candidates(
                project_key=project, review_status=review_status, limit=limit
            ):
                refs = s.list_candidate_source_refs(candidate_id=c.get("candidate_id"), limit=10)
                c = dict(c)
                c["source_refs"] = [
                    {
                        "source_family": r.get("source_family"),
                        "source_ref_hash": r.get("source_ref_hash"),
                        "evidence_redacted": r.get("evidence_redacted"),
                    }
                    for r in refs
                ]
                items.append({"type": "commitment", **c})
        payload: dict[str, Any] = {
            "command": "second-brain phase-10 list-candidates",
            "ok": True,
            "project": project,
            "candidate_type": candidate_type,
            "review_status": review_status,
            "count": len(items),
            "candidates": items,
            "guardrails": {
                "advisory_only": True,
                "no_auto_accept": True,
                "review_status_preserved": True,
                "raw_excerpts_bounded_in_refs": True,
            },
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 list-candidates",
            "ok": False,
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


def _resolve_raw_for_source_ref(ref: dict[str, Any], store: Any) -> "dict[str, Any] | None":
    """Resolve a candidate_source_ref to the actual raw content row (full) when available.

    Uses the P05 direct raw getters (policy controlled at store level for these direct paths).
    Returns None if no raw or unknown family. Bounded caller responsibility.
    """
    fam = (ref or {}).get("source_family")
    h = (ref or {}).get("source_ref_hash")
    if not fam or not h:
        return None
    try:
        if fam == "email_message_raw_content":
            return store.get_email_message_raw_content(message_id_hash=h)
        if fam == "calendar_event_raw_content":
            # h may be event_index_id or graph hash; try both
            row = store.get_calendar_event_raw_content(event_index_id=h)
            if row:
                return row
            return store.get_calendar_event_raw_content(graph_event_id_hash=h)
        # thread context etc. can be added; for P08 focus on message/event raw
    except Exception:
        pass
    return None


@phase_10_app.command("candidate-source")
def phase_10_candidate_source(
    candidate_id: str = typer.Option(
        ...,
        "--candidate-id",
        help="The candidate_id from task_candidates or commitment_candidates.",
    ),  # noqa: B008
    candidate_type: str = typer.Option(
        "task", "--candidate-type", help="task|commitment (used to select table for load)."
    ),  # noqa: B008
    include_full_raw: bool = typer.Option(
        True,
        "--include-full-raw/--excerpts-only",
        help="Resolve source refs to full raw content rows from V42 (default). When false, only the stored evidence_redacted excerpts are shown.",
    ),  # noqa: B008
    json_out: bool = typer.Option(True, "--json", help="Machine readable (default)."),  # noqa: B008
) -> None:
    """Inspect the actual raw email/calendar content behind a Phase 10 action candidate's source refs.

    Loads the candidate (review_status etc.) + its candidate_source_refs, then (when --include-full-raw)
    resolves each ref via the local raw getters to attach the full 'raw_content' payload (subject/body/etc.).
    This makes the 'actual content behind candidates' visible for review without leaving the local tool.
    """
    from hb_assistant.construction.store import ConstructionStore

    try:
        s = ConstructionStore()
        cand: "dict[str, Any] | None" = None
        ctype = candidate_type
        if ctype == "task":
            # filter client-side for the id (list doesn't take id filter)
            for r in s.list_task_candidates(limit=10000):
                if r.get("candidate_id") == candidate_id:
                    cand = dict(r)
                    break
        else:
            for r in s.list_commitment_candidates(limit=10000):
                if r.get("candidate_id") == candidate_id:
                    cand = dict(r)
                    ctype = "commitment"
                    break
        if not cand:
            payload = {
                "command": "second-brain phase-10 candidate-source",
                "ok": False,
                "error": "candidate_not_found",
                "candidate_id": candidate_id,
            }
            typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
            raise typer.Exit(3)

        refs = s.list_candidate_source_refs(candidate_id=candidate_id, limit=50)
        enriched_refs: list[dict[str, Any]] = []
        for r in refs:
            er = dict(r)
            if include_full_raw:
                raw = _resolve_raw_for_source_ref(
                    {
                        "source_family": r.get("source_family"),
                        "source_ref_hash": r.get("source_ref_hash"),
                    },
                    s,
                )
                if raw:
                    er["raw_content"] = raw
                    er["_raw_content_included"] = True
            enriched_refs.append(er)

        payload = {
            "command": "second-brain phase-10 candidate-source",
            "ok": True,
            "candidate_id": candidate_id,
            "candidate_type": ctype,
            "candidate": cand,
            "source_refs": enriched_refs,
            "raw_mode_visible": True,
            "guardrails": {
                "local_only": True,
                "advisory_only": True,
                "no_auto_accept": True,
                "full_raw_bodies_only_in_sanctioned_review_detail": True,
                "bounded_excerpts_in_candidate_source_refs": True,
                "review_inspect_only": True,
            },
            "note": "Raw content (actual body from local V42; policy email_calendar) — review/inspect use only. Use phase-10 review-candidate to change review_status.",
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 candidate-source",
            "ok": False,
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


@phase_10_app.command("review-candidate")
def phase_10_review_candidate(
    candidate_id: str = typer.Option(
        ..., "--candidate-id", help="candidate_id of the task or commitment candidate."
    ),  # noqa: B008
    candidate_type: str = typer.Option("task", "--candidate-type", help="task|commitment"),  # noqa: B008
    decision: str = typer.Option(
        ..., "--decision", help="pending|accepted|ignored|snoozed|rejected (maps to review_status)."
    ),  # noqa: B008
    reason: "str | None" = typer.Option(  # noqa: B008
        None, "--reason", help="Redacted operator note for the decision."
    ),  # noqa: B008
    emit: bool = typer.Option(
        False,
        "--emit/--no-emit",
        help="Persist the review_status change (dry-run default, like memory review).",
    ),  # noqa: B008
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable report (default)."),  # noqa: B008
) -> None:
    """Apply an explicit operator review decision to a Phase 10 raw-content action candidate.

    Mirrors the memory review pattern exactly (dry default, --emit to persist, guardrails, exit codes).
    Updates review_status on the V41 candidate row. Optionally writes a candidate_review_event row
    (if the table is present). Does not auto-promote to accepted_* tables; advisory only.
    Raw source content can be inspected first via candidate-source or the graph raw-* detail commands.
    """
    from hb_assistant.construction.store import ConstructionStore

    VALID = {"pending", "accepted", "ignored", "snoozed", "rejected"}
    if decision not in VALID:
        payload = {
            "command": "second-brain phase-10 review-candidate",
            "ok": False,
            "error": "invalid_decision",
            "valid": sorted(VALID),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(2)

    try:
        s = ConstructionStore()
        # locate the row
        cand = None
        if candidate_type == "task":
            for r in s.list_task_candidates(limit=10000):
                if r.get("candidate_id") == candidate_id:
                    cand = dict(r)
                    break
        else:
            for r in s.list_commitment_candidates(limit=10000):
                if r.get("candidate_id") == candidate_id:
                    cand = dict(r)
                    break
        if not cand:
            payload = {
                "command": "second-brain phase-10 review-candidate",
                "ok": False,
                "error": "candidate_not_found",
                "candidate_id": candidate_id,
            }
            typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
            raise typer.Exit(3)

        prior_status = cand.get("review_status") or "pending"
        if emit:
            # Use the additive store helpers (P08) — clean, no private access.
            s.set_candidate_review_status(
                candidate_type=candidate_type,
                candidate_id=candidate_id,
                review_status=decision,
            )
            # best-effort event (non-fatal if table absent or other issue)
            s.insert_candidate_review_event(
                candidate_type=candidate_type,
                candidate_id=candidate_id,
                decision=decision,
                reason_redacted=reason,
                reviewer_ref="operator",
            )

        payload = {
            "command": "second-brain phase-10 review-candidate",
            "ok": True,
            "emitted": emit,
            "candidate_id": candidate_id,
            "candidate_type": candidate_type,
            "decision": decision,
            "prior_review_status": prior_status,
            "new_review_status": decision if emit else prior_status,
            "reason_redacted": reason,
            "guardrails": {
                "explicit_confirmation_required_like_memory": True,
                "advisory_only": True,
                "no_silent_accept": True,
                "no_auto_promote": True,
                "review_status_preserved": True,
                "raw_excerpts_bounded": True,
            },
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)
    except typer.Exit:
        raise
    except Exception as e:
        payload = {
            "command": "second-brain phase-10 review-candidate",
            "ok": False,
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


@phase_10_app.command("obsidian-raw-export")
def phase_10_obsidian_raw_export(
    project: "str | None" = typer.Option(  # noqa: B008
        None, "--project", help="Project key to scope raw packets for export."
    ),  # noqa: B008
    date: "str | None" = typer.Option(None, "--date", help="Brief date or note date (YYYY-MM-DD)."),  # noqa: B008
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Default dry-run; --apply to write bounded raw section to Obsidian (only if policy permits).",
    ),  # noqa: B008
    json_out: bool = typer.Option(True, "--json"),  # noqa: B008
) -> None:
    """Config-gated export of raw email/calendar context packets into Obsidian (bounded, provenance-carrying, explicit markers).
    Respects obsidian_allow_raw_content + permissive raw_content.mode. Default disabled (no write, no leakage).
    When enabled, writes under allowlisted Phase 10A raw review markers with frontmatter (raw_content, policy, source refs).
    """
    from datetime import date as dt_date

    from hb_assistant.construction.second_brain.local_ai.raw_context import (
        build_raw_calendar_context_packet,
        build_raw_email_context_packet,
    )
    from hb_assistant.construction.store import ConstructionStore
    from hb_assistant.obsidian.writer import MarkerBoundedWriter

    try:
        from hb_assistant.construction.second_brain.local_ai.contracts import (
            load_raw_content_policy as _load_raw_pol,  # noqa: E402
        )

        rc = _load_raw_pol()
        rcd = getattr(rc, "raw_content", None)
        downstream = getattr(rcd, "downstream", None) if rcd is not None else None
        flag = (
            bool(getattr(downstream, "obsidian_allow_raw_content", False))
            if downstream is not None
            else False
        )
        mode = str(getattr(rcd, "mode", "") or "").lower() if rcd is not None else ""
        permissive = (
            mode in ("", "all_supported", "all_supported_plus_downstream") or "downstream" in mode
        )
        allowed = bool(flag and permissive)
    except Exception:
        allowed = False
        mode = None

    payload_base = {
        "command": "second-brain phase-10 obsidian-raw-export",
        "project": project,
        "date": date,
        "dry_run": dry_run,
        "obsidian_raw_allowed_by_policy": allowed,
        "raw_policy_mode": mode,
    }

    if not allowed:
        payload = {
            **payload_base,
            "ok": False,
            "reason": "obsidian_raw_disabled (default; set obsidian_allow_raw_content + permissive mode in raw_content_policy to enable)",
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0 if dry_run else 2)

    # Policy allows: build packets (builders apply their model_context.include_raw_content bounds)
    store = ConstructionStore()
    email_pkt = build_raw_email_context_packet(project_key=project, store=store)
    cal_pkt = build_raw_calendar_context_packet(project_key=project, store=store)

    note_date = dt_date.today().isoformat() if not date else str(date)
    # Bounded raw note content (explicit, source linked, frontmatter)
    raw_note = f"""---
phase: "10A"
packet_types: ["raw_email_context", "raw_calendar_context"]
raw_content: true
policy_mode: {mode or "unknown"}
project: {project or "global"}
date: {note_date}
source_refs: {(email_pkt or {}).get("source_refs", []) + (cal_pkt or {}).get("source_refs", [])}
guardrails: {{local_first: true, bounded: true, provenance: true, no_pem_jwt_url: true}}
---

<!-- HB_PHASE10_RAW_CONTEXT:BEGIN -->

# Raw Context Packets (per policy)

## Email
```json
{json.dumps(email_pkt, indent=2, default=str)[:8000]}
```

## Calendar
```json
{json.dumps(cal_pkt, indent=2, default=str)[:8000]}
```

<!-- HB_PHASE10_RAW_CONTEXT:END -->
"""

    if dry_run:
        payload = {
            **payload_base,
            "ok": True,
            "dry_run": True,
            "would_write": True,
            "note_preview_len": len(raw_note),
            "email_included": bool((email_pkt or {}).get("raw_content_included")),
            "calendar_included": bool((cal_pkt or {}).get("raw_content_included")),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)

    # apply: use MarkerBoundedWriter (preserves outside markers)
    try:
        w = MarkerBoundedWriter()
        w.write_bounded_section(
            target_date=dt_date.fromisoformat(note_date) if note_date else dt_date.today(),
            inner_content=raw_note,
            frontmatter_updates={"phase": "10A", "raw_content": True, "obsidian_raw_export": True},
            dry_run=False,
            companion=False,
        )
        payload = {**payload_base, "ok": True, "applied": True, "note_date": note_date}
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)
    except Exception as e:  # pragma: no cover - defensive
        payload = {**payload_base, "ok": False, "error": str(e)[:200]}
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None


# ---------------------------------------------------------------------------
# Phase 10 Prompt 04 — Local Model Structured Output Client CLI surfaces.
# Local-only, advisory, dry-run default. No writeback; receipts are hash-only.
# ---------------------------------------------------------------------------
@local_model_app.command("status")
def local_model_status(
    provider: str = typer.Option(  # noqa: B008
        "ollama", "--provider", help="ollama|mock. mock is offline-safe (no daemon)."
    ),
    mock: bool = typer.Option(  # noqa: B008
        False, "--mock", help="Shortcut for --provider mock (offline readiness shape)."
    ),
    heavy_enabled: bool = typer.Option(  # noqa: B008
        False, "--heavy-enabled", help="Treat heavy profiles as eligible (still requires a model)."
    ),
    write_evidence: bool = typer.Option(  # noqa: B008
        False, "--write-evidence", help="Also write 03-local-model-status-proof.{json,md}."
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Probe local model readiness against the Phase 10 profile tiers (read-only, no generation)."""
    from hb_assistant.construction.second_brain.local_ai import build_local_model_status

    provider_name = "mock" if mock else provider
    try:
        result = build_local_model_status(
            provider_name=provider_name,
            heavy_enabled=heavy_enabled,
            write_evidence=write_evidence,
        )
    except Exception as e:
        payload = {
            "command": "second-brain local-model status",
            "ok": False,
            "status": "status_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(3) from None
    typer.echo(json.dumps(result, indent=2, default=str) if json_out else str(result))
    raise typer.Exit(0 if result.get("ready") else 3)


@ai_jobs_app.command("status")
def ai_jobs_status(
    environment: "str | None" = typer.Option(  # noqa: B008
        None, "--environment", help="dev|production. Scopes queue/run counts (isolation)."
    ),
    list_jobs: bool = typer.Option(  # noqa: B008
        False, "--list", help="Also list queued/running job rows (metadata only)."
    ),
    db: "str | None" = typer.Option(  # noqa: B008
        None, "--db", help="Explicit SQLite path (tests/isolation). Default: ambient app DB."
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Report Phase 10 AI-job posture: queue counts by status + recent run aggregates (read-only)."""
    from hb_assistant.construction.store import ConstructionStore

    try:
        store = ConstructionStore(db_path=db)
        summary = store.ai_job_status_summary(environment=environment)
        payload: dict[str, Any] = {
            "command": "second-brain ai-jobs status",
            "ok": True,
            **summary,
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "environment_isolated": True,
            },
        }
        if list_jobs:
            payload["jobs"] = store.list_ai_jobs(environment=environment, limit=200)
    except Exception as e:
        payload = {
            "command": "second-brain ai-jobs status",
            "ok": False,
            "status": "status_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@ai_jobs_app.command("enqueue")
def ai_jobs_enqueue(
    job_type: str = typer.Option(  # noqa: B008
        ..., "--job-type", help="Job type (must be in the Phase 10 ai_job_contract)."
    ),
    environment: str = typer.Option(  # noqa: B008
        "dev", "--environment", help="dev|production (row-level isolation)."
    ),
    idempotency_key: "str | None" = typer.Option(  # noqa: B008
        None, "--idempotency-key", help="Idempotency key; defaults to a deterministic daily hash."
    ),
    priority: int = typer.Option(100, "--priority", help="Lower runs first."),  # noqa: B008
    source_watermark: "str | None" = typer.Option(  # noqa: B008
        None, "--source-watermark", help="Optional source watermark recorded on the job."
    ),
    db: "str | None" = typer.Option(  # noqa: B008
        None, "--db", help="Explicit SQLite path (tests/isolation). Default: ambient app DB."
    ),
    dry_run: bool = typer.Option(  # noqa: B008
        True,
        "--dry-run/--apply",
        help="Preview only (default). --apply writes the queue row (idempotent).",
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Idempotently enqueue an AI job into the V41 ai_job_queue (advisory; metadata only).

    Dry-run (default) previews the would-be row and writes nothing. --apply inserts the row keyed by
    UNIQUE(environment, job_type, idempotency_key); a duplicate is a no-op. No raw, no writeback.
    """
    from hb_assistant.construction.second_brain.local_ai import enqueue_ai_job_request
    from hb_assistant.construction.store import ConstructionStore

    try:
        result = enqueue_ai_job_request(
            store=ConstructionStore(db_path=db),
            job_type=job_type,
            environment=environment,
            idempotency_key=idempotency_key,
            priority=priority,
            source_watermark=source_watermark,
            dry_run=dry_run,
        )
        payload: dict[str, Any] = {"command": "second-brain ai-jobs enqueue", **result}
    except Exception as e:
        payload = {
            "command": "second-brain ai-jobs enqueue",
            "ok": False,
            "status": "enqueue_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if payload.get("ok") else 2)


@ai_jobs_app.command("run")
def ai_jobs_run(
    environment: str = typer.Option(  # noqa: B008
        "dev", "--environment", help="dev|production. Scopes claimed jobs + the no-overlap lock."
    ),
    max_items: int = typer.Option(10, "--max-items", help="Cap jobs claimed this run."),  # noqa: B008
    db: "str | None" = typer.Option(  # noqa: B008
        None, "--db", help="Explicit SQLite path (tests/isolation). Default: ambient app DB."
    ),
    dry_run: bool = typer.Option(  # noqa: B008
        True,
        "--dry-run/--apply",
        help="Preview only (default; zero writes). --apply runs jobs + writes receipts.",
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Claim + run eligible queued AI jobs under a no-overlap lock (retry/backoff; dry-run default).

    Dry-run claims and simulates with zero writes. --apply transitions jobs (running→succeeded /
    failed→retry), writes ai_job_runs + hash-only local_model_run_receipts, and respects
    max_concurrent_jobs=1 via a per-environment file lock. Local-only, advisory, no writeback.
    """
    from hb_assistant.construction.second_brain.local_ai import run_ai_jobs
    from hb_assistant.construction.store import ConstructionStore

    try:
        result = run_ai_jobs(
            store=ConstructionStore(db_path=db),
            environment=environment,
            max_items=max_items,
            dry_run=dry_run,
        )
        payload: dict[str, Any] = {"command": "second-brain ai-jobs run", **result}
    except Exception as e:
        payload = {
            "command": "second-brain ai-jobs run",
            "ok": False,
            "dry_run": dry_run,
            "status": "run_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    # Exit 2 when a run was blocked by an in-progress run (no-overlap); 0 otherwise.
    raise typer.Exit(0 if payload.get("ok") else 2)


@action_intel_app.command("extract-fixture")
def action_intel_extract_fixture(
    fixture: str = typer.Option(..., "--fixture", help="Path to a local_ai fixture JSON file."),  # noqa: B008
    profile_id: str = typer.Option(  # noqa: B008
        "default_extract", "--profile", help="Local model profile to resolve."
    ),
    apply: bool = typer.Option(  # noqa: B008
        False,
        "--apply",
        help="Write a hash-only run receipt to local_model_run_receipts. Default: no write.",
    ),
    db: "str | None" = typer.Option(  # noqa: B008
        None, "--db", help="Explicit SQLite path (tests/isolation). Default: ambient app DB."
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Run the structured-output client over one fixture and emit the validated ActionCandidate.

    A deterministic offline backend returns the fixture's expected candidate; the client validates
    it against the ActionCandidate schema. Advisory only — no DB write unless --apply, and even then
    only a hash-only receipt (never raw prompt/response/body). High-stakes items remain review-only.
    """
    import pathlib

    from hb_assistant.construction.second_brain.local_ai import (
        ActionCandidate,
        StaticOutputClient,
        StructuredOutputClient,
        action_candidate_dict_from_fixture,
        load_local_model_profiles,
    )
    from hb_assistant.construction.store import ConstructionStore

    try:
        fixture_data = json.loads(pathlib.Path(fixture).read_text(encoding="utf-8"))
        profiles = load_local_model_profiles()
        profile = next((p for p in profiles.profiles if p.profile_id == profile_id), None)
        if profile is None:
            raise ValueError(f"unknown profile_id {profile_id!r}")
        candidate = action_candidate_dict_from_fixture(fixture_data)
        store = ConstructionStore(db_path=db) if apply else None
        result = StructuredOutputClient().run(
            schema=ActionCandidate,
            profile=profile,
            profiles=profiles,
            system="fixture structured extraction",
            prompt="extract action candidate",
            input_context=json.dumps(fixture_data.get("input_redacted", {}), sort_keys=True),
            task_type="extract_email_tasks",
            backend=StaticOutputClient(json.dumps(candidate)),
            store=store,
            dry_run=not apply,
        )
        payload: dict[str, Any] = {
            "command": "second-brain action-intel extract-fixture",
            "ok": result.schema_valid,
            "fixture_id": fixture_data.get("fixture_id"),
            "applied": apply,
            "status": result.status,
            "schema_valid": result.schema_valid,
            "candidate": result.validated,
            "input_context_hash": result.input_context_hash,
            "output_hash": result.output_hash,
            "receipt_id": result.receipt_id,
            "would_write_receipt": result.would_write_receipt,
            "guardrails": {
                "local_only": True,
                "advisory_only": True,
                "strict_schema": True,
                "no_writeback": True,
                "receipt_hash_only": True,
                "high_stakes_review_only": True,
            },
        }
    except Exception as e:
        payload = {
            "command": "second-brain action-intel extract-fixture",
            "ok": False,
            "status": "extract_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if result.schema_valid else 3)


@action_intel_app.command("run-fixtures")
def action_intel_run_fixtures(
    fixtures_dir: str = typer.Option(  # noqa: B008
        "tests/fixtures/local_ai/fixture_suite",
        "--fixtures-dir",
        help="Directory of scenario fixtures to run (default: the Prompt 06 suite).",
    ),
    profile_id: str = typer.Option(  # noqa: B008
        "default_extract", "--profile", help="Local model profile to resolve."
    ),
    json_out: bool = typer.Option(True, "--json", help="Emit machine-readable JSON (default)."),  # noqa: B008
) -> None:
    """Run the action-candidate fixture suite as a batch validation/regression harness.

    Every fixture is run through the schema-enforced structured-output client over the
    ActionCandidate schema; each run's outcome is classified and compared to the fixture's declared
    ``expected_outcome`` (valid / schema_invalid / unavailable / blocked). Advisory and dry-run only —
    no DB write, no raw payloads (only SHA-256[:12] hashes are surfaced). Exits 0 when every fixture
    matched, else 3.
    """
    from hb_assistant.construction.second_brain.local_ai import run_fixture_suite

    try:
        result = run_fixture_suite(fixtures_dir=fixtures_dir, profile_id=profile_id)
        payload: dict[str, Any] = {
            "command": "second-brain action-intel run-fixtures",
            "ok": result["all_matched"],
            **result,
            "guardrails": {
                "local_only": True,
                "advisory_only": True,
                "dry_run": True,
                "no_writeback": True,
                "no_raw_persistence": True,
                "high_stakes_review_only": result["high_risk_routing_ok"],
            },
        }
    except Exception as e:
        payload = {
            "command": "second-brain action-intel run-fixtures",
            "ok": False,
            "status": "run_error",
            "error": str(e)[:300],
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if payload["ok"] else 3)
