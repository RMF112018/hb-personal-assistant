"""Phase 10 Prompt 04 — Local Model Structured Output Client.

A reusable, schema-enforced wrapper around a local generation backend (Ollama by default).
It turns a free-form local-model call into a validated, auditable structured-output run:

- **Schema enforcement.** The raw model output is parsed as JSON and validated against a
  caller-supplied Pydantic model (e.g. :class:`ActionCandidate`) *before* it is trusted or
  returned. Validation failures never crash the run — they are mapped to a closed ``status``.
- **Per-profile timeout.** The backend timeout is taken from the resolved
  :class:`LocalModelProfile.timeout_seconds` (never hardcoded).
- **Bounded retry / self-repair.** On bad JSON or schema-invalid output the client appends a
  redacted repair instruction and retries (``_MAX_ATTEMPTS`` total).
- **Single-hop fallback.** If the primary profile still fails, the client resolves
  ``LocalModelProfiles.fallbacks[profile_id]`` (one hop only — the seed is single-hop), retries
  once, and records ``fallback_used``.
- **Redacted / hashing-only receipts.** A run writes one ``local_model_run_receipts`` row carrying
  only SHA-256[:12] hashes of the input context and raw output (via the shared
  ``procore.normalizers.hashing.hash_summary``), plus metadata (status, schema_valid, latency,
  fallback_used). No raw prompt, response, body, URL, token, or path is ever persisted. The write
  is skipped entirely in ``dry_run`` (the would-be receipt fields are surfaced instead).
- **Heavy-profile gate.** A ``heavy_profile`` profile refuses to run unless ``heavy_enabled=True``.
- **Redacted errors.** Backend/timeouts/validation errors are reduced to short category codes;
  raw exception text is kept only in the in-memory result, never in the receipt row.

This module performs no Graph/Procore/email/calendar writeback and is local-only. It does not
refactor the Phase 10A Prompt 07 extractor (``raw_action_intelligence.py``) — it is an independent
primitive that the new Prompt 04 CLI surfaces (``ai-jobs run``, ``action-intel extract-fixture``)
build on.

Backends implement the narrow :class:`GenerationBackend` protocol
(``generate_json(*, system, prompt) -> str``); the production
:class:`~hb_assistant.construction.classification.client.OllamaChatClient` satisfies it
structurally. :class:`StaticOutputClient` is the in-module offline/test backend.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from hb_assistant.construction.classification.client import (
    OllamaChatClient,
    OllamaUnavailable,
)
from hb_assistant.procore.normalizers.hashing import hash_summary

from .models import LocalModelProfile, LocalModelProfiles

#: Total generation attempts on the primary profile before fallback (incl. self-repair).
_MAX_ATTEMPTS = 3

#: Closed set of run statuses (mirrors the receipt ``status`` column contract).
RunStatus = str  # one of: ok | schema_invalid | unavailable | timeout | failed | blocked


@runtime_checkable
class GenerationBackend(Protocol):
    """Narrow backend protocol. ``OllamaChatClient`` satisfies it structurally."""

    def generate_json(self, *, system: str, prompt: str) -> str: ...


class StaticOutputClient:
    """Offline/test generation backend returning canned JSON (no daemon, no network).

    Pass a single ``output`` string to always return it, or a list of ``outputs`` to script a
    bad-then-good retry sequence (each call advances the cursor; the last item repeats). Pass
    ``raise_unavailable=True`` to simulate an unreachable daemon (raises ``OllamaUnavailable``).
    """

    def __init__(
        self,
        output: str | None = None,
        *,
        outputs: list[str] | None = None,
        raise_unavailable: bool = False,
        error_code: str = "ollama_request_failed",
    ) -> None:
        if outputs is not None:
            self._outputs = list(outputs)
        elif output is not None:
            self._outputs = [output]
        else:
            self._outputs = ["[]"]
        self._raise_unavailable = raise_unavailable
        self._error_code = error_code
        self._calls = 0

    @property
    def call_count(self) -> int:
        return self._calls

    def generate_json(self, *, system: str, prompt: str) -> str:
        if self._raise_unavailable:
            raise OllamaUnavailable(self._error_code)
        idx = min(self._calls, len(self._outputs) - 1)
        self._calls += 1
        return self._outputs[idx]


class StructuredOutputResult(BaseModel):
    """In-memory result of a structured-output run (advisory; receipt is hash-only)."""

    status: RunStatus
    profile_id: str
    provider: str
    model_name: str
    task_type: str
    schema_name: str
    schema_valid: bool = False
    fallback_used: bool = False
    attempts: int = 0
    latency_ms: int = 0
    input_context_hash: str
    output_hash: str | None = None
    error_redacted: str | None = None
    #: Validated schema object as a plain dict (advisory; None when invalid/unavailable).
    validated: dict[str, Any] | None = None
    receipt_id: str | None = None
    #: When dry_run, the receipt is NOT written; this holds the fields that *would* be written.
    would_write_receipt: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


def _resolve_profile(
    profiles: LocalModelProfiles, profile_id: str
) -> LocalModelProfile | None:
    for p in profiles.profiles:
        if p.profile_id == profile_id:
            return p
    return None


def _build_backend(profile: LocalModelProfile) -> GenerationBackend:
    """Construct the production Ollama backend for a profile (per-profile timeout)."""
    return OllamaChatClient(
        model=profile.model_name,
        timeout=float(profile.timeout_seconds),
    )


def _hash_prefix(text: str | None) -> str | None:
    summary = hash_summary(text)
    return summary["hash_prefix"] if summary else None


def action_candidate_dict_from_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Build a complete :class:`ActionCandidate`-shaped dict from a local_ai test fixture.

    Fixtures carry a partial ``expected`` block plus ``input_redacted`` metadata and a stable
    ``source_ref``. This deterministically fills the required ActionCandidate fields so the
    :class:`StaticOutputClient` can return a candidate that the client then validates — exercising
    the full generate→validate→receipt path offline. Raw values are never introduced: the title
    and reason come from already-redacted fixture fields, bounded in length.
    """
    expected = fixture.get("expected") or {}
    inp = fixture.get("input_redacted") or {}
    source_ref = fixture.get("source_ref") or fixture.get("fixture_id") or "fixture:unknown"
    title = (
        inp.get("thread_subject_redacted")
        or inp.get("summary_redacted")
        or fixture.get("fixture_id")
        or "Fixture action"
    )
    reason = inp.get("summary_redacted") or f"Derived from fixture {fixture.get('fixture_id')!r}."
    return {
        "candidate_type": expected.get("candidate_type", "task"),
        "title": str(title)[:240],
        "project_key": None,
        "assignee": expected.get("assignee", "unknown"),
        "due_at": None,
        "urgency": expected.get("urgency", "normal"),
        "waiting_state": expected.get("waiting_state", "unknown"),
        "source_refs": [str(source_ref)],
        "confidence": float(expected.get("confidence", 0.7)),
        "reason": str(reason)[:1000],
        "review_status": "pending",
        "safety_category": expected.get("safety_category", "normal"),
        "recommended_next_action": expected.get("recommended_next_action", "review"),
        "external_action_requires_approval": True,
    }


class StructuredOutputClient:
    """Schema-enforced local-model client with timeouts, fallback, and hash-only receipts."""

    def run(
        self,
        *,
        schema: type[BaseModel],
        profile: LocalModelProfile,
        profiles: LocalModelProfiles,
        system: str,
        prompt: str,
        input_context: str,
        task_type: str,
        backend: Optional[GenerationBackend] = None,
        store: Optional[Any] = None,
        dry_run: bool = True,
        heavy_enabled: bool = False,
        schema_name: Optional[str] = None,
    ) -> StructuredOutputResult:
        """Generate, validate against ``schema``, and (unless dry-run) write a hash-only receipt.

        ``backend`` is injected for tests/offline; when omitted a real ``OllamaChatClient`` is
        built from the profile. ``store`` is a ``ConstructionStore`` used only to persist the
        receipt when ``dry_run`` is False.
        """
        started = time.monotonic()
        schema_name = schema_name or getattr(schema, "__name__", "Schema")
        input_context_hash = _hash_prefix(input_context) or ""

        def _finish(
            *,
            status: RunStatus,
            used_profile: LocalModelProfile,
            fallback_used: bool,
            attempts: int,
            schema_valid: bool,
            validated: dict[str, Any] | None,
            output_hash: str | None,
            error_redacted: str | None,
        ) -> StructuredOutputResult:
            latency_ms = int((time.monotonic() - started) * 1000)
            receipt_fields = {
                "profile_id": used_profile.profile_id,
                "provider": used_profile.provider,
                "model_name": used_profile.model_name,
                "task_type": task_type,
                "status": status,
                "input_context_hash": input_context_hash,
                "output_hash": output_hash,
                "schema_name": schema_name,
                "schema_valid": schema_valid,
                "latency_ms": latency_ms,
                "fallback_used": fallback_used,
            }
            receipt_id: str | None = None
            would_write: dict[str, Any] | None = None
            if dry_run or store is None:
                would_write = dict(receipt_fields)
            else:
                receipt_id = uuid.uuid4().hex
                store.insert_local_model_run_receipt(
                    model_run_receipt_id=receipt_id,
                    **receipt_fields,
                )
            return StructuredOutputResult(
                status=status,
                profile_id=used_profile.profile_id,
                provider=used_profile.provider,
                model_name=used_profile.model_name,
                task_type=task_type,
                schema_name=schema_name,
                schema_valid=schema_valid,
                fallback_used=fallback_used,
                attempts=attempts,
                latency_ms=latency_ms,
                input_context_hash=input_context_hash,
                output_hash=output_hash,
                error_redacted=error_redacted,
                validated=validated,
                receipt_id=receipt_id,
                would_write_receipt=would_write,
            )

        # 1. Heavy-profile gate — refuse unless explicitly enabled.
        if profile.heavy_profile and not heavy_enabled:
            return _finish(
                status="blocked",
                used_profile=profile,
                fallback_used=False,
                attempts=0,
                schema_valid=False,
                validated=None,
                output_hash=None,
                error_redacted="heavy_profile_requires_explicit_enable",
            )

        # 2. Primary attempt(s) with bounded self-repair.
        primary = self._attempt(
            schema=schema,
            profile=profile,
            system=system,
            prompt=prompt,
            backend=backend if backend is not None else None,
        )
        if primary.ok:
            return _finish(
                status="ok",
                used_profile=profile,
                fallback_used=False,
                attempts=primary.attempts,
                schema_valid=True,
                validated=primary.validated,
                output_hash=primary.output_hash,
                error_redacted=None,
            )

        # 3. Single-hop fallback (seed is single-hop). Only when the primary failed.
        fallback_id = profiles.fallbacks.get(profile.profile_id)
        fallback_profile = (
            _resolve_profile(profiles, fallback_id) if fallback_id else None
        )
        # A fallback to a heavy profile still honours the heavy gate.
        if fallback_profile is not None and not (
            fallback_profile.heavy_profile and not heavy_enabled
        ):
            secondary = self._attempt(
                schema=schema,
                profile=fallback_profile,
                system=system,
                prompt=prompt,
                # A caller-injected backend is profile-agnostic in tests; reuse it.
                backend=backend if backend is not None else None,
            )
            if secondary.ok:
                return _finish(
                    status="ok",
                    used_profile=fallback_profile,
                    fallback_used=True,
                    attempts=primary.attempts + secondary.attempts,
                    schema_valid=True,
                    validated=secondary.validated,
                    output_hash=secondary.output_hash,
                    error_redacted=None,
                )
            return _finish(
                status=secondary.status,
                used_profile=fallback_profile,
                fallback_used=True,
                attempts=primary.attempts + secondary.attempts,
                schema_valid=False,
                validated=None,
                output_hash=secondary.output_hash,
                error_redacted=secondary.error_redacted,
            )

        # 4. No fallback available (or fallback gated) — terminal failure on primary.
        return _finish(
            status=primary.status,
            used_profile=profile,
            fallback_used=False,
            attempts=primary.attempts,
            schema_valid=False,
            validated=None,
            output_hash=primary.output_hash,
            error_redacted=primary.error_redacted,
        )

    # -- internal single-profile attempt loop ------------------------------------------------
    class _AttemptResult(BaseModel):
        ok: bool
        status: RunStatus
        attempts: int
        validated: dict[str, Any] | None = None
        output_hash: str | None = None
        error_redacted: str | None = None
        model_config = {"extra": "forbid"}

    def _attempt(
        self,
        *,
        schema: type[BaseModel],
        profile: LocalModelProfile,
        system: str,
        prompt: str,
        backend: Optional[GenerationBackend],
    ) -> "StructuredOutputClient._AttemptResult":
        backend = backend if backend is not None else _build_backend(profile)
        current_prompt = prompt
        last_output_hash: str | None = None
        last_error: str | None = None
        attempts = 0
        for _ in range(_MAX_ATTEMPTS):
            attempts += 1
            try:
                raw = backend.generate_json(system=system, prompt=current_prompt)
            except OllamaUnavailable as exc:
                # Redacted category code only (e.g. ollama_request_failed / ollama_status_<n>).
                code = str(exc) or "unavailable"
                status = "timeout" if "timeout" in code else "unavailable"
                return self._AttemptResult(
                    ok=False,
                    status=status,
                    attempts=attempts,
                    output_hash=None,
                    error_redacted=code,
                )
            last_output_hash = _hash_prefix(raw)
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                last_error = "invalid_json"
                current_prompt = self._repair_prompt(prompt, last_error)
                continue
            try:
                validated = schema.model_validate(parsed)
            except ValidationError as exc:
                last_error = "schema_validation_failed"
                # Keep a bounded, structural repair hint — never the raw output.
                current_prompt = self._repair_prompt(
                    prompt, f"{last_error}: {self._first_error(exc)}"
                )
                continue
            return self._AttemptResult(
                ok=True,
                status="ok",
                attempts=attempts,
                validated=validated.model_dump(mode="json"),
                output_hash=last_output_hash,
                error_redacted=None,
            )
        return self._AttemptResult(
            ok=False,
            status="schema_invalid",
            attempts=attempts,
            output_hash=last_output_hash,
            error_redacted=last_error or "schema_invalid",
        )

    @staticmethod
    def _repair_prompt(base_prompt: str, error_redacted: str) -> str:
        return (
            f"{base_prompt}\n\n"
            f"Your previous output was rejected ({error_redacted}). "
            "Return ONLY valid JSON that exactly matches the required schema. No prose."
        )

    @staticmethod
    def _first_error(exc: ValidationError) -> str:
        try:
            err = exc.errors()[0]
            loc = ".".join(str(p) for p in err.get("loc", ()))
            return f"{loc}:{err.get('type', 'invalid')}"[:120]
        except Exception:
            return "invalid"
