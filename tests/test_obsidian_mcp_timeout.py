"""Obsidian MCP tool-timeout guard, off-loop execution, and diagnostics.

Proves the fix for Grok tool timeouts: every MCP tool runs its blocking service
call off the event loop under a bounded timeout, so a stalled tool returns a fast
structured ``tool_timeout`` error instead of hanging the whole server. Also proves
redacted ``tool_start``/``tool_end``/``tool_error`` diagnostics (no token/content
leak) and strict-JSON serialization for every registered tool.
"""

# ruff: noqa: I001,E402

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.service import ObsidianMcpService
from hb_assistant.store.migrator import SQLiteMigrator

HOST = "127.0.0.1:3010"
_HEADERS = {"Accept": "application/json, text/event-stream", "Host": HOST}
_MCP_LOGGER = "hb_assistant.obsidian_mcp.mcp"

# Names in registry order; the strict-JSON sweep below must reach every one of them.
_ALL_TOOLS = [
    "list_directory", "search_vault", "read_file", "create_note", "patch_note",
    "vault_map", "vault_summarize_note", "vault_summarize_folder", "vault_read_eml",
    "vault_email_inventory", "vault_parse_email", "vault_read_frontmatter",
    "vault_update_frontmatter", "vault_search_by_properties", "vault_dataview_query",
    "vault_get_backlinks", "vault_get_unlinked_mentions", "vault_get_note_graph",
    "vault_create_note_from_template", "vault_append_to_daily_note",
    "vault_semantic_search", "vault_move_note_plan", "vault_move_note_apply",
    "vault_rename_note_plan", "vault_rename_note_apply", "vault_archive_note_plan",
    "vault_archive_note_apply", "vault_delete_note_plan", "vault_extract_action_items",
    "vault_project_status_summary", "vault_extract_project_mentions",
    "vault_curation_plan", "vault_curation_apply", "vault_create_moc_plan",
    "vault_auto_link_plan", "vault_bulk_tagging_plan", "vault_email_to_note_plan",
    "vault_email_to_note_apply",
    "search_sources", "search_knowledge", "source_index_status", "rebuild_source_index",
    "generate_source_card", "refresh_stale_source_notes", "summarize_source",
]

# Minimal arguments per tool. Missing files / bogus plan_ids are fine: a structured
# error is still strict-JSON; the point is that no tool crashes or emits non-JSON.
_MIN_ARGS: dict[str, dict] = {
    "search_vault": {"query": "Grok", "path_scope": "Projects"},
    "read_file": {"path": "Projects/Scope.md"},
    "create_note": {"path": "Managed/New.md", "content": "# New\n\nbody"},
    "patch_note": {"path": "Projects/Scope.md", "content": "# Scope\n\nx", "expected_sha256": "0" * 64},
    "vault_summarize_note": {"path": "Projects/Scope.md"},
    "vault_read_eml": {"path": "Projects/Scope.md"},
    "vault_parse_email": {"path": "Projects/Scope.md"},
    "vault_read_frontmatter": {"path": "Projects/Scope.md"},
    "vault_update_frontmatter": {"path": "Projects/Scope.md", "updates": {"k": "v"}, "expected_sha256": "0" * 64},
    "vault_get_backlinks": {"target_path": "Projects/Scope.md"},
    "vault_get_unlinked_mentions": {"target_title": "Scope"},
    "vault_create_note_from_template": {"template_path": "Projects/Scope.md", "target_path": "Managed/T.md"},
    "vault_append_to_daily_note": {"content": "- note"},
    "vault_semantic_search": {"query": "Grok"},
    "vault_move_note_plan": {"source_path": "Projects/Scope.md", "target_path": "Projects/Moved.md"},
    "vault_move_note_apply": {"plan_id": "missing"},
    "vault_rename_note_plan": {"source_path": "Projects/Scope.md", "new_name": "Renamed.md"},
    "vault_rename_note_apply": {"plan_id": "missing"},
    "vault_archive_note_plan": {"source_path": "Projects/Scope.md"},
    "vault_archive_note_apply": {"plan_id": "missing"},
    "vault_delete_note_plan": {"source_path": "Projects/Scope.md"},
    "vault_extract_action_items": {"path": "Projects/Scope.md"},
    "vault_curation_apply": {"plan_id": "missing"},
    "vault_email_to_note_plan": {"email_path": "Projects/Scope.md", "target_folder": "Managed"},
    "vault_email_to_note_apply": {"plan_id": "missing"},
    "search_sources": {"query": "Grok"},
    "search_knowledge": {"query": "Grok"},
    "generate_source_card": {"source_id": "missing"},
    "summarize_source": {"source_id": "missing"},
}


def _reject_constant(value: str) -> None:
    raise AssertionError(f"non-strict JSON constant in MCP response: {value}")


def _strict_json(text: str) -> dict:
    text = text.strip()
    if "data: " in text:
        text = text.split("data: ", 1)[1].strip()
    return json.loads(text, parse_constant=_reject_constant)


def _write_config(tmp_path: Path, vault: Path) -> Path:
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                f"  application_support_root: {(tmp_path / 'app-support').as_posix()!r}",
                f"  obsidian_vault: {vault.as_posix()!r}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _make(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    vault = tmp_path / "vault"
    (vault / "Projects").mkdir(parents=True)
    (vault / "Projects" / "Scope.md").write_text(
        "# Scope\n\nGrok conduit belongs to electrical.\n", encoding="utf-8"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(_write_config(tmp_path, vault)))
    db = str(tmp_path / "api.sqlite")
    SQLiteMigrator(db_path=db).apply()
    client = TestClient(create_app(db_path=db), base_url=f"http://{HOST}")
    return client, vault


def _configure(client: TestClient, vault: Path, **extra) -> None:
    patch = {
        "enabled": True,
        "vault_root": str(vault),
        "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "summarization_backend": "deterministic",
    }
    patch.update(extra)
    res = client.patch(
        "/api/settings/obsidian-mcp/config", json=patch, headers={"X-HB-UI-Role": "operator"}
    )
    assert res.status_code == 200, res.text


def _session(client: TestClient, *, authorization: str | None = None) -> dict:
    headers = dict(_HEADERS)
    if authorization:
        headers["authorization"] = authorization
    init = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "hb-test", "version": "1.0"},
            },
        },
        headers=headers,
    )
    assert init.status_code == 200, init.text
    sid = init.headers.get("mcp-session-id")
    if sid:
        headers["mcp-session-id"] = sid
    client.post(
        "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers
    )
    return headers


def _call(client: TestClient, headers: dict, name: str, arguments: dict, _id: int = 99):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": _id, "method": "tools/call",
              "params": {"name": name, "arguments": arguments}},
        headers=headers,
    )


def test_stalled_tool_returns_fast_structured_timeout_and_server_stays_responsive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _make(tmp_path, monkeypatch)

    def _slow_search(self, payload):  # noqa: ANN001, ARG001
        time.sleep(5)
        return {"results": []}

    monkeypatch.setattr(ObsidianMcpService, "search_vault", _slow_search)
    with client:
        _configure(client, vault, tool_timeout_seconds=1)
        headers = _session(client)

        started = time.monotonic()
        stalled = _call(client, headers, "search_vault", {"query": "Grok"}, _id=2)
        elapsed = time.monotonic() - started

        assert stalled.status_code == 200
        payload = _strict_json(stalled.text)
        assert payload["result"]["isError"] is True
        assert "tool_timeout" in stalled.text
        # Freed at ~1s by abandoning the worker thread, well under the 5s sleep.
        assert elapsed < 4.0, f"timeout did not free the loop fast (elapsed={elapsed:.2f}s)"

        # A second, lightweight tool still responds — the server was not wedged.
        ok = _call(client, headers, "list_directory", {"path": "Projects"}, _id=3)
        assert ok.status_code == 200
        assert _strict_json(ok.text)["result"]["isError"] is False


def test_diagnostics_emitted_and_leak_no_token_or_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_token = "super-secret-bearer-value"
    secret_body = "CONFIDENTIAL salary figures and the codeword pineapple"
    client, vault = _make(tmp_path, monkeypatch)
    with client:
        _configure(client, vault, bearer_token=secret_token)
        headers = _session(client, authorization=f"Bearer {secret_token}")

        with caplog_at(_MCP_LOGGER) as records:
            created = _call(
                client,
                headers,
                "create_note",
                {"path": "Managed/Diag.md", "content": secret_body},
                _id=4,
            )
        assert created.status_code == 200
        assert _strict_json(created.text)["result"]["isError"] is False

    diag = _diag_records(records)
    statuses = [r["status"] for r in diag if r["tool"] == "create_note"]
    assert "start" in statuses and "ok" in statuses
    end = next(r for r in diag if r["tool"] == "create_note" and r["status"] == "ok")
    assert end["caller_surface"] == "mcp"
    assert end["authorization_present"] is True
    assert end["principal_kind"] == "static_bearer"
    assert end["content_chars"] == len(secret_body)
    assert "elapsed_ms" in end

    blob = _records_blob(records)
    assert secret_token not in blob, "bearer token leaked into diagnostics"
    assert secret_body not in blob, "note content leaked into diagnostics"
    assert "pineapple" not in blob, "note content leaked into diagnostics"


def test_timeout_emits_tool_error_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _make(tmp_path, monkeypatch)

    def _slow_search(self, payload):  # noqa: ANN001, ARG001
        time.sleep(5)
        return {"results": []}

    monkeypatch.setattr(ObsidianMcpService, "search_vault", _slow_search)
    with client:
        _configure(client, vault, tool_timeout_seconds=1)
        headers = _session(client)
        with caplog_at(_MCP_LOGGER) as records:
            _call(client, headers, "search_vault", {"query": "Grok"}, _id=5)

    diag = _diag_records(records)
    err = next(r for r in diag if r["tool"] == "search_vault" and r["status"] == "tool_timeout")
    assert err["error_code"] == "tool_timeout"
    assert "elapsed_ms" in err


def test_insufficient_scope_rejected_before_offload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only OAuth token calling a write tool fails fast with insufficient_scope,
    and the service method is never invoked — proving scope enforcement runs on the
    event loop before any work is offloaded to a worker thread."""
    from hb_assistant.obsidian_mcp import oauth_store

    client, vault = _make(tmp_path, monkeypatch)
    invoked = {"create_note": False}
    real_create = ObsidianMcpService.create_note

    def _flag_create(self, payload):  # noqa: ANN001
        invoked["create_note"] = True
        return real_create(self, payload)

    monkeypatch.setattr(ObsidianMcpService, "create_note", _flag_create)
    with client:
        _configure(client, vault, oauth_enabled=True)
        token = oauth_store.issue_access_token(["obsidian.read"])["access_token"]
        headers = _session(client, authorization=f"Bearer {token}")
        resp = _call(client, headers, "create_note", {"path": "Managed/Nope.md", "content": "x"}, _id=8)
        assert resp.status_code == 200
        payload = _strict_json(resp.text)
        assert payload["result"]["isError"] is True
        assert "missing required scope" in resp.text  # surfaced insufficient_scope message
    assert invoked["create_note"] is False


@pytest.mark.parametrize("tool", _ALL_TOOLS)
def test_every_tool_result_is_strict_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    client, vault = _make(tmp_path, monkeypatch)
    with client:
        _configure(client, vault)
        headers = _session(client)
        resp = _call(client, headers, tool, _MIN_ARGS.get(tool, {}), _id=7)
        assert resp.status_code == 200, resp.text
        payload = _strict_json(resp.text)  # raises on NaN/Infinity or non-JSON
        assert "result" in payload or "error" in payload


# --- small log-capture helpers (avoid depending on the caplog fixture's level wiring) ---
class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class caplog_at:  # noqa: N801 - context manager reads naturally lowercase
    def __init__(self, logger_name: str) -> None:
        self._logger = logging.getLogger(logger_name)
        self._handler = _ListHandler()
        self._prev_level = self._logger.level

    def __enter__(self) -> list[logging.LogRecord]:
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.INFO)
        return self._handler.records

    def __exit__(self, *exc) -> None:
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._prev_level)


def _diag_records(records: list[logging.LogRecord]) -> list[dict]:
    return [r.obsidian_mcp for r in records if hasattr(r, "obsidian_mcp")]


def _records_blob(records: list[logging.LogRecord]) -> str:
    parts: list[str] = []
    for r in records:
        parts.append(r.getMessage())
        if hasattr(r, "obsidian_mcp"):
            parts.append(json.dumps(r.obsidian_mcp, default=str))
    return "\n".join(parts)
