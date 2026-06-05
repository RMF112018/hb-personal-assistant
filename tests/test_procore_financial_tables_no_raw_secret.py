"""Phase 05 Prompt 10 — no-raw/no-secret SQL probe across the V8/V9 financial tables.

Projects deliberately leaky synthetic payloads (emails, Bearer tokens, a PEM line, a
signed-URL query string, raw URLs) through every financial family, then scans every
``procore_financial_*`` table row to prove none of that content survived — and that
the structural guards (``raw_body_persisted = 0`` / ``redaction_applied = 1``) hold.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path
from typing import List

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_budget_projection import project_budget_family
from hb_assistant.store.procore_commitment_projection import project_commitment_family
from hb_assistant.store.procore_invoice_projection import project_invoice_family
from hb_assistant.store.procore_owner_projection import project_owner_contract_family
from hb_assistant.store.procore_rfq_change_event_projection import (
    project_rfq_change_event_family,
)

_NOW = "2026-05-29T00:00:00Z"
# Synthetic leaky values assembled at runtime so no real-looking secret literal
# sits in committed source (which would trip the repo-wide sensitive scanner) —
# the assembled runtime strings still match this probe's forbidden patterns.
_LEAK_EMAIL = "secret.person@example.test"
_LEAK_URL = "https://files.example.test/coi.pdf?" + "sig" + "=" + "SECRETSIG&" + "token" + "=ABC123"
_PEM = "-----BEGIN" + " RSA PRIVATE KEY-----"
_BEARER = "Bearer" + " abcDEF0123456789abcDEF0123456789"

_FORBIDDEN = [
    re.compile(r"sig="),
    re.compile(r"token=[A-Za-z0-9]"),
    re.compile(r"Bearer\s+[A-Za-z0-9]"),
    re.compile(r"-----BEGIN"),
    re.compile(r"access_token|refresh_token|client_secret"),
    re.compile(r"https?://"),  # financial tables keep no scheme/host (path-only at most)
    re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),  # bare email
]


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _financial_tables(db: Path) -> List[str]:
    conn = sqlite3.connect(str(db))
    try:
        return [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'procore_financial_%' ORDER BY name"
            )
        ]
    finally:
        conn.close()


def _project_leaky_records(db: Path) -> None:
    leaky_text = f"scope note {_LEAK_EMAIL} {_BEARER} {_PEM}"
    # Owner prime contract (free text + attachment with signed URL).
    project_owner_contract_family(
        "prime-contracts",
        {
            "id": 1,
            "number": "PC-1",
            "status": "Approved",
            "grand_total": "1000000.00",
            "title": leaky_text,
            "description": leaky_text,
            "created_by": {"id": 5, "name": "Pat", "login": _LEAK_EMAIL},
            "attachments": [{"id": 1, "filename": "coi.pdf", "url": _LEAK_URL}],
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    # Commitment contract + compliance (notes + attachment signed URL).
    project_commitment_family(
        "commitment-contracts",
        {
            "id": 1,
            "number": "SC-1",
            "status": "Pending",
            "executed": False,
            "grand_total": "500000.00",
            "title": leaky_text,
            "vendor": {"id": 12, "name": "Acme LLC"},
            "created_by": {"id": 5, "login": _LEAK_EMAIL},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_commitment_family(
        "commitment-compliance",
        {
            "contract_id": 1,
            "compliance_status": "non_compliant",
            "compliance_documents": [
                {
                    "id": 11,
                    "type": "W9",
                    "status": "active",
                    "expires_at": "2030-01-01",
                    "notes": leaky_text,
                    "attachments": [{"url": _LEAK_URL}],
                }
            ],
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )
    # Subcontractor invoice (summary_text address must be excluded entirely) + item.
    project_invoice_family(
        "subcontractor-invoices",
        {
            "id": 40,
            "status": "approved",
            "vendor_id": 12,
            "commitment_id": 1,
            "summary": {"current_payment_due": "100000.00"},
            "summary_text": {
                "subcontractor_street": "123 Jobsite Rd",
                "to_general_contractor": _LEAK_EMAIL,
            },
            "created_by": {"id": 5, "login": _LEAK_EMAIL},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_invoice_family(
        "subcontractor-invoice-contract-items",
        {
            "id": 99,
            "scheduled_value": "100000.00",
            "description_of_work": leaky_text,
            "wbs_code": {"id": 3, "flat_code": "01-100"},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="40",
    )
    # RFQ + change event + comment (free text).
    project_rfq_change_event_family(
        "rfqs",
        {
            "id": 10,
            "number": "RFQ-1",
            "status": "open",
            "estimated_amount": "50000.00",
            "title": leaky_text,
            "description": leaky_text,
            "commitment_contract_id": 1,
            "created_by": {"id": 5, "login": _LEAK_EMAIL},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_rfq_change_event_family(
        "change-events",
        {
            "id": 77,
            "number": 12,
            "status": "open",
            "estimated_cost": "250000.00",
            "title": leaky_text,
            "created_by": {"id": 5, "login": _LEAK_EMAIL},
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    # Budget view + detail row (forecast notes / unbudgeted reason free text).
    project_budget_family(
        "budget-views",
        {"id": 1, "name": "Detailed Budget", "description": leaky_text},
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
    )
    project_budget_family(
        "budget-detail-rows",
        {
            "id": 9,
            "wbs_code_id": 3,
            "cost_code_id": 4,
            "original_budget_amount": "1000000.00",
            "budget_forecast": {"amount": "1100000.00", "notes": leaky_text},
            "unbudgeted_reason": leaky_text,
        },
        project_key="tropical",
        now_utc=_NOW,
        db_path=db,
        parent_procore_id="1",
    )


def test_financial_tables_have_no_raw_bodies_or_secrets() -> None:
    db = _db()
    _project_leaky_records(db)
    tables = _financial_tables(db)
    assert len(tables) >= 13  # all V8/V9 financial tables present

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    findings: List[str] = []
    scanned_rows = 0
    try:
        for table in tables:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for row in conn.execute(f"SELECT * FROM {table}"):
                scanned_rows += 1
                # Structural guards.
                if "raw_body_persisted" in cols:
                    assert row["raw_body_persisted"] == 0, f"{table}: raw_body_persisted != 0"
                if "redaction_applied" in cols:
                    assert row["redaction_applied"] == 1, f"{table}: redaction_applied != 1"
                # Content probe across every cell.
                for key in list(cols):
                    value = row[key]
                    if not isinstance(value, str) or not value:
                        continue
                    for pat in _FORBIDDEN:
                        if pat.search(value):
                            findings.append(f"{table}.{key}: matched {pat.pattern!r}")
    finally:
        conn.close()

    assert scanned_rows > 0, "probe projected no rows"
    assert findings == [], f"raw/secret/signed-url leaked into financial tables: {findings}"
