"""Regression protection for endpoint-specific structured projection (V47).

Guards against regression to shallow generic projection: nested business arrays must
land in child/detail tables, high-value fields must be first-class columns, the registry
allow-list must fail closed on unknown paths, replay must be idempotent, source-quality
precedence must hold, and no transport secret may ever reach a column or sidecar.

Most tests are hermetic: they build a registry from a synthetic fixture's own field
inventory and point the loader at it, so they never depend on production payloads.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from hb_assistant.procore import projection_audit as audit
from hb_assistant.procore import projection_engine as eng
from hb_assistant.procore import projection_paths as pp
from hb_assistant.procore import projection_registry as registry
from hb_assistant.procore.structured_analytics import (
    SOURCE_QUALITY_FIXTURE_FULL,
    SOURCE_QUALITY_LEGACY,
    SOURCE_QUALITY_LIVE_FULL,
    scrub_transport_secrets,
    upsert_full_raw_payload_and_structured,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

ENDPOINT = "change-events"

# A change-event payload with the nested structure that seeded this package: nested
# change_items with budget_code.segment_items, money/quantity/cost-code fields, a vendor,
# markup_items, attachments, production_quantities, and an auth secret to be excluded.
_CHANGE_EVENT: dict[str, Any] = {
    "id": 7001,
    "number": "CE-7001",
    "company_id": 42,
    "project_id": 99,
    "status": "open",
    "change_reason": "design_development",
    "change_type": "tbd",
    "scope": "in_scope",
    "title": "Foundation rework",
    "description": "Rework footings",
    "created_at": "2026-01-02T00:00:00Z",
    "updated_at": "2026-01-03T00:00:00Z",
    "access_token": "SECRET-bearer-value-should-never-persist",
    "change_items": [
        {
            "id": 1,
            "amount": "1250.00",
            "amount_project_currency": "1250.00",
            "quantity": "10",
            "unit_cost": "125.00",
            "unit_of_measure": "ea",
            "status": "pending",
            "title": "Footing A",
            "number": "1",
            "budget_code": {
                "id": 555,
                "flat_code": "03-100",
                "segment_items": [{"id": 11, "name": "Concrete", "code": "03"}],
            },
            "vendor": {"id": 88, "name": "Acme Concrete LLC"},
            "disabled_fields": ["foo", "bar"],
        }
    ],
    "markup_items": [{"id": 2, "value": "50.00", "wbs_code": {"id": 9, "flat_code": "10-000"}}],
    "attachments": [{"id": 3, "name": "co.pdf", "url": "https://storage.example.com/co.pdf"}],
    "production_quantities": [{"id": 4, "quantity": "5"}],
}


def _inventory(payload: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    paths: dict[str, set[str]] = {}
    for path, typ in pp.iter_path_types(payload):
        paths.setdefault(path, set()).add(typ)
    return {ENDPOINT: {p: sorted(ts) for p, ts in paths.items()}}


def _install_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: dict[str, Any]
) -> None:
    """Build a registry from ``payload``'s inventory and point the loader at it."""
    doc = registry.build_registry(_inventory(payload))
    path = tmp_path / "reg.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(registry, "REGISTRY_PATH", path)
    registry.load_registry.cache_clear()


@pytest.fixture(autouse=True)
def _clear_registry_cache() -> Any:
    registry.load_registry.cache_clear()
    yield
    registry.load_registry.cache_clear()


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "proj.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    return db


def _project(
    db: Path, payload: dict[str, Any], *, source_quality: str = SOURCE_QUALITY_FIXTURE_FULL
) -> dict[str, Any]:
    scrubbed = scrub_transport_secrets(payload)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        receipt = eng.project_endpoint_specific(
            conn,
            endpoint_id=ENDPOINT,
            project_key="tropical",
            procore_project_id="99",
            record_id=str(payload["id"]),
            parent_record_id=None,
            payload=scrubbed,
            raw_payload_id="raw-1",
            payload_hash="hash-1",
            source_quality=source_quality,
            fetched_at="2026-01-03T00:00:00Z",
            now_utc="2026-01-03T00:00:00Z",
            mode=eng.MODE_ENFORCE,
        )
        conn.commit()
    finally:
        conn.close()
    return receipt


# --- Test 1: schema head + tables (committed registry) ----------------------------


def test_v47_schema_head_and_tables_present(tmp_path: Path) -> None:
    assert LATEST_SCHEMA_VERSION == 47
    db = tmp_path / "fresh.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == 47
    conn = sqlite3.connect(db)
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # every committed-registry table exists
    for table in registry.all_table_names():
        assert table in existing, table
    # V46 + V7 tables retained (additive, no regression)
    for table in (
        "procore_endpoint_raw_payloads",
        "procore_raw_change_events",
        "procore_inspection_items",
        "procore_inspection_sections",
    ):
        assert table in existing, table
    # zero-CHECK guards + sidecar on a representative primary table
    cols = {r[1] for r in conn.execute("PRAGMA table_info(procore_ep_change_events)")}
    for guard in (
        "external_writeback_performed",
        "raw_payload_emitted_to_read_model",
        "raw_payload_emitted_to_evidence",
        "payload_sidecar_json",
        "raw_payload_id",
    ):
        assert guard in cols, guard
    conn.close()


def test_committed_registry_loads_and_is_complete() -> None:
    plans = registry.load_registry()
    # Every endpoint with full raw payloads at registry-generation time is covered. The
    # seed change-events endpoint and the financial families must be present.
    assert len(plans) >= 36
    for required in ("change-events", "rfis", "submittals", "commitment-contracts", "subcontractor-invoices"):
        assert required in plans, required
    # table names are globally unique and all use the projection prefix.
    tables = registry.all_table_names()
    assert len(tables) == len(set(tables))
    assert all(t.startswith(registry.TABLE_PREFIX) for t in tables)
    # DDL builds and is non-trivial.
    ddl = registry.build_v47_ddl()
    assert sum(1 for s in ddl if s.startswith("CREATE TABLE")) == len(tables)


# --- Test 2: nested-array projection writes child rows + high-value columns --------


def test_nested_arrays_project_to_child_tables_with_high_value_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    receipt = _project(db, _CHANGE_EVENT)
    assert receipt["primary_rows"] == 1
    assert (
        receipt["child_rows"] >= 5
    )  # change_items, segment_items, markup_items, attachments, production_quantities

    plan = registry.plan_for(ENDPOINT)
    assert plan is not None
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    # primary high-value scalar + identity columns populated
    prow = conn.execute(f"SELECT * FROM {plan.primary_table}").fetchone()
    assert prow["number"] == "CE-7001"
    assert prow["status"] == "open"
    assert prow["company_id"] == "42"  # routed to standard column from payload
    assert prow["change_reason"] == "design_development"

    # change_items child table: money/quantity/cost-code/vendor are FIRST-CLASS columns
    ci_table = next(c.table for c in plan.child_tables if c.array_path == "$.change_items")
    crow = conn.execute(f"SELECT * FROM {ci_table}").fetchone()
    assert crow["amount"] == "1250.00"
    assert crow["unit_cost"] == "125.00"
    assert crow["quantity"] == "10"
    assert crow["item_id"] == "1"
    assert crow["budget_code_flat_code"] == "03-100"
    assert crow["vendor_name"] == "Acme Concrete LLC"

    # grandchild segment_items linked to its parent change_item
    seg_table = next(
        c.table for c in plan.child_tables if c.array_path.endswith("budget_code.segment_items")
    )
    seg = conn.execute(f"SELECT * FROM {seg_table}").fetchone()
    assert seg["parent_item_id"] == "1"
    assert seg["primary_record_key"] == prow["record_key"]
    conn.close()


def test_every_fixture_path_is_mapped_zero_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None
    scrubbed = scrub_transport_secrets(_CHANGE_EVENT)
    unknown = [
        p
        for p in pp.walk_paths(scrubbed)
        if p != pp.ROOT and p not in plan.known_paths and not pp.is_transport_secret(p)
    ]
    assert unknown == []


# --- Test 3: completeness gate fails closed on an unmapped business field ----------


def test_unknown_business_field_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Registry built WITHOUT the surprise field; payload then introduces it.
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    surprise = {**_CHANGE_EVENT, "brand_new_business_field": "value"}

    # enforce mode raises
    conn = sqlite3.connect(db)
    with pytest.raises(eng.UnknownProjectionPath):
        eng.project_endpoint_specific(
            conn,
            endpoint_id=ENDPOINT,
            project_key="tropical",
            procore_project_id="99",
            record_id="7001",
            parent_record_id=None,
            payload=scrub_transport_secrets(surprise),
            raw_payload_id="raw-1",
            payload_hash="h",
            source_quality=SOURCE_QUALITY_LIVE_FULL,
            fetched_at="2026-01-03T00:00:00Z",
            now_utc="2026-01-03T00:00:00Z",
            mode=eng.MODE_ENFORCE,
        )

    # live mode degrades (does not raise, does not write a partial projection)
    receipt = eng.project_endpoint_specific(
        conn,
        endpoint_id=ENDPOINT,
        project_key="tropical",
        procore_project_id="99",
        record_id="7001",
        parent_record_id=None,
        payload=scrub_transport_secrets(surprise),
        raw_payload_id="raw-1",
        payload_hash="h",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
        fetched_at="2026-01-03T00:00:00Z",
        now_utc="2026-01-03T00:00:00Z",
        mode=eng.MODE_LIVE,
    )
    conn.commit()
    assert receipt["ok"] is False
    assert receipt["state"] == "degraded_unknown_projection_fields"
    assert receipt["unknown_field_path_count"] >= 1
    assert receipt["primary_rows"] == 0
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None
    n = conn.execute(f"SELECT COUNT(*) FROM {plan.primary_table}").fetchone()[0]
    assert n == 0
    conn.close()


def test_live_upsert_degrades_but_persists_raw_on_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    surprise = {**_CHANGE_EVENT, "brand_new_business_field": "value"}
    receipt = upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id=ENDPOINT,
        project_key="tropical",
        procore_project_id="99",
        raw_item=surprise,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    # raw payload still persisted (nothing lost), endpoint-specific projection degraded
    assert receipt["raw_procore_payload_persisted"] == 1
    assert receipt["endpoint_specific"]["ok"] is False
    assert receipt["endpoint_specific"]["state"] == "degraded_unknown_projection_fields"


# --- Test 4: audit over a projected DB reports zero unmapped/unknown --------------


def test_projection_audit_clean_after_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    # persist a full raw payload so the audit (which reads the raw landing) has input
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id=ENDPOINT,
        project_key="tropical",
        procore_project_id="99",
        raw_item=_CHANGE_EVENT,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    result = audit.projection_audit(db_path=db)
    assert result["ok"] is True
    assert result["unmapped_primary_business_fields"] == 0
    assert result["unmapped_nested_business_fields"] == 0
    assert result["unknown_business_field_paths"] == 0


# --- Test 5: idempotent replay ----------------------------------------------------


def test_idempotent_replay_no_duplicate_child_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None

    _project(db, _CHANGE_EVENT)
    conn = sqlite3.connect(db)
    first = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in plan.all_tables()}
    conn.close()

    _project(db, _CHANGE_EVENT)  # replay
    conn = sqlite3.connect(db)
    second = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in plan.all_tables()}
    conn.close()
    assert first == second
    assert first[plan.primary_table] == 1


# --- Test 6: source-quality no-downgrade -----------------------------------------


def test_legacy_does_not_downgrade_full_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    db = _db(tmp_path)
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None

    # high-quality projection first
    _project(db, _CHANGE_EVENT, source_quality=SOURCE_QUALITY_LIVE_FULL)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    before = conn.execute(f"SELECT source_quality FROM {plan.primary_table}").fetchone()[
        "source_quality"
    ]
    conn.close()
    assert before == SOURCE_QUALITY_LIVE_FULL

    # a lower-rank legacy replay must be skipped, not overwrite
    receipt = _project(db, _CHANGE_EVENT, source_quality=SOURCE_QUALITY_LEGACY)
    assert receipt["endpoint_specific_projection_status"] == "skipped_higher_quality"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    after = conn.execute(f"SELECT source_quality FROM {plan.primary_table}").fetchone()[
        "source_quality"
    ]
    conn.close()
    assert after == SOURCE_QUALITY_LIVE_FULL


# --- Test 7: no raw/transport-secret leak; guard columns enforce ------------------


def test_transport_secret_never_reaches_column_or_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_registry(monkeypatch, tmp_path, _CHANGE_EVENT)
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None

    # registry marks the auth secret excluded and never as a column
    secret_entries = [
        e
        for e in json.loads(registry.REGISTRY_PATH.read_text())["endpoints"][ENDPOINT]["path_map"]
        if "access_token" in e["path"]
    ]
    assert secret_entries and all(e["dest"].startswith("exclude:") for e in secret_entries)
    assert all("access_token" not in col for _, col in plan.primary_columns)

    db = _db(tmp_path)
    _project(db, _CHANGE_EVENT)  # _project scrubs transport secrets first, as production does
    conn = sqlite3.connect(db)
    for table in plan.all_tables():
        for row in conn.execute(f"SELECT * FROM {table}"):
            assert "SECRET-bearer-value" not in json.dumps(list(row), default=str)
    # guard column rejects a writeback flag
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"UPDATE {plan.primary_table} SET external_writeback_performed = 1")
    conn.close()


def test_no_leak_scan_passes_on_committed_registry() -> None:
    from hb_assistant.procore.structured_analytics import no_raw_leak_scan

    result = no_raw_leak_scan([str(registry.REGISTRY_PATH)])
    assert result["ok"] is True, result["findings"]
