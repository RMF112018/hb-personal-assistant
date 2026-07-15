"""SourceRefreshOrchestrator: one safe daily local data refresh.

Stage sequence (each stage is failure-isolated; a stage failure degrades overall
status but never aborts the run):

  1. preflight   — schema/DB readiness, repo SHA, no-writeback attestation
  2. procore     — auth status, optional token refresh, mapped-project sync → SQLite
  3. graph       — auth status, mail-thread-summary (local) + calendar/files (live, gated)
  4. rebuild     — approved-source manifest, coverage parity, vector index, Daily Brief V2,
                   no-raw-vector + MCP attestations
  5. finalize    — consolidated JSON, guardrails, next operator action, evidence

Dry-run (default) plans only and writes nothing. ``--apply`` (which the CLI gates
behind ``--confirm``) upserts to local SQLite only. Any *live external read*
(Procore live GET, Graph calendar/files) additionally requires ``--confirm`` and the
relevant live gate; without it those reads are skipped (never silently performed).

The orchestrator imports the underlying surfaces at module scope so tests can patch
them at this module's namespace.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from hb_assistant.config.path_policy import PathPolicy

# --- Second-brain (Phase-09) rebuild + proof surfaces -----------------------------
from hb_assistant.construction.second_brain.daily_brief.packet import (
    build_daily_brief_packet_v2,
    build_daily_brief_packet_v2_proof,
)
from hb_assistant.construction.second_brain.daily_brief.rendered_quality import (
    build_daily_brief_v2_quality_proof,
)
from hb_assistant.construction.second_brain.local_ai.projection_activation import (
    run_email_calendar_projection_stage,
)
from hb_assistant.construction.second_brain.mcp.proof import (
    build_no_mcp_writeback_proof,
    build_no_raw_mcp_access_proof,
)
from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
    build_coverage_parity_closeout,
)
from hb_assistant.construction.second_brain.retrieval.no_raw_vector_index_proof import (
    build_no_raw_vector_index_proof,
)
from hb_assistant.construction.second_brain.retrieval.source_manifest import (
    build_approved_source_manifest,
    build_approved_source_manifest_proof,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    build_vector_index_apply,
    build_vector_index_dry_run,
)

# --- Procore surfaces (patchable at this namespace) -------------------------------
from hb_assistant.procore.auth import check_auth_status
from hb_assistant.procore.budget_detail_read_model import project_budget_detail_read_model
from hb_assistant.procore.daily_refresh_plan import (
    UNSUPPORTED_ENDPOINTS,
    build_daily_refresh_plan,
    classify_receipt,
    daily_log_window,
    is_degraded_status,
    is_skipped_status,
)
from hb_assistant.procore.live_gate import (
    assert_live_mapping_strict,
    live_env_active,
)
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.procore.loader import load_procore_projects
from hb_assistant.procore.models import LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES
from hb_assistant.procore.projection_audit import projection_audit, projection_schema_audit
from hb_assistant.procore.projection_engine import (
    MODE_ENFORCE,
    UnknownProjectionPath,
    backfill_endpoint_specific_from_raw_payloads,
)
from hb_assistant.procore.structured_analytics import RAW_LANDING_TABLE, SOURCE_QUALITY_LIVE_FULL
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

# Canonical Procore persistence path (the tables operational read-models consume).
PROCORE_CANONICAL_TABLES = (
    "procore_live_records",
    "procore_live_sync_runs",
    "procore_live_sync_watermarks",
)

BUDGET_DETAIL_ENDPOINT_IDS = (
    "budget-views",
    "budget-detail-columns",
    "budget-detail-rows",
)

BUDGET_DETAIL_STRUCTURED_TABLES = (
    "procore_ep_budget_views",
    "procore_ep_budget_detail_columns",
    "procore_ep_budget_detail_rows",
    "procore_ep_budget_detail_row_cells",
)

COMMAND = "construction-agent refresh-sources"

# Defense-in-depth scrub list applied to any serialized evidence.
_REDACT_TOKENS = (
    "access_token",
    "refresh_token",
    "client_secret",
    "Authorization",
    "authorization",
    "Bearer",
    "bearer",
    "PRIVATE KEY",
    "SECRET",
)

# Static guardrail attestation. Each flag mirrors an invariant enforced by the
# underlying surfaces (SQLite CHECK constraints, scope policy, proof scans).
_GUARDRAILS_BASE: dict[str, bool] = {
    "no_procore_writeback": True,
    "no_m365_writeback": True,
    "no_raw_email_or_calendar_body": True,
    "no_join_url_persisted": True,
    "no_raw_procore_payload": True,
    "no_prompts_or_model_responses_persisted": True,
    "no_vectors_in_sqlite": True,
    "mcp_exposure_unchanged": True,
    "local_sqlite_only": True,
    "fail_closed": True,
}


@dataclass(frozen=True)
class RefreshOptions:
    """Resolved CLI flags for one refresh invocation."""

    all_: bool = True
    apply: bool = False
    confirm: bool = False
    procore_only: bool = False
    graph_only: bool = False
    skip_vector: bool = False
    skip_daily_brief_proof: bool = False
    brief_date: Optional[str] = None
    # Local-only / mock mode: never touch live external systems (no Procore/Graph
    # auth/status/probe/read). Rebuild from existing local SQLite only. Used by the dev
    # scheduler and by production scheduled runs when live reads are config-disabled.
    mock_data: bool = False
    # Per-source live-read switches. Default True preserves the manual
    # `refresh-sources --apply --confirm` behavior; scheduled jobs always set these
    # explicitly rather than relying on the defaults.
    allow_procore_live: bool = True
    allow_graph_live: bool = True
    procore_project_scope: Literal["pilot_only", "all_mapped"] = "pilot_only"
    procore_project_keys: tuple[str, ...] = ()

    @property
    def dry_run(self) -> bool:
        return not self.apply

    @property
    def live_reads_enabled(self) -> bool:
        """True only when this run may perform any live external read."""
        return not self.mock_data and (self.allow_procore_live or self.allow_graph_live)


def _safe_git_sha() -> Optional[str]:
    """Best-effort short repo SHA (safe for evidence). Never raises."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        return out or None
    except Exception:
        return None


def _zero_counts() -> dict[str, int]:
    return {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0, "planned": 0}


def _status_histogram(endpoints: list[dict[str, Any]]) -> dict[str, int]:
    """Count endpoint rows by their taxonomy status code (operator-readable)."""
    hist: dict[str, int] = {}
    for row in endpoints:
        code = str(row.get("status", "unknown"))
        hist[code] = hist.get(code, 0) + 1
    return hist


@dataclass
class _Accumulator:
    """Mutable run state shared across stages."""

    failures: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    degraded: bool = False


class SourceRefreshOrchestrator:
    """Sequences existing source-sync + rebuild surfaces into one consolidated run."""

    def __init__(
        self,
        *,
        db_path: Optional[Path] = None,
        evidence_dir: Optional[Path] = None,
    ) -> None:
        self.pp = PathPolicy()
        self.db_path: Path = db_path or self.pp.get_db_path()
        self.evidence_dir: Path = evidence_dir or (
            self.pp.get_evidence_dir() / "source-refresh-runs"
        )
        self.repo_sha = _safe_git_sha()
        self._acc = _Accumulator()

    # -- small helpers -------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _stage(self, name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Run a stage with failure isolation. Returns the stage result or a safe stub."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — isolation is the whole point
            self._acc.degraded = True
            reason = f"{type(exc).__name__}: {str(exc)[:200]}"
            self._acc.failures.append({"stage": name, "status": "failed", "reason": reason})
            return {"status": "failed", "reason": reason}

    def _warn(self, message: str) -> None:
        if message not in self._acc.warnings:
            self._acc.warnings.append(message)

    def _db_path_str(self) -> str:
        return str(self.db_path)

    def _schema_version(self) -> int:
        try:
            return int(SQLiteMigrator(self.db_path).current_version())
        except Exception:
            return 0

    # -- public entry --------------------------------------------------------------

    def run(self, *, options: RefreshOptions) -> dict[str, Any]:
        """Execute the full refresh and return one consolidated, redacted summary."""
        self._acc = _Accumulator()
        # Ensure the resolved (possibly isolated dev) DB directory exists so every stage
        # binds to self.db_path — never the ambient/production DB.
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        summary: dict[str, Any] = {
            "command": COMMAND,
            "generated_utc": self._now_iso(),
            "repo_sha": self.repo_sha,
            "dry_run": options.dry_run,
            "apply": options.apply,
            "mock_data": options.mock_data,
            "live_reads_enabled": options.live_reads_enabled,
            "live_mode": "live_source" if options.live_reads_enabled else "local_only",
            "status": "ok",
            "preflight": {},
            "procore_auth_status": None,
            "graph_auth_status": None,
            "procore_sync_summary": {"status": "skipped", "reason": "not_run"},
            "procore_projection_summary": {"status": "skipped", "reason": "not_run"},
            "graph_sync_summary": {"status": "skipped", "reason": "not_run"},
            "email_calendar_projection_summary": {"status": "skipped", "reason": "not_run"},
            "sqlite_upsert_summary": {
                "procore": _zero_counts(),
                "graph": _zero_counts(),
                "total": _zero_counts(),
            },
            "retrieval_rebuild_summary": {"status": "skipped", "reason": "not_run"},
            "vector_rebuild_summary": {"status": "skipped", "reason": "not_run"},
            "daily_brief_v2_summary": {"status": "skipped", "reason": "not_run"},
            "guardrails": dict(_GUARDRAILS_BASE),
            "warnings": [],
            "failures": [],
            "next_operator_action": "none",
        }

        try:
            summary["preflight"] = self._stage("preflight", lambda: self._preflight(options))

            if not options.graph_only:
                summary["procore_sync_summary"] = self._stage(
                    "procore", lambda: self._procore_stage(options)
                )
                summary["procore_auth_status"] = summary["procore_sync_summary"].get("auth_status")
                summary["procore_projection_summary"] = self._stage(
                    "procore_projection",
                    lambda: self._procore_projection_stage(
                        options, summary["procore_sync_summary"]
                    ),
                )
            else:
                summary["procore_sync_summary"] = {"status": "skipped", "reason": "graph_only"}
                summary["procore_projection_summary"] = {
                    "status": "skipped",
                    "reason": "graph_only",
                }

            if not options.procore_only:
                summary["graph_sync_summary"] = self._stage(
                    "graph", lambda: self._graph_stage(options)
                )
                summary["graph_auth_status"] = summary["graph_sync_summary"].get("auth_status")
                summary["email_calendar_projection_summary"] = self._stage(
                    "email_calendar_projection",
                    lambda: self._email_calendar_projection_stage(
                        options, summary["graph_sync_summary"]
                    ),
                )
            else:
                summary["graph_sync_summary"] = {"status": "skipped", "reason": "procore_only"}
                summary["email_calendar_projection_summary"] = {
                    "status": "skipped",
                    "reason": "procore_only",
                }

            self._aggregate_upserts(summary)

            rebuild = self._stage("rebuild", lambda: self._rebuild_stage(options))
            summary["retrieval_rebuild_summary"] = rebuild.get("retrieval", rebuild)
            summary["vector_rebuild_summary"] = rebuild.get(
                "vector", {"status": "skipped", "reason": "not_run"}
            )
            summary["daily_brief_v2_summary"] = rebuild.get(
                "daily_brief_v2", {"status": "skipped", "reason": "not_run"}
            )
            for key, value in rebuild.get("guardrails", {}).items():
                summary["guardrails"][key] = value
        except Exception as exc:  # noqa: BLE001 — top-level safety net
            self._acc.failures.append(
                {"stage": "run", "status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
            )
            summary["status"] = "failed"

        return self._finalize(summary, options)

    # -- stage 1: preflight --------------------------------------------------------

    def _preflight(self, options: RefreshOptions) -> dict[str, Any]:
        current = self._schema_version()
        schema_ok = current >= LATEST_SCHEMA_VERSION
        migrated = False

        # Operator decision: auto-migrate only under apply+confirm.
        if options.apply and options.confirm and not schema_ok:
            try:
                # NF-F-001 (N-A5a): the refresh is an ordinary data path, not a migration-authority
                # route. Self-heal only a non-managed dev/rehearsal/workspace DB; a behind managed
                # DB is NOT migrated ambiently here — it degrades below and must be migrated via the
                # authorized startup/admin route.
                from hb_assistant.store.schema_readiness import self_heal_if_non_managed

                before_version = current
                self_heal_if_non_managed(self.db_path)
                current = self._schema_version()
                schema_ok = current >= LATEST_SCHEMA_VERSION
                migrated = current > before_version
            except Exception as exc:  # noqa: BLE001
                self._acc.degraded = True
                self._acc.failures.append(
                    {
                        "stage": "preflight",
                        "status": "failed",
                        "reason": f"auto_migrate_failed: {type(exc).__name__}: {str(exc)[:160]}",
                    }
                )

        if not schema_ok:
            self._warn(
                f"local schema v{current} is behind LATEST_SCHEMA_VERSION "
                f"v{LATEST_SCHEMA_VERSION}; rebuild surfaces will fail closed"
            )

        return {
            "status": "ok" if schema_ok else "schema_behind",
            "schema_version": current,
            "latest_schema_version": LATEST_SCHEMA_VERSION,
            "schema_ok": schema_ok,
            "auto_migrated": migrated,
            "db_path": self._db_path_str(),
            "repo_sha": self.repo_sha,
            "no_writeback_attestation": True,
        }

    # -- stage 2: procore ----------------------------------------------------------

    def _procore_stage(self, options: RefreshOptions) -> dict[str, Any]:
        if options.mock_data or not options.allow_procore_live:
            # Local-only/mock: never call Procore auth/status/probe/read. Rebuild stages
            # read existing local SQLite. No credentials required.
            return {
                "status": "mock_data_local_only" if options.mock_data else "live_disabled",
                "auth_status": "skipped",
                "ready_for_live_calls": False,
                "live_read_performed": False,
                "counts": _zero_counts(),
            }

        report = check_auth_status()
        auth_status = report.status
        ready = bool(report.ready_for_live_calls)

        if options.apply and not ready:
            # Fail closed: never perform a live read when auth is not ready.
            self._acc.degraded = True
            return {
                "status": "blocked_auth_not_ready",
                "auth_status": auth_status,
                "ready_for_live_calls": ready,
                "hint": report.hint,
                "live_read_performed": False,
                "counts": _zero_counts(),
            }

        registry = load_procore_projects()
        scope = self._resolve_procore_project_scope(registry, options)
        if scope["blocking_rejections"]:
            self._acc.degraded = True
            return {
                "status": "blocked_project_scope",
                "auth_status": auth_status,
                "ready_for_live_calls": ready,
                "live_read_performed": False,
                "project_scope_policy": scope,
                "counts": _zero_counts(),
            }
        project_keys = [p["project_key"] for p in scope["selected_projects"]]
        if not project_keys:
            self._acc.degraded = True
            return {
                "status": "no_live_refresh_eligible_projects",
                "auth_status": auth_status,
                "ready_for_live_calls": ready,
                "live_read_performed": False,
                "project_scope_policy": scope,
                "counts": _zero_counts(),
            }

        live_env = live_env_active()
        do_live_apply = (
            options.apply and options.confirm and ready and live_env and options.allow_procore_live
        )
        if options.apply and not live_env:
            self._warn(
                "Procore apply requested but HB_PROCORE_LIVE is not set; live read gated "
                "— produced dry-run plan only"
            )
        if do_live_apply:
            assert_live_mapping_strict(registry, project_keys)

        # Daily refresh now reads through the canonical EndpointAdapter registry via
        # run_live_sync (writing procore_live_*), replacing the stale per-project seed
        # fanout. Dry-run plans only (no live call); apply executes the live chain.
        plan = build_daily_refresh_plan()
        if not do_live_apply:
            return self._procore_plan_only(plan, scope, auth_status, ready, live_env)
        return self._procore_live_execute(plan, scope, options, auth_status, ready, live_env)

    @staticmethod
    def _resolve_procore_project_scope(registry: Any, options: RefreshOptions) -> dict[str, Any]:
        """Resolve scheduled Procore project scope with explicit skipped/rejected reasons."""
        allowlist = tuple(k.strip() for k in options.procore_project_keys if k.strip())
        allowset = set(allowlist)
        by_key = {p.hb_project_key: p for p in registry.projects}
        selected: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        blocking: list[dict[str, Any]] = []

        for key in allowlist:
            if key not in by_key:
                blocking.append({"project_key": key, "reason": "unknown_key"})

        for project in registry.projects:
            key = project.hb_project_key
            status = str(project.status)
            has_project_id = bool((project.procore_project_id or "").strip())
            row = {
                "project_key": key,
                "status": status,
                "procore_project_id_present": has_project_id,
            }
            allowlisted = not allowset or key in allowset
            if not allowlisted:
                skipped.append({**row, "reason": "not_in_allowlist"})
                continue

            if options.procore_project_scope == "pilot_only" and status != "pilot":
                reason = f"status_not_pilot:{status}"
                if allowset:
                    blocking.append({**row, "reason": reason})
                else:
                    skipped.append({**row, "reason": reason})
                continue

            if (
                options.procore_project_scope == "all_mapped"
                and status not in LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES
            ):
                reason = f"status_not_live_refresh_eligible:{status}"
                if allowset:
                    blocking.append({**row, "reason": reason})
                else:
                    skipped.append({**row, "reason": reason})
                continue

            if not has_project_id:
                reason = "procore_project_id_empty"
                if allowset:
                    blocking.append({**row, "reason": reason})
                else:
                    skipped.append({**row, "reason": reason})
                continue

            selected.append(row)

        return {
            "scope": options.procore_project_scope,
            "allowlist": list(allowlist),
            "eligible_statuses": list(LIVE_REFRESH_ELIGIBLE_PROJECT_STATUSES),
            "selected_project_count": len(selected),
            "skipped_project_count": len(skipped),
            "blocking_rejection_count": len(blocking),
            "selected_projects": selected,
            "skipped_projects": skipped,
            "blocking_rejections": blocking,
        }

    def _procore_plan_only(
        self,
        plan: tuple[Any, ...],
        scope: dict[str, Any],
        auth_status: str,
        ready: bool,
        live_env: bool,
    ) -> dict[str, Any]:
        """Dry-run posture: describe the canonical plan without any live read or write."""
        endpoints: list[dict[str, Any]] = []
        counts = _zero_counts()
        project_keys = [p["project_key"] for p in scope["selected_projects"]]
        for pe in plan:
            keys = project_keys[:1] if pe.company_level else project_keys
            for key in keys:
                endpoints.append(
                    {
                        "endpoint": pe.canonical_id,
                        "legacy_alias": pe.legacy_alias,
                        "scope": "company" if pe.company_level else key,
                        "date_windowed": pe.date_windowed,
                        "status": "planned",
                    }
                )
                counts["planned"] += 1
        for legacy_id, code in UNSUPPORTED_ENDPOINTS.items():
            endpoints.append(
                {"endpoint": legacy_id, "legacy_alias": legacy_id, "scope": "n/a", "status": code}
            )
            counts["skipped"] += 1
        summary = {
            "endpoints_planned": counts["planned"],
            "endpoints_skipped": counts["skipped"],
            "endpoints_succeeded": 0,
            "contract_bug_failures": 0,
            "externally_blocked": 0,
            "by_status": _status_histogram(endpoints),
        }
        return {
            "status": "planned",
            "auth_status": auth_status,
            "ready_for_live_calls": ready,
            "mode": "dry_run",
            "live_read_performed": False,
            "live_env_active": live_env,
            "persistence_path": "procore_live",
            "canonical_tables": list(PROCORE_CANONICAL_TABLES),
            "project_scope_policy": scope,
            "endpoint_summary": summary,
            "endpoints": endpoints,
            "projects": [{"project_key": k, "status": "planned"} for k in project_keys],
            "counts": counts,
        }

    def _procore_live_execute(
        self,
        plan: tuple[Any, ...],
        scope: dict[str, Any],
        options: RefreshOptions,
        auth_status: str,
        ready: bool,
        live_env: bool,
    ) -> dict[str, Any]:
        """Apply posture: run each canonical endpoint via run_live_sync and aggregate."""
        brief_date = self._resolve_brief_date(options)
        start_date, end_date = daily_log_window(brief_date)
        project_keys = [p["project_key"] for p in scope["selected_projects"]]

        endpoints: list[dict[str, Any]] = []
        per_project: dict[str, dict[str, int]] = {
            k: {"ok": 0, "skipped": 0, "failed": 0} for k in project_keys
        }
        counts = _zero_counts()

        for pe in plan:
            keys = project_keys[:1] if pe.company_level else project_keys
            # A company-level endpoint is fetched once; the remaining pilots are
            # marked intentionally skipped below rather than re-running the
            # company-wide read.
            for key in keys:
                receipt = self._run_live_endpoint(pe, key, start_date, end_date)
                code = classify_receipt(receipt)
                endpoints.append(self._endpoint_row(pe, key, receipt, code))
                self._tally_endpoint(pe, key, code, receipt, counts, per_project)
            if pe.company_level:
                for key in project_keys[1:]:
                    endpoints.append(
                        {
                            "endpoint": pe.canonical_id,
                            "legacy_alias": pe.legacy_alias,
                            "scope": key,
                            "status": "skipped_company_level_already_handled",
                        }
                    )
                    counts["skipped"] += 1
                    per_project[key]["skipped"] += 1

        for legacy_id, code in UNSUPPORTED_ENDPOINTS.items():
            endpoints.append(
                {"endpoint": legacy_id, "legacy_alias": legacy_id, "scope": "n/a", "status": code}
            )
            counts["skipped"] += 1

        projects = [
            {
                "project_key": key,
                "status": "degraded" if tally["failed"] else "ok",
                "endpoints_ok": tally["ok"],
                "endpoints_skipped": tally["skipped"],
                "endpoints_failed": tally["failed"],
            }
            for key, tally in per_project.items()
        ]
        any_failed = counts["failed"] > 0
        stage_status = "degraded" if any_failed else "ok"
        summary = {
            "endpoints_planned": len(endpoints),
            "endpoints_succeeded": counts["inserted"] + counts["updated"],
            "endpoints_skipped": counts["skipped"],
            "contract_bug_failures": sum(
                1 for e in endpoints if e.get("status", "").startswith("contract_bug_")
            ),
            "externally_blocked": sum(
                1
                for e in endpoints
                if e.get("status") in ("transport_error_retryable", "transport_error_non_retryable")
            ),
            "by_status": _status_histogram(endpoints),
        }
        return {
            "status": stage_status,
            "auth_status": auth_status,
            "ready_for_live_calls": ready,
            "mode": "apply",
            "live_read_performed": True,
            "live_env_active": live_env,
            "persistence_path": "procore_live",
            "canonical_tables": list(PROCORE_CANONICAL_TABLES),
            "tables_written": list(PROCORE_CANONICAL_TABLES),
            "project_scope_policy": scope,
            "endpoint_summary": summary,
            "endpoints": endpoints,
            "projects": projects,
            "counts": counts,
            "next_operator_action": self._procore_next_action(summary),
            "inspect_hint": (
                "Inspect canonical Procore data with `hb-assistant procore live records "
                "--project <key> --endpoint <id>`; run history in procore_live_sync_runs."
            ),
        }

    @staticmethod
    def _procore_next_action(summary: dict[str, Any]) -> str:
        """Operator guidance derived from the endpoint taxonomy histogram."""
        if summary.get("contract_bug_failures"):
            return (
                "Procore endpoint contract regression — inspect procore_live_sync_runs "
                "for transport_error rows and re-validate the canonical adapter."
            )
        if summary.get("externally_blocked"):
            return "External Procore service/transport errors — retry after the rate window."
        by_status = summary.get("by_status", {})
        if any(k.startswith("blocked_") for k in by_status):
            return "Run `hb-assistant procore auth login` and confirm pilot mapping, then re-run."
        return "none"

    def _run_live_endpoint(
        self, pe: Any, project_key: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Invoke run_live_sync for one canonical endpoint; never raises."""
        kwargs: dict[str, Any] = {
            "project_key": project_key,
            "endpoint": pe.canonical_id,
            "apply": True,
            "sqlite_only": True,
            "confirm_live_get": True,
            "mode_hint": "live_apply",
            "db_path": self.db_path,
        }
        if pe.date_windowed:
            kwargs["start_date"] = start_date
            kwargs["end_date"] = end_date
        try:
            return run_live_sync(**kwargs)
        except Exception as exc:  # noqa: BLE001 — isolate one endpoint, keep going
            return {
                "endpoint_id": pe.canonical_id,
                "state": "transport_error",
                "status": "error",
                "reason_codes": [f"orchestrator_exception:{type(exc).__name__}"],
                "redacted_errors": [{"orchestrator_error": type(exc).__name__}],
                "sqlite_upserted_count": 0,
                "retrieved_count": 0,
            }

    @staticmethod
    def _endpoint_row(
        pe: Any, project_key: str, receipt: dict[str, Any], code: str
    ) -> dict[str, Any]:
        return {
            "endpoint": pe.canonical_id,
            "legacy_alias": pe.legacy_alias,
            "scope": "company" if pe.company_level else project_key,
            "project_key": project_key,
            "company_level": bool(pe.company_level),
            "status": code,
            "retrieved": int(receipt.get("retrieved_count", 0) or 0),
            "upserted": int(receipt.get("sqlite_upserted_count", 0) or 0),
            "sync_run_id": receipt.get("sync_run_id"),
            "raw_payload_rows_written": int(receipt.get("raw_payload_rows_written", 0) or 0),
        }

    def _tally_endpoint(
        self,
        pe: Any,
        project_key: str,
        code: str,
        receipt: dict[str, Any],
        counts: dict[str, int],
        per_project: dict[str, dict[str, int]],
    ) -> None:
        upserted = int(receipt.get("sqlite_upserted_count", 0) or 0)
        if code == "success":
            counts["inserted"] += upserted
            per_project[project_key]["ok"] += 1
        elif is_skipped_status(code):
            counts["skipped"] += 1
            per_project[project_key]["skipped"] += 1
        elif is_degraded_status(code):
            counts["failed"] += 1
            per_project[project_key]["failed"] += 1
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": f"procore.{project_key}",
                    "status": "degraded",
                    "reason": f"{pe.canonical_id} ({pe.legacy_alias}): {code}",
                }
            )
        else:  # defensive: unknown -> treat as degradation
            counts["failed"] += 1
            per_project[project_key]["failed"] += 1
            self._acc.degraded = True

    @staticmethod
    def _resolve_brief_date(options: RefreshOptions) -> date:
        if options.brief_date:
            try:
                return date.fromisoformat(options.brief_date)
            except ValueError:
                pass
        return date.today()

    # -- stage 2b: procore projection ---------------------------------------------

    def _procore_projection_stage(
        self, options: RefreshOptions, procore_summary: dict[str, Any]
    ) -> dict[str, Any]:
        scope = procore_summary.get("project_scope_policy") or {
            "selected_projects": [],
            "skipped_projects": [],
            "selected_project_count": 0,
            "skipped_project_count": 0,
            "blocking_rejections": [],
        }
        # Unsafe-mapping / unknown-allowlist rejections block the run before any live read;
        # surface them as explicit blocked_* freshness counts (a typo in the allowlist must
        # never silently narrow scope).
        blocking_rejections = scope.get("blocking_rejections", []) or []
        blocked_unknown = sum(
            1 for b in blocking_rejections if str(b.get("reason", "")) == "unknown_key"
        )
        blocked_unsafe = len(blocking_rejections) - blocked_unknown
        default_freshness: dict[str, Any] = {
            "ok": not blocking_rejections,
            "status": "blocked" if blocking_rejections else "skipped",
            "source_quality": SOURCE_QUALITY_LIVE_FULL,
            "raw_landing_table": RAW_LANDING_TABLE,
            "counts_by_status": {
                "ok_payload_landed": 0,
                "ok_empty_result": 0,
                "ok_skipped_with_reason": 0,
                "degraded_raw_payload_landing_missing": 0,
                "degraded_detail_payload_unavailable": 0,
                "degraded_external_blocked": 0,
                "blocked_unsafe_mapping": blocked_unsafe,
                "blocked_unknown_allowlist_key": blocked_unknown,
            },
            "missing_fresh_raw_payloads": [],
            "missing_fresh_raw_payload_count": 0,
            "raw_rows_by_project": {},
            "raw_rows_by_project_endpoint": {},
            "guardrails": {"emits_values": False, "counts_only": True},
        }
        base: dict[str, Any] = {
            "status": "skipped",
            "reason": "not_run",
            "selected_project_count": int(scope.get("selected_project_count", 0) or 0),
            "skipped_project_count": int(scope.get("skipped_project_count", 0) or 0),
            "selected_projects": scope.get("selected_projects", []),
            "skipped_projects": scope.get("skipped_projects", []),
            "blocking_rejections": blocking_rejections,
            "raw_full_payload_freshness": default_freshness,
            "raw_full_rows_by_project": {},
            "raw_full_rows_by_project_endpoint": {},
            "projection_schema_audit": {"ok": False, "runtime_plan_schema_mismatches": 0},
            "projection_reprocess": {
                "ok": False,
                "primary_rows_written": 0,
                "child_rows_written": 0,
            },
            "budget_detail_read_model": self._empty_budget_detail_read_model_summary(),
            "projection_audit": {
                "ok": False,
                "unknown_business_field_paths": 0,
                "runtime_plan_schema_mismatches": 0,
            },
            "guardrails": {"live_calls_disabled": True, "writeback": "none", "emits_values": False},
        }

        if procore_summary.get("status") == "blocked_project_scope":
            self._acc.degraded = True
            return {**base, "status": "blocked_project_scope", "reason": "project_scope_blocked"}
        if not options.apply:
            return {**base, "status": "skipped", "reason": "dry_run"}
        if not procore_summary.get("live_read_performed"):
            return {**base, "status": "skipped", "reason": "procore_live_read_not_performed"}

        freshness = self._verify_procore_raw_payload_freshness(procore_summary)
        base["raw_full_rows_by_project"] = freshness["raw_full_rows_by_project"]
        base["raw_full_rows_by_project_endpoint"] = freshness[
            "raw_full_rows_by_project_endpoint"
        ]
        base["raw_full_payload_freshness"] = freshness
        if not freshness["ok"]:
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "procore_projection.raw_payload_freshness",
                    "status": "degraded",
                    "reason": "raw_full_payload_freshness_missing",
                }
            )
            return {
                **base,
                "status": "degraded",
                "reason": "raw_full_payload_freshness_missing",
            }

        # NF-F-001 (N-A5b): ordinary projection path — never ambiently migrate a managed DB. Self-heal
        # only a non-managed target; a behind managed DB is surfaced by the schema audit below (which
        # degrades the run) rather than silently migrated on the projection path.
        from hb_assistant.store.schema_readiness import self_heal_if_non_managed

        self_heal_if_non_managed(self.db_path)
        schema = projection_schema_audit(db_path=self.db_path)
        base["projection_schema_audit"] = self._summarize_projection_schema_audit(schema)
        if not schema.get("ok"):
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "procore_projection.schema_audit",
                    "status": "degraded",
                    "reason": "schema_parity_broken",
                }
            )
            return {**base, "status": "degraded", "reason": "schema_parity_broken"}

        try:
            reprocess = backfill_endpoint_specific_from_raw_payloads(
                db_path=self.db_path,
                apply=True,
                limit=200000,
                mode=MODE_ENFORCE,
            )
        except UnknownProjectionPath as exc:
            reprocess = {
                "ok": False,
                "status": "fail_closed_unknown_path",
                "endpoint": exc.endpoint_id,
                "degraded_unknown_projection_fields": len(exc.unknown),
                "unknown_business_field_sample": sorted(exc.unknown)[:20],
                "primary_rows_written": 0,
                "child_rows_written": 0,
                "guardrails": {"live_calls_disabled": True, "writeback": "none"},
            }
        base["projection_reprocess"] = self._summarize_projection_reprocess(reprocess)

        budget_detail = self._reconcile_budget_detail_read_model(scope, freshness)
        base["budget_detail_read_model"] = budget_detail

        if not reprocess.get("ok"):
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "procore_projection.reprocess",
                    "status": "degraded",
                    "reason": str(reprocess.get("status", "projection_reprocess_failed")),
                }
            )
            if not budget_detail.get("ok"):
                self._acc.failures.append(
                    {
                        "stage": "procore_projection.budget_detail_read_model",
                        "status": "degraded",
                        "reason": str(
                            budget_detail.get("status", "budget_detail_reconcile_failed")
                        ),
                    }
                )
            return {
                **base,
                "status": "degraded",
                "reason": "projection_reprocess_failed",
            }

        if not budget_detail.get("ok"):
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "procore_projection.budget_detail_read_model",
                    "status": "degraded",
                    "reason": str(budget_detail.get("status", "budget_detail_reconcile_failed")),
                }
            )
            return {
                **base,
                "status": "degraded",
                "reason": str(budget_detail.get("status", "budget_detail_reconcile_failed")),
            }

        audit = projection_audit(db_path=self.db_path)
        base["projection_audit"] = self._summarize_projection_audit(audit)
        if not audit.get("ok"):
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "procore_projection.audit",
                    "status": "degraded",
                    "reason": "projection_audit_not_ok",
                }
            )
            return {**base, "status": "degraded", "reason": "projection_audit_not_ok"}

        return {**base, "status": "ok", "reason": "projection_pipeline_ok"}

    @staticmethod
    def _empty_budget_detail_read_model_summary() -> dict[str, Any]:
        return {
            "ok": False,
            "status": "not_run",
            "mode": "scheduled_reconciliation",
            "raw_landing_rows_by_endpoint": dict.fromkeys(BUDGET_DETAIL_ENDPOINT_IDS, 0),
            "raw_landing_rows_by_project_endpoint": {},
            "structured_table_counts": dict.fromkeys(BUDGET_DETAIL_STRUCTURED_TABLES, 0),
            "configured_budget_view_ids_by_project": {},
            "selected_budget_view_ids_by_project": {},
            "projects": [],
            "totals": {
                "inspected_raw_rows": 0,
                "structured_budget_detail_column_rows_inserted_or_updated": 0,
                "structured_budget_detail_row_rows_inserted_or_updated": 0,
                "budget_detail_cell_rows_inserted_or_updated": 0,
                "skipped_missing_record_id": 0,
                "skipped_lower_quality": 0,
                "degraded_parse_errors": 0,
            },
            "guardrails": {
                "idempotent_reconciliation": True,
                "separate_from_projection_reprocess": True,
                "live_calls_disabled": True,
                "writeback": "none",
                "external_writeback_performed": 0,
                "raw_payload_body_emitted": False,
                "emits_values": False,
                "counts_only": True,
            },
        }

    def _reconcile_budget_detail_read_model(
        self, scope: dict[str, Any], freshness: dict[str, Any]
    ) -> dict[str, Any]:
        """Replay Budget Detail read-model projections once per selected project.

        The generic endpoint-specific projection replay may already refresh some
        Budget Detail tables. This step is reported separately and uses the
        dedicated projector's upsert path as an idempotent reconciliation pass,
        not as a second raw-ingestion path.
        """
        selected_project_keys = [
            str(row.get("project_key"))
            for row in scope.get("selected_projects", []) or []
            if row.get("project_key")
        ]
        raw_by_project_endpoint = freshness.get("raw_rows_by_project_endpoint") or {}
        filtered_raw_by_project_endpoint: dict[str, dict[str, int]] = {}
        raw_by_endpoint = dict.fromkeys(BUDGET_DETAIL_ENDPOINT_IDS, 0)
        for project_key in selected_project_keys:
            endpoint_counts = raw_by_project_endpoint.get(project_key, {}) or {}
            filtered = {
                eid: int(endpoint_counts.get(eid, 0) or 0) for eid in BUDGET_DETAIL_ENDPOINT_IDS
            }
            filtered_raw_by_project_endpoint[project_key] = filtered
            for eid, count in filtered.items():
                raw_by_endpoint[eid] += count

        totals = self._empty_budget_detail_read_model_summary()["totals"].copy()
        projects: list[dict[str, Any]] = []
        configured_by_project: dict[str, list[str]] = {}
        selected_by_project: dict[str, list[str]] = {}
        ok = True

        for project_key in selected_project_keys:
            configured_view_ids = self._configured_budget_detail_view_ids(project_key)
            configured_by_project[project_key] = configured_view_ids
            selected_by_project[project_key] = configured_view_ids
            try:
                receipt = project_budget_detail_read_model(
                    db_path=self.db_path,
                    project_key=project_key,
                    require_live_full=True,
                    apply=True,
                )
            except Exception as exc:  # noqa: BLE001 - isolate one project, keep receipt body-free
                receipt = {
                    "ok": False,
                    "status": "exception",
                    "error_kind": type(exc).__name__,
                    "local_db_write_performed": False,
                    "external_writeback_performed": 0,
                    "raw_payload_body_emitted": False,
                }

            project_ok = bool(receipt.get("ok", False))
            ok = ok and project_ok
            for key in totals:
                totals[key] += int(receipt.get(key, 0) or 0)
            projects.append(
                {
                    "project_key": project_key,
                    "ok": project_ok,
                    "status": str(receipt.get("status", "failed")),
                    "configured_budget_view_ids": configured_view_ids,
                    "selected_budget_view_ids": configured_view_ids,
                    "inspected_raw_rows": int(receipt.get("inspected_raw_rows", 0) or 0),
                    "structured_budget_detail_column_rows_inserted_or_updated": int(
                        receipt.get(
                            "structured_budget_detail_column_rows_inserted_or_updated", 0
                        )
                        or 0
                    ),
                    "structured_budget_detail_row_rows_inserted_or_updated": int(
                        receipt.get("structured_budget_detail_row_rows_inserted_or_updated", 0)
                        or 0
                    ),
                    "budget_detail_cell_rows_inserted_or_updated": int(
                        receipt.get("budget_detail_cell_rows_inserted_or_updated", 0) or 0
                    ),
                    "skipped_missing_record_id": int(
                        receipt.get("skipped_missing_record_id", 0) or 0
                    ),
                    "skipped_lower_quality": int(receipt.get("skipped_lower_quality", 0) or 0),
                    "degraded_parse_errors": int(receipt.get("degraded_parse_errors", 0) or 0),
                    "local_db_write_performed": bool(
                        receipt.get("local_db_write_performed", False)
                    ),
                    "external_writeback_performed": int(
                        receipt.get("external_writeback_performed", 0) or 0
                    ),
                    "raw_payload_body_emitted": bool(
                        receipt.get("raw_payload_body_emitted", False)
                    ),
                }
            )

        return {
            "ok": ok,
            "status": "success" if ok else "degraded",
            "mode": "scheduled_reconciliation",
            "raw_landing_rows_by_endpoint": raw_by_endpoint,
            "raw_landing_rows_by_project_endpoint": filtered_raw_by_project_endpoint,
            "structured_table_counts": self._budget_detail_structured_table_counts(
                selected_project_keys
            ),
            "configured_budget_view_ids_by_project": configured_by_project,
            "selected_budget_view_ids_by_project": selected_by_project,
            "projects": projects,
            "totals": totals,
            "guardrails": {
                "idempotent_reconciliation": True,
                "separate_from_projection_reprocess": True,
                "live_calls_disabled": True,
                "writeback": "none",
                "external_writeback_performed": 0,
                "raw_payload_body_emitted": False,
                "emits_values": False,
                "counts_only": True,
            },
        }

    @staticmethod
    def _configured_budget_detail_view_ids(project_key: str) -> list[str]:
        repo_root = Path(__file__).resolve().parents[3]
        cfg_path = (
            repo_root
            / "subrepos"
            / "construction-financial-review"
            / "config"
            / "projects"
            / f"{project_key}.json"
        )
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        candidates: list[Any] = []
        for container_key in ("budget_details", "procore", "forecast_intelligence"):
            container = cfg.get(container_key)
            if isinstance(container, dict):
                candidates.extend(
                    (
                        container.get("budget_view_id"),
                        container.get("budget_detail_budget_view_id"),
                        container.get("budget_view_ids"),
                        container.get("budget_detail_budget_view_ids"),
                    )
                )
        candidates.extend(
            (
                cfg.get("budget_view_id"),
                cfg.get("budget_detail_budget_view_id"),
                cfg.get("budget_view_ids"),
                cfg.get("budget_detail_budget_view_ids"),
            )
        )
        out: list[str] = []
        for value in candidates:
            if isinstance(value, list):
                out.extend(str(item) for item in value if item not in (None, ""))
            elif value not in (None, ""):
                out.append(str(value))
        return sorted(set(out))

    def _budget_detail_structured_table_counts(self, project_keys: list[str]) -> dict[str, int]:
        counts = dict.fromkeys(BUDGET_DETAIL_STRUCTURED_TABLES, 0)
        conn = sqlite3.connect(str(self.db_path))
        try:
            for table in BUDGET_DETAIL_STRUCTURED_TABLES:
                try:
                    if project_keys:
                        placeholders = ", ".join("?" for _ in project_keys)
                        sql = f"SELECT COUNT(*) FROM {table} WHERE project_key IN ({placeholders})"
                        count = conn.execute(sql, tuple(project_keys)).fetchone()[0]
                    else:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    count = 0
                counts[table] = int(count or 0)
        finally:
            conn.close()
        return counts

    def _verify_procore_raw_payload_freshness(self, procore_summary: dict[str, Any]) -> dict[str, Any]:
        """Classify each selected project/endpoint's raw-payload landing into one status.

        Passing statuses (``ok_*``) never degrade the run; ``degraded_*`` keep the gate
        fail-closed. Landing is proven by the presence of CURRENT live full-payload rows for
        the ``(project_key, endpoint_key)`` — the exact rows projection replay consumes — and
        NOT by ``capture_run_id`` (which ``_insert_full_raw_payload`` does not refresh on
        idempotent re-run upserts, so filtering by it under-counts re-confirmed records).

        Taxonomy:
          - ``ok_payload_landed``   live success, retrieved > 0, current live rows present.
          - ``ok_empty_result``     live success, retrieved == 0 (valid no-data / no-tool stage).
          - ``ok_skipped_with_reason`` endpoint skipped (ineligible / unsupported / 403 / 404 /
                                       company-level already handled) — reason always recorded.
          - ``degraded_raw_payload_landing_missing`` retrieved > 0 but no current live rows.
          - ``degraded_detail_payload_unavailable``  detail/full endpoint retrieved a list but
                                                     the richer payload did not land.
          - ``degraded_external_blocked`` transport / contract / normalizer failure (never green;
                                          the run is already degraded by the procore stage).
        """
        counts = self._current_live_full_payload_counts()
        by_project = counts["by_project"]
        by_project_endpoint = counts["by_project_endpoint"]

        status_counts: dict[str, int] = {
            "ok_payload_landed": 0,
            "ok_empty_result": 0,
            "ok_skipped_with_reason": 0,
            "degraded_raw_payload_landing_missing": 0,
            "degraded_detail_payload_unavailable": 0,
            "degraded_external_blocked": 0,
            "blocked_unsafe_mapping": 0,
            "blocked_unknown_allowlist_key": 0,
        }
        classified: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []

        for endpoint in procore_summary.get("endpoints", []):
            code = str(endpoint.get("status") or "")
            endpoint_id = str(endpoint.get("endpoint") or "")
            # Landing rows are keyed by the real project_key the endpoint ran under (company
            # endpoints carry scope="company" but a concrete project_key); fall back to scope.
            landing_key = str(endpoint.get("project_key") or endpoint.get("scope") or "")
            retrieved = int(endpoint.get("retrieved", 0) or 0)
            landed = int(by_project_endpoint.get(landing_key, {}).get(endpoint_id, 0) or 0)

            if is_skipped_status(code):
                status = "ok_skipped_with_reason"
            elif code == "success":
                if retrieved <= 0:
                    status = "ok_empty_result"
                elif landed > 0:
                    status = "ok_payload_landed"
                elif self._endpoint_requires_detail_payload(endpoint_id):
                    status = "degraded_detail_payload_unavailable"
                else:
                    status = "degraded_raw_payload_landing_missing"
            else:
                # transport_error*, contract_bug, normalizer_missing, unknown_degraded, ...
                status = "degraded_external_blocked"

            status_counts[status] += 1
            row = {
                "project_key": landing_key,
                "scope": str(endpoint.get("scope") or landing_key),
                "endpoint": endpoint_id,
                "freshness_status": status,
                "reason": code,
                "retrieved": retrieved,
                "raw_full_rows": landed,
            }
            classified.append(row)
            if status in (
                "degraded_raw_payload_landing_missing",
                "degraded_detail_payload_unavailable",
            ):
                missing.append(row)

        # The gate (which authorizes projection replay) fails closed only on raw-landing
        # gaps: a retrieved endpoint whose rows did not land would feed replay incomplete
        # data. External transport failures keep the run degraded via the procore stage but
        # do not block replay over the payloads that DID land (pre-existing posture).
        landing_failures = (
            status_counts["degraded_raw_payload_landing_missing"]
            + status_counts["degraded_detail_payload_unavailable"]
        )
        blocking = (
            status_counts["blocked_unsafe_mapping"]
            + status_counts["blocked_unknown_allowlist_key"]
        )
        ok = landing_failures == 0 and blocking == 0
        sync_run_ids_checked = sorted(
            {
                str(e.get("sync_run_id"))
                for e in procore_summary.get("endpoints", [])
                if e.get("sync_run_id")
            }
        )
        return {
            "ok": ok,
            "status": "ok" if ok else "degraded",
            "source_quality": SOURCE_QUALITY_LIVE_FULL,
            "raw_landing_table": RAW_LANDING_TABLE,
            "attribution": "current_live_full_payload_rows_by_project_endpoint",
            "counts_by_status": status_counts,
            "external_blocked_count": status_counts["degraded_external_blocked"],
            "classified_endpoints": classified[:200],
            "sync_run_ids_checked": sync_run_ids_checked,
            "raw_rows_by_project": by_project,
            "raw_rows_by_project_endpoint": by_project_endpoint,
            # Back-compat aliases for existing receipt consumers/evidence.
            "raw_full_rows_by_project": by_project,
            "raw_full_rows_by_project_endpoint": by_project_endpoint,
            "missing_fresh_raw_payloads": missing[:50],
            "missing_fresh_raw_payload_count": landing_failures,
            "guardrails": {"emits_values": False, "counts_only": True},
        }

    def _current_live_full_payload_counts(self) -> dict[str, Any]:
        """Current live full-payload row counts per ``(project_key, endpoint_key)``.

        Mirrors projection replay's own selection (``raw_procore_payload_persisted=1 AND
        is_current=1`` at ``source_quality='live_full_payload'``) with NO ``capture_run_id``
        filter. ``fixture_full_payload`` is intentionally excluded so a production live run is
        satisfied by live source-quality rows only (fixtures count only in tests/mock mode).
        """
        by_project: dict[str, int] = {}
        by_project_endpoint: dict[str, dict[str, int]] = {}
        sql = (
            f"SELECT project_key, endpoint_key, COUNT(*) FROM {RAW_LANDING_TABLE} "
            "WHERE raw_procore_payload_persisted = 1 AND is_current = 1 "
            "AND source_quality = ? GROUP BY project_key, endpoint_key"
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            for project_key, endpoint_key, count in conn.execute(sql, (SOURCE_QUALITY_LIVE_FULL,)):
                pkey = str(project_key)
                ekey = str(endpoint_key)
                cnt = int(count)
                by_project[pkey] = by_project.get(pkey, 0) + cnt
                by_project_endpoint.setdefault(pkey, {})[ekey] = cnt
        except sqlite3.Error:
            pass
        finally:
            conn.close()
        return {"by_project": by_project, "by_project_endpoint": by_project_endpoint}

    @staticmethod
    def _endpoint_requires_detail_payload(canonical_id: str) -> bool:
        """True if the endpoint's richest payload needs a detail/full (N+1) expansion.

        A detail endpoint pairs a parent list path with a non-paginated per-record detail GET
        (e.g. ``meeting-detail``). The entire daily-refresh plan is list-only (returns False);
        the check is kept for forward coverage of detail endpoints.
        """
        from hb_assistant.procore import endpoints as _endpoints

        adapter = _endpoints.get(canonical_id)
        if adapter is None:
            return False
        return getattr(adapter, "parent_path_template", None) is not None and (
            getattr(adapter, "pagination", None) == "none"
        )

    @staticmethod
    def _summarize_projection_schema_audit(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(payload.get("ok", False)),
            "runtime_plan_schema_mismatches": int(
                payload.get("runtime_plan_schema_mismatches", 0) or 0
            ),
            "missing_table_count": int(payload.get("missing_table_count", 0) or 0),
            "missing_column_count": int(payload.get("missing_column_count", 0) or 0),
            "mismatches_sample": payload.get("mismatches", [])[:20],
            "guardrails": payload.get("guardrails", {}),
        }

    @staticmethod
    def _summarize_projection_reprocess(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(payload.get("ok", False)),
            "status": payload.get("status", "ok" if payload.get("ok") else "failed"),
            "primary_rows_written": int(payload.get("primary_rows_written", 0) or 0),
            "child_rows_written": int(payload.get("child_rows_written", 0) or 0),
            "raw_full_rows_inspected": int(payload.get("raw_full_rows_inspected", 0) or 0),
            "degraded_unknown_projection_fields": int(
                payload.get("degraded_unknown_projection_fields", 0) or 0
            ),
            "runtime_plan_schema_mismatches": int(
                payload.get("runtime_plan_schema_mismatches", 0) or 0
            ),
            "guardrails": payload.get("guardrails", {}),
        }

    @staticmethod
    def _summarize_projection_audit(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": bool(payload.get("ok", False)),
            "endpoint_count": int(payload.get("endpoint_count", 0) or 0),
            "unknown_business_field_paths": int(
                payload.get("unknown_business_field_paths", 0) or 0
            ),
            "unmapped_primary_business_fields": int(
                payload.get("unmapped_primary_business_fields", 0) or 0
            ),
            "unmapped_nested_business_fields": int(
                payload.get("unmapped_nested_business_fields", 0) or 0
            ),
            "runtime_plan_schema_mismatches": int(
                payload.get("runtime_plan_schema_mismatches", 0) or 0
            ),
            "guardrails": payload.get("guardrails", {}),
        }

    # -- stage 3: graph ------------------------------------------------------------

    def _graph_stage(self, options: RefreshOptions) -> dict[str, Any]:
        dry_run = options.dry_run

        families: dict[str, dict[str, Any]] = {}

        # Mail thread summary is local-only (reads SQLite, no Graph call) — always runnable.
        families["mail_thread_summary"] = self._stage(
            "graph.mail_thread_summary",
            lambda: self._graph_mail_thread_summary(dry_run),
        )

        # Live families (calendar, files) read from Graph even to plan. They require
        # --confirm AND allow_graph_live AND not mock_data. The Graph auth/status probe
        # is performed ONLY when a live read is actually intended — mock/local-only runs
        # never touch Graph auth/status/probe/read.
        live_intended = options.confirm and options.allow_graph_live and not options.mock_data
        token_type = "skipped"
        token_ready = False
        if not live_intended:
            if options.mock_data:
                reason, overall = "mock_data_local_only", "mock_data_local_only"
            elif not options.allow_graph_live:
                reason, overall = "live_disabled", "partial_local_only"
            else:
                reason, overall = "confirm_required_for_live_read", "partial_local_only"
            gated = {"status": "skipped", "reason": reason}
            families["email_raw_content"] = dict(gated)
            families["calendar_event_index"] = dict(gated)
            families["calendar_raw_content"] = dict(gated)
            families["files"] = dict(gated)
        else:
            info = self._graph_status()
            token_type = info.get("token_type", "none")
            token_ready = token_type != "none"
            if not token_ready:
                blocked = {"status": "blocked_auth_not_ready", "reason": "no_delegated_token"}
                families["email_raw_content"] = dict(blocked)
                families["calendar_event_index"] = dict(blocked)
                families["calendar_raw_content"] = dict(blocked)
                families["files"] = dict(blocked)
                self._acc.degraded = True
                overall = "blocked_auth_not_ready"
            else:
                families["email_raw_content"] = self._stage(
                    "graph.email_raw_content",
                    lambda: self._graph_email_raw(dry_run),
                )
                families["calendar_event_index"] = self._stage(
                    "graph.calendar_event_index",
                    lambda: self._graph_calendar(dry_run),
                )
                families["calendar_raw_content"] = self._calendar_raw_family(
                    families["calendar_event_index"]
                )
                families["files"] = self._stage(
                    "graph.files",
                    lambda: self._graph_files(dry_run),
                )
                bad = [
                    name
                    for name, fam in families.items()
                    if fam.get("status") not in ("ok", "skipped")
                ]
                if bad:
                    self._acc.degraded = True
                    overall = "degraded"
                else:
                    overall = "ok"

        return {
            "status": overall,
            "auth_status": token_type,
            "token_ready": token_ready,
            "families": families,
            "counts": self._graph_counts(families),
            "tables": self._email_calendar_raw_table_counts(),
            "freshness": self._email_calendar_raw_freshness(),
            "guardrails": {
                "read_only_graph_clients": True,
                "no_graph_send": True,
                "no_graph_draft": True,
                "no_graph_update": True,
                "no_graph_delete": True,
                "no_calendar_mutation": True,
                "external_writeback_performed": 0,
                "emits_values": False,
            },
        }

    def _graph_status(self) -> dict[str, Any]:
        from hb_assistant.auth.providers import DelegatedAuthProvider
        from hb_assistant.config.loader import load_config

        try:
            cfg = load_config()
            provider = DelegatedAuthProvider(
                cfg.identity.tenant_id,
                cfg.identity.client_id,
                list(cfg.identity.delegated_scopes),
                path_policy=PathPolicy(cfg),
            )
            return provider.status_info()
        except Exception as exc:  # noqa: BLE001 — treat any failure as no-token, fail closed
            return {"token_type": "none", "detail": f"{type(exc).__name__}: {str(exc)[:120]}"}

    def _graph_mail_thread_summary(self, dry_run: bool) -> dict[str, Any]:
        from hb_assistant.construction.calendar import load_email_thread_summary_policy
        from hb_assistant.construction.email import EmailThreadSummaryMaterializer
        from hb_assistant.construction.store.repositories import ConstructionStore

        materializer = EmailThreadSummaryMaterializer(
            ConstructionStore(db_path=self._db_path_str()),
            policy=load_email_thread_summary_policy(),
        )
        report = materializer.materialize(dry_run=dry_run)
        data = report.model_dump() if hasattr(report, "model_dump") else dict(report)
        return {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "local_only": True,
            "summarized": int(data.get("summarized", 0) or 0),
            "considered": int(data.get("considered", 0) or 0),
            "persisted": bool(data.get("persisted", False)),
        }

    def _graph_email_raw(self, dry_run: bool) -> dict[str, Any]:
        from hb_assistant.construction.email import EmailMessageIndexer
        from hb_assistant.construction.store.repositories import ConstructionStore
        from hb_assistant.graph.mail_endpoint_guard import load_mail_endpoint_contract
        from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient

        client = self._graph_client_scoped(["Mail.Read"])
        try:
            reader = ReadOnlyMailClient(client, contract=load_mail_endpoint_contract())
            indexer = EmailMessageIndexer(reader, ConstructionStore(db_path=self._db_path_str()))
            result = indexer.index(dry_run=dry_run, include_raw_content=True)
            data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        finally:
            client.close()

        return {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "live_read_performed": True,
            "raw_body_fetch_performed": bool(
                (not dry_run) and int(data.get("raw_emails_persisted", 0) or 0) > 0
            ),
            "folders_crawled": int(data.get("folders_crawled", 0) or 0),
            "messages_seen": int(data.get("messages_seen", 0) or 0),
            "messages_indexed": int(data.get("messages_indexed", 0) or 0),
            "raw_emails_persisted": int(data.get("raw_emails_persisted", 0) or 0),
            "raw_threads_built": int(data.get("raw_threads_built", 0) or 0),
            "persisted": bool(data.get("persisted", False)),
            "tables_written": (
                ["email_message_raw_content", "email_thread_raw_context"] if not dry_run else []
            ),
            "guardrails": {
                "read_only_graph_client": True,
                "external_writeback_performed": 0,
                "emits_values": False,
            },
        }

    def _graph_client(self) -> Any:
        from hb_assistant.auth.providers import DelegatedAuthProvider
        from hb_assistant.config.loader import load_config
        from hb_assistant.graph.http_client import GraphHttpClient

        cfg = load_config()
        scopes = list(cfg.identity.delegated_scopes)
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            scopes,
            path_policy=PathPolicy(cfg),
        )

        def token_getter(s: Optional[list[str]] = None) -> dict[str, Any]:
            return provider.get_token(s or scopes)

        return GraphHttpClient(token_getter)

    def _graph_calendar(self, dry_run: bool) -> dict[str, Any]:
        from hb_assistant.construction.calendar.event_indexer import CalendarEventIndexer
        from hb_assistant.construction.calendar.policy import load_calendar_source_policy
        from hb_assistant.construction.store.repositories import ConstructionStore
        from hb_assistant.graph.calendar_endpoint_guard import load_calendar_endpoint_contract
        from hb_assistant.graph.calendar_readonly_client import ReadOnlyCalendarClient

        client = self._graph_client()
        results: list[dict[str, Any]] = []
        try:
            reader = ReadOnlyCalendarClient(client, contract=load_calendar_endpoint_contract())
            indexer = CalendarEventIndexer(reader, ConstructionStore(db_path=self._db_path_str()))
            policy = load_calendar_source_policy()
            if policy.defaults.enabled:
                for src in policy.sources:
                    res = indexer.index(
                        source_id=src.source_id,
                        mailbox_owner=src.mailbox_owner,
                        calendar_role=src.calendar_role,
                        policy_id=src.policy_id,
                        lookback_days=policy.defaults.lookback_days,
                        lookahead_days=policy.defaults.lookahead_days,
                        max_items=policy.defaults.max_items_per_run,
                        dry_run=dry_run,
                        include_raw_content=True,
                    )
                    results.append(res.model_dump())
        finally:
            client.close()

        indexed = sum(int(r.get("events_indexed", 0) or 0) for r in results)
        raw_events = sum(int(r.get("raw_events_persisted", 0) or 0) for r in results)
        return {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "live_read_performed": True,
            "sources": len(results),
            "events_indexed": indexed,
            "raw_events_persisted": raw_events,
            "full_event_body_fetch_performed": bool((not dry_run) and raw_events > 0),
            "persisted": bool((not dry_run) and any(r.get("persisted") for r in results)),
            "tables_written": (
                ["calendar_event_index", "calendar_event_raw_content"] if not dry_run else []
            ),
        }

    @staticmethod
    def _calendar_raw_family(calendar_summary: dict[str, Any]) -> dict[str, Any]:
        if calendar_summary.get("status") != "ok":
            return {
                "status": calendar_summary.get("status", "skipped"),
                "reason": calendar_summary.get("reason", "calendar_index_not_ok"),
            }
        return {
            "status": "ok",
            "mode": calendar_summary.get("mode"),
            "live_read_performed": bool(calendar_summary.get("live_read_performed")),
            "raw_events_persisted": int(calendar_summary.get("raw_events_persisted", 0) or 0),
            "full_event_body_fetch_performed": bool(
                calendar_summary.get("full_event_body_fetch_performed", False)
            ),
            "persisted": bool(calendar_summary.get("persisted", False)),
            "tables_written": ["calendar_event_raw_content"]
            if calendar_summary.get("mode") == "apply"
            else [],
            "guardrails": {
                "read_only_graph_client": True,
                "external_writeback_performed": 0,
                "emits_values": False,
            },
        }

    def _graph_files(self, dry_run: bool) -> dict[str, Any]:
        from hb_assistant.construction.config import load_source_registry
        from hb_assistant.construction.graph import scopes_for_source_kind
        from hb_assistant.construction.graph.drive_item_indexer import DriveItemIndexer
        from hb_assistant.construction.store.repositories import ConstructionStore

        registry = load_source_registry()
        store = ConstructionStore(db_path=self._db_path_str()) if not dry_run else None
        results: list[dict[str, Any]] = []
        for src in registry.sources:
            client = self._graph_client_scoped(scopes_for_source_kind(src.kind))
            try:
                indexer = DriveItemIndexer(client, store=store)
                res = indexer.index(src, dry_run=dry_run)
                results.append(res.model_dump() if hasattr(res, "model_dump") else dict(res))
            finally:
                client.close()

        indexed = sum(int(r.get("items_indexed", r.get("items_seen", 0)) or 0) for r in results)
        return {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "live_read_performed": True,
            "sources": len(results),
            "items_indexed": indexed,
        }

    def _graph_client_scoped(self, scopes: list[str]) -> Any:
        from hb_assistant.auth.providers import DelegatedAuthProvider
        from hb_assistant.config.loader import load_config
        from hb_assistant.graph.http_client import GraphHttpClient

        cfg = load_config()
        provider = DelegatedAuthProvider(
            cfg.identity.tenant_id,
            cfg.identity.client_id,
            list(cfg.identity.delegated_scopes),
            path_policy=PathPolicy(cfg),
        )

        def token_getter(s: Optional[list[str]] = None) -> dict[str, Any]:
            return provider.get_token(s or scopes)

        return GraphHttpClient(token_getter)

    @staticmethod
    def _graph_counts(families: dict[str, dict[str, Any]]) -> dict[str, int]:
        counts = _zero_counts()
        for fam in families.values():
            if fam.get("status") != "ok":
                continue
            planned = int(
                fam.get("events_indexed", 0)
                or fam.get("items_indexed", 0)
                or fam.get("summarized", 0)
                or fam.get("messages_seen", 0)
                or fam.get("raw_events_persisted", 0)
                or 0
            )
            if fam.get("mode") == "apply" and fam.get("persisted"):
                counts["inserted"] += planned
            else:
                counts["planned"] += planned
        return counts

    def _email_calendar_raw_table_counts(self) -> dict[str, int]:
        tables = (
            "email_message_raw_content",
            "email_thread_raw_context",
            "calendar_event_raw_content",
        )
        return self._table_counts(tables)

    def _email_calendar_structured_table_counts(self) -> dict[str, int]:
        tables = (
            "email_raw_message_structured",
            "email_raw_thread_structured",
            "calendar_raw_event_structured",
        )
        return self._table_counts(tables)

    def _table_counts(self, tables: tuple[str, ...]) -> dict[str, int]:
        out: dict[str, int] = {}
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                for table in tables:
                    try:
                        out[table] = int(
                            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        )
                    except sqlite3.Error:
                        out[table] = 0
            finally:
                conn.close()
        except sqlite3.Error:
            return dict.fromkeys(tables, 0)
        return out

    def _email_calendar_raw_freshness(self) -> dict[str, Any]:
        specs = {
            "email_message": ("email_message_raw_content", "source_updated_at_utc"),
            "email_thread": ("email_thread_raw_context", "source_updated_at_utc"),
            "calendar_event": ("calendar_event_raw_content", "source_updated_at_utc"),
        }
        out: dict[str, Any] = {}
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                for family, (table, col) in specs.items():
                    try:
                        row = conn.execute(f"SELECT MAX({col}) FROM {table}").fetchone()
                        out[family] = row[0] if row else None
                    except sqlite3.Error:
                        out[family] = None
            finally:
                conn.close()
        except sqlite3.Error:
            return dict.fromkeys(specs, None)
        return out

    def _email_calendar_projection_stage(
        self, options: RefreshOptions, graph_summary: dict[str, Any]
    ) -> dict[str, Any]:
        if options.procore_only:
            return {"status": "skipped", "reason": "procore_only"}
        graph_status = str(graph_summary.get("status", "unknown"))
        if graph_status in ("blocked_auth_not_ready", "live_disabled", "mock_data_local_only"):
            return {
                "status": "skipped",
                "reason": f"graph_raw_ingestion_{graph_status}",
                "graph_status": graph_status,
                "raw_tables": self._email_calendar_raw_table_counts(),
                "structured_tables": self._email_calendar_structured_table_counts(),
                "guardrails": {"external_writeback_performed": 0, "emits_values": False},
            }

        before = self._email_calendar_structured_table_counts()
        receipt = run_email_calendar_projection_stage(db_path=self.db_path, apply=options.apply)
        after = self._email_calendar_structured_table_counts()
        status = str(receipt.get("status", "unknown"))
        if status in ("degraded", "failed"):
            self._acc.degraded = True
            self._acc.failures.append(
                {
                    "stage": "email_calendar_projection",
                    "status": status,
                    "reason": ",".join(receipt.get("degraded_reason") or [])[:200]
                    or "email_calendar_projection_not_ok",
                }
            )
        return {
            "status": status,
            "mode": receipt.get("mode"),
            "graph_status": graph_status,
            "run_id": receipt.get("run_id"),
            "raw_rows_by_family": receipt.get("raw_rows_by_family", {}),
            "structured_rows_by_family": receipt.get("structured_rows_by_family", {}),
            "structured_tables_before": before,
            "structured_tables_after": after,
            "families_with_raw_rows": receipt.get("families_with_raw_rows", 0),
            "projection_coverage_status": receipt.get("projection_coverage_status"),
            "total_unmapped_business_fields": receipt.get("total_unmapped_business_fields", 0),
            "degraded_reason": receipt.get("degraded_reason", []),
            "guardrails": receipt.get("guardrails", {}),
        }

    # -- count aggregation ---------------------------------------------------------

    def _aggregate_upserts(self, summary: dict[str, Any]) -> None:
        upserts = summary["sqlite_upsert_summary"]
        proc = summary["procore_sync_summary"].get("counts")
        graph = summary["graph_sync_summary"].get("counts")
        if isinstance(proc, dict):
            upserts["procore"] = proc
        if isinstance(graph, dict):
            upserts["graph"] = graph
        total = _zero_counts()
        for source in ("procore", "graph"):
            for key, value in upserts[source].items():
                total[key] = total.get(key, 0) + int(value or 0)
        upserts["total"] = total

    # -- stage 4: rebuild ----------------------------------------------------------

    def _rebuild_stage(self, options: RefreshOptions) -> dict[str, Any]:
        # Sub-proofs are consumed in-memory for the consolidated summary. They are
        # NEVER asked to write evidence: their default ``evidence_dir`` targets the
        # authoritative per-phase bundles, and the refresh command must not rewrite
        # another phase's evidence. The refresh command owns only its own bundle.
        db = self._db_path_str()
        guardrails: dict[str, bool] = {}

        retrieval: dict[str, Any] = {"status": "ok"}
        retrieval["approved_sources"] = self._stage(
            "rebuild.approved_sources",
            lambda: self._summarize_manifest(
                build_approved_source_manifest(db),
                build_approved_source_manifest_proof(write_evidence=False),
            ),
        )
        retrieval["coverage_parity"] = self._stage(
            "rebuild.coverage_parity",
            lambda: self._summarize_closeout(
                build_coverage_parity_closeout(db, write_evidence=False)
            ),
        )

        vector = self._rebuild_vector(options)
        daily_brief = self._rebuild_daily_brief(options)

        # Forensic + MCP attestations fold into guardrails.
        no_raw = self._stage(
            "rebuild.no_raw_vector_index",
            lambda: build_no_raw_vector_index_proof(db, write_evidence=False),
        )
        guardrails["no_raw_vector_index_proof_passed"] = bool(no_raw.get("proof_passed", False))
        mcp_access = self._stage(
            "rebuild.mcp_no_raw_access",
            lambda: build_no_raw_mcp_access_proof(db_path=db, write_evidence=False),
        )
        guardrails["mcp_no_raw_access_proof_passed"] = bool(mcp_access.get("proof_passed", False))
        mcp_writeback = self._stage(
            "rebuild.mcp_no_writeback",
            lambda: build_no_mcp_writeback_proof(db_path=db, write_evidence=False),
        )
        guardrails["mcp_no_writeback_proof_passed"] = bool(mcp_writeback.get("proof_passed", False))

        return {
            "retrieval": retrieval,
            "vector": vector,
            "daily_brief_v2": daily_brief,
            "guardrails": guardrails,
        }

    @staticmethod
    def _summarize_manifest(manifest: dict[str, Any], proof: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": manifest.get("status", "unknown"),
            "approved_ref_count": manifest.get("approved_ref_count", 0),
            "approved_family_count": manifest.get("approved_family_count", 0),
            "manifest_hash": manifest.get("manifest_hash"),
            "proof_passed": bool(proof.get("proof_passed", False)),
        }

    @staticmethod
    def _summarize_closeout(closeout: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ok" if closeout.get("closeout_ok") else "degraded",
            "closeout_ok": bool(closeout.get("closeout_ok", False)),
            "sub_proofs_passed": closeout.get("sub_proofs_passed"),
        }

    def _rebuild_vector(self, options: RefreshOptions) -> dict[str, Any]:
        if options.skip_vector:
            return {"status": "skipped", "reason": "skip_vector"}
        db = self._db_path_str()
        plan = self._stage("rebuild.vector_dry_run", lambda: build_vector_index_dry_run(db))
        result: dict[str, Any] = {
            "status": "planned",
            "dry_run": {
                "status": plan.get("status"),
                "planned_chunk_count": plan.get("planned_chunk_count"),
                "ready_to_apply": plan.get("ready_to_apply"),
                "vectors_persisted_to_sqlite": plan.get("vectors_persisted_to_sqlite", False),
            },
        }
        if options.apply:
            applied = self._stage("rebuild.vector_apply", lambda: build_vector_index_apply(db))
            apply_status = applied.get("status")
            result["apply"] = {
                "status": apply_status,
                "applied_item_count": applied.get("applied_item_count"),
                "vector_store_location": applied.get("vector_store_location"),
                "vectors_persisted_to_sqlite": applied.get("vectors_persisted_to_sqlite", False),
                "blocker_reason": applied.get("blocker_reason"),
            }
            if apply_status == "applied":
                result["status"] = "applied"
            else:
                result["status"] = "apply_blocked"
                self._warn(
                    f"vector apply blocked: {applied.get('blocker_reason', 'unknown')} "
                    "(install retrieval extras or use --skip-vector)"
                )
        return result

    def _rebuild_daily_brief(self, options: RefreshOptions) -> dict[str, Any]:
        if options.skip_daily_brief_proof:
            return {"status": "skipped", "reason": "skip_daily_brief_proof"}
        brief_date = options.brief_date or date.today().isoformat()
        db = self._db_path_str()
        mode = "apply" if options.apply else "dry_run"

        packet = self._stage(
            "rebuild.daily_brief_packet",
            lambda: build_daily_brief_packet_v2(brief_date=brief_date, mode=mode, db_path=db),
        )
        packet_proof = self._stage(
            "rebuild.daily_brief_packet_proof",
            lambda: build_daily_brief_packet_v2_proof(write_evidence=False),
        )
        quality_proof = self._stage(
            "rebuild.daily_brief_quality_proof",
            lambda: build_daily_brief_v2_quality_proof(write_evidence=False),
        )
        return {
            "status": "ok",
            "brief_date": brief_date,
            "mode": mode,
            "packet_version": packet.get("packet_version"),
            "packet_status": packet.get("status"),
            "packet_proof_passed": bool(packet_proof.get("proof_passed", False)),
            "quality_proof_passed": bool(quality_proof.get("proof_passed", False)),
        }

    # -- stage 5: finalize ---------------------------------------------------------

    def _finalize(self, summary: dict[str, Any], options: RefreshOptions) -> dict[str, Any]:
        summary["failures"] = self._acc.failures
        summary["warnings"] = self._acc.warnings

        if summary["status"] != "failed":
            summary["status"] = "degraded" if self._acc.degraded else "ok"

        summary["next_operator_action"] = self._next_action(summary, options)
        return summary

    @staticmethod
    def _next_action(summary: dict[str, Any], options: RefreshOptions) -> str:
        procore = summary["procore_sync_summary"]
        graph = summary["graph_sync_summary"]
        if procore.get("status") == "blocked_auth_not_ready":
            return "Run `hb-assistant procore auth login` to enable Procore live sync."
        if graph.get("status") == "blocked_auth_not_ready":
            return "Run `hb-assistant auth login` to obtain a delegated Graph token."
        procore_action = procore.get("next_operator_action")
        if procore_action and procore_action != "none":
            return procore_action
        if summary["status"] == "failed" or summary["failures"]:
            return "Review failures[] and warnings[], then re-run."
        if options.dry_run:
            return (
                "Re-run with `--apply --confirm` (and HB_PROCORE_LIVE=1 for live Procore "
                "reads) to persist the refresh."
            )
        return "none"

    # -- evidence ------------------------------------------------------------------

    def write_evidence(self, summary: dict[str, Any], *, suffix: str) -> Path:
        """Write a redacted JSON evidence file under the run evidence dir."""
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f"source-refresh-{suffix}.json"
        path.write_text(self.redact_json(summary))
        return path

    @staticmethod
    def redact_json(payload: dict[str, Any]) -> str:
        text = json.dumps(payload, indent=2, default=str, sort_keys=True)
        for bad in _REDACT_TOKENS:
            text = text.replace(bad, "[REDACTED]")
        return text


def _open_ro_count(db_path: Path, table: str) -> int:
    """Helper for tests/evidence: row count of a table (0 if absent)."""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 — fixed caller table
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0
