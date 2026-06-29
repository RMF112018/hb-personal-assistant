"""Optional local-LLM summarization with a guaranteed deterministic fallback.

The summarize/extract tools prefer a local model (Ollama by default, optionally the
Anthropic ``second-brain`` extra) but must never *require* one: any unavailability,
import error, timeout, or malformed output falls back to the deterministic analysis from
``extract.py``. The returned ``mode`` tells the caller which path produced the result.

No prompt or model response is ever persisted. The backend is injectable (any object with
``generate_json(*, system, prompt) -> str``) so tests run without a live daemon.
"""

from __future__ import annotations

import json
from time import perf_counter as _perf_counter
from typing import Any, Protocol

from .config import ObsidianMcpConfig

_SUMMARY_KEYS = ("summary", "key_points", "action_items", "decisions", "entities", "suggested_tags", "suggested_links")

_JSON_CONTRACT = (
    "Return ONLY a JSON object with keys: summary (string), key_points (string array), "
    "action_items (string array), decisions (string array), entities (string array), "
    "suggested_tags (string array), suggested_links (string array). Be concise and factual; "
    "do not invent facts not present in the text."
)

_SYSTEM_PROMPT = (
    "You summarize a single Obsidian note or email for a construction project executive. "
    + _JSON_CONTRACT
)

# File-type-tuned advisory system prompts. The JSON output contract is identical across types;
# only the framing differs so the advisory emphasizes what matters for each format. Used only on
# the source-card summarization path (note/email summarize keeps the default prompt).
_FILE_TYPE_PROMPTS = {
    "pdf": (
        "You summarize an extracted PDF document (drawings, specs, RFIs, or reports) for a "
        "construction project executive. Note any sheet/section references and obligations. "
        + _JSON_CONTRACT
    ),
    "docx": (
        "You summarize an extracted Word document (letters, scopes, contracts, minutes) for a "
        "construction project executive. Capture decisions, commitments, and dates. "
        + _JSON_CONTRACT
    ),
    "xlsx": (
        "You summarize an extracted spreadsheet (schedules, budgets, logs, trackers) for a "
        "construction project executive. Note what the columns/totals track and any flagged rows. "
        + _JSON_CONTRACT
    ),
    "csv": (
        "You summarize tabular CSV data for a construction project executive. Note what each "
        "column represents and any notable values. " + _JSON_CONTRACT
    ),
    "md": (
        "You summarize a Markdown note for a construction project executive. " + _JSON_CONTRACT
    ),
    "txt": (
        "You summarize a plain-text file for a construction project executive. " + _JSON_CONTRACT
    ),
}


def _prompt_for(file_ext: str | None) -> str:
    """Pick a file-type-tuned advisory system prompt, falling back to the default."""
    if not file_ext:
        return _SYSTEM_PROMPT
    return _FILE_TYPE_PROMPTS.get(file_ext.lower(), _SYSTEM_PROMPT)


# --- Typed construction-drawing advisory (PM-grade) --------------------------------------------
# The model receives DETERMINISTIC facts (already extracted) + a bounded excerpt and returns a
# strict PM-facing schema. It must not invent facts; unsupported fields are "unknown"/empty.
_DRAWING_LIST_KEYS = (
    "scope_elements", "coordination_items", "submittals_or_shop_drawings", "field_installation_risks",
    "referenced_sheets", "revision_impacts", "pm_followups", "verify_against_source",
)
_DRAWING_CONFIDENCE_KEYS = ("sheet_identity", "scope_summary", "action_items")
_DRAWING_LIST_CAP = 12

_DRAWING_SYSTEM_PROMPT = (
    "You assist a construction Project Manager. You are given DETERMINISTIC FACTS already extracted "
    "from one construction drawing sheet (sheet number, title, project, revision, referenced sheets, "
    "datums, notes, coordination flags), followed by a bounded text excerpt. Produce a PM-facing "
    "interpretation. Do NOT invent entities, dates, revision descriptions, or sheet references that "
    "are not present in the facts/excerpt; if a field is unsupported, use \"unknown\" or an empty "
    "array. Use construction PM language focused on coordination, submittals, procurement, field "
    "risk, and cross-discipline references. Output is advisory and NOT authoritative.\n"
    "Return ONLY a JSON object with keys: plain_english_summary (string), what_this_sheet_is_for "
    "(string), scope_elements (string array), coordination_items (string array), "
    "submittals_or_shop_drawings (string array), field_installation_risks (string array), "
    "referenced_sheets (string array), revision_impacts (string array), pm_followups (string array), "
    "confidence (object with keys sheet_identity, scope_summary, action_items each one of "
    "high|medium|low), verify_against_source (string array)."
)


def _normalize_drawing(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce model output into the strict drawing schema (bounded, typed)."""
    out: dict[str, Any] = {
        "plain_english_summary": str(data.get("plain_english_summary") or "").strip(),
        "what_this_sheet_is_for": str(data.get("what_this_sheet_is_for") or "").strip(),
    }
    for key in _DRAWING_LIST_KEYS:
        value = data.get(key)
        out[key] = (
            [str(v).strip() for v in value if str(v).strip()][:_DRAWING_LIST_CAP]
            if isinstance(value, list) else []
        )
    conf = data.get("confidence") if isinstance(data.get("confidence"), dict) else {}
    out["confidence"] = {
        k: (str(conf.get(k)).lower() if str(conf.get(k)).lower() in ("high", "medium", "low") else "low")
        for k in _DRAWING_CONFIDENCE_KEYS
    }
    return out


def summarize_drawing(
    config: ObsidianMcpConfig,
    *,
    prompt_text: str,
    backend: GenerationBackend | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    """Typed PM advisory for construction drawings. Returns (data|None, mode, reason).

    ``data`` is the normalized drawing schema on the model path, else ``None`` with ``mode``
    ``"deterministic_fallback"`` and a specific ``reason`` (disabled/ollama_unavailable/timeout/
    empty_response/invalid_json). The caller falls back to the deterministic card on None.
    ``prompt_text`` already embeds the deterministic facts + bounded excerpt.
    """
    if config.summarization_backend == "deterministic":
        return None, "deterministic_fallback", "disabled"
    chosen = backend or _resolve_backend(config)
    if chosen is None:
        return None, "deterministic_fallback", "ollama_unavailable"
    try:
        raw = chosen.generate_json(system=_DRAWING_SYSTEM_PROMPT, prompt=prompt_text)
    except Exception as exc:  # noqa: BLE001 - any backend failure falls back deterministically
        return None, "deterministic_fallback", _network_reason(exc)
    if not (raw or "").strip():
        return None, "deterministic_fallback", "empty_response"
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("non_object_response")
    except (ValueError, TypeError, KeyError):
        return None, "deterministic_fallback", "invalid_json"
    return _normalize_drawing(data), "llm", "ok"


class GenerationBackend(Protocol):
    def generate_json(self, *, system: str, prompt: str) -> str: ...


def _resolve_backend(config: ObsidianMcpConfig) -> GenerationBackend | None:
    """Construct the configured local-model backend, or None if unavailable."""
    provider = config.summarization_provider
    try:
        if provider == "ollama":
            from hb_assistant.construction.classification.client import OllamaChatClient

            return OllamaChatClient(
                model=config.summarization_model,
                timeout=float(config.source_summary_ollama_timeout_seconds),
            )
        if provider == "anthropic":
            return _AnthropicBackend(model=config.summarization_model)
    except Exception:  # noqa: BLE001 - optional dependency / construction import absent
        return None
    return None


def _network_reason(exc: BaseException) -> str:
    """Map a backend (network) failure to a stable category code.

    The codes come from ``OllamaUnavailable`` messages (sanitized — no URL/body). Anything
    unrecognized degrades to ``ollama_unavailable``. These are category codes only; no
    prompt or model response is ever persisted.
    """
    message = str(exc)
    if message == "ollama_timeout":
        return "timeout"
    if message == "ollama_missing_response_field":
        return "empty_response"
    return "ollama_unavailable"


def summarize(
    config: ObsidianMcpConfig,
    *,
    text: str,
    deterministic: dict[str, Any],
    backend: GenerationBackend | None = None,
    file_ext: str | None = None,
) -> tuple[dict[str, Any], str, str]:
    """Return (result, mode, reason).

    ``mode`` is ``"llm"`` or ``"deterministic_fallback"``. ``reason`` is ``"ok"`` on the
    model path, ``"disabled"`` when summarization is configured off, or a specific failure
    category (``timeout``, ``invalid_json``, ``empty_response``, ``ollama_unavailable``)
    when the model path falls back. ``file_ext`` selects a file-type-tuned advisory prompt
    (defaults to the generic note/email prompt).
    """
    if config.summarization_backend == "deterministic":
        return dict(deterministic), "deterministic_fallback", "disabled"
    chosen = backend or _resolve_backend(config)
    if chosen is None:
        return dict(deterministic), "deterministic_fallback", "ollama_unavailable"
    try:
        raw = chosen.generate_json(system=_prompt_for(file_ext), prompt=text)
    except Exception as exc:  # noqa: BLE001 - any backend failure falls back deterministically
        return dict(deterministic), "deterministic_fallback", _network_reason(exc)
    if not (raw or "").strip():
        return dict(deterministic), "deterministic_fallback", "empty_response"
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("non_object_response")
    except (ValueError, TypeError, KeyError):
        return dict(deterministic), "deterministic_fallback", "invalid_json"
    return _merge(data, deterministic), "llm", "ok"


def validate_summary_model(config: ObsidianMcpConfig) -> dict[str, Any]:
    """Validate ``config.summarization_model`` against the locally installed Ollama tags.

    Returns a structured report (never raises): ``available`` (daemon reachable), ``models``
    (installed tags), ``requested``, ``resolved`` (the tag that would actually run), ``match``
    (``exact`` | ``tag_resolved`` | ``missing`` | ``unknown``), and ``latency_ms``. A bare name
    (``llama3.1``) resolves to the first installed ``name:tag`` (``llama3.1:8b``) and is reported
    as ``tag_resolved`` — we never silently rewrite the persisted config.
    """
    requested = config.summarization_model
    report: dict[str, Any] = {
        "provider": config.summarization_provider,
        "requested": requested,
        "available": False,
        "models": [],
        "resolved": None,
        "match": "unknown",
        "latency_ms": None,
    }
    if config.summarization_provider != "ollama":
        # Non-ollama providers are not introspectable here; report as unknown.
        return report
    try:
        from hb_assistant.construction.classification.client import list_ollama_models
    except Exception:  # noqa: BLE001 - construction import absent
        report["match"] = "ollama_unavailable"
        return report
    start = _perf_counter()
    try:
        models = list_ollama_models()
    except Exception as exc:  # noqa: BLE001 - daemon down / bad envelope
        report["match"] = "ollama_unavailable"
        report["reason"] = str(exc)
        return report
    report["available"] = True
    report["models"] = models
    report["latency_ms"] = int((_perf_counter() - start) * 1000)
    if requested in models:
        report["resolved"] = requested
        report["match"] = "exact"
    else:
        resolved = next((m for m in models if m.split(":", 1)[0] == requested), None)
        if resolved is not None:
            report["resolved"] = resolved
            report["match"] = "tag_resolved"
        else:
            report["match"] = "missing"
    return report


def _merge(data: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    """Take model fields where present and well-typed; fall back per-field otherwise."""
    result = dict(deterministic)
    for key in _SUMMARY_KEYS:
        value = data.get(key)
        if key == "summary":
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
        elif isinstance(value, list):
            result[key] = [str(v).strip() for v in value if str(v).strip()]
    return result


class _AnthropicBackend:
    """Lazy Anthropic adapter (only used when summarization_provider == 'anthropic')."""

    def __init__(self, *, model: str) -> None:
        from anthropic import Anthropic  # noqa: PLC0415 - optional 'second-brain' extra

        self._client = Anthropic()
        self._model = model

    def generate_json(self, *, system: str, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system + " Respond with JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "".join(parts)
