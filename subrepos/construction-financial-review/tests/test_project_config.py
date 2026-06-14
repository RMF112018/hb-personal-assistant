import json
from pathlib import Path

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
TROPICAL = SUBPROJECT_ROOT / "config" / "projects" / "tropical.json"


def test_tropical_config_loads():
    cfg = json.loads(TROPICAL.read_text(encoding="utf-8"))
    assert cfg["project_key"] == "tropical"
    assert cfg["job_reference"] == "23-435-01"
    assert cfg["forecast_period"] == "2026-June"


def test_tropical_config_approved_decisions():
    cfg = json.loads(TROPICAL.read_text(encoding="utf-8"))
    assert cfg["budget_amount_field"] == "budget_amounts.revised_budget"
    assert cfg["current_projected_cost_field"] == "budget_amounts.projected_costs"
    assert cfg["materiality_absolute"] == "25000.00"
    assert cfg["materiality_percent"] == "0.10"


def test_crosswalk_path_points_to_installed_file():
    cfg = json.loads(TROPICAL.read_text(encoding="utf-8"))
    rel = cfg["owner_sov_scope_crosswalk"]
    assert (SUBPROJECT_ROOT / rel).exists(), f"crosswalk not installed at {rel}"
