# Reviewer Code Map

## INDEPENDENT_METHODS
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:27: INDEPENDENT_METHODS = ("owner_progress_eac", "procore_progress_eac", "schedule_remaining_work_eac",`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:17: from .estimators_uncapped import INDEPENDENT_METHODS`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:76: if e["method"] in INDEPENDENT_METHODS and e["applicable"] and dec(e["eac"]) is not None]`

## each estimator
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:79: def owner_progress_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:95: def procore_progress_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:116: def schedule_remaining_work_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:138: def trend_projection_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:169: def commitment_exposure_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:190: def cpi_blend_eac(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:224: def erp_eac_reference(b: dict) -> OrderedDict:`

## reconciliation weighting
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:19: RELIABILITY_WEIGHT = {"high": Decimal("1.0"), "medium": Decimal("0.6"), "low": Decimal("0.3")}`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:65: def select_final(budget_code_key: str, project_key: str, estimates: list[dict], bundle: dict,`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:86: base = RELIABILITY_WEIGHT.get(e["reliability"], Decimal("0.3"))`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:105: ("effective_weight", str(w.quantize(Decimal("0.0001")))),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:157: contributions, key=lambda c: Decimal(c["effective_weight"]), reverse=True)]`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:192: recommendation = reconcile_final.select_final(key, project_key, ests, bundle, calibration)`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:733: ("reliability_weight_map", {"high": "1.0", "medium": "0.6", "low": "0.3"}),`

## actuals floor
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:1: """Uncapped EAC/ETC estimators. The ONLY clamp is the actuals floor.`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:52: ("floored_to_actuals", floored),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:69: ("floored_to_actuals", False),`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:527: enforces the actuals floor + window + manual + duplicate-conflict + acceptance gates, and emits applied`

## ERP reference treatment
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:29: REFERENCE_METHODS = ("erp_projected_reference", "erp_eac_reference")`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:75: ("note", label + " — REFERENCE ONLY; never weighted, never a cap or fallback floor."),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:195: modeled answer. ERP stays a labeled reference only.`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:220: def erp_projected_reference(b: dict) -> OrderedDict:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:221: return _reference("erp_projected_reference", b.get("projected_costs"), "ERP current projected cost")`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/estimators_uncapped.py:231: erp_projected_reference, erp_eac_reference)`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/reconcile_final.py:168: ("erp_projected_reference", money_str(projected) if projected is not None else None),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:773: "forecast_recommendations_by_budget_code.jsonl (crosswalk_v2) — read only, reference only"),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:1000: "`requires_human_acceptance` (always true). `erp_projected_reference` is reference only.",`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:1021: "- ERP projected cost is reference only — never a cap and never a fallback floor.",`

## cost-basis override/suppression
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:38: from ..forecast_cost_basis import apply as cost_basis_apply`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:156: # Dormant / closed-code suppression runs BEFORE phasing: a CLOSED - DO NOT USE code, or a code idle`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:159: dcfg = cfg.get("dormant_code_suppression") or {}`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:164: # Staffing/general-conditions signals for recent-zero-run suppression: the staffing code list and the`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:172: cost_basis_rows = []`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:194: # dormant / closed-code suppression (authoritative decision; emitted as the status file)`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:202: if decision["suppression_applied"]:`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:231: # and emit pre_cost_basis_model_* + cost_basis_status for downstream idempotency.`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:233: cb_decision = _apply_cost_basis_intel(key, bc, recommendation, dorm_dec)`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:234: cost_basis_rows.append(cost_basis_apply.build_cost_basis_audit_row(cb_decision))`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:258: write_json(out / "audit" / "dormant_code_suppression_audit.json",`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:261: for _r in cost_basis_rows:`

## time-series shadow estimator
- UNVERIFIED in targeted source set.

## statsforecast isolated runtime
- UNVERIFIED in targeted source set.

## readiness preflight
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:248: preflight_stability_seconds: float) -> int:`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:269: preflight_stability_seconds=preflight_stability_seconds)`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:286: preflight_stability_seconds: float,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:309: preflight_stability_seconds=preflight_stability_seconds, runs=runs, seed=seed,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:327: preflight_stability_seconds: float) -> int:`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:349: preflight_stability_seconds=preflight_stability_seconds)`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:366: preflight_stability_seconds: float,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:393: preflight_stability_seconds=preflight_stability_seconds,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:555: cost-loading readiness, GC/GR behavior + fee projected-budget cap, change-order exposure). Read-only`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:726: def cmd_db_cutover_readiness(*, data_root: str, work_root: str, context_stamp: str,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:728: """Controlled DB-cutover-readiness gate (Phase 10; evidence only).`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:730: Validates readiness prerequisites for the DB-backed context->analysis chain against an EXPLICIT`

## semantic gates
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py:813: "- `audit/*` — evidence_registry, evidence_weighting (no-double-count), history_consumption, "`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py:822: "collapsed with explicit reason codes; independence groups prevent double-counting.",`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/evidence_scoring.py:5: double-counting a signal that surfaces in several upstream packages. Cost-frequency may shape monthly`

## accuracy gate
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:34: from ..forecast_accuracy import signals`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:35: from ..forecast_accuracy.llm import narrate`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:37: from ..forecast_accuracy.llm.client import OllamaClient`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:49: PRIOR_ACCURACY_GLOB = "forecast_accuracy_package_tropical_*"`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:92: out = out_base / f"forecast_accuracy_next_package_tropical_{stamp}"`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:271: write_jsonl(out / "forecast_accuracy_next_by_budget_code.jsonl", accuracy_next)`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:319: ("prior_forecast_accuracy_package", str(prior_accuracy_pkg) if prior_accuracy_pkg else None),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:393: rec_file = prior_pkg / "forecast_accuracy_recommendations.jsonl"`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:759: ("prior_forecast_accuracy_package", str(prior_pkg) if prior_pkg else None),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:770: ("prior_forecast_accuracy_package", str(prior_pkg) if prior_pkg else None),`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:949: f"# forecast_accuracy_next_package_tropical ({meta['package_stamp']})",`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py:714: from ..forecast_accuracy.llm import narrate`

## package generation
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_intelligence/generate_forecast_intelligence_package.py:47: GENERATOR_NAME = "construction_financial_review.forecast_intelligence.generate_forecast_intelligence_package"`
- `subrepos/construction-financial-review/src/construction_financial_review/forecast_comprehensive/generate_comprehensive_forecast_package.py:482: from ..forecast_cost_frequency import generate_forecast_cost_frequency_package as fcfgen`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:42: "run-context": Path(__file__).parent / "context" / "generate_forecast_context_package.py",`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:43: "run-analysis": Path(__file__).parent / "analysis" / "generate_forecast_analysis_package.py",`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:45: "run-crosswalk-v2": Path(__file__).parent / "analysis" / "generate_forecast_analysis_crosswalk_v2.py",`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:143: def cmd_forecast_config_import(*, project: str, config_root: str, db_path: str,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:162: def cmd_forecast_config_snapshot(*, project: str, db_path: str, snapshot_name: str,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:188: def cmd_forecast_config_export(*, project: str, db_path: str, snapshot_id: str | None,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:207: def cmd_forecast_model_controls_db_config_proof(*, project: str, live_db_path: str,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:222: run_forecast_model_controls_db_config_proof,`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:226: report = run_forecast_model_controls_db_config_proof(`
- `subrepos/construction-financial-review/src/construction_financial_review/cli.py:242: def cmd_forecast_monthly_db_config_proof(*, project: str, live_db_path: str,`
