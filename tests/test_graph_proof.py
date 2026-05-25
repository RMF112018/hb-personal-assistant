"""Tests for current runtime delegated graph proof runner and CLI wiring."""

from __future__ import annotations

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.graph.proof_runner import _classify_delegated_claims, run_delegated_graph_proof


runner = CliRunner()


def test_delegated_classification_rule() -> None:
    delegated = _classify_delegated_claims({"scp": "User.Read Mail.Read"})
    assert delegated["classification"] == "delegated"
    assert delegated["has_scp"] is True
    assert delegated["has_roles"] is False
    assert delegated["delegated_runtime_valid"] is True

    app_only = _classify_delegated_claims({"roles": ["Sites.Read.All"]})
    assert app_only["classification"] == "app_only"
    assert app_only["delegated_runtime_valid"] is False


def test_runner_blocks_without_delegated_token(monkeypatch) -> None:
    from hb_assistant.graph import proof_runner as pr

    class FakeDelegated:
        def __init__(self, *args, **kwargs):
            pass

        def get_token(self, scopes=None, force_refresh=False):
            raise RuntimeError("no token")

    class FakeAppOnly:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(pr, "DelegatedAuthProvider", FakeDelegated)
    monkeypatch.setattr(pr, "AppOnlyAuthProvider", FakeAppOnly)

    result = run_delegated_graph_proof(safe=True)
    assert result["status"] == "blocked_no_token"
    assert "remediation" in result


def test_cli_proof_positional_grammar_parses() -> None:
    result = runner.invoke(app, ["diagnostics", "proof", "delegated-graph", "--json"])
    assert result.exit_code in (0, 1)


def test_cli_proof_back_compat_alias_parses() -> None:
    result = runner.invoke(app, ["diagnostics", "proof", "--delegated-graph", "--json"])
    assert result.exit_code in (0, 1)
