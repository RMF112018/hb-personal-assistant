"""Phase 08B local macOS notification surface (Prompt 11).

Previews (dry-run, default) and — on apply, *real-but-policy-gated exactly like the Prompt-04 launchd
install* — emits a **local** macOS Notification Center banner (via ``osascript``) summarising the
daily brief. The notification is built from the durable, redacted handoff ``NotificationSummary``
(counts only — no raw content) and recorded as a metadata-only V33 receipt (counts + a title HASH;
the raw notification text is never persisted).

A local Notification Center banner is NOT external delivery (no email/Slack/Teams/SMS/push/webhook/
Graph ``sendMail``) — it is the explicit objective. The actual emission is fail-closed behind the seed
``daily_brief_notification.emit`` flag (default ``false``): while disabled, apply returns
``NOTIFY_DISABLED_BY_POLICY`` and invokes no ``osascript``. The ``osascript`` runner is injectable so
tests never fire a real banner.

Reason codes: ``NOTIFY_NEVER_GENERATED`` (no brief), ``NOTIFY_BLOCKED`` (run blocked/degraded),
``NOTIFY_STALE`` (older than ``max_age_hours``), ``NOTIFY_ELIGIBLE`` (ready; dry-run preview),
``NOTIFY_DISABLED_BY_POLICY`` (apply requested but emission policy off — fail-closed),
``NOTIFY_EMITTED`` (apply + policy on -> local banner emitted), ``NOTIFY_ALREADY_EMITTED`` (idempotent).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.store import read_daily_brief_handoff, read_latest_daily_brief_runs

_FORBIDDEN_TOKENS = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)

# Reason codes (declared in the Phase 08B automation policy + gate contracts).
NOTIFY_NEVER_GENERATED = "NOTIFY_NEVER_GENERATED"
NOTIFY_BLOCKED = "NOTIFY_BLOCKED"
NOTIFY_STALE = "NOTIFY_STALE"
NOTIFY_ELIGIBLE = "NOTIFY_ELIGIBLE"
NOTIFY_DISABLED_BY_POLICY = "NOTIFY_DISABLED_BY_POLICY"
NOTIFY_EMITTED = "NOTIFY_EMITTED"
NOTIFY_ALREADY_EMITTED = "NOTIFY_ALREADY_EMITTED"

_CHANNEL = "local_macos"
_DEFAULT_MAX_AGE_HOURS = 36
_BLOCKED_STATUS = "blocked"

# An injectable notifier: (title, body) -> success bool. Tests pass a fake so no real banner fires.
Notifier = Callable[[str, str], bool]


class DailyBriefNotificationStatus(BaseModel):
    """Daily-brief notification snapshot (metadata-only; redacted; no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    brief_date: str | None = None
    brief_run_id: str | None = None
    eligible: bool = False
    already_emitted: bool = False
    mode: str | None = None  # "dry_run" | "apply"
    notify_status: str | None = (
        None  # "preview" | "emitted" | "already_emitted" | "skipped" | "disabled"
    )
    emitted: bool = False
    policy_emit_enabled: bool = False
    channel: str = _CHANNEL
    title_preview: str | None = None
    body_preview: str | None = None
    title_hash: str | None = None
    attention_count: int = 0
    review_required_count: int = 0
    warning_count: int = 0
    project_count: int = 0
    emitted_utc: str | None = None
    last_run_status: str | None = None
    degradation_mode: str | None = None
    age_seconds: int | None = None
    runs_examined: int = 0
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail", "degradation_mode", "title_preview", "body_preview")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("daily-brief-notify field must not carry raw/forbidden tokens")
        return value


def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _cfg() -> dict[str, Any]:
    cfg = _safe_seed().get("daily_brief_notification", {})
    return cfg if isinstance(cfg, dict) else {}


def _policy_emit_enabled(seed: dict[str, Any] | None = None) -> bool:
    """Read the fail-closed local-emission policy flag (default False). Mirrors launchd's gate."""
    cfg = (seed if seed is not None else _safe_seed()).get("daily_brief_notification", {})
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("emit", False))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _values_only_blob(obj: Any) -> str:
    """Concatenate VALUES (not dict keys) so the raw-content scan ignores schema field names."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif node is not None:
            out.append(str(node))

    walk(obj)
    return " ".join(out)


def _select_run(runs: list[dict[str, Any]], brief_date: str | None) -> dict[str, Any] | None:
    if brief_date is not None:
        for run in runs:
            if str(run.get("brief_date")) == brief_date:
                return run
        return None
    return runs[0] if runs else None


def _prior_emitted(brief_run_id: str | None, brief_date: str | None, db_path: str | None) -> bool:
    """True when a V33 receipt already records an emitted notification for this brief."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    if brief_run_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_notification_receipts "
            "WHERE notify_status = 'emitted' AND brief_run_id = ?",
            (brief_run_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_notification_receipts "
            "WHERE notify_status = 'emitted' AND brief_date = ?",
            (brief_date,),
        ).fetchone()
    return bool(row and row[0])


def build_notification_text(summary: Any) -> tuple[str, str]:
    """Build the redacted (title, body) banner text from a handoff NotificationSummary (counts only)."""
    title = str(getattr(summary, "title_redacted", "") or "HB Daily Brief")
    attention = int(getattr(summary, "attention_count", 0) or 0)
    review = int(getattr(summary, "review_required_count", 0) or 0)
    warning = int(getattr(summary, "warning_count", 0) or 0)
    project = int(getattr(summary, "project_count", 0) or 0)
    body = f"{attention} priority · {review} review · {warning} warnings · {project} projects"
    return title, body


def _default_macos_notifier(title: str, body: str) -> bool:
    """Emit a local macOS Notification Center banner via osascript. Local-only; no shell, no network."""
    if sys.platform != "darwin":  # pragma: no cover - platform-specific
        return False
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_body}" with title "{safe_title}"'
    try:  # pragma: no cover - exercised only on a real Mac with policy enabled
        cp = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=False
        )
        return cp.returncode == 0
    except Exception:  # pragma: no cover - defensive
        return False


def write_daily_brief_notification_receipt(
    *,
    brief_date: str,
    notify_status: str,
    reason_code: str,
    mode: str,
    brief_run_id: str | None = None,
    attention_count: int = 0,
    review_required_count: int = 0,
    warning_count: int = 0,
    project_count: int = 0,
    title_hash: str | None = None,
    emitted_utc: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only V33 notification receipt; returns ``notification_receipt_id``.

    Local-only, additive. ``channel`` is fixed to ``local_macos`` (DB CHECK); only counts + a title
    HASH are stored (never raw text); the no-raw / no-writeback guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V33 table exists (idempotent)
    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO daily_brief_notification_receipts
                (notification_receipt_id, brief_run_id, brief_date, channel, notify_status,
                 reason_code, mode, attention_count, review_required_count, warning_count,
                 project_count, title_hash, emitted_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                brief_run_id,
                brief_date,
                _CHANNEL,
                notify_status,
                reason_code,
                mode,
                attention_count,
                review_required_count,
                warning_count,
                project_count,
                title_hash,
                emitted_utc,
            ),
        )
    return receipt_id


def evaluate_daily_brief_notification(
    *, brief_date: str | None = None, db_path: str | None = None, now: datetime | None = None
) -> DailyBriefNotificationStatus:
    """Read-only notification eligibility for the latest (or ``brief_date``) brief. Writes nothing."""
    cfg = _cfg()
    max_age_seconds = int(cfg.get("max_age_hours", _DEFAULT_MAX_AGE_HOURS)) * 3600
    now = now or datetime.now(timezone.utc)
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    generated = datetime.now(timezone.utc).isoformat()
    policy_emit = _policy_emit_enabled(seed)

    runs = read_latest_daily_brief_runs(db_path=db_path, limit=50)
    base: dict[str, Any] = {
        "policy_version": str(seed.get("version", "unknown")),
        "schema_version": schema_version,
        "generated_utc": generated,
        "runs_examined": len(runs),
        "policy_emit_enabled": policy_emit,
    }

    run = _select_run(runs, brief_date)
    if run is None:
        return DailyBriefNotificationStatus(
            overall_status="attention",
            reason_code=NOTIFY_NEVER_GENERATED,
            brief_date=brief_date,
            detail="no_daily_brief_run_for_date",
            **base,
        )

    run_brief_date = str(run.get("brief_date")) if run.get("brief_date") else None
    brief_run_id = str(run.get("brief_run_id")) if run.get("brief_run_id") else None
    last_status = str(run.get("status")) if run.get("status") is not None else None
    degradation = run.get("degradation_mode")
    last_utc = run.get("generated_utc")
    parsed = _parse_utc(str(last_utc) if last_utc else None)
    age = int((now.astimezone(timezone.utc) - parsed).total_seconds()) if parsed else None

    common: dict[str, Any] = {
        "brief_date": run_brief_date,
        "brief_run_id": brief_run_id,
        "last_run_status": last_status,
        "degradation_mode": str(degradation) if degradation else None,
        "age_seconds": age,
        **base,
    }

    if last_status == _BLOCKED_STATUS or str(degradation or "") == _BLOCKED_STATUS:
        return DailyBriefNotificationStatus(
            overall_status="attention",
            reason_code=NOTIFY_BLOCKED,
            detail="brief_run_blocked_or_degraded",
            **common,
        )
    if age is not None and age > max_age_seconds:
        return DailyBriefNotificationStatus(
            overall_status="attention",
            reason_code=NOTIFY_STALE,
            detail="brief_older_than_max_age",
            **common,
        )
    if _prior_emitted(brief_run_id, run_brief_date, db_path):
        return DailyBriefNotificationStatus(
            overall_status="ok",
            reason_code=NOTIFY_ALREADY_EMITTED,
            eligible=True,
            already_emitted=True,
            detail="already_emitted_local_notification",
            **common,
        )
    return DailyBriefNotificationStatus(
        overall_status="ok",
        reason_code=NOTIFY_ELIGIBLE,
        eligible=True,
        detail="ready_for_local_notification",
        **common,
    )


def run_daily_brief_notification_agent(
    *,
    brief_date: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
    notifier: Notifier | None = None,
    policy_emit: bool | None = None,
) -> tuple[DailyBriefNotificationStatus, str | None]:
    """Evaluate, then (apply, dry-run default) emit a local macOS notification for the brief.

    Dry-run previews the redacted banner and writes nothing. Apply is fail-closed behind the policy
    flag: while emission is disabled (default) it returns ``NOTIFY_DISABLED_BY_POLICY`` and invokes no
    ``osascript``; when enabled it calls ``notifier(title, body)`` and records a V33 receipt. The
    optional V28 agent receipt is emit-gated. ``policy_emit`` overrides the seed flag (tests/proofs).
    """
    status = evaluate_daily_brief_notification(brief_date=brief_date, db_path=db_path, now=now)
    dry_run = mode != "apply"
    status.mode = mode
    emit_allowed = _policy_emit_enabled() if policy_emit is None else policy_emit
    status.policy_emit_enabled = emit_allowed

    if status.reason_code in (NOTIFY_ELIGIBLE, NOTIFY_ALREADY_EMITTED):
        payload = read_daily_brief_handoff(str(status.brief_run_id), db_path=db_path)
        summary = payload.notification_summary if payload is not None else None
        if summary is not None:
            title, body = build_notification_text(summary)
            status.title_preview = title
            status.body_preview = body
            status.title_hash = _sha256(title)
            status.attention_count = int(getattr(summary, "attention_count", 0) or 0)
            status.review_required_count = int(getattr(summary, "review_required_count", 0) or 0)
            status.warning_count = int(getattr(summary, "warning_count", 0) or 0)
            status.project_count = int(getattr(summary, "project_count", 0) or 0)

    if status.reason_code == NOTIFY_ALREADY_EMITTED:
        status.notify_status = "already_emitted"
    elif dry_run:
        status.notify_status = "preview"
    elif status.reason_code == NOTIFY_ELIGIBLE:
        if not emit_allowed:
            # Fail-closed: apply requested but local emission disabled by policy. No osascript.
            status.reason_code = NOTIFY_DISABLED_BY_POLICY
            status.overall_status = "attention"
            status.notify_status = "disabled"
            status.detail = "local_notification_disabled_by_policy"
        else:
            send = notifier if notifier is not None else _default_macos_notifier
            ok = bool(send(status.title_preview or "HB Daily Brief", status.body_preview or ""))
            emitted_utc = datetime.now(timezone.utc).isoformat()
            status.reason_code = NOTIFY_EMITTED
            status.notify_status = "emitted"
            status.emitted = ok
            status.emitted_utc = emitted_utc
            status.detail = "local_notification_emitted"
            write_daily_brief_notification_receipt(
                brief_date=str(status.brief_date),
                brief_run_id=status.brief_run_id,
                notify_status="emitted",
                reason_code=NOTIFY_EMITTED,
                mode="apply",
                attention_count=status.attention_count,
                review_required_count=status.review_required_count,
                warning_count=status.warning_count,
                project_count=status.project_count,
                title_hash=status.title_hash,
                emitted_utc=emitted_utc,
                db_path=db_path,
            )
    else:
        # Blocked / stale / never-generated: refuse to notify.
        status.notify_status = "skipped"

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="daily_brief_notification_agent",
            run_kind="daily_brief_notification",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


def build_daily_brief_notification_proof() -> dict[str, Any]:
    """Deterministic proof (temp migrated DB) over all notification paths."""
    import sqlite3
    import tempfile
    from datetime import timedelta

    from hb_assistant.construction.store import ConstructionStore

    now = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

    def _insert_run(db: str, *, brief_run_id: str, status: str, generated_utc: str) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, "
                " project_count, review_required_count, generated_utc) "
                "VALUES (?, '2026-06-02', 'dry_run', ?, 3, 1, ?)",
                (brief_run_id, status, generated_utc),
            )
            conn.execute(
                "INSERT INTO daily_brief_handoff_lines (line_id, brief_run_id, section, line_index, "
                " title_redacted, review_tier, source_refs_json, generated_utc) "
                "VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI 042', 2, '[]', ?)",
                (uuid.uuid4().hex, brief_run_id, generated_utc),
            )
        conn.close()

    calls: list[tuple[str, str]] = []

    def _fake_notifier(title: str, body: str) -> bool:
        calls.append((title, body))
        return True

    with tempfile.TemporaryDirectory() as tmp:
        recent = (now - timedelta(hours=1)).isoformat()

        empty_db = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty_db)
        never_run = evaluate_daily_brief_notification(db_path=empty_db, now=now)

        blocked_db = f"{tmp}/blocked.sqlite3"
        ConstructionStore(blocked_db)
        _insert_run(
            blocked_db, brief_run_id=uuid.uuid4().hex, status="blocked", generated_utc=recent
        )
        blocked = evaluate_daily_brief_notification(db_path=blocked_db, now=now)

        stale_db = f"{tmp}/stale.sqlite3"
        ConstructionStore(stale_db)
        _insert_run(
            stale_db,
            brief_run_id=uuid.uuid4().hex,
            status="synthesized",
            generated_utc=(now - timedelta(hours=72)).isoformat(),
        )
        stale = evaluate_daily_brief_notification(db_path=stale_db, now=now)

        # Disabled-by-policy: apply with emission OFF must NOT call the notifier or write a receipt.
        disabled_db = f"{tmp}/disabled.sqlite3"
        ConstructionStore(disabled_db)
        _insert_run(disabled_db, brief_run_id="run-dis", status="synthesized", generated_utc=recent)
        preview, _ = run_daily_brief_notification_agent(
            db_path=disabled_db, mode="dry_run", now=now, notifier=_fake_notifier
        )
        disabled, _ = run_daily_brief_notification_agent(
            db_path=disabled_db, mode="apply", now=now, notifier=_fake_notifier, policy_emit=False
        )
        calls_after_disabled = len(calls)
        disabled_conn = sqlite3.connect(disabled_db)
        disabled_receipts = disabled_conn.execute(
            "SELECT COUNT(*) FROM daily_brief_notification_receipts"
        ).fetchone()[0]
        disabled_conn.close()

        # Emitted: apply with emission ON (injected fake) -> banner emitted + V33 receipt.
        ok_db = f"{tmp}/ok.sqlite3"
        ConstructionStore(ok_db)
        _insert_run(ok_db, brief_run_id="run-ok", status="synthesized", generated_utc=recent)
        emitted, _ = run_daily_brief_notification_agent(
            db_path=ok_db, mode="apply", now=now, notifier=_fake_notifier, policy_emit=True
        )
        idempotent, _ = run_daily_brief_notification_agent(
            db_path=ok_db, mode="apply", now=now, notifier=_fake_notifier, policy_emit=True
        )

    blob = _values_only_blob(
        [
            never_run.model_dump(),
            blocked.model_dump(),
            stale.model_dump(),
            preview.model_dump(),
            disabled.model_dump(),
            emitted.model_dump(),
            idempotent.model_dump(),
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        never_run.reason_code == NOTIFY_NEVER_GENERATED
        and blocked.reason_code == NOTIFY_BLOCKED
        and stale.reason_code == NOTIFY_STALE
        and preview.reason_code == NOTIFY_ELIGIBLE
        and preview.notify_status == "preview"
        and disabled.reason_code == NOTIFY_DISABLED_BY_POLICY
        and calls_after_disabled == 0  # disabled + dry-run never called the notifier
        and disabled_receipts == 0  # and wrote no receipt
        and emitted.reason_code == NOTIFY_EMITTED
        and emitted.emitted is True
        and idempotent.reason_code == NOTIFY_ALREADY_EMITTED
        and no_raw_content
    )
    return {
        "proof": "phase_08b_daily_brief_notification",
        "proof_passed": proof_passed,
        "never_generated_reason_code": never_run.reason_code,
        "blocked_reason_code": blocked.reason_code,
        "stale_reason_code": stale.reason_code,
        "eligible_reason_code": preview.reason_code,
        "disabled_reason_code": disabled.reason_code,
        "emitted_reason_code": emitted.reason_code,
        "already_emitted_reason_code": idempotent.reason_code,
        "disabled_invoked_no_notifier": calls_after_disabled == 0,
        "disabled_wrote_no_receipt": disabled_receipts == 0,
        "no_raw_content": no_raw_content,
        "channel": _CHANNEL,
        "guardrails": {
            "local_first": True,
            "dry_run_default": True,
            "fail_closed_emission": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
