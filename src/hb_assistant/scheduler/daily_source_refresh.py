"""The scheduled job: call the unified source-refresh orchestrator in-process.

Never a manual Graph/Procore command chain. Live-read options are ALWAYS passed
explicitly (never relying on RefreshOptions defaults). Production runs are local-only
unless the scheduler config explicitly enables live reads; live Procore reads also
require HB_PROCORE_LIVE, which this job sets only for the duration of the run.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Iterator

from hb_assistant.launcher.profiles import Profile
from hb_assistant.procore.live_gate import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.scheduler.models import ScheduledRefreshReceipt
from hb_assistant.source_refresh.orchestrator import (
    RefreshOptions,
    SourceRefreshOrchestrator,
    _safe_git_sha,
)
from hb_assistant.store.repositories import Store


@contextlib.contextmanager
def _maybe_live_env(enable: bool) -> Iterator[None]:
    """Set HB_PROCORE_LIVE=1 only for the duration of the run, then restore."""
    if not enable:
        yield
        return
    prior = os.environ.get(LIVE_ENV_VAR)
    os.environ[LIVE_ENV_VAR] = LIVE_ENV_ENABLER
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(LIVE_ENV_VAR, None)
        else:
            os.environ[LIVE_ENV_VAR] = prior


class DailySourceRefreshJob:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def build_options(self, schedule_date: date) -> RefreshOptions:
        """Explicit per-environment live-read options (never relies on defaults)."""
        sc = self.profile.scheduler
        if self.profile.environment == "dev":
            # Dev: mock/local only — no Procore/Graph auth/status/probe/read, no creds.
            return RefreshOptions(
                all_=True,
                apply=True,
                confirm=True,
                mock_data=True,
                allow_procore_live=False,
                allow_graph_live=False,
                procore_project_scope=sc.procore_project_scope,
                procore_project_keys=tuple(sc.procore_project_keys),
                brief_date=schedule_date.isoformat(),
            )
        master = sc.enable_live_reads
        procore_live = bool(master and sc.enable_procore_live_reads)
        graph_live = bool(master and sc.enable_graph_live_reads)
        # Production is never "mock". Local-only (no live source) still performs zero
        # live auth/status/probe because the orchestrator gates on allow_*_live, not
        # mock_data. mock_data is reserved for Dev / explicit --mock-data.
        return RefreshOptions(
            all_=True,
            apply=True,
            confirm=True,
            mock_data=False,
            allow_procore_live=procore_live,
            allow_graph_live=graph_live,
            procore_project_scope=sc.procore_project_scope,
            procore_project_keys=tuple(sc.procore_project_keys),
            brief_date=schedule_date.isoformat(),
        )

    def execute(self, *, schedule_date: date, trigger: str) -> ScheduledRefreshReceipt:
        # Forced/manual runs do not inherit the launchd plist's NumberOfFiles limits, so
        # raise RLIMIT_NOFILE here too (best-effort) and record the FD budget + an open-FD
        # snapshot, guarding the `OSError: [Errno 24] Too many open files` failure mode.
        diagnostics = _raise_fd_limit()
        diagnostics["open_fd_count_start"] = _open_fd_count()

        options = self.build_options(schedule_date)
        procore_live = options.allow_procore_live and not options.mock_data
        graph_live = options.allow_graph_live and not options.mock_data

        # Ensure the isolated environment DB directory exists (dev's "(Dev)" root may be
        # fresh) so all local SQLite access binds to this environment's DB.
        self.profile.db_path.parent.mkdir(parents=True, exist_ok=True)
        store = Store(db_path=str(self.profile.db_path))
        run_id: int | None = None
        try:
            run_id = store.record_assistant_run(
                run_type="daily-source-refresh",
                target_date=schedule_date.isoformat(),
                trigger=trigger,
                dry_run=False,
            )
        except Exception:
            run_id = None

        evidence_dir = self.profile.evidence_path / "scheduled"
        orchestrator = SourceRefreshOrchestrator(
            db_path=self.profile.db_path, evidence_dir=evidence_dir
        )
        with _maybe_live_env(procore_live):
            summary = orchestrator.run(options=options)

        status = str(summary.get("status", "unknown"))
        if run_id is not None:
            with contextlib.suppress(Exception):
                store.finish_assistant_run(run_id, status)

        # Persist the FULL redacted orchestrator summary (failures[], per-stage status,
        # next_operator_action) so a degraded run is diagnosable without re-running. The
        # orchestrator owns the redaction; this never raises into the run.
        evidence_summary_path: str | None = None
        with contextlib.suppress(Exception):
            run_tag = f"run{run_id}" if run_id is not None else "runNA"
            written = orchestrator.write_evidence(
                summary, suffix=f"{self.profile.environment}-{schedule_date.isoformat()}-{run_tag}"
            )
            evidence_summary_path = _redact(str(written))

        diagnostics["open_fd_count_end"] = _open_fd_count()

        failures = _safe_failures(summary.get("failures") or [])
        stages = {
            "preflight": _stage_status(summary.get("preflight")),
            "procore": _stage_status(summary.get("procore_sync_summary")),
            "procore_projection": _stage_status(summary.get("procore_projection_summary")),
            "graph": _stage_status(summary.get("graph_sync_summary")),
            "email_calendar_projection": _stage_status(
                summary.get("email_calendar_projection_summary")
            ),
            "rebuild": _stage_status(summary.get("retrieval_rebuild_summary")),
        }

        receipt = ScheduledRefreshReceipt(
            generated_utc=datetime.now(timezone.utc).isoformat(),
            repo_sha=_safe_git_sha(),
            environment=self.profile.environment,
            schedule_date=schedule_date.isoformat(),
            trigger=trigger,
            mode="live_source" if options.live_reads_enabled else "local_only",
            live_reads_enabled=options.live_reads_enabled,
            procore_live=procore_live,
            graph_live=graph_live,
            mock_data=options.mock_data,
            db_path=_redact(str(self.profile.db_path)),
            orchestrator_status=status,
            ledger_run_id=run_id,
            counts=summary.get("sqlite_upsert_summary", {}).get("total", {}),
            guardrails=summary.get("guardrails", {}),
            failure_count=len(failures),
            failures=failures,
            stages=stages,
            procore_projection_summary=summary.get("procore_projection_summary", {}),
            graph_sync_summary=summary.get("graph_sync_summary", {}),
            email_calendar_projection_summary=summary.get(
                "email_calendar_projection_summary", {}
            ),
            procore_auth_status=(
                str(summary.get("procore_auth_status"))
                if summary.get("procore_auth_status") is not None
                else None
            ),
            graph_auth_status=(
                str(summary.get("graph_auth_status"))
                if summary.get("graph_auth_status") is not None
                else None
            ),
            next_operator_action=summary.get("next_operator_action"),
            evidence_summary_path=evidence_summary_path,
            diagnostics=diagnostics,
            # Honest: never collapse degraded -> ok. The receipt mirrors the orchestrator.
            status=status if status in ("ok", "degraded", "failed") else "failed",
        )
        receipt.receipt_path = _write_receipt(evidence_dir, receipt)
        return receipt


def _raise_fd_limit(target: int = 8192) -> dict[str, Any]:
    """Best-effort raise of ``RLIMIT_NOFILE`` so forced/manual runs match the launchd budget.

    Returns the resulting soft/hard limits (counts only). Never raises into the run; if the
    platform lacks ``resource`` or the call is denied, the run proceeds unchanged.
    """
    info: dict[str, Any] = {}
    try:
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        want = target if hard in (resource.RLIM_INFINITY, -1) else min(target, hard)
        if soft != resource.RLIM_INFINITY and soft < want:
            with contextlib.suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
                soft = want
        info["fd_soft_limit"] = soft
        info["fd_hard_limit"] = hard
    except Exception:  # noqa: BLE001 — diagnostics are best-effort, never fatal
        pass
    return info


def _open_fd_count() -> int | None:
    """Best-effort count of currently-open file descriptors (stdlib only, no psutil)."""
    for path in ("/dev/fd", f"/proc/{os.getpid()}/fd"):
        try:
            return len(os.listdir(path))
        except OSError:
            continue
    return None


def _redact(text: str) -> str:
    home = os.path.expanduser("~")
    return text.replace(home, "~") if text.startswith(home) else text


_RECEIPT_SCRUB = ("access_token", "refresh_token", "client_secret", "Bearer", "SECRET")
# Defense-in-depth: redact token-shaped values (JWTs, bearer tokens, long opaque secrets) even if a
# reason string somehow carried one. Orchestrator/Procore reasons are already reason-code-level.
_TOKENISH = re.compile(r"eyJ[A-Za-z0-9_.\-]{6,}|Bearer\s+[A-Za-z0-9._\-]{6,}|[A-Za-z0-9_\-]{40,}")


def _scrub(text: str) -> str:
    for bad in _RECEIPT_SCRUB:
        text = text.replace(bad, "[REDACTED]")
    return _TOKENISH.sub("[REDACTED]", text)


def _stage_status(stage: Any) -> str:
    """Extract a safe per-stage status string from a summary sub-object."""
    if isinstance(stage, dict):
        return str(stage.get("status", "unknown"))
    return "unknown"


def _safe_failures(raw: Any) -> list[dict[str, Any]]:
    """Project orchestrator failures[] to a bounded, redacted, operator-safe shape (no secrets)."""
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for f in raw[:20]:
        if not isinstance(f, dict):
            continue
        out.append(
            {
                "stage": str(f.get("stage", ""))[:80],
                "status": str(f.get("status", ""))[:24],
                "reason": _scrub(str(f.get("reason", ""))[:200]),
            }
        )
    return out


def _write_receipt(evidence_dir: Any, receipt: ScheduledRefreshReceipt) -> str:
    from pathlib import Path

    out = Path(evidence_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"scheduled-refresh-{receipt.environment}-{receipt.schedule_date}.json"
    payload = receipt.model_dump()
    payload.pop("receipt_path", None)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    for bad in ("access_token", "refresh_token", "client_secret", "Bearer", "SECRET"):
        text = text.replace(bad, "[REDACTED]")
    path.write_text(text)
    return str(path)
