"""Phase 10 (252) — New Today overnight change digest tests.

Covers the reviewer's hard requirements:

* exact / near-exact BUSINESS-EVENT strings per source family (email, calendar, Procore RFI,
  RFI-response, invoice, change-order, commitment, SharePoint) — and a regression guard that the
  output never degrades to "…signal", "attendees / domains", or count-only summaries;
* New Today is the first visible section with the required header + subhead contract;
* project display names render, never raw keys/slugs;
* Procore detail-or-drop demotes detail-missing records to diagnostics (never a New Today item);
* the email usefulness gate marks the digest degraded when substrate exists but nothing is actionable;
* the deterministic refresh-window contract (fallback + run-marker);
* the bounded Ollama overlay (mock) enriches framing without touching facts; a leak withholds it;
* deterministic fallback (no model) still produces usable items;
* Markdown ↔ browser HTML render the same items and both are raw-safe;
* persistence guard columns are zero and --max-persist fail-closes.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.daily_run_html import (
    render_daily_run_html,
    scan_daily_run_html,
)
from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
    scan_text_for_forbidden,
)
from hb_assistant.construction.second_brain.local_ai.new_today_digest import (
    build_new_today_digest,
    compute_refresh_window,
)
from hb_assistant.construction.second_brain.local_ai.new_today_presentation import (
    build_render_model,
    render_markdown,
)
from hb_assistant.construction.second_brain.local_ai.ollama_new_today import apply_model_overlay
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection
from tests._phase_10_new_today_seed import BRIEF_DATE, seed_new_today_fixture

runner = CliRunner()


class _Store:
    def __init__(self, db: str) -> None:
        self._db_path = db


def _digest(db: str):
    return build_new_today_digest(store=_Store(db), brief_date=BRIEF_DATE)


def _markdown(db: str) -> str:
    digest = _digest(db)
    status = "degraded" if digest["gates"]["email_degraded"] else "ok"
    return render_markdown(build_render_model(digest, status=status))


# --- Per-family business sentences (revision 7) ------------------------------------------------


def test_email_event_is_a_business_sentence(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert "John Smith (Coastal Pipeline) emailed you yesterday at 4:30 PM" in md
    assert "Alton Hilltop at PBG" in md  # display name, not the key
    assert "Confirm whether the latest draft has been returned or assign follow-up." in md


def test_invoice_event_renders_vendor_number_amount_period_status(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert (
        "Coastal Pipeline submitted Invoice #1842 for Tropical for the pay period ending "
        "05/25/2026 for $58,200.00. It has not been reviewed yet." in md
    )


def test_rfi_event_renders_number_title_status_impact_respondent(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert 'RFI #025 ("Tropical drainage detail") for Tropical is Open.' in md
    assert "Flagged for cost impact." in md
    assert "Ball in court: Seema Shibi." in md


def test_rfi_response_event(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert "Seema Shibi responded to RFI #025 for Tropical." in md


def test_change_order_event(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert 'Change Order #07 ("Garage slab revision") for PGA The Modern & Garage is Pending' in md
    assert "$12,500.00" in md


def test_commitment_event(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert 'Commitment #C-12 ("Site concrete") for The Wellington is Approved' in md


def test_sharepoint_event(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert 'Maria Gomez updated "Wellington Permit Set Rev3.pdf"' in md
    assert "The Wellington" in md


def test_calendar_event(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert "Brian Olsen" in md and "Alton Hilltop vibro compaction" in md


def test_no_regression_to_signal_or_count_language(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path)).lower()
    assert " signal" not in md
    assert "attendees / domains" not in md and "domains" not in md
    assert "procore financial / project signals" not in md
    assert "payment-due invoice signal" not in md


# --- Section + contract -----------------------------------------------------------------------


def test_header_subhead_and_new_today_first(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    assert md.startswith("# Today's Daily Brief")
    assert "_Summary of the top items for 2026-06-12 and prep through 2026-06-19_" in md
    # New Today is the first substantive section and precedes any group.
    assert "## New Today" in md
    assert md.index("## New Today") < md.index("### Needs your attention")
    # No schedule/status metadata above New Today.
    above = md[: md.index("## New Today")]
    assert "friday_next_week" not in above and "status" not in above.lower()


def test_attention_groups_present_and_ordered(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    i_attn = md.index("Needs your attention")
    i_team = md.index("Team follow-up / monitor")
    i_aware = md.index("Awareness only")
    assert i_attn < i_team < i_aware


def test_no_raw_project_keys_in_output(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))
    for key in ("alton-hilltop-pbg", "pga-modern-garage", "the-wellington", "__needs_review__"):
        assert key not in md


# --- Detail-or-drop + usefulness gates --------------------------------------------------------


def test_procore_detail_missing_demotes_to_diagnostic(tmp_path: Path) -> None:
    digest = _digest(_seed(tmp_path))
    labels = [d["label"] for d in digest["diagnostics"]]
    assert any("RFI missing number/status" in x for x in labels)
    assert any("Invoice missing number/vendor/status" in x for x in labels)
    # Demoted rows never appear as business items.
    md = render_markdown(build_render_model(digest))
    assert "#526" not in md and "#1843" not in md


def test_email_usefulness_gate_degraded_when_no_actionable(tmp_path: Path) -> None:
    db = str(tmp_path / "gap.db")
    seed_new_today_fixture(db, include_detail_gaps=False)
    conn = get_connection(db)
    # Remove the actionable follow-up so email substrate exists but nothing is actionable.
    conn.execute("DELETE FROM task_candidates")
    conn.commit()
    digest = build_new_today_digest(store=_Store(db), brief_date=BRIEF_DATE)
    assert digest["gates"]["email_substrate_present"] is True
    assert digest["gates"]["email_actionable_count"] == 0
    assert digest["gates"]["email_degraded"] is True
    model = build_render_model(digest, status="degraded")
    assert model["degraded_warning"] is not None


# --- Refresh window contract ------------------------------------------------------------------


def test_refresh_window_fallback_contract(tmp_path: Path) -> None:
    win = compute_refresh_window(_Store(_seed(tmp_path)), BRIEF_DATE)
    assert win.source == "fallback_window"
    assert win.start_utc < win.end_utc
    assert win.rationale


def test_refresh_window_uses_run_markers(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    conn = get_connection(db)
    meta = [
        (r[1], r[2], r[3], r[4]) for r in conn.execute("PRAGMA table_info(procore_live_sync_runs)")
    ]

    def ins_run(sid: str, completed: str) -> None:
        kw = {
            "sync_run_id": sid,
            "endpoint_id": "rfis",
            "command_endpoint": "rfis",
            "project_key": "tropical",
            "procore_project_id": "1",
            "company_id": "1",
            "mode": "apply",
            "started_at_utc": "2026-06-11T20:00:00+00:00",
            "completed_at_utc": completed,
            "state": "success",
            "status": "success",
        }
        for name, typ, notnull, dflt in meta:
            if notnull and dflt is None and name not in kw:
                kw[name] = 0 if str(typ or "").upper().startswith(("INT", "REAL", "NUM")) else "x"
        conn.execute(
            f"INSERT INTO procore_live_sync_runs ({','.join(kw)}) VALUES ({','.join('?' * len(kw))})",
            tuple(kw.values()),
        )

    ins_run("r0", "2026-06-11T00:30:00+00:00")
    ins_run("r1", "2026-06-12T00:30:00+00:00")
    conn.commit()
    win = compute_refresh_window(_Store(db), BRIEF_DATE)
    assert win.source == "run_markers"
    assert win.start_utc.startswith("2026-06-11T00:30")
    assert win.end_utc.startswith("2026-06-12T00:30")


# --- Ollama overlay + deterministic fallback --------------------------------------------------


def test_model_overlay_polishes_framing_not_facts(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    store = ConstructionStore(db_path=db)
    digest = build_new_today_digest(store=store, brief_date=BRIEF_DATE)
    inv = next(e for e in digest["events"] if e.business_record_number == "1842")
    det_summary = inv.summary_text
    advice = json.dumps(
        {
            "items": [
                {
                    "ref": inv.event_id,
                    "why_it_matters": "Unreviewed invoice that affects the next pay cycle.",
                    "recommended_action": "Assign the review owner today.",
                    "attention_class": "needs_attention",
                }
            ]
        }
    )
    profiles = load_local_model_profiles()
    profile = next(p for p in profiles.profiles if p.profile_id == "default_extract")
    res = apply_model_overlay(
        digest["events"],
        profile=profile,
        profiles=profiles,
        backend=StaticOutputClient(advice),
        store=store,
        dry_run=True,
    )
    assert res["status"] == "ok" and res["enriched_count"] >= 1
    assert inv.enrichment_status == "model_enriched"
    assert inv.why_it_matters == "Unreviewed invoice that affects the next pay cycle."
    assert inv.summary_text == det_summary  # deterministic facts untouched
    # Hash-only receipt fields only — never raw prompt/response.
    assert "would_write_receipt" in res


def test_model_overlay_withheld_on_leak(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    store = ConstructionStore(db_path=db)
    digest = build_new_today_digest(store=store, brief_date=BRIEF_DATE)
    ev = digest["events"][0]
    before = ev.why_it_matters
    leak = json.dumps(
        {
            "items": [
                {
                    "ref": ev.event_id,
                    "why_it_matters": "see https://x.example.com",
                    "recommended_action": "ok",
                }
            ]
        }
    )
    profiles = load_local_model_profiles()
    profile = next(p for p in profiles.profiles if p.profile_id == "default_extract")
    res = apply_model_overlay(
        digest["events"],
        profile=profile,
        profiles=profiles,
        backend=StaticOutputClient(leak),
        store=store,
        dry_run=True,
    )
    assert res["status"] == "withheld"
    assert ev.why_it_matters == before  # unchanged on withhold


def test_deterministic_fallback_no_model_is_usable(tmp_path: Path) -> None:
    md = _markdown(_seed(tmp_path))  # built with no model client at all
    assert "RFI #025" in md and "Invoice #1842" in md
    assert scan_text_for_forbidden(md) == []


# --- Markdown <-> HTML parity + raw-safety -----------------------------------------------------


def test_markdown_and_html_render_same_items_raw_safe(tmp_path: Path) -> None:
    digest = _digest(_seed(tmp_path))
    model = build_render_model(digest, status="ok")
    md = render_markdown(model)
    html = render_daily_run_html(
        brief_date=BRIEF_DATE,
        status="success",
        sections=[],
        summary={"rendered": 0},
        warnings=[],
        generated_label="2026-06-12T05:00",
        new_today=model,
    )
    # Same business anchors appear in both surfaces.
    for anchor in ("Invoice #1842", "RFI #025", "Today"):
        assert anchor in md
        assert anchor in html
    # New Today precedes the collapsed diagnostics in the browser HTML.
    assert html.index("New Today") < html.index("Run details / diagnostics")
    # Both surfaces are egress-clean.
    assert scan_text_for_forbidden(md) == []
    assert scan_daily_run_html(html) == []


# --- Persistence: guard columns zero + cap ----------------------------------------------------


def test_persist_guard_columns_zero_and_cap(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "new-today",
            "--db",
            db,
            "--brief-date",
            BRIEF_DATE,
            "--no-client",
            "--apply",
            "--max-persist",
            "100",
            "--json",
        ],
    )
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    assert payload["persist"]["persisted"] is True
    conn = get_connection(db)
    guards = [
        c[1]
        for c in conn.execute("PRAGMA table_info(daily_brief_change_events)")
        if c[1].endswith(("_persisted", "_performed"))
    ]
    total = conn.execute(
        f"SELECT {'+'.join('COALESCE(SUM(' + g + '),0)' for g in guards)} "
        "FROM daily_brief_change_events"
    ).fetchone()[0]
    assert total == 0


def test_apply_cap_fails_closed(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "new-today",
            "--db",
            db,
            "--brief-date",
            BRIEF_DATE,
            "--no-client",
            "--apply",
            "--max-persist",
            "1",
            "--json",
        ],
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["persist"]["capped"] is True
    assert payload["persist"]["persisted_events"] == 0
    conn = get_connection(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_change_events").fetchone()[0] == 0


# --- CLI surface ------------------------------------------------------------------------------


def test_cli_dry_run_writes_nothing_and_is_raw_free(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "new-today",
            "--db",
            db,
            "--brief-date",
            BRIEF_DATE,
            "--no-client",
            "--json",
        ],
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["status"] == "ok"
    assert payload["raw_safety_scan"]["clean"] is True
    conn = get_connection(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_change_events").fetchone()[0] == 0
    for forbidden in ("http://", "https://", "bearer", "raw_body", "@coastal"):
        assert forbidden not in res.stdout.lower()


def test_cli_apply_requires_tmp_db(tmp_path: Path) -> None:
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "new-today",
            "--db",
            "/Users/x/Library/Application Support/app.db",
            "--apply",
            "--max-persist",
            "10",
            "--json",
        ],
    )
    assert res.exit_code == 2
    assert json.loads(res.stdout)["error"] == "apply_requires_tmp_db"


# --- helpers ----------------------------------------------------------------------------------


def _seed(tmp_path: Path) -> str:
    db = str(tmp_path / "new_today.db")
    seed_new_today_fixture(db)
    return db
