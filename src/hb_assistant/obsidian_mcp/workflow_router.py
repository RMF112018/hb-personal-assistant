"""N8C-15 deterministic, route-only workflow router.

Accepts a bounded ``WorkflowRequest``, resolves the intended workflow type (explicit type wins; else a
conservative keyword fallback; else unknown), routes to the correct EXISTING N8C read surfaces, and returns
a normalized workflow-result envelope of BOUNDED, whitelisted metadata.

Hard boundaries (enforced by construction here):
  * READ-ONLY. The router only calls repository READ methods. It never calls a build/apply writer, a source
    scan/reindex, a source-card generator, an enrichment/qwen worker, or a live source-file read.
  * NO PERSISTENCE. Nothing is written — no workflow run/event/receipt/history, no raw request. The
    ``workflow_id`` is an ephemeral deterministic response id (N8C-15 adds no schema).
  * NO EXECUTION. Every envelope carries the fixed no-execution policy block. ``action_draft_preparation``
    returns deferred capabilities only; nothing is staged, scheduled, sent, or created.
  * NO LLM / NO NETWORK. Intent classification is deterministic keyword matching only.
  * BOUNDED. Only whitelisted scalar metadata is copied from upstream artifacts — never a full export, a
    raw body, a raw prompt/response, a ``*_json`` blob, or a full upstream payload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .workflow_models import (
    MAX_CITATIONS,
    MAX_ITEMS,
    MAX_REVIEW_LABELS,
    MAX_SELECTED_ARTIFACTS,
    MAX_SOURCE_REFS,
    POLICY_BLOCK,
    STATUS_DEFERRED,
    STATUS_INSUFFICIENT_CONTEXT,
    STATUS_MISSING_REQUIRED_ARTIFACT,
    STATUS_NEEDS_CLARIFICATION,
    STATUS_ROUTED,
    TARGET_ANSWER_DRAFTS,
    TARGET_DECISION_MEMORY,
    TARGET_INTELLIGENCE_PROJECTIONS,
    TARGET_RESEARCH_PACKETS,
    TARGET_SOURCE_CONNECTOR,
    TARGET_UNKNOWN,
    WF_ACTION_DRAFT_PREPARATION,
    WF_ASK_SECOND_BRAIN,
    WF_DAILY_BRIEF_CONTEXT,
    WF_DECISION_PREFERENCE_LOOKUP,
    WF_DRAFT_REVIEW,
    WF_MEETING_PREP,
    WF_OPEN_LOOP_TRIAGE,
    WF_PROJECT_INTELLIGENCE_CONTEXT,
    WF_RESEARCH_ANSWER,
    WF_SOURCE_FILE_LOOKUP,
    WF_UNKNOWN,
    WORKFLOW_POLICY_CONTEXT_ONLY,
    WORKFLOW_ROUTER_VERSION,
    WORKFLOW_TYPE_ALIASES,
    WORKFLOW_TYPES,
    RoutingDecision,
    WorkflowRequest,
    bounded_metadata,
    classify_workflow_type_from_keywords,
    compute_workflow_id,
)
from .workflow_registry import catalog, get_spec

# --- bounded whitelists (scalar-only; never *_json / metadata_json / raw bodies) --------
_DRAFT_WL = ("draft_id", "draft_type", "title", "status", "packet_id", "created_at", "section_count",
             "citation_count", "trusted_section_count", "candidate_section_count", "open_question_count",
             "excluded_count", "truncated")
_PACKET_WL = ("packet_id", "packet_type", "title", "status", "projection_id", "created_at", "item_count",
              "citation_count", "trusted_count", "candidate_count", "open_question_count", "excluded_count",
              "truncated")
_PROJECTION_WL = ("projection_id", "projection_type", "title", "status", "created_at", "item_count",
                  "trusted_count", "candidate_count", "excluded_count", "truncated")
_PACK_WL = ("pack_id", "pack_type", "title", "status", "item_count", "truncated", "created_at")
_REVIEW_WL = ("review_item_id", "target_kind", "target_id", "review_type", "review_state",
              "effective_state", "stale", "superseded", "created_at")
_DECISION_WL = ("decision_id", "decision_type", "domain", "status", "review_state", "created_at")
_PREFERENCE_WL = ("preference_id", "preference_type", "domain", "status", "review_state", "created_at")
_OPEN_LOOP_WL = ("open_loop_id", "open_loop_type", "domain", "status", "review_state", "priority",
                 "owner_hint", "due_at", "created_at")
_NODE_WL = ("node_id", "node_type", "canonical_name", "domain", "status", "review_tier", "mention_count",
            "created_at")
_CITATION_WL = ("draft_citation_id", "citation_id", "packet_citation_id", "citation_type", "citation_label",
                "label", "target_kind", "review_state", "effective_state", "inclusion_state")
_SOURCE_REF_WL = ("source_ref", "source_root_key", "rel_path", "note_rel_path", "source_id")
# Claim refs carry NO claim_text / evidence_excerpt (bounded pointers only — clarification #4).
_CLAIM_WL = ("claim_id", "claim_type", "status", "review_state", "source_state", "confidence", "card_id",
             "source_id", "source_root_key", "source_rel_path", "note_rel_path", "created_at")
# Bounded source-FILE ref (index metadata only; never a snippet/body — clarification #7).
_SOURCE_FILE_WL = ("source_ref", "source_id", "source_root_key", "rel_path", "source_kind", "extension",
                   "mime_type")


class WorkflowRouter:
    """Deterministic, read-only router over existing N8C repositories. Construct once per db_path."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path is not None else None

    # -- public API ----------------------------------------------------------------------
    def catalog(self) -> dict[str, Any]:
        """Return the read-only workflow registry catalog (no DB access)."""
        return catalog()

    def route(self, request: WorkflowRequest, *, conn: Any = None) -> dict[str, Any]:
        """Resolve intent, route to existing surfaces, and return the normalized envelope."""
        wf_type, resolution, warnings = self._resolve_type(request)

        if wf_type == WF_UNKNOWN:
            status = STATUS_NEEDS_CLARIFICATION if request.workflow_type else STATUS_INSUFFICIENT_CONTEXT
            decision = RoutingDecision(WF_UNKNOWN, resolution, TARGET_UNKNOWN, [TARGET_UNKNOWN],
                                       "no unambiguous workflow type; not guessing")
            return self._envelope(request, wf_type, decision, status=status, warnings=warnings,
                                  open_questions=["Which workflow was intended? Provide workflow_type or an "
                                                  "artifact id (draft_id/packet_id/...)."],
                                  requires_operator_review=True)

        handler = self._HANDLERS[wf_type]
        parts = handler(self, request, conn)
        parts.setdefault("warnings", [])
        parts["warnings"] = list(warnings) + list(parts["warnings"])
        return self._envelope(request, wf_type, parts.pop("routing_decision"), **parts)

    # -- intent resolution ---------------------------------------------------------------
    def _resolve_type(self, request: WorkflowRequest) -> tuple[str, str, list[str]]:
        """Explicit valid type wins; else conservative keyword fallback; else unknown."""
        warnings: list[str] = []
        explicit = request.workflow_type
        if explicit:
            # Bridge the V114 recipe-registry ids (e.g. source_file_search) onto this router's canonical
            # types so a workflow id read from pa_workflow_recipe_get doesn't resolve to unknown here.
            explicit = WORKFLOW_TYPE_ALIASES.get(explicit, explicit)
            if explicit in WORKFLOW_TYPES and explicit != WF_UNKNOWN:
                return explicit, "explicit", warnings
            warnings.append("unknown_workflow_type")
            return WF_UNKNOWN, "unresolved", warnings
        guess = classify_workflow_type_from_keywords(request.query, request.objective)
        if guess != WF_UNKNOWN:
            return guess, "keyword_fallback", warnings
        return WF_UNKNOWN, "unresolved", warnings

    # -- per-workflow handlers (each returns envelope parts; all READ-ONLY) --------------
    def _handle_ask_second_brain(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        spec = get_spec(WF_ASK_SECOND_BRAIN)
        # Explicit artifact ids win, in preference order.
        if req.draft_id:
            return self._route_single(WF_ASK_SECOND_BRAIN, TARGET_ANSWER_DRAFTS, "draft", req.draft_id,
                                      self._get_draft(req.draft_id, conn), _DRAFT_WL, spec)
        if req.packet_id:
            return self._route_single(WF_ASK_SECOND_BRAIN, TARGET_RESEARCH_PACKETS, "packet", req.packet_id,
                                      self._get_packet(req.packet_id, conn), _PACKET_WL, spec)
        if req.projection_id:
            return self._route_single(WF_ASK_SECOND_BRAIN, TARGET_INTELLIGENCE_PROJECTIONS, "projection",
                                      req.projection_id, self._get_projection(req.projection_id, conn),
                                      _PROJECTION_WL, spec)
        # No explicit artifact — insufficient context (do not fabricate a search/answer).
        decision = RoutingDecision(WF_ASK_SECOND_BRAIN, "explicit" if req.workflow_type else
                                   "keyword_fallback", TARGET_UNKNOWN, list(spec.fallback_targets),
                                   "no artifact id supplied; nothing to route to")
        return {"routing_decision": decision, "status": STATUS_INSUFFICIENT_CONTEXT,
                "advisory_next_steps": ["Supply a draft_id, packet_id, or projection_id, or a more specific "
                                        "query, to route this ask."],
                "requires_operator_review": True}

    def _handle_research_answer(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        spec = get_spec(WF_RESEARCH_ANSWER)
        if req.draft_id:
            return self._route_single(WF_RESEARCH_ANSWER, TARGET_ANSWER_DRAFTS, "draft", req.draft_id,
                                      self._get_draft(req.draft_id, conn), _DRAFT_WL, spec)
        if req.packet_id:
            return self._route_single(WF_RESEARCH_ANSWER, TARGET_RESEARCH_PACKETS, "packet", req.packet_id,
                                      self._get_packet(req.packet_id, conn), _PACKET_WL, spec)
        decision = RoutingDecision(WF_RESEARCH_ANSWER, "explicit", TARGET_UNKNOWN,
                                   list(spec.primary_targets), "research_answer requires a draft_id or "
                                   "packet_id")
        return {"routing_decision": decision, "status": STATUS_NEEDS_CLARIFICATION,
                "open_questions": ["Provide a draft_id or packet_id to route a research answer."],
                "requires_operator_review": True}

    def _handle_source_file_lookup(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        del conn
        spec = get_spec(WF_SOURCE_FILE_LOOKUP)
        decision = RoutingDecision(WF_SOURCE_FILE_LOOKUP, "explicit" if req.workflow_type else
                                   "keyword_fallback", TARGET_SOURCE_CONNECTOR, [TARGET_SOURCE_CONNECTOR],
                                   "route to indexed source-connector surface (no live read here)")
        route_ref: dict[str, Any] = {"target": TARGET_SOURCE_CONNECTOR}
        if req.query:
            route_ref["query"] = req.query
        if req.source_root_key:
            route_ref["source_root_key"] = req.source_root_key
        return {"routing_decision": decision, "status": STATUS_ROUTED,
                "selected_artifacts": [route_ref],
                "advisory_next_steps": ["Use the source-connector search/list/metadata surface with the "
                                        "routed query/source_root_key to locate files."],
                "deferred_capabilities": list(spec.deferred_capabilities)}

    # N8C-17: the four context-assembly workflows delegate to deterministic, read-only handlers that build
    # bounded ``workflow_sections`` over existing N8C artifacts (no execution, no persistence, no source read).
    def _handle_meeting_prep(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        from . import workflow_handlers
        return workflow_handlers.assemble_meeting_prep(self, req, conn)

    def _handle_daily_brief_context(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        from . import workflow_handlers
        return workflow_handlers.assemble_daily_brief_context(self, req, conn)

    def _handle_project_intelligence_context(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        from . import workflow_handlers
        return workflow_handlers.assemble_project_intelligence_context(self, req, conn)

    def _handle_open_loop_triage(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        from . import workflow_handlers
        return workflow_handlers.assemble_open_loop_triage(self, req, conn)

    def _handle_decision_preference_lookup(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        spec = get_spec(WF_DECISION_PREFERENCE_LOOKUP)
        if req.decision_id:
            return self._route_single(WF_DECISION_PREFERENCE_LOOKUP, TARGET_DECISION_MEMORY, "decision",
                                      req.decision_id, self._get_decision(req.decision_id, conn),
                                      _DECISION_WL, spec)
        if req.preference_id:
            return self._route_single(WF_DECISION_PREFERENCE_LOOKUP, TARGET_DECISION_MEMORY, "preference",
                                      req.preference_id, self._get_preference(req.preference_id, conn),
                                      _PREFERENCE_WL, spec)
        decision = RoutingDecision(WF_DECISION_PREFERENCE_LOOKUP, "explicit" if req.workflow_type else
                                   "keyword_fallback", TARGET_DECISION_MEMORY, list(spec.primary_targets),
                                   "route to decision/preference records + review/effective state")
        return {"routing_decision": decision, "status": STATUS_INSUFFICIENT_CONTEXT,
                "advisory_next_steps": ["Supply a decision_id or preference_id to route a lookup."],
                "requires_operator_review": True}

    def _handle_draft_review(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        spec = get_spec(WF_DRAFT_REVIEW)
        selected: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        source_refs: list[dict[str, Any]] = []
        review_labels: list[str] = []
        warnings: list[str] = []
        if not (req.draft_id or req.packet_id):
            decision = RoutingDecision(WF_DRAFT_REVIEW, "explicit", TARGET_ANSWER_DRAFTS,
                                       list(spec.primary_targets), "draft_review requires a draft_id or "
                                       "packet_id")
            return {"routing_decision": decision, "status": STATUS_NEEDS_CLARIFICATION,
                    "open_questions": ["Provide a draft_id or packet_id to review."],
                    "requires_operator_review": True}
        if req.draft_id:
            draft = self._get_draft(req.draft_id, conn)
            if draft is None:
                return self._missing(WF_DRAFT_REVIEW, TARGET_ANSWER_DRAFTS, "draft", req.draft_id, spec)
            selected.append(self._artifact(TARGET_ANSWER_DRAFTS, "draft", req.draft_id, draft, _DRAFT_WL))
            review_labels, citations, source_refs, warnings = self._inspect_draft(req.draft_id, draft, conn)
        if req.packet_id:
            packet = self._get_packet(req.packet_id, conn)
            if packet is None:
                return self._missing(WF_DRAFT_REVIEW, TARGET_RESEARCH_PACKETS, "packet", req.packet_id, spec)
            selected.append(self._artifact(TARGET_RESEARCH_PACKETS, "packet", req.packet_id, packet,
                                           _PACKET_WL))
            warnings += self._packet_warnings(packet)
        decision = RoutingDecision(WF_DRAFT_REVIEW, "explicit" if req.workflow_type else "keyword_fallback",
                                   TARGET_ANSWER_DRAFTS, list(spec.primary_targets),
                                   "inspect draft/packet metadata; preserve citation/review labels")
        return {"routing_decision": decision, "status": STATUS_ROUTED, "selected_artifacts": selected,
                "citations": citations[:MAX_CITATIONS], "source_refs": source_refs[:MAX_SOURCE_REFS],
                "review_labels": _dedupe(review_labels)[:MAX_REVIEW_LABELS], "warnings": _dedupe(warnings),
                "advisory_next_steps": ["Review the flagged citation/candidate/excluded warnings; nothing "
                                        "is modified."]}

    def _handle_action_draft_preparation(self, req: WorkflowRequest, conn: Any) -> dict[str, Any]:
        del conn
        spec = get_spec(WF_ACTION_DRAFT_PREPARATION)
        decision = RoutingDecision(WF_ACTION_DRAFT_PREPARATION, "explicit", TARGET_UNKNOWN, [TARGET_UNKNOWN],
                                   "contract-only in N8C-15; action staging deferred to N8C-18")
        return {"routing_decision": decision, "status": STATUS_DEFERRED,
                "deferred_capabilities": list(spec.deferred_capabilities),
                "advisory_next_steps": ["Action staging is deferred to N8C-18. No action, draft, task, "
                                        "reminder, or calendar item is created."],
                "requires_operator_review": True}

    # -- shared handler helpers ----------------------------------------------------------
    def _route_single(self, wf_type: str, target: str, kind: str, art_id: str, rec: dict[str, Any] | None,
                      whitelist: tuple[str, ...], spec: Any) -> dict[str, Any]:
        """Route to one explicit artifact; missing → missing_required_artifact (never build it)."""
        if rec is None:
            return self._missing(wf_type, target, kind, art_id, spec)
        decision = RoutingDecision(wf_type, "explicit", target, [target],
                                   f"route to existing {kind} {art_id}")
        return {"routing_decision": decision, "status": STATUS_ROUTED,
                "selected_artifacts": [self._artifact(target, kind, art_id, rec, whitelist)]}

    def _missing(self, wf_type: str, target: str, kind: str, art_id: str, spec: Any) -> dict[str, Any]:
        decision = RoutingDecision(wf_type, "explicit", target, [target],
                                   f"required {kind} {art_id} does not exist")
        deferred = list(getattr(spec, "deferred_capabilities", ()) or ()) or [f"build_{kind}"]
        return {"routing_decision": decision, "status": STATUS_MISSING_REQUIRED_ARTIFACT,
                "deferred_capabilities": deferred,
                "advisory_next_steps": [f"The {kind} {art_id} does not exist; build it via its own "
                                        f"read/build surface before routing. Not built here."],
                "requires_operator_review": True}

    @staticmethod
    def _artifact(target: str, kind: str, art_id: str, rec: dict[str, Any],
                  whitelist: tuple[str, ...]) -> dict[str, Any]:
        return {"target": target, "artifact_kind": kind, "artifact_id": art_id,
                "metadata": bounded_metadata(rec, whitelist)}

    def _inspect_draft(self, draft_id: str, header: dict[str, Any],
                       conn: Any) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """Read-only draft inspection: distinct review labels, bounded citations + source refs, warnings."""
        repo = self._draft_repo()
        labels: list[str] = []
        for sec in repo.list_answer_draft_sections(draft_id, limit=MAX_ITEMS, conn=conn):
            if sec.get("review_label"):
                labels.append(str(sec["review_label"]))
        citations: list[dict[str, Any]] = []
        source_refs: list[dict[str, Any]] = []
        for cit in repo.list_answer_draft_citations(draft_id, limit=MAX_CITATIONS, conn=conn):
            citations.append(bounded_metadata(cit, _CITATION_WL))
            sref = bounded_metadata(cit, _SOURCE_REF_WL)
            if sref:
                source_refs.append(sref)
        return _dedupe(labels), citations, source_refs, self._draft_warnings(header)

    @staticmethod
    def _draft_warnings(header: dict[str, Any]) -> list[str]:
        warns: list[str] = []
        if int(header.get("citation_count") or 0) == 0:
            warns.append("draft_has_no_citations")
        if int(header.get("candidate_section_count") or 0) > 0:
            warns.append("draft_contains_candidate_content")
        if int(header.get("excluded_count") or 0) > 0:
            warns.append("draft_has_excluded_content")
        return warns

    @staticmethod
    def _packet_warnings(header: dict[str, Any]) -> list[str]:
        warns: list[str] = []
        if int(header.get("citation_count") or 0) == 0:
            warns.append("packet_has_no_citations")
        if int(header.get("candidate_count") or 0) > 0:
            warns.append("packet_contains_candidate_content")
        if int(header.get("excluded_count") or 0) > 0:
            warns.append("packet_has_excluded_content")
        return warns

    # -- lazy repository accessors (read-only) -------------------------------------------
    # A getter that hits a not-yet-provisioned artifact family (unmigrated DB) degrades to "absent"
    # rather than crashing the envelope; any other DB error still propagates.
    @staticmethod
    def _guard_one(call: Any) -> dict[str, Any] | None:
        import sqlite3
        try:
            return call()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return None
            raise

    @staticmethod
    def _guard_many(call: Any) -> list[dict[str, Any]]:
        import sqlite3
        try:
            return call()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise

    def _draft_repo(self) -> Any:
        from .answer_draft_repository import AnswerDraftRepository
        return AnswerDraftRepository(self.db_path)

    def _get_draft(self, draft_id: str, conn: Any) -> dict[str, Any] | None:
        return self._guard_one(lambda: self._draft_repo().get_answer_draft(draft_id, conn=conn))

    def _get_packet(self, packet_id: str, conn: Any) -> dict[str, Any] | None:
        from .research_packet_repository import ResearchPacketRepository
        return self._guard_one(
            lambda: ResearchPacketRepository(self.db_path).get_research_packet(packet_id, conn=conn))

    def _get_projection(self, projection_id: str, conn: Any) -> dict[str, Any] | None:
        from .intelligence_projection_repository import IntelligenceProjectionRepository
        return self._guard_one(
            lambda: IntelligenceProjectionRepository(self.db_path).get_projection(projection_id, conn=conn))

    def _get_context_pack(self, pack_id: str, conn: Any) -> dict[str, Any] | None:
        from .context_pack_repository import ContextPackRepository
        return self._guard_one(lambda: ContextPackRepository(self.db_path).get_pack(pack_id, conn=conn))

    def _get_memory_node(self, node_id: str, conn: Any) -> dict[str, Any] | None:
        from .memory_repository import MemoryRepository
        return self._guard_one(lambda: MemoryRepository(self.db_path).get_node(node_id, conn=conn))

    def _decision_repo(self) -> Any:
        from .decision_memory_repository import DecisionMemoryRepository
        return DecisionMemoryRepository(self.db_path)

    def _get_decision(self, decision_id: str, conn: Any) -> dict[str, Any] | None:
        return self._guard_one(lambda: self._decision_repo().get_decision(decision_id, conn=conn))

    def _get_preference(self, preference_id: str, conn: Any) -> dict[str, Any] | None:
        return self._guard_one(lambda: self._decision_repo().get_preference(preference_id, conn=conn))

    def _get_open_loop(self, open_loop_id: str, conn: Any) -> dict[str, Any] | None:
        return self._guard_one(lambda: self._decision_repo().get_open_loop(open_loop_id, conn=conn))

    def _list_open_loops(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: self._decision_repo().list_open_loops(limit=limit, conn=conn))

    def _effective_state_for(self, target_kind: str, target_id: str, conn: Any) -> list[dict[str, Any]]:
        from .review_repository import ReviewRepository
        return self._guard_many(lambda: ReviewRepository(self.db_path).effective_state_for_target(
            target_kind, target_id, conn=conn))

    # -- N8C-17 bounded LIST accessors (read-only; each caps input+output; guarded on unmigrated DB) -------
    def _list_context_packs(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .context_pack_repository import ContextPackRepository
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: ContextPackRepository(self.db_path).list_packs(limit=limit, conn=conn))

    def _list_projections(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .intelligence_projection_repository import IntelligenceProjectionRepository
        limit = _bounded_limit(limit)
        return self._guard_many(
            lambda: IntelligenceProjectionRepository(self.db_path).list_projections(limit=limit, conn=conn))

    def _list_research_packets(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .research_packet_repository import ResearchPacketRepository
        limit = _bounded_limit(limit)
        return self._guard_many(
            lambda: ResearchPacketRepository(self.db_path).list_research_packets(limit=limit, conn=conn))

    def _list_drafts(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: self._draft_repo().list_answer_drafts(limit=limit, conn=conn))

    def _list_decisions(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: self._decision_repo().list_decisions(limit=limit, conn=conn))

    def _list_preferences(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: self._decision_repo().list_preferences(limit=limit, conn=conn))

    def _list_nodes(self, conn: Any, *, domain: str | None = None,
                    limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .memory_repository import MemoryRepository
        limit = _bounded_limit(limit)
        return self._guard_many(
            lambda: MemoryRepository(self.db_path).list_nodes(domain=domain or None, limit=limit, conn=conn))

    def _list_review_items(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .review_repository import ReviewRepository
        limit = _bounded_limit(limit)
        return self._guard_many(
            lambda: ReviewRepository(self.db_path).list_review_items(limit=limit, conn=conn))

    def _list_claims(self, conn: Any, *, limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        from .claim_repository import ClaimRepository
        limit = _bounded_limit(limit)
        return self._guard_many(lambda: ClaimRepository(self.db_path).list_claims(limit=limit, conn=conn))

    def _packet_citations(self, packet_id: str, conn: Any) -> list[dict[str, Any]]:
        from .research_packet_repository import ResearchPacketRepository
        return self._guard_many(lambda: ResearchPacketRepository(self.db_path)
                                .list_research_packet_citations(packet_id, limit=MAX_CITATIONS, conn=conn))

    def _search_source_files(self, query: str, conn: Any, *, source_root_key: str | None = None,
                             limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
        """Indexed FTS search over source FILES (metadata only; NO live filesystem read, NO snippet copied).
        Returns bounded index rows; empty when the index is absent/disabled or the query is blank."""
        if not query:
            return []
        limit = _bounded_limit(limit)

        def _call() -> list[dict[str, Any]]:
            from .config import ObsidianMcpConfig
            from .source_connector_service import search_source_files as _svc_search
            from .source_index_repository import SourceIndexRepository
            env = _svc_search(SourceIndexRepository(self.db_path), ObsidianMcpConfig(), query=query,
                              source_root_key=source_root_key or None, limit=limit, conn=conn)
            return list(env.get("items") or [])

        try:
            return self._guard_many(_call)
        except Exception:  # noqa: BLE001 — index disabled / invalid input degrades to no source files.
            return []

    # -- envelope assembly ---------------------------------------------------------------
    def _envelope(self, request: WorkflowRequest, wf_type: str, decision: RoutingDecision, *,
                  status: str, selected_artifacts: list[dict[str, Any]] | None = None,
                  trusted_items: list[Any] | None = None, candidate_items: list[Any] | None = None,
                  excluded_items: list[Any] | None = None, citations: list[Any] | None = None,
                  source_refs: list[Any] | None = None, review_labels: list[str] | None = None,
                  open_questions: list[str] | None = None, risks_or_caveats: list[str] | None = None,
                  deferred_capabilities: list[str] | None = None,
                  advisory_next_steps: list[str] | None = None,
                  requires_operator_review: bool = False, warnings: list[str] | None = None,
                  workflow_sections: dict[str, list[Any]] | None = None,
                  workflow_policy: str = WORKFLOW_POLICY_CONTEXT_ONLY,
                  ) -> dict[str, Any]:
        """Assemble the normalized, bounded, no-execution workflow-result envelope."""
        return {
            "workflow_id": compute_workflow_id(wf_type, request),
            "workflow_type": wf_type,
            "request": request.to_public_dict(),
            "routing_decision": decision.to_dict(),
            "selected_artifacts": (selected_artifacts or [])[:MAX_SELECTED_ARTIFACTS],
            "trusted_items": (trusted_items or [])[:MAX_ITEMS],
            "candidate_items": (candidate_items or [])[:MAX_ITEMS],
            "excluded_items": (excluded_items or [])[:MAX_ITEMS],
            "citations": (citations or [])[:MAX_CITATIONS],
            "source_refs": (source_refs or [])[:MAX_SOURCE_REFS],
            "review_labels": (review_labels or [])[:MAX_REVIEW_LABELS],
            "open_questions": (open_questions or [])[:MAX_ITEMS],
            "risks_or_caveats": (risks_or_caveats or [])[:MAX_ITEMS],
            "deferred_capabilities": (deferred_capabilities or [])[:MAX_ITEMS],
            # Advisory review/navigation suggestions only — never executable instructions (clarification #5).
            "advisory_next_steps": (advisory_next_steps or [])[:MAX_ITEMS],
            "requires_operator_review": bool(requires_operator_review),
            "status": status,
            "warnings": (warnings or [])[:MAX_ITEMS],
            # N8C-17: named, bounded per-workflow context sections (each capped; non-list values dropped).
            "workflow_sections": _bound_sections(workflow_sections),
            "metadata": {"router_version": WORKFLOW_ROUTER_VERSION, "resolution": decision.resolution},
            # Additive, more-specific marker: this layer assembles CONTEXT only (never a final answer/action).
            "workflow_policy": workflow_policy,
            **POLICY_BLOCK,
        }

    _HANDLERS = {
        WF_ASK_SECOND_BRAIN: _handle_ask_second_brain,
        WF_RESEARCH_ANSWER: _handle_research_answer,
        WF_SOURCE_FILE_LOOKUP: _handle_source_file_lookup,
        WF_MEETING_PREP: _handle_meeting_prep,
        WF_DAILY_BRIEF_CONTEXT: _handle_daily_brief_context,
        WF_PROJECT_INTELLIGENCE_CONTEXT: _handle_project_intelligence_context,
        WF_OPEN_LOOP_TRIAGE: _handle_open_loop_triage,
        WF_DECISION_PREFERENCE_LOOKUP: _handle_decision_preference_lookup,
        WF_DRAFT_REVIEW: _handle_draft_review,
        WF_ACTION_DRAFT_PREPARATION: _handle_action_draft_preparation,
    }


def _bounded_limit(limit: Any) -> int:
    """Clamp a list-accessor limit into [1, MAX_ITEMS] (never let a caller request an unbounded read)."""
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return MAX_ITEMS
    return max(1, min(MAX_ITEMS, n))


def _bound_sections(sections: dict[str, list[Any]] | None) -> dict[str, list[Any]]:
    """Bound the per-workflow sections map: keep only list values, cap each list to MAX_ITEMS, cap the
    number of sections. Non-list section values are dropped (defense-in-depth for the bounded rule)."""
    if not sections:
        return {}
    out: dict[str, list[Any]] = {}
    for name, items in list(sections.items())[:MAX_ITEMS]:
        if isinstance(items, list):
            out[str(name)] = items[:MAX_ITEMS]
    return out


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving de-duplication for bounded label lists."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def route_request(db_path: str | Path | None, **inputs: Any) -> dict[str, Any]:
    """Convenience one-shot: build a bounded request from raw inputs and route it (read-only)."""
    return WorkflowRouter(db_path).route(WorkflowRequest.from_inputs(**inputs))
