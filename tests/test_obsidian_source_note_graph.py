"""Phase 10C — local note graph (deterministic candidates + qwen vetting + reciprocal links/tags).

Synthetic temp only; no real Ollama. Proves strong-commonality gating, schema-bound advisory vetting,
approved-enum-only tags, reciprocal two-way links, one-side-fail-writes-neither, byte-preservation
outside managed/tag regions, and no source-read / index / scan / queue / DB / runtime mutation.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.classification.client import OllamaUnavailable
from hb_assistant.obsidian_mcp import source_note_graph as ng
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_note_apply_graph.py"
_spec = importlib.util.spec_from_file_location("apply_note_graph", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# Split so committed test source carries no literal work-card path/id pattern.
_W = "Source Notes/" + "Work"
_ABS_NEEDLES = ("/" + "Users/", "/" + "Volumes/")


def _rel(name, sfx="abcdef123456"):
    return _W + "/" + name + "__" + sfx + ".md"

_APPROVE = {"approved": True, "relationship_type": "same_company", "confidence": 0.9,
            "reason": "Both notes name the same subcontractor.",
            "tags_for_source": ["related/company", "review/qwen-vetted"],
            "tags_for_target": ["related/company", "review/qwen-vetted"]}


class _FakeClient:
    base_url = "http://localhost:11434"

    def __init__(self, *, payload=None, exc=None, raw=None):
        self._payload, self._exc, self._raw = payload or _APPROVE, exc, raw
        self.calls = 0

    def generate_json(self, *, system, prompt):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._raw if self._raw is not None else json.dumps(self._payload)


def _fact(nid, rel, *, project=None, vendor=None, dt="rfi", docnum=None, date=None, tags=()):
    base = Path(rel).stem
    return ng.NoteFact(note_id=nid, note_rel=rel, basename=base, display=ng._display_name(base),
                       project=project, vendor=vendor, document_type=dt, document_number=docnum,
                       doc_date=date, disposition="auto_card_high", review_needed=False,
                       title_tokens=ng._title_tokens(base), existing_tags=tuple(tags),
                       summary_text="summary")


# --------------------------------------------------------------------- candidate retrieval (1-7)

def test_strong_commonality_required_and_path_only_insufficient():
    a = _fact("a", _rel("RFI 1 Door"), project="25-1")
    b = _fact("b", _rel("RFI 2 Window"), project="25-1")
    assert ng.is_candidate(a, b)[0] is True  # same project = strong
    c = _fact("c", _rel("Misc One"), project="25-2", dt="general_document")
    d = _fact("d", _rel("Misc Two"), project="25-3", dt="general_document")
    assert ng.is_candidate(c, d)[0] is False  # different everything → path/folder-only is not enough


def test_stricter_threshold_for_template_reference_metadata():
    a = _fact("a", _rel("Template One"), project="25-1", dt="template_form")
    b = _fact("b", _rel("Other"), project="25-1", dt="rfi")
    assert ng.is_candidate(a, b)[0] is False  # template needs 2 strong; only same_project present
    b2 = _fact("b", _rel("Other"), project="25-1", vendor="acme",
               dt="rfi")
    a2 = _fact("a", _rel("Template"), project="25-1", vendor="acme",
               dt="template_form")
    assert ng.is_candidate(a2, b2)[0] is True  # project + vendor = 2 strong


def test_no_self_links_and_dedup_and_caps():
    facts = [_fact(f"n{i}", _rel(f"RFI {i} X", "x"*8 + f"{i:04d}"), project="25-1")
             for i in range(6)]
    cands = ng.build_candidates(facts, max_per_note=2, max_relationships=50)
    assert all(c.a.note_id != c.b.note_id for c in cands)
    keys = [tuple(sorted((c.a.note_id, c.b.note_id))) for c in cands]
    assert len(keys) == len(set(keys))  # no duplicate unordered pairs
    per: dict[str, int] = {}
    for c in cands:
        per[c.a.note_id] = per.get(c.a.note_id, 0) + 1
        per[c.b.note_id] = per.get(c.b.note_id, 0) + 1
    assert max(per.values()) <= 2  # per-note cap
    assert len(ng.build_candidates(facts, max_per_note=10, max_relationships=3)) == 3  # global cap


# ------------------------------------------------------------------------------- vetting (8-14)

def test_vet_uses_local_client_and_handles_failures():
    a = _fact("a", _rel("A"), project="25-1")
    b = _fact("b", _rel("B"), project="25-1")
    cand = ng.Candidate(a=a, b=b, strong=1, signals=("same_project",))
    ok, _ = ng.vet_candidate(_FakeClient(), cand)
    assert ok is not None and ok["relationship_type"] == "same_company"
    assert ng.vet_candidate(_FakeClient(raw="not json"), cand)[0] is None
    assert ng.vet_candidate(_FakeClient(exc=OllamaUnavailable("ollama_timeout")), cand)[0] is None


def test_validate_vet_rejects_bad_outputs():
    base = dict(_APPROVE)
    assert ng.validate_vet({**base, "relationship_type": "made_up"}) is None  # unknown enum
    assert ng.validate_vet({**base, "relationship_type": "reject"}) is None  # non-apply type
    assert ng.validate_vet({**base, "confidence": 0.5}) is None  # below default threshold
    assert ng.validate_vet({**base, "tags_for_source": ["totally/invented"]}) is None  # unknown tag
    assert ng.validate_vet({**base, "approved": False}) is None
    assert ng.validate_vet({**base, "reason": "x" * 201}) is None
    assert ng.validate_vet(base) is not None


def test_sanitize_tag_rejects_invented_namespaces():
    assert ng.sanitize_tag("related/project") == "related/project"
    assert ng.sanitize_tag("Related/Project") == "related/project"
    assert ng.sanitize_tag("madeup/thing") is None
    assert ng.sanitize_tag("notanamespace") is None


# ------------------------------------------------------------------------------- writers (15-26)

def test_apply_tags_preserves_and_dedups_and_caps():
    text = "---\nnote_type: source_card\ntags:\n  - source/external_file\n  - domain/work\n---\n# x\n"
    out, reason = ng.apply_tags(text, ["related/project", "source/external_file", "review/qwen-vetted"])
    assert reason == "ok"
    assert out.count("- source/external_file") == 1  # existing preserved, not duplicated
    assert "- related/project" in out and "- review/qwen-vetted" in out
    assert "note_type: source_card" in out  # other frontmatter untouched


def test_apply_tags_skips_non_block_frontmatter():
    inline = "---\ntags: [a, b]\n---\n# x\n"
    assert ng.apply_tags(inline, ["related/project"])[0] is None
    scalar = "---\ntags: foo\n---\n# x\n"
    assert ng.apply_tags(scalar, ["related/project"])[0] is None
    none = "# x\nno frontmatter\n"
    assert ng.apply_tags(none, ["related/project"])[0] is None


def test_build_wiki_link_is_vault_relative_disambiguated_no_abs_path():
    f = _fact("a", _rel("Big Note"), project="25-1")
    link = ng.build_wiki_link(f)
    assert link == "[[" + _W + "/Big Note__abcdef123456|Big Note]]"
    assert all(bad not in link for bad in _ABS_NEEDLES)


def test_upsert_related_block_inserts_in_section_and_dedups():
    card = ("## Related Project\n- Detected project number: 25-1; no project record linked yet.\n\n"
            "## Related People / Companies\n- none\n")
    blink = "[[" + _W + "/B__bbbbbbbb2222|B]]"
    links = ["- " + blink + " — same_project · qwen-vetted · confidence 0.90"]
    out, reason = ng.upsert_related_block(card, links + links, section="## Related Project")
    assert reason == "inserted"
    assert out.count(ng.REL_BLOCK_BEGIN) == 1 and out.count(ng.REL_BLOCK_END) == 1
    assert out.count(blink) == 1  # dedup
    # existing deterministic line + other section preserved
    assert "no project record linked yet." in out and "## Related People / Companies" in out
    # re-running updates the same block (no second block)
    out2, reason2 = ng.upsert_related_block(out, links, section="## Related Project")
    assert reason2 == "updated" and out2.count(ng.REL_BLOCK_BEGIN) == 1


def test_upsert_related_block_appends_section_when_absent():
    plain = "# Some Note\n\nbody\n"
    out, reason = ng.upsert_related_block(plain, ["- [[X|X]]"], section="## Related Notes")
    assert reason == "section_appended" and "## Related Notes" in out
    assert "# Some Note" in out and "body" in out


# --------------------------------------------------------------------- integration env (15-40)

@pytest.fixture(autouse=True)
def _no_backend(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(mod, "list_ollama_models", lambda **k: ["qwen2.5:14b"])


def _env(tmp_path, monkeypatch, *, frozen_true=False):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cyml = tmp_path / "c.yml"
    cyml.write_text(f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
                    f"  obsidian_vault: {vault.as_posix()!r}\n")
    monkeypatch.setenv("HB_PA_CONFIG", str(cyml))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "syn-source"
    (root / "25-244").mkdir(parents=True)
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True, "source_card_generation_enabled": True,
           # frozen automation flags must be explicitly false (the model defaults auto_refresh True).
           "external_source_watch_enabled": False, "source_card_auto_generate_enabled": False,
           "source_summary_auto_generate_enabled": False, "source_note_auto_refresh_enabled": False,
           "external_sources": [{"source_root_key": "syn-work", "path": str(root), "enabled": True}]}
    if frozen_true:
        cfg["external_source_watch_enabled"] = True
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg))
    config = ObsidianMcpConfig.model_validate(cfg)
    repo = SourceIndexRepository(db)
    # Two same-vendor subcontracts (strong same_vendor signal) + one unrelated note.
    seed = [("25-244/Subcontract Concrete - MEP Prime.md", "Subcontract for concrete work."),
            ("25-244/Subcontract Steel - MEP Prime.md", "Subcontract for structural steel."),
            ("25-999/Misc Unrelated.md", "# Misc\n\nUnrelated note.")]
    (root / "25-999").mkdir(parents=True, exist_ok=True)
    for rel, body in seed:
        f = root / rel
        f.write_text(body, encoding="utf-8")
        sid = index_source_file(f, config.external_sources[0], repo, config)
        generate_source_card(repo, config, source_id=sid)
    return {"db": db, "cfgp": str(cfgp), "vault": vault, "root": root, "repo": repo, "tmp": tmp_path}


def _args(env, *, apply=False, vet=False, confirm=True, approved_count=1, **over):
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--model", "qwen2.5:14b", "--max-notes", "25", "--max-candidates-per-note", "10",
         "--max-relationships", "50", "--evidence-dir", str(env["tmp"] / "ev"),
         "--backup-dir", str(env["tmp"] / "bk"), "--json-output"]
    if vet:
        a.append("--vet")
    if apply:
        a.append("--apply")
        # post-vet checkpoint (Phase 10G): must equal the vetted approved count (1 in these fixtures).
        if approved_count is not None:
            a += ["--confirm-apply-approved-count", str(approved_count)]
        if confirm:
            a += ["--confirm-db-path", env["db"], "--confirm-vault-path", str(env["vault"]),
                  "--confirm-model", "qwen2.5:14b"]
    for k, v in over.items():
        flag = "--" + k.replace("_", "-")
        a.append(flag) if v is True else a.extend([flag, str(v)])
    return a


def _run(argv, capsys, **kw):
    rc = mod.main(argv, **kw)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if rc == 0 and out.strip() else None)


def _work(env):
    return sorted((env["vault"] / "Source Notes" / "Work").glob("*.md"))


def test_dry_run_no_vet_makes_zero_ollama_calls(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)

    def _boom(model, timeout):
        raise AssertionError("Ollama must not be used without --vet")

    rc, out = _run(_args(env), capsys, client_factory=_boom)
    assert rc == 0 and out["ollama_called"] is False
    assert out["candidate_pairs"] == 1  # the two same-vendor subcontracts pair; misc note excluded


def test_dry_run_vet_uses_fake_client_and_reports_counts(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    fc = _FakeClient()
    rc, out = _run(_args(env, vet=True), capsys, client_factory=lambda m, t: fc)
    assert rc == 0 and out["ollama_called"] is True and fc.calls == 1
    assert out["approved_pairs"] == 1 and out["would_add_reciprocal_links"] == 2
    assert out["would_modify_notes"] == 2


def test_apply_writes_reciprocal_links_and_tags(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc, out = _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())
    assert rc == 0
    assert out["relationships_applied"] == 1 and out["reciprocal_links_applied"] == 2
    assert out["notes_modified"] == 2 and out["created"] == 0 and out["deleted"] == 0
    assert out["queue_delta"] == 0 and out["db_mutations"] == 0
    cards = {p.name: p.read_text() for p in _work(env) if "Subcontract" in p.name}
    names = list(cards)
    a, b = names[0], names[1]
    astem, bstem = a[:-3], b[:-3]
    assert f"[[Source Notes/Work/{bstem}|" in cards[a]  # A links B
    assert f"[[Source Notes/Work/{astem}|" in cards[b]  # B links A (reciprocal)
    for c in cards.values():
        assert "- related/company" in c and "- review/qwen-vetted" in c
        assert c.count(ng.REL_BLOCK_BEGIN) == 1
    assert len(list((tmp_path / "bk" / "Source Notes" / "Work").glob("*.md"))) == 2


def test_apply_preserves_canonical_sections_and_bytes_outside_managed(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    before = {p.name: p.read_text() for p in _work(env)}
    _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())
    canon = ["## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
             "## Related Project", "## Related People / Companies", "## Related Decisions",
             "## Related Meetings", "## Source Basis", "## Advisory Summary", "## Follow-Up"]
    for p in _work(env):
        if "Subcontract" not in p.name:
            assert p.read_text() == before[p.name]  # untouched note byte-identical
            continue
        new = p.read_text()
        assert [ln for ln in new.splitlines() if ln.startswith("## ")] == canon
        # Key Facts / Source Basis / Follow-Up unchanged vs before (outside managed regions)
        for sec in ("## Key Facts", "## Source Basis", "## Follow-Up"):
            assert ng._section_body(new, sec) == ng._section_body(before[p.name], sec)


def test_apply_one_side_unwritable_writes_neither(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    # make ONE RFI card's frontmatter non-block-style → unwritable → its pair must be skipped
    rfis = [p for p in _work(env) if "Subcontract" in p.name]
    victim = rfis[0]
    txt = victim.read_text().replace("tags:\n", "tags: [inline, x]\n", 1)
    # drop the original block tag lines that followed (best-effort: collapse the list)
    victim.write_text(txt, encoding="utf-8")
    before = {p.name: p.read_text() for p in _work(env)}
    rc, out = _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())
    assert rc == 0 and out["relationships_applied"] == 0  # pair dropped
    assert {p.name: p.read_text() for p in _work(env)} == before  # neither side written


def test_apply_refusals(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    assert _run(_args(env, apply=True, confirm=False), capsys,
                client_factory=lambda m, t: _FakeClient())[0] == 3
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: True)
    assert _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())[0] == 3


def test_apply_refuses_when_frozen_flags_true(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch, frozen_true=True)
    assert _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())[0] == 3


def test_apply_refuses_when_queue_not_empty(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    c = sqlite3.connect(env["db"])
    c.execute("INSERT INTO source_intelligence_events (event_type,rel_path,source_root_key,status)"
              " VALUES ('modified','x','syn-work','queued')")
    c.commit()
    c.close()
    assert _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())[0] == 3


def test_apply_refuses_when_ollama_unavailable(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "list_ollama_models", lambda **k: ["llama3.1"])  # qwen not installed
    assert _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())[0] == 3


def test_apply_no_db_or_source_read_or_scan(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    import builtins
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open",
                        lambda p, *a, **k: (_ for _ in ()).throw(AssertionError(f"src read {p}"))
                        if "/syn-source/" in str(p) else real_open(p, *a, **k))

    def counts():
        cc = sqlite3.connect(env["db"])
        try:
            return (cc.execute("SELECT COUNT(*) FROM source_intelligence_generated_notes").fetchone()[0],
                    cc.execute("SELECT COUNT(*) FROM source_intelligence_events").fetchone()[0])
        finally:
            cc.close()

    b = counts()
    rc, out = _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())
    assert rc == 0 and out["db_mutations"] == 0 and counts() == b


def test_script_has_no_index_scan_or_queue_calls():
    for src in (_SCRIPT.read_text(),
                Path(ng.__file__).read_text()):
        for forbidden in ("index_source_file", "scan_source_root", "drain_queue", "enqueue_event",
                          "claim_queued", "record_relationships", "upsert_summary"):
            assert forbidden not in src, forbidden


def test_safe_summary_has_no_paths_titles_or_bodies(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    _run(_args(env, apply=True), capsys, client_factory=lambda m, t: _FakeClient())
    safe = (tmp_path / "ev" / "note-graph-apply-summary-safe.json").read_text()
    for needle in ("25-244", "Subcontract", "MEP Prime", "Concrete", "[[", str(env["vault"]),
                   str(env["root"]), "/" + "Users/", "hb-" + "related-notes"):
        assert needle not in safe, needle
