"""Coverage for the two forecast_monthly cleanup patches:
(a) determinism.frozen_stamp is recorded (not null) on a frozen run; and
(b) monthly_project_forecast.jsonl splits the overrun count into cumulative vs material ($25k AND 10%).

Skips when the local forecast data root / required packages are not present.
"""
from pathlib import Path

import pytest

from construction_financial_review.common.io import read_json, read_jsonl
from construction_financial_review.forecast_monthly import generate_monthly_forecast_package as gen

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CFG = read_json(SUBPROJECT_ROOT / "config" / "projects" / "tropical.json")
DATA_ROOT = Path(CFG["default_data_root"])

pytestmark = pytest.mark.skipif(
    not (DATA_ROOT.is_dir() and list(DATA_ROOT.glob("forecast_accuracy_next_package_tropical_*"))
         and list(DATA_ROOT.glob("forecast_context_package_tropical_*"))),
    reason="local forecast data root / required packages not present",
)

STAMP = "20260101_000000"


def _generate(tmp_path):
    res = gen.generate("tropical", CFG, data_root=DATA_ROOT, frozen_stamp=STAMP,
                       out_root=tmp_path, with_llm=False)
    return Path(res["output_package"])


def test_determinism_frozen_stamp_recorded(tmp_path):
    out = _generate(tmp_path)
    det = read_json(out / "validation_report.json")["determinism"]
    assert det["frozen_stamp"] == STAMP
    assert det["diff_result"] == "pass"


def test_overrun_count_fields_split_and_material_le_cumulative(tmp_path):
    out = _generate(tmp_path)
    rows = list(read_jsonl(out / "monthly_project_forecast.jsonl"))
    assert rows
    for r in rows:
        assert "number_of_overrun_budget_codes" not in r
        assert "number_of_cumulative_codes_exceeding_current_projected_cost" in r
        assert "number_of_material_projected_overrun_codes" in r
        cumulative = r["number_of_cumulative_codes_exceeding_current_projected_cost"]
        material = r["number_of_material_projected_overrun_codes"]
        assert 0 <= material <= cumulative
