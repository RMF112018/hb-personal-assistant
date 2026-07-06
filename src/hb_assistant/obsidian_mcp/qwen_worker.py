"""Enrichment worker: claim → generate → validate → receipt (N8C-5).

The single place a queued enrichment job is executed. It is invoked ONLY by an explicit CLI command
(``hb-assistant qwen-worker ...``) or a test — there is NO backend lifespan / scheduler / watcher
path that starts it, so nothing runs on startup.

Safety contract enforced here:
  * atomic claim + owner-checked completion (via :class:`EnrichmentRepository`);
  * source text is read only through the bounded, redaction-safe N8C-3 navigation service;
  * oversized/malformed model output fails with a receipt — never silently truncated + ingested;
  * source/card digest is re-checked at completion; drift/deletion/ambiguity ⇒ ``stale_rejected``;
  * claim_extraction ingests ``candidate``/``unreviewed`` claims through the N8C-4 ``future_qwen``
    seam — no auto-accept, no vault mutation; backlink suggestions are stored only.
  * ``dry_run`` is strictly READ-ONLY: it peeks + previews and persists nothing (no claim, no lease,
    no receipt, no claim insert, no queue mutation).
"""

from __future__ import annotations

from typing import Any

from . import source_card_identity as identity
from . import source_navigation as nav
from .claim_repository import ClaimRepository
from .enrichment_model_provider import ModelProvider, ModelUnavailable
from .enrichment_models import (
    APPLIED_CANDIDATE_CLAIMS_INGESTED,
    APPLIED_STALE_REJECTED,
    APPLIED_STORED_ONLY,
    DEFAULT_MODEL_NAME,
    IMPLEMENTED_JOB_TYPES,
    JOB_BACKLINK_SUGGESTIONS,
    JOB_CLAIM_EXTRACTION,
    JOB_SOURCE_SUMMARY,
    RESULT_MAX_CHARS,
    STATUS_COMPLETED,
    STATUS_STALE,
    EnrichmentValidationError,
    OversizedModelOutput,
    dumps_capped,
    parse_result,
    sha256_hex,
)
from .enrichment_repository import EnrichmentRepository
from .source_index_repository import SourceIndexRepository

DEFAULT_LEASE_SECONDS = 300
DEFAULT_TIMEOUT_S = 60.0

PROMPT_VERSIONS = {
    JOB_SOURCE_SUMMARY: "source_summary-v1",
    JOB_CLAIM_EXTRACTION: "claim_extraction-v1",
    JOB_BACKLINK_SUGGESTIONS: "backlink_suggestions-v1",
}

_INSTRUCTIONS = {
    JOB_SOURCE_SUMMARY: (
        "Summarize the SOURCE TEXT for a personal knowledge base. Return a single JSON object: "
        '{"summary": string, "key_points": [string], "confidence": number 0..1}.'
    ),
    JOB_CLAIM_EXTRACTION: (
        "Extract atomic, source-backed claims from the SOURCE TEXT. Every claim needs an "
        "evidence_excerpt copied from the text. Return a single JSON object: "
        '{"claims": [{"claim_type": one of '
        "fact|date|risk|assumption|preference|commitment|task_candidate|contradiction_candidate|"
        'decision_candidate|unknown, "claim_text": string, "evidence_excerpt": string, '
        '"confidence": number 0..1}]}.'
    ),
    JOB_BACKLINK_SUGGESTIONS: (
        "Suggest related notes to link from the SOURCE TEXT. Return a single JSON object: "
        '{"suggestions": [{"target": string, "reason": string, "confidence": number 0..1}]}.'
    ),
}


def _build_prompt(job_type: str, source_text: str) -> str:
    # The ``[[job_type:...]]`` marker lets FakeModelProvider return the right canned payload in tests;
    # a live model treats it as an inert header.
    instruction = _INSTRUCTIONS[job_type]
    return f"[[job_type:{job_type}]]\n{instruction}\n\nSOURCE TEXT:\n{source_text}"


def _base_meta(worker_id: str, provider: ModelProvider, job_type: str, *,
               input_digest: str, source_digest: str | None) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "runtime": getattr(provider, "runtime", "unknown"),
        "model_name": DEFAULT_MODEL_NAME,
        "prompt_version": PROMPT_VERSIONS.get(job_type),
        "job_type": job_type,
        "input_digest": input_digest,
        "source_digest_at_completion": source_digest,
    }


def _subject_stale_reason(source_repo: SourceIndexRepository, job: dict[str, Any]) -> str | None:
    """Re-validate the source/card at completion. Returns a stale reason, or None if fresh.

    Pure DB checks (no vault read): source deleted/gone, content digest drift vs the enqueue
    snapshot, or an ambiguous card→source link. Mirrors the N8C-2 identity guards used by N8C-4.
    """
    source_id = job.get("source_id")
    if source_id:
        detail = source_repo.get_source_detail(str(source_id))
        if detail is None or detail.get("deleted"):
            return "source_deleted"
        snap = job.get("source_digest")
        current = detail.get("content_sha256")
        if snap and current and snap != current:
            return "source_digest_drift"
    note = job.get("note_rel_path")
    if note:
        reverse = identity.get_source_for_card(source_repo, str(note))
        if reverse.resolution == "ambiguous":
            return "ambiguous_source_card_link"
    return None


def poll_and_process(
    *,
    db_path: str,
    provider: ModelProvider,
    worker_id: str,
    limit: int = 1,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    job_types: tuple[str, ...] | None = None,
    dry_run: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> list[dict[str, Any]]:
    """Claim + process up to ``limit`` queued jobs. With ``dry_run`` it previews the next job only
    and persists nothing. Returns one outcome dict per job handled."""
    enrich = EnrichmentRepository(db_path)
    source_repo = SourceIndexRepository(db_path)
    claim_repo = ClaimRepository(db_path)

    if dry_run:
        job = enrich.peek_next_job(job_types=job_types)
        if job is None:
            return []
        return [_preview_job(source_repo, provider, job, timeout_s)]

    results: list[dict[str, Any]] = []
    for _ in range(max(int(limit), 1)):
        job = enrich.claim_next_job(worker_id, lease_seconds, job_types=job_types)
        if job is None:
            break
        results.append(_run_job(enrich, source_repo, claim_repo, provider, worker_id, job, timeout_s))
    return results


def _preview_job(source_repo: SourceIndexRepository, provider: ModelProvider,
                 job: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """READ-ONLY dry-run preview. Never claims, leases, ingests, or writes a receipt."""
    job_id, job_type = job["job_id"], job["job_type"]
    out: dict[str, Any] = {"job_id": job_id, "job_type": job_type, "dry_run": True}
    if job_type not in IMPLEMENTED_JOB_TYPES:
        return {**out, "outcome": "unsupported_job_type"}
    src = _source_text(source_repo, job)
    if src is None:
        return {**out, "outcome": "source_not_found"}
    prompt = _build_prompt(job_type, src)
    try:
        raw = provider.generate(prompt, model=DEFAULT_MODEL_NAME, timeout_s=timeout_s)
        parsed = parse_result(job_type, raw)
    except (ModelUnavailable, EnrichmentValidationError) as exc:
        return {**out, "outcome": "would_fail", "error": str(exc)}
    return {**out, "outcome": "would_complete", "preview": parsed.result,
            "would_ingest_claims": len(parsed.claim_candidates)}


def _source_text(source_repo: SourceIndexRepository, job: dict[str, Any]) -> str | None:
    source_id = job.get("source_id")
    if not source_id:
        return ""  # note-anchored jobs without a source_id carry payload text only (none yet)
    env = nav.get_source(source_repo, str(source_id))
    if env is None:
        return None
    src = env.get("source") or {}
    return str(src.get("text_excerpt") or "")


def _run_job(enrich: EnrichmentRepository, source_repo: SourceIndexRepository,
             claim_repo: ClaimRepository, provider: ModelProvider, worker_id: str,
             job: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    job_id, job_type = job["job_id"], job["job_type"]
    out: dict[str, Any] = {"job_id": job_id, "job_type": job_type}

    if job_type not in IMPLEMENTED_JOB_TYPES:
        enrich.fail_job(job_id, worker_id, f"unsupported_job_type:{job_type}")
        return {**out, "status": "failed", "reason": "unsupported_job_type"}

    enrich.mark_running(job_id, worker_id)

    source_env_text = _source_text(source_repo, job)
    src_detail = source_repo.get_source_detail(str(job["source_id"])) if job.get("source_id") else {}
    src = src_detail or {}
    input_digest = sha256_hex(_build_prompt(job_type, source_env_text or ""))
    meta = _base_meta(worker_id, provider, job_type, input_digest=input_digest,
                      source_digest=(src.get("content_sha256") if src else None))

    if source_env_text is None:
        # Source vanished between enqueue and run.
        enrich.complete_job(job_id, worker_id, status=STATUS_STALE, result_json=None,
                            applied_status=APPLIED_STALE_REJECTED,
                            receipt_metadata={**meta, "safety_flags": ["source_not_found"]})
        return {**out, "status": STATUS_STALE, "applied_status": APPLIED_STALE_REJECTED,
                "reason": "source_not_found"}

    prompt = _build_prompt(job_type, source_env_text)
    try:
        raw = provider.generate(prompt, model=DEFAULT_MODEL_NAME, timeout_s=timeout_s)
    except ModelUnavailable as exc:
        res = enrich.fail_job(job_id, worker_id, f"model_unavailable:{exc}", receipt_metadata=meta)
        return {**out, "status": res.get("status"), "reason": "model_unavailable"}

    meta["output_digest"] = sha256_hex(raw)

    # Validate + normalize; oversized or malformed output FAILS (no truncate-and-ingest).
    try:
        parsed = parse_result(job_type, raw)
    except OversizedModelOutput as exc:
        res = enrich.fail_job(job_id, worker_id, str(exc), receipt_metadata=meta)
        return {**out, "status": res.get("status"), "reason": "oversized_model_output"}
    except EnrichmentValidationError as exc:
        res = enrich.fail_job(job_id, worker_id, f"invalid_result:{exc}", receipt_metadata=meta)
        return {**out, "status": res.get("status"), "reason": "invalid_result"}

    # Digest / identity re-validation at completion — never apply/ingest stale model output.
    stale_reason = _subject_stale_reason(source_repo, job)
    if stale_reason:
        enrich.complete_job(job_id, worker_id, status=STATUS_STALE, result_json=None,
                            applied_status=APPLIED_STALE_REJECTED,
                            receipt_metadata={**meta, "safety_flags": [*parsed.safety_flags, stale_reason]})
        return {**out, "status": STATUS_STALE, "applied_status": APPLIED_STALE_REJECTED,
                "reason": stale_reason}

    meta["safety_flags"] = list(parsed.safety_flags)
    applied_status = APPLIED_STORED_ONLY
    result_payload = dict(parsed.result)

    if job_type == JOB_CLAIM_EXTRACTION and parsed.claim_candidates:
        ingest = claim_repo.ingest_candidates(
            parsed.claim_candidates,
            source_id=job.get("source_id"),
            note_rel_path=job.get("note_rel_path"),
            card_id=job.get("card_id"),
            source_kind=src.get("source_kind"),
            source_root_key=src.get("source_root_key"),
            source_rel_path=src.get("rel_path"),
            extracted_by="future_qwen",
            extractor_version=PROMPT_VERSIONS[job_type],
            model_name=DEFAULT_MODEL_NAME,
            status="candidate",
            review_state="unreviewed",
        )
        applied_status = APPLIED_CANDIDATE_CLAIMS_INGESTED
        result_payload["ingest"] = {k: ingest[k] for k in ("ingested", "updated", "rejected", "count")}

    result_json = dumps_capped(result_payload, RESULT_MAX_CHARS)
    enrich.complete_job(job_id, worker_id, status=STATUS_COMPLETED, result_json=result_json,
                        applied_status=applied_status, receipt_metadata=meta)
    return {**out, "status": STATUS_COMPLETED, "applied_status": applied_status,
            "claims_ingested": result_payload.get("ingest", {}).get("count", 0)}
