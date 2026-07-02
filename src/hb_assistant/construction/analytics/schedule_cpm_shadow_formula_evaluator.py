"""Independent shadow CPM formula evaluator for formula-trace evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_OFFSET_DECIMALS = 6
_FLOAT_TOL = 1e-6
_SUPPORTED = frozenset({"FS", "SS", "FF", "SF"})

FORMULA_EXPRESSIONS = {
    "forward_FS": "ES_successor = EF_predecessor + lag",
    "forward_SS": "ES_successor = ES_predecessor + lag",
    "forward_FF": "ES_successor = EF_predecessor + lag - duration_successor",
    "forward_SF": "ES_successor = ES_predecessor + lag - duration_successor",
    "backward_FS": "LF_predecessor = LS_successor - lag",
    "backward_FF": "LF_predecessor = LF_successor - lag",
    "backward_SS": "LS_predecessor = LS_successor - lag; LF = LS + duration",
    "backward_SF": "LS_predecessor = LF_successor - lag; LF = LS + duration",
    "total_float": "LS - ES",
    "free_float_FS": "ES_successor - EF_predecessor - lag",
    "free_float_SS": "ES_successor - ES_predecessor - lag",
    "free_float_FF": "EF_successor - EF_predecessor - lag",
    "free_float_SF": "EF_successor - ES_predecessor - lag",
}


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, _OFFSET_DECIMALS)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ShadowCandidate:
    relationship_id: str
    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None
    lag_days: float
    candidate_value: float | None
    formula_expression: str
    pass_name: str


@dataclass
class ShadowCandidateEvaluation:
    pass_name: str
    candidate_count: int
    selected_candidate_id: str | None
    selected_value: float | None
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    tie_break_applied: bool = False
    tie_break_rule: str = "max_value_then_relationship_id"


@dataclass
class ShadowActivityResult:
    activity_id: str
    early_start: float | None = None
    early_finish: float | None = None
    late_start: float | None = None
    late_finish: float | None = None
    total_float: float | None = None
    free_float: float | None = None
    criticality_class: str | None = None
    forward_evaluation: ShadowCandidateEvaluation | None = None
    backward_evaluation: ShadowCandidateEvaluation | None = None


@dataclass
class ShadowRelationshipResult:
    relationship_id: str
    predecessor_activity_id: str
    successor_activity_id: str
    relationship_type: str | None
    lag_days: float
    forward_candidate_es: float | None = None
    forward_formula: str | None = None
    backward_candidate_lf: float | None = None
    backward_candidate_ls: float | None = None
    backward_formula: str | None = None
    free_float_candidate: float | None = None
    free_float_formula: str | None = None


class CpmShadowFormulaEvaluator:
    """Shadow evaluator with explicit formula strings and candidate audit trails."""

    def evaluate_forward_candidate(
        self,
        *,
        rel_type: str | None,
        lag_days: float,
        pred_es: float | None,
        pred_ef: float | None,
        succ_duration: float | None,
    ) -> tuple[float | None, str]:
        if rel_type not in _SUPPORTED:
            return None, "unsupported_relationship_type"
        lag = lag_days or 0.0
        if rel_type == "SS":
            return _round((pred_es or 0.0) + lag), FORMULA_EXPRESSIONS["forward_SS"]
        if rel_type == "FS":
            if pred_ef is None:
                return None, "blocked_predecessor_no_finish"
            return _round(pred_ef + lag), FORMULA_EXPRESSIONS["forward_FS"]
        if succ_duration is None:
            return None, "successor_duration_unknown"
        if rel_type == "FF":
            if pred_ef is None:
                return None, "blocked_predecessor_no_finish"
            return _round(pred_ef + lag - succ_duration), FORMULA_EXPRESSIONS["forward_FF"]
        return _round((pred_es or 0.0) + lag - succ_duration), FORMULA_EXPRESSIONS["forward_SF"]

    def evaluate_backward_candidate(
        self,
        *,
        rel_type: str | None,
        lag_days: float,
        pred_duration: float | None,
        succ_ls: float | None,
        succ_lf: float | None,
    ) -> tuple[float | None, float | None, str]:
        if rel_type not in _SUPPORTED:
            return None, None, "unsupported_relationship_type"
        lag = lag_days or 0.0
        if rel_type in ("FS", "SS") and succ_ls is None:
            return None, None, "blocked_successor_no_late_start"
        if rel_type in ("FF", "SF") and succ_lf is None:
            return None, None, "blocked_successor_no_late_finish"
        if rel_type == "FS":
            cand_lf = succ_ls - lag
            cand_ls = cand_lf - pred_duration if pred_duration is not None else None
            return _round(cand_ls), _round(cand_lf), FORMULA_EXPRESSIONS["backward_FS"]
        if rel_type == "FF":
            cand_lf = succ_lf - lag
            cand_ls = cand_lf - pred_duration if pred_duration is not None else None
            return _round(cand_ls), _round(cand_lf), FORMULA_EXPRESSIONS["backward_FF"]
        if pred_duration is None:
            return None, None, "predecessor_duration_unknown"
        cand_ls = (succ_ls - lag) if rel_type == "SS" else (succ_lf - lag)
        cand_lf = cand_ls + pred_duration
        expr = FORMULA_EXPRESSIONS["backward_SS" if rel_type == "SS" else "backward_SF"]
        return _round(cand_ls), _round(cand_lf), expr

    def evaluate_free_float_candidate(
        self,
        *,
        rel_type: str | None,
        lag_days: float,
        pred_es: float | None,
        pred_ef: float | None,
        succ_es: float | None,
        succ_ef: float | None,
    ) -> tuple[float | None, str]:
        if rel_type not in _SUPPORTED:
            return None, "unsupported_relationship_type"
        lag = lag_days or 0.0
        if rel_type == "FS":
            if succ_es is None or pred_ef is None:
                return None, "missing_successor_early_values"
            return _round(succ_es - pred_ef - lag), FORMULA_EXPRESSIONS["free_float_FS"]
        if rel_type == "SS":
            if succ_es is None or pred_es is None:
                return None, "missing_successor_early_values"
            return _round(succ_es - pred_es - lag), FORMULA_EXPRESSIONS["free_float_SS"]
        if rel_type == "FF":
            if succ_ef is None or pred_ef is None:
                return None, "missing_successor_early_values"
            return _round(succ_ef - pred_ef - lag), FORMULA_EXPRESSIONS["free_float_FF"]
        if succ_ef is None or pred_es is None:
            return None, "missing_successor_early_values"
        return _round(succ_ef - pred_es - lag), FORMULA_EXPRESSIONS["free_float_SF"]

    @staticmethod
    def evaluate_total_float(
        es: float | None, ls: float | None, ef: float | None, lf: float | None
    ) -> float | None:
        start_tf = ls - es if (ls is not None and es is not None) else None
        finish_tf = lf - ef if (lf is not None and ef is not None) else None
        if start_tf is not None and finish_tf is not None:
            if abs(start_tf - finish_tf) <= _FLOAT_TOL:
                return _round(start_tf)
            return _round(start_tf)
        if start_tf is not None:
            return _round(start_tf)
        if finish_tf is not None:
            return _round(finish_tf)
        return None

    @staticmethod
    def evaluate_criticality(
        total_float: float | None,
        *,
        critical_threshold: float = 0.0,
        near_critical_threshold: float = 10.0,
        tolerance: float = _FLOAT_TOL,
    ) -> str | None:
        if total_float is None:
            return "unclassified"
        if total_float <= critical_threshold + tolerance:
            return "computed_critical"
        if total_float <= near_critical_threshold + tolerance:
            return "computed_near_critical"
        return "computed_noncritical"

    def select_max_candidates(
        self,
        candidates: list[ShadowCandidate],
        *,
        pass_name: str = "forward",
    ) -> ShadowCandidateEvaluation:
        valid = [c for c in candidates if c.candidate_value is not None]
        if not valid:
            return ShadowCandidateEvaluation(
                pass_name=pass_name,
                candidate_count=len(candidates),
                selected_candidate_id=None,
                selected_value=None,
            )
        ordered = sorted(
            valid,
            key=lambda c: (-(c.candidate_value or 0), c.relationship_id),
        )
        selected = ordered[0]
        rejected: list[dict[str, Any]] = []
        tie_break = (
            len(ordered) > 1 and ordered[0].candidate_value == ordered[1].candidate_value
        )
        for c in ordered[1:]:
            rejected.append(
                {
                    "relationship_id": c.relationship_id,
                    "candidate_value": c.candidate_value,
                    "rejection_reason": "less_than_selected_max",
                }
            )
        return ShadowCandidateEvaluation(
            pass_name=pass_name,
            candidate_count=len(candidates),
            selected_candidate_id=selected.relationship_id,
            selected_value=selected.candidate_value,
            rejected_candidates=rejected,
            tie_break_applied=tie_break,
        )

    def select_min_candidates(
        self, candidates: list[ShadowCandidate], *, pass_name: str = "backward"
    ) -> ShadowCandidateEvaluation:
        valid = [c for c in candidates if c.candidate_value is not None]
        if not valid:
            return ShadowCandidateEvaluation(
                pass_name=pass_name,
                candidate_count=len(candidates),
                selected_candidate_id=None,
                selected_value=None,
            )
        ordered = sorted(valid, key=lambda c: (c.candidate_value or 0, c.relationship_id))
        selected = ordered[0]
        rejected = [
            {
                "relationship_id": c.relationship_id,
                "candidate_value": c.candidate_value,
                "rejection_reason": "greater_than_selected_min",
            }
            for c in ordered[1:]
        ]
        tie_break = (
            len(ordered) > 1 and ordered[0].candidate_value == ordered[1].candidate_value
        )
        return ShadowCandidateEvaluation(
            pass_name=pass_name,
            candidate_count=len(candidates),
            selected_candidate_id=selected.relationship_id,
            selected_value=selected.candidate_value,
            rejected_candidates=rejected,
            tie_break_applied=tie_break,
            tie_break_rule="min_value_then_relationship_id",
        )

    def run_full_shadow_chain(
        self,
        *,
        topo_order: list[str],
        activities: dict[str, dict[str, Any]],
        relationships: list[dict[str, Any]],
        finish_anchor_lf: float | None,
        critical_threshold: float = 0.0,
        near_critical_threshold: float = 10.0,
    ) -> tuple[dict[str, ShadowActivityResult], list[ShadowRelationshipResult]]:
        incoming: dict[str, list[dict[str, Any]]] = {}
        outgoing: dict[str, list[dict[str, Any]]] = {}
        for rel in relationships:
            pred = str(rel.get("predecessor_activity_id", ""))
            succ = str(rel.get("successor_activity_id", ""))
            incoming.setdefault(succ, []).append(rel)
            outgoing.setdefault(pred, []).append(rel)

        activity_results: dict[str, ShadowActivityResult] = {}
        rel_results: list[ShadowRelationshipResult] = []
        es_map: dict[str, float] = {}
        ef_map: dict[str, float | None] = {}
        ls_map: dict[str, float | None] = {}
        lf_map: dict[str, float | None] = {}

        for aid in topo_order:
            act = activities.get(aid, {})
            duration = _as_float(act.get("duration_value"))
            if duration is None and act.get("is_milestone"):
                duration = 0.0
            if duration is None:
                duration = _as_float(act.get("duration_original")) or _as_float(
                    act.get("duration_remaining")
                )

            fwd_candidates: list[ShadowCandidate] = []
            for rel in sorted(
                incoming.get(aid, []),
                key=lambda r: (
                    str(r.get("predecessor_activity_id", "")),
                    str(r.get("relationship_type") or ""),
                    str(r.get("relationship_row_id") or r.get("relationship_ref") or ""),
                ),
            ):
                pred = str(rel.get("predecessor_activity_id", ""))
                rel_id = str(
                    rel.get("relationship_ref")
                    or rel.get("relationship_row_id")
                    or f"{pred}->{aid}"
                )
                lag = _as_float(rel.get("normalized_lag_days")) or 0.0
                rel_type = str(rel.get("relationship_type") or "") or None
                cand, formula = self.evaluate_forward_candidate(
                    rel_type=rel_type,
                    lag_days=lag,
                    pred_es=es_map.get(pred),
                    pred_ef=ef_map.get(pred),
                    succ_duration=duration,
                )
                fwd_candidates.append(
                    ShadowCandidate(
                        relationship_id=rel_id,
                        predecessor_activity_id=pred,
                        successor_activity_id=aid,
                        relationship_type=rel_type,
                        lag_days=lag,
                        candidate_value=cand,
                        formula_expression=formula,
                        pass_name="forward",
                    )
                )
                rel_results.append(
                    ShadowRelationshipResult(
                        relationship_id=rel_id,
                        predecessor_activity_id=pred,
                        successor_activity_id=aid,
                        relationship_type=rel_type,
                        lag_days=lag,
                        forward_candidate_es=cand,
                        forward_formula=formula,
                    )
                )

            fwd_eval = self.select_max_candidates(fwd_candidates, pass_name="forward")
            es = max(
                [c.candidate_value for c in fwd_candidates if c.candidate_value is not None],
                default=0.0,
            )
            es = max(es, 0.0)
            ef = es + duration if duration is not None else None
            es_map[aid] = _round(es) or 0.0
            ef_map[aid] = _round(ef)
            activity_results[aid] = ShadowActivityResult(
                activity_id=aid,
                early_start=_round(es),
                early_finish=_round(ef),
                forward_evaluation=fwd_eval,
            )

        for aid in reversed(topo_order):
            row = activity_results[aid]
            duration_val = None
            if row.early_start is not None and row.early_finish is not None:
                duration_val = row.early_finish - row.early_start
            succs = sorted(
                outgoing.get(aid, []),
                key=lambda r: (
                    str(r.get("successor_activity_id", "")),
                    str(r.get("relationship_type") or ""),
                    str(r.get("relationship_row_id") or ""),
                ),
            )
            if not succs:
                lf = finish_anchor_lf
                bwd_eval = None
            else:
                bwd_candidates: list[ShadowCandidate] = []
                for rel in succs:
                    succ = str(rel.get("successor_activity_id", ""))
                    rel_id = str(
                        rel.get("relationship_ref")
                        or rel.get("relationship_row_id")
                        or f"{aid}->{succ}"
                    )
                    lag = _as_float(rel.get("normalized_lag_days")) or 0.0
                    rel_type = str(rel.get("relationship_type") or "") or None
                    cand_ls, cand_lf, formula = self.evaluate_backward_candidate(
                        rel_type=rel_type,
                        lag_days=lag,
                        pred_duration=duration_val,
                        succ_ls=ls_map.get(succ),
                        succ_lf=lf_map.get(succ),
                    )
                    for rr in rel_results:
                        if rr.relationship_id == rel_id:
                            rr.backward_candidate_lf = cand_lf
                            rr.backward_candidate_ls = cand_ls
                            rr.backward_formula = formula
                    bwd_candidates.append(
                        ShadowCandidate(
                            relationship_id=rel_id,
                            predecessor_activity_id=aid,
                            successor_activity_id=succ,
                            relationship_type=rel_type,
                            lag_days=lag,
                            candidate_value=cand_lf,
                            formula_expression=formula,
                            pass_name="backward",
                        )
                    )
                bwd_eval = self.select_min_candidates(bwd_candidates, pass_name="backward")
                lf = bwd_eval.selected_value

            ls = lf - duration_val if (lf is not None and duration_val is not None) else None
            lf_map[aid] = _round(lf)
            ls_map[aid] = _round(ls)
            row.late_start = _round(ls)
            row.late_finish = _round(lf)
            row.backward_evaluation = bwd_eval if succs else None
            row.total_float = self.evaluate_total_float(
                row.early_start, row.late_start, row.early_finish, row.late_finish
            )
            if succs:
                ff_cands: list[tuple[float, str, str]] = []
                for rel in succs:
                    succ = str(rel.get("successor_activity_id", ""))
                    rel_id = str(
                        rel.get("relationship_ref")
                        or rel.get("relationship_row_id")
                        or f"{aid}->{succ}"
                    )
                    lag = _as_float(rel.get("normalized_lag_days")) or 0.0
                    rel_type = str(rel.get("relationship_type") or "") or None
                    succ_row = activity_results.get(succ)
                    ff, ff_formula = self.evaluate_free_float_candidate(
                        rel_type=rel_type,
                        lag_days=lag,
                        pred_es=row.early_start,
                        pred_ef=row.early_finish,
                        succ_es=succ_row.early_start if succ_row else None,
                        succ_ef=succ_row.early_finish if succ_row else None,
                    )
                    for rr in rel_results:
                        if rr.relationship_id == rel_id:
                            rr.free_float_candidate = ff
                            rr.free_float_formula = ff_formula
                    if ff is not None:
                        ff_cands.append((ff, succ, rel_id))
                if ff_cands:
                    best = min(ff_cands, key=lambda t: (t[0], t[1], t[2]))
                    row.free_float = _round(best[0])
            row.criticality_class = self.evaluate_criticality(
                row.total_float,
                critical_threshold=critical_threshold,
                near_critical_threshold=near_critical_threshold,
            )

        return activity_results, rel_results


__all__ = [
    "CpmShadowFormulaEvaluator",
    "FORMULA_EXPRESSIONS",
    "ShadowActivityResult",
    "ShadowCandidateEvaluation",
    "ShadowRelationshipResult",
]
