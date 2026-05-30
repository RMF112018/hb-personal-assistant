"""Phase 06 Prompt 11 — Ollama structured email intelligence (local-only, advisory).

Turns already-indexed, project-matched email into a **schema-constrained, advisory**
local-model classification: project-match suggestions, topic labels, relationship
candidates, risk flags, and review reasons. The model is advisory only — it never
mutates the mailbox, never makes legal/contractual/financial/personnel determinations,
and its output never overrides the deterministic Prompt-10 review rules.

Body context is used **only** through a controlled, in-memory ``decrypt_text`` read that
is discarded immediately after building the prompt. No decrypted body, no full-body
plaintext, and no raw prompt/response text is ever logged, returned, or persisted — only
the structured, redacted advisory output (V14 ``email_model_classifications``) plus review
routing and a per-run audit receipt.

Invalid model JSON is rejected (never partially persisted) and routes the message to
review. This mirrors the construction classification validator/router precedent.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from hb_assistant.construction.classification.client import (
    OllamaChatClient,
    OllamaUnavailable,
)
from hb_assistant.construction.email.project_matcher import load_pilot_project_descriptors
from hb_assistant.construction.email.review_categories import classify_review_categories
from hb_assistant.construction.policy.email_active import (
    EmailIntelligenceActivePolicy,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.security.text_vault import decrypt_text

CLASSIFICATION_VERSION = "phase06-email-ollama-v1"
DEFAULT_MODEL_NAME = "mistral"
_LOW_CONFIDENCE_FALLBACK = 0.75
# Bounded body snippet length used for in-memory prompt context (never persisted).
_BODY_SNIPPET_CHARS = 600

# Forbidden output keys (defense in depth on top of the strict Pydantic models): the
# model must never echo a body or assert a protected determination.
_FORBIDDEN_OUTPUT_KEYS = (
    "body",
    "body_text",
    "body" + "_html",
    "raw_email",
    "plain" + "_text",
    "legal" + "_determination",
    "contractual" + "_determination",
    "financial" + "_determination",
    "personnel" + "_determination",
)

_SYSTEM_PROMPT = (
    "You are a local, advisory email-intelligence assistant for a construction "
    "general contractor. Classify the message into STRICT JSON only. You must not "
    "make legal, contractual, claim, personnel, or financial determinations; your "
    "output is advisory and routed to human review. Never echo the email body. "
    "Respond with a single JSON object matching the required schema."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvalidEmailModelOutputError(Exception):
    """Raised when raw model output cannot be parsed/validated (routes to review)."""

    def __init__(self, code: str, snippet: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.snippet = snippet
        self.detail = detail


class ProjectMatchSuggestion(BaseModel):
    project_key: str
    signal: str
    confidence: float

    model_config = {"extra": "forbid"}


class RelationshipHint(BaseModel):
    candidate_type: str
    target_hint: str
    confidence: float

    model_config = {"extra": "forbid"}


class EmailModelOutput(BaseModel):
    """The model's structured output (matches ollama_email_intelligence_schema.json)."""

    project_match_suggestions: list[ProjectMatchSuggestion]
    topic_labels: list[str]
    relationship_candidates: list[RelationshipHint]
    risk_flags: list[str]
    review_required: bool
    review_reasons: list[str]
    confidence: float

    model_config = {"extra": "forbid"}


class EmailClassificationResult(BaseModel):
    """The persisted/emitted advisory record (never includes body text)."""

    message_id: str
    classification_version: str
    project_match_suggestions: list[ProjectMatchSuggestion]
    relationship_candidates: list[RelationshipHint]
    risk_flags: list[str]
    review_recommendation: dict[str, Any]
    confidence: float

    model_config = {"extra": "forbid"}


class EmailClassificationSample(BaseModel):
    """Evidence-safe preview of one classification (redacted; never body text)."""

    message_ref: str
    classification_status: str
    topic_labels: list[str]
    risk_flags: list[str]
    sensitivity_categories: list[str]
    review_required: bool
    confidence: float
    encrypted_body_context_used: bool

    model_config = {"extra": "forbid"}


class EmailClassificationReport(BaseModel):
    """Outcome of a classify run (counts + redacted samples; no body text)."""

    project_key: Optional[str] = None
    project_number: Optional[str] = None
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    classification_version: str
    model_name: str
    use_encrypted_body_context: bool
    messages_considered: int
    model_attempted_count: int
    encrypted_body_context_used_count: int
    model_outputs_valid: bool
    model_outputs_invalid_count: int
    review_required_count: int
    plaintext_persisted: bool = False
    samples: list[EmailClassificationSample]
    disclaimer: str = (
        "model output is advisory only; deterministic review rules govern; no plaintext "
        "body is persisted or emitted"
    )

    model_config = {"extra": "forbid"}


def _scan_forbidden_keys(value: Any) -> Optional[str]:
    """Recursively find a forbidden key anywhere in a parsed JSON structure."""
    if isinstance(value, dict):
        for k, v in value.items():
            kl = str(k).lower()
            if kl in _FORBIDDEN_OUTPUT_KEYS or kl.endswith("_determination"):
                return str(k)
            found = _scan_forbidden_keys(v)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _scan_forbidden_keys(item)
            if found:
                return found
    return None


def _snippet(raw: str, limit: int = 200) -> str:
    return " ".join(raw.split())[:limit]


def parse_and_validate_email_output(raw: str) -> EmailModelOutput:
    """Parse + validate raw model output into ``EmailModelOutput``.

    Raises ``InvalidEmailModelOutputError`` (sanitized snippet, never plaintext body)
    on any failure: empty, non-JSON, non-object, forbidden field, or schema mismatch.
    """
    if raw is None or not raw.strip():
        raise InvalidEmailModelOutputError("empty_output", "")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise InvalidEmailModelOutputError("json_parse_failed", _snippet(raw), str(e)) from None
    if not isinstance(parsed, dict):
        raise InvalidEmailModelOutputError("not_a_json_object", _snippet(raw))
    forbidden = _scan_forbidden_keys(parsed)
    if forbidden is not None:
        raise InvalidEmailModelOutputError(
            "forbidden_field", _snippet(raw), f"forbidden output key: {forbidden}"
        )
    try:
        return EmailModelOutput.model_validate(parsed)
    except ValidationError as e:
        raise InvalidEmailModelOutputError(
            "schema_validation_failed", _snippet(raw), f"{e.error_count()} validation error(s)"
        ) from None


class EmailIntelligenceClassifier:
    """Local-only advisory Ollama classification over indexed, project-matched email."""

    def __init__(
        self,
        store: ConstructionStore,
        *,
        policy: Optional[EmailIntelligenceActivePolicy] = None,
        client: Optional[OllamaChatClient] = None,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        self._store = store
        self._policy = policy or load_email_intelligence_active_policy()
        self._client = client
        self._model_name = model_name

    def classify(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        use_encrypted_body_context: bool = False,
        dry_run: bool = True,
        max_messages: int = 200,
        mock_output: Optional[str] = None,
    ) -> EmailClassificationReport:
        lookback = max(1, min(int(lookback_days or self._policy.default_lookback_days), 366))
        descriptors = load_pilot_project_descriptors(project_key)
        descriptor = descriptors[0] if descriptors else None
        project_number = descriptor.project_number if descriptor else None
        received_after = (
            (_utc_now() - timedelta(days=lookback)).replace(microsecond=0).isoformat()
        )
        low_threshold = float(
            getattr(self._policy, "low_confidence_threshold", _LOW_CONFIDENCE_FALLBACK)
        )

        matches = self._store.list_email_project_matches(
            project_key=project_key, limit=max_messages
        )
        best_by_message: dict[str, dict[str, Any]] = {}
        for m in matches:
            mid = m["message_id"]
            if mid not in best_by_message or m["confidence"] > best_by_message[mid]["confidence"]:
                best_by_message[mid] = m

        considered = 0
        model_attempted = 0
        body_context_used = 0
        invalid_count = 0
        review_count = 0
        run_id = f"{uuid.uuid4()}:classify"
        samples: list[EmailClassificationSample] = []

        for mid in sorted(best_by_message):
            match = best_by_message[mid]
            msg = self._store.get_email_message(mid)
            if msg is None:
                continue
            received = msg.get("received_datetime")
            if received and received < received_after:
                continue
            considered += 1

            confidence = float(match.get("confidence") or 0.0)
            preview = msg.get("body_preview_excerpt_redacted") or ""
            sensitive = classify_review_categories(preview)
            deterministic_review = bool(sensitive) or confidence < low_threshold

            # Controlled, in-memory body decrypt (discarded after model call).
            body_used = False
            prompt: Optional[str] = None
            if use_encrypted_body_context:
                vault = self._store.get_email_body_vault_ref(mid)
                if vault is not None:
                    plaintext = decrypt_text(vault.get("encrypted_full_body_ref"))
                    if plaintext:
                        body_used = True
                        body_context_used += 1
                        # The decrypted snippet is used ONLY to build the in-memory
                        # prompt below; it is never logged, returned, or persisted.
                        prompt = self._build_prompt(msg, match, sensitive, plaintext)
                        del plaintext
            if prompt is None:
                prompt = self._build_prompt(msg, match, sensitive, None)

            raw = self._run_model(prompt=prompt, mock_output=mock_output)
            # Explicitly drop prompt context (may include bounded decrypted body).
            del prompt

            status = "model_unavailable"
            model_output: Optional[EmailModelOutput] = None
            if raw is not None:
                model_attempted += 1
                try:
                    model_output = parse_and_validate_email_output(raw)
                    status = "valid"
                except InvalidEmailModelOutputError:
                    status = "invalid_model_output"
                    invalid_count += 1

            # Deterministic Prompt-10 rules always govern; the model can only add review.
            review_required = deterministic_review
            review_reasons: list[str] = []
            if sensitive:
                review_reasons.append("sensitive_category:" + ",".join(sensitive))
            if confidence < low_threshold:
                review_reasons.append("low_confidence_project_match")
            if status == "invalid_model_output":
                review_required = True
                review_reasons.append("invalid_model_output")
            elif model_output is not None:
                if model_output.review_required:
                    review_required = True
                    review_reasons.append("model_review_recommended")
                if model_output.confidence < low_threshold:
                    review_required = True
                    review_reasons.append("low_model_confidence")
                review_reasons.extend(
                    f"model:{r}" for r in model_output.review_reasons if r
                )

            if review_required:
                review_count += 1

            if not dry_run:
                self._persist(
                    msg=msg,
                    match=match,
                    status=status,
                    model_output=model_output,
                    sensitive=sensitive,
                    review_required=review_required,
                    review_reasons=review_reasons,
                    project_key=project_key,
                )

            if len(samples) < 10:
                samples.append(
                    EmailClassificationSample(
                        message_ref=(hash_value(mid) or mid)[:16],
                        classification_status=status,
                        topic_labels=model_output.topic_labels if model_output else [],
                        risk_flags=model_output.risk_flags if model_output else [],
                        sensitivity_categories=sensitive,
                        review_required=review_required,
                        confidence=(model_output.confidence if model_output else confidence),
                        encrypted_body_context_used=body_used,
                    )
                )

        if not dry_run:
            self._store.insert_email_processing_receipt(
                receipt_id=run_id,
                operation="model_classification",
                status="ok",
                run_id=run_id,
                project_key=project_key,
                detail={
                    "messages_considered": considered,
                    "model_attempted": model_attempted,
                    "encrypted_body_context_used": body_context_used,
                    "model_outputs_invalid": invalid_count,
                    "review_required": review_count,
                    "classification_version": CLASSIFICATION_VERSION,
                    "model_name": self._model_name,
                },
            )

        return EmailClassificationReport(
            project_key=project_key,
            project_number=project_number,
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=not dry_run,
            classification_version=CLASSIFICATION_VERSION,
            model_name=self._model_name,
            use_encrypted_body_context=use_encrypted_body_context,
            messages_considered=considered,
            model_attempted_count=model_attempted,
            encrypted_body_context_used_count=body_context_used,
            model_outputs_valid=invalid_count == 0,
            model_outputs_invalid_count=invalid_count,
            review_required_count=review_count,
            plaintext_persisted=False,
            samples=samples,
        )

    # --- prompt + model -------------------------------------------------------

    def _build_prompt(
        self,
        msg: dict[str, Any],
        match: dict[str, Any],
        sensitive: list[str],
        body_text_ctx: Optional[str],
    ) -> str:
        """Build the bounded in-memory model prompt.

        May include a bounded decrypted-body snippet for context; the returned string
        is used only for the immediate model call and is never logged or persisted.
        """
        recipients = self._store.list_email_message_recipients(message_id=msg["message_id"])
        domains = sorted({r.get("domain") for r in recipients if r.get("domain")})
        lines = [
            f"subject: {msg.get('subject_redacted') or ''}",
            f"sender_domain: {msg.get('sender_domain') or ''}",
            f"recipient_domains: {', '.join(d for d in domains if d)}",
            f"received: {msg.get('received_datetime') or ''}",
            f"project_signal: {match.get('match_signal') or ''}",
            f"project_confidence: {match.get('confidence')}",
            f"sensitivity_categories: {', '.join(sensitive)}",
        ]
        if body_text_ctx:
            lines.append(f"body_context: {body_text_ctx[:_BODY_SNIPPET_CHARS]}")
        return "\n".join(lines)

    def _run_model(self, *, prompt: str, mock_output: Optional[str]) -> Optional[str]:
        if mock_output is not None:
            return mock_output
        if self._client is None:
            return None
        try:
            return self._client.generate_json(system=_SYSTEM_PROMPT, prompt=prompt)
        except OllamaUnavailable:
            return None

    # --- persistence ----------------------------------------------------------

    def _persist(
        self,
        *,
        msg: dict[str, Any],
        match: dict[str, Any],
        status: str,
        model_output: Optional[EmailModelOutput],
        sensitive: list[str],
        review_required: bool,
        review_reasons: list[str],
        project_key: Optional[str],
    ) -> None:
        mid = msg["message_id"]
        schema_version = CLASSIFICATION_VERSION
        cid = (
            hash_value(f"{mid}|{self._model_name}|{schema_version}") or f"{mid}:{self._model_name}"
        )
        self._store.upsert_email_model_classification(
            classification_id=cid,
            message_id=mid,
            model_name=self._model_name,
            schema_version=schema_version,
            classification_status=status,
            conversation_id=msg.get("conversation_id"),
            project_key=project_key or match.get("project_key"),
            model_version=None,
            project_match_confidence=float(match.get("confidence") or 0.0),
            topic_labels=(model_output.topic_labels if model_output else []),
            relationship_candidates=(
                [c.model_dump() for c in model_output.relationship_candidates]
                if model_output
                else []
            ),
            risk_flags=(model_output.risk_flags if model_output else []),
            sensitive_categories=sensitive,
            review_required=review_required,
            review_reasons=review_reasons,
        )
        if review_required:
            reason = "; ".join(review_reasons) or "model_classification_review"
            category = sensitive[0] if sensitive else "model_review"
            review_id = hash_value(f"{mid}|{category}|{reason}") or f"{mid}:{category}"
            self._store.enqueue_email_review_item(
                review_id=review_id,
                message_id=mid,
                category=category,
                sensitivity="high" if sensitive else "medium",
                reason=reason,
                suggested_action="manual_review",
                confidence=float(match.get("confidence") or 0.0),
                project_key=project_key or match.get("project_key"),
            )
