"""Phase 08B Daily Brief Delivery Agent + local-only delivery orchestration (Prompt 09).

Takes an already-generated, approved brief (from the durable V26 ``daily_brief_runs`` ledger +
the V27 ``daily_brief_handoff_lines`` recovery table) and performs the **local-only** delivery to
the Obsidian vault — idempotently, dry-run by default. Generation, evaluation, and the morning
orchestrator are out of scope; this module is purely the delivery step.

The only delivery channel is the local Obsidian vault (the documented daily-brief target). There is
NO external delivery (no email/Slack/Teams/SMS/push/webhook/Graph ``sendMail``) — the V31
``daily_brief_delivery_receipts`` table hard-pins ``delivery_channel = 'obsidian_vault'`` at the DB
layer. Receipts are metadata-only (redacted vault path + content hash + structured reason code).

Reason codes: ``DELIVERY_NEVER_GENERATED`` (no brief for the date), ``DELIVERY_BLOCKED`` (the run
is blocked / degraded — never delivered), ``DELIVERY_STALE`` (the brief is older than
``max_age_hours`` — too old to deliver), ``DELIVERY_ELIGIBLE`` (ready; dry-run preview),
``DELIVERY_COMPLETED`` (apply wrote the vault note + delivery receipt), ``DELIVERY_ALREADY_DELIVERED``
(idempotent no-op — already delivered).

Apply writes the vault note (marker-bounded + atomic, via the existing ``write_brief_output``) and
records the delivery in V31 — that ledger is the delivery action's durable state and gives default
idempotency. The optional V28 agent-run receipt is emit-gated (off by default). Dry-run (default)
writes nothing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.models import HANDOFF_SECTIONS
from .daily_brief.output import write_brief_output
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
DELIVERY_NEVER_GENERATED = "DELIVERY_NEVER_GENERATED"
DELIVERY_BLOCKED = "DELIVERY_BLOCKED"
DELIVERY_STALE = "DELIVERY_STALE"
DELIVERY_ELIGIBLE = "DELIVERY_ELIGIBLE"
DELIVERY_COMPLETED = "DELIVERY_COMPLETED"
DELIVERY_ALREADY_DELIVERED = "DELIVERY_ALREADY_DELIVERED"

_DELIVERY_CHANNEL = "obsidian_vault"
_DEFAULT_MAX_AGE_HOURS = 36
_BLOCKED_STATUS = "blocked"

# Human-facing section headings for the rendered vault note (HANDOFF_SECTIONS order).
_SECTION_HEADINGS: dict[str, str] = {
    "priority_actions": "Priority Actions",
    "waiting_on": "Waiting On / Warnings",
    "meeting_prep": "Meeting Prep",
    "file_review_queue": "File Review Queue (mandatory review)",
    "project_signals": "Project Signals",
}


class DailyBriefDeliveryStatus(BaseModel):
    """Daily-brief delivery snapshot (metadata-only; redacted; no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    brief_date: str | None = None
    brief_run_id: str | None = None
    eligible: bool = False
    already_delivered: bool = False
    mode: str | None = None  # "dry_run" | "apply" (None for a pure evaluate)
    delivery_status: str | None = None  # "preview" | "delivered" | "already_delivered" | "skipped"
    written: bool = False
    delivery_channel: str = _DELIVERY_CHANNEL
    content_hash: str | None = None
    output_path_redacted: str | None = None
    output_path_hash: str | None = None
    delivered_utc: str | None = None
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

    @field_validator("detail", "degradation_mode", "output_path_redacted")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("daily-brief-delivery field must not carry raw/forbidden tokens")
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
    cfg = _safe_seed().get("daily_brief_delivery", {})
    return cfg if isinstance(cfg, dict) else {}


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
    """Pick the run to deliver: the latest matching ``brief_date``, or the latest overall."""
    if brief_date is not None:
        for run in runs:
            if str(run.get("brief_date")) == brief_date:
                return run
        return None
    return runs[0] if runs else None


def _prior_delivered(brief_run_id: str | None, brief_date: str | None, db_path: str | None) -> bool:
    """True when a V31 receipt already records a completed delivery for this brief."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    if brief_run_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_delivery_receipts "
            "WHERE delivery_status = 'delivered' AND brief_run_id = ?",
            (brief_run_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_delivery_receipts "
            "WHERE delivery_status = 'delivered' AND brief_date = ?",
            (brief_date,),
        ).fetchone()
    return bool(row and row[0])


def write_daily_brief_delivery_receipt(
    *,
    brief_date: str,
    delivery_status: str,
    reason_code: str,
    mode: str,
    brief_run_id: str | None = None,
    content_hash: str | None = None,
    output_path_redacted: str | None = None,
    output_path_hash: str | None = None,
    delivered_utc: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only V31 delivery receipt; returns ``delivery_receipt_id``.

    Local-only, additive. ``delivery_channel`` is fixed to ``obsidian_vault`` (DB CHECK enforces
    it); the no-raw / no-writeback guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V31 table exists (idempotent)
    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO daily_brief_delivery_receipts
                (delivery_receipt_id, brief_run_id, brief_date, delivery_channel, delivery_status,
                 reason_code, mode, content_hash, output_path_redacted, output_path_hash,
                 delivered_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                brief_run_id,
                brief_date,
                _DELIVERY_CHANNEL,
                delivery_status,
                reason_code,
                mode,
                content_hash,
                output_path_redacted,
                output_path_hash,
                delivered_utc,
            ),
        )
    return receipt_id


def _render_brief_markdown_from_handoff(payload: Any) -> str:
    """Render redacted, deterministic inner brief markdown from a durable handoff payload.

    Built from the structured V27 handoff sections (never from a model response). Mirrors the
    ``daily_brief/output.py`` line format; no raw content.
    """
    lines: list[str] = [
        f"# Daily Brief — {payload.brief_date}",
        "",
        (
            f"_Advisory only. review_tier={payload.review_tier}; "
            f"degradation={payload.degradation_mode}; "
            f"eligible_for_delivery={payload.eligible_for_delivery}. "
            "Tier-3 items are routed to mandatory review and never presented as fact._"
        ),
    ]
    for section in HANDOFF_SECTIONS:
        heading = _SECTION_HEADINGS.get(section, section.replace("_", " ").title())
        section_lines = payload.sections.get(section, [])
        lines += ["", f"## {heading}"]
        if section_lines:
            for item in section_lines:
                refs = " ".join(
                    f"{r.get('source_family', '')}:{r.get('source_ref', '')}"
                    for r in item.source_refs
                )
                suffix = f" (source: {refs})" if refs else ""
                lines.append(f"- [tier {item.review_tier}] {item.title_redacted}{suffix}")
        else:
            lines.append("_None._")
    return "\n".join(lines)


def evaluate_daily_brief_delivery(
    *, brief_date: str | None = None, db_path: str | None = None, now: datetime | None = None
) -> DailyBriefDeliveryStatus:
    """Read-only delivery eligibility for the latest (or ``brief_date``) brief. Writes nothing."""
    cfg = _cfg()
    max_age_hours = int(cfg.get("max_age_hours", _DEFAULT_MAX_AGE_HOURS))
    max_age_seconds = max_age_hours * 3600
    now = now or datetime.now(timezone.utc)
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
        return DailyBriefDeliveryStatus(
            overall_status="attention",
            reason_code=DELIVERY_NEVER_GENERATED,
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

    blocked = last_status == _BLOCKED_STATUS or str(degradation or "") == _BLOCKED_STATUS
    if blocked:
        return DailyBriefDeliveryStatus(
            overall_status="attention",
            reason_code=DELIVERY_BLOCKED,
            detail="brief_run_blocked_or_degraded",
            **common,
        )
    if age is not None and age > max_age_seconds:
        return DailyBriefDeliveryStatus(
            overall_status="attention",
            reason_code=DELIVERY_STALE,
            detail="brief_older_than_max_age",
            **common,
        )

    already = _prior_delivered(brief_run_id, run_brief_date, db_path)
    if already:
        return DailyBriefDeliveryStatus(
            overall_status="ok",
            reason_code=DELIVERY_ALREADY_DELIVERED,
            eligible=True,
            already_delivered=True,
            detail="already_delivered_to_vault",
            **common,
        )
    return DailyBriefDeliveryStatus(
        overall_status="ok",
        reason_code=DELIVERY_ELIGIBLE,
        eligible=True,
        detail="ready_for_local_delivery",
        **common,
    )


def run_daily_brief_delivery_agent(
    *,
    brief_date: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
    vault_brief_dir: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
) -> tuple[DailyBriefDeliveryStatus, str | None]:
    """Evaluate, then (apply, dry-run default) deliver the brief locally to the Obsidian vault.

    Dry-run writes nothing. Apply, when eligible, renders the redacted note from the durable
    handoff, writes it to the vault, and records a V31 delivery receipt (the delivery ledger).
    The optional V28 agent-run receipt is emit-gated. Returns ``(status, agent_run_id | None)``.
    """
    status = evaluate_daily_brief_delivery(brief_date=brief_date, db_path=db_path, now=now)
    dry_run = mode != "apply"
    status.mode = mode

    if dry_run:
        status.delivery_status = "preview"
    elif status.reason_code == DELIVERY_ELIGIBLE:
        payload = read_daily_brief_handoff(str(status.brief_run_id), db_path=db_path)
        if payload is None:  # pragma: no cover - defensive (run row without handoff)
            status.reason_code = DELIVERY_NEVER_GENERATED
            status.overall_status = "attention"
            status.delivery_status = "skipped"
            status.detail = "handoff_payload_missing"
        else:
            content = _render_brief_markdown_from_handoff(payload)
            result = write_brief_output(
                brief_date=str(status.brief_date),
                content=content,
                vault_brief_dir=vault_brief_dir,
                apply=True,
            )
            delivered = datetime.now(timezone.utc).isoformat()
            status.reason_code = DELIVERY_COMPLETED
            status.delivery_status = "delivered"
            status.written = True
            status.content_hash = result.content_hash
            status.output_path_redacted = result.output_path_redacted
            status.output_path_hash = result.output_path_hash
            status.delivered_utc = delivered
            status.detail = "delivered_to_vault"
            write_daily_brief_delivery_receipt(
                brief_date=str(status.brief_date),
                brief_run_id=status.brief_run_id,
                delivery_status="delivered",
                reason_code=DELIVERY_COMPLETED,
                mode="apply",
                content_hash=result.content_hash,
                output_path_redacted=result.output_path_redacted,
                output_path_hash=result.output_path_hash,
                delivered_utc=delivered,
                db_path=db_path,
            )
    elif status.reason_code == DELIVERY_ALREADY_DELIVERED:
        status.delivery_status = "already_delivered"
    else:
        # Blocked / stale / never-generated: refuse to deliver.
        status.delivery_status = "skipped"

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="daily_brief_delivery_agent",
            run_kind="daily_brief_delivery",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


def build_daily_brief_delivery_proof() -> dict[str, Any]:
    """Deterministic proof for ``daily-brief-delivery-proof.json`` (temp migrated DB + temp vault).

    Exercises never-generated, blocked, stale, eligible (dry-run), completed (apply), and the
    idempotent already-delivered path; asserts dry-run writes nothing and no raw content leaks.
    """
    import sqlite3
    import tempfile
    from datetime import timedelta

    from hb_assistant.construction.store import ConstructionStore

    now = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

    def _insert_run(
        db: str,
        *,
        brief_run_id: str,
        status: str,
        generated_utc: str,
        with_handoff: bool = True,
    ) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                """
                INSERT INTO daily_brief_runs
                    (brief_run_id, brief_date, mode, status, generated_utc)
                VALUES (?, '2026-06-02', 'dry_run', ?, ?)
                """,
                (brief_run_id, status, generated_utc),
            )
            if with_handoff:
                conn.execute(
                    """
                    INSERT INTO daily_brief_handoff_lines
                        (line_id, brief_run_id, section, line_index, title_redacted, review_tier,
                         source_refs_json, generated_utc)
                    VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI response', 2, '[]', ?)
                    """,
                    (uuid.uuid4().hex, brief_run_id, generated_utc),
                )
        conn.close()

    with tempfile.TemporaryDirectory() as tmp:
        recent = (now - timedelta(hours=1)).isoformat()

        empty_db = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty_db)
        never_run = evaluate_daily_brief_delivery(db_path=empty_db, now=now)

        blocked_db = f"{tmp}/blocked.sqlite3"
        ConstructionStore(blocked_db)
        _insert_run(
            blocked_db, brief_run_id=uuid.uuid4().hex, status="blocked", generated_utc=recent
        )
        blocked = evaluate_daily_brief_delivery(db_path=blocked_db, now=now)

        stale_db = f"{tmp}/stale.sqlite3"
        ConstructionStore(stale_db)
        _insert_run(
            stale_db,
            brief_run_id=uuid.uuid4().hex,
            status="synthesized",
            generated_utc=(now - timedelta(hours=72)).isoformat(),
        )
        stale = evaluate_daily_brief_delivery(db_path=stale_db, now=now)

        # Eligible / completed / idempotent — one DB + a temp vault dir (never the real vault).
        ok_db = f"{tmp}/ok.sqlite3"
        vault_dir = f"{tmp}/vault_brief"
        ConstructionStore(ok_db)
        _insert_run(ok_db, brief_run_id="run-ok-1", status="synthesized", generated_utc=recent)

        preview = evaluate_daily_brief_delivery(db_path=ok_db, now=now)
        dry, _ = run_daily_brief_delivery_agent(
            db_path=ok_db, vault_brief_dir=vault_dir, mode="dry_run", now=now
        )
        wrote_in_dry_run = Path(vault_dir).exists()

        completed, _ = run_daily_brief_delivery_agent(
            db_path=ok_db, vault_brief_dir=vault_dir, mode="apply", now=now
        )
        delivered_file_exists = (Path(vault_dir) / "2026-06-02_daily_brief.md").exists()
        idempotent, _ = run_daily_brief_delivery_agent(
            db_path=ok_db, vault_brief_dir=vault_dir, mode="apply", now=now
        )

    blob = _values_only_blob(
        [
            never_run.model_dump(),
            blocked.model_dump(),
            stale.model_dump(),
            preview.model_dump(),
            dry.model_dump(),
            completed.model_dump(),
            idempotent.model_dump(),
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        never_run.reason_code == DELIVERY_NEVER_GENERATED
        and blocked.reason_code == DELIVERY_BLOCKED
        and stale.reason_code == DELIVERY_STALE
        and preview.reason_code == DELIVERY_ELIGIBLE
        and dry.delivery_status == "preview"
        and dry.written is False
        and not wrote_in_dry_run
        and completed.reason_code == DELIVERY_COMPLETED
        and completed.written is True
        and delivered_file_exists
        and idempotent.reason_code == DELIVERY_ALREADY_DELIVERED
        and no_raw_content
    )
    return {
        "proof": "phase_08b_daily_brief_delivery",
        "proof_passed": proof_passed,
        "never_generated_reason_code": never_run.reason_code,
        "blocked_reason_code": blocked.reason_code,
        "stale_reason_code": stale.reason_code,
        "eligible_reason_code": preview.reason_code,
        "completed_reason_code": completed.reason_code,
        "already_delivered_reason_code": idempotent.reason_code,
        "dry_run_wrote_nothing": not wrote_in_dry_run,
        "no_raw_content": no_raw_content,
        "delivery_channel": _DELIVERY_CHANNEL,
        "guardrails": {
            "local_first": True,
            "dry_run_default": True,
            "deterministic": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
