"""Phase 10D — project folder parsing, procore resolution, and card identity enrichment. Synthetic only."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp import source_project_identity as spi

_TROP = [{"project_key": "tropical", "project_number": "23-435-01",
          "display_name": "23-435-01 - Tropical World Nursery Senior Living Facility",
          "procore_project_id": "2525840"},
         {"project_key": "caretta", "project_number": "23-101-00",
          "display_name": "23-101-00 - Caretta", "procore_project_id": "111"}]


class _FakeReadModel:
    def __init__(self, rows):
        self._rows = rows

    def factory(self, *, db_path=None):
        return self

    def build(self):
        return {"projects": self._rows}


@pytest.fixture
def _patch_readmodel(monkeypatch):
    def _install(rows):
        import hb_assistant.construction.analytics.project_summary_readmodel as rm
        fake = _FakeReadModel(rows)
        monkeypatch.setattr(rm, "ProjectSummaryReadModelService", lambda *, db_path=None: fake)
    return _install


# ------------------------------------------------------------------------------- folder parsing

def test_parse_project_folder_extracts_identity():
    p = spi.parse_project_folder(
        "/x/CloudStorage/Work/NAS - HB/Projects/2023/23-435-01 - Tropical/10_Preconstruction/a.pdf")
    assert p == {"project_number": "23-435-01", "short_name": "Tropical", "year": "2023",
                 "folder_name": "23-435-01 - Tropical"}


def test_parse_project_folder_rejects_nonmatching():
    assert spi.parse_project_folder("/x/Work/Random Folder/file.pdf") is None
    assert spi.parse_project_folder("/x/Projects/2023/Tropical/file.pdf") is None  # no NN-NNN-NN


# ------------------------------------------------------------------------------- resolver

def test_resolve_by_number(_patch_readmodel):
    _patch_readmodel(_TROP)
    ident = spi.resolve_project(number="23-435-01", name="Tropical", db_path="x")
    assert ident.project_key == "tropical" and ident.project_number == "23-435-01"
    assert ident.procore_project_id == "2525840"
    assert ident.project_name == "Tropical World Nursery Senior Living Facility"
    assert ident.project_acronym == "TWN"  # from the alias seed
    assert "folder_project_number" in ident.match_basis and "procore_project_key" in ident.match_basis


def test_resolve_by_name_alias_when_number_absent(_patch_readmodel):
    _patch_readmodel(_TROP)
    ident = spi.resolve_project(number=None, name="Tropical", db_path="x")
    assert ident.project_key == "tropical" and "alias_name" in ident.match_basis


def test_resolve_ambiguous_raises(_patch_readmodel):
    dup = _TROP + [{"project_key": "tropical-2", "project_number": "23-435-01",
                    "display_name": "dup", "procore_project_id": "999"}]
    _patch_readmodel(dup)
    with pytest.raises(spi.ProjectResolveError):
        spi.resolve_project(number="23-435-01", name="Tropical", db_path="x")


def test_resolve_missing_raises(_patch_readmodel):
    _patch_readmodel([{"project_key": "other", "project_number": "99-999-99",
                       "display_name": "Other", "procore_project_id": "5"}])
    with pytest.raises(spi.ProjectResolveError):
        spi.resolve_project(number="23-435-01", name="Nonexistent Zzz", db_path="x")


# ------------------------------------------------------------------------------- enrichment

_IDENT = spi.ProjectIdentity(
    project_number="23-435-01", project_key="tropical", procore_project_id="2525840",
    project_name="Tropical World Nursery Senior Living Facility", project_acronym="TWN",
    aliases=("TWN",), source_project_folder_name="23-435-01 - Tropical",
    match_basis=("folder_project_number", "procore_project_key"))


def test_identity_marker_round_trip():
    card = "\n".join([spi.identity_marker(_IDENT), "- Resolved project: x", spi.IDENTITY_END])
    parsed = spi.parse_identity_marker(card)
    assert parsed == {"project_number": "23-435-01", "project_key": "tropical",
                      "procore_project_id": "2525840"}


def test_enrich_inserts_block_under_related_project_byte_safe():
    card = ("---\nnote_type: source_card\n---\n# Source Card: x\n\n## Key Facts\n- a\n\n"
            "## Related Project\n- Detected project number: 23-435-01; no project record linked yet.\n\n"
            "## Related People / Companies\n- none\n")
    out, reason = spi.enrich_card_with_project_identity(card, _IDENT)
    assert reason == "inserted"
    assert out.count(spi.IDENTITY_BEGIN_PREFIX) == 1 and out.count(spi.IDENTITY_END) == 1
    assert 'project_key="tropical"' in out and 'procore_project_id="2525840"' in out
    # Key Facts + the People section + the detected line preserved
    assert "## Key Facts\n- a" in out and "## Related People / Companies" in out
    assert "no project record linked yet." in out
    assert spi.parse_identity_marker(out)["project_key"] == "tropical"
    assert ("/" + "Users/") not in out
    # idempotent update (no second block)
    out2, reason2 = spi.enrich_card_with_project_identity(out, _IDENT)
    assert reason2 == "updated" and out2.count(spi.IDENTITY_BEGIN_PREFIX) == 1


def test_enrich_refuses_without_related_project_section():
    assert spi.enrich_card_with_project_identity("# note\n\nbody\n", _IDENT)[0] is None
