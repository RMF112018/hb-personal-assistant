"""Phase 10 Prompt 05 — AI job queue enqueue + run lifecycle (local-only, advisory).

Closes the lifecycle Prompt 04 deferred: **enqueue → claim → run → receipt** over the V41
``ai_job_queue`` / ``ai_job_runs`` tables, with:

- **Idempotent enqueue** keyed by ``(environment, job_type, idempotency_key)``.
- **No-overlap (single-flight)** execution via the existing
  ``construction/second_brain/run_registry`` atomic file lock (``max_concurrent_jobs = 1``).
- **Retry / backoff** — a failed job is returned to ``queued`` (bumping ``retry_count``) until it
  reaches ``max_retries`` attempts, then ``failed``; re-claim is suppressed until
  ``retry_backoff_seconds`` have elapsed since the job's latest run (computed from ``ai_job_runs``
  history — no schema change).
- **Dry-run default** — claim + simulate with **zero writes** (no queue mutation, no run row, no
  receipt); ``--apply`` performs the writes.
- **Environment isolation** — every row is keyed by ``environment``; the lock is named per env.

The per-job work for Prompt 05 drives the Prompt 04 :class:`StructuredOutputClient` over the bundled
``tests/fixtures/local_ai/*`` (real raw-content extraction at scale is Prompt 06+). Each model call
validates against :class:`ActionCandidate` and leaves a hash-only ``local_model_run_receipts`` row.

No Graph/Procore/email/calendar writeback; no raw prompt/response/body/URL/token/path persisted.

Public entry points:
    enqueue_ai_job_request(*, store, job_type, environment, ...) -> dict
    run_ai_jobs(*, store, environment, max_items, dry_run, ...) -> dict
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.second_brain.run_registry import (
    acquire_run_lock,
    release_run_lock,
)

from .contracts import load_ai_job_policy, load_phase_10_contract
from .models import ActionCandidate, AiJobPolicy, LocalModelProfiles
from .structured_output import (
    GenerationBackend,
    StaticOutputClient,
    StructuredOutputClient,
    action_candidate_dict_from_fixture,
)

_DEFAULT_FIXTURES_DIR = "tests/fixtures/local_ai"
_LOCK_RUN_KIND = "ai_jobs_run"
_DEFAULT_PROFILE_ID = "default_extract"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_job_types() -> set[str]:
    """Job types allowed by the published Phase 10 AI-job contract (fail-open to a safe default)."""
    try:
        contract = load_phase_10_contract("ai_job_contract")
        jt = contract.get("job_types")
        if isinstance(jt, list) and jt:
            return {str(x) for x in jt}
    except Exception:  # pragma: no cover - defensive
        pass
    return {"extract_email_tasks"}


def _default_idempotency_key(job_type: str, source_watermark: Optional[str], now: str) -> str:
    day = now[:10] if now else ""
    raw = f"{job_type}|{source_watermark or 'none'}|{day}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def enqueue_ai_job_request(
    *,
    store: Any,
    job_type: str,
    environment: str = "dev",
    idempotency_key: Optional[str] = None,
    priority: int = 100,
    source_watermark: Optional[str] = None,
    payload_json: str = "{}",
    dry_run: bool = True,
    policy: Optional[AiJobPolicy] = None,
    now: Optional[str] = None,
) -> dict[str, Any]:
    """Validate + idempotently enqueue one AI job (dry-run previews; ``apply`` writes)."""
    policy = policy or load_ai_job_policy()
    now_s = now or _now()
    if job_type not in _valid_job_types():
        return {
            "status": "blocked",
            "ok": False,
            "blockers": ["invalid_job_type"],
            "job_type": job_type,
            "environment": environment,
        }
    key = idempotency_key or _default_idempotency_key(job_type, source_watermark, now_s)
    max_retries = policy.defaults.max_retries
    would_row = {
        "environment": environment,
        "job_type": job_type,
        "idempotency_key": key,
        "priority": int(priority),
        "source_watermark": source_watermark,
        "status": "queued",
        "max_retries": max_retries,
    }
    if dry_run:
        return {
            "status": "preview",
            "ok": True,
            "dry_run": True,
            "enqueued": False,
            "would_enqueue": would_row,
            "guardrails": {"local_only": True, "advisory_only": True, "dry_run_zero_writes": True},
        }
    job_id = uuid.uuid4().hex
    created = store.enqueue_ai_job(
        job_id=job_id,
        environment=environment,
        job_type=job_type,
        idempotency_key=key,
        priority=int(priority),
        source_watermark=source_watermark,
        payload_json=payload_json,
        max_retries=max_retries,
    )
    return {
        "status": "enqueued" if created else "exists",
        "ok": True,
        "dry_run": False,
        "enqueued": created,
        "job_id": job_id if created else None,
        "idempotency_key": key,
        "environment": environment,
        "job_type": job_type,
        "guardrails": {"local_only": True, "advisory_only": True, "idempotent": True},
    }


def _resolve_profile(profiles: LocalModelProfiles, profile_id: Optional[str]):
    pid = profile_id or _DEFAULT_PROFILE_ID
    prof = next((p for p in profiles.profiles if p.profile_id == pid), None)
    if prof is None:
        prof = next((p for p in profiles.profiles if p.profile_id == _DEFAULT_PROFILE_ID), None)
    return prof


def _job_profile_id(policy: AiJobPolicy, job_type: str) -> Optional[str]:
    jt = policy.job_types.get(job_type)
    return jt.profile_id if jt else None


def _load_fixtures(fixtures_dir: str, limit: int) -> list[dict[str, Any]]:
    base = Path(fixtures_dir)
    out: list[dict[str, Any]] = []
    for fp in sorted(base.glob("*.json"))[: max(0, int(limit))]:
        try:
            out.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _run_one_job(
    *,
    store: Any,
    job: dict[str, Any],
    profiles: LocalModelProfiles,
    policy: AiJobPolicy,
    fixtures_dir: str,
    backend: Optional[GenerationBackend],
    dry_run: bool,
    now: Optional[str],
) -> dict[str, Any]:
    job_id = job["job_id"]
    job_type = job["job_type"]
    profile = _resolve_profile(profiles, _job_profile_id(policy, job_type))
    if profile is None:
        return {"job_id": job_id, "outcome": "blocked", "blockers": ["no_profile_resolved"]}

    run_id = uuid.uuid4().hex
    if not dry_run:
        store.mark_ai_job_running(job_id=job_id, now=now)
        store.insert_ai_job_run(
            run_id=run_id,
            job_id=job_id,
            run_kind=job_type,
            status="running",
            dry_run=False,
            profile_id=profile.profile_id,
            started_utc=now,
        )

    produced = valid = rejected = 0
    backend_failed = False
    err_redacted: Optional[str] = None
    if job_type == "extract_email_tasks":
        # Prompt 07: the real deterministic-signal extractor over email thread summaries.
        # Lazy import avoids any package-init ordering surprise (ai_jobs is imported first).
        from .email_task_extraction import extract_email_task_candidates

        report = extract_email_task_candidates(
            store=store,
            profile_id=profile.profile_id,
            profiles=profiles,
            backend=backend,
            dry_run=dry_run,
            max_items=policy.defaults.max_items_per_run,
            mode="metadata_safe",
        )
        produced = int(report["produced"])
        valid = int(report["accepted"])
        rejected = int(report["rejected"])
        backend_failed = bool(report["backend_unavailable"])
        err_redacted = report["error_redacted"]
    else:
        client = StructuredOutputClient()
        fixtures = _load_fixtures(fixtures_dir, policy.defaults.max_items_per_run)
        for fixture in fixtures:
            candidate = action_candidate_dict_from_fixture(fixture)
            b = backend if backend is not None else StaticOutputClient(json.dumps(candidate))
            result = client.run(
                schema=ActionCandidate,
                profile=profile,
                profiles=profiles,
                system="ai-jobs structured extraction",
                prompt="extract action candidate",
                input_context=json.dumps(fixture.get("input_redacted", {}), sort_keys=True),
                task_type=job_type,
                backend=b,
                store=None if dry_run else store,
                dry_run=dry_run,
            )
            produced += 1
            if result.schema_valid:
                valid += 1
            elif result.status in {"unavailable", "timeout", "failed"}:
                backend_failed = True
                err_redacted = result.error_redacted or result.status
            else:
                rejected += 1

    # A job fails if the backend was unavailable, or it produced items but none validated.
    job_failed = backend_failed or (produced > 0 and valid == 0)

    if dry_run:
        return {
            "job_id": job_id,
            "job_type": job_type,
            "outcome": "would_fail" if job_failed else "would_succeed",
            "produced": produced,
            "schema_valid": valid,
            "rejected": rejected,
        }

    if job_failed:
        store.complete_ai_job_run(
            run_id=run_id,
            status="failed",
            candidate_count=produced,
            accepted_count=0,
            rejected_count=rejected,
            warning_count=0,
            blockers_json=json.dumps([err_redacted or "job_failed"]),
            finished_utc=now,
        )
        next_attempt = int(job.get("retry_count", 0)) + 1
        max_retries = int(job.get("max_retries", policy.defaults.max_retries))
        if next_attempt >= max_retries:
            store.complete_ai_job(
                job_id=job_id,
                status="failed",
                error_redacted=err_redacted or "job_failed",
                increment_retry=True,
                now=now,
            )
            outcome = "failed"
        else:
            store.complete_ai_job(
                job_id=job_id,
                status="queued",
                error_redacted=err_redacted or "job_failed",
                increment_retry=True,
                now=now,
            )
            outcome = "retry_scheduled"
    else:
        store.complete_ai_job_run(
            run_id=run_id,
            status="succeeded",
            candidate_count=produced,
            accepted_count=0,
            rejected_count=rejected,
            warning_count=0,
            blockers_json="[]",
            finished_utc=now,
        )
        store.complete_ai_job(job_id=job_id, status="succeeded", now=now)
        outcome = "succeeded"

    return {
        "job_id": job_id,
        "job_type": job_type,
        "run_id": run_id,
        "outcome": outcome,
        "produced": produced,
        "schema_valid": valid,
        "rejected": rejected,
        "error_redacted": err_redacted,
    }


def run_ai_jobs(
    *,
    store: Any,
    environment: str = "dev",
    max_items: int = 10,
    dry_run: bool = True,
    profiles: Optional[LocalModelProfiles] = None,
    policy: Optional[AiJobPolicy] = None,
    fixtures_dir: str = _DEFAULT_FIXTURES_DIR,
    backend: Optional[GenerationBackend] = None,
    locks_dir: Optional[str] = None,
    stale_lock_seconds: int = 300,
    now: Optional[str] = None,
) -> dict[str, Any]:
    """Claim + run eligible queued jobs under a no-overlap lock; retry/backoff on failure.

    Dry-run (default) claims and simulates with zero writes. ``backend`` (a GenerationBackend) is
    injected for tests/offline; omitted, each job uses a deterministic fixture-backed backend.
    """
    from .contracts import load_local_model_profiles  # local import; avoids import cycles

    profiles = profiles or load_local_model_profiles()
    policy = policy or load_ai_job_policy()
    backoff = policy.defaults.retry_backoff_seconds
    lock_name = f"ai_jobs_{environment}"

    lock = acquire_run_lock(
        run_kind=_LOCK_RUN_KIND,
        lock_name=lock_name,
        locks_dir=locks_dir,
        stale_lock_seconds=stale_lock_seconds,
        now=_parse_now(now),
        dry_run=dry_run,
    )
    if lock.status == "blocked":
        return {
            "status": "blocked",
            "ok": False,
            "dry_run": dry_run,
            "environment": environment,
            "blockers": ["run_overlap_blocked"],
            "lock_status": lock.status,
        }

    token = lock.token
    try:
        claimed = store.claim_eligible_ai_jobs(
            environment=environment,
            limit=max_items,
            backoff_seconds=backoff,
            now=now,
        )
        results = [
            _run_one_job(
                store=store,
                job=job,
                profiles=profiles,
                policy=policy,
                fixtures_dir=fixtures_dir,
                backend=backend,
                dry_run=dry_run,
                now=now,
            )
            for job in claimed
        ]
        succeeded = sum(1 for r in results if r.get("outcome") in {"succeeded", "would_succeed"})
        retried = sum(1 for r in results if r.get("outcome") == "retry_scheduled")
        failed = sum(1 for r in results if r.get("outcome") in {"failed", "would_fail"})
        return {
            "status": "ok",
            "ok": True,
            "dry_run": dry_run,
            "environment": environment,
            "lock_status": lock.status,
            "max_concurrent_jobs": policy.defaults.max_concurrent_jobs,
            "retry_backoff_seconds": backoff,
            "claimed": len(claimed),
            "succeeded": succeeded,
            "retry_scheduled": retried,
            "failed": failed,
            "results": results,
            "guardrails": {
                "local_only": True,
                "advisory_only": True,
                "no_overlap": True,
                "dry_run_zero_writes": dry_run,
                "no_writeback": True,
                "receipts_hash_only": True,
                "environment_isolated": True,
            },
        }
    finally:
        if token:
            release_run_lock(token=token, lock_name=lock_name, locks_dir=locks_dir)


def _parse_now(now: Optional[str]) -> Optional[datetime]:
    if not now:
        return None
    try:
        text = now.replace("Z", "+00:00") if now.endswith("Z") else now
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
