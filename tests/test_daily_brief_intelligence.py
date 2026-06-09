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
    # --db override is echoed (redacted) so the operator can confirm it ran against a copy.
    assert payload["db_mode"] == "explicit_db"
    assert payload["db_path_redacted"] == db
    # selected_profile is the route-selected profile; terminal/profile_id is the generation profile.
    assert "route_selected_profile" in payload
    assert "terminal_profile_id" in payload
    # warnings/blockers are always arrays.
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["blockers"], list)


# -- Candidate availability / dry-run semantics (Phase 10 remediation) -----------------------

CANDS_DATED = [
    {**CANDS[0], "created_utc": "2026-06-09T05:00:00+00:00"},
    {**CANDS[1], "created_utc": "2026-06-09T05:00:00+00:00"},
]


def test_no_candidate_availability_warns_and_requires_apply() -> None:
    result = build_daily_brief_intelligence(
        candidates=[],
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        brief_date="2026-06-09",
        generation_mode="read_only",
    )
    assert result.candidate_count == 0
    assert result.candidate_freshness == "none"
    assert "no_persisted_candidates_for_date" in result.warnings
    assert "requires_daily_run_apply_to_generate_candidates" in result.warnings
    assert result.candidate_availability["requires_apply_for_fresh_candidates"] is True


def test_standalone_reads_preexisting_candidates_warning() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_DATED,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        brief_date="2026-06-09",
        generation_mode="read_only",
    )
    assert result.candidate_count == 2
    assert result.candidate_freshness == "current"
    assert "standalone_reads_preexisting_candidates_only" in result.warnings
    av = result.candidate_availability
    assert av["candidate_generation_mode"] == "read_only"
    assert av["candidate_source"] == "daily_brief_action_candidates"


def test_dry_run_pipeline_candidate_warning() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_DATED,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        brief_date="2026-06-09",
        generation_mode="pipeline_dry_run",
    )
    assert "dry_run_did_not_persist_new_candidates" in result.warnings
    assert "intelligence_reflects_preexisting_candidates" in result.warnings
    assert result.candidate_availability["requires_apply_for_fresh_candidates"] is True


def test_apply_pipeline_does_not_require_apply() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_DATED,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=False,
        brief_date="2026-06-09",
        generation_mode="pipeline_apply",
    )
    av = result.candidate_availability
    assert av["candidate_generation_mode"] == "pipeline_apply"
    assert av["requires_apply_for_fresh_candidates"] is False
    assert "dry_run_did_not_persist_new_candidates" not in result.warnings


def test_candidate_date_mismatch_warns_preexisting() -> None:
    # created_utc predates the requested brief_date -> preexisting + mismatch warning.
    stale = [{**CANDS[0], "created_utc": "2026-05-01T05:00:00+00:00"}]
    result = build_daily_brief_intelligence(
        candidates=stale,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        brief_date="2026-06-09",
        generation_mode="read_only",
    )
    assert result.candidate_freshness == "preexisting"
    assert "candidate_rows_predate_requested_brief_date" in result.warnings


def test_candidate_availability_keys_in_safe_payload() -> None:
    sp = build_daily_brief_intelligence(
        candidates=CANDS_DATED,
        profiles=_profiles(),
        backend=StaticOutputClient(GOOD_INTEL),
        dry_run=True,
        brief_date="2026-06-09",
    ).safe_payload()
    assert sp["candidate_count"] == 2
    assert "candidate_freshness" in sp
    for key in (
        "candidate_count",
        "candidate_brief_date",
        "candidate_source",
        "candidate_generation_mode",
        "candidate_freshness",
        "requires_apply_for_fresh_candidates",
        "dry_run_candidate_warning",
    ):
        assert key in sp["candidate_availability"]


# -- Schema repair + source-link hardening (Phase 10 remediation) ----------------------------
# Canonical ids use the real 37-char `dbac-<hex>` shape so alias mapping is exercised distinctly
# from the short ids used elsewhere in this module.

CANDS_HEX = [
    {
        "daily_brief_action_candidate_id": "dbac-44e6ceaef1c24603cd0261789cd58419",
        "section": "actions",
        "title_redacted": "Send transmittal",
        "project_key": "P1",
        "confidence": 0.8,
        "recommended_next_action": "review",
    },
    {
        "daily_brief_action_candidate_id": "dbac-f8c7c12bb9db803dfad82addfcb92df3",
        "section": "waiting",
        "title_redacted": "Look-ahead pending",
        "project_key": "P2",
        "confidence": 0.6,
        "recommended_next_action": "review",
    },
]
_HEX0 = CANDS_HEX[0]["daily_brief_action_candidate_id"]
_HEX1 = CANDS_HEX[1]["daily_brief_action_candidate_id"]


def _intel_citing(*source_id_lists: list[str]) -> str:
    bullets = [
        {"text": f"bullet {i}", "source_ids": sids, "confidence": 0.7, "reason_code": "x"}
        for i, sids in enumerate(source_id_lists)
    ]
    return json.dumps({"executive_catchup": ["ok"], "top_priorities": bullets})


def test_alias_ids_mapped_to_canonical() -> None:
    # Model cites the short alias c1; the filter maps it back to the canonical hex id.
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(_intel_citing(["c1"])),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.intelligence["top_priorities"][0]["source_ids"] == [_HEX0]
    assert result.metrics["alias_mapping_used"] is True
    assert result.metrics["source_link_coverage"] == 1.0


def test_canonical_ids_still_accepted() -> None:
    # Model echoes the canonical hex id directly; still accepted (no alias resolution needed).
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(_intel_citing([_HEX1])),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.intelligence["top_priorities"][0]["source_ids"] == [_HEX1]
    assert result.metrics["alias_mapping_used"] is False


def test_unknown_source_ids_counted_and_dropped() -> None:
    # One bullet cites a real alias + an unknown id; one bullet cites only unknown ids.
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(_intel_citing(["c1", "c99"], ["c98"])),
        dry_run=True,
    )
    assert result.enriched is True
    tp = result.intelligence["top_priorities"]
    assert len(tp) == 1  # the all-unknown bullet was dropped
    assert tp[0]["source_ids"] == [_HEX0]
    assert result.metrics["unknown_source_ids_count"] == 2  # c99 + c98
    assert result.metrics["bullets_dropped"] == 1
    assert result.metrics["model_bullets_seen"] == 2


def test_all_unsourced_withheld_with_diagnostics() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(_intel_citing(["nope"], ["also_nope"])),
        dry_run=True,
    )
    assert result.enriched is False
    assert result.withheld_reason == "no_source_linked_bullets"
    assert result.metrics["unknown_source_ids_count"] == 2
    assert result.metrics["model_bullets_seen"] == 2
    assert result.metrics["allowed_candidate_count"] == 2


def test_partial_source_linked_enriches_with_full_coverage() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(_intel_citing(["c1"], ["unknown"])),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.metrics["bullets_kept"] == 1
    assert result.metrics["bullets_dropped"] == 1
    assert result.metrics["source_link_coverage"] == 1.0


def test_schema_invalid_reports_safe_diagnostics() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient("not json {"),
        dry_run=True,
    )
    assert result.enriched is False
    assert result.metrics["schema_error_category"] == "schema_invalid"
    assert result.metrics["attempts"] >= 2
    assert result.metrics["repair_attempted"] is True
    # No raw model error text leaks (only bounded category + structural counters).
    from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
        scan_text_for_forbidden,
    )

    assert scan_text_for_forbidden(json.dumps(result.safe_payload())) == []


def test_repair_recovers_after_one_bad_output() -> None:
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(outputs=["bad json {", _intel_citing(["c1"])]),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.attempts == 2
    assert result.fallback_used is False


def test_bare_array_top_level_is_coerced() -> None:
    # Model returns a bare JSON array of bullets (common JSON-mode failure) instead of an object.
    arr = json.dumps(
        [{"text": "ship it", "source_ids": ["c1"], "confidence": 0.8, "reason_code": "x"}]
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX, profiles=_profiles(), backend=StaticOutputClient(arr), dry_run=True
    )
    assert result.enriched is True
    assert result.intelligence["top_priorities"][0]["source_ids"] == [_HEX0]


def test_executive_catchup_string_is_coerced_not_rejected() -> None:
    # The 12B model commonly returns executive_catchup as a prose STRING (not a list). The whole
    # object must still validate (string wrapped into a single-element list), not fail schema-invalid.
    payload = json.dumps(
        {
            "executive_catchup": "Two loops are waiting on others; one item is due today.",
            "top_priorities": [
                {"text": "ship it", "source_ids": ["c1"], "confidence": 0.8, "reason_code": "x"}
            ],
        }
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX,
        profiles=_profiles(),
        backend=StaticOutputClient(payload),
        dry_run=True,
    )
    assert result.enriched is True
    assert result.schema_valid is True
    assert result.intelligence["executive_catchup"] == [
        "Two loops are waiting on others; one item is due today."
    ]
    assert result.intelligence["top_priorities"][0]["source_ids"] == [_HEX0]


def test_single_key_envelope_is_unwrapped() -> None:
    env = json.dumps(
        {
            "daily_brief_intelligence": {
                "executive_catchup": ["ok"],
                "top_priorities": [
                    {"text": "ship it", "source_ids": ["c2"], "confidence": 0.7, "reason_code": "x"}
                ],
            }
        }
    )
    result = build_daily_brief_intelligence(
        candidates=CANDS_HEX, profiles=_profiles(), backend=StaticOutputClient(env), dry_run=True
    )
    assert result.enriched is True
    assert result.intelligence["top_priorities"][0]["source_ids"] == [_HEX1]
