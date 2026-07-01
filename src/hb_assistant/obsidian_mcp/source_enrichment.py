"""Phase 10J: first-class local-Ollama enrichment workflow — shared library.

Cross-cutting support for the unified enrichment orchestrator (summaries + tags + backlinks) that the
per-capability scripts (Phase 10B/10G) do not provide:

- a **canonical reject-reason taxonomy** + normalizer that maps each engine's native reason strings to
  one stable set of codes, so failures are counted consistently across all three workflows;
- a **passthrough observability client wrapper** that counts Ollama calls, times per-call latency, and
  classifies failures/timeouts without changing engine behavior (it proxies ``.model``/``.base_url`` and
  ``generate_text``/``generate_json``). Token counts are NOT exposed by that client seam, so they are
  reported as ``null`` — never fabricated;
- a **count-only safe-evidence writer** with a whitelist renderer (reads only known count keys, so a
  sensitive string placed in an unknown key can never leak into committed evidence).

No model calls, file writes, DB access, or runtime mutation happen here beyond the explicit evidence
writer the caller invokes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

# --- Canonical reject-reason taxonomy (Phase 10J spec) ------------------------------------------
REJECT_REASONS = frozenset({
    "invalid_format", "metadata_conflict", "unsupported_claim", "unknown_tag",
    "unknown_relationship_type", "weak_basis", "duplicate_review_only",
    "model_timeout", "model_unavailable",
    # Phase 10J summary-quality-hardening reasons (source-card summaries).
    "classification_conflict", "generic_spec_unqualified", "missing_data_quality_note",
    "ungrounded", "thin_key_details", "missing_required_family_signal",
})

# Engine-native reason string -> canonical taxonomy code. Anything not listed (and not already a
# canonical code) is passed through verbatim so nothing is silently miscategorized.
_REASON_MAP = {
    # summary engine (source_local_summary: validate_advisory / generate_advisory)
    "format_invalid": "invalid_format",
    "noncanonical_shape": "invalid_format",
    "invalid_response": "invalid_format",
    "empty_response": "model_unavailable",
    "timeout": "model_timeout",
    "ollama_unavailable": "model_unavailable",
    "missing_source_record": "unsupported_claim",
    # graph vetting (source_note_graph.vet_candidate) — coarse buckets: validate_vet collapses
    # low-confidence / off-enum type / unknown tag / duplicate into a single "rejected".
    "invalid_json": "invalid_format",
    "rejected": "weak_basis",
    # metadata_conflict / unknown_tag / unsupported_claim / unknown_relationship_type /
    # duplicate_review_only / weak_basis are already canonical.
}


def normalize_reason(reason: str) -> str:
    """Map an engine-native reason string to the canonical taxonomy (verbatim if already canonical)."""
    r = str(reason or "").strip()
    if r in REJECT_REASONS:
        return r
    if r.startswith("ollama:"):
        return "model_timeout" if "timeout" in r else "model_unavailable"
    if r.startswith(("tags:", "block:")):
        return "invalid_format"
    return _REASON_MAP.get(r, r)


def merge_reasons(*reason_dicts: dict[str, int] | None) -> dict[str, int]:
    """Aggregate one or more {reason: count} dicts into a single canonical-code histogram."""
    out: dict[str, int] = {}
    for d in reason_dicts:
        for reason, n in (d or {}).items():
            out[normalize_reason(reason)] = out.get(normalize_reason(reason), 0) + int(n)
    return dict(sorted(out.items()))


# --- Model observability -----------------------------------------------------------------------
class ObservabilityRecorder:
    """Accumulates Ollama call metrics across every enrichment sub-workflow in one run."""

    def __init__(self) -> None:
        self.calls = 0
        self.successes = 0
        self.failures = 0
        self.timeouts = 0
        self.latencies_ms: list[int] = []

    def snapshot(self, *, model: str, model_match: str | None = None) -> dict[str, Any]:
        lat = self.latencies_ms
        return {
            "ollama_calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "latency_ms_total": sum(lat),
            "latency_ms_max": max(lat) if lat else 0,
            "latency_ms_avg": round(sum(lat) / len(lat)) if lat else 0,
            "model": model,
            "model_match": model_match,
            # The generate_text/generate_json client seam discards Ollama eval counts, so token
            # accounting is unavailable here — reported null rather than fabricated.
            "tokens": None,
        }


class ObservableClient:
    """Passthrough wrapper around an ``OllamaChatClient``: counts calls, times latency, classifies
    failures. Proxies ``.model``/``.base_url`` and ``generate_text``/``generate_json`` so the existing
    Phase 10B/10G engines use it unchanged via their ``client_factory`` seam."""

    def __init__(self, inner: Any, recorder: ObservabilityRecorder) -> None:
        self._inner = inner
        self._rec = recorder

    @property
    def model(self) -> Any:
        return self._inner.model

    @property
    def base_url(self) -> Any:
        return getattr(self._inner, "base_url", None)

    def _timed(self, fn: Callable[..., str], **kwargs: Any) -> str:
        from hb_assistant.construction.classification.client import OllamaUnavailable
        self._rec.calls += 1
        t0 = time.perf_counter()
        try:
            out = fn(**kwargs)
        except OllamaUnavailable as exc:
            self._rec.failures += 1
            if "timeout" in str(exc):
                self._rec.timeouts += 1
            raise
        finally:
            self._rec.latencies_ms.append(int((time.perf_counter() - t0) * 1000))
        self._rec.successes += 1
        return out

    def generate_text(self, *, system: str, prompt: str) -> str:
        return self._timed(self._inner.generate_text, system=system, prompt=prompt)

    def generate_json(self, *, system: str, prompt: str) -> str:
        return self._timed(self._inner.generate_json, system=system, prompt=prompt)


# --- Count-only safe evidence ------------------------------------------------------------------
def _sub(safe: dict[str, Any], key: str) -> dict[str, Any]:
    v = safe.get(key)
    return v if isinstance(v, dict) else {}


def render_enrichment_report(safe: dict[str, Any]) -> str:
    """Whitelist renderer: reads ONLY known count keys, so sensitive strings stuffed into unknown
    keys can never leak. Mirrors the Phase 10I report guarantee."""
    def g(k: str) -> Any:
        return safe.get(k, "n/a")

    def dist(d: dict[str, Any] | None) -> str:
        return ", ".join(f"{k}: {v}" for k, v in sorted((d or {}).items())) if isinstance(d, dict) \
            else "none"

    summ, tags, back, obs = (_sub(safe, k) for k in ("summaries", "tags", "backlinks", "observability"))
    rev = _sub(safe, "review")
    inv = _sub(safe, "invariants")
    lines = [
        "# Phase 10J — Local Enrichment Workflow — Review Report (safe / count-only)",
        "",
        f"- mode: {g('mode')}",
        f"- model: {g('model')}",
        f"- modes_run: {', '.join(safe.get('modes_run') or []) or 'none'}",
        f"- project_number: {g('project_number')}",
        "",
        "## Summaries",
        f"- available: {summ.get('cards_available', 'n/a')}, "
        f"eligible: {summ.get('cards_eligible', 'n/a')}, "
        f"attempted: {summ.get('cards_attempted', 'n/a')}, "
        f"truncated: {summ.get('selection_truncated', 'n/a')}",
        f"- generated: {summ.get('summaries_generated', 'n/a')}, "
        f"rejected: {summ.get('summaries_rejected', 'n/a')}, "
        f"left_pending: {summ.get('cards_left_pending', 'n/a')}, "
        f"written: {summ.get('cards_written', 'n/a')}, "
        f"pending_to_generated: {summ.get('marker_transitions_pending_to_generated', 'n/a')}",
        f"- classifier_conflicts: {summ.get('classifier_conflicts', 'n/a')}",
        "",
        "## Tags",
        f"- cards_checked: {tags.get('cards_checked', 'n/a')}, "
        f"proposed: {tags.get('tags_proposed', 'n/a')}, applied: {tags.get('tags_applied', 'n/a')}, "
        f"cards_tagged: {tags.get('cards_tagged', 'n/a')}, failed: {tags.get('failed', 'n/a')}",
        "",
        "## Backlinks",
        f"- candidate_pairs: {back.get('candidate_pairs', 'n/a')}, "
        f"vetted: {back.get('vetted_pairs', 'n/a')}, approved: {back.get('approved_pairs', 'n/a')}, "
        f"applied: {back.get('relationships_applied', 'n/a')}, "
        f"reciprocal_links: {back.get('reciprocal_links_applied', 'n/a')}",
        f"- duplicate_review_candidates (review-only): {back.get('duplicate_review_candidates', 'n/a')}",
        f"- backlink_integrity_passed: {back.get('backlink_integrity_passed', 'n/a')} "
        f"(verified={back.get('backlinks_verified', 'n/a')})",
        "",
        "## Review Surfaces (Phase 10I)",
        f"- cards_checked: {rev.get('cards_checked', 'n/a')}, "
        f"duplicate_review_pairs: {rev.get('duplicate_review_pairs', 'n/a')}, "
        f"isolated_high_value_cards: {rev.get('isolated_high_value_cards', 'n/a')}",
        "",
        "## Reject Reasons (canonical taxonomy)",
        f"- {dist(safe.get('reject_reasons'))}",
        "",
        "## Model Observability",
        f"- ollama_calls: {obs.get('ollama_calls', 'n/a')}, successes: {obs.get('successes', 'n/a')}, "
        f"failures: {obs.get('failures', 'n/a')}, timeouts: {obs.get('timeouts', 'n/a')}",
        f"- latency_ms (total/avg/max): {obs.get('latency_ms_total', 'n/a')}/"
        f"{obs.get('latency_ms_avg', 'n/a')}/{obs.get('latency_ms_max', 'n/a')}",
        f"- model: {obs.get('model', 'n/a')} (match={obs.get('model_match', 'n/a')}), "
        f"tokens: {obs.get('tokens', 'n/a')}",
        "",
        "## Invariants",
        f"- db_mutations: {inv.get('db_mutations', 'n/a')}, queue_delta: {inv.get('queue_delta', 'n/a')}, "
        f"created: {inv.get('created', 'n/a')}, deleted: {inv.get('deleted', 'n/a')}",
        "",
    ]
    return "\n".join(lines)


def write_enrichment_evidence(evidence_dir: str | Path, safe: dict[str, Any],
                              detail_rows: list[dict[str, Any]], *, phase: str = "phase10j") -> None:
    """Write the two-tier evidence bundle: committable count-only ``-safe.*`` + git-ignored detail."""
    ev = Path(evidence_dir)
    ev.mkdir(parents=True, exist_ok=True)
    (ev / f"{phase}-enrichment-summary-safe.json").write_text(
        json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
    (ev / f"{phase}-enrichment-report-safe.md").write_text(
        render_enrichment_report(safe), encoding="utf-8")
    ls = ev / "local-sensitive"
    ls.mkdir(parents=True, exist_ok=True)
    (ls / f"{phase}-enrichment-detail-local-sensitive.json").write_text(
        json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
