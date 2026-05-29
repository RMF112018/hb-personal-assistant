"""Phase 05 Obsidian financial register.

Projects the V8/V9 financial tables + action signals + change history into one
deterministic, source-linked Obsidian note per project — ten sections (contract
summary, open financial actions, prime change orders, commitments & compliance,
subcontractor invoices, payment applications, RFQs & change events, budget movement,
retainage/payment risk, last 30-day financial changes).

Read-only / local — never calls Procore. Dry-run builds the rendered note;
``--apply`` writes the single marker-bounded note alongside the other ``procore-*``
artifacts in ``01_Projects/``. Output carries only already-redacted columns + the
source ``record_key`` (+ ``procore_record_id`` / endpoint where available) + a local
query-command reference — never raw payload bodies, signed URLs, emails, or tokens.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..store.procore_budget_projection import BUDGET_ENDPOINTS
from ..store.procore_commitment_projection import COMMITMENT_ENDPOINTS
from ..store.procore_enrichment import get_procore_action_signals
from ..store.procore_financials import (
    read_financial_budget_changes,
    read_financial_change_events,
    read_financial_change_orders,
    read_financial_compliance_documents,
    read_financial_contract_summary,
    read_financial_payment_applications,
    read_financial_rfqs,
    read_financial_risk_view,
    read_financial_subcontractor_invoices,
)
from ..store.procore_history import get_procore_changes
from ..store.procore_invoice_projection import INVOICE_ENDPOINTS
from ..store.procore_owner_projection import OWNER_ENDPOINTS
from ..store.procore_rfq_change_event_projection import RFQ_ENDPOINTS
from .obsidian import PROCORE_GUARDRAILS, _write_procore_artifact
from .obsidian_register import _section, _table

_MARKER_KIND = "FINANCIAL-REGISTER"
_FILENAME_SUFFIX = "procore-financial-register.md"

_FINANCIAL_ENDPOINTS = (
    OWNER_ENDPOINTS | COMMITMENT_ENDPOINTS | INVOICE_ENDPOINTS | RFQ_ENDPOINTS | BUDGET_ENDPOINTS
)

# Defensive output fence — register content is built only from redacted columns, but
# fail closed if any secret/URL/email/token shape ever reaches the rendered note.
_FORBIDDEN = [
    re.compile(r"https?://"),
    re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9]", re.IGNORECASE),
    re.compile(r"-----BEGIN"),
    re.compile(r"sig="),
]


def _assert_no_raw(text: str) -> None:
    for pat in _FORBIDDEN:
        if pat.search(text):
            raise ValueError(f"financial register output fence: matched {pat.pattern!r}")


def _q(project_key: str, verb: str, extra: str = "") -> str:
    base = f"hb-assistant procore live financial {verb} --project {project_key}"
    return f"{base} {extra} --json".replace("  ", " ").strip()


def build_financial_register(
    project_key: str, *, now_utc: str, since_utc: str, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Build the ten financial register sections for a project (pure read)."""
    contracts = read_financial_contract_summary(project_key=project_key, db_path=db_path)
    prime_cos = read_financial_change_orders(
        project_key=project_key, change_order_family="prime", db_path=db_path
    )
    compliance = read_financial_compliance_documents(project_key=project_key, db_path=db_path)
    invoices = read_financial_subcontractor_invoices(project_key=project_key, db_path=db_path)
    pay_apps = read_financial_payment_applications(project_key=project_key, db_path=db_path)
    rfqs = read_financial_rfqs(project_key=project_key, db_path=db_path)
    change_events = read_financial_change_events(project_key=project_key, db_path=db_path)
    budget_changes = read_financial_budget_changes(project_key=project_key, db_path=db_path)
    risk = read_financial_risk_view(project_key=project_key, db_path=db_path)
    signals = get_procore_action_signals(
        project_key=project_key, signal_status="open", db_path=db_path
    )
    fin_signals = [s for s in signals if s.get("endpoint_id") in _FINANCIAL_ENDPOINTS]
    changes = get_procore_changes(project_key=project_key, since_utc=since_utc, db_path=db_path)
    fin_changes = [c for c in changes if c.get("endpoint_id") in _FINANCIAL_ENDPOINTS]

    commitments = [c for c in contracts if c.get("contract_family") == "commitment"]

    commitments_md = _table(
        ["Record Key", "Contract ID", "Number", "Status", "Grand Total"],
        [
            [
                c.get("record_key"),
                c.get("contract_id"),
                c.get("number"),
                c.get("status"),
                c.get("grand_total"),
            ]
            for c in commitments
        ],
        empty="No commitment contracts.",
    )
    compliance_md = _table(
        ["Compliance Key", "Contract Record Key", "Doc Type", "Status", "Compliant", "Expires"],
        [
            [
                d.get("compliance_key"),
                d.get("contract_record_key"),
                d.get("document_type"),
                d.get("status"),
                d.get("compliant"),
                d.get("expiration_date"),
            ]
            for d in compliance
        ],
        empty="No compliance documents.",
    )
    rfqs_md = _table(
        ["Record Key", "RFQ ID", "Number", "Status", "Estimated Amount", "Sched Impact"],
        [
            [
                r.get("record_key"),
                r.get("rfq_id"),
                r.get("number"),
                r.get("status"),
                r.get("estimated_amount"),
                r.get("estimated_schedule_impact"),
            ]
            for r in rfqs
        ],
        empty="No RFQs.",
    )
    change_events_md = _table(
        ["Record Key", "Change Event ID", "Number", "Status", "Est Cost", "Sched Impact"],
        [
            [
                c.get("record_key"),
                c.get("change_event_id"),
                c.get("number"),
                c.get("status"),
                c.get("estimated_cost"),
                c.get("schedule_impact_amount"),
            ]
            for c in change_events
        ],
        empty="No change events.",
    )
    risk_md = _table(
        ["Risk Type", "Record Key", "Number", "Status", "Amount"],
        [
            [
                r.get("risk_type"),
                r.get("record_key"),
                r.get("number"),
                r.get("status"),
                r.get("amount"),
            ]
            for r in risk
        ],
        empty="No derived financial risk rows.",
    )
    retainage_md = _table(
        ["Record Key", "Source", "Status", "Total Retainage"],
        [
            [
                i.get("record_key"),
                "subcontractor_invoice",
                i.get("status"),
                i.get("total_retainage"),
            ]
            for i in invoices
            if (i.get("total_retainage") or "") not in ("", "0", "0.00", None)
        ]
        + [
            [p.get("record_key"), "payment_application", p.get("status"), p.get("total_retainage")]
            for p in pay_apps
            if (p.get("total_retainage") or "") not in ("", "0", "0.00", None)
        ],
        empty="No retainage currently held.",
    )

    sections: Dict[str, str] = {
        "contract_summary": _section(
            "Contract Summary",
            _q(project_key, "contracts"),
            _table(
                [
                    "Record Key",
                    "Family",
                    "Contract ID",
                    "Number",
                    "Status",
                    "Grand Total",
                    "Currency",
                ],
                [
                    [
                        c.get("record_key"),
                        c.get("contract_family"),
                        c.get("contract_id"),
                        c.get("number"),
                        c.get("status"),
                        c.get("grand_total"),
                        c.get("currency_iso_code"),
                    ]
                    for c in contracts
                ],
                empty="No contracts projected.",
            ),
        ),
        "open_financial_actions": _section(
            "Open Financial Actions",
            f"hb-assistant procore live actions --project {project_key} --status open --json",
            _table(
                ["Signal", "Importance", "Endpoint", "Record Key", "Due", "Title"],
                [
                    [
                        s.get("signal_type"),
                        s.get("importance"),
                        s.get("endpoint_id"),
                        s.get("record_key"),
                        s.get("due_at_utc") or "",
                        s.get("title_redacted") or "",
                    ]
                    for s in fin_signals
                ],
                empty="No open financial action signals.",
            ),
        ),
        "prime_change_orders": _section(
            "Prime Change Orders",
            _q(project_key, "contracts", "--type prime"),
            _table(
                [
                    "Record Key",
                    "CO ID",
                    "Number",
                    "Status",
                    "Executed",
                    "Paid",
                    "Grand Total",
                    "Sched Impact",
                ],
                [
                    [
                        c.get("record_key"),
                        c.get("change_order_id"),
                        c.get("number"),
                        c.get("status"),
                        c.get("executed"),
                        c.get("paid"),
                        c.get("grand_total"),
                        c.get("schedule_impact_amount"),
                    ]
                    for c in prime_cos
                ],
                empty="No prime change orders.",
            ),
        ),
        "commitments_and_compliance": _section(
            "Commitments and Compliance",
            _q(project_key, "contracts", "--type commitment"),
            f"{commitments_md}\n\n**Compliance Documents**\n\n{compliance_md}",
        ),
        "subcontractor_invoices": _section(
            "Subcontractor Invoices",
            _q(project_key, "invoices"),
            _table(
                [
                    "Record Key",
                    "Invoice ID",
                    "Commitment",
                    "Billing Period",
                    "Vendor",
                    "Number",
                    "Status",
                    "Payment Due",
                    "Retainage",
                ],
                [
                    [
                        i.get("record_key"),
                        i.get("invoice_id"),
                        i.get("commitment_id"),
                        i.get("billing_period_id"),
                        i.get("vendor_id"),
                        i.get("number"),
                        i.get("status"),
                        i.get("current_payment_due"),
                        i.get("total_retainage"),
                    ]
                    for i in invoices
                ],
                empty="No subcontractor invoices.",
            ),
        ),
        "payment_applications": _section(
            "Payment Applications",
            _q(project_key, "summary"),
            _table(
                [
                    "Record Key",
                    "Payment App ID",
                    "Prime Contract",
                    "Number",
                    "Status",
                    "Payment Due",
                    "Retainage",
                    "Balance to Finish",
                ],
                [
                    [
                        p.get("record_key"),
                        p.get("payment_application_id"),
                        p.get("prime_contract_id"),
                        p.get("number"),
                        p.get("status"),
                        p.get("current_payment_due"),
                        p.get("total_retainage"),
                        p.get("balance_to_finish_including_retainage"),
                    ]
                    for p in pay_apps
                ],
                empty="No payment applications.",
            ),
        ),
        "rfqs_and_change_events": _section(
            "RFQs and Change Events",
            _q(project_key, "summary"),
            f"{rfqs_md}\n\n**Change Events**\n\n{change_events_md}",
        ),
        "budget_movement": _section(
            "Budget Movement",
            _q(project_key, "budget"),
            _table(
                ["Record Key", "Kind", "Change ID", "Number", "Status", "Adjustment", "From", "To"],
                [
                    [
                        b.get("budget_change_key"),
                        b.get("budget_change_kind"),
                        b.get("budget_change_id"),
                        b.get("number"),
                        b.get("status"),
                        b.get("adjustment_amount"),
                        b.get("from_amount"),
                        b.get("to_amount"),
                    ]
                    for b in budget_changes
                ],
                empty="No budget changes/modifications.",
            ),
        ),
        "retainage_payment_risk": _section(
            "Retainage / Payment Risk",
            _q(project_key, "risk"),
            f"{risk_md}\n\n**Retainage Held**\n\n{retainage_md}",
        ),
        "last_30d_financial_changes": _section(
            "Last 30-Day Financial Changes",
            _q(project_key, "changes", '--since "30 days ago"'),
            _table(
                [
                    "Detected",
                    "Endpoint",
                    "Procore Record",
                    "Field",
                    "Category",
                    "Type",
                    "Record Key",
                ],
                [
                    [
                        c.get("detected_at_utc"),
                        c.get("endpoint_id"),
                        c.get("procore_record_id"),
                        c.get("field_path"),
                        c.get("change_category"),
                        c.get("change_type"),
                        c.get("record_key"),
                    ]
                    for c in fin_changes
                ],
                empty="No financial changes in the window.",
            ),
        ),
    }

    counts = {
        "contracts": len(contracts),
        "open_financial_actions": len(fin_signals),
        "prime_change_orders": len(prime_cos),
        "commitments": len(commitments),
        "compliance_documents": len(compliance),
        "subcontractor_invoices": len(invoices),
        "payment_applications": len(pay_apps),
        "rfqs": len(rfqs),
        "change_events": len(change_events),
        "budget_changes": len(budget_changes),
        "risk_rows": len(risk),
        "recent_financial_changes": len(fin_changes),
    }
    rendered = _render_note(project_key, now_utc=now_utc, since_utc=since_utc, sections=sections)
    _assert_no_raw(rendered)
    return {
        "project_key": project_key,
        "generated_utc": now_utc,
        "since_utc": since_utc,
        "sections": sections,
        "rendered": rendered,
        "counts": counts,
        "review_sensitive": False,
        "guardrails": dict(PROCORE_GUARDRAILS),
    }


_SECTION_ORDER = [
    "contract_summary",
    "open_financial_actions",
    "prime_change_orders",
    "commitments_and_compliance",
    "subcontractor_invoices",
    "payment_applications",
    "rfqs_and_change_events",
    "budget_movement",
    "retainage_payment_risk",
    "last_30d_financial_changes",
]


def _render_note(
    project_key: str, *, now_utc: str, since_utc: str, sections: Dict[str, str]
) -> str:
    frontmatter = "\n".join(
        [
            "---",
            "type: procore_financial_register",
            f"project_key: {project_key}",
            "source: procore_financial_sqlite",
            "review_sensitive: false",
            f"generated_utc: {now_utc}",
            "---",
        ]
    )
    body = "\n\n".join(sections[k] for k in _SECTION_ORDER)
    guardrails = "\n".join(f"- {k}: {v}" for k, v in PROCORE_GUARDRAILS.items())
    return (
        f"{frontmatter}\n\n# Procore Financial Register — {project_key}\n\n"
        f"_Changes window since: {since_utc}. Local SQLite financial projection — no Procore call._\n\n"
        f"{body}\n\n## Guardrails\n\n{guardrails}\n"
    )


def apply_financial_register(
    project_key: str, *, now_utc: str, since_utc: str, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Build + write the single financial-register note (marker-bounded). Returns the
    build result with ``written_paths`` populated (or empty + ``vault_configured=False``
    when no vault root is set)."""
    from ..construction.manifests.vault_writer import ConstructionVaultWriter

    result = build_financial_register(
        project_key, now_utc=now_utc, since_utc=since_utc, db_path=db_path
    )
    writer = ConstructionVaultWriter()
    if not writer.configured:
        result["written_paths"] = []
        result["vault_configured"] = False
        return result
    path = _write_procore_artifact(
        writer.root, f"{project_key}.{_FILENAME_SUFFIX}", result["rendered"], _MARKER_KIND
    )
    result["written_paths"] = [str(path)]
    result["vault_configured"] = True
    return result


__all__ = ["build_financial_register", "apply_financial_register"]
