"""Advisory forecast narratives from deterministic facts.

Builds prompts from numeric facts only, calls a generation backend, validates the JSON against a
fixed schema, safety-scans the output, and FALLS BACK to a deterministic template on any failure
(unavailable / invalid / unsafe). Emits hash-only receipts. Never produces a recommended number.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from typing import Optional

from ...common.hashing import sha256_text
from ...common.safety import FAIL_CATEGORIES, scan_text
from .backend import GenerationBackend
from .client import OllamaUnavailable

SYSTEM_PROMPT = (
    "You are a construction cost-forecast review assistant. You receive ONLY pre-computed numeric "
    "facts about one budget code. Explain them for a human reviewer. You MUST NOT invent or change "
    "any number, and you MUST NOT recommend a specific cost figure. Use only the provided facts. "
    "Return ONLY a JSON object with keys: forecast_rationale (string), top_risks (array of strings), "
    "review_questions (array of strings), mapping_disambiguation_suggestion (string or null), "
    "qualitative_confidence (one of \"low\",\"medium\",\"high\"). No prose outside the JSON."
)

REQUIRED_KEYS = ("forecast_rationale", "top_risks", "review_questions",
                 "mapping_disambiguation_suggestion", "qualitative_confidence")
MAX_OUTPUT_CHARS = 4000


def build_facts(bundle: dict, reconciliation: dict, confidence: dict, adequacy: dict) -> OrderedDict:
    """Deterministic numeric facts handed to the model (no raw payloads, no secrets)."""
    return OrderedDict([
        ("project_key", bundle.get("project_key")),
        ("budget_code_key", bundle.get("budget_code_key")),
        ("budget_code_description", bundle.get("budget_code_description")),
        ("actual_cost_all_source_to_date", bundle.get("actual_cost_all_source_to_date")),
        ("erp_projected_costs", reconciliation.get("erp_projected_costs")),
        ("model_recommended_projected_cost", reconciliation.get("model_recommended_projected_cost")),
        ("model_reconciled_eac", reconciliation.get("model_reconciled_eac")),
        ("model_eac_low", reconciliation.get("model_eac_low")),
        ("model_eac_high", reconciliation.get("model_eac_high")),
        ("model_divergence", reconciliation.get("model_divergence")),
        ("n_independent_models", reconciliation.get("n_independent_models")),
        ("reconciliation_basis", reconciliation.get("reconciliation_basis")),
        ("forecast_adequacy", adequacy.get("forecast_adequacy")),
        ("adequacy_severity", adequacy.get("adequacy_severity")),
        ("calibrated_confidence", confidence.get("calibrated_confidence")),
        ("confidence_band", confidence.get("confidence_band")),
        ("owner_latest_percent_complete", bundle.get("owner_latest_percent_complete")),
        ("schedule_remaining_work_status", bundle.get("schedule_remaining_work_status")),
        ("schedule_open_activity_count", bundle.get("schedule_open_activity_count")),
        ("evidence_depth", bundle.get("evidence_depth")),
    ])


def render_template(facts: dict) -> OrderedDict:
    """Deterministic narrative used in mock mode and as the fail-closed fallback."""
    adequacy = facts.get("forecast_adequacy")
    erp = facts.get("erp_projected_costs")
    model = facts.get("model_recommended_projected_cost")
    rationale = (
        f"ERP projected cost is {erp} vs an independent model-reconciled forecast of {model} "
        f"({facts.get('n_independent_models')} independent model(s); adequacy: {adequacy}). "
        f"Calibrated confidence {facts.get('calibrated_confidence')} ({facts.get('confidence_band')})."
    )
    risks = []
    if adequacy == "likely_low":
        risks.append("ERP forecast appears low versus independent estimates; potential under-forecast.")
    elif adequacy == "likely_high":
        risks.append("ERP forecast appears high versus independent estimates; potential over-forecast.")
    if facts.get("schedule_remaining_work_status") == "material_remaining_work":
        risks.append("Material remaining schedule work indicates continued cost exposure.")
    if not risks:
        risks.append("No material model-vs-ERP divergence detected.")
    questions = [
        "Does the ERP projected cost reflect the latest committed and change-order scope?",
        "Are there known cost events not yet captured in actuals or commitments?",
    ]
    disambig = None
    if facts.get("reconciliation_basis") == "erp_baseline_only":
        disambig = "No independent evidence; treat the model number as ERP-derived only."
    conf_band = facts.get("confidence_band")
    qual = "high" if conf_band in ("high", "very_high") else ("low" if conf_band in ("low", "very_low") else "medium")
    return OrderedDict([
        ("forecast_rationale", rationale),
        ("top_risks", risks),
        ("review_questions", questions),
        ("mapping_disambiguation_suggestion", disambig),
        ("qualitative_confidence", qual),
    ])


def _validate(raw: str) -> tuple[bool, str, Optional[OrderedDict]]:
    if len(raw) > MAX_OUTPUT_CHARS:
        return False, "output_too_large", None
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return False, "invalid_json", None
    if not isinstance(obj, dict):
        return False, "not_object", None
    for k in REQUIRED_KEYS:
        if k not in obj:
            return False, "schema_missing_field", None
    if not isinstance(obj.get("forecast_rationale"), str):
        return False, "schema_bad_rationale", None
    for lk in ("top_risks", "review_questions"):
        v = obj.get(lk)
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return False, "schema_bad_list", None
    md = obj.get("mapping_disambiguation_suggestion")
    if md is not None and not isinstance(md, str):
        return False, "schema_bad_disambig", None
    if obj.get("qualitative_confidence") not in ("low", "medium", "high"):
        return False, "schema_bad_confidence", None
    norm = OrderedDict([
        ("forecast_rationale", obj["forecast_rationale"][:2000]),
        ("top_risks", [s[:400] for s in obj["top_risks"]][:8]),
        ("review_questions", [s[:400] for s in obj["review_questions"]][:8]),
        ("mapping_disambiguation_suggestion", md[:600] if isinstance(md, str) else None),
        ("qualitative_confidence", obj["qualitative_confidence"]),
    ])
    return True, "ok", norm


def _is_safe(narrative: dict) -> bool:
    counts = scan_text(json.dumps(narrative, ensure_ascii=False))
    return all(counts.get(c, 0) == 0 for c in FAIL_CATEGORIES)


def narrate_one(facts: dict, backend: Optional[GenerationBackend], model_label: str) -> tuple[OrderedDict, OrderedDict]:
    """Return (narrative_row, receipt_row). Mock when backend is None; fail-closed to template."""
    facts_json = json.dumps(facts, ensure_ascii=False, sort_keys=True)
    input_hash = sha256_text(facts_json)[:12]
    key = facts.get("budget_code_key")

    def _finish(narrative, source, status, fallback_used):
        safe = _is_safe(narrative)
        if not safe:
            narrative = render_template(facts)
            source, status, fallback_used = "deterministic_template", "unsafe_output_blocked", True
        out = OrderedDict([("project_key", facts.get("project_key")), ("budget_code_key", key),
                           ("source", source)])
        out.update(narrative)
        receipt = OrderedDict([
            ("budget_code_key", key), ("source", source), ("model", model_label),
            ("status", status), ("fallback_used", fallback_used),
            ("input_facts_hash", input_hash),
            ("output_hash", sha256_text(json.dumps(narrative, ensure_ascii=False, sort_keys=True))[:12]),
            ("safety_passed", _is_safe(narrative)),
        ])
        return out, receipt

    if backend is None:
        return _finish(render_template(facts), "deterministic_template", "mock", False)

    prompt = ("Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, indent=0)
              + "\n\nReturn the required JSON object only.")
    try:
        raw = backend.generate_json(system=SYSTEM_PROMPT, prompt=prompt)
    except OllamaUnavailable as exc:
        return _finish(render_template(facts), "deterministic_template", str(exc) or "unavailable", True)
    ok, code, norm = _validate(raw)
    if not ok or norm is None:
        return _finish(render_template(facts), "deterministic_template", code, True)
    return _finish(norm, f"ollama:{model_label}", "ok", False)
