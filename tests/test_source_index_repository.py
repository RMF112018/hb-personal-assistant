"""SourceIndexRepository: explicit FTS sync, idempotency, durable queue, domain links.

Also carries the PI-WI-03a permanent-identity adversarial suite (re-key, fail-closed resolver + v2 codec,
PC-AC-ID-005, the pre-commit lifecycle oracle, the serving-trust gate) and BOTH set-equality guards
(§3.1 22-method current-address register; §3.1b physical re-key occurrence discovery).
"""

from __future__ import annotations

import ast
import inspect
import re
import sqlite3
import uuid
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_index_repository as repo_mod
from hb_assistant.obsidian_mcp.source_connector_models import (
    SourceConnectorValidationError,
    classify_source_ref,
    encode_source_ref,
)
from hb_assistant.obsidian_mcp.source_index_repository import (
    DualAuthorityGuardError,
    LifecycleOracleError,
    SourceIndexRepository,
    source_id_for,
)
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> SourceIndexRepository:
    db = str(tmp_path / "idx.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return SourceIndexRepository(db)


def _file(rel: str, *, sha: str, mtime: int, excerpt: str, project: str | None = None) -> dict:
    return {
        "source_kind": "external_file", "source_root_key": "proj", "rel_path": rel,
        "content_sha256": sha, "mtime_ns": mtime, "file_ext": rel.rsplit(".", 1)[-1],
        "project_key": project, "extraction_status": "ok",
        "text_excerpt": excerpt, "excerpt_char_count": len(excerpt),
    }


def test_upsert_and_search(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/Conduit RFI.pdf", sha="s1", mtime=1,
                                  excerpt="Underground conduit for electrical", project="tropical"))
    hits = repo.search_sources("conduit", limit=5)
    assert len(hits) == 1 and hits[0]["path"] == "a/Conduit RFI.pdf"
    assert hits[0]["result_type"] == "source"
    assert repo.search_sources("conduit", project_key="tropical")
    assert repo.search_sources("conduit", project_key="other") == []


def test_idempotency_lookup_carries_hash(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="abc", mtime=99, excerpt="hello"))
    look = repo.lookup_by_path("external_file", "a/x.md")
    assert look["content_sha256"] == "abc" and look["mtime_ns"] == 99
    assert look["fts_rowid"] is not None


def test_reindex_keeps_single_fts_row(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="alpha conduit"))
    repo.upsert_source_file(_file("a/x.md", sha="s2", mtime=2, excerpt="beta tunnel"))
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0] == 1
    assert repo.search_sources("tunnel")  # new content searchable
    assert repo.search_sources("alpha") == []  # old content gone


def test_delete_removes_fts_and_marks_deleted(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="conduit"))
    repo.mark_deleted("external_file", "a/x.md")
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0] == 0
    assert repo.search_sources("conduit") == []
    assert con.execute(
        "SELECT deleted FROM source_intelligence_sources WHERE rel_path='a/x.md'"
    ).fetchone()[0] == 1


def test_queue_debounce_claim_complete(repo: SourceIndexRepository) -> None:
    e1 = repo.enqueue_event(event_type="modified", rel_path="p/q.md", source_root_key="proj")
    e2 = repo.enqueue_event(event_type="modified", rel_path="p/q.md", source_root_key="proj")
    assert e1 == e2  # coalesced while queued
    claimed = repo.claim_queued(10)
    assert len(claimed) == 1 and claimed[0]["rel_path"] == "p/q.md"
    assert repo.claim_queued(10) == []  # nothing left queued
    repo.complete_event(claimed[0]["event_id"], "done")
    assert repo.index_status()["queued_count"] == 0


def test_requeue_stuck_processing(repo: SourceIndexRepository) -> None:
    repo.enqueue_event(event_type="modified", rel_path="p/q.md")
    repo.claim_queued(10)  # → processing
    con = sqlite3.connect(repo.db_path)
    # force updated_at into the past so the TTL trips
    con.execute("UPDATE source_intelligence_events SET updated_at='2000-01-01T00:00:00+00:00'")
    con.commit()
    assert repo.requeue_stuck(ttl_seconds=60) == 1
    assert repo.index_status()["queued_count"] == 1


def test_domain_link_has_no_text(repo: SourceIndexRepository) -> None:
    # R11-D2: link_domain_source returns a durable source_entity_id and mints via P1 + a synthetic
    # current locator; no raw parent source_id write.
    eid = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                  domain_ref_id="msg-1", project_number="22-101-00")
    con = sqlite3.connect(repo.db_path)
    assert con.execute(
        "SELECT domain_ref_id FROM source_intelligence_sources WHERE source_entity_id=?", (eid,)
    ).fetchone()[0] == "msg-1"
    # synthetic current locator encodes the complete stable identity tuple (kind + table + id)
    root, rel = con.execute(
        "SELECT source_root_key, rel_path FROM source_index_locators "
        "WHERE source_entity_id=? AND is_current_locator=1", (eid,)
    ).fetchone()
    assert root == "domain::email::email_messages" and rel == "msg-1"
    # no text row for a link source
    assert con.execute(
        "SELECT COUNT(*) FROM source_intelligence_text WHERE source_entity_id=?", (eid,)
    ).fetchone()[0] == 0


def test_domain_link_idempotent_relink_same_entity(repo: SourceIndexRepository) -> None:
    # Re-linking the same (kind, table, id) resolves to the SAME entity (path-uniqueness over the
    # synthetic address) — never a second live entity.
    a = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                domain_ref_id="msg-9")
    b = repo.link_domain_source(source_kind="email", domain_ref_table="email_messages",
                                domain_ref_id="msg-9", project_number="22-101-00")
    assert a == b


def test_domain_link_collision_cross_table_distinct_entities(repo: SourceIndexRepository) -> None:
    # R11-D2 collision case (b): same (kind, id) across DIFFERENT domain_ref_table → distinct entities +
    # distinct current locators (the synthetic address includes domain_ref_table).
    e1 = repo.link_domain_source(source_kind="schedule", domain_ref_table="records",
                                 domain_ref_id="123")
    e2 = repo.link_domain_source(source_kind="schedule", domain_ref_table="tasks",
                                 domain_ref_id="123")
    assert e1 != e2
    con = sqlite3.connect(repo.db_path)
    roots = {
        r[0]
        for r in con.execute(
            "SELECT source_root_key FROM source_index_locators "
            "WHERE source_entity_id IN (?,?) AND is_current_locator=1", (e1, e2)
        ).fetchall()
    }
    assert roots == {"domain::schedule::records", "domain::schedule::tasks"}


def test_domain_link_cross_kind_same_table_id_fails_closed(repo: SourceIndexRepository) -> None:
    # R11-D2 collision case (a): same (domain_ref_table, id) across DIFFERENT source_kind. REPO-TRUTH
    # CONFLICT: the frozen V128 index idx_si_sources_domain is UNIQUE(domain_ref_table, domain_ref_id)
    # (no source_kind), so a distinct second entity for the SAME (table,id) is impossible. The synthetic
    # kind-specific locator prevents a SILENT REBIND to the first entity (P-B); the frozen parent UNIQUE
    # then refuses the second link fail-closed (IntegrityError) rather than aliasing. Repo truth is the
    # highest authority, so the accepted-plan "distinct entities" here is superseded by a fail-closed
    # refusal. (Flagged for reauthorization — see the implementation report.)
    repo.link_domain_source(source_kind="email", domain_ref_table="records", domain_ref_id="777")
    with pytest.raises(sqlite3.IntegrityError):
        repo.link_domain_source(source_kind="schedule", domain_ref_table="records",
                                domain_ref_id="777")


def test_register_roots_deactivates_removed(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a/x.md", sha="s1", mtime=1, excerpt="x"))
    repo.register_source_roots([{"source_root_key": "other", "enabled": True}])  # 'proj' removed
    con = sqlite3.connect(repo.db_path)
    assert con.execute(
        "SELECT active FROM source_intelligence_sources WHERE source_root_key='proj'"
    ).fetchone()[0] == 0


# ============================================================================================
# PI-WI-03a permanent-identity adversarial suite
# ============================================================================================

def _legacy_source_id(repo: SourceIndexRepository, entity_id: str) -> str:
    con = sqlite3.connect(repo.db_path)
    return con.execute(
        "SELECT source_id FROM source_index_locators WHERE source_entity_id=? AND is_current_locator=1",
        (entity_id,),
    ).fetchone()[0]


# ---- v2 codec fail-closed (per branch) ----

def test_v2_codec_roundtrip_and_classification() -> None:
    eid = uuid.uuid4().hex
    ref = encode_source_ref(eid)
    assert ref.startswith("hbsrc2_")
    assert classify_source_ref(source_ref=ref) == ("entity", eid)
    assert classify_source_ref(source_id=eid) == ("legacy", eid)  # bare 32-hex = legacy, never entity


def test_v2_codec_fail_closed_branches() -> None:
    eid = uuid.uuid4().hex
    ref = encode_source_ref(eid)
    # unknown prefix
    with pytest.raises(SourceConnectorValidationError):
        classify_source_ref(source_ref="hbsrc9_" + ref[len("hbsrc2_"):])
    # tampered body (corrupt a char inside the id portion, not the low-bit tail)
    i = len("hbsrc2_") + 4
    tampered = ref[:i] + ("A" if ref[i] != "A" else "B") + ref[i + 1:]
    with pytest.raises(SourceConnectorValidationError):
        classify_source_ref(source_ref=tampered)
    # a v1 hbsrc1_ ref is LEGACY, never entity (no v1 entity fallback)
    from hb_assistant.obsidian_mcp.source_connector_models import (
        _SOURCE_REF_PREFIX,
        _b64u_encode,
        _source_id_checksum,
    )
    v1 = _SOURCE_REF_PREFIX + _b64u_encode(f"{eid}{_source_id_checksum(eid)}".encode())
    assert classify_source_ref(source_ref=v1) == ("legacy", eid)
    # neither id nor ref
    with pytest.raises(SourceConnectorValidationError):
        classify_source_ref()
    # a non-hex bare id is not a legacy handle
    with pytest.raises(SourceConnectorValidationError):
        classify_source_ref(source_id="not-hex")


def test_resolve_entity_v2_and_legacy(repo: SourceIndexRepository) -> None:
    eid = repo.upsert_source_file(_file("r/a.md", sha="s1", mtime=1, excerpt="hello"))
    legacy = _legacy_source_id(repo, eid)
    assert repo.resolve_entity(source_ref=encode_source_ref(eid)) == eid          # v2 entity
    assert repo.resolve_entity(source_id=legacy) == eid                            # legacy DISTINCT
    # a bare entity id presented as source_id (legacy) does NOT fall back to the entity
    assert repo.resolve_entity(source_id=eid) is None
    # unknown entity ref → None
    assert repo.resolve_entity(source_ref=encode_source_ref(uuid.uuid4().hex)) is None


# ---- PC-AC-ID-005: DISTINCT legacy resolver ----

def test_pc_ac_id_005_move_deleted_reuse_neverseen(repo: SourceIndexRepository) -> None:
    # index at a path, capture its legacy handle
    eid = repo.upsert_source_file(_file("p/orig.md", sha="s1", mtime=1, excerpt="x"))
    legacy = _legacy_source_id(repo, eid)
    # deleted-not-reused → resolves to the original TOMBSTONED entity (exactly one locator with that sid)
    repo.mark_deleted("external_file", "p/orig.md")
    assert repo.resolve_entity(source_id=legacy) == eid
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT status FROM source_index_entities WHERE source_entity_id=?",
                       (eid,)).fetchone()[0] == "TOMBSTONED"
    # same-path reuse (≥2 locators carry the same legacy sid) → UNRESOLVED (never rebinds to current)
    eid2 = repo.upsert_source_file(_file("p/orig.md", sha="s2", mtime=2, excerpt="y"))
    assert eid2 != eid
    assert repo.resolve_entity(source_id=legacy) is None
    # never-seen legacy handle → UNRESOLVED
    assert repo.resolve_entity(source_id=source_id_for("external_file", source_root_key="proj",
                                                       rel_path="never/seen.md")) is None


# ---- lifecycle oracle ROLLBACK ----

def test_lifecycle_oracle_rolls_back_violation(
    repo: SourceIndexRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force a mint that OMITS the current locator → a LIVE entity with zero current locators violates the
    # pre-commit oracle → LifecycleOracleError, and the whole transaction rolls back (nothing persisted).
    monkeypatch.setattr(repo, "_insert_current_locator", lambda *a, **k: None)
    with pytest.raises(LifecycleOracleError):
        repo.upsert_source_file(_file("o/a.md", sha="s1", mtime=1, excerpt="x"))
    con = sqlite3.connect(repo.db_path)
    assert con.execute("SELECT COUNT(*) FROM source_index_entities").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM source_intelligence_sources").fetchone()[0] == 0


def test_lifecycle_oracle_detects_tombstoned_with_current_locator(
    repo: SourceIndexRepository,
) -> None:
    eid = repo.upsert_source_file(_file("o/b.md", sha="s1", mtime=1, excerpt="x"))
    with sqlite3.connect(repo.db_path) as c:  # corrupt: TOMBSTONED but keep its current locator
        c.execute("UPDATE source_index_entities SET status='TOMBSTONED' WHERE source_entity_id=?", (eid,))
        c.commit()
    c2 = sqlite3.connect(repo.db_path)
    with pytest.raises(LifecycleOracleError):
        repo._assert_lifecycle_oracle(c2, eid)


def test_lifecycle_error_and_guard_error_types() -> None:
    assert issubclass(LifecycleOracleError, RuntimeError)
    assert issubclass(DualAuthorityGuardError, RuntimeError)


# ---- serving-trust gate: EXCLUDE / DEGRADE / count-exclusivity ----

def _mark_policy_stale(repo: SourceIndexRepository, entity_id: str) -> None:
    with sqlite3.connect(repo.db_path) as c:
        c.execute("UPDATE source_index_locators SET policy_validation_state='policy_stale' "
                  "WHERE source_entity_id=? AND is_current_locator=1", (entity_id,))
        c.commit()


def test_serving_trust_search_excludes_policy_stale(repo: SourceIndexRepository) -> None:
    eid = repo.upsert_source_file(_file("s/a.md", sha="s1", mtime=1, excerpt="quantum tunnelling"))
    assert repo.search_sources("quantum")            # searchable while validated
    _mark_policy_stale(repo, eid)
    assert repo.search_sources("quantum") == []       # EXCLUDE: policy-stale filtered out of search
    assert repo.search_source_files("quantum") == []


def test_serving_trust_counts_exclusivity(repo: SourceIndexRepository) -> None:
    eid = repo.upsert_source_file(_file("c/a.md", sha="s1", mtime=1, excerpt="alpha beta"))
    counts = repo.content_status_counts("proj")
    assert counts["content_searchable"] >= 1 and counts["policy_unverified"] == 0
    _mark_policy_stale(repo, eid)
    counts2 = repo.content_status_counts("proj")
    # count-exclusivity: a policy-stale locator no longer counts as searchable; it moves to the
    # policy_unverified bucket (never both).
    assert counts2["content_searchable"] == 0
    assert counts2["policy_unverified"] == 1


def test_serving_trust_list_degrades_marks_rows(repo: SourceIndexRepository) -> None:
    eid = repo.upsert_source_file(_file("l/a.md", sha="s1", mtime=1, excerpt="gamma"))
    rows = repo.list_source_files("proj")
    assert rows and all(r["policy_unverified"] is False for r in rows)
    _mark_policy_stale(repo, eid)
    rows2 = repo.list_source_files("proj")
    # DEGRADE (not exclude): the row is still returned, but MARKED policy_unverified.
    marked = [r for r in rows2 if r["rel_path"] == "l/a.md"]
    assert marked and marked[0]["policy_unverified"] is True


def test_reindex_revalidates_policy(repo: SourceIndexRepository) -> None:
    eid = repo.upsert_source_file(_file("v/a.md", sha="s1", mtime=1, excerpt="delta"))
    _mark_policy_stale(repo, eid)
    assert repo.search_sources("delta") == []
    # a real reindex that stamps a fingerprint clears policy_validation_state in the same write
    repo.upsert_source_file({**_file("v/a.md", sha="s2", mtime=2, excerpt="delta"),
                             "last_indexed_fingerprint": "fp-current"})
    assert repo.search_sources("delta")   # revalidated → searchable again


# ============================================================================================
# F-002 — go-forward relationship dst_ref persisted as a v2 (hbsrc2_) entity ref
# ============================================================================================

def test_f002_source_relationship_persists_v2_dst_ref(repo: SourceIndexRepository) -> None:
    src = repo.upsert_source_file(_file("d/a.md", sha="s1", mtime=1, excerpt="alpha"))
    tgt = repo.upsert_source_file(_file("d/b.md", sha="s2", mtime=2, excerpt="beta"))
    # source_notes builds a 'source' link with a BARE entity id as dst_ref; the write path must persist v2.
    repo.record_relationships(src, [{"dst_kind": "source", "dst_ref": tgt,
                                     "relation": "links_to", "confidence": "high",
                                     "evidence": {"sheet": "A-101"}}])
    con = sqlite3.connect(repo.db_path)
    stored = con.execute(
        "SELECT dst_ref FROM source_intelligence_relationships "
        "WHERE src_source_entity_id=? AND dst_kind='source'", (src,)
    ).fetchone()[0]
    # DB assertion: a newly-written SOURCE relationship carries an hbsrc2_ v2 dst_ref (never bare/legacy)
    assert stored.startswith("hbsrc2_")
    assert classify_source_ref(source_ref=stored) == ("entity", tgt)
    # the read resolver still resolves the v2 dst_ref to the target's CURRENT rel_path
    link = [r for r in repo.list_relationships(src) if r["dst_kind"] == "source"][0]
    assert link["dst_rel_path"] == "d/b.md"


def test_f002_unresolvable_source_target_is_skipped(repo: SourceIndexRepository) -> None:
    # a 'source' target that is neither a live entity nor a resolvable legacy handle is NOT persisted
    # (fail-closed: never a bare/legacy source dst_ref), preserving the hbsrc2_-only invariant.
    src = repo.upsert_source_file(_file("d/a.md", sha="s1", mtime=1, excerpt="alpha"))
    repo.record_relationships(src, [{"dst_kind": "source",
                                     "dst_ref": "f" * 32, "relation": "links_to"}])
    con = sqlite3.connect(repo.db_path)
    assert con.execute(
        "SELECT COUNT(*) FROM source_intelligence_relationships "
        "WHERE src_source_entity_id=? AND dst_kind='source'", (src,)
    ).fetchone()[0] == 0


# ============================================================================================
# F-004 — lifecycle oracle realizes the current-locator uniqueness contract (explicit rechecks)
# ============================================================================================

def test_f004_oracle_rejects_duplicate_current_per_live_path(repo: SourceIndexRepository) -> None:
    # The non-redundant recheck: two DISTINCT entities each with ONE current locator at the SAME live
    # (root, rel_path). bad_live/bad_tomb/dup_entity all pass; only the explicit per-live-path query fires.
    e1 = repo.upsert_source_file(_file("u/a.md", sha="s1", mtime=1, excerpt="x"))
    e2 = repo.upsert_source_file(_file("u/b.md", sha="s2", mtime=2, excerpt="y"))
    con = sqlite3.connect(repo.db_path)
    # bypass the V128 partial-unique path index to inject the schema-forbidden duplicate-current locator
    con.execute("DROP INDEX IF EXISTS idx_locators_active_path")
    root, rel = con.execute(
        "SELECT source_root_key, rel_path FROM source_index_locators "
        "WHERE source_entity_id=? AND is_current_locator=1", (e1,)
    ).fetchone()
    con.execute("UPDATE source_index_locators SET source_root_key=?, rel_path=? "
                "WHERE source_entity_id=? AND is_current_locator=1", (root, rel, e2))
    con.commit()
    c2 = sqlite3.connect(repo.db_path)
    # scoped hot-path check (from e1) AND the full-scan invariant both fail closed via the new query
    with pytest.raises(LifecycleOracleError, match="duplicate_current_locator_per_live_path"):
        repo._assert_lifecycle_oracle(c2, e1)
    with pytest.raises(LifecycleOracleError, match="duplicate_current_locator_per_live_path"):
        repo._assert_lifecycle_oracle(c2)


def test_f004_oracle_rejects_duplicate_current_per_entity(repo: SourceIndexRepository) -> None:
    # A per-entity duplicate-current locator (one entity, two current locators) is rejected. bad_live is
    # the first detector for a LIVE entity; the explicit dup_entity query is the defence-in-depth backstop.
    e1 = repo.upsert_source_file(_file("w/a.md", sha="s1", mtime=1, excerpt="x"))
    con = sqlite3.connect(repo.db_path)
    con.execute("DROP INDEX IF EXISTS idx_locators_current_per_entity")
    con.execute("DROP INDEX IF EXISTS idx_locators_active_path")
    con.execute("INSERT INTO source_index_locators(locator_id, source_entity_id, source_id, "
                "source_root_key, rel_path, is_current_locator, tombstoned_at, generation_seq) "
                "VALUES (?,?,?,?,?,1,NULL,0)", (uuid.uuid4().hex, e1, "dup", "proj", "w/dup.md"))
    con.commit()
    c2 = sqlite3.connect(repo.db_path)
    with pytest.raises(LifecycleOracleError):
        repo._assert_lifecycle_oracle(c2, e1)


# ============================================================================================
# F-001 — dual-authority + physical re-key guard: exact, complete, FAIL-CLOSED occurrence registry
# ============================================================================================
# Replaces the R1 token-presence Guard-1 and the silently-skipping Guard-2 (review finding
# CP-PI-WI-03A-IMPL-F-001). A single fail-closed analyzer AST-discovers EVERY execute/executemany in
# source_index_repository.py, reconstructs its SQL (following intra-function assignments / concatenations /
# f-strings / %-format / conditional fragments) or FAILS CLOSED — never a silent skip — and builds an
# occurrence registry keyed by (enclosing symbol, call ordinal, authority class ∈
# {CA,OW,LKA,MOVE_TRANSITION,non-address}, normalized SQL). Coverage spans the 7 V128-re-keyed content
# tables PLUS the two identity tables (source_index_entities, source_index_locators), over execute AND
# executemany. The frozen EXPECTED set is proven SET-EQUAL against live discovery: any addition, omission,
# renamed symbol, changed SQL, or role change fails closed. On top of set-equality the analyzer proves the
# dual-authority invariants (PC-AC-ID-001): _mint_entity is the SOLE source_index_entities insert;
# _insert_current_locator the SOLE locator insert; the current/tombstone flags are written ONLY by
# _demote_current_locator; no content-table statement carries a raw parent `source_id`; and no
# renamed_from_source_id / bare src_source_id survives.

_CONTENT_TABLES = (
    "source_intelligence_sources", "source_intelligence_metadata", "source_intelligence_text",
    "source_intelligence_summaries", "source_intelligence_chunks",
    "source_intelligence_generated_notes", "source_intelligence_relationships",
)
_IDENTITY_TABLES = ("source_index_entities", "source_index_locators")
_REGISTERED_TABLES = _CONTENT_TABLES + _IDENTITY_TABLES
_MOVE_METHODS = frozenset({
    "_confirmed_move_locked", "apply_confirmed_same_root_move",
    "apply_owned_confirmed_same_root_move",
})
# OW writes ONLY these F-005 observation / serving-trust columns onto an already-resolved current locator.
_OW_SET_COLUMNS = frozenset({
    "last_seen_generation", "last_seen_at", "last_indexed_fingerprint", "policy_validation_state",
})
_IDENTITY_TOKENS = ("source_entity_id", "src_source_entity_id")
_ADDRESS_TOKENS = ("source_id", "source_root_key", "rel_path")


class _Unreconstructable(Exception):
    """Internal: an execute() SQL argument that cannot be reduced to a string (→ fail closed)."""


def _own_scope_nodes(node: ast.AST):
    """Descendants of ``node`` in the SAME function scope (never crosses into a nested
    FunctionDef/AsyncFunctionDef/Lambda), so per-symbol ordinals + assignment tracking cannot leak
    across scopes (a nested-scope evasion still fails closed)."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(n))


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ---- F-001 R3B: fail-closed, call-site-aware, control-flow-safe reaching-definition analyzer ----
# Stable rejection categories (PLAN-R3B-F-013/F-014/F-018). Each is attached to the raised
# ``DualAuthorityGuardError`` as ``.category`` so a negative fixture asserts the INTENDED path, not
# merely that *some* exception fired.
_CAT_FORBIDDEN = "forbidden_dual_authority_occurrence"
_CAT_AMBIGUOUS = "ambiguous_control_flow"
_CAT_APPEND = "unsupported_append_control_flow"
_CAT_LIMIT = "candidate_expansion_limit"
_CAT_UNRECON = "unreconstructable_sql"
_CAT_ALIAS = "unsupported_execute_alias"
_CAT_GETATTR = "unsupported_dynamic_getattr"
_CAT_SCRIPT = "unsupported_sql_execution_form"
_CAT_CYCLE = "cyclic_definition"
_CAT_INCONSISTENT = "inconsistent_candidate_classification"

# Bounded enumeration (PLAN-R3B-F-008/F-022): at most N=5 admissible one-shot conditional append sites
# per execute call (≤ 32 candidate strings). AST inspection at 74697519 shows observed max = 3
# (search_source_files), so N=5 carries 2 sites of headroom.
_MAX_COND_APPEND_SITES = 5
_MAX_CANDIDATES = 32

# Compound-statement AST node types whose body-like fields introduce a control-flow container.
_BLOCK_TYPES = tuple(
    t
    for t in (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try,
        ast.ExceptHandler, getattr(ast, "TryStar", None), getattr(ast, "Match", None),
        getattr(ast, "match_case", None),
    )
    if isinstance(t, type)
)
_BRANCH_FIELDS = ("body", "orelse", "finalbody", "handlers", "cases")


def _guard(category: str, message: str) -> DualAuthorityGuardError:
    """Build a categorized :class:`DualAuthorityGuardError` (``.category`` = stable reason code)."""
    err = DualAuthorityGuardError(f"{category}: {message}")
    err.category = category  # type: ignore[attr-defined]
    return err


def _pos(node: ast.AST) -> tuple[int, int]:
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))


class _Recon:
    """Reconstruction result for one SQL expression at one execute call: the deterministic §(a3)
    representative (all admissible appends applied, source order), the full set of runtime candidate
    strings (conditional appends forked), and the count of admissible conditional append sites."""

    __slots__ = ("rep", "candidates", "cond")

    def __init__(self, rep: str, candidates, cond: int) -> None:
        self.rep = rep
        self.candidates = frozenset(candidates)
        self.cond = cond


def _scope_parents(func: ast.AST) -> tuple[dict, dict]:
    """``child -> parent`` and ``child -> field-name-in-parent`` maps for ``func``'s OWN scope (never
    descending into a nested FunctionDef/AsyncFunctionDef/Lambda)."""
    parents: dict = {}
    field_of: dict = {}

    def visit(node: ast.AST) -> None:
        for fname, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for child in children:
                if isinstance(child, ast.AST):
                    parents[child] = node
                    field_of[child] = fname
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                        continue
                    visit(child)

    visit(func)
    return parents, field_of


def _stmt_chain(node: ast.AST, parents: dict, field_of: dict) -> list:
    """The control-flow container chain enclosing ``node`` (outermost → innermost) as
    ``[(compound_stmt, branch_field), ...]`` — the syntactic path used (no CFG) to distinguish a
    straight-line/linear step from a control-flow-nested one."""
    chain: list = []
    cur = node
    while cur in parents:
        p = parents[cur]
        fld = field_of.get(cur)
        if isinstance(p, _BLOCK_TYPES) and fld in _BRANCH_FIELDS:
            chain.append((p, fld))
        cur = p
    chain.reverse()
    return chain


def _classify_reach(a_node: ast.AST, op: str, ctx: dict) -> str:
    """Classify a lexically-preceding assignment ``a_node`` (``op`` ∈ {``=``, ``+=``}) relative to the
    governed execute call ``ctx['call']`` — PURELY SYNTACTIC (PLAN-R3B-F-013/F-014, operator + container,
    NEVER string similarity). Returns ``'replace'`` (unconditional/same-block ``=``), ``'uappend'``
    (straight-line unconditional ``+=``), or ``'cappend'`` (admissible one-shot conditional ``+=``);
    otherwise raises the category-specific guard."""
    call = ctx["call"]
    ca = _stmt_chain(a_node, ctx["parents"], ctx["field_of"])
    ck = _stmt_chain(call, ctx["parents"], ctx["field_of"])
    i = 0
    while i < len(ca) and i < len(ck) and ca[i] == ck[i]:
        i += 1
    extra_a = ca[i:]
    if not extra_a:
        # Same immediate block, or an ancestor block shared with the call, entered before the call:
        # straight-line. A `=` is the §(a2) same-block/linear single value; a `+=` is unconditional.
        return "replace" if op == "=" else "uappend"
    if len(extra_a) == 1:
        stmt, fld = extra_a[0]
        if (
            op == "+="
            and isinstance(stmt, ast.If)
            and fld == "body"
            and not stmt.orelse
            and _pos(stmt) < _pos(call)
        ):
            # AugAssign(Add) directly in the body of a simple `if` (no else/elif) on the
            # unconditionally-entered path to the call → admissible ONE-SHOT conditional append.
            return "cappend"
    if op == "+=":
        raise _guard(
            _CAT_APPEND,
            f"append to '{getattr(a_node.target, 'id', '?') if hasattr(a_node, 'target') else '?'}' "
            "in unsupported control flow (loop-accumulated / try / except / match / if-else / nested)",
        )
    raise _guard(
        _CAT_AMBIGUOUS,
        "control-flow-nested assignment can produce a distinct reaching value (KILL by AST node type)",
    )


def _name_assignments(func: ast.AST) -> dict:
    """``name -> [(node, op, rhs), ...]`` for every ``=``-family / ``+=`` (str-building) binding of a
    Name in ``func``'s own scope. RETAINS each assignment node so discovery can filter to
    lexically-preceding steps and classify its control-flow container."""
    out: dict = {}
    for n in _own_scope_nodes(func):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            out.setdefault(n.targets[0].id, []).append((n, "=", n.value))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            out.setdefault(n.target.id, []).append((n, "=", n.value))
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and isinstance(n.op, ast.Add):
            out.setdefault(n.target.id, []).append((n, "+=", n.value))
        elif isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
            out.setdefault(n.target.id, []).append((n, "=", n.value))
    return out


def _combine(left: _Recon, right: _Recon) -> _Recon:
    """Concatenate two reconstructions (BinOp ``+`` / JoinedStr fold): representative = rep+rep, the
    candidate set is the (bounded) Cartesian product, conditional-site counts add."""
    cands = {a + b for a in left.candidates for b in right.candidates}
    if len(cands) > _MAX_CANDIDATES:
        raise _guard(_CAT_LIMIT, "candidate product exceeds the 32-string bound")
    return _Recon(left.rep + right.rep, cands, left.cond + right.cond)


def _reconstruct_expr(node: ast.AST, ctx: dict, seen: frozenset) -> _Recon:
    """Reduce an expression to its runtime SQL candidate set + §(a3) representative, following simple
    Name reaching-definitions / ``+`` / ``%`` / f-string / conditional fragments. Fail closed
    (category-specific ``DualAuthorityGuardError``) on anything not reducible — NEVER a silent skip.
    The governed execute call position (``ctx['call']``) threads through every recursion (F-016)."""
    s = _const_str(node)
    if s is not None:
        return _Recon(s, {s}, 0)
    if isinstance(node, ast.Constant):
        raise _guard(_CAT_UNRECON, f"non-string constant SQL argument ({node.value!r})")
    if isinstance(node, ast.JoinedStr):
        joined = "".join(
            _const_str(v) if _const_str(v) is not None else "{}" for v in node.values
        )
        return _Recon(joined, {joined}, 0)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _combine(
            _reconstruct_expr(node.left, ctx, seen), _reconstruct_expr(node.right, ctx, seen)
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        # "<literal with %-placeholders>" % (...) — the table/column names live in the literal left.
        return _reconstruct_expr(node.left, ctx, seen)
    if isinstance(node, ast.IfExp):
        # conditional SQL fragment: keep BOTH branches so a forbidden token in either stays visible.
        return _combine(
            _reconstruct_expr(node.body, ctx, seen), _reconstruct_expr(node.orelse, ctx, seen)
        )
    if isinstance(node, ast.Name):
        return _reconstruct_name(node.id, ctx, seen)
    raise _guard(_CAT_UNRECON, f"unreconstructable SQL expression ({type(node).__name__})")


def _reconstruct_name(name: str, ctx: dict, seen: frozenset) -> _Recon:
    """Reaching-definition reconstruction of a Name at ``ctx['call']`` — SOURCE-ORDERED event stream
    (PLAN-R3B-F-008/F-022, NO pre-folding): unconditional ``=`` replaces the candidate set; unconditional
    ``+=`` appends to every candidate; an admissible one-shot conditional ``+=`` forks {unchanged} ∪
    {appended}; dedup after EVERY event; the 32-candidate bound after EVERY fork. The representative
    takes the applied branch at every conditional append (§(a3))."""
    if name in seen:
        raise _guard(_CAT_CYCLE, f"cyclic/recursive definition of '{name}'")
    seen = seen | {name}
    call_pos = _pos(ctx["call"])
    events = [
        (_pos(a_node), a_node, op, rhs)
        for (a_node, op, rhs) in ctx["assignmap"].get(name, [])
        if _pos(a_node) < call_pos  # assignments AT/AFTER the call are excluded (post-call bypass fix)
    ]
    if not events:
        raise _guard(_CAT_UNRECON, f"no reaching definition for '{name}' before the call")
    events.sort(key=lambda e: e[0])
    rep: str | None = None
    candidates: set[str] | None = None
    cond = 0
    for _p, a_node, op, rhs in events:
        kind = _classify_reach(a_node, op, ctx)
        sub = _reconstruct_expr(rhs, ctx, seen)
        if kind == "replace":
            rep, candidates, cond = sub.rep, set(sub.candidates), sub.cond
        elif candidates is None or rep is None:
            raise _guard(_CAT_UNRECON, f"append to '{name}' with no reconstructable preceding value")
        elif kind == "uappend":
            rep = rep + sub.rep
            candidates = {c + d for c in candidates for d in sub.candidates}
            cond += sub.cond
        else:  # cappend — fork {unchanged} ∪ {appended}
            rep = rep + sub.rep
            candidates = candidates | {c + d for c in candidates for d in sub.candidates}
            cond += 1 + sub.cond
        if cond > _MAX_COND_APPEND_SITES:
            raise _guard(_CAT_LIMIT, f"'{name}' exceeds N={_MAX_COND_APPEND_SITES} conditional append sites")
        if len(candidates) > _MAX_CANDIDATES:
            raise _guard(_CAT_LIMIT, f"'{name}' exceeds the 32-candidate bound")
    assert rep is not None and candidates is not None
    return _Recon(rep, candidates, cond)


def _norm_sql(sql: str) -> str:
    return " ".join(sql.split())


def _classify(symbol: str, sql: str) -> str:
    """Deterministic R8 §5.4 authority class from the enclosing symbol + normalized SQL."""
    if symbol in _MOVE_METHODS:
        return "MOVE_TRANSITION"
    if sql.startswith("UPDATE source_index_locators SET"):
        set_clause = sql[len("UPDATE source_index_locators SET"):].split(" WHERE ")[0]
        cols = set(re.findall(r"([a-z_]+)\s*=", set_clause))
        if cols and cols <= _OW_SET_COLUMNS:
            return "OW"
    has_identity = any(re.search(rf"\b{t}\b", sql) for t in _IDENTITY_TOKENS)
    has_address = any(re.search(rf"\b{t}\b", sql) for t in _ADDRESS_TOKENS)
    if not has_identity and not has_address:
        return "non-address"
    return "CA"


def _forbidden_reason(symbol: str, sql: str) -> str | None:
    """PC-AC-ID-001 dual-authority violation in a normalized candidate SQL, or None. Applied to EVERY
    runtime candidate (§(a1)) — a forbidden pattern reachable on ANY branch fails closed."""
    if "INSERT INTO source_index_entities" in sql and symbol != "_mint_entity":
        return f"source_index_entities insert outside _mint_entity: {symbol}"
    if "INSERT INTO source_index_locators" in sql and symbol != "_insert_current_locator":
        return f"source_index_locators insert outside _insert_current_locator: {symbol}"
    if sql.startswith("UPDATE source_index_locators SET"):
        set_clause = sql[len("UPDATE source_index_locators SET"):].split(" WHERE ")[0]
        written = set(re.findall(r"([a-z_]+)\s*=", set_clause))
        if (written & {"is_current_locator", "tombstoned_at", "source_id"}
                and symbol != "_demote_current_locator"):
            return f"raw current-locator/address write outside the lifecycle: {symbol}"
    if "renamed_from_source_id" in sql:
        return f"forbidden renamed_from_source_id lineage authority: {symbol}"
    if re.search(r"\bsrc_source_id\b", sql):
        return f"un-re-keyed src_source_id column: {symbol}"
    if ("source_index_locators" not in sql and "source_intelligence_events" not in sql
            and re.search(r"\bsource_id\b", sql)):
        return f"raw parent-address source_id on a content table: {symbol}"
    return None


def _scan_unsupported_forms(tree: ast.AST) -> None:
    """Bounded fail-closed alias / dynamic-getattr / executescript policy (PLAN-R3-F-002/F-010/F-019/
    F-020), applied to EVERY own-scope function — independent of whether that function also contains a
    directly-discovered execute call: any ``.execute``/``.executemany`` Attribute that is not the immediate
    func of a discovered Call → ``unsupported_execute_alias``; any ``executescript`` reference →
    ``unsupported_sql_execution_form``; any ``getattr`` with a non-literal attribute-name →
    ``unsupported_dynamic_getattr`` (constant ``getattr(x, 'execute'|'executescript')`` covered too)."""
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nodes = list(_own_scope_nodes(func))
        direct = {
            id(n.func)
            for n in nodes
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("execute", "executemany")
        }
        for n in nodes:
            if isinstance(n, ast.Attribute):
                if n.attr == "executescript":
                    raise _guard(_CAT_SCRIPT, f"executescript reference in {func.name}")
                if n.attr in ("execute", "executemany") and id(n) not in direct:
                    raise _guard(_CAT_ALIAS, f"aliased .{n.attr} bound method in {func.name}")
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "getattr" and len(n.args) >= 2):
                attr = _const_str(n.args[1])
                if attr is None:
                    raise _guard(_CAT_GETATTR, f"non-literal getattr attribute in {func.name}")
                if attr == "executescript":
                    raise _guard(_CAT_SCRIPT, f"getattr(_, 'executescript') in {func.name}")
                if attr in ("execute", "executemany"):
                    raise _guard(_CAT_ALIAS, f"getattr(_, '{attr}') in {func.name}")


def _discover_occurrences(src: str) -> list[tuple[str, int, str, str]]:
    """(symbol, ordinal, authority_class, normalized_sql) for every execute/executemany touching a
    registered table. Reconstructs each statement's runtime candidate set (source-ordered event stream)
    or FAILS CLOSED (``DualAuthorityGuardError``); emits EXACTLY ONE deterministic §(a3) representative
    per call. The ordinal is the call's source-order position among ALL execute/executemany in the
    enclosing symbol."""
    tree = ast.parse(src)
    _scan_unsupported_forms(tree)
    occ: list[tuple[str, int, str, str]] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parents, field_of = _scope_parents(func)
        assignmap = _name_assignments(func)
        calls = [
            n for n in _own_scope_nodes(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("execute", "executemany")
        ]
        calls.sort(key=lambda n: (n.lineno, n.col_offset))
        for ordinal, n in enumerate(calls):
            if not n.args:
                raise _guard(
                    _CAT_UNRECON,
                    f"execute with no SQL argument in {func.name} @L{n.lineno} (cannot prove safe)",
                )
            ctx = {"call": n, "parents": parents, "field_of": field_of, "assignmap": assignmap}
            recon = _reconstruct_expr(n.args[0], ctx, frozenset())
            # §(a1) safety: EVERY runtime candidate is reconstructed + checked (not only base+suffix).
            cand_norms = {_norm_sql(csql) for csql in recon.candidates}
            for csql in cand_norms:
                reason = _forbidden_reason(func.name, csql)
                if reason is not None:
                    raise _guard(_CAT_FORBIDDEN, reason)
            rep_sql = _norm_sql(recon.rep)
            if any(t in rep_sql for t in _REGISTERED_TABLES):
                # §(a3): the representative is emitted ONLY if every candidate shares the same
                # registered-table set + authority class (differ only in non-authority clauses).
                tabsets = {
                    frozenset(t for t in _REGISTERED_TABLES if t in csql) for csql in cand_norms
                }
                classes = {_classify(func.name, csql) for csql in cand_norms}
                if len(tabsets) > 1 or len(classes) > 1:
                    raise _guard(
                        _CAT_INCONSISTENT,
                        f"candidates disagree on registered-table set / class in {func.name} "
                        f"@L{n.lineno} (fail closed, no occurrence)",
                    )
                occ.append((func.name, ordinal, _classify(func.name, rep_sql), rep_sql))
    return occ


def _assert_dual_authority(occ: list[tuple[str, int, str, str]]) -> None:
    """PC-AC-ID-001 structural invariants over the discovered registry — each violation fails closed."""
    for symbol, _ordinal, _cls, sql in occ:
        if "INSERT INTO source_index_entities" in sql and symbol != "_mint_entity":
            raise DualAuthorityGuardError(
                f"source_index_entities insert outside _mint_entity: {symbol}"
            )
        if "INSERT INTO source_index_locators" in sql and symbol != "_insert_current_locator":
            raise DualAuthorityGuardError(
                f"source_index_locators insert outside _insert_current_locator: {symbol}"
            )
        if sql.startswith("UPDATE source_index_locators SET"):
            set_clause = sql[len("UPDATE source_index_locators SET"):].split(" WHERE ")[0]
            written = set(re.findall(r"([a-z_]+)\s*=", set_clause))
            if (written & {"is_current_locator", "tombstoned_at", "source_id"}
                    and symbol != "_demote_current_locator"):
                raise DualAuthorityGuardError(
                    f"raw current-locator/address write outside the lifecycle: {symbol}: {sql}"
                )
        if "renamed_from_source_id" in sql:
            raise DualAuthorityGuardError(
                f"forbidden renamed_from_source_id lineage authority: {symbol}"
            )
        if re.search(r"\bsrc_source_id\b", sql):
            raise DualAuthorityGuardError(f"un-re-keyed src_source_id column: {symbol}")
        # No content-table statement may carry a raw parent `source_id` (re-keyed to source_entity_id).
        # A bare source_id is legitimate ONLY on the locator table or the out-of-scope events table.
        if ("source_index_locators" not in sql and "source_intelligence_events" not in sql
                and re.search(r"\bsource_id\b", sql)):
            raise DualAuthorityGuardError(
                f"raw parent-address source_id on a content table: {symbol}: {sql}"
            )


def _verify_dual_authority(src: str) -> list[tuple[str, int, str, str]]:
    occ = _discover_occurrences(src)
    _assert_dual_authority(occ)
    return occ


# Frozen occurrence registry at the reviewed commit (63ab7c5b + R2), proven SET-EQUAL to live discovery.
_EXPECTED_OCCURRENCES = frozenset({
    ('_assert_lifecycle_oracle', 0, 'CA', "SELECT COUNT(*) FROM source_index_entities e WHERE e.status='LIVE' AND (SELECT COUNT(*) FROM source_index_locators l WHERE l.source_entity_id=e.source_entity_id AND l.is_current_locator=1) != 1 AND e.source_entity_id = :eid"),
    ('_assert_lifecycle_oracle', 1, 'CA', "SELECT COUNT(*) FROM source_index_entities e WHERE e.status='TOMBSTONED' AND (SELECT COUNT(*) FROM source_index_locators l WHERE l.source_entity_id=e.source_entity_id AND l.is_current_locator=1) != 0 AND e.source_entity_id = :eid"),
    ('_assert_lifecycle_oracle', 2, 'CA', 'SELECT COUNT(*) FROM (SELECT l.source_entity_id FROM source_index_locators l WHERE l.is_current_locator=1 AND l.source_entity_id = :eid GROUP BY l.source_entity_id HAVING COUNT(*) > 1)'),
    ('_assert_lifecycle_oracle', 3, 'CA', 'SELECT COUNT(*) FROM (SELECT l.source_root_key, l.rel_path FROM source_index_locators l WHERE l.is_current_locator=1 AND l.tombstoned_at IS NULL AND l.rel_path IS NOT NULL AND (l.source_root_key, l.rel_path) IN (SELECT source_root_key, rel_path FROM source_index_locators WHERE is_current_locator=1 AND rel_path IS NOT NULL AND source_entity_id = :eid) GROUP BY l.source_root_key, l.rel_path HAVING COUNT(*) > 1)'),
    ('_demote_current_locator', 0, 'CA', 'UPDATE source_index_locators SET is_current_locator=0, tombstoned_at=? WHERE source_entity_id=? AND is_current_locator=1'),
    ('_demote_current_locator', 1, 'CA', 'UPDATE source_index_locators SET is_current_locator=0 WHERE source_entity_id=? AND is_current_locator=1'),
    ('_insert_current_locator', 0, 'CA', 'INSERT INTO source_index_locators (locator_id, source_entity_id, source_id, source_root_key, rel_path, is_current_locator, tombstoned_at, generation_seq) VALUES (?,?,?,?,?,1,NULL,0)'),
    ('_invalidate_content_locked', 0, 'CA', 'SELECT fts_rowid FROM source_intelligence_metadata WHERE source_entity_id=?'),
    ('_invalidate_content_locked', 2, 'CA', 'DELETE FROM source_intelligence_text WHERE source_entity_id=?'),
    ('_invalidate_content_locked', 3, 'CA', 'DELETE FROM source_intelligence_chunks WHERE source_entity_id=?'),
    ('_invalidate_content_locked', 4, 'CA', "UPDATE source_intelligence_metadata SET content_sha256='', fts_rowid=NULL, page_count=NULL, paragraph_count=NULL, sheet_count=NULL, extraction_failure_code=NULL, extraction_disposition=NULL, content_indexed_at=NULL, extraction_status='pending' WHERE source_entity_id=?"),
    ('_locator_for_path', 0, 'CA', 'SELECT s.source_entity_id, l.source_id, l.source_root_key, l.rel_path FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE s.source_kind=? AND l.rel_path=? AND l.source_root_key=?'),
    ('_mark_deleted_by_source_id_locked', 0, 'CA', 'SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_entity_id=?'),
    ('_mark_deleted_by_source_id_locked', 2, 'CA', 'UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_entity_id=?'),
    ('_mark_generated_notes_stale', 0, 'CA', "UPDATE source_intelligence_generated_notes SET generation_status='stale', updated_at=? WHERE source_entity_id=? AND generation_status='generated'"),
    ('_mint_entity', 0, 'CA', "INSERT INTO source_index_entities (source_entity_id, created_at, status) VALUES (?,?,'LIVE')"),
    ('_resolve_dst_ref_entity', 0, 'CA', 'SELECT source_entity_id FROM source_index_entities WHERE source_entity_id=?'),
    ('_resolve_entity_by_source_id', 0, 'CA', 'SELECT DISTINCT source_entity_id FROM source_index_locators WHERE source_id=?'),
    ('_tombstone_entity', 0, 'CA', "UPDATE source_index_entities SET status='TOMBSTONED' WHERE source_entity_id=?"),
    ('_upsert_source_file_locked', 0, 'CA', 'SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_entity_id=?'),
    ('_upsert_source_file_locked', 1, 'OW', 'UPDATE source_index_locators SET last_seen_generation=COALESCE(?, last_seen_generation), last_seen_at=COALESCE(?, last_seen_at), last_indexed_fingerprint=COALESCE(?, last_indexed_fingerprint), policy_validation_state=CASE WHEN ? IS NOT NULL THEN NULL ELSE policy_validation_state END WHERE source_entity_id=? AND is_current_locator=1'),
    ('_upsert_source_file_locked', 2, 'CA', 'INSERT INTO source_intelligence_sources (source_entity_id, source_kind, source_root_key, rel_path, abs_path_hash, project_key, project_number, active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,1,0,?,?) ON CONFLICT(source_entity_id) DO UPDATE SET source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, project_key=excluded.project_key, project_number=excluded.project_number, active=1, deleted=0'),
    ('_upsert_source_file_locked', 3, 'CA', 'INSERT INTO source_intelligence_sources (source_entity_id, source_kind, source_root_key, rel_path, abs_path_hash, project_key, project_number, active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,1,0,?,?) ON CONFLICT(source_entity_id) DO UPDATE SET source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, project_key=excluded.project_key, project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at'),
    ('_upsert_source_file_locked', 4, 'CA', 'SELECT text_excerpt FROM source_intelligence_text WHERE source_entity_id=?'),
    ('_upsert_source_file_locked', 7, 'CA', 'INSERT INTO source_intelligence_metadata (source_entity_id, file_ext, size_bytes, mtime_ns, extraction_status, fts_rowid, indexed_at, extraction_disposition) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(source_entity_id) DO UPDATE SET file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, fts_rowid=excluded.fts_rowid, extraction_disposition=excluded.extraction_disposition, indexed_at=excluded.indexed_at'),
    ('_upsert_source_file_locked', 8, 'CA', "DELETE FROM source_intelligence_relationships WHERE src_source_entity_id=? AND relation='belongs_to_project'"),
    ('_upsert_source_file_locked', 9, 'CA', 'INSERT INTO source_intelligence_relationships (relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET confidence=excluded.confidence, evidence_json=excluded.evidence_json'),
    ('_upsert_source_file_locked', 13, 'CA', 'INSERT INTO source_intelligence_metadata (source_entity_id, file_ext, size_bytes, mtime_ns, content_sha256, page_count, paragraph_count, sheet_count, extraction_status, extraction_failure_code, fts_rowid, indexed_at, extraction_disposition, content_indexed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_entity_id) DO UPDATE SET file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, content_sha256=excluded.content_sha256, page_count=excluded.page_count, paragraph_count=excluded.paragraph_count, sheet_count=excluded.sheet_count, extraction_status=excluded.extraction_status, extraction_failure_code=excluded.extraction_failure_code, fts_rowid=excluded.fts_rowid, indexed_at=excluded.indexed_at, extraction_disposition=excluded.extraction_disposition, content_indexed_at=excluded.content_indexed_at'),
    ('_upsert_source_file_locked', 14, 'CA', 'INSERT INTO source_intelligence_text (source_entity_id, text_excerpt, excerpt_char_count, excerpt_truncated, full_text_sha256, text_vault_ref, raw_body_persisted, redaction_applied, updated_at) VALUES (?,?,?,?,?,?,0,1,?) ON CONFLICT(source_entity_id) DO UPDATE SET text_excerpt=excluded.text_excerpt, excerpt_char_count=excluded.excerpt_char_count, excerpt_truncated=excluded.excerpt_truncated, full_text_sha256=excluded.full_text_sha256, text_vault_ref=excluded.text_vault_ref, updated_at=excluded.updated_at'),
    ('_upsert_source_file_locked', 15, 'CA', 'DELETE FROM source_intelligence_text WHERE source_entity_id=?'),
    ('_upsert_source_file_locked', 16, 'CA', 'DELETE FROM source_intelligence_chunks WHERE source_entity_id=?'),
    ('_upsert_source_file_locked', 17, 'CA', 'INSERT INTO source_intelligence_chunks (chunk_id, source_entity_id, ordinal, chunk_text, char_count, raw_body_persisted, created_at) VALUES (?,?,?,?,?,0,?)'),
    ('_upsert_source_file_locked', 18, 'CA', "DELETE FROM source_intelligence_relationships WHERE src_source_entity_id=? AND relation='belongs_to_project'"),
    ('_upsert_source_file_locked', 19, 'CA', 'INSERT INTO source_intelligence_relationships (relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET confidence=excluded.confidence, evidence_json=excluded.evidence_json'),
    ('active_index_state', 0, 'CA', "SELECT l.rel_path, m.mtime_ns, m.size_bytes FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_kind='external_file' AND l.source_root_key=? AND l.rel_path IS NOT NULL AND s.deleted=0"),
    ('active_rel_paths', 0, 'CA', 'SELECT l.rel_path FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE l.source_root_key=? AND l.rel_path IS NOT NULL AND s.deleted=0'),
    ('content_status_counts', 0, 'CA', "SELECT COALESCE(m.extraction_disposition, CASE m.extraction_status WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' ELSE 'metadata_only' END) AS disp, m.extraction_status AS st, CASE WHEN l.policy_validation_state IS NULL THEN 0 ELSE 1 END AS policy_stale, SUM(CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END) AS searchable, SUM(CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END) AS has_fts, COUNT(*) AS n FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 GROUP BY disp, st, policy_stale"),
    ('count_source_files', 0, 'CA', "SELECT COUNT(*) FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE s.source_kind='external_file' AND s.deleted=0 AND l.source_root_key = ?"),
    ('delete_summary', 0, 'CA', 'DELETE FROM source_intelligence_summaries WHERE source_entity_id=?'),
    ('distinct_indexed_root_keys', 0, 'CA', 'SELECT DISTINCT l.source_root_key FROM source_index_locators l WHERE l.is_current_locator=1 AND l.tombstoned_at IS NULL AND l.source_root_key IS NOT NULL ORDER BY l.source_root_key'),
    ('generated_note_counts', 0, 'non-address', "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='generated'"),
    ('get_source_detail', 0, 'CA', 'SELECT s.source_entity_id, s.source_kind, CASE WHEN s.domain_ref_table IS NOT NULL THEN NULL ELSE l.source_root_key END, CASE WHEN s.domain_ref_table IS NOT NULL THEN NULL ELSE l.rel_path END, s.domain_ref_table, s.domain_ref_id, s.project_key, s.project_number, s.deleted, m.file_ext, m.size_bytes, m.mtime_ns, m.content_sha256, m.page_count, m.paragraph_count, m.sheet_count, m.extraction_status, m.indexed_at, t.text_excerpt, t.excerpt_char_count, t.excerpt_truncated, t.text_vault_ref FROM source_intelligence_sources s LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id WHERE s.source_entity_id = ?'),
    ('get_sources_for_note', 0, 'CA', 'SELECT g.source_entity_id, g.generation_status, g.generated_at, s.source_kind, l.rel_path, l.source_root_key, s.deleted, s.active FROM source_intelligence_generated_notes g JOIN source_intelligence_sources s ON s.source_entity_id = g.source_entity_id LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE g.note_rel_path=? ORDER BY g.updated_at'),
    ('get_summary', 0, 'CA', 'SELECT model_provider, model_name, prompt_version, prompt_sha256, summary_sha256, source_sha256, generated_at FROM source_intelligence_summaries WHERE source_entity_id=?'),
    ('has_generated_note', 0, 'CA', "SELECT 1 FROM source_intelligence_generated_notes WHERE source_entity_id=? AND generation_status IN ('generated','stale') LIMIT 1"),
    ('index_status', 0, 'non-address', 'SELECT source_kind, COUNT(*) FROM source_intelligence_sources WHERE deleted=0 GROUP BY source_kind'),
    ('index_status', 6, 'non-address', 'SELECT MAX(indexed_at) FROM source_intelligence_metadata'),
    ('index_status', 7, 'non-address', "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='stale'"),
    ('index_status', 9, 'non-address', 'SELECT COUNT(*) FROM source_intelligence_summaries'),
    ('index_status', 10, 'CA', 'SELECT COUNT(*) FROM source_intelligence_summaries s JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_sha256 IS NOT m.content_sha256'),
    ('index_status', 11, 'non-address', "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='generated'"),
    ('link_domain_source', 0, 'CA', 'INSERT INTO source_intelligence_sources (source_entity_id, source_kind, domain_ref_table, domain_ref_id, project_key, project_number, active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,1,0,?,?) ON CONFLICT(source_entity_id) DO UPDATE SET project_key=excluded.project_key, project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at'),
    ('list_cards_for_source', 0, 'CA', 'SELECT generated_note_id, note_rel_path, generation_status, generated_at, updated_at FROM source_intelligence_generated_notes WHERE source_entity_id=? ORDER BY updated_at'),
    ('list_generated_notes', 0, 'CA', 'SELECT g.generated_note_id, g.source_entity_id, g.note_rel_path, g.generation_status, l.rel_path, s.source_kind FROM source_intelligence_generated_notes g JOIN source_intelligence_sources s ON s.source_entity_id = g.source_entity_id LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE g.generation_status IN ({}) ORDER BY g.updated_at'),
    ('list_relationships', 0, 'CA', 'SELECT r.dst_kind, r.dst_ref, r.relation, r.confidence, r.evidence_json FROM source_intelligence_relationships r WHERE r.src_source_entity_id=? ORDER BY r.created_at'),
    ('list_relationships', 1, 'CA', 'SELECT rel_path FROM source_index_locators WHERE source_entity_id=? AND is_current_locator=1'),
    ('list_root_file_sources', 0, 'CA', "SELECT s.source_entity_id, l.rel_path, s.project_number FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE s.source_kind='external_file' AND l.source_root_key=? AND l.rel_path IS NOT NULL AND s.deleted=0"),
    ('list_source_files', 0, 'CA', "SELECT l.source_root_key, l.rel_path, s.source_entity_id, m.file_ext, l.policy_validation_state FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_kind='external_file' AND s.deleted=0 AND l.source_root_key = ? AND l.rel_path IS NOT NULL AND l.rel_path LIKE ? ESCAPE '\\' AND (l.rel_path > ? OR (l.rel_path = ? AND s.source_entity_id > ?)) ORDER BY l.rel_path, s.source_entity_id LIMIT ?"),
    ('list_stale_generated_notes', 0, 'CA', "SELECT source_entity_id, note_rel_path FROM source_intelligence_generated_notes WHERE generation_status='stale' ORDER BY updated_at LIMIT ?"),
    ('load_metadata_state_batch', 0, 'CA', "SELECT l.rel_path, m.mtime_ns, m.size_bytes, CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END AS has_fts, COALESCE(m.extraction_disposition, CASE m.extraction_status WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' ELSE 'metadata_only' END) AS disp, s.project_key AS project_key, s.project_number AS project_number, l.last_indexed_fingerprint AS fingerprint, COALESCE((SELECT CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 'plain' WHEN t.text_vault_ref IS NOT NULL AND LENGTH(t.text_vault_ref) > 0 THEN 'vault' ELSE 'none' END FROM source_intelligence_text t WHERE t.source_entity_id = s.source_entity_id), 'none') AS content_mode FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 AND l.rel_path IN ({})"),
    ('lookup_by_path', 0, 'CA', 'SELECT s.source_entity_id, m.content_sha256, m.mtime_ns, m.fts_rowid, s.deleted, m.size_bytes FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_kind=? AND l.rel_path=? AND l.source_root_key=?'),
    ('mark_deleted', 0, 'CA', 'SELECT s.source_entity_id, m.fts_rowid FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id=s.source_entity_id AND l.is_current_locator=1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id=s.source_entity_id WHERE s.source_kind=? AND l.rel_path=? AND l.source_root_key=?'),
    ('mark_deleted', 2, 'CA', 'UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_entity_id=?'),
    ('mark_deleted_batch', 0, 'CA', 'SELECT s.source_entity_id, m.fts_rowid FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id=s.source_entity_id AND l.is_current_locator=1 LEFT JOIN source_intelligence_metadata m ON m.source_entity_id=s.source_entity_id WHERE s.source_kind=? AND l.rel_path=? AND l.source_root_key=?'),
    ('mark_deleted_batch', 2, 'CA', 'UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_entity_id=?'),
    ('record_generated_note', 0, 'CA', 'INSERT INTO source_intelligence_generated_notes (generated_note_id, source_entity_id, note_rel_path, generation_status, generated_at, updated_at) VALUES (?,?,?,?,?,?) ON CONFLICT(source_entity_id, note_rel_path) DO UPDATE SET generation_status=excluded.generation_status, generated_at=excluded.generated_at, updated_at=excluded.updated_at'),
    ('record_relationships', 0, 'CA', 'INSERT INTO source_intelligence_relationships (relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET confidence=excluded.confidence, evidence_json=excluded.evidence_json'),
    ('register_source_roots', 1, 'CA', 'SELECT DISTINCT l.source_root_key FROM source_index_locators l WHERE l.is_current_locator=1 AND l.source_root_key IS NOT NULL'),
    ('register_source_roots', 2, 'CA', 'SELECT s.source_entity_id FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE l.source_root_key=? AND s.deleted=0'),
    ('register_source_roots', 3, 'CA', 'UPDATE source_intelligence_sources SET active=0, updated_at=? WHERE source_entity_id=?'),
    ('resolve_entity', 0, 'CA', 'SELECT source_entity_id FROM source_index_entities WHERE source_entity_id=?'),
    ('search_notes', 0, 'CA', "SELECT n.rel_path, n.aux, bm25(obsidian_note_fts) AS rank, snippet(obsidian_note_fts, 0, '[', ']', '…', 12) AS snip, s.source_entity_id FROM obsidian_note_fts n JOIN source_intelligence_metadata m ON m.fts_rowid = n.rowid JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id AND s.source_kind='obsidian_note' JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 AND l.policy_validation_state IS NULL WHERE obsidian_note_fts MATCH ? AND s.deleted=0 AND n.rel_path LIKE ? ORDER BY rank LIMIT ?"),
    ('search_source_files', 0, 'CA', "SELECT src_root, rel, sid, ext, rank, snip_text, snip_path, snip_aux, est, disp, has_text FROM ( SELECT COALESCE(l.source_root_key,'') AS src_root, COALESCE(l.rel_path,'') AS rel, s.source_entity_id AS sid, m.file_ext AS ext, bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, m.extraction_status AS est, m.extraction_disposition AS disp, CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text FROM source_intelligence_fts f JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 AND l.policy_validation_state IS NULL LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' AND l.source_root_key = ? AND m.file_ext = ? ) WHERE rank > ? OR (rank = ? AND src_root > ?) OR (rank = ? AND src_root = ? AND rel > ?) OR (rank = ? AND src_root = ? AND rel = ? AND sid > ?) ORDER BY rank, src_root, rel, sid LIMIT ?"),
    ('search_sources', 0, 'CA', "SELECT l.rel_path, f.aux, bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, s.source_entity_id, m.extraction_status, m.extraction_disposition, CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text FROM source_intelligence_fts f JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 AND l.policy_validation_state IS NULL LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' AND f.aux = ? ORDER BY rank LIMIT ?"),
    ('set_generated_note_status', 0, 'non-address', 'UPDATE source_intelligence_generated_notes SET generation_status=?, updated_at=? WHERE generated_note_id=?'),
    ('stale_candidates_batch', 0, 'CA', "SELECT s.source_entity_id, l.rel_path FROM source_intelligence_sources s JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id AND l.is_current_locator = 1 WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 AND (l.last_seen_generation IS NULL OR l.last_seen_generation != ?) AND julianday(s.updated_at) <= julianday(?) AND s.source_entity_id > ? ORDER BY s.source_entity_id LIMIT ?"),
    ('stamp_last_seen', 0, 'OW', "UPDATE source_index_locators SET last_seen_generation=?, last_seen_at=? WHERE is_current_locator=1 AND source_root_key=? AND rel_path IN ({}) AND source_entity_id IN (SELECT source_entity_id FROM source_intelligence_sources WHERE source_kind='external_file' AND deleted=0)"),
    ('stamp_last_seen', 1, 'OW', "UPDATE source_index_locators SET last_seen_generation=?, last_seen_at=? WHERE is_current_locator=1 AND source_root_key=? AND rel_path IN ({}) AND source_entity_id IN (SELECT source_entity_id FROM source_intelligence_sources WHERE source_kind='external_file' AND deleted=0)"),
    ('summary_counts', 0, 'non-address', 'SELECT COUNT(*) FROM source_intelligence_summaries'),
    ('summary_counts', 1, 'CA', 'SELECT COUNT(*) FROM source_intelligence_summaries s JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id WHERE s.source_sha256 IS NOT m.content_sha256'),
    ('upsert_summary', 0, 'CA', 'INSERT INTO source_intelligence_summaries (source_entity_id, model_provider, model_name, prompt_version, prompt_sha256, summary_sha256, source_sha256, advisory, generated_at) VALUES (?,?,?,?,?,?,?,1,?) ON CONFLICT(source_entity_id) DO UPDATE SET model_provider=excluded.model_provider, model_name=excluded.model_name, prompt_version=excluded.prompt_version, prompt_sha256=excluded.prompt_sha256, summary_sha256=excluded.summary_sha256, source_sha256=excluded.source_sha256, generated_at=excluded.generated_at'),
})


def test_f001_occurrence_registry_set_equal_and_fail_closed() -> None:
    """Live AST discovery over source_index_repository.py is SET-EQUAL to the frozen registry: any
    added / removed / renamed / changed re-keyed-table statement fails closed. Also proves discovery is
    complete over all 9 registered tables and every statement was reconstructed (no silent skip)."""
    discovered = frozenset(_verify_dual_authority(inspect.getsource(repo_mod)))
    added = discovered - _EXPECTED_OCCURRENCES
    removed = _EXPECTED_OCCURRENCES - discovered
    assert not added, f"unregistered occurrence(s) — fail closed: {sorted(added)}"
    assert not removed, f"missing registered occurrence(s) — fail closed: {sorted(removed)}"
    assert discovered == _EXPECTED_OCCURRENCES


def test_f001_class_totals_and_lka_zero() -> None:
    """Authority-class totals are a stated contract; LKA is zero in this runtime surface (§5.3)."""
    from collections import Counter
    totals = Counter(cls for _s, _o, cls, _sql in _EXPECTED_OCCURRENCES)
    assert totals["CA"] == 70 and totals["OW"] == 3 and totals["non-address"] == 8
    assert totals["LKA"] == 0 and totals["MOVE_TRANSITION"] == 0
    assert sum(totals.values()) == 81


def test_f001_mint_entity_and_insert_locator_are_sole_authorities() -> None:
    occ = _verify_dual_authority(inspect.getsource(repo_mod))
    entity_ins = [(s, o) for s, o, _c, sql in occ if "INSERT INTO source_index_entities" in sql]
    assert entity_ins and all(s == "_mint_entity" for s, _o in entity_ins)
    loc_ins = [(s, o) for s, o, _c, sql in occ if "INSERT INTO source_index_locators" in sql]
    assert loc_ins and all(s == "_insert_current_locator" for s, _o in loc_ins)
    # current/tombstone flags are written only by _demote_current_locator (no raw parent-address write)
    flag_writes = [
        s for s, _o, _c, sql in occ
        if sql.startswith("UPDATE source_index_locators SET")
        and ({"is_current_locator", "tombstoned_at"}
             & set(re.findall(r"([a-z_]+)\s*=",
                              sql[len('UPDATE source_index_locators SET'):].split(' WHERE ')[0])))
    ]
    assert flag_writes and all(s == "_demote_current_locator" for s in flag_writes)


# ---- F-001 negative fixtures: each makes the guard REJECT (DualAuthorityGuardError) ----

_REPO_SRC = inspect.getsource(repo_mod)


def test_f001_negative_second_entity_insert_outside_mint() -> None:
    evil = _REPO_SRC + (
        "\n\ndef _injected_second_entity_insert(c, eid):\n"
        "    c.execute(\"INSERT INTO source_index_entities (source_entity_id, created_at, status) \"\n"
        "              \"VALUES (?,?,'LIVE')\", (eid, 'now'))\n"
    )
    with pytest.raises(DualAuthorityGuardError):
        _verify_dual_authority(evil)


def test_f001_negative_variable_built_forbidden_sql() -> None:
    # A forbidden content-table source_id write ASSEMBLED by intra-function concatenation: the analyzer
    # RESOLVES the variable (does not skip it) and rejects the raw parent-address write.
    evil = _REPO_SRC + (
        "\n\ndef _injected_variable_forbidden(c, x):\n"
        "    sql = \"UPDATE source_intelligence_metadata SET \"\n"
        "    sql += \"source_id=? WHERE source_entity_id=?\"\n"
        "    c.execute(sql, (x, x))\n"
    )
    with pytest.raises(DualAuthorityGuardError):
        _verify_dual_authority(evil)


def test_f001_negative_raw_parent_address_write() -> None:
    evil = _REPO_SRC + (
        "\n\ndef _injected_raw_current_locator(c, eid):\n"
        "    c.execute(\"UPDATE source_index_locators SET is_current_locator=1 \"\n"
        "              \"WHERE source_entity_id=?\", (eid,))\n"
    )
    with pytest.raises(DualAuthorityGuardError):
        _verify_dual_authority(evil)


def test_f001_negative_unreconstructable_sql() -> None:
    # An execute() whose SQL cannot be reconstructed to a string must FAIL CLOSED (never a silent skip).
    evil = _REPO_SRC + (
        "\n\ndef _injected_dynamic_sql(c, make_sql):\n"
        "    c.execute(make_sql())\n"
    )
    with pytest.raises(DualAuthorityGuardError):
        _verify_dual_authority(evil)


# ============================================================================================
# F-001 R3B — analyzer helpers + control-flow / alias / append / bound fixtures
# (each negative asserts its SPECIFIC category; positives are DISCOVERED unchanged)
# ============================================================================================

def _analyze_call(src: str, func_name: str) -> "_Recon":
    """Reconstruct the FIRST execute call in ``func_name`` → its _Recon (rep + candidate set + cond
    sites). Used by the F-022 fixtures to assert the EXACT reconstructed candidates + representative."""
    tree = ast.parse(src)
    func = next(
        f for f in ast.walk(tree)
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == func_name
    )
    parents, field_of = _scope_parents(func)
    assignmap = _name_assignments(func)
    calls = sorted(
        (n for n in _own_scope_nodes(func)
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
         and n.func.attr in ("execute", "executemany")),
        key=lambda n: (n.lineno, n.col_offset),
    )
    n = calls[0]
    ctx = {"call": n, "parents": parents, "field_of": field_of, "assignmap": assignmap}
    return _reconstruct_expr(n.args[0], ctx, frozenset())


def _reject_cat(src: str, category: str) -> None:
    """The analyzer REJECTS ``src`` with EXACTLY ``category`` (not merely some exception)."""
    with pytest.raises(DualAuthorityGuardError) as ei:
        _verify_dual_authority(src)
    assert getattr(ei.value, "category", None) == category, (category, str(ei.value))


# ---- (i)-(v) reaching-def KILL rejections ----

def test_f001_neg_i_post_call_reassignment_forbidden() -> None:
    # The forbidden pre-call INSERT is NOT hidden by a post-call reassignment (excluded) → forbidden.
    _reject_cat(
        "def _e(c):\n"
        "    sql = \"INSERT INTO source_index_entities (source_entity_id) VALUES (?)\"\n"
        "    c.execute(sql, ('x',))\n"
        "    sql = \"SELECT 1\"\n",
        _CAT_FORBIDDEN,
    )


def test_f001_neg_ii_forbidden_then_conditional_safe_kill() -> None:
    _reject_cat(
        "def _e(c, cond):\n"
        "    sql = \"INSERT INTO source_index_entities (source_entity_id) VALUES (?)\"\n"
        "    if cond:\n"
        "        sql = \"SELECT 1\"\n"
        "    c.execute(sql, ('x',))\n",
        _CAT_AMBIGUOUS,
    )


def test_f001_neg_iii_safe_then_conditional_forbidden_kill() -> None:
    _reject_cat(
        "def _e(c, cond):\n"
        "    sql = \"SELECT 1\"\n"
        "    if cond:\n"
        "        sql = \"INSERT INTO source_index_entities (source_entity_id) VALUES (?)\"\n"
        "    c.execute(sql, ('x',))\n",
        _CAT_AMBIGUOUS,
    )


def test_f001_neg_iv_branch_specific_kill() -> None:
    _reject_cat(
        "def _e(c, cond):\n"
        "    if cond:\n"
        "        sql = \"INSERT INTO source_index_entities (source_entity_id) VALUES (?)\"\n"
        "    else:\n"
        "        sql = \"SELECT 1\"\n"
        "    c.execute(sql, ('x',))\n",
        _CAT_AMBIGUOUS,
    )


def test_f001_neg_v_loop_kill_feeding_post_loop_call() -> None:
    _reject_cat(
        "def _e(c, items):\n"
        "    for item in items:\n"
        "        sql = \"INSERT INTO source_index_entities (source_entity_id) VALUES (?)\"\n"
        "    c.execute(sql, ('x',))\n",
        _CAT_AMBIGUOUS,
    )


# ---- (xii)-(xiii) append building a forbidden reference ----

def test_f001_neg_xii_cumulative_straightline_forbidden() -> None:
    _reject_cat(
        "def _e(c, x):\n"
        "    sql = \"UPDATE source_intelligence_metadata SET \"\n"
        "    sql += \"source_id=? \"\n"
        "    sql += \"WHERE source_entity_id=?\"\n"
        "    c.execute(sql, (x, x))\n",
        _CAT_FORBIDDEN,
    )


def test_f001_neg_xiii_conditional_append_forbidden_ref() -> None:
    # A one-shot conditional += whose folded base+suffix contains a forbidden content-table source_id
    # write → forbidden_dual_authority_occurrence (NOT ambiguous_control_flow).
    _reject_cat(
        "def _e(c, cond):\n"
        "    sql = \"SELECT 1\"\n"
        "    if cond:\n"
        "        sql += \" ; UPDATE source_intelligence_metadata SET source_id=? WHERE source_entity_id=?\"\n"
        "    c.execute(sql, ())\n",
        _CAT_FORBIDDEN,
    )


# ---- (vi)-(xi),(xiv) alias / dynamic getattr rejections ----

def test_f001_neg_vi_ordinary_execute_alias() -> None:
    _reject_cat("def _e(c):\n    run = c.execute\n    run(\"SELECT 1\")\n", _CAT_ALIAS)


def test_f001_neg_vii_annotated_execute_alias() -> None:
    _reject_cat("def _e(c):\n    run: object = c.execute\n", _CAT_ALIAS)


def test_f001_neg_viii_destructuring_execute_alias() -> None:
    _reject_cat("def _e(c):\n    (run,) = (c.execute,)\n", _CAT_ALIAS)


def test_f001_neg_ix_constant_getattr_execute_alias() -> None:
    _reject_cat("def _e(c):\n    run = getattr(c, \"execute\")\n    run(\"SELECT 1\")\n", _CAT_ALIAS)


def test_f001_neg_x_walrus_execute_alias() -> None:
    _reject_cat("def _e(c):\n    if (run := c.execute):\n        run(\"SELECT 1\")\n", _CAT_ALIAS)


def test_f001_neg_xi_nonliteral_getattr() -> None:
    _reject_cat(
        "def _e(c):\n    name = \"execute\"\n    run = getattr(c, name)\n    run(\"SELECT 1\")\n",
        _CAT_GETATTR,
    )


def test_f001_neg_xi_nonliteral_getattr_passed_as_argument() -> None:
    # Not gated on a direct .execute: a non-literal getattr passed straight to a helper still rejects.
    _reject_cat(
        "def _e(c, helper):\n    method = \"execute\"\n    helper(getattr(c, method))\n",
        _CAT_GETATTR,
    )


def test_f001_neg_xiv_only_execution_is_variable_getattr() -> None:
    # F-019: a function whose ONLY execution path is a variable-derived getattr (no direct .execute).
    _reject_cat(
        "def _e(c, sql):\n    m = \"execute\"\n    fn = getattr(c, m)\n    return fn(sql)\n",
        _CAT_GETATTR,
    )


# ---- (xv) executescript unsupported execution form ----

def test_f001_neg_xv_executescript_direct() -> None:
    _reject_cat("def _e(c):\n    c.executescript(\"SELECT 1; SELECT 2\")\n", _CAT_SCRIPT)


def test_f001_neg_xv_executescript_alias() -> None:
    _reject_cat("def _e(c):\n    run = c.executescript\n    run(\"SELECT 1\")\n", _CAT_SCRIPT)


def test_f001_neg_xv_executescript_getattr() -> None:
    _reject_cat("def _e(c):\n    run = getattr(c, \"executescript\")\n", _CAT_SCRIPT)


# ---- (xvi) node-type KILL rejection despite append-like RHS ----

def test_f001_neg_xvi_conditional_kill_with_append_like_rhs() -> None:
    # A conditional `=` whose RHS is base+suffix is STILL an ambiguous KILL (decided by node type,
    # never by the append-like appearance of the RHS).
    _reject_cat(
        "def _e(c, cond):\n"
        "    base = \"SELECT source_entity_id FROM source_intelligence_sources WHERE x=?\"\n"
        "    sql = base\n"
        "    if cond:\n"
        "        sql = base + \" AND y=?\"\n"
        "    c.execute(sql, ())\n",
        _CAT_AMBIGUOUS,
    )


# ---- (xvii)-(xix) unsupported append multiplicity ----

def test_f001_neg_xvii_loop_append_post_loop_call() -> None:
    _reject_cat(
        "def _e(c, items):\n"
        "    sql = \"SELECT source_entity_id FROM source_intelligence_sources\"\n"
        "    for item in items:\n"
        "        sql += \" x\"\n"
        "    c.execute(sql, ())\n",
        _CAT_APPEND,
    )


def test_f001_neg_xviii_if_else_append_pair() -> None:
    _reject_cat(
        "def _e(c, cond):\n"
        "    sql = \"SELECT source_entity_id FROM source_intelligence_sources\"\n"
        "    if cond:\n"
        "        sql += \" a\"\n"
        "    else:\n"
        "        sql += \" b\"\n"
        "    c.execute(sql, ())\n",
        _CAT_APPEND,
    )


def test_f001_neg_xix_try_except_append() -> None:
    _reject_cat(
        "def _e(c):\n"
        "    sql = \"SELECT source_entity_id FROM source_intelligence_sources\"\n"
        "    try:\n"
        "        sql += \" a\"\n"
        "    except Exception:\n"
        "        pass\n"
        "    c.execute(sql, ())\n",
        _CAT_APPEND,
    )


# ---- (xx) N+1 admissible append sites → candidate_expansion_limit ----

_N_PLUS_ONE_SRC = (
    "def _e(c, a, b, d, e, f, g):\n"
    "    sql = \"SELECT source_entity_id FROM source_intelligence_sources WHERE 1=1\"\n"
    "    if a:\n        sql += \" AND c1=?\"\n"
    "    if b:\n        sql += \" AND c2=?\"\n"
    "    if d:\n        sql += \" AND c3=?\"\n"
    "    if e:\n        sql += \" AND c4=?\"\n"
    "    if f:\n        sql += \" AND c5=?\"\n"
    "    if g:\n        sql += \" AND c6=?\"\n"
    "    c.execute(sql, ())\n"
)


def test_f001_neg_xx_n_plus_one_expansion_limit() -> None:
    _reject_cat(_N_PLUS_ONE_SRC, _CAT_LIMIT)


# ---- Positives (DISCOVERED, no raise) ----

_P0_SRC = (
    "def _p0(c, a, b, d, e, f):\n"
    "    sql = \"SELECT source_entity_id FROM source_intelligence_sources WHERE 1=1\"\n"
    "    if a:\n        sql += \" AND c1=?\"\n"
    "    if b:\n        sql += \" AND c2=?\"\n"
    "    if d:\n        sql += \" AND c3=?\"\n"
    "    if e:\n        sql += \" AND c4=?\"\n"
    "    if f:\n        sql += \" AND c5=?\"\n"
    "    c.execute(sql, ())\n"
)
_P1_SRC = (
    "def _p1(c, flag):\n"
    "    sql = \"SELECT source_entity_id FROM source_intelligence_sources\"\n"
    "    if flag:\n        sql += \" WHERE aux=?\"\n"
    "    c.execute(sql, ())\n"
)
_P2_SRC = (
    "def _p2(c, items):\n"
    "    base_sql = \"SELECT source_entity_id FROM source_intelligence_sources WHERE k=?\"\n"
    "    for item in items:\n"
    "        sql = base_sql\n"
    "        c.execute(sql, (item,))\n"
)


def test_f001_pos_p0_n5_boundary_all_candidates_enumerated() -> None:
    recon = _analyze_call(_P0_SRC, "_p0")
    assert recon.cond == 5
    assert len(recon.candidates) == 32  # 2**5, at the bound (not exceeding)
    rep = _norm_sql(recon.rep)
    assert rep == ("SELECT source_entity_id FROM source_intelligence_sources WHERE 1=1 "
                   "AND c1=? AND c2=? AND c3=? AND c4=? AND c5=?")
    occ = _discover_occurrences(_P0_SRC)  # DISCOVERED (no raise), exactly one occurrence
    assert occ == [("_p0", 0, "CA", rep)]


def test_f001_pos_p1_benign_conditional_append_discovered() -> None:
    recon = _analyze_call(_P1_SRC, "_p1")
    assert recon.candidates == frozenset({
        "SELECT source_entity_id FROM source_intelligence_sources",
        "SELECT source_entity_id FROM source_intelligence_sources WHERE aux=?",
    })
    occ = _discover_occurrences(_P1_SRC)
    assert occ == [
        ("_p1", 0, "CA", "SELECT source_entity_id FROM source_intelligence_sources WHERE aux=?")
    ]


def test_f001_pos_p2_same_block_nested_assignment_discovered() -> None:
    occ = _discover_occurrences(_P2_SRC)
    assert occ == [
        ("_p2", 0, "CA", "SELECT source_entity_id FROM source_intelligence_sources WHERE k=?")
    ]


# ---- F-022 source-order interleaved fixtures (exact candidates + representative) ----

def test_f022_conditional_then_unconditional() -> None:
    src = (
        "def _e(c, cond):\n"
        "    sql = \"A\"\n"
        "    if cond:\n        sql += \"B\"\n"
        "    sql += \"C\"\n"
        "    c.execute(sql, ())\n"
    )
    recon = _analyze_call(src, "_e")
    assert recon.candidates == frozenset({"AC", "ABC"}) and recon.rep == "ABC"


def test_f022_unconditional_then_conditional() -> None:
    src = (
        "def _e(c, cond):\n"
        "    sql = \"A\"\n"
        "    sql += \"B\"\n"
        "    if cond:\n        sql += \"C\"\n"
        "    c.execute(sql, ())\n"
    )
    recon = _analyze_call(src, "_e")
    assert recon.candidates == frozenset({"AB", "ABC"}) and recon.rep == "ABC"


def test_f022_two_conditionals_split_by_unconditional() -> None:
    # The search_source_files shape: unconditional appends are NEVER pre-folded across conditional sites.
    src = (
        "def _e(c, c1, c2):\n"
        "    sql = \"A\"\n"
        "    if c1:\n        sql += \"B\"\n"
        "    sql += \"C\"\n"
        "    if c2:\n        sql += \"D\"\n"
        "    c.execute(sql, ())\n"
    )
    recon = _analyze_call(src, "_e")
    assert recon.candidates == frozenset({"AC", "ABC", "ACD", "ABCD"})
    assert recon.rep == "ABCD" and recon.cond == 2


def test_f022_boundary_forming_identifier_across_fragments() -> None:
    # Two fragments jointly form a registered-table identifier neither contains alone — the analyzer
    # reconstructs the FULL joined candidate (so token-at-boundary detection is possible).
    src = (
        "def _e(c, cond):\n"
        "    sql = \"SELECT 1 FROM source_intelligence_\"\n"
        "    if cond:\n        sql += \"sources WHERE aux=?\"\n"
        "    c.execute(sql, ())\n"
    )
    recon = _analyze_call(src, "_e")
    assert recon.candidates == frozenset({
        "SELECT 1 FROM source_intelligence_",
        "SELECT 1 FROM source_intelligence_sources WHERE aux=?",
    })
    assert recon.rep == "SELECT 1 FROM source_intelligence_sources WHERE aux=?"


# ============================================================================================
# F-002 R3B — tri-state collision-aware dst_ref READ resolution (7 bare rows + prefixed + F-023)
# ============================================================================================

def _resolve_dst(repo: SourceIndexRepository, ref: str) -> str | None:
    with sqlite3.connect(repo.db_path) as c:
        return repo._resolve_dst_ref_entity(c, ref)


def _add_locator(repo: SourceIndexRepository, *, source_id: str, entity_id: str, rel: str) -> None:
    """Inject a NON-current (demoted) locator carrying ``source_id`` for ``entity_id`` — used to
    construct legacy NO_MATCH / UNIQUE / AMBIGUOUS states over the DISTINCT resolver."""
    with sqlite3.connect(repo.db_path) as c:
        c.execute(
            "INSERT INTO source_index_locators(locator_id, source_entity_id, source_id, "
            "source_root_key, rel_path, is_current_locator, tombstoned_at, generation_seq) "
            "VALUES (?,?,?,?,?,0,?,?)",
            (uuid.uuid4().hex, entity_id, source_id, "proj", rel,
             "2000-01-01T00:00:00+00:00", 900),
        )
        c.commit()


def _v1_ref(source_id: str) -> str:
    from hb_assistant.obsidian_mcp.source_connector_models import (
        _SOURCE_REF_PREFIX,
        _b64u_encode,
        _source_id_checksum,
    )
    return _SOURCE_REF_PREFIX + _b64u_encode(
        f"{source_id}{_source_id_checksum(source_id)}".encode("ascii")
    )


def _entity_count(repo: SourceIndexRepository) -> int:
    with sqlite3.connect(repo.db_path) as c:
        return c.execute("SELECT COUNT(*) FROM source_index_entities").fetchone()[0]


# ---- the seven bare-value tri-state rows (PLAN-R3B-F-020) ----

def test_f002_bare_row1_entity_nomatch_legacy_ambiguous(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    e2 = repo.upsert_source_file(_file("b.md", sha="s2", mtime=2, excerpt="y"))
    v = "a" * 32  # canonical bare, NOT an entity id
    _add_locator(repo, source_id=v, entity_id=e1, rel="p1")
    _add_locator(repo, source_id=v, entity_id=e2, rel="p2")
    before = _entity_count(repo)
    assert _resolve_dst(repo, v) is None       # legacy AMBIGUOUS + entity none → None
    assert _entity_count(repo) == before       # no entity created/rebound


def test_f002_bare_row2_entity_match_legacy_ambiguous(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    e2 = repo.upsert_source_file(_file("b.md", sha="s2", mtime=2, excerpt="y"))
    _add_locator(repo, source_id=e1, entity_id=e1, rel="p1")
    _add_locator(repo, source_id=e1, entity_id=e2, rel="p2")  # source_id=e1 → {e1,e2} AMBIGUOUS
    assert _resolve_dst(repo, e1) is None       # ambiguous legacy OVERRIDES the entity hit


def test_f002_bare_row3_entity_match_legacy_nomatch(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    assert _resolve_dst(repo, e1) == e1         # write-path compatibility case


def test_f002_bare_row4_entity_nomatch_legacy_unique(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    legacy = _legacy_source_id(repo, e1)        # a hash source_id, not an entity id
    assert _resolve_dst(repo, legacy) == e1     # legacy UNIQUE, entity none → legacy entity


def test_f002_bare_row5_both_unique_same(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    _add_locator(repo, source_id=e1, entity_id=e1, rel="p1")  # source_id=e1 UNIQUE → e1
    assert _resolve_dst(repo, e1) == e1         # both domains agree → entity


def test_f002_bare_row6_both_unique_different_collision(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    e2 = repo.upsert_source_file(_file("b.md", sha="s2", mtime=2, excerpt="y"))
    _add_locator(repo, source_id=e1, entity_id=e2, rel="p1")  # entity(e1)=e1 but legacy UNIQUE→e2
    assert _resolve_dst(repo, e1) is None       # cross-domain collision → None


def test_f002_bare_row7_neither_domain(repo: SourceIndexRepository) -> None:
    assert _resolve_dst(repo, "b" * 32) is None


# ---- prefixed hbsrc1_ / hbsrc2_ ----

def test_f002_prefixed_hbsrc1_decodes_and_resolves(repo: SourceIndexRepository) -> None:
    # THE R2-F-002 bug: a canonical hbsrc1_ legacy ref must decode to its handle and resolve DISTINCT.
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    legacy = _legacy_source_id(repo, e1)
    assert _resolve_dst(repo, _v1_ref(legacy)) == e1


def test_f002_prefixed_hbsrc1_no_match(repo: SourceIndexRepository) -> None:
    assert _resolve_dst(repo, _v1_ref("c" * 32)) is None


def test_f002_prefixed_hbsrc1_ambiguous(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    e2 = repo.upsert_source_file(_file("b.md", sha="s2", mtime=2, excerpt="y"))
    v = "d" * 32
    _add_locator(repo, source_id=v, entity_id=e1, rel="p1")
    _add_locator(repo, source_id=v, entity_id=e2, rel="p2")
    assert _resolve_dst(repo, _v1_ref(v)) is None      # prefixed AMBIGUOUS legacy → None


def test_f002_prefixed_hbsrc2_entity(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    assert _resolve_dst(repo, encode_source_ref(e1)) == e1


def test_f002_prefixed_hbsrc2_nonexistent(repo: SourceIndexRepository) -> None:
    assert _resolve_dst(repo, encode_source_ref(uuid.uuid4().hex)) is None


def test_f002_prefixed_hbsrc2_tampered(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    ref = encode_source_ref(e1)
    i = len("hbsrc2_") + 4
    tampered = ref[:i] + ("A" if ref[i] != "A" else "B") + ref[i + 1:]
    assert _resolve_dst(repo, tampered) is None


# ---- F-023 canonical bare validation (malformed / unknown prefix → None BEFORE any lookup) ----

def test_f002_f023_malformed_bare_none_before_lookup(repo: SourceIndexRepository) -> None:
    # Deliberately insert a locator whose source_id IS the malformed value; it must STILL not resolve
    # (canonical validation rejects the input before any domain lookup).
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    bad = "not-canonical-hex-value"
    _add_locator(repo, source_id=bad, entity_id=e1, rel="p1")
    assert _resolve_dst(repo, bad) is None


def test_f002_f023_unsupported_hbsrc3_prefix_none(repo: SourceIndexRepository) -> None:
    e1 = repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    bad = "hbsrc3_" + ("a" * 32)
    _add_locator(repo, source_id=bad, entity_id=e1, rel="p1")  # even with matching data present
    assert _resolve_dst(repo, bad) is None


def test_f002_resolver_creates_no_entity(repo: SourceIndexRepository) -> None:
    repo.upsert_source_file(_file("a.md", sha="s1", mtime=1, excerpt="x"))
    before = _entity_count(repo)
    for ref in ("b" * 32, _v1_ref("c" * 32), "hbsrc3_" + "a" * 32, "bad"):
        _resolve_dst(repo, ref)
    assert _entity_count(repo) == before
