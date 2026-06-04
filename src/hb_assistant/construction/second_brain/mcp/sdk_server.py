"""Phase 08D MCP SDK adapter — the real local stdio server (Prompt 15).

Wires the existing, audit-proven Phase 08D building blocks to a low-level ``mcp`` SDK
``Server`` so ``hb-assistant second-brain mcp serve --stdio`` actually speaks the MCP
JSON-RPC protocol to a local client (e.g. Claude Desktop). No new business logic — every
surface routes through the same safe components the guard proofs already cover:

- **tools** → :func:`ToolBroker.dispatch` (deny-first, bounded, metadata-only receipts);
- **resources** → :func:`read_resource` (read-only bounded resolvers);
- **prompts** → :func:`render_prompt` (advisory templates, no raw stores).

The broker is the single deny-first policy authority: ``call_tool`` is registered with
``validate_input=False`` so *every* tool call — allowed, denied, or unknown — flows
through the broker, which validates arguments, bounds output, fails closed on raw
content, and writes a metadata-only allow/deny receipt. The local stdio transport is the
package's explicitly allowed transport; no network listener is ever opened.

The ``mcp`` SDK is an optional extra (``pip install -e .[mcp]``); it is imported lazily
inside the entrypoints only, so the base install and the full test suite still run with
the SDK absent. stdout is the JSON-RPC channel — this module writes nothing to stdout.
"""

from __future__ import annotations

import json
from typing import Any

from . import (
    build_default_broker,
    load_allowed_tools,
    load_prompts,
    load_resources,
    read_resource,
    render_prompt,
)

SERVER_NAME = "hb-personal-assistant"
_CLIENT_NAME = "mcp-client"

# Advisory per-tool argument hints surfaced to the client. ``ToolBroker.dispatch``
# (registered with validate_input=False) is the authoritative validator/gate; these
# schemas are descriptive only and stay permissive (additionalProperties=True) so the
# broker — not the SDK — owns every accept/deny decision.
_TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "hb_status": {"type": "object", "properties": {}, "additionalProperties": True},
    "hb_query": {
        "type": "object",
        "properties": {"question": {"type": "string"}, "project_key": {"type": "string"}},
        "required": ["question"],
        "additionalProperties": True,
    },
    "hb_research_packet": {
        "type": "object",
        "properties": {"packet_type": {"type": "string"}, "project_key": {"type": "string"}},
        "additionalProperties": True,
    },
    "hb_get_daily_brief": {
        "type": "object",
        "properties": {"brief_date": {"type": "string"}},
        "additionalProperties": True,
    },
    "hb_open_daily_brief": {
        "type": "object",
        "properties": {"brief_date": {"type": "string"}, "target": {"type": "string"}},
        "additionalProperties": True,
    },
    "hb_review_load_status": {
        "type": "object",
        "properties": {"project_key": {"type": "string"}},
        "additionalProperties": True,
    },
    "hb_memory_review_list": {"type": "object", "properties": {}, "additionalProperties": True},
    "hb_memory_feedback": {
        "type": "object",
        "properties": {
            "target_id": {"type": "string"},
            "target_kind": {"type": "string"},
            "feedback_class": {"type": "string"},
            "rating": {"type": "integer"},
            "reason_redacted": {"type": "string"},
        },
        "required": ["target_id"],
        "additionalProperties": True,
    },
    "hb_validation_status": {"type": "object", "properties": {}, "additionalProperties": True},
}


def build_mcp_app(*, db_path: str | None = None) -> Any:
    """Build a low-level ``mcp`` ``Server`` bound to the safe broker/resources/prompts.

    Lazily imports the ``mcp`` SDK (optional extra). Returns the configured ``Server``;
    the caller drives the transport (see :func:`serve_stdio_loop`).
    """
    from mcp import types  # noqa: PLC0415 (lazy — optional extra)
    from mcp.server.lowlevel import Server  # noqa: PLC0415
    from mcp.server.lowlevel.helper_types import ReadResourceContents  # noqa: PLC0415

    app: Any = Server(SERVER_NAME)
    broker = build_default_broker(db_path=db_path, persist=True)
    allowed = load_allowed_tools()

    @app.list_tools()
    async def _list_tools() -> list[Any]:
        return [
            types.Tool(
                name=name,
                description=str(allowed[name].get("maps_to") or name),
                inputSchema=_TOOL_INPUT_SCHEMAS.get(
                    name, {"type": "object", "additionalProperties": True}
                ),
            )
            for name in sorted(allowed)
        ]

    # validate_input=False: the broker is the single deny-first authority, so unknown /
    # denied tools still reach dispatch and produce a metadata-only denial receipt.
    @app.call_tool(validate_input=False)
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[Any]:
        envelope = broker.dispatch(name, arguments or {}, client_name=_CLIENT_NAME)
        return [types.TextContent(type="text", text=json.dumps(envelope, default=str))]

    @app.list_resources()
    async def _list_resources() -> list[Any]:
        return [
            types.Resource(
                uri=entry["uri"],
                name=str(entry["wrapper"]),
                description=str(entry.get("source") or ""),
                mimeType="application/json",
            )
            for entry in load_resources()
        ]

    @app.read_resource()
    async def _read_resource(uri: Any) -> list[Any]:
        payload = read_resource(str(uri), db_path=db_path)
        return [
            ReadResourceContents(
                content=json.dumps(payload, default=str), mime_type="application/json"
            )
        ]

    @app.list_prompts()
    async def _list_prompts() -> list[Any]:
        prompts: list[Any] = []
        for entry in load_prompts():
            rendered = render_prompt(str(entry["name"]), {})
            arguments = [
                types.PromptArgument(
                    name=str(arg["name"]), required=bool(arg.get("required", False))
                )
                for arg in rendered.get("arguments", [])
            ]
            prompts.append(
                types.Prompt(
                    name=str(entry["name"]),
                    description=str(rendered.get("description") or ""),
                    arguments=arguments,
                )
            )
        return prompts

    @app.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None) -> Any:
        rendered = render_prompt(name, arguments or {})
        # MCP prompt messages only carry user/assistant roles; the advisory "system"
        # posture message is surfaced as a leading user message.
        messages = [
            types.PromptMessage(
                role="assistant" if message.get("role") == "assistant" else "user",
                content=types.TextContent(type="text", text=str(message.get("content", ""))),
            )
            for message in rendered.get("messages", [])
        ]
        return types.GetPromptResult(
            description=str(rendered.get("description") or ""), messages=messages
        )

    return app


async def serve_stdio_loop(*, db_path: str | None = None) -> None:
    """Run the local stdio MCP server loop until the client disconnects.

    Blocking. stdout/stdin are the JSON-RPC channel; diagnostics belong on stderr.
    """
    from mcp.server.stdio import stdio_server  # noqa: PLC0415 (lazy — optional extra)

    app = build_mcp_app(db_path=db_path)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
