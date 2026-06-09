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
from typing import Any, Callable, Optional

from hb_assistant.config.path_policy import PathPolicy

# --- Second-brain (Phase-09) rebuild + proof surfaces -----------------------------
from hb_assistant.construction.second_brain.daily_brief.packet import (
    build_daily_brief_packet_v2,
    build_daily_brief_packet_v2_proof,
)
from hb_assistant.construction.second_brain.daily_brief.rendered_quality import (
    build_daily_brief_v2_quality_proof,
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
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

# Canonical Procore persistence path (the tables operational read-models consume).
PROCORE_CANONICAL_TABLES = (
    "procore_live_records",
    "procore_live_sync_runs",
    "procore_live_sync_watermarks",
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
            "graph_sync_summary": {"status": "skipped", "reason": "not_run"},
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
            else:
                summary["procore_sync_summary"] = {"status": "skipped", "reason": "graph_only"}

            if not options.procore_only:
                summary["graph_sync_summary"] = self._stage(
                    "graph", lambda: self._graph_stage(options)
                )
                summary["graph_auth_status"] = summary["graph_sync_summary"].get("auth_status")
            else:
                summary["graph_sync_summary"] = {"status": "skipped", "reason": "procore_only"}

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
                SQLiteMigrator(self.db_path).apply()
                current = self._schema_version()
                schema_ok = current >= LATEST_SCHEMA_VERSION
                migrated = True
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
        pilot_keys = [p.hb_project_key for p in registry.projects if p.status == "pilot"]
        if not pilot_keys:
            return {
                "status": "no_pilot_projects",
                "auth_status": auth_status,
                "ready_for_live_calls": ready,
                "live_read_performed": False,
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
            assert_live_mapping_strict(registry, pilot_keys)

        # Daily refresh now reads through the canonical EndpointAdapter registry via
        # run_live_sync (writing procore_live_*), replacing the stale per-project seed
        # fanout. Dry-run plans only (no live call); apply executes the live chain.
        plan = build_daily_refresh_plan()
        if not do_live_apply:
            return self._procore_plan_only(plan, pilot_keys, auth_status, ready, live_env)
        return self._procore_live_execute(plan, pilot_keys, options, auth_status, ready, live_env)

    def _procore_plan_only(
        self,
        plan: tuple[Any, ...],
        pilot_keys: list[str],
        auth_status: str,
        ready: bool,
        live_env: bool,
    ) -> dict[str, Any]:
        """Dry-run posture: describe the canonical plan without any live read or write."""
        endpoints: list[dict[str, Any]] = []
        counts = _zero_counts()
        for pe in plan:
            keys = pilot_keys[:1] if pe.company_level else pilot_keys
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
            "endpoint_summary": summary,
            "endpoints": endpoints,
            "projects": [{"project_key": k, "status": "planned"} for k in pilot_keys],
            "counts": counts,
        }

    def _procore_live_execute(
        self,
        plan: tuple[Any, ...],
        pilot_keys: list[str],
        options: RefreshOptions,
        auth_status: str,
        ready: bool,
        live_env: bool,
    ) -> dict[str, Any]:
        """Apply posture: run each canonical endpoint via run_live_sync and aggregate."""
        brief_date = self._resolve_brief_date(options)
        start_date, end_date = daily_log_window(brief_date)

        endpoints: list[dict[str, Any]] = []
        per_project: dict[str, dict[str, int]] = {
            k: {"ok": 0, "skipped": 0, "failed": 0} for k in pilot_keys
        }
        counts = _zero_counts()

        for pe in plan:
            keys = pilot_keys[:1] if pe.company_level else pilot_keys
            # A company-level endpoint is fetched once; the remaining pilots are
            # marked intentionally skipped below rather than re-running the
            # company-wide read.
            for key in keys:
                receipt = self._run_live_endpoint(pe, key, start_date, end_date)
                code = classify_receipt(receipt)
                endpoints.append(self._endpoint_row(pe, key, receipt, code))
                self._tally_endpoint(pe, key, code, receipt, counts, per_project)
            if pe.company_level:
                for key in pilot_keys[1:]:
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
            "status": code,
            "retrieved": int(receipt.get("retrieved_count", 0) or 0),
            "upserted": int(receipt.get("sqlite_upserted_count", 0) or 0),
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
            families["calendar_event_index"] = dict(gated)
            families["files"] = dict(gated)
        else:
            info = self._graph_status()
            token_type = info.get("token_type", "none")
            token_ready = token_type != "none"
            if not token_ready:
                blocked = {"status": "blocked_auth_not_ready", "reason": "no_delegated_token"}
                families["calendar_event_index"] = dict(blocked)
                families["files"] = dict(blocked)
                self._acc.degraded = True
                overall = "blocked_auth_not_ready"
            else:
                families["calendar_event_index"] = self._stage(
                    "graph.calendar_event_index",
                    lambda: self._graph_calendar(dry_run),
                )
                families["files"] = self._stage(
                    "graph.files",
                    lambda: self._graph_files(dry_run),
                )
                overall = "ok"

        return {
            "status": overall,
            "auth_status": token_type,
            "token_ready": token_ready,
            "families": families,
            "counts": self._graph_counts(families),
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
                    )
                    results.append(res.model_dump())
        finally:
            client.close()

        indexed = sum(int(r.get("events_indexed", 0) or 0) for r in results)
        return {
            "status": "ok",
            "mode": "dry_run" if dry_run else "apply",
            "live_read_performed": True,
            "sources": len(results),
            "events_indexed": indexed,
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
                or 0
            )
            if fam.get("mode") == "apply" and fam.get("persisted"):
                counts["inserted"] += planned
            else:
                counts["planned"] += planned
        return counts

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
