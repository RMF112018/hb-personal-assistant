"""Tests for the construction-agent Ollama classification layer (Phase 01 Step 8).

Covers:
- Pydantic model + routing-config loading + validators
- Strict JSON + schema validation (every failure mode)
- Deterministic router: protected category, low confidence, controller-policy
  override (model can never override controller, even at confidence 1.0)
- ConstructionStore V4 audit-table roundtrip
- OllamaChatClient: redacted error on network failure
- ClassificationService end-to-end with a mocked client
- CLI: classify run --fixture, --mock-output (valid + invalid), classify decisions
- Guardrail string-scans
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.classification import (
    ClassificationRouter,
    ClassificationService,
    InvalidModelOutputError,
    ModelClassification,
    ModelRoutingConfig,
    ModelRoutingError,
    OllamaChatClient,
    OllamaUnavailable,
    load_model_routing_config,
    parse_and_validate,
)
from hb_assistant.construction.classification.loader import ENV_VAR
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    load_review_rules,
)
from hb_assistant.construction.store import ConstructionStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "model_decisions.sqlite")


@pytest.fixture
def store(db_path: str) -> ConstructionStore:
    return ConstructionStore(db_path)


@pytest.fixture
def config() -> ModelRoutingConfig:
    return load_model_routing_config()


@pytest.fixture
def policy_evaluator() -> ReviewPolicyEvaluator:
    return ReviewPolicyEvaluator(load_review_rules())


@pytest.fixture
def router(config: ModelRoutingConfig) -> ClassificationRouter:
    return ClassificationRouter(config)


@pytest.fixture
def router_with_policy(
    config: ModelRoutingConfig, policy_evaluator: ReviewPolicyEvaluator,
) -> ClassificationRouter:
    return ClassificationRouter(config, policy_evaluator=policy_evaluator)


@pytest.fixture
def service(
    config: ModelRoutingConfig, router: ClassificationRouter, store: ConstructionStore,
) -> ClassificationService:
    return ClassificationService(config=config, router=router, store=store)


def _valid_raw(
    item_id: str = "i1",
    label: str = "operational",
    confidence: float = 0.9,
) -> str:
    return json.dumps({
        "item_id": item_id,
        "proposed_label": label,
        "confidence": confidence,
        "rationale": "test rationale",
        "risk_terms": [],
    })


def _inventory_item(
    item_id: str = "i1", name: str = "x.pdf", parent_path: str = "/General",
) -> dict[str, Any]:
    return {"item_id": item_id, "name": name, "parent_path": parent_path}


# ---------------------------------------------------------------------------
# Pydantic model + routing config
# ---------------------------------------------------------------------------


def test_seed_routing_config_loads_with_required_tasks(config: ModelRoutingConfig) -> None:
    assert config.default_model
    assert config.low_confidence_threshold == 0.7
    task_names = {t.task for t in config.tasks}
    assert {"classification", "review_reason"}.issubset(task_names)


def test_routing_config_protected_categories_complete(config: ModelRoutingConfig) -> None:
    for cat in ("contract", "financial", "legal", "incident", "injury", "personnel"):
        assert cat in config.protected_categories


def test_routing_config_rejects_missing_protected_category() -> None:
    with pytest.raises(ValidationError):
        ModelRoutingConfig.model_validate({
            "default_model": "m",
            "protected_categories": ["contract"],  # missing 5 others
            "tasks": [{"task": "classification", "model": "m", "system_prompt": "p"}],
        })


def test_routing_config_rejects_duplicate_task() -> None:
    with pytest.raises(ValidationError):
        ModelRoutingConfig.model_validate({
            "default_model": "m",
            "tasks": [
                {"task": "classification", "model": "m1", "system_prompt": "p"},
                {"task": "classification", "model": "m2", "system_prompt": "p"},
            ],
        })


def test_routing_config_rejects_invalid_threshold() -> None:
    with pytest.raises(ValidationError):
        ModelRoutingConfig.model_validate({
            "default_model": "m",
            "low_confidence_threshold": 1.5,
            "tasks": [{"task": "classification", "model": "m", "system_prompt": "p"}],
        })


def test_env_var_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "routing.yml"
    override.write_text(
        yaml.safe_dump({
            "version": 99,
            "default_model": "override-model",
            "low_confidence_threshold": 0.5,
            "tasks": [
                {"task": "classification", "model": "override-model", "system_prompt": "p"},
                {"task": "review_reason", "model": "override-model", "system_prompt": "p"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_VAR, str(override))
    cfg = load_model_routing_config()
    assert cfg.version == 99
    assert cfg.default_model == "override-model"
    assert cfg.low_confidence_threshold == 0.5


def test_missing_seed_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hb_assistant.construction.classification import loader as loader_mod
    monkeypatch.setattr(loader_mod, "_resolve_seed_path", lambda: tmp_path / "missing.yaml")
    monkeypatch.setattr(loader_mod, "_resolve_repo_override_path", lambda: tmp_path / "absent.yml")
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(ModelRoutingError):
        load_model_routing_config()


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def test_validator_accepts_well_formed_output() -> None:
    c = parse_and_validate(_valid_raw())
    assert isinstance(c, ModelClassification)
    assert c.confidence == 0.9


def test_validator_rejects_empty_string() -> None:
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate("")
    assert exc.value.code == "empty_output"


def test_validator_rejects_malformed_json() -> None:
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate("not-json")
    assert exc.value.code == "json_parse_failed"


def test_validator_rejects_json_array() -> None:
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate('[1,2,3]')
    assert exc.value.code == "not_a_json_object"


def test_validator_rejects_missing_required_field() -> None:
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate(json.dumps({"item_id": "x", "confidence": 0.9}))
    assert exc.value.code == "schema_validation_failed"


def test_validator_rejects_extra_fields() -> None:
    raw = json.dumps({
        "item_id": "x", "proposed_label": "operational", "confidence": 0.9,
        "rationale": "r", "risk_terms": [], "stowaway": "should-fail",
    })
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate(raw)
    assert exc.value.code == "schema_validation_failed"


def test_validator_rejects_unknown_proposed_label() -> None:
    raw = json.dumps({
        "item_id": "x", "proposed_label": "chaos", "confidence": 0.9,
        "rationale": "r", "risk_terms": [],
    })
    with pytest.raises(InvalidModelOutputError):
        parse_and_validate(raw)


def test_validator_rejects_out_of_range_confidence() -> None:
    raw = json.dumps({
        "item_id": "x", "proposed_label": "other", "confidence": 1.5,
        "rationale": "r", "risk_terms": [],
    })
    with pytest.raises(InvalidModelOutputError):
        parse_and_validate(raw)


def test_validator_rejects_empty_rationale() -> None:
    raw = json.dumps({
        "item_id": "x", "proposed_label": "other", "confidence": 0.5,
        "rationale": "   ", "risk_terms": [],
    })
    with pytest.raises(InvalidModelOutputError):
        parse_and_validate(raw)


def test_validator_truncates_snippet_in_exception_message() -> None:
    huge = "garbage " * 200
    with pytest.raises(InvalidModelOutputError) as exc:
        parse_and_validate(huge)
    msg = str(exc.value)
    # snippet capped at 200 chars
    assert len(exc.value.snippet) <= 200
    assert "garbage" in msg


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def test_router_accepts_high_confidence_non_protected(
    router: ClassificationRouter,
) -> None:
    c = parse_and_validate(_valid_raw(label="operational", confidence=0.95))
    d = router.decide(
        classification=c, source_key="s", item_id="i1", project_key=None,
        model_name="m", model_task="classification", raw_output=_valid_raw(),
    )
    assert d.status == "accepted"
    assert d.routing_reason == "model_accepted"


def test_router_routes_protected_category_to_review(router: ClassificationRouter) -> None:
    c = parse_and_validate(_valid_raw(label="contract", confidence=1.0))
    d = router.decide(
        classification=c, source_key="s", item_id="i1", project_key=None,
        model_name="m", model_task="classification", raw_output=_valid_raw(),
    )
    assert d.status == "review"
    assert "protected_category:contract" in d.routing_reason


def test_router_routes_low_confidence_to_review(router: ClassificationRouter) -> None:
    c = parse_and_validate(_valid_raw(label="operational", confidence=0.1))
    d = router.decide(
        classification=c, source_key="s", item_id="i1", project_key=None,
        model_name="m", model_task="classification", raw_output=_valid_raw(),
    )
    assert d.status == "review"
    assert "low_confidence:0.100" in d.routing_reason


def test_router_controller_policy_overrides_model_high_confidence(
    router_with_policy: ClassificationRouter,
) -> None:
    """Even at confidence 1.0 with a non-protected label, controller policy wins."""
    c = parse_and_validate(_valid_raw(label="operational", confidence=1.0))
    # Inventory item lives under /Contracts/ — controller policy will flag it
    item = _inventory_item(name="Misc.pdf", parent_path="/Tropical/Contracts/Vendors")
    d = router_with_policy.decide(
        classification=c, source_key="s", item_id="i1", project_key=None,
        model_name="m", model_task="classification", raw_output=_valid_raw(),
        inventory_item=item,
    )
    assert d.status == "review"
    assert "controller_policy_flagged:" in d.routing_reason


def test_router_truncates_raw_output(router: ClassificationRouter) -> None:
    c = parse_and_validate(_valid_raw())
    huge = "X" * 10000
    d = router.decide(
        classification=c, source_key="s", item_id="i1", project_key=None,
        model_name="m", model_task="classification", raw_output=huge,
    )
    assert len(d.raw_output_truncated) <= router.config.max_output_chars


# ---------------------------------------------------------------------------
# Service end-to-end (offline; classify_with_raw)
# ---------------------------------------------------------------------------


def test_service_classify_with_raw_persists_accepted(service: ClassificationService) -> None:
    d = service.classify_with_raw(
        raw_output=_valid_raw(item_id="i1", label="operational", confidence=0.95),
        source_key="s", item_id="i1", project_key="p", model_task="classification",
        model_name="m", inventory_item=_inventory_item(),
    )
    assert d.status == "accepted"
    rows = service._store.list_model_decisions()
    assert len(rows) == 1
    assert rows[0]["status"] == "accepted"


def test_service_classify_with_raw_persists_review_for_protected(
    service: ClassificationService,
) -> None:
    d = service.classify_with_raw(
        raw_output=_valid_raw(item_id="i1", label="contract", confidence=0.95),
        source_key="s", item_id="i1", project_key="p", model_task="classification",
        model_name="m", inventory_item=_inventory_item(),
    )
    assert d.status == "review"
    rows = service._store.list_model_decisions(status="review")
    assert len(rows) == 1


def test_service_raises_invalid_for_bad_json_and_persists_nothing(
    service: ClassificationService,
) -> None:
    with pytest.raises(InvalidModelOutputError):
        service.classify_with_raw(
            raw_output="not json",
            source_key="s", item_id="i1", project_key=None,
            model_task="classification", model_name="m",
            inventory_item=_inventory_item(),
        )
    assert service._store.count_model_decisions() == 0


def test_service_forces_review_on_item_id_mismatch(service: ClassificationService) -> None:
    """If the model echoes back the wrong item_id, we don't trust it."""
    d = service.classify_with_raw(
        raw_output=_valid_raw(item_id="WRONG", label="operational", confidence=0.95),
        source_key="s", item_id="i1", project_key=None, model_task="classification",
        model_name="m", inventory_item=_inventory_item("i1"),
    )
    assert d.status == "review"
    assert "item_id_mismatch:" in d.routing_reason


# ---------------------------------------------------------------------------
# Store roundtrip
# ---------------------------------------------------------------------------


def test_store_list_filters_by_status_and_source(service: ClassificationService) -> None:
    service.classify_with_raw(
        raw_output=_valid_raw("a", "operational", 0.95),
        source_key="src-a", item_id="a", project_key=None,
        model_task="classification", model_name="m", inventory_item=_inventory_item("a"),
    )
    service.classify_with_raw(
        raw_output=_valid_raw("b", "contract", 0.95),
        source_key="src-b", item_id="b", project_key=None,
        model_task="classification", model_name="m", inventory_item=_inventory_item("b"),
    )
    store = service._store
    assert store.count_model_decisions() == 2
    assert store.count_model_decisions(status="accepted") == 1
    assert store.count_model_decisions(status="review") == 1
    assert store.count_model_decisions(source_key="src-a") == 1
    assert len(store.list_model_decisions(source_key="src-b", status="review")) == 1


# ---------------------------------------------------------------------------
# Client (mocked requests)
# ---------------------------------------------------------------------------


def test_client_raises_unavailable_on_network_failure() -> None:
    import requests
    client = OllamaChatClient(model="m")
    with patch.object(
        requests, "post", side_effect=requests.ConnectionError("connect refused"),
    ), pytest.raises(OllamaUnavailable) as exc:
        client.generate_json(system="s", prompt="p")
    # Sanitized — no host/URL/refused text
    assert "localhost" not in str(exc.value)
    assert "refused" not in str(exc.value)
    assert "ollama_" in str(exc.value)


def test_client_raises_unavailable_on_non_200() -> None:
    import requests
    client = OllamaChatClient(model="m")
    mock_response = MagicMock()
    mock_response.status_code = 503
    with (
        patch.object(requests, "post", return_value=mock_response),
        pytest.raises(OllamaUnavailable) as exc,
    ):
        client.generate_json(system="s", prompt="p")
    assert "ollama_status_503" in str(exc.value)


def test_client_raises_unavailable_when_envelope_missing_response_field() -> None:
    import requests
    client = OllamaChatClient(model="m")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unexpected": "shape"}
    with (
        patch.object(requests, "post", return_value=mock_response),
        pytest.raises(OllamaUnavailable),
    ):
        client.generate_json(system="s", prompt="p")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _patch_store_to_tmp(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    """Force CLI to use a temp SQLite DB (mirrors pattern from review-queue tests)."""
    from hb_assistant.store import connection as conn_mod
    real = conn_mod.get_connection

    def _get(_: str | None = None):
        return real(db_path)

    monkeypatch.setattr(conn_mod, "get_connection", _get)
    from hb_assistant.construction.store import repositories as repo_mod
    from hb_assistant.store import migrator as mig_mod
    monkeypatch.setattr(repo_mod, "get_connection", _get)
    monkeypatch.setattr(mig_mod, "get_connection", _get)


def test_cli_classify_run_fixture_sample(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app, ["classify", "run", "--fixture", "sample", "--json"],
    )
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["mode"] == "fixture"
    assert p["summary"]["total"] == 3
    assert p["summary"]["accepted"] == 1
    assert p["summary"]["review"] == 2
    assert p["summary"]["rejected"] == 0
    # Every decision was persisted
    assert ConstructionStore().count_model_decisions() == 3


def test_cli_classify_run_unknown_fixture(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app, ["classify", "run", "--fixture", "nope", "--json"],
    )
    assert r.exit_code == 1
    assert json.loads(r.output)["status"] == "unknown_fixture"


def test_cli_classify_run_mock_output_valid(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    store = ConstructionStore()
    store.upsert_inventory_item(
        source_key="tropical-sharepoint", drive_id="d", item_id="it1",
        name="Photos.zip", web_url="https://e/i", parent_path="/Tropical/General",
        size_bytes=1, is_folder=False, last_modified=None, etag=None,
    )
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app,
        ["classify", "run",
         "--source", "tropical-sharepoint", "--item", "it1",
         "--mock-output", _valid_raw("it1", "operational", 0.9),
         "--json"],
    )
    assert r.exit_code == 0, r.output
    p = json.loads(r.output)
    assert p["mode"] == "mock_output"
    assert p["decision"]["status"] == "accepted"


def test_cli_classify_run_mock_output_invalid(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    store = ConstructionStore()
    store.upsert_inventory_item(
        source_key="tropical-sharepoint", drive_id="d", item_id="it1",
        name="Photos.zip", web_url="https://e/i", parent_path="/Tropical/General",
        size_bytes=1, is_folder=False, last_modified=None, etag=None,
    )
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app,
        ["classify", "run",
         "--source", "tropical-sharepoint", "--item", "it1",
         "--mock-output", "not-json",
         "--json"],
    )
    assert r.exit_code == 1, r.output
    p = json.loads(r.output)
    assert p["status"] == "invalid_model_output"
    assert p["code"] == "json_parse_failed"
    # Nothing was persisted on rejection
    assert ConstructionStore().count_model_decisions() == 0


def test_cli_classify_run_item_not_found(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app,
        ["classify", "run",
         "--source", "tropical-sharepoint", "--item", "missing-it",
         "--mock-output", _valid_raw(),
         "--json"],
    )
    assert r.exit_code == 1
    assert json.loads(r.output)["status"] == "item_not_found"


def test_cli_classify_decisions_lists_persisted_rows(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    # Seed via fixture run
    runner.invoke(construction_cli.app, ["classify", "run", "--fixture", "sample", "--json"])

    r = runner.invoke(construction_cli.app, ["classify", "decisions", "--json"])
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["total"] == 3
    assert p["counts_by_status"]["accepted"] == 1
    assert p["counts_by_status"]["review"] == 2


def test_cli_classify_decisions_invalid_status(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    r = runner.invoke(
        construction_cli.app, ["classify", "decisions", "--status", "garbage", "--json"]
    )
    assert r.exit_code == 1
    assert json.loads(r.output)["status"] == "invalid_status_filter"


# ---------------------------------------------------------------------------
# Guardrail string-scans
# ---------------------------------------------------------------------------


def test_decision_record_never_carries_body_text(service: ClassificationService) -> None:
    """The router consumes only metadata — body text cannot appear in the audit row."""
    BODY = "BODY_SENTINEL_SHOULD_NEVER_APPEAR_IN_AUDIT_ROW"
    raw = _valid_raw("i1", "operational", 0.9)
    # We don't feed BODY anywhere — but assert by construction that no field
    # carries body content from the inventory dict, even when inventory is
    # contaminated.
    item_with_body = _inventory_item("i1")
    item_with_body["body"] = BODY  # hypothetical contamination — must not propagate

    decision = service.classify_with_raw(
        raw_output=raw, source_key="s", item_id="i1", project_key=None,
        model_task="classification", model_name="m", inventory_item=item_with_body,
    )
    blob = json.dumps(decision.model_dump())
    assert BODY not in blob


def test_protected_categories_match_review_queue_seed() -> None:
    """Protected list must match the controller-policy seed, otherwise routing
    can disagree across layers."""
    from hb_assistant.construction.policy.models import PROTECTED_CATEGORIES as POLICY_CATS
    cfg = load_model_routing_config()
    for cat in POLICY_CATS:
        assert cat in cfg.protected_categories
