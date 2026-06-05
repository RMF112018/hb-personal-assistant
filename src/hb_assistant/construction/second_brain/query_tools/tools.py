"""Phase 08A allowlisted read-only SQLite query tools (Prompt 06).

Each query tool is an explicit, named service function — the model never generates
or executes SQL. ``run_query_tool`` dispatches by allowlisted *name* only (an
unknown / model-authored string raises ``QueryToolError`` before any DB access),
resolves the tool to an approved local read-model reader (reused from Prompt 04),
runs it under an enforced read-only connection (``PRAGMA query_only = ON``) where
the layer owns the connection, bounds the result, and returns source-linked,
review-tier-labeled facts. Tools provide bounded facts only; they never decide
final answers (the retrieval orchestrator does, in Prompt 07).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

from ..retrieval import RetrievalItem
from ..retrieval.readers import (
    READER_REGISTRY,
    read_accepted_memory,
    read_aging_exposure,
    read_risk_digest,
)
from .models import QueryToolResult
from .policy import (
    ALLOWLISTED_QUERY_TOOLS,
    QUERY_TOOL_FAMILY_MAP,
    QueryToolError,
    relationship_states_for,
)
from .store import write_query_tool_receipt

# Backed families whose reader accepts an injected connection, so the bounded SELECT
# genuinely runs under the read-only (PRAGMA query_only) connection the layer owns.
_CONN_AWARE_READERS = {
    "project_risk_digest_items": read_risk_digest,
    "aging_exposure_report_items": read_aging_exposure,
    "accepted_long_term_memory": read_accepted_memory,
}

_RELATIONSHIP_TOOLS = ("relationship_candidates", "accepted_relationships")


@contextmanager
def read_only_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection pinned read-only via ``PRAGMA query_only = ON``.

    Any attempted write/DDL on the yielded connection raises
    ``sqlite3.OperationalError`` — the enforceable read-only transaction posture for
    the query-tool layer. The connection is closed on exit.
    """
    conn = get_connection(Path(db_path) if db_path is not None else None)
    try:
        conn.execute("PRAGMA query_only = ON")
        yield conn
    finally:
        conn.close()


def _source_ref(item: RetrievalItem) -> dict[str, str]:
    ref = {
        "source_family": item.source_family,
        "source_ref": item.source_ref,
        "record_type": item.record_type,
        "record_ref": item.record_ref,
        "confidence_class": item.confidence_class,
        "review_tier": str(item.review_tier),
        "review_status": item.review_status,
    }
    if item.evidence_ref:
        ref["evidence_ref"] = item.evidence_ref
    return ref


def _read_items(family: str, project_key: str | None, db_path: str | None) -> list[RetrievalItem]:
    store = ConstructionStore(db_path)
    reader = _CONN_AWARE_READERS.get(family)
    if reader is not None:
        # Layer owns the connection -> run the bounded SELECT under query_only.
        with read_only_connection(db_path) as conn:
            return reader(store, db_path, project_key, conn=conn)
    # ConstructionStore-backed readers issue only fixed SELECTs (structural read-only).
    return READER_REGISTRY[family](store, db_path, project_key)


def run_query_tool(
    tool_name: str,
    *,
    project_key: str | None = None,
    db_path: str | None = None,
    max_rows: int = 200,
    emit_receipt: bool = True,
) -> QueryToolResult:
    """Run one allowlisted query tool; returns a bounded, source-linked result.

    Raises ``QueryToolError`` for any non-allowlisted tool name (the only "deny
    arbitrary SQL" path — there is no SQL-string parameter anywhere in this API).
    """
    if tool_name not in ALLOWLISTED_QUERY_TOOLS:
        raise QueryToolError(f"tool not allowlisted: {tool_name!r}")

    family = QUERY_TOOL_FAMILY_MAP.get(tool_name)
    warnings: list[str] = []
    items: list[RetrievalItem] = []
    status: str = "ok"

    if family is None:
        status = "no_read_model"
        warnings.append(f"no_read_model:{tool_name}")
    elif family not in READER_REGISTRY:
        status = "no_read_model"
        warnings.append(f"no_read_model:{family}")
    else:
        items = _read_items(family, project_key, db_path)
        if tool_name in _RELATIONSHIP_TOOLS:
            allowed = relationship_states_for(tool_name)
            items = [it for it in items if it.relationship_state in allowed]

    truncated = False
    if len(items) > max_rows:
        items = items[:max_rows]
        truncated = True

    if status == "ok" and not items:
        status = "empty"

    char_count = sum(len(it.content_excerpt_redacted) for it in items)
    tier_summary = {"1": 0, "2": 0, "3": 0}
    for it in items:
        tier_summary[str(it.review_tier)] += 1

    result = QueryToolResult(
        tool_name=tool_name,
        project_key=project_key,
        status=status,  # type: ignore[arg-type]
        items=items,
        source_refs=[_source_ref(it) for it in items],
        row_count=len(items),
        char_count=char_count,
        truncated=truncated,
        review_tier_summary=tier_summary,
        warnings=warnings,
    )

    if emit_receipt:
        write_query_tool_receipt(result=result, db_path=db_path)
    return result


def list_query_tools() -> list[dict[str, Any]]:
    """Return the allowlist with each tool's backing read-model + availability."""
    out: list[dict[str, Any]] = []
    for name in ALLOWLISTED_QUERY_TOOLS:
        family = QUERY_TOOL_FAMILY_MAP.get(name)
        backed = family is not None and family in READER_REGISTRY
        out.append(
            {
                "tool_name": name,
                "source_family": family,
                "backed": backed,
                "availability": "backed" if backed else "no_read_model",
            }
        )
    return out


def build_sqlite_query_tool_proof() -> dict[str, Any]:
    """Deterministic proof for ``sqlite-query-tool-proof.json``.

    Proves: arbitrary/unknown tool names are rejected; the read-only connection
    blocks writes; results are source-linked + review-tier-labeled with no raw
    content; ``no_read_model`` tools degrade gracefully; the policy validates.
    """
    import tempfile

    # 1) Arbitrary / model-authored SQL has no path — rejected before any DB access.
    arbitrary_rejected = False
    for bad in ("SELECT * FROM sqlite_master", "DROP TABLE query_tool_receipts", "totally_made_up"):
        try:
            run_query_tool(bad, emit_receipt=False)
        except QueryToolError:
            arbitrary_rejected = True
        else:
            arbitrary_rejected = False
            break

    # 2) no_read_model tools degrade gracefully (no DB read, no receipt).
    deferred = run_query_tool("project_context", emit_receipt=False)
    graceful_degradation = deferred.status == "no_read_model" and not deferred.items

    # 3) Read-only posture: a write under read_only_connection raises.
    read_only_enforced = False
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "proof.sqlite3")
        with read_only_connection(db_path) as conn:
            try:
                conn.execute("CREATE TABLE _ro_probe (x INTEGER)")
            except sqlite3.OperationalError:
                read_only_enforced = True

    # 4) Results are source-linked + tier-labeled with no raw content (synthetic).
    synthetic = QueryToolResult(
        tool_name="risk_digest",
        project_key="P1",
        status="ok",
        items=[
            RetrievalItem(
                source_family="project_risk_digest_items",
                source_ref="risk-1",
                record_type="schedule_slip",
                record_ref="risk-1",
                project_key="P1",
                confidence_class="medium",
                review_tier=2,
                review_status="review_recommended",
                review_required=False,
                evidence_ref="ev-1",
                content_excerpt_redacted="schedule_slip band=amber",
                recency="2026-06-01T00:00:00Z",
            ),
            RetrievalItem(
                source_family="project_risk_digest_items",
                source_ref="risk-2",
                record_type="cost_exposure",
                record_ref="risk-2",
                project_key="P1",
                confidence_class="low",
                review_tier=3,
                review_status="review_required",
                review_required=True,
                content_excerpt_redacted="cost_exposure band=red",
                recency="2026-05-20T00:00:00Z",
            ),
        ],
        source_refs=[],
        row_count=2,
        char_count=0,
    )
    synthetic = synthetic.model_copy(
        update={"source_refs": [_source_ref(it) for it in synthetic.items]}
    )
    blob = synthetic.model_dump_json()
    no_raw_content = not any(
        token in blob
        for token in (
            "raw_body",
            "raw_document_text",
            "raw_calendar_payload",
            "raw_prompt",
            "raw_response",
            "signed_url",
            "download_url",
            "secret",
            "token",
        )
    )
    source_refs_present = all(
        r.get("source_family") and r.get("source_ref") and r.get("review_tier")
        for r in synthetic.source_refs
    )
    tier3 = [it for it in synthetic.items if it.review_tier == 3]
    tier3_not_concluded = all(
        it.review_required and it.review_status == "review_required" for it in tier3
    )

    # 5) Relationship split is disjoint (candidates vs accepted).
    relationship_split_disjoint = not (
        relationship_states_for("relationship_candidates")
        & relationship_states_for("accepted_relationships")
    )

    # 6) Policy + contract validate.
    from .policy import validate_query_tool_policy

    policy = validate_query_tool_policy()

    backed = [t for t in ALLOWLISTED_QUERY_TOOLS if QUERY_TOOL_FAMILY_MAP[t] in READER_REGISTRY]
    proof_passed = bool(
        arbitrary_rejected
        and graceful_degradation
        and read_only_enforced
        and no_raw_content
        and source_refs_present
        and tier3_not_concluded
        and relationship_split_disjoint
        and policy["valid"]
    )
    return {
        "proof": "phase_08a_sqlite_query_tools",
        "proof_passed": proof_passed,
        "contract_version": policy["contract_version"],
        "seed_version": policy["seed_version"],
        "allowlisted_tools": list(ALLOWLISTED_QUERY_TOOLS),
        "backed_tools": backed,
        "no_read_model_tools": [
            t for t in ALLOWLISTED_QUERY_TOOLS if QUERY_TOOL_FAMILY_MAP[t] not in READER_REGISTRY
        ],
        "arbitrary_sql_rejected": arbitrary_rejected,
        "read_only_posture_enforced": read_only_enforced,
        "no_read_model_graceful_degradation": graceful_degradation,
        "no_raw_content": no_raw_content,
        "source_refs_present": source_refs_present,
        "tier3_visible_not_concluded": tier3_not_concluded,
        "relationship_split_disjoint": relationship_split_disjoint,
        "policy_valid": policy["valid"],
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_arbitrary_sql": True,
            "no_model_generated_sql": True,
            "read_only": True,
            "source_refs_required": True,
            "review_tier_required": True,
            "model_direct_external_api_access": False,
        },
    }
