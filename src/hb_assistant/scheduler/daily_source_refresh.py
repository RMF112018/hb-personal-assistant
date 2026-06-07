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
                brief_date=schedule_date.isoformat(),
            )
        master = sc.enable_live_reads
        procore_live = bool(master and sc.enable_procore_live_reads)
        graph_live = bool(master and sc.enable_graph_live_reads)
        any_live = procore_live or graph_live
        return RefreshOptions(
            all_=True,
            apply=True,
            confirm=True,
            # When no source is live, run pure local-only (no auth/status/probe at all).
            mock_data=not any_live,
            allow_procore_live=procore_live,
            allow_graph_live=graph_live,
            brief_date=schedule_date.isoformat(),
        )

    def execute(self, *, schedule_date: date, trigger: str) -> ScheduledRefreshReceipt:
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
            status="ok" if status in ("ok", "degraded") else "failed",
        )
        receipt.receipt_path = _write_receipt(evidence_dir, receipt)
        return receipt


def _redact(text: str) -> str:
    home = os.path.expanduser("~")
    return text.replace(home, "~") if text.startswith(home) else text


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
