from pathlib import Path

from construction_financial_review.mapping.validate_owner_sov_scope_crosswalk import validate

SUBPROJECT_ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = (SUBPROJECT_ROOT / "config" / "crosswalks" / "tropical"
             / "owner_sov_scope_crosswalk_tropical_authoritative_20260614_final.jsonl")


def test_installed_crosswalk_present():
    assert CROSSWALK.exists(), f"missing installed crosswalk: {CROSSWALK}"


def test_structural_and_fact_checks_pass():
    # No context package supplied here -> coverage checks skipped; structural + fact checks must pass.
    report = validate(CROSSWALK)
    checks = report["checks"]
    assert report["passed"] is True, report["errors"]
    assert checks["crosswalk_row_count"] == 58
    assert checks["no_duplicate_crosswalk_id"] is True
    assert checks["no_blank_owner_sov_code"] is True
    assert checks["owner_10xx_two_description_sensitive_rows"] is True


def test_required_mapping_facts():
    checks = validate(CROSSWALK)["checks"]
    assert checks["map_20_18_105"] is True       # -> 1000.20-18-170.MAT
    assert checks["map_99_01_790"] is True       # -> 1000.90-01-300.MAT
    assert checks["map_15_01_426"] is True        # -> 1000.15-01-426.MAT
    assert checks["map_15_01_530"] is True        # LAB/LBN/MAT/SUB
    assert checks["map_15_01_xxx_excludes_426_530"] is True
    assert checks["zero_unresolved_owner_sov_rows"] is True
