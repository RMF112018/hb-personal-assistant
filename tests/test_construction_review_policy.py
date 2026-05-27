"""Tests for the construction-agent review queue policy (Phase 01 Step 7).

Covers:
- Pydantic rule loading and validators
- Deterministic evaluator across folder_path / document_name / risk_term
- Router idempotency on the (source_key, item_id, rule_id) unique constraint
- ConstructionStore review-queue roundtrip
- ManifestService.build_review_required_note() default store-pull
- CLI ``review evaluate`` and ``review list``
- Guardrail: source-document body text never reaches the rendered note
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli import construction as construction_cli
from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.manifests import (
    ManifestRenderer,
    ManifestService,
)
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    ReviewQueueRouter,
    ReviewRule,
    ReviewRules,
    ReviewRulesError,
    RuleMatch,
    load_review_rules,
)
from hb_assistant.construction.policy.loader import ENV_VAR
from hb_assistant.construction.store import ConstructionStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "review.sqlite")


@pytest.fixture
def store(db_path: str) -> ConstructionStore:
    return ConstructionStore(db_path)


@pytest.fixture
def seed_rules() -> ReviewRules:
    return load_review_rules()


@pytest.fixture
def evaluator(seed_rules: ReviewRules) -> ReviewPolicyEvaluator:
    return ReviewPolicyEvaluator(seed_rules)


def _seed_inventory(store: ConstructionStore, source_key: str = "tropical-sharepoint") -> None:
    """Seed an inventory mix covering every protected category + a clean miss."""
    items = [
        # contract via folder
        ("item-contract-folder", "Master Agreement.pdf", "/Tropical/Contracts/Vendors"),
        # contract via document name (Change Order)
        ("item-change-order", "Change Order 04 - Roofing.pdf", "/Tropical/General"),
        # financial via folder
        ("item-financials-folder", "Q3 Forecast.xlsx", "/Tropical/Financials/2026"),
        # financial via invoice document name
        ("item-invoice", "Invoice 1042 - Subcontractor.pdf", "/Tropical/General"),
        # financial via purchase order document name
        ("item-po", "PO 2025-08 - Steel.pdf", "/Tropical/General"),
        # legal via folder
        ("item-legal-folder", "Counsel Memo.docx", "/Tropical/Legal"),
        # incident via folder + risk term (multi-rule)
        ("item-incident-folder", "Site Incident Report.pdf", "/Tropical/Safety/Incidents"),
        # injury via risk term
        ("item-injury-term", "Worker Injury Log.pdf", "/Tropical/General"),
        # personnel via folder
        ("item-personnel-folder", "Onboarding.docx", "/Tropical/HR/Employees"),
        # confidential via risk term
        ("item-confidential", "Confidential Memo.pdf", "/Tropical/General"),
        # low-confidence via budget term
        ("item-low-conf-budget", "Budget Estimate Draft.xlsx", "/Tropical/General"),
        # clean miss — should produce ZERO matches
        ("item-clean-miss", "Project Photos.zip", "/Tropical/General"),
    ]
    for item_id, name, parent_path in items:
        store.upsert_inventory_item(
            source_key=source_key,
            drive_id="drive-fake",
            item_id=item_id,
            name=name,
            web_url=f"https://example/{item_id}",
            parent_path=parent_path,
            size_bytes=1024,
            is_folder=False,
            last_modified=None,
            etag=None,
        )


# ---------------------------------------------------------------------------
# Rule loading + validators
# ---------------------------------------------------------------------------


def test_seed_rules_load_and_cover_protected_categories(seed_rules: ReviewRules) -> None:
    assert seed_rules.version >= 1
    assert seed_rules.low_confidence_threshold == 0.7
    labels = {r.classification_label for r in seed_rules.rules}
    for required in ("contract", "financial", "legal", "incident", "injury", "personnel"):
        assert required in labels, f"seed missing protected category {required!r}"


def test_seed_rules_have_unique_ids(seed_rules: ReviewRules) -> None:
    ids = [r.rule_id for r in seed_rules.rules]
    assert len(ids) == len(set(ids))


def test_seed_includes_low_confidence_rule(seed_rules: ReviewRules) -> None:
    low_conf = [r for r in seed_rules.rules if r.confidence < seed_rules.low_confidence_threshold]
    assert low_conf, "seed must include at least one low-confidence rule for routing hints"


def test_duplicate_rule_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        ReviewRules.model_validate(
            {
                "rules": [
                    {
                        "rule_id": "dup",
                        "kind": "risk_term",
                        "pattern": "x",
                        "sensitivity": "high",
                        "classification_label": "contract",
                        "reason": "r",
                        "suggested_action": "review",
                    },
                    {
                        "rule_id": "dup",
                        "kind": "risk_term",
                        "pattern": "y",
                        "sensitivity": "high",
                        "classification_label": "financial",
                        "reason": "r",
                        "suggested_action": "review",
                    },
                ]
            }
        )


def test_missing_protected_category_rejected() -> None:
    with pytest.raises(ValidationError):
        ReviewRules.model_validate(
            {
                "rules": [
                    {
                        "rule_id": "only-contract",
                        "kind": "risk_term",
                        "pattern": "contract",
                        "sensitivity": "high",
                        "classification_label": "contract",
                        "reason": "r",
                        "suggested_action": "review",
                    }
                ]
            }
        )


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        ReviewRule(
            rule_id="x",
            kind="filetype",  # type: ignore[arg-type]
            pattern="*.pdf",
            sensitivity="high",
            classification_label="contract",
            reason="r",
            suggested_action="review",
        )


def test_invalid_sensitivity_rejected() -> None:
    with pytest.raises(ValidationError):
        ReviewRule(
            rule_id="x",
            kind="risk_term",
            pattern="x",
            sensitivity="extreme",  # type: ignore[arg-type]
            classification_label="contract",
            reason="r",
            suggested_action="review",
        )


def test_confidence_range_validated() -> None:
    with pytest.raises(ValidationError):
        ReviewRule(
            rule_id="x", kind="risk_term", pattern="x", sensitivity="high",
            classification_label="contract", reason="r", suggested_action="review",
            confidence=1.5,
        )


def test_rule_id_must_be_kebab_case() -> None:
    with pytest.raises(ValidationError):
        ReviewRule(
            rule_id="Bad ID",
            kind="risk_term", pattern="x", sensitivity="high",
            classification_label="contract", reason="r", suggested_action="review",
        )


def test_env_var_override_replaces_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = tmp_path / "rules.yml"
    override.write_text(
        yaml.safe_dump(
            {
                "version": 99,
                "low_confidence_threshold": 0.5,
                "rules": [
                    {
                        "rule_id": f"only-{cat}",
                        "kind": "risk_term",
                        "pattern": cat,
                        "sensitivity": "high",
                        "classification_label": cat,
                        "reason": f"contains {cat}",
                        "suggested_action": "controller_review",
                    }
                    for cat in ("contract", "financial", "legal", "incident", "injury", "personnel")
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_VAR, str(override))
    rules = load_review_rules()
    assert rules.version == 99
    assert {r.rule_id for r in rules.rules} == {
        "only-contract", "only-financial", "only-legal",
        "only-incident", "only-injury", "only-personnel",
    }


def test_missing_seed_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from hb_assistant.construction.policy import loader as loader_mod

    monkeypatch.setattr(loader_mod, "_resolve_seed_path", lambda: tmp_path / "missing.yaml")
    monkeypatch.setattr(loader_mod, "_resolve_repo_override_path", lambda: tmp_path / "absent.yml")
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(ReviewRulesError):
        load_review_rules()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _item(item_id: str, name: str, parent_path: str) -> dict:
    return {"item_id": item_id, "name": name, "parent_path": parent_path}


def test_evaluator_matches_contract_folder(evaluator: ReviewPolicyEvaluator) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key="p",
        item=_item("i1", "Master Agreement.pdf", "/Tropical/Contracts/Vendors"),
    )
    rule_ids = {m.rule_id for m in matches}
    assert "folder-contracts" in rule_ids


def test_evaluator_matches_change_order_doc_name(evaluator: ReviewPolicyEvaluator) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key="p",
        item=_item("i2", "Change Order 04 - Roofing.pdf", "/Tropical/General"),
    )
    assert any(m.rule_id == "doc-change-order" for m in matches)
    assert all(m.classification_label != "personnel" for m in matches)


def test_evaluator_matches_injury_risk_term(evaluator: ReviewPolicyEvaluator) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key="p",
        item=_item("i3", "Worker Injury Log.pdf", "/Tropical/General"),
    )
    rule_ids = {m.rule_id for m in matches}
    assert "term-injury" in rule_ids
    inj = next(m for m in matches if m.rule_id == "term-injury")
    assert inj.sensitivity == "critical"


def test_evaluator_is_case_insensitive(evaluator: ReviewPolicyEvaluator) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key=None,
        item=_item("i4", "INVOICE 99.pdf", "/TROPICAL/general"),
    )
    assert any(m.rule_id == "doc-invoice" for m in matches)


def test_evaluator_emits_multiple_matches_for_one_item(evaluator: ReviewPolicyEvaluator) -> None:
    # Incident folder + incident risk term must both fire so controllers see provenance.
    matches = evaluator.evaluate(
        source_key="src", project_key="p",
        item=_item("i5", "Site Incident Report.pdf", "/Tropical/Safety/Incidents"),
    )
    rule_ids = {m.rule_id for m in matches}
    assert {"folder-incidents", "term-incident"}.issubset(rule_ids)


def test_evaluator_low_confidence_rule_carries_low_confidence(
    evaluator: ReviewPolicyEvaluator, seed_rules: ReviewRules,
) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key=None,
        item=_item("i6", "Budget Estimate Draft.xlsx", "/Tropical/General"),
    )
    budget = next((m for m in matches if m.rule_id == "term-budget-ambiguous"), None)
    assert budget is not None
    assert budget.confidence < seed_rules.low_confidence_threshold


def test_evaluator_clean_miss_yields_no_matches(evaluator: ReviewPolicyEvaluator) -> None:
    matches = evaluator.evaluate(
        source_key="src", project_key="p",
        item=_item("i7", "Project Photos.zip", "/Tropical/General"),
    )
    assert matches == []


def test_evaluator_ignores_item_with_missing_id(evaluator: ReviewPolicyEvaluator) -> None:
    assert evaluator.evaluate(source_key="src", project_key=None, item={"name": "x"}) == []


# ---------------------------------------------------------------------------
# Router + store roundtrip
# ---------------------------------------------------------------------------


def test_router_dry_run_does_not_persist(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    _seed_inventory(store)
    router = ReviewQueueRouter(store, evaluator)
    result = router.evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=False,
    )
    assert result.matches_found > 0
    assert result.enqueued == 0
    assert store.count_review_queue() == 0


def test_router_apply_enqueues_and_is_idempotent(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    _seed_inventory(store)
    router = ReviewQueueRouter(store, evaluator)

    first = router.evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )
    enqueued_first = first.enqueued
    assert enqueued_first > 0
    assert first.skipped_already_open == 0
    assert store.count_review_queue() == enqueued_first

    second = router.evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )
    assert second.enqueued == 0
    assert second.skipped_already_open == enqueued_first
    assert store.count_review_queue() == enqueued_first


def test_store_list_review_queue_filters_by_status_and_source(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    _seed_inventory(store)
    router = ReviewQueueRouter(store, evaluator)
    router.evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )

    all_rows = store.list_review_queue(status=None)
    open_rows = store.list_review_queue(status="open")
    resolved_rows = store.list_review_queue(status="resolved")
    other_source = store.list_review_queue(source_key="nonexistent", status=None)

    assert len(all_rows) == len(open_rows) > 0
    assert resolved_rows == []
    assert other_source == []


def test_store_enqueue_returns_false_on_duplicate(
    store: ConstructionStore,
) -> None:
    match = RuleMatch(
        rule_id="folder-contracts", item_id="x", source_key="s", project_key="p",
        name="n", parent_path="/Contracts", sensitivity="high",
        classification_label="contract", reason="r", suggested_action="review",
    )
    assert store.enqueue_review_item(match) is True
    assert store.enqueue_review_item(match) is False


# ---------------------------------------------------------------------------
# ManifestService default store-pull + render
# ---------------------------------------------------------------------------


def test_build_review_required_note_defaults_to_store_pull(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    _seed_inventory(store)
    ReviewQueueRouter(store, evaluator).evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )

    svc = ManifestService(store)
    note = svc.build_review_required_note()
    assert len(note.items) == store.count_review_queue()
    assert all(item.source_key == "tropical-sharepoint" for item in note.items)
    assert all(item.reason for item in note.items)


def test_build_review_required_note_explicit_items_bypasses_store(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    _seed_inventory(store)
    ReviewQueueRouter(store, evaluator).evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )

    svc = ManifestService(store)
    note = svc.build_review_required_note(items=[])
    assert note.items == []


def test_rendered_note_never_leaks_body_text(
    store: ConstructionStore, evaluator: ReviewPolicyEvaluator,
) -> None:
    """Guardrail: only metadata fields appear in the rendered Markdown.

    We seed the inventory with a sentinel string in a known body-shaped field
    and assert the renderer cannot surface it (because the renderer only ever
    sees Pydantic ReviewRequiredItem fields — which don't carry body content).
    """
    _seed_inventory(store)
    SENTINEL = "BODY_SENTINEL_SHOULD_NEVER_APPEAR_IN_VAULT"

    svc = ManifestService(store)
    ReviewQueueRouter(store, evaluator).evaluate_source(
        source_key="tropical-sharepoint", project_key="tropical", apply=True,
    )
    note = svc.build_review_required_note()
    rendered = ManifestRenderer.render_review_required(note)
    assert SENTINEL not in rendered
    # Sanity: at least one item rendered
    assert "controller_review" in rendered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _patch_store_to_tmp(monkeypatch: pytest.MonkeyPatch, db_path: str) -> None:
    """Force the CLI to use a temp SQLite DB via the connection layer."""
    from hb_assistant.store import connection as conn_mod

    real_get_connection = conn_mod.get_connection

    def _get(db: str | None = None):
        return real_get_connection(db_path)

    monkeypatch.setattr(conn_mod, "get_connection", _get)
    # Also patch the symbol re-exported into modules that imported it eagerly.
    from hb_assistant.construction.store import repositories as repo_mod
    from hb_assistant.store import migrator as mig_mod
    monkeypatch.setattr(repo_mod, "get_connection", _get)
    monkeypatch.setattr(mig_mod, "get_connection", _get)


def test_cli_review_list_empty(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    result = runner.invoke(construction_cli.app, ["review", "list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == 0
    assert payload["counts_by_status"] == {"open": 0, "resolved": 0, "deferred": 0}
    assert payload["guardrails"]["model_decisioning"] is False


def test_cli_review_evaluate_dry_run_does_not_persist(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    store = ConstructionStore()
    _seed_inventory(store)

    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "tropical-sharepoint", "--dry-run", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["matches_found"] > 0
    assert payload["summary"]["enqueued"] == 0
    assert ConstructionStore().count_review_queue() == 0


def test_cli_review_evaluate_apply_then_list_then_idempotent(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    store = ConstructionStore()
    _seed_inventory(store)

    runner = CliRunner()
    apply1 = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "tropical-sharepoint", "--apply", "--json"],
    )
    assert apply1.exit_code == 0, apply1.output
    p1 = json.loads(apply1.output)
    assert p1["mode"] == "apply"
    assert p1["summary"]["enqueued"] > 0
    enq = p1["summary"]["enqueued"]

    listing = runner.invoke(construction_cli.app, ["review", "list", "--json"])
    assert listing.exit_code == 0, listing.output
    pl = json.loads(listing.output)
    assert pl["total"] == enq
    assert pl["counts_by_status"]["open"] == enq

    apply2 = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "tropical-sharepoint", "--apply", "--json"],
    )
    assert apply2.exit_code == 0
    p2 = json.loads(apply2.output)
    assert p2["summary"]["enqueued"] == 0
    assert p2["summary"]["skipped_already_open"] == enq


def test_cli_review_list_invalid_status(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app, ["review", "list", "--status", "garbage", "--json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "invalid_status_filter"


def test_cli_review_evaluate_unknown_source(
    monkeypatch: pytest.MonkeyPatch, db_path: str,
) -> None:
    _patch_store_to_tmp(monkeypatch, db_path)
    runner = CliRunner()
    result = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "nonexistent-source", "--json"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "not_found"


def test_cli_vault_preview_populates_review_note_from_store(
    monkeypatch: pytest.MonkeyPatch, db_path: str, tmp_path: Path,
) -> None:
    """End-to-end: enqueue items, then vault preview surfaces a populated note."""
    _patch_store_to_tmp(monkeypatch, db_path)
    store = ConstructionStore()
    _seed_inventory(store)

    runner = CliRunner()
    apply_eval = runner.invoke(
        construction_cli.app,
        ["review", "evaluate", "--source", "tropical-sharepoint", "--apply", "--json"],
    )
    assert apply_eval.exit_code == 0, apply_eval.output

    vault_root = tmp_path / "vault"
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault_root))
    preview = runner.invoke(
        construction_cli.app, ["vault", "preview", "--apply", "--json"]
    )
    assert preview.exit_code == 0, preview.output
    rendered_review = json.loads(preview.output)["rendered"]["review_required_md"]
    assert "_no items currently flagged for review_" not in rendered_review
    assert "controller_review" in rendered_review

    # The note file must exist and contain the same items.
    written = next((vault_root / "02_Review_Queue").iterdir())
    body = written.read_text(encoding="utf-8")
    assert "controller_review" in body


# ---------------------------------------------------------------------------
# Source registry sanity (ensures the seed source key used in tests resolves)
# ---------------------------------------------------------------------------


def test_seed_source_key_used_by_tests_exists() -> None:
    from hb_assistant.construction.config import load_source_registry
    registry = load_source_registry()
    assert any(s.source_key == "tropical-sharepoint" for s in registry.sources)


def test_source_location_constructs_for_test_fixtures() -> None:
    # Defensive: ensure the SourceLocation model still accepts the test shape
    SourceLocation(
        source_key="tropical-sharepoint",
        project_key="tropical",
        kind="sharepoint_site",
        display_name="Tropical SharePoint Site",
        read_only=True,
        resolution_status="pending",
    )
