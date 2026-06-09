"""Phase 10 model-routing candidate — optional local-only daily-brief intelligence enrichment.

A **narrow, advisory** layer (v1) on top of the deterministic ``daily_brief_action_candidates`` set.
It uses the model router to pick the local profile for ``daily_brief_synthesis_quality`` and the
reusable :class:`StructuredOutputClient` to produce a compact, source-linked executive intelligence
object with exactly these sections:

* executive catch-up (short narrative)
* top priorities
* open loops
* waiting on me  /  waiting on others
* meeting prep
* project / Procore risk

Hard rules (fail-closed, advisory-only):

* The deterministic brief stays authoritative — this never replaces candidate generation.
* **Every bullet must cite ≥1 existing candidate ID.** Bullets are filtered to the intersection of
  their cited ``source_ids`` with the known candidate IDs; bullets that cite nothing real are
  dropped. If nothing survives, enrichment is withheld.
* If the model is unavailable / JSON-invalid / schema-invalid / redaction-failing, enrichment is
  withheld and the caller falls back to the deterministic brief.
* No raw prompt/response is persisted or returned (receipts are hash-only; default no DB write).
* Input is the already-redacted candidate read model (safe fields only), so the adapter is
  raw-safe by construction; ``allow_raw`` is reserved and does not widen what the model sees here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator

from .model_eval_metrics import compute_usefulness, scan_text_for_forbidden
from .model_router import RouteResult, route_task_family
from .models import LocalModelProfile, LocalModelProfiles
from .provider import resolve_local_model_client
from .structured_output import GenerationBackend, StructuredOutputClient

_TASK_FAMILY = "daily_brief_synthesis_quality"
_TASK_TYPE = "daily_brief_intelligence"
_DEFAULT_PROFILE_ID = "brief_synthesis"

_MAX_TEXT = 500
_MAX_CODE = 48
_MAX_BULLETS = 12
_MAX_NARRATIVE = 7

#: The bullet sections that MUST be source-linked (executive_catchup is narrative prose).
_BULLET_SECTIONS = (
    "top_priorities",
    "open_loops",
    "waiting_on_me",
    "waiting_on_others",
    "meeting_prep",
    "project_risk",
)


def _clamp(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


class IntelBullet(BaseModel):
    """A single advisory bullet that must cite existing candidate IDs."""

    text: str
    source_ids: list[str] = []
    confidence: float = 0.5
    reason_code: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("text")
    @classmethod
    def _v_text(cls, v: object) -> str:
        return _clamp(v, _MAX_TEXT)

    @field_validator("reason_code")
    @classmethod
    def _v_reason(cls, v: object) -> str:
        return _clamp(v, _MAX_CODE)

    @field_validator("source_ids", mode="before")
    @classmethod
    def _v_sources(cls, v: object) -> list[str]:
        # `mode="before"` so a stray scalar (e.g. a single id as a bare string) is coerced rather
        # than failing list-type validation outright.
        if isinstance(v, str):
            v = [v] if v.strip() else []
        if not isinstance(v, list):
            return []
        return [_clamp(s, _MAX_CODE) for s in v if _clamp(s, _MAX_CODE)][:_MAX_BULLETS]

    @field_validator("confidence")
    @classmethod
    def _v_conf(cls, v: object) -> float:
        try:
            return max(0.0, min(1.0, float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.5


class DailyBriefIntelligence(BaseModel):
    """The narrow v1 advisory intelligence object (six source-linked sections + catch-up)."""

    executive_catchup: list[str] = []
    top_priorities: list[IntelBullet] = []
    open_loops: list[IntelBullet] = []
    waiting_on_me: list[IntelBullet] = []
    waiting_on_others: list[IntelBullet] = []
    meeting_prep: list[IntelBullet] = []
    project_risk: list[IntelBullet] = []

    model_config = {"extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _coerce_top_level(cls, v: object) -> object:
        # Conservative top-level coercion: a 12B model in JSON mode sometimes returns a bare array of
        # bullets, or wraps the object under a single non-schema key (e.g. {"intelligence": {...}}).
        # Reshape those into the expected object WITHOUT inventing content — the source-link filter
        # and redaction scan downstream still enforce safety (unsourced/unsafe bullets are dropped).
        if isinstance(v, list):
            return {"top_priorities": v}
        if isinstance(v, dict):
            known = set(cls.model_fields)
            if v and not (known & set(v.keys())) and len(v) == 1:
                inner = next(iter(v.values()))
                if isinstance(inner, dict):
                    return inner
                if isinstance(inner, list):
                    return {"top_priorities": inner}
        return v

    @field_validator("executive_catchup", mode="before")
    @classmethod
    def _v_catchup(cls, v: object) -> list[str]:
        # `mode="before"` so a prose string (the common 12B behavior — it returns one narrative
        # paragraph instead of a list) is wrapped into a single-element list rather than failing
        # list-type validation and sinking the whole object as schema_invalid.
        if isinstance(v, str):
            v = [v] if v.strip() else []
        if not isinstance(v, list):
            return []
        return [_clamp(s, _MAX_TEXT) for s in v if _clamp(s, _MAX_TEXT)][:_MAX_NARRATIVE]

    @field_validator(*_BULLET_SECTIONS, mode="before")
    @classmethod
    def _coerce_bullets(cls, v: object) -> list[Any]:
        # Resilient coercion: a 12B model often emits bullets as bare strings or dicts keyed
        # ``summary``/``title`` instead of ``text``. Rather than fail the whole brief on one stray
        # item, normalize each into a ``{text: ...}`` dict and DROP items with no usable text. The
        # source-link filter and redaction scan downstream still enforce safety.
        if not isinstance(v, list):
            return []
        out: list[Any] = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    out.append({"text": text})
            elif isinstance(item, dict):
                text = str(
                    item.get("text") or item.get("summary") or item.get("title") or ""
                ).strip()
                if text:
                    merged = dict(item)
                    merged["text"] = text
                    out.append(merged)
            if len(out) >= _MAX_BULLETS:
                break
        return out


@dataclass
class DailyBriefIntelligenceResult:
    """Outcome of an enrichment attempt (advisory; receipt is hash-only; no raw retained).

    Profile reporting is deliberately unambiguous (Phase 10 remediation): the **route-selected**
    profile (what the router chose for the task family) is reported separately from the
    **terminal/generation** profile (what actually produced or last-attempted the output, which can
    differ when :class:`StructuredOutputClient` falls back). ``profile_id`` is retained for backwards
    compatibility and equals ``terminal_profile_id``.
    """

    status: str
    enriched: bool
    withheld_reason: Optional[str]
    profile_id: str
    model_name: str
    schema_valid: bool
    fallback_used: bool
    attempts: int
    latency_ms: int
    intelligence: Optional[dict[str, Any]]
    # -- explicit routing/reporting contract --------------------------------------------------
    route_selected_profile: str = ""
    route_model_name: str = ""
    route_reason_code: str = ""
    generation_profile_id: str = ""
    terminal_profile_id: str = ""
    fallback_chain: list[str] = field(default_factory=list)
    models_attempted: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # -- candidate availability / dry-run semantics (Phase 10 remediation) --------------------
    candidate_count: int = 0
    candidate_freshness: str = ""
    candidate_availability: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    would_write_receipt: Optional[dict[str, Any]] = None

    def safe_payload(self) -> dict[str, Any]:
        """Surfaceable, raw-safe payload (no raw prompt/response)."""
        return {
            "status": self.status,
            "enriched": self.enriched,
            "withheld_reason": self.withheld_reason,
            # backwards-compatible terminal profile (== terminal_profile_id):
            "profile_id": self.profile_id,
            "model_name": self.model_name,
            "schema_valid": self.schema_valid,
            "fallback_used": self.fallback_used,
            "latency_ms": self.latency_ms,
            # explicit, unambiguous routing/reporting fields:
            "route_selected_profile": self.route_selected_profile,
            "route_model_name": self.route_model_name,
            "route_reason_code": self.route_reason_code,
            "generation_profile_id": self.generation_profile_id,
            "terminal_profile_id": self.terminal_profile_id,
            "fallback_chain": list(self.fallback_chain),
            "models_attempted": list(self.models_attempted),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            # candidate availability / dry-run semantics:
            "candidate_count": self.candidate_count,
            "candidate_freshness": self.candidate_freshness,
            "candidate_availability": self.candidate_availability,
            "intelligence": self.intelligence,
            "metrics": self.metrics,
        }


_SYSTEM_PROMPT = (
    "You are the chief of staff for a senior construction executive. You receive a redacted list of "
    "already-extracted daily-brief action candidates (each with a stable id, section, redacted "
    "title, project, confidence, and recommended next action). Produce a concise, decision-ready "
    "advisory intelligence object as JSON ONLY, matching the schema. Rules:\n"
    "- Cite candidate ids in source_ids for EVERY bullet, using ONLY the ids provided. Never invent "
    "an id, name, amount, date, email, URL, or token.\n"
    "- executive_catchup: 2-5 short plain-English sentences on what matters today.\n"
    "- top_priorities: the few genuinely most important items.\n"
    "- open_loops: things still in flight.\n"
    "- waiting_on_me vs waiting_on_others: split who owes the next move.\n"
    "- meeting_prep: meetings worth preparing, with why/prep.\n"
    "- project_risk: aging/overdue project or Procore signals.\n"
    "- Each bullet has text, source_ids (>=1 real id), confidence (0..1), reason_code.\n"
    "Return ONLY a single JSON OBJECT (not an array) with these top-level keys: executive_catchup, "
    "top_priorities, open_loops, waiting_on_me, waiting_on_others, meeting_prep, project_risk. "
    'Example bullet: {"text": "...", "source_ids": ["c1"], "confidence": 0.8, "reason_code": "due_today"}.'
)


def _candidate_view(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Project candidates into the compact model view with short citeable aliases (c1, c2, ...).

    A 12B model reliably copies a short token like ``c3`` but frequently garbles a 37-char canonical
    id such as ``dbac-<32 hex>`` — which silently drops every bullet at the source-link filter. We
    therefore show the model only the short alias and map it back to the canonical
    ``daily_brief_action_candidate_id`` internally. Returns ``(view, alias_to_canonical)``.
    """
    view: list[dict[str, Any]] = []
    alias_to_canonical: dict[str, str] = {}
    for i, c in enumerate(candidates, start=1):
        canonical = str(c.get("daily_brief_action_candidate_id") or "")
        if not canonical:
            continue
        alias = f"c{i}"
        alias_to_canonical[alias] = canonical
        view.append(
            {
                "id": alias,
                "section": c.get("section"),
                "title": c.get("title_redacted"),
                "project": c.get("project_key"),
                "confidence": c.get("confidence"),
                "recommended_next_action": c.get("recommended_next_action"),
            }
        )
    return view, alias_to_canonical


def _select_profile(profiles: LocalModelProfiles, profile_id: str) -> Optional[LocalModelProfile]:
    return next((p for p in profiles.profiles if p.profile_id == profile_id), None)


def _resolve_source_id(
    sid: str, alias_to_canonical: dict[str, str], canonical_ids: set[str]
) -> tuple[Optional[str], bool]:
    """Map a cited id to a canonical candidate id. Returns (canonical_or_None, used_alias)."""
    if sid in alias_to_canonical:
        return alias_to_canonical[sid], True
    if sid in canonical_ids:
        return sid, False
    return None, False


def _filter_source_links(
    validated: dict[str, Any],
    alias_to_canonical: dict[str, str],
    canonical_ids: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep only bullets citing a real candidate (by alias or canonical id); map cites to canonical.

    Returns ``(filtered, stats)`` where ``stats`` carries safe source-link diagnostics
    (model_bullets_seen, bullets_kept, bullets_dropped, unknown_source_ids_count, alias_mapping_used).
    """
    filtered: dict[str, Any] = {"executive_catchup": list(validated.get("executive_catchup") or [])}
    kept = 0
    dropped = 0
    seen = 0
    unknown = 0
    alias_used = False
    for section in _BULLET_SECTIONS:
        out: list[dict[str, Any]] = []
        for bullet in validated.get(section) or []:
            seen += 1
            real: list[str] = []
            for sid in bullet.get("source_ids") or []:
                canonical, used_alias = _resolve_source_id(sid, alias_to_canonical, canonical_ids)
                if canonical is None:
                    unknown += 1
                    continue
                alias_used = alias_used or used_alias
                if canonical not in real:
                    real.append(canonical)
            if real:
                bullet = dict(bullet)
                bullet["source_ids"] = real
                out.append(bullet)
                kept += 1
            else:
                dropped += 1
        filtered[section] = out
    stats = {
        "model_bullets_seen": seen,
        "bullets_kept": kept,
        "bullets_dropped": dropped,
        "unknown_source_ids_count": unknown,
        "alias_mapping_used": alias_used,
        "allowed_candidate_count": len(canonical_ids),
    }
    return filtered, stats


@dataclass
class _RouteCtx:
    """The route decision context, kept separate from the terminal generation profile."""

    selected_profile: str = ""
    model_name: str = ""
    reason_code: str = ""
    fallback_chain: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def _seed_chain(profiles: LocalModelProfiles, primary: str) -> list[str]:
    """Best-effort local-only fallback chain for an injected-backend path (no router call)."""
    chain = [primary]
    single = profiles.fallbacks.get(primary)
    if single and single not in chain:
        chain.append(single)
    return chain


def _models_attempted(route: _RouteCtx, terminal_model_name: str) -> list[str]:
    """Ordered, de-duplicated model names that were (or would be) attempted."""
    out: list[str] = []
    for name in (route.model_name, terminal_model_name):
        if name and name not in out:
            out.append(name)
    return out


def _reporting_warnings(
    *, route: _RouteCtx, terminal_profile_id: str, fallback_used: bool, status: str, enriched: bool
) -> list[str]:
    """Operator-meaningful, raw-safe warnings describing route vs terminal profile divergence."""
    warnings: list[str] = []
    if fallback_used:
        warnings.append("fallback_profile_attempted")
    if (
        route.selected_profile
        and terminal_profile_id
        and terminal_profile_id != route.selected_profile
    ):
        warnings.append("terminal_profile_differs_from_route")
    if status == "schema_invalid":
        warnings.append("schema_invalid_after_repair")
    if not enriched:
        warnings.append("deterministic_fallback_preserved")
    return warnings


#: Map a closed run/withhold status to a bounded, raw-safe schema-error category code.
_SCHEMA_ERROR_CATEGORIES = {
    "ok": "none",
    "schema_invalid": "schema_invalid",
    "unavailable": "model_unavailable",
    "model_unavailable": "model_unavailable",
    "timeout": "model_timeout",
    "failed": "generation_failed",
    "blocked": "profile_blocked",
    "no_candidates": "no_candidates",
    "redaction_failed": "redaction_failed",
    "no_source_linked_bullets": "no_source_linked_bullets",
    "profile_error": "profile_error",
}


def _schema_error_category(status: str) -> str:
    return _SCHEMA_ERROR_CATEGORIES.get(status, "unknown")


def _withheld(
    *,
    status: str,
    reason: str,
    route: _RouteCtx,
    terminal_profile_id: str,
    terminal_model_name: str,
    result: Any = None,
    extra_metrics: Optional[dict[str, Any]] = None,
) -> DailyBriefIntelligenceResult:
    fallback_used = bool(getattr(result, "fallback_used", False))
    attempts = int(getattr(result, "attempts", 0))
    warnings = _reporting_warnings(
        route=route,
        terminal_profile_id=terminal_profile_id,
        fallback_used=fallback_used,
        status=status,
        enriched=False,
    )
    metrics: dict[str, Any] = {
        "withheld": True,
        "reason": reason,
        # bounded, raw-safe schema/repair diagnostics (no raw model error text):
        "schema_error_category": _schema_error_category(status),
        "attempts": attempts,
        "repair_attempted": attempts > 1,
        "fallback_used": fallback_used,
        "terminal_profile_id": terminal_profile_id,
    }
    if extra_metrics:
        metrics.update(extra_metrics)
    return DailyBriefIntelligenceResult(
        status=status,
        enriched=False,
        withheld_reason=reason,
        profile_id=terminal_profile_id,
        model_name=terminal_model_name,
        schema_valid=bool(getattr(result, "schema_valid", False)),
        fallback_used=fallback_used,
        attempts=attempts,
        latency_ms=int(getattr(result, "latency_ms", 0)),
        intelligence=None,
        route_selected_profile=route.selected_profile,
        route_model_name=route.model_name,
        route_reason_code=route.reason_code,
        generation_profile_id=terminal_profile_id,
        terminal_profile_id=terminal_profile_id,
        fallback_chain=list(route.fallback_chain),
        models_attempted=_models_attempted(route, terminal_model_name),
        blockers=[reason] + [b for b in route.blockers if b != reason],
        warnings=warnings,
        metrics=metrics,
        would_write_receipt=getattr(result, "would_write_receipt", None),
    )


#: Candidate generation modes (operator-visible): standalone intelligence is always read-only;
#: daily-run reflects whether the generation stages ran in dry-run or were applied.
_GENERATION_MODES = ("read_only", "pipeline_dry_run", "pipeline_apply")


def _candidate_availability(
    candidates: list[dict[str, Any]], brief_date: Optional[str], generation_mode: str
) -> tuple[dict[str, Any], list[str]]:
    """Compute operator-visible candidate availability + dry-run dependency warnings (raw-safe).

    Standalone intelligence enriches only already-persisted ``daily_brief_action_candidates``; a
    dry-run daily-run discovers candidates but does not persist them, so fresh candidates require an
    apply. This surfaces that dependency instead of silently enriching an empty/stale set.
    """
    count = len(candidates)
    created_dates = sorted(
        str(c.get("created_utc") or "")[:10] for c in candidates if c.get("created_utc")
    )
    if count == 0:
        freshness = "none"
    elif brief_date and created_dates and created_dates[-1] >= brief_date:
        freshness = "current"
    else:
        freshness = "preexisting"

    mode = generation_mode if generation_mode in _GENERATION_MODES else "read_only"
    requires_apply = mode in ("read_only", "pipeline_dry_run")
    availability = {
        "candidate_count": count,
        "candidate_brief_date": brief_date,
        "candidate_source": "daily_brief_action_candidates",
        "candidate_generation_mode": mode,
        "candidate_freshness": freshness,
        "requires_apply_for_fresh_candidates": requires_apply,
        "dry_run_candidate_warning": mode in ("read_only", "pipeline_dry_run"),
    }
    warnings: list[str] = []
    if count == 0:
        warnings.append("no_persisted_candidates_for_date")
        warnings.append("requires_daily_run_apply_to_generate_candidates")
    if mode == "read_only" and count > 0:
        warnings.append("standalone_reads_preexisting_candidates_only")
    if mode == "pipeline_dry_run":
        warnings.append("dry_run_did_not_persist_new_candidates")
        if count > 0:
            warnings.append("intelligence_reflects_preexisting_candidates")
    if freshness == "preexisting" and brief_date:
        warnings.append("candidate_rows_predate_requested_brief_date")
    return availability, warnings


def build_daily_brief_intelligence(
    *,
    candidates: list[dict[str, Any]],
    profiles: LocalModelProfiles,
    routing: Any = None,
    present_models: set[str] | None = None,
    backend: Optional[GenerationBackend] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    allow_raw: bool = False,
    store: Optional[Any] = None,
    brief_date: Optional[str] = None,
    generation_mode: str = "read_only",
) -> DailyBriefIntelligenceResult:
    """Produce advisory daily-brief intelligence, or withhold (fail-closed) to the deterministic brief.

    ``backend`` is injected for offline tests; when omitted a real local client is resolved for the
    routed profile (and enrichment is withheld if none is available). ``store`` is used only to write
    a hash-only receipt when ``dry_run`` is False; default is no DB write. ``brief_date`` and
    ``generation_mode`` drive operator-visible candidate-availability diagnostics (they never change
    what the model sees).
    """
    result = _run_intelligence(
        candidates=candidates,
        profiles=profiles,
        routing=routing,
        present_models=present_models,
        backend=backend,
        profile_id=profile_id,
        dry_run=dry_run,
        allow_raw=allow_raw,
        store=store,
    )
    availability, avail_warnings = _candidate_availability(candidates, brief_date, generation_mode)
    result.candidate_count = availability["candidate_count"]
    result.candidate_freshness = availability["candidate_freshness"]
    result.candidate_availability = availability
    for w in avail_warnings:
        if w not in result.warnings:
            result.warnings.append(w)
    return result


def _run_intelligence(
    *,
    candidates: list[dict[str, Any]],
    profiles: LocalModelProfiles,
    routing: Any = None,
    present_models: set[str] | None = None,
    backend: Optional[GenerationBackend] = None,
    profile_id: Optional[str] = None,
    dry_run: bool = True,
    allow_raw: bool = False,
    store: Optional[Any] = None,
) -> DailyBriefIntelligenceResult:
    """Core enrichment path (route → generate → filter → redact). See the public wrapper above."""
    allowed_ids = {
        str(c.get("daily_brief_action_candidate_id"))
        for c in candidates
        if c.get("daily_brief_action_candidate_id")
    }
    chosen_profile_id = profile_id or _DEFAULT_PROFILE_ID
    route_ctx = _RouteCtx(selected_profile=chosen_profile_id)
    if not allowed_ids:
        return _withheld(
            status="no_candidates",
            reason="no_candidates",
            route=route_ctx,
            terminal_profile_id=chosen_profile_id,
            terminal_model_name="",
        )

    # Resolve the profile + backend. The router decides the route-selected profile (reported
    # separately from the terminal generation profile). When a backend is injected (offline/tests)
    # the route is the chosen profile and the chain comes from the profile seed.
    if backend is None:
        route: RouteResult = route_task_family(
            _TASK_FAMILY, profiles=profiles, routing=routing, present_models=present_models
        )
        route_ctx = _RouteCtx(
            selected_profile=route.selected_profile or chosen_profile_id,
            model_name=route.model_name or "",
            reason_code=route.reason_code or "",
            fallback_chain=list(route.fallback_chain),
            blockers=list(route.blockers),
        )
        if route.blocked or not route.selected_profile:
            return _withheld(
                status="model_unavailable",
                reason=route.reason_code or "model_unavailable",
                route=route_ctx,
                terminal_profile_id=route.selected_profile or chosen_profile_id,
                terminal_model_name=route.model_name or "",
            )
        chosen_profile_id = route.selected_profile
        client, _model_name, why = resolve_local_model_client(
            profile_id=chosen_profile_id, profiles=profiles
        )
        if client is None:
            return _withheld(
                status="model_unavailable",
                reason=why or "live_model_client_missing",
                route=route_ctx,
                terminal_profile_id=chosen_profile_id,
                terminal_model_name=route.model_name or "",
            )
        backend = client
    else:
        injected = _select_profile(profiles, chosen_profile_id)
        route_ctx = _RouteCtx(
            selected_profile=chosen_profile_id,
            model_name=injected.model_name if injected else "",
            reason_code="injected_backend",
            fallback_chain=_seed_chain(profiles, chosen_profile_id),
        )

    profile = _select_profile(profiles, chosen_profile_id)
    if profile is None:
        return _withheld(
            status="profile_error",
            reason="profile_not_found",
            route=route_ctx,
            terminal_profile_id=chosen_profile_id,
            terminal_model_name="",
        )

    view, alias_to_canonical = _candidate_view(candidates)
    input_context = json.dumps(view, sort_keys=True, default=str)
    prompt = (
        "Produce the advisory intelligence JSON for these redacted daily-brief candidates. Cite only "
        "these short ids (e.g. c1, c2) in source_ids; never invent an id.\n\nCANDIDATES:\n"
        + input_context
    )

    result = StructuredOutputClient().run(
        schema=DailyBriefIntelligence,
        profile=profile,
        profiles=profiles,
        system=_SYSTEM_PROMPT,
        prompt=prompt,
        input_context=input_context,
        task_type=_TASK_TYPE,
        backend=backend,
        store=store if (store is not None and not dry_run) else None,
        dry_run=dry_run,
    )

    if result.status != "ok" or result.validated is None:
        return _withheld(
            status=result.status,
            reason=result.error_redacted or result.status,
            route=route_ctx,
            terminal_profile_id=result.profile_id,
            terminal_model_name=result.model_name,
            result=result,
        )

    filtered, link_stats = _filter_source_links(result.validated, alias_to_canonical, allowed_ids)
    kept = int(link_stats["bullets_kept"])

    findings = scan_text_for_forbidden(json.dumps(filtered, default=str))
    if findings:
        return _withheld(
            status="redaction_failed",
            reason="redaction_failed:" + ",".join(findings),
            route=route_ctx,
            terminal_profile_id=result.profile_id,
            terminal_model_name=result.model_name,
            result=result,
            extra_metrics=link_stats,
        )

    if kept == 0:
        return _withheld(
            status="no_source_linked_bullets",
            reason="no_source_linked_bullets",
            route=route_ctx,
            terminal_profile_id=result.profile_id,
            terminal_model_name=result.model_name,
            result=result,
            extra_metrics=link_stats,
        )

    sections_populated = [s for s in _BULLET_SECTIONS if filtered.get(s)]
    metrics = {
        **link_stats,
        "source_link_coverage": 1.0,  # by construction: every kept bullet cites a real candidate
        "sections_populated": sections_populated,
        "waiting_on_me": len(filtered.get("waiting_on_me") or []),
        "waiting_on_others": len(filtered.get("waiting_on_others") or []),
        "meeting_prep": len(filtered.get("meeting_prep") or []),
        "top_priorities": len(filtered.get("top_priorities") or []),
        "usefulness_score": compute_usefulness(
            filtered, expected_sections=["executive_catchup", *_BULLET_SECTIONS]
        ),
        "raw_allowed": bool(allow_raw),
    }

    return DailyBriefIntelligenceResult(
        status="ok",
        enriched=True,
        withheld_reason=None,
        profile_id=result.profile_id,
        model_name=result.model_name,
        schema_valid=result.schema_valid,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
        latency_ms=result.latency_ms,
        intelligence=filtered,
        route_selected_profile=route_ctx.selected_profile,
        route_model_name=route_ctx.model_name,
        route_reason_code=route_ctx.reason_code,
        generation_profile_id=result.profile_id,
        terminal_profile_id=result.profile_id,
        fallback_chain=list(route_ctx.fallback_chain),
        models_attempted=_models_attempted(route_ctx, result.model_name),
        warnings=_reporting_warnings(
            route=route_ctx,
            terminal_profile_id=result.profile_id,
            fallback_used=result.fallback_used,
            status="ok",
            enriched=True,
        ),
        metrics=metrics,
        would_write_receipt=result.would_write_receipt,
    )
