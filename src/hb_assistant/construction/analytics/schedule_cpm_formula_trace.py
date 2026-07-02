"""CPM formula trace export: lineage-resolved chain, triple diff, shadow evaluator."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.schedule_cpm_backward_pass import (
    compute_backward_pass,
    resolve_finish_anchor,
)
from hb_assistant.construction.analytics.schedule_cpm_criticality import compute_criticality
from hb_assistant.construction.analytics.schedule_cpm_float import compute_float
from hb_assistant.construction.analytics.schedule_cpm_forward_pass import compute_forward_pass
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_shadow_formula_evaluator import (
    CpmShadowFormulaEvaluator,
    FORMULA_EXPRESSIONS,
    PATH_DURATION_DEFINITION,
    ShadowLongestPathResult,
    identities_match,
    relationship_identity_from_persisted_path,
)
from hb_assistant.construction.analytics.schedule_quality_normalization import (
    calendar_hours_per_day,
    normalize_duration_days,
    normalize_lag_result,
)
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository

CPM_FORMULA_TRACE_VERSION = "2026-07-02.cpm-longest-path-shadow.v2"

_OFFSET_TOL = 1e-6

SOURCE_FLOAT_FIELDS = (
    "total_float",
    "derived_total_float_days",
    "explicit_total_float_days",
)
SOURCE_CRITICAL_FIELDS = ("is_critical",)

STAGE_EXPECTED_STATUS = {
    "criticality": "criticality_classification_only",
    "longest_path": "longest_path_only",
    "float": "forward_backward_float_only",
    "backward_pass": "backward_pass_only",
    "forward_pass": "forward_pass_only",
}

ROW_COUNT_TABLES = (
    "schedule_cpm_runs",
    "schedule_cpm_activity_results",
    "schedule_cpm_relationship_results",
    "schedule_cpm_paths",
    "schedule_cpm_path_activities",
    "schedule_cpm_diagnostics",
    "procore_ep_schedule_activities",
    "procore_ep_schedule_relationships",
    "schedule_file_imports",
)


class CpmChainResolutionError(Exception):
    """Raised when CPM run lineage cannot be resolved (exit code 3)."""


@dataclass
class CpmRunChain:
    schedule_version_key: str
    import_id: str
    stages: dict[str, dict[str, Any]]
    chain_id: str
    resolution_mode: str
    status: str
    lineage_valid: bool
    limitations: list[str] = field(default_factory=list)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values_match(a: Any, b: Any, *, tolerance: float) -> bool:
    fa, fb = _as_float(a), _as_float(b)
    if fa is None and fb is None:
        return True
    if fa is None or fb is None:
        return False
    return abs(fa - fb) <= tolerance


def _relationship_ref(rel: dict[str, Any]) -> str:
    if rel.get("relationship_ref"):
        return str(rel["relationship_ref"])
    pred = str(rel.get("predecessor_activity_id") or "")
    succ = str(rel.get("successor_activity_id") or "")
    rel_type = str(rel.get("relationship_type") or "") or None
    if pred and succ:
        base = f"{pred}->{succ}"
        return f"{base} ({rel_type})" if rel_type else base
    return str(rel.get("relationship_row_id") or "")


def snapshot_db_row_counts(db_path: str | Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        for table in ROW_COUNT_TABLES:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = int(row[0]) if row else 0
            except sqlite3.Error:
                counts[table] = -1
    return counts


def assert_db_unchanged(before: dict[str, int], after: dict[str, int]) -> None:
    mismatches = {
        table: (before.get(table), after.get(table))
        for table in ROW_COUNT_TABLES
        if before.get(table) != after.get(table)
    }
    if mismatches:
        raise AssertionError(f"database row counts changed after export: {mismatches}")


def build_code_version_metadata(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[4]
    module_paths = [
        root / "src/hb_assistant/construction/analytics/schedule_cpm_forward_pass.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_backward_pass.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_float.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_criticality.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_shadow_formula_evaluator.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_longest_path.py",
        root / "src/hb_assistant/construction/analytics/schedule_cpm_formula_trace.py",
    ]
    hashes: dict[str, str] = {}
    for path in module_paths:
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()[:16]
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except Exception:
        head = "unknown"
    return {
        "formula_version": CPM_FORMULA_TRACE_VERSION,
        "repo_head": head,
        "module_hashes": hashes,
    }


class CpmRunChainResolver:
    def __init__(self, *, db_path: str) -> None:
        self._repo = ScheduleCpmDiagnosticsRepository(db_path=db_path)

    def resolve(
        self,
        schedule_version_key: str,
        *,
        cpm_run_id: str | None = None,
        latest: bool = False,
        allow_partial_chain: bool = False,
    ) -> CpmRunChain:
        if bool(cpm_run_id) == bool(latest):
            raise ValueError("exactly one of cpm_run_id or latest must be set")
        mode = "explicit_cpm_run_id" if cpm_run_id else "latest_terminal_criticality"
        if latest:
            start = self._latest_terminal_criticality(schedule_version_key)
            if start is None:
                raise CpmChainResolutionError("no criticality run found for version")
        else:
            start = self._repo.get_run(str(cpm_run_id))
            if start is None:
                raise CpmChainResolutionError(f"unknown cpm_run_id: {cpm_run_id}")

        stages = self._walk_lineage(start)
        import_ids = {str(r.get("import_id") or "") for r in stages.values() if r}
        import_id = next(iter(import_ids - {""}), "")
        if len(import_ids - {""}) > 1:
            raise CpmChainResolutionError("mixed import_id across lineage")

        required = ("criticality", "longest_path", "float", "backward_pass", "forward_pass")
        missing = [s for s in required if stages.get(s) is None]
        status = "complete" if not missing else "partial"
        if missing and not allow_partial_chain:
            raise CpmChainResolutionError(f"incomplete chain; missing stages: {missing}")

        ordered_ids = [
            str(stages[s]["cpm_run_id"])
            for s in ("forward_pass", "backward_pass", "float", "longest_path", "criticality")
            if stages.get(s)
        ]
        chain_id = hashlib.sha256("|".join(ordered_ids).encode()).hexdigest()[:16]
        limitations: list[str] = []
        if missing:
            limitations.append(f"missing stages: {missing}")
        graph = self._find_graph_run(schedule_version_key, import_id)
        if graph:
            stages["graph_diagnostics"] = graph

        lineage_valid = self._validate_lineage(stages)
        if not lineage_valid:
            raise CpmChainResolutionError("lineage validation failed")

        return CpmRunChain(
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            stages=stages,
            chain_id=chain_id,
            resolution_mode=mode,
            status=status,
            lineage_valid=lineage_valid,
            limitations=limitations,
        )

    def _latest_terminal_criticality(self, schedule_version_key: str) -> dict[str, Any] | None:
        runs = [
            r
            for r in self._repo.list_runs(schedule_version_key)
            if r.get("calculation_type") == "criticality"
            and r.get("cpm_recalculation_status") == STAGE_EXPECTED_STATUS["criticality"]
        ]
        if not runs:
            return None
        runs.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("cpm_run_id"))), reverse=True)
        return runs[0]

    def _walk_lineage(self, start: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
        stages: dict[str, dict[str, Any] | None] = {
            "criticality": None,
            "longest_path": None,
            "float": None,
            "backward_pass": None,
            "forward_pass": None,
        }
        calc = str(start.get("calculation_type") or "")
        if calc == "criticality":
            stages["criticality"] = start
            stages["longest_path"] = self._follow_source(start)
            stages["float"] = self._follow_source(stages["longest_path"]) if stages["longest_path"] else None
            stages["backward_pass"] = self._follow_source(stages["float"]) if stages["float"] else None
        elif calc == "longest_path":
            stages["longest_path"] = start
            stages["float"] = self._follow_source(start)
            stages["backward_pass"] = self._follow_source(stages["float"]) if stages["float"] else None
            crit = self._find_child_run(start, "criticality")
            stages["criticality"] = crit
        elif calc == "float":
            stages["float"] = start
            stages["backward_pass"] = self._follow_source(start)
            stages["longest_path"] = self._find_child_run(start, "longest_path")
            stages["criticality"] = (
                self._find_child_run(stages["longest_path"], "criticality")
                if stages["longest_path"]
                else None
            )
        elif calc == "backward_pass":
            stages["backward_pass"] = start
            stages["forward_pass"] = self._find_forward_for_backward(start)
            stages["float"] = self._find_child_run(start, "float")
            stages["longest_path"] = (
                self._find_child_run(stages["float"], "longest_path") if stages["float"] else None
            )
            stages["criticality"] = (
                self._find_child_run(stages["longest_path"], "criticality")
                if stages["longest_path"]
                else None
            )
        elif calc == "forward_pass":
            stages["forward_pass"] = start
            stages["backward_pass"] = self._find_child_run(start, "backward_pass")
            stages["float"] = (
                self._find_child_run(stages["backward_pass"], "float")
                if stages["backward_pass"]
                else None
            )
            stages["longest_path"] = (
                self._find_child_run(stages["float"], "longest_path") if stages["float"] else None
            )
            stages["criticality"] = (
                self._find_child_run(stages["longest_path"], "criticality")
                if stages["longest_path"]
                else None
            )
        else:
            raise CpmChainResolutionError(f"unsupported start calculation_type: {calc}")

        if stages["backward_pass"] and not stages["forward_pass"]:
            stages["forward_pass"] = self._find_forward_for_backward(stages["backward_pass"])
        return stages

    def _follow_source(self, run: dict[str, Any] | None) -> dict[str, Any] | None:
        if not run:
            return None
        parent_id = run.get("source_run_id")
        if not parent_id:
            return None
        return self._repo.get_run(str(parent_id))

    def _find_forward_for_backward(self, backward: dict[str, Any]) -> dict[str, Any] | None:
        import_id = str(backward.get("import_id") or "")
        version = str(backward.get("schedule_version_key") or "")
        candidates = [
            r
            for r in self._repo.list_runs(version)
            if r.get("calculation_type") == "forward_pass"
            and str(r.get("import_id") or "") == import_id
            and r.get("cpm_recalculation_status") == STAGE_EXPECTED_STATUS["forward_pass"]
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: (str(r.get("created_at") or ""), str(r.get("cpm_run_id"))),
            reverse=True,
        )
        return candidates[0]

    def _find_child_run(
        self, parent: dict[str, Any] | None, calculation_type: str
    ) -> dict[str, Any] | None:
        if not parent:
            return None
        parent_id = str(parent.get("cpm_run_id"))
        version = str(parent.get("schedule_version_key") or "")
        matches = [
            r
            for r in self._repo.list_runs(version)
            if r.get("calculation_type") == calculation_type
            and str(r.get("source_run_id") or "") == parent_id
        ]
        if not matches:
            return None
        if len(matches) > 1:
            matches.sort(
                key=lambda r: (str(r.get("created_at") or ""), str(r.get("cpm_run_id"))),
                reverse=True,
            )
        return matches[0]

    def _find_graph_run(self, schedule_version_key: str, import_id: str) -> dict[str, Any] | None:
        if not import_id:
            return None
        candidates = [
            r
            for r in self._repo.list_runs(schedule_version_key)
            if str(r.get("import_id") or "") == import_id
            and (r.get("calculation_type") in (None, "", "graph") or r.get("analysis_scope") == "graph_diagnostics")
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: (str(r.get("created_at") or ""), str(r.get("cpm_run_id"))),
            reverse=True,
        )
        return candidates[0]

    def _validate_lineage(self, stages: dict[str, dict[str, Any] | None]) -> bool:
        pairs = (
            ("criticality", "longest_path"),
            ("longest_path", "float"),
            ("float", "backward_pass"),
        )
        for child_name, parent_name in pairs:
            child, parent = stages.get(child_name), stages.get(parent_name)
            if child and parent:
                if str(child.get("source_run_id") or "") != str(parent.get("cpm_run_id")):
                    return False
                if str(child.get("schedule_version_key") or "") != str(
                    parent.get("schedule_version_key") or ""
                ):
                    return False
        fwd, bwd = stages.get("forward_pass"), stages.get("backward_pass")
        if fwd and bwd:
            if str(fwd.get("import_id") or "") != str(bwd.get("import_id") or ""):
                return False
        for name, run in stages.items():
            if not run or name == "graph_diagnostics":
                continue
            expected = STAGE_EXPECTED_STATUS.get(name)
            if expected and run.get("cpm_recalculation_status") != expected:
                return False
        return True


class ScheduleCpmFormulaTraceBuilder:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._cpm_repo = ScheduleCpmDiagnosticsRepository(db_path=db_path)
        self._activities = ScheduleActivityRepository(db_path=db_path)
        self._shadow = CpmShadowFormulaEvaluator()

    def build(
        self,
        chain: CpmRunChain,
        *,
        tolerance: float = 0.0,
        allow_missing_longest_path: bool = False,
    ) -> dict[str, Any]:
        version = chain.schedule_version_key
        canonical_activities = self._load_activities(version)
        canonical_relationships = self._activities.list_relationships(version)
        calendars = self._activities.list_calendars(version)
        graph = build_graph(canonical_activities, canonical_relationships)

        float_run = chain.stages.get("float") or {}
        crit_run = chain.stages.get("criticality") or {}
        fwd_run = chain.stages.get("forward_pass") or {}
        bwd_run = chain.stages.get("backward_pass") or {}
        lp_run = chain.stages.get("longest_path") or {}

        persisted_activities = {
            str(a["activity_id"]): a
            for a in self._cpm_repo.list_activity_results(str(crit_run.get("cpm_run_id", "")))
        }
        if not persisted_activities and float_run:
            persisted_activities = {
                str(a["activity_id"]): a
                for a in self._cpm_repo.list_activity_results(str(float_run.get("cpm_run_id", "")))
            }

        persisted_fwd_rels = {
            _relationship_ref(r): r
            for r in self._cpm_repo.list_relationship_results(str(fwd_run.get("cpm_run_id", "")))
        }
        persisted_bwd_rels = {
            _relationship_ref(r): r
            for r in self._cpm_repo.list_relationship_results(str(bwd_run.get("cpm_run_id", "")))
        }

        engine = self._engine_recompute(
            canonical_activities,
            canonical_relationships,
            calendars,
            graph,
            float_run,
            bwd_run,
            lp_run,
            crit_run,
        )
        shadow_acts, shadow_rels = self._shadow_recompute(
            canonical_activities,
            canonical_relationships,
            graph,
            calendars,
            float_run,
            crit_run,
        )

        activity_traces: list[dict[str, Any]] = []
        activity_mismatches: list[dict[str, Any]] = []
        for aid in graph.topological_order or []:
            canon = next((a for a in canonical_activities if str(a.get("activity_id")) == aid), {})
            persisted = persisted_activities.get(aid, {})
            eng = engine["activities"].get(aid, {})
            sh = shadow_acts.get(aid)
            trace = self._activity_trace(
                chain=chain,
                activity_id=aid,
                canonical=canon,
                persisted=persisted,
                engine=eng,
                shadow=sh,
                tolerance=tolerance,
            )
            activity_traces.append(trace)
            activity_mismatches.extend(trace.get("_mismatches", []))

        relationship_traces: list[dict[str, Any]] = []
        relationship_mismatches: list[dict[str, Any]] = []
        for rel in canonical_relationships:
            ref = _relationship_ref(rel)
            pred = str(rel.get("predecessor_activity_id", ""))
            succ = str(rel.get("successor_activity_id", ""))
            persisted_f = persisted_fwd_rels.get(ref, {})
            persisted_b = persisted_bwd_rels.get(ref, {})
            sh_rel = next((r for r in shadow_rels if r.relationship_id == ref), None)
            eng_f = engine["relationships"].get(ref, {})
            rtrace = self._relationship_trace(
                chain=chain,
                rel=rel,
                ref=ref,
                persisted_forward=persisted_f,
                persisted_backward=persisted_b,
                engine=eng_f,
                shadow=sh_rel,
                tolerance=tolerance,
            )
            relationship_traces.append(rtrace)
            relationship_mismatches.extend(rtrace.get("_mismatches", []))

        source_exclusion = self._source_field_exclusion(
            canonical_activities, persisted_activities, engine["activities"]
        )
        shadow_float_acts, shadow_float_rels = self._shadow_float_rows(
            shadow_acts, shadow_rels, graph, canonical_activities, canonical_relationships
        )
        longest_path, longest_path_traces = self._longest_path_diff(
            chain,
            lp_run,
            graph,
            shadow_float_acts,
            shadow_float_rels,
            allow_missing_longest_path=allow_missing_longest_path,
            tolerance=tolerance,
        )
        diff = self._build_diff(
            chain=chain,
            activity_traces=activity_traces,
            relationship_traces=relationship_traces,
            activity_mismatches=activity_mismatches,
            relationship_mismatches=relationship_mismatches,
            source_exclusion=source_exclusion,
            longest_path=longest_path,
            tolerance=tolerance,
        )
        code_version = build_code_version_metadata()
        summary = {
            "mode": "schedule_cpm_formula_trace",
            "schedule_version_key": version,
            "cpm_run_id": str(crit_run.get("cpm_run_id") or float_run.get("cpm_run_id") or ""),
            "formula_version": CPM_FORMULA_TRACE_VERSION,
            "code_version": code_version,
            "chain_resolution": {
                "chain_id": chain.chain_id,
                "resolution_mode": chain.resolution_mode,
                "status": chain.status,
                "lineage_valid": chain.lineage_valid,
                "stages": {
                    k: {"cpm_run_id": v.get("cpm_run_id"), "calculation_type": v.get("calculation_type")}
                    for k, v in chain.stages.items()
                    if v
                },
                "limitations": chain.limitations,
            },
            "activity_count": len(activity_traces),
            "relationship_count": len(relationship_traces),
            "diff_status": diff.get("status"),
        }
        return {
            "summary": summary,
            "activity_traces": activity_traces,
            "relationship_traces": relationship_traces,
            "diff": diff,
            "code_version": code_version,
            "longest_path": longest_path,
            "longest_path_traces": longest_path_traces,
        }

    def _load_activities(self, schedule_version_key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._activities.list_activities(schedule_version_key, limit=500, offset=offset)
            rows.extend(page)
            if len(page) < 500:
                break
            offset += 500
        return rows

    def _engine_recompute(
        self,
        activities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        calendars: list[dict[str, Any]],
        graph: Any,
        float_run: dict[str, Any],
        bwd_run: dict[str, Any],
        lp_run: dict[str, Any],
        crit_run: dict[str, Any],
    ) -> dict[str, Any]:
        anchor_iso = float_run.get("schedule_start_anchor") or bwd_run.get("schedule_start_anchor")
        anchor = datetime.fromisoformat(str(anchor_iso)) if anchor_iso else datetime(2026, 1, 1)
        anchor_source = str(float_run.get("schedule_start_anchor_source") or "data_date")

        fwd = compute_forward_pass(
            activities, relationships, graph, anchor=anchor, anchor_source=anchor_source, calendars=calendars
        )
        fwd_act = {a.activity_id: a for a in fwd.activities}
        fwd_rel = {r.relationship_ref: r for r in fwd.relationships}

        max_ef = max(
            (a.early_finish_offset_days for a in fwd.activities if a.early_finish_offset_days is not None),
            default=None,
        )
        finish_iso = bwd_run.get("schedule_finish_anchor")
        scheduled_finish = None
        if finish_iso:
            try:
                scheduled_finish = datetime.fromisoformat(str(finish_iso))
            except ValueError:
                scheduled_finish = None
        finish_offset, finish_source, finish_caveat = resolve_finish_anchor(
            source_scheduled_finish=scheduled_finish,
            source_planned_finish=None,
            max_early_finish_offset=max_ef,
            start_anchor=anchor,
        )
        if finish_source is None and bwd_run.get("schedule_finish_anchor_source"):
            finish_source = str(bwd_run.get("schedule_finish_anchor_source"))

        bwd = compute_backward_pass(
            graph,
            [self._fwd_act_dict(a) for a in fwd.activities],
            [self._fwd_rel_dict(r) for r in fwd.relationships],
            finish_anchor_offset=finish_offset,
            finish_anchor_source=finish_source,
            finish_anchor_caveat=finish_caveat,
            start_anchor=anchor,
        )
        bwd_act = {a.activity_id: a for a in bwd.activities}

        merged_cpm = []
        for aid, fa in fwd_act.items():
            ba = bwd_act.get(aid)
            merged_cpm.append(
                {
                    "activity_id": aid,
                    "early_start_offset_days": fa.early_start_offset_days,
                    "early_finish_offset_days": fa.early_finish_offset_days,
                    "late_start_offset_days": ba.late_start_offset_days if ba else None,
                    "late_finish_offset_days": ba.late_finish_offset_days if ba else None,
                    "topological_index": fa.topological_index,
                }
            )
        flt = compute_float(graph, merged_cpm, [self._fwd_rel_dict(r) for r in fwd.relationships])
        flt_act = {a.activity_id: a for a in flt.activities}

        lp_activities: list[dict[str, Any]] = []
        if lp_run:
            for path in self._cpm_repo.list_paths(str(lp_run.get("cpm_run_id"))):
                lp_activities.extend(self._cpm_repo.list_path_activities(path["path_id"]))

        crit_threshold = _as_float(crit_run.get("critical_float_threshold_days")) or 0.0
        near_threshold = _as_float(crit_run.get("near_critical_float_threshold_days")) or 10.0
        crit = compute_criticality(
            graph,
            [
                {
                    "activity_id": a.activity_id,
                    "computed_total_float": a.computed_total_float,
                    "computed_free_float": a.computed_free_float,
                    "topological_index": a.topological_index,
                }
                for a in flt.activities
            ],
            lp_activities,
            critical_threshold_days=crit_threshold,
            near_critical_threshold_days=near_threshold,
        )
        crit_act = {a.activity_id: a for a in crit.activities}

        activities_out: dict[str, dict[str, Any]] = {}
        for aid in graph.topological_order or []:
            fa, ba, fla, ca = fwd_act.get(aid), bwd_act.get(aid), flt_act.get(aid), crit_act.get(aid)
            activities_out[aid] = {
                "early_start": fa.early_start_offset_days if fa else None,
                "early_finish": fa.early_finish_offset_days if fa else None,
                "late_start": ba.late_start_offset_days if ba else None,
                "late_finish": ba.late_finish_offset_days if ba else None,
                "total_float": fla.computed_total_float if fla else None,
                "free_float": fla.computed_free_float if fla else None,
                "criticality_class": ca.computed_criticality_class if ca else None,
            }
        rels_out = {
            ref: {
                "forward_candidate_es": r.candidate_successor_early_start_offset,
                "relationship_type": r.relationship_type,
            }
            for ref, r in fwd_rel.items()
        }
        return {"activities": activities_out, "relationships": rels_out}

    def _shadow_recompute(
        self,
        activities: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        graph: Any,
        calendars: list[dict[str, Any]],
        float_run: dict[str, Any],
        crit_run: dict[str, Any],
    ) -> tuple[dict[str, Any], list[Any]]:
        calendars = calendars or []
        act_map: dict[str, dict[str, Any]] = {}
        for a in activities:
            aid = str(a.get("activity_id"))
            hpd = calendar_hours_per_day(calendars, a.get("calendar_id"))
            dur = normalize_duration_days(
                duration_value=a.get("duration_original") or a.get("duration_remaining"),
                duration_unit=a.get("duration_unit"),
                hours_per_day=hpd,
                source_format=a.get("source_format"),
            )
            if a.get("is_milestone"):
                dur = 0.0
            act_map[aid] = {**a, "duration_value": dur}

        rel_norm: list[dict[str, Any]] = []
        for rel in relationships:
            hpd = calendar_hours_per_day(calendars, rel.get("calendar_id"))
            lag_res = normalize_lag_result(
                rel.get("lag_value"),
                rel.get("lag_unit"),
                hours_per_day=hpd,
            )
            rel_norm.append(
                {
                    **rel,
                    "normalized_lag_days": float(lag_res.normalized_days or 0.0),
                    "relationship_ref": _relationship_ref(rel),
                }
            )

        finish_lf = None
        fa_iso = float_run.get("schedule_finish_anchor")
        sa_iso = float_run.get("schedule_start_anchor")
        if fa_iso and sa_iso:
            try:
                finish_lf = (
                    datetime.fromisoformat(str(fa_iso)) - datetime.fromisoformat(str(sa_iso))
                ).days
            except ValueError:
                finish_lf = None

        crit_t = _as_float(crit_run.get("critical_float_threshold_days")) or 0.0
        near_t = _as_float(crit_run.get("near_critical_float_threshold_days")) or 10.0
        shadow_acts, shadow_rels = self._shadow.run_full_shadow_chain(
            topo_order=list(graph.topological_order or []),
            activities=act_map,
            relationships=rel_norm,
            finish_anchor_lf=finish_lf,
            critical_threshold=crit_t,
            near_critical_threshold=near_t,
        )
        return shadow_acts, shadow_rels

    def _shadow_float_rows(
        self,
        shadow_acts: dict[str, Any],
        shadow_rels: list[Any],
        graph: Any,
        canonical_activities: list[dict[str, Any]],
        canonical_relationships: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        topo_by_id = {
            str(a.get("activity_id")): a.get("topological_index")
            for a in canonical_activities
            if isinstance(a.get("topological_index"), int)
        }
        float_acts: list[dict[str, Any]] = []
        for aid in graph.topological_order or []:
            sh = shadow_acts.get(aid)
            if not sh:
                continue
            canon = next((a for a in canonical_activities if str(a.get("activity_id")) == aid), {})
            duration = _as_float(canon.get("duration_value"))
            if duration is None and canon.get("is_milestone"):
                duration = 0.0
            if duration is None and sh.early_start is not None and sh.early_finish is not None:
                duration = sh.early_finish - sh.early_start
            float_acts.append(
                {
                    "activity_id": aid,
                    "activity_name": canon.get("activity_name"),
                    "topological_index": topo_by_id.get(aid),
                    "early_start_offset_days": sh.early_start,
                    "early_finish_offset_days": sh.early_finish,
                    "duration_value": duration,
                    "computed_total_float": sh.total_float,
                    "computed_free_float": sh.free_float,
                }
            )
        float_rels: list[dict[str, Any]] = []
        canon_rel_by_pair = {
            (str(r.get("predecessor_activity_id")), str(r.get("successor_activity_id"))): r
            for r in canonical_relationships
        }
        for rel in shadow_rels:
            pair = (rel.predecessor_activity_id, rel.successor_activity_id)
            canon = canon_rel_by_pair.get(pair, {})
            row_id = str(canon.get("relationship_row_id") or rel.relationship_id)
            float_rels.append(
                {
                    "predecessor_activity_id": rel.predecessor_activity_id,
                    "successor_activity_id": rel.successor_activity_id,
                    "relationship_type": rel.relationship_type,
                    "normalized_lag_days": rel.lag_days,
                    "candidate_successor_early_start_offset": rel.forward_candidate_es,
                    "relationship_ref": rel.relationship_id,
                    "relationship_row_id": row_id,
                }
            )
        return float_acts, float_rels

    def _longest_path_diff(
        self,
        chain: CpmRunChain,
        lp_run: dict[str, Any],
        graph: Any,
        shadow_float_acts: list[dict[str, Any]],
        shadow_float_rels: list[dict[str, Any]],
        *,
        allow_missing_longest_path: bool,
        tolerance: float,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        shadow_result = self._shadow.evaluate_longest_path(
            graph_result=graph,
            float_activities=shadow_float_acts,
            float_relationships=shadow_float_rels,
        )
        traces = self._longest_path_traces(chain, shadow_result)

        if not shadow_float_acts:
            block = {
                "shadow_recompute_supported": True,
                "diff_status": "not_computable_empty_graph",
                "algorithm_id": shadow_result.summary.algorithm_id if shadow_result.summary else None,
                "path_duration_basis": PATH_DURATION_DEFINITION,
                "path_count": 0,
                "shadow_path_count": 0,
                "persisted_path_count": 0,
            }
            return block, traces

        if shadow_result.block_reason == "no_terminal_activity":
            block = {
                "shadow_recompute_supported": True,
                "diff_status": "not_computable_no_terminal_activity",
                "path_duration_basis": PATH_DURATION_DEFINITION,
                "path_count": 0,
                "shadow_path_count": 0,
                "persisted_path_count": 0,
            }
            return block, traces

        persisted_paths: list[dict[str, Any]] = []
        persisted_activities_by_path: dict[str, list[dict[str, Any]]] = {}
        if lp_run:
            persisted_paths = self._cpm_repo.list_paths(str(lp_run.get("cpm_run_id")))
            for path in persisted_paths:
                persisted_activities_by_path[str(path["path_id"])] = self._cpm_repo.list_path_activities(
                    str(path["path_id"])
                )

        lp_expected = chain.stages.get("longest_path") is not None
        if lp_expected and not persisted_paths:
            diff_status = (
                "allowed_missing_longest_path"
                if allow_missing_longest_path
                else "missing_required_longest_path_rows"
            )
            block = {
                "shadow_recompute_supported": True,
                "diff_status": diff_status,
                "path_duration_basis": PATH_DURATION_DEFINITION,
                "path_count": 0,
                "shadow_path_count": 1 if shadow_result.activities else 0,
                "persisted_path_count": 0,
                "shadow_summary": shadow_result.summary.to_dict() if shadow_result.summary else None,
            }
            return block, traces

        primary = next((p for p in persisted_paths if int(p.get("path_rank") or 0) == 1), None)
        if not primary and persisted_paths:
            primary = persisted_paths[0]

        path_mismatches: list[dict[str, Any]] = []
        matched_path_count = 0
        if primary and shadow_result.summary:
            persisted_acts = persisted_activities_by_path.get(str(primary["path_id"]), [])
            persisted_ids = [str(a["activity_id"]) for a in sorted(persisted_acts, key=lambda r: r["path_sequence"])]
            shadow_ids = shadow_result.activity_ids

            if persisted_ids != shadow_ids:
                path_mismatches.append(
                    {
                        "field": "activity_ids",
                        "persisted": persisted_ids,
                        "shadow": shadow_ids,
                    }
                )

            shadow_rel_map = {
                (str(r.get("predecessor_activity_id")), str(r.get("successor_activity_id"))): r
                for r in shadow_float_rels
            }
            for i, pact in enumerate(sorted(persisted_acts, key=lambda r: r["path_sequence"])):
                if i == 0:
                    continue
                pred_id = persisted_ids[i - 1]
                succ_id = persisted_ids[i]
                shadow_rel_row = shadow_rel_map.get((pred_id, succ_id), {})
                persisted_identity = relationship_identity_from_persisted_path(
                    relationship_from_previous_ref=pact.get("relationship_from_previous_ref"),
                    relationship_from_previous_id=pact.get("relationship_from_previous_id"),
                    predecessor_activity_id=pred_id,
                    successor_activity_id=succ_id,
                    relationship_type=str(shadow_rel_row.get("relationship_type") or ""),
                    lag=_as_float(shadow_rel_row.get("normalized_lag_days")) or 0.0,
                )
                shadow_act = next(
                    (a for a in shadow_result.activities if a.activity_id == succ_id),
                    None,
                )
                shadow_identity = shadow_act.relationship_from_previous if shadow_act else None
                if not identities_match(persisted_identity, shadow_identity):
                    path_mismatches.append(
                        {
                            "field": "relationship_identity",
                            "activity_id": succ_id,
                            "persisted": persisted_identity.to_dict(),
                            "shadow": shadow_identity.to_dict() if shadow_identity else None,
                        }
                    )

            for field, persist_key in (
                ("path_duration", "path_duration"),
                ("path_start_offset_days", "path_start_offset_days"),
                ("path_finish_offset_days", "path_finish_offset_days"),
            ):
                persisted_val = primary.get(persist_key)
                shadow_val = getattr(shadow_result.summary, persist_key, None)
                if not _values_match(persisted_val, shadow_val, tolerance=tolerance):
                    path_mismatches.append(
                        {
                            "field": field,
                            "persisted": persisted_val,
                            "shadow": shadow_val,
                        }
                    )

            if str(primary.get("end_activity_id") or "") != str(shadow_result.summary.end_activity_id or ""):
                path_mismatches.append(
                    {
                        "field": "end_activity_id",
                        "persisted": primary.get("end_activity_id"),
                        "shadow": shadow_result.summary.end_activity_id,
                    }
                )

            if not path_mismatches:
                matched_path_count = 1

        diff_status = "pass" if matched_path_count == 1 else "fail"
        if not primary and shadow_result.activities and lp_expected:
            diff_status = (
                "allowed_missing_longest_path"
                if allow_missing_longest_path
                else "missing_required_longest_path_rows"
            )

        block = {
            "shadow_recompute_supported": True,
            "diff_status": diff_status,
            "algorithm_id": shadow_result.summary.algorithm_id if shadow_result.summary else None,
            "path_duration_basis": PATH_DURATION_DEFINITION,
            "path_count": len(persisted_paths),
            "persisted_path_count": len(persisted_paths),
            "shadow_path_count": 1 if shadow_result.activities else 0,
            "matched_path_count": matched_path_count,
            "mismatched_path_count": 0 if matched_path_count else (1 if primary else 0),
            "path_mismatches": path_mismatches[:50],
            "shadow_summary": shadow_result.summary.to_dict() if shadow_result.summary else None,
            "persisted_summary": (
                {
                    "path_rank": primary.get("path_rank"),
                    "end_activity_id": primary.get("end_activity_id"),
                    "path_duration": primary.get("path_duration"),
                    "path_start_offset_days": primary.get("path_start_offset_days"),
                    "path_finish_offset_days": primary.get("path_finish_offset_days"),
                }
                if primary
                else None
            ),
        }
        return block, traces

    def _longest_path_traces(
        self,
        chain: CpmRunChain,
        shadow_result: ShadowLongestPathResult,
    ) -> list[dict[str, Any]]:
        if not shadow_result.summary:
            return []
        code_version = build_code_version_metadata()
        return [
            {
                "trace_type": "longest_path",
                "schedule_version_key": chain.schedule_version_key,
                "cpm_run_id": chain.stages.get("longest_path", {}).get("cpm_run_id"),
                "formula_version": CPM_FORMULA_TRACE_VERSION,
                "code_version": code_version,
                "algorithm_id": shadow_result.summary.algorithm_id,
                "path_basis": shadow_result.summary.path_basis,
                "path_duration_basis": PATH_DURATION_DEFINITION,
                "path_status": shadow_result.summary.path_status,
                "summary": shadow_result.summary.to_dict(),
                "activities": [a.to_dict() for a in shadow_result.activities],
            }
        ]

    @staticmethod
    def _fwd_act_dict(a: Any) -> dict[str, Any]:
        return {
            "activity_id": a.activity_id,
            "activity_name": a.activity_name,
            "topological_index": a.topological_index,
            "early_start_offset_days": a.early_start_offset_days,
            "early_finish_offset_days": a.early_finish_offset_days,
            "duration_value": a.duration_value,
            "duration_unit": a.duration_unit,
            "duration_source": a.duration_source,
            "predecessor_count": a.predecessor_count,
            "successor_count": a.successor_count,
            "forward_pass_status": a.forward_pass_status,
        }

    @staticmethod
    def _fwd_rel_dict(r: Any) -> dict[str, Any]:
        return {
            "relationship_row_id": r.relationship_row_id,
            "relationship_ref": r.relationship_ref,
            "predecessor_activity_id": r.predecessor_activity_id,
            "successor_activity_id": r.successor_activity_id,
            "relationship_type": r.relationship_type,
            "normalized_lag_days": r.normalized_lag_days,
            "candidate_successor_early_start_offset": r.candidate_successor_early_start_offset,
            "relationship_calc_status": r.relationship_calc_status,
        }

    def _triple_field(
        self,
        field: str,
        persisted: Any,
        engine: Any,
        shadow: Any,
        *,
        tolerance: float,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        pe = _values_match(persisted, engine, tolerance=tolerance)
        es = _values_match(engine, shadow, tolerance=tolerance)
        ps = _values_match(persisted, shadow, tolerance=tolerance)
        block = {
            "persisted_result": persisted,
            "engine_recomputed_result": engine,
            "shadow_formula_result": shadow,
            "match_persisted_vs_engine": pe,
            "match_engine_vs_shadow": es,
            "match_persisted_vs_shadow": ps,
            "tolerance": tolerance,
        }
        mismatches = []
        if not pe or not es:
            mismatches.append(
                {
                    "field": field,
                    "persisted": persisted,
                    "engine": engine,
                    "shadow": shadow,
                }
            )
        return block, mismatches

    def _activity_trace(
        self,
        *,
        chain: CpmRunChain,
        activity_id: str,
        canonical: dict[str, Any],
        persisted: dict[str, Any],
        engine: dict[str, Any],
        shadow: Any,
        tolerance: float,
    ) -> dict[str, Any]:
        code_version = build_code_version_metadata()
        mismatches: list[dict[str, Any]] = []
        fields = (
            ("early_start", "early_start_offset_days", "early_start"),
            ("early_finish", "early_finish_offset_days", "early_finish"),
            ("late_start", "late_start_offset_days", "late_start"),
            ("late_finish", "late_finish_offset_days", "late_finish"),
            ("total_float", "computed_total_float", "total_float"),
            ("free_float", "computed_free_float", "free_float"),
            ("criticality", "computed_criticality_class", "criticality_class"),
        )
        blocks: dict[str, Any] = {}
        for label, persist_key, engine_key in fields:
            p = persisted.get(persist_key) if label != "criticality" else persisted.get("computed_criticality_class")
            e = engine.get(engine_key)
            s = getattr(shadow, engine_key, None) if shadow else None
            if label == "criticality" and shadow:
                s = shadow.criticality_class
            block, mm = self._triple_field(label, p, e, s, tolerance=tolerance)
            blocks[label] = block
            mismatches.extend(mm)

        source_block = self._per_activity_source_exclusion(canonical, persisted, engine)
        fwd_eval = None
        bwd_eval = None
        if shadow and shadow.forward_evaluation:
            fwd_eval = {
                "candidate_count": shadow.forward_evaluation.candidate_count,
                "selected_candidate_id": shadow.forward_evaluation.selected_candidate_id,
                "rejected_candidates": shadow.forward_evaluation.rejected_candidates,
                "tie_break_applied": shadow.forward_evaluation.tie_break_applied,
                "tie_break_rule": shadow.forward_evaluation.tie_break_rule,
            }
        if shadow and shadow.backward_evaluation:
            bwd_eval = {
                "candidate_count": shadow.backward_evaluation.candidate_count,
                "selected_candidate_id": shadow.backward_evaluation.selected_candidate_id,
                "rejected_candidates": shadow.backward_evaluation.rejected_candidates,
                "tie_break_applied": shadow.backward_evaluation.tie_break_applied,
                "tie_break_rule": shadow.backward_evaluation.tie_break_rule,
            }

        trace = {
            "trace_type": "activity",
            "schedule_version_key": chain.schedule_version_key,
            "cpm_run_id": chain.stages.get("criticality", {}).get("cpm_run_id"),
            "activity_id": activity_id,
            "activity_code": activity_id,
            "activity_name": canonical.get("activity_name"),
            "formula_version": CPM_FORMULA_TRACE_VERSION,
            "code_version": code_version,
            "forward_pass": {
                "formula_family": "forward",
                "formula_expression": FORMULA_EXPRESSIONS["forward_FS"],
                "computed_early_start": blocks["early_start"],
                "computed_early_finish": blocks["early_finish"],
                "candidate_evaluation": fwd_eval,
            },
            "backward_pass": {
                "formula_family": "backward",
                "computed_late_start": blocks["late_start"],
                "computed_late_finish": blocks["late_finish"],
                "candidate_evaluation": bwd_eval,
            },
            "float": {
                "total_float_formula": FORMULA_EXPRESSIONS["total_float"],
                "computed_total_float": blocks["total_float"],
                "computed_free_float": blocks["free_float"],
            },
            "criticality": {
                "formula_family": "criticality",
                "computed_classification": blocks["criticality"],
            },
            "source_field_exclusion": source_block,
            "duration": {
                "value": _as_float(canonical.get("duration_original") or canonical.get("duration_remaining")),
                "unit": "days",
                "source": "canonical",
                "source_field_exclusion": {
                    "imported_total_float_excluded": True,
                    "imported_free_float_excluded": True,
                    "imported_critical_flag_excluded": True,
                },
            },
        }
        trace["_mismatches"] = mismatches
        return trace

    def _relationship_trace(
        self,
        *,
        chain: CpmRunChain,
        rel: dict[str, Any],
        ref: str,
        persisted_forward: dict[str, Any],
        persisted_backward: dict[str, Any],
        engine: dict[str, Any],
        shadow: Any,
        tolerance: float,
    ) -> dict[str, Any]:
        mismatches: list[dict[str, Any]] = []
        p_fwd = persisted_forward.get("candidate_successor_early_start_offset")
        e_fwd = engine.get("forward_candidate_es")
        s_fwd = shadow.forward_candidate_es if shadow else None
        fwd_block, mm1 = self._triple_field("forward_candidate_es", p_fwd, e_fwd, s_fwd, tolerance=tolerance)
        mismatches.extend(mm1)
        rel_type = str(rel.get("relationship_type") or "")
        expr_key = f"forward_{rel_type}" if rel_type in {"FS", "SS", "FF", "SF"} else "forward_FS"
        trace = {
            "trace_type": "relationship",
            "schedule_version_key": chain.schedule_version_key,
            "cpm_run_id": chain.stages.get("forward_pass", {}).get("cpm_run_id"),
            "relationship_id": ref,
            "predecessor_activity_id": rel.get("predecessor_activity_id"),
            "successor_activity_id": rel.get("successor_activity_id"),
            "relationship_type": rel_type,
            "lag": _as_float(rel.get("lag_value")) or 0,
            "formula_version": CPM_FORMULA_TRACE_VERSION,
            "code_version": build_code_version_metadata(),
            "forward_candidate_formula": FORMULA_EXPRESSIONS.get(expr_key),
            "forward_candidate_value": fwd_block,
            "backward_candidate_formula": shadow.backward_formula if shadow else None,
            "backward_candidate_value": {
                "late_start": shadow.backward_candidate_ls if shadow else None,
                "late_finish": shadow.backward_candidate_lf if shadow else None,
            },
            "free_float_candidate": shadow.free_float_candidate if shadow else None,
            "persisted_fields": {
                "forward": persisted_forward,
                "backward": persisted_backward,
            },
            "match": fwd_block.get("match_persisted_vs_engine") and fwd_block.get("match_engine_vs_shadow"),
            "tolerance": tolerance,
        }
        trace["_mismatches"] = mismatches
        return trace

    def _per_activity_source_exclusion(
        self,
        canonical: dict[str, Any],
        persisted: dict[str, Any],
        engine_activities: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        aid = str(canonical.get("activity_id"))
        eng = engine_activities.get(aid, {})
        block: dict[str, Any] = {}
        for field in SOURCE_FLOAT_FIELDS:
            src = _as_float(canonical.get(field))
            block[f"source_{field}_present"] = src is not None
            if src is not None:
                block[f"source_{field}_value"] = src
                comp = eng.get("total_float")
                block[f"source_{field}_used_as_computed_total_float"] = (
                    comp is not None and abs(comp - src) <= _OFFSET_TOL
                )
        for field in SOURCE_CRITICAL_FIELDS:
            present = canonical.get(field) not in (None, "", 0, False)
            block[f"source_{field}_present"] = bool(present)
            if present:
                block[f"source_{field}_used_as_computed_criticality"] = False
        return block

    def _source_field_exclusion(
        self,
        canonical_activities: list[dict[str, Any]],
        persisted_activities: dict[str, dict[str, Any]],
        engine_activities: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        violations: list[dict[str, Any]] = []
        checked = list(SOURCE_FLOAT_FIELDS) + list(SOURCE_CRITICAL_FIELDS)
        for canon in canonical_activities:
            per = self._per_activity_source_exclusion(canon, persisted_activities.get(str(canon.get("activity_id")), {}), engine_activities)
            for field in SOURCE_FLOAT_FIELDS:
                if per.get(f"source_{field}_used_as_computed_total_float"):
                    violations.append(
                        {
                            "activity_id": canon.get("activity_id"),
                            "field": field,
                            "severity": "requires_review",
                            "reason": "computed_total_float_equals_source_without_formula_support",
                        }
                    )
        status = "pass" if not violations else "fail"
        return {
            "status": status,
            "source_fields_checked": checked,
            "violations": violations,
        }

    def _build_diff(
        self,
        *,
        chain: CpmRunChain,
        activity_traces: list[dict[str, Any]],
        relationship_traces: list[dict[str, Any]],
        activity_mismatches: list[dict[str, Any]],
        relationship_mismatches: list[dict[str, Any]],
        source_exclusion: dict[str, Any],
        longest_path: dict[str, Any],
        tolerance: float,
    ) -> dict[str, Any]:
        act_mm = [m for t in activity_traces for m in t.get("_mismatches", [])]
        rel_mm = [m for t in relationship_traces for m in t.get("_mismatches", [])]
        mismatched_activities = sum(1 for t in activity_traces if t.get("_mismatches"))
        mismatched_relationships = sum(1 for t in relationship_traces if t.get("_mismatches"))
        matched_a = len(activity_traces) - mismatched_activities
        matched_r = len(relationship_traces) - mismatched_relationships
        lp_status = longest_path.get("diff_status", "fail")
        stage_status = {
            "forward_pass": "pass" if not act_mm else "fail",
            "backward_pass": "pass" if not act_mm else "fail",
            "float": "pass" if not act_mm else "fail",
            "criticality": "pass" if not act_mm else "fail",
            "longest_path": lp_status,
            "source_field_exclusion": source_exclusion.get("status", "pass"),
        }
        evaluated = [
            "forward_pass",
            "backward_pass",
            "float",
            "criticality",
            "longest_path",
            "source_field_exclusion",
        ]
        fail_lp = lp_status in {"fail", "missing_required_longest_path_rows"}
        if act_mm or rel_mm or source_exclusion.get("status") != "pass" or fail_lp:
            status = "fail"
        elif lp_status == "pass":
            status = "pass"
        else:
            status = "fail"
        return {
            "schedule_version_key": chain.schedule_version_key,
            "cpm_run_id": chain.stages.get("criticality", {}).get("cpm_run_id"),
            "formula_version": CPM_FORMULA_TRACE_VERSION,
            "code_version": build_code_version_metadata(),
            "activity_count": len(activity_traces),
            "relationship_count": len(relationship_traces),
            "matched_activity_count": matched_a,
            "mismatched_activity_count": mismatched_activities,
            "matched_relationship_count": matched_r,
            "mismatched_relationship_count": mismatched_relationships,
            "tolerance": tolerance,
            "status": status,
            "evaluated_stages": evaluated,
            "excluded_stages": [],
            "stage_status": stage_status,
            "longest_path": longest_path,
            "source_field_exclusion": source_exclusion,
            "activity_mismatches": act_mm[:50],
            "relationship_mismatches": rel_mm[:50],
            "limitations": [lim for lim in chain.limitations if lim],
        }


class ScheduleCpmFormulaTraceExporter:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._resolver = CpmRunChainResolver(db_path=db_path)
        self._builder = ScheduleCpmFormulaTraceBuilder(db_path=db_path)

    def export(
        self,
        *,
        schedule_version_key: str,
        out_dir: Path,
        latest: bool = False,
        cpm_run_id: str | None = None,
        allow_partial_chain: bool = False,
        allow_missing_longest_path: bool = False,
        tolerance: float = 0.0,
        technical: bool = False,
    ) -> tuple[dict[str, Any], int]:
        out_dir.mkdir(parents=True, exist_ok=True)
        chain = self._resolver.resolve(
            schedule_version_key,
            cpm_run_id=cpm_run_id,
            latest=latest,
            allow_partial_chain=allow_partial_chain,
        )
        package = self._builder.build(
            chain,
            tolerance=tolerance,
            allow_missing_longest_path=allow_missing_longest_path,
        )
        summary = package["summary"]
        if technical:
            summary["db_path"] = str(Path(self._db_path).resolve())

        (out_dir / "cpm-run-summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        with (out_dir / "cpm-activity-formula-trace.jsonl").open("w", encoding="utf-8") as fh:
            for row in package["activity_traces"]:
                clean = {k: v for k, v in row.items() if not k.startswith("_")}
                fh.write(json.dumps(clean) + "\n")
        with (out_dir / "cpm-relationship-formula-trace.jsonl").open("w", encoding="utf-8") as fh:
            for row in package["relationship_traces"]:
                clean = {k: v for k, v in row.items() if not k.startswith("_")}
                fh.write(json.dumps(clean) + "\n")
        with (out_dir / "cpm-longest-path-formula-trace.jsonl").open("w", encoding="utf-8") as fh:
            for row in package.get("longest_path_traces", []):
                fh.write(json.dumps(row) + "\n")
        (out_dir / "cpm-validation-recompute-diff.json").write_text(
            json.dumps(package["diff"], indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "cpm-formula-audit.md").write_text(
            self._render_audit(package, technical=technical), encoding="utf-8"
        )
        exit_code = self._exit_code(package["diff"])
        return package, exit_code

    @staticmethod
    def _exit_code(diff: dict[str, Any]) -> int:
        lp_status = diff.get("longest_path", {}).get("diff_status")
        if diff.get("status") == "fail":
            return 1
        if diff.get("source_field_exclusion", {}).get("status") == "fail":
            return 1
        if lp_status in {"fail", "missing_required_longest_path_rows"}:
            return 1
        return 0

    @staticmethod
    def _render_audit(package: dict[str, Any], *, technical: bool) -> str:
        diff = package["diff"]
        summary = package["summary"]
        lp = package.get("longest_path", {})
        lines = [
            "# CPM formula audit",
            "",
            f"- schedule version: `{summary.get('schedule_version_key')}`",
            f"- chain id: `{summary.get('chain_resolution', {}).get('chain_id')}`",
            f"- formula version: `{summary.get('formula_version')}`",
            f"- diff status: **{diff.get('status')}**",
            f"- activities traced: {summary.get('activity_count')}",
            f"- relationships traced: {summary.get('relationship_count')}",
            f"- matched activities: {diff.get('matched_activity_count')}",
            f"- mismatched activities: {diff.get('mismatched_activity_count')}",
            "",
            "## Source-field exclusion",
            "",
            f"- status: {diff.get('source_field_exclusion', {}).get('status')}",
            "",
            "## Longest path",
            "",
            f"- algorithm: `{lp.get('algorithm_id')}`",
            f"- path duration basis: {lp.get('path_duration_basis')}",
            f"- diff status: **{lp.get('diff_status')}**",
            f"- persisted paths: {lp.get('persisted_path_count')}",
            f"- shadow paths: {lp.get('shadow_path_count')}",
            f"- matched paths: {lp.get('matched_path_count')}",
            f"- mismatched paths: {lp.get('mismatched_path_count')}",
            "",
            "## Version compatibility",
            "",
            "- v1 exports may show `longest_path.diff_status = not_evaluated` and overall `pass_with_exclusions`.",
            "- v2 requires `longest_path.diff_status = pass` or `fail` unless `--allow-missing-longest-path` is supplied.",
            "",
            "## Conclusion",
            "",
            (
                "Formula trace export completed for operator review. "
                "This report does not assert contractual schedule authority."
            ),
            "",
            "## Reproduce",
            "",
            "```bash",
            "python scripts/dev_schedule_cpm_formula_trace_export.py \\",
            "  --db-path <copied-db> \\",
            f"  --schedule-version-key {summary.get('schedule_version_key')} \\",
            "  --latest \\",
            "  --out-dir <evidence-dir>/cpm-formula-trace",
            "```",
        ]
        if technical:
            lines.insert(5, f"- repo head: `{summary.get('code_version', {}).get('repo_head')}`")
        return "\n".join(lines) + "\n"


__all__ = [
    "CPM_FORMULA_TRACE_VERSION",
    "CpmChainResolutionError",
    "CpmRunChain",
    "CpmRunChainResolver",
    "ScheduleCpmFormulaTraceBuilder",
    "ScheduleCpmFormulaTraceExporter",
    "assert_db_unchanged",
    "build_code_version_metadata",
    "snapshot_db_row_counts",
]
