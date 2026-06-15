"""forecast_staffing_plan resolver: LAB-only unique resolution, ambiguity, acceptance gating."""
from construction_financial_review.forecast_staffing_plan import mapping as smap
from construction_financial_review.forecast_staffing_plan import staffing_schema as ss


def _canon(cost_code, roles_by_cat):
    """roles_by_cat: {category: role} -> canonical rows for one cost code."""
    return [{"budget_code_key": f"1000.{cost_code}.{cat}", "cost_code": cost_code, "category": cat,
             "budget_code_description": f"TROPICAL WORLD NURSERY-CONSTR.{role}.{cat}"}
            for cat, role in roles_by_cat.items()]


FAMILY = {"LAB": "SUPERINTENDENT 2", "LBN": "SUPERINTENDENT 2", "MAT": "SUPERINTENDENT 2"}


def _idx(rows):
    return smap.build_canonical_family_index(rows), {r["budget_code_key"] for r in rows}


def test_unique_lab_with_accepted_override_applies():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    overrides = {"10-01-314": [{"target_budget_code_key": "1000.10-01-314.LAB",
                                "acceptance_status": "accepted", "allocation_share": "1.0000"}]}
    r = smap.resolve_cost_code("10-01-314", fam, keys, overrides, require_acceptance=True)
    assert r["mapping_status"] == ss.M_OP_APPROVED
    assert r["numeric_target_budget_code_key"] == "1000.10-01-314.LAB"
    assert r["applied_numeric"] is True
    # the whole family is recorded as date-context targets
    assert set(r["date_context_target_budget_code_keys"]) == set(keys)


def test_unique_lab_pending_when_no_accepted_override_and_acceptance_required():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    r = smap.resolve_cost_code("10-01-314", fam, keys, {}, require_acceptance=True)
    assert r["mapping_status"] == ss.M_RESOLVED_PENDING
    assert r["applied_numeric"] is False


def test_unique_lab_applies_without_override_when_acceptance_not_required():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    r = smap.resolve_cost_code("10-01-314", fam, keys, {}, require_acceptance=False)
    assert r["mapping_status"] == ss.M_RESOLVED_PENDING
    assert r["applied_numeric"] is True
    assert r["numeric_target_budget_code_key"] == "1000.10-01-314.LAB"


def test_two_roles_is_ambiguous_and_unapplied():
    rows = _canon("10-01-999", {"LAB": "ROLE A"}) + _canon("10-01-999", {"LAB": "ROLE B"})
    fam, keys = _idx(rows)
    overrides = {"10-01-999": [{"target_budget_code_key": "1000.10-01-999.LAB",
                               "acceptance_status": "accepted"}]}
    r = smap.resolve_cost_code("10-01-999", fam, keys, overrides, require_acceptance=True)
    assert r["mapping_status"] == ss.M_AMBIGUOUS
    assert r["applied_numeric"] is False


def test_invented_override_target_fails_closed():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    overrides = {"10-01-314": [{"target_budget_code_key": "9999.99-99-999.LAB",
                               "acceptance_status": "accepted"}]}
    r = smap.resolve_cost_code("10-01-314", fam, keys, overrides, require_acceptance=True)
    assert r["mapping_status"] == ss.M_INVENTED
    assert r["applied_numeric"] is False


def test_override_disagrees_with_resolver_is_mismatch():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    # accepted override points at the .LBN (canonical) instead of the resolved .LAB
    overrides = {"10-01-314": [{"target_budget_code_key": "1000.10-01-314.LBN",
                               "acceptance_status": "accepted"}]}
    r = smap.resolve_cost_code("10-01-314", fam, keys, overrides, require_acceptance=True)
    assert r["mapping_status"] == ss.M_MISMATCH
    assert r["applied_numeric"] is False


def test_unmapped_cost_code():
    rows = _canon("10-01-314", FAMILY)
    fam, keys = _idx(rows)
    r = smap.resolve_cost_code("99-99-999", fam, keys, {}, require_acceptance=True)
    assert r["mapping_status"] == ss.M_UNMAPPED
    assert r["applied_numeric"] is False
