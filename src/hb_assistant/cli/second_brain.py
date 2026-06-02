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
        typer.echo(
            json.dumps(err_payload, indent=2, default=str) if json_out else str(err_payload)
        )
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
