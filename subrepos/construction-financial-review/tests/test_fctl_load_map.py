"""forecast_controls: parsing, duplicate detection, required fields, and canonical mapping."""
from __future__ import annotations

import json
from pathlib import Path

from construction_financial_review.forecast_controls import load_controls
from construction_financial_review.forecast_controls import mapping as cmap

SUBROOT = Path(__file__).resolve().parents[1]

BASE = {
    "project_key": "tropical", "control_id": "c1", "budget_code_key": "1000.15-07-590.SUB",
    "cost_code": "15-07-590", "control_type": "closeout_stop_date", "forecast_stop_date": "2026-07-31",
    "acceptance_status": "pending", "requires_human_acceptance": True, "accepted_by": None,
    "accepted_at": None, "acceptance_notes": None, "source": "operator_decision", "reason": "r",
}


def _write(tmp_path, rows) -> dict:
    p = tmp_path / "controls.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return {"forecast_controls": {"enabled": True, "control_file": str(p)}}


def test_parse_controls_jsonl(tmp_path):
    cfg = _write(tmp_path, [BASE])
    res = load_controls.load(cfg, SUBROOT)
    assert res["present"] and res["parse_ok"] and res["structurally_valid"]
    assert res["control_count"] == 1


def test_duplicate_control_id_fails(tmp_path):
    cfg = _write(tmp_path, [BASE, {**BASE, "control_id": "c1"}])
    res = load_controls.load(cfg, SUBROOT)
    assert res["duplicate_control_ids"] == ["c1"]
    assert res["structurally_valid"] is False


def test_missing_acceptance_fields_fails(tmp_path):
    bad = {k: v for k, v in BASE.items() if k != "acceptance_status"}
    cfg = _write(tmp_path, [bad])
    res = load_controls.load(cfg, SUBROOT)
    assert res["controls_missing_required_fields"]
    assert res["structurally_valid"] is False


def test_unparseable_line_fails(tmp_path):
    p = tmp_path / "controls.jsonl"
    p.write_text('{"control_id": "c1"\n', encoding="utf-8")  # truncated json
    cfg = {"forecast_controls": {"enabled": True, "control_file": str(p)}}
    res = load_controls.load(cfg, SUBROOT)
    assert res["parse_ok"] is False


def test_budget_code_key_mapping_succeeds():
    canon = {"1000.15-07-590.SUB", "1000.10-01-100.LAB"}
    idx = cmap.cost_code_to_keys(canon)
    m = cmap.map_control(BASE, canon, idx)
    assert m["mapping_status"] == cmap.M_EXPLICIT
    assert m["mapped_budget_code_key"] == "1000.15-07-590.SUB"


def test_invented_budget_code_key_fails():
    canon = {"1000.10-01-100.LAB"}
    idx = cmap.cost_code_to_keys(canon)
    m = cmap.map_control({**BASE, "budget_code_key": "9999.99-99-999.SUB"}, canon, idx)
    assert m["mapping_status"] == cmap.M_INVENTED
    assert m["mapped_budget_code_key"] is None


def test_cost_code_only_unique_resolves():
    canon = {"1000.15-07-590.SUB", "1000.10-01-100.LAB"}
    idx = cmap.cost_code_to_keys(canon)
    ctrl = {**BASE, "budget_code_key": None}
    m = cmap.map_control(ctrl, canon, idx)
    assert m["mapping_status"] == cmap.M_RESOLVED
    assert m["mapped_budget_code_key"] == "1000.15-07-590.SUB"


def test_cost_code_only_ambiguous_fails():
    canon = {"1000.15-07-590.SUB", "2000.15-07-590.SUB"}
    idx = cmap.cost_code_to_keys(canon)
    ctrl = {**BASE, "budget_code_key": None}
    m = cmap.map_control(ctrl, canon, idx)
    assert m["mapping_status"] == cmap.M_AMBIGUOUS
    assert m["mapped_budget_code_key"] is None
    assert len(m["candidate_budget_code_keys"]) == 2
