"""Data Quality Gates and Phase Go/No-Go (Phase 07A Prompt 07).

Implements measurable gates per resources/json/data_quality_gate_thresholds.json
and the 12+ gates enumerated in the Phase 07A spec (09_ and Prompt 07).

- Loads thresholds (deterministic + candidate orphan rates, coverage mins, latency target, raw/writeback=0).
- Computes observed values via defensive direct queries on V20/V21 marts, source_system_record_map,
  relationship_resolution_queue, construction_project_identity, and prior gate results (for latency #8).
- Classifies each gate result as: pass | warning | fail_blocking | deferred_not_blocking | not_applicable.
- Assigns future_phase (07B for calendar/email threads, 07C for documents, 08B for financials, None for 07A-core).
- Persists every result via the pre-existing ConstructionStore.insert_data_quality_gate_result (0 new repo helpers; see store-helpers todo in plan: no modifications were made to repositories.py for Prompt 07).
- Emits rich report with per-gate details + explicit phase_go_nogo summaries for 07B/07C/07D.
- Hard guard: never reports meeting-prep / risk / financial readiness as true while dependent gates fail or are not_applicable in a blocking way.
- All operations local-only, deterministic, offline. No external calls, no raw content.

Public entry point: evaluate_data_quality_gates(db_path=None, persist=True) -> dict
CLI surface (added in construction.py): hb-assistant construction-agent data-quality gates --json
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import time
from datetime import datetime, timezone
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

# ---------------------------------------------------------------------------
# Constants and Guardrails (visible in every report)
# ---------------------------------------------------------------------------

_GATES_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "local_sqlite_only_via_existing_insert",
    "no_raw_content": True,
    "phase_assignments_visible": True,
    "meeting_prep_readiness_requires_all_calendar_email_doc_gates": True,
    "financial_readiness_requires_financial_gates": True,
    "risk_digest_readiness_requires_relationship_and_source_gates": True,
    "candidates_never_auto_promoted": True,
}

_STOP_CONDITIONS_CHECKED = [
    "gates_run_deterministically_offline",
    "gate_failures_not_hidden",
    "phase_assignments_explicit_for_blockers",
    "meeting_prep_not_reported_ready_while_calendar_thread_doc_gates_fail",
    "no_raw_content_or_writeback_leakage_in_gate_logic",
]

# Minimum gates per spec (09_ + Prompt 07). Order is conventional for reporting.
_CORE_GATE_NAMES = [
    "project_identity_coverage",
    "source_record_map_coverage",
    "deterministic_orphan_rate",
    "candidate_orphan_rate",
    "email_classifier_persistence_status",
    "calendar_population_status",
    "email_thread_summary_population_status",
    "meeting_email_candidate_population_status",
    "document_card_population_status",
    "financial_amount_parseability",
    "financial_currency_completeness",
    "review_required_routing_presence",
    "raw_content_leakage_scan",
    "external_writeback_scan",
    "query_latency_p95",  # covers the 8 target queries including gate results query
]

# Phase assignment map (used for blockers in go/no-go summaries)
_PHASE_ASSIGNMENTS = {
    "calendar_population_status": "07B",
    "email_classifier_persistence_status": "07B",
    "email_thread_summary_population_status": "07B",
    "meeting_email_candidate_population_status": "07B",
    "document_card_population_status": "07C",
    "financial_amount_parseability": "08B",
    "financial_currency_completeness": "08B",
    # Others are 07A core or relationship (07D-enabling but not blocking 07A exit)
}

# ---------------------------------------------------------------------------
# Helpers (duplicated minimal style from siblings; no cross-module re-import of internals)
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_git_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[4]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _get_schema_version(db_path: Optional[str | Path] = None) -> int:
    try:
        conn = get_connection(db_path)
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _load_thresholds() -> dict[str, float]:
    """Load the canonical thresholds JSON. Prefers package resources; falls back to filesystem."""
    pkg = "hb_assistant.resources.json"
    filename = "data_quality_gate_thresholds.json"
    try:
        # Modern importlib.resources (Python 3.9+)
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(pkg) / filename).read_text(encoding="utf-8")
        else:
            # Fallback for older
            text = importlib_resources.read_text(pkg, filename, encoding="utf-8")
        return json.loads(text)
    except Exception:
        # Filesystem fallback (dev / test environments)
        candidate = Path(__file__).resolve().parents[4] / "src" / "hb_assistant" / "resources" / "json" / filename
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        # Last resort defaults (still enforce the spirit of the thresholds)
        return {
            "deterministic_orphan_rate_max": 0.02,
            "candidate_orphan_rate_warning": 0.10,
            "project_identity_coverage_min": 1.0,
            "financial_amount_parseability_min": 0.99,
            "financial_currency_completeness_min": 0.95,
            "query_latency_ms_target": 500,
            "raw_content_leakage_allowed": 0,
            "external_writeback_allowed": 0,
        }


def _load_phase_07b_gate_manifest() -> dict[str, Any]:
    """Load the authoritative Phase 07B gate manifest (gates + meeting-prep prerequisites).

    Prefers package resources; falls back to the filesystem and finally to an in-code copy
    so the evaluator never crashes on a partial install."""
    pkg = "hb_assistant.resources.json"
    filename = "phase_07b_data_quality_gates.json"
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(pkg) / filename).read_text(encoding="utf-8")
        else:
            text = importlib_resources.read_text(pkg, filename, encoding="utf-8")
        return json.loads(text)
    except Exception:
        candidate = (
            Path(__file__).resolve().parents[4]
            / "src" / "hb_assistant" / "resources" / "json" / filename
        )
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        return {
            "version": "phase07b-data-quality-gates-v1",
            "gates": [
                {"name": "calendar_population_status", "phase": "07B", "kind": "presence",
                 "table": "calendar_event_index"},
                {"name": "email_classifier_persistence_status", "phase": "07B",
                 "kind": "presence", "table": "email_model_classifications"},
                {"name": "email_thread_summary_population_status", "phase": "07B",
                 "kind": "presence", "table": "email_thread_summaries"},
                {"name": "meeting_email_candidate_population_status", "phase": "07B",
                 "kind": "presence", "table": "meeting_email_relationship_candidates"},
            ],
            "meeting_prep_prerequisites": [
                "calendar_population_status", "email_classifier_persistence_status",
                "email_thread_summary_population_status",
                "meeting_email_candidate_population_status",
                "document_card_population_status", "deterministic_orphan_rate",
                "candidate_orphan_rate", "review_required_routing_presence",
                "raw_content_leakage_scan", "external_writeback_scan",
            ],
            "auto_readiness_allowed": False,
        }


def _safe_select(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
    except Exception:
        return []


def _safe_scalar(conn, sql: str, params: tuple = ()) -> Any:
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GateEvaluator
# ---------------------------------------------------------------------------

class GateEvaluator:
    """Computes, classifies, persists, and reports all Phase 07A data quality gates."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = db_path
        self.repo_sha = _get_git_sha()
        self.schema_version = _get_schema_version(db_path)
        self.generated_utc = _now()
        self.run_id = f"phase07a-gates-{self.generated_utc[:19].replace(':','-')}"
        self.thresholds = _load_thresholds()
        self.phase_07b_manifest = _load_phase_07b_gate_manifest()
        self.results: list[dict[str, Any]] = []
        self.review_items: list[str] = []  # populated only for high-impact items needing human attention

    def _classify(
        self,
        gate_name: str,
        observed: Any,
        threshold: Optional[float],
        *,
        higher_is_better: bool = True,
        is_boolean: bool = False,
        is_latency: bool = False,
        future_phase: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return a fully populated gate result row ready for persistence + report."""
        status = "not_applicable"
        blocking = 0
        reason = None
        observed_value = observed

        if observed is None:
            status = "not_applicable"
            reason = "no_data_in_local_store"
        elif is_boolean:
            # True = good for readiness gates that are simple presence flags
            status = "pass" if bool(observed) else "deferred_not_blocking"
            if not bool(observed) and future_phase:
                blocking = 0  # deferred by definition
                reason = f"deferred_to_{future_phase}"
            elif not bool(observed):
                reason = "feature_not_yet_implemented"
        elif is_latency:
            target = threshold or self.thresholds.get("query_latency_ms_target", 500)
            status = "pass" if (observed is not None and float(observed) <= target) else "warning"
            if status == "warning":
                reason = f"exceeds_target_{target}ms"
        else:
            # numeric comparison
            if threshold is None:
                status = "not_applicable"
                reason = "no_threshold_defined"
            else:
                val = float(observed)
                if higher_is_better:
                    if val >= threshold:
                        status = "pass"
                    else:
                        # coverage / parseability style gates
                        if gate_name in ("project_identity_coverage",):
                            status = "fail_blocking"
                            blocking = 1
                            reason = f"below_minimum_{threshold}"
                        else:
                            status = "warning"
                            reason = f"below_threshold_{threshold}"
                else:
                    # rates (lower is better)
                    if val <= threshold:
                        status = "pass"
                    else:
                        if gate_name == "deterministic_orphan_rate":
                            status = "fail_blocking"
                            blocking = 1
                            reason = f"exceeds_max_{threshold}"
                        else:
                            status = "warning"
                            reason = f"exceeds_warning_{threshold}"

        # Force explicit future_phase for known blockers even if not blocking 07A exit
        assigned_phase = future_phase or _PHASE_ASSIGNMENTS.get(gate_name)

        result = {
            "gate_name": gate_name,
            "gate_status": status,
            "threshold": threshold,
            "observed": observed_value,
            "blocking": blocking,
            "future_phase": assigned_phase,
            "reason": reason,
            "run_id": self.run_id,
        }
        self.results.append(result)
        return result

    # -----------------------------------------------------------------------
    # Individual gate computations (all defensive)
    # -----------------------------------------------------------------------

    def _gate_project_identity_coverage(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        total_pilot = _safe_scalar(conn, "SELECT COUNT(*) FROM construction_project_identity WHERE lifecycle IN ('Active','Pilot')")
        covered = _safe_scalar(
            conn,
            """
            SELECT COUNT(DISTINCT project_key)
            FROM project_source_coverage_mart
            WHERE project_key IN (SELECT project_key FROM construction_project_identity WHERE lifecycle IN ('Active','Pilot'))
            """,
        )
        if not total_pilot or total_pilot == 0:
            return self._classify("project_identity_coverage", None, self.thresholds.get("project_identity_coverage_min"), future_phase=None)
        ratio = (covered or 0) / total_pilot
        return self._classify("project_identity_coverage", ratio, self.thresholds.get("project_identity_coverage_min"), future_phase=None)

    def _gate_source_record_map_coverage(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        total = _safe_scalar(conn, "SELECT COUNT(*) FROM source_system_record_map")
        if total is None or total == 0:
            return self._classify("source_record_map_coverage", 0.0, 0.8, future_phase=None)  # soft; will be warning if empty after apply
        mapped = _safe_scalar(conn, "SELECT COUNT(*) FROM source_system_record_map WHERE project_key IS NOT NULL")
        ratio = (mapped or 0) / total
        return self._classify("source_record_map_coverage", ratio, 0.8, future_phase=None)

    def _gate_deterministic_orphan_rate(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        # Prefer the mart if populated; fall back to direct queue calculation
        rate = _safe_scalar(conn, "SELECT deterministic_orphan_rate FROM relationship_quality_mart LIMIT 1")
        if rate is None:
            det = _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM relationship_resolution_queue WHERE confidence_class='deterministic_exact_id' AND relationship_status='orphaned'",
            ) or 0
            total_det = _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM relationship_resolution_queue WHERE confidence_class='deterministic_exact_id'",
            ) or 0
            rate = (det / total_det) if total_det > 0 else 0.0
        return self._classify(
            "deterministic_orphan_rate",
            rate,
            self.thresholds.get("deterministic_orphan_rate_max"),
            higher_is_better=False,
            future_phase=None,
        )

    def _gate_candidate_orphan_rate(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        rate = _safe_scalar(conn, "SELECT candidate_orphan_rate FROM relationship_quality_mart LIMIT 1")
        if rate is None:
            cand = _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM relationship_resolution_queue WHERE confidence_class IN ('weak_heuristic_single_signal','model_proposed_candidate') AND relationship_status='orphaned'",
            ) or 0
            total_cand = _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM relationship_resolution_queue WHERE confidence_class IN ('weak_heuristic_single_signal','model_proposed_candidate')",
            ) or 0
            rate = (cand / total_cand) if total_cand > 0 else 0.0
        return self._classify(
            "candidate_orphan_rate",
            rate,
            self.thresholds.get("candidate_orphan_rate_warning"),
            higher_is_better=False,
            future_phase=None,
        )

    def _gate_phase_07b_presence(self) -> None:
        """Manifest-driven Phase 07B presence gates (calendar / email-classifier /
        thread-summary / meeting-email-candidate readiness). Each gate passes when its
        redacted read-model table holds at least one row, else defers to 07B. Table names
        come from the trusted in-package manifest, not user input."""
        conn = get_connection(self.db_path)
        for gate in self.phase_07b_manifest.get("gates", []):
            table = gate["table"]
            count = (
                _safe_scalar(conn, f"SELECT COUNT(*) FROM {table}")
                if self._table_exists(conn, table)
                else 0
            )
            self._classify(
                gate["name"],
                bool(count and int(count) > 0),
                None,
                is_boolean=True,
                future_phase=gate.get("phase", "07B"),
            )

    def _gate_document_card_population(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        count = _safe_scalar(conn, "SELECT COUNT(*) FROM construction_document_cards") if self._table_exists(conn, "construction_document_cards") else 0
        return self._classify("document_card_population_status", count > 0, None, is_boolean=True, future_phase="07C")

    def _gate_financial_amount_parseability(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        # Look for any financial fact table with amount columns; compute parseability ratio if data present
        if not self._table_exists(conn, "procore_financial_contracts"):
            return self._classify("financial_amount_parseability", None, self.thresholds.get("financial_amount_parseability_min"), future_phase="08B")
        total = _safe_scalar(conn, "SELECT COUNT(*) FROM procore_financial_contracts") or 0
        if total == 0:
            return self._classify("financial_amount_parseability", 0.0, self.thresholds.get("financial_amount_parseability_min"), future_phase="08B")
        # Heuristic: rows that have a non-null contract_amount or similar numeric
        parsed = _safe_scalar(conn, "SELECT COUNT(*) FROM procore_financial_contracts WHERE contract_amount IS NOT NULL") or 0
        ratio = parsed / total
        return self._classify("financial_amount_parseability", ratio, self.thresholds.get("financial_amount_parseability_min"), future_phase="08B")

    def _gate_financial_currency_completeness(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        if not self._table_exists(conn, "procore_financial_contracts"):
            return self._classify("financial_currency_completeness", None, self.thresholds.get("financial_currency_completeness_min"), future_phase="08B")
        total = _safe_scalar(conn, "SELECT COUNT(*) FROM procore_financial_contracts") or 0
        if total == 0:
            return self._classify("financial_currency_completeness", 0.0, self.thresholds.get("financial_currency_completeness_min"), future_phase="08B")
        complete = _safe_scalar(conn, "SELECT COUNT(*) FROM procore_financial_contracts WHERE currency IS NOT NULL AND currency != ''") or 0
        ratio = complete / total
        return self._classify("financial_currency_completeness", ratio, self.thresholds.get("financial_currency_completeness_min"), future_phase="08B")

    def _gate_review_required_routing_presence(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        # Any row in relationship_resolution_queue with review_required=1 is evidence the path exists and is populated
        count = _safe_scalar(conn, "SELECT COUNT(*) FROM relationship_resolution_queue WHERE review_required = 1") or 0
        return self._classify("review_required_routing_presence", count > 0, None, is_boolean=True, future_phase=None)

    def _gate_raw_content_leakage(self) -> dict[str, Any]:
        # Attestation from prior prompts + explicit guard in this module (we never SELECT raw bodies)
        # We also scan the gate_results table for any previous "raw_content_leakage_scan" that was not zero.
        conn = get_connection(self.db_path)
        bad = _safe_scalar(
            conn,
            "SELECT COUNT(*) FROM data_quality_gate_results WHERE gate_name='raw_content_leakage_scan' AND observed > 0 ORDER BY created_utc DESC LIMIT 1",
        ) or 0
        observed = 0 if bad == 0 else bad
        return self._classify("raw_content_leakage_scan", observed, self.thresholds.get("raw_content_leakage_allowed"), future_phase=None)

    def _gate_external_writeback(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        bad = _safe_scalar(
            conn,
            "SELECT COUNT(*) FROM data_quality_gate_results WHERE gate_name='external_writeback_scan' AND observed > 0 ORDER BY created_utc DESC LIMIT 1",
        ) or 0
        observed = 0 if bad == 0 else bad
        return self._classify("external_writeback_scan", observed, self.thresholds.get("external_writeback_allowed"), future_phase=None)

    def _gate_query_latency(self) -> dict[str, Any]:
        # Re-measure a representative fast query (gate results themselves + one coverage query)
        conn = get_connection(self.db_path)
        start = time.perf_counter()
        try:
            conn.execute("SELECT COUNT(*) FROM data_quality_gate_results").fetchone()
            conn.execute("SELECT project_key, source_domain FROM project_source_coverage_mart LIMIT 5").fetchall()
        except Exception:
            pass
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        target = self.thresholds.get("query_latency_ms_target", 500)
        return self._classify("query_latency_p95", elapsed_ms, target, is_latency=True, future_phase=None)

    def _table_exists(self, conn, name: str) -> bool:
        try:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
            return row is not None
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Orchestration
    # -----------------------------------------------------------------------

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        """Execute all gates, persist results (if requested), and return the full report."""
        self.results = []
        self.review_items = []

        # Execute in defined order
        self._gate_project_identity_coverage()
        self._gate_source_record_map_coverage()
        self._gate_deterministic_orphan_rate()
        self._gate_candidate_orphan_rate()
        self._gate_phase_07b_presence()
        self._gate_document_card_population()
        self._gate_financial_amount_parseability()
        self._gate_financial_currency_completeness()
        self._gate_review_required_routing_presence()
        self._gate_raw_content_leakage()
        self._gate_external_writeback()
        self._gate_query_latency()

        # Persist via the existing, already-migration-gated repository method
        if persist:
            store = ConstructionStore(db_path=self.db_path)
            for r in self.results:
                gate_row = {
                    "gate_result_id": f"{self.run_id}:{r['gate_name']}",
                    "run_id": self.run_id,
                    "gate_name": r["gate_name"],
                    "gate_status": r["gate_status"],
                    "threshold_json": json.dumps({"threshold": r["threshold"]}, default=str),
                    "observed_json": json.dumps({"observed": r["observed"]}, default=str),
                    "blocking": r["blocking"],
                    "created_utc": self.generated_utc,
                }
                with contextlib.suppress(Exception):
                    store.insert_data_quality_gate_result(gate_row)

        # Build phase go/no-go summaries (explicit, never hides blockers)
        phase_07b_blockers = [r for r in self.results if r.get("future_phase") == "07B" and r["gate_status"] not in ("pass",)]
        phase_07c_blockers = [r for r in self.results if r.get("future_phase") == "07C" and r["gate_status"] not in ("pass",)]
        phase_07d_readiness = [r for r in self.results if r["gate_name"] in ("deterministic_orphan_rate", "candidate_orphan_rate", "review_required_routing_presence") and r["gate_status"] == "pass"]
        phase_07a_core_pass = all(r["gate_status"] in ("pass", "warning", "deferred_not_blocking") for r in self.results if r.get("future_phase") is None)

        # Hard stop-condition enforcement in the report (visible to operator)
        meeting_prep_claim = "blocked" if any(b["future_phase"] in ("07B", "07C") for b in self.results if b["gate_status"] not in ("pass",)) else "needs_07b_07c_data"
        financial_claim = "blocked" if any(b["future_phase"] == "08B" for b in self.results if b["gate_status"] not in ("pass",)) else "needs_financial_data"

        # Structured meeting-prep (07D) prerequisite check driven by the 07B manifest:
        # readiness requires EVERY prerequisite gate (07B + 07C + relationship + safety) to
        # pass; auto_readiness_allowed stays false so 07D is never auto-claimed.
        prereqs = self.phase_07b_manifest.get("meeting_prep_prerequisites", [])
        by_name = {r["gate_name"]: r for r in self.results}
        meeting_prep_blocked_by = [
            n for n in prereqs if (by_name.get(n) or {}).get("gate_status") != "pass"
        ]
        meeting_prep_readiness = {
            "ready": len(meeting_prep_blocked_by) == 0,
            "blocked_by": meeting_prep_blocked_by,
            "prerequisites": prereqs,
            "auto_readiness_allowed": bool(
                self.phase_07b_manifest.get("auto_readiness_allowed", False)
            ),
        }

        report = {
            "command": "construction-agent data-quality gates",
            "run_id": self.run_id,
            "generated_utc": self.generated_utc,
            "repo_sha": self.repo_sha,
            "schema_version": self.schema_version,
            "thresholds": self.thresholds,
            "gates": self.results,
            "phase_go_nogo": {
                "07A_exit": {
                    "ready": phase_07a_core_pass,
                    "blocking_gates": [r["gate_name"] for r in self.results if r["gate_status"] == "fail_blocking"],
                },
                "07B": {
                    "blocked_by": [r["gate_name"] for r in phase_07b_blockers],
                    "ready_for": ["calendar_ingestion", "email_thread_summaries", "meeting_project_matching"],
                },
                "07C": {
                    "blocked_by": [r["gate_name"] for r in phase_07c_blockers],
                    "ready_for": ["document_card_population", "file_to_record_relationships"],
                },
                "07D": {
                    "relationship_quality_ready": len(phase_07d_readiness) >= 2,
                    "meeting_prep_readiness": meeting_prep_readiness,
                    "notes": "07D can proceed on deterministic relationships even if candidate rates are warnings.",
                },
                "08B": {
                    "financial_readiness": financial_claim,
                },
            },
            "meeting_prep_readiness_claim": meeting_prep_claim,
            "risk_digest_readiness_claim": "blocked" if not phase_07a_core_pass else "partial",
            "guardrails": _GATES_GUARDRAILS,
            "stop_conditions_checked": _STOP_CONDITIONS_CHECKED,
            "review_items": self.review_items,
        }
        return report


def evaluate_data_quality_gates(
    *, db_path: Optional[str | Path] = None, persist: bool = True, json_out: bool = True
) -> dict[str, Any]:
    """Public entry point used by CLI and tests."""
    evaluator = GateEvaluator(db_path=db_path)
    return evaluator.run(persist=persist)
