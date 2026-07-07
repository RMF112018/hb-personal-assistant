"""N8C-17 deterministic, read-only workflow context-assembly handlers.

Four bounded handlers that turn a routed ``WorkflowRequest`` into named ``workflow_sections`` of BOUNDED,
whitelisted artifact references drawn from EXISTING N8C read repositories:

  * ``assemble_daily_brief_context`` — recent items across packs/projections/packets/drafts/decisions/
    preferences/open-loops/memory, split trusted vs candidate + open loops + review-needed.
  * ``assemble_meeting_prep`` — supplied artifacts + type/project-filtered context, prior decisions/
    preferences, open loops, questions to resolve.
  * ``assemble_project_intelligence_context`` — project-scoped claims/decisions/preferences/open-loops +
    INDEXED source-FILE references (metadata only — never a live file read, never a snippet body).
  * ``assemble_open_loop_triage`` — active / candidate / blocked-or-waiting / review-needed / stale-or-
    superseded open loops + related decisions.

Hard boundaries (same as the router that delegates here):
  * READ-ONLY — only repository READ methods via the router's guarded accessors. No writer/build/apply, no
    source scan/reindex, no source-card gen, no enrichment/qwen worker, no live source-file read.
  * NO PERSISTENCE, NO EXECUTION, NO LLM, NO NETWORK. Nothing is staged, scheduled, sent, or created.
  * BOUNDED — only whitelisted SCALAR metadata is copied (ids, types, status, review labels, citation ids,
    source refs, root-relative paths, counts, timestamps). NEVER ``section_body``/``evidence_excerpt``/a
    ``*_json`` blob/a raw body/a full export/a search snippet.
  * CONSERVATIVE review classification — accepted/trusted → trusted; candidate/unreviewed/needs_review →
    candidate; rejected/not_required/superseded/stale → excluded; missing/unknown/contradictory → candidate
    (NEVER trusted). A review overlay (effective/review state) wins over a record's own status.
  * ``advisory_next_steps`` is advisory navigation/review guidance ONLY — never an execution instruction.
"""

from __future__ import annotations

from typing import Any

from .workflow_models import (
    MAX_CITATIONS,
    MAX_ITEMS,
    MAX_REVIEW_LABELS,
    MAX_SECTION_ITEMS,
    MAX_SELECTED_ARTIFACTS,
    MAX_SOURCE_REFS,
    STATUS_INSUFFICIENT_CONTEXT,
    STATUS_ROUTED,
    TARGET_ANSWER_DRAFTS,
    TARGET_CLAIMS,
    TARGET_CONTEXT_PACKS,
    TARGET_DECISION_MEMORY,
    TARGET_INTELLIGENCE_PROJECTIONS,
    TARGET_MEMORY,
    TARGET_OPEN_LOOPS,
    TARGET_RESEARCH_PACKETS,
    TARGET_REVIEW_QUEUE,
    WF_DAILY_BRIEF_CONTEXT,
    WF_MEETING_PREP,
    WF_OPEN_LOOP_TRIAGE,
    WF_PROJECT_INTELLIGENCE_CONTEXT,
    RoutingDecision,
    WorkflowRequest,
    bounded_metadata,
)
from .workflow_registry import get_spec
from .workflow_router import (
    _CITATION_WL,
    _CLAIM_WL,
    _DECISION_WL,
    _DRAFT_WL,
    _NODE_WL,
    _OPEN_LOOP_WL,
    _PACK_WL,
    _PACKET_WL,
    _PREFERENCE_WL,
    _PROJECTION_WL,
    _REVIEW_WL,
    _SOURCE_FILE_WL,
    _dedupe,
)

# -- conservative review-state classification (clarification #8) -----------------------------
TRUSTED = "trusted"
CANDIDATE = "candidate"
EXCLUDED = "excluded"

_TRUSTED_TOKENS = frozenset({"accepted", "operator_accepted", "trusted", "effective_support",
                             "supported", "approved"})
_EXCLUDED_TOKENS = frozenset({"rejected", "operator_rejected", "not_required", "superseded", "stale",
                              "obsolete", "excluded", "withdrawn"})
_CANDIDATE_TOKENS = frozenset({"candidate", "unreviewed", "needs_review", "deferred", "pending",
                               "in_review", "proposed"})

# Fields collected when copying a bounded source reference off any record (never a body/snippet).
_REF_COLLECT_WL = ("source_ref", "source_root_key", "rel_path", "source_rel_path", "note_rel_path",
                   "source_id")

_MAX_CITED_ARTIFACTS = 10  # cap explicit draft/packet citation reads per assembly (bounded I/O).


def _classify(rec: dict[str, Any]) -> str:
    """Classify a record as trusted/candidate/excluded. A review overlay (effective_state/review_state)
    wins over the record's own ``status``; anything unknown/missing/contradictory → candidate (never
    trusted)."""
    overlay = [str(rec[f]).lower() for f in ("effective_state", "review_state") if rec.get(f)]
    toks = set(overlay) if overlay else ({str(rec["status"]).lower()} if rec.get("status") else set())
    if toks & _EXCLUDED_TOKENS:
        return EXCLUDED
    if (toks & _TRUSTED_TOKENS) and not (toks & _CANDIDATE_TOKENS):
        return TRUSTED
    return CANDIDATE


def _labels(*record_lists: list[dict[str, Any]]) -> list[str]:
    """Distinct review/effective-state labels across records (order-preserving, bounded)."""
    out: list[str] = []
    for records in record_lists:
        for rec in records:
            for f in ("review_state", "effective_state"):
                v = rec.get(f)
                if v:
                    out.append(str(v))
    return _dedupe(out)[:MAX_REVIEW_LABELS]


def _refs(*record_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bounded source references collected off records (no extra reads, no bodies)."""
    out: list[dict[str, Any]] = []
    for records in record_lists:
        for rec in records:
            ref = bounded_metadata(rec, _REF_COLLECT_WL)
            if ref:
                out.append(ref)
    return _dedupe_dicts(out)[:MAX_SOURCE_REFS]


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order-preserving de-dup for small bounded dict lists (by sorted-items signature)."""
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        sig = tuple(sorted(it.items()))
        if sig not in seen:
            seen.add(sig)
            out.append(it)
    return out


def _bucket(router: Any, records: list[dict[str, Any]], target: str, kind: str, id_key: str,
            wl: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    """Split records into trusted/candidate/excluded bounded artifact-ref lists."""
    out: dict[str, list[dict[str, Any]]] = {TRUSTED: [], CANDIDATE: [], EXCLUDED: []}
    for rec in records:
        art = router._artifact(target, kind, str(rec.get(id_key) or ""), rec, wl)
        out[_classify(rec)].append(art)
    return out


def _merge_buckets(*buckets: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {TRUSTED: [], CANDIDATE: [], EXCLUDED: []}
    for b in buckets:
        for cls in (TRUSTED, CANDIDATE, EXCLUDED):
            out[cls].extend(b.get(cls, []))
    return out


def _cap(items: list[Any]) -> list[Any]:
    return items[:MAX_SECTION_ITEMS]


def _explicit_artifacts(router: Any, req: WorkflowRequest,
                        conn: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                            list[dict[str, Any]], list[str], list[str]]:
    """Resolve any supplied artifact ids (draft/packet/projection/context_pack/memory_node). Returns
    (artifact_refs, citations, source_refs, review_labels, warnings). A supplied-but-missing id yields a
    ``missing_<kind>`` warning (never a build). Citations are read ONLY for explicit draft/packet ids."""
    checks = (
        ("draft_id", TARGET_ANSWER_DRAFTS, "draft", router._get_draft, _DRAFT_WL),
        ("packet_id", TARGET_RESEARCH_PACKETS, "packet", router._get_packet, _PACKET_WL),
        ("projection_id", TARGET_INTELLIGENCE_PROJECTIONS, "projection", router._get_projection,
         _PROJECTION_WL),
        ("context_pack_id", TARGET_CONTEXT_PACKS, "context_pack", router._get_context_pack, _PACK_WL),
        ("memory_node_id", TARGET_MEMORY, "memory_node", router._get_memory_node, _NODE_WL),
    )
    arts: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    source_refs: list[dict[str, Any]] = []
    labels: list[str] = []
    warnings: list[str] = []
    for field_name, target, kind, getter, wl in checks:
        art_id = getattr(req, field_name)
        if not art_id:
            continue
        rec = getter(art_id, conn)
        if rec is None:
            warnings.append(f"missing_{kind}")
            continue
        arts.append(router._artifact(target, kind, art_id, rec, wl))
        if kind == "draft":
            d_labels, d_cits, d_refs, d_warns = router._inspect_draft(art_id, rec, conn)
            labels += d_labels
            citations += d_cits
            source_refs += d_refs
            warnings += d_warns
        elif kind == "packet":
            for cit in router._packet_citations(art_id, conn):
                citations.append(bounded_metadata(cit, _CITATION_WL))
                sref = bounded_metadata(cit, _REF_COLLECT_WL)
                if sref:
                    source_refs.append(sref)
            warnings += router._packet_warnings(rec)
    return arts, citations[:MAX_CITATIONS], source_refs, _dedupe(labels), warnings


def _missing_citation_warning(trusted_items: list[Any], citations: list[Any],
                              source_refs: list[Any]) -> list[str]:
    """Flag trusted content that carries no citation/source-ref backing (advisory data-quality signal)."""
    if trusted_items and not citations and not source_refs:
        return ["missing_citation_coverage"]
    return []


def _decision(wf_type: str, req: WorkflowRequest, primary: str, targets: list[str],
              reason: str) -> RoutingDecision:
    return RoutingDecision(wf_type, "explicit" if req.workflow_type else "keyword_fallback",
                           primary, list(targets), reason)


# ============================================================================================
# daily_brief_context
# ============================================================================================
def assemble_daily_brief_context(router: Any, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
    spec = get_spec(WF_DAILY_BRIEF_CONTEXT)
    limit = req.limit
    packs = router._list_context_packs(conn, limit=limit)
    projections = router._list_projections(conn, limit=limit)
    packets = router._list_research_packets(conn, limit=limit)
    drafts = router._list_drafts(conn, limit=limit)
    decisions = router._list_decisions(conn, limit=limit)
    preferences = router._list_preferences(conn, limit=limit)
    open_loops = router._list_open_loops(conn, limit=limit)
    nodes = router._list_nodes(conn, domain=req.domain, limit=limit)
    review_items = router._list_review_items(conn, limit=limit)

    merged = _merge_buckets(
        _bucket(router, packs, TARGET_CONTEXT_PACKS, "context_pack", "pack_id", _PACK_WL),
        _bucket(router, projections, TARGET_INTELLIGENCE_PROJECTIONS, "projection", "projection_id",
                _PROJECTION_WL),
        _bucket(router, packets, TARGET_RESEARCH_PACKETS, "packet", "packet_id", _PACKET_WL),
        _bucket(router, drafts, TARGET_ANSWER_DRAFTS, "draft", "draft_id", _DRAFT_WL),
        _bucket(router, decisions, TARGET_DECISION_MEMORY, "decision", "decision_id", _DECISION_WL),
        _bucket(router, preferences, TARGET_DECISION_MEMORY, "preference", "preference_id", _PREFERENCE_WL),
        _bucket(router, nodes, TARGET_MEMORY, "memory_node", "node_id", _NODE_WL),
    )
    open_loop_refs = [router._artifact(TARGET_OPEN_LOOPS, "open_loop", str(r.get("open_loop_id") or ""),
                                       r, _OPEN_LOOP_WL)
                      for r in open_loops if str(r.get("status") or "").lower() in ("open", "candidate")]
    review_needed = [router._artifact(TARGET_REVIEW_QUEUE, "review_item",
                                      str(r.get("review_item_id") or ""), r, _REVIEW_WL)
                     for r in review_items
                     if str(r.get("effective_state") or "").lower() in ("candidate",)
                     or str(r.get("review_state") or "").lower() in ("unreviewed", "needs_review")]

    sections = {
        "trusted_updates": _cap(merged[TRUSTED]),
        "candidate_updates": _cap(merged[CANDIDATE]),
        "open_loops": _cap(open_loop_refs),
        "review_needed": _cap(review_needed),
    }
    source_refs = _refs(decisions, preferences, packets, drafts, open_loops, nodes)
    review_labels = _labels(decisions, preferences, open_loops, review_items)
    risks = _caveats(candidate=merged[CANDIDATE], excluded=merged[EXCLUDED], review_needed=review_needed)
    warnings = _missing_citation_warning(merged[TRUSTED], [], source_refs)

    has_content = any(sections.values())
    status = STATUS_ROUTED if has_content else STATUS_INSUFFICIENT_CONTEXT
    advisory = ["Open the flagged candidate updates and review-needed items in the review queue to confirm "
                "them before relying on them.",
                "Inspect the citations behind any listed artifact via draft_review or "
                "decision_preference_lookup. This is context, not a final brief."]
    if not has_content:
        advisory = ["No recent context artifacts were found for the daily brief."]
    return {
        "routing_decision": _decision(WF_DAILY_BRIEF_CONTEXT, req, TARGET_CONTEXT_PACKS,
                                      list(spec.primary_targets),
                                      "assemble bounded recent-context sections (read-only; no brief built)"),
        "status": status,
        "selected_artifacts": (merged[TRUSTED] + merged[CANDIDATE] + open_loop_refs)[:MAX_SELECTED_ARTIFACTS],
        "trusted_items": _cap(merged[TRUSTED]),
        "candidate_items": _cap(merged[CANDIDATE]),
        "excluded_items": _cap(merged[EXCLUDED]),
        "source_refs": source_refs,
        "review_labels": review_labels,
        "risks_or_caveats": risks,
        "deferred_capabilities": list(spec.deferred_capabilities),
        "advisory_next_steps": advisory,
        "requires_operator_review": bool(merged[CANDIDATE] or review_needed),
        "warnings": warnings,
        "workflow_sections": sections,
    }


# ============================================================================================
# meeting_prep
# ============================================================================================
def assemble_meeting_prep(router: Any, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
    spec = get_spec(WF_MEETING_PREP)
    limit = req.limit
    explicit_arts, citations, ex_refs, ex_labels, warnings = _explicit_artifacts(router, req, conn)

    decisions = router._list_decisions(conn, limit=limit)
    preferences = router._list_preferences(conn, limit=limit)
    open_loops = router._list_open_loops(conn, limit=limit)

    ctx = _merge_buckets(
        _bucket(router, decisions, TARGET_DECISION_MEMORY, "decision", "decision_id", _DECISION_WL),
        _bucket(router, preferences, TARGET_DECISION_MEMORY, "preference", "preference_id", _PREFERENCE_WL),
    )
    # Explicit artifacts are context the operator chose — treated as trusted_context by selection.
    trusted_ctx = _cap(explicit_arts + ctx[TRUSTED])
    candidate_ctx = _cap(ctx[CANDIDATE])
    prior_decisions = _cap([router._artifact(TARGET_DECISION_MEMORY, "decision",
                                             str(r.get("decision_id") or ""), r, _DECISION_WL)
                            for r in decisions])
    known_preferences = _cap([router._artifact(TARGET_DECISION_MEMORY, "preference",
                                               str(r.get("preference_id") or ""), r, _PREFERENCE_WL)
                             for r in preferences])
    open_loop_refs = _cap([router._artifact(TARGET_OPEN_LOOPS, "open_loop",
                                            str(r.get("open_loop_id") or ""), r, _OPEN_LOOP_WL)
                          for r in open_loops
                          if str(r.get("status") or "").lower() in ("open", "candidate")])

    objective_echo = [{k: v for k, v in {
        "objective": req.objective, "meeting_title": req.meeting_title, "project_key": req.project_key,
        "attendee_count": len(req.attendee_names) or None,
        "attendee_org_count": len(req.attendee_orgs) or None,
    }.items() if v}]
    objective_echo = [d for d in objective_echo if d]
    questions = _questions_to_resolve(candidate_ctx, open_loop_refs, warnings)

    sections = {
        "meeting_objective": objective_echo,
        "trusted_context": trusted_ctx,
        "candidate_context": candidate_ctx,
        "prior_decisions": prior_decisions,
        "known_preferences": known_preferences,
        "open_loops": open_loop_refs,
        "questions_to_resolve": questions,
    }
    source_refs = _dedupe_dicts(ex_refs + _refs(decisions, preferences, open_loops))[:MAX_SOURCE_REFS]
    review_labels = _dedupe(ex_labels + _labels(decisions, preferences, open_loops))[:MAX_REVIEW_LABELS]
    risks = _caveats(candidate=candidate_ctx, excluded=ctx[EXCLUDED], review_needed=[])
    warnings = _dedupe(warnings + _missing_citation_warning(trusted_ctx, citations, source_refs))

    has_content = any(v for v in sections.values() if v is not objective_echo) or bool(explicit_arts)
    status = STATUS_ROUTED if has_content else STATUS_INSUFFICIENT_CONTEXT
    advisory = ["Confirm the candidate context and open loops in the review queue before the meeting.",
                "Inspect citations on any supplied draft or packet via draft_review. This is meeting "
                "context only, not an agenda or invitation."]
    return {
        "routing_decision": _decision(WF_MEETING_PREP, req, TARGET_DECISION_MEMORY,
                                      list(spec.primary_targets),
                                      "assemble bounded meeting-context sections (read-only; no invite/agenda)"),
        "status": status,
        "selected_artifacts": (explicit_arts + ctx[TRUSTED] + ctx[CANDIDATE])[:MAX_SELECTED_ARTIFACTS],
        "trusted_items": trusted_ctx,
        "candidate_items": candidate_ctx,
        "excluded_items": _cap(ctx[EXCLUDED]),
        "citations": citations[:MAX_CITATIONS],
        "source_refs": source_refs,
        "review_labels": review_labels,
        "risks_or_caveats": risks,
        "deferred_capabilities": list(spec.deferred_capabilities),
        "advisory_next_steps": advisory,
        "requires_operator_review": bool(candidate_ctx),
        "warnings": warnings,
        "workflow_sections": sections,
    }


# ============================================================================================
# project_intelligence_context
# ============================================================================================
def assemble_project_intelligence_context(router: Any, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
    spec = get_spec(WF_PROJECT_INTELLIGENCE_CONTEXT)
    limit = req.limit
    claims = router._list_claims(conn, limit=limit)
    decisions = router._list_decisions(conn, limit=limit)
    preferences = router._list_preferences(conn, limit=limit)
    open_loops = router._list_open_loops(conn, limit=limit)
    nodes = router._list_nodes(conn, domain=req.domain, limit=limit)
    review_items = router._list_review_items(conn, limit=limit)

    # Bounded INDEX search over source FILES — metadata only, no live read, no snippet copied.
    query = req.query or req.project_key or ""
    source_files_raw = router._search_source_files(query, conn, source_root_key=req.source_root_key,
                                                   limit=limit)
    source_files = _cap([bounded_metadata(row, _SOURCE_FILE_WL) for row in source_files_raw])

    claim_buckets = _bucket(router, claims, TARGET_CLAIMS, "claim", "claim_id", _CLAIM_WL)
    node_buckets = _bucket(router, nodes, TARGET_MEMORY, "memory_node", "node_id", _NODE_WL)
    facts = _merge_buckets(claim_buckets, node_buckets)
    dp = _merge_buckets(
        _bucket(router, decisions, TARGET_DECISION_MEMORY, "decision", "decision_id", _DECISION_WL),
        _bucket(router, preferences, TARGET_DECISION_MEMORY, "preference", "preference_id", _PREFERENCE_WL),
    )
    open_loop_refs = _cap([router._artifact(TARGET_OPEN_LOOPS, "open_loop",
                                            str(r.get("open_loop_id") or ""), r, _OPEN_LOOP_WL)
                          for r in open_loops
                          if str(r.get("status") or "").lower() in ("open", "candidate")])
    review_needed = _cap([router._artifact(TARGET_REVIEW_QUEUE, "review_item",
                                           str(r.get("review_item_id") or ""), r, _REVIEW_WL)
                         for r in review_items
                         if str(r.get("effective_state") or "").lower() == "candidate"
                         or str(r.get("review_state") or "").lower() in ("unreviewed", "needs_review")])

    project_scope = [{k: v for k, v in {
        "project_key": req.project_key, "domain": req.domain, "query": req.query,
        "source_root_key": req.source_root_key,
    }.items() if v}]
    sections = {
        "project_scope": [s for s in project_scope if s],
        "trusted_facts": _cap(facts[TRUSTED]),
        "candidate_findings": _cap(facts[CANDIDATE]),
        "source_files": source_files,
        "decisions_preferences": _cap(dp[TRUSTED] + dp[CANDIDATE]),
        "open_loops": open_loop_refs,
        "review_needed": review_needed,
    }
    source_refs = _dedupe_dicts(_refs(claims, decisions, preferences, open_loops, nodes)
                                + source_files)[:MAX_SOURCE_REFS]
    review_labels = _labels(claims, decisions, preferences, open_loops, review_items)
    risks = _caveats(candidate=facts[CANDIDATE], excluded=facts[EXCLUDED], review_needed=review_needed)
    warnings = _missing_citation_warning(facts[TRUSTED], [], source_refs)

    has_content = any(v for v in sections.values() if v is not sections["project_scope"])
    status = STATUS_ROUTED if has_content else STATUS_INSUFFICIENT_CONTEXT
    advisory = ["Confirm candidate findings and review-needed items in the review queue before treating "
                "them as project truth.",
                "Open any listed source file via the source-connector search and metadata surface. Source "
                "references here are index metadata only."]
    return {
        "routing_decision": _decision(WF_PROJECT_INTELLIGENCE_CONTEXT, req, TARGET_INTELLIGENCE_PROJECTIONS,
                                      list(spec.primary_targets),
                                      "assemble bounded project-context sections (read-only; index metadata "
                                      "only)"),
        "status": status,
        "selected_artifacts": (facts[TRUSTED] + facts[CANDIDATE] + open_loop_refs)[:MAX_SELECTED_ARTIFACTS],
        "trusted_items": _cap(facts[TRUSTED]),
        "candidate_items": _cap(facts[CANDIDATE]),
        "excluded_items": _cap(facts[EXCLUDED]),
        "source_refs": source_refs,
        "review_labels": review_labels,
        "risks_or_caveats": risks,
        "deferred_capabilities": list(spec.deferred_capabilities),
        "advisory_next_steps": advisory,
        "requires_operator_review": bool(facts[CANDIDATE] or review_needed),
        "warnings": warnings,
        "workflow_sections": sections,
    }


# ============================================================================================
# open_loop_triage
# ============================================================================================
def assemble_open_loop_triage(router: Any, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
    spec = get_spec(WF_OPEN_LOOP_TRIAGE)
    review_labels: list[str] = []

    if req.open_loop_id:
        rec = router._get_open_loop(req.open_loop_id, conn)
        if rec is None:
            return router._missing(WF_OPEN_LOOP_TRIAGE, TARGET_OPEN_LOOPS, "open_loop", req.open_loop_id,
                                   spec)
        loops = [rec]
        for es in router._effective_state_for("open_loop", req.open_loop_id, conn):
            if es.get("effective_state"):
                review_labels.append(str(es["effective_state"]))
    else:
        loops = router._list_open_loops(conn, limit=req.limit)

    active, candidate, blocked, stale, needs_review = [], [], [], [], []
    for rec in loops:
        art = router._artifact(TARGET_OPEN_LOOPS, "open_loop", str(rec.get("open_loop_id") or ""), rec,
                               _OPEN_LOOP_WL)
        status = str(rec.get("status") or "").lower()
        loop_type = str(rec.get("open_loop_type") or "").lower()
        review_state = str(rec.get("review_state") or "").lower()
        if status == "closed":
            continue  # resolved — not surfaced for triage
        if status in ("stale", "superseded", "rejected"):
            stale.append(art)
            continue  # already inactive — never also flagged as needing review
        if loop_type == "waiting_for":
            blocked.append(art)
        elif status == "open":
            active.append(art)
        else:  # "candidate" or any other non-terminal status → conservative candidate bucket
            candidate.append(art)
        if review_state in ("unreviewed", "needs_review"):
            needs_review.append(art)

    decisions = router._list_decisions(conn, limit=req.limit)
    related_decisions = _cap([router._artifact(TARGET_DECISION_MEMORY, "decision",
                                               str(r.get("decision_id") or ""), r, _DECISION_WL)
                             for r in decisions if _classify(r) != EXCLUDED])

    sections = {
        "active_open_loops": _cap(active),
        "candidate_open_loops": _cap(candidate),
        "blocked_or_waiting": _cap(blocked),
        "review_needed": _cap(needs_review),
        "stale_or_superseded": _cap(stale),
        "related_decisions": related_decisions,
    }
    review_labels = _dedupe(review_labels + _labels(loops, decisions))[:MAX_REVIEW_LABELS]
    source_refs = _refs(loops, decisions)
    risks = _caveats(candidate=candidate, excluded=stale, review_needed=needs_review)

    has_content = any(sections[k] for k in ("active_open_loops", "candidate_open_loops",
                                            "blocked_or_waiting", "stale_or_superseded"))
    status = STATUS_ROUTED if (has_content or req.open_loop_id) else STATUS_INSUFFICIENT_CONTEXT
    advisory = ["Review candidate and review-needed open loops in the review queue to confirm them.",
                "Follow related_decisions for context on blocked or waiting loops. This is triage context "
                "only."]
    return {
        "routing_decision": _decision(WF_OPEN_LOOP_TRIAGE, req, TARGET_OPEN_LOOPS,
                                      list(spec.primary_targets),
                                      "triage existing open-loop records + review state (no task/disposition "
                                      "write)"),
        "status": status,
        "selected_artifacts": (active + blocked + candidate)[:MAX_SELECTED_ARTIFACTS],
        "trusted_items": _cap(active),
        "candidate_items": _cap(candidate),
        "excluded_items": _cap(stale),
        "source_refs": source_refs,
        "review_labels": review_labels,
        "risks_or_caveats": risks,
        "deferred_capabilities": list(spec.deferred_capabilities),
        "advisory_next_steps": advisory,
        "requires_operator_review": bool(candidate or needs_review),
        "warnings": [],
        "workflow_sections": sections,
    }


def _caveats(*, candidate: list[Any], excluded: list[Any], review_needed: list[Any]) -> list[str]:
    """Bounded, advisory data-quality caveats (never execution instructions)."""
    out: list[str] = []
    if candidate:
        out.append(f"{len(candidate)} candidate item(s) are unconfirmed and require review before use.")
    if review_needed:
        out.append(f"{len(review_needed)} item(s) are pending review.")
    if excluded:
        out.append(f"{len(excluded)} excluded/superseded/stale item(s) were withheld from trusted context.")
    return out[:MAX_ITEMS]


def _questions_to_resolve(candidate_ctx: list[Any], open_loops: list[Any],
                          warnings: list[str]) -> list[str]:
    """Advisory questions (navigation/review prompts only) for meeting prep."""
    out: list[str] = []
    if candidate_ctx:
        out.append("Which candidate context items should be confirmed or dropped before the meeting?")
    if open_loops:
        out.append("Which open loops need an owner or an update ahead of the meeting?")
    if any(w.startswith("missing_") for w in warnings):
        out.append("A supplied artifact id could not be found — is the correct id available?")
    return out[:MAX_SECTION_ITEMS]
