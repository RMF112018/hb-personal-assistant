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
from scripts.proofs import procore_null_projection_audit as null_projection_audit

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
            "cost_impact": {
                "contract": {
                    "confirmed": {
                        "id": 991,
                        "number": "CCO-991",
                        "status": "approved",
                        "title": "Confirmed contract cost",
                    }
                },
                "vendor": {
                    "confirmed": {
                        "id": 88,
                        "name": "Acme Concrete LLC",
                    }
                },
            },
            "disabled_fields": ["foo", "bar"],
        }
    ],
    "markup_items": [{"id": 2, "value": "50.00", "wbs_code": {"id": 9, "flat_code": "10-000"}}],
    "attachments": [{"id": 3, "name": "co.pdf", "url": "https://storage.example.com/co.pdf"}],
    "production_quantities": [{"id": 4, "quantity": "5"}],
}


def _change_event_with_budget_modification() -> dict[str, Any]:
    return {
        "id": 7002,
        "number": "CE-7002",
        "company_id": 42,
        "project_id": 99,
        "status": {"id": 1, "name": "Open", "mapped_to_status": "open"},
        "change_reason": {"id": 2, "change_reason": "Owner Request"},
        "change_type": {"id": 3, "name": "Budget Transfer", "abbreviation": "BT"},
        "scope": "in_scope",
        "title": "Budget transfer",
        "description": "Transfer budget impact",
        "created_at": "2026-01-02T00:00:00Z",
        "updated_at": "2026-01-03T00:00:00Z",
        "currency_configuration": {"currency_iso_code": "USD"},
        "custom_fields": {},
        "change_items": [
            {
                "id": 1,
                "event_id": 7002,
                "event_number": "CE-7002",
                "event_title": "Budget transfer",
                "item_type": "change_event_line_item",
                "description": "Budget modification line",
                "created_at": "2026-01-02T00:00:00Z",
                "updated_at": "2026-01-03T00:00:00Z",
                "budget_code": {
                    "id": 555,
                    "flat_code": "03-100",
                    "description": "Concrete",
                    "segment_items": [
                        {
                            "id": 11,
                            "name": "Concrete",
                            "code": "03",
                            "path_ids": [11],
                            "path_codes": ["03"],
                            "segment": {"id": 4, "name": "Cost Code", "type": "cost_code"},
                        }
                    ],
                },
                "budget_impact": {
                    "budget_change": None,
                    "budget_modification": {
                        "amount": "2500.00",
                        "budget_modification_id": 99001,
                        "notes": "Transfer budget to material line",
                        "transfer_from": {"id": 301, "name": "Contingency"},
                        "transfer_to": {"id": 302, "name": "Materials"},
                    },
                    "source_of_latest_budget_impact": "budget_modification",
                    "source_of_stage": "approved",
                },
            }
        ],
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
    assert LATEST_SCHEMA_VERSION >= 49  # V47 tables + V48 reconciliation + later additive heads
    db = tmp_path / "fresh.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
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


def test_committed_change_events_budget_modification_paths_project(
    tmp_path: Path,
) -> None:
    payload = _change_event_with_budget_modification()
    db = _db(tmp_path)
    plan = registry.plan_for(ENDPOINT)
    assert plan is not None

    receipt = _project(db, payload, source_quality=SOURCE_QUALITY_LIVE_FULL)
    assert receipt["ok"] is True
    assert receipt["endpoint_specific_projection_status"] == "ok"

    ci_table = next(c.table for c in plan.child_tables if c.array_path == "$.change_items")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    crow = conn.execute(f"SELECT * FROM {ci_table} WHERE item_id = '1'").fetchone()
    conn.close()

    assert crow["budget_impact_budget_modification_amount"] == "2500.00"
    assert crow["budget_impact_budget_modification_budget_modification_id"] == "99001"
    assert crow["budget_impact_budget_modification_notes"] == "Transfer budget to material line"
    assert crow["budget_impact_budget_modification_transfer_from_id"] == "301"
    assert crow["budget_impact_budget_modification_transfer_from_name"] == "Contingency"
    assert crow["budget_impact_budget_modification_transfer_to_id"] == "302"
    assert crow["budget_impact_budget_modification_transfer_to_name"] == "Materials"


def test_committed_change_events_budget_modification_audit_clean(tmp_path: Path) -> None:
    payload = _change_event_with_budget_modification()
    db = _db(tmp_path)
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id=ENDPOINT,
        project_key="tropical",
        procore_project_id="99",
        raw_item=payload,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    result = audit.projection_audit(db_path=db, endpoint=ENDPOINT)
    assert result["ok"] is True
    assert result["unknown_business_field_paths"] == 0
    assert result["runtime_plan_schema_mismatches"] == 0


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


def test_committed_change_event_cost_impact_confirmed_objects_project(
    tmp_path: Path,
) -> None:
    payload = {
        "id": 7010,
        "change_items": [
            {
                "id": 1,
                "cost_impact": {
                    "contract": {
                        "confirmed": {
                            "id": 991,
                            "number": "CCO-991",
                            "status": "approved",
                            "title": "Confirmed contract cost",
                        }
                    },
                    "vendor": {
                        "confirmed": {
                            "id": 88,
                            "name": "Acme Concrete LLC",
                        }
                    },
                },
            }
        ],
    }
    db = _db(tmp_path)
    receipt = _project(db, payload, source_quality=SOURCE_QUALITY_LIVE_FULL)
    assert receipt["ok"] is True
    assert receipt["endpoint_specific_projection_status"] == "ok"

    plan = registry.plan_for(ENDPOINT)
    assert plan is not None
    ci_table = next(c.table for c in plan.child_tables if c.array_path == "$.change_items")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT * FROM {ci_table} WHERE item_id = '1'").fetchone()
        assert row["cost_impact_contract_confirmed"] == "Confirmed contract cost"
        assert row["cost_impact_vendor_confirmed"] == "Acme Concrete LLC"
    finally:
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


# --- Hotfix: runtime plan/schema parity (V48) -------------------------------------

_DROP_COLUMN_OK = sqlite3.sqlite_version_info >= (3, 35, 0)


def test_object_null_container_is_not_promoted_to_column() -> None:
    """A field that is an object in some payloads and null in others (object|null) must be
    a structural container, never a literal column, while its scalar children stay columns
    (the architect / submittal_package defect)."""
    inv = {
        "prime-contracts": {
            "$": ["object"],
            "$.id": ["integer"],
            "$.architect": ["object", "null"],  # object|null container
            "$.architect.id": ["integer"],
            "$.architect.login": ["string"],
            "$.architect.name": ["string"],
        }
    }
    doc = registry.build_registry(inv)
    ep = doc["endpoints"]["prime-contracts"]
    cols = {c["column"] for c in ep["primary_columns"]}
    assert "architect" not in cols  # container NOT a column
    assert {"architect_id", "architect_login", "architect_name"} <= cols  # children kept
    dest = {e["path"]: e["dest"] for e in ep["path_map"]}
    assert dest["$.architect"] == "structural"


def test_committed_registry_has_no_object_container_columns() -> None:
    """No primary/child column may be a bare object container (regression guard for the
    architect/submittal_package/submittal_workflow_template promotion bug)."""
    plans = registry.load_registry()
    pc = plans["prime-contracts"]
    pcols = {c for _, c in pc.primary_columns}
    assert "architect" not in pcols
    assert {"architect_id", "architect_login", "architect_name"} <= pcols
    sm = plans["submittals"]
    scols = {c for _, c in sm.primary_columns}
    assert "submittal_package" not in scols
    assert "submittal_workflow_template" not in scols
    assert any(c.startswith("submittal_package_") for c in scols)


def test_runtime_plan_schema_mismatches_zero_after_migrate(tmp_path: Path) -> None:
    db = _db(tmp_path)  # migrates the committed registry to head (48)
    conn = sqlite3.connect(db)
    try:
        assert audit.plan_schema_mismatches(conn) == []
    finally:
        conn.close()


@pytest.mark.skipif(not _DROP_COLUMN_OK, reason="sqlite < 3.35 has no ALTER TABLE DROP COLUMN")
def test_v48_reconciles_missing_column_even_at_head(tmp_path: Path) -> None:
    """Proves the V48 reconciliation runs UNCONDITIONALLY: a DB already at head with a
    dropped registry column is reconciled by a re-run of apply()."""
    db = _db(tmp_path)
    assert SQLiteMigrator(db_path=str(db)).current_version() == LATEST_SCHEMA_VERSION
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE procore_ep_prime_contracts DROP COLUMN architect_id")
    conn.commit()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(procore_ep_prime_contracts)")}
    conn.close()
    assert "architect_id" not in cols  # drift created at head
    # re-apply at head -> reconciliation re-adds the column
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    conn = sqlite3.connect(db)
    healed = {r[1] for r in conn.execute("PRAGMA table_info(procore_ep_prime_contracts)")}
    conn.close()
    assert "architect_id" in healed


@pytest.mark.skipif(not _DROP_COLUMN_OK, reason="sqlite < 3.35 has no ALTER TABLE DROP COLUMN")
def test_schema_drift_fails_audit_and_reprocess_guards(tmp_path: Path) -> None:
    """A missing planned insert column makes schema audit ok=false and makes
    projection-reprocess --apply fail closed with schema_parity_broken — never
    sqlite3.OperationalError."""
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("ALTER TABLE procore_ep_prime_contracts DROP COLUMN architect_id")
    conn.commit()
    conn.close()

    schema_res = audit.projection_schema_audit(db_path=db)
    assert schema_res["ok"] is False
    assert schema_res["runtime_plan_schema_mismatches"] >= 1

    # engine apply guard returns a structured receipt, does not raise OperationalError
    receipt = eng.backfill_endpoint_specific_from_raw_payloads(
        db_path=db, apply=True, mode=eng.MODE_ENFORCE
    )
    assert receipt["ok"] is False
    assert receipt["status"] == "schema_parity_broken"
    assert receipt["primary_rows_written"] == 0
    assert receipt["external_writeback_performed"] == 0


def test_reprocess_apply_succeeds_after_reconcile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: a payload with an object|null container projects without
    OperationalError after migrate (reconcile)."""
    payload = {**_CHANGE_EVENT, "architect": None}  # object|null at top level
    _install_registry(monkeypatch, tmp_path, payload)
    db = _db(tmp_path)
    # persist a full raw payload, then reprocess --apply (enforce); must not raise
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id=ENDPOINT,
        project_key="tropical",
        procore_project_id="99",
        raw_item=payload,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    receipt = eng.backfill_endpoint_specific_from_raw_payloads(
        db_path=db, apply=True, mode=eng.MODE_ENFORCE
    )
    assert receipt["ok"] is True
    assert receipt["primary_rows_written"] >= 1
    assert audit.projection_schema_audit(db_path=db)["ok"] is True


def test_batch1_punch_closed_fields_project_from_current_payload_shapes(tmp_path: Path) -> None:
    """Batch 1 regression: current punch payloads expose closed_by as an object and
    assignment attachment item fields. These paths must be allow-listed without adding
    columns, and closed_at / closed_by must project into the existing columns."""
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    payload = {
        "id": 123,
        "closed_at": "2026-06-01T12:00:00Z",
        "closed_by": {
            "id": 456,
            "login": "reviewer@example.invalid",
            "name": "Owner Reviewer",
            "company_name": "Example Company",
            "locale": None,
        },
        "assignments": [
            {
                "id": 1,
                "approved": True,
                "attachments": [
                    {
                        "id": 2,
                        "filename": "redacted.pdf",
                        "url": "https://storage.example.invalid/redacted.pdf",
                    }
                ],
            }
        ],
    }
    try:
        receipt = eng.project_endpoint_specific(
            conn,
            endpoint_id="punch-items",
            project_key="tropical",
            procore_project_id="99",
            record_id="123",
            parent_record_id=None,
            payload=payload,
            raw_payload_id="raw-punch-batch1",
            payload_hash="hash-punch-batch1",
            source_quality=SOURCE_QUALITY_LIVE_FULL,
            fetched_at="2026-06-01T12:00:00Z",
            now_utc="2026-06-01T12:01:00Z",
            mode=eng.MODE_ENFORCE,
        )
        row = conn.execute(
            "SELECT closed_at, closed_by FROM procore_ep_punch_items WHERE record_id = '123'"
        ).fetchone()
    finally:
        conn.close()

    assert receipt["ok"] is True
    assert row["closed_at"] == "2026-06-01T12:00:00Z"
    assert row["closed_by"] == "Owner Reviewer"


def test_batch1_prime_contract_boolean_projects_with_attachment_sidecar_paths(
    tmp_path: Path,
) -> None:
    """Batch 1 regression: current prime-contract payloads include top-level
    attachment item fields and a boolean show_line_items_to_non_admins value."""
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    payload = {
        "id": 321,
        "show_line_items_to_non_admins": True,
        "attachments": [
            {
                "id": 654,
                "filename": "redacted.pdf",
                "name": "Redacted",
                "url": "https://storage.example.invalid/redacted.pdf",
            }
        ],
    }
    try:
        receipt = eng.project_endpoint_specific(
            conn,
            endpoint_id="prime-contracts",
            project_key="tropical",
            procore_project_id="99",
            record_id="321",
            parent_record_id=None,
            payload=payload,
            raw_payload_id="raw-prime-batch1",
            payload_hash="hash-prime-batch1",
            source_quality=SOURCE_QUALITY_LIVE_FULL,
            fetched_at="2026-06-01T12:00:00Z",
            now_utc="2026-06-01T12:01:00Z",
            mode=eng.MODE_ENFORCE,
        )
        row = conn.execute(
            "SELECT show_line_items_to_non_admins FROM procore_ep_prime_contracts "
            "WHERE record_id = '321'"
        ).fetchone()
    finally:
        conn.close()

    assert receipt["ok"] is True
    assert row["show_line_items_to_non_admins"] == "True"


def test_patch1_commitment_change_order_scalar_reference_fields_project(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    payload = {
        "id": 9001,
        "change_order_change_reason": {"id": 11, "change_reason": "Owner Request"},
        "designated_reviewer": {"id": 22, "name": "Design Reviewer"},
        "received_from": {"id": 33, "name": "Prime Contractor"},
        "reviewed_by": {"id": 44, "name": "Project Executive"},
    }
    try:
        receipt = eng.project_endpoint_specific(
            conn,
            endpoint_id="commitment-change-orders",
            project_key="tropical",
            procore_project_id="99",
            record_id="9001",
            parent_record_id=None,
            payload=payload,
            raw_payload_id="raw-commitment-co-patch1",
            payload_hash="hash-commitment-co-patch1",
            source_quality=SOURCE_QUALITY_LIVE_FULL,
            fetched_at="2026-06-19T00:00:00Z",
            now_utc="2026-06-19T00:01:00Z",
            mode=eng.MODE_ENFORCE,
        )
        row = conn.execute(
            """
            SELECT
              change_order_change_reason_id,
              change_order_change_reason_change_reason,
              designated_reviewer_id,
              designated_reviewer_name,
              received_from_id,
              received_from_name,
              reviewed_by_id,
              reviewed_by_name,
              company_id
            FROM procore_ep_commitment_change_orders
            WHERE record_id = '9001'
            """
        ).fetchone()
        table_columns = {
            column["name"]
            for column in conn.execute(
                "PRAGMA table_info(procore_ep_commitment_change_orders)"
            ).fetchall()
        }
        bare_object_values = {}
        for column in (
            "change_order_change_reason",
            "designated_reviewer",
            "received_from",
            "reviewed_by",
        ):
            if column in table_columns:
                bare_object_values[column] = conn.execute(
                    f"SELECT {column} FROM procore_ep_commitment_change_orders "  # noqa: S608
                    "WHERE record_id = '9001'"
                ).fetchone()[0]
    finally:
        conn.close()

    assert receipt["ok"] is True
    assert row["change_order_change_reason_id"] == "11"
    assert row["change_order_change_reason_change_reason"] == "Owner Request"
    assert row["designated_reviewer_id"] == "22"
    assert row["designated_reviewer_name"] == "Design Reviewer"
    assert row["received_from_id"] == "33"
    assert row["received_from_name"] == "Prime Contractor"
    assert row["reviewed_by_id"] == "44"
    assert row["reviewed_by_name"] == "Project Executive"
    assert all(value is None for value in bare_object_values.values())
    assert row["company_id"] is None

    payload_after_audit = null_projection_audit.audit_database(db)
    by_field = {
        (record["table"], record["column"]): record
        for record in payload_after_audit["columns"]
    }
    for column in (
        "change_order_change_reason_id",
        "change_order_change_reason_change_reason",
        "designated_reviewer_id",
        "designated_reviewer_name",
        "received_from_id",
        "received_from_name",
        "reviewed_by_id",
        "reviewed_by_name",
    ):
        assert (
            by_field[("procore_ep_commitment_change_orders", column)][
                "suspected_projection_defect"
            ]
            is False
        )


def test_patch1_prime_change_order_scalar_reference_fields_project(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    payload = {
        "id": 9101,
        "change_order_change_reason": {"id": 55, "change_reason": "Scope Change"},
        "designated_reviewer": {"id": 66, "name": "Owner Reviewer"},
        "received_from": {"id": 77, "name": "Architect"},
    }
    try:
        receipt = eng.project_endpoint_specific(
            conn,
            endpoint_id="prime-change-orders",
            project_key="tropical",
            procore_project_id="99",
            record_id="9101",
            parent_record_id=None,
            payload=payload,
            raw_payload_id="raw-prime-co-patch1",
            payload_hash="hash-prime-co-patch1",
            source_quality=SOURCE_QUALITY_LIVE_FULL,
            fetched_at="2026-06-19T00:00:00Z",
            now_utc="2026-06-19T00:01:00Z",
            mode=eng.MODE_ENFORCE,
        )
        row = conn.execute(
            """
            SELECT
              change_order_change_reason_id,
              change_order_change_reason_change_reason,
              designated_reviewer_id,
              designated_reviewer_name,
              received_from_id,
              received_from_name,
              company_id
            FROM procore_ep_prime_change_orders
            WHERE record_id = '9101'
            """
        ).fetchone()
        table_columns = {
            column["name"]
            for column in conn.execute(
                "PRAGMA table_info(procore_ep_prime_change_orders)"
            ).fetchall()
        }
        bare_object_values = {}
        for column in (
            "change_order_change_reason",
            "designated_reviewer",
            "received_from",
        ):
            if column in table_columns:
                bare_object_values[column] = conn.execute(
                    f"SELECT {column} FROM procore_ep_prime_change_orders "  # noqa: S608
                    "WHERE record_id = '9101'"
                ).fetchone()[0]
    finally:
        conn.close()

    assert receipt["ok"] is True
    assert row["change_order_change_reason_id"] == "55"
    assert row["change_order_change_reason_change_reason"] == "Scope Change"
    assert row["designated_reviewer_id"] == "66"
    assert row["designated_reviewer_name"] == "Owner Reviewer"
    assert row["received_from_id"] == "77"
    assert row["received_from_name"] == "Architect"
    assert all(value is None for value in bare_object_values.values())
    assert row["company_id"] is None

    payload_after_audit = null_projection_audit.audit_database(db)
    by_field = {
        (record["table"], record["column"]): record
        for record in payload_after_audit["columns"]
    }
    for column in (
        "change_order_change_reason_id",
        "change_order_change_reason_change_reason",
        "designated_reviewer_id",
        "designated_reviewer_name",
        "received_from_id",
        "received_from_name",
    ):
        assert (
            by_field[("procore_ep_prime_change_orders", column)]["suspected_projection_defect"]
            is False
        )
