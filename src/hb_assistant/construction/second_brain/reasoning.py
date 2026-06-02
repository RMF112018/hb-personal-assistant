"""Phase 08A Claude adapter boundary (Prompt 03).

The single, safety-critical transport boundary through which every later 08A
feature (interactive query, daily brief, memory synthesis) reaches Claude. It is
deliberately mock-first and offline-by-default; the live path is opt-in, gated,
and never exercised by the test suite.

Non-negotiable guardrails enforced here:

* An adapter only ever accepts a :class:`ContextEnvelope` — a bounded, redacted,
  source-linked packet. It never receives raw DB rows, raw vault notes, raw
  bodies, signed/download URLs, secrets, tokens, or any external-system handle.
* The model is never given the ability to call Microsoft Graph, Procore,
  Obsidian file APIs, or SQL — the adapter is a pure text-in/structured-out
  boundary.
* Synthesis is refused (no model call) until research-packet and context-policy
  checks pass and source references are present. Tier 3 (mandatory-review) items
  are never auto-accepted as fact — they are returned ``review_required`` in a
  degraded, blocked result.
* Raw prompts and raw model responses are never persisted or returned; only the
  structured, source-referenced :class:`AdapterResult` leaves this module.

The live mechanism is the official ``anthropic`` SDK, lazy-imported so the base
install, migrations, full test suite, and mock mode run with no cloud-model
tooling present (``pip install -e .[second-brain]`` enables live).
"""

from __future__ import annotations

import hashlib
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, field_validator

from .config import ENV_API_KEY, Mode, SecondBrainConfig

ContextQuality = Literal["sufficient", "partial", "insufficient"]
DegradationMode = Literal["none", "graceful_degraded", "blocked"]
ReviewStatus = Literal["auto_advisory", "review_recommended", "review_required"]
Disposition = Literal["advisory", "actionable"]

# Mirrors source_reference_contract.json forbidden fields. Any source-reference
# carrying one of these keys is rejected at the envelope boundary.
FORBIDDEN_REFERENCE_FIELDS: frozenset[str] = frozenset(
    {
        "raw_url",
        "download_url",
        "signed_url",
        "token",
        "secret",
        "raw_body",
        "raw_document_text",
        "raw_calendar_payload",
        "raw_prompt",
        "raw_response",
    }
)


class AnthropicUnavailable(RuntimeError):
    """Raised when live mode is requested but the Anthropic SDK is unavailable.

    The message never carries secrets, keys, prompts, or responses.
    """


class ContextEnvelope(BaseModel):
    """Bounded, redacted, source-linked context — the only adapter input."""

    question: str
    source_references: list[dict[str, str]]
    review_tier: int = 3
    review_reason_code: str = "T3_MODEL_ONLY"
    confidence_class: str = "low"
    research_packet_ok: bool = False
    context_quality: ContextQuality = "insufficient"
    disposition: Disposition = "advisory"
    coverage_warnings: list[str] = []
    stale_unknown_warnings: list[str] = []
    conflict_warnings: list[str] = []

    model_config = {"extra": "forbid"}

    @field_validator("review_tier")
    @classmethod
    def _tier_in_range(cls, value: int) -> int:
        if value not in (1, 2, 3):
            raise ValueError("review_tier must be 1, 2, or 3")
        return value

    @field_validator("source_references")
    @classmethod
    def _no_raw_reference_fields(
        cls, refs: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        for ref in refs:
            leaked = FORBIDDEN_REFERENCE_FIELDS.intersection(ref)
            if leaked:
                raise ValueError(
                    f"source_reference carries forbidden raw field(s): {sorted(leaked)}"
                )
        return refs


class AdapterResult(BaseModel):
    """Structured, source-referenced adapter output (no raw content)."""

    answer: str
    mode: Mode
    synthesized: bool
    source_references: list[dict[str, str]]
    confidence: str
    review_tier: int
    review_reason_code: str
    review_status: ReviewStatus
    disposition: Disposition
    degradation_mode: DegradationMode
    coverage_warnings: list[str] = []
    stale_unknown_warnings: list[str] = []
    conflict_warnings: list[str] = []

    model_config = {"extra": "forbid"}


def _review_status_for_tier(tier: int) -> ReviewStatus:
    mapping: dict[int, ReviewStatus] = {
        1: "auto_advisory",
        2: "review_recommended",
        3: "review_required",
    }
    return mapping[tier]


class ClaudeAdapter(ABC):
    """Adapter base: enforces the pre-synthesis gate, then delegates generation."""

    def __init__(self, *, mode: Mode) -> None:
        self.mode: Mode = mode

    def _blocked_reasons(self, envelope: ContextEnvelope) -> list[str]:
        reasons: list[str] = []
        if not envelope.research_packet_ok:
            reasons.append("research_packet_not_passed")
        if not envelope.source_references:
            reasons.append("no_source_references")
        if envelope.context_quality == "insufficient":
            reasons.append("context_quality_insufficient")
        if envelope.review_tier == 3:
            # Tier 3 is mandatory-review: never auto-accepted as fact.
            reasons.append("tier_3_mandatory_review")
        return reasons

    def synthesize(self, envelope: ContextEnvelope) -> AdapterResult:
        """Gate, then synthesize. Returns a degraded result if blocked (no call)."""
        blocked = self._blocked_reasons(envelope)
        review_status = _review_status_for_tier(envelope.review_tier)

        if blocked:
            return AdapterResult(
                answer="",
                mode=self.mode,
                synthesized=False,
                source_references=envelope.source_references,
                confidence=envelope.confidence_class,
                review_tier=envelope.review_tier,
                review_reason_code=envelope.review_reason_code,
                review_status="review_required",
                disposition=envelope.disposition,
                degradation_mode="blocked",
                coverage_warnings=[*envelope.coverage_warnings, *blocked],
                stale_unknown_warnings=envelope.stale_unknown_warnings,
                conflict_warnings=envelope.conflict_warnings,
            )

        answer = self._generate(envelope)
        degradation: DegradationMode = (
            "none"
            if envelope.context_quality == "sufficient" and envelope.review_tier == 1
            else "graceful_degraded"
        )
        return AdapterResult(
            answer=answer,
            mode=self.mode,
            synthesized=True,
            source_references=envelope.source_references,
            confidence=envelope.confidence_class,
            review_tier=envelope.review_tier,
            review_reason_code=envelope.review_reason_code,
            review_status=review_status,
            disposition=envelope.disposition,
            degradation_mode=degradation,
            coverage_warnings=envelope.coverage_warnings,
            stale_unknown_warnings=envelope.stale_unknown_warnings,
            conflict_warnings=envelope.conflict_warnings,
        )

    @abstractmethod
    def _generate(self, envelope: ContextEnvelope) -> str:
        """Produce a source-linked answer string from the bounded envelope."""
        raise NotImplementedError


class MockClaudeAdapter(ClaudeAdapter):
    """Deterministic offline adapter — the test/default synthesis path."""

    def __init__(self) -> None:
        super().__init__(mode="mock")

    def _generate(self, envelope: ContextEnvelope) -> str:
        n = len(envelope.source_references)
        return (
            f"[mock advisory synthesis] {n} source reference(s); "
            f"review tier {envelope.review_tier} ({envelope.review_reason_code}); "
            "advisory only — verify against linked sources."
        )


class LiveClaudeAdapter(ClaudeAdapter):
    """Opt-in live adapter over the official Anthropic SDK (lazy-imported).

    Never invoked by the test suite. The API key is read from the environment at
    call time and is never stored on the instance, logged, or returned.
    """

    def __init__(self, config: SecondBrainConfig) -> None:
        super().__init__(mode="live")
        self._model = config.claude_model
        self._max_output_tokens = config.max_output_tokens

    def _generate(self, envelope: ContextEnvelope) -> str:
        try:
            import anthropic  # noqa: PLC0415  (lazy by design — optional extra)
        except ImportError as exc:  # pragma: no cover - exercised via base install
            raise AnthropicUnavailable(
                "Anthropic SDK not installed. Install with "
                "`pip install -e .[second-brain]` to enable live Claude mode."
            ) from exc

        api_key = (os.environ.get(ENV_API_KEY) or "").strip()
        if not api_key:  # pragma: no cover - live path
            raise AnthropicUnavailable(f"{ENV_API_KEY} not set; cannot run live mode.")

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(  # pragma: no cover - live path
            model=self._model,
            max_tokens=self._max_output_tokens,
            system=(
                "You are a source-grounded construction-intelligence assistant. "
                "Answer only from the supplied bounded source references. Never "
                "assert legal, contractual, claim, personnel, safety, financial, "
                "entitlement, or schedule-impact determinations as fact; flag them "
                "for human review."
            ),
            messages=[{"role": "user", "content": _bounded_prompt(envelope)}],
        )
        return _first_text_block(message)  # pragma: no cover - live path


def _bounded_prompt(envelope: ContextEnvelope) -> str:
    """Render the bounded prompt from envelope metadata only (no raw content)."""
    refs = "; ".join(
        ref.get("source_id") or ref.get("source_hash") or "ref" for ref in envelope.source_references
    )
    return (
        f"Question: {envelope.question}\n"
        f"Source references: {refs}\n"
        f"Context quality: {envelope.context_quality}. "
        "Answer only from these references; cite them."
    )


def _first_text_block(message: object) -> str:  # pragma: no cover - live path
    content = getattr(message, "content", None)
    if isinstance(content, list) and content:
        text = getattr(content[0], "text", None)
        if isinstance(text, str):
            return text
    return ""


def build_claude_adapter(config: SecondBrainConfig) -> ClaudeAdapter | None:
    """Factory: disabled -> None; mock -> MockClaudeAdapter; live -> LiveClaudeAdapter."""
    if config.mode == "live":
        return LiveClaudeAdapter(config)
    if config.mode == "mock":
        return MockClaudeAdapter()
    return None


class ModelCallReceipt(BaseModel):
    """Metadata-only audit receipt for one model call (in-memory).

    Mirrors the future `second_brain_agent_model_receipts` row shape (deferred to
    V27). Carries content hashes and token counts only — never the raw prompt,
    raw response, signed/download URLs, secrets, or any raw source body.
    """

    model_receipt_id: str
    agent_run_id: str | None = None
    model_profile_id: str
    model_id: str | None = None
    input_context_hash: str
    output_hash: str
    input_token_count: int
    output_token_count: int
    temperature: float | None = None
    effort: str | None = None
    created_utc: str

    model_config = {"extra": "forbid"}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _approx_tokens(text: str) -> int:
    # Deterministic, offline approximation (~4 chars/token); no tokenizer dependency.
    return (len(text) + 3) // 4


def build_model_call_receipt(
    *,
    model_profile_id: str,
    model_id: str | None,
    input_context: str,
    output_text: str,
    agent_run_id: str | None = None,
    temperature: float | None = None,
    effort: str | None = None,
) -> ModelCallReceipt:
    """Build a metadata-only model-call receipt (hashes + token counts; no raw)."""
    return ModelCallReceipt(
        model_receipt_id=uuid.uuid4().hex,
        agent_run_id=agent_run_id,
        model_profile_id=model_profile_id,
        model_id=model_id,
        input_context_hash=_sha256(input_context),
        output_hash=_sha256(output_text),
        input_token_count=_approx_tokens(input_context),
        output_token_count=_approx_tokens(output_text),
        temperature=temperature,
        effort=effort,
        created_utc=datetime.now(timezone.utc).isoformat(),
    )


def build_claude_adapter_mock_proof() -> dict[str, object]:
    """Deterministic proof for `claude-adapter-mock-proof.json`.

    Runs a representative envelope through the mock adapter, builds a metadata-only
    model-call receipt, and proves the live path is never invoked.
    """
    envelope = ContextEnvelope(
        question="What changed on the pilot project this week?",
        source_references=[{"source_id": "S1"}, {"source_hash": "abc123"}],
        review_tier=1,
        review_reason_code="T1_DETERMINISTIC_SOURCE_BACKED",
        confidence_class="high",
        research_packet_ok=True,
        context_quality="sufficient",
    )
    adapter = MockClaudeAdapter()
    result = adapter.synthesize(envelope)
    receipt = build_model_call_receipt(
        model_profile_id="fast_summary",
        model_id="claude-haiku-4-5",
        input_context=envelope.question,
        output_text=result.answer,
    )

    result_blob = result.model_dump_json() + receipt.model_dump_json()
    no_raw_content = not any(
        token in result_blob
        for token in ("signed_url", "download_url", "raw_body", "raw_prompt", "raw_response")
    )

    return {
        "proof": "phase_08a_claude_adapter_mock",
        "proof_passed": bool(
            result.synthesized and result.mode == "mock" and no_raw_content
        ),
        "mode": result.mode,
        "synthesized": result.synthesized,
        "live_called": False,
        "no_raw_content": no_raw_content,
        "review_status": result.review_status,
        "degradation_mode": result.degradation_mode,
        "source_reference_count": len(result.source_references),
        "model_call_receipt": {
            "model_profile_id": receipt.model_profile_id,
            "model_id": receipt.model_id,
            "input_context_hash": receipt.input_context_hash,
            "output_hash": receipt.output_hash,
            "input_token_count": receipt.input_token_count,
            "output_token_count": receipt.output_token_count,
            "raw_prompt_persisted": False,
            "raw_response_persisted": False,
        },
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
            "mcp_implemented": False,
        },
    }
