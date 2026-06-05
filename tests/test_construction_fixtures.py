"""Tests for the canonical fixture inventory + validation harness (Phase 01 Step 11).

Covers:
- Inventory size + per-kind counts.
- Full harness pass.
- INVALID model-output fixtures each raise with the declared error code.
- Review-policy fixtures fire the declared expected_rule_ids set.
- Guardrail string-scans: no body text in graph-delta fixtures; no
  common secret patterns anywhere in the inventory; harness performs no
  HTTP imports.
- CLI: ``construction-agent fixtures validate`` (full + kind filter +
  invalid kind exit 1); help-shape regression.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.classification import (
    InvalidModelOutputError,
    parse_and_validate,
)
from hb_assistant.construction.fixtures import (
    ALL_FIXTURES,
    GRAPH_DELTA_FIXTURES,
    INVALID_FIXTURES,
    KIND_ALIASES,
    PROCORE_CONTRACT_FIXTURES,
    PROCORE_PROJECTS_FIXTURES,
    REVIEW_POLICY_FIXTURES,
    SOURCE_REGISTRY_FIXTURES,
    VALID_FIXTURES,
    FixtureHarness,
    iter_fixtures,
)
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    load_review_rules,
)

# ---------------------------------------------------------------------------
# Inventory shape
# ---------------------------------------------------------------------------


def test_inventory_size_matches_module_dicts() -> None:
    expected = (
        len(GRAPH_DELTA_FIXTURES)
        + len(SOURCE_REGISTRY_FIXTURES)
        + len(REVIEW_POLICY_FIXTURES)
        + len(VALID_FIXTURES)
        + len(INVALID_FIXTURES)
        + len(PROCORE_CONTRACT_FIXTURES)
        + len(PROCORE_PROJECTS_FIXTURES)
    )
    assert len(ALL_FIXTURES) == expected


def test_inventory_keys_use_kind_prefix() -> None:
    for name in ALL_FIXTURES:
        assert ":" in name, f"fixture key {name!r} must use 'kind:short_name' shape"


def test_iter_fixtures_filters_by_alias() -> None:
    rows = list(iter_fixtures("model_output"))
    kinds = {entry["kind"] for _, entry in rows}
    assert kinds == {"model_output_valid", "model_output_invalid"}


def test_iter_fixtures_rejects_unknown_kind() -> None:
    with pytest.raises(KeyError):
        list(iter_fixtures("garbage"))


def test_known_kind_aliases_match_documented_set() -> None:
    assert set(KIND_ALIASES) == {
        "graph_delta",
        "source_registry",
        "review_policy",
        "model_output",
        "procore",
    }


# ---------------------------------------------------------------------------
# Harness — full + per-kind
# ---------------------------------------------------------------------------


def test_full_harness_validates_clean() -> None:
    r = FixtureHarness().validate_all()
    assert r.ok is True, [row for row in r.results if not row["passed"]]
    assert r.failed == 0
    assert r.total == len(ALL_FIXTURES)


@pytest.mark.parametrize("kind", sorted(KIND_ALIASES))
def test_harness_per_kind_filter(kind: str) -> None:
    r = FixtureHarness().validate_all(kind=kind)
    assert r.ok is True
    expected_internal_kinds = set(KIND_ALIASES[kind])
    actual_kinds = {row["kind"] for row in r.results}
    assert actual_kinds == expected_internal_kinds


# ---------------------------------------------------------------------------
# Invalid model fixtures raise with the declared code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,entry", sorted(INVALID_FIXTURES.items()))
def test_invalid_model_fixture_raises_declared_code(name: str, entry: dict) -> None:
    expected = entry["expected_code"]
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate(entry["raw"])
    assert exc.value.code == expected, (
        f"fixture {name!r} declared code={expected!r} but raised {exc.value.code!r}"
    )


# ---------------------------------------------------------------------------
# Review-policy fixtures fire expected rules
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def evaluator() -> ReviewPolicyEvaluator:
    return ReviewPolicyEvaluator(load_review_rules())


@pytest.mark.parametrize("name,fixture", sorted(REVIEW_POLICY_FIXTURES.items()))
def test_review_policy_fixture_fires_expected(
    evaluator: ReviewPolicyEvaluator,
    name: str,
    fixture: dict,
) -> None:
    matches = evaluator.evaluate(
        source_key="fixture",
        project_key=None,
        item=fixture["inventory"],
    )
    actual = {m.rule_id for m in matches}
    expected = set(fixture["expected_rule_ids"])
    if expected:
        assert expected.issubset(actual), (
            f"{name}: expected {sorted(expected)}, got {sorted(actual)}"
        )
    else:
        assert actual == set(), f"{name}: expected zero matches, got {sorted(actual)}"


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


_BODY_FIELDS = ("content", "body", "text", "excerpt")


def test_graph_delta_fixtures_have_no_body_text() -> None:
    for name, payload in GRAPH_DELTA_FIXTURES.items():
        for entry in payload.get("value", []):
            for field in _BODY_FIELDS:
                assert field not in entry, (
                    f"graph_delta fixture {name!r} illegally carries body field {field!r}"
                )


_SECRET_PATTERNS = (
    "AKIA",  # AWS access key prefix
    "Bearer ",  # bearer-token header
    "PRIVATE KEY",  # PEM blob
    "-----BEGIN",  # PEM marker
    "password=",
    "secret=",
    "api_key=",
    "x-api-key:",
)


def test_fixture_inventory_carries_no_secrets() -> None:
    blob = json.dumps(
        {name: entry["payload"] for name, entry in ALL_FIXTURES.items()},
        default=str,
    )
    for needle in _SECRET_PATTERNS:
        assert needle not in blob, (
            f"fixture inventory unexpectedly contains secret pattern {needle!r}"
        )


def test_fixture_module_imports_no_http_client() -> None:
    """Harness must not import requests / httpx / urllib3 / aiohttp."""
    import importlib
    import inspect
    import pkgutil

    import hb_assistant.construction.fixtures as pkg

    banned = {"requests", "httpx", "urllib3", "aiohttp"}
    for _, name, ispkg in pkgutil.walk_packages(
        pkg.__path__, prefix="hb_assistant.construction.fixtures."
    ):
        if ispkg:
            continue
        mod = importlib.import_module(name)
        src = inspect.getsource(mod)
        for ban in banned:
            assert f"import {ban}" not in src, f"{name} unexpectedly imports {ban}"
            assert f"from {ban}" not in src, f"{name} unexpectedly imports from {ban}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_root_help_lists_fixtures(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["--help"])
    assert r.exit_code == 0
    assert "fixtures" in r.output


def test_cli_fixtures_validate_clean(runner: CliRunner) -> None:
    r = runner.invoke(construction_cli.app, ["fixtures", "validate", "--json"])
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["report"]["ok"] is True
    assert p["report"]["failed"] == 0
    assert p["report"]["total"] == len(ALL_FIXTURES)
    assert p["guardrails"]["no_secrets_in_fixtures"] is True


def test_cli_fixtures_validate_kind_filter(runner: CliRunner) -> None:
    r = runner.invoke(
        construction_cli.app,
        ["fixtures", "validate", "--kind", "model_output", "--json"],
    )
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["filter"]["kind"] == "model_output"
    kinds_seen = {row["kind"] for row in p["report"]["results"]}
    assert kinds_seen == {"model_output_valid", "model_output_invalid"}


def test_cli_fixtures_validate_invalid_kind_exits_1(runner: CliRunner) -> None:
    r = runner.invoke(
        construction_cli.app,
        ["fixtures", "validate", "--kind", "garbage", "--json"],
    )
    assert r.exit_code == 1
    p = json.loads(r.output)
    assert p["status"] == "invalid_kind_filter"
    assert "garbage" in p["requested"]
