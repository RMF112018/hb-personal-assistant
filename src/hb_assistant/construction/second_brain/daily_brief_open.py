"""Phase 08B brief-open, consolidated delivery-status & receipts workflows (Prompt 12).

Three additive, local-only surfaces over the daily-brief delivery ledgers:

1. **Brief open** — previews (dry-run, default) and — on apply, *real-but-policy-gated like the
   Prompt-11 notify surface* — runs macOS ``open`` on a produced LOCAL artifact (the delivered vault
   note (V31) or the rendered HTML (V32)), recording a metadata-only V34 receipt (redacted path +
   path hash; never raw content). ``open_target`` is pinned to ``vault`` | ``html``.
2. **Consolidated delivery status** — a read-only view that ties the four lifecycle stages together
   (delivered V31 / rendered V32 / notified V33 / opened V34) with a single ``STATUS_*`` reason code.
   (The per-surface ``delivery-status`` command from Prompt 09 is unchanged.)
3. **Receipts** — a read-only metadata list across the four ledgers.

Fail-closed: while seed ``daily_brief_open.open=false`` (default), apply returns
``OPEN_DISABLED_BY_POLICY`` and invokes no ``open``. The ``open`` runner is injectable so tests never
launch an app. No external writeback/delivery; no raw content persisted.
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
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator, ensure_schema_ready

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.output import resolve_brief_path
from .daily_brief.store import read_latest_daily_brief_runs

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

# Brief-open reason codes.
OPEN_NEVER_GENERATED = "OPEN_NEVER_GENERATED"
OPEN_BLOCKED = "OPEN_BLOCKED"
OPEN_STALE = "OPEN_STALE"
OPEN_NOT_AVAILABLE = "OPEN_NOT_AVAILABLE"
OPEN_ELIGIBLE = "OPEN_ELIGIBLE"
OPEN_DISABLED_BY_POLICY = "OPEN_DISABLED_BY_POLICY"
OPEN_COMPLETED = "OPEN_COMPLETED"
OPEN_ALREADY_OPENED = "OPEN_ALREADY_OPENED"

# Consolidated-status reason codes.
STATUS_NEVER_GENERATED = "STATUS_NEVER_GENERATED"
STATUS_NOT_DELIVERED = "STATUS_NOT_DELIVERED"
STATUS_DELIVERED = "STATUS_DELIVERED"
STATUS_PARTIAL = "STATUS_PARTIAL"
STATUS_COMPLETE = "STATUS_COMPLETE"

_VALID_TARGETS = ("vault", "html")
_DEFAULT_MAX_AGE_HOURS = 36
_BLOCKED_STATUS = "blocked"

# An injectable opener: (path) -> success bool. Tests pass a fake so no app is launched.
Opener = Callable[[str], bool]


class DailyBriefOpenStatus(BaseModel):
    """Brief-open snapshot (metadata-only; redacted; no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    brief_date: str | None = None
    brief_run_id: str | None = None
    open_target: str = "vault"
    eligible: bool = False
    already_opened: bool = False
    mode: str | None = None
    open_status: str | None = (
        None  # "preview" | "opened" | "already_opened" | "skipped" | "disabled"
    )
    opened: bool = False
    policy_open_enabled: bool = False
    path_redacted: str | None = None
    path_hash: str | None = None
    opened_utc: str | None = None
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

    @field_validator("detail", "degradation_mode", "path_redacted")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("daily-brief-open field must not carry raw/forbidden tokens")
        return value


class DailyBriefLifecycleStatus(BaseModel):
    """Consolidated delivery-lifecycle snapshot (metadata-only)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    brief_date: str | None = None
    brief_run_id: str | None = None
    delivered: bool = False
    rendered: bool = False
    notified: bool = False
    opened: bool = False
    last_run_status: str | None = None
    runs_examined: int = 0
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}


def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _cfg() -> dict[str, Any]:
    cfg = _safe_seed().get("daily_brief_open", {})
    return cfg if isinstance(cfg, dict) else {}


def _policy_open_enabled(seed: dict[str, Any] | None = None) -> bool:
    """Read the fail-closed local-open policy flag (default False). Mirrors notify's gate."""
    cfg = (seed if seed is not None else _safe_seed()).get("daily_brief_open", {})
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("open", False))


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


def _redact_path(path: Path) -> str:
    """Redact an absolute path to a repo-/home-free relative form."""
    policy = PathPolicy()
    for root in (policy.get_app_support(), policy.get_vault_root()):
        try:
            return str(path.relative_to(root))
        except (ValueError, Exception):  # pragma: no cover - defensive
            continue
    return f"{path.parent.name}/{path.name}"


def _resolve_target_path(
    brief_date: str,
    target: str,
    *,
    vault_brief_dir: str | None = None,
    html_dir: str | None = None,
) -> Path:
    if target == "html":
        base = Path(html_dir) if html_dir is not None else PathPolicy().get_html_dir()
        return base / f"{brief_date}_daily_brief.html"
    return resolve_brief_path(brief_date, vault_brief_dir=vault_brief_dir)


def _conn(db_path: str | None) -> Any:
    ensure_schema_ready(db_path)
    return get_connection(Path(db_path) if db_path is not None else None)


def _has_terminal_receipt(
    conn: Any,
    table: str,
    status_col: str,
    status_val: str,
    brief_run_id: str | None,
    brief_date: str | None,
) -> bool:
    if brief_run_id is not None:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {status_col} = ? AND brief_run_id = ?",
            (status_val, brief_run_id),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {status_col} = ? AND brief_date = ?",
            (status_val, brief_date),
        ).fetchone()
    return bool(row and row[0])


def _artifact_present(
    brief_run_id: str | None, brief_date: str | None, target: str, db_path: str | None
) -> bool:
    """Was the target artifact produced? vault -> a V31 delivered row; html -> a V32 rendered row."""
    conn = _conn(db_path)
    if target == "html":
        return _has_terminal_receipt(
            conn,
            "daily_brief_html_render_receipts",
            "render_status",
            "rendered",
            brief_run_id,
            brief_date,
        )
    return _has_terminal_receipt(
        conn,
        "daily_brief_delivery_receipts",
        "delivery_status",
        "delivered",
        brief_run_id,
        brief_date,
    )


def _prior_opened(
    brief_run_id: str | None, brief_date: str | None, target: str, db_path: str | None
) -> bool:
    conn = _conn(db_path)
    if brief_run_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_open_receipts "
            "WHERE open_status = 'opened' AND open_target = ? AND brief_run_id = ?",
            (target, brief_run_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_open_receipts "
            "WHERE open_status = 'opened' AND open_target = ? AND brief_date = ?",
            (target, brief_date),
        ).fetchone()
    return bool(row and row[0])


def write_daily_brief_open_receipt(
    *,
    brief_date: str,
    open_target: str,
    open_status: str,
    reason_code: str,
    mode: str,
    brief_run_id: str | None = None,
    path_redacted: str | None = None,
    path_hash: str | None = None,
    opened_utc: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only V34 open receipt; returns ``open_receipt_id``.

    Local-only, additive. ``open_target`` is constrained to vault|html (DB CHECK); only a redacted
    path + a path HASH are stored (never raw content); guard columns stay at 0 via DB CHECKs.
    """
    ensure_schema_ready(db_path)
    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO daily_brief_open_receipts
                (open_receipt_id, brief_run_id, brief_date, open_target, open_status, reason_code,
                 mode, path_redacted, path_hash, opened_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                brief_run_id,
                brief_date,
                open_target,
                open_status,
                reason_code,
                mode,
                path_redacted,
                path_hash,
                opened_utc,
            ),
        )
    return receipt_id


def _default_opener(path: str) -> bool:
    """Open a local file with the macOS ``open`` command. Local-only; no shell, no network."""
    if sys.platform != "darwin":  # pragma: no cover - platform-specific
        return False
    try:  # pragma: no cover - exercised only on a real Mac with policy enabled
        cp = subprocess.run(["open", path], capture_output=True, text=True, check=False)
        return cp.returncode == 0
    except Exception:  # pragma: no cover - defensive
        return False


def evaluate_brief_open(
    *,
    brief_date: str | None = None,
    target: str = "vault",
    db_path: str | None = None,
    now: datetime | None = None,
) -> DailyBriefOpenStatus:
    """Read-only brief-open eligibility for the latest (or ``brief_date``) brief. Writes nothing."""
    if target not in _VALID_TARGETS:
        target = "vault"
    cfg = _cfg()
    max_age_seconds = int(cfg.get("max_age_hours", _DEFAULT_MAX_AGE_HOURS)) * 3600
    now = now or datetime.now(timezone.utc)
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    generated = datetime.now(timezone.utc).isoformat()

    runs = read_latest_daily_brief_runs(db_path=db_path, limit=50)
    base: dict[str, Any] = {
        "open_target": target,
        "policy_version": str(seed.get("version", "unknown")),
        "schema_version": schema_version,
        "generated_utc": generated,
        "runs_examined": len(runs),
        "policy_open_enabled": _policy_open_enabled(seed),
    }

    run = _select_run(runs, brief_date)
    if run is None:
        return DailyBriefOpenStatus(
            overall_status="attention",
            reason_code=OPEN_NEVER_GENERATED,
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
        return DailyBriefOpenStatus(
            overall_status="attention",
            reason_code=OPEN_BLOCKED,
            detail="brief_run_blocked_or_degraded",
            **common,
        )
    if age is not None and age > max_age_seconds:
        return DailyBriefOpenStatus(
            overall_status="attention",
            reason_code=OPEN_STALE,
            detail="brief_older_than_max_age",
            **common,
        )
    if not _artifact_present(brief_run_id, run_brief_date, target, db_path):
        return DailyBriefOpenStatus(
            overall_status="attention",
            reason_code=OPEN_NOT_AVAILABLE,
            detail="target_artifact_not_produced",
            **common,
        )
    if _prior_opened(brief_run_id, run_brief_date, target, db_path):
        return DailyBriefOpenStatus(
            overall_status="ok",
            reason_code=OPEN_ALREADY_OPENED,
            eligible=True,
            already_opened=True,
            detail="already_opened_local_artifact",
            **common,
        )
    return DailyBriefOpenStatus(
        overall_status="ok",
        reason_code=OPEN_ELIGIBLE,
        eligible=True,
        detail="ready_to_open_local_artifact",
        **common,
    )


def run_brief_open_agent(
    *,
    brief_date: str | None = None,
    target: str = "vault",
    mode: str = "dry_run",
    db_path: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
    opener: Opener | None = None,
    policy_open: bool | None = None,
    vault_brief_dir: str | None = None,
    html_dir: str | None = None,
) -> tuple[DailyBriefOpenStatus, str | None]:
    """Evaluate, then (apply, dry-run default) open the produced local artifact for the brief.

    Dry-run previews the would-be ``open`` and writes nothing. Apply is fail-closed behind the policy
    flag: while open is disabled (default) it returns ``OPEN_DISABLED_BY_POLICY`` and invokes no
    ``open``; when enabled it calls ``opener(path)`` and records a V34 receipt. ``policy_open``
    overrides the seed flag (tests/proofs).
    """
    if target not in _VALID_TARGETS:
        target = "vault"
    status = evaluate_brief_open(brief_date=brief_date, target=target, db_path=db_path, now=now)
    dry_run = mode != "apply"
    status.mode = mode
    open_allowed = _policy_open_enabled() if policy_open is None else policy_open
    status.policy_open_enabled = open_allowed

    if status.reason_code in (OPEN_ELIGIBLE, OPEN_ALREADY_OPENED) and status.brief_date:
        path = _resolve_target_path(
            str(status.brief_date), target, vault_brief_dir=vault_brief_dir, html_dir=html_dir
        )
        status.path_redacted = _redact_path(path)
        status.path_hash = _sha256(str(path))

    if status.reason_code == OPEN_ALREADY_OPENED:
        status.open_status = "already_opened"
    elif dry_run:
        status.open_status = "preview"
    elif status.reason_code == OPEN_ELIGIBLE:
        if not open_allowed:
            status.reason_code = OPEN_DISABLED_BY_POLICY
            status.overall_status = "attention"
            status.open_status = "disabled"
            status.detail = "local_open_disabled_by_policy"
        else:
            path = _resolve_target_path(
                str(status.brief_date), target, vault_brief_dir=vault_brief_dir, html_dir=html_dir
            )
            send = opener if opener is not None else _default_opener
            ok = bool(send(str(path)))
            opened_utc = datetime.now(timezone.utc).isoformat()
            status.reason_code = OPEN_COMPLETED
            status.open_status = "opened"
            status.opened = ok
            status.opened_utc = opened_utc
            status.detail = "opened_local_artifact"
            write_daily_brief_open_receipt(
                brief_date=str(status.brief_date),
                brief_run_id=status.brief_run_id,
                open_target=target,
                open_status="opened",
                reason_code=OPEN_COMPLETED,
                mode="apply",
                path_redacted=status.path_redacted,
                path_hash=status.path_hash,
                opened_utc=opened_utc,
                db_path=db_path,
            )
    else:
        status.open_status = "skipped"

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="daily_brief_open_agent",
            run_kind="daily_brief_open",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


def evaluate_brief_delivery_status(
    *, brief_date: str | None = None, db_path: str | None = None, now: datetime | None = None
) -> DailyBriefLifecycleStatus:
    """Read-only consolidated lifecycle status (delivered/rendered/notified/opened). Writes nothing."""
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    generated = datetime.now(timezone.utc).isoformat()

    runs = read_latest_daily_brief_runs(db_path=db_path, limit=50)
    base: dict[str, Any] = {
        "policy_version": str(seed.get("version", "unknown")),
        "schema_version": schema_version,
        "generated_utc": generated,
        "runs_examined": len(runs),
    }
    run = _select_run(runs, brief_date)
    if run is None:
        return DailyBriefLifecycleStatus(
            overall_status="attention",
            reason_code=STATUS_NEVER_GENERATED,
            brief_date=brief_date,
            detail="no_daily_brief_run_for_date",
            **base,
        )

    run_brief_date = str(run.get("brief_date")) if run.get("brief_date") else None
    brief_run_id = str(run.get("brief_run_id")) if run.get("brief_run_id") else None
    conn = _conn(db_path)
    delivered = _has_terminal_receipt(
        conn,
        "daily_brief_delivery_receipts",
        "delivery_status",
        "delivered",
        brief_run_id,
        run_brief_date,
    )
    rendered = _has_terminal_receipt(
        conn,
        "daily_brief_html_render_receipts",
        "render_status",
        "rendered",
        brief_run_id,
        run_brief_date,
    )
    notified = _has_terminal_receipt(
        conn,
        "daily_brief_notification_receipts",
        "notify_status",
        "emitted",
        brief_run_id,
        run_brief_date,
    )
    opened = _has_terminal_receipt(
        conn,
        "daily_brief_open_receipts",
        "open_status",
        "opened",
        brief_run_id,
        run_brief_date,
    )

    common: dict[str, Any] = {
        "brief_date": run_brief_date,
        "brief_run_id": brief_run_id,
        "last_run_status": str(run.get("status")) if run.get("status") is not None else None,
        "delivered": delivered,
        "rendered": rendered,
        "notified": notified,
        "opened": opened,
        **base,
    }
    if not delivered:
        return DailyBriefLifecycleStatus(
            overall_status="attention",
            reason_code=STATUS_NOT_DELIVERED,
            detail="brief_not_yet_delivered",
            **common,
        )
    downstream = [rendered, notified, opened]
    if all(downstream):
        return DailyBriefLifecycleStatus(
            overall_status="ok",
            reason_code=STATUS_COMPLETE,
            detail="delivered_rendered_notified_opened",
            **common,
        )
    if any(downstream):
        return DailyBriefLifecycleStatus(
            overall_status="ok",
            reason_code=STATUS_PARTIAL,
            detail="delivered_with_some_downstream",
            **common,
        )
    return DailyBriefLifecycleStatus(
        overall_status="ok",
        reason_code=STATUS_DELIVERED,
        detail="delivered_only",
        **common,
    )


_RECEIPT_SOURCES = (
    ("delivery", "daily_brief_delivery_receipts", "delivery_status", "output_path_redacted"),
    ("html_render", "daily_brief_html_render_receipts", "render_status", "html_path_redacted"),
    ("notification", "daily_brief_notification_receipts", "notify_status", None),
    ("open", "daily_brief_open_receipts", "open_status", "path_redacted"),
)


def list_brief_receipts(
    *, brief_date: str | None = None, limit: int = 50, db_path: str | None = None
) -> list[dict[str, Any]]:
    """Read-only metadata list of recent receipts across the four delivery ledgers (no raw content)."""
    conn = _conn(db_path)
    rows: list[dict[str, Any]] = []
    for surface, table, status_col, path_col in _RECEIPT_SOURCES:
        path_sel = path_col if path_col is not None else "NULL AS path_redacted"
        path_alias = "" if path_col is None else f"{path_col} AS path_redacted"
        select_path = path_alias or path_sel
        where = "WHERE brief_date = ?" if brief_date is not None else ""
        params: tuple[Any, ...] = (brief_date, limit) if brief_date is not None else (limit,)
        sql = (
            f"SELECT brief_date, brief_run_id, {status_col} AS status, reason_code, "
            f"{select_path}, created_utc FROM {table} {where} "
            f"ORDER BY created_utc DESC, rowid DESC LIMIT ?"
        )
        for row in conn.execute(sql, params).fetchall():
            d = dict(row)
            d["surface"] = surface
            rows.append(d)
    rows.sort(key=lambda r: str(r.get("created_utc") or ""), reverse=True)
    return rows[:limit]


def build_brief_open_proof() -> dict[str, Any]:
    """Deterministic proof (temp migrated DB) over all open + consolidated-status + receipts paths."""
    import sqlite3
    import tempfile
    from datetime import timedelta

    from hb_assistant.construction.store import ConstructionStore

    now = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

    def _insert_run(db: str, *, brief_run_id: str, status: str, generated_utc: str) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
                "VALUES (?, '2026-06-02', 'dry_run', ?, ?)",
                (brief_run_id, status, generated_utc),
            )
        conn.close()

    def _insert_delivery(db: str, *, brief_run_id: str) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                "INSERT INTO daily_brief_delivery_receipts (delivery_receipt_id, brief_run_id, "
                " brief_date, delivery_channel, delivery_status, mode, output_path_redacted) "
                "VALUES (?, ?, '2026-06-02', 'obsidian_vault', 'delivered', 'apply', "
                " '12_Daily_Brief/2026-06-02_daily_brief.md')",
                (uuid.uuid4().hex, brief_run_id),
            )
        conn.close()

    calls: list[str] = []

    def _fake_opener(path: str) -> bool:
        calls.append(path)
        return True

    with tempfile.TemporaryDirectory() as tmp:
        recent = (now - timedelta(hours=1)).isoformat()

        empty_db = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty_db)
        never_run = evaluate_brief_open(db_path=empty_db, now=now)
        status_never = evaluate_brief_delivery_status(db_path=empty_db, now=now)

        blocked_db = f"{tmp}/blocked.sqlite3"
        ConstructionStore(blocked_db)
        _insert_run(
            blocked_db, brief_run_id=uuid.uuid4().hex, status="blocked", generated_utc=recent
        )
        blocked = evaluate_brief_open(db_path=blocked_db, now=now)

        stale_db = f"{tmp}/stale.sqlite3"
        ConstructionStore(stale_db)
        _insert_run(
            stale_db,
            brief_run_id="run-stale",
            status="synthesized",
            generated_utc=(now - timedelta(hours=72)).isoformat(),
        )
        _insert_delivery(stale_db, brief_run_id="run-stale")
        stale = evaluate_brief_open(db_path=stale_db, now=now)

        # Not-available: delivered nothing yet.
        na_db = f"{tmp}/na.sqlite3"
        ConstructionStore(na_db)
        _insert_run(na_db, brief_run_id="run-na", status="synthesized", generated_utc=recent)
        not_available = evaluate_brief_open(db_path=na_db, now=now)
        status_not_delivered = evaluate_brief_delivery_status(db_path=na_db, now=now)

        # Eligible / completed / idempotent + consolidated status transitions.
        ok_db = f"{tmp}/ok.sqlite3"
        ConstructionStore(ok_db)
        _insert_run(ok_db, brief_run_id="run-ok", status="synthesized", generated_utc=recent)
        _insert_delivery(ok_db, brief_run_id="run-ok")
        status_delivered = evaluate_brief_delivery_status(db_path=ok_db, now=now)

        preview, _ = run_brief_open_agent(
            db_path=ok_db, mode="dry_run", now=now, opener=_fake_opener, policy_open=True
        )
        disabled, _ = run_brief_open_agent(
            db_path=ok_db, mode="apply", now=now, opener=_fake_opener, policy_open=False
        )
        calls_after_disabled = len(calls)
        completed, _ = run_brief_open_agent(
            db_path=ok_db, mode="apply", now=now, opener=_fake_opener, policy_open=True
        )
        idempotent, _ = run_brief_open_agent(
            db_path=ok_db, mode="apply", now=now, opener=_fake_opener, policy_open=True
        )
        receipts = list_brief_receipts(db_path=ok_db)
        status_complete_conn = sqlite3.connect(ok_db)
        with status_complete_conn:
            status_complete_conn.execute(
                "INSERT INTO daily_brief_html_render_receipts (html_render_receipt_id, brief_run_id, "
                " brief_date, render_status, mode) VALUES (?, 'run-ok','2026-06-02','rendered','apply')",
                (uuid.uuid4().hex,),
            )
            status_complete_conn.execute(
                "INSERT INTO daily_brief_notification_receipts (notification_receipt_id, brief_run_id, "
                " brief_date, channel, notify_status, mode) "
                "VALUES (?, 'run-ok','2026-06-02','local_macos','emitted','apply')",
                (uuid.uuid4().hex,),
            )
        status_complete_conn.close()
        status_complete = evaluate_brief_delivery_status(db_path=ok_db, now=now)

    blob = _values_only_blob(
        [
            never_run.model_dump(),
            blocked.model_dump(),
            stale.model_dump(),
            not_available.model_dump(),
            preview.model_dump(),
            disabled.model_dump(),
            completed.model_dump(),
            idempotent.model_dump(),
            status_complete.model_dump(),
            receipts,
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        never_run.reason_code == OPEN_NEVER_GENERATED
        and status_never.reason_code == STATUS_NEVER_GENERATED
        and blocked.reason_code == OPEN_BLOCKED
        and stale.reason_code == OPEN_STALE
        and not_available.reason_code == OPEN_NOT_AVAILABLE
        and status_not_delivered.reason_code == STATUS_NOT_DELIVERED
        and status_delivered.reason_code == STATUS_DELIVERED
        and preview.reason_code == OPEN_ELIGIBLE
        and preview.open_status == "preview"
        and disabled.reason_code == OPEN_DISABLED_BY_POLICY
        and calls_after_disabled == 0
        and completed.reason_code == OPEN_COMPLETED
        and completed.opened is True
        and idempotent.reason_code == OPEN_ALREADY_OPENED
        and status_complete.reason_code == STATUS_COMPLETE
        and len(receipts) >= 2
        and no_raw_content
    )
    return {
        "proof": "phase_08b_daily_brief_open",
        "proof_passed": proof_passed,
        "never_generated_reason_code": never_run.reason_code,
        "blocked_reason_code": blocked.reason_code,
        "stale_reason_code": stale.reason_code,
        "not_available_reason_code": not_available.reason_code,
        "eligible_reason_code": preview.reason_code,
        "disabled_reason_code": disabled.reason_code,
        "completed_reason_code": completed.reason_code,
        "already_opened_reason_code": idempotent.reason_code,
        "status_codes": [
            status_never.reason_code,
            status_not_delivered.reason_code,
            status_delivered.reason_code,
            status_complete.reason_code,
        ],
        "disabled_invoked_no_opener": calls_after_disabled == 0,
        "receipts_listed": len(receipts),
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "dry_run_default": True,
            "fail_closed_open": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
