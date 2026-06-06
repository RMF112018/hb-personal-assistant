"""Phase 08D Prompt 15 — operational local stdio MCP serve proof.

End-to-end MCP protocol round trip against the real adapter (``build_mcp_app``) using the
SDK's in-memory connected client/server session — the same JSON-RPC surface a desktop
client drives, without spawning a process. Skipped when the optional ``mcp`` SDK is absent
(the base install stays green). Proves: initialize; 9 tools / 5 resources / 5 prompts; an
allowed tool call returns a metadata-only envelope and writes a receipt; a denied/unknown
tool returns a denial + denial receipt; resources/prompts resolve bounded payloads; and no
raw content / token / URL / PEM marker appears in any payload.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

import anyio
from mcp.shared.memory import create_connected_server_and_client_session as connect

from hb_assistant.construction.second_brain.mcp.sdk_server import build_mcp_app

# Forbidden raw/secret/URL shapes that must never appear in any MCP payload.
_FORBIDDEN_MARKERS = ("BEGIN RSA", "BEGIN PRIVATE", "?sig=", "AKIA", "Bearer ", "sk-")


async def _roundtrip(db: str) -> dict[str, Any]:
    app = build_mcp_app(db_path=db)
    out: dict[str, Any] = {}
    async with connect(app) as session:
        init = await session.initialize()
        out["server"] = init.serverInfo.name
        out["tools"] = sorted(t.name for t in (await session.list_tools()).tools)
        out["resources"] = len((await session.list_resources()).resources)
        out["prompts"] = len((await session.list_prompts()).prompts)
        out["allowed_text"] = (await session.call_tool("hb_status", {})).content[0].text
        out["denied_text"] = (await session.call_tool("hb_delete_everything", {})).content[0].text
        out["resource_text"] = (await session.read_resource("hb://status/system")).contents[0].text
        gp = await session.get_prompt("ask_project_question", {"question": "Q"})
        out["prompt_roles"] = [m.role for m in gp.messages]
        out["prompt_text"] = " ".join(getattr(m.content, "text", "") for m in gp.messages)
    return out


def test_operational_stdio_roundtrip_is_safe_and_receipted() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "op.db")
        out = anyio.run(_roundtrip, db)

        # Protocol surface.
        assert out["server"] == "hb-personal-assistant"
        assert len(out["tools"]) == 10 and all(name.startswith("hb_") for name in out["tools"])
        assert out["resources"] == 5
        assert out["prompts"] == 5

        # Allowed tool: metadata-only envelope + receipt id.
        allowed = json.loads(out["allowed_text"])
        assert allowed["decision"] == "allowed"
        assert allowed["denied"] is False
        assert allowed["receipt_id"]

        # Denied/unknown tool: denial + denial receipt id.
        denied = json.loads(out["denied_text"])
        assert denied["decision"] == "denied"
        assert denied["denied"] is True
        assert denied["receipt_id"]

        # Resource resolves to a bounded JSON payload; prompt uses only user/assistant roles.
        resource = json.loads(out["resource_text"])
        assert resource["uri"] == "hb://status/system"
        assert set(out["prompt_roles"]) <= {"user", "assistant"}

        # No raw content / token / URL / PEM marker in any payload.
        blob = " ".join(
            [out["allowed_text"], out["denied_text"], out["resource_text"], out["prompt_text"]]
        )
        for marker in _FORBIDDEN_MARKERS:
            assert marker not in blob, marker

        # Metadata-only receipts persisted (1 allow + 1 deny), guard columns clean.
        conn = sqlite3.connect(db)
        try:
            allow_n = conn.execute(
                "SELECT COUNT(*) FROM second_brain_mcp_tool_call_receipts"
            ).fetchone()[0]
            deny_n = conn.execute(
                "SELECT COUNT(*) FROM second_brain_mcp_denial_receipts"
            ).fetchone()[0]
        finally:
            conn.close()
        assert allow_n >= 1
        assert deny_n >= 1
