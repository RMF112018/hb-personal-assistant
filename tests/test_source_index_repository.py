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
# GUARD 1 (§3.1) — the 22-method current-address register: set-equality + locator binding
# ============================================================================================

_CURRENT_ADDRESS_METHODS = {
    # §5.2 reads (6)
    "list_relationships", "content_status_counts", "distinct_indexed_root_keys",
    "count_source_files", "list_generated_notes", "get_sources_for_note",
    # §5.2 write/delete/deactivate (4)
    "register_source_roots", "mark_deleted", "mark_deleted_batch", "mark_deleted_by_source_id",
    # §2.8.2 current-locator-bound reads (12)
    "lookup_by_path", "active_rel_paths", "active_index_state", "list_root_file_sources",
    "load_metadata_state_batch", "stale_candidates_batch", "find_successor_source_id",
    "get_source_detail", "search_sources", "search_notes", "search_source_files",
    "list_source_files",
}
# Symbols whose presence proves an occurrence resolves the address through the current locator
# (either an explicit join or a lifecycle primitive that binds/tombstones it).
_LOCATOR_BINDING_TOKENS = (
    "is_current_locator", "_locator_for_path", "_mark_deleted_by_source_id_locked",
    "_tombstone_entity", "_resolve_dst_ref_entity",
)


def test_guard1_current_address_register_binds_locator() -> None:
    assert len(_CURRENT_ADDRESS_METHODS) == 22
    for name in _CURRENT_ADDRESS_METHODS:
        assert hasattr(SourceIndexRepository, name), f"missing current-address method {name}"
    for name in _CURRENT_ADDRESS_METHODS:
        body = inspect.getsource(getattr(SourceIndexRepository, name))
        if name == "find_successor_source_id":
            # R11-D1: this registered method is resolved to `return None` (no locator bind, no lineage).
            assert "return None" in body and "renamed_from_source_id" not in body.split('"""')[-1]
            continue
        assert any(tok in body for tok in _LOCATOR_BINDING_TOKENS), (
            f"current-address method {name} does not bind the current locator"
        )


# ============================================================================================
# GUARD 2 (§3.1b) — physical re-key occurrence discovery (semantic/AST, fail-closed)
# ============================================================================================

_REKEYED_TABLES = (
    "source_intelligence_sources", "source_intelligence_metadata", "source_intelligence_text",
    "source_intelligence_summaries", "source_intelligence_chunks",
    "source_intelligence_generated_notes", "source_intelligence_relationships",
)


def _sql_text_from_execute_arg(node: ast.expr) -> str | None:
    """Reconstruct the (possibly f-string / implicitly-concatenated) SQL literal of an execute() arg.
    Adjacent string literals are already merged by the parser into one Constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f-string: keep only literal segments (table/col names)
        parts = [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        return " ".join(parts) if parts else None
    return None


def _discover_execute_sql() -> list[tuple[int, str]]:
    """AST-discover every ``*.execute(<sql literal>, ...)`` in the repository module; return
    ``(lineno, sql_text)`` for those touching a re-keyed table."""
    src = inspect.getsource(repo_mod)
    tree = ast.parse(src)
    found: list[tuple[int, str]] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execute" and n.args):
            continue
        sql = _sql_text_from_execute_arg(n.args[0])
        if sql is None:
            continue
        if any(t in sql for t in _REKEYED_TABLES):
            found.append((n.lineno, " ".join(sql.split())))
    return found


def test_guard2_physical_rekey_complete_and_fail_closed() -> None:
    """Fail-closed AST discovery: EVERY execute() statement touching one of the 7 V128-re-keyed tables
    must be entity-keyed and must NOT carry a dropped/forbidden legacy address column. This proves the
    physical re-key is complete and no legacy current-address authority (renamed_from_source_id, the old
    src_source_id / <alias>.source_id columns on the 7 tables) survives."""
    occurrences = _discover_execute_sql()
    assert occurrences, "discovery found no re-keyed-table SQL (scan is broken)"

    # (a) R11 P-C: the renamed_from lineage authority is never used at runtime.
    bad_lineage = [(ln, s) for ln, s in occurrences if "renamed_from_source_id" in s]
    assert not bad_lineage, f"forbidden renamed_from_source_id usage: {bad_lineage}"

    # (b) relationships re-keyed: no bare src_source_id column survives.
    bad_rel = [(ln, s) for ln, s in occurrences if re.search(r"\bsrc_source_id\b", s)]
    assert not bad_rel, f"un-re-keyed src_source_id: {bad_rel}"

    # (c) the 7 tables key on source_entity_id — no aliased legacy <alias>.source_id column of a
    # re-keyed table. Locator (alias l / column source_index_locators.source_id) and the out-of-scope
    # events table keep their own source_id, so only the sources/metadata/text/gen/summaries aliases
    # (s/m/t/g/u) are forbidden.
    bad_col = [(ln, s) for ln, s in occurrences if re.search(r"\b[smtgu]\.source_id\b", s)]
    assert not bad_col, f"un-re-keyed <alias>.source_id on a 7-table: {bad_col}"

    # (d) any statement that SELECTs/filters a bare `source_id` column (not qualified, not the locator's)
    # against a re-keyed table without also referencing the locator is forbidden. Statements that touch
    # ONLY the 7 tables (no locator, no events) must never contain the bare token ``source_id`` except
    # as the locator column (which requires source_index_locators to be present).
    for ln, s in occurrences:
        touches_locator = "source_index_locators" in s
        touches_events = "source_intelligence_events" in s
        if touches_locator or touches_events:
            continue
        # pure 7-table statement: source_id must be fully absent (re-keyed to source_entity_id)
        assert not re.search(r"\bsource_id\b", s), f"bare source_id on pure 7-table stmt @L{ln}: {s}"


def test_guard2_rekey_uses_entity_key() -> None:
    """Positive half of the set-equality: every discovered 7-table statement that references an identity
    column references the durable entity key (source_entity_id / src_source_entity_id) or is a bare
    non-address statement (COUNT / generated_note_id / chunk_id / fts only)."""
    occurrences = _discover_execute_sql()
    for ln, s in occurrences:
        addresses_identity = re.search(r"\bsource_entity_id\b|\bsrc_source_entity_id\b", s)
        non_address = (
            re.search(r"\bCOUNT\(\*\)", s)
            or "generated_note_id" in s
            or "chunk_id" in s
            or "MAX(indexed_at)" in s
        )
        touches_locator = "source_index_locators" in s
        # every 7-table statement is either identity-keyed on the entity, a benign non-address op,
        # or a current-locator-bound resolution — never an un-re-keyed address statement.
        assert addresses_identity or non_address or touches_locator, (
            f"unclassified 7-table statement @L{ln}: {s}"
        )
