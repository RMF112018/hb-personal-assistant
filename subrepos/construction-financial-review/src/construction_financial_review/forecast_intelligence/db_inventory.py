"""Read-only inventory of the local hb-personal-assistant SQLite DB.

The DB is opened strictly read-only (``mode=ro``); nothing is ever written. The emitted inventory is
schema + row counts ONLY — no cell values, no payload columns. A separate project-level change-order
aggregation returns Decimal dollar sums for the audit reconciliation; those sums are NOT attributed
to any budget code (the DB carries no deterministic commitment/contract -> budget-code link), so they
inform context only and never drive a per-code estimate.
"""
from __future__ import annotations

import os
import sqlite3
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..common.money import D, money_str

DEFAULT_DB_PATH = ("~/Library/Application Support/HB Personal Assistant/db/"
                   "hb-personal-assistant.sqlite")
DEFAULT_TABLES = (
    "procore_financial_change_orders",
    "procore_financial_contracts",
    "procore_financial_subcontractor_invoices",
    "procore_financial_invoice_items",
    "procore_financial_amount_facts",
    "procore_financial_budget_rows",
)


def resolve_db_path(cfg: dict) -> Path:
    fi = cfg.get("forecast_intelligence") or {}
    raw = fi.get("db_path") or DEFAULT_DB_PATH
    return Path(os.path.expanduser(raw))


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def inventory(cfg: dict, project_key: str) -> OrderedDict:
    """Schema + counts only (deterministic; no payloads, no timestamps)."""
    path = resolve_db_path(cfg)
    fi = cfg.get("forecast_intelligence") or {}
    tables = tuple(fi.get("db_inventory_tables") or DEFAULT_TABLES)
    if not path.exists():
        return OrderedDict([
            ("db_present", False),
            ("db_path", str(path)),
            ("note", "Local DB not present; inventory skipped. Quantitative forecast is unaffected."),
            ("tables", []),
        ])
    con = _connect_ro(path)
    try:
        cur = con.cursor()
        existing = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()}
        rows = []
        for t in tables:
            if t not in existing:
                rows.append(OrderedDict([("table", t), ("present", False)]))
                continue
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
            n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            try:
                nt = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE project_key=?",
                                 (project_key,)).fetchone()[0]
            except sqlite3.Error:
                nt = None
            rows.append(OrderedDict([
                ("table", t), ("present", True),
                ("column_names", cols), ("row_count", n),
                ("project_row_count", nt),
            ]))
        return OrderedDict([
            ("db_present", True),
            ("db_path", str(path)),
            ("inventory_scope", "schema_and_counts_only_no_payloads"),
            ("tables", rows),
        ])
    finally:
        con.close()


def change_order_aggregation(cfg: dict, project_key: str) -> OrderedDict:
    """Project-level change-order dollar aggregation (informational; not attributed to codes)."""
    path = resolve_db_path(cfg)
    if not path.exists():
        return OrderedDict([("db_present", False), ("families", [])])
    con = _connect_ro(path)
    try:
        cur = con.cursor()
        try:
            data = cur.execute(
                "SELECT change_order_family, grand_total FROM procore_financial_change_orders "
                "WHERE project_key=?", (project_key,)).fetchall()
        except sqlite3.Error:
            return OrderedDict([("db_present", True), ("families", []),
                                ("note", "change-order table absent or unscannable")])
        fam: dict[str, dict] = {}
        for family, grand_total in data:
            g = fam.setdefault(family or "unknown",
                               {"count": 0, "approved_additive": Decimal("0"),
                                "deductive": Decimal("0"), "deductive_count": 0})
            amt = D(grand_total)
            g["count"] += 1
            if amt < 0:
                g["deductive"] += amt
                g["deductive_count"] += 1
            else:
                g["approved_additive"] += amt
        families = []
        for name in sorted(fam):
            g = fam[name]
            net = g["approved_additive"] + g["deductive"]
            families.append(OrderedDict([
                ("change_order_family", name),
                ("count", g["count"]),
                ("deductive_count", g["deductive_count"]),
                ("approved_additive_total", money_str(g["approved_additive"])),
                ("deductive_total", money_str(g["deductive"])),
                ("net_total", money_str(net)),
            ]))
        return OrderedDict([
            ("db_present", True),
            ("attribution",
             "project-level only; change orders carry no deterministic budget-code link, so these "
             "sums inform context and are NEVER used to set a per-budget-code estimate"),
            ("families", families),
        ])
    finally:
        con.close()
