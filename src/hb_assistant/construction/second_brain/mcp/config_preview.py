"""Phase 08D Claude Desktop config-preview surface (Prompt 03).

Builds a *safe, preview-only* Claude Desktop ``mcpServers`` entry for the local stdio
MCP server, asserts it conforms to the shipped JSON Schema
(``claude_desktop_config_preview.schema.json``) and the safety policy (command/args
exact, stdio transport, env keys allow-listed, no broad filesystem path), persists a
metadata-only preview row, and writes ``claude-desktop-config-preview.json`` to the 08D
evidence directory. It never edits the real Claude Desktop config and never persists env
*values* — only env key names.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw
from .policy import TRANSPORT, _policy_version
from .store import _sha256, write_mcp_claude_desktop_config_preview

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-08d-mcp-bridge"
PREVIEW_JSON = "claude-desktop-config-preview.json"

_SERVER_KEY = "hb-personal-assistant"
_EXPECTED_COMMAND = "hb-assistant"
_EXPECTED_ARGS = ["second-brain", "mcp", "serve", "--stdio", "--json"]
# Pre-approved env key allow-list (no secrets, no filesystem paths, no values persisted).
_ALLOWED_ENV_KEYS = {"HB_MCP_TRANSPORT", "HB_MCP_POLICY"}
_DEFAULT_ENV = {"HB_MCP_TRANSPORT": "stdio", "HB_MCP_POLICY": "local_safe"}


def _server_entry(env: dict[str, str]) -> dict[str, Any]:
    return {
        "mcpServers": {
            _SERVER_KEY: {
                "command": _EXPECTED_COMMAND,
                "args": list(_EXPECTED_ARGS),
                "env": dict(env),
            }
        }
    }


def assess_config_safety(preview: dict[str, Any]) -> dict[str, Any]:
    """Return a safety report for a candidate preview (no exceptions on unsafe)."""
    reasons: list[str] = []
    servers = preview.get("mcpServers")
    entry = servers.get(_SERVER_KEY) if isinstance(servers, dict) else None
    if not isinstance(entry, dict):
        return {"safe": False, "unsafe_reasons": ["missing_hb_personal_assistant_server"]}

    command = entry.get("command")
    args = entry.get("args")
    env = entry.get("env") or {}

    if command != _EXPECTED_COMMAND:
        reasons.append("unsafe_command")
    if args != _EXPECTED_ARGS:
        reasons.append("unsafe_args")
    # transport must be stdio: argv pins --stdio and env (if present) must say stdio.
    if "--stdio" not in (args or []):
        reasons.append("unsupported_transport")
    if isinstance(env, dict):
        for key, value in env.items():
            if key not in _ALLOWED_ENV_KEYS:
                reasons.append(f"unsafe_env_key:{key}")
            elif "/" in str(value) or "\\" in str(value):
                reasons.append(f"broad_filesystem_path_in_env:{key}")
        if str(env.get("HB_MCP_TRANSPORT", "stdio")) != TRANSPORT:
            reasons.append("unsupported_transport")
    else:
        reasons.append("unsafe_env")

    return {"safe": not reasons, "unsafe_reasons": reasons}


def _load_schema() -> dict[str, Any]:
    from ..contracts import _load_json_resource

    return _load_json_resource("claude_desktop_config_preview.schema.json")


def _conforms_to_schema(preview: dict[str, Any]) -> bool:
    """Lightweight conformance check against the shipped JSON Schema consts."""
    schema = _load_schema()
    try:
        props = schema["properties"]["mcpServers"]["properties"][_SERVER_KEY]["properties"]
        command_const = props["command"]["const"]
        arg_consts = [item["const"] for item in props["args"]["prefixItems"]]
    except (KeyError, TypeError):
        return False
    entry = preview["mcpServers"][_SERVER_KEY]
    return bool(entry["command"] == command_const and entry["args"] == arg_consts)


def build_claude_desktop_config_preview(
    *,
    client: str = "claude-desktop",
    env: dict[str, str] | None = None,
    db_path: str | None = None,
    evidence_dir: str | None = None,
    persist: bool = True,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Build, validate, persist, and (optionally) write the Claude Desktop config preview."""
    preview = _server_entry(env if env is not None else _DEFAULT_ENV)
    safety = assess_config_safety(preview)
    conforms = _conforms_to_schema(preview)
    config_hash = _sha256(preview)
    policy_version = _policy_version()

    entry = preview["mcpServers"][_SERVER_KEY]
    env_keys = sorted((entry.get("env") or {}).keys())

    out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
    evidence_path = str(out_dir / PREVIEW_JSON)

    result = {
        "command": "second-brain mcp config-preview",
        "phase": "08D",
        "client": client,
        "transport": TRANSPORT,
        "safe": bool(safety["safe"]) and conforms,
        "schema_conformant": conforms,
        "unsafe_reasons": safety["unsafe_reasons"],
        "config_hash": config_hash,
        "policy_version": policy_version,
        "env_keys": env_keys,
        "preview": preview,
        "evidence_path": evidence_path,
        "auto_apply": False,
        "guardrails": {
            "preview_only_no_auto_apply": True,
            "transport_stdio_only": True,
            "env_values_persisted": False,
            "command_is_hb_assistant_only": True,
        },
    }

    # Fail-closed on any forbidden raw pattern before any write.
    _assert_no_raw(json.dumps(result, default=str), "mcp claude-desktop config preview")

    if persist:
        result["preview_id"] = write_mcp_claude_desktop_config_preview(
            client_name=client,
            safe=bool(result["safe"]),
            transport=TRANSPORT,
            command_redacted=_EXPECTED_COMMAND,
            args=list(_EXPECTED_ARGS),
            env_keys=env_keys,
            config_hash=config_hash,
            policy_version=policy_version,
            evidence_path=evidence_path,
            db_path=db_path,
        )

    if write_evidence:
        out_dir.mkdir(parents=True, exist_ok=True)
        Path(evidence_path).write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")

    return result
