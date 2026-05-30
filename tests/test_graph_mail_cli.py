"""Phase 06 Prompt 04 — `hb-assistant graph mail status --json` CLI.

Verifies the command parses, emits the expected read-only-readiness envelope with
the runtime guard self-test passing, and never leaks a token.
"""

from __future__ import annotations

import json
from pathlib import Path

import hb_assistant.cli.graph as graph_cli
from typer.testing import CliRunner

from hb_assistant.cli.main import app

runner = CliRunner()


def _invoke(tmp_path: Path, *args: str):
    return runner.invoke(
        app,
        list(args),
        env={"HB_APP_SUPPORT_DIR": str(tmp_path)},
        catch_exceptions=False,
    )


def test_graph_mail_status_json_envelope(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "status", "--json", "--no-probe")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    for key in ("command", "ok", "auth", "guard_self_test", "mail_probe", "guardrails", "contract"):
        assert key in payload, f"missing {key}"
    assert payload["command"] == "graph mail status"
    # Endpoint guard proven at runtime, no network needed.
    assert payload["guard_self_test"]["passed"] is True
    assert payload["guard_self_test"]["anomalies"] == []
    assert payload["guardrails"]["mutation_endpoints_blocked"] is True
    assert payload["guardrails"]["metadata_only_select"] is True
    assert payload["guardrails"]["attachment_content_excluded"] is True
    assert payload["guardrails"]["no_mail_write_scopes_requested"] is True
    assert payload["mail_read_scope_present"] is True
    assert payload["contract"]["allowed_methods"] == ["GET"]


def test_graph_mail_status_no_token_leak(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "status", "--json", "--no-probe")
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_mail_status_no_probe_marks_probe_not_attempted(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "status", "--json", "--no-probe")
    payload = json.loads(res.output)
    assert payload["mail_probe"]["attempted"] is False


def test_graph_mail_folders_dry_run_parses(tmp_path: Path) -> None:
    # No token in the isolated env, so this resolves to an error envelope, but the
    # command must parse, stay read-only, and never leak a token.
    res = _invoke(tmp_path, "graph", "mail", "folders", "--dry-run", "--json")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail folders"
    assert payload["dry_run"] is True
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_mail_index_parses(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "index", "--project", "tropical", "--lookback-days", "30", "--json")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail index"
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_mail_discover_dry_run_parses(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "mail", "discover", "--project", "tropical", "--lookback-days", "30", "--dry-run", "--json")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail discover"
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_mail_relationships_parses(tmp_path: Path) -> None:
    # Local-only command (no Graph); should run cleanly.
    res = _invoke(tmp_path, "graph", "mail", "relationships", "--project", "tropical", "--lookback-days", "30", "--dry-run", "--json")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail relationships"
    assert payload.get("disclaimer", "").find("not determinations") >= 0 or payload.get("ok") is False
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_mail_review_queue_parses(tmp_path: Path) -> None:
    # Local-only command (no Graph); evidence-safe dry-run preview.
    res = _invoke(tmp_path, "graph", "mail", "review-queue", "--project", "tropical", "--lookback-days", "30", "--dry-run", "--json")
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail review-queue"
    if payload.get("ok"):
        assert payload["dry_run"] is True
        assert "messages_considered" in payload
    # never leak a token or a decrypted body
    assert "access_token" not in res.output
    assert "Bearer " not in res.output
    assert "----- decrypted body" not in res.output


def test_graph_mail_classify_parses(tmp_path: Path) -> None:
    # Local-only advisory classification; evidence-safe dry-run preview.
    res = _invoke(
        tmp_path, "graph", "mail", "classify", "--project", "tropical",
        "--lookback-days", "30", "--use-encrypted-body-context", "--dry-run", "--json",
    )
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail classify"
    if payload.get("ok"):
        assert payload["plaintext_persisted"] is False
        assert payload["dry_run"] is True
        for key in ("messages_considered", "encrypted_body_context_used_count",
                    "model_outputs_valid", "review_required_count"):
            assert key in payload
    assert "access_token" not in res.output
    assert "Bearer " not in res.output
    assert "----- decrypted body" not in res.output


def test_graph_mail_classify_dry_run_still_initializes_model_client(
    tmp_path: Path, monkeypatch
) -> None:
    calls: dict[str, int] = {"client_init": 0}

    class _FakeClient:
        def __init__(self, model_name: str) -> None:
            calls["client_init"] += 1

    monkeypatch.setattr(graph_cli, "OllamaChatClient", _FakeClient)

    res = _invoke(
        tmp_path,
        "graph",
        "mail",
        "classify",
        "--project",
        "tropical",
        "--lookback-days",
        "30",
        "--dry-run",
        "--json",
    )
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail classify"
    assert calls["client_init"] == 1


def test_graph_mail_obsidian_parses(tmp_path: Path) -> None:
    res = _invoke(
        tmp_path,
        "graph",
        "mail",
        "obsidian",
        "--project",
        "tropical",
        "--include-encrypted-body-status",
        "--dry-run",
        "--json",
    )
    assert res.exit_code in (0, 1)
    payload = json.loads(res.output)
    assert payload["command"] == "graph mail obsidian"
    if payload.get("ok"):
        for key in (
            "notes_planned",
            "messages_referenced",
            "encrypted_body_refs_referenced",
            "encrypted_body_status_included",
            "plaintext_body_written",
        ):
            assert key in payload
        assert payload["plaintext_body_written"] is False
    assert "access_token" not in res.output
    assert "Bearer " not in res.output
    assert "----- decrypted body" not in res.output
