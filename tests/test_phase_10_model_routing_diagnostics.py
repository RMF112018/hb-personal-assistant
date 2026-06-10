"""Phase 10 — local model routing diagnostics (fail-closed, raw-free, deterministic).

Proves the consolidated diagnostics sweep covers every routed task family, reports availability /
fail-closed / fallback correctly under model-present, model-missing, and daemon-unreachable probes,
declares a safety category per family, never routes to cloud, and emits no raw content; and that the
`local-model diagnostics` CLI verb works.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.model_diagnostics import (
    TASK_SAFETY_CATEGORY,
    build_routing_diagnostics,
    render_routing_diagnostics_markdown,
)

runner = CliRunner()
# Models that satisfy the primary profiles (mistral-nemo for default/synthesis; qwen for review).
PRESENT = {"mistral-nemo:12b", "qwen2.5:14b", "llama3.1:8b"}


def test_daemon_unreachable_is_fail_closed_no_cloud() -> None:
    diag = build_routing_diagnostics(present_models=None, daemon_reachable=False)
    assert diag["ok"] is True
    assert diag["counts"]["total"] >= 6
    assert diag["counts"]["blocked"] == diag["counts"]["total"]  # every family fails closed
    for d in diag["diagnostics"]:
        assert d["available"] is False
        assert d["fail_closed_reason"] is not None
        assert d["no_cloud"] is True
        assert d["safety_category"] == TASK_SAFETY_CATEGORY.get(d["task_family"], "redacted_advisory")
    assert diag["guardrails"]["no_cloud"] is True
    assert diag["guardrails"]["fail_closed_on_unavailable"] is True


def test_models_present_are_available() -> None:
    diag = build_routing_diagnostics(present_models=PRESENT, daemon_reachable=True)
    assert diag["counts"]["available"] == diag["counts"]["total"]
    for d in diag["diagnostics"]:
        assert d["selected_profile"] is not None
        assert d["model_name"] in PRESENT
        assert d["candidate_model_chain"]  # chain populated


def test_missing_primary_model_falls_back_or_blocks() -> None:
    # Only the shared default extractor model present → review_filter's primary (qwen) is missing,
    # so relationship_scoring must fall back to default_extract (or block, never cloud).
    diag = build_routing_diagnostics(present_models={"mistral-nemo:12b"}, daemon_reachable=True)
    rel = next(d for d in diag["diagnostics"] if d["task_family"] == "relationship_scoring")
    assert rel["no_cloud"] is True
    if rel["available"]:
        assert rel["reason_code"] == "selected_fallback"
        assert rel["fallback_reason"] == "model_missing"
    else:
        assert rel["fail_closed_reason"] is not None


def test_no_raw_content_in_output() -> None:
    diag = build_routing_diagnostics(present_models=PRESENT, daemon_reachable=True)
    blob = json.dumps(diag) + render_routing_diagnostics_markdown(diag)
    for bad in ("Bearer ", "https://", "-----BEGIN", '"prompt"', '"response"', "@"):
        assert bad not in blob


def test_cli_diagnostics_emits_json() -> None:
    res = runner.invoke(app, ["second-brain", "local-model", "diagnostics", "--mock", "--json"])
    assert res.exit_code in (0, 2), res.output
    payload = json.loads(res.output)
    assert payload["command"] == "second-brain local-model diagnostics"
    assert "diagnostics" in payload
    assert payload["guardrails"]["no_cloud"] is True
