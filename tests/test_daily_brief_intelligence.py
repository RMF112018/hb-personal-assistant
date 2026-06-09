"""Phase 10 — daily-brief intelligence adapter tests (offline, source-linked, fail-closed)."""

from __future__ import annotations

import json
import sqlite3

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.daily_brief_intelligence import (
    build_daily_brief_intelligence,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

CANDS = [
    {
        "daily_brief_action_candidate_id": "c1",
        "section": "actions",
        "title_redacted": "Send transmittal",
        "project_key": "P1",
        "confidence": 0.8,
        "recommended_next_action": "draft_followup",
    },
    {
        "daily_brief_action_candidate_id": "c2",
        "section": "waiting",
        "title_redacted": "Look-ahead pending",
        "project_key": "P2",
        "confidence": 0.6,
        "recommended_next_action": "review",
    },
]

GOOD_INTEL = json.dumps(
    {
        "executive_catchup": ["One deadline today; two loops waiting on others."],
        "top_priorities": [
            {
                "text": "Send the transmittal",
                "source_ids": ["c1"],
                "confidence": 0.9,
                "reason_code": "due_today",
            }
        ],
        "open_loops": [
            {
                "text": "Look-ahead pending",
                "source_ids": ["c2"],
                "confidence": 0.6,
                "reason_code": "stale",
            }
        ],
        "waiting_on_me": [
            {
                "text": "Transmittal owed by you",
                "source_ids": ["c1"],
                "confidence": 0.8,
                "reason_code": "owed_by_me",
            }
        ],
        "waiting_on_others": [
            {
                "text": "Super owes look-ahead",
                "source_ids": ["c2"],
                "confidence": 0.7,
                "reason_code": "owed_by_other",
            }
        ],
        "meeting_prep": [],
        "project_risk": [],
    }
)


def _profiles():
    return load_local_model_profiles()


def test_success_is_source_linked_and_advisory() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.status == "ok"
    intel = result.intelligence
    assert intel is not None
    # Every kept bullet cites only real candidate ids.
    real = {"c1", "c2"}
    for section in ("top_priorities", "open_loops", "waiting_on_me", "waiting_on_others"):
        for bullet in intel[section]:
            assert bullet["source_ids"]
            assert set(bullet["source_ids"]).issubset(real)
    assert result.metrics["source_link_coverage"] == 1.0
    assert result.metrics["waiting_on_me"] == 1
    assert result.metrics["waiting_on_others"] == 1
    # The surfaced payload is redaction-clean (no URLs/emails/tokens/join links).
    from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
        scan_text_for_forbidden,
    )

    assert scan_text_for_forbidden(json.dumps(result.safe_payload())) == []


def test_reporting_contract_route_vs_terminal_profile() -> None:
    # Happy path: route-selected == terminal == brief_synthesis, no fallback.
    result = build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
    )
    sp = result.safe_payload()
    assert result.route_selected_profile == "brief_synthesis"
    assert result.terminal_profile_id == "brief_synthesis"
    assert result.generation_profile_id == "brief_synthesis"
    assert result.fallback_used is False
    assert "terminal_profile_differs_from_route" not in result.warnings
    # The contract keys are present and stable on the surfaced payload.
    for key in (
        "route_selected_profile",
        "route_model_name",
        "route_reason_code",
        "generation_profile_id",
        "terminal_profile_id",
        "fallback_chain",
        "models_attempted",
        "blockers",
        "warnings",
        "profile_id",
    ):
        assert key in sp
    assert sp["profile_id"] == sp["terminal_profile_id"]
    # No raw prompt/response/validated leakage in the safe payload.
    for forbidden in ("prompt", "validated", "raw_output", "response"):
        assert forbidden not in sp


def test_reporting_contract_fallback_terminal_differs_from_route() -> None:
    # Primary brief_synthesis emits bad JSON for all attempts, then the single-hop fallback
    # (default_extract) returns valid source-linked output. Route stays brief_synthesis; terminal
    # becomes default_extract; both divergence warnings fire.
    result = build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient(outputs=["not json {", "still bad", "nope", GOOD_INTEL]),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.route_selected_profile == "brief_synthesis"
    assert result.terminal_profile_id == "default_extract"
    assert result.fallback_used is True
    assert "fallback_profile_attempted" in result.warnings
    assert "terminal_profile_differs_from_route" in result.warnings


def test_loose_bullets_are_coerced_not_rejected() -> None:
    # Model emits a dict keyed 'summary' (not 'text') + a bare string bullet (no source).
    loose = json.dumps(
        {
            "executive_catchup": ["catch up"],
            "top_priorities": [
                {"summary": "Send the transmittal", "source_ids": ["c1"], "confidence": 0.7},
                "a bare string with no source",
            ],
        }
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS, profiles=_profiles(), backend=StaticOutputClient(loose), dry_run=True
    )
    assert result.enriched is True  # coerced dict survived; not all-or-nothing
    tp = result.intelligence["top_priorities"]
    assert len(tp) == 1  # bare unsourced string dropped by the source-link filter
    assert tp[0]["text"] == "Send the transmittal"
    assert tp[0]["source_ids"] == ["c1"]


def test_invalid_json_falls_back() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient("not json {"),
        dry_run=True,
    )
    assert result.enriched is False
    assert result.intelligence is None
    assert result.withheld_reason is not None


def test_missing_source_links_withheld() -> None:
    bad = json.dumps(
        {
            "executive_catchup": ["ok"],
            "top_priorities": [
                {
                    "text": "do a thing",
                    "source_ids": ["not_a_real_id"],
                    "confidence": 0.5,
                    "reason_code": "x",
                }
            ],
        }
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS, profiles=_profiles(), backend=StaticOutputClient(bad), dry_run=True
    )
    assert result.enriched is False
    assert result.withheld_reason == "no_source_linked_bullets"


def test_redaction_failure_withheld() -> None:
    leaky = json.dumps(
        {
            "executive_catchup": ["ok"],
            "top_priorities": [
                {
                    "text": "ping http://evil.example.com now",
                    "source_ids": ["c1"],
                    "confidence": 0.5,
                    "reason_code": "x",
                }
            ],
        }
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS, profiles=_profiles(), backend=StaticOutputClient(leaky), dry_run=True
    )
    assert result.enriched is False
    assert result.withheld_reason is not None
    assert result.withheld_reason.startswith("redaction_failed")


def test_model_unavailable_falls_back() -> None:
    # No backend injected + daemon unreachable (present_models=None) -> route blocked -> withheld.
    result = build_daily_brief_intelligence(
        candidates=CANDS, profiles=_profiles(), present_models=None, dry_run=True
    )
    assert result.enriched is False
    assert result.status == "model_unavailable"


def test_no_candidates_withheld() -> None:
    result = build_daily_brief_intelligence(
        candidates=[], profiles=_profiles(), backend=StaticOutputClient(GOOD_INTEL), dry_run=True
    )
    assert result.enriched is False
    assert result.withheld_reason == "no_candidates"


def test_raw_flag_does_not_widen_model_input() -> None:
    # allow_raw is reserved; the adapter still only consumes redacted candidate fields.
    result = build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        allow_raw=True,
    )
    assert result.enriched is True
    assert result.metrics["raw_allowed"] is True


def test_no_candidate_table_mutation(tmp_path) -> None:
    db = str(tmp_path / "intel.sqlite")
    store = ConstructionStore(db_path=db)
    # Dry-run with a real store must not write any candidate rows.
    build_daily_brief_intelligence(
        candidates=CANDS,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        store=store,
    )
    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM daily_brief_action_candidates").fetchone()[0]
    conn.close()
    assert count == 0


def test_cli_intelligence_offline_withholds_safely(tmp_path) -> None:
    db = str(tmp_path / "cli_intel.sqlite")
    ConstructionStore(db_path=db)  # migrate empty schema
    result = runner.invoke(
        app,
        [
            "second-brain",
            "daily-brief",
            "intelligence",
            "--date",
            "2026-06-09",
            "--mock",
            "--db",
            db,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    # No candidates in an empty DB -> withheld, deterministic fallback.
    assert payload["enriched"] is False
    assert payload["applied"] is False
