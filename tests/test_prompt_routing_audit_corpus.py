"""July 2026 audit §4 — versioned 50-prompt routing corpus (PR-14)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from hb_assistant.obsidian_mcp.prompt_preflight import route_prompt  # noqa: E402
from route_proof_lib import evaluate_route_expectations, route_actual  # noqa: E402

_CORPUS_PATH = ROOT / "tests" / "fixtures" / "prompt_routing_audit_corpus_v1.json"
_CORPUS: dict = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
_CASES: list[dict] = _CORPUS["cases"]


def _route_case(case: dict) -> tuple[dict, dict]:
    kwargs = dict(case.get("route_kwargs") or {})
    plan = route_prompt(case["prompt"], **kwargs)
    return plan, route_actual(plan)


def _plan_mismatches(case: dict, plan: dict) -> list[str]:
    expected_plan = case.get("expected_plan") or {}
    mismatches: list[str] = []
    for key, expected in expected_plan.items():
        got = plan.get(key)
        if got != expected:
            mismatches.append(f"plan[{key}]: expected {expected!r} got {got!r}")
    return mismatches


def test_corpus_metadata() -> None:
    assert _CORPUS["corpus_version"] == 1
    assert _CORPUS["case_count"] == 50
    assert len(_CASES) == 50
    assert _CORPUS["required_count"] == 47
    assert _CORPUS["accepted_partial_count"] == 3
    assert {c["audit_row"] for c in _CASES} == set(range(1, 51))


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_audit_corpus_offline_route(case: dict) -> None:
    plan, actual = _route_case(case)
    mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
    mismatches.extend(_plan_mismatches(case, plan))
    if case.get("enforcement") == "accepted_partial" and mismatches:
        pytest.xfail(f"accepted_partial debt: {mismatches}")
    assert mismatches == [], (case["id"], mismatches, actual)


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.get("enforcement") == "required"],
    ids=[c["id"] for c in _CASES if c.get("enforcement") == "required"],
)
def test_required_audit_rows_pass_offline(case: dict) -> None:
    plan, actual = _route_case(case)
    mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
    mismatches.extend(_plan_mismatches(case, plan))
    assert mismatches == [], (case["id"], mismatches, actual)


@pytest.fixture()
def broker_route_fn():
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
    from hb_assistant.store.migrator import SQLiteMigrator

    d = Path(tempfile.mkdtemp(prefix="audit-corpus-broker-"))
    db = str(d / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    vault = d / "vault"
    vault.mkdir()
    cfg = NasMcpConfig(
        db_path=Path(db),
        audit_dir=d / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=d / "bk", support_dir=d / "sup"),
    )
    broker = NasMcpBroker(cfg)

    def route(prompt: str, **kwargs: object) -> dict:
        payload = {"prompt": prompt, **kwargs}
        receipt = broker.dispatch("pa_prompt_route", payload)
        assert receipt.get("ok"), receipt
        return receipt["result"]

    return route


@pytest.mark.parametrize(
    "case",
    [c for c in _CASES if c.get("enforcement") == "required"],
    ids=[f"broker-{c['id']}" for c in _CASES if c.get("enforcement") == "required"],
)
def test_required_audit_rows_pass_broker(case: dict, broker_route_fn) -> None:
    kwargs = dict(case.get("route_kwargs") or {})
    plan = broker_route_fn(case["prompt"], **kwargs)
    actual = route_actual(plan)
    mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
    mismatches.extend(_plan_mismatches(case, plan))
    assert mismatches == [], (case["id"], mismatches, actual)


@pytest.mark.live
@pytest.mark.parametrize("case", _CASES, ids=[f"live-{c['id']}" for c in _CASES])
def test_audit_corpus_live_nas_replay(case: dict) -> None:
    """Optional NAS/container replay — run with HB_PROMPT_ROUTING_AUDIT_LIVE=1."""
    if os.environ.get("HB_PROMPT_ROUTING_AUDIT_LIVE") != "1":
        pytest.skip("set HB_PROMPT_ROUTING_AUDIT_LIVE=1 for live NAS replay")

    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig

    broker = NasMcpBroker(NasMcpConfig.from_env())
    kwargs = dict(case.get("route_kwargs") or {})
    receipt = broker.dispatch("pa_prompt_route", {"prompt": case["prompt"], **kwargs})
    assert receipt.get("ok"), receipt
    plan = receipt["result"]
    actual = route_actual(plan)
    mismatches = evaluate_route_expectations(case.get("expected") or {}, actual)
    mismatches.extend(_plan_mismatches(case, plan))
    if case.get("enforcement") == "accepted_partial" and mismatches:
        pytest.xfail(f"accepted_partial debt: {mismatches}")
    assert mismatches == [], (case["id"], mismatches, actual)