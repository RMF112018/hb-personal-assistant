"""Phase 08B source / runtime / retrieval freshness observability (Prompt 07).

A deterministic, read-only observability surface with three sub-evaluators, each reporting
structured reason codes:

1. **Source freshness** — the latest "last successful sync" watermark per ingestion domain
   (Graph drive / mail / calendar, Procore) vs ``source_max_age_hours``.
2. **Runtime health** — COMPOSES the existing automation-health agent (path / store / schema /
   handoff); it does not re-implement those checks.
3. **Retrieval freshness** — the Obsidian index manifest age + whether notes were modified after
   the last index, and the latest retrieval receipt + its stale-unknown count vs
   ``retrieval_max_age_hours``.

Pure observability: the ONLY apply-capable path is the emit-gated V28 agent-run receipt (off by
default). Read-only SELECTs, table-existence guarded; no external writeback, delivery, or raw
content. Thresholds + reason codes come from the Phase 08B automation policy seed ``freshness``
section.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_health import evaluate_automation_health
from .automation_policy import load_phase_08b_automation_policy_seed

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
SOURCE_FRESH = "SOURCE_FRESH"
SOURCE_STALE = "SOURCE_STALE"
SOURCE_FRESHNESS_UNKNOWN = "SOURCE_FRESHNESS_UNKNOWN"
RETRIEVAL_FRESH = "RETRIEVAL_FRESH"
RETRIEVAL_STALE = "RETRIEVAL_STALE"
RETRIEVAL_INDEX_MISSING = "RETRIEVAL_INDEX_MISSING"
RUNTIME_HEALTH_OK = "RUNTIME_HEALTH_OK"
RUNTIME_HEALTH_DEGRADED = "RUNTIME_HEALTH_DEGRADED"
OBSERVABILITY_OK = "OBSERVABILITY_OK"
OBSERVABILITY_DEGRADED = "OBSERVABILITY_DEGRADED"

_DEFAULT_SOURCE_MAX_AGE_HOURS = 48
_DEFAULT_RETRIEVAL_MAX_AGE_HOURS = 168

# (domain label, table, freshness column) — the latest successful-sync watermark per domain.
_SOURCE_WATERMARKS: tuple[tuple[str, str, str], ...] = (
    ("graph_drive", "construction_source_sync_state", "last_successful_sync_utc"),
    ("graph_mail", "email_sync_state", "last_successful_sync_utc"),
    ("graph_calendar", "calendar_sync_state", "last_successful_sync_utc"),
    ("procore", "procore_live_sync_watermarks", "last_success_at_utc"),
)


# --------------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------------
class FreshnessSignal(BaseModel):
    """One deterministic freshness signal (metadata-only; no raw content)."""

    name: str
    domain: str
    status: str  # "fresh" | "stale" | "unknown"
    reason_code: str
    last_event_utc: str | None = None
    age_seconds: int | None = None
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("freshness detail must not carry raw/forbidden tokens")
        return value


class FreshnessGroupStatus(BaseModel):
    """Overall status for a freshness sub-evaluator (source or retrieval)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    signals: list[FreshnessSignal] = []
    stale_count: int = 0
    unknown_count: int = 0

    model_config = {"extra": "forbid"}


class RuntimeHealthStatus(BaseModel):
    """Compact runtime-health summary composed from the automation-health agent."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    degraded_checks: list[str] = []

    model_config = {"extra": "forbid"}


class ObservabilitySnapshot(BaseModel):
    """Combined source / runtime / retrieval observability snapshot (no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    source: FreshnessGroupStatus
    runtime: RuntimeHealthStatus
    retrieval: FreshnessGroupStatus
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""

    model_config = {"extra": "forbid"}


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _freshness_cfg() -> dict[str, Any]:
    cfg = _safe_seed().get("freshness", {})
    return cfg if isinstance(cfg, dict) else {}


def _conn(db_path: str | None) -> Any:
    return get_connection(Path(db_path) if db_path is not None else None)


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


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


def _max_timestamp(conn: Any, table: str, column: str) -> str | None:
    if not _table_exists(conn, table):
        return None
    try:
        row = conn.execute(
            f"SELECT MAX({column}) FROM {table} WHERE {column} IS NOT NULL"
        ).fetchone()
    except Exception:  # pragma: no cover - defensive
        return None
    return row[0] if row and row[0] else None


def _age_signal(
    *,
    name: str,
    domain: str,
    last_event_utc: str | None,
    now: datetime,
    max_age_seconds: int,
    fresh_code: str,
    stale_code: str,
    unknown_code: str,
) -> FreshnessSignal:
    parsed = _parse_utc(last_event_utc)
    if parsed is None:
        return FreshnessSignal(
            name=name,
            domain=domain,
            status="unknown",
            reason_code=unknown_code,
            detail="no_successful_sync_recorded",
        )
    age = int((now.astimezone(timezone.utc) - parsed).total_seconds())
    if age > max_age_seconds:
        return FreshnessSignal(
            name=name,
            domain=domain,
            status="stale",
            reason_code=stale_code,
            last_event_utc=last_event_utc,
            age_seconds=age,
            detail="age_exceeds_threshold",
        )
    return FreshnessSignal(
        name=name,
        domain=domain,
        status="fresh",
        reason_code=fresh_code,
        last_event_utc=last_event_utc,
        age_seconds=age,
        detail="within_threshold",
    )


def _group(signals: list[FreshnessSignal]) -> tuple[str, int, int]:
    stale = sum(1 for s in signals if s.status == "stale")
    unknown = sum(1 for s in signals if s.status == "unknown")
    overall = "ok" if stale == 0 else "attention"
    return overall, stale, unknown


# --------------------------------------------------------------------------------------------
# Source freshness
# --------------------------------------------------------------------------------------------
def evaluate_source_freshness(
    *, db_path: str | None = None, now: datetime | None = None
) -> FreshnessGroupStatus:
    """Read-only per-domain source freshness (latest successful-sync watermark vs threshold)."""
    cfg = _freshness_cfg()
    max_age_hours = int(cfg.get("source_max_age_hours", _DEFAULT_SOURCE_MAX_AGE_HOURS))
    max_age_seconds = max_age_hours * 3600
    now = now or datetime.now(timezone.utc)
    conn = _conn(_resolved_db(db_path))

    signals: list[FreshnessSignal] = []
    for domain, table, column in _SOURCE_WATERMARKS:
        latest = _max_timestamp(conn, table, column)
        signals.append(
            _age_signal(
                name=domain,
                domain=domain,
                last_event_utc=latest,
                now=now,
                max_age_seconds=max_age_seconds,
                fresh_code=str(cfg.get("source_fresh_reason_code", SOURCE_FRESH)),
                stale_code=str(cfg.get("source_stale_reason_code", SOURCE_STALE)),
                unknown_code=str(cfg.get("source_unknown_reason_code", SOURCE_FRESHNESS_UNKNOWN)),
            )
        )

    overall, stale, unknown = _group(signals)
    reason = (
        SOURCE_STALE
        if stale
        else (SOURCE_FRESHNESS_UNKNOWN if unknown == len(signals) else SOURCE_FRESH)
    )
    return FreshnessGroupStatus(
        overall_status=overall,
        reason_code=reason,
        signals=signals,
        stale_count=stale,
        unknown_count=unknown,
    )


# --------------------------------------------------------------------------------------------
# Retrieval freshness
# --------------------------------------------------------------------------------------------
def evaluate_retrieval_freshness(
    *, db_path: str | None = None, now: datetime | None = None
) -> FreshnessGroupStatus:
    """Read-only retrieval freshness: index age + notes-changed-since-index + retrieval recency."""
    cfg = _freshness_cfg()
    max_age_hours = int(cfg.get("retrieval_max_age_hours", _DEFAULT_RETRIEVAL_MAX_AGE_HOURS))
    max_age_seconds = max_age_hours * 3600
    now = now or datetime.now(timezone.utc)
    conn = _conn(_resolved_db(db_path))

    fresh_code = str(cfg.get("retrieval_fresh_reason_code", RETRIEVAL_FRESH))
    stale_code = str(cfg.get("retrieval_stale_reason_code", RETRIEVAL_STALE))
    missing_code = str(cfg.get("index_missing_reason_code", RETRIEVAL_INDEX_MISSING))

    signals: list[FreshnessSignal] = []

    # Obsidian index manifest.
    manifest_utc = _max_timestamp(conn, "obsidian_index_manifests", "generated_utc")
    if manifest_utc is None:
        signals.append(
            FreshnessSignal(
                name="obsidian_index",
                domain="retrieval",
                status="unknown",
                reason_code=missing_code,
                detail="no_index_manifest",
            )
        )
    else:
        notes_utc = _max_timestamp(conn, "obsidian_index_entries", "modified_utc")
        manifest_dt = _parse_utc(manifest_utc)
        notes_dt = _parse_utc(notes_utc)
        age = (
            int((now.astimezone(timezone.utc) - manifest_dt).total_seconds())
            if manifest_dt
            else None
        )
        notes_changed = bool(manifest_dt and notes_dt and notes_dt > manifest_dt)
        too_old = bool(age is not None and age > max_age_seconds)
        if notes_changed or too_old:
            signals.append(
                FreshnessSignal(
                    name="obsidian_index",
                    domain="retrieval",
                    status="stale",
                    reason_code=stale_code,
                    last_event_utc=manifest_utc,
                    age_seconds=age,
                    detail="notes_modified_after_index"
                    if notes_changed
                    else "index_age_exceeds_threshold",
                )
            )
        else:
            signals.append(
                FreshnessSignal(
                    name="obsidian_index",
                    domain="retrieval",
                    status="fresh",
                    reason_code=fresh_code,
                    last_event_utc=manifest_utc,
                    age_seconds=age,
                    detail="index_current",
                )
            )

    # Latest retrieval query receipt + its stale-unknown count.
    retrieval_utc = _max_timestamp(conn, "retrieval_query_receipts", "created_utc")
    if retrieval_utc is None:
        signals.append(
            FreshnessSignal(
                name="retrieval_query",
                domain="retrieval",
                status="unknown",
                reason_code=missing_code,
                detail="no_retrieval_receipts",
            )
        )
    else:
        stale_unknown = 0
        try:
            row = conn.execute(
                "SELECT stale_unknown_count FROM retrieval_query_receipts "
                "ORDER BY created_utc DESC, retrieval_receipt_id DESC LIMIT 1"
            ).fetchone()
            stale_unknown = int(row[0]) if row and row[0] is not None else 0
        except Exception:  # pragma: no cover - defensive
            stale_unknown = 0
        rdt = _parse_utc(retrieval_utc)
        age = int((now.astimezone(timezone.utc) - rdt).total_seconds()) if rdt else None
        too_old = bool(age is not None and age > max_age_seconds)
        if stale_unknown > 0 or too_old:
            signals.append(
                FreshnessSignal(
                    name="retrieval_query",
                    domain="retrieval",
                    status="stale",
                    reason_code=stale_code,
                    last_event_utc=retrieval_utc,
                    age_seconds=age,
                    detail="stale_unknown_refs_present"
                    if stale_unknown > 0
                    else "retrieval_age_exceeds_threshold",
                )
            )
        else:
            signals.append(
                FreshnessSignal(
                    name="retrieval_query",
                    domain="retrieval",
                    status="fresh",
                    reason_code=fresh_code,
                    last_event_utc=retrieval_utc,
                    age_seconds=age,
                    detail="recent_retrieval",
                )
            )

    overall, stale, unknown = _group(signals)
    if stale:
        reason = stale_code
    elif unknown == len(signals):
        reason = missing_code
    else:
        reason = fresh_code
    return FreshnessGroupStatus(
        overall_status=overall,
        reason_code=reason,
        signals=signals,
        stale_count=stale,
        unknown_count=unknown,
    )


# --------------------------------------------------------------------------------------------
# Runtime health (composes the automation-health agent)
# --------------------------------------------------------------------------------------------
def evaluate_runtime_health(*, db_path: str | None = None) -> RuntimeHealthStatus:
    """Compact runtime-health summary composed from the existing automation-health agent."""
    health = evaluate_automation_health(db_path=db_path)
    ok = health.overall_status == "ok"
    return RuntimeHealthStatus(
        overall_status="ok" if ok else "attention",
        reason_code=RUNTIME_HEALTH_OK if ok else RUNTIME_HEALTH_DEGRADED,
        degraded_checks=list(health.degraded_checks),
    )


# --------------------------------------------------------------------------------------------
# Combined snapshot + emit-gated receipt
# --------------------------------------------------------------------------------------------
def evaluate_observability(
    *, db_path: str | None = None, now: datetime | None = None
) -> ObservabilitySnapshot:
    """Combine source + runtime + retrieval observability (read-only)."""
    generated = datetime.now(timezone.utc).isoformat()
    source = evaluate_source_freshness(db_path=db_path, now=now)
    runtime = evaluate_runtime_health(db_path=db_path)
    retrieval = evaluate_retrieval_freshness(db_path=db_path, now=now)

    all_ok = (
        source.overall_status == "ok"
        and runtime.overall_status == "ok"
        and retrieval.overall_status == "ok"
    )
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    return ObservabilitySnapshot(
        overall_status="ok" if all_ok else "attention",
        reason_code=OBSERVABILITY_OK if all_ok else OBSERVABILITY_DEGRADED,
        source=source,
        runtime=runtime,
        retrieval=retrieval,
        policy_version=str(seed.get("version", "unknown")),
        schema_version=schema_version,
        generated_utc=generated,
    )


def run_observability(
    *, db_path: str | None = None, now: datetime | None = None, emit_receipt: bool = False
) -> tuple[ObservabilitySnapshot, str | None]:
    """Evaluate observability (read-only); when ``emit_receipt``, persist a metadata-only V28 receipt."""
    snapshot = evaluate_observability(db_path=db_path, now=now)
    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="freshness_observability_agent",
            run_kind="freshness_observability",
            status=snapshot.overall_status,
            reason_code=snapshot.reason_code,
            started_utc=snapshot.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return snapshot, agent_run_id


# --------------------------------------------------------------------------------------------
# Proof
# --------------------------------------------------------------------------------------------
def build_freshness_observability_proof() -> dict[str, Any]:
    """Deterministic proof for ``freshness-observability-proof.json`` (temp migrated DB)."""
    import json
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/observability.sqlite3"
        ConstructionStore(db)  # migrate to LATEST (empty source/index tables)
        now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

        # Empty DB: sources all unknown, retrieval index missing, runtime healthy.
        empty = evaluate_observability(db_path=db, now=now)

        # Seed a FRESH drive watermark + a STALE mail watermark to exercise both transitions.
        conn = get_connection(Path(db))
        fresh_ts = (now - timedelta(hours=1)).isoformat()
        stale_ts = (now - timedelta(hours=240)).isoformat()
        with conn:
            conn.execute(
                "INSERT INTO construction_source_locations "
                "(source_id, source_system, source_scope, source_name) "
                "VALUES ('s-drive','sharepoint','project','Drive X')"
            )
            conn.execute(
                "INSERT INTO construction_source_sync_state (source_id, last_successful_sync_utc, sync_status) "
                "VALUES ('s-drive', ?, 'ok')",
                (fresh_ts,),
            )
            conn.execute(
                "INSERT INTO email_source_locations (source_id, mailbox_owner_hash, folder_role) "
                "VALUES ('s-mail','hash1','inbox')"
            )
            conn.execute(
                "INSERT INTO email_sync_state (source_id, folder_id, sync_mode, last_successful_sync_utc) "
                "VALUES ('s-mail','f1','delta', ?)",
                (stale_ts,),
            )
        seeded_source = evaluate_source_freshness(db_path=db, now=now)
        seeded_obs = evaluate_observability(db_path=db, now=now)

    by_domain = {s.domain: s for s in seeded_source.signals}
    drive_fresh = by_domain.get("graph_drive")
    mail_stale = by_domain.get("graph_mail")

    blob = json.dumps(
        [empty.model_dump(), seeded_source.model_dump(), seeded_obs.model_dump()], default=str
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        # Empty fresh install: nothing stale -> OK; unknown sources + missing index reported.
        empty.reason_code == OBSERVABILITY_OK
        and empty.runtime.reason_code == RUNTIME_HEALTH_OK
        and empty.retrieval.reason_code == RETRIEVAL_INDEX_MISSING
        and empty.source.reason_code == SOURCE_FRESHNESS_UNKNOWN
        # Seeded: a fresh drive watermark + a stale mail watermark drive the transitions.
        and drive_fresh is not None
        and drive_fresh.reason_code == SOURCE_FRESH
        and mail_stale is not None
        and mail_stale.reason_code == SOURCE_STALE
        and seeded_source.stale_count == 1
        # A stale source degrades the combined snapshot.
        and seeded_obs.reason_code == OBSERVABILITY_DEGRADED
        and seeded_obs.overall_status == "attention"
        and no_raw_content
    )
    return {
        "proof": "phase_08b_freshness_observability",
        "proof_passed": proof_passed,
        "empty_reason_code": empty.reason_code,
        "runtime_reason_code": empty.runtime.reason_code,
        "retrieval_reason_code": empty.retrieval.reason_code,
        "source_fresh_reason_code": drive_fresh.reason_code if drive_fresh else None,
        "source_stale_reason_code": mail_stale.reason_code if mail_stale else None,
        "degraded_reason_code": seeded_obs.reason_code,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "deterministic": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
