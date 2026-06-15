"""Shared minimal `inputs` factory for forecast_improvement_audit unit tests."""
from collections import OrderedDict

FEE_KEY = "1000.20-18-110.OVH"
NONFEE_KEY = "1000.15-03-100.SUB"


def budget_entry(key, cost_code, desc, **amounts):
    return {
        "budget_code_key": key, "cost_code": cost_code, "budget_code_description": desc,
        "amounts": dict(amounts),
    }


def minimal_inputs(**over):
    base = OrderedDict([
        ("project_key", "tropical"),
        ("data_root", "/tmp/nonexistent_data_root"),
        ("discovery", OrderedDict([
            ("context", {"present": True, "path": "/tmp/nonexistent_data_root/ctx",
                         "package_name": "ctx", "required": True, "manifest_present": True}),
            ("intelligence", {"present": True, "path": "/tmp/nonexistent_data_root/acc",
                              "package_name": "acc", "required": True, "manifest_present": True}),
        ])),
        ("budget_codes", []),
        ("budget_by_key", {}),
        ("monthly_actuals", []),
        ("latest_sub_invoice_by_key", {}),
        ("owner_pay_totals", []),
        ("accuracy_by_key", {}),
        ("recommendations_by_key", {}),
        ("trend_by_key", {}),
        ("sched_evidence_by_key", {}),
        ("backtest", None),
        ("calibration_summary", None),
        ("monthly_conf_by_key", {}),
        ("prob_backtest", None),
        ("code_overrun", []),
        ("schedule_activities", []),
        ("gcgr_line_summary", []),
        ("gcgr_monthly", []),
        ("cf_code_rows", []),
        ("db", {"db_present": True, "change_orders": [], "contracts": []}),
        ("db_schema_inventory", OrderedDict([("db_present", True), ("tables", [])])),
        ("source_files", []),
    ])
    base.update(over)
    return base
