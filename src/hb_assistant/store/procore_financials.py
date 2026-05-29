"""Phase 05 Procore financial projection repository.

Store-layer upsert + read primitives for the V8 financial tables (contracts,
line items, change orders + their line items, payment applications, subcontractor
invoice items, RFQs, change events, budget views/rows/changes, compliance
documents, and cross-object amount facts).

Posture (carries the Phase 04B contract):
- **Amounts are preserved verbatim as decimal-safe TEXT** — callers pass money
  values as ``str`` and they are stored byte-for-byte. Nothing here ever calls
  ``float()`` on an amount (TEXT affinity would otherwise re-format a float and
  silently lose precision). High-precision and negative decimal strings survive
  a round-trip unchanged.
- **Redaction is enforced at this boundary** (defense-in-depth on top of the
  normalizers): ``*_redacted`` text columns are masked + truncated via
  ``_redact_excerpt`` (no emails / phones / URLs / signed-URL tokens),
  ``description_summary_json`` columns store a hash + length + masked excerpt
  only, and ``attachment_path_redacted`` keeps the URL path only. Every row sets
  ``raw_body_persisted = 0`` and (where present) ``redaction_applied = 1`` to
  satisfy the table CHECK constraints — no raw payload bodies ever persist.
- Every key is caller-supplied and deterministic and every write is a
  conflict-upsert on the primary key, so re-projecting the same record records
  no duplicates (idempotent).

Self-contained: no import from ``hb_assistant.procore`` (store-layer
independence, mirroring ``procore_history.py`` / ``procore_enrichment.py``). No
live-sync wiring here — the dispatch that calls these functions lands in a later
prompt.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

from .connection import get_connection, transaction


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def _hash(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join("" if p is None else str(p) for p in parts).encode("utf-8")
    ).hexdigest()[:32]


def _hash12(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value):
        return None
    if not isinstance(value, str):
        value = json.dumps(value, default=str, sort_keys=True)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _url_path(value: Any) -> Optional[str]:
    """Return the path component only — never scheme/host/query (drops signed-URL tokens)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return urlparse(value).path or None
    except ValueError:
        return None


_EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){7,}\d")
_URL_RE = re.compile(r"https?://\S+")


def _redact_excerpt(value: Any, max_chars: int = 200) -> Optional[str]:
    """Mask emails / phones / URLs, collapse whitespace, truncate."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if not text:
        return None
    masked = _URL_RE.sub("[url]", text)
    masked = _EMAIL_RE.sub("[email]", masked)
    masked = _PHONE_RE.sub("[phone]", masked)
    masked = re.sub(r"\s+", " ", masked).strip()
    if not masked:
        return None
    return masked[:max_chars]


def _text_summary(value: Any) -> Optional[str]:
    """Free text / structured notes -> JSON {hash, len, excerpt} — no raw body."""
    if value is None:
        return None
    raw = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    if not raw:
        return None
    return json.dumps(
        {"hash": _hash12(raw), "len": len(raw), "excerpt": _redact_excerpt(raw, 120)},
        sort_keys=True,
    )


# Columns whose values must be reduced before persisting (enforced regardless of
# whether the caller already redacted). Everything else (amounts, ids, statuses,
# dates, booleans) is stored verbatim.
_EXCERPT_COLUMNS = frozenset(
    {"title_redacted", "name_redacted", "wbs_description_redacted", "notes_summary_redacted"}
)
_SUMMARY_JSON_COLUMNS = frozenset({"description_summary_json"})
_URL_PATH_COLUMNS = frozenset({"attachment_path_redacted"})


def _redact_field(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in _EXCERPT_COLUMNS:
        return _redact_excerpt(value, 200)
    if column in _SUMMARY_JSON_COLUMNS:
        return _text_summary(value)
    if column in _URL_PATH_COLUMNS:
        return _url_path(value)
    return value


# Allowed column whitelist per table (excludes the two redaction-guard columns,
# which this module always sets). Unknown keys fail closed.
_COLUMNS: Dict[str, frozenset] = {
    "procore_financial_contracts": frozenset(
        {
            "record_key", "project_key", "endpoint_id", "contract_id", "contract_family",
            "contract_type", "number", "title_redacted", "status", "executed", "private",
            "accounting_method", "vendor_entity_key", "company_entity_key", "grand_total",
            "original_contract_sum", "revised_contract_sum", "approved_change_orders_amount",
            "pending_change_orders_amount", "retainage_percent", "currency_iso_code",
            "base_currency_iso_code", "currency_exchange_rate", "contract_date", "start_date",
            "completion_date", "updated_at_utc", "last_sync_run_id",
        }
    ),
    "procore_financial_line_items": frozenset(
        {
            "line_item_key", "project_key", "parent_record_key", "endpoint_id", "line_item_id",
            "line_item_kind", "description_summary_json", "wbs_code_id", "wbs_flat_code",
            "wbs_description_redacted", "cost_code_id", "line_item_type_id", "tax_code_id",
            "quantity", "uom", "unit_cost", "amount", "scheduled_value", "billed_to_date",
            "work_completed_this_period", "materials_presently_stored", "retainage_held",
            "position", "currency_iso_code",
        }
    ),
    "procore_financial_change_orders": frozenset(
        {
            "record_key", "project_key", "endpoint_id", "change_order_id", "change_order_family",
            "contract_record_key", "contract_id", "number", "title_redacted", "status",
            "executed", "paid", "private", "field_change", "signature_required", "grand_total",
            "schedule_impact_amount", "due_date", "invoiced_date", "paid_date", "reviewed_at_utc",
            "updated_at_utc",
        }
    ),
    "procore_financial_payment_applications": frozenset(
        {
            "record_key", "project_key", "endpoint_id", "payment_application_id",
            "contract_record_key", "prime_contract_id", "billing_period_id", "invoice_number",
            "number", "status", "billing_date", "period_start", "period_end", "percent_complete",
            "current_payment_due", "total_amount_paid", "total_retainage",
            "balance_to_finish_including_retainage", "contract_sum_to_date", "updated_at_utc",
        }
    ),
    "procore_financial_invoice_items": frozenset(
        {
            "invoice_item_key", "project_key", "endpoint_id", "invoice_record_key",
            "requisition_id", "item_id", "item_type", "line_item_id", "cost_code_id",
            "wbs_flat_code", "description_summary_json", "scheduled_value",
            "work_completed_this_period", "materials_presently_stored",
            "total_completed_and_stored_to_date", "retainage_held", "subcontractor_claimed_amount",
            "status", "position",
        }
    ),
    "procore_financial_rfqs": frozenset(
        {
            "record_key", "project_key", "endpoint_id", "rfq_id", "commitment_contract_id",
            "number", "title_redacted", "status", "private", "due_date", "estimated_amount",
            "estimated_schedule_impact", "estimated_status", "intent_to_quote", "original_quote",
            "updated_at_utc",
        }
    ),
    "procore_financial_change_events": frozenset(
        {
            "record_key", "project_key", "endpoint_id", "change_event_id", "number",
            "title_redacted", "status", "scope", "estimated_cost", "estimated_revenue",
            "schedule_impact_amount", "owner_cost_amount", "commitment_cost_amount",
            "updated_at_utc",
        }
    ),
    "procore_financial_budget_views": frozenset(
        {
            "budget_view_key", "project_key", "budget_view_id", "name_redacted",
            "description_summary_json", "updated_at_utc",
        }
    ),
    "procore_financial_budget_rows": frozenset(
        {
            "budget_row_key", "project_key", "budget_view_key", "endpoint_id", "row_id",
            "wbs_code_id", "wbs_flat_code", "cost_code_id", "line_item_type_id",
            "column_values_json_redacted",
        }
    ),
    "procore_financial_change_order_line_items": frozenset(
        {
            "line_item_key", "project_key", "change_order_record_key", "endpoint_id",
            "line_item_id", "change_order_family", "description_summary_json", "wbs_code_id",
            "wbs_flat_code", "cost_code_id", "line_item_type_id", "quantity", "uom", "unit_cost",
            "amount", "position", "currency_iso_code",
        }
    ),
    "procore_financial_budget_changes": frozenset(
        {
            "budget_change_key", "project_key", "endpoint_id", "budget_change_kind",
            "budget_change_id", "budget_view_key", "parent_change_key", "number", "status",
            "title_redacted", "wbs_code_id", "wbs_flat_code", "cost_code_id", "adjustment_amount",
            "from_amount", "to_amount", "approved_at_utc", "updated_at_utc",
        }
    ),
    "procore_financial_compliance_documents": frozenset(
        {
            "compliance_key", "project_key", "contract_record_key", "endpoint_id",
            "compliance_id", "document_type", "status", "compliant", "effective_date",
            "expiration_date", "attachment_path_redacted", "notes_summary_redacted",
            "updated_at_utc",
        }
    ),
    "procore_financial_amount_facts": frozenset(
        {
            "amount_fact_id", "project_key", "record_key", "endpoint_id", "amount_name",
            "amount_value", "currency_iso_code", "base_currency_iso_code", "period_start",
            "period_end", "wbs_code_id", "cost_code_id", "source_field_path", "created_at_utc",
        }
    ),
}

# Tables that carry the redaction_applied guard column (amount_facts does not).
_HAS_REDACTION_APPLIED = frozenset(t for t in _COLUMNS if t != "procore_financial_amount_facts")


def _persist(
    table: str,
    pk: str,
    row: Mapping[str, Any],
    *,
    db_path: Optional[Path],
) -> None:
    allowed = _COLUMNS[table]
    unknown = set(row) - allowed
    if unknown:
        raise ValueError(f"{table}: unknown columns {sorted(unknown)}")
    # Build the persisted row: redact recognised sensitive columns, set guards.
    persisted: Dict[str, Any] = {col: _redact_field(col, val) for col, val in row.items()}
    persisted["raw_body_persisted"] = 0
    if table in _HAS_REDACTION_APPLIED:
        persisted["redaction_applied"] = 1
    cols = list(persisted.keys())
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c != pk)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({pk}) DO UPDATE SET {updates}"
    )
    conn = _open(db_path)
    with transaction(conn):
        conn.execute(sql, tuple(persisted[c] for c in cols))


# ---------------------------------------------------------------------------
# Upserts — one per projection table. ``fields`` carries the optional columns
# (actual column names); required NOT NULL columns are explicit kwargs.
# ---------------------------------------------------------------------------


def upsert_financial_contract(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    contract_id: str,
    contract_family: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        contract_id=str(contract_id),
        contract_family=contract_family,
    )
    _persist("procore_financial_contracts", "record_key", row, db_path=db_path)
    return record_key


def upsert_financial_line_item(
    *,
    line_item_key: str,
    project_key: str,
    parent_record_key: str,
    endpoint_id: str,
    line_item_id: str,
    line_item_kind: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        line_item_key=line_item_key,
        project_key=project_key,
        parent_record_key=parent_record_key,
        endpoint_id=endpoint_id,
        line_item_id=str(line_item_id),
        line_item_kind=line_item_kind,
    )
    _persist("procore_financial_line_items", "line_item_key", row, db_path=db_path)
    return line_item_key


def upsert_financial_change_order(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    change_order_id: str,
    change_order_family: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        change_order_id=str(change_order_id),
        change_order_family=change_order_family,
    )
    _persist("procore_financial_change_orders", "record_key", row, db_path=db_path)
    return record_key


def upsert_financial_change_order_line_item(
    *,
    line_item_key: str,
    project_key: str,
    change_order_record_key: str,
    endpoint_id: str,
    line_item_id: str,
    change_order_family: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        line_item_key=line_item_key,
        project_key=project_key,
        change_order_record_key=change_order_record_key,
        endpoint_id=endpoint_id,
        line_item_id=str(line_item_id),
        change_order_family=change_order_family,
    )
    _persist(
        "procore_financial_change_order_line_items", "line_item_key", row, db_path=db_path
    )
    return line_item_key


def upsert_financial_payment_application(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    payment_application_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        payment_application_id=str(payment_application_id),
    )
    _persist("procore_financial_payment_applications", "record_key", row, db_path=db_path)
    return record_key


def upsert_financial_invoice_item(
    *,
    invoice_item_key: str,
    project_key: str,
    endpoint_id: str,
    item_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        invoice_item_key=invoice_item_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        item_id=str(item_id),
    )
    _persist("procore_financial_invoice_items", "invoice_item_key", row, db_path=db_path)
    return invoice_item_key


def upsert_financial_rfq(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    rfq_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        rfq_id=str(rfq_id),
    )
    _persist("procore_financial_rfqs", "record_key", row, db_path=db_path)
    return record_key


def upsert_financial_change_event(
    *,
    record_key: str,
    project_key: str,
    endpoint_id: str,
    change_event_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        record_key=record_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        change_event_id=str(change_event_id),
    )
    _persist("procore_financial_change_events", "record_key", row, db_path=db_path)
    return record_key


def upsert_financial_budget_view(
    *,
    budget_view_key: str,
    project_key: str,
    budget_view_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        budget_view_key=budget_view_key,
        project_key=project_key,
        budget_view_id=str(budget_view_id),
    )
    _persist("procore_financial_budget_views", "budget_view_key", row, db_path=db_path)
    return budget_view_key


def upsert_financial_budget_row(
    *,
    budget_row_key: str,
    project_key: str,
    endpoint_id: str,
    row_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        budget_row_key=budget_row_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        row_id=str(row_id),
    )
    _persist("procore_financial_budget_rows", "budget_row_key", row, db_path=db_path)
    return budget_row_key


def upsert_financial_budget_change(
    *,
    budget_change_key: str,
    project_key: str,
    endpoint_id: str,
    budget_change_kind: str,
    budget_change_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        budget_change_key=budget_change_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        budget_change_kind=budget_change_kind,
        budget_change_id=str(budget_change_id),
    )
    _persist("procore_financial_budget_changes", "budget_change_key", row, db_path=db_path)
    return budget_change_key


def upsert_financial_compliance_document(
    *,
    compliance_key: str,
    project_key: str,
    endpoint_id: str,
    compliance_id: str,
    fields: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> str:
    row: Dict[str, Any] = dict(fields or {})
    row.update(
        compliance_key=compliance_key,
        project_key=project_key,
        endpoint_id=endpoint_id,
        compliance_id=str(compliance_id),
    )
    _persist(
        "procore_financial_compliance_documents", "compliance_key", row, db_path=db_path
    )
    return compliance_key


def emit_financial_amount_fact(
    *,
    project_key: str,
    record_key: str,
    endpoint_id: str,
    amount_name: str,
    amount_value: str,
    source_field_path: str,
    created_at_utc: str,
    currency_iso_code: Optional[str] = None,
    base_currency_iso_code: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    wbs_code_id: Optional[str] = None,
    cost_code_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    """Emit one cross-object amount fact. ``amount_value`` is stored verbatim as
    TEXT (decimal-safe). The id is deterministic so re-emitting is a no-op."""
    amount_fact_id = _hash(
        project_key, record_key, amount_name, period_start, period_end, wbs_code_id
    )
    row: Dict[str, Any] = {
        "amount_fact_id": amount_fact_id,
        "project_key": project_key,
        "record_key": record_key,
        "endpoint_id": endpoint_id,
        "amount_name": amount_name,
        "amount_value": amount_value,
        "source_field_path": source_field_path,
        "created_at_utc": created_at_utc,
        "currency_iso_code": currency_iso_code,
        "base_currency_iso_code": base_currency_iso_code,
        "period_start": period_start,
        "period_end": period_end,
        "wbs_code_id": wbs_code_id,
        "cost_code_id": cost_code_id,
    }
    _persist("procore_financial_amount_facts", "amount_fact_id", row, db_path=db_path)
    return amount_fact_id


# ---------------------------------------------------------------------------
# Read views (deterministic; ordered).
# ---------------------------------------------------------------------------


def _rows(conn: sqlite3.Connection, sql: str, params: tuple) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def read_financial_contract_summary(
    *, project_key: str, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    conn = _open(db_path)
    return _rows(
        conn,
        """
        SELECT record_key, contract_family, contract_id, number, status, executed,
               original_contract_sum, revised_contract_sum, approved_change_orders_amount,
               pending_change_orders_amount, grand_total, currency_iso_code
        FROM procore_financial_contracts
        WHERE project_key = ?
        ORDER BY contract_family, number, contract_id
        """,
        (project_key,),
    )


def read_financial_amount_facts(
    *,
    project_key: str,
    amount_name: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    conn = _open(db_path)
    if amount_name is None:
        return _rows(
            conn,
            """
            SELECT amount_fact_id, record_key, endpoint_id, amount_name, amount_value,
                   currency_iso_code, period_start, period_end, wbs_code_id, cost_code_id,
                   source_field_path
            FROM procore_financial_amount_facts
            WHERE project_key = ?
            ORDER BY amount_name, record_key
            """,
            (project_key,),
        )
    return _rows(
        conn,
        """
        SELECT amount_fact_id, record_key, endpoint_id, amount_name, amount_value,
               currency_iso_code, period_start, period_end, wbs_code_id, cost_code_id,
               source_field_path
        FROM procore_financial_amount_facts
        WHERE project_key = ? AND amount_name = ?
        ORDER BY record_key
        """,
        (project_key, amount_name),
    )


def read_financial_risk_view(
    *, project_key: str, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Derived risk rows from existing columns: unexecuted contracts and
    executed-but-unpaid change orders. Read-only, deterministic."""
    conn = _open(db_path)
    return _rows(
        conn,
        """
        SELECT 'contract_unexecuted' AS risk_type, record_key, number, status,
               grand_total AS amount
        FROM procore_financial_contracts
        WHERE project_key = ? AND (executed = 0 OR executed IS NULL)
        UNION ALL
        SELECT 'change_order_unpaid' AS risk_type, record_key, number, status,
               grand_total AS amount
        FROM procore_financial_change_orders
        WHERE project_key = ? AND executed = 1 AND (paid = 0 OR paid IS NULL)
        ORDER BY risk_type, number, record_key
        """,
        (project_key, project_key),
    )


__all__ = [
    "upsert_financial_contract",
    "upsert_financial_line_item",
    "upsert_financial_change_order",
    "upsert_financial_change_order_line_item",
    "upsert_financial_payment_application",
    "upsert_financial_invoice_item",
    "upsert_financial_rfq",
    "upsert_financial_change_event",
    "upsert_financial_budget_view",
    "upsert_financial_budget_row",
    "upsert_financial_budget_change",
    "upsert_financial_compliance_document",
    "emit_financial_amount_fact",
    "read_financial_contract_summary",
    "read_financial_amount_facts",
    "read_financial_risk_view",
]
